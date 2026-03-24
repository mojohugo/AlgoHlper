from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from algohlper.utils import utc_now

ArtifactType = Literal["brute", "generator", "user_solution", "compare", "readme"]
TaskType = Literal["parse", "starter_assets", "duel"]
TaskStatus = Literal["queued", "running", "completed", "failed"]
GeneratorProvider = Literal["auto", "template", "openai"]


class ProblemSample(BaseModel):
    input: str
    output: str


class ProblemSpec(BaseModel):
    title: str = "Untitled Problem"
    statement: str = ""
    input_format: str = ""
    output_format: str = ""
    constraints: dict[str, str] = Field(default_factory=dict)
    samples: list[ProblemSample] = Field(default_factory=list)
    problem_type_guess: list[str] = Field(default_factory=list)
    special_notes: list[str] = Field(default_factory=list)
    parse_confidence: dict[str, float] = Field(default_factory=dict)


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ProblemTextInput(BaseModel):
    content: str = Field(min_length=1)
    format: Literal["text", "markdown", "latex"] = "markdown"


class ArtifactUpsertRequest(BaseModel):
    type: ArtifactType
    language: str = Field(min_length=1, max_length=50)
    code: str = Field(min_length=1)


class ArtifactRecord(BaseModel):
    type: ArtifactType
    language: str
    code: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class DuelRequest(BaseModel):
    rounds: int = Field(default=100, ge=1, le=5000)
    time_limit_ms: int = Field(default=1000, ge=10, le=60_000)
    memory_limit_mb: int = Field(default=256, ge=16, le=4096)
    generator_mode: list[str] = Field(default_factory=lambda: ["random", "edge", "small"])
    stop_on_first_fail: bool = True
    minimize_counterexample: bool = False
    seed_start: int = 1


class GenerationRequest(BaseModel):
    provider: GeneratorProvider = "auto"
    assets: list[Literal["brute", "generator", "compare", "readme"]] = Field(
        default_factory=lambda: ["brute", "generator", "compare", "readme"]
    )
    instructions: str | None = None
    force_overwrite: bool = True
    self_test: bool = True


class GenerationValidationResult(BaseModel):
    skipped: bool = False
    compile_logs: dict[str, str] = Field(default_factory=dict)
    generator_smoke_ok: bool = False
    sample_total: int = 0
    sample_passed: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class DuelFailure(BaseModel):
    round: int
    seed: int
    mode: str
    size: int
    reason: str
    input: str
    expected_output: str = ""
    actual_output: str = ""
    stderr: str = ""
    timed_out: bool = False
    user_exit_code: int | None = None
    brute_exit_code: int | None = None


class DuelResult(BaseModel):
    status: Literal["completed", "counterexample_found", "failed"]
    rounds_requested: int
    rounds_completed: int
    compile_logs: dict[str, str] = Field(default_factory=dict)
    failure: DuelFailure | None = None
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class TaskLog(BaseModel):
    time: datetime = Field(default_factory=utc_now)
    level: Literal["info", "warning", "error"] = "info"
    message: str


class TaskRecord(BaseModel):
    id: str
    project_id: str
    type: TaskType
    status: TaskStatus = "queued"
    progress: int = 0
    current_stage: str | None = None
    logs: list[TaskLog] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None


class ProjectRecord(BaseModel):
    id: str
    name: str
    status: str = "draft"
    raw_problem_content: str | None = None
    raw_problem_format: str | None = None
    normalized_problem_content: str | None = None
    problem_spec: ProblemSpec | None = None
    artifacts: dict[str, ArtifactRecord] = Field(default_factory=dict)
    task_ids: list[str] = Field(default_factory=list)
    last_duel_result: DuelResult | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
