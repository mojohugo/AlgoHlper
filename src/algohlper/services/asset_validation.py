from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from algohlper.config import Settings
from algohlper.models import ArtifactRecord, GenerationValidationResult, ProblemSpec


@dataclass(slots=True)
class _RunResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    time_ms: int


class AssetValidationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def validate_cpp_assets(
        self,
        *,
        spec: ProblemSpec,
        artifacts: dict[str, ArtifactRecord],
    ) -> GenerationValidationResult:
        report = GenerationValidationResult()
        cpp_artifacts = {
            name: artifact
            for name, artifact in artifacts.items()
            if artifact.language.lower() == "cpp" and name in {"brute", "generator"}
        }
        if not cpp_artifacts:
            report.skipped = True
            report.warnings.append("没有可验证的 C++ 资产，已跳过自检。")
            return report

        with tempfile.TemporaryDirectory(prefix="algohlper-validate-") as temp_dir:
            workdir = Path(temp_dir)
            binaries: dict[str, Path] = {}
            for name, artifact in cpp_artifacts.items():
                binary_path = self._compile_cpp(workdir, name, artifact.code, report.compile_logs)
                if binary_path is None:
                    report.errors.append(f"{name}.cpp 编译失败")
                else:
                    binaries[name] = binary_path

            if report.errors:
                return report

            if "generator" in binaries:
                generator_result = self._run_program(
                    binaries["generator"],
                    ["1", "small", "3"],
                    stdin_text="",
                    time_limit_ms=min(self.settings.default_time_limit_ms, 1000),
                )
                if generator_result.timed_out:
                    report.errors.append("generator 自检超时")
                elif generator_result.exit_code != 0:
                    report.errors.append("generator 自检运行失败")
                elif not generator_result.stdout.strip():
                    report.errors.append("generator 自检未输出任何内容")
                else:
                    report.generator_smoke_ok = True

            if "brute" in binaries:
                if not spec.samples:
                    report.warnings.append("ProblemSpec 不含样例，跳过 brute 样例校验。")
                else:
                    for sample in spec.samples[:3]:
                        report.sample_total += 1
                        brute_result = self._run_program(
                            binaries["brute"],
                            [],
                            stdin_text=sample.input,
                            time_limit_ms=min(self.settings.default_time_limit_ms, 1000),
                        )
                        if brute_result.timed_out:
                            report.errors.append(f"brute 在样例 {report.sample_total} 上超时")
                            continue
                        if brute_result.exit_code != 0:
                            report.errors.append(f"brute 在样例 {report.sample_total} 上运行失败")
                            continue
                        if self._normalize_output(brute_result.stdout) != self._normalize_output(sample.output):
                            report.errors.append(f"brute 未通过样例 {report.sample_total}")
                            continue
                        report.sample_passed += 1

            return report

    def _compile_cpp(self, workdir: Path, name: str, code: str, compile_logs: dict[str, str]) -> Path | None:
        source_path = workdir / f"{name}.cpp"
        source_path.write_text(code, encoding="utf-8")
        suffix = ".exe" if os.name == "nt" else ""
        binary_path = workdir / f"{name}{suffix}"
        command = [self.settings.cxx, *self.settings.compile_args, str(source_path), "-o", str(binary_path)]
        result = subprocess.run(command, capture_output=True, text=True)
        compile_logs[name] = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            return None
        return binary_path

    def _run_program(
        self,
        executable: Path,
        args: list[str],
        *,
        stdin_text: str,
        time_limit_ms: int,
    ) -> _RunResult:
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                [str(executable), *args],
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=time_limit_ms / 1000,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            return _RunResult(
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                timed_out=False,
                time_ms=elapsed_ms,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return _RunResult(
                exit_code=-1,
                stdout=stdout,
                stderr=stderr,
                timed_out=True,
                time_ms=elapsed_ms,
            )

    @staticmethod
    def _normalize_output(text: str) -> str:
        lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)
