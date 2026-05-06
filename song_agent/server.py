from __future__ import annotations

import json
import mimetypes
import os
import shutil
import threading
import time
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.parse import parse_qs

from song_agent import __version__
from song_agent.agent.multinode_pipeline import rerun_multinode_from_node
from song_agent.auth import AuthConfig, validate_bearer_header
from song_agent.batching import BatchDocument, BatchStore, now_iso
from song_agent.cli import generate_request
from song_agent.node_graph import affected_nodes_for_retry, downstream_nodes, upstream_nodes
from song_agent.node_store import NodeStore
from song_agent.projectio import ProjectPaths, append_event, read_json, slugify, write_json
from song_agent.projects import ProjectStore
from song_agent.provider import (
    ProviderError,
    load_provider_config,
    provider_configured,
    reset_provider_config,
    save_provider_config_from_dict,
    test_provider_config,
)
from song_agent.renderers.midi import render_midi
from song_agent.renderers.audio import (
    RendererError,
    load_renderer_config,
    render_audio,
    renderer_configured,
    reset_renderer_config,
    save_renderer_config_from_dict,
    test_renderer_config,
)
from song_agent.runtime_views import (
    build_timeline_view,
    build_tracks_view,
    build_validator_view,
    build_quality_view,
)
from song_agent.schemas.song import SongPlan, SongRequest
from song_agent.stems import (
    StemManifest,
    clear_stem_artifacts,
    load_or_preview_stem_manifest,
    read_stem_manifest,
    render_stem_audio,
    render_stem_midis,
    stem_manifest_stale,
    stem_audio_path,
    stem_midi_path,
)
from song_agent.webui import panel_html


RUNS_DIR = Path("runs")


class JobCancelled(Exception):
    """Raised when a job stops at a stage boundary after cancellation."""


@dataclass
class JobState:
    job_id: str
    title: str
    output_dir: str
    status: str
    created_at: str
    updated_at: str
    step: str = "created"
    message: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempt_count: int = 0
    cancel_requested: bool = False
    pause_requested: bool = False
    hidden: bool = False
    input_payload: dict[str, Any] = field(default_factory=dict)
    provider_snapshot: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    deleted: bool = False
    interrupted: bool = False
    last_seen_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    heartbeat_at: str | None = None
    retry_requested: bool = False
    retry_count: int = 0
    max_retries: int = 0
    next_retry_at: str | None = None
    last_error: str | None = None
    stalled: bool = False
    stall_timeout_seconds: int = 300
    generation_mode: str = "local"
    pipeline_mode: str = "single"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobState":
        now = _utc_now()
        return cls(
            job_id=str(data["job_id"]),
            title=str(data.get("title", data["job_id"])),
            output_dir=str(data["output_dir"]),
            status=str(data.get("status", "completed")),
            created_at=str(data.get("created_at", now)),
            updated_at=str(data.get("updated_at", now)),
            step=str(data.get("step", "")),
            message=str(data.get("message", "")),
            summary=_dict_or_empty(data.get("summary")),
            error=None if data.get("error") is None else str(data.get("error")),
            attempt_count=int(data.get("attempt_count", 0) or 0),
            cancel_requested=bool(data.get("cancel_requested", False)),
            pause_requested=bool(data.get("pause_requested", False)),
            hidden=bool(data.get("hidden", False)),
            input_payload=_dict_or_empty(data.get("input_payload")),
            provider_snapshot=_dict_or_empty(data.get("provider_snapshot")),
            artifacts=_dict_or_empty(data.get("artifacts")),
            deleted=bool(data.get("deleted", False)),
            interrupted=bool(data.get("interrupted", False)),
            last_seen_at=None
            if data.get("last_seen_at") is None
            else str(data.get("last_seen_at")),
            started_at=None if data.get("started_at") is None else str(data.get("started_at")),
            finished_at=None if data.get("finished_at") is None else str(data.get("finished_at")),
            heartbeat_at=None
            if data.get("heartbeat_at") is None
            else str(data.get("heartbeat_at")),
            retry_requested=bool(data.get("retry_requested", False)),
            retry_count=int(data.get("retry_count", 0) or 0),
            max_retries=int(data.get("max_retries", 0) or 0),
            next_retry_at=None
            if data.get("next_retry_at") is None
            else str(data.get("next_retry_at")),
            last_error=None if data.get("last_error") is None else str(data.get("last_error")),
            stalled=bool(data.get("stalled", False)),
            stall_timeout_seconds=int(data.get("stall_timeout_seconds", 300) or 300),
            generation_mode=str(data.get("generation_mode", "local") or "local"),
            pipeline_mode=str(data.get("pipeline_mode", "single") or "single"),
        )


