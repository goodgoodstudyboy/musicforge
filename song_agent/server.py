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
from song_agent.assets import (
    AssetStore,
    apply_asset_refs_to_plan,
    asset_audio_path,
    asset_midi_path,
    asset_public_dict,
    asset_prompt_summaries,
    asset_refs_snapshot,
    extract_assets_from_song_plan,
    write_asset_refs_snapshot,
)
from song_agent.batching import BatchDocument, BatchStore, now_iso
from song_agent.candidate_groups import (
    CandidateGroup,
    CandidateGroupStore,
    candidate_audio_path,
    candidate_group_stale,
    candidate_midi_path,
)
from song_agent.candidate_scoring import score_provider_edit_candidate
from song_agent.cli import generate_request
from song_agent.edits import (
    EditIntent,
    EditedSongPlanResult,
    apply_edit_intent,
    build_edit_metadata,
    build_edit_targets,
    edit_change_summary,
    edit_variant_type,
    validate_edit_intent,
)
from song_agent.edit_presets import EditPresetStore, merge_preset_intent
from song_agent.final_export import (
    FinalExportError,
    FinalExportOptions,
    build_final_export_bundle,
    build_final_export_zip,
    final_export_dir,
    final_export_zip_path,
    read_final_export_manifest,
)
from song_agent.node_graph import affected_nodes_for_retry, downstream_nodes, upstream_nodes
from song_agent.node_store import NodeStore
from song_agent.prompt_templates import PromptTemplateStore
from song_agent.projectio import ProjectPaths, append_event, read_json, slugify, write_json
from song_agent.project_compare import compare_project_versions
from song_agent.provider_edits import (
    ProviderEditPatch,
    apply_provider_edit_patch,
    create_provider_edit_preview,
    delete_provider_edit_preview,
    generate_provider_edit_candidates,
    generate_provider_edit_patch,
    mark_provider_edit_preview_applied,
    preview_candidate_plan,
    preview_patch,
    preview_stale,
    read_provider_edit_preview,
    song_plan_hash,
)
from song_agent.provider_usage import (
    build_provider_usage_report,
    collect_candidate_group_provider_usage_records,
    collect_project_provider_usage_records,
    usage_record_from_file,
)
from song_agent.prompt_ab import PromptABStore
from song_agent.projects import ProjectStore
from song_agent.project_quality import (
    QualityGateConfig,
    evaluate_quality_gate,
    load_quality_gate_config,
    save_quality_gate_config,
)
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
    job_type: str = "song"
    edit_metadata: dict[str, Any] = field(default_factory=dict)

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
            job_type=str(data.get("job_type", "song") or "song"),
            edit_metadata=_dict_or_empty(data.get("edit_metadata")),
        )


