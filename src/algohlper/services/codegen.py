from __future__ import annotations

import json
from dataclasses import dataclass

from algohlper.config import Settings
from algohlper.models import ArtifactRecord, GenerationRequest, GenerationValidationResult, ProblemSpec, ProjectRecord
from algohlper.services.asset_validation import AssetValidationService
from algohlper.services.starter_assets import build_compare_script, build_repro_readme, build_starter_artifacts


class CodeGenerationError(RuntimeError):
    pass


@dataclass(slots=True)
class CodeGenerationResult:
    provider: str
    artifacts: dict[str, ArtifactRecord]
    warnings: list[str]
    validation: GenerationValidationResult


class TemplateCodeGenerator:
    provider_name = "template"

    def generate(
        self,
        project: ProjectRecord,
        spec: ProblemSpec,
        request: GenerationRequest,
    ) -> CodeGenerationResult:
        artifacts = build_starter_artifacts(project, spec)
        filtered = {name: artifact for name, artifact in artifacts.items() if name in request.assets}
        return CodeGenerationResult(
            provider=self.provider_name,
            artifacts=filtered,
            warnings=["当前使用模板生成器，brute/gen 仍需要你或后续模型补全。"],
            validation=GenerationValidationResult(
                skipped=True,
                warnings=["模板生成器产物是占位模板，默认跳过编译/样例自检。"],
            ),
        )


class OpenAICodeGenerator:
    provider_name = "openai"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.validator = AssetValidationService(settings)

    def generate(
        self,
        project: ProjectRecord,
        spec: ProblemSpec,
        request: GenerationRequest,
    ) -> CodeGenerationResult:
        if not self.settings.openai_api_key:
            raise CodeGenerationError("OPENAI_API_KEY 未配置，无法使用 openai provider")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise CodeGenerationError(
                "未安装 openai SDK。请执行: python -m pip install -e .[openai]"
            ) from exc

        client = OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            timeout=self.settings.openai_timeout_s,
        )
        instructions = _build_system_instructions()
        prompt = _build_user_prompt(project=project, spec=spec, extra_instructions=request.instructions)
        response = client.responses.create(
            model=self.settings.openai_model,
            instructions=instructions,
            input=prompt,
        )
        raw_text = getattr(response, "output_text", "") or ""
        if not raw_text.strip():
            raise CodeGenerationError("OpenAI 返回空内容，未生成任何资产")
        payload = _extract_json_payload(raw_text)

        artifacts: dict[str, ArtifactRecord] = {}
        template_artifacts = build_starter_artifacts(project, spec)
        for asset_name in request.assets:
            if asset_name == "brute":
                code = payload.get("brute_cpp", "").strip()
                if not code:
                    raise CodeGenerationError("OpenAI 返回中缺少 brute_cpp")
                artifacts["brute"] = ArtifactRecord(type="brute", language="cpp", code=code)
            elif asset_name == "generator":
                code = payload.get("generator_cpp", "").strip()
                if not code:
                    raise CodeGenerationError("OpenAI 返回中缺少 generator_cpp")
                artifacts["generator"] = ArtifactRecord(type="generator", language="cpp", code=code)
            elif asset_name in {"compare", "readme"}:
                artifacts[asset_name] = template_artifacts[asset_name]

        notes = payload.get("notes")
        warnings = [notes.strip()] if isinstance(notes, str) and notes.strip() else []
        warnings.append("OpenAI 生成结果仍建议先编译并用样例自测，再开始大规模对拍。")
        validation = GenerationValidationResult(skipped=True)
        if request.self_test:
            validation = self.validator.validate_cpp_assets(spec=spec, artifacts=artifacts)
            warnings.extend(validation.warnings)
            if validation.errors:
                error_message = "; ".join(validation.errors)
                raise CodeGenerationError(f"生成资产未通过自检：{error_message}")
        return CodeGenerationResult(
            provider=self.provider_name,
            artifacts=artifacts,
            warnings=warnings,
            validation=validation,
        )


class CompositeCodeGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.template_generator = TemplateCodeGenerator()
        self.openai_generator = OpenAICodeGenerator(settings)

    def generate(
        self,
        project: ProjectRecord,
        spec: ProblemSpec,
        request: GenerationRequest,
    ) -> CodeGenerationResult:
        provider = request.provider
        if provider == "auto":
            provider = "openai" if self.settings.openai_api_key else self.settings.codegen_provider
            if provider == "auto":
                provider = "template"

        if provider == "template":
            return self.template_generator.generate(project, spec, request)
        if provider == "openai":
            try:
                return self.openai_generator.generate(project, spec, request)
            except CodeGenerationError as exc:
                if request.provider == "auto":
                    fallback = self.template_generator.generate(project, spec, request)
                    fallback.warnings.insert(0, f"OpenAI provider 不可用，已回退到模板生成器：{exc}")
                    return fallback
                raise
        raise CodeGenerationError(f"Unsupported provider: {provider}")


def _build_system_instructions() -> str:
    return (
        "You generate duel assets for competitive-programming debugging. "
        "Return a single JSON object and nothing else. "
        "JSON keys: brute_cpp, generator_cpp, notes. "
        "brute_cpp and generator_cpp must be complete C++17 programs. "
        "The brute solution must prioritize correctness on small inputs. "
        "The generator must accept command line arguments: seed mode size. "
        "Do not wrap JSON in markdown fences."
    )


def _build_user_prompt(
    *,
    project: ProjectRecord,
    spec: ProblemSpec,
    extra_instructions: str | None,
) -> str:
    payload = {
        "project_name": project.name,
        "problem_spec": spec.model_dump(mode="json"),
        "raw_problem_content": project.raw_problem_content or "",
        "extra_instructions": extra_instructions or "",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_json_payload(raw_text: str) -> dict:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise CodeGenerationError(f"OpenAI 返回不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise CodeGenerationError("OpenAI 返回 JSON 不是对象")
    return payload


def build_fallback_compare_artifact() -> ArtifactRecord:
    return ArtifactRecord(type="compare", language="python", code=build_compare_script())


def build_fallback_readme_artifact(project: ProjectRecord, spec: ProblemSpec) -> ArtifactRecord:
    return ArtifactRecord(type="readme", language="markdown", code=build_repro_readme(project, spec))
