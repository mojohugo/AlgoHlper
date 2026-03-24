from __future__ import annotations

from algohlper.config import Settings


def create_celery_app(settings: Settings | None = None):
    try:
        from celery import Celery
    except ImportError as exc:
        raise ImportError("Celery 未安装。请执行: python -m pip install -e .[queue]") from exc

    resolved = settings or Settings.from_env()
    app = Celery(
        "algohlper",
        broker=resolved.celery_broker_url,
        backend=resolved.celery_result_backend,
        include=["algohlper.worker.tasks"],
    )
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        worker_prefetch_multiplier=1,
    )
    return app
