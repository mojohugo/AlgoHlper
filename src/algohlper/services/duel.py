from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from algohlper.config import Settings
from algohlper.models import DuelFailure, DuelRequest, DuelResult


@dataclass(slots=True)
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    time_ms: int
    timed_out: bool = False


class DuelService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def duel(self, brute_code: str, generator_code: str, user_code: str, request: DuelRequest) -> DuelResult:
        warnings = [
            "当前版本使用本地 subprocess 执行，memory_limit_mb 仅保留在接口层，尚未真正强制。",
            "当前版本未实现 counterexample minimization。",
        ]
        with tempfile.TemporaryDirectory(prefix="algohlper-duel-") as temp_dir:
            workdir = Path(temp_dir)
            compile_logs: dict[str, str] = {}
            brute_bin = self._compile_cpp(workdir, "brute", brute_code, compile_logs)
            if brute_bin is None:
                return DuelResult(
                    status="failed",
                    rounds_requested=request.rounds,
                    rounds_completed=0,
                    compile_logs=compile_logs,
                    summary="brute.cpp 编译失败",
                    warnings=warnings,
                )
            generator_bin = self._compile_cpp(workdir, "gen", generator_code, compile_logs)
            if generator_bin is None:
                return DuelResult(
                    status="failed",
                    rounds_requested=request.rounds,
                    rounds_completed=0,
                    compile_logs=compile_logs,
                    summary="gen.cpp 编译失败",
                    warnings=warnings,
                )
            user_bin = self._compile_cpp(workdir, "main", user_code, compile_logs)
            if user_bin is None:
                return DuelResult(
                    status="failed",
                    rounds_requested=request.rounds,
                    rounds_completed=0,
                    compile_logs=compile_logs,
                    summary="main.cpp 编译失败",
                    warnings=warnings,
                )

            first_failure: DuelFailure | None = None
            rounds_completed = 0
            modes = request.generator_mode or ["random"]
            for round_index in range(request.rounds):
                round_no = round_index + 1
                seed = request.seed_start + round_index
                mode = modes[round_index % len(modes)]
                size = self._choose_size(round_no, request.rounds)
                generator_result = self._run_program(
                    generator_bin,
                    [str(seed), mode, str(size)],
                    stdin_text="",
                    time_limit_ms=min(request.time_limit_ms, self.settings.default_time_limit_ms),
                )
                if generator_result.timed_out or generator_result.exit_code != 0:
                    return DuelResult(
                        status="failed",
                        rounds_requested=request.rounds,
                        rounds_completed=rounds_completed,
                        compile_logs=compile_logs,
                        summary="数据生成器运行失败",
                        warnings=warnings,
                        failure=DuelFailure(
                            round=round_no,
                            seed=seed,
                            mode=mode,
                            size=size,
                            reason="generator_runtime_error",
                            input="",
                            stderr=generator_result.stderr,
                            timed_out=generator_result.timed_out,
                        ),
                    )
                input_text = generator_result.stdout
                brute_result = self._run_program(
                    brute_bin,
                    [],
                    stdin_text=input_text,
                    time_limit_ms=request.time_limit_ms,
                )
                if brute_result.timed_out or brute_result.exit_code != 0:
                    return DuelResult(
                        status="failed",
                        rounds_requested=request.rounds,
                        rounds_completed=rounds_completed,
                        compile_logs=compile_logs,
                        summary="参考解运行失败，当前对拍结果不可信",
                        warnings=warnings,
                        failure=DuelFailure(
                            round=round_no,
                            seed=seed,
                            mode=mode,
                            size=size,
                            reason="brute_runtime_error",
                            input=input_text,
                            stderr=brute_result.stderr,
                            timed_out=brute_result.timed_out,
                            brute_exit_code=brute_result.exit_code,
                        ),
                    )
                user_result = self._run_program(
                    user_bin,
                    [],
                    stdin_text=input_text,
                    time_limit_ms=request.time_limit_ms,
                )
                rounds_completed = round_no
                failure = self._detect_failure(
                    round_no=round_no,
                    seed=seed,
                    mode=mode,
                    size=size,
                    input_text=input_text,
                    brute_result=brute_result,
                    user_result=user_result,
                )
                if failure is None:
                    continue
                if first_failure is None:
                    first_failure = failure
                if request.stop_on_first_fail:
                    break

            if first_failure is not None:
                return DuelResult(
                    status="counterexample_found",
                    rounds_requested=request.rounds,
                    rounds_completed=rounds_completed,
                    compile_logs=compile_logs,
                    failure=first_failure,
                    summary="发现首个失败样例",
                    warnings=warnings,
                )
            return DuelResult(
                status="completed",
                rounds_requested=request.rounds,
                rounds_completed=rounds_completed,
                compile_logs=compile_logs,
                summary="本轮对拍未发现失败样例",
                warnings=warnings,
            )

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
    ) -> ExecutionResult:
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
            return ExecutionResult(
                exit_code=completed.returncode,
                stdout=self._truncate_output(completed.stdout),
                stderr=self._truncate_output(completed.stderr),
                time_ms=elapsed_ms,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return ExecutionResult(
                exit_code=-1,
                stdout=self._truncate_output(stdout),
                stderr=self._truncate_output(stderr),
                time_ms=elapsed_ms,
                timed_out=True,
            )

    def _truncate_output(self, content: str) -> str:
        if len(content) <= self.settings.max_output_bytes:
            return content
        suffix = "\n[truncated by AlgoHlper]\n"
        return content[: self.settings.max_output_bytes] + suffix

    @staticmethod
    def _choose_size(round_no: int, total_rounds: int) -> int:
        threshold_small = max(1, int(total_rounds * 0.2))
        threshold_medium = max(threshold_small + 1, int(total_rounds * 0.7))
        if round_no <= threshold_small:
            return 1 + ((round_no - 1) % 5)
        if round_no <= threshold_medium:
            return 6 + ((round_no - threshold_small - 1) % 15)
        return 21 + ((round_no - threshold_medium - 1) % 30)

    @staticmethod
    def _normalize_output(text: str) -> str:
        lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)

    def _detect_failure(
        self,
        *,
        round_no: int,
        seed: int,
        mode: str,
        size: int,
        input_text: str,
        brute_result: ExecutionResult,
        user_result: ExecutionResult,
    ) -> DuelFailure | None:
        if user_result.timed_out:
            return DuelFailure(
                round=round_no,
                seed=seed,
                mode=mode,
                size=size,
                reason="user_timed_out",
                input=input_text,
                expected_output=brute_result.stdout,
                actual_output=user_result.stdout,
                stderr=user_result.stderr,
                timed_out=True,
                user_exit_code=user_result.exit_code,
                brute_exit_code=brute_result.exit_code,
            )
        if user_result.exit_code != 0:
            return DuelFailure(
                round=round_no,
                seed=seed,
                mode=mode,
                size=size,
                reason="user_runtime_error",
                input=input_text,
                expected_output=brute_result.stdout,
                actual_output=user_result.stdout,
                stderr=user_result.stderr,
                timed_out=False,
                user_exit_code=user_result.exit_code,
                brute_exit_code=brute_result.exit_code,
            )
        if self._normalize_output(brute_result.stdout) != self._normalize_output(user_result.stdout):
            return DuelFailure(
                round=round_no,
                seed=seed,
                mode=mode,
                size=size,
                reason="wrong_answer",
                input=input_text,
                expected_output=brute_result.stdout,
                actual_output=user_result.stdout,
                stderr=user_result.stderr,
                timed_out=False,
                user_exit_code=user_result.exit_code,
                brute_exit_code=brute_result.exit_code,
            )
        return None
