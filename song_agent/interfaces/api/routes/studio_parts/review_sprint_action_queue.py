from __future__ import annotations

from song_agent.application.http_ports import studio as studio_ports
from song_agent.application.http_ports.studio import (
    ReviewCandidate,
    ReviewSprint,
    ReviewTask,
    SongPlan,
    SprintActionItem,
    SprintActionQueue,
)
from song_agent.platform.contracts.coercion import (
    as_document as _as_document,
    as_list as _as_list,
    as_string_list as _as_string_list,
)
from song_agent.interfaces.api.route_contexts.studio import StudioRouteContext

from song_agent.platform.contracts.documents import JsonDocument

from song_agent.application.interface_persistence import write_interface_document
from song_agent.interfaces.api.routes.studio_parts.review_sprint_action_queue_completion import StudioReviewSprintActionQueueCompletion

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioRoutesReviewSprintActionQueue(StudioReviewSprintActionQueueCompletion, StudioRouteContext):
    def _run_review_sprint_action_queue(
        self,
        project_id: str,
        sprint_store: studio_ports.ReviewSprintStore,
        task_store: studio_ports.ReviewTaskStore,
        sprint: ReviewSprint,
        queue_store: studio_ports.ReviewSprintActionQueueStore,
        queue_id: str,
        payload: JsonDocument,
    ) -> JsonDocument:
        queue = queue_store.read_queue(queue_id)
        if queue.project_id != project_id or queue.sprint_id != sprint.sprint_id:
            raise FileNotFoundError(queue_id)
        if queue.status == "archived":
            raise _interfaces_api_runtime.ReviewSprintStateError("Archived action queue cannot be run.")
        selected_ids, include_provider, rerun_failed, stop_on_failure = self._action_queue_run_options(queue, payload)
        results: list[JsonDocument] = []
        queue = queue_store.update_queue(
            _interfaces_api_runtime.replace(queue, status="running"),
            event="queue_run_started",
            payload={"selected_item_ids": selected_ids, "include_provider": include_provider},
            now=_interfaces_api_runtime._utc_now(),
        )
        self.project_store.append_event(project_id, "review_sprint_action_queue_started", {"sprint_id": sprint.sprint_id, "queue_id": queue.queue_id})
        provider_runs, max_provider = 0, int(queue.settings.get("max_provider_actions") or 3)
        for item in _interfaces_api_runtime._select_action_queue_items(queue, selected_ids, rerun_failed=rerun_failed):
            if item.safety == "provider_safe" and not include_provider:
                results.append({"item_id": item.item_id, "status": "skipped", "reason": "provider action requires include_provider=true"})
                continue
            if item.safety == "provider_safe":
                if provider_runs >= max_provider:
                    item = self._set_action_item(
                        queue_store,
                        queue,
                        item,
                        status="blocked",
                        error="Provider action limit reached for this queue run.",
                        event="item_blocked",
                    )
                    queue = queue_store.read_queue(queue.queue_id)
                    results.append({"item_id": item.item_id, "status": item.status, "error": item.error})
                    if stop_on_failure:
                        break
                    continue
                provider_runs += 1
            item = self._set_action_item(queue_store, queue, item, status="running", event="item_started")
            queue = queue_store.read_queue(queue.queue_id)
            try:
                item = self._execute_review_sprint_action_item(project_id, sprint_store, task_store, sprint, queue, item)
                event = "item_blocked" if item.status == "blocked" else ("item_skipped" if item.status == "skipped" else "item_completed")
                item = self._set_action_item(queue_store, queue, item, status=item.status, result=item.result, error=item.error, event=event)
                self.project_store.append_event(
                    project_id,
                    "review_sprint_action_item_completed",
                    {
                        "sprint_id": sprint.sprint_id,
                        "queue_id": queue.queue_id,
                        "item_id": item.item_id,
                        "status": item.status,
                        "action": item.action,
                    },
                )
                results.append({"item_id": item.item_id, "status": item.status, "result": item.result, "error": item.error})
            except (
                _interfaces_api_runtime.ReviewSprintStateError,
                _interfaces_api_runtime.ReviewTaskStateError,
                _interfaces_api_runtime.ContextPackStaleError,
            ) as exc:
                item = self._set_action_item(queue_store, queue, item, status="blocked", error=str(exc), event="item_blocked")
                results.append({"item_id": item.item_id, "status": item.status, "error": item.error})
                if stop_on_failure:
                    break
            except (_interfaces_api_runtime.ProviderError, _interfaces_api_runtime.ReviewTaskError, ValueError, FileNotFoundError) as exc:
                item = self._set_action_item(queue_store, queue, item, status="failed", error=str(exc), event="item_failed")
                results.append({"item_id": item.item_id, "status": item.status, "error": item.error})
                if stop_on_failure:
                    break
            finally:
                queue = queue_store.read_queue(queue.queue_id)
        return self._complete_review_sprint_action_queue(project_id, sprint_store, task_store, sprint, queue_store, queue, results)

    @staticmethod
    def _action_queue_run_options(queue: SprintActionQueue, payload: JsonDocument) -> tuple[list[str], bool, bool, bool]:
        return (
            _as_string_list(payload.get("item_ids")),
            bool(payload.get("include_provider", queue.settings.get("run_provider_actions", False))),
            bool(payload.get("rerun_failed", False)),
            bool(payload.get("stop_on_failure", queue.settings.get("stop_on_failure", False))),
        )

    def _execute_review_sprint_action_item(
        self,
        project_id: str,
        sprint_store: studio_ports.ReviewSprintStore,
        task_store: studio_ports.ReviewTaskStore,
        sprint: ReviewSprint,
        queue: SprintActionQueue,
        item: SprintActionItem,
    ) -> SprintActionItem:
        if item.safety in {"manual_required", "informational"}:
            return _interfaces_api_runtime.replace(
                item,
                status="manual_required" if item.safety == "manual_required" else "skipped",
                completed_at=_interfaces_api_runtime._utc_now(),
            )
        if item.safety == "blocked":
            return _interfaces_api_runtime.replace(item, status="blocked", error=item.error or "Action item is blocked.", completed_at=_interfaces_api_runtime._utc_now())
        if item.action == "refresh_conflicts":
            sprint, report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
            return _interfaces_api_runtime.replace(
                item,
                status="completed",
                result={"conflict_count": len(_as_list(report.get("conflicts")))},
                completed_at=_interfaces_api_runtime._utc_now(),
            )
        if item.action == "refresh_recommendations":
            sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
            report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
            return _interfaces_api_runtime.replace(
                item,
                status="completed",
                result={"recommended_count": len(_as_list(report.get("recommended_order"))), "created_at": report.get("created_at")},
                completed_at=_interfaces_api_runtime._utc_now(),
            )
        report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
        if _interfaces_api_runtime.queue_report_is_stale(queue, report):
            return _interfaces_api_runtime.replace(
                item,
                status="blocked",
                error="Action queue is stale because the Recommendation Report changed. Recreate the queue.",
                completed_at=_interfaces_api_runtime._utc_now(),
            )
        task = self._ensure_action_item_task_current(project_id, task_store, sprint, item)
        if item.action == "save_recommended_context_pack":
            result = self._execute_queue_context_pack_action(project_id, sprint_store, task_store, sprint, item)
        elif item.action == "generate_local_candidates":
            result = self._generate_review_task_local_candidates_for_queue(project_id, task_store, task, item.input)
        elif item.action == "generate_provider_candidates":
            result = self._generate_review_task_provider_candidates_for_queue(project_id, task_store, task, item.input)
        elif item.action == "refresh_judge_report":
            result = self._refresh_review_task_judge_report(project_id, task_store, task, item.input)
            result["sprint_judge_summary"] = self._get_or_refresh_sprint_judge_summary(project_id, sprint_store, task_store, sprint, refresh=True)
        elif item.action == "refresh_decision_report":
            result = self._refresh_review_task_decision_report_for_queue(project_id, task_store, task, item.input)
        else:
            result = {"message": "Action is not executable from the queue."}
            return _interfaces_api_runtime.replace(item, status="skipped", result=result, completed_at=_interfaces_api_runtime._utc_now())
        self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint_store.read_sprint(sprint.sprint_id))
        return _interfaces_api_runtime.replace(
            item,
            status="completed",
            result=_interfaces_api_runtime.sanitize_metadata(result),
            error=None,
            completed_at=_interfaces_api_runtime._utc_now(),
        )

    def _ensure_action_item_task_current(
        self,
        project_id: str,
        task_store: studio_ports.ReviewTaskStore,
        sprint: ReviewSprint,
        item: SprintActionItem,
    ) -> ReviewTask:
        if not item.task_id or item.task_id not in self._review_sprint_ordered_task_ids(sprint):
            raise _interfaces_api_runtime.ReviewSprintStateError("Action item task is no longer in this sprint.")
        task = task_store.read_task(item.task_id)
        if task.project_id != project_id:
            raise FileNotFoundError(item.task_id)
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        _interfaces_api_runtime.ensure_task_current(task, parent_plan)
        return task

    def _generate_review_task_local_candidates_for_queue(
        self,
        project_id: str,
        task_store: studio_ports.ReviewTaskStore,
        task: ReviewTask,
        payload: JsonDocument,
    ) -> JsonDocument:
        candidates = task_store.list_candidates(task.task_id)
        if bool(payload.get("skip_existing_ready", True)) and any(candidate.candidate_type == "local_review_intents" and candidate.status in {"ready", "applied"} for candidate in candidates):
            return {"status": "skipped", "reason": "ready local candidate exists", "created_count": 0, "created_candidate_ids": []}
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        _interfaces_api_runtime.ensure_task_current(task, parent_plan)
        strategies = _as_string_list(payload.get("strategies")) or ["balanced"]
        render_midi = bool(payload.get("render_midi", True))
        generated = []
        for candidate, candidate_plan, validator, summary in _interfaces_api_runtime.build_local_review_candidates(task, parent_plan, strategies=strategies):
            generated.append(
                task_store.create_candidate(
                    task=task,
                    candidate=candidate,
                    candidate_plan=candidate_plan,
                    validator=validator,
                    summary=summary,
                    render_midi_file=render_midi,
                    now=_interfaces_api_runtime._utc_now(),
                )
            )
        ranked = task_store.rank_candidates(task)
        updated_task = task_store.update_counts(task, now=_interfaces_api_runtime._utc_now())
        decision_report = task_store.write_decision_report(
            updated_task,
            _interfaces_api_runtime.build_review_decision_report(task=updated_task, candidates=ranked, parent_plan=parent_plan, now=_interfaces_api_runtime._utc_now()),
            now=_interfaces_api_runtime._utc_now(),
        )
        self.project_store.append_event(project_id, "review_sprint_action_local_candidates_generated", {"task_id": task.task_id, "candidate_count": len(generated)})
        return {
            "status": "generated" if generated else "skipped",
            "created_count": len(generated),
            "created_candidate_ids": [candidate.candidate_id for candidate in generated],
            "decision_report": _interfaces_api_runtime.review_decision_summary(decision_report),
            "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(ranked),
        }

    def _read_review_task_judge_report(
        self,
        project_id: str,
        task_store: studio_ports.ReviewTaskStore,
        task: ReviewTask,
        candidates: list[ReviewCandidate] | None = None,
        *,
        parent_plan: SongPlan | None = None,
    ) -> JsonDocument:
        report = task_store.read_judge_report(task.task_id, default={})
        if not report:
            return {}
        try:
            if parent_plan is None:
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
            template_id = str(report.get("template_id") or _interfaces_api_runtime.REVIEW_JUDGE_TEMPLATE_ID)
            template = self.prompt_template_store.get_template(template_id)
            return _interfaces_api_runtime.read_judge_report_with_stale(task_store, task, candidates=candidates, parent_plan=parent_plan, template=template)
        except (FileNotFoundError, _interfaces_api_runtime.ProviderError, _interfaces_api_runtime.ReviewTaskError, _interfaces_api_runtime.ReviewTaskStateError, ValueError, TypeError):
            return _interfaces_api_runtime.mark_judge_report_stale(report, stale=True)

    def _refresh_review_task_judge_report(
        self,
        project_id: str,
        task_store: studio_ports.ReviewTaskStore,
        task: ReviewTask,
        payload: JsonDocument | None = None,
    ) -> JsonDocument:
        payload = _as_document(payload)
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        _interfaces_api_runtime.ensure_task_current(task, parent_plan)
        template_id = str(payload.get("template_id") or _interfaces_api_runtime.REVIEW_JUDGE_TEMPLATE_ID).strip()
        template = self.prompt_template_store.get_template(template_id)
        if not template.enabled:
            raise _interfaces_api_runtime.ReviewTaskStateError("Prompt template is disabled.")
        all_candidates = task_store.rank_candidates(task)
        requested_ids = _as_string_list(payload.get("candidate_ids"))
        candidates = [candidate for candidate in all_candidates if not requested_ids or candidate.candidate_id in requested_ids]
        candidates = [candidate for candidate in candidates if candidate.status == "ready"]
        if not candidates:
            raise _interfaces_api_runtime.ReviewTaskStateError("Review judge requires at least one ready candidate.")
        decision_report = _interfaces_api_runtime._try_read_review_decision_report(task_store, task.task_id)
        config, _sources = _interfaces_api_runtime.load_provider_config()
        started_at = _interfaces_api_runtime._utc_now()
        report, provider_snapshot = _interfaces_api_runtime.run_provider_review_judge(
            project_id=project_id,
            task=task,
            candidates=candidates,
            parent_plan=parent_plan,
            template=template,
            config=config,
            decision_report=decision_report,
            note=str(payload.get("note") or ""),
            now=_interfaces_api_runtime._utc_now(),
        )
        saved = task_store.write_judge_report(task, report, now=_interfaces_api_runtime._utc_now())
        provider_usage = _as_document(provider_snapshot.get("usage"))
        usage_record = _interfaces_api_runtime._provider_usage_record(
            config_snapshot=provider_snapshot,
            operation="provider_review_judge",
            template_id=template.template_id,
            started_at=started_at,
            status="completed",
            provider_usage=provider_usage,
            request_id=provider_snapshot.get("request_id"),
        )
        write_interface_document(task_store.judge_provider_usage_path(task.task_id), usage_record)
        ranked = task_store.rank_candidates(task)
        refreshed_decision = task_store.write_decision_report(
            task,
            _interfaces_api_runtime.build_review_decision_report(
                task=task,
                candidates=ranked,
                parent_plan=parent_plan,
                now=_interfaces_api_runtime._utc_now(),
                notes=str(payload.get("decision_note") or ""),
                judge_report=saved,
            ),
            now=_interfaces_api_runtime._utc_now(),
        )
        self.project_store.append_event(
            project_id,
            "review_task_judge_report_refreshed",
            {
                "task_id": task.task_id,
                "recommended_candidate_id": saved.get("recommended_candidate_id"),
                "template_id": template.template_id,
            },
        )
        return {
            "ok": True,
            "task": task.to_dict(),
            "judge_report": saved,
            "summary": _interfaces_api_runtime.judge_report_summary(saved),
            "decision_report": refreshed_decision,
            "provider_snapshot": provider_snapshot,
        }

    def _refresh_review_task_decision_report_for_queue(
        self,
        project_id: str,
        task_store: studio_ports.ReviewTaskStore,
        task: ReviewTask,
        payload: JsonDocument,
    ) -> JsonDocument:
        _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
        _interfaces_api_runtime.ensure_task_current(task, parent_plan)
        ranked = task_store.rank_candidates(task)
        judge_report = self._read_review_task_judge_report(project_id, task_store, task, ranked, parent_plan=parent_plan)
        decision_report = task_store.write_decision_report(
            task,
            _interfaces_api_runtime.build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_interfaces_api_runtime._utc_now(), notes=str(payload.get("note") or ""), judge_report=judge_report),
            now=_interfaces_api_runtime._utc_now(),
        )
        self.project_store.append_event(project_id, "review_sprint_action_decision_report_refreshed", {"task_id": task.task_id, "recommended_candidate_id": decision_report.get("recommended_candidate_id")})
        return {
            "decision_report": _interfaces_api_runtime.review_decision_summary(decision_report),
            "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(ranked),
            "candidate_count": len(ranked),
        }

    def _set_action_item(
        self,
        queue_store: studio_ports.ReviewSprintActionQueueStore,
        queue: SprintActionQueue,
        item: SprintActionItem,
        *,
        status: str,
        result: JsonDocument | None = None,
        error: str | None = None,
        event: str | None = None,
    ) -> SprintActionItem:
        now = _interfaces_api_runtime._utc_now()
        updated_item = _interfaces_api_runtime.replace(
            item,
            status=status,
            result=_interfaces_api_runtime.sanitize_metadata(result if result is not None else item.result),
            error=None if error is None else str(_interfaces_api_runtime.sanitize_metadata({"error": error}).get("error") or ""),
            started_at=now if status == "running" else item.started_at,
            completed_at=now if status in {"completed", "failed", "skipped", "blocked", "manual_required"} else item.completed_at,
            attempt=item.attempt + 1 if status == "running" else item.attempt,
        )
        items = [updated_item if existing.item_id == item.item_id else existing for existing in queue.items]
        updated_queue = _interfaces_api_runtime.replace(queue, items=items)
        queue_store.update_queue(updated_queue, event=event, payload={"item_id": item.item_id, "action": item.action, "status": status}, now=now)
        return updated_item
