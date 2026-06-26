from __future__ import annotations

from typing import Any, Dict, Optional

from app.performance.task_queue import AnalysisTaskQueue


class ProgressTracker:
    """Aggregates task status for UI polling."""

    def __init__(self, queue: Optional[AnalysisTaskQueue] = None) -> None:
        self.queue = queue or AnalysisTaskQueue()

    def snapshot(self) -> Dict[str, Any]:
        tasks = self.queue.tasks()
        counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        for task in tasks:
            counts[task.status] = counts.get(task.status, 0) + 1
        total = len(tasks)
        done = counts.get("completed", 0) + counts.get("failed", 0)
        return {
            "total": total,
            "completed": counts.get("completed", 0),
            "running": counts.get("running", 0),
            "pending": counts.get("pending", 0),
            "failed": counts.get("failed", 0),
            "percent_complete": done / total if total else 0.0,
            "tasks": self.queue.snapshot(),
        }

    def is_finished(self) -> bool:
        snap = self.snapshot()
        return snap["total"] > 0 and snap["pending"] == 0 and snap["running"] == 0
