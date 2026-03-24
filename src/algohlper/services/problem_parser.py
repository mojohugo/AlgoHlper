from __future__ import annotations

import itertools
import re
from typing import Iterable

from algohlper.models import ProblemSample, ProblemSpec

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "statement": (
        "description",
        "problem description",
        "statement",
        "题目描述",
        "描述",
        "题意",
    ),
    "input_format": (
        "input",
        "input format",
        "input description",
        "输入",
        "输入格式",
        "输入描述",
    ),
    "output_format": (
        "output",
        "output format",
        "output description",
        "输出",
        "输出格式",
        "输出描述",
    ),
    "constraints": (
        "constraints",
        "constraint",
        "limits",
        "约束",
        "限制",
        "数据范围",
    ),
    "sample_input": (
        "sample input",
        "example input",
        "input sample",
        "样例输入",
        "输入样例",
        "示例输入",
    ),
    "sample_output": (
        "sample output",
        "example output",
        "output sample",
        "样例输出",
        "输出样例",
        "示例输出",
    ),
}

_PROBLEM_TAGS: dict[str, tuple[str, ...]] = {
    "array": ("array", "数组", "sequence", "序列"),
    "string": ("string", "字符串"),
    "graph": ("graph", "图", "edge", "vertex"),
    "tree": ("tree", "树"),
    "dp": ("dynamic programming", "dp", "状态转移"),
    "greedy": ("greedy", "贪心"),
    "math": ("math", "数学", "gcd", "lcm", "mod"),
}


def normalize_problem_text(content: str) -> str:
    text = content.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
    return text.strip() + "\n"


def parse_problem_spec(content: str) -> ProblemSpec:
    normalized = normalize_problem_text(content)
    lines = normalized.split("\n")
    title, start_index = _extract_title(lines)
    chunks = _split_sections(lines[start_index:])

    statement = _join_sections(chunks, "statement") or normalized.strip()
    input_format = _join_sections(chunks, "input_format")
    output_format = _join_sections(chunks, "output_format")
    constraints_text = _join_sections(chunks, "constraints")
    constraints = _extract_constraints(constraints_text or statement)
    samples = _extract_samples(chunks)
    problem_type_guess = _guess_problem_types(normalized)
    special_notes = _extract_special_notes(normalized)
    parse_confidence = {
        "title": 0.9 if title != "Untitled Problem" else 0.2,
        "input_format": 0.85 if input_format else 0.25,
        "output_format": 0.85 if output_format else 0.25,
        "constraints": 0.75 if constraints else 0.25,
        "samples": 0.9 if samples else 0.3,
    }
    return ProblemSpec(
        title=title,
        statement=statement.strip(),
        input_format=input_format.strip(),
        output_format=output_format.strip(),
        constraints=constraints,
        samples=samples,
        problem_type_guess=problem_type_guess,
        special_notes=special_notes,
        parse_confidence=parse_confidence,
    )


def _extract_title(lines: list[str]) -> tuple[str, int]:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        candidate = re.sub(r"^#+", "", stripped).strip(" ：:")
        if _detect_section_key(candidate):
            return "Untitled Problem", index
        if len(candidate) <= 120:
            return candidate, index + 1
        break
    return "Untitled Problem", 0


def _split_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    chunks: list[tuple[str, list[str]]] = []
    current_key = "statement"
    current_lines: list[str] = []
    for line in lines:
        key = _detect_section_key(line)
        if key:
            if current_lines:
                chunks.append((current_key, current_lines))
            current_key = key
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        chunks.append((current_key, current_lines))
    return chunks


def _detect_section_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    if len(stripped) > 80 and not stripped.startswith("#"):
        return None
    heading = re.sub(r"^#+", "", stripped).strip(" ：:").lower()
    for key, aliases in _SECTION_ALIASES.items():
        for alias in aliases:
            if heading == alias or heading.startswith(alias + " ") or re.fullmatch(alias + r"\s*\d*", heading):
                return key
    return None


def _join_sections(chunks: Iterable[tuple[str, list[str]]], key: str) -> str:
    parts = [
        "\n".join(lines).strip()
        for section_key, lines in chunks
        if section_key == key and any(line.strip() for line in lines)
    ]
    return "\n\n".join(part for part in parts if part)


def _extract_samples(chunks: Iterable[tuple[str, list[str]]]) -> list[ProblemSample]:
    sample_inputs: list[str] = []
    sample_outputs: list[str] = []
    for key, lines in chunks:
        text = "\n".join(lines).strip()
        if not text:
            continue
        if key == "sample_input":
            sample_inputs.extend(_extract_text_blocks(text))
        elif key == "sample_output":
            sample_outputs.extend(_extract_text_blocks(text))
    samples: list[ProblemSample] = []
    for sample_input, sample_output in itertools.zip_longest(sample_inputs, sample_outputs, fillvalue=""):
        if sample_input and sample_output:
            samples.append(ProblemSample(input=sample_input, output=sample_output))
    return samples


def _extract_text_blocks(text: str) -> list[str]:
    fenced = [match.strip() for match in re.findall(r"```(?:[\w+-]+)?\n(.*?)```", text, flags=re.S)]
    if fenced:
        return fenced
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
    return blocks or [text.strip()]


def _extract_constraints(text: str) -> dict[str, str]:
    constraints: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip(" -*")
        if not line:
            continue
        if not any(token in line for token in ("<=", ">=", "<", ">", "≤", "≥")) and not re.search(r"\b\d+e\d+\b", line, flags=re.I):
            continue
        identifiers = re.findall(r"[A-Za-z][A-Za-z0-9_]*", line)
        key = identifiers[0] if identifiers else f"constraint_{len(constraints) + 1}"
        constraints[key] = line
    return constraints


def _guess_problem_types(text: str) -> list[str]:
    lowered = text.lower()
    guesses: list[str] = []
    for tag, keywords in _PROBLEM_TAGS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            guesses.append(tag)
    return guesses


def _extract_special_notes(text: str) -> list[str]:
    lowered = text.lower()
    notes: list[str] = []
    if any(token in lowered for token in ("multiple test", "multiple testcase", "多组测试", "多测")):
        notes.append("multiple testcases")
    if any(token in lowered for token in ("1-index", "1 indexed", "下标从 1 开始", "1-based")):
        notes.append("1-indexed")
    if any(token in lowered for token in ("interactive", "交互")):
        notes.append("interactive")
    if any(token in lowered for token in ("mod", "取模", "modulo")):
        notes.append("contains modulo arithmetic")
    return notes
