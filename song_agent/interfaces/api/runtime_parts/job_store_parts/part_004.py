from __future__ import annotations

from song_agent.interfaces.api.runtime_parts.dependencies.part_001 import Any, EditIntent, EditedSongPlanResult, Path, apply_asset_refs_to_plan, apply_edit_intent, asset_refs_snapshot, build_edit_metadata, write_asset_refs_snapshot

from song_agent.interfaces.api.runtime_parts.dependencies.part_005 import ProjectPaths, ProviderEditPatch, SongPlan, append_event, apply_candidate_intents, apply_provider_edit_patch, apply_review_edit, clear_stem_artifacts, context_pack_snapshot, read_json, reference_refs_snapshot, render_midi, write_context_pack_snapshot, write_json, write_reference_refs_snapshot

from song_agent.interfaces.api.runtime_parts.helpers.part_001 import _build_summary, _build_validator_report, _utc_now

from song_agent.interfaces.api.runtime_parts.helpers.part_002 import _candidate_source_summary, _job_artifacts

from song_agent.interfaces.api.runtime_parts.core import JobCancelled

class JobStorePart004:
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
                from song_agent.application.legacy_dependencies.review_edits import ReviewEditIntent

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
                        "review_judge": metadata.get("review_judge") if isinstance(metadata.get("review_judge"), dict) else {},
                        "review_sprint": metadata.get("review_sprint") if isinstance(metadata.get("review_sprint"), dict) else {},
                        "review_sprint_recommendation": metadata.get("review_sprint_recommendation") if isinstance(metadata.get("review_sprint_recommendation"), dict) else {},
                        "review_sprint_action_queue": metadata.get("review_sprint_action_queue") if isinstance(metadata.get("review_sprint_action_queue"), dict) else {},
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
