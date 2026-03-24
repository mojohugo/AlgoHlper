from __future__ import annotations

from algohlper.config import Settings
from algohlper.models import DuelRequest, GenerationRequest
from algohlper.services.job_runner import run_duel_job, run_generate_job, run_parse_job
from algohlper.services.task_queue import build_job_context
from algohlper.worker.celery_app import create_celery_app

celery_app = create_celery_app(Settings.from_env())


@celery_app.task(name="algohlper.parse_project")
def parse_project_task(*, project_id: str, task_id: str):
    context = build_job_context(Settings.from_env())
    run_parse_job(project_id=project_id, context=context, existing_task_id=task_id)


@celery_app.task(name="algohlper.generate_artifacts")
def generate_artifacts_task(*, project_id: str, task_id: str, payload: dict):
    context = build_job_context(Settings.from_env())
    run_generate_job(
        project_id=project_id,
        payload=GenerationRequest.model_validate(payload),
        context=context,
        existing_task_id=task_id,
    )


@celery_app.task(name="algohlper.duel_project")
def duel_project_task(*, project_id: str, task_id: str, payload: dict):
    context = build_job_context(Settings.from_env())
    run_duel_job(
        project_id=project_id,
        payload=DuelRequest.model_validate(payload),
        context=context,
        existing_task_id=task_id,
    )
