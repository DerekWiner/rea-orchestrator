import json
import time

import pytest

from rea_orchestrator import Dispatcher, DispatchError, TaskRequest, TaskStatus, WorkerRegistry


def request(**overrides):
    data = {"task_id": "task-1", "specialist": "test.echo", "input": {"question": "check a claim"}, "requires_approval": True, "timeout_seconds": 1}
    data.update(overrides)
    return TaskRequest.from_dict(data)


def registry(worker=lambda payload: {"echo": payload}):
    result = WorkerRegistry()
    result.register("test.echo", worker)
    return result


def test_approval_is_required_before_worker_runs():
    called = []
    with pytest.raises(DispatchError, match="approval required"):
        Dispatcher(registry(lambda payload: called.append(payload) or {})).dispatch(request())
    assert called == []


def test_success_returns_output_and_audit_events(tmp_path):
    audit = tmp_path / "events.jsonl"
    result = Dispatcher(registry(), audit_path=audit).dispatch(request(), approved=True)
    assert result.status is TaskStatus.COMPLETED
    assert result.output == {"echo": {"question": "check a claim"}}
    events = [json.loads(line) for line in audit.read_text().splitlines()]
    assert [event["event"] for event in events] == ["dispatch_started", "dispatch_finished"]


def test_unknown_worker_is_rejected():
    with pytest.raises(DispatchError, match="no explicitly registered worker"):
        Dispatcher(WorkerRegistry()).dispatch(request(), approved=True)


def test_worker_exception_becomes_failed_result():
    def broken(_payload):
        raise RuntimeError("synthetic failure")
    result = Dispatcher(registry(broken)).dispatch(request(), approved=True)
    assert result.status is TaskStatus.FAILED
    assert "synthetic failure" in result.error


def test_timeout_is_reported():
    def slow(_payload):
        time.sleep(0.2)
        return {"late": True}
    result = Dispatcher(registry(slow)).dispatch(request(timeout_seconds=0.05), approved=True)
    assert result.status is TaskStatus.TIMED_OUT


def test_successful_idempotency_key_reuses_result():
    calls = []
    dispatcher = Dispatcher(registry(lambda payload: calls.append(payload) or {"ok": True}))
    first = dispatcher.dispatch(request(idempotency_key="once"), approved=True)
    second = dispatcher.dispatch(request(task_id="task-2", idempotency_key="once"), approved=True)
    assert first == second
    assert len(calls) == 1


def test_task_rejects_unknown_fields_and_invalid_timeout():
    with pytest.raises(ValueError, match="unknown task field"):
        request(untrusted_code="print(1)")
    with pytest.raises(ValueError, match="timeout_seconds"):
        request(timeout_seconds=999)


def test_worker_output_must_be_json_serializable():
    result = Dispatcher(registry(lambda _payload: {"not_json": object()})).dispatch(request(), approved=True)
    assert result.status is TaskStatus.FAILED
    assert "not JSON serializable" in result.error
