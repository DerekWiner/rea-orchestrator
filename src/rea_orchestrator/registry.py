"""Explicit allow-list registry for specialist handlers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Worker = Callable[[dict[str, Any]], dict[str, Any]]


class WorkerRegistry:
    """Maps explicit names to trusted in-process callables.

    Registration is an operator action. Task input cannot import modules, name
    arbitrary Python callables, or cause network discovery.
    """

    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}

    def register(self, name: str, worker: Worker) -> None:
        if not isinstance(name, str) or not name:
            raise ValueError("worker name must be a non-empty string")
        if name in self._workers:
            raise ValueError(f"worker {name!r} is already registered")
        if not callable(worker):
            raise TypeError("worker must be callable")
        self._workers[name] = worker

    def get(self, name: str) -> Worker | None:
        return self._workers.get(name)

    def names(self) -> list[str]:
        return sorted(self._workers)
