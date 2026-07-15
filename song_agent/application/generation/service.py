from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from song_agent.domains.creation.agent.multinode_pipeline import generate_multinode_song_plan
from song_agent.domains.creation.agent.pipeline import SongAgent
from song_agent.domains.creation.agent.provider_pipeline import generate_provider_song_plan
from song_agent.domains.creation.node_store import NodeStore
from song_agent.domains.studio.projectio import ProjectPaths, default_run_dir, read_json, write_json
from song_agent.domains.creation.provider import ProviderConfig
from song_agent.domains.quality.quality import validate_song_plan
from song_agent.domains.creation.renderers.midi import render_midi
from song_agent.domains.creation.runtime import GraphRunner, PipelineStep, ResumeMismatchError
from song_agent.domains.creation.schemas.song import SongRequest
from song_agent.platform.contracts.run_state import ArtifactRef, RunState


def generate_request(
    request: SongRequest,
    *,
    out_dir: Path | None = None,
    resume: bool = False,
    force: bool = False,
    provider_config: ProviderConfig | None = None,
    provider_snapshot: dict | None = None,
    control: Callable[[str, str], None] | None = None,
    pipeline_mode: str = "single",
) -> tuple[Path, Path]:
    if resume and force:
        raise ValueError("--resume and --force cannot be used together.")
    if pipeline_mode not in {"single", "multinode"}:
        raise ValueError("pipeline_mode must be either single or multinode.")

    run_dir = out_dir or default_run_dir(request.title)
    if force and run_dir.exists():
        _reset_known_run_artifacts(run_dir)
    paths = ProjectPaths.create(run_dir)
    state = RunState(run_id=run_dir.name, request=request.to_dict())
    run_options = _run_options(provider_config, pipeline_mode)

    if resume:
        _ensure_resume_request_matches(paths, request)
        _ensure_resume_options_match(paths, run_options)

    runner = GraphRunner(
        _build_steps(
            paths,
            request,
            provider_config=provider_config,
            provider_snapshot=provider_snapshot,
            pipeline_mode=pipeline_mode,
            control=control,
            run_options=run_options,
        ),
        resume=resume,
        control=control,
    )
    try:
        runner.run(state, paths)
    except ResumeMismatchError as exc:
        raise ValueError(str(exc)) from exc

    return paths.data / "song-plan.json", paths.renders / "song.mid"


def _ensure_resume_request_matches(paths: ProjectPaths, request: SongRequest) -> None:
    request_path = paths.data / "request.json"
    if not request_path.exists():
        return
    if read_json(request_path) != request.to_dict():
        raise ValueError(
            "Cannot resume this run because data/request.json does not match "
            "the current request. Use a new output directory or rerun with --force."
        )


def _ensure_resume_options_match(paths: ProjectPaths, run_options: dict[str, str]) -> None:
    options_path = paths.data / "run-options.json"
    if not options_path.exists():
        if run_options == {"generation_mode": "local", "pipeline_mode": "single"}:
            return
        raise ValueError(
            "Cannot resume this run because data/run-options.json is missing "
            "and the requested generation or pipeline mode is not the legacy "
            "local/single mode. Use a new output directory or rerun with --force."
        )
    if read_json(options_path) != run_options:
        raise ValueError(
            "Cannot resume this run because data/run-options.json does not match "
            "the requested generation or pipeline mode. Use a new output directory "
            "or rerun with --force."
        )


def _reset_known_run_artifacts(run_dir: Path) -> None:
    for child_name in ("data", "renders", "logs", "stems"):
        child_path = run_dir / child_name
        if child_path.exists():
            shutil.rmtree(child_path)


def _build_steps(
    paths: ProjectPaths,
    request: SongRequest,
    *,
    provider_config: ProviderConfig | None = None,
    provider_snapshot: dict | None = None,
    pipeline_mode: str = "single",
    control: Callable[[str, str], None] | None = None,
    run_options: dict[str, str] | None = None,
) -> list[PipelineStep]:
    request_path = paths.data / "request.json"
    options_path = paths.data / "run-options.json"
    plan_path = paths.data / "song-plan.json"
    midi_path = paths.renders / "song.mid"
    provider_snapshot_path = paths.data / "provider-snapshot.json"
    compose_output_path = paths.data / "nodes" / "song_plan_builder.json" if pipeline_mode == "multinode" else plan_path

    def write_request(state: RunState, current_paths: ProjectPaths) -> None:
        write_json(request_path, request.to_dict())
        write_json(options_path, run_options or _run_options(provider_config, pipeline_mode))
        state.add_artifact("request", ArtifactRef("json", str(request_path), "Normalized song request."))
        state.add_artifact("run_options", ArtifactRef("json", str(options_path), "Generation and pipeline mode options."))

    def compose(state: RunState, current_paths: ProjectPaths) -> None:
        if pipeline_mode == "multinode":
            plan = generate_multinode_song_plan(
                request,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot,
                node_store=NodeStore(current_paths.root),
                control=control,
            )
        elif provider_config is None:
            plan = SongAgent().generate(request)
        else:
            plan = generate_provider_song_plan(request, provider_config)
        write_json(plan_path, plan.to_dict())
        state.add_artifact("song_plan", ArtifactRef("json", str(plan_path), "Structured song plan."))
        if provider_snapshot is not None:
            write_json(provider_snapshot_path, provider_snapshot)
            state.add_artifact("provider_snapshot", ArtifactRef("json", str(provider_snapshot_path), "Masked provider snapshot."))

    def validate(state: RunState, current_paths: ProjectPaths) -> None:
        from song_agent.domains.creation.schemas.song import SongPlan

        validate_song_plan(SongPlan.from_dict(read_json(plan_path)))

    def render(state: RunState, current_paths: ProjectPaths) -> None:
        from song_agent.domains.creation.schemas.song import SongPlan

        render_midi(SongPlan.from_dict(read_json(plan_path)), midi_path)
        state.add_artifact("midi", ArtifactRef("midi", str(midi_path), "Rendered MIDI."))

    return [
        PipelineStep("normalize_request", request_path, write_request),
        PipelineStep(_compose_step_name(provider_config, pipeline_mode), compose_output_path, compose),
        PipelineStep("validate_song_plan", None, validate),
        PipelineStep("render_midi", midi_path, render),
    ]


def _compose_step_name(provider_config: ProviderConfig | None, pipeline_mode: str) -> str:
    if pipeline_mode == "multinode":
        return "multinode_compose"
    if provider_config is not None:
        return "provider_compose"
    return "deterministic_compose"


def _run_options(provider_config: ProviderConfig | None, pipeline_mode: str) -> dict[str, str]:
    return {
        "generation_mode": "provider" if provider_config is not None else "local",
        "pipeline_mode": pipeline_mode,
    }
