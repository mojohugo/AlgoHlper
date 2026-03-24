from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
        client = self._create_client()
        instructions = _build_system_instructions()
        prompt = _build_user_prompt(project=project, spec=spec, extra_instructions=request.instructions)
        payload = self._request_payload(client=client, instructions=instructions, prompt=prompt)

        attempts = request.repair_rounds + 1
        last_validation = GenerationValidationResult(skipped=not request.self_test)
        warnings: list[str] = []
        for attempt_index in range(attempts):
            artifacts = self._payload_to_artifacts(project=project, spec=spec, request=request, payload=payload)
            warnings = self._payload_warnings(payload)
            warnings.append("OpenAI 生成结果仍建议先编译并用样例自测，再开始大规模对拍。")
            if not request.self_test:
                return CodeGenerationResult(
                    provider=self.provider_name,
                    artifacts=artifacts,
                    warnings=warnings,
                    validation=GenerationValidationResult(skipped=True),
                )

            last_validation = self.validator.validate_cpp_assets(spec=spec, artifacts=artifacts)
            warnings.extend(last_validation.warnings)
            if not last_validation.errors:
                return CodeGenerationResult(
                    provider=self.provider_name,
                    artifacts=artifacts,
                    warnings=warnings,
                    validation=last_validation,
                )

            if attempt_index >= request.repair_rounds:
                break

            repair_prompt = _build_repair_prompt(
                project=project,
                spec=spec,
                previous_payload=payload,
                validation=last_validation,
                extra_instructions=request.instructions,
            )
            payload = self._request_payload(
                client=client,
                instructions=_build_repair_system_instructions(),
                prompt=repair_prompt,
            )

        error_message = "; ".join(last_validation.errors) if last_validation.errors else "未知自检失败"
        raise CodeGenerationError(f"生成资产未通过自检：{error_message}")

    def _create_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise CodeGenerationError(
                "未安装 openai SDK。请执行: python -m pip install -e .[openai]"
            ) from exc
        return OpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
            timeout=self.settings.openai_timeout_s,
        )

    def _request_payload(self, *, client: Any, instructions: str, prompt: str) -> dict:
        request_kwargs: dict[str, Any] = {
            "model": self.settings.openai_model,
            "input": _build_openai_input(instructions=instructions, prompt=prompt),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "duel_assets",
                    "schema": _build_duel_assets_json_schema(),
                    "strict": True,
                },
                "verbosity": "low",
            },
            "max_output_tokens": 4000,
        }
        reasoning_effort = _normalize_reasoning_effort(self.settings.openai_reasoning_effort)
        if reasoning_effort:
            request_kwargs["reasoning"] = {"effort": reasoning_effort}
        response = client.responses.create(**request_kwargs)
        raw_text = _extract_response_text(response)
        if not raw_text.strip():
            raise CodeGenerationError(
                f"OpenAI 返回空内容，未生成任何资产（{_describe_response_shape(response)}）"
            )
        return _extract_json_payload(raw_text)

    def _payload_to_artifacts(
        self,
        *,
        project: ProjectRecord,
        spec: ProblemSpec,
        request: GenerationRequest,
        payload: dict,
    ) -> dict[str, ArtifactRecord]:
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
        return artifacts

    @staticmethod
    def _payload_warnings(payload: dict) -> list[str]:
        notes = payload.get("notes")
        return [notes.strip()] if isinstance(notes, str) and notes.strip() else []


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


