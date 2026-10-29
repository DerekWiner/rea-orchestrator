"""A bounded dispatcher with approval gates and append-only event records."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .models import TaskRequest, TaskStatus
from .registry import WorkerRegistry


class DispatchError(RuntimeError):
    """Raised when a request cannot be dispatched safely."""


@dataclass(frozen=True)
class DispatchResult:
    task_id: str
    specialist: str
    status: TaskStatus
    started_at: str
    finished_at: str
    elapsed_seconds: float
    output: dict[str, Any] | None = None
    error: str | None = None
    idempotency_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Dispatcher:
    """Dispatch requests only to explicitly registered in-process workers.

    A timeout bounds how long the caller waits. Python threads cannot safely
    terminate a running worker, so this is not an isolation boundary. Use a
    separate process/container with OS limits for untrusted or expensive code.
    """

    def __init__(
        self,
        registry: WorkerRegistry,
        *,
        audit_path: str | Path | None = None,
        max_workers: int = 4,
        clock: Callable[[], str] = _now,
    ) -> None:
        if max_workers < 1 or max_workers > 32:
            raise ValueError("max_workers must be between 1 and 32")
        self.registry = registry
        self.audit_path = Path(audit_path) if audit_path is not None else None
        self.max_workers = max_workers
        self.clock = clock
        self._completed_by_key: dict[str, DispatchResult] = {}

    def _record(self, event: dict[str, Any]) -> None:
        if self.audit_path is None:
            return
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")

    def dispatch(self, request: TaskRequest, *, approved: bool = False) -> DispatchResult:
        if request.requires_approval and not approved:
            raise DispatchError("approval required before dispatch")
        worker = self.registry.get(request.specialist)
        if worker is None:
            raise DispatchError(f"no explicitly registered worker named {request.specialist!r}")
        if request.idempotency_key and request.idempotency_key in self._completed_by_key:
            prior = self._completed_by_key[request.idempotency_key]
            self._record({"event": "idempotency_replay", "task_id": request.task_id,
                          "idempotency_key": request.idempotency_key, "prior_task_id": prior.task_id,
                          "at": self.clock()})
            return prior

        started_at = self.clock()
        started = time.monotonic()
        self._record({"event": "dispatch_started", "task_id": request.task_id,
                      "specialist": request.specialist, "at": started_at,
                      "approved": approved, "timeout_seconds": request.timeout_seconds})
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="rea-worker")
        future = executor.submit(worker, dict(request.input))
        try:
            output = future.result(timeout=request.timeout_seconds)
            if not isinstance(output, dict):
                raise TypeError("worker must return a JSON-serializable object")
            # Ensure the output can be safely represented in the JSON audit stream.
            json.dumps(output, ensure_ascii=False)
            status, error = TaskStatus.COMPLETED, None
        except FutureTimeout:
            future.cancel()
            status, output, error = TaskStatus.TIMED_OUT, None, "worker exceeded caller wait timeout"
        except Exception as exc:  # worker errors are captured as task outcomes
            status, output, error = TaskStatus.FAILED, None, f"{type(exc).__name__}: {exc}"
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        result = DispatchResult(
            task_id=request.task_id, specialist=request.specialist, status=status,
            started_at=started_at, finished_at=self.clock(),
            elapsed_seconds=round(time.monotonic() - started, 6), output=output,
            error=error, idempotency_key=request.idempotency_key,
        )
        self._record({"event": "dispatch_finished", **result.to_dict()})
        if status == TaskStatus.COMPLETED and request.idempotency_key:
            self._completed_by_key[request.idempotency_key] = result
        return result