class JobStore:
    def __init__(self, runs_dir: Path = RUNS_DIR) -> None:
        self.runs_dir = Path(runs_dir).resolve()
        self.lock = threading.RLock()
        self.jobs: dict[str, JobState] = {}
        self.load_existing_jobs()

    def load_existing_jobs(self) -> None:
        if not self.runs_dir.exists():
            return
        for state_path in self.runs_dir.glob("*/data/job-state.json"):
            try:
                job = JobState.from_dict(read_json(state_path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if job.status in {"queued", "running", "waiting_retry", "paused"}:
                job.status = "interrupted"
                job.step = "interrupted"
                job.message = "This job was interrupted by a previous server shutdown."
                job.error = "Job was running when the server stopped."
                job.interrupted = True
                job.updated_at = _utc_now()
                self._write_job(job)
            self.jobs[job.job_id] = job

    def list_jobs(self, include_hidden: bool = False) -> list[JobState]:
        with self.lock:
            return sorted(
                [
                    job
                    for job in self.jobs.values()
                    if include_hidden or not job.hidden
                ],
                key=lambda job: job.created_at,
                reverse=True,
            )

    def get_job(self, job_id: str) -> JobState | None:
        with self.lock:
            return self.jobs.get(job_id)

    def create_job(self, payload: dict[str, Any], start_immediately: bool = True) -> JobState:
        request = SongRequest.from_dict(payload)
        generation_mode = _generation_mode(payload)
        pipeline_mode = _pipeline_mode(payload)
        provider_snapshot: dict[str, Any]
        if generation_mode == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            provider_snapshot = provider_config.to_snapshot("provider", _utc_now())
        else:
            provider_snapshot = {"mode": "local", "summary": "Local deterministic composer"}
        with self.lock:
            run_dir = self._reserve_run_dir(request.title)
            job_id = run_dir.name
            now = _utc_now()
            job = JobState(
                job_id=job_id,
                title=request.title,
                output_dir=str(run_dir),
                status="queued",
                created_at=now,
                updated_at=now,
                step="queued",
                message="Queued for local deterministic generation.",
                input_payload=request.to_dict(),
                provider_snapshot=provider_snapshot,
                heartbeat_at=now,
                generation_mode=generation_mode,
                pipeline_mode=pipeline_mode,
            )
            self.jobs[job_id] = job
            self._write_job(job)

        if start_immediately:
            self.start_job(job_id)
        return job

    def start_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if job is None or job.status != "queued":
            return False
        if job.cancel_requested:
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
            )
            return False
        thread = threading.Thread(
            target=self._run_job,
            args=(job_id,),
            name=f"musicforge-job-{job_id}",
            daemon=True,
        )
        thread.start()
        return True

    def hide_job(self, job_id: str, hidden: bool) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        self._update_job(job, hidden=hidden)
        return job

    def cancel_job(self, job_id: str) -> tuple[JobState | None, HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return None, HTTPStatus.NOT_FOUND, "Job not found."
        if job.status == "queued":
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
                cancel_requested=True,
            )
            return job, HTTPStatus.OK, None
        if job.status == "running":
            self._update_job(
                job,
                cancel_requested=True,
                message="Cancellation requested; job will stop at the next stage boundary.",
            )
            return job, HTTPStatus.OK, None
        if job.status == "cancelled":
            return job, HTTPStatus.OK, None
        return job, HTTPStatus.CONFLICT, f"Cannot cancel a {job.status} job."

    def retry_job(self, job_id: str) -> tuple[JobState | None, HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return None, HTTPStatus.NOT_FOUND, "Job not found."
        if job.status not in {"failed", "stalled", "interrupted"}:
            return job, HTTPStatus.CONFLICT, f"Cannot retry a {job.status} job."

        try:
            provider_snapshot = self._provider_snapshot_for_retry(job)
        except ProviderError as exc:
            return job, HTTPStatus.BAD_REQUEST, str(exc)

        previous_error = job.error or job.last_error
        self._update_job(
            job,
            status="queued",
            step="queued",
            message="Retry queued.",
            error=None,
            last_error=previous_error,
            retry_requested=True,
            retry_count=job.retry_count + 1,
            cancel_requested=False,
            stalled=False,
            interrupted=False,
            finished_at=None,
            provider_snapshot=provider_snapshot,
            heartbeat_at=_utc_now(),
        )
        append_event(
            ProjectPaths.create(Path(job.output_dir)),
            {"event": "retry_requested", "retry_count": job.retry_count},
        )
        self.start_job(job_id)
        return job, HTTPStatus.OK, None

    def retry_job_node(
        self,
        job_id: str,
        node_name: str,
    ) -> tuple[JobState | None, HTTPStatus, str | None, dict[str, Any]]:
        job = self.get_job(job_id)
        if job is None:
            return None, HTTPStatus.NOT_FOUND, "Job not found.", {}
        try:
            affected_nodes = affected_nodes_for_retry(node_name)
        except ValueError as exc:
            if str(exc).startswith("Unknown node:"):
                return job, HTTPStatus.NOT_FOUND, "Node record not found.", {}
            return job, HTTPStatus.BAD_REQUEST, str(exc), {}
        if job.pipeline_mode != "multinode":
            return job, HTTPStatus.CONFLICT, "Node retry requires a multinode job.", {}
        if job.status == "running":
            return job, HTTPStatus.CONFLICT, "Cannot retry a node while the job is running.", {}
        if job.status not in {"completed", "failed", "stalled", "interrupted"}:
            return job, HTTPStatus.CONFLICT, f"Cannot retry a node for a {job.status} job.", {}

        node_store = NodeStore(Path(job.output_dir))
        try:
            node_store.read_node(node_name)
        except FileNotFoundError:
            return job, HTTPStatus.NOT_FOUND, "Node record not found.", {}
        except ValueError as exc:
            return job, HTTPStatus.BAD_REQUEST, str(exc), {}

        try:
            provider_snapshot = self._provider_snapshot_for_retry(job)
        except ProviderError as exc:
            return job, HTTPStatus.BAD_REQUEST, str(exc), {}

        retry = {"node": node_name, "affected_nodes": affected_nodes}
        self._update_job(
            job,
            status="running",
            step=f"retry:{node_name}",
            message=f"Retrying node {node_name}.",
            error=None,
            retry_requested=True,
            retry_count=job.retry_count + 1,
            cancel_requested=False,
            stalled=False,
            interrupted=False,
            finished_at=None,
            provider_snapshot=provider_snapshot,
            heartbeat_at=_utc_now(),
        )
        thread = threading.Thread(
            target=self._run_node_retry,
            args=(job.job_id, node_name, affected_nodes, provider_snapshot),
            name=f"musicforge-node-retry-{job.job_id}-{node_name}",
            daemon=True,
        )
        thread.start()
        return job, HTTPStatus.ACCEPTED, None, retry

    def run_watchdog_tick(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        marked = 0
        with self.lock:
            jobs = list(self.jobs.values())
        for job in jobs:
            if job.status != "running":
                continue
            heartbeat = _parse_iso_datetime(job.heartbeat_at or job.updated_at)
            if heartbeat is None:
                continue
            elapsed = (now - heartbeat).total_seconds()
            if elapsed > job.stall_timeout_seconds:
                self._update_job(
                    job,
                    status="stalled",
                    step="stalled",
                    message="Job stalled because no heartbeat was observed.",
                    error="No heartbeat within stall timeout.",
                    last_error="No heartbeat within stall timeout.",
                    stalled=True,
                    finished_at=_utc_now(),
                )
                marked += 1
        return marked

    def delete_job(self, job_id: str) -> tuple[bool, HTTPStatus, str | None]:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return False, HTTPStatus.NOT_FOUND, "Job not found."
            if job.status == "running":
                return False, HTTPStatus.CONFLICT, "Cannot delete a running job. Cancel it first."
            try:
                run_dir = self._ensure_run_dir_is_safe(Path(job.output_dir))
            except ValueError as exc:
                return False, HTTPStatus.CONFLICT, str(exc)
            if run_dir.exists():
                shutil.rmtree(run_dir)
            self.jobs.pop(job_id, None)
            return True, HTTPStatus.OK, None

    def render_job_audio(self, job_id: str) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        midi_path = run_dir / "renders" / "song.mid"
        if not midi_path.exists():
            return {}, HTTPStatus.CONFLICT, "song.mid is not available for this job yet."
        try:
            config, _sources = load_renderer_config()
            wav_path = render_audio(midi_path, run_dir / "renders" / "song.wav", config)
        except RendererError as exc:
            error_path = run_dir / "logs" / "audio-render-error.json"
            write_json(
                error_path,
                {
                    "error": str(exc),
                    "checked_at": _utc_now(),
                },
            )
            return {}, HTTPStatus.BAD_REQUEST, str(exc)

        validator_report_path = run_dir / "data" / "validator-report.json"
        if validator_report_path.exists():
            report = read_json(validator_report_path)
            report["audio"] = _audio_report(wav_path)
            write_json(validator_report_path, report)
        artifacts = dict(job.artifacts)
        artifacts["audio"] = str(wav_path)
        self._update_job(job, artifacts=artifacts)
        return {
            "audio": str(wav_path),
            "artifact": _artifact_dict(wav_path),
        }, HTTPStatus.OK, None

    def get_job_stems(self, job_id: str) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            return {}, HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet."
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            manifest = load_or_preview_stem_manifest(plan, run_dir, job.job_id, now=_utc_now())
        except ValueError as exc:
            return {}, HTTPStatus.CONFLICT, str(exc)
        return _manifest_response(job.job_id, manifest), HTTPStatus.OK, None

    def render_job_stems(
        self,
        job_id: str,
        *,
        force: bool = False,
    ) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            return {}, HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet."
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            existing_manifest = read_stem_manifest(run_dir)
            if existing_manifest is not None and stem_manifest_stale(existing_manifest, plan):
                clear_stem_artifacts(run_dir)
            manifest = render_stem_midis(plan, run_dir, job.job_id, now=_utc_now(), force=force)
        except ValueError as exc:
            return {}, HTTPStatus.CONFLICT, str(exc)
        artifacts = dict(job.artifacts)
        artifacts["stems"] = str(run_dir / "stems" / "manifest.json")
        self._update_job(job, artifacts=artifacts)
        return _manifest_response(job.job_id, manifest, status=_stem_midi_manifest_status(manifest)), HTTPStatus.OK, None

    def render_job_stem_audio(
        self,
        job_id: str,
        *,
        stem_ids: list[str] | None = None,
        force: bool = False,
    ) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            return {}, HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet."
        try:
            manifest = read_stem_manifest(run_dir)
            if manifest is None:
                plan = SongPlan.from_dict(read_json(plan_path))
                manifest = render_stem_midis(plan, run_dir, job.job_id, now=_utc_now())
            else:
                plan = SongPlan.from_dict(read_json(plan_path))
                if stem_manifest_stale(manifest, plan):
                    clear_stem_artifacts(run_dir)
                    return {}, HTTPStatus.CONFLICT, "Stem manifest is stale. Render stems again."
            config, _sources = load_renderer_config()
            config.validate_ready_for_render()
            manifest = render_stem_audio(
                run_dir,
                config,
                plan=plan,
                stem_ids=stem_ids,
                force=force,
                now=_utc_now(),
            )
        except FileNotFoundError as exc:
            return {}, HTTPStatus.NOT_FOUND, str(exc) or "Stem not found."
        except RendererError as exc:
            return {}, HTTPStatus.BAD_REQUEST, str(exc)
        except ValueError as exc:
            return {}, HTTPStatus.CONFLICT, str(exc)
        artifacts = dict(job.artifacts)
        artifacts["stems"] = str(run_dir / "stems" / "manifest.json")
        if any(stem.audio_exists for stem in manifest.stems):
            artifacts["stem_audio"] = str(run_dir / "stems" / "audio")
        self._update_job(job, artifacts=artifacts)
        return _manifest_response(job.job_id, manifest, status=_stem_audio_manifest_status(manifest)), HTTPStatus.OK, None

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job is None:
            return

        request = SongRequest.from_dict(job.input_payload)
        provider_config = None
        provider_snapshot = job.provider_snapshot
        if provider_snapshot.get("mode") == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            ProjectPaths.create(Path(job.output_dir))
            write_json(
                Path(job.output_dir) / "data" / "provider-snapshot.json",
                provider_snapshot,
            )
        if job.cancel_requested:
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
            )
            return
        self._update_job(
            job,
            status="running",
            step="generate",
            message="Generating song plan and MIDI.",
            attempt_count=job.attempt_count + 1,
            started_at=job.started_at or _utc_now(),
            heartbeat_at=_utc_now(),
            stalled=False,
        )
        try:
            append_event(
                ProjectPaths.create(Path(job.output_dir)),
                {"event": "attempt_started", "attempt_count": job.attempt_count},
            )
            job = self.get_job(job_id)
            if job is None or job.cancel_requested:
                if job is not None:
                    self._update_job(
                        job,
                        status="cancelled",
                        step="cancelled",
                        message="Job was cancelled before generation started.",
                    )
                return
            self._heartbeat(job)
            plan_path, midi_path = generate_request(
                request,
                out_dir=Path(job.output_dir),
                force=False,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot if provider_config is not None else None,
                control=self._control_callback(job_id),
                pipeline_mode=job.pipeline_mode,
            )
            clear_stem_artifacts(Path(job.output_dir))
            job = self.get_job(job_id)
            if job is None:
                return
            if job.cancel_requested:
                self._update_job(
                    job,
                    status="cancelled",
                    step="cancelled",
                    message="Job was cancelled after the generation stage.",
                    finished_at=_utc_now(),
                )
                return
            self._heartbeat(job)
            validator_report_path = Path(job.output_dir) / "data" / "validator-report.json"
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            artifacts = {
                "request": str(Path(job.output_dir) / "data" / "request.json"),
                "song_plan": str(plan_path),
                "run_summary": str(Path(job.output_dir) / "data" / "run-summary.json"),
                "validator_report": str(validator_report_path),
                "job_state": str(Path(job.output_dir) / "data" / "job-state.json"),
                "events": str(Path(job.output_dir) / "logs" / "events.jsonl"),
                "midi": str(midi_path),
            }
            provider_snapshot_path = Path(job.output_dir) / "data" / "provider-snapshot.json"
            if provider_snapshot_path.exists():
                artifacts["provider_snapshot"] = str(provider_snapshot_path)
            nodes_dir = Path(job.output_dir) / "data" / "nodes"
            if nodes_dir.exists():
                artifacts["nodes"] = str(nodes_dir)
            self._update_job(
                job,
                status="completed",
                step="completed",
                message="Song generation completed.",
                summary=summary,
                error=None,
                last_error=None,
                finished_at=_utc_now(),
                artifacts=artifacts,
            )
        except JobCancelled:
            job = self.get_job(job_id)
            if job is not None:
                self._update_job(
                    job,
                    status="cancelled",
                    step="cancelled",
                    message="Job was cancelled at a stage boundary.",
                    finished_at=_utc_now(),
                )
        except Exception as exc:
            self._update_job(
                job,
                status="failed",
                step="failed",
                message="Song generation failed.",
                error=str(exc),
                last_error=str(exc),
                finished_at=_utc_now(),
            )

    def _run_node_retry(
        self,
        job_id: str,
        node_name: str,
        affected_nodes: list[str],
        provider_snapshot: dict[str, Any],
    ) -> None:
        job = self.get_job(job_id)
        if job is None:
            return
        request = SongRequest.from_dict(job.input_payload)
        run_dir = Path(job.output_dir)
        paths = ProjectPaths.create(run_dir)
        node_store = NodeStore(run_dir)
        provider_config = None
        if provider_snapshot.get("mode") == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            write_json(paths.data / "provider-snapshot.json", provider_snapshot)
        try:
            append_event(
                paths,
                {"event": "node_retry_requested", "node": node_name, "affected_nodes": affected_nodes},
            )
            invalidated = node_store.invalidate_nodes(affected_nodes, invalidated_by=node_name)
            for record in invalidated:
                append_event(
                    paths,
                    {"event": "node_invalidated", "node": record.node, "invalidated_by": node_name},
                )
            if job.cancel_requested:
                raise JobCancelled()
            self._heartbeat(job)
            plan = rerun_multinode_from_node(
                request,
                node_name,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot if provider_config is not None else None,
                node_store=node_store,
                control=self._control_callback(job_id),
            )
            plan.validate()
            plan_path = paths.data / "song-plan.json"
            midi_path = paths.renders / "song.mid"
            validator_report_path = paths.data / "validator-report.json"
            write_json(plan_path, plan.to_dict())
            render_midi(plan, midi_path)
            clear_stem_artifacts(run_dir)
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            artifacts = _job_artifacts(run_dir, plan_path, midi_path, validator_report_path)
            self._update_job(
                job,
                status="completed",
                step="completed",
                message=f"Node {node_name} retry completed.",
                summary=summary,
                error=None,
                last_error=None,
                finished_at=_utc_now(),
                artifacts=artifacts,
            )
            append_event(
                paths,
                {"event": "node_retry_completed", "node": node_name, "affected_nodes": affected_nodes},
            )
        except JobCancelled:
            latest = self.get_job(job_id)
            if latest is not None:
                self._update_job(
                    latest,
                    status="cancelled",
                    step="cancelled",
                    message="Node retry was cancelled at a stage boundary.",
                    finished_at=_utc_now(),
                )
        except Exception as exc:
            latest = self.get_job(job_id) or job
            self._update_job(
                latest,
                status="failed",
                step="failed",
                message=f"Node {node_name} retry failed.",
                error=str(exc),
                last_error=str(exc),
                finished_at=_utc_now(),
            )

    def _update_job(self, job: JobState, **changes: Any) -> None:
        with self.lock:
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = _utc_now()
            self.jobs[job.job_id] = job
            self._write_job(job)

    def _heartbeat(self, job: JobState) -> None:
        self._update_job(job, heartbeat_at=_utc_now(), last_seen_at=_utc_now())

    def _control_callback(self, job_id: str):
        def control(phase: str, step_name: str) -> None:
            job = self.get_job(job_id)
            if job is None:
                raise JobCancelled()
            self._update_job(
                job,
                heartbeat_at=_utc_now(),
                last_seen_at=_utc_now(),
                step=step_name,
            )
            if job.cancel_requested:
                raise JobCancelled()

        return control

    def _write_job(self, job: JobState) -> None:
        paths = ProjectPaths.create(Path(job.output_dir))
        write_json(paths.data / "job-state.json", job.to_dict())

    def _reserve_run_dir(self, title: str) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(title)
        for index in range(1, 10_000):
            name = slug if index == 1 else f"{slug}-{index}"
            candidate = self.runs_dir / name
            try:
                candidate.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return candidate
        raise RuntimeError(f"Could not allocate a unique run directory for {title!r}.")

    def _ensure_run_dir_is_safe(self, run_dir: Path) -> Path:
        base = self.runs_dir.resolve()
        target = run_dir.resolve()
        if target == base:
            raise ValueError("Refusing to delete runs directory.")
        if base not in target.parents:
            raise ValueError("Refusing to delete outside runs directory.")
        return target

    def _provider_snapshot_for_retry(self, job: JobState) -> dict[str, Any]:
        if job.provider_snapshot.get("mode") != "provider":
            return job.provider_snapshot
        provider_config, _sources = load_provider_config()
        provider_config.validate_ready_for_provider()
        return provider_config.to_snapshot("provider", _utc_now())


class BatchRunner:
    def __init__(self, batch_store: BatchStore, job_store: JobStore) -> None:
        self.batch_store = batch_store
        self.job_store = job_store
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.threads: dict[str, threading.Thread] = {}
        self.audio_threads: dict[str, threading.Thread] = {}
        self.stem_threads: dict[str, threading.Thread] = {}
        self.recover_existing_batches()

    def recover_existing_batches(self) -> None:
        for document in self.batch_store.list_batches(include_hidden=True):
            recovered_audio = self._recover_interrupted_audio(document)
            if recovered_audio:
                self.batch_store.save_batch(document)
                self.batch_store.append_event(
                    document.state.batch_id,
                    "batch_audio_recovered_failed",
                    {"failed_count": recovered_audio},
                )
            if document.state.status not in {"queued", "running", "paused"}:
                continue
            synced = self._sync_running_items(document.state.batch_id)
            if synced is None:
                continue
            if synced.state.queued_count == 0 and synced.state.running_count == 0:
                self._finish_batch(synced)
                continue
            if synced.state.status in {"queued", "running"}:
                synced.state.status = "paused"
                synced.state.error = "Batch was interrupted by a previous server shutdown."
                self.batch_store.save_batch(synced)
                self.batch_store.append_event(
                    synced.state.batch_id,
                    "batch_recovered_paused",
                    {"queued_count": synced.state.queued_count},
                )

    @staticmethod
    def _recover_interrupted_audio(document: BatchDocument) -> int:
        recovered = 0
        for item in document.items:
            if item.audio_status in {"queued", "running"}:
                item.audio_status = "failed"
                item.audio_error = "Audio render was interrupted by a previous server shutdown."
                item.updated_at = now_iso()
                recovered += 1
            if item.stem_status in {"queued", "running"}:
                item.stem_status = "failed"
                item.stem_error = "Stem render was interrupted by a previous server shutdown."
                item.updated_at = now_iso()
                recovered += 1
        return recovered

    def launch_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running":
            return document, HTTPStatus.CONFLICT, "Batch is already running.", 0
        if not any(item.status == "queued" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch has no queued items to launch.", 0
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error, 0

        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        started = self._start_available_items(batch_id)
        document = self.batch_store.get_batch(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(batch_id, "batch_launched", {"started_count": started})
        return document, HTTPStatus.ACCEPTED, None, started

    def pause_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status not in {"running", "queued"}:
            return document, HTTPStatus.CONFLICT, "Only a running batch can be paused."
        document.state.status = "paused"
        document.state.error = None
        self.batch_store.save_batch(document)
        self.batch_store.append_event(batch_id, "batch_paused", {})
        return document, HTTPStatus.OK, None

    def resume_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status != "paused":
            return document, HTTPStatus.CONFLICT, "Only a paused batch can be resumed."
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error
        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        self._start_available_items(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(batch_id, "batch_resumed", {})
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None

    def retry_failed(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        if document.state.status == "running":
            return document, HTTPStatus.CONFLICT, "Cannot retry failed items while the batch is running.", 0
        reset_count = 0
        for item in document.items:
            if item.status in {"failed", "cancelled"}:
                item.status = "queued"
                item.error = None
                item.job_id = None
                item.output_dir = None
                item.audio_status = "not_started"
                item.audio_path = None
                item.audio_error = None
                item.stem_status = "not_started"
                item.stem_manifest_path = None
                item.stem_count = 0
                item.stem_audio_completed_count = 0
                item.stem_error = None
                item.updated_at = now_iso()
                reset_count += 1
        if reset_count == 0:
            return document, HTTPStatus.CONFLICT, "Batch has no failed items to retry.", 0
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error, 0
        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        started = self._start_available_items(batch_id)
        document = self.batch_store.get_batch(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(
            batch_id,
            "batch_retry_failed",
            {"reset_count": reset_count, "started_count": started},
        )
        return document, HTTPStatus.ACCEPTED, None, reset_count

    def render_audio(
        self,
        batch_id: str,
        *,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Cannot render batch audio while batch generation is running.", 0
        if any(item.audio_status in {"queued", "running"} for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch audio render is already running.", 0
        renderer_error = self._renderer_readiness_error()
        if renderer_error is not None:
            return document, HTTPStatus.BAD_REQUEST, renderer_error, 0

        queued_count = 0
        for item in document.items:
            if failed_only and item.audio_status != "failed":
                continue
            if item.status != "completed":
                if not failed_only and item.audio_status == "not_started":
                    item.audio_status = "skipped"
                    item.audio_error = "Batch item is not completed."
                    item.updated_at = now_iso()
                continue
            if not failed_only and item.audio_status == "completed" and item.audio_path:
                continue
            item.audio_status = "queued"
            item.audio_path = None
            item.audio_error = None
            item.updated_at = now_iso()
            queued_count += 1

        if queued_count == 0:
            message = (
                "Batch has no failed audio renders to retry."
                if failed_only
                else "Batch has no completed items that need audio render."
            )
            return document, HTTPStatus.CONFLICT, message, 0

        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            batch_id,
            "batch_audio_render_requested",
            {"queued_count": queued_count, "failed_only": failed_only},
        )
        self._start_available_audio_items(batch_id)
        self._ensure_audio_thread(batch_id)
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None, queued_count

    def render_stems(
        self,
        batch_id: str,
        *,
        audio: bool = False,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Cannot render batch stems while batch generation is running.", 0
        if any(item.stem_status in {"queued", "running"} for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch stem render is already running.", 0
        if audio:
            renderer_error = self._renderer_readiness_error()
            if renderer_error is not None:
                return document, HTTPStatus.BAD_REQUEST, renderer_error, 0

        queued_count = 0
        for item in document.items:
            if failed_only and item.stem_status not in {"failed", "partial_failed"}:
                continue
            if item.status != "completed":
                if not failed_only and item.stem_status == "not_started":
                    item.stem_status = "skipped"
                    item.stem_error = "Batch item is not completed."
                    item.updated_at = now_iso()
                continue
            if (
                not audio
                and not failed_only
                and item.stem_status == "completed"
                and item.stem_manifest_path
            ):
                continue
            if (
                audio
                and item.stem_status == "completed"
                and item.stem_count
                and item.stem_audio_completed_count >= item.stem_count
            ):
                continue
            if audio and not item.stem_manifest_path and item.stem_status not in {"failed", "partial_failed"}:
                continue
            if not audio:
                item.stem_manifest_path = None
                item.stem_count = 0
                item.stem_audio_completed_count = 0
            item.stem_status = "queued"
            item.stem_error = None
            item.updated_at = now_iso()
            queued_count += 1

        if queued_count == 0:
            if failed_only:
                message = "Batch has no failed stem renders to retry."
            elif audio:
                message = "Batch has no completed items that need stem audio render."
            else:
                message = "Batch has no completed items that need stem render."
            return document, HTTPStatus.CONFLICT, message, 0

        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            batch_id,
            "batch_stem_render_requested",
            {"queued_count": queued_count, "audio": audio, "failed_only": failed_only},
        )
        self._start_available_stem_items(batch_id, audio=audio)
        self._ensure_stem_thread(batch_id, audio=audio)
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None, queued_count

    def delete_batch(self, batch_id: str) -> tuple[bool, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return False, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return False, HTTPStatus.CONFLICT, "Cannot delete a running batch. Pause it first."
        self.batch_store.delete_batch(batch_id)
        return True, HTTPStatus.OK, None

    def shutdown(self) -> None:
        self.stop_event.set()
        with self.lock:
            threads = [*self.threads.values(), *self.audio_threads.values(), *self.stem_threads.values()]
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2)

    def _run_batch(self, batch_id: str) -> None:
        try:
            while not self.stop_event.is_set():
                document = self._sync_running_items(batch_id)
                if document is None:
                    return
                if document.state.status == "paused":
                    if document.state.running_count == 0:
                        return
                    time.sleep(0.1)
                    continue
                if document.state.status != "running":
                    return
                self._start_available_items(batch_id)
                document = self._sync_running_items(batch_id)
                if document is None:
                    return
                if document.state.status == "running" and document.state.queued_count == 0 and document.state.running_count == 0:
                    self._finish_batch(document)
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.threads.pop(batch_id, None)

    def _run_batch_audio(self, batch_id: str) -> None:
        try:
            while not self.stop_event.is_set():
                self._start_available_audio_items(batch_id)
                document = self._sync_audio_items(batch_id)
                if document is None:
                    return
                if not any(item.audio_status in {"queued", "running"} for item in document.items):
                    self.batch_store.append_event(
                        batch_id,
                        "batch_audio_render_finished",
                        self._audio_counts(document),
                    )
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.audio_threads.pop(batch_id, None)

    def _run_batch_stems(self, batch_id: str, audio: bool) -> None:
        try:
            while not self.stop_event.is_set():
                self._start_available_stem_items(batch_id, audio=audio)
                document = self._sync_stem_items(batch_id)
                if document is None:
                    return
                if not any(item.stem_status in {"queued", "running"} for item in document.items):
                    self.batch_store.append_event(
                        batch_id,
                        "batch_stem_render_finished",
                        self._stem_counts(document),
                    )
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.stem_threads.pop(batch_id, None)

    def _ensure_thread(self, batch_id: str) -> None:
        with self.lock:
            existing = self.threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch,
                args=(batch_id,),
                name=f"musicforge-batch-{batch_id}",
                daemon=True,
            )
            self.threads[batch_id] = thread
            thread.start()

    def _ensure_audio_thread(self, batch_id: str) -> None:
        with self.lock:
            existing = self.audio_threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch_audio,
                args=(batch_id,),
                name=f"musicforge-batch-audio-{batch_id}",
                daemon=True,
            )
            self.audio_threads[batch_id] = thread
            thread.start()

    def _ensure_stem_thread(self, batch_id: str, *, audio: bool) -> None:
        with self.lock:
            existing = self.stem_threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch_stems,
                args=(batch_id, audio),
                name=f"musicforge-batch-stems-{batch_id}",
                daemon=True,
            )
            self.stem_threads[batch_id] = thread
            thread.start()

    def _start_available_items(self, batch_id: str) -> int:
        with self.lock:
            document = self.batch_store.get_batch(batch_id)
            if document.state.status != "running":
                return 0
            running_count = sum(1 for item in document.items if item.status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            for item in document.items:
                if item.status != "queued" or started >= available:
                    continue
                try:
                    job = self.job_store.create_job(item.request, start_immediately=True)
                except Exception as exc:
                    item.status = "failed"
                    item.error = str(exc)
                    item.updated_at = now_iso()
                    document.state.error = str(exc)
                    continue
                item.status = "running"
                item.job_id = job.job_id
                item.output_dir = job.output_dir
                item.error = None
                item.attempt_count += 1
                item.updated_at = now_iso()
                started += 1
                self.batch_store.append_event(
                    batch_id,
                    "batch_item_started",
                    {
                        "item_id": item.item_id,
                        "job_id": job.job_id,
                        "attempt_count": item.attempt_count,
                    },
                )
            self.batch_store.save_batch(document)
            return started

    def _sync_running_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None
            changed = False
            for item in document.items:
                if item.status != "running" or not item.job_id:
                    continue
                job = self.job_store.get_job(item.job_id)
                if job is None:
                    item.status = "failed"
                    item.error = "Linked job is missing."
                    item.updated_at = now_iso()
                    changed = True
                    continue
                if job.output_dir:
                    item.output_dir = job.output_dir
                if job.status == "completed":
                    item.status = "completed"
                    item.error = None
                    item.updated_at = now_iso()
                    changed = True
                    self.batch_store.append_event(
                        batch_id,
                        "batch_item_completed",
                        {"item_id": item.item_id, "job_id": job.job_id},
                    )
                elif job.status == "cancelled":
                    item.status = "cancelled"
                    item.error = job.error or "Job was cancelled."
                    item.updated_at = now_iso()
                    changed = True
                elif job.status in {"failed", "interrupted", "stalled"}:
                    item.status = "failed"
                    item.error = job.error or job.last_error or f"Job ended with status {job.status}."
                    item.updated_at = now_iso()
                    changed = True
            if changed:
                self.batch_store.save_batch(document)
                document = self.batch_store.get_batch(batch_id)
            return document

    def _start_available_audio_items(self, batch_id: str) -> int:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return 0
            running_count = sum(1 for item in document.items if item.audio_status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            threads_to_start: list[threading.Thread] = []
            for item in document.items:
                if item.audio_status != "queued" or started >= available:
                    continue
                if item.status != "completed" or not item.job_id:
                    item.audio_status = "failed"
                    item.audio_error = "Batch item does not have a completed job."
                    item.updated_at = now_iso()
                    continue
                item.audio_status = "running"
                item.audio_error = None
                item.updated_at = now_iso()
                started += 1
                threads_to_start.append(
                    threading.Thread(
                        target=self._render_audio_item,
                        args=(batch_id, item.item_id, item.job_id),
                        name=f"musicforge-batch-audio-item-{batch_id}-{item.item_id}",
                        daemon=True,
                    )
                )
                self.batch_store.append_event(
                    batch_id,
                    "batch_audio_item_started",
                    {"item_id": item.item_id, "job_id": item.job_id},
                )
            self.batch_store.save_batch(document)
            for thread in threads_to_start:
                thread.start()
            return started

    def _render_audio_item(self, batch_id: str, item_id: str, job_id: str) -> None:
        audio, status, error = self.job_store.render_job_audio(job_id)
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return
            for item in document.items:
                if item.item_id != item_id:
                    continue
                if error is None and status == HTTPStatus.OK:
                    item.audio_status = "completed"
                    item.audio_path = audio.get("audio")
                    item.audio_error = None
                    event_type = "batch_audio_item_completed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "audio": item.audio_path}
                else:
                    item.audio_status = "failed"
                    item.audio_path = None
                    item.audio_error = error or f"Audio render failed with status {status.value}."
                    event_type = "batch_audio_item_failed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "error": item.audio_error}
                item.updated_at = now_iso()
                self.batch_store.save_batch(document)
                self.batch_store.append_event(batch_id, event_type, payload)
                return

    def _start_available_stem_items(self, batch_id: str, *, audio: bool) -> int:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return 0
            running_count = sum(1 for item in document.items if item.stem_status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            threads_to_start: list[threading.Thread] = []
            for item in document.items:
                if item.stem_status != "queued" or started >= available:
                    continue
                if item.status != "completed" or not item.job_id:
                    item.stem_status = "failed"
                    item.stem_error = "Batch item does not have a completed job."
                    item.updated_at = now_iso()
                    continue
                item.stem_status = "running"
                item.stem_error = None
                item.updated_at = now_iso()
                started += 1
                threads_to_start.append(
                    threading.Thread(
                        target=self._render_stem_item,
                        args=(batch_id, item.item_id, item.job_id, audio),
                        name=f"musicforge-batch-stem-item-{batch_id}-{item.item_id}",
                        daemon=True,
                    )
                )
                self.batch_store.append_event(
                    batch_id,
                    "batch_stem_item_started",
                    {"item_id": item.item_id, "job_id": item.job_id, "audio": audio},
                )
            self.batch_store.save_batch(document)
            for thread in threads_to_start:
                thread.start()
            return started

    def _render_stem_item(self, batch_id: str, item_id: str, job_id: str, audio: bool) -> None:
        if audio:
            data, status, error = self.job_store.render_job_stem_audio(job_id)
        else:
            data, status, error = self.job_store.render_job_stems(job_id)
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return
            for item in document.items:
                if item.item_id != item_id:
                    continue
                job = self.job_store.get_job(job_id)
                if error is None and status == HTTPStatus.OK:
                    manifest = data.get("manifest", {})
                    stems = manifest.get("stems", [])
                    item.stem_manifest_path = str(Path(job.output_dir) / "stems" / "manifest.json") if job else item.stem_manifest_path
                    item.stem_count = len(stems)
                    item.stem_audio_completed_count = sum(1 for stem in stems if stem.get("audio_status") == "completed")
                    item.stem_status = data.get("status", "completed")
                    item.stem_error = (
                        "One or more stems failed."
                        if item.stem_status in {"partial_failed", "failed"}
                        else None
                    )
                    event_type = "batch_stem_item_completed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "status": item.stem_status}
                else:
                    item.stem_status = "failed"
                    item.stem_error = error or f"Stem render failed with status {status.value}."
                    event_type = "batch_stem_item_failed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "error": item.stem_error}
                item.updated_at = now_iso()
                self.batch_store.save_batch(document)
                self.batch_store.append_event(batch_id, event_type, payload)
                return

    def _sync_audio_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                return self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None

    def _sync_stem_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                return self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None

    def _finish_batch(self, document: BatchDocument) -> None:
        if document.state.failed_count or document.state.cancelled_count:
            document.state.status = "completed_with_errors"
            document.state.error = "One or more batch items failed."
        else:
            document.state.status = "completed"
            document.state.error = None
        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            document.state.batch_id,
            "batch_finished",
            {"status": document.state.status},
        )

    @staticmethod
    def _provider_readiness_error(document: BatchDocument) -> str | None:
        if not any(
            item.status == "queued" and item.request.get("generation_mode") == "provider"
            for item in document.items
        ):
            return None
        provider_config, _sources = load_provider_config()
        try:
            provider_config.validate_ready_for_provider()
        except ProviderError as exc:
            return str(exc)
        return None

    @staticmethod
    def _renderer_readiness_error() -> str | None:
        config, _sources = load_renderer_config()
        try:
            config.validate_ready_for_render()
        except RendererError as exc:
            return str(exc)
        return None

    @staticmethod
    def _audio_counts(document: BatchDocument) -> dict[str, int]:
        counts = {
            "not_started": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in document.items:
            counts[item.audio_status] = counts.get(item.audio_status, 0) + 1
        return counts

    @staticmethod
    def _stem_counts(document: BatchDocument) -> dict[str, int]:
        counts = {
            "not_started": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "partial_completed": 0,
            "partial_failed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in document.items:
            counts[item.stem_status] = counts.get(item.stem_status, 0) + 1
        return counts


class MusicForgeHandler(BaseHTTPRequestHandler):
    server_version = "MusicForgeHTTP/0.1"

    def do_GET(self) -> None:
        self._handle_request("GET")

    def do_POST(self) -> None:
        self._handle_request("POST")

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def store(self) -> JobStore:
        return self.server.job_store  # type: ignore[attr-defined]

    @property
    def batch_store(self) -> BatchStore:
        return self.server.batch_store  # type: ignore[attr-defined]

    @property
    def batch_runner(self) -> BatchRunner:
        return self.server.batch_runner  # type: ignore[attr-defined]

    @property
    def project_store(self) -> ProjectStore:
        return self.server.project_store  # type: ignore[attr-defined]

    @property
    def auth_config(self) -> AuthConfig:
        return self.server.auth_config  # type: ignore[attr-defined]

    def _handle_request(self, method: str) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if self._auth_required(path) and not self._is_authorized():
                self._send_unauthorized()
                return
            if method == "GET" and path == "/":
                self._send_html(panel_html())
                return
            if method == "GET" and path == "/api/info":
                self._send_json(
                    api_info(
                        self.auth_config,
                        authorized=(not self.auth_config.enabled) or self._is_authorized(),
                    )
                )
                return
            if method == "GET" and path == "/api/template":
                self._send_json(api_template())
                return
            if path == "/api/provider":
                self._handle_provider_route(method)
                return
            if path == "/api/provider/reset":
                self._handle_provider_reset(method)
                return
            if path == "/api/provider/test":
                self._handle_provider_test(method)
                return
            if path == "/api/renderer":
                self._handle_renderer_route(method)
                return
            if path == "/api/renderer/reset":
                self._handle_renderer_reset(method)
                return
            if path == "/api/renderer/test":
                self._handle_renderer_test(method)
                return
            if path == "/api/jobs":
                if method == "GET":
                    query = parse_qs(parsed.query)
                    include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
                    self._send_json(
                        {
                            "jobs": [
                                job.to_dict()
                                for job in self.store.list_jobs(include_hidden=include_hidden)
                            ]
                        }
                    )
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    job = self.store.create_job(payload)
                    self._send_json(job.to_dict(), status=HTTPStatus.ACCEPTED)
                    return

            if path == "/api/batches":
                if method == "GET":
                    query = parse_qs(parsed.query)
                    include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
                    self._send_json(
                        {
                            "batches": [
                                document.state.to_dict()
                                for document in self.batch_store.list_batches(
                                    include_hidden=include_hidden
                                )
                            ]
                        }
                    )
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if path == "/api/batches/import-csv":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                document = self.batch_store.import_csv(
                    name=str(payload.get("name") or "Untitled Batch"),
                    csv_text=str(payload.get("csv_text") or ""),
                    generation_mode=str(payload.get("generation_mode") or "local"),
                    pipeline_mode=str(payload.get("pipeline_mode") or "multinode"),
                    max_concurrency=payload.get("max_concurrency", 1),
                )
                self._send_json(document.to_dict(), status=HTTPStatus.CREATED)
                return

            if path == "/api/projects":
                self._handle_projects_root(method, parsed.query)
                return

            project_route = _match_project_route(path)
            if project_route is not None:
                project_id, tail = project_route
                self._handle_project_route(method, project_id, tail, parsed.query)
                return

            batch_route = _match_batch_route(path)
            if batch_route is not None:
                batch_id, tail = batch_route
                self._handle_batch_route(method, batch_id, tail)
                return

            job_route = _match_job_route(path)
            if job_route is not None:
                job_id, tail = job_route
                self._handle_job_route(method, job_id, tail)
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Route not found.")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))

    def _handle_provider_route(self, method: str) -> None:
        if method == "GET":
            config, sources = load_provider_config()
            self._send_json(
                {
                    "configured": provider_configured(config),
                    "config": config.to_public_dict(sources),
                }
            )
            return
        if method == "POST":
            config = save_provider_config_from_dict(self._read_json_body())
            self._send_json(
                {
                    "ok": True,
                    "configured": provider_configured(config),
                    "config": config.to_public_dict(),
                }
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_provider_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        reset_provider_config()
        config, _sources = load_provider_config()
        self._send_json({"ok": True, "configured": provider_configured(config)})

    def _handle_provider_test(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        config, _sources = load_provider_config()
        self._send_json(test_provider_config(config))

    def _handle_renderer_route(self, method: str) -> None:
        if method == "GET":
            config, sources = load_renderer_config()
            self._send_json(
                {
                    "configured": renderer_configured(config),
                    "config": config.to_public_dict(sources),
                }
            )
            return
        if method == "POST":
            config = save_renderer_config_from_dict(self._read_json_body())
            self._send_json(
                {
                    "ok": True,
                    "configured": renderer_configured(config),
                    "config": config.to_public_dict(),
                }
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_renderer_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        reset_renderer_config()
        config, _sources = load_renderer_config()
        self._send_json({"ok": True, "configured": renderer_configured(config)})

    def _handle_renderer_test(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        config, _sources = load_renderer_config()
        self._send_json(test_renderer_config(config))

    def _handle_projects_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
            self._send_json(
                {
                    "projects": [
                        self.project_store.sync_project(document.state.project_id, self.store.get_job).state.to_dict()
                        for document in self.project_store.list_projects(include_hidden=include_hidden)
                    ]
                }
            )
            return
        if method == "POST":
            payload = self._read_json_body()
            document = self.project_store.create_project(
                name=str(payload.get("name") or payload.get("title") or "Untitled Project"),
                description=str(payload.get("description") or ""),
                tags=_string_list(payload.get("tags")),
            )
            job = None
            if isinstance(payload.get("request"), dict):
                request_payload = {
                    **payload["request"],
                    "generation_mode": payload.get("generation_mode", payload["request"].get("generation_mode", "local")),
                    "pipeline_mode": payload.get("pipeline_mode", payload["request"].get("pipeline_mode", "single")),
                }
                job = self.store.create_job(request_payload)
                document = self.project_store.add_version_from_job(
                    document.state.project_id,
                    job,
                    name=str(payload.get("version_name") or "Version 1"),
                    note=str(payload.get("version_note") or ""),
                )
            self._send_json(
                {
                    **document.to_dict(),
                    "job": job.to_dict() if job is not None else None,
                },
                status=HTTPStatus.CREATED,
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_project_route(self, method: str, project_id: str, tail: str, query_string: str) -> None:
        if tail == "":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json(document.to_dict())
            return

        if tail == "/versions":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            request_data = payload.get("request")
            if not isinstance(request_data, dict):
                self._send_error(HTTPStatus.BAD_REQUEST, "request must be an object.")
                return
            try:
                self.project_store.get_project(project_id)
                request_payload = {
                    **request_data,
                    "generation_mode": payload.get("generation_mode", request_data.get("generation_mode", "local")),
                    "pipeline_mode": payload.get("pipeline_mode", request_data.get("pipeline_mode", "single")),
                }
                job = self.store.create_job(request_payload)
                document = self.project_store.add_version_from_job(
                    project_id,
                    job,
                    name=str(payload.get("name") or ""),
                    note=str(payload.get("note") or ""),
                )
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            except ValueError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self._send_json(
                {"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict()},
                status=HTTPStatus.ACCEPTED,
            )
            return

        if tail == "/versions/from-job":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            job_id = str(payload.get("job_id") or "")
            job = self.store.get_job(job_id)
            if job is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
                return
            try:
                document = self.project_store.add_version_from_job(
                    project_id,
                    job,
                    name=str(payload.get("name") or ""),
                    note=str(payload.get("note") or ""),
                )
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            except ValueError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict()})
            return

        if tail in {"/selected", "/final"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._read_json_body()
            version_id = str(payload.get("version_id") or "")
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                if tail == "/selected":
                    document = self.project_store.set_selected_version(project_id, version_id)
                else:
                    document = self.project_store.set_final_version(project_id, version_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                return
            except ValueError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            self._send_json({"ok": True, **document.to_dict()})
            return

        if tail == "/diff":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            left = str(query.get("left", [""])[0])
            right = str(query.get("right", [""])[0])
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(self.project_store.diff_versions(project_id, left, right))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if tail == "/export":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(self.project_store.export_project(project_id))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return

        if tail == "/events":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.get_project(project_id)
                self._send_json({"events": self.project_store.read_events(project_id)})
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return

        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.project_store.hide_project(project_id, tail == "/hide")
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json({"ok": True, **document.to_dict()})
            return

        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.project_store.delete_project(project_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            self._send_json({"ok": True, "deleted": True, "project_id": project_id})
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Project route not found.")

    def _handle_batch_route(self, method: str, batch_id: str, tail: str) -> None:
        if tail == "":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
                return
            self._send_json(document.to_dict())
            return

        if tail == "/launch":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, started = self.batch_runner.launch_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json(
                {"ok": True, "started_count": started, **document.to_dict()},
                status=status,
            )
            return

        if tail == "/pause":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error = self.batch_runner.pause_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **document.to_dict()}, status=status)
            return

        if tail == "/resume":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error = self.batch_runner.resume_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **document.to_dict()}, status=status)
            return

        if tail == "/retry-failed":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, reset_count = self.batch_runner.retry_failed(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "reset_count": reset_count, **document.to_dict()}, status=status)
            return

        if tail in {"/render-audio", "/render-failed-audio"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, queued_count = self.batch_runner.render_audio(
                batch_id,
                failed_only=tail == "/render-failed-audio",
            )
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "queued_count": queued_count, **document.to_dict()}, status=status)
            return

        if tail in {
            "/render-stems",
            "/render-stem-audio",
            "/render-failed-stems",
            "/render-failed-stem-audio",
        }:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            document, status, error, queued_count = self.batch_runner.render_stems(
                batch_id,
                audio=tail in {"/render-stem-audio", "/render-failed-stem-audio"},
                failed_only=tail in {"/render-failed-stems", "/render-failed-stem-audio"},
            )
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "queued_count": queued_count, **document.to_dict()}, status=status)
            return

        if tail == "/export":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self._send_json(self.batch_store.export_batch(batch_id))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
            return

        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                document = self.batch_store.hide_batch(batch_id, tail == "/hide")
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
                return
            self._send_json({"ok": True, **document.to_dict()})
            return

        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            deleted, status, error = self.batch_runner.delete_batch(batch_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "deleted": deleted, "batch_id": batch_id})
            return

        if tail == "/open-folder":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                batch_dir = self.batch_store.batch_dir(batch_id)
                if not batch_dir.exists():
                    raise FileNotFoundError(batch_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Batch not found.")
                return
            open_folder(batch_dir)
            self._send_json({"ok": True, "path": str(batch_dir)})
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Batch route not found.")

    def _handle_job_route(self, method: str, job_id: str, tail: str) -> None:
        job = self.store.get_job(job_id)
        if job is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
            return

        run_dir = Path(job.output_dir)
        if tail == "/open-folder":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            open_folder(run_dir)
            self._send_json({"ok": True, "path": str(run_dir)})
            return
        if tail in {"/hide", "/unhide"}:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job = self.store.hide_job(job_id, hidden=tail == "/hide")
            if job is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
                return
            self._send_json({"ok": True, "job": job.to_dict()})
            return
        if tail == "/cancel":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job, status, error = self.store.cancel_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "job": job.to_dict() if job is not None else None})
            return
        if tail == "/retry":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            job, status, error = self.store.retry_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "job": job.to_dict() if job is not None else None})
            return
        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            deleted, status, error = self.store.delete_job(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "deleted": deleted, "job_id": job_id})
            return
        if tail == "/render-audio":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            audio, status, error = self.store.render_job_audio(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, "job_id": job_id, **audio}, status=status)
            return
        if tail == "/render-stems":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            data, status, error = self.store.render_job_stems(job_id, force=bool(payload.get("force", False)))
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **data}, status=status)
            return
        if tail == "/render-stem-audio":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            payload = self._optional_json_body()
            stem_ids = payload.get("stem_ids")
            if stem_ids is not None:
                if not isinstance(stem_ids, list):
                    self._send_error(HTTPStatus.BAD_REQUEST, "stem_ids must be a list.")
                    return
                stem_ids = [str(stem_id) for stem_id in stem_ids]
            data, status, error = self.store.render_job_stem_audio(
                job_id,
                stem_ids=stem_ids,
                force=bool(payload.get("force", False)),
            )
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json({"ok": True, **data}, status=status)
            return
        if tail.startswith("/nodes/") and tail.endswith("/retry"):
            self._send_node_retry(method, job, tail)
            return

        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return

        if tail == "":
            self._send_json(job.to_dict())
            return
        if tail == "/song-plan":
            plan_path = run_dir / "data" / "song-plan.json"
            if not plan_path.exists():
                self._send_error(
                    HTTPStatus.CONFLICT,
                    "song-plan.json is not available for this job yet.",
                )
                return
            self._send_json(read_json(plan_path))
            return
        if tail == "/timeline":
            self._send_runtime_view(job, "timeline")
            return
        if tail == "/tracks":
            self._send_runtime_view(job, "tracks")
            return
        if tail == "/validator":
            self._send_runtime_view(job, "validator")
            return
        if tail == "/quality":
            self._send_runtime_view(job, "quality")
            return
        if tail == "/events":
            self._send_json({"events": _read_events(run_dir / "logs" / "events.jsonl")})
            return
        if tail == "/artifacts":
            self._send_json({"artifacts": discover_artifacts(run_dir)})
            return
        if tail == "/midi":
            self._send_file(run_dir / "renders" / "song.mid", "audio/midi")
            return
        if tail == "/audio":
            audio_path = run_dir / "renders" / "song.wav"
            if not audio_path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Audio render is not available for this job.")
                return
            self._send_file(audio_path, "audio/wav")
            return
        if tail == "/stems":
            data, status, error = self.store.get_job_stems(job_id)
            if error is not None:
                self._send_error(status, error)
                return
            self._send_json(data, status=status)
            return
        if tail.startswith("/stems/"):
            self._send_stem_file(job, tail)
            return
        if tail == "/nodes":
            self._send_nodes_list(job)
            return
        if tail.startswith("/nodes/"):
            self._send_node_route(method, job, tail)
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Job route not found.")

    def _send_runtime_view(self, job: JobState, view_name: str) -> None:
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        validator_path = run_dir / "data" / "validator-report.json"
        if view_name in {"timeline", "tracks", "quality"} and not plan_path.exists():
            self._send_error(
                HTTPStatus.CONFLICT,
                "song-plan.json is not available for this job yet.",
            )
            return

        if view_name == "validator":
            report = read_json(validator_path) if validator_path.exists() else None
            plan = read_json(plan_path) if plan_path.exists() else None
            self._send_json(
                {
                    "job_id": job.job_id,
                    "view": build_validator_view(report, plan),
                }
            )
            return
        if view_name == "quality":
            plan = read_json(plan_path)
            critic_report = _read_critic_report(run_dir)
            self._send_json(
                {
                    "job_id": job.job_id,
                    "view": build_quality_view(plan, critic_report),
                }
            )
            return

        plan = read_json(plan_path)
        if view_name == "timeline":
            view = build_timeline_view(plan)
        elif view_name == "tracks":
            view = build_tracks_view(plan)
        else:
            self._send_error(HTTPStatus.NOT_FOUND, "Runtime view not found.")
            return
        self._send_json({"job_id": job.job_id, "view": view})

    def _send_nodes_list(self, job: JobState) -> None:
        records = NodeStore(Path(job.output_dir)).list_nodes()
        self._send_json(
            {
                "job_id": job.job_id,
                "nodes": [record.to_summary_dict() for record in records],
            }
        )

    def _send_node_retry(self, method: str, job: JobState, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "nodes" or parts[2] != "retry":
            self._send_error(HTTPStatus.NOT_FOUND, "Node route not found.")
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        node_name = unquote(parts[1])
        job, status, error, retry = self.store.retry_job_node(job.job_id, node_name)
        if error is not None:
            self._send_error(status, error)
            return
        self._send_json(
            {"ok": True, "job": job.to_dict() if job is not None else None, "retry": retry},
            status=status,
        )

    def _send_node_route(self, method: str, job: JobState, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) == 2:
            _nodes, node_name = parts
            try:
                record = NodeStore(Path(job.output_dir)).read_node(unquote(node_name))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Node record not found.")
                return
            self._send_json({"job_id": job.job_id, "node": record.to_dict()})
            return
        if len(parts) == 3 and parts[2] == "dependencies":
            try:
                node_name = unquote(parts[1])
                upstream = upstream_nodes(node_name)
                downstream = downstream_nodes(node_name)
            except ValueError as exc:
                if str(exc).startswith("Unknown node:"):
                    self._send_error(HTTPStatus.NOT_FOUND, "Node record not found.")
                    return
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(
                {
                    "job_id": job.job_id,
                    "node": node_name,
                    "upstream": upstream,
                    "downstream": downstream,
                    "affected_nodes": [node_name, *downstream],
                }
            )
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Node route not found.")

    def _send_stem_file(self, job: JobState, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "stems" or parts[2] not in {"midi", "audio"}:
            self._send_error(HTTPStatus.NOT_FOUND, "Stem route not found.")
            return
        stem_id = unquote(parts[1])
        run_dir = Path(job.output_dir)
        manifest = read_stem_manifest(run_dir)
        if manifest is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Stem manifest not found.")
            return
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            if stem_manifest_stale(manifest, plan):
                clear_stem_artifacts(run_dir)
                self._send_error(HTTPStatus.CONFLICT, "Stem manifest is stale. Render stems again.")
                return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        try:
            if parts[2] == "midi":
                self._send_file(stem_midi_path(run_dir, manifest, stem_id), "audio/midi")
            else:
                self._send_file(stem_audio_path(run_dir, manifest, stem_id), "audio/wav")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Stem not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            raise ValueError("Request body must be JSON.")
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _optional_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        if not body:
            return {}
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object.")
        return data

    def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK.value)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.exists() or not path.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "File not found.")
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK.value)
        self.send_header(
            "Content-Type",
            content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json({"error": message}, status=status)

    def _send_unauthorized(self) -> None:
        body = b'{\n  "error": "Unauthorized."\n}'
        self.send_response(HTTPStatus.UNAUTHORIZED.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("WWW-Authenticate", "Bearer")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth_required(self, path: str) -> bool:
        if not self.auth_config.enabled:
            return False
        if path == "/" or path == "/api/info":
            return False
        return True

    def _is_authorized(self) -> bool:
        token = self.auth_config.token
        if not token:
            return False
        return validate_bearer_header(self.headers.get("Authorization"), token)


class MusicForgeHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        auth_config: AuthConfig | None = None,
    ) -> None:
        super().__init__(server_address, MusicForgeHandler)
        self.auth_config = auth_config or AuthConfig(enabled=False)
        self.job_store = JobStore()
        self.batch_store = BatchStore()
        self.project_store = ProjectStore()
        self.batch_runner = BatchRunner(self.batch_store, self.job_store)
        self.watchdog_stop = threading.Event()
        self.watchdog_thread = _start_watchdog(self.job_store, self.watchdog_stop)

    def server_close(self) -> None:
        self.batch_runner.shutdown()
        self.watchdog_stop.set()
        if self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=2)
        super().server_close()


