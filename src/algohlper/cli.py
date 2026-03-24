from __future__ import annotations

import argparse
import json
from pathlib import Path

from algohlper.config import Settings
from algohlper.models import DuelRequest, GenerationRequest, ProjectRecord
from algohlper.services.codegen import CompositeCodeGenerator
from algohlper.services.duel import DuelService
from algohlper.services.problem_parser import parse_problem_spec
from algohlper.utils import read_text_file


def main() -> int:
    parser = argparse.ArgumentParser(prog="algohlper", description="AlgoHlper CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="Parse problem statement into ProblemSpec JSON")
    parse_parser.add_argument("input_path")
    parse_parser.add_argument("--format", default="markdown", choices=["text", "markdown", "latex"])
    parse_parser.add_argument("--output")

    starter_parser = subparsers.add_parser("starter", help="Generate starter artifacts")
    starter_parser.add_argument("input_path")
    starter_parser.add_argument("output_dir")
    starter_parser.add_argument("--format", default="markdown", choices=["text", "markdown", "latex"])
    starter_parser.add_argument("--project-name", default="CLI Starter Project")

    generate_parser = subparsers.add_parser("generate", help="Generate artifacts with provider auto/template/openai")
    generate_parser.add_argument("input_path")
    generate_parser.add_argument("output_dir")
    generate_parser.add_argument("--format", default="markdown", choices=["text", "markdown", "latex"])
    generate_parser.add_argument("--project-name", default="CLI Generated Project")
    generate_parser.add_argument("--provider", default="auto", choices=["auto", "template", "openai"])
    generate_parser.add_argument("--instructions")

    duel_parser = subparsers.add_parser("duel", help="Compile and run local duel")
    duel_parser.add_argument("--brute", required=True)
    duel_parser.add_argument("--generator", required=True)
    duel_parser.add_argument("--user", required=True)
    duel_parser.add_argument("--rounds", type=int, default=100)
    duel_parser.add_argument("--time-limit-ms", type=int, default=1000)
    duel_parser.add_argument("--memory-limit-mb", type=int, default=256)
    duel_parser.add_argument("--seed-start", type=int, default=1)
    duel_parser.add_argument("--modes", nargs="*", default=["random", "edge", "small"])
    duel_parser.add_argument("--output")

    args = parser.parse_args()
    if args.command == "parse":
        return _run_parse(args)
    if args.command == "starter":
        return _run_starter(args)
    if args.command == "generate":
        return _run_generate(args)
    if args.command == "duel":
        return _run_duel(args)
    raise RuntimeError(f"Unsupported command: {args.command}")


def _run_parse(args: argparse.Namespace) -> int:
    spec = parse_problem_spec(read_text_file(args.input_path))
    content = json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(content + "\n", encoding="utf-8")
    else:
        print(content)
    return 0


def _run_starter(args: argparse.Namespace) -> int:
    return _write_generated_artifacts(
        input_path=args.input_path,
        output_dir=args.output_dir,
        project_name=args.project_name,
        provider="template",
        instructions=None,
    )


def _run_generate(args: argparse.Namespace) -> int:
    return _write_generated_artifacts(
        input_path=args.input_path,
        output_dir=args.output_dir,
        project_name=args.project_name,
        provider=args.provider,
        instructions=args.instructions,
    )


def _write_generated_artifacts(
    *,
    input_path: str,
    output_dir: str,
    project_name: str,
    provider: str,
    instructions: str | None,
) -> int:
    raw_problem = read_text_file(input_path)
    spec = parse_problem_spec(raw_problem)
    project = ProjectRecord(id="cli_project", name=project_name, problem_spec=spec, raw_problem_content=raw_problem)
    settings = Settings.from_env()
    generator = CompositeCodeGenerator(settings)
    result = generator.generate(
        project,
        spec,
        GenerationRequest(provider=provider, instructions=instructions),
    )
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    filename_map = {
        "brute": "brute.cpp",
        "generator": "gen.cpp",
        "compare": "compare.py",
        "readme": "README.md",
    }
    for artifact_type, artifact in result.artifacts.items():
        (output_dir_path / filename_map[artifact_type]).write_text(artifact.code, encoding="utf-8")
    spec_path = output_dir_path / "problem_spec.json"
    spec_path.write_text(json.dumps(spec.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    meta_path = output_dir_path / "generation_meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "provider": result.provider,
                "warnings": result.warnings,
                "validation": result.validation.model_dump(mode="json"),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Artifacts written to {output_dir_path} via provider={result.provider}")
    for warning in result.warnings:
        print(f"- {warning}")
    return 0


def _run_duel(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    service = DuelService(settings)
    request = DuelRequest(
        rounds=args.rounds,
        time_limit_ms=args.time_limit_ms,
        memory_limit_mb=args.memory_limit_mb,
        generator_mode=args.modes,
        seed_start=args.seed_start,
    )
    result = service.duel(
        brute_code=read_text_file(args.brute),
        generator_code=read_text_file(args.generator),
        user_code=read_text_file(args.user),
        request=request,
    )
    content = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(content + "\n", encoding="utf-8")
    else:
        print(content)
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
