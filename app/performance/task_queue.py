from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AnalysisTask:
    name: str
    fingerprint: str = ""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: Any = None

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or time.time()
        start = self.started_at or self.created_at
        return max(0.0, end - start)


class AnalysisTaskQueue:
    """In-memory task queue with pending/running/completed/failed status."""

    def __init__(self) -> None:
        self._tasks: Dict[str, AnalysisTask] = {}

    def enqueue(self, name: str, fingerprint: str = "") -> AnalysisTask:
        task = AnalysisTask(name=name, fingerprint=fingerprint)
        self._tasks[task.task_id] = task
        return task

    def mark_running(self, task_id: str) -> None:
        task = self._tasks[task_id]
        task.status = "running"
        task.started_at = time.time()

    def mark_completed(self, task_id: str, result: Any = None) -> None:
        task = self._tasks[task_id]
        task.status = "completed"
        task.completed_at = time.time()
        task.result = result

    def mark_failed(self, task_id: str, exc: BaseException) -> None:
        task = self._tasks[task_id]
        task.status = "failed"
        task.completed_at = time.time()
        task.error = str(exc)

    def get(self, task_id: str) -> AnalysisTask:
        return self._tasks[task_id]

    def tasks(self) -> list[AnalysisTask]:
        return list(self._tasks.values())

    def snapshot(self) -> Dict[str, Any]:
        return {
            task.task_id: {
                "name": task.name,
                "status": task.status,
                "fingerprint": task.fingerprint,
                "duration_seconds": task.duration_seconds,
                "error": task.error,
            }
            for task in self.tasks()
        }