def create_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    auth_config: AuthConfig | None = None,
) -> MusicForgeHTTPServer:
    return MusicForgeHTTPServer((host, port), auth_config=auth_config)


def serve(
    host: str = "127.0.0.1",
    port: int = 8787,
    auth_config: AuthConfig | None = None,
) -> None:
    server = create_server(host, port, auth_config=auth_config)
    url = f"http://{host}:{port}"
    print(f"MusicForge Studio running at {url}")
    if server.auth_config.enabled:
        print("Access control: enabled")
    else:
        print("Access control: disabled for localhost")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping MusicForge Studio.")
    finally:
        server.server_close()


def api_info(
    auth_config: AuthConfig | None = None,
    *,
    authorized: bool = True,
) -> dict[str, Any]:
    auth_required = bool(auth_config and auth_config.enabled)
    public_info: dict[str, Any] = {
        "app": "MusicForge",
        "version": __version__,
        "auth_required": auth_required,
    }
    if auth_required and not authorized:
        return public_info
    return {
        **public_info,
        "cwd": str(Path.cwd()),
        "runs_dir": str(RUNS_DIR),
        "mode": "local-deterministic",
        "provider": {"enabled": False, "summary": "Local deterministic composer"},
    }


def api_template() -> dict[str, Any]:
    return {
        "defaults": {
            "title": "Rainy Convenience Store",
            "language": "zh",
            "style": "city pop, soft rock, warm synths, clean electric guitar",
            "theme": "a person remembers an old friend during a rainy night in the city",
            "duration_seconds": 180,
            "vocal_mode": "guide_melody",
            "tempo_bpm": 92,
            "key": "C major",
        },
        "presets": [
            {
                "name": "City Pop 120s",
                "style": "city pop, soft rock, warm synths, clean electric guitar",
                "duration_seconds": 120,
                "tempo_bpm": 92,
                "key": "C major",
            },
            {
                "name": "Lo-fi Loop 60s",
                "style": "lo-fi hip hop, mellow keys, dusty drums",
                "duration_seconds": 60,
                "tempo_bpm": 78,
                "key": "A minor",
            },
            {
                "name": "Game Battle Loop 45s",
                "style": "game battle loop, synth bass, tight drums",
                "duration_seconds": 45,
                "tempo_bpm": 132,
                "key": "D minor",
            },
        ],
    }


