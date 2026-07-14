from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.dependencies.part_001 import Any, AssetStore, HTTPStatus, JobState, Path, build_edit_metadata, json, threading, validate_edit_intent

from song_agent.interfaces.api.runtime_parts.dependencies.part_005 import ContextPackStore, ProjectPaths, ReferenceStore, SongRequest, load_provider_config, read_json, write_json

from song_agent.interfaces.api.runtime_parts.helpers.part_002 import _candidate_source_summary

from song_agent.interfaces.api.runtime_parts.helpers.part_005 import _clean_title, _generation_mode, _pipeline_mode

from song_agent.interfaces.api.runtime_parts.helpers.part_001 import _utc_now

from song_agent.interfaces.api.runtime_parts.core import RUNS_DIR

class JobStorePart001:
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
