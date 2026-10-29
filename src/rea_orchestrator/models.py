"""Validated, serializable task models."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class TaskStatus(str, Enum):
    PROPOSED = "proposed"
    BLOCKED = "blocked"
    DISPATCHED = "dispatched"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class TaskRequest:
    """A bounded request for one explicitly registered worker."""

    task_id: str
    specialist: str
    input: dict[str, Any]
    timeout_seconds: float = 10.0
    requires_approval: bool = True
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Any) -> "TaskRequest":
        if not isinstance(raw, dict):
            raise ValueError("task request must be a JSON object")
        allowed = {"task_id", "specialist", "input", "timeout_seconds", "requires_approval", "idempotency_key", "metadata"}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"unknown task field(s): {', '.join(sorted(unknown))}")
        task_id, specialist, payload = raw.get("task_id"), raw.get("specialist"), raw.get("input")
        if not isinstance(task_id, str) or not _ID.fullmatch(task_id):
            raise ValueError("task_id must be 1-200 safe identifier characters")
        if not isinstance(specialist, str) or not _ID.fullmatch(specialist):
            raise ValueError("specialist must be 1-200 safe identifier characters")
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        timeout = raw.get("timeout_seconds", 10.0)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise ValueError("timeout_seconds must be a number")
        if not 0.05 <= float(timeout) <= 300:
            raise ValueError("timeout_seconds must be between 0.05 and 300")
        approval = raw.get("requires_approval", True)
        if not isinstance(approval, bool):
            raise ValueError("requires_approval must be a boolean")
        idem = raw.get("idempotency_key")
        if idem is not None and (not isinstance(idem, str) or not idem or len(idem) > 200):
            raise ValueError("idempotency_key must be a non-empty string of at most 200 chars")
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a JSON object")
        return cls(task_id, specialist, payload, float(timeout), approval, idem, metadata)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
