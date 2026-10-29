"""Command-line interface for the local demo dispatcher."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .dispatcher import Dispatcher, DispatchError
from .models import TaskRequest
from .registry import WorkerRegistry


def _echo(payload: dict[str, Any]) -> dict[str, Any]:
    """Demonstration worker. It does not call an LLM or external service."""
    return {"worker": "demo.echo", "received": payload, "note": "demo output, not an investigation finding"}


def build_registry() -> WorkerRegistry:
    registry = WorkerRegistry()
    registry.register("demo.echo", _echo)
    return registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch a JSON task to an explicitly registered local worker")
    parser.add_argument("task_file", nargs="?", help="JSON task request file")
    parser.add_argument("--approve", action="store_true", help="approve this dispatch for this invocation")
    parser.add_argument("--audit", default="rea-events.jsonl", help="append-only JSONL event path")
    parser.add_argument("--list-workers", action="store_true", help="list built-in demo workers and exit")
    args = parser.parse_args(argv)
    registry = build_registry()
    if args.list_workers:
        print(json.dumps({"workers": registry.names()}, indent=2))
        return 0
    if not args.task_file:
        parser.error("task_file is required unless --list-workers is used")
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
