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
    parser.add_argument("request", type=Path, help="Path to a song request JSON file.")
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
    return parser


def main() -> None:
    try:
        _main()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.resume and args.force:
        raise ValueError("--resume and --force cannot be used together.")

    raw = json.loads(args.request.read_text(encoding="utf-8"))
    request = SongRequest.from_dict(raw)

    if args.dry_run:
        print(json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
        return

    run_dir = args.out or default_run_dir(request.title)
    if args.force and run_dir.exists():
        _reset_known_run_artifacts(run_dir)
    paths = ProjectPaths.create(run_dir)
    state = RunState(run_id=run_dir.name, request=request.to_dict())

    if args.resume:
        _ensure_resume_request_matches(paths, request)

    runner = GraphRunner(_build_steps(paths, request), resume=args.resume)
    try:
        runner.run(state, paths)
    except ResumeMismatchError as exc:
        raise ValueError(str(exc)) from exc

    print(f"Wrote song plan: {paths.data / 'song-plan.json'}")
    print(f"Wrote MIDI: {paths.renders / 'song.mid'}")


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