class JobStore:
    def __init__(self, runs_dir: Path = RUNS_DIR, asset_store: AssetStore | None = None) -> None:
        self.runs_dir = Path(runs_dir).resolve()
        self.asset_store = asset_store or AssetStore()
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
        asset_refs = payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else []
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
                input_payload={**request.to_dict(), "asset_refs": asset_refs} if asset_refs else request.to_dict(),
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

    def create_edit_job(
        self,
        *,
        project_id: str,
        parent_version_id: str,
        parent_job: JobState,
        parent_plan: SongPlan,
        intent: EditIntent,
        preset: dict[str, Any] | None = None,
        name: str = "",
        start_immediately: bool = True,
        provider_patch: dict[str, Any] | None = None,
        provider_usage: dict[str, Any] | None = None,
        provider_snapshot: dict[str, Any] | None = None,
        template_id: str | None = None,
        preview_id: str | None = None,
        candidate_group_id: str | None = None,
        candidate_id: str | None = None,
        candidate: dict[str, Any] | None = None,
        asset_refs: list[dict[str, Any]] | None = None,
    ) -> JobState:
        validate_edit_intent(parent_plan, intent)
        if intent.provider_mode == "provider" and provider_patch is None:
            raise NotImplementedError("Provider-backed edit is not implemented in v1.1.0.")
        with self.lock:
            title = _clean_title(name) or f"{parent_plan.title} {intent.edit_type}"
            run_dir = self._reserve_run_dir(title)
            job_id = run_dir.name
            now = _utc_now()
            metadata = build_edit_metadata(
                project_id=project_id,
                parent_version_id=parent_version_id,
                parent_job_id=parent_job.job_id,
                intent=intent,
                created_at=now,
            )
            metadata["preset"] = preset
            if provider_patch is not None:
                metadata["provider_patch"] = provider_patch
                metadata["provider"] = provider_snapshot or {}
                metadata["provider_usage"] = provider_usage or {}
                metadata["template_id"] = template_id
                metadata["preview_id"] = preview_id
                if candidate_group_id:
                    metadata["candidate_group_id"] = candidate_group_id
                if candidate_id:
                    metadata["candidate_id"] = candidate_id
                if candidate:
                    metadata["candidate"] = _candidate_source_summary(candidate)
            if asset_refs:
                metadata["asset_refs"] = list(asset_refs)
            job = JobState(
                job_id=job_id,
                title=title,
                output_dir=str(run_dir),
                status="queued",
                created_at=now,
                updated_at=now,
                step="queued",
                message="Queued for local deterministic edit.",
                input_payload={
                    **parent_job.input_payload,
                    "edit_type": intent.edit_type,
                    "parent_job_id": parent_job.job_id,
                    "parent_version_id": parent_version_id,
                    "project_id": project_id,
                    **({"asset_refs": list(asset_refs)} if asset_refs else {}),
                },
                provider_snapshot=provider_snapshot or {"mode": "local", "summary": "Local deterministic edit engine"},
                heartbeat_at=now,
                generation_mode=intent.provider_mode,
                pipeline_mode=parent_job.pipeline_mode,
                job_type="edit",
                edit_metadata=metadata,
            )
            if preset:
                job.input_payload["preset_id"] = preset.get("preset_id")
            if provider_patch is not None:
                job.input_payload["provider_patch"] = {
                    "summary": provider_patch.get("summary"),
                    "operation_count": len(provider_patch.get("operations", [])),
                }
                job.input_payload["template_id"] = template_id
                job.input_payload["preview_id"] = preview_id
                if candidate_group_id:
                    job.input_payload["candidate_group_id"] = candidate_group_id
                if candidate_id:
                    job.input_payload["candidate_id"] = candidate_id
                if candidate:
                    job.input_payload["candidate"] = _candidate_source_summary(candidate)
            self.jobs[job_id] = job
            self._write_job(job)
            write_json(ProjectPaths.create(run_dir).data / "edit-metadata.json", metadata)
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
            target=self._run_edit_job if job.job_type == "edit" else self._run_job,
            args=(job_id,),
            name=f"musicforge-{job.job_type}-job-{job_id}",
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
            asset_snapshot = self._prepare_asset_refs_for_job(job)
            plan_path, midi_path = generate_request(
                request,
                out_dir=Path(job.output_dir),
                force=False,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot if provider_config is not None else None,
                control=self._control_callback(job_id),
                pipeline_mode=job.pipeline_mode,
            )
            if asset_snapshot["asset_refs"]:
                plan = SongPlan.from_dict(read_json(plan_path))
                plan = apply_asset_refs_to_plan(plan, self.asset_store, asset_snapshot["asset_refs"])
                write_json(plan_path, plan.to_dict())
                render_midi(plan, midi_path)
                write_asset_refs_snapshot(Path(job.output_dir), asset_snapshot)
                self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "job_generation", "job_id": job.job_id})
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
            if (Path(job.output_dir) / "data" / "asset-refs.json").exists():
                artifacts["asset_refs"] = str(Path(job.output_dir) / "data" / "asset-refs.json")
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

    def _run_edit_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job is None:
            return
        run_dir = Path(job.output_dir)
        paths = ProjectPaths.create(run_dir)
        if job.cancel_requested:
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Edit job was cancelled before generation started.",
            )
            return
        self._update_job(
            job,
            status="running",
            step="edit",
            message="Applying local edit intent.",
            attempt_count=job.attempt_count + 1,
            started_at=job.started_at or _utc_now(),
            heartbeat_at=_utc_now(),
            stalled=False,
        )
        try:
            metadata = dict(job.edit_metadata)
            intent = EditIntent.from_dict(metadata)
            parent_job_id = str(metadata.get("parent_job_id") or "")
            parent_job = self.get_job(parent_job_id)
            if parent_job is None:
                raise FileNotFoundError("Parent version job is missing.")
            parent_plan_path = Path(parent_job.output_dir) / "data" / "song-plan.json"
            if not parent_plan_path.exists():
                raise FileNotFoundError("Parent song-plan.json is missing.")
            parent_plan = SongPlan.from_dict(read_json(parent_plan_path))
            append_event(paths, {"event": "edit_started", "edit_type": intent.edit_type, "target": intent.target.to_dict()})
            self._heartbeat(job)
            asset_snapshot = self._prepare_asset_refs_for_job(job)
            provider_patch_data = metadata.get("provider_patch")
            if provider_patch_data:
                patch = ProviderEditPatch.from_dict(provider_patch_data)
                result = apply_provider_edit_patch(parent_plan, patch)
            else:
                result = apply_edit_intent(parent_plan, intent)
            if asset_snapshot["asset_refs"]:
                result_plan = apply_asset_refs_to_plan(result.plan, self.asset_store, asset_snapshot["asset_refs"])
                result = EditedSongPlanResult(plan=result_plan, summary=result.summary, warnings=result.warnings)
            if job.cancel_requested:
                raise JobCancelled()
            plan_path = paths.data / "song-plan.json"
            midi_path = paths.renders / "song.mid"
            validator_report_path = paths.data / "validator-report.json"
            request_path = paths.data / "request.json"
            write_json(request_path, job.input_payload)
            edit_metadata = build_edit_metadata(
                project_id=str(metadata.get("project_id") or ""),
                parent_version_id=str(metadata.get("parent_version_id") or ""),
                parent_job_id=parent_job.job_id,
                intent=intent,
                created_at=str(metadata.get("created_at") or job.created_at),
                summary=result.summary,
                warnings=result.warnings,
            )
            edit_metadata["preset"] = metadata.get("preset")
            if provider_patch_data:
                edit_metadata["provider_mode"] = "provider"
                edit_metadata["provider_patch"] = provider_patch_data
                edit_metadata["provider"] = metadata.get("provider") or {}
                edit_metadata["template_id"] = metadata.get("template_id")
                edit_metadata["preview_id"] = metadata.get("preview_id")
                if metadata.get("candidate_group_id"):
                    edit_metadata["candidate_group_id"] = metadata.get("candidate_group_id")
                if metadata.get("candidate_id"):
                    edit_metadata["candidate_id"] = metadata.get("candidate_id")
                if metadata.get("candidate"):
                    edit_metadata["candidate"] = _candidate_source_summary(metadata.get("candidate"))
            if asset_snapshot["asset_refs"]:
                edit_metadata["asset_refs"] = list(asset_snapshot["asset_refs"])
            write_json(paths.data / "edit-metadata.json", edit_metadata)
            if asset_snapshot["asset_refs"]:
                write_asset_refs_snapshot(run_dir, asset_snapshot)
                self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "edit", "job_id": job.job_id, "project_id": metadata.get("project_id"), "version_id": metadata.get("parent_version_id")})
            if metadata.get("provider_usage"):
                usage = dict(metadata["provider_usage"])
                usage["completed_at"] = _utc_now()
                usage["status"] = "completed"
                write_json(paths.data / "provider-usage.json", usage)
            write_json(plan_path, result.plan.to_dict())
            render_midi(result.plan, midi_path)
            clear_stem_artifacts(run_dir)
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            summary["edit"] = result.summary
            write_json(paths.data / "run-summary.json", summary)
            artifacts = _job_artifacts(run_dir, plan_path, midi_path, validator_report_path)
            artifacts["edit_metadata"] = str(paths.data / "edit-metadata.json")
            if (paths.data / "asset-refs.json").exists():
                artifacts["asset_refs"] = str(paths.data / "asset-refs.json")
            if (paths.data / "provider-usage.json").exists():
                artifacts["provider_usage"] = str(paths.data / "provider-usage.json")
            self._update_job(
                job,
                status="completed",
                step="completed",
                message="Edit job completed.",
                summary=summary,
                error=None,
                last_error=None,
                finished_at=_utc_now(),
                artifacts=artifacts,
                edit_metadata=edit_metadata,
            )
            append_event(paths, {"event": "edit_completed", "summary": result.summary})
        except JobCancelled:
            latest = self.get_job(job_id)
            if latest is not None:
                self._update_job(
                    latest,
                    status="cancelled",
                    step="cancelled",
                    message="Edit job was cancelled at a stage boundary.",
                    finished_at=_utc_now(),
                )
        except Exception as exc:
            latest = self.get_job(job_id) or job
            self._update_job(
                latest,
                status="failed",
                step="failed",
                message="Edit job failed.",
                error=str(exc),
                last_error=str(exc),
                finished_at=_utc_now(),
            )

    def _prepare_asset_refs_for_job(self, job: JobState) -> dict[str, Any]:
        snapshot = asset_refs_snapshot(self.asset_store, job.input_payload.get("asset_refs"), captured_at=_utc_now())
        if snapshot["asset_refs"]:
            ProjectPaths.create(Path(job.output_dir))
            write_asset_refs_snapshot(Path(job.output_dir), snapshot)
        return snapshot

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
    def __init__(self, batch_store: BatchStore, job_store: JobStore, project_store: ProjectStore | None = None) -> None:
        self.batch_store = batch_store
        self.job_store = job_store
        self.project_store = project_store
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
                    self._archive_item_to_project(document, item, job)
                    changed = True
                    self.batch_store.append_event(
                        batch_id,
                        "batch_item_completed",
                        {
                            "item_id": item.item_id,
                            "job_id": job.job_id,
                            "project_id": item.project_id,
                            "version_id": item.version_id,
                        },
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

    def _archive_item_to_project(self, document: BatchDocument, item: Any, job: JobState) -> None:
        if self.project_store is None or not item.project:
            return
        if item.project_id and item.version_id:
            return
        project = self.project_store.find_or_create_project(item.project)
        item.project_id = project.state.project_id
        try:
            updated = self.project_store.add_version_from_job(
                project.state.project_id,
                job,
                name=item.version_name or "",
                note=item.version_note or "",
            )
        except ValueError as exc:
            if "already attached" not in str(exc):
                raise
            updated = self.project_store.get_project(project.state.project_id)
        version = next((version for version in updated.versions if version.job_id == job.job_id), None)
        if version is not None:
            item.version_id = version.version_id
        self.batch_store.append_event(
            document.state.batch_id,
            "batch_item_archived_to_project",
            {
                "item_id": item.item_id,
                "job_id": job.job_id,
                "project_id": item.project_id,
                "version_id": item.version_id,
            },
        )

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
    def edit_preset_store(self) -> EditPresetStore:
        return self.server.edit_preset_store  # type: ignore[attr-defined]

    @property
    def prompt_template_store(self) -> PromptTemplateStore:
        return self.server.prompt_template_store  # type: ignore[attr-defined]

    @property
    def asset_store(self) -> AssetStore:
        return self.server.asset_store  # type: ignore[attr-defined]

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

            if path == "/api/usage/provider":
                self._handle_provider_usage_root(method)
                return

            if path == "/api/assets":
                self._handle_assets_root(method, parsed.query)
                return

            if path == "/api/assets/extract/from-job":
                self._handle_asset_extract_from_job(method)
                return

            if path == "/api/assets/extract/from-project-version":
                self._handle_asset_extract_from_project_version(method)
                return

            if path == "/api/assets/extract/from-candidate":
                self._handle_asset_extract_from_candidate(method)
                return

            if path == "/api/edit-presets":
                self._handle_edit_presets_root(method)
                return

            if path == "/api/edit-presets/reset":
                self._handle_edit_presets_reset(method)
                return

            if path == "/api/prompt-templates":
                self._handle_prompt_templates_root(method)
                return

            if path == "/api/prompt-templates/reset":
                self._handle_prompt_templates_reset(method)
                return

            prompt_template_route = _match_prompt_template_route(path)
            if prompt_template_route is not None:
                template_id, tail = prompt_template_route
                self._handle_prompt_template_route(method, template_id, tail)
                return

            edit_preset_route = _match_edit_preset_route(path)
            if edit_preset_route is not None:
                preset_id, tail = edit_preset_route
                self._handle_edit_preset_route(method, preset_id, tail)
                return

            asset_route = _match_asset_route(path)
            if asset_route is not None:
                asset_id, tail = asset_route
                self._handle_asset_route(method, asset_id, tail)
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

    def _handle_edit_presets_root(self, method: str) -> None:
        if method == "GET":
            self._send_json(self.edit_preset_store.to_response())
            return
        if method == "POST":
            try:
                preset = self.edit_preset_store.save_preset(self._read_json_body())
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "preset": preset.to_dict(), **self.edit_preset_store.to_response()}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_edit_preset_route(self, method: str, preset_id: str, tail: str) -> None:
        if tail == "":
            if method == "GET":
                try:
                    preset = self.edit_preset_store.get_preset(preset_id)
                except (FileNotFoundError, ValueError):
                    self._send_error(HTTPStatus.NOT_FOUND, "Edit preset not found.")
                    return
                self._send_json({"preset": preset.to_dict()})
                return
            if method == "POST":
                try:
                    preset = self.edit_preset_store.save_preset(self._read_json_body(), preset_id=preset_id)
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json({"ok": True, "preset": preset.to_dict(), **self.edit_preset_store.to_response()})
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if tail == "/delete":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.edit_preset_store.delete_preset(preset_id)
            except PermissionError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            except (FileNotFoundError, ValueError):
                self._send_error(HTTPStatus.NOT_FOUND, "Edit preset not found.")
                return
            self._send_json({"ok": True, **self.edit_preset_store.to_response()})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Edit preset route not found.")

    def _handle_edit_presets_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        self.edit_preset_store.reset()
        self._send_json({"ok": True, **self.edit_preset_store.to_response()})

    def _handle_prompt_templates_root(self, method: str) -> None:
        if method == "GET":
            self._send_json(self.prompt_template_store.to_response())
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_prompt_templates_reset(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        self.prompt_template_store.reset()
        self._send_json({"ok": True, **self.prompt_template_store.to_response()})

    def _handle_prompt_template_route(self, method: str, template_id: str, tail: str) -> None:
        if tail == "":
            if method == "GET":
                try:
                    template = self.prompt_template_store.get_template(template_id)
                except (FileNotFoundError, ValueError):
                    self._send_error(HTTPStatus.NOT_FOUND, "Prompt template not found.")
                    return
                self._send_json({"template": template.to_dict()})
                return
            if method == "POST":
                try:
                    template = self.prompt_template_store.save_template(template_id, self._read_json_body())
                except FileNotFoundError:
                    self._send_error(HTTPStatus.NOT_FOUND, "Prompt template not found.")
                    return
                except ValueError as exc:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_json({"ok": True, "template": template.to_dict(), **self.prompt_template_store.to_response()})
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if tail == "/reset":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                self.prompt_template_store.reset_template(template_id)
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, **self.prompt_template_store.to_response()})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Prompt template route not found.")

    def _handle_projects_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            include_hidden = query.get("include_hidden", ["0"])[0] in {"1", "true", "yes"}
            hidden_filter = _query_value(query, "hidden")
            q = _query_value(query, "q")
            status_filter = _query_value(query, "status")
            variant_type = _query_value(query, "variant_type")
            documents = [
                self.project_store.sync_project(document.state.project_id, self.store.get_job)
                for document in self.project_store.list_projects(include_hidden=include_hidden or hidden_filter == "true")
            ]
            projects = [
                document.state.to_dict()
                for document in documents
                if _project_matches_filters(
                    document,
                    q=q,
                    status=status_filter,
                    variant_type=variant_type,
                    hidden=hidden_filter,
                )
            ]
            self._send_json(
                {
                    "projects": projects,
                    "filters": {
                        "q": q,
                        "status": status_filter,
                        "variant_type": variant_type,
                        "hidden": hidden_filter,
                        "include_hidden": include_hidden,
                    },
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

    def _handle_assets_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            filters = {key: _query_value(query, key) for key in ("q", "type", "tag", "style", "mood", "min_quality", "favorite")}
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            limit_value = _query_value(query, "limit")
            limit = int(limit_value) if limit_value else 100
            assets = self.asset_store.list_assets(include_hidden=include_hidden, filters=filters)[: max(1, min(limit, 500))]
            self._send_json({"assets": [asset_public_dict(asset) for asset in assets], "count": len(assets), "filters": {**filters, "include_hidden": include_hidden}})
            return
        if method == "POST":
            try:
                asset = self.asset_store.create_asset(self._read_json_body(), now=_utc_now())
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "asset": asset_public_dict(asset)}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_asset_route(self, method: str, asset_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method == "GET":
                    self._send_json({"asset": asset_public_dict(self.asset_store.read_asset(asset_id))})
                    return
                if method == "POST":
                    asset = self.asset_store.update_asset(asset_id, self._read_json_body())
                    self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.hide_asset(asset_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail in {"/favorite", "/unfavorite"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.favorite_asset(asset_id, favorite=tail == "/favorite")
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.delete_asset(asset_id)
                self._send_json({"ok": True, "deleted": True, "asset_id": asset_id})
                return
            if tail == "/render-midi":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.asset_store.render_asset_midi(asset_id)
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail == "/render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                asset = self.asset_store.render_asset_audio(asset_id, config)
                self._send_json({"ok": True, "asset": asset_public_dict(asset)})
                return
            if tail == "/midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.read_asset(asset_id)
                self._send_file(asset_midi_path(self.asset_store.asset_dir(asset_id)), "audio/midi", filename=f"{asset_id}.mid")
                return
            if tail == "/audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.asset_store.read_asset(asset_id)
                self._send_file(asset_audio_path(self.asset_store.asset_dir(asset_id)), "audio/wav", filename=f"{asset_id}.wav")
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Asset not found.")
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            status = HTTPStatus.CONFLICT if "MIDI preview" in str(exc) or "do not have MIDI" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Asset route not found.")

    def _handle_asset_extract_from_job(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        job_id = str(payload.get("job_id") or "")
        job = self.store.get_job(job_id)
        if job is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Job not found.")
            return
        plan_path = Path(job.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is missing.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            assets = self._create_assets_from_plan(plan, {"source_type": "job", "job_id": job.job_id, "style": job.input_payload.get("style")}, payload)
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [asset_public_dict(asset) for asset in assets]}, status=HTTPStatus.CREATED)

    def _handle_asset_extract_from_project_version(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        project_id = str(payload.get("project_id") or "")
        version_id = str(payload.get("version_id") or "")
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        plan_path = Path(version.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is missing.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            assets = self._create_assets_from_plan(
                plan,
                {"source_type": "project_version", "project_id": project_id, "version_id": version.version_id, "job_id": version.job_id, "style": version.request.get("style")},
                payload,
            )
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [asset_public_dict(asset) for asset in assets]}, status=HTTPStatus.CREATED)

    def _handle_asset_extract_from_candidate(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        project_id = str(payload.get("project_id") or "")
        group_id = str(payload.get("candidate_group_id") or "")
        candidate_id = str(payload.get("candidate_id") or "")
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            plan = SongPlan.from_dict(group_store.read_candidate_plan(group.group_id, candidate_id))
            assets = self._create_assets_from_plan(
                plan,
                {
                    "source_type": "candidate",
                    "project_id": project_id,
                    "version_id": group.parent_version_id,
                    "job_id": group.parent_job_id,
                    "candidate_group_id": group.group_id,
                    "candidate_id": candidate_id,
                },
                payload,
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "assets": [asset_public_dict(asset) for asset in assets]}, status=HTTPStatus.CREATED)

    def _create_assets_from_plan(self, plan: SongPlan, source: dict[str, Any], payload: dict[str, Any]) -> list[Any]:
        assets = []
        for asset_payload in extract_assets_from_song_plan(plan, source, payload):
            assets.append(self.asset_store.create_asset(asset_payload, now=_utc_now()))
        return assets

    def _handle_provider_usage_root(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        records: list[dict[str, Any]] = []
        for job in self.store.list_jobs(include_hidden=True):
            record = usage_record_from_file(
                Path(job.output_dir) / "data" / "provider-usage.json",
                source_type="job",
                source_id=job.job_id,
                job_id=job.job_id,
            )
            if record is not None:
                records.append(record)
        for document in self.project_store.list_projects(include_hidden=True):
            project_dir = self.project_store.project_dir(document.state.project_id)
            groups_dir = project_dir / "candidate-groups"
            if not groups_dir.exists():
                continue
            for usage_path in sorted(groups_dir.glob("*/provider-usage.json")):
                record = usage_record_from_file(
                    usage_path,
                    source_type="candidate_group",
                    source_id=usage_path.parent.name,
                    project_id=document.state.project_id,
                    group_id=usage_path.parent.name,
                )
                if record is not None:
                    records.append(record)
        self._send_json(build_provider_usage_report(scope="global", records=records))

    def _handle_project_route(self, method: str, project_id: str, tail: str, query_string: str) -> None:
        variation_match = _match_project_variation_tail(tail)
        if variation_match is not None:
            parent_version_id = variation_match
            self._handle_project_variation(method, project_id, parent_version_id)
            return

        edit_match = _match_project_edit_tail(tail)
        if edit_match is not None:
            version_id, edit_tail = edit_match
            if edit_tail == "edit":
                self._handle_project_edit(method, project_id, version_id)
            else:
                self._handle_project_edit_targets(method, project_id, version_id)
            return

        preview_match = _match_project_edit_preview_tail(tail)
        if preview_match is not None:
            parent_version_id, preview_id, action = preview_match
            if action == "create":
                self._handle_project_edit_preview(method, project_id, parent_version_id)
            elif action == "apply":
                self._handle_project_edit_preview_apply(method, project_id, parent_version_id, preview_id)
            elif action == "delete":
                self._handle_project_edit_preview_delete(method, project_id, parent_version_id, preview_id)
            return

        candidate_create_match = _match_project_edit_candidates_tail(tail)
        if candidate_create_match is not None:
            version_id, action = candidate_create_match
            if action == "create":
                self._handle_project_edit_candidates(method, project_id, version_id)
            else:
                self._handle_project_prompt_ab_create(method, project_id, version_id)
            return

        candidate_group_match = _match_project_candidate_group_tail(tail)
        if candidate_group_match is not None:
            group_id, action = candidate_group_match
            if action == "detail":
                self._handle_project_candidate_group_detail(method, project_id, group_id)
            elif action == "apply":
                self._handle_project_candidate_group_apply(method, project_id, group_id)
            elif action == "delete":
                self._handle_project_candidate_group_delete(method, project_id, group_id)
            elif action in {"render-midi", "render-audio"}:
                self._handle_project_candidate_group_render(method, project_id, group_id, action)
            elif action == "usage":
                self._handle_project_candidate_group_usage(method, project_id, group_id)
            return

        candidate_artifact_match = _match_project_candidate_artifact_tail(tail)
        if candidate_artifact_match is not None:
            group_id, candidate_id, action = candidate_artifact_match
            self._handle_project_candidate_artifact(method, project_id, group_id, candidate_id, action)
            return

        prompt_ab_match = _match_project_prompt_ab_tail(tail)
        if prompt_ab_match is not None:
            ab_id, action = prompt_ab_match
            if action == "list":
                self._handle_project_prompt_ab_list(method, project_id)
            elif action == "detail":
                self._handle_project_prompt_ab_detail(method, project_id, ab_id)
            else:
                self._handle_project_prompt_ab_delete(method, project_id, ab_id)
            return

        if tail == "/candidate-groups":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._handle_project_candidate_groups_list(project_id)
            return

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
                if isinstance(payload.get("asset_refs"), list):
                    request_payload["asset_refs"] = payload["asset_refs"]
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

        evaluate_match = _match_project_evaluate_tail(tail)
        if evaluate_match is not None:
            self._handle_project_evaluate(method, project_id, evaluate_match)
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
                    document, gate_result = self._set_final_version_with_gate(
                        project_id,
                        version_id,
                        force=bool(payload.get("force", False)),
                    )
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                return
            except PermissionError as exc:
                self._send_json(exc.args[0], status=HTTPStatus.CONFLICT)
                return
            except ValueError as exc:
                self._send_error(HTTPStatus.CONFLICT, str(exc))
                return
            response = {"ok": True, **document.to_dict()}
            if tail == "/final":
                response["quality_gate"] = gate_result.to_dict()
            self._send_json(response)
            return

        if tail == "/quality-gate":
            self._handle_project_quality_gate(method, project_id)
            return

        if tail == "/quality-gate/evaluate-all":
            self._handle_project_evaluate_all(method, project_id)
            return

        if tail == "/final-export":
            self._handle_project_final_export(method, project_id)
            return

        if tail == "/final-export/zip":
            self._handle_project_final_export_zip(method, project_id)
            return

        if tail == "/final-export.zip":
            self._handle_project_final_export_zip_download(method, project_id)
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

        if tail == "/compare":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            left = str(query.get("left", [""])[0])
            right = str(query.get("right", [""])[0])
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
                self._send_json(compare_project_versions(document, left, right))
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if tail == "/provider-usage":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            self._handle_project_provider_usage(project_id)
            return

        if tail == "/usage/provider":
            self._handle_project_provider_usage_report(method, project_id)
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

    def _handle_project_quality_gate(self, method: str, project_id: str) -> None:
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        if method == "GET":
            self._send_json({"config": load_quality_gate_config(project_dir).to_dict()})
            return
        if method == "POST":
            config = QualityGateConfig.from_dict(self._read_json_body())
            save_quality_gate_config(project_dir, config)
            self.project_store.append_event(project_id, "quality_gate_config_saved", {"config": config.to_dict()})
            self._send_json({"ok": True, "config": config.to_dict()})
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_project_evaluate(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        result = self._evaluate_project_version(project_id, version)
        document = self.project_store.update_version_quality_gate(project_id, version.version_id, result)
        version = next(item for item in document.versions if item.version_id == version_id)
        self._send_json({"ok": True, "version": version.to_dict(), "quality_gate": result.to_dict(), **document.to_dict()})

    def _handle_project_evaluate_all(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        results = []
        for version in document.versions:
            result = self._evaluate_project_version(project_id, version)
            self.project_store.update_version_quality_gate(project_id, version.version_id, result)
            results.append({"version_id": version.version_id, "quality_gate": result.to_dict()})
        document = self.project_store.get_project(project_id)
        self._send_json({"ok": True, "results": results, **document.to_dict()})

    def _handle_project_final_export(self, method: str, project_id: str) -> None:
        if method == "GET":
            try:
                project_dir = self.project_store.project_dir(project_id)
                self.project_store.get_project(project_id)
                manifest = read_final_export_manifest(project_dir)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Final export not found.")
                return
            self._send_json({"final_export": manifest})
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return

        payload = self._optional_json_body()
        options = FinalExportOptions.from_dict(payload)
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return

        version_id = options.version_id or document.state.final_version_id
        if not version_id:
            self._send_error(HTTPStatus.CONFLICT, "Project has no final version.")
            return
        version = next((item for item in document.versions if item.version_id == version_id), None)
        if version is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        if version.status != "completed":
            self._send_error(HTTPStatus.CONFLICT, "Only completed versions can be exported.")
            return
        if self.store.get_job(version.job_id) is None:
            self._send_error(HTTPStatus.CONFLICT, "Version job is missing.")
            return

        gate_result = self._evaluate_project_version(project_id, version)
        document = self.project_store.update_version_quality_gate(project_id, version.version_id, gate_result)
        version = next(item for item in document.versions if item.version_id == version_id)
        if gate_result.status not in {"passed", "warning"} and not options.force:
            self.project_store.append_event(
                project_id,
                "final_export_gate_failed",
                {"version_id": version.version_id, "status": gate_result.status, "score": gate_result.score},
            )
            self._send_json(
                {
                    "error": "Quality gate failed.",
                    "quality_gate": gate_result.to_dict(),
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        project_dir = self.project_store.project_dir(project_id)
        project_export = self.project_store.export_project(project_id)
        document = self.project_store.get_project(project_id)
        version = next(item for item in document.versions if item.version_id == version_id)
        try:
            manifest = build_final_export_bundle(
                project=document.state,
                version=version,
                project_dir=project_dir,
                run_dir=Path(version.output_dir),
                gate=gate_result,
                options=options,
                now=_utc_now(),
                project_export=project_export,
            )
        except FinalExportError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        document = self.project_store.update_version_final_export(
            project_id,
            version.version_id,
            final_export_dir(project_dir),
        )
        version = next(item for item in document.versions if item.version_id == version_id)
        self._send_json(
            {
                "ok": True,
                "version": version.to_dict(),
                "quality_gate": gate_result.to_dict(),
                "final_export": manifest,
                **document.to_dict(),
            }
        )

    def _handle_project_final_export_zip(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
            zip_info = build_final_export_zip(project_dir, now=_utc_now())
            self.project_store.append_event(project_id, "final_export_zip_created", zip_info)
        except FileNotFoundError:
            self._send_error(HTTPStatus.CONFLICT, "Final export has not been generated.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "project_id": project_id, "zip": zip_info})

    def _handle_project_final_export_zip_download(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            self.project_store.get_project(project_id)
            zip_path = final_export_zip_path(project_dir)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_file(zip_path, "application/zip", filename=f"musicforge-{project_id}-final-export.zip")

    def _set_final_version_with_gate(self, project_id: str, version_id: str, *, force: bool) -> tuple[Any, Any]:
        document = self.project_store.get_project(project_id)
        version = next((version for version in document.versions if version.version_id == version_id), None)
        if version is None:
            raise FileNotFoundError(version_id)
        if version.status != "completed":
            raise ValueError("Only completed versions can be marked final.")
        result = self._evaluate_project_version(project_id, version)
        self.project_store.update_version_quality_gate(project_id, version.version_id, result)
        if result.status not in {"passed", "warning"} and not force:
            self.project_store.append_event(
                project_id,
                "final_version_gate_failed",
                {"version_id": version.version_id, "status": result.status, "score": result.score},
            )
            raise PermissionError(
                {
                    "error": "Quality gate failed.",
                    "quality_gate": result.to_dict(),
                }
            )
        document = self.project_store.set_final_version(project_id, version.version_id)
        if force and result.status not in {"passed", "warning"}:
            self.project_store.append_event(
                project_id,
                "final_version_force_set",
                {"version_id": version.version_id, "status": result.status, "score": result.score},
            )
        return document, result

    def _evaluate_project_version(self, project_id: str, version: Any) -> Any:
        config = load_quality_gate_config(self.project_store.project_dir(project_id))
        return evaluate_quality_gate(Path(version.output_dir), config, now=_utc_now())

    def _handle_project_variation(self, method: str, project_id: str, parent_version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            parent = next(version for version in document.versions if version.version_id == parent_version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            self._send_error(HTTPStatus.CONFLICT, "Parent version job is missing.")
            return
        request_patch = payload.get("request_patch") or {}
        if not isinstance(request_patch, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "request_patch must be an object.")
            return
        try:
            request_payload = _variation_request_payload(
                parent.request,
                request_patch,
                generation_mode=payload.get("generation_mode"),
                pipeline_mode=payload.get("pipeline_mode"),
            )
            if isinstance(payload.get("asset_refs"), list):
                request_payload["asset_refs"] = payload["asset_refs"]
            job = self.store.create_job(request_payload)
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("name") or ""),
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type=str(payload.get("variant_type") or "manual"),
                change_summary=str(payload.get("change_summary") or ""),
            )
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        version = next(version for version in document.versions if version.job_id == job.job_id)
        self.project_store.append_event(
            project_id,
            "variation_created",
            {
                "parent_version_id": parent.version_id,
                "version_id": version.version_id,
                "job_id": job.job_id,
                "variant_type": version.variant_type,
            },
        )
        self._send_json(
            {"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict()},
            status=HTTPStatus.ACCEPTED,
        )

    def _handle_project_edit(self, method: str, project_id: str, version_id: str) -> None:
        if method == "GET":
            try:
                document = self.project_store.sync_project(project_id, self.store.get_job)
                version = next(version for version in document.versions if version.version_id == version_id)
            except StopIteration:
                self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
                return
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
                return
            metadata = _read_edit_metadata_for_run(Path(version.output_dir))
            if metadata is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Edit metadata not found.")
                return
            self._send_json({"version_id": version.version_id, "edit": metadata})
            return
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            parent = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            self._send_error(HTTPStatus.CONFLICT, "Parent version job is missing.")
            return
        if parent.status != "completed" or parent_job.status != "completed":
            self._send_error(HTTPStatus.CONFLICT, "Parent version must be completed before editing.")
            return
        parent_plan_path = Path(parent.output_dir) / "data" / "song-plan.json"
        if not parent_plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "Parent song-plan.json is missing.")
            return
        preset_ref = None
        try:
            parent_plan = SongPlan.from_dict(read_json(parent_plan_path))
            preset_id = str(payload.get("preset_id") or "").strip()
            intent_payload = payload
            if preset_id:
                preset = self.edit_preset_store.get_preset(preset_id)
                intent_payload = merge_preset_intent(preset, payload, parent_plan)
                preset_ref = preset.public_ref()
            intent = EditIntent.from_dict(intent_payload)
            validate_edit_intent(parent_plan, intent)
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                preset=preset_ref,
                name=str(payload.get("name") or ""),
                start_immediately=bool(payload.get("start_immediately", True)),
                asset_refs=payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else None,
            )
            variant_type = edit_variant_type(intent.edit_type)
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("name") or "") or f"Edit {len(document.versions) + 1}",
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type=variant_type,
                change_summary=str(payload.get("change_summary") or edit_change_summary(intent)),
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Edit preset not found.")
            return
        except NotImplementedError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        version = next(version for version in document.versions if version.job_id == job.job_id)
        self.project_store.append_event(
            project_id,
            "version_edit_created",
            {
                "parent_version_id": parent.version_id,
                "version_id": version.version_id,
                "job_id": job.job_id,
                "edit_type": intent.edit_type,
            },
        )
        self._send_json(
            {
                "ok": True,
                **document.to_dict(),
                "version": version.to_dict(),
                "job": job.to_dict(),
                "edit": job.edit_metadata,
            },
            status=HTTPStatus.ACCEPTED,
        )

    def _handle_project_edit_targets(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next(version for version in document.versions if version.version_id == version_id)
        except StopIteration:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        plan_path = Path(version.output_dir) / "data" / "song-plan.json"
        if not plan_path.exists():
            self._send_error(HTTPStatus.CONFLICT, "song-plan.json is not available for this version.")
            return
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json(build_edit_targets(plan))

    def _handle_project_edit_preview(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            instruction = str(payload.get("instruction") or "").strip()
            if not instruction:
                self._send_error(HTTPStatus.BAD_REQUEST, "instruction is required.")
                return
            template_id = str(payload.get("template_id") or "provider-edit-intent").strip()
            template = self.prompt_template_store.get_template(template_id)
            if not template.enabled:
                self._send_error(HTTPStatus.CONFLICT, "Prompt template is disabled.")
                return
            config, _sources = load_provider_config()
            asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
            asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
            patch, provider_snapshot = generate_provider_edit_patch(
                parent_plan=parent_plan,
                instruction=instruction,
                template=template,
                config=config,
                asset_references=asset_prompt_refs,
            )
            provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
            preview = create_provider_edit_preview(
                project_dir=self.project_store.project_dir(project_id),
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job_id=parent_job.job_id,
                parent_plan=parent_plan,
                instruction=instruction,
                template=template,
                patch=patch,
                now=_utc_now(),
                provider_usage=provider_usage,
                provider_request_id=None if provider_snapshot.get("request_id") is None else str(provider_snapshot.get("request_id")),
                asset_refs=asset_snapshot["asset_refs"],
            )
            if asset_snapshot["asset_refs"]:
                self.asset_store.mark_used(
                    asset_snapshot["asset_refs"],
                    {
                        "usage_type": "provider_edit_preview",
                        "project_id": project_id,
                        "version_id": parent.version_id,
                        "preview_id": preview.preview_id,
                    },
                )
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_preview",
                template_id=template.template_id,
                started_at=preview.created_at,
                status="completed",
                provider_usage=provider_usage,
                request_id=provider_snapshot.get("request_id"),
            )
            write_json(
                self.project_store.project_dir(project_id) / "edit-previews" / preview.preview_id / "provider-usage.json",
                usage,
            )
            self.project_store.append_event(
                project_id,
                "provider_edit_preview_created",
                {"parent_version_id": parent.version_id, "preview_id": preview.preview_id, "template_id": template.template_id},
            )
        except FileNotFoundError as exc:
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "preview": preview.to_dict(), "patch": patch.to_dict()}, status=HTTPStatus.CREATED)

    def _handle_project_edit_preview_apply(self, method: str, project_id: str, version_id: str, preview_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            preview = read_provider_edit_preview(self.project_store.project_dir(project_id), preview_id)
            if preview.parent_version_id != parent.version_id:
                self._send_error(HTTPStatus.CONFLICT, "Preview does not belong to this parent version.")
                return
            if preview.status == "applied":
                self._send_error(HTTPStatus.CONFLICT, "Provider edit preview has already been applied.")
                return
            if preview_stale(preview, parent_plan):
                self._send_error(HTTPStatus.CONFLICT, "Provider edit preview is stale because the parent song-plan.json has changed.")
                return
            patch = preview_patch(self.project_store.project_dir(project_id), preview_id)
            candidate = preview_candidate_plan(self.project_store.project_dir(project_id), preview_id)
            candidate.validate()
            intent = EditIntent.from_dict(
                {
                    "edit_type": "section_energy",
                    "target": {"section_name": parent_plan.sections[0].name},
                    "instruction": preview.instruction,
                    "strength": 6,
                    "provider_mode": "provider",
                    "payload": {"preview_id": preview_id},
                }
            )
            config, _sources = load_provider_config()
            provider_snapshot = config.to_snapshot("provider", _utc_now())
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_apply",
                template_id=preview.template_id,
                started_at=_utc_now(),
                status="queued",
                provider_usage=preview.provider_usage,
                request_id=preview.provider_request_id,
            )
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                name=str(payload.get("name") or "") or f"Provider Edit {len(document.versions) + 1}",
                start_immediately=bool(payload.get("start_immediately", True)),
                provider_patch=patch.to_dict(),
                provider_usage=usage,
                provider_snapshot=provider_snapshot,
                template_id=preview.template_id,
                preview_id=preview_id,
                asset_refs=preview.source.get("asset_refs") if isinstance(preview.source.get("asset_refs"), list) else None,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("name") or "") or f"Provider Edit {len(document.versions) + 1}",
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="provider_edit",
                change_summary=str(payload.get("change_summary") or patch.summary),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            mark_provider_edit_preview_applied(self.project_store.project_dir(project_id), preview_id, job.job_id, version.version_id)
            self.project_store.append_event(
                project_id,
                "provider_edit_applied",
                {"parent_version_id": parent.version_id, "preview_id": preview_id, "version_id": version.version_id, "job_id": job.job_id},
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Provider edit preview not found.")
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "preview": preview.to_dict()}, status=HTTPStatus.ACCEPTED)

    def _handle_project_edit_preview_delete(self, method: str, project_id: str, version_id: str, preview_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            delete_provider_edit_preview(self.project_store.project_dir(project_id), preview_id)
            self.project_store.append_event(project_id, "provider_edit_preview_deleted", {"preview_id": preview_id, "parent_version_id": version_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Provider edit preview not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "preview_id": preview_id})

    def _handle_project_edit_candidates(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            group = self._create_project_candidate_group(project_id, version_id, payload)
        except FileNotFoundError as exc:
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "group": group.to_dict()}, status=HTTPStatus.CREATED)

    def _create_project_candidate_group(self, project_id: str, version_id: str, payload: dict[str, Any], *, mark_asset_usage: bool = True) -> Any:
        _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
        instruction = str(payload.get("instruction") or "").strip()
        if not instruction:
            raise ValueError("instruction is required.")
        candidate_count = int(payload.get("candidate_count") or 3)
        template_id = str(payload.get("template_id") or "provider-edit-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise ValueError("Prompt template is disabled.")
        config, _sources = load_provider_config()
        asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
        asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        patches, provider_snapshot = generate_provider_edit_candidates(
            parent_plan=parent_plan,
            instruction=instruction,
            template=template,
            config=config,
            candidate_count=candidate_count,
            asset_references=asset_prompt_refs,
        )
        provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
        project_dir = self.project_store.project_dir(project_id)
        group_store = CandidateGroupStore(project_dir)
        group = group_store.create_group(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_job_id=parent_job.job_id,
            instruction=instruction,
            template_id=template.template_id,
            candidate_count=len(patches),
            source={
                "parent_version_id": parent.version_id,
                "parent_job_id": parent_job.job_id,
                "song_plan_sha256": song_plan_hash(parent_plan),
                "asset_refs": list(asset_snapshot["asset_refs"]),
            },
            provider_usage=provider_usage,
            provider_request_id=None if provider_snapshot.get("request_id") is None else str(provider_snapshot.get("request_id")),
            now=_utc_now(),
        )
        usage_record = _provider_usage_record(
            config_snapshot=provider_snapshot,
            operation="provider_edit_candidates",
            template_id=template.template_id,
            started_at=group.created_at,
            status="completed",
            provider_usage=provider_usage,
            request_id=provider_snapshot.get("request_id"),
        )
        write_json(project_dir / "candidate-groups" / group.group_id / "provider-usage.json", usage_record)
        for patch in patches:
            try:
                result = apply_provider_edit_patch(parent_plan, patch)
                validator = {
                    "status": "passed",
                    "checks": ["provider_edit_patch_schema", "edit_intent_validation", "song_plan_validation"],
                    "checked_at": _utc_now(),
                }
                scores = score_provider_edit_candidate(
                    parent_plan=parent_plan,
                    candidate_plan=result.plan,
                    patch=patch,
                    validator_status="passed",
                )
                group_store.add_candidate(
                    group,
                    summary=patch.summary,
                    status="ready",
                    patch=patch.to_dict(),
                    scores=scores.to_dict(),
                    validator=validator,
                    quality=result.plan.quality.to_dict() if result.plan.quality else None,
                    provider_usage={},
                    candidate_plan=result.plan.to_dict(),
                    now=_utc_now(),
                )
                current_group = group_store.read_group(group.group_id)
                latest_candidate = current_group.candidates[-1]
                group_store.render_candidate_midi(group.group_id, latest_candidate.candidate_id)
            except Exception as exc:
                group_store.add_candidate(
                    group,
                    summary=patch.summary,
                    status="failed",
                    patch=patch.to_dict(),
                    scores={},
                    validator={"status": "failed", "error": str(exc), "checked_at": _utc_now()},
                    quality=None,
                    error=str(exc),
                    now=_utc_now(),
                )
            group = group_store.read_group(group.group_id)
        if asset_snapshot["asset_refs"] and mark_asset_usage:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "candidate_generation", "project_id": project_id, "version_id": parent.version_id, "candidate_group_id": group.group_id})
        self.project_store.append_event(
            project_id,
            "provider_edit_candidate_group_created",
            {
                "parent_version_id": parent.version_id,
                "group_id": group.group_id,
                "candidate_count": len(group.candidates),
                "template_id": template.template_id,
                "status": group.status,
            },
        )
        return group

    def _handle_project_candidate_groups_list(self, project_id: str) -> None:
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            self._send_json({"project_id": project_id, "groups": [group.to_dict() for group in group_store.list_groups()]})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_detail(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            self._send_json({"project_id": project_id, "group": group.to_dict()})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_candidate_group_usage(self, method: str, project_id: str, group_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            CandidateGroupStore(project_dir).read_group(group_id)
            records = collect_candidate_group_provider_usage_records(project_id, group_id, project_dir)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(build_provider_usage_report(scope="candidate_group", project_id=project_id, records=records))

    def _handle_project_candidate_group_apply(self, method: str, project_id: str, group_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = group_store.read_group(group_id)
            parent = next((version for version in document.versions if version.version_id == group.parent_version_id), None)
            if parent is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Parent version not found.")
                return
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, parent.version_id)
            if candidate_group_stale(group, song_plan_hash(parent_plan)):
                self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group is stale because the parent song-plan.json has changed.")
                return
            if group.status == "applied":
                self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group has already been applied.")
                return
            candidate_id = str(payload.get("candidate_id") or _top_ranked_candidate_id(group) or "")
            candidate = next((item for item in group.candidates if item.candidate_id == candidate_id), None)
            if candidate is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
                return
            if candidate.status != "ready":
                self._send_error(HTTPStatus.CONFLICT, "Only ready candidates can be applied.")
                return
            patch = ProviderEditPatch.from_dict(group_store.read_candidate_patch(group.group_id, candidate.candidate_id))
            candidate_plan = SongPlan.from_dict(group_store.read_candidate_plan(group.group_id, candidate.candidate_id))
            candidate_plan.validate()
            intent = EditIntent.from_dict(
                {
                    "edit_type": "section_energy",
                    "target": {"section_name": parent_plan.sections[0].name},
                    "instruction": group.instruction,
                    "strength": 6,
                    "provider_mode": "provider",
                    "payload": {"candidate_group_id": group.group_id, "candidate_id": candidate.candidate_id},
                }
            )
            config, _sources = load_provider_config()
            provider_snapshot = config.to_snapshot("provider", _utc_now())
            usage = _provider_usage_record(
                config_snapshot=provider_snapshot,
                operation="provider_edit_candidate_apply",
                template_id=group.template_id,
                started_at=_utc_now(),
                status="queued",
                provider_usage=group.provider_usage,
                request_id=group.provider_request_id,
            )
            name = str(payload.get("name") or "") or f"Provider Candidate {len(document.versions) + 1}"
            job = self.store.create_edit_job(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job=parent_job,
                parent_plan=parent_plan,
                intent=intent,
                name=name,
                start_immediately=bool(payload.get("start_immediately", True)),
                provider_patch=patch.to_dict(),
                provider_usage=usage,
                provider_snapshot=provider_snapshot,
                template_id=group.template_id,
                preview_id=group.group_id,
                candidate_group_id=group.group_id,
                candidate_id=candidate.candidate_id,
                candidate=_candidate_source_summary(
                    {
                        "candidate_group_id": group.group_id,
                        "candidate_id": candidate.candidate_id,
                        "rank": candidate.rank,
                        "score": candidate.scores.get("combined"),
                        "quality_overall": candidate.scores.get("quality_overall"),
                        "summary": candidate.summary,
                        "status": candidate.status,
                        "created_at": candidate.created_at,
                    }
                ),
                asset_refs=group.source.get("asset_refs") if isinstance(group.source.get("asset_refs"), list) else None,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=name,
                note=str(payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="provider_edit",
                change_summary=str(payload.get("change_summary") or patch.summary),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            group = group_store.mark_applied(group.group_id, candidate.candidate_id, version_id=version.version_id, job_id=job.job_id)
            self.project_store.append_event(
                project_id,
                "provider_edit_candidate_applied",
                {
                    "parent_version_id": parent.version_id,
                    "group_id": group.group_id,
                    "candidate_id": candidate.candidate_id,
                    "version_id": version.version_id,
                    "job_id": job.job_id,
                },
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, **document.to_dict(), "group": group.to_dict(), "version": version.to_dict(), "job": job.to_dict()}, status=HTTPStatus.ACCEPTED)

    def _handle_project_candidate_group_delete(self, method: str, project_id: str, group_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group_store.delete_group(group_id)
            self.project_store.append_event(project_id, "provider_edit_candidate_group_deleted", {"group_id": group_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "group_id": group_id})

    def _handle_project_candidate_group_render(self, method: str, project_id: str, group_id: str, action: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = self._project_candidate_group_or_conflict(project_id, group_store, group_id)
            if group is None:
                return
            if action == "render-midi":
                group = group_store.render_group_midi(group.group_id)
            else:
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                group = group_store.render_group_audio(group.group_id, config)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "group": group.to_dict()})

    def _handle_project_candidate_artifact(self, method: str, project_id: str, group_id: str, candidate_id: str, action: str) -> None:
        try:
            group_store = CandidateGroupStore(self.project_store.project_dir(project_id))
            group = self._project_candidate_group_or_conflict(project_id, group_store, group_id)
            if group is None:
                return
            candidate_dir = group_store.candidate_dir(group.group_id, candidate_id)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Candidate group not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if action == "midi":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            path = candidate_midi_path(candidate_dir)
            if not path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate MIDI preview not found.")
                return
            self._send_file(path, "audio/midi")
            return

        if action == "audio":
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            path = candidate_audio_path(candidate_dir)
            if not path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate WAV preview not found.")
                return
            self._send_file(path, "audio/wav")
            return

        if action == "render-midi":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                candidate = group_store.render_candidate_midi(group.group_id, candidate_id)
                group = group_store.read_group(group.group_id)
                self._send_json({"ok": True, "candidate": candidate.to_dict(), "group": group.to_dict()})
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if action == "render-audio":
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            try:
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                candidate = group_store.render_candidate_audio(group.group_id, candidate_id, config)
                group = group_store.read_group(group.group_id)
                self._send_json({"ok": True, "candidate": candidate.to_dict(), "group": group.to_dict()})
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Candidate not found.")
            except RendererError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        self._send_error(HTTPStatus.NOT_FOUND, "Candidate artifact route not found.")

    def _project_candidate_group_or_conflict(self, project_id: str, group_store: CandidateGroupStore, group_id: str) -> Any | None:
        document = self.project_store.sync_project(project_id, self.store.get_job)
        group = group_store.read_group(group_id)
        parent = next((version for version in document.versions if version.version_id == group.parent_version_id), None)
        if parent is None:
            self._send_error(HTTPStatus.NOT_FOUND, "Parent version not found.")
            return None
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, parent.version_id)
        if candidate_group_stale(group, song_plan_hash(parent_plan)):
            self._send_error(HTTPStatus.CONFLICT, "Provider edit candidate group is stale because the parent song-plan.json has changed.")
            return None
        return group

    def _handle_project_prompt_ab_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        created_group_ids: list[str] = []
        try:
            instruction = str(payload.get("instruction") or "").strip()
            if not instruction:
                raise ValueError("instruction is required.")
            candidate_count = int(payload.get("candidate_count") or 2)
            template_ids = _prompt_ab_template_ids(payload.get("template_ids"))
            groups = []
            for template_id in template_ids:
                group = self._create_project_candidate_group(
                    project_id,
                    version_id,
                    {
                        **payload,
                        "instruction": instruction,
                        "candidate_count": candidate_count,
                        "template_id": template_id,
                    },
                    mark_asset_usage=False,
                )
                groups.append(group)
                created_group_ids.append(group.group_id)
            project_dir = self.project_store.project_dir(project_id)
            experiment = PromptABStore(project_dir).create_experiment(
                project_id=project_id,
                parent_version_id=version_id,
                instruction=instruction,
                candidate_count=candidate_count,
                template_ids=template_ids,
                group_ids=[group.group_id for group in groups],
                now=_utc_now(),
            )
            self.project_store.append_event(
                project_id,
                "provider_prompt_ab_created",
                {"ab_id": experiment.ab_id, "group_ids": list(experiment.group_ids), "template_ids": list(template_ids)},
            )
            for group in groups:
                refs = group.source.get("asset_refs") if isinstance(group.source, dict) else None
                if isinstance(refs, list) and refs:
                    self.asset_store.mark_used(
                        refs,
                        {
                            "usage_type": "prompt_ab_candidate_generation",
                            "project_id": project_id,
                            "version_id": version_id,
                            "candidate_group_id": group.group_id,
                            "prompt_ab_id": experiment.ab_id,
                        },
                    )
        except FileNotFoundError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            message = "Version not found." if str(exc) == version_id else "Provider edit resource not found."
            self._send_error(HTTPStatus.NOT_FOUND, message)
            return
        except ProviderError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(
            {"ok": True, "experiment": experiment.to_dict(), "groups": [group.to_dict() for group in groups]},
            status=HTTPStatus.CREATED,
        )

    def _rollback_prompt_ab_groups(self, project_id: str, group_ids: list[str]) -> None:
        if not group_ids:
            return
        try:
            project_dir = self.project_store.project_dir(project_id)
            group_store = CandidateGroupStore(project_dir)
            deleted = []
            for group_id in group_ids:
                try:
                    group_store.delete_group(group_id)
                    deleted.append(group_id)
                except (FileNotFoundError, ValueError):
                    continue
            if deleted:
                self.project_store.append_event(project_id, "provider_prompt_ab_rolled_back", {"group_ids": deleted})
        except (FileNotFoundError, ValueError):
            return

    def _handle_project_prompt_ab_list(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            experiments = PromptABStore(self.project_store.project_dir(project_id)).list_experiments()
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"project_id": project_id, "experiments": [experiment.to_dict() for experiment in experiments]})

    def _handle_project_prompt_ab_detail(self, method: str, project_id: str, ab_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            experiment = PromptABStore(project_dir).read_experiment(ab_id)
            group_store = CandidateGroupStore(project_dir)
            groups = [group_store.read_group(group_id).to_dict() for group_id in experiment.group_ids]
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Prompt A/B experiment not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"project_id": project_id, "experiment": experiment.to_dict(), "groups": groups})

    def _handle_project_prompt_ab_delete(self, method: str, project_id: str, ab_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            PromptABStore(self.project_store.project_dir(project_id)).delete_experiment(ab_id)
            self.project_store.append_event(project_id, "provider_prompt_ab_deleted", {"ab_id": ab_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Prompt A/B experiment not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "deleted": True, "ab_id": ab_id})

    def _handle_project_provider_usage(self, project_id: str) -> None:
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        usage_records = []
        for version in document.versions:
            usage_path = Path(version.output_dir) / "data" / "provider-usage.json"
            if usage_path.exists():
                usage = read_json(usage_path)
                usage_records.append({"version_id": version.version_id, "job_id": version.job_id, "usage": usage})
        group_records = []
        groups_dir = self.project_store.project_dir(project_id) / "candidate-groups"
        if groups_dir.exists():
            for usage_path in sorted(groups_dir.glob("*/provider-usage.json")):
                try:
                    usage = read_json(usage_path)
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
                group_records.append({"group_id": usage_path.parent.name, "usage": usage})
        total_tokens = sum(int(record["usage"].get("total_tokens") or 0) for record in usage_records)
        total_tokens += sum(int(record["usage"].get("total_tokens") or 0) for record in group_records)
        self._send_json(
            {
                "project_id": project_id,
                "total_calls": len(usage_records) + len(group_records),
                "total_tokens": total_tokens,
                "records": usage_records,
                "candidate_group_records": group_records,
            }
        )

    def _handle_project_provider_usage_report(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            project_dir = self.project_store.project_dir(project_id)
            records = collect_project_provider_usage_records(project_id, document.versions, project_dir)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_json(build_provider_usage_report(scope="project", project_id=project_id, records=records))

    def _project_edit_parent(self, project_id: str, version_id: str) -> tuple[Any, Any, JobState, SongPlan]:
        document = self.project_store.sync_project(project_id, self.store.get_job)
        parent = next((version for version in document.versions if version.version_id == version_id), None)
        if parent is None:
            raise FileNotFoundError(version_id)
        parent_job = self.store.get_job(parent.job_id)
        if parent_job is None:
            raise ValueError("Parent version job is missing.")
        if parent.status != "completed" or parent_job.status != "completed":
            raise ValueError("Parent version must be completed before editing.")
        parent_plan_path = Path(parent.output_dir) / "data" / "song-plan.json"
        if not parent_plan_path.exists():
            raise ValueError("Parent song-plan.json is missing.")
        parent_plan = SongPlan.from_dict(read_json(parent_plan_path))
        return document, parent, parent_job, parent_plan

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
        if tail == "/edit":
            metadata = _read_edit_metadata_for_run(run_dir)
            if metadata is None:
                self._send_error(HTTPStatus.NOT_FOUND, "Edit metadata not found.")
                return
            self._send_json({"job_id": job.job_id, "edit": metadata})
            return
        if tail == "/provider-usage":
            usage_path = run_dir / "data" / "provider-usage.json"
            if not usage_path.exists():
                self._send_error(HTTPStatus.NOT_FOUND, "Provider usage not found.")
                return
            self._send_json({"job_id": job.job_id, "usage": read_json(usage_path)})
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

    def _send_file(self, path: Path, content_type: str | None = None, *, filename: str | None = None) -> None:
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
        self.send_header("Content-Disposition", f'attachment; filename="{filename or path.name}"')
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
        self.asset_store = AssetStore()
        self.job_store = JobStore(asset_store=self.asset_store)
        self.batch_store = BatchStore()
        self.project_store = ProjectStore()
        self.edit_preset_store = EditPresetStore()
        self.prompt_template_store = PromptTemplateStore()
        self.batch_runner = BatchRunner(self.batch_store, self.job_store, self.project_store)
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


def _provider_usage_record(
    *,
    config_snapshot: dict[str, Any],
    operation: str,
    template_id: str,
    started_at: str,
    status: str,
    provider_usage: dict[str, Any] | None = None,
    request_id: Any = None,
) -> dict[str, Any]:
    provider_usage = provider_usage or {}
    prompt_tokens = _usage_int(provider_usage, "prompt_tokens")
    completion_tokens = _usage_int(provider_usage, "completion_tokens")
    total_tokens = _usage_int(provider_usage, "total_tokens") or prompt_tokens + completion_tokens
    return {
        "provider_type": config_snapshot.get("wire_api") or "unknown",
        "model": config_snapshot.get("model") or "",
        "operation": operation,
        "template_id": template_id,
        "started_at": started_at,
        "completed_at": _utc_now() if status != "queued" else None,
        "latency_ms": None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": None,
        "request_id": None if request_id is None else str(request_id),
        "status": status,
    }


def _usage_int(usage: dict[str, Any], field_name: str) -> int:
    value = usage.get(field_name)
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


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
    edit_metadata_path = run_dir / "data" / "edit-metadata.json"
    if edit_metadata_path.exists():
        artifacts["edit_metadata"] = str(edit_metadata_path)
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


def _read_edit_metadata_for_run(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "data" / "edit-metadata.json"
    if not path.exists():
        return None
    try:
        metadata = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return metadata


def _top_ranked_candidate_id(group: Any) -> str | None:
    if group.ranking:
        return str(group.ranking[0].get("candidate_id") or "") or None
    ready = [candidate for candidate in group.candidates if candidate.status == "ready"]
    if not ready:
        return None
    return max(ready, key=lambda candidate: int(candidate.scores.get("combined") or 0)).candidate_id


def _candidate_source_summary(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    return {
        "candidate_group_id": str(data.get("candidate_group_id") or ""),
        "candidate_id": str(data.get("candidate_id") or ""),
        "rank": _optional_positive_int(data.get("rank")),
        "score": _optional_positive_int(data.get("score")),
        "quality_overall": _optional_positive_int(data.get("quality_overall")),
        "summary": str(data.get("summary") or "")[:240],
        "status": str(data.get("status") or ""),
        "created_at": str(data.get("created_at") or ""),
    }


def _optional_positive_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _prompt_ab_template_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("template_ids must be a list.")
    template_ids = [str(item).strip() for item in value if str(item).strip()]
    if len(template_ids) < 2:
        raise ValueError("Prompt A/B requires at least two template ids.")
    if len(template_ids) > 4:
        raise ValueError("Prompt A/B supports at most four template ids.")
    return template_ids


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


def _match_edit_preset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/edit-presets/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "reset":
        return None
    if "/" in rest:
        preset_id, tail = rest.split("/", 1)
        return unquote(preset_id), "/" + tail
    return unquote(rest), ""


def _match_prompt_template_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/prompt-templates/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "reset":
        return None
    if "/" in rest:
        template_id, tail = rest.split("/", 1)
        return unquote(template_id), "/" + tail
    return unquote(rest), ""


def _match_asset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/assets/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest.startswith("extract/"):
        return None
    if "/" in rest:
        asset_id, tail = rest.split("/", 1)
        return unquote(asset_id), "/" + tail
    return unquote(rest), ""


def _match_project_variation_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "variation":
        return unquote(parts[1])
    return None


def _match_project_edit_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] in {"edit", "edit-targets"}:
        return unquote(parts[1]), parts[2]
    return None


def _match_project_edit_preview_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "edit-preview":
        return unquote(parts[1]), "", "create"
    if len(parts) == 5 and parts[0] == "versions" and parts[2] == "edit-preview" and parts[4] in {"apply", "delete"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None


def _match_project_edit_candidates_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "edit-candidates":
        return unquote(parts[1]), "create"
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "edit-candidates" and parts[3] == "ab":
        return unquote(parts[1]), "ab"
    return None


def _match_project_candidate_group_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "candidate-groups":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] in {"apply", "delete"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] in {"render-midi", "render-audio"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] == "usage":
        return unquote(parts[1]), "usage"
    return None


def _match_project_candidate_artifact_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 5 and parts[0] == "candidate-groups" and parts[2] == "candidates" and parts[4] in {"midi", "audio", "render-midi", "render-audio"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None


def _match_project_prompt_ab_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 1 and parts[0] == "prompt-ab":
        return "", "list"
    if len(parts) == 2 and parts[0] == "prompt-ab":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "prompt-ab" and parts[2] == "delete":
        return unquote(parts[1]), "delete"
    return None


def _match_project_evaluate_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "evaluate":
        return unquote(parts[1])
    return None


VARIATION_REQUEST_FIELDS = {
    "title",
    "language",
    "style",
    "theme",
    "duration_seconds",
    "vocal_mode",
    "tempo_bpm",
    "key",
    "lyrics",
    "generation_mode",
    "pipeline_mode",
}


def _variation_request_payload(
    parent_request: dict[str, Any],
    request_patch: dict[str, Any],
    *,
    generation_mode: Any = None,
    pipeline_mode: Any = None,
) -> dict[str, Any]:
    unknown = sorted(set(request_patch) - VARIATION_REQUEST_FIELDS)
    if unknown:
        raise ValueError(f"request_patch contains unsupported fields: {', '.join(unknown)}.")
    payload = {key: value for key, value in parent_request.items() if key in VARIATION_REQUEST_FIELDS}
    payload.update(request_patch)
    if generation_mode is not None:
        payload["generation_mode"] = generation_mode
    if pipeline_mode is not None:
        payload["pipeline_mode"] = pipeline_mode
    SongRequest.from_dict(payload)
    _generation_mode(payload)
    _pipeline_mode(payload)
    return payload


def _query_value(query: dict[str, list[str]], name: str) -> str:
    return str(query.get(name, [""])[0] or "").strip()


def _project_matches_filters(
    document: Any,
    *,
    q: str,
    status: str,
    variant_type: str,
    hidden: str,
) -> bool:
    if hidden == "true" and not document.state.hidden:
        return False
    if hidden == "false" and document.state.hidden:
        return False
    if status:
        if status == "selected" and not document.state.selected_version_id:
            return False
        elif status == "final" and not document.state.final_version_id:
            return False
        elif status == "gate_failed" and not any(version.quality_gate_status == "failed" for version in document.versions):
            return False
        elif status not in {"selected", "final", "gate_failed"} and document.state.status != status:
            return False
    if variant_type and not any(version.variant_type == variant_type for version in document.versions):
        return False
    if q:
        needle = q.lower()
        haystack = " ".join(
            [
                document.state.name,
                document.state.description,
                " ".join(document.state.tags),
                *[version.name for version in document.versions],
                *[version.note for version in document.versions],
            ]
        ).lower()
        if needle not in haystack:
            return False
    return True


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


def _clean_title(value: Any) -> str:
    return str(value or "").strip()


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
