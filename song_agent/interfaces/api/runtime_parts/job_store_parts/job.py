from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.dependencies.core_dependencies import Path, apply_asset_refs_to_plan, generate_request, write_asset_refs_snapshot

from song_agent.interfaces.api.runtime_parts.dependencies.creation_quality_dependencies import ProjectPaths, SongPlan, SongRequest, append_event, clear_stem_artifacts, load_provider_config, read_json, render_midi, write_json, write_reference_refs_snapshot

from song_agent.interfaces.api.runtime_parts.helpers.api_info import _build_summary, _build_validator_report, _utc_now

from song_agent.interfaces.api.runtime_parts.core import JobCancelled

class JobStoreJob:
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
