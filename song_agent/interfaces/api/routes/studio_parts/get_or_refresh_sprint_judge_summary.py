from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioRoutesGetOrRefreshSprintJudgeSummary:
    def _get_or_refresh_sprint_judge_summary(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        *,
        refresh: bool,
    ) -> dict[str, _interfaces_api_runtime.Any]:
        if not refresh:
            existing = sprint_store.read_judge_summary(sprint.sprint_id, default={})
            if existing:
                return existing
        reports = []
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                reports.append(self._read_review_task_judge_report(project_id, task_store, task, candidates))
            except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
                continue
        summary = _interfaces_api_runtime.sprint_judge_summary(sprint_id=sprint.sprint_id, task_reports=[report for report in reports if report], now=_interfaces_api_runtime._utc_now())
        return sprint_store.write_judge_summary(sprint, summary, now=_interfaces_api_runtime._utc_now())

    def _refresh_review_sprint_judge_reports(
        self,
        project_id: str,
        sprint_store: ReviewSprintStore,
        task_store: ReviewTaskStore,
        sprint: Any,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, _interfaces_api_runtime.Any]:
        payload = payload if isinstance(payload, dict) else {}
        requested = [str(item) for item in payload.get("task_ids", []) if str(item).strip()] if isinstance(payload.get("task_ids"), list) else []
        sprint_task_ids = self._review_sprint_ordered_task_ids(sprint)
        task_ids = [task_id for task_id in sprint_task_ids if not requested or task_id in requested]
        max_tasks = max(1, min(20, int(payload.get("max_tasks") or len(task_ids) or 1)))
        skip_existing = bool(payload.get("skip_existing_current", False))
        results = []
        processed = 0
        for task_id in task_ids:
            if processed >= max_tasks:
                results.append({"task_id": task_id, "status": "skipped", "reason": "max_tasks reached"})
                continue
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                ready = [candidate for candidate in candidates if candidate.status == "ready"]
                if not ready:
                    results.append({"task_id": task_id, "status": "skipped", "reason": "no ready candidates"})
                    continue
                existing = self._read_review_task_judge_report(project_id, task_store, task, candidates)
                if skip_existing and existing and existing.get("status") == "completed" and not existing.get("stale"):
                    results.append({"task_id": task_id, "status": "skipped", "reason": "current judge report exists", "summary": _interfaces_api_runtime.judge_report_summary(existing)})
                    continue
                result = self._refresh_review_task_judge_report(project_id, task_store, task, payload)
                results.append({"task_id": task_id, "status": "completed", "summary": result.get("summary", {})})
                processed += 1
            except (_interfaces_api_runtime.ReviewTaskStateError, _interfaces_api_runtime.ReviewTaskError, _interfaces_api_runtime.ProviderError, ValueError, FileNotFoundError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        summary = self._get_or_refresh_sprint_judge_summary(project_id, sprint_store, task_store, sprint, refresh=True)
        self.project_store.append_event(project_id, "review_sprint_judge_summary_refreshed", {"sprint_id": sprint.sprint_id, "judged_task_count": summary.get("judged_task_count")})
        return _interfaces_api_runtime.sanitize_metadata({**summary, "results": results})

    def _review_sprint_task_items(self, task_store: ReviewTaskStore, sprint: Any) -> list[dict[str, _interfaces_api_runtime.Any]]:
        items = []
        for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
            if not ref.get("included", True):
                continue
            task_id = str(ref.get("task_id") or "")
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                decision_report = _interfaces_api_runtime._try_read_review_decision_report(task_store, task.task_id)
                judge_report = self._read_review_task_judge_report(sprint.project_id, task_store, task, candidates)
                items.append(
                    {
                        "ref": ref,
                        "task": task.to_dict(),
                        "candidates": [candidate.to_dict() for candidate in candidates],
                        "decision_report": decision_report,
                        "judge_report": judge_report,
                        "judge_summary": _interfaces_api_runtime.judge_report_summary(judge_report),
                        "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(candidates),
                    }
                )
            except FileNotFoundError:
                items.append({"ref": ref, "task_id": task_id, "missing": True})
        return items

    def _refresh_review_sprint_state(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any) -> tuple[_interfaces_api_runtime.Any, dict[str, _interfaces_api_runtime.Any]]:
        parent_hashes = self._review_sprint_parent_plan_hashes(project_id, task_store, sprint)
        report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes=parent_hashes, now=_interfaces_api_runtime._utc_now())
        sprint = sprint_store.refresh_summary(sprint, task_store=task_store, now=_interfaces_api_runtime._utc_now())
        return sprint, report

    def _refresh_review_sprint_recommendations(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any) -> dict[str, _interfaces_api_runtime.Any]:
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        index = self.library_index_store.load_or_build(self.asset_store, self.reference_store)
        report = _interfaces_api_runtime.build_review_sprint_recommendation_report(
            project_id=project_id,
            sprint=sprint,
            task_store=task_store,
            sprint_store=sprint_store,
            library_index=index,
            project_document=project_document,
            now=_interfaces_api_runtime._utc_now(),
        )
        return sprint_store.write_recommendation_report(sprint, report, now=report.get("created_at") or _interfaces_api_runtime._utc_now())

    def _review_sprint_parent_plan_hashes(self, project_id: str, task_store: ReviewTaskStore, sprint: Any) -> dict[str, str]:
        hashes: dict[str, str] = {}
        version_ids = []
        for ref in sprint.task_refs:
            if not ref.get("included", True):
                continue
            try:
                task = task_store.read_task(str(ref.get("task_id") or ""))
            except FileNotFoundError:
                continue
            if task.project_id == project_id and task.parent_version_id not in version_ids:
                version_ids.append(task.parent_version_id)
        for version_id in version_ids:
            try:
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, version_id)
            except FileNotFoundError:
                continue
            hashes[version_id] = _interfaces_api_runtime.song_plan_hash(parent_plan)
        return hashes

    def _review_sprint_ordered_task_ids(self, sprint: Any) -> list[str]:
        task_ids = []
        for ref in sorted(sprint.task_refs, key=lambda item: int(item.get("order") or 0)):
            if ref.get("included", True) and ref.get("task_id"):
                task_ids.append(str(ref.get("task_id")))
        return task_ids

    def _review_sprint_membership_summary(self, project_id: str, task_id: str) -> dict[str, _interfaces_api_runtime.Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = _interfaces_api_runtime.ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                refs = [ref for ref in sprint.task_refs if ref.get("included", True)]
                if task_id not in {str(ref.get("task_id") or "") for ref in refs}:
                    continue
                summary = sprint_store.read_summary(sprint.sprint_id, default={})
                conflict_report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
                recommendation_report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                queue_store = _interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                queue_summary = _interfaces_api_runtime.action_queue_collection_summary(queue_store.list_queues(include_archived=True))
                judge_summary_data = sprint_store.read_judge_summary(sprint.sprint_id, default={})
                matches.append(_interfaces_api_runtime.review_sprint_export_summary(sprint, summary, conflict_report, recommendation_report, queue_summary, judge_summary_data))
            if not matches:
                return {}
            return _interfaces_api_runtime.sanitize_metadata({"sprint_ids": [item["sprint_id"] for item in matches], "primary": matches[0], "sprints": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
            return {}

    def _review_sprint_recommendation_summary_for_task(self, project_id: str, task_id: str) -> dict[str, _interfaces_api_runtime.Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = _interfaces_api_runtime.ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                if task_id not in self._review_sprint_ordered_task_ids(sprint):
                    continue
                report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                action = _interfaces_api_runtime._recommendation_action_for_task(report, task_id)
                if action:
                    matches.append(
                        {
                            "sprint_id": sprint.sprint_id,
                            "task_id": task_id,
                            "report_created_at": report.get("created_at"),
                            "rank": action.get("rank"),
                            "action": action.get("action"),
                            "score": action.get("score"),
                            "reason": action.get("reason"),
                            "context_ref_count": _interfaces_api_runtime._context_ref_count(action.get("context_pack_preview")),
                        }
                    )
            if not matches:
                return {}
            return _interfaces_api_runtime.sanitize_metadata({"primary": matches[0], "recommendations": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
            return {}

    def _review_sprint_action_queue_summary_for_task(self, project_id: str, task_id: str) -> dict[str, _interfaces_api_runtime.Any]:
        try:
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = _interfaces_api_runtime.ReviewSprintStore(project_dir)
            matches = []
            for sprint in sprint_store.list_sprints(include_archived=True):
                if task_id not in self._review_sprint_ordered_task_ids(sprint):
                    continue
                queue_store = _interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                for queue in queue_store.list_queues(include_archived=True):
                    related = [item for item in queue.items if item.task_id == task_id]
                    if not related:
                        continue
                    manual_apply = next((item for item in related if item.action == "manual_apply_candidate"), None)
                    primary_item = manual_apply or related[0]
                    matches.append(
                        {
                            "sprint_id": sprint.sprint_id,
                            "queue_id": queue.queue_id,
                            "task_id": task_id,
                            "status": queue.status,
                            "related_action": primary_item.action,
                            "related_item_id": primary_item.item_id,
                            "related_item_status": primary_item.status,
                        }
                    )
            if not matches:
                return {}
            return _interfaces_api_runtime.sanitize_metadata({"primary": matches[0], "queues": matches})
        except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
            return {}

    def _generate_review_sprint_local_candidates(self, project_id: str, sprint_store: ReviewSprintStore, task_store: ReviewTaskStore, sprint: Any, payload: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
        if sprint.status not in {"open", "in_progress", "blocked"}:
            raise _interfaces_api_runtime.ReviewSprintStateError(f"Cannot generate candidates for a {sprint.status} review sprint.")
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        stop_on_conflict = bool(payload.get("stop_on_conflict", sprint.settings.get("stop_on_conflict", False)))
        if stop_on_conflict and any(item.get("severity") == "blocking" for item in conflict_report.get("conflicts", [])):
            raise _interfaces_api_runtime.ReviewSprintStateError("Review sprint has blocking conflicts.")
        strategies = payload.get("strategies") if isinstance(payload.get("strategies"), list) else sprint.settings.get("local_candidate_strategies")
        render_midi = bool(payload.get("render_midi", sprint.settings.get("render_midi", True)))
        skip_existing = bool(payload.get("skip_existing_ready", True))
        results = []
        created_total = 0
        for task_id in self._review_sprint_ordered_task_ids(sprint):
            try:
                task = task_store.read_task(task_id)
                candidates = task_store.list_candidates(task.task_id)
                if skip_existing and any(candidate.candidate_type == "local_review_intents" and candidate.status in {"ready", "applied"} for candidate in candidates):
                    results.append({"task_id": task.task_id, "status": "skipped", "reason": "ready local candidate exists"})
                    continue
                _document, _parent, _parent_job, parent_plan = self._project_edit_parent(project_id, task.parent_version_id)
                _interfaces_api_runtime.ensure_task_current(task, parent_plan)
                generated = []
                for candidate, candidate_plan, validator, summary in _interfaces_api_runtime.build_local_review_candidates(task, parent_plan, strategies=strategies):
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
                decision_report = task_store.write_decision_report(task, _interfaces_api_runtime.build_review_decision_report(task=task, candidates=ranked, parent_plan=parent_plan, now=_interfaces_api_runtime._utc_now()), now=_interfaces_api_runtime._utc_now())
                created_total += len(generated)
                results.append(
                    {
                        "task_id": task.task_id,
                        "status": "generated" if generated else "skipped",
                        "created_count": len(generated),
                        "created_candidate_ids": [candidate.candidate_id for candidate in generated],
                        "decision_report": _interfaces_api_runtime.review_decision_summary(decision_report),
                        "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(ranked),
                    }
                )
            except (FileNotFoundError, _interfaces_api_runtime.ReviewTaskError, _interfaces_api_runtime.ReviewTaskStateError, ValueError) as exc:
                results.append({"task_id": task_id, "status": "failed", "error": str(exc)})
        sprint, conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
        self.project_store.append_event(project_id, "review_sprint_local_candidates_generated", {"sprint_id": sprint.sprint_id, "created_count": created_total})
        response = self._review_sprint_response(sprint_store, task_store, sprint)
        response.update({"results": _interfaces_api_runtime.sanitize_metadata(results), "created_count": created_total})
        return response
