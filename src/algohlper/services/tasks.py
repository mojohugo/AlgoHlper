from __future__ import annotations

from algohlper.models import TaskLog, TaskRecord, TaskType
from algohlper.services.storage import JsonFileStore
from algohlper.utils import utc_now


class TaskTracker:
    def __init__(self, store: JsonFileStore):
        self.store = store

    def create(self, project_id: str, task_type: TaskType, stage: str) -> TaskRecord:
        task = TaskRecord(
            id=self.store._next_id("tsk"),
            project_id=project_id,
            type=task_type,
            status="running",
            current_stage=stage,
            progress=0,
        )
        self.store.save_task(task)
        return task

    def append_log(
        self,
        task_id: str,
        message: str,
        *,
        level: str = "info",
        progress: int | None = None,
        current_stage: str | None = None,
    ) -> TaskRecord:
        task = self.store.require_task(task_id)
        task.logs.append(TaskLog(level=level, message=message))
        if progress is not None:
            task.progress = progress
        if current_stage is not None:
            task.current_stage = current_stage
        self.store.save_task(task)
        return task

    def complete(
        self,
        task_id: str,
        *,
        result: dict | None = None,
        progress: int = 100,
        current_stage: str = "completed",
    ) -> TaskRecord:
        task = self.store.require_task(task_id)
        task.status = "completed"
        task.progress = progress
        task.current_stage = current_stage
        task.result = result
        task.finished_at = utc_now()
        self.store.save_task(task)
        return task

    def fail(self, task_id: str, error: str, *, current_stage: str) -> TaskRecord:
        task = self.store.require_task(task_id)
        task.status = "failed"
        task.error = error
        task.current_stage = current_stage
        task.finished_at = utc_now()
        task.logs.append(TaskLog(level="error", message=error))
        self.store.save_task(task)
        return task
