from __future__ import annotations

import json
import mimetypes
import os
import re
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
from song_agent.editor_clips import (
    EditorClipError,
    EditorClipUnavailableError,
    build_clip_insert_patch,
    build_editor_clip_from_ref,
    list_editor_clips,
)
from song_agent.editor_templates import (
    EditorTemplateError,
    EditorTemplateStore,
    EditorTemplateUnavailableError,
    build_multitrack_clip_from_ref,
    build_multitrack_clip_insert_patch,
    section_template_public_dict,
    suggest_lane_mappings,
    track_template_public_dict,
)
from song_agent.editor_audition import (
    EditorAuditionError,
    EditorAuditionStore,
    EditorAuditionUnavailableError,
    audition_summary_for_preview,
)
from song_agent.editor_review import EditorReviewError, audition_asset_payload
from song_agent.editor_view import build_editor_diff, build_editor_view, build_editor_view_from_result
from song_agent.final_export import (
    FinalExportError,
    FinalExportOptions,
    build_final_export_bundle,
    build_final_export_zip,
    final_export_dir,
    final_export_zip_path,
    read_final_export_manifest,
)
from song_agent.context_packs import (
    ContextPackStaleError,
    ContextPackStore,
    apply_context_pack,
    context_pack_public_dict,
    context_pack_snapshot,
    merge_context_refs,
    write_context_pack_snapshot,
)
from song_agent.library_index import LibraryIndexStore, asset_source_hash, recommend_library_context, search_library
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
from song_agent.review_edits import (
    ReviewEditError,
    ReviewEditStore,
    ReviewEditUnavailableError,
    apply_review_edit,
    build_review_edit,
    review_edit_instruction_for_provider,
    review_edit_metadata,
    review_edit_summary,
)
from song_agent.review_tasks import (
    ReviewTaskError,
    ReviewTaskStateError,
    ReviewTaskStore,
    apply_candidate_intents,
    build_provider_review_candidates,
    build_review_decision_report,
    build_local_review_candidates,
    candidate_apply_metadata,
    ensure_candidate_current,
    _ensure_task_open_for_apply,
    ensure_task_current,
    mark_task_archived,
    mark_task_resolved,
    review_candidate_summary,
    review_candidate_source_breakdown,
    review_decision_summary,
    review_task_summary,
    task_list_summary,
)
from song_agent.review_sprints import (
    ReviewSprintError,
    ReviewSprintStateError,
    ReviewSprintStore,
    review_sprint_export_summary,
)
from song_agent.review_sprint_recommendations import (
    build_review_sprint_recommendation_report,
    recommendation_report_summary,
)
from song_agent.provider_usage import (
    build_provider_usage_report,
    collect_candidate_group_provider_usage_records,
    collect_project_provider_usage_records,
    usage_record_from_file,
)
from song_agent.prompt_ab import PromptABStore
from song_agent.projects import ProjectStore
from song_agent.references import (
    MAX_REFERENCE_WAV_BYTES,
    ReferenceStore,
    reference_file_url,
    reference_prompt_summaries,
    reference_public_dict,
    reference_refs_snapshot,
    write_reference_refs_snapshot,
)
from song_agent.redaction import sanitize_metadata
from song_agent.reference_analysis import (
    ReferenceAnalysisError,
    analyze_reference,
    create_asset_from_slice,
    generate_slices,
    get_analysis_report,
    get_slice_manifest,
    render_reference_slice_audio,
    render_reference_slice_midi,
    require_fresh_analysis,
    require_fresh_slices,
    slice_audio_path,
    slice_midi_path,
)
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
from song_agent.song_editor import (
    EditorPatchError,
    EditorPatchStaleError,
    EditorPreviewStore,
    apply_editor_patch,
    build_editor_state,
    editor_edit_metadata,
    song_plan_hash as editor_song_plan_hash,
)
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
REFERENCE_IMPORT_MAX_BODY_BYTES = int(MAX_REFERENCE_WAV_BYTES * 4 / 3) + 1_000_000


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
    def __init__(
        self,
        runs_dir: Path = RUNS_DIR,
        asset_store: AssetStore | None = None,
        reference_store: ReferenceStore | None = None,
        context_pack_store: ContextPackStore | None = None,
    ) -> None:
        self.runs_dir = Path(runs_dir).resolve()
        self.asset_store = asset_store or AssetStore()
        self.reference_store = reference_store or ReferenceStore()
        self.context_pack_store = context_pack_store or ContextPackStore()
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
        reference_refs = payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else []
        context_pack = payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None
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
                input_payload={
                    **request.to_dict(),
                    **({"asset_refs": asset_refs} if asset_refs else {}),
                    **({"reference_refs": reference_refs} if reference_refs else {}),
                    **({"context_pack": context_pack} if context_pack else {}),
                },
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
        reference_refs: list[dict[str, Any]] | None = None,
        context_pack: dict[str, Any] | None = None,
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
            if reference_refs:
                metadata["reference_refs"] = list(reference_refs)
            if context_pack:
                metadata["context_pack"] = dict(context_pack)
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
                    **({"reference_refs": list(reference_refs)} if reference_refs else {}),
                    **({"context_pack": dict(context_pack)} if context_pack else {}),
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
            context_snapshot = self._prepare_context_pack_for_job(job)
            asset_snapshot = self._prepare_asset_refs_for_job(job)
            reference_snapshot = self._prepare_reference_refs_for_job(job)
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
            if reference_snapshot["reference_refs"]:
                write_reference_refs_snapshot(Path(job.output_dir), reference_snapshot)
                self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "job_generation", "job_id": job.job_id})
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
            if (Path(job.output_dir) / "data" / "reference-refs.json").exists():
                artifacts["reference_refs"] = str(Path(job.output_dir) / "data" / "reference-refs.json")
            if (Path(job.output_dir) / "data" / "context-pack.json").exists():
                artifacts["context_pack"] = str(Path(job.output_dir) / "data" / "context-pack.json")
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
            context_snapshot = self._prepare_context_pack_for_job(job)
            asset_snapshot = self._prepare_asset_refs_for_job(job)
            reference_snapshot = self._prepare_reference_refs_for_job(job)
            provider_patch_data = metadata.get("provider_patch")
            if provider_patch_data:
                patch = ProviderEditPatch.from_dict(provider_patch_data)
                result = apply_provider_edit_patch(parent_plan, patch)
            else:
                result = apply_edit_intent(parent_plan, intent)
            if asset_snapshot["asset_refs"]:
                result_plan = apply_asset_refs_to_plan(result.plan, self.asset_store, asset_snapshot["asset_refs"])
                result = EditedSongPlanResult(plan=result_plan, summary=result.summary, warnings=result.warnings)
            if metadata.get("edit_source") == "audition_review" and isinstance(metadata.get("review_edit"), dict):
                from song_agent.review_edits import ReviewEditIntent

                review_edit_result = apply_review_edit(parent_plan, ReviewEditIntent.from_dict(metadata["review_edit"]))
                result = review_edit_result
                if asset_snapshot["asset_refs"]:
                    result_plan = apply_asset_refs_to_plan(result.plan, self.asset_store, asset_snapshot["asset_refs"])
                    result = EditedSongPlanResult(plan=result_plan, summary=result.summary, warnings=result.warnings)
            if metadata.get("edit_source") == "review_task_candidate" and isinstance(metadata.get("review_candidate_intents"), list):
                intents = [EditIntent.from_dict(dict(item)) for item in metadata["review_candidate_intents"] if isinstance(item, dict)]
                result = apply_candidate_intents(parent_plan, intents)
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
            if reference_snapshot["reference_refs"]:
                edit_metadata["reference_refs"] = list(reference_snapshot["reference_refs"])
            if context_snapshot:
                edit_metadata["context_pack"] = context_snapshot
            if metadata.get("edit_source") == "audition_review":
                edit_metadata.update(
                    {
                        "edit_source": "audition_review",
                        "review_edit": metadata.get("review_edit"),
                        "review_summary": metadata.get("review_summary") or {},
                    }
                )
            if metadata.get("edit_source") == "review_task_candidate":
                edit_metadata.update(
                    {
                        "edit_source": "review_task_candidate",
                        "operation_count": len(metadata.get("review_candidate_intents") or []),
                        "review_task": metadata.get("review_task") if isinstance(metadata.get("review_task"), dict) else {},
                        "review_candidate": metadata.get("review_candidate") if isinstance(metadata.get("review_candidate"), dict) else {},
                        "review_candidate_source": metadata.get("review_candidate_source") if isinstance(metadata.get("review_candidate_source"), dict) else {},
                        "review_provider_patch": metadata.get("review_provider_patch") if isinstance(metadata.get("review_provider_patch"), dict) else {},
                        "review_decision": metadata.get("review_decision") if isinstance(metadata.get("review_decision"), dict) else {},
                        "review_sprint": metadata.get("review_sprint") if isinstance(metadata.get("review_sprint"), dict) else {},
                        "review_sprint_recommendation": metadata.get("review_sprint_recommendation") if isinstance(metadata.get("review_sprint_recommendation"), dict) else {},
                        "review_edit": metadata.get("review_edit") if isinstance(metadata.get("review_edit"), dict) else {},
                        "review_candidate_intents": metadata.get("review_candidate_intents") if isinstance(metadata.get("review_candidate_intents"), list) else [],
                    }
                )
            write_json(paths.data / "edit-metadata.json", edit_metadata)
            if asset_snapshot["asset_refs"]:
                write_asset_refs_snapshot(run_dir, asset_snapshot)
                self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "edit", "job_id": job.job_id, "project_id": metadata.get("project_id"), "version_id": metadata.get("parent_version_id")})
            if reference_snapshot["reference_refs"]:
                write_reference_refs_snapshot(run_dir, reference_snapshot)
                self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "edit", "job_id": job.job_id, "project_id": metadata.get("project_id"), "version_id": metadata.get("parent_version_id")})
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
            if (paths.data / "reference-refs.json").exists():
                artifacts["reference_refs"] = str(paths.data / "reference-refs.json")
            if (paths.data / "context-pack.json").exists():
                artifacts["context_pack"] = str(paths.data / "context-pack.json")
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

    def _prepare_reference_refs_for_job(self, job: JobState) -> dict[str, Any]:
        snapshot = reference_refs_snapshot(self.reference_store, job.input_payload.get("reference_refs"), captured_at=_utc_now())
        if snapshot["reference_refs"]:
            ProjectPaths.create(Path(job.output_dir))
            write_reference_refs_snapshot(Path(job.output_dir), snapshot)
        return snapshot

    def _prepare_context_pack_for_job(self, job: JobState) -> dict[str, Any] | None:
        context_pack = job.input_payload.get("context_pack")
        if not isinstance(context_pack, dict) or not context_pack.get("pack_id"):
            return None
        pack = self.context_pack_store.read_pack(str(context_pack["pack_id"]))
        applied = {
            "asset_refs": job.input_payload.get("asset_refs") if isinstance(job.input_payload.get("asset_refs"), list) else [],
            "reference_refs": job.input_payload.get("reference_refs") if isinstance(job.input_payload.get("reference_refs"), list) else [],
        }
        snapshot = context_pack_snapshot(pack, applied, captured_at=_utc_now())
        ProjectPaths.create(Path(job.output_dir))
        write_context_pack_snapshot(Path(job.output_dir), snapshot)
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
            if self._archive_completed_project_items(document):
                changed = True
            if changed:
                self.batch_store.save_batch(document)
                document = self.batch_store.get_batch(batch_id)
            return document

    def _archive_completed_project_items(self, document: BatchDocument) -> bool:
        changed = False
        for item in sorted(document.items, key=lambda batch_item: batch_item.index):
            if item.status != "completed" or not item.project:
                continue
            if item.project_id and item.version_id:
                continue
            if self._has_unarchived_prior_project_item(document, item):
                continue
            if not item.job_id:
                continue
            job = self.job_store.get_job(item.job_id)
            if job is None or job.status != "completed":
                continue
            self._archive_item_to_project(document, item, job)
            changed = True
        return changed

    @staticmethod
    def _has_unarchived_prior_project_item(document: BatchDocument, item: Any) -> bool:
        for prior in document.items:
            if prior.index >= item.index or prior.project != item.project:
                continue
            if prior.status in {"queued", "running"}:
                return True
            if prior.status == "completed" and not prior.version_id:
                return True
        return False

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
    def editor_template_store(self) -> EditorTemplateStore:
        return self.server.editor_template_store  # type: ignore[attr-defined]

    @property
    def asset_store(self) -> AssetStore:
        return self.server.asset_store  # type: ignore[attr-defined]

    @property
    def reference_store(self) -> ReferenceStore:
        return self.server.reference_store  # type: ignore[attr-defined]

    @property
    def library_index_store(self) -> LibraryIndexStore:
        return self.server.library_index_store  # type: ignore[attr-defined]

    @property
    def context_pack_store(self) -> ContextPackStore:
        return self.server.context_pack_store  # type: ignore[attr-defined]

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
                    payload = self._expand_context_pack_payload(payload)
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

            if path == "/api/library/index":
                self._handle_library_index(method)
                return

            if path == "/api/library/rebuild":
                self._handle_library_rebuild(method)
                return

            if path == "/api/library/search":
                self._handle_library_search(method)
                return

            if path == "/api/library/recommend":
                self._handle_library_recommend(method)
                return

            if path == "/api/context-packs":
                self._handle_context_packs_root(method, parsed.query)
                return

            if path == "/api/references":
                self._handle_references_root(method, parsed.query)
                return

            if path == "/api/references/import":
                self._handle_reference_import(method)
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

            if path == "/api/editor-templates":
                self._handle_editor_templates_root(method, parsed.query)
                return

            editor_template_route = _match_editor_template_route(path)
            if editor_template_route is not None:
                template_type, template_id, tail = editor_template_route
                self._handle_editor_template_route(method, template_type, template_id, tail)
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

            reference_route = _match_reference_route(path)
            if reference_route is not None:
                reference_id, tail = reference_route
                self._handle_reference_route(method, reference_id, tail)
                return

            context_pack_route = _match_context_pack_route(path)
            if context_pack_route is not None:
                pack_id, tail = context_pack_route
                self._handle_context_pack_route(method, pack_id, tail)
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
        except ContextPackStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
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

    def _handle_editor_templates_root(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = parse_qs(query_string)
        include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
        self._send_json(self.editor_template_store.to_response(include_hidden=include_hidden, project_store=self.project_store))

    def _handle_editor_template_route(self, method: str, template_type: str, template_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if template_type == "sections":
                    template = self.editor_template_store.read_section_template(template_id)
                    self._send_json({"template": section_template_public_dict(template, project_store=self.project_store)})
                    return
                template = self.editor_template_store.read_track_template(template_id)
                self._send_json({"template": track_template_public_dict(template)})
                return
            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                template = self.editor_template_store.hide_template("section" if template_type == "sections" else "track", template_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "template": template})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.editor_template_store.delete_template("section" if template_type == "sections" else "track", template_id)
                self._send_json({"ok": True, "deleted": True, "template_id": template_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Editor template route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor template not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

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
                if isinstance(payload.get("asset_refs"), list):
                    request_payload["asset_refs"] = payload["asset_refs"]
                if isinstance(payload.get("reference_refs"), list):
                    request_payload["reference_refs"] = payload["reference_refs"]
                if payload.get("context_pack_id"):
                    request_payload["context_pack_id"] = payload["context_pack_id"]
                request_payload = self._expand_context_pack_payload(request_payload)
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

    def _handle_library_index(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        self._send_json({"ok": True, "index": index.summary()})

    def _handle_library_rebuild(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        index = self.library_index_store.rebuild(self.asset_store, self.reference_store, now=_utc_now())
        self._send_json({"ok": True, "index": index.summary()})

    def _handle_library_search(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        result = search_library(index, payload)
        self.library_index_store.append_event("library_search_requested", {"result_count": result["count"], "query": result.get("query")}, now=_utc_now())
        self._send_json(result)

    def _handle_library_recommend(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        result = recommend_library_context(index, payload)
        recommendation = result.get("recommendation", {})
        self.library_index_store.append_event(
            "library_recommend_requested",
            {
                "asset_count": len(recommendation.get("asset_results", [])),
                "reference_count": len(recommendation.get("reference_results", [])),
                "goal": payload.get("goal"),
            },
            now=_utc_now(),
        )
        self._send_json(result)

    def _handle_context_packs_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            packs = self.context_pack_store.list_packs(include_hidden=include_hidden)
            self._send_json({"context_packs": [context_pack_public_dict(pack) for pack in packs], "count": len(packs)})
            return
        if method == "POST":
            try:
                pack = self.context_pack_store.create_pack(
                    self._read_json_body(),
                    asset_store=self.asset_store,
                    reference_store=self.reference_store,
                    now=_utc_now(),
                )
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_context_pack_route(self, method: str, pack_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"context_pack": context_pack_public_dict(self.context_pack_store.read_pack(pack_id))})
                return
            if tail == "/apply-preview":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                applied = self.context_pack_store.apply_preview(pack_id, asset_store=self.asset_store, reference_store=self.reference_store, captured_at=_utc_now())
                self.context_pack_store.append_event(pack_id, "context_pack_applied", {"mode": "preview"}, now=_utc_now())
                self._send_json(applied)
                return
            if tail == "/hide":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                pack = self.context_pack_store.hide_pack(pack_id, True)
                self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)})
                return
            if tail == "/unhide":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                pack = self.context_pack_store.hide_pack(pack_id, False)
                self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.context_pack_store.delete_pack(pack_id)
                self._send_json({"ok": True, "deleted": True, "pack_id": pack_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Context pack route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Context pack not found.")
        except ContextPackStaleError as exc:
            try:
                self.context_pack_store.append_event(pack_id, "context_pack_stale", {"error": str(exc)}, now=_utc_now())
            except (OSError, ValueError):
                pass
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

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

    def _handle_references_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            filters = {key: _query_value(query, key) for key in ("q", "type", "tag", "favorite", "project_id")}
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            limit_value = _query_value(query, "limit")
            limit = int(limit_value) if limit_value else 100
            references = self.reference_store.list_references(include_hidden=include_hidden, filters=filters)[: max(1, min(limit, 500))]
            self._send_json(
                {
                    "references": [reference_public_dict(reference) for reference in references],
                    "count": len(references),
                    "filters": {**filters, "include_hidden": include_hidden},
                }
            )
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_reference_import(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        if not self._content_length_within(REFERENCE_IMPORT_MAX_BODY_BYTES):
            self._send_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Reference import request body is too large.")
            return
        try:
            reference, duplicate = self.reference_store.import_reference(self._read_json_body(), now=_utc_now())
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(
            {"ok": True, "duplicate": duplicate, "reference": reference_public_dict(reference)},
            status=HTTPStatus.OK if duplicate else HTTPStatus.CREATED,
        )

    def _handle_reference_route(self, method: str, reference_id: str, tail: str) -> None:
        try:
            if tail == "":
                if method == "GET":
                    self._send_json({"reference": reference_public_dict(self.reference_store.read_reference(reference_id))})
                    return
                if method == "POST":
                    reference = self.reference_store.update_reference(reference_id, self._read_json_body())
                    self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail in {"/hide", "/unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reference = self.reference_store.hide_reference(reference_id, hidden=tail == "/hide")
                self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                return
            if tail in {"/favorite", "/unfavorite"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reference = self.reference_store.favorite_reference(reference_id, favorite=tail == "/favorite")
                self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                return
            if tail == "/delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.reference_store.delete_reference(reference_id)
                self._send_json({"ok": True, "deleted": True, "reference_id": reference_id})
                return
            if tail == "/file":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                reference = self.reference_store.read_reference(reference_id)
                self._send_file(self.reference_store.file_path(reference_id), reference.media_type, filename=reference.original_filename)
                return
            if tail == "/analysis":
                if method == "GET":
                    self._send_json({"analysis": get_analysis_report(self.reference_store, reference_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    self._send_json({"ok": True, "analysis": analyze_reference(self.reference_store, reference_id, force=bool(payload.get("force", False)), now=_utc_now())})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/analyze":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                self._send_json({"ok": True, "analysis": analyze_reference(self.reference_store, reference_id, force=bool(payload.get("force", False)), now=_utc_now())})
                return
            if tail == "/slices":
                if method == "GET":
                    self._send_json({"manifest": get_slice_manifest(self.reference_store, reference_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    require_fresh_analysis(self.reference_store, reference_id)
                    self._send_json({"ok": True, "manifest": generate_slices(self.reference_store, reference_id, force=bool(payload.get("force", False)), now=_utc_now())})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail.startswith("/slices/"):
                self._handle_reference_slice_route(method, reference_id, tail)
                return
            if tail in {"/link-project", "/unlink-project"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                project_id = str(payload.get("project_id") or "")
                self.project_store.get_project(project_id)
                reference = (
                    self.reference_store.link_project(reference_id, project_id)
                    if tail == "/link-project"
                    else self.reference_store.unlink_project(reference_id, project_id)
                )
                self._send_json({"ok": True, "reference": reference_public_dict(reference)})
                return
            if tail == "/create-asset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = self.reference_store.create_asset_from_reference(reference_id, self._read_json_body(), self.asset_store)
                self._send_json({"ok": True, "asset": asset}, status=HTTPStatus.CREATED)
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Reference not found.")
            return
        except ReferenceAnalysisError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            status = HTTPStatus.CONFLICT if "Hidden references" in str(exc) or "cannot be converted" in str(exc) else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Reference route not found.")

    def _handle_reference_slice_route(self, method: str, reference_id: str, tail: str) -> None:
        parts = tail.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "slices":
            self._send_error(HTTPStatus.NOT_FOUND, "Reference slice route not found.")
            return
        slice_id = unquote(parts[1])
        action = parts[2]
        try:
            if action == "render-midi":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **render_reference_slice_midi(self.reference_store, reference_id, slice_id, now=_utc_now())})
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                self._send_json({"ok": True, **render_reference_slice_audio(self.reference_store, reference_id, slice_id, config, now=_utc_now())})
                return
            if action == "create-asset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                asset = create_asset_from_slice(self.reference_store, reference_id, slice_id, self._read_json_body(), self.asset_store, now=_utc_now())
                self._send_json({"ok": True, "asset": asset}, status=HTTPStatus.CREATED)
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = require_fresh_slices(self.reference_store, reference_id)
                reference_dir = self.reference_store.reference_dir(reference_id)
                if not any(item.get("slice_id") == slice_id for item in manifest.get("slices", []) if isinstance(item, dict)):
                    raise FileNotFoundError(slice_id)
                self._send_file(slice_midi_path(reference_dir, slice_id), "audio/midi", filename=f"{reference_id}-{slice_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = require_fresh_slices(self.reference_store, reference_id)
                if not any(item.get("slice_id") == slice_id for item in manifest.get("slices", []) if isinstance(item, dict)):
                    raise FileNotFoundError(slice_id)
                reference_dir = self.reference_store.reference_dir(reference_id)
                self._send_file(slice_audio_path(reference_dir, slice_id), "audio/wav", filename=f"{reference_id}-{slice_id}.wav")
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Reference slice not found.")
            return
        except ReferenceAnalysisError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Reference slice route not found.")

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
        editor_state_version = _match_project_editor_state_tail(tail)
        if editor_state_version is not None:
            self._handle_project_editor_state(method, project_id, editor_state_version)
            return

        editor_view_match = _match_project_editor_view_tail(tail)
        if editor_view_match is not None:
            self._handle_project_editor_view(method, project_id, editor_view_match)
            return

        editor_draft_match = _match_project_editor_draft_tail(tail)
        if editor_draft_match is not None:
            self._handle_project_editor_draft(method, project_id, editor_draft_match)
            return

        editor_clips_match = _match_project_editor_clips_tail(tail)
        if editor_clips_match is not None:
            self._handle_project_editor_clips(method, project_id, editor_clips_match)
            return

        editor_clip_draft_match = _match_project_editor_clip_draft_tail(tail)
        if editor_clip_draft_match is not None:
            self._handle_project_editor_clip_draft(method, project_id, editor_clip_draft_match)
            return

        section_template_match = _match_project_section_template_tail(tail)
        if section_template_match is not None:
            self._handle_project_section_template_create(method, project_id, section_template_match)
            return

        track_template_match = _match_project_track_template_tail(tail)
        if track_template_match is not None:
            self._handle_project_track_template_create(method, project_id, track_template_match)
            return

        template_mapping_match = _match_project_editor_template_mapping_tail(tail)
        if template_mapping_match is not None:
            self._handle_project_editor_template_mapping(method, project_id, template_mapping_match)
            return

        multitrack_draft_match = _match_project_editor_multitrack_clip_draft_tail(tail)
        if multitrack_draft_match is not None:
            self._handle_project_editor_multitrack_clip_draft(method, project_id, multitrack_draft_match)
            return

        editor_preview_create = _match_project_editor_preview_create_tail(tail)
        if editor_preview_create is not None:
            self._handle_project_editor_preview_create(method, project_id, editor_preview_create)
            return

        version_audio_match = _match_project_version_audio_tail(tail)
        if version_audio_match is not None:
            version_id, action = version_audio_match
            self._handle_project_version_audio_route(method, project_id, version_id, action)
            return

        editor_preview_root = _match_project_editor_preview_root_tail(tail)
        if editor_preview_root is not None:
            self._handle_project_editor_preview_root(method, project_id, editor_preview_root)
            return

        if tail == "/audition-reviews":
            self._handle_project_audition_reviews(method, project_id, None, query_string)
            return

        editor_review_root = _match_project_editor_audition_reviews_tail(tail)
        if editor_review_root is not None:
            self._handle_project_audition_reviews(method, project_id, editor_review_root, query_string)
            return

        editor_auditions_root = _match_project_editor_auditions_root_tail(tail)
        if editor_auditions_root is not None:
            preview_id = editor_auditions_root
            self._handle_project_editor_auditions_root(method, project_id, preview_id)
            return

        editor_audition_marker_match = _match_project_editor_audition_marker_tail(tail)
        if editor_audition_marker_match is not None:
            preview_id, audition_id, marker_id, action = editor_audition_marker_match
            self._handle_project_editor_audition_marker_route(method, project_id, preview_id, audition_id, marker_id, action)
            return

        editor_audition_match = _match_project_editor_audition_tail(tail)
        if editor_audition_match is not None:
            preview_id, audition_id, action = editor_audition_match
            self._handle_project_editor_audition_route(method, project_id, preview_id, audition_id, action)
            return

        review_sprint_match = _match_project_review_sprint_tail(tail)
        if review_sprint_match is not None:
            sprint_id, action = review_sprint_match
            self._handle_project_review_sprint_route(method, project_id, sprint_id, action)
            return

        if tail == "/review-sprints":
            self._handle_project_review_sprints_root(method, project_id, query_string)
            return

        review_task_candidate_match = _match_project_review_task_candidate_tail(tail)
        if review_task_candidate_match is not None:
            task_id, candidate_id, action = review_task_candidate_match
            self._handle_project_review_task_candidate_route(method, project_id, task_id, candidate_id, action)
            return

        review_task_match = _match_project_review_task_tail(tail)
        if review_task_match is not None:
            task_id, action = review_task_match
            self._handle_project_review_task_route(method, project_id, task_id, action)
            return

        if tail == "/review-tasks":
            self._handle_project_review_tasks_root(method, project_id, query_string)
            return

        editor_preview_match = _match_project_editor_preview_tail(tail)
        if editor_preview_match is not None:
            preview_id, action = editor_preview_match
            self._handle_project_editor_preview_route(method, project_id, preview_id, action)
            return

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
                if isinstance(payload.get("reference_refs"), list):
                    request_payload["reference_refs"] = payload["reference_refs"]
                if payload.get("context_pack_id"):
                    request_payload["context_pack_id"] = payload["context_pack_id"]
                request_payload = self._expand_context_pack_payload(request_payload)
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

        if tail == "/references":
            self._handle_project_references(method, project_id)
            return

        if tail in {"/references/link", "/references/unlink"}:
            self._handle_project_reference_link(method, project_id, unlink=tail.endswith("/unlink"))
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

    def _handle_project_references(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            references = self.reference_store.list_references(filters={"project_id": project_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        self._send_json({"project_id": project_id, "references": [reference_public_dict(reference) for reference in references]})

    def _handle_project_reference_link(self, method: str, project_id: str, *, unlink: bool) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        reference_id = str(payload.get("reference_id") or "")
        try:
            self.project_store.get_project(project_id)
            reference = (
                self.reference_store.unlink_project(reference_id, project_id)
                if unlink
                else self.reference_store.link_project(reference_id, project_id)
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project or reference not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self.project_store.append_event(project_id, "reference_unlinked" if unlink else "reference_linked", {"reference_id": reference.reference_id})
        self._send_json({"ok": True, "reference": reference_public_dict(reference)})

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
            if isinstance(payload.get("reference_refs"), list):
                request_payload["reference_refs"] = payload["reference_refs"]
            if payload.get("context_pack_id"):
                request_payload["context_pack_id"] = payload["context_pack_id"]
            request_payload = self._expand_context_pack_payload(request_payload)
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
            payload = self._expand_context_pack_payload(payload)
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
                reference_refs=payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else None,
                context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
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

    def _handle_project_editor_state(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _job, plan = self._project_edit_parent(project_id, version_id)
            state = build_editor_state(plan)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"project_id": project_id, "version_id": version.version_id, **state})

    def _handle_project_editor_view(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _job, plan = self._project_edit_parent(project_id, version_id)
            view = build_editor_view(plan)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json({"project_id": project_id, "version_id": version.version_id, "view": view})

    def _handle_project_editor_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        patch_data = payload.get("patch")
        if not isinstance(patch_data, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "patch must be an object.")
            return
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            result = apply_editor_patch(parent_plan, patch_data)
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": list(result.warnings),
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response: dict[str, Any] = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(result.patch.operations),
                "summary": summary,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", False)):
                response["view"] = build_editor_view_from_result(result)
            if bool(payload.get("include_diff", False)):
                response["diff"] = build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)

    def _handle_project_editor_clips(self, method: str, project_id: str, version_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            _document, version, _parent_job, _parent_plan = self._project_edit_parent(project_id, version_id)
            catalog = list_editor_clips(
                project_id=project_id,
                version_id=version.version_id,
                asset_store=self.asset_store,
                reference_store=self.reference_store,
                project_store=self.project_store,
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorClipError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        self._send_json(catalog)

    def _handle_project_editor_clip_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = build_editor_clip_from_ref(
                payload.get("clip_ref"),
                default_project_id=project_id,
                asset_store=self.asset_store,
                reference_store=self.reference_store,
                project_store=self.project_store,
            )
            existing_patch_data = payload.get("current_patch")
            existing_result = None
            draft_plan = None
            existing_operations: list[dict[str, Any]] = []
            existing_metadata: dict[str, Any] = {}
            draft_state = None
            if isinstance(existing_patch_data, dict):
                existing_result = apply_editor_patch(parent_plan, existing_patch_data)
                draft_plan = existing_result.plan
                existing_operations = list(existing_result.patch.operations)
                existing_metadata = dict(existing_result.patch.metadata)
                draft_state = build_editor_view_from_result(existing_result)
            patch_data, clip_summary, clip_warnings = build_clip_insert_patch(parent_plan, clip, payload, draft_plan=draft_plan, draft_state=draft_state)
            combined_patch = {
                **patch_data,
                "operations": [*existing_operations, *patch_data["operations"]],
                "metadata": self._merge_editor_patch_metadata(existing_metadata, patch_data.get("metadata")),
            }
            result = apply_editor_patch(parent_plan, combined_patch)
            warnings = [*clip_warnings, *result.warnings]
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": warnings,
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(patch_data["operations"]),
                "patch": patch_data,
                "combined_patch": result.patch.to_dict(),
                "clip_summary": clip_summary,
                "summary": summary,
                "warnings": warnings,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_clip_schema", "editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", True)):
                draft_view = build_editor_view_from_result(result)
                response["draft_view"] = draft_view
                response["view"] = draft_view
            if bool(payload.get("include_diff", True)):
                response["diff"] = build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Clip or version not found.")
            return
        except EditorClipUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorClipError, EditorPatchError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)

    def _handle_project_section_template_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            self.project_store.get_project(project_id)
            template = self.editor_template_store.create_section_template_from_project_version(
                project_store=self.project_store,
                project_id=project_id,
                version_id=version_id,
                section_id=str(payload.get("section_id") or ""),
                payload=payload,
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "section_template_created", {"version_id": version_id, "template_id": template.template_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "template": section_template_public_dict(template, project_store=self.project_store)}, status=HTTPStatus.CREATED)

    def _handle_project_track_template_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            self.project_store.get_project(project_id)
            template = self.editor_template_store.create_track_template_from_project_version(
                project_store=self.project_store,
                project_id=project_id,
                version_id=version_id,
                track_id=str(payload.get("track_id") or ""),
                payload=payload,
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "track_template_created", {"version_id": version_id, "template_id": template.template_id})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "template": track_template_public_dict(template)}, status=HTTPStatus.CREATED)

    def _handle_project_editor_template_mapping(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = build_multitrack_clip_from_ref(
                payload.get("source_ref"),
                template_store=self.editor_template_store,
                project_store=self.project_store,
                default_project_id=project_id,
            )
            state = build_editor_state(parent_plan)
            suggestions = suggest_lane_mappings(clip, state)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Template or version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, EditorPatchError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "project_id": project_id, "version_id": version.version_id, "clip": clip.summary(), "suggestions": suggestions})

    def _handle_project_editor_multitrack_clip_draft(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            _document, version, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            clip = build_multitrack_clip_from_ref(
                payload.get("source_ref"),
                template_store=self.editor_template_store,
                project_store=self.project_store,
                default_project_id=project_id,
            )
            existing_patch_data = payload.get("current_patch")
            existing_result = None
            draft_plan = None
            existing_operations: list[dict[str, Any]] = []
            existing_metadata: dict[str, Any] = {}
            draft_state = None
            if isinstance(existing_patch_data, dict):
                existing_result = apply_editor_patch(parent_plan, existing_patch_data)
                draft_plan = existing_result.plan
                existing_operations = list(existing_result.patch.operations)
                existing_metadata = dict(existing_result.patch.metadata)
                draft_state = build_editor_view_from_result(existing_result)
            patch_data, template_summary, template_warnings = build_multitrack_clip_insert_patch(parent_plan, clip, payload, draft_plan=draft_plan, draft_state=draft_state)
            combined_patch = {
                **patch_data,
                "operations": [*existing_operations, *patch_data["operations"]],
                "metadata": self._merge_editor_patch_metadata(existing_metadata, patch_data.get("metadata")),
            }
            result = apply_editor_patch(parent_plan, combined_patch)
            warnings = [*template_warnings, *result.warnings]
            summary = {
                "operation_count": len(result.patch.operations),
                "changed_sections": list(result.summary.get("changed_sections") or []),
                "changed_tracks": list(result.summary.get("changed_tracks") or []),
                "warnings": warnings,
                "operation_counts": dict(result.summary.get("operation_counts") or {}),
            }
            response = {
                "ok": True,
                "project_id": project_id,
                "version_id": version.version_id,
                "base_plan_hash": result.patch.base_plan_hash,
                "operation_count": len(patch_data["operations"]),
                "patch": patch_data,
                "combined_patch": result.patch.to_dict(),
                "template_summary": template_summary,
                "mapping_suggestions": suggest_lane_mappings(clip, build_editor_state(parent_plan)),
                "summary": summary,
                "warnings": warnings,
                "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                "validator": {"status": "passed", "checks": ["editor_template_schema", "editor_patch_schema", "song_plan_validation"]},
            }
            if bool(payload.get("include_view", True)):
                draft_view = build_editor_view_from_result(result)
                response["draft_view"] = draft_view
                response["view"] = draft_view
            if bool(payload.get("include_diff", True)):
                response["diff"] = build_editor_diff(parent_plan, result.plan, result.patch)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Template or version not found.")
            return
        except EditorTemplateUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except (EditorTemplateError, EditorPatchError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json(response)

    def _handle_project_editor_preview_create(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        patch_data = payload.get("patch")
        if not isinstance(patch_data, dict):
            self._send_error(HTTPStatus.BAD_REQUEST, "patch must be an object.")
            return
        try:
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            result = apply_editor_patch(parent_plan, patch_data)
            project_dir = self.project_store.project_dir(project_id)
            preview, _preview_dir = EditorPreviewStore(project_dir).create_preview(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job_id=parent_job.job_id,
                parent_plan=parent_plan,
                patch=result.patch,
                result=result,
                render_midi=bool(payload.get("render_midi", True)),
                now=_utc_now(),
            )
            self.project_store.append_event(
                project_id,
                "editor_preview_created",
                {
                    "parent_version_id": parent.version_id,
                    "preview_id": preview.preview_id,
                    "operation_count": preview.operation_count,
                },
            )
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except EditorPatchError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_json({"ok": True, "preview": preview.to_dict()}, status=HTTPStatus.CREATED)

    def _handle_project_version_audio_route(self, method: str, project_id: str, version_id: str, action: str) -> None:
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next((item for item in document.versions if item.version_id == version_id), None)
            if version is None:
                raise FileNotFoundError(version_id)
            job = self.store.get_job(version.job_id)
            if job is None:
                raise FileNotFoundError(version.job_id)
            audio_path = Path(job.output_dir) / "renders" / "song.wav"
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if not audio_path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Audio render is not available for this version.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{version_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audio, status, error = self.store.render_job_audio(job.job_id)
                if error is not None:
                    self._send_error(status, str(sanitize_metadata({"error": error}).get("error") or "Audio render failed."))
                    return
                self.project_store.append_event(project_id, "project_version_audio_rendered", {"version_id": version_id, "job_id": job.job_id})
                wav_path = Path(job.output_dir) / "renders" / "song.wav"
                self._send_json(
                    {
                        "ok": True,
                        "version_id": version_id,
                        "job_id": job.job_id,
                        "audio_status": "completed",
                        "audio_url": f"/api/projects/{project_id}/versions/{version_id}/audio",
                        "audio": {"exists": wav_path.exists(), "size_bytes": wav_path.stat().st_size if wav_path.exists() else 0, **audio},
                    },
                    status=status,
                )
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Project version audio route not found.")

    def _handle_project_editor_preview_root(self, method: str, project_id: str, action: str) -> None:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        try:
            self.project_store.get_project(project_id)
            if action == "list":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "project_id": project_id, "previews": [preview.to_dict() for preview in store.list_previews()]})
                return
            if action == "cleanup":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = store.cleanup_previews(
                    delete_unapplied_older_than_days=int(payload.get("delete_unapplied_older_than_days", 7) or 7),
                    keep_latest=int(payload.get("keep_latest", 20) or 20),
                    now=_utc_now(),
                )
                self.project_store.append_event(project_id, "editor_previews_cleanup", result)
                self._send_json({"ok": True, **result})
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Editor preview route not found.")

    def _handle_project_editor_auditions_root(self, method: str, project_id: str, preview_id: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview = preview_store.read_preview(preview_id)
            if method == "GET":
                auditions = audition_store.list_auditions(preview_id)
                self._send_json({"ok": True, "project_id": project_id, "preview_id": preview_id, "auditions": [item.to_dict() for item in auditions]})
                return
            if method == "POST":
                payload = self._read_json_body()
                source = str(payload.get("source") or "preview").strip()
                if source not in {"preview", "parent"}:
                    self._send_error(HTTPStatus.BAD_REQUEST, "source must be parent or preview.")
                    return
                _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
                if preview.parent_job_id != parent_job.job_id:
                    self._send_error(HTTPStatus.CONFLICT, "Editor preview parent job does not match the current version.")
                    return
                if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
                    self._send_error(HTTPStatus.CONFLICT, "Editor preview is stale because the parent song-plan.json has changed.")
                    return
                if source == "parent":
                    source_plan = parent_plan
                    source_state = None
                else:
                    patch = preview_store.read_patch(preview_id)
                    result = apply_editor_patch(parent_plan, patch)
                    source_plan = result.plan
                    source_state = build_editor_view_from_result(result)
                payload = {**payload, "source": source}
                audition = audition_store.create_audition(project_id=project_id, preview=preview, source_plan=source_plan, editor_state=source_state, payload=payload, now=_utc_now())
                if bool(payload.get("render_audio", False)):
                    config, _sources = load_renderer_config()
                    config.validate_ready_for_render()
                    audition = audition_store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition.audition_id, config=config, now=_utc_now())
                self.project_store.append_event(
                    project_id,
                    "editor_audition_created",
                    {"parent_version_id": parent.version_id, "preview_id": preview_id, "audition_id": audition.audition_id, "source": audition.source},
                )
                self._send_json({"ok": True, "audition": audition.to_dict()}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor preview not found.")
        except EditorAuditionUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
        except (EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_editor_audition_route(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview_store.read_preview(preview_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "audition": audition_store.read_audition(preview_id, audition_id).to_dict()})
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.read_audition(preview_id, audition_id)
                self._send_file(audition_store.midi_path(preview_id, audition_id), "audio/midi", filename=f"{project_id}-{preview_id}-{audition_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.read_audition(preview_id, audition_id)
                self._send_file(audition_store.audio_path(preview_id, audition_id), "audio/wav", filename=f"{project_id}-{preview_id}-{audition_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                audition = audition_store.render_audition_audio(project_id=project_id, preview_id=preview_id, audition_id=audition_id, config=config, now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_audio_rendered", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "audition": audition.to_dict()})
                return
            if action == "review":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition = audition_store.update_review(preview_id, audition_id, self._read_json_body(), now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_review_updated", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "review": audition.review})
                return
            if action == "markers":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition = audition_store.add_marker(preview_id, audition_id, self._read_json_body(), now=_utc_now())
                marker = (audition.review.get("markers") or [])[-1]
                self.project_store.append_event(project_id, "editor_audition_marker_added", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker.get("marker_id")})
                self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker}, status=HTTPStatus.CREATED)
                return
            if action == "create-asset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                manifest = audition_store.read_audition(preview_id, audition_id)
                plan = audition_store.read_plan(preview_id, audition_id)
                asset_payload = audition_asset_payload(plan, manifest, self._read_json_body())
                asset = self.asset_store.create_asset(asset_payload, now=_utc_now())
                audition = audition_store.record_asset_created(preview_id, audition_id, asset.asset_id, now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_asset_created", {"preview_id": preview_id, "audition_id": audition_id, "asset_id": asset.asset_id})
                self._send_json({"ok": True, "asset": asset_public_dict(asset), "audition": audition.to_dict()}, status=HTTPStatus.CREATED)
                return
            if action == "review-task":
                self._handle_project_review_task_create(method, project_id, preview_id, audition_id)
                return
            if action in {"review-edit-preview", "review-edit", "provider-review-edit-preview", "create-context-pack"}:
                self._handle_project_editor_audition_next_action(method, project_id, preview_id, audition_id, action)
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                audition_store.delete_audition(preview_id, audition_id)
                self.project_store.append_event(project_id, "editor_audition_deleted", {"preview_id": preview_id, "audition_id": audition_id})
                self._send_json({"ok": True, "deleted": True, "audition_id": audition_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition not found.")
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
        except EditorReviewError as exc:
            status = HTTPStatus.CONFLICT if "no notes" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
        except (EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_editor_audition_next_action(self, method: str, project_id: str, preview_id: str, audition_id: str, action: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            if action == "create-context-pack":
                self._handle_audition_context_pack(project_id, preview_id, audition_id, payload)
                return
            document, parent, parent_job, parent_plan, preview, audition, audition_plan = self._review_edit_context(project_id, preview_id, audition_id)
            review_edit = build_review_edit(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_plan=parent_plan,
                audition=audition,
                audition_plan=audition_plan,
                payload=payload,
                now=_utc_now(),
            )
            result = apply_review_edit(parent_plan, review_edit)
            validator = {"status": "passed", "checks": ["review_edit_intent", "edit_intent_validation", "song_plan_validation"], "checked_at": _utc_now()}
            if action == "review-edit-preview":
                stored = ReviewEditStore(self.project_store.project_dir(project_id)).create_preview(
                    review_edit=review_edit,
                    parent_plan=parent_plan,
                    result=result,
                    validator=validator,
                    now=_utc_now(),
                )
                self.project_store.append_event(project_id, "audition_review_edit_preview_created", {"preview_id": preview_id, "audition_id": audition_id, "review_edit_id": stored.review_edit_id})
                self._send_json(
                    {
                        "ok": True,
                        "review_edit": stored.to_dict(),
                        "summary": review_edit_summary(stored, result),
                        "quality": result.plan.quality.to_dict() if result.plan.quality else {},
                        "validator": validator,
                    },
                    status=HTTPStatus.CREATED,
                )
                return
            if action == "provider-review-edit-preview":
                self._handle_provider_review_edit_preview(project_id, parent, parent_job, parent_plan, review_edit, payload)
                return
            job = self._create_review_edit_job(
                project_id=project_id,
                parent=parent,
                parent_job=parent_job,
                parent_plan=parent_plan,
                review_edit=review_edit,
                result=result,
                payload=payload,
            )
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=str(payload.get("version_name") or payload.get("name") or "Review Edit"),
                note=str(payload.get("version_note") or payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type=edit_variant_type(EditIntent.from_dict(review_edit.intents[0]).edit_type),
                change_summary=str(payload.get("change_summary") or f"Review edit from {audition.audition_id}"),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            self.project_store.append_event(project_id, "audition_review_edit_created", {"preview_id": preview_id, "audition_id": audition_id, "version_id": version.version_id, "job_id": job.job_id})
            self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "review_edit": review_edit.to_dict(), "summary": review_edit_summary(review_edit, result)}, status=HTTPStatus.ACCEPTED)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review edit resource not found.")
        except ReviewEditUnavailableError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewEditError, EditorAuditionError, EditorPatchStaleError, ValueError) as exc:
            status = HTTPStatus.CONFLICT if "stale" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _review_edit_context(self, project_id: str, preview_id: str, audition_id: str) -> tuple[Any, Any, JobState, SongPlan, Any, Any, SongPlan]:
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.get_project(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        preview = preview_store.read_preview(preview_id)
        audition = audition_store.read_audition(preview_id, audition_id)
        audition_plan = audition_store.read_plan(preview_id, audition_id)
        document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
        if preview.parent_job_id != parent_job.job_id:
            raise EditorPatchStaleError("Editor preview parent job does not match the current version.")
        if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
            raise EditorPatchStaleError("Editor preview is stale because the parent song-plan.json has changed.")
        return document, parent, parent_job, parent_plan, preview, audition, audition_plan

    def _handle_project_review_task_create(self, method: str, project_id: str, preview_id: str, audition_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._optional_json_body()
        try:
            _document, parent, _parent_job, parent_plan, preview, audition, audition_plan = self._review_edit_context(project_id, preview_id, audition_id)
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            task = task_store.create_task(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_plan=parent_plan,
                preview=preview,
                audition=audition,
                audition_plan=audition_plan,
                payload=payload,
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "review_task_created", {"task_id": task.task_id, "preview_id": preview_id, "audition_id": audition_id})
            self._send_json({"ok": True, "task": task.to_dict(), "candidates": [], "events": task_store.read_events(task.task_id)}, status=HTTPStatus.CREATED)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review task source not found.")
        except ReviewTaskStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewTaskError, EditorAuditionError, EditorPatchStaleError, ValueError) as exc:
            status = HTTPStatus.CONFLICT if "stale" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))

    def _handle_project_review_tasks_root(self, method: str, project_id: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            query = parse_qs(query_string)
            include_archived = _query_value(query, "include_archived").lower() in {"1", "true", "yes"}
            status = _query_value(query, "status") or None
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            tasks = task_store.list_tasks(include_archived=include_archived, status=status)
            self._send_json({"ok": True, "project_id": project_id, "summary": task_list_summary(tasks), "tasks": [task.to_dict() for task in tasks]})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_review_sprints_root(self, method: str, project_id: str, query_string: str) -> None:
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            task_store = ReviewTaskStore(project_dir)
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived").lower() in {"1", "true", "yes"}
                status = _query_value(query, "status") or None
                sprints = sprint_store.list_sprints(include_archived=include_archived, status=status)
                payloads = [self._review_sprint_public_payload(sprint_store, sprint) for sprint in sprints]
                self._send_json({"ok": True, "project_id": project_id, "summary": _review_sprints_list_summary(payloads), "sprints": payloads})
                return
            if method == "POST":
                payload = self._optional_json_body()
                sprint = sprint_store.create_sprint(project_id=project_id, task_store=task_store, payload=payload, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_created", {"sprint_id": sprint.sprint_id, "task_count": len(sprint.task_refs)})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint), status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except ReviewSprintStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewSprintError, ReviewTaskError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_review_sprint_route(self, method: str, project_id: str, sprint_id: str, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            task_store = ReviewTaskStore(project_dir)
            sprint = sprint_store.read_sprint(sprint_id)
            if sprint.project_id != project_id:
                raise FileNotFoundError(sprint_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint, include_events=True))
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_refreshed", {"sprint_id": sprint.sprint_id, "status": sprint.status})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "close":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                sprint = sprint_store.close_sprint(sprint, now=_utc_now())
                sprint = sprint_store.refresh_summary(sprint, task_store=task_store, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_closed", {"sprint_id": sprint.sprint_id})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = sprint_store.archive_sprint(sprint, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_archived", {"sprint_id": sprint.sprint_id})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else ([payload.get("task_id")] if payload.get("task_id") else [])
                sprint = sprint_store.add_tasks(
                    sprint,
                    task_store=task_store,
                    task_ids=[str(item) for item in task_ids],
                    lane=str(payload.get("lane") or ""),
                    notes=str(payload.get("notes") or ""),
                    now=_utc_now(),
                )
                self.project_store.append_event(project_id, "review_sprint_tasks_added", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks-remove":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else ([payload.get("task_id")] if payload.get("task_id") else [])
                for task_id in task_ids:
                    sprint = sprint_store.remove_task(sprint, str(task_id), task_store=task_store, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_tasks_removed", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks-reorder":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else []
                sprint = sprint_store.reorder_tasks(sprint, [str(item) for item in task_ids], task_store=task_store, now=_utc_now())
                self.project_store.append_event(project_id, "review_sprint_tasks_reordered", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "conflicts":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
                if not report:
                    report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes=self._review_sprint_parent_plan_hashes(project_id, task_store, sprint), now=_utc_now())
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "conflict_report": report})
                return
            if action == "conflicts-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_conflicts_refreshed", {"sprint_id": sprint.sprint_id, "conflict_count": len(report.get("conflicts", []))})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "recommendations":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                if not report:
                    report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "recommendation_report": report, "summary": recommendation_report_summary(report)})
                return
            if action == "recommendations-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, _conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_recommendations_refreshed", {"sprint_id": sprint.sprint_id, "recommended_count": len(report.get("recommended_order", []))})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "recommendation_report": report, "summary": recommendation_report_summary(report)})
                return
            if action.startswith("recommendation-context-pack:"):
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                task_id = action.split(":", 1)[1]
                payload = self._optional_json_body()
                result = self._save_review_sprint_recommendation_context_pack(project_id, sprint_store, task_store, sprint, task_id, payload)
                self._send_json(result, status=HTTPStatus.CREATED)
                return
            if action == "generate-local-candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = self._generate_review_sprint_local_candidates(project_id, sprint_store, task_store, sprint, payload)
                self._send_json(result, status=HTTPStatus.ACCEPTED)
                return
            if action == "generate-provider-candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._expand_context_pack_payload(self._optional_json_body())
                result = self._generate_review_sprint_provider_candidates(project_id, sprint_store, task_store, sprint, payload)
                self._send_json(result, status=HTTPStatus.ACCEPTED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Review sprint route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review sprint not found.")
        except (ReviewSprintStateError, ReviewTaskStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (ReviewSprintError, ReviewTaskError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _review_sprint_response(
        self,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        *,
        include_events: bool = False,
    ) -> dict[str, Any]:
        summary = sprint_store.read_summary(sprint.sprint_id, default={})
        conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        response = {
            "ok": True,
            "sprint": sprint.to_dict(),
            "summary": summary,
            "conflict_report": conflict_report,
            "recommendation_report": recommendation_report,
            "recommendation_summary": recommendation_report_summary(recommendation_report),
            "export_summary": review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report),
            "tasks": self._review_sprint_task_items(task_store, sprint),
        }
        if include_events:
            response["events"] = sprint_store.read_events(sprint.sprint_id)
        return response

    def _review_sprint_public_payload(self, sprint_store: ReviewSprintStore, sprint: Any) -> dict[str, Any]:
        summary = sprint_store.read_summary(sprint.sprint_id, default={})
        conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
        recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        return {
            **sprint.to_dict(),
            "summary": summary,
            "conflict_report": conflict_report,
            "recommendation_report": recommendation_report,
            "recommendation_summary": recommendation_report_summary(recommendation_report),
            "export_summary": review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report),
        }

    def _review_sprint_task_items(self, task_store: ReviewTaskStore, sprint: Any) -> list[dict[str, Any]]:
        items = []
        for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
            if not ref.get("included", True):
                continue
            task_id = str(ref.get("task_id") or "")
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                decision_report = _try_read_review_decision_report(task_store, task.task_id)
                items.append(
                    {
                        "ref": ref,
                        "task": task.to_dict(),
                        "candidates": [candidate.to_dict() for candidate in candidates],
                        "decision_report": decision_report,
                        "provider_summary": review_candidate_source_breakdown(candidates),
                    }
                )
            except FileNotFoundError:
                items.append({"ref": ref, "task_id": task_id, "missing": True})
        return items

    def _refresh_review_sprint_state(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any) -> tuple[Any, dict[str, Any]]:
        parent_hashes = self._review_sprint_parent_plan_hashes(project_id, task_store, sprint)
        report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes=parent_hashes, now=_utc_now())
        sprint = sprint_store.refresh_summary(sprint, task_store=task_store, now=_utc_now())
        return sprint, report

    def _refresh_review_sprint_recommendations(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any) -> dict[str, Any]:
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        report = build_review_sprint_recommendation_report(
            project_id=project_id,
            sprint=sprint,
            task_store=task_store,
            sprint_store=sprint_store,
            library_index=index,
            project_document=project_document,
            now=_utc_now(),
        )
        return sprint_store.write_recommendation_report(sprint, report, now=report.get("created_at") or _utc_now())

    def _save_review_sprint_recommendation_context_pack(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task_id not in self._review_sprint_ordered_task_ids(sprint):
            raise FileNotFoundError(task_id)
        task = task_store.read_task(task_id)
        if task.project_id != project_id:
            raise FileNotFoundError(task_id)
        report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        if not report:
            report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
        action = _recommendation_action_for_task(report, task_id)
        if not action:
            raise ReviewSprintStateError("Recommendation for task is missing.")
        preview = action.get("context_pack_preview") if isinstance(action.get("context_pack_preview"), dict) else {}
        asset_refs = preview.get("asset_refs") if isinstance(preview.get("asset_refs"), list) else []
        reference_refs = preview.get("reference_refs") if isinstance(preview.get("reference_refs"), list) else []
        if not asset_refs and not reference_refs:
            raise ReviewSprintStateError("Recommendation has no context refs to save.")
        self._ensure_recommendation_context_refs_current(asset_refs, reference_refs)
        pack_payload = {
            "name": str(payload.get("name") or f"{sprint.name} {task_id} Context Pack")[:160],
            "description": str(payload.get("description") or f"Saved from Review Sprint recommendation {sprint.sprint_id} for {task_id}.")[:1000],
            "created_from": {
                "source_type": "review_sprint_recommendation",
                "project_id": project_id,
                "sprint_id": sprint.sprint_id,
                "task_id": task_id,
                "recommendation_created_at": report.get("created_at"),
                "recommendation_rank": action.get("rank"),
                "recommended_action": action.get("action"),
            },
            "query": preview.get("query") if isinstance(preview.get("query"), dict) else {},
            "asset_refs": asset_refs,
            "reference_refs": reference_refs,
            "selection": {
                "mode": "recommendation",
                "selected_by": str(payload.get("selected_by") or "user")[:80],
                "score_summary": action.get("score_breakdown") if isinstance(action.get("score_breakdown"), dict) else {},
            },
        }
        pack = self.context_pack_store.create_pack(pack_payload, asset_store=self.asset_store, reference_store=self.reference_store, now=_utc_now())
        self.project_store.append_event(project_id, "review_sprint_recommendation_context_pack_saved", {"sprint_id": sprint.sprint_id, "task_id": task_id, "pack_id": pack.pack_id})
        return {"ok": True, "context_pack": context_pack_public_dict(pack), "recommendation": action}

    def _ensure_recommendation_context_refs_current(self, asset_refs: list[dict[str, Any]], reference_refs: list[dict[str, Any]]) -> None:
        for ref in asset_refs:
            asset = self.asset_store.read_asset(str(ref.get("asset_id") or ""))
            if asset.hidden or str(ref.get("source_hash") or "") != asset_source_hash(asset):
                raise ReviewSprintStateError("Recommendation context asset is stale. Refresh recommendations before saving.")
        for ref in reference_refs:
            reference = self.reference_store.read_reference(str(ref.get("reference_id") or ""))
            if reference.hidden or str(ref.get("source_hash") or "") != reference.sha256:
                raise ReviewSprintStateError("Recommendation context reference is stale. Refresh recommendations before saving.")

    def _review_sprint_parent_plan_hashes(self, project_id: str, task_store: ReviewTaskStore, sprint: Any) -> dict[str, str]:
        hashes: dict[str, str] = {}
        version_ids = []
        for ref in sprint.task_refs:
            if not ref.get("included", True):
                continue
            try:
                task = task_store.read_task(str(ref.get("task_id") or ""))
            except FileNotFoundError:
                continue
            if task.project_id == project_id and task.parent_version_id not in version_ids:
                version_ids.append(task.parent_version_id)
        for version_id in version_ids:
            try:
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            except FileNotFoundError:
                continue
            hashes[version_id] = song_plan_hash(parent_plan)
        return hashes

    def _review_sprint_ordered_task_ids(self, sprint: Any) -> list[str]:
        task_ids = []
        for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
            if ref.get("included", True) and ref.get("task_id"):
                task_ids.append(str(ref.get("task_id")))
        return task_ids

    def _review_sprint_membership_summary(self, project_id: str, task_id: str) -> dict[str, Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                refs = [ref for ref in sprint.task_refs if ref.get("included", True)]
                if task_id not in {str(ref.get("task_id") or "") for ref in refs}:
                    continue
                summary = sprint_store.read_summary(sprint.sprint_id, default={})
                conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
                recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                matches.append(review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report))
            if not matches:
                return {}
            return sanitize_metadata({"sprint_ids": [item["sprint_id"] for item in matches], "primary": matches[0], "sprints": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
            return {}

    def _review_sprint_recommendation_summary_for_task(self, project_id: str, task_id: str) -> dict[str, Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                if task_id not in self._review_sprint_ordered_task_ids(sprint):
                    continue
                report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                action = _recommendation_action_for_task(report, task_id)
                if action:
                    matches.append(
                        {
                            "sprint_id": sprint.sprint_id,
                            "task_id": task_id,
                            "report_created_at": report.get("created_at"),
                            "rank": action.get("rank"),
                            "action": action.get("action"),
                            "score": action.get("score"),
                            "reason": action.get("reason"),
                            "context_ref_count": _context_ref_count(action.get("context_pack_preview")),
                        }
                    )
            if not matches:
                return {}
            return sanitize_metadata({"primary": matches[0], "recommendations": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, json.JSONDecodeError):
            return {}

    def _generate_review_sprint_local_candidates(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if sprint.status not in {"open", "in_progress", "blocked"}:
            raise ReviewSprintStateError(f"Cannot generate candidates for a {sprint.status} review sprint.")
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        stop_on_conflict = bool(payload.get("stop_on_conflict", sprint.settings.get("stop_on_conflict", False)))
        if stop_on_conflict and any(item.get("severity") == "blocking" for item in conflict_report.get("conflicts", [])):
            raise ReviewSprintStateError("Review sprint has blocking conflicts.")
        strategies = payload.get("strategies") if isinstance(payload.get("strategies"), list) else sprint.settings.get("local_candidate_strategies")
        render_midi = bool(payload.get("render_midi", sprint.settings.get("render_midi", True)))
        skip_existing = bool(payload.get("skip_existing_ready", True))
        results = []
        created_total = 0
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                if skip_existing and any(candidate.candidate_type == "local_review_intents" and candidate.status in {"ready", "applied"} for candidate in candidates):
                    results.append({"task_id": task.task_id, "status": "skipped", "reason": "ready local candidate exists"})
                    continue
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                generated = []
                for candidate, candidate_plan, validator, summary in build_local_review_candidates(task, parent_plan, strategies=strategies):
                    stored = task_store.create_candidate(
                        task=task,
                        candidate=candidate,
                        candidate_plan=candidate_plan,
                        validator=validator,
                        summary=summary,
                        render_midi_file=render_midi,
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now()), now=_utc_now())
                created_total += len(generated)
                results.append(
                    {
                        "task_id": task.task_id,
                        "status": "generated" if generated else "skipped",
                        "created_count": len(generated),
                        "created_candidate_ids": [candidate.candidate_id for candidate in generated],
                        "decision_report": review_decision_summary(decision_report),
                        "provider_summary": review_candidate_source_breakdown(ranked),
                    }
                )
            except (FileNotFoundError, ReviewTaskError, ReviewTaskStateError, ValueError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        self.project_store.append_event(project_id, "review_sprint_local_candidates_generated", {"sprint_id": sprint.sprint_id, "created_count": created_total})
        response = self._review_sprint_response(sprint_store, task_store, sprint)
        response.update({"results": sanitize_metadata(results), "created_count": created_total})
        return response

    def _generate_review_sprint_provider_candidates(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, payload: dict[str, Any]) -> dict[str, Any]:
        if sprint.status not in {"open", "in_progress", "blocked"}:
            raise ReviewSprintStateError(f"Cannot generate provider candidates for a {sprint.status} review sprint.")
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        stop_on_conflict = bool(payload.get("stop_on_conflict", sprint.settings.get("stop_on_conflict", False)))
        if stop_on_conflict and any(item.get("severity") == "blocking" for item in conflict_report.get("conflicts", [])):
            raise ReviewSprintStateError("Review sprint has blocking conflicts.")
        template_id = str(payload.get("template_id") or sprint.settings.get("provider_template_id") or "provider-review-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise ReviewSprintStateError("Prompt template is disabled.")
        candidate_count = max(1, min(5, int(payload.get("candidate_count") or sprint.settings.get("provider_candidate_count") or 2)))
        render_midi = bool(payload.get("render_midi", sprint.settings.get("render_midi", True)))
        skip_existing = bool(payload.get("skip_existing_provider", True))
        include_local_context = bool(payload.get("include_local_context", True))
        config, _sources = load_provider_config()
        asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
        asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
        reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
        results = []
        created_total = 0
        provider_snapshots = []
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                if skip_existing and any((candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")) and candidate.status in {"ready", "applied"} for candidate in candidates):
                    results.append({"task_id": task.task_id, "status": "skipped", "reason": "ready provider candidate exists"})
                    continue
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                local_context = candidates if include_local_context else []
                generated_specs, provider_snapshot, instruction = build_provider_review_candidates(
                    task=task,
                    parent_plan=parent_plan,
                    template=template,
                    config=config,
                    candidate_count=candidate_count,
                    local_candidates=local_context,
                    asset_references=asset_prompt_refs,
                    reference_references=reference_prompt_refs,
                )
                generated = []
                for candidate, candidate_plan, validator, summary in generated_specs:
                    stored = task_store.create_candidate(
                        task=task,
                        candidate=candidate,
                        candidate_plan=candidate_plan,
                        validator=validator,
                        summary=summary,
                        render_midi_file=render_midi,
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
                usage_record = _provider_usage_record(
                    config_snapshot=provider_snapshot,
                    operation="review_sprint_provider_candidates",
                    template_id=template.template_id,
                    started_at=_utc_now(),
                    status="completed",
                    provider_usage=provider_usage,
                    request_id=provider_snapshot.get("request_id"),
                )
                write_json(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("decision_note") or "")), now=_utc_now())
                created_total += len(generated)
                provider_snapshots.append(provider_snapshot)
                results.append(
                    {
                        "task_id": task.task_id,
                        "status": "generated" if generated else "skipped",
                        "created_count": len(generated),
                        "created_candidate_ids": [candidate.candidate_id for candidate in generated],
                        "instruction": instruction,
                        "decision_report": review_decision_summary(decision_report),
                        "provider_summary": review_candidate_source_breakdown(ranked),
                        "provider_snapshot": provider_snapshot,
                    }
                )
            except (FileNotFoundError, ReviewTaskError, ReviewTaskStateError, ProviderError, ValueError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        if asset_snapshot["asset_refs"]:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "review_sprint_provider_candidates", "project_id": project_id, "review_sprint_id": sprint.sprint_id})
        if reference_snapshot["reference_refs"]:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "review_sprint_provider_candidates", "project_id": project_id, "review_sprint_id": sprint.sprint_id})
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        self.project_store.append_event(project_id, "review_sprint_provider_candidates_generated", {"sprint_id": sprint.sprint_id, "created_count": created_total, "template_id": template.template_id})
        response = self._review_sprint_response(sprint_store, task_store, sprint)
        response.update({"results": sanitize_metadata(results), "created_count": created_total, "provider_snapshots": sanitize_metadata(provider_snapshots)})
        return response

    def _handle_project_review_task_route(self, method: str, project_id: str, task_id: str, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            task = task_store.read_task(task_id)
            if task.project_id != project_id:
                raise FileNotFoundError(task_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidates = task_store.list_candidates(task.task_id)
                decision_report = _try_read_review_decision_report(task_store, task.task_id)
                self._send_json({"ok": True, "task": task.to_dict(), "candidates": [candidate.to_dict() for candidate in candidates], "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(candidates), "events": task_store.read_events(task.task_id)})
                return
            if action == "candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                _document, parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                strategies = payload.get("strategies") if isinstance(payload.get("strategies"), list) else None
                generated = []
                for candidate, candidate_plan, validator, summary in build_local_review_candidates(task, parent_plan, strategies=strategies):
                    stored = task_store.create_candidate(
                        task=task,
                        candidate=candidate,
                        candidate_plan=candidate_plan,
                        validator=validator,
                        summary=summary,
                        render_midi_file=bool(payload.get("render_midi", True)),
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now()), now=_utc_now())
                self.project_store.append_event(project_id, "review_task_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated)})
                self._send_json({"ok": True, "task": task.to_dict(), "candidates": [candidate.to_dict() for candidate in ranked], "created": [candidate.to_dict() for candidate in generated], "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(ranked)}, status=HTTPStatus.CREATED)
                return
            if action == "provider-candidates":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                payload = self._expand_context_pack_payload(payload)
                _document, parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                template_id = str(payload.get("template_id") or "provider-review-candidates").strip()
                template = self.prompt_template_store.get_template(template_id)
                if not template.enabled:
                    self._send_error(HTTPStatus.CONFLICT, "Prompt template is disabled.")
                    return
                candidate_count = int(payload.get("candidate_count") or 3)
                config, _sources = load_provider_config()
                asset_snapshot = asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_utc_now())
                asset_prompt_refs = asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
                reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
                reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
                local_context = task_store.list_candidates(task.task_id) if bool(payload.get("include_local_context", True)) else []
                generated_specs, provider_snapshot, instruction = build_provider_review_candidates(
                    task=task,
                    parent_plan=parent_plan,
                    template=template,
                    config=config,
                    candidate_count=candidate_count,
                    local_candidates=local_context,
                    asset_references=asset_prompt_refs,
                    reference_references=reference_prompt_refs,
                )
                generated = []
                for candidate, candidate_plan, validator, summary in generated_specs:
                    stored = task_store.create_candidate(
                        task=task,
                        candidate=candidate,
                        candidate_plan=candidate_plan,
                        validator=validator,
                        summary=summary,
                        render_midi_file=bool(payload.get("render_midi", True)),
                        now=_utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_utc_now())
                provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
                usage_record = _provider_usage_record(
                    config_snapshot=provider_snapshot,
                    operation="provider_review_candidates",
                    template_id=template.template_id,
                    started_at=_utc_now(),
                    status="completed",
                    provider_usage=provider_usage,
                    request_id=provider_snapshot.get("request_id"),
                )
                write_json(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("decision_note") or "")), now=_utc_now())
                if asset_snapshot["asset_refs"]:
                    self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "review_task_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
                if reference_snapshot["reference_refs"]:
                    self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "review_task_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
                self.project_store.append_event(project_id, "review_task_provider_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated), "template_id": template.template_id})
                self._send_json({"ok": True, "task": task.to_dict(), "candidates": [candidate.to_dict() for candidate in ranked], "created": [candidate.to_dict() for candidate in generated], "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(ranked), "provider_snapshot": provider_snapshot, "instruction": instruction}, status=HTTPStatus.CREATED)
                return
            if action == "decision-report":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidates = task_store.rank_candidates(task)
                decision_report = _try_read_review_decision_report(task_store, task.task_id)
                if not decision_report:
                    _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                    decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=candidates, parent_plan=parent_plan, now=_utc_now()), now=_utc_now())
                self._send_json({"ok": True, "task": task.to_dict(), "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(candidates)})
                return
            if action == "decision-report-refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                ensure_task_current(task, parent_plan)
                candidates = task_store.rank_candidates(task)
                decision_report = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=candidates, parent_plan=parent_plan, now=_utc_now(), notes=str(payload.get("note") or "")), now=_utc_now())
                self.project_store.append_event(project_id, "review_task_decision_report_refreshed", {"task_id": task.task_id, "recommended_candidate_id": decision_report.get("recommended_candidate_id")})
                self._send_json({"ok": True, "task": task.to_dict(), "decision_report": decision_report, "provider_summary": review_candidate_source_breakdown(candidates)})
                return
            if action == "resolve":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task = task_store.update_task(mark_task_resolved(task, str(payload.get("note") or ""), now=_utc_now()), event="review_task_resolved", payload={"note": payload.get("note") or ""}, now=_utc_now())
                self.project_store.append_event(project_id, "review_task_resolved", {"task_id": task.task_id, "candidate_id": task.selected_candidate_id, "version_id": task.applied_version_id})
                self._send_json({"ok": True, "task": task.to_dict()})
                return
            if action == "needs-more-work":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task, follow_up = self._create_review_task_follow_up(project_id, task_store, task, payload)
                self._send_json({"ok": True, "task": task.to_dict(), "follow_up_task": follow_up.to_dict()}, status=HTTPStatus.CREATED)
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                task = task_store.update_task(mark_task_archived(task), event="review_task_archived", payload={}, now=_utc_now())
                self.project_store.append_event(project_id, "review_task_archived", {"task_id": task.task_id})
                self._send_json({"ok": True, "task": task.to_dict()})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Review task route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review task not found.")
        except ReviewTaskStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ProviderError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (ReviewTaskError, EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_review_task_candidate_route(self, method: str, project_id: str, task_id: str, candidate_id: str, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
            task_store = ReviewTaskStore(self.project_store.project_dir(project_id))
            task = task_store.read_task(task_id)
            candidate = task_store.read_candidate(task_id, candidate_id)
            if task.project_id != project_id or candidate.project_id != project_id:
                raise FileNotFoundError(candidate_id)
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
            ensure_candidate_current(task, candidate, parent_plan)
            if action == "render-midi":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidate = task_store.render_candidate_midi(task, candidate, now=_utc_now())
                self._send_json({"ok": True, "task": task_store.read_task(task.task_id).to_dict(), "candidate": candidate.to_dict()})
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config, _sources = load_renderer_config()
                config.validate_ready_for_render()
                candidate = task_store.render_candidate_audio(task, candidate, config, now=_utc_now())
                self._send_json({"ok": True, "task": task_store.read_task(task.task_id).to_dict(), "candidate": candidate.to_dict()})
                return
            if action in {"midi", "audio"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                path = task_store.candidate_midi_path(task_id, candidate_id) if action == "midi" else task_store.candidate_audio_path(task_id, candidate_id)
                if not path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Review candidate artifact not found.")
                    return
                self._send_file(path, "audio/midi" if action == "midi" else "audio/wav", filename=f"{project_id}-{task_id}-{candidate_id}.{ 'mid' if action == 'midi' else 'wav' }")
                return
            if action == "apply":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task, candidate, version, job, result = self._apply_review_task_candidate(project_id, task_store, task, candidate, parent, parent_job, parent_plan, payload)
                self._send_json({"ok": True, "task": task.to_dict(), "candidate": candidate.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "summary": result.summary}, status=HTTPStatus.ACCEPTED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Review candidate route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Review candidate not found.")
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReviewTaskStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (ReviewTaskError, ValueError) as exc:
            status = HTTPStatus.CONFLICT if "unsafe" in str(exc).lower() or "stale" in str(exc).lower() else HTTPStatus.BAD_REQUEST
            self._send_error(status, str(exc))

    def _apply_review_task_candidate(
        self,
        project_id: str,
        task_store: ReviewTaskStore,
        task: Any,
        candidate: Any,
        parent: Any,
        parent_job: JobState,
        parent_plan: SongPlan,
        payload: dict[str, Any],
    ) -> tuple[Any, Any, Any, JobState, Any]:
        _ensure_task_open_for_apply(task)
        if candidate.status != "ready":
            raise ReviewTaskStateError("Candidate is not ready.")
        result = apply_candidate_intents(parent_plan, [EditIntent.from_dict(item) for item in candidate.intents])
        primary = EditIntent.from_dict(candidate.intents[0])
        name = str(payload.get("name") or payload.get("version_name") or f"Review Candidate {candidate.candidate_id}")
        job = self.store.create_edit_job(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_job=parent_job,
            parent_plan=parent_plan,
            intent=primary,
            name=name,
            start_immediately=False,
            asset_refs=payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else None,
            reference_refs=payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else None,
            context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
        )
        decision_report = _try_read_review_decision_report(task_store, task.task_id)
        metadata = {
            **job.edit_metadata,
            **candidate_apply_metadata(task, candidate, result, decision_report=decision_report),
            "edit_type": primary.edit_type,
            "target": primary.target.to_dict(),
            "instruction": primary.instruction,
            "preserve": list(primary.preserve),
            "strength": primary.strength,
        }
        sprint_membership = self._review_sprint_membership_summary(project_id, task.task_id)
        if sprint_membership:
            metadata["review_sprint"] = sprint_membership
        sprint_recommendation = self._review_sprint_recommendation_summary_for_task(project_id, task.task_id)
        if sprint_recommendation:
            metadata["review_sprint_recommendation"] = sprint_recommendation
        job.edit_metadata = metadata
        job.input_payload["review_task_id"] = task.task_id
        job.input_payload["review_candidate_id"] = candidate.candidate_id
        job.input_payload["review_task"] = review_task_summary(task, candidate)
        job.input_payload["review_candidate"] = review_candidate_summary(candidate)
        if decision_report:
            job.input_payload["review_decision"] = review_decision_summary(decision_report)
        if sprint_membership:
            job.input_payload["review_sprint"] = sprint_membership
        if sprint_recommendation:
            job.input_payload["review_sprint_recommendation"] = sprint_recommendation
        self.store._write_job(job)
        write_json(ProjectPaths.create(Path(job.output_dir)).data / "edit-metadata.json", metadata)
        self.store.start_job(job.job_id)
        document = self.project_store.add_version_from_job(
            project_id,
            job,
            name=name,
            note=str(payload.get("note") or payload.get("version_note") or ""),
            parent_version_id=parent.version_id,
            variant_type=edit_variant_type(primary.edit_type),
            change_summary=str(payload.get("change_summary") or f"Review task {task.task_id} candidate {candidate.candidate_id}"),
        )
        version = next(version for version in document.versions if version.job_id == job.job_id)
        candidate = task_store.update_candidate(
            type(candidate).from_dict({**candidate.to_dict(), "status": "applied"}),
            event="review_candidate_applied",
            payload={"version_id": version.version_id, "job_id": job.job_id},
            now=_utc_now(),
        )
        task = task_store.update_task(
            type(task).from_dict(
                {
                    **task.to_dict(),
                    "status": "applied",
                    "selected_candidate_id": candidate.candidate_id,
                    "applied_version_id": version.version_id,
                    "applied_job_id": job.job_id,
                }
            ),
            event="review_task_candidate_applied",
            payload={"candidate_id": candidate.candidate_id, "version_id": version.version_id, "job_id": job.job_id},
            now=_utc_now(),
        )
        self.project_store.append_event(project_id, "review_task_candidate_applied", {"task_id": task.task_id, "candidate_id": candidate.candidate_id, "version_id": version.version_id, "job_id": job.job_id})
        return task, candidate, version, job, result

    def _create_review_task_follow_up(self, project_id: str, task_store: ReviewTaskStore, task: Any, payload: dict[str, Any]) -> tuple[Any, Any]:
        if task.status != "applied" or not task.applied_version_id:
            raise ReviewTaskStateError("Only applied review tasks can be marked needs_more_work.")
        candidate = task_store.read_candidate(task.task_id, task.selected_candidate_id or "")
        _document, parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.applied_version_id)
        preview = EditorPreviewStore(self.project_store.project_dir(project_id)).read_preview(task.preview_id)
        audition_store = EditorAuditionStore(self.project_store.project_dir(project_id))
        audition = audition_store.read_audition(task.preview_id, task.audition_id)
        audition_plan = audition_store.read_plan(task.preview_id, task.audition_id)
        follow_up = task_store.create_task(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_plan=parent_plan,
            preview=preview,
            audition=audition,
            audition_plan=audition_plan,
            payload={
                "title": payload.get("title") or f"Follow-up for {task.task_id}",
            },
            previous={
                "previous_task_id": task.task_id,
                "previous_candidate_id": candidate.candidate_id,
                "previous_applied_version_id": task.applied_version_id,
            },
            now=_utc_now(),
        )
        task = task_store.update_task(
            type(task).from_dict({**task.to_dict(), "status": "needs_more_work", "follow_up_task_id": follow_up.task_id, "resolution_note": str(payload.get("note") or "")}),
            event="review_task_needs_more_work",
            payload={"follow_up_task_id": follow_up.task_id, "note": payload.get("note") or ""},
            now=_utc_now(),
        )
        self.project_store.append_event(project_id, "review_task_needs_more_work", {"task_id": task.task_id, "follow_up_task_id": follow_up.task_id, "version_id": task.applied_version_id})
        return task, follow_up

    def _create_review_edit_job(
        self,
        *,
        project_id: str,
        parent: Any,
        parent_job: JobState,
        parent_plan: SongPlan,
        review_edit: Any,
        result: Any,
        payload: dict[str, Any],
    ) -> JobState:
        primary_intent = EditIntent.from_dict(review_edit.intents[0])
        job = self.store.create_edit_job(
            project_id=project_id,
            parent_version_id=parent.version_id,
            parent_job=parent_job,
            parent_plan=parent_plan,
            intent=primary_intent,
            name=str(payload.get("version_name") or payload.get("name") or "Review Edit"),
            start_immediately=False,
            asset_refs=payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else None,
            reference_refs=payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else None,
            context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
        )
        metadata = {
            **job.edit_metadata,
            **review_edit_metadata(review_edit, result),
            "edit_type": primary_intent.edit_type,
            "target": primary_intent.target.to_dict(),
            "instruction": primary_intent.instruction,
            "preserve": list(primary_intent.preserve),
            "strength": primary_intent.strength,
        }
        job.edit_metadata = metadata
        job.input_payload["review_edit_id"] = review_edit.review_edit_id
        job.input_payload["review_edit"] = review_edit_summary(review_edit, result)
        self.store._write_job(job)
        write_json(ProjectPaths.create(Path(job.output_dir)).data / "edit-metadata.json", metadata)
        self.store.start_job(job.job_id)
        return job

    def _handle_provider_review_edit_preview(self, project_id: str, parent: Any, parent_job: JobState, parent_plan: SongPlan, review_edit: Any, payload: dict[str, Any]) -> None:
        template_id = str(payload.get("template_id") or "provider-review-edit-intent").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            self._send_error(HTTPStatus.CONFLICT, "Prompt template is disabled.")
            return
        config, _sources = load_provider_config()
        instruction = review_edit_instruction_for_provider(review_edit)
        patch, provider_snapshot = generate_provider_edit_patch(
            parent_plan=parent_plan,
            instruction=instruction,
            template=template,
            config=config,
            asset_references=[],
            reference_references=[],
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
        )
        preview_dir = self.project_store.project_dir(project_id) / "edit-previews" / preview.preview_id
        data = preview.to_dict()
        data["source"] = {**data.get("source", {}), "review_edit": review_edit.to_dict()}
        write_json(preview_dir / "preview.json", data)
        usage = _provider_usage_record(
            config_snapshot=provider_snapshot,
            operation="provider_review_edit_preview",
            template_id=template.template_id,
            started_at=preview.created_at,
            status="completed",
            provider_usage=provider_usage,
            request_id=provider_snapshot.get("request_id"),
        )
        write_json(preview_dir / "provider-usage.json", usage)
        self.project_store.append_event(project_id, "provider_review_edit_preview_created", {"parent_version_id": parent.version_id, "preview_id": preview.preview_id, "template_id": template.template_id})
        self._send_json({"ok": True, "preview": read_provider_edit_preview(self.project_store.project_dir(project_id), preview.preview_id).to_dict(), "patch": patch.to_dict(), "review_edit": review_edit.to_dict()}, status=HTTPStatus.CREATED)

    def _handle_audition_context_pack(self, project_id: str, preview_id: str, audition_id: str, payload: dict[str, Any]) -> None:
        project_dir = self.project_store.project_dir(project_id)
        self.project_store.get_project(project_id)
        audition = EditorAuditionStore(project_dir).read_audition(preview_id, audition_id)
        review = audition.review if isinstance(audition.review, dict) else {}
        asset_id = str(payload.get("asset_id") or review.get("last_asset_id") or "").strip()
        if not asset_id:
            raise ReviewEditUnavailableError("No audition asset is available for context pack creation.")
        pack = self.context_pack_store.create_pack(
            {
                "name": payload.get("name") or f"Context from {audition_id}",
                "description": payload.get("description") or "Created from audition review.",
                "created_from": {
                    "source_type": "audition_review",
                    "project_id": project_id,
                    "preview_id": preview_id,
                    "audition_id": audition_id,
                    "rating": review.get("rating", 0),
                    "status": review.get("status", "unreviewed"),
                },
                "asset_refs": [{"asset_id": asset_id, "role": "audition_review_favorite", "strength": 0.9}],
                "selection": {
                    "mode": "audition_review",
                    "selected_by": "user",
                    "score_summary": [{"asset_id": asset_id, "rating": review.get("rating", 0), "favorite": bool(review.get("favorite", False))}],
                },
            },
            asset_store=self.asset_store,
            reference_store=self.reference_store,
            now=_utc_now(),
        )
        self.project_store.append_event(project_id, "audition_review_context_pack_created", {"preview_id": preview_id, "audition_id": audition_id, "pack_id": pack.pack_id, "asset_id": asset_id})
        self._send_json({"ok": True, "context_pack": context_pack_public_dict(pack)}, status=HTTPStatus.CREATED)

    def _handle_project_editor_audition_marker_route(self, method: str, project_id: str, preview_id: str, audition_id: str, marker_id: str, action: str) -> None:
        project_dir = self.project_store.project_dir(project_id)
        preview_store = EditorPreviewStore(project_dir)
        audition_store = EditorAuditionStore(project_dir)
        try:
            self.project_store.get_project(project_id)
            preview_store.read_preview(preview_id)
            audition_store.read_audition(preview_id, audition_id)
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action == "update":
                audition = audition_store.update_marker(preview_id, audition_id, marker_id, self._read_json_body(), now=_utc_now())
                marker = next((item for item in audition.review.get("markers", []) if item.get("marker_id") == marker_id), None)
                self.project_store.append_event(project_id, "editor_audition_marker_updated", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "marker": marker})
                return
            if action == "delete":
                audition = audition_store.delete_marker(preview_id, audition_id, marker_id, now=_utc_now())
                self.project_store.append_event(project_id, "editor_audition_marker_deleted", {"preview_id": preview_id, "audition_id": audition_id, "marker_id": marker_id})
                self._send_json({"ok": True, "audition": audition.to_dict(), "deleted": True, "marker_id": marker_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition marker route not found.")
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor audition marker not found.")
        except (EditorReviewError, EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_audition_reviews(self, method: str, project_id: str, preview_id: str | None, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            if preview_id is not None:
                EditorPreviewStore(self.project_store.project_dir(project_id)).read_preview(preview_id)
            query = parse_qs(query_string)
            filters = {
                key: _query_value(query, key)
                for key in ("source", "status", "favorite", "min_rating", "track_mode", "range_mode", "sort", "order", "limit")
                if _query_value(query, key)
            }
            board = EditorAuditionStore(self.project_store.project_dir(project_id)).review_board(preview_id=preview_id, filters=filters)
            self._send_json({"ok": True, "project_id": project_id, "preview_id": preview_id, **board})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project or editor preview not found.")
        except (EditorReviewError, EditorAuditionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_editor_preview_route(self, method: str, project_id: str, preview_id: str, action: str) -> None:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        try:
            self.project_store.get_project(project_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preview = store.read_preview(preview_id)
                self._send_json({"ok": True, "preview": preview.to_dict()})
                return
            if action == "patch":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                include_operations = "include_operations=true" in self.path or "include_operations=1" in self.path
                self._send_json({"ok": True, "patch": store.read_patch_summary(preview_id, include_operations=include_operations)})
                return
            if action == "song-plan":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "song_plan": store.read_plan(preview_id).to_dict()})
                return
            if action == "midi":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.read_preview(preview_id)
                self._send_file(store.preview_dir(preview_id) / "song.mid", "audio/midi", filename=f"{project_id}-{preview_id}.mid")
                return
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.read_preview(preview_id)
                audio_path = store.preview_dir(preview_id) / "song.wav"
                if not audio_path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Preview audio render is not available.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{preview_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "preview": self._render_editor_preview_audio(project_id, preview_id).to_dict()})
                return
            if action == "delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                store.delete_preview(preview_id)
                self.project_store.append_event(project_id, "editor_preview_deleted", {"preview_id": preview_id})
                self._send_json({"ok": True, "deleted": True, "preview_id": preview_id})
                return
            if action == "apply":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                self._handle_project_editor_preview_apply(project_id, preview_id, payload)
                return
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Editor preview not found.")
            return
        except EditorPatchStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
        except RendererError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."))
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Editor preview route not found.")

    def _render_editor_preview_audio(self, project_id: str, preview_id: str) -> Any:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        preview = store.read_preview(preview_id)
        preview_dir = store.preview_dir(preview_id)
        midi_path = preview_dir / "song.mid"
        try:
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
        except FileNotFoundError as exc:
            raise FileNotFoundError("Parent version not found.") from exc
        if preview.parent_job_id != parent_job.job_id:
            raise EditorPatchStaleError("Editor preview parent job does not match the current version.")
        if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
            raise EditorPatchStaleError("Editor preview is stale because the parent song-plan.json has changed.")
        patch = store.read_patch(preview_id)
        result = apply_editor_patch(parent_plan, patch)
        result.plan.validate()
        write_json(preview_dir / "song-plan.json", result.plan.to_dict())
        render_midi(result.plan, midi_path)
        report_path = preview_dir / "validator-report.json"
        report = read_json(report_path) if report_path.exists() else {}
        report.update(_build_validator_report(preview_dir / "song-plan.json", midi_path))
        try:
            config, _sources = load_renderer_config()
            config.validate_ready_for_render()
            wav_path = render_audio(midi_path, preview_dir / "song.wav", config)
        except RendererError as exc:
            updated = store.update_preview_audio(
                preview_id,
                status="failed",
                audio_error=str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."),
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "editor_preview_audio_failed", {"preview_id": preview_id, "error": updated.audio_error})
            raise
        updated = store.update_preview_audio(
            preview_id,
            status="completed",
            audio_url=f"/api/projects/{project_id}/editor-previews/{preview_id}/audio",
            audio_size_bytes=wav_path.stat().st_size,
            now=_utc_now(),
        )
        report["audio"] = _audio_report(wav_path)
        write_json(report_path, report)
        self.project_store.append_event(project_id, "editor_preview_audio_rendered", {"preview_id": preview_id, "size_bytes": wav_path.stat().st_size})
        return updated

    def _handle_project_editor_preview_apply(self, project_id: str, preview_id: str, payload: dict[str, Any]) -> None:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        with self.project_store.lock, store.lock:
            preview = store.read_preview(preview_id)
            if preview.applied_version_id:
                self._send_error(HTTPStatus.CONFLICT, "Editor preview has already been applied.")
                return
            try:
                document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
            except FileNotFoundError:
                self._send_error(HTTPStatus.NOT_FOUND, "Parent version not found.")
                return
            if preview.parent_job_id != parent_job.job_id:
                self._send_error(HTTPStatus.CONFLICT, "Editor preview parent job does not match the current version.")
                return
            if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
                self._send_error(HTTPStatus.CONFLICT, "Editor preview is stale because the parent song-plan.json has changed.")
                return
            patch = store.read_patch(preview_id)
            result = apply_editor_patch(parent_plan, patch)
            result.plan.validate()
            preview_plan_mismatch = False
            try:
                preview_plan = store.read_plan(preview_id)
                preview_plan_mismatch = editor_song_plan_hash(preview_plan) != editor_song_plan_hash(result.plan)
            except (OSError, ValueError, TypeError, KeyError):
                preview_plan_mismatch = True
            run_title = str(payload.get("version_name") or payload.get("name") or preview.label or "Editor Version")
            run_dir = self.store._reserve_run_dir(run_title)
            job_id = run_dir.name
            now = _utc_now()
            metadata = editor_edit_metadata(
                project_id=project_id,
                parent_version_id=parent.version_id,
                parent_job_id=parent_job.job_id,
                preview_id=preview.preview_id,
                patch=patch,
                result=result,
                created_at=now,
            )
            audition_summary = audition_summary_for_preview(self.project_store.project_dir(project_id), preview.preview_id)
            if audition_summary.get("audition_count"):
                metadata["audition_summary"] = audition_summary
                if isinstance(metadata.get("summary"), dict):
                    metadata["summary"]["audition_count"] = audition_summary.get("audition_count", 0)
                    metadata["summary"]["audition_sources"] = audition_summary.get("sources", [])
            if preview_plan_mismatch:
                metadata["warnings"] = [
                    *metadata.get("warnings", []),
                    "Preview song-plan.json differed from recomputed editor patch result; applied recomputed plan.",
                ]
                metadata["preview_plan_mismatch"] = True
            paths = ProjectPaths.create(run_dir)
            plan_path = paths.data / "song-plan.json"
            midi_path = paths.renders / "song.mid"
            validator_report_path = paths.data / "validator-report.json"
            request_payload = {
                **parent.request,
                "project_id": project_id,
                "parent_version_id": parent.version_id,
                "parent_job_id": parent_job.job_id,
                "editor_preview_id": preview.preview_id,
                "edit_type": "manual_editor_edit",
            }
            write_json(paths.data / "request.json", request_payload)
            write_json(paths.data / "editor-patch.json", patch.to_dict())
            write_json(paths.data / "edit-metadata.json", metadata)
            write_json(plan_path, result.plan.to_dict())
            render_midi(result.plan, midi_path)
            clear_stem_artifacts(run_dir)
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            summary["edit"] = metadata["summary"]
            write_json(paths.data / "run-summary.json", summary)
            append_event(paths, {"event": "editor_preview_applied", "preview_id": preview.preview_id, "parent_version_id": parent.version_id})
            job = JobState(
                job_id=job_id,
                title=run_title,
                output_dir=str(run_dir),
                status="completed",
                created_at=now,
                updated_at=now,
                step="completed",
                message="Editor patch applied.",
                summary=summary,
                input_payload=request_payload,
                provider_snapshot={"mode": "local", "summary": "Visual editor patch"},
                artifacts={**_job_artifacts(run_dir, plan_path, midi_path, validator_report_path), "editor_patch": str(paths.data / "editor-patch.json")},
                finished_at=now,
                heartbeat_at=now,
                generation_mode="local",
                pipeline_mode=parent.pipeline_mode,
                job_type="edit",
                edit_metadata=metadata,
            )
            self.store.jobs[job.job_id] = job
            self.store._write_job(job)
            document = self.project_store.add_version_from_job(
                project_id,
                job,
                name=run_title,
                note=str(payload.get("version_note") or payload.get("note") or ""),
                parent_version_id=parent.version_id,
                variant_type="manual_editor_edit",
                change_summary=str(payload.get("change_summary") or preview.label or "Visual editor patch"),
            )
            version = next(version for version in document.versions if version.job_id == job.job_id)
            updated_preview = store.mark_applied(preview_id, version_id=version.version_id, job_id=job.job_id, now=_utc_now())
            self.project_store.append_event(
                project_id,
                "editor_preview_applied",
                {"parent_version_id": parent.version_id, "preview_id": preview_id, "version_id": version.version_id, "job_id": job.job_id},
            )
        self._send_json({"ok": True, **document.to_dict(), "version": version.to_dict(), "job": job.to_dict(), "preview": updated_preview.to_dict()}, status=HTTPStatus.CREATED)

    def _handle_project_edit_preview(self, method: str, project_id: str, version_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        payload = self._read_json_body()
        try:
            payload = self._expand_context_pack_payload(payload)
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
            reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
            reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
            patch, provider_snapshot = generate_provider_edit_patch(
                parent_plan=parent_plan,
                instruction=instruction,
                template=template,
                config=config,
                asset_references=asset_prompt_refs,
                reference_references=reference_prompt_refs,
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
                reference_refs=reference_snapshot["reference_refs"],
                context_pack=payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None,
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
            if reference_snapshot["reference_refs"]:
                self.reference_store.mark_used(
                    reference_snapshot["reference_refs"],
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
            context_pack = preview.source.get("context_pack") if isinstance(preview.source.get("context_pack"), dict) else None
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
                reference_refs=preview.source.get("reference_refs") if isinstance(preview.source.get("reference_refs"), list) else None,
                context_pack=context_pack,
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
            payload = self._expand_context_pack_payload(payload)
            group = self._create_project_candidate_group(project_id, version_id, payload)
        except ContextPackStaleError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
            return
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
        reference_snapshot = reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_utc_now())
        reference_prompt_refs = reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
        patches, provider_snapshot = generate_provider_edit_candidates(
            parent_plan=parent_plan,
            instruction=instruction,
            template=template,
            config=config,
            candidate_count=candidate_count,
            asset_references=asset_prompt_refs,
            reference_references=reference_prompt_refs,
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
                "reference_refs": list(reference_snapshot["reference_refs"]),
                **({"context_pack": dict(payload["context_pack"])} if isinstance(payload.get("context_pack"), dict) else {}),
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
        if reference_snapshot["reference_refs"] and mark_asset_usage:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "candidate_generation", "project_id": project_id, "version_id": parent.version_id, "candidate_group_id": group.group_id})
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
                reference_refs=group.source.get("reference_refs") if isinstance(group.source.get("reference_refs"), list) else None,
                context_pack=group.source.get("context_pack") if isinstance(group.source.get("context_pack"), dict) else None,
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
            payload = self._expand_context_pack_payload(payload)
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
                reference_refs = group.source.get("reference_refs") if isinstance(group.source, dict) else None
                if isinstance(reference_refs, list) and reference_refs:
                    self.reference_store.mark_used(
                        reference_refs,
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
        except ContextPackStaleError as exc:
            self._rollback_prompt_ab_groups(project_id, created_group_ids)
            self._send_error(HTTPStatus.CONFLICT, str(exc))
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

    def _merge_editor_patch_metadata(self, left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
        return _merge_editor_patch_metadata(left, right)

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
        self.send_header("Content-Disposition", _content_disposition_filename(filename or path.name))
        self.end_headers()
        self.wfile.write(body)

    def _content_length_within(self, limit: int) -> bool:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return False
        return 0 <= length <= limit

    def _expand_context_pack_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        pack_id = str(payload.get("context_pack_id") or "").strip()
        if not pack_id:
            return payload
        pack = self.context_pack_store.read_pack(pack_id)
        applied = apply_context_pack(pack, asset_store=self.asset_store, reference_store=self.reference_store, captured_at=_utc_now())
        asset_refs = merge_context_refs(payload.get("asset_refs"), applied["asset_refs"], "asset_id", 5)
        reference_refs = merge_context_refs(payload.get("reference_refs"), applied["reference_refs"], "reference_id", 5)
        return {
            **payload,
            "asset_refs": asset_refs,
            "reference_refs": reference_refs,
            "context_pack": context_pack_snapshot(pack, {"asset_refs": asset_refs, "reference_refs": reference_refs}, captured_at=_utc_now()),
        }

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
        self.reference_store = ReferenceStore()
        self.library_index_store = LibraryIndexStore()
        self.context_pack_store = ContextPackStore()
        self.job_store = JobStore(asset_store=self.asset_store, reference_store=self.reference_store, context_pack_store=self.context_pack_store)
        self.batch_store = BatchStore()
        self.project_store = ProjectStore()
        self.edit_preset_store = EditPresetStore()
        self.prompt_template_store = PromptTemplateStore()
        self.editor_template_store = EditorTemplateStore()
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


def _try_read_review_decision_report(task_store: ReviewTaskStore, task_id: str) -> dict[str, Any]:
    try:
        return task_store.read_decision_report(task_id)
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _review_sprints_list_summary(sprints: list[dict[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    total_conflicts = 0
    blocking_conflicts = 0
    for sprint in sprints:
        status = str(sprint.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        summary = sprint.get("summary") if isinstance(sprint.get("summary"), dict) else {}
        counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}
        total_conflicts += int(counts.get("conflict_count") or 0)
        blocking_conflicts += int(counts.get("blocking_conflict_count") or 0)
    return sanitize_metadata(
        {
            "total": len(sprints),
            "statuses": statuses,
            "conflict_count": total_conflicts,
            "blocking_conflict_count": blocking_conflicts,
        }
    )


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


def _merge_editor_patch_metadata(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in (left, right):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if key in {"clip_inserts", "template_inserts"}:
                continue
            merged[key] = value
    inserts: list[dict[str, Any]] = []
    template_inserts: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_templates: set[str] = set()
    for source in (left, right):
        raw_inserts = source.get("clip_inserts") if isinstance(source, dict) else None
        if not isinstance(raw_inserts, list):
            continue
        for item in raw_inserts:
            if not isinstance(item, dict):
                continue
            group_id = str(item.get("clip_group_id") or "")
            key = group_id or json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            inserts.append(sanitize_metadata(dict(item)))
    if inserts:
        merged["clip_inserts"] = inserts[:20]
    for source in (left, right):
        raw_inserts = source.get("template_inserts") if isinstance(source, dict) else None
        if not isinstance(raw_inserts, list):
            continue
        for item in raw_inserts:
            if not isinstance(item, dict):
                continue
            group_id = str(item.get("template_group_id") or "")
            key = group_id or json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen_templates:
                continue
            seen_templates.add(key)
            template_inserts.append(sanitize_metadata(dict(item)))
    if template_inserts:
        merged["template_inserts"] = template_inserts[:20]
    return sanitize_metadata(merged)


def _match_editor_template_route(path: str) -> tuple[str, str, str] | None:
    prefix = "/api/editor-templates/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    parts = rest.split("/")
    if len(parts) < 2 or parts[0] not in {"sections", "tracks"}:
        return None
    template_id = unquote(parts[1])
    tail = "" if len(parts) == 2 else "/" + "/".join(parts[2:])
    return parts[0], template_id, tail


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


def _match_reference_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/references/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "import":
        return None
    if "/" in rest:
        reference_id, tail = rest.split("/", 1)
        return unquote(reference_id), "/" + tail
    return unquote(rest), ""


def _match_context_pack_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/context-packs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        pack_id, tail = rest.split("/", 1)
        return unquote(pack_id), "/" + tail
    return unquote(rest), ""


def _match_project_variation_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "variation":
        return unquote(parts[1])
    return None


def _match_project_editor_state_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-state":
        return unquote(parts[1])
    return None


def _match_project_editor_view_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-view":
        return unquote(parts[1])
    return None


def _match_project_editor_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-draft":
        return unquote(parts[1])
    return None


def _match_project_editor_clips_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-clips":
        return unquote(parts[1])
    return None


def _match_project_editor_clip_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-clip-draft":
        return unquote(parts[1])
    return None


def _match_project_section_template_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "section-templates":
        return unquote(parts[1])
    return None


def _match_project_track_template_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "track-templates":
        return unquote(parts[1])
    return None


def _match_project_editor_template_mapping_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-template-mapping":
        return unquote(parts[1])
    return None


def _match_project_editor_multitrack_clip_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-multitrack-clip-draft":
        return unquote(parts[1])
    return None


def _match_project_editor_preview_create_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-preview":
        return unquote(parts[1])
    return None


def _match_project_version_audio_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] in {"audio", "render-audio"}:
        return unquote(parts[1]), parts[2]
    return None


def _match_project_editor_preview_root_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 1 and parts[0] == "editor-previews":
        return "list"
    if len(parts) == 2 and parts[0] == "editor-previews" and parts[1] == "cleanup":
        return "cleanup"
    return None


def _match_project_editor_auditions_root_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] == "auditions":
        return unquote(parts[1])
    return None


def _match_project_editor_audition_reviews_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] == "audition-reviews":
        return unquote(parts[1])
    return None


def _match_project_editor_audition_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "editor-previews" and parts[2] == "auditions":
        return unquote(parts[1]), unquote(parts[3]), "detail"
    if len(parts) == 5 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] in {
        "midi",
        "audio",
        "render-audio",
        "review",
        "markers",
        "create-asset",
        "review-edit-preview",
        "review-edit",
        "provider-review-edit-preview",
        "create-context-pack",
        "review-task",
        "delete",
    }:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None


def _match_project_editor_audition_marker_tail(tail: str) -> tuple[str, str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 6 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] == "markers":
        return unquote(parts[1]), unquote(parts[3]), unquote(parts[5]), "update"
    if len(parts) == 7 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] == "markers" and parts[6] == "delete":
        return unquote(parts[1]), unquote(parts[3]), unquote(parts[5]), "delete"
    return None


def _match_project_editor_preview_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "editor-previews":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] in {"patch", "song-plan", "midi", "audio", "render-audio", "delete", "apply"}:
        return unquote(parts[1]), parts[2]
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


def _match_project_review_task_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "review-tasks":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "review-tasks" and parts[2] in {"candidates", "provider-candidates", "decision-report", "resolve", "needs-more-work", "archive"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 4 and parts[0] == "review-tasks" and parts[2] == "decision-report" and parts[3] == "refresh":
        return unquote(parts[1]), "decision-report-refresh"
    return None


def _match_project_review_sprint_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "review-sprints":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "review-sprints" and parts[2] in {"refresh", "close", "archive", "tasks", "generate-local-candidates", "generate-provider-candidates", "conflicts", "recommendations"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "tasks" and parts[3] in {"remove", "reorder"}:
        return unquote(parts[1]), f"tasks-{parts[3]}"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "conflicts" and parts[3] == "refresh":
        return unquote(parts[1]), "conflicts-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "recommendations" and parts[3] == "refresh":
        return unquote(parts[1]), "recommendations-refresh"
    if len(parts) == 5 and parts[0] == "review-sprints" and parts[2] == "recommendations" and parts[4] == "context-pack":
        return unquote(parts[1]), f"recommendation-context-pack:{unquote(parts[3])}"
    return None


def _recommendation_action_for_task(report: dict[str, Any], task_id: str) -> dict[str, Any]:
    actions = report.get("recommended_actions") if isinstance(report, dict) else []
    for action in actions if isinstance(actions, list) else []:
        if isinstance(action, dict) and action.get("task_id") == task_id:
            return action
    return {}


def _context_ref_count(preview: Any) -> int:
    if not isinstance(preview, dict):
        return 0
    return len(preview.get("asset_refs") or []) + len(preview.get("reference_refs") or [])


def _match_project_review_task_candidate_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 5 and parts[0] == "review-tasks" and parts[2] == "candidates" and parts[4] in {"midi", "audio", "render-midi", "render-audio", "apply"}:
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


def _content_disposition_filename(filename: str) -> str:
    ascii_name = _safe_download_filename(filename)
    utf8_name = "".join(char for char in str(filename) if ord(char) >= 32 and char not in {'"', "\r", "\n"})
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{_rfc5987_quote(utf8_name)}"


def _safe_download_filename(filename: str) -> str:
    name = Path(str(filename or "download")).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    cleaned = cleaned.strip(" ._")
    if not cleaned:
        cleaned = "download"
    if len(cleaned) > 120:
        suffix = Path(cleaned).suffix[:16]
        stem = Path(cleaned).stem[: max(1, 120 - len(suffix))]
        cleaned = f"{stem}{suffix}"
    return cleaned


def _rfc5987_quote(value: str) -> str:
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$&+-.^_`|~"
    return "".join(char if char in allowed else f"%{byte:02X}" for char in value for byte in char.encode("utf-8"))


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
