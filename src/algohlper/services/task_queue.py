from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from algohlper.config import Settings
from algohlper.models import DuelRequest, GenerationRequest
from algohlper.services.codegen import CompositeCodeGenerator
from algohlper.services.duel import DuelService
from algohlper.services.job_runner import JobContext, run_duel_job, run_generate_job, run_parse_job
from algohlper.services.storage import JsonFileStore
from algohlper.services.tasks import TaskTracker


class TaskQueue(Protocol):
    backend_name: str

    def submit_parse(self, *, project_id: str, task_id: str) -> None: ...

    def submit_generate(self, *, project_id: str, task_id: str, payload: GenerationRequest) -> None: ...

    def submit_duel(self, *, project_id: str, task_id: str, payload: DuelRequest) -> None: ...


class InProcessTaskQueue:
    backend_name = "inprocess"

    def __init__(self, *, context: JobContext, max_workers: int = 4):
        self.context = context
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="algohlper")

    def submit_parse(self, *, project_id: str, task_id: str) -> None:
        self.executor.submit(
            lambda: run_parse_job(project_id=project_id, context=self.context, existing_task_id=task_id)
        )

    def submit_generate(self, *, project_id: str, task_id: str, payload: GenerationRequest) -> None:
        self.executor.submit(
            lambda: run_generate_job(
                project_id=project_id,
                payload=payload,
                context=self.context,
                existing_task_id=task_id,
            )
        )

    def submit_duel(self, *, project_id: str, task_id: str, payload: DuelRequest) -> None:
        self.executor.submit(
            lambda: run_duel_job(
                project_id=project_id,
                payload=payload,
                context=self.context,
                existing_task_id=task_id,
            )
        )


class CeleryTaskQueue:
    backend_name = "celery"

    def __init__(self, celery_app, fallback_queue: TaskQueue | None = None):
        self.celery_app = celery_app
        self.fallback_queue = fallback_queue

    def _send_task_with_fallback(self, *, task_name: str, kwargs: dict, fallback_submit) -> None:
        try:
            self.celery_app.send_task(task_name, kwargs=kwargs)
        except Exception:
            if self.fallback_queue is None:
                raise
            fallback_submit()

    def submit_parse(self, *, project_id: str, task_id: str) -> None:
        self._send_task_with_fallback(
            task_name="algohlper.parse_project",
            kwargs={"project_id": project_id, "task_id": task_id},
            fallback_submit=lambda: self.fallback_queue.submit_parse(
                project_id=project_id,
                task_id=task_id,
            ),
        )

    def submit_generate(self, *, project_id: str, task_id: str, payload: GenerationRequest) -> None:
        self._send_task_with_fallback(
            task_name="algohlper.generate_artifacts",
            kwargs={
                "project_id": project_id,
                "task_id": task_id,
                "payload": payload.model_dump(mode="json"),
            },
            fallback_submit=lambda: self.fallback_queue.submit_generate(
                project_id=project_id,
                task_id=task_id,
                payload=payload,
            ),
        )

    def submit_duel(self, *, project_id: str, task_id: str, payload: DuelRequest) -> None:
        self._send_task_with_fallback(
            task_name="algohlper.duel_project",
            kwargs={
                "project_id": project_id,
                "task_id": task_id,
                "payload": payload.model_dump(mode="json"),
            },
            fallback_submit=lambda: self.fallback_queue.submit_duel(
                project_id=project_id,
                task_id=task_id,
                payload=payload,
            ),
        )


def build_job_context(settings: Settings) -> JobContext:
    store = JsonFileStore(settings.data_dir)
    tasks = TaskTracker(store)
    code_generator = CompositeCodeGenerator(settings)
    duel_service = DuelService(settings)
    return JobContext(
        store=store,
        tasks=tasks,
        code_generator=code_generator,
        duel_service=duel_service,
    )


def create_task_queue(
    settings: Settings,
    *,
    store: JsonFileStore | None = None,
    tasks: TaskTracker | None = None,
    code_generator: CompositeCodeGenerator | None = None,
    duel_service: DuelService | None = None,
):
    backend = settings.task_queue_backend.lower()
    resolved_store = store or JsonFileStore(settings.data_dir)
    resolved_tasks = tasks or TaskTracker(resolved_store)
    context = JobContext(
        store=resolved_store,
        tasks=resolved_tasks,
        code_generator=code_generator or CompositeCodeGenerator(settings),
        duel_service=duel_service or DuelService(settings),
    )
    inprocess_queue = InProcessTaskQueue(context=context, max_workers=settings.inprocess_workers)

    if backend == "celery":
        try:
            from algohlper.worker.celery_app import create_celery_app

            celery_app = create_celery_app(settings)
            return CeleryTaskQueue(celery_app, fallback_queue=inprocess_queue)
        except ImportError:
            backend = "inprocess"

    return inprocess_queue
