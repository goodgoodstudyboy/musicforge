from __future__ import annotations

from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.application.interface_persistence import write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesSaveReviewSprintRecommendationContextPack:
    def _save_review_sprint_recommendation_context_pack(self, project_id: str, sprint_store: _interfaces_api_runtime.ReviewSprintStore, task_store: _interfaces_api_runtime.ReviewTaskStore, sprint: Any, task_id: str, payload: ImplementationDocument) -> ImplementationDocument:
        if task_id not in self._review_sprint_ordered_task_ids(sprint):
            raise FileNotFoundError(task_id)
        task = task_store.read_task(task_id)
        if task.project_id != project_id:
            raise FileNotFoundError(task_id)
        report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        if not report:
            report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
        action = _interfaces_api_runtime._recommendation_action_for_task(report, task_id)
        if not action:
            raise _interfaces_api_runtime.ReviewSprintStateError("Recommendation for task is missing.")
        preview = action.get("context_pack_preview") if isinstance(action.get("context_pack_preview"), dict) else {}
        asset_refs = preview.get("asset_refs") if isinstance(preview.get("asset_refs"), list) else []
        reference_refs = preview.get("reference_refs") if isinstance(preview.get("reference_refs"), list) else []
        if not asset_refs and not reference_refs:
            raise _interfaces_api_runtime.ReviewSprintStateError("Recommendation has no context refs to save.")
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
        pack = self.context_pack_store.create_pack(pack_payload, asset_store=self.asset_store, reference_store=self.reference_store, now=_interfaces_api_runtime._utc_now())
        self.project_store.append_event(project_id, "review_sprint_recommendation_context_pack_saved", {"sprint_id": sprint.sprint_id, "task_id": task_id, "pack_id": pack.pack_id})
        return {"ok": True, "context_pack": _interfaces_api_runtime.context_pack_public_dict(pack), "recommendation": action}

    def _ensure_recommendation_context_refs_current(self, asset_refs: list[ImplementationDocument], reference_refs: list[ImplementationDocument]) -> None:
        for ref in asset_refs:
            asset = self.asset_store.read_asset(str(ref.get("asset_id") or ""))
            if asset.hidden or str(ref.get("source_hash") or "") != _interfaces_api_runtime.asset_source_hash(asset):
                raise _interfaces_api_runtime.ReviewSprintStateError("Recommendation context asset is stale. Refresh recommendations before saving.")
        for ref in reference_refs:
            reference = self.reference_store.read_reference(str(ref.get("reference_id") or ""))
            if reference.hidden or str(ref.get("source_hash") or "") != reference.sha256:
                raise _interfaces_api_runtime.ReviewSprintStateError("Recommendation context reference is stale. Refresh recommendations before saving.")

    def _generate_review_sprint_provider_candidates(self, project_id: str, sprint_store: _interfaces_api_runtime.ReviewSprintStore, task_store: _interfaces_api_runtime.ReviewTaskStore, sprint: Any, payload: ImplementationDocument) -> ImplementationDocument:
        if sprint.status not in {"open", "in_progress", "blocked"}:
            raise _interfaces_api_runtime.ReviewSprintStateError(f"Cannot generate provider candidates for a {sprint.status} review sprint.")
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        stop_on_conflict = bool(payload.get("stop_on_conflict", sprint.settings.get("stop_on_conflict", False)))
        if stop_on_conflict and any(item.get("severity") == "blocking" for item in conflict_report.get("conflicts", [])):
            raise _interfaces_api_runtime.ReviewSprintStateError("Review sprint has blocking conflicts.")
        template_id = str(payload.get("template_id") or sprint.settings.get("provider_template_id") or "provider-review-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise _interfaces_api_runtime.ReviewSprintStateError("Prompt template is disabled.")
        candidate_count = max(1, min(5, int(payload.get("candidate_count") or sprint.settings.get("provider_candidate_count") or 2)))
        render_midi = bool(payload.get("render_midi", sprint.settings.get("render_midi", True)))
        skip_existing = bool(payload.get("skip_existing_provider", True))
        include_local_context = bool(payload.get("include_local_context", True))
        config, _sources = _interfaces_api_runtime.load_provider_config()
        asset_snapshot = _interfaces_api_runtime.asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_interfaces_api_runtime._utc_now())
        asset_prompt_refs = _interfaces_api_runtime.asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        reference_snapshot = _interfaces_api_runtime.reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_interfaces_api_runtime._utc_now())
        reference_prompt_refs = _interfaces_api_runtime.reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
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
                _interfaces_api_runtime.ensure_task_current(task, parent_plan)
                local_context = candidates if include_local_context else []
                generated_specs, provider_snapshot, instruction = _interfaces_api_runtime.build_provider_review_candidates(
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
                        now=_interfaces_api_runtime._utc_now(),
                    )
                    generated.append(stored)
                ranked = task_store.rank_candidates(task)
                task = task_store.update_counts(task, now=_interfaces_api_runtime._utc_now())
                provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
                usage_record = _interfaces_api_runtime._provider_usage_record(
                    config_snapshot=provider_snapshot,
                    operation="review_sprint_provider_candidates",
                    template_id=template.template_id,
                    started_at=_interfaces_api_runtime._utc_now(),
                    status="completed",
                    provider_usage=provider_usage,
                    request_id=provider_snapshot.get("request_id"),
                )
                write_interface_document(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
                decision_report = task_store.write_decision_report(task, _interfaces_api_runtime.build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_interfaces_api_runtime._utc_now(), notes=str(payload.get("decision_note") or "")), now=_interfaces_api_runtime._utc_now())
                created_total += len(generated)
                provider_snapshots.append(provider_snapshot)
                results.append(
                    {
                        "task_id": task.task_id,
                        "status": "generated" if generated else "skipped",
                        "created_count": len(generated),
                        "created_candidate_ids": [candidate.candidate_id for candidate in generated],
                        "instruction": instruction,
                        "decision_report": _interfaces_api_runtime.review_decision_summary(decision_report),
                        "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(ranked),
                        "provider_snapshot": provider_snapshot,
                    }
                )
            except (FileNotFoundError, _interfaces_api_runtime.ReviewTaskError, _interfaces_api_runtime.ReviewTaskStateError, _interfaces_api_runtime.ProviderError, ValueError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        if asset_snapshot["asset_refs"]:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "review_sprint_provider_candidates", "project_id": project_id, "review_sprint_id": sprint.sprint_id})
        if reference_snapshot["reference_refs"]:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "review_sprint_provider_candidates", "project_id": project_id, "review_sprint_id": sprint.sprint_id})
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        self.project_store.append_event(project_id, "review_sprint_provider_candidates_generated", {"sprint_id": sprint.sprint_id, "created_count": created_total, "template_id": template.template_id})
        response = self._review_sprint_response(sprint_store, task_store, sprint)
        response.update({"results": _interfaces_api_runtime.sanitize_metadata(results), "created_count": created_total, "provider_snapshots": _interfaces_api_runtime.sanitize_metadata(provider_snapshots)})
        return response

    def _execute_queue_context_pack_action(self, project_id: str, sprint_store: _interfaces_api_runtime.ReviewSprintStore, task_store: _interfaces_api_runtime.ReviewTaskStore, sprint: Any, item: _interfaces_api_runtime.SprintActionItem) -> ImplementationDocument:
        context_pack_id = str((item.result or {}).get("context_pack_id") or "")
        if context_pack_id:
            pack = self.context_pack_store.read_pack(context_pack_id)
            return {"status": "skipped", "reason": "context pack already created", "context_pack_id": pack.pack_id}
        preview = item.input.get("context_pack_preview") if isinstance(item.input.get("context_pack_preview"), dict) else {}
        asset_refs = preview.get("asset_refs") if isinstance(preview.get("asset_refs"), list) else []
        reference_refs = preview.get("reference_refs") if isinstance(preview.get("reference_refs"), list) else []
        if not asset_refs and not reference_refs:
            return {"status": "skipped", "reason": "recommendation has no context refs"}
        result = self._save_review_sprint_recommendation_context_pack(project_id, sprint_store, task_store, sprint, str(item.task_id), {"name": item.input.get("name") or ""})
        return {"status": "created", "context_pack_id": result["context_pack"]["pack_id"], "asset_count": len(result["context_pack"].get("asset_refs") or []), "reference_count": len(result["context_pack"].get("reference_refs") or [])}

    def _generate_review_task_provider_candidates_for_queue(self, project_id: str, task_store: _interfaces_api_runtime.ReviewTaskStore, task: Any, payload: ImplementationDocument) -> ImplementationDocument:
        payload = self._expand_context_pack_payload(payload)
        candidates = task_store.list_candidates(task.task_id)
        if bool(payload.get("skip_existing_provider", True)) and any((candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")) and candidate.status in {"ready", "applied"} for candidate in candidates):
            return {"status": "skipped", "reason": "ready provider candidate exists", "created_count": 0, "created_candidate_ids": []}
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        _interfaces_api_runtime.ensure_task_current(task, parent_plan)
        template_id = str(payload.get("template_id") or "provider-review-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise _interfaces_api_runtime.ReviewSprintStateError("Prompt template is disabled.")
        candidate_count = max(1, min(5, int(payload.get("candidate_count") or 2)))
        config, _sources = _interfaces_api_runtime.load_provider_config()
        asset_snapshot = _interfaces_api_runtime.asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=_interfaces_api_runtime._utc_now())
        asset_prompt_refs = _interfaces_api_runtime.asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))
        reference_snapshot = _interfaces_api_runtime.reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=_interfaces_api_runtime._utc_now())
        reference_prompt_refs = _interfaces_api_runtime.reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))
        local_context = candidates if bool(payload.get("include_local_context", True)) else []
        generated_specs, provider_snapshot, instruction = _interfaces_api_runtime.build_provider_review_candidates(
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
            generated.append(task_store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=bool(payload.get("render_midi", True)), now=_interfaces_api_runtime._utc_now()))
        ranked = task_store.rank_candidates(task)
        updated_task = task_store.update_counts(task, now=_interfaces_api_runtime._utc_now())
        provider_usage = provider_snapshot.get("usage") if isinstance(provider_snapshot.get("usage"), dict) else {}
        usage_record = _interfaces_api_runtime._provider_usage_record(config_snapshot=provider_snapshot, operation="review_sprint_action_provider_candidates", template_id=template.template_id, started_at=_interfaces_api_runtime._utc_now(), status="completed", provider_usage=provider_usage, request_id=provider_snapshot.get("request_id"))
        write_interface_document(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
        decision_report = task_store.write_decision_report(updated_task, _interfaces_api_runtime.build_review_decision_report(task=updated_task, candidates=ranked, parent_plan=parent_plan, now=_interfaces_api_runtime._utc_now(), notes=str(payload.get("decision_note") or "")), now=_interfaces_api_runtime._utc_now())
        if asset_snapshot["asset_refs"]:
            self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "review_sprint_action_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
        if reference_snapshot["reference_refs"]:
            self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "review_sprint_action_provider_candidates", "project_id": project_id, "review_task_id": task.task_id})
        self.project_store.append_event(project_id, "review_sprint_action_provider_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated), "template_id": template.template_id})
        return {"status": "generated" if generated else "skipped", "created_count": len(generated), "created_candidate_ids": [candidate.candidate_id for candidate in generated], "instruction": instruction, "decision_report": _interfaces_api_runtime.review_decision_summary(decision_report), "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(ranked), "provider_snapshot": provider_snapshot}