def _build_repair_system_instructions() -> str:
    return (
        "You repair previously generated duel assets for competitive-programming debugging. "
        "Return a single JSON object and nothing else. "
        "JSON keys: brute_cpp, generator_cpp, notes. "
        "Use the validation errors and compiler logs to fix the code. "
        "Keep both programs as complete C++17 programs. "
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


def _build_repair_prompt(
    *,
    project: ProjectRecord,
    spec: ProblemSpec,
    previous_payload: dict,
    validation: GenerationValidationResult,
    extra_instructions: str | None,
) -> str:
    payload = {
        "project_name": project.name,
        "problem_spec": spec.model_dump(mode="json"),
        "raw_problem_content": project.raw_problem_content or "",
        "previous_generation": previous_payload,
        "validation": validation.model_dump(mode="json"),
        "extra_instructions": extra_instructions or "",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _build_openai_input(*, instructions: str, prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "developer",
            "content": (
                f"{instructions} "
                "Return only the final JSON payload. "
                "Do not narrate your plan. "
                "Do not inspect the workspace. "
                "Do not wrap the JSON in markdown fences."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def _build_duel_assets_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "brute_cpp": {
                "type": "string",
                "description": "Complete C++17 brute-force solution used as the reference implementation.",
            },
            "generator_cpp": {
                "type": "string",
                "description": "Complete C++17 random test generator that accepts seed mode size arguments.",
            },
            "notes": {
                "type": "string",
                "description": "Short implementation notes or caveats for the generated assets.",
            },
        },
        "required": ["brute_cpp", "generator_cpp", "notes"],
    }


def _normalize_reasoning_effort(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized not in {"low", "medium", "high", "xhigh"}:
        return None
    if normalized == "xhigh":
        return "medium"
    return normalized


def _extract_response_text(response: Any) -> str:
    direct_text = getattr(response, "output_text", None)
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    if isinstance(response, str):
        stripped = response.strip()
        if not stripped:
            return ""
        if _looks_like_sse_payload(stripped):
            sse_text = _extract_text_from_sse(stripped)
            if sse_text.strip():
                return sse_text
        json_like = stripped.startswith("{") or stripped.startswith("[")
        if json_like:
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return response
            extracted = _extract_text_from_mapping(parsed)
            return extracted or response
        return response

    if isinstance(response, Mapping):
        return _extract_text_from_mapping(response)

    dumped = _safe_model_dump(response)
    if isinstance(dumped, Mapping):
        extracted = _extract_text_from_mapping(dumped)
        if extracted.strip():
            return extracted

    output = getattr(response, "output", None)
    extracted = _extract_text_from_output(output)
    if extracted.strip():
        return extracted

    content = getattr(response, "content", None)
    extracted = _extract_text_from_content(content)
    if extracted.strip():
        return extracted

    return ""


def _looks_like_sse_payload(raw_text: str) -> bool:
    return "event:" in raw_text and "data:" in raw_text


def _extract_text_from_sse(raw_text: str) -> str:
    deltas: list[str] = []
    completed_payload: Mapping[str, Any] | None = None

    for event_name, event_payload in _iter_sse_events(raw_text):
        if event_name == "response.output_text.done":
            text = event_payload.get("text")
            if isinstance(text, str) and text.strip():
                return text

        if event_name == "response.content_part.done":
            part = event_payload.get("part")
            if isinstance(part, Mapping):
                text = _extract_text_from_content([part])
                if text.strip():
                    return text

        if event_name == "response.output_item.done":
            item = event_payload.get("item")
            if isinstance(item, Mapping):
                text = _extract_text_from_output([item])
                if text.strip():
                    return text

        if event_name == "response.completed":
            completed_payload = event_payload

        delta = event_payload.get("delta")
        if event_name == "response.output_text.delta" and isinstance(delta, str):
            deltas.append(delta)

    if completed_payload is not None:
        completed_text = _extract_text_from_mapping(completed_payload)
        if completed_text.strip():
            return completed_text

    return "".join(deltas)


def _iter_sse_events(raw_text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    event_name: str | None = None
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_name, data_lines
        if not data_lines:
            event_name = None
            return
        raw_data = "\n".join(data_lines).strip()
        event_name_to_store = event_name or "message"
        event_name = None
        data_lines = []
        if not raw_data or raw_data == "[DONE]":
            return
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            return
        if isinstance(parsed, Mapping):
            events.append((event_name_to_store, dict(parsed)))

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if stripped.startswith(":"):
            continue
        if stripped.startswith("event:"):
            event_name = stripped.partition(":")[2].strip() or None
            continue
        if stripped.startswith("data:"):
            data_lines.append(stripped.partition(":")[2].lstrip())

    flush()
    return events


def _extract_text_from_mapping(payload: Mapping[str, Any]) -> str:
    direct_output_text = payload.get("output_text")
    if isinstance(direct_output_text, str) and direct_output_text.strip():
        return direct_output_text

    nested_response = payload.get("response")
    if isinstance(nested_response, Mapping):
        nested_text = _extract_text_from_mapping(nested_response)
        if nested_text.strip():
            return nested_text

    output_text = _extract_text_from_output(payload.get("output"))
    if output_text.strip():
        return output_text

    message = payload.get("message")
    if isinstance(message, Mapping):
        message_text = _extract_text_from_content(message.get("content"))
        if message_text.strip():
            return message_text

    content_text = _extract_text_from_content(payload.get("content"))
    if content_text.strip():
        return content_text

    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, Mapping):
                continue
            message_payload = choice.get("message")
            if isinstance(message_payload, Mapping):
                choice_text = _extract_text_from_content(message_payload.get("content"))
                if choice_text.strip():
                    return choice_text
            text = choice.get("text")
            if isinstance(text, str) and text.strip():
                return text

    direct_text = payload.get("text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text

    return ""


def _extract_text_from_output(output: Any) -> str:
    if not isinstance(output, list):
        return ""

    chunks: list[str] = []
    for item in output:
        mapping = item if isinstance(item, Mapping) else _safe_model_dump(item)
        if not isinstance(mapping, Mapping):
            continue
        content_text = _extract_text_from_content(mapping.get("content"))
        if content_text.strip():
            chunks.append(content_text)
    return "".join(chunks)


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    chunks: list[str] = []
    for part in content:
        mapping = part if isinstance(part, Mapping) else _safe_model_dump(part)
        if isinstance(mapping, Mapping):
            text = mapping.get("text")
            if isinstance(text, str) and text:
                chunks.append(text)
                continue
        text = getattr(part, "text", None)
        if isinstance(text, str) and text:
            chunks.append(text)
    return "".join(chunks)


def _safe_model_dump(value: Any) -> dict[str, Any] | None:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump(mode="python")
        except TypeError:
            dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dict(dumped)

    if isinstance(value, Mapping):
        return dict(value)

    value_dict = getattr(value, "__dict__", None)
    if isinstance(value_dict, dict):
        return dict(value_dict)

    return None


def _describe_response_shape(response: Any) -> str:
    if isinstance(response, str):
        summary = "响应类型=str"
        if _looks_like_sse_payload(response):
            return f"{summary}，收到 SSE 事件流"
        return f"{summary}，片段={_truncate_text(response)}"

    if isinstance(response, Mapping):
        keys = ", ".join(str(key) for key in list(response.keys())[:8])
        return f"响应类型=dict，keys=[{keys}]"

    dumped = _safe_model_dump(response)
    if isinstance(dumped, dict):
        keys = ", ".join(str(key) for key in list(dumped.keys())[:8])
        return f"响应类型={type(response).__name__}，keys=[{keys}]"

    return f"响应类型={type(response).__name__}"


def _truncate_text(value: str, limit: int = 160) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


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
        raise CodeGenerationError(
            f"OpenAI 返回不是合法 JSON：{exc}；内容片段：{_truncate_text(stripped)}"
        ) from exc
    if not isinstance(payload, dict):
        raise CodeGenerationError(f"OpenAI 返回 JSON 不是对象：{type(payload).__name__}")
    return payload


def build_fallback_compare_artifact() -> ArtifactRecord:
    return ArtifactRecord(type="compare", language="python", code=build_compare_script())


def build_fallback_readme_artifact(project: ProjectRecord, spec: ProblemSpec) -> ArtifactRecord:
    return ArtifactRecord(type="readme", language="markdown", code=build_repro_readme(project, spec))
