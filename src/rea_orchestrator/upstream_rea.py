"""Normalize an explicitly captured upstream REA run into an REA Core record.

This module does not connect to MCP or execute analysis. It converts a local,
versioned capture envelope while preserving the distinction between tool output,
interpretation, and unsupported conclusions.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Callable

SCHEMA_URI = "https://rea.dev/schemas/investigation"
CAPTURE_VERSION = "1.0"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_TARGET_KINDS = {"file", "repository", "dataset", "model", "document", "binary", "service", "other"}
_RUN_STATUSES = {"completed", "failed", "skipped", "timed_out"}


class CaptureError(ValueError):
    """The capture envelope is malformed or contains unsupported references."""


def _required_text(value: Any, path: str, limit: int = 10000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CaptureError(f"{path} must be a non-empty string of at most {limit} characters")
    return value


def _timestamp(value: Any, path: str) -> str:
    text = _required_text(value, path, 100)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CaptureError(f"{path} must be an ISO 8601 timestamp") from exc
    return text


def _safe_id(value: Any, path: str) -> str:
    text = _required_text(value, path, 200)
    if not _SAFE_ID.fullmatch(text):
        raise CaptureError(f"{path} contains unsupported identifier characters")
    return text


def _sha256_json(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_capture(
    capture: Any,
    *,
    validate_record: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Convert a capture envelope to a REA Core v1 record.

    A caller may supply REA Core's validate_document function. If supplied,
    any validation issues reject the result. Without it, this function performs
    envelope checks only; callers must still run the REA Core validator.
    """
    if not isinstance(capture, dict):
        raise CaptureError("capture must be a JSON object")
    if capture.get("capture_version") != CAPTURE_VERSION:
        raise CaptureError(f"capture_version must be {CAPTURE_VERSION!r}")

    investigation_id = _safe_id(capture.get("investigation_id"), "investigation_id")
    created_at = _timestamp(capture.get("created_at"), "created_at")
    question = _required_text(capture.get("question"), "question")
    target = capture.get("target")
    provider = capture.get("provider")
    runs = capture.get("tool_runs")
    if not isinstance(target, dict):
        raise CaptureError("target must be an object")
    if not isinstance(provider, dict):
        raise CaptureError("provider must be an object")
    if not isinstance(runs, list):
        raise CaptureError("tool_runs must be an array")

    target_id = _safe_id(target.get("artifact_id", "target-1"), "target.artifact_id")
    target_kind = target.get("kind", "other")
    if target_kind not in _TARGET_KINDS:
        raise CaptureError("target.kind is unsupported")
    target_description = _required_text(target.get("description"), "target.description", 5000)
    artifact: dict[str, Any] = {
        "artifact_id": target_id,
        "kind": target_kind,
        "description": target_description,
        "trust_level": "user_supplied",
        "metadata": {"capture_version": CAPTURE_VERSION},
    }
    if isinstance(target.get("uri"), str) and target["uri"]:
        artifact["uri"] = target["uri"]
    if target.get("sha256") is not None:
        digest = _required_text(target["sha256"], "target.sha256", 64)
        if not re.fullmatch(r"[A-Fa-f0-9]{64}", digest):
            raise CaptureError("target.sha256 must be a 64-character hexadecimal digest")
        artifact["sha256"] = digest.lower()

    provider_name = _required_text(provider.get("name"), "provider.name", 500)
    provider_version = provider.get("version", "unknown")
    if not isinstance(provider_version, str) or not provider_version:
        raise CaptureError("provider.version must be a non-empty string")
    provider_revision = provider.get("source_revision")
    if provider_revision is not None and not isinstance(provider_revision, str):
        raise CaptureError("provider.source_revision must be a string when supplied")

    methods: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    evidence_by_run: dict[str, str] = {}
    capture_limitations = capture.get("limitations", [])
    if not isinstance(capture_limitations, list) or not all(isinstance(item, str) for item in capture_limitations):
        raise CaptureError("limitations must be an array of strings")
    limitations = list(capture_limitations)
    seen_runs: set[str] = set()

    for index, run in enumerate(runs):
        path = f"tool_runs[{index}]"
        if not isinstance(run, dict):
            raise CaptureError(f"{path} must be an object")
        run_id = _safe_id(run.get("run_id"), f"{path}.run_id")
        if run_id in seen_runs:
            raise CaptureError(f"duplicate tool run id {run_id!r}")
        seen_runs.add(run_id)
        tool_name = _required_text(run.get("tool_name"), f"{path}.tool_name", 500)
        status = run.get("status")
        if status not in _RUN_STATUSES:
            raise CaptureError(f"{path}.status must be one of {sorted(_RUN_STATUSES)}")
        observed_at = _timestamp(run.get("observed_at"), f"{path}.observed_at")
        method_id = f"method-{run_id}"
        execution_mode = run.get("execution_mode", "unknown")
        if execution_mode not in {"not_run", "static_analysis", "sandboxed", "controlled_environment", "external_service", "unknown"}:
            raise CaptureError(f"{path}.execution_mode is unsupported")
        network_access = run.get("network_access", False)
        if not isinstance(network_access, bool):
            raise CaptureError(f"{path}.network_access must be a boolean")
        methods.append({
            "method_id": method_id,
            "name": tool_name,
            "tool": provider_name,
            "tool_version": provider_version,
            "execution_mode": execution_mode,
            "network_access": network_access,
            "parameters": {"run_id": run_id, "status": status},
            "notes": "Captured upstream tool invocation. Metadata is descriptive and does not independently prove execution."
        })
        run_limitations = run.get("limitations", [])
        if not isinstance(run_limitations, list) or not all(isinstance(x, str) for x in run_limitations):
            raise CaptureError(f"{path}.limitations must be an array of strings")
        if status != "completed":
            limitations.append(f"Upstream tool run {run_id} ended with status {status}; it was not converted into evidence.")
            limitations.extend(f"{run_id}: {item}" for item in run_limitations)
            continue
        summary = run.get("result_summary")
        if not isinstance(summary, str) or not summary.strip():
            limitations.append(f"Upstream tool run {run_id} reported completion but had no result_summary.")
            limitations.extend(f"{run_id}: {item}" for item in run_limitations)
            continue

        evidence_id = f"evidence-{run_id}"
        raw_result = run.get("raw_result")
        evidence_item: dict[str, Any] = {
            "evidence_id": evidence_id,
            "evidence_type": "observation",
            "statement": f"Upstream tool output summary for {tool_name}: {summary}",
            "artifact_ids": [target_id],
            "method_ids": [method_id],
            "observed_at": observed_at,
            "source_reference": f"upstream-rea://tool-run/{run_id}",
            "confidence": 1.0,
            "limitations": run_limitations + [
                "This record captures a tool output summary; it does not independently establish the summary's truth."
            ],
            "metadata": {
                "upstream_run_id": run_id,
                "provider": provider_name,
                "raw_result_present": raw_result is not None
            }
        }
        if raw_result is not None:
            evidence_item["metadata"]["raw_result_sha256"] = _sha256_json(raw_result)
        evidence.append(evidence_item)
        evidence_by_run[run_id] = evidence_id

    findings_input = capture.get("findings", [])
    if not isinstance(findings_input, list):
        raise CaptureError("findings must be an array")
    findings: list[dict[str, Any]] = []
    seen_findings: set[str] = set()
    for index, item in enumerate(findings_input):
        path = f"findings[{index}]"
        if not isinstance(item, dict):
            raise CaptureError(f"{path} must be an object")
        finding_id = _safe_id(item.get("finding_id"), f"{path}.finding_id")
        if finding_id in seen_findings:
            raise CaptureError(f"duplicate finding id {finding_id!r}")
        seen_findings.add(finding_id)
        statement = _required_text(item.get("statement"), f"{path}.statement")
        refs = item.get("evidence_run_ids")
        if not isinstance(refs, list) or not refs:
            raise CaptureError(f"{path}.evidence_run_ids must be a non-empty array")
        if not all(isinstance(ref, str) for ref in refs):
            raise CaptureError(f"{path}.evidence_run_ids must contain strings")
        missing = [ref for ref in refs if ref not in evidence_by_run]
        if missing:
            raise CaptureError(f"{path} references runs without usable evidence: {missing}")
        confidence = item.get("confidence", 0.5)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise CaptureError(f"{path}.confidence must be between 0 and 1")
        status = item.get("status", "proposed")
        if status not in {"proposed", "supported", "contradicted", "independently_replicated", "unresolved"}:
            raise CaptureError(f"{path}.status is unsupported")
        finding: dict[str, Any] = {
            "finding_id": finding_id,
            "statement": statement,
            "evidence_ids": [evidence_by_run[ref] for ref in refs],
            "confidence": float(confidence),
            "status": status
        }
        if item.get("validation_notes") is not None:
            finding["validation_notes"] = _required_text(item["validation_notes"], f"{path}.validation_notes", 10000)
        findings.append(finding)

    if not evidence and not limitations:
        limitations.append("No completed upstream tool run yielded a usable result summary.")
    status = "completed" if evidence and all(run.get("status") == "completed" for run in runs) and not limitations else "in_progress"
    record: dict[str, Any] = {
        "schema": SCHEMA_URI,
        "schema_version": "1.0.0",
        "investigation_id": investigation_id,
        "created_at": created_at,
        "title": _required_text(capture.get("title", "Upstream REA investigation"), "title", 500),
        "question": question,
        "status": status,
        "domain": "software-reverse-engineering",
        "summary": "Normalized capture of upstream REA tool output. Review findings and limitations before relying on conclusions.",
        "artifacts": [artifact],
        "methods": methods,
        "evidence": evidence,
        "findings": findings,
        "limitations": limitations,
        "extensions": {
            "upstream_rea": {
                "provider": provider_name,
                "version": provider_version,
                "source_revision": provider_revision,
                "capture_version": CAPTURE_VERSION,
                "capture_sha256": _sha256_json(capture)
            }
        }
    }
    if validate_record is not None:
        issues = validate_record(record)
        if issues:
            rendered = "; ".join(str(issue) for issue in issues)
            raise CaptureError(f"REA Core validation failed: {rendered}")
    return record
