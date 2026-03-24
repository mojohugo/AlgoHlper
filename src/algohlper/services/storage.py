from __future__ import annotations

import threading
import uuid
from pathlib import Path

from algohlper.models import ProjectRecord, TaskRecord
from algohlper.utils import utc_now


class JsonFileStore:
    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.RLock()
        self.projects_dir = root / "projects"
        self.tasks_dir = root / "tasks"
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str) -> ProjectRecord:
        with self._lock:
            project = ProjectRecord(id=self._next_id("prj"), name=name)
            self.save_project(project)
            return project

    def list_projects(self) -> list[ProjectRecord]:
        with self._lock:
            projects = [ProjectRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in self.projects_dir.glob("*.json")]
            return sorted(projects, key=lambda item: item.created_at, reverse=True)

    def save_project(self, project: ProjectRecord) -> ProjectRecord:
        with self._lock:
            project.updated_at = utc_now()
            self._atomic_write(self.projects_dir / f"{project.id}.json", project.model_dump_json(indent=2))
            return project

    def load_project(self, project_id: str) -> ProjectRecord | None:
        with self._lock:
            path = self.projects_dir / f"{project_id}.json"
            if not path.exists():
                return None
            return ProjectRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def require_project(self, project_id: str) -> ProjectRecord:
        project = self.load_project(project_id)
        if project is None:
            raise KeyError(f"Project {project_id} not found")
        return project

    def save_task(self, task: TaskRecord) -> TaskRecord:
        with self._lock:
            self._atomic_write(self.tasks_dir / f"{task.id}.json", task.model_dump_json(indent=2))
            return task

    def load_task(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            path = self.tasks_dir / f"{task_id}.json"
            if not path.exists():
                return None
            return TaskRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def require_task(self, task_id: str) -> TaskRecord:
        task = self.load_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found")
        return task

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)

    @staticmethod
    def _next_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"
