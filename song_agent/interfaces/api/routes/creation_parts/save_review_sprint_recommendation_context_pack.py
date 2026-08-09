from __future__ import annotations

from dataclasses import dataclass

from song_agent.application.http_ports import creation as creation_ports
from song_agent.platform.contracts.coercion import as_document as _as_document, as_list as _as_list
from song_agent.platform.contracts.coercion import as_documents as _as_documents
from song_agent.platform.contracts.coercion import as_int as _as_int

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext

from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document, normalize_json_value

from song_agent.application.interface_persistence import write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


@dataclass(frozen=True)
class _ProviderCandidateContext:
    template: creation_ports.PromptTemplate
    config: creation_ports.ProviderConfig
    candidate_count: int
    render_midi: bool
    include_local_context: bool
    asset_snapshot: JsonDocument
    asset_prompt_refs: list[JsonDocument]
    reference_snapshot: JsonDocument
    reference_prompt_refs: list[JsonDocument]


class CreationRoutesSaveReviewSprintRecommendationContextPack(CreationRouteContext):
    def _save_review_sprint_recommendation_context_pack(
        self,
        project_id: str,
        sprint_store: creation_ports.ReviewSprintStore,
        task_store: creation_ports.ReviewTaskStore,
        sprint: creation_ports.ReviewSprint,
        task_id: str,
        payload: JsonDocument,
    ) -> JsonDocument:
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
        preview = _as_document(action.get("context_pack_preview"))
        asset_refs = _as_documents(preview.get("asset_refs"))
        reference_refs = _as_documents(preview.get("reference_refs"))
        if not asset_refs and not reference_refs:
            raise _interfaces_api_runtime.ReviewSprintStateError("Recommendation has no context refs to save.")
        self._ensure_recommendation_context_refs_current(asset_refs, reference_refs)
        pack_payload = normalize_json_document(
            {
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
                "query": _as_document(preview.get("query")),
                "asset_refs": asset_refs,
                "reference_refs": reference_refs,
                "selection": {
                    "mode": "recommendation",
                    "selected_by": str(payload.get("selected_by") or "user")[:80],
                    "score_summary": _as_document(action.get("score_breakdown")),
                },
            }
        )
        pack = self.context_pack_store.create_pack(pack_payload, asset_store=self.asset_store, reference_store=self.reference_store, now=_interfaces_api_runtime._utc_now())
        self.project_store.append_event(
            project_id,
            "review_sprint_recommendation_context_pack_saved",
            {"sprint_id": sprint.sprint_id, "task_id": task_id, "pack_id": pack.pack_id},
        )
        return normalize_json_document(
            {
                "ok": True,
                "context_pack": _interfaces_api_runtime.context_pack_public_dict(pack),
                "recommendation": action,
            }
        )

    def _ensure_recommendation_context_refs_current(self, asset_refs: list[JsonDocument], reference_refs: list[JsonDocument]) -> None:
        for ref in asset_refs:
            asset = self.asset_store.read_asset(str(ref.get("asset_id") or ""))
            if asset.hidden or str(ref.get("source_hash") or "") != _interfaces_api_runtime.asset_source_hash(asset):
                raise _interfaces_api_runtime.ReviewSprintStateError("Recommendation context asset is stale. Refresh recommendations before saving.")
        for ref in reference_refs:
            reference = self.reference_store.read_reference(str(ref.get("reference_id") or ""))
            if reference.hidden or str(ref.get("source_hash") or "") != reference.sha256:
                raise _interfaces_api_runtime.ReviewSprintStateError("Recommendation context reference is stale. Refresh recommendations before saving.")

    def _prepare_provider_candidate_context(self, payload: JsonDocument, settings: JsonDocument) -> _ProviderCandidateContext:
        template_id = str(payload.get("template_id") or settings.get("provider_template_id") or "provider-review-candidates").strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise _interfaces_api_runtime.ReviewSprintStateError("Prompt template is disabled.")
        config, _sources = _interfaces_api_runtime.load_provider_config()
        captured_at = _interfaces_api_runtime._utc_now()
        return _ProviderCandidateContext(
            template=template,
            config=config,
            candidate_count=max(1, min(5, _as_int(payload.get("candidate_count") or settings.get("provider_candidate_count") or 2))),
            render_midi=bool(payload.get("render_midi", settings.get("render_midi", True))),
            include_local_context=bool(payload.get("include_local_context", True)),
            asset_snapshot=_as_document(_interfaces_api_runtime.asset_refs_snapshot(self.asset_store, payload.get("asset_refs"), captured_at=captured_at)),
            asset_prompt_refs=_as_documents(_interfaces_api_runtime.asset_prompt_summaries(self.asset_store, payload.get("asset_refs"))),
            reference_snapshot=_as_document(_interfaces_api_runtime.reference_refs_snapshot(self.reference_store, payload.get("reference_refs"), captured_at=captured_at)),
            reference_prompt_refs=_as_documents(_interfaces_api_runtime.reference_prompt_summaries(self.reference_store, payload.get("reference_refs"))),
        )

    def _generate_provider_task_result(
        self,
        project_id: str,
        task_store: creation_ports.ReviewTaskStore,
        task: creation_ports.ReviewTask,
        payload: JsonDocument,
        context: _ProviderCandidateContext,
        *,
        operation: str,
    ) -> JsonDocument:
        candidates = task_store.list_candidates(task.task_id)
        if bool(payload.get("skip_existing_provider", True)) and any(
            (candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")) and candidate.status in {"ready", "applied"}
            for candidate in candidates
        ):
            return {"task_id": task.task_id, "status": "skipped", "reason": "ready provider candidate exists", "created_count": 0, "created_candidate_ids": []}
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        _interfaces_api_runtime.ensure_task_current(task, parent_plan)
        generated_specs, provider_snapshot, instruction = _interfaces_api_runtime.build_provider_review_candidates(
            task=task,
            parent_plan=parent_plan,
            template=context.template,
            config=context.config,
            candidate_count=context.candidate_count,
            local_candidates=candidates if context.include_local_context else [],
            asset_references=context.asset_prompt_refs,
            reference_references=context.reference_prompt_refs,
        )
        generated: list[creation_ports.ReviewCandidate] = []
        for candidate, candidate_plan, validator, summary in generated_specs:
            generated.append(
                task_store.create_candidate(
                    task=task,
                    candidate=candidate,
                    candidate_plan=candidate_plan,
                    validator=validator,
                    summary=summary,
                    render_midi_file=context.render_midi,
                    now=_interfaces_api_runtime._utc_now(),
                )
            )
        ranked = task_store.rank_candidates(task)
        task = task_store.update_counts(task, now=_interfaces_api_runtime._utc_now())
        usage_record = _interfaces_api_runtime._provider_usage_record(
            config_snapshot=provider_snapshot,
            operation=operation,
            template_id=context.template.template_id,
            started_at=_interfaces_api_runtime._utc_now(),
            status="completed",
            provider_usage=_as_document(provider_snapshot.get("usage")),
            request_id=provider_snapshot.get("request_id"),
        )
        write_interface_document(task_store.task_dir(task.task_id) / "provider-usage.json", usage_record)
        decision_report = task_store.write_decision_report(
            task,
            _interfaces_api_runtime.build_review_decision_report(
                task=task,
                candidates=ranked,
                parent_plan=parent_plan,
                now=_interfaces_api_runtime._utc_now(),
                notes=str(payload.get("decision_note") or ""),
            ),
            now=_interfaces_api_runtime._utc_now(),
        )
        return normalize_json_document(
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

    def _mark_provider_context_used(self, context: _ProviderCandidateContext, metadata: JsonDocument) -> None:
        asset_refs = _as_documents(context.asset_snapshot.get("asset_refs"))
        if asset_refs:
            self.asset_store.mark_used(asset_refs, metadata)
        reference_refs = _as_documents(context.reference_snapshot.get("reference_refs"))
        if reference_refs:
            self.reference_store.mark_used(reference_refs, metadata)

    def _generate_review_sprint_provider_candidates(
        self,
        project_id: str,
        sprint_store: creation_ports.ReviewSprintStore,
        task_store: creation_ports.ReviewTaskStore,
        sprint: creation_ports.ReviewSprint,
        payload: JsonDocument,
    ) -> JsonDocument:
        if sprint.status not in {"open", "in_progress", "blocked"}:
            raise _interfaces_api_runtime.ReviewSprintStateError(f"Cannot generate provider candidates for a {sprint.status} review sprint.")
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        stop_on_conflict = bool(payload.get("stop_on_conflict", sprint.settings.get("stop_on_conflict", False)))
        if stop_on_conflict and any(item.get("severity") == "blocking" for item in _as_documents(conflict_report.get("conflicts"))):
            raise _interfaces_api_runtime.ReviewSprintStateError("Review sprint has blocking conflicts.")
        context = self._prepare_provider_candidate_context(payload, sprint.settings)
        results: list[JsonDocument] = []
        provider_snapshots: list[JsonDocument] = []
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                result = self._generate_provider_task_result(
                    project_id,
                    task_store,
                    task_store.read_task(task_id),
                    payload,
                    context,
                    operation="review_sprint_provider_candidates",
                )
                results.append(result)
                snapshot = _as_document(result.get("provider_snapshot"))
                if snapshot:
                    provider_snapshots.append(snapshot)
            except (FileNotFoundError, _interfaces_api_runtime.ReviewTaskError, _interfaces_api_runtime.ReviewTaskStateError, _interfaces_api_runtime.ProviderError, ValueError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        created_total = sum(_as_int(result.get("created_count")) for result in results)
        self._mark_provider_context_used(
            context,
            {"usage_type": "review_sprint_provider_candidates", "project_id": project_id, "review_sprint_id": sprint.sprint_id},
        )
        sprint, _conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        self.project_store.append_event(
            project_id,
            "review_sprint_provider_candidates_generated",
            {"sprint_id": sprint.sprint_id, "created_count": created_total, "template_id": context.template.template_id},
        )
        response = self._review_sprint_response(sprint_store, task_store, sprint)
        response["results"] = normalize_json_value(_interfaces_api_runtime.sanitize_metadata(results))
        response["created_count"] = created_total
        response["provider_snapshots"] = normalize_json_value(_interfaces_api_runtime.sanitize_metadata(provider_snapshots))
        return response

    def _execute_queue_context_pack_action(
        self,
        project_id: str,
        sprint_store: creation_ports.ReviewSprintStore,
        task_store: creation_ports.ReviewTaskStore,
        sprint: creation_ports.ReviewSprint,
        item: creation_ports.SprintActionItem,
    ) -> JsonDocument:
        context_pack_id = str(_as_document(item.result).get("context_pack_id") or "")
        if context_pack_id:
            pack = self.context_pack_store.read_pack(context_pack_id)
            return {"status": "skipped", "reason": "context pack already created", "context_pack_id": pack.pack_id}
        preview = _as_document(item.input.get("context_pack_preview"))
        asset_refs = _as_documents(preview.get("asset_refs"))
        reference_refs = _as_documents(preview.get("reference_refs"))
        if not asset_refs and not reference_refs:
            return {"status": "skipped", "reason": "recommendation has no context refs"}
        result = self._save_review_sprint_recommendation_context_pack(project_id, sprint_store, task_store, sprint, str(item.task_id), {"name": item.input.get("name") or ""})
        context_pack = _as_document(result.get("context_pack"))
        return normalize_json_document(
            {
                "status": "created",
                "context_pack_id": context_pack.get("pack_id"),
                "asset_count": len(_as_list(context_pack.get("asset_refs"))),
                "reference_count": len(_as_list(context_pack.get("reference_refs"))),
            }
        )

    def _generate_review_task_provider_candidates_for_queue(
        self,
        project_id: str,
        task_store: creation_ports.ReviewTaskStore,
        task: creation_ports.ReviewTask,
        payload: JsonDocument,
    ) -> JsonDocument:
        payload = self._expand_context_pack_payload(payload)
        candidates = task_store.list_candidates(task.task_id)
        if bool(payload.get("skip_existing_provider", True)) and any(
            (candidate.candidate_type == "provider_review_patch" or candidate.source.get("provider")) and candidate.status in {"ready", "applied"}
            for candidate in candidates
        ):
            return normalize_json_document(
                {
                    "status": "skipped",
                    "reason": "ready provider candidate exists",
                    "created_count": 0,
                    "created_candidate_ids": [],
                }
            )
        context = self._prepare_provider_candidate_context(payload, {})
        result = self._generate_provider_task_result(
            project_id,
            task_store,
            task,
            payload,
            context,
            operation="review_sprint_action_provider_candidates",
        )
        self._mark_provider_context_used(
            context,
            {"usage_type": "review_sprint_action_provider_candidates", "project_id": project_id, "review_task_id": task.task_id},
        )
        self.project_store.append_event(
            project_id,
            "review_sprint_action_provider_candidates_generated",
            {"task_id": task.task_id, "candidate_count": _as_int(result.get("created_count")), "template_id": context.template.template_id},
        )
        result.pop("task_id", None)
        return result
