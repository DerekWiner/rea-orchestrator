import copy
import pytest

from rea_orchestrator.upstream_rea import CaptureError, normalize_capture


def fixture():
    return {
        "capture_version": "1.0",
        "investigation_id": "notes-feature-001",
        "created_at": "2026-10-29T00:00:00Z",
        "title": "Synthetic Notes feature trace",
        "question": "Which local code path handles the feature?",
        "target": {
            "artifact_id": "target-app",
            "kind": "repository",
            "description": "Synthetic fixture, not a real application",
            "uri": "file:///tmp/synthetic-notes",
            "sha256": "a" * 64
        },
        "provider": {
            "name": "morluto/rea",
            "version": "fixture-version",
            "source_revision": "fixture-commit"
        },
        "tool_runs": [{
            "run_id": "trace-feature",
            "tool_name": "analyze_javascript_application",
            "status": "completed",
            "observed_at": "2026-10-29T00:01:00Z",
            "execution_mode": "static_analysis",
            "network_access": False,
            "result_summary": "The fixture reports a renderer-to-preload IPC call.",
            "raw_result": {"nodes": ["renderer", "preload", "ipc"]},
            "limitations": ["Synthetic fixture output"]
        }],
        "findings": [{
            "finding_id": "ipc-path",
            "statement": "The captured tool summary reports a renderer-to-preload IPC path.",
            "evidence_run_ids": ["trace-feature"],
            "confidence": 0.7,
            "status": "proposed"
        }],
        "limitations": ["No live target was inspected."]
    }


def test_normalizes_tool_output_without_claiming_independent_truth():
    record = normalize_capture(fixture())
    assert record["schema_version"] == "1.0.0"
    assert record["evidence"][0]["evidence_type"] == "observation"
    assert record["evidence"][0]["metadata"]["raw_result_present"] is True
    assert record["evidence"][0]["metadata"]["raw_result_sha256"]
    assert record["findings"][0]["evidence_ids"] == ["evidence-trace-feature"]
    assert record["status"] == "in_progress"
    assert "No live target" in record["limitations"][0]


def test_rejects_finding_that_references_failed_or_missing_evidence():
    capture = fixture()
    capture["tool_runs"][0]["status"] = "failed"
    with pytest.raises(CaptureError, match="without usable evidence"):
        normalize_capture(capture)


def test_rejects_duplicate_run_ids():
    capture = fixture()
    capture["tool_runs"].append(copy.deepcopy(capture["tool_runs"][0]))
    with pytest.raises(CaptureError, match="duplicate tool run id"):
        normalize_capture(capture)


def test_rejects_invalid_target_hash():
    capture = fixture()
    capture["target"]["sha256"] = "not-a-hash"
    with pytest.raises(CaptureError, match="64-character hexadecimal"):
        normalize_capture(capture)


def test_validator_hook_rejects_structurally_invalid_record():
    def validator(record):
        return ["fixture validation failure"]
    with pytest.raises(CaptureError, match="REA Core validation failed"):
        normalize_capture(fixture(), validate_record=validator)


def test_capture_hash_is_deterministic():
    first = normalize_capture(fixture())
    second = normalize_capture(fixture())
    assert first["extensions"]["upstream_rea"]["capture_sha256"] == second["extensions"]["upstream_rea"]["capture_sha256"]


def test_result_summary_is_required_to_create_evidence():
    capture = fixture()
    capture["tool_runs"][0]["result_summary"] = ""
    capture["findings"] = []
    record = normalize_capture(capture)
    assert record["evidence"] == []
    assert any("no result_summary" in item for item in record["limitations"])



def test_normalized_record_passes_real_rea_core_validator():
    from rea_core.validation import validate_document

    record = normalize_capture(fixture(), validate_record=validate_document)
    assert validate_document(record) == []



def test_cli_normalizes_fixture_and_validates_with_core(capsys):
    from pathlib import Path
    from rea_orchestrator.cli import main

    fixture_path = Path(__file__).parents[1] / "examples" / "upstream-rea-capture.json"
    result = main(["--normalize-capture", str(fixture_path), "--validate-core"])
    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "1.0.0"
    assert output["extensions"]["upstream_rea"]["capture_sha256"]


def test_cli_rejects_core_validation_without_capture(capsys):
    from rea_orchestrator.cli import main

    with pytest.raises(SystemExit) as error:
        main(["--validate-core", "--list-workers"])
    assert error.value.code == 2