def discover_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            artifacts.append(
                _artifact_dict(path)
            )
    return artifacts


def open_folder(path: Path) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    webbrowser.open(path.resolve().as_uri())


def _build_summary(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    tracks = plan.get("tracks", [])
    sections = plan.get("sections", [])
    return {
        "title": plan.get("title"),
        "tempo_bpm": plan.get("tempo_bpm"),
        "key": plan.get("key"),
        "meter": plan.get("meter"),
        "section_count": len(sections),
        "track_count": len(tracks),
        "note_count": sum(len(track.get("notes", [])) for track in tracks),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
    }


def _build_validator_report(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    return {
        "status": "passed",
        "checks": [
            "song_request_schema",
            "song_plan_schema",
            "song_plan_validation",
            "midi_render",
        ],
        "title": plan.get("title"),
        "midi_path": str(midi_path),
        "midi_exists": midi_path.exists(),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
        "checked_at": _utc_now(),
    }


def _audio_report(audio_path: Path) -> dict[str, Any]:
    return {
        "exists": audio_path.exists(),
        "path": str(audio_path),
        "size_bytes": audio_path.stat().st_size if audio_path.exists() else 0,
    }


def _manifest_response(
    job_id: str,
    manifest: StemManifest,
    *,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": status or _stem_manifest_status(manifest),
        "manifest": manifest.to_dict(),
    }


def _stem_midi_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    if all(stem.midi_exists or stem.audio_status == "skipped" for stem in manifest.stems):
        return "completed"
    if any(stem.midi_exists for stem in manifest.stems):
        return "partial_failed"
    return "failed"


def _stem_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    if any(stem.audio_exists for stem in manifest.stems):
        return _stem_audio_manifest_status(manifest)
    if any(stem.midi_exists for stem in manifest.stems):
        return _stem_midi_manifest_status(manifest)
    return "not_started"


def _stem_audio_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    statuses = {stem.audio_status for stem in manifest.stems}
    if statuses <= {"completed", "skipped"}:
        return "completed"
    if "failed" in statuses and ("completed" in statuses or "skipped" in statuses):
        return "partial_failed"
    if "failed" in statuses:
        return "failed"
    if "completed" in statuses:
        return "partial_completed"
    return "not_started"


def _job_artifacts(
    run_dir: Path,
    plan_path: Path,
    midi_path: Path,
    validator_report_path: Path,
) -> dict[str, str]:
    artifacts = {
        "request": str(run_dir / "data" / "request.json"),
        "song_plan": str(plan_path),
        "run_summary": str(run_dir / "data" / "run-summary.json"),
        "validator_report": str(validator_report_path),
        "job_state": str(run_dir / "data" / "job-state.json"),
        "events": str(run_dir / "logs" / "events.jsonl"),
        "midi": str(midi_path),
    }
    provider_snapshot_path = run_dir / "data" / "provider-snapshot.json"
    if provider_snapshot_path.exists():
        artifacts["provider_snapshot"] = str(provider_snapshot_path)
    nodes_dir = run_dir / "data" / "nodes"
    if nodes_dir.exists():
        artifacts["nodes"] = str(nodes_dir)
    return artifacts


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def _read_critic_report(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "data" / "nodes" / "critic.json"
    if not path.exists():
        return None
    try:
        record = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    output = record.get("output")
    return output if isinstance(output, dict) else None


def _match_job_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/jobs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if "/" in rest:
        job_id, tail = rest.split("/", 1)
        return unquote(job_id), "/" + tail
    return unquote(rest), ""


def _match_batch_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/batches/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "import-csv":
        return None
    if "/" in rest:
        batch_id, tail = rest.split("/", 1)
        return unquote(batch_id), "/" + tail
    return unquote(rest), ""


def _match_project_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/projects/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        project_id, tail = rest.split("/", 1)
        return unquote(project_id), "/" + tail
    return unquote(rest), ""


def _artifact_kind(path: Path) -> str:
    if path.suffix == ".json":
        return "json"
    if path.suffix == ".jsonl":
        return "events"
    if path.suffix == ".mid":
        return "midi"
    if path.suffix == ".wav":
        return "audio"
    return "file"


def _artifact_dict(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "path": str(path),
        "kind": _artifact_kind(path),
        "size": path.stat().st_size,
        "size_bytes": path.stat().st_size,
    }


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be a list.")
    return [str(item).strip() for item in value if str(item).strip()]


def _generation_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("generation_mode", "local") or "local")
    if mode not in {"local", "provider"}:
        raise ValueError("generation_mode must be either local or provider.")
    return mode


def _pipeline_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("pipeline_mode", "single") or "single")
    if mode not in {"single", "multinode"}:
        raise ValueError("pipeline_mode must be either single or multinode.")
    return mode


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _start_watchdog(store: JobStore, stop_event: threading.Event) -> threading.Thread:
    def run() -> None:
        while not stop_event.wait(5):
            store.run_watchdog_tick()

    thread = threading.Thread(target=run, name="musicforge-watchdog", daemon=True)
    thread.start()
    return thread


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
