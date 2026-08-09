from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from collections.abc import Callable
from typing import Protocol
import threading

from song_agent.application.jobs.model import JobState
from song_agent.domains.creation.batching import BatchDocument
from song_agent.domains.creation.edits import EditIntent
from song_agent.domains.creation.schemas.song import SongPlan
from song_agent.domains.quality.audio_profiles import RendererProfile
from song_agent.domains.creation.renderers.audio import RendererConfig
from song_agent.domains.studio.assets import AssetStore
from song_agent.domains.studio.context_packs import ContextPackStore
from song_agent.domains.studio.references import ReferenceStore
from song_agent.domains.studio.project_repository import ProjectDocument
from song_agent.platform.contracts.documents import JsonDocument


class JobRuntimePort(Protocol):
    jobs: dict[str, JobState]

    def create_job(
        self,
        payload: JsonDocument,
        start_immediately: bool = True,
    ) -> JobState: ...

    def get_job(self, job_id: str) -> JobState | None: ...

    def list_jobs(self, include_hidden: bool = False) -> list[JobState]: ...

    def _write_job(self, job: JobState) -> None: ...

    def start_job(self, job_id: str) -> bool: ...

    def create_edit_job(
        self,
        *,
        project_id: str,
        parent_version_id: str,
        parent_job: JobState,
        parent_plan: SongPlan,
        intent: EditIntent,
        preset: JsonDocument | None = None,
        name: str = "",
        start_immediately: bool = True,
        provider_patch: JsonDocument | None = None,
        provider_usage: JsonDocument | None = None,
        provider_snapshot: JsonDocument | None = None,
        template_id: str | None = None,
        preview_id: str | None = None,
        candidate_group_id: str | None = None,
        candidate_id: str | None = None,
        candidate: JsonDocument | None = None,
        asset_refs: list[JsonDocument] | None = None,
        reference_refs: list[JsonDocument] | None = None,
        context_pack: JsonDocument | None = None,
    ) -> JobState: ...

    def retry_job_node(
        self,
        job_id: str,
        node_name: str,
    ) -> tuple[JobState | None, HTTPStatus, str | None, JsonDocument]: ...

    def retry_job(self, job_id: str) -> tuple[JobState | None, HTTPStatus, str | None]: ...

    def hide_job(self, job_id: str, hidden: bool) -> JobState | None: ...

    def cancel_job(self, job_id: str) -> tuple[JobState | None, HTTPStatus, str | None]: ...

    def delete_job(self, job_id: str) -> tuple[bool, HTTPStatus, str | None]: ...

    def _reserve_run_dir(self, title: str) -> Path: ...

    def render_job_audio(
        self,
        job_id: str,
        *,
        config: RendererConfig | None = None,
        audio_profile: RendererProfile | None = None,
    ) -> tuple[JsonDocument, HTTPStatus, str | None]: ...

    def get_job_stems(self, job_id: str) -> tuple[JsonDocument, HTTPStatus, str | None]: ...

    def render_job_stems(
        self,
        job_id: str,
        *,
        force: bool = False,
    ) -> tuple[JsonDocument, HTTPStatus, str | None]: ...

    def render_job_stem_audio(
        self,
        job_id: str,
        *,
        stem_ids: list[str] | None = None,
        force: bool = False,
    ) -> tuple[JsonDocument, HTTPStatus, str | None]: ...


class BatchStorePort(Protocol):
    def list_batches(self, *, include_hidden: bool = False) -> list[BatchDocument]: ...

    def get_batch(self, batch_id: str) -> BatchDocument: ...

    def save_batch(self, document: BatchDocument) -> None: ...

    def delete_batch(self, batch_id: str) -> None: ...

    def export_batch(self, batch_id: str) -> JsonDocument: ...

    def hide_batch(self, batch_id: str, hidden: bool) -> BatchDocument: ...

    def batch_dir(self, batch_id: str) -> Path: ...

    def append_event(
        self,
        batch_id: str,
        event_type: str,
        payload: JsonDocument,
    ) -> None: ...

    def import_csv(
        self,
        *,
        name: str,
        csv_text: str,
        generation_mode: str = "local",
        pipeline_mode: str = "multinode",
        max_concurrency: int | str = 1,
    ) -> BatchDocument: ...


class BatchRunnerPort(Protocol):
    def launch_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]: ...

    def pause_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]: ...

    def resume_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]: ...

    def retry_failed(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]: ...

    def render_audio(
        self,
        batch_id: str,
        *,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]: ...

    def render_stems(
        self,
        batch_id: str,
        *,
        audio: bool = False,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]: ...

    def delete_batch(self, batch_id: str) -> tuple[bool, HTTPStatus, str | None]: ...


