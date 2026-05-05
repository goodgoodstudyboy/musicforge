from __future__ import annotations

import argparse
import json
import shutil
import sys
import os
from pathlib import Path
from collections.abc import Callable

from song_agent.agent.multinode_pipeline import generate_multinode_song_plan
from song_agent.agent.pipeline import SongAgent
from song_agent.agent.provider_pipeline import generate_provider_song_plan
from song_agent.auth import build_auth_config
from song_agent.node_store import NodeStore
from song_agent.projectio import ProjectPaths, default_run_dir, read_json, write_json
from song_agent.provider import (
    ProviderConfig,
    ProviderError,
    load_provider_config,
    provider_configured,
    test_provider_config,
)
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
    serve_parser.add_argument(
        "--access-token",
        default=None,
        help="Bearer token required for Studio/API access.",
    )
    return serve_parser

def build_generate_parser() -> argparse.ArgumentParser:
    generate_parser = argparse.ArgumentParser(
        description="Generate a MIDI song demo from a request JSON file."
    )
    _add_generate_args(generate_parser)
    return generate_parser


def build_doctor_parser() -> argparse.ArgumentParser:
    doctor_parser = argparse.ArgumentParser(description="Check the local MusicForge setup.")
    doctor_parser.add_argument(
        "--provider-test",
        action="store_true",
        help="Run the configured provider connectivity check.",
    )
    return doctor_parser


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
    parser.add_argument(
        "--pipeline-mode",
        choices=["single", "multinode"],
        default="single",
        help="Pipeline to run: single or multinode.",
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

        auth_config = build_auth_config(args.host, args.access_token, os.environ)
        serve(args.host, args.port, auth_config=auth_config)
        return

    if raw_args and raw_args[0] == "generate":
        parser = build_generate_parser()
        args = parser.parse_args(raw_args[1:])
    elif raw_args and raw_args[0] == "doctor":
        parser = build_doctor_parser()
        args = parser.parse_args(raw_args[1:])
        run_doctor(provider_test=args.provider_test)
        return
    elif raw_args and raw_args[0] == "release-check":
        from song_agent.release_checks import print_release_check_report, run_release_checks

        report = run_release_checks()
        print_release_check_report(report)
        if not report.ok:
            raise SystemExit(1)
        return
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
        pipeline_mode=args.pipeline_mode,
    )


def generate_from_file(
    request_path: Path,
    *,
    out_dir: Path | None = None,
    dry_run: bool = False,
    resume: bool = False,
    force: bool = False,
    pipeline_mode: str = "single",
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
        pipeline_mode=pipeline_mode,
    )
    print(f"Wrote song plan: {plan_path}")
    print(f"Wrote MIDI: {midi_path}")
    return plan_path, midi_path


def run_doctor(*, provider_test: bool = False) -> None:
    print("MusicForge doctor")
    print(f"python: ok ({sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")
    print(f"cwd writable: {_writable_status(Path.cwd())}")
    print(f"runs writable: {_writable_status(Path('runs'))}")
    try:
        config, _sources = load_provider_config()
        if provider_configured(config):
            print(
                "provider config: configured "
                f"({config.wire_api}, model={config.model}, key={config.to_public_dict()['api_key_masked'] or '-'})"
            )
        elif config.model or config.base_url or config.api_key:
            print("provider config: warning incomplete")
        else:
            print("provider config: missing")
        if provider_test:
            result = test_provider_config(config)
            print(f"provider test: ok ({result['provider']['wire_api']})")
    except ProviderError as exc:
        print(f"provider config: warning {exc}")
        if provider_test:
            print(f"provider test: failed ({exc})")
    print("local deterministic mode: ok")


def _writable_status(path: Path) -> str:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".musicforge-write-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return "failed"
    return "ok"


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

    existing_request = read_json(request_path)
    current_request = request.to_dict()
    if existing_request != current_request:
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

    existing_options = read_json(options_path)
    if existing_options != run_options:
        raise ValueError(
            "Cannot resume this run because data/run-options.json does not match "
            "the requested generation or pipeline mode. Use a new output directory "
            "or rerun with --force."
        )


def _reset_known_run_artifacts(run_dir: Path) -> None:
    for child_name in ("data", "renders", "logs"):
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
    compose_output_path = (
        paths.data / "nodes" / "song_plan_builder.json"
        if pipeline_mode == "multinode"
        else plan_path
    )

    def write_request(state: RunState, paths: ProjectPaths) -> None:
        write_json(request_path, request.to_dict())
        write_json(options_path, run_options or _run_options(provider_config, pipeline_mode))
        state.add_artifact(
            "request",
            ArtifactRef("json", str(request_path), "Normalized song request."),
        )
        state.add_artifact(
            "run_options",
            ArtifactRef("json", str(options_path), "Generation and pipeline mode options."),
        )

    def compose(state: RunState, paths: ProjectPaths) -> None:
        if pipeline_mode == "multinode":
            plan = generate_multinode_song_plan(
                request,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot,
                node_store=NodeStore(paths.root),
                control=control,
            )
        elif provider_config is None:
            plan = SongAgent().generate(request)
        else:
            plan = generate_provider_song_plan(request, provider_config)
        write_json(plan_path, plan.to_dict())
        state.add_artifact(
            "song_plan",
            ArtifactRef("json", str(plan_path), "Structured song plan."),
        )
        if provider_snapshot is not None:
            write_json(provider_snapshot_path, provider_snapshot)
            state.add_artifact(
                "provider_snapshot",
                ArtifactRef("json", str(provider_snapshot_path), "Masked provider snapshot."),
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
        PipelineStep(_compose_step_name(provider_config, pipeline_mode), compose_output_path, compose),
        PipelineStep("validate_song_plan", None, validate),
        PipelineStep("render_midi", midi_path, render),
    ]


def _compose_step_name(
    provider_config: ProviderConfig | None,
    pipeline_mode: str,
) -> str:
    if pipeline_mode == "multinode":
        return "multinode_compose"
    if provider_config is not None:
        return "provider_compose"
    return "deterministic_compose"


def _run_options(
    provider_config: ProviderConfig | None,
    pipeline_mode: str,
) -> dict[str, str]:
    return {
        "generation_mode": "provider" if provider_config is not None else "local",
        "pipeline_mode": pipeline_mode,
    }


if __name__ == "__main__":
    main()
