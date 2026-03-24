from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    data_dir: Path
    cxx: str = "g++"
    compile_args: tuple[str, ...] = ("-O2", "-std=c++17", "-pipe")
    default_time_limit_ms: int = 1000
    max_output_bytes: int = 200_000
    codegen_provider: str = "template"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4"
    openai_base_url: str | None = None
    openai_timeout_s: float = 120.0
    openai_reasoning_effort: str = "medium"

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("ALGOHLPER_DATA_DIR", ".algohlper_data")).resolve()
        cxx = os.getenv("ALGOHLPER_CXX", "g++")
        compile_args = tuple(
            arg
            for arg in os.getenv("ALGOHLPER_CXX_FLAGS", "-O2 -std=c++17 -pipe").split()
            if arg
        )
        default_time_limit_ms = int(os.getenv("ALGOHLPER_DEFAULT_TIME_LIMIT_MS", "1000"))
        max_output_bytes = int(os.getenv("ALGOHLPER_MAX_OUTPUT_BYTES", "200000"))
        codegen_provider = os.getenv("ALGOHLPER_CODEGEN_PROVIDER", "template")
        openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ALGOHLPER_OPENAI_API_KEY")
        openai_model = os.getenv("ALGOHLPER_OPENAI_MODEL", "gpt-5.4")
        openai_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("ALGOHLPER_OPENAI_BASE_URL")
        openai_timeout_s = float(os.getenv("ALGOHLPER_OPENAI_TIMEOUT_S", "120"))
        openai_reasoning_effort = os.getenv("ALGOHLPER_OPENAI_REASONING_EFFORT", "medium")
        return cls(
            data_dir=data_dir,
            cxx=cxx,
            compile_args=compile_args,
            default_time_limit_ms=default_time_limit_ms,
            max_output_bytes=max_output_bytes,
            codegen_provider=codegen_provider,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            openai_base_url=openai_base_url,
            openai_timeout_s=openai_timeout_s,
            openai_reasoning_effort=openai_reasoning_effort,
        )
