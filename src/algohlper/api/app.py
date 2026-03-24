from __future__ import annotations

from fastapi import FastAPI, HTTPException

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
)
from algohlper.services.codegen import CodeGenerationError, CompositeCodeGenerator
from algohlper.services.duel import DuelService
from algohlper.services.problem_parser import normalize_problem_text, parse_problem_spec
from algohlper.services.storage import JsonFileStore
from algohlper.services.tasks import TaskTracker
from algohlper.utils import utc_now


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    store = JsonFileStore(resolved_settings.data_dir)
    tasks = TaskTracker(store)
    duel_service = DuelService(resolved_settings)
    code_generator = CompositeCodeGenerator(resolved_settings)

    app = FastAPI(title="AlgoHlper API", version="0.1.0")
    app.state.settings = resolved_settings
    app.state.store = store
    app.state.tasks = tasks
    app.state.duel_service = duel_service
    app.state.code_generator = code_generator

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "time": utc_now().isoformat()}

    @app.post("/api/projects", response_model=ProjectRecord)
    def create_project(payload: CreateProjectRequest) -> ProjectRecord:
        return store.create_project(payload.name)

    @app.get("/api/projects", response_model=list[ProjectRecord])
    def list_projects() -> list[ProjectRecord]:
        return store.list_projects()

    @app.get("/api/projects/{project_id}", response_model=ProjectRecord)
    def get_project(project_id: str) -> ProjectRecord:
        return _get_project_or_404(store, project_id)

    @app.post("/api/projects/{project_id}/problem-text", response_model=ProjectRecord)
    def upsert_problem_text(project_id: str, payload: ProblemTextInput) -> ProjectRecord:
        project = _get_project_or_404(store, project_id)
        project.raw_problem_content = payload.content
        project.raw_problem_format = payload.format
        project.normalized_problem_content = normalize_problem_text(payload.content)
        project.problem_spec = None
        project.status = "draft"
        return store.save_project(project)

    @app.post("/api/projects/{project_id}/parse")
    def parse_project(project_id: str) -> dict:
        project = _get_project_or_404(store, project_id)
        if not project.raw_problem_content:
            raise HTTPException(status_code=400, detail="Project has no problem text")
        task = tasks.create(project.id, "parse", "normalize_problem")
        _attach_task(project, task.id, store)
        tasks.append_log(task.id, "开始标准化题面", progress=10, current_stage="normalize_problem")
        spec = parse_problem_spec(project.raw_problem_content)
        tasks.append_log(task.id, "规则解析完成", progress=70, current_stage="extract_problem_spec")
        project.problem_spec = spec
        project.status = "parsed"
        store.save_project(project)
        task = tasks.complete(
            task.id,
            result={"problem_spec": spec.model_dump(mode="json")},
            current_stage="completed",
        )
        return {"task": task, "problem_spec": spec}

    @app.get("/api/projects/{project_id}/problem-spec", response_model=ProblemSpec)
    def get_problem_spec(project_id: str) -> ProblemSpec:
        project = _get_project_or_404(store, project_id)
        if project.problem_spec is None:
            raise HTTPException(status_code=404, detail="Problem spec not found")
        return project.problem_spec

    @app.put("/api/projects/{project_id}/problem-spec", response_model=ProjectRecord)
    def update_problem_spec(project_id: str, spec: ProblemSpec) -> ProjectRecord:
        project = _get_project_or_404(store, project_id)
        project.problem_spec = spec
        project.status = "parsed"
        return store.save_project(project)

    @app.post("/api/projects/{project_id}/generate-artifacts")
    def generate_artifacts(project_id: str, payload: GenerationRequest) -> dict:
        project = _get_project_or_404(store, project_id)
        spec = project.problem_spec
        if spec is None:
            if not project.raw_problem_content:
                raise HTTPException(status_code=400, detail="Project has no problem text")
            spec = parse_problem_spec(project.raw_problem_content)
            project.problem_spec = spec
        task = tasks.create(project.id, "starter_assets", "generate_templates")
        _attach_task(project, task.id, store)
        tasks.append_log(task.id, "开始生成代码资产", progress=20, current_stage="generate_templates")
        try:
            generation_result = code_generator.generate(project, spec, payload)
        except CodeGenerationError as exc:
            task = tasks.fail(task.id, str(exc), current_stage="generate_failed")
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if payload.force_overwrite:
            project.artifacts.update(generation_result.artifacts)
        else:
            for artifact_name, artifact in generation_result.artifacts.items():
                project.artifacts.setdefault(artifact_name, artifact)
        project.status = "ready"
        store.save_project(project)
        task = tasks.complete(
            task.id,
            result={
                "provider": generation_result.provider,
                "artifacts": list(generation_result.artifacts.keys()),
                "warnings": generation_result.warnings,
            },
            current_stage="completed",
        )
        return {
            "task": task,
            "provider": generation_result.provider,
            "warnings": generation_result.warnings,
            "artifacts": generation_result.artifacts,
        }

    @app.post("/api/projects/{project_id}/generate-starter-artifacts")
    def generate_starter_artifacts(project_id: str) -> dict:
        return generate_artifacts(project_id, GenerationRequest(provider="template"))

    @app.post("/api/projects/{project_id}/artifacts", response_model=ProjectRecord)
    def upsert_artifact(project_id: str, payload: ArtifactUpsertRequest) -> ProjectRecord:
        project = _get_project_or_404(store, project_id)
        artifact = ArtifactRecord(type=payload.type, language=payload.language, code=payload.code)
        project.artifacts[payload.type] = artifact
        if payload.type == "user_solution":
            project.status = "ready"
        return store.save_project(project)

    @app.get("/api/projects/{project_id}/artifacts", response_model=dict[str, ArtifactRecord])
    def list_artifacts(project_id: str) -> dict[str, ArtifactRecord]:
        project = _get_project_or_404(store, project_id)
        return project.artifacts

    @app.post("/api/projects/{project_id}/duel")
    def duel_project(project_id: str, payload: DuelRequest) -> dict:
        project = _get_project_or_404(store, project_id)
        try:
            brute = project.artifacts["brute"].code
            generator = project.artifacts["generator"].code
            user_solution = project.artifacts["user_solution"].code
        except KeyError as exc:
            raise HTTPException(status_code=400, detail=f"Missing artifact: {exc.args[0]}") from exc
        task = tasks.create(project.id, "duel", "compile")
        _attach_task(project, task.id, store)
        tasks.append_log(task.id, "开始编译并执行对拍", progress=10, current_stage="compile")
        result = duel_service.duel(brute, generator, user_solution, payload)
        project.last_duel_result = result
        project.status = result.status
        store.save_project(project)
        if result.status == "failed":
            task = tasks.fail(task.id, result.summary, current_stage="duel_failed")
        else:
            task = tasks.complete(
                task.id,
                result=result.model_dump(mode="json"),
                current_stage=result.status,
            )
        return {"task": task, "result": result}

    @app.get("/api/projects/{project_id}/duel-result")
    def get_duel_result(project_id: str):
        project = _get_project_or_404(store, project_id)
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


def _get_project_or_404(store: JsonFileStore, project_id: str) -> ProjectRecord:
    try:
        return store.require_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _attach_task(project: ProjectRecord, task_id: str, store: JsonFileStore) -> None:
    if task_id not in project.task_ids:
        project.task_ids.append(task_id)
        store.save_project(project)


app = create_app()
