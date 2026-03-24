from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


@dataclass(slots=True)
class Settings:
    data_dir: Path
    cxx: str = "g++"
    compile_args: tuple[str, ...] = ("-O2", "-std=c++17", "-pipe")
    default_time_limit_ms: int = 1000
    max_output_bytes: int = 200_000
    task_queue_backend: str = "inprocess"
    inprocess_workers: int = 4
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_broker_db: int = 0
    redis_result_db: int = 1
    celery_worker_pool: str = "solo"
    codegen_provider: str = "template"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4"
    openai_base_url: str | None = None
    openai_timeout_s: float = 120.0
    openai_reasoning_effort: str = "medium"

    @classmethod
    def from_env(cls) -> "Settings":
        codex_config = _load_codex_config()
        codex_provider = _extract_codex_provider(codex_config)

        data_dir = Path(os.getenv("ALGOHLPER_DATA_DIR", ".algohlper_data")).resolve()
        cxx = os.getenv("ALGOHLPER_CXX", "g++")
        compile_args = tuple(
            arg
            for arg in os.getenv("ALGOHLPER_CXX_FLAGS", "-O2 -std=c++17 -pipe").split()
            if arg
        )
        default_time_limit_ms = int(os.getenv("ALGOHLPER_DEFAULT_TIME_LIMIT_MS", "1000"))
        max_output_bytes = int(os.getenv("ALGOHLPER_MAX_OUTPUT_BYTES", "200000"))
        task_queue_backend = os.getenv("ALGOHLPER_TASK_QUEUE_BACKEND", "inprocess")
        inprocess_workers = int(os.getenv("ALGOHLPER_INPROCESS_WORKERS", "4"))
        redis_host = os.getenv("ALGOHLPER_REDIS_HOST", "127.0.0.1")
        redis_port = int(os.getenv("ALGOHLPER_REDIS_PORT", "6379"))
        redis_password = os.getenv("ALGOHLPER_REDIS_PASSWORD")
        redis_broker_db = int(os.getenv("ALGOHLPER_REDIS_BROKER_DB", "0"))
        redis_result_db = int(os.getenv("ALGOHLPER_REDIS_RESULT_DB", "1"))
        celery_broker_url = os.getenv("ALGOHLPER_CELERY_BROKER_URL") or _build_redis_url(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_broker_db,
        )
        celery_result_backend = os.getenv("ALGOHLPER_CELERY_RESULT_BACKEND") or _build_redis_url(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_result_db,
        )
        default_pool = "solo" if sys.platform.startswith("win") else "prefork"
        celery_worker_pool = os.getenv("ALGOHLPER_CELERY_WORKER_POOL", default_pool)
        codegen_provider = os.getenv("ALGOHLPER_CODEGEN_PROVIDER", "template")
        openai_api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ALGOHLPER_OPENAI_API_KEY")
            or os.getenv("CODEX_API_KEY")
            or _read_codex_env_key(codex_provider)
        )
        openai_model = (
            os.getenv("ALGOHLPER_OPENAI_MODEL")
            or os.getenv("OPENAI_MODEL")
            or _safe_str(codex_config.get("model"))
            or "gpt-5.4"
        )
        openai_base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("ALGOHLPER_OPENAI_BASE_URL")
            or _safe_str(codex_provider.get("base_url"))
        )
        openai_timeout_s = float(os.getenv("ALGOHLPER_OPENAI_TIMEOUT_S", "120"))
        openai_reasoning_effort = (
            os.getenv("ALGOHLPER_OPENAI_REASONING_EFFORT")
            or os.getenv("OPENAI_REASONING_EFFORT")
            or _safe_str(codex_config.get("model_reasoning_effort"))
            or "medium"
        )
        return cls(
            data_dir=data_dir,
            cxx=cxx,
            compile_args=compile_args,
            default_time_limit_ms=default_time_limit_ms,
            max_output_bytes=max_output_bytes,
            task_queue_backend=task_queue_backend,
            inprocess_workers=inprocess_workers,
            celery_broker_url=celery_broker_url,
            celery_result_backend=celery_result_backend,
            redis_host=redis_host,
            redis_port=redis_port,
            redis_password=redis_password,
            redis_broker_db=redis_broker_db,
            redis_result_db=redis_result_db,
            celery_worker_pool=celery_worker_pool,
            codegen_provider=codegen_provider,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            openai_base_url=openai_base_url,
            openai_timeout_s=openai_timeout_s,
            openai_reasoning_effort=openai_reasoning_effort,
        )


def _load_codex_config() -> dict:
    config_path = Path.home() / ".codex" / "config.toml"
    if not config_path.exists():
        return {}
    try:
        with config_path.open("rb") as file:
            loaded = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _extract_codex_provider(config: dict) -> dict:
    provider_name = _safe_str(config.get("model_provider"))
    providers = config.get("model_providers")
    if not provider_name or not isinstance(providers, dict):
        return {}
    provider = providers.get(provider_name)
    return provider if isinstance(provider, dict) else {}


def _read_codex_env_key(provider: dict) -> str | None:
    env_key = _safe_str(provider.get("env_key"))
    if not env_key:
        return None
    return os.getenv(env_key)


def _safe_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _build_redis_url(*, host: str, port: int, password: str | None, db: int) -> str:
    auth = f":{quote(password, safe='')}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"