class ProjectArchivePort(Protocol):
    def find_or_create_project(self, name: str) -> ProjectDocument: ...

    def add_version_from_job(
        self,
        project_id: str,
        job: JobState,
        name: str = "",
        note: str = "",
    ) -> ProjectDocument: ...

    def get_project(self, project_id: str) -> ProjectDocument: ...


ControlCallback = Callable[[str, str], None]


class JobStoreContext:
    """Typed contract shared by the composed JobStore implementation mixins."""

    asset_store: AssetStore
    context_pack_store: ContextPackStore
    jobs: dict[str, JobState]
    lock: threading.RLock
    reference_store: ReferenceStore
    runs_dir: Path

    def get_job(self, job_id: str) -> JobState | None:
        raise NotImplementedError

    def start_job(self, job_id: str) -> bool:
        raise NotImplementedError

    def _control_callback(self, job_id: str) -> ControlCallback:
        raise NotImplementedError

    def _ensure_run_dir_is_safe(self, run_dir: Path) -> Path:
        raise NotImplementedError

    def _heartbeat(self, job: JobState) -> None:
        raise NotImplementedError

    def _prepare_asset_refs_for_job(self, job: JobState) -> JsonDocument:
        raise NotImplementedError

    def _prepare_context_pack_for_job(self, job: JobState) -> JsonDocument | None:
        raise NotImplementedError

    def _prepare_reference_refs_for_job(self, job: JobState) -> JsonDocument:
        raise NotImplementedError

    def _provider_snapshot_for_retry(self, job: JobState) -> JsonDocument:
        raise NotImplementedError

    def _reserve_run_dir(self, title: str) -> Path:
        raise NotImplementedError

    def _run_edit_job(self, job_id: str) -> None:
        raise NotImplementedError

    def _run_job(self, job_id: str) -> None:
        raise NotImplementedError

    def _run_node_retry(
        self,
        job_id: str,
        node_name: str,
        affected_nodes: list[str],
        provider_snapshot: JsonDocument,
    ) -> None:
        raise NotImplementedError

    def _update_job(self, job: JobState, **changes: object) -> None:
        raise NotImplementedError

    def _write_job(self, job: JobState) -> None:
        raise NotImplementedError


class BatchRunnerContext:
    """Typed contract shared by the composed BatchRunner implementation mixins."""

    audio_threads: dict[str, threading.Thread]
    batch_store: BatchStorePort
    job_store: JobRuntimePort
    lock: threading.RLock
    project_store: ProjectArchivePort | None
    stem_threads: dict[str, threading.Thread]
    stop_event: threading.Event
    threads: dict[str, threading.Thread]

    def _audio_counts(self, document: BatchDocument) -> dict[str, int]:
        raise NotImplementedError

    def _ensure_audio_thread(self, batch_id: str) -> None:
        raise NotImplementedError

    def _ensure_stem_thread(self, batch_id: str, *, audio: bool) -> None:
        raise NotImplementedError

    def _ensure_thread(self, batch_id: str) -> None:
        raise NotImplementedError

    def _finish_batch(self, document: BatchDocument) -> None:
        raise NotImplementedError

    def _provider_readiness_error(self, document: BatchDocument) -> str | None:
        raise NotImplementedError

    def _renderer_readiness_error(self) -> str | None:
        raise NotImplementedError

    def _render_audio_item(self, batch_id: str, item_id: str, job_id: str) -> None:
        raise NotImplementedError

    def _render_stem_item(
        self,
        batch_id: str,
        item_id: str,
        job_id: str,
        audio: bool,
    ) -> None:
        raise NotImplementedError

    def _start_available_audio_items(self, batch_id: str) -> int:
        raise NotImplementedError

    def _start_available_items(self, batch_id: str) -> int:
        raise NotImplementedError

    def _start_available_stem_items(self, batch_id: str, *, audio: bool) -> int:
        raise NotImplementedError

    def _stem_counts(self, document: BatchDocument) -> dict[str, int]:
        raise NotImplementedError

    def _sync_audio_items(self, batch_id: str) -> BatchDocument | None:
        raise NotImplementedError

    def _sync_running_items(self, batch_id: str) -> BatchDocument | None:
        raise NotImplementedError

    def _sync_stem_items(self, batch_id: str) -> BatchDocument | None:
        raise NotImplementedError


__all__ = [
    "BatchRunnerContext",
    "BatchRunnerPort",
    "BatchStorePort",
    "ControlCallback",
    "JobRuntimePort",
    "JobStoreContext",
    "ProjectArchivePort",
]
