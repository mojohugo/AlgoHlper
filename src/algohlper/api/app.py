from __future__ import annotations

import importlib.util

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from algohlper.config import Settings
from algohlper.models import (
    ArtifactRecord,
    ArtifactUpsertRequest,
    CreateProjectRequest,
    DuelRequest,
    GenerationRequest,
    ProblemSpec,
    ProblemTextInput,
    ProjectRecord,
    QuickRunRequest,
    QuickRunResult,
    RuntimeInfo,
    RuntimeOpenAIInfo,
    RuntimeQueueInfo,
    RuntimeRedisInfo,
    RuntimeToolchainInfo,
)
from algohlper.services.job_runner import (
    JobContext,
    attach_task,
    get_project_or_404,
    require_duel_artifacts,
    run_duel_job,
    run_generate_job,
    run_parse_job,
)
from algohlper.services.codegen import CompositeCodeGenerator
from algohlper.services.duel import DuelService
from algohlper.services.problem_parser import normalize_problem_text
from algohlper.services.storage import JsonFileStore
from algohlper.services.task_queue import create_task_queue
from algohlper.services.tasks import TaskTracker
from algohlper.utils import utc_now


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    store = JsonFileStore(resolved_settings.data_dir)
    tasks = TaskTracker(store)
    code_generator = CompositeCodeGenerator(resolved_settings)
    duel_service = DuelService(resolved_settings)
    context = JobContext(
        store=store,
        tasks=tasks,
        code_generator=code_generator,
        duel_service=duel_service,
    )
    queue = create_task_queue(
        resolved_settings,
        store=store,
        tasks=tasks,
        code_generator=code_generator,
        duel_service=duel_service,
    )

    app = FastAPI(title="AlgoHlper API", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.store = store
    app.state.tasks = tasks
    app.state.context = context
    app.state.queue = queue
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "time": utc_now().isoformat()}

    @app.get("/api/runtime", response_model=RuntimeInfo)
    def get_runtime() -> RuntimeInfo:
        openai_sdk_installed = _module_available("openai")
        active_backend = getattr(queue, "backend_name", resolved_settings.task_queue_backend)
        return RuntimeInfo(
            api_time=utc_now(),
            openai=RuntimeOpenAIInfo(
                configured=bool(resolved_settings.openai_api_key),
                sdk_installed=openai_sdk_installed,
                provider_available=bool(resolved_settings.openai_api_key) and openai_sdk_installed,
                model=resolved_settings.openai_model,
                base_url=resolved_settings.openai_base_url,
                reasoning_effort=resolved_settings.openai_reasoning_effort,
            ),
            queue=RuntimeQueueInfo(
                requested_backend=resolved_settings.task_queue_backend,
                active_backend=active_backend,
                worker_pool=resolved_settings.celery_worker_pool,
            ),
            redis=RuntimeRedisInfo(
                host=resolved_settings.redis_host,
                port=resolved_settings.redis_port,
                password_configured=bool(resolved_settings.redis_password),
            ),
            toolchain=RuntimeToolchainInfo(
                cxx=resolved_settings.cxx,
                codegen_provider=resolved_settings.codegen_provider,
            ),
        )

    @app.post("/api/projects", response_model=ProjectRecord)
    def create_project(payload: CreateProjectRequest) -> ProjectRecord:
        return store.create_project(payload.name)

    @app.get("/api/projects", response_model=list[ProjectRecord])
    def list_projects() -> list[ProjectRecord]:
        return store.list_projects()

    @app.get("/api/projects/{project_id}", response_model=ProjectRecord)
    def get_project(project_id: str) -> ProjectRecord:
        return get_project_or_404(store, project_id)

    @app.post("/api/projects/{project_id}/problem-text", response_model=ProjectRecord)
    def upsert_problem_text(project_id: str, payload: ProblemTextInput) -> ProjectRecord:
        project = get_project_or_404(store, project_id)
        project.raw_problem_content = payload.content
        project.raw_problem_format = payload.format
        project.normalized_problem_content = normalize_problem_text(payload.content)
        project.problem_spec = None
        project.status = "draft"
        return store.save_project(project)

    @app.post("/api/projects/{project_id}/parse")
    def parse_project(project_id: str) -> dict:
        task, spec = run_parse_job(project_id=project_id, context=context)
        return {"task": task, "problem_spec": spec}

    @app.post("/api/projects/{project_id}/parse-async")
    def parse_project_async(project_id: str) -> dict:
        project = get_project_or_404(store, project_id)
        if not project.raw_problem_content:
            raise HTTPException(status_code=400, detail="Project has no problem text")
        task = tasks.create(project.id, "parse", "queued", status="queued")
        attach_task(project, task.id, store)
        queue.submit_parse(project_id=project_id, task_id=task.id)
        return {"task": task}

    @app.get("/api/projects/{project_id}/problem-spec", response_model=ProblemSpec)
    def get_problem_spec(project_id: str) -> ProblemSpec:
        project = get_project_or_404(store, project_id)
        if project.problem_spec is None:
            raise HTTPException(status_code=404, detail="Problem spec not found")
        return project.problem_spec

    @app.put("/api/projects/{project_id}/problem-spec", response_model=ProjectRecord)
    def update_problem_spec(project_id: str, spec: ProblemSpec) -> ProjectRecord:
        project = get_project_or_404(store, project_id)
        project.problem_spec = spec
        project.status = "parsed"
        return store.save_project(project)

    @app.post("/api/projects/{project_id}/generate-artifacts")
    def generate_artifacts(project_id: str, payload: GenerationRequest) -> dict:
        task, result_payload = run_generate_job(
            project_id=project_id,
            payload=payload,
            context=context,
        )
        return {"task": task, **result_payload}

    @app.post("/api/projects/{project_id}/generate-artifacts-async")
    def generate_artifacts_async(project_id: str, payload: GenerationRequest) -> dict:
        project = get_project_or_404(store, project_id)
        if project.problem_spec is None and not project.raw_problem_content:
            raise HTTPException(status_code=400, detail="Project has no problem text")
        task = tasks.create(project.id, "starter_assets", "queued", status="queued")
        attach_task(project, task.id, store)
        queue.submit_generate(project_id=project_id, task_id=task.id, payload=payload)
        return {"task": task}

    @app.post("/api/projects/{project_id}/generate-starter-artifacts")
    def generate_starter_artifacts(project_id: str) -> dict:
        return generate_artifacts(project_id, GenerationRequest(provider="template"))

    @app.post("/api/projects/{project_id}/artifacts", response_model=ProjectRecord)
    def upsert_artifact(project_id: str, payload: ArtifactUpsertRequest) -> ProjectRecord:
        project = get_project_or_404(store, project_id)
        artifact = ArtifactRecord(type=payload.type, language=payload.language, code=payload.code)
        project.artifacts[payload.type] = artifact
        if payload.type == "user_solution":
            project.status = "ready"
        return store.save_project(project)

    @app.get("/api/projects/{project_id}/artifacts", response_model=dict[str, ArtifactRecord])
    def list_artifacts(project_id: str) -> dict[str, ArtifactRecord]:
        project = get_project_or_404(store, project_id)
        return project.artifacts

    @app.post("/api/projects/{project_id}/duel")
    def duel_project(project_id: str, payload: DuelRequest) -> dict:
        task, result = run_duel_job(
            project_id=project_id,
            payload=payload,
            context=context,
        )
        return {"task": task, "result": result}

    @app.post("/api/projects/{project_id}/duel-async")
    def duel_project_async(project_id: str, payload: DuelRequest) -> dict:
        project = get_project_or_404(store, project_id)
        require_duel_artifacts(project)
        task = tasks.create(project.id, "duel", "queued", status="queued")
        attach_task(project, task.id, store)
        queue.submit_duel(project_id=project_id, task_id=task.id, payload=payload)
        return {"task": task}

    @app.post("/api/projects/{project_id}/run-user", response_model=QuickRunResult)
    def run_user_code(project_id: str, payload: QuickRunRequest) -> QuickRunResult:
        get_project_or_404(store, project_id)
        return duel_service.run_user_code(
            code=payload.code,
            input_text=payload.input,
            time_limit_ms=payload.time_limit_ms,
        )

    @app.get("/api/projects/{project_id}/duel-result")
    def get_duel_result(project_id: str):
        project = get_project_or_404(store, project_id)
        if project.last_duel_result is None:
            raise HTTPException(status_code=404, detail="Duel result not found")
        return project.last_duel_result

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str):
        try:
            return store.require_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


app = create_app()
