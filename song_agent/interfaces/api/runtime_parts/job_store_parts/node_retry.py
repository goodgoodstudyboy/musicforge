from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.job_store_context import JobStoreContext

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import Any, JobState, Path, rerun_multinode_from_node

import song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies as creation_dependencies
from song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies import ProjectPaths, SongRequest, append_event, clear_stem_artifacts, load_provider_config, render_midi, slugify, write_json

from song_agent.interfaces.api.runtime_parts.helpers.api_info import _build_summary, _build_validator_report, _utc_now

from song_agent.interfaces.api.runtime_parts.helpers.job_artifacts import _job_artifacts

from song_agent.interfaces.api.runtime_parts.core import JobCancelled

class JobStoreNodeRetry(JobStoreContext):
    def _run_node_retry(
        self,
        job_id: str,
        node_name: str,
        affected_nodes: list[str],
        provider_snapshot: ImplementationDocument,
    ) -> None:
        job = self.get_job(job_id)
        if job is None:
            return
        request = SongRequest.from_dict(job.input_payload)
        run_dir = Path(job.output_dir)
        paths = ProjectPaths.create(run_dir)
        node_store = creation_dependencies.NodeStore(run_dir)
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

    def _provider_snapshot_for_retry(self, job: JobState) -> ImplementationDocument:
        if job.provider_snapshot.get("mode") != "provider":
            return job.provider_snapshot
        provider_config, _sources = load_provider_config()
        provider_config.validate_ready_for_provider()
        return provider_config.to_snapshot("provider", _utc_now())
