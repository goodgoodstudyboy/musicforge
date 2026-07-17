from __future__ import annotations

from typing import Any


class BatchRunnerContext:
    """Static inventory of members supplied by runtime composition."""

    _archive_completed_project_items: Any
    _archive_item_to_project: Any
    _audio_counts: Any
    _ensure_audio_thread: Any
    _ensure_stem_thread: Any
    _ensure_thread: Any
    _finish_batch: Any
    _has_unarchived_prior_project_item: Any
    _provider_readiness_error: Any
    _recover_interrupted_audio: Any
    _render_audio_item: Any
    _render_stem_item: Any
    _renderer_readiness_error: Any
    _run_batch: Any
    _run_batch_audio: Any
    _run_batch_stems: Any
    _start_available_audio_items: Any
    _start_available_items: Any
    _start_available_stem_items: Any
    _stem_counts: Any
    _sync_audio_items: Any
    _sync_running_items: Any
    _sync_stem_items: Any
    audio_threads: Any
    batch_store: Any
    job_store: Any
    lock: Any
    project_store: Any
    recover_existing_batches: Any
    stem_threads: Any
    stop_event: Any
    threads: Any
