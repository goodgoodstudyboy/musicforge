from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesProjectReviewSprint:
    def _handle_project_review_sprint_route(self, method: str, project_id: str, sprint_id: str, action: str) -> None:
        try:
            self.project_store.get_project(project_id)
            project_dir = self.project_store.project_dir(project_id)
            sprint_store = _interfaces_api_runtime.ReviewSprintStore(project_dir)
            task_store = _interfaces_api_runtime.ReviewTaskStore(project_dir)
            sprint = sprint_store.read_sprint(sprint_id)
            if sprint.project_id != project_id:
                raise FileNotFoundError(sprint_id)
            if action == "detail":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint, include_events=True))
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_refreshed", {"sprint_id": sprint.sprint_id, "status": sprint.status})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "close":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                sprint, _report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                closeout_report = self._get_or_refresh_sprint_closeout(project_id, sprint_store, task_store, sprint, refresh=True)
                force = bool(payload.get("force", False))
                if not _interfaces_api_runtime.closeout_allows_close(closeout_report) and not force:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, "Review Sprint closeout gate failed. Refresh closeout report or pass force=true with override_reason.")
                    return
                if force and not str(payload.get("override_reason") or "").strip():
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "override_reason is required when force=true.")
                    return
                if force:
                    closeout_report = sprint_store.write_closeout_report(sprint, _interfaces_api_runtime.mark_closeout_report_forced(closeout_report), now=_interfaces_api_runtime._utc_now())
                signoff = sprint_store.read_signoff(sprint.sprint_id, default={})
                if not signoff:
                    signoff = sprint_store.write_signoff(sprint, _interfaces_api_runtime.build_signoff_record(project_id=project_id, sprint=sprint, closeout_report=closeout_report, payload={**payload, "force": force}, now=_interfaces_api_runtime._utc_now()), now=_interfaces_api_runtime._utc_now())
                elif force and not bool(signoff.get("forced", False)):
                    raise _interfaces_api_runtime.ReviewSprintStateError("Review Sprint is already signed off.")
                event_name = "review_sprint_force_closed" if force else "review_sprint_closed"
                sprint = sprint_store.close_sprint(sprint, now=_interfaces_api_runtime._utc_now())
                sprint = sprint_store.refresh_summary(sprint, task_store=task_store, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, event_name, {"sprint_id": sprint.sprint_id, "forced": force, "closeout_status": closeout_report.get("status")})
                response = self._review_sprint_response(sprint_store, task_store, sprint)
                response.update({"closeout_report": closeout_report, "closeout_summary": _interfaces_api_runtime.closeout_report_summary(closeout_report), "signoff": signoff, "signoff_summary": _interfaces_api_runtime.signoff_summary(signoff)})
                self._send_json(response)
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = sprint_store.archive_sprint(sprint, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "review_sprint_archived", {"sprint_id": sprint.sprint_id})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else ([payload.get("task_id")] if payload.get("task_id") else [])
                sprint = sprint_store.add_tasks(
                    sprint,
                    task_store=task_store,
                    task_ids=[str(item) for item in task_ids],
                    lane=str(payload.get("lane") or ""),
                    notes=str(payload.get("notes") or ""),
                    now=_interfaces_api_runtime._utc_now(),
                )
                self.project_store.append_event(project_id, "review_sprint_tasks_added", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks-remove":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else ([payload.get("task_id")] if payload.get("task_id") else [])
                for task_id in task_ids:
                    sprint = sprint_store.remove_task(sprint, str(task_id), task_store=task_store, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "review_sprint_tasks_removed", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "tasks-reorder":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                task_ids = payload.get("task_ids") if isinstance(payload.get("task_ids"), list) else []
                sprint = sprint_store.reorder_tasks(sprint, [str(item) for item in task_ids], task_store=task_store, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "review_sprint_tasks_reordered", {"sprint_id": sprint.sprint_id, "task_ids": task_ids})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "conflicts":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = sprint_store.read_conflict_report(sprint.sprint_id, default={})
                if not report:
                    report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes=self._review_sprint_parent_plan_hashes(project_id, task_store, sprint), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "conflict_report": report})
                return
            if action == "conflicts-refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_conflicts_refreshed", {"sprint_id": sprint.sprint_id, "conflict_count": len(report.get("conflicts", []))})
                self._send_json(self._review_sprint_response(sprint_store, task_store, sprint))
                return
            if action == "recommendations":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                if not report:
                    report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "recommendation_report": report, "summary": _interfaces_api_runtime.recommendation_report_summary(report)})
                return
            if action == "recommendations-refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint, _conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                self.project_store.append_event(project_id, "review_sprint_recommendations_refreshed", {"sprint_id": sprint.sprint_id, "recommended_count": len(report.get("recommended_order", []))})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "recommendation_report": report, "summary": _interfaces_api_runtime.recommendation_report_summary(report)})
                return
            if action == "metrics":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_metrics(project_id, sprint_store, task_store, sprint, refresh=False)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "metrics_report": report, "summary": _interfaces_api_runtime.sprint_metrics_summary(report)})
                return
            if action == "metrics-refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_metrics(project_id, sprint_store, task_store, sprint, refresh=True)
                sprint_store.append_event(sprint.sprint_id, "review_sprint_metrics_refreshed", {"readiness": (report.get("risk_readiness") or {}).get("readiness") if isinstance(report.get("risk_readiness"), dict) else None}, now=_interfaces_api_runtime._utc_now())
                self.project_store.append_event(project_id, "review_sprint_metrics_refreshed", {"sprint_id": sprint.sprint_id, "readiness": (report.get("risk_readiness") or {}).get("readiness") if isinstance(report.get("risk_readiness"), dict) else None})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "metrics_report": report, "summary": _interfaces_api_runtime.sprint_metrics_summary(report)})
                return
            if action == "judge-summary":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                summary = self._get_or_refresh_sprint_judge_summary(project_id, sprint_store, task_store, sprint, refresh=False)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "judge_summary": summary})
                return
            if action == "judge-summary-refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                summary = self._refresh_review_sprint_judge_reports(project_id, sprint_store, task_store, sprint, payload)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "judge_summary": summary})
                return
            if action == "closeout":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_closeout(project_id, sprint_store, task_store, sprint, refresh=False)
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "closeout_report": report, "summary": _interfaces_api_runtime.closeout_report_summary(report)})
                return
            if action == "closeout-refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self._get_or_refresh_sprint_closeout(project_id, sprint_store, task_store, sprint, refresh=True)
                self.project_store.append_event(project_id, "review_sprint_closeout_refreshed", {"sprint_id": sprint.sprint_id, "status": report.get("status"), "readiness": report.get("readiness")})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "closeout_report": report, "summary": _interfaces_api_runtime.closeout_report_summary(report)})
                return
            if action == "signoff":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                record = sprint_store.read_signoff(sprint.sprint_id, default={})
                self._send_json({"ok": True, "sprint": sprint.to_dict(), "signoff": record, "summary": _interfaces_api_runtime.signoff_summary(record)})
                return
            if action == "action-queues":
                queue_store = _interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                if method == "GET":
                    queues = queue_store.list_queues(include_archived=True)
                    self._send_json({"ok": True, "sprint": sprint.to_dict(), "queues": [queue.to_dict() for queue in queues], "latest_queue": queues[0].to_dict() if queues else {}, "summary": _interfaces_api_runtime.action_queue_collection_summary(queues)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    if bool(payload.get("refresh_recommendations", True)):
                        sprint, _conflict_report = self._refresh_review_sprint_state(project_id, sprint_store, task_store, sprint)
                        report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                    else:
                        report = sprint_store.read_recommendation_report(sprint.sprint_id, default={})
                        if not report:
                            report = self._refresh_review_sprint_recommendations(project_id, sprint_store, task_store, sprint)
                    queue = _interfaces_api_runtime.build_action_queue_from_recommendation_report(
                        project_id=project_id,
                        sprint=sprint,
                        recommendation_report=report,
                        name=str(payload.get("name") or "") or None,
                        settings=payload.get("settings") if isinstance(payload.get("settings"), dict) else {},
                        now=_interfaces_api_runtime._utc_now(),
                    )
                    created = queue_store.create_queue(queue, now=_interfaces_api_runtime._utc_now())
                    self.project_store.append_event(project_id, "review_sprint_action_queue_created", {"sprint_id": sprint.sprint_id, "queue_id": created.queue_id, "item_count": len(created.items)})
                    self._send_json({"ok": True, "sprint": sprint.to_dict(), "queue": created.to_dict(), "summary": _interfaces_api_runtime.action_queue_summary(created)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if action.startswith("action-queue:"):
                queue_id, queue_action = action.split(":", 2)[1:]
                queue_store = _interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
                if queue_action == "detail":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    queue = queue_store.read_queue(queue_id)
                    if queue.project_id != project_id or queue.sprint_id != sprint.sprint_id:
                        raise FileNotFoundError(queue_id)
                    self._send_json({"ok": True, "sprint": sprint.to_dict(), "queue": queue.to_dict(), "events": queue_store.read_events(queue.queue_id), "summary": _interfaces_api_runtime.action_queue_summary(queue)})
                    return
                if queue_action == "run":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    result = self._run_review_sprint_action_queue(project_id, sprint_store, task_store, sprint, queue_store, queue_id, payload)
                    self._send_json(result)
                    return
                if queue_action == "archive":
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    queue = queue_store.read_queue(queue_id)
                    if queue.project_id != project_id or queue.sprint_id != sprint.sprint_id:
                        raise FileNotFoundError(queue_id)
                    archived = queue_store.archive_queue(queue.queue_id, now=_interfaces_api_runtime._utc_now())
                    self.project_store.append_event(project_id, "review_sprint_action_queue_archived", {"sprint_id": sprint.sprint_id, "queue_id": archived.queue_id})
                    self._send_json({"ok": True, "queue": archived.to_dict(), "summary": _interfaces_api_runtime.action_queue_summary(archived)})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review sprint action queue route not found.")
                return
            if action.startswith("recommendation-context-pack:"):
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                task_id = action.split(":", 1)[1]
                payload = self._optional_json_body()
                result = self._save_review_sprint_recommendation_context_pack(project_id, sprint_store, task_store, sprint, task_id, payload)
                self._send_json(result, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "generate-local-candidates":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = self._generate_review_sprint_local_candidates(project_id, sprint_store, task_store, sprint, payload)
                self._send_json(result, status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
                return
            if action == "generate-provider-candidates":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._expand_context_pack_payload(self._optional_json_body())
                result = self._generate_review_sprint_provider_candidates(project_id, sprint_store, task_store, sprint, payload)
                self._send_json(result, status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review sprint route not found.")
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review sprint not found.")
        except (_interfaces_api_runtime.ReviewSprintStateError, _interfaces_api_runtime.ReviewTaskStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ProviderError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except (_interfaces_api_runtime.ReviewSprintError, _interfaces_api_runtime.ReviewTaskError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _get_or_refresh_project_review_metrics(self, project_id: str, *, refresh: bool) -> dict[str, _interfaces_api_runtime.Any]:
        project_dir = self.project_store.project_dir(project_id)
        metrics_store = _interfaces_api_runtime.ReviewMetricsStore(project_dir)
        if not refresh:
            existing = metrics_store.read_project_metrics(default={})
            if existing:
                return existing
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        sprint_store = _interfaces_api_runtime.ReviewSprintStore(project_dir)
        task_store = _interfaces_api_runtime.ReviewTaskStore(project_dir)
        provider_records = _interfaces_api_runtime.collect_project_provider_usage_records(project_id, project_document.versions, project_dir)
        report = _interfaces_api_runtime.build_project_review_metrics(
            project_id=project_id,
            project_document=project_document,
            sprint_store=sprint_store,
            task_store=task_store,
            provider_usage_records=provider_records,
            now=_interfaces_api_runtime._utc_now(),
        )
        saved = metrics_store.write_project_metrics(report)
        for summary in saved.get("sprint_summaries", []) if isinstance(saved.get("sprint_summaries"), list) else []:
            sprint_id = str(summary.get("sprint_id") or "")
            if sprint_id:
                try:
                    sprint = sprint_store.read_sprint(sprint_id)
                    sprint_report = _interfaces_api_runtime.build_sprint_metrics_report(
                        project_id=project_id,
                        sprint=sprint,
                        project_document=project_document,
                        task_store=task_store,
                        sprint_store=sprint_store,
                        queue_store=_interfaces_api_runtime.ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id)),
                        provider_usage_records=provider_records,
                        now=saved.get("created_at") or _interfaces_api_runtime._utc_now(),
                    )
                    metrics_store.write_sprint_metrics(sprint.sprint_id, sprint_report)
                except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
                    continue
        return saved
