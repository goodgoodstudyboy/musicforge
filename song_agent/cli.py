from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.agent.pipeline import SongAgent
from song_agent.projectio import ProjectPaths, default_run_dir, read_json, write_json
from song_agent.quality import validate_song_plan
from song_agent.renderers.midi import render_midi
from song_agent.runtime import GraphRunner, PipelineStep
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
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    raw = json.loads(args.request.read_text(encoding="utf-8"))
    request = SongRequest.from_dict(raw)

    if args.dry_run:
        print(json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
        return

    run_dir = args.out or default_run_dir(request.title)
    paths = ProjectPaths.create(run_dir)
    state = RunState(run_id=run_dir.name, request=request.to_dict())

    runner = GraphRunner(_build_steps(paths, request), resume=args.resume)
    runner.run(state, paths)

    print(f"Wrote song plan: {paths.data / 'song-plan.json'}")
    print(f"Wrote MIDI: {paths.renders / 'song.mid'}")


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
