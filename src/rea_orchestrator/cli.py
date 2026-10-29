"""Command-line interface for local dispatch and capture normalization."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .dispatcher import Dispatcher, DispatchError
from .models import TaskRequest
from .registry import WorkerRegistry
from .upstream_rea import CaptureError, normalize_capture


def _echo(payload: dict[str, Any]) -> dict[str, Any]:
    """Demonstration worker. It does not call an LLM or external service."""
    return {"worker": "demo.echo", "received": payload, "note": "demo output, not an investigation finding"}


def build_registry() -> WorkerRegistry:
    registry = WorkerRegistry()
    registry.register("demo.echo", _echo)
    return registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch local REA tasks or normalize captured upstream REA output")
    parser.add_argument("task_file", nargs="?", help="JSON task request file")
    parser.add_argument("--approve", action="store_true", help="approve this dispatch for this invocation")
    parser.add_argument("--audit", default="rea-events.jsonl", help="append-only JSONL event path")
    parser.add_argument("--list-workers", action="store_true", help="list built-in demo workers and exit")
    parser.add_argument("--normalize-capture", metavar="FILE", help="normalize a captured upstream REA envelope into an REA Core record")
    parser.add_argument("--validate-core", action="store_true", help="validate normalized output using the installed rea-core package")
    args = parser.parse_args(argv)

    if args.validate_core and not args.normalize_capture:
        parser.error("--validate-core requires --normalize-capture")
    if args.normalize_capture:
        try:
            raw = json.loads(Path(args.normalize_capture).read_text(encoding="utf-8"))
            validator = None
            if args.validate_core:
                try:
                    from rea_core.validation import validate_document
                except ImportError as exc:
                    raise CaptureError("rea-core is not installed; install it or omit --validate-core") from exc
                validator = validate_document
            record = normalize_capture(raw, validate_record=validator)
        except (OSError, UnicodeError, json.JSONDecodeError, CaptureError) as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 2
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0

    registry = build_registry()
    if args.list_workers:
        print(json.dumps({"workers": registry.names()}, indent=2))
        return 0
    if not args.task_file:
        parser.error("task_file is required unless --list-workers or --normalize-capture is used")
    try:
        raw = json.loads(Path(args.task_file).read_text(encoding="utf-8"))
        request = TaskRequest.from_dict(raw)
        result = Dispatcher(registry, audit_path=args.audit).dispatch(request, approved=args.approve)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, DispatchError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.status.value == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
