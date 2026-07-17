from __future__ import annotations

from typing import Any


class JobStoreContext:
    """Static inventory of members supplied by runtime composition."""

    _control_callback: Any
    _create_edit_job_part_01: Any
    _create_edit_job_part_02: Any
    _create_edit_job_part_03: Any
    _ensure_run_dir_is_safe: Any
    _heartbeat: Any
    _prepare_asset_refs_for_job: Any
    _prepare_context_pack_for_job: Any
    _prepare_reference_refs_for_job: Any
    _provider_snapshot_for_retry: Any
    _reserve_run_dir: Any
    _run_edit_job: Any
    _run_edit_job_part_01: Any
    _run_edit_job_part_02: Any
    _run_edit_job_part_03: Any
    _run_job: Any
    _run_job_part_01: Any
    _run_job_part_02: Any
    _run_node_retry: Any
    _update_job: Any
    _write_job: Any
    asset_store: Any
    context_pack_store: Any
    get_job: Any
    jobs: Any
    load_existing_jobs: Any
    lock: Any
    reference_store: Any
    runs_dir: Any
    start_job: Any
