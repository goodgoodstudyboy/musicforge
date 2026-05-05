from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from song_agent.agent.pipeline import SongAgent
from song_agent.projectio import ProjectPaths, default_run_dir, read_json, write_json
from song_agent.quality import validate_song_plan
from song_agent.renderers.midi import render_midi
from song_agent.runtime import GraphRunner, PipelineStep, ResumeMismatchError
from song_agent.schemas.song import SongRequest
from song_agent.state import ArtifactRef, RunState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a local MIDI song demo.")
    _add_generate_args(parser)
    return parser

def build_serve_parser() -> argparse.ArgumentParser:
    serve_parser = argparse.ArgumentParser(description="Start the local web panel.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve_parser.add_argument("--port", type=int, default=8787, help="Port to bind.")
    return serve_parser

def build_generate_parser() -> argparse.ArgumentParser:
    generate_parser = argparse.ArgumentParser(
        description="Generate a MIDI song demo from a request JSON file."
    )
    _add_generate_args(generate_parser)
    return generate_parser


def _add_generate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "request",
        type=Path,
        nargs="?",
        help="Path to a song request JSON file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Run output directory. Defaults to runs/<request-title-slug>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the normalized request without calling an LLM.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip graph steps whose expected artifacts already exist.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output directory instead of resuming it.",
    )


def main() -> None:
    try:
        _main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _main() -> None:
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "serve":
        parser = build_serve_parser()
        args = parser.parse_args(raw_args[1:])
        from song_agent.server import serve

        serve(args.host, args.port)
        return

    if raw_args and raw_args[0] == "generate":
        parser = build_generate_parser()
        args = parser.parse_args(raw_args[1:])
    else:
        parser = build_parser()
        args = parser.parse_args(raw_args)

    request_path = args.request
    if request_path is None:
        parser.error("the following arguments are required: request")

    generate_from_file(
        request_path,
        out_dir=args.out,
        dry_run=args.dry_run,
        resume=args.resume,
        force=args.force,
    )


def generate_from_file(
    request_path: Path,
    *,
    out_dir: Path | None = None,
    dry_run: bool = False,
    resume: bool = False,
    force: bool = False,
) -> tuple[Path, Path] | None:
    raw = json.loads(request_path.read_text(encoding="utf-8"))
    request = SongRequest.from_dict(raw)

    if dry_run:
        print(json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
        return None

    plan_path, midi_path = generate_request(
        request,
        out_dir=out_dir,
        resume=resume,
        force=force,
    )
    print(f"Wrote song plan: {plan_path}")
    print(f"Wrote MIDI: {midi_path}")
    return plan_path, midi_path


def generate_request(
    request: SongRequest,
    *,
    out_dir: Path | None = None,
    resume: bool = False,
    force: bool = False,
) -> tuple[Path, Path]:
    if resume and force:
        raise ValueError("--resume and --force cannot be used together.")

    run_dir = out_dir or default_run_dir(request.title)
    if force and run_dir.exists():
        _reset_known_run_artifacts(run_dir)
    paths = ProjectPaths.create(run_dir)
    state = RunState(run_id=run_dir.name, request=request.to_dict())

    if resume:
        _ensure_resume_request_matches(paths, request)

    runner = GraphRunner(_build_steps(paths, request), resume=resume)
    try:
        runner.run(state, paths)
    except ResumeMismatchError as exc:
        raise ValueError(str(exc)) from exc

    return paths.data / "song-plan.json", paths.renders / "song.mid"


def _ensure_resume_request_matches(paths: ProjectPaths, request: SongRequest) -> None:
    request_path = paths.data / "request.json"
    if not request_path.exists():
        return

    existing_request = read_json(request_path)
    current_request = request.to_dict()
    if existing_request != current_request:
        raise ValueError(
            "Cannot resume this run because data/request.json does not match "
            "the current request. Use a new output directory or rerun with --force."
        )


def _reset_known_run_artifacts(run_dir: Path) -> None:
    for child_name in ("data", "renders", "logs"):
        child_path = run_dir / child_name
        if child_path.exists():
            shutil.rmtree(child_path)


def _build_steps(paths: ProjectPaths, request: SongRequest) -> list[PipelineStep]:
    request_path = paths.data / "request.json"
    plan_path = paths.data / "song-plan.json"
    midi_path = paths.renders / "song.mid"

    def write_request(state: RunState, paths: ProjectPaths) -> None:
        write_json(request_path, request.to_dict())
        state.add_artifact(
            "request",
            ArtifactRef("json", str(request_path), "Normalized song request."),
        )

    def compose(state: RunState, paths: ProjectPaths) -> None:
        plan = SongAgent().generate(request)
        write_json(plan_path, plan.to_dict())
        state.add_artifact(
            "song_plan",
            ArtifactRef("json", str(plan_path), "Structured song plan."),
        )

    def validate(state: RunState, paths: ProjectPaths) -> None:
        from song_agent.schemas.song import SongPlan

        plan = SongPlan.from_dict(read_json(plan_path))
        validate_song_plan(plan)

    def render(state: RunState, paths: ProjectPaths) -> None:
        from song_agent.schemas.song import SongPlan

        plan = SongPlan.from_dict(read_json(plan_path))
        render_midi(plan, midi_path)
        state.add_artifact("midi", ArtifactRef("midi", str(midi_path), "Rendered MIDI."))

    return [
        PipelineStep("normalize_request", request_path, write_request),
        PipelineStep("deterministic_compose", plan_path, compose),
        PipelineStep("validate_song_plan", None, validate),
        PipelineStep("render_midi", midi_path, render),
    ]


if __name__ == "__main__":
    main()
