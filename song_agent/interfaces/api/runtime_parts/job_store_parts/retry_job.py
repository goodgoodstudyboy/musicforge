from __future__ import annotations

from song_agent.platform.contracts import DomainDocument
from song_agent.interfaces.api.runtime_parts.job_store_context import JobStoreContext

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import AUDIO_ARTIFACT_FILENAME, Any, HTTPStatus, JobState, Path, audio_artifact_summary, build_audio_artifact_manifest, datetime, shutil, threading, timezone, write_audio_artifact_manifest

import song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies as creation_dependencies
from song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies import ProjectPaths, ProviderError, RendererError, SongPlan, affected_nodes_for_retry, append_event, clear_stem_artifacts, load_or_preview_stem_manifest, load_renderer_config, read_json, read_stem_manifest, render_audio, render_stem_audio, render_stem_midis, stem_manifest_stale, write_json

from song_agent.interfaces.api.runtime_parts.helpers.api_info import _artifact_dict, _audio_report, _manifest_response, _stem_audio_manifest_status, _stem_midi_manifest_status, _utc_now

from song_agent.interfaces.api.runtime_parts.helpers.generation_mode import _parse_iso_datetime

class JobStoreRetryJob(JobStoreContext):
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
    ) -> tuple[JobState | None, HTTPStatus, str | None, DomainDocument]:
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

        node_store = creation_dependencies.NodeStore(Path(job.output_dir))
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

    def render_job_audio(self, job_id: str, *, config: Any | None = None, audio_profile: Any | None = None) -> tuple[DomainDocument, HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        midi_path = run_dir / "renders" / "song.mid"
        if not midi_path.exists():
            return {}, HTTPStatus.CONFLICT, "song.mid is not available for this job yet."
        try:
            if config is None:
                config, _sources = load_renderer_config()
            wav_path = render_audio(midi_path, run_dir / "renders" / "song.wav", config)
            manifest = build_audio_artifact_manifest(
                artifact_id=f"job-{job_id}",
                scope="job",
                wav_path=wav_path,
                midi_path=midi_path,
                song_plan_path=run_dir / "data" / "song-plan.json",
                renderer_config=config,
                profile=audio_profile,
                extra_source={"job_id": job_id},
                now=_utc_now(),
            )
            write_audio_artifact_manifest(run_dir / "renders" / AUDIO_ARTIFACT_FILENAME, manifest)
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
            report["audio_artifact"] = audio_artifact_summary(manifest)
            write_json(validator_report_path, report)
        artifacts = dict(job.artifacts)
        artifacts["audio"] = str(wav_path)
        artifacts["audio_artifact"] = str(run_dir / "renders" / AUDIO_ARTIFACT_FILENAME)
        self._update_job(job, artifacts=artifacts)
        return {
            "audio": str(wav_path),
            "artifact": _artifact_dict(wav_path),
            "audio_artifact": manifest,
            "audio_artifact_summary": audio_artifact_summary(manifest),
        }, HTTPStatus.OK, None

    def get_job_stems(self, job_id: str) -> tuple[DomainDocument, HTTPStatus, str | None]:
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
    ) -> tuple[DomainDocument, HTTPStatus, str | None]:
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
    ) -> tuple[DomainDocument, HTTPStatus, str | None]:
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
