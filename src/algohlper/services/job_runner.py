from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from algohlper.models import DuelRequest, GenerationRequest, ProjectRecord
from algohlper.services.codegen import CodeGenerationError, CompositeCodeGenerator
from algohlper.services.duel import DuelService
from algohlper.services.problem_parser import parse_problem_spec
from algohlper.services.storage import JsonFileStore
from algohlper.services.tasks import TaskTracker


@dataclass(slots=True)
class JobContext:
    store: JsonFileStore
    tasks: TaskTracker
    code_generator: CompositeCodeGenerator
    duel_service: DuelService


def run_parse_job(
    *,
    project_id: str,
    context: JobContext,
    existing_task_id: str | None = None,
):
    project = get_project_or_404(context.store, project_id)
    if not project.raw_problem_content:
        raise HTTPException(status_code=400, detail="Project has no problem text")
    task = prepare_task(
        context.tasks,
        project,
        context.store,
        task_type="parse",
        stage="normalize_problem",
        existing_task_id=existing_task_id,
    )
    try:
        context.tasks.append_log(task.id, "开始标准化题面", progress=10, current_stage="normalize_problem")
        spec = parse_problem_spec(project.raw_problem_content)
        context.tasks.append_log(task.id, "规则解析完成", progress=70, current_stage="extract_problem_spec")
        project.problem_spec = spec
        project.status = "parsed"
        context.store.save_project(project)
        task = context.tasks.complete(
            task.id,
            result={"problem_spec": spec.model_dump(mode="json")},
            current_stage="completed",
        )
        return task, spec
    except HTTPException:
        if existing_task_id:
            context.tasks.fail(task.id, "Project has no problem text", current_stage="parse_failed")
        raise
    except Exception as exc:
        context.tasks.fail(task.id, str(exc), current_stage="parse_failed")
        raise


def run_generate_job(
    *,
    project_id: str,
    payload: GenerationRequest,
    context: JobContext,
    existing_task_id: str | None = None,
):
    project = get_project_or_404(context.store, project_id)
    spec = project.problem_spec
    if spec is None:
        if not project.raw_problem_content:
            raise HTTPException(status_code=400, detail="Project has no problem text")
        spec = parse_problem_spec(project.raw_problem_content)
        project.problem_spec = spec
    task = prepare_task(
        context.tasks,
        project,
        context.store,
        task_type="starter_assets",
        stage="generate_templates",
        existing_task_id=existing_task_id,
    )
    try:
        context.tasks.append_log(task.id, "开始生成代码资产", progress=20, current_stage="generate_templates")
        generation_result = context.code_generator.generate(project, spec, payload)
        if payload.force_overwrite:
            project.artifacts.update(generation_result.artifacts)
        else:
            for artifact_name, artifact in generation_result.artifacts.items():
                project.artifacts.setdefault(artifact_name, artifact)
        project.status = "ready"
        context.store.save_project(project)
        result_payload = {
            "provider": generation_result.provider,
            "warnings": generation_result.warnings,
            "validation": generation_result.validation,
            "artifacts": generation_result.artifacts,
        }
        task = context.tasks.complete(
            task.id,
            result={
                "provider": generation_result.provider,
                "artifacts": list(generation_result.artifacts.keys()),
                "warnings": generation_result.warnings,
                "validation": generation_result.validation.model_dump(mode="json"),
            },
            current_stage="completed",
        )
        return task, result_payload
    except CodeGenerationError as exc:
        context.tasks.fail(task.id, str(exc), current_stage="generate_failed")
        if existing_task_id:
            return context.store.require_task(task.id), {"error": str(exc)}
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        context.tasks.fail(task.id, "Project has no problem text", current_stage="generate_failed")
        raise
    except Exception as exc:
        context.tasks.fail(task.id, str(exc), current_stage="generate_failed")
        raise


def run_duel_job(
    *,
    project_id: str,
    payload: DuelRequest,
    context: JobContext,
    existing_task_id: str | None = None,
):
    project = get_project_or_404(context.store, project_id)
    brute, generator, user_solution = require_duel_artifacts(project)
    task = prepare_task(
        context.tasks,
        project,
        context.store,
        task_type="duel",
        stage="compile",
        existing_task_id=existing_task_id,
    )
    try:
        context.tasks.append_log(task.id, "开始编译并执行对拍", progress=10, current_stage="compile")
        result = context.duel_service.duel(brute, generator, user_solution, payload)
        project.last_duel_result = result
        project.status = result.status
        context.store.save_project(project)
        if result.status == "failed":
            task = context.tasks.fail(task.id, result.summary, current_stage="duel_failed")
        else:
            task = context.tasks.complete(
                task.id,
                result=result.model_dump(mode="json"),
                current_stage=result.status,
            )
        return task, result
    except HTTPException:
        context.tasks.fail(task.id, "Missing duel artifacts", current_stage="duel_failed")
        raise
    except Exception as exc:
        context.tasks.fail(task.id, str(exc), current_stage="duel_failed")
        raise


def get_project_or_404(store: JsonFileStore, project_id: str) -> ProjectRecord:
    try:
        return store.require_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def attach_task(project: ProjectRecord, task_id: str, store: JsonFileStore) -> None:
    if task_id not in project.task_ids:
        project.task_ids.append(task_id)
        store.save_project(project)


def prepare_task(
    tasks: TaskTracker,
    project: ProjectRecord,
    store: JsonFileStore,
    *,
    task_type: str,
    stage: str,
    existing_task_id: str | None,
):
    if existing_task_id:
        return tasks.start(existing_task_id, current_stage=stage)
    task = tasks.create(project.id, task_type, stage)
    attach_task(project, task.id, store)
    return task


def require_duel_artifacts(project: ProjectRecord) -> tuple[str, str, str]:
    try:
        brute = project.artifacts["brute"].code
        generator = project.artifacts["generator"].code
        user_solution = project.artifacts["user_solution"].code
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Missing artifact: {exc.args[0]}") from exc
    return brute, generator, user_solution
