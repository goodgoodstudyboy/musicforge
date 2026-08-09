from __future__ import annotations

from song_agent.interfaces.bootstrap.api import creation_quality as _api_store_factories

from song_agent.platform.contracts.coercion import as_list as _as_list, list_or as _list_or

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext

from song_agent.platform.contracts.documents import JsonDocument

from .project_review_sprint_action_queues import CreationReviewSprintActionQueueRoutes


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class CreationRoutesProjectReviewSprint(CreationReviewSprintActionQueueRoutes, CreationRouteContext):
    def _handle_project_review_sprint_route_part_01(self, method: str, project_id: str, sprint_id: str, action: str, _split_state):
        self.project_store.get_project(project_id)
        project_dir = self.project_store.project_dir(project_id)
        _split_state["sprint_store"] = _api_store_factories.review_sprint_store(project_dir)
        _split_state["task_store"] = _api_store_factories.review_task_store(project_dir)
        _split_state["sprint"] = _split_state["sprint_store"].read_sprint(sprint_id)
        if _split_state["sprint"].project_id != project_id:
            raise FileNotFoundError(sprint_id)
        if action == "detail":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            self._send_json(self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], include_events=True))
            return (True, None)
        if action == "refresh":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["sprint"], _report = self._refresh_review_sprint_state(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"])
            self.project_store.append_event(
                project_id,
                "review_sprint_refreshed",
                {"sprint_id": _split_state["sprint"].sprint_id, "status": _split_state["sprint"].status},
            )
            self._send_json(self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"]))
            return (True, None)
        if action == "close":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["payload"] = self._optional_json_body()
            _split_state["sprint"], _report = self._refresh_review_sprint_state(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"])
            closeout_report = self._get_or_refresh_sprint_closeout(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], refresh=True)
            force = bool(_split_state["payload"].get("force", False))
            if not _interfaces_api_runtime.closeout_allows_close(closeout_report) and (not force):
                self._send_error(
                    _interfaces_api_runtime.HTTPStatus.CONFLICT,
                    "Review Sprint closeout gate failed. Refresh closeout report or pass force=true with override_reason.",
                )
                return (True, None)
            if force and (not str(_split_state["payload"].get("override_reason") or "").strip()):
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, "override_reason is required when force=true.")
                return (True, None)
            if force:
                closeout_report = _split_state["sprint_store"].write_closeout_report(
                    _split_state["sprint"],
                    _interfaces_api_runtime.mark_closeout_report_forced(closeout_report),
                    now=_interfaces_api_runtime._utc_now(),
                )
            signoff = _split_state["sprint_store"].read_signoff(_split_state["sprint"].sprint_id, default={})
            if not signoff:
                signoff = _split_state["sprint_store"].write_signoff(
                    _split_state["sprint"],
                    _interfaces_api_runtime.build_signoff_record(
                        project_id=project_id,
                        sprint=_split_state["sprint"],
                        closeout_report=closeout_report,
                        payload={**_split_state["payload"], "force": force},
                        now=_interfaces_api_runtime._utc_now(),
                    ),
                    now=_interfaces_api_runtime._utc_now(),
                )
            elif force and (not bool(signoff.get("forced", False))):
                raise _interfaces_api_runtime.ReviewSprintStateError("Review Sprint is already signed off.")
            event_name = "review_sprint_force_closed" if force else "review_sprint_closed"
            _split_state["sprint"] = _split_state["sprint_store"].close_sprint(_split_state["sprint"], now=_interfaces_api_runtime._utc_now())
            _split_state["sprint"] = _split_state["sprint_store"].refresh_summary(_split_state["sprint"], task_store=_split_state["task_store"], now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(
                project_id,
                event_name,
                {"sprint_id": _split_state["sprint"].sprint_id, "forced": force, "closeout_status": closeout_report.get("status")},
            )
            response = self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"])
            response.update(
                {
                    "closeout_report": closeout_report,
                    "closeout_summary": _interfaces_api_runtime.closeout_report_summary(closeout_report),
                    "signoff": signoff,
                    "signoff_summary": _interfaces_api_runtime.signoff_summary(signoff),
                }
            )
            self._send_json(response)
            return (True, None)
        if action == "archive":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["sprint"] = _split_state["sprint_store"].archive_sprint(_split_state["sprint"], now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "review_sprint_archived", {"sprint_id": _split_state["sprint"].sprint_id})
            self._send_json(self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"]))
            return (True, None)
        return (False, None)

    def _handle_project_review_sprint_route_part_02(self, method: str, project_id: str, sprint_id: str, action: str, _split_state):
        if action == "tasks":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["payload"] = self._optional_json_body()
            task_ids = _list_or(_split_state["payload"].get("task_ids"), [_split_state["payload"].get("task_id")] if _split_state["payload"].get("task_id") else [])
            _split_state["sprint"] = _split_state["sprint_store"].add_tasks(
                _split_state["sprint"],
                task_store=_split_state["task_store"],
                task_ids=[str(item) for item in task_ids],
                lane=str(_split_state["payload"].get("lane") or ""),
                notes=str(_split_state["payload"].get("notes") or ""),
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(project_id, "review_sprint_tasks_added", {"sprint_id": _split_state["sprint"].sprint_id, "task_ids": task_ids})
            self._send_json(self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"]))
            return (True, None)
        if action == "tasks-remove":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["payload"] = self._optional_json_body()
            task_ids = _list_or(_split_state["payload"].get("task_ids"), [_split_state["payload"].get("task_id")] if _split_state["payload"].get("task_id") else [])
            for _split_state["task_id"] in task_ids:
                _split_state["sprint"] = _split_state["sprint_store"].remove_task(_split_state["sprint"], str(_split_state["task_id"]), task_store=_split_state["task_store"], now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "review_sprint_tasks_removed", {"sprint_id": _split_state["sprint"].sprint_id, "task_ids": task_ids})
            self._send_json(self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"]))
            return (True, None)
        if action == "tasks-reorder":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["payload"] = self._optional_json_body()
            task_ids = _as_list(_split_state["payload"].get("task_ids"))
            _split_state["sprint"] = _split_state["sprint_store"].reorder_tasks(_split_state["sprint"], [str(item) for item in task_ids], task_store=_split_state["task_store"], now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "review_sprint_tasks_reordered", {"sprint_id": _split_state["sprint"].sprint_id, "task_ids": task_ids})
            self._send_json(self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"]))
            return (True, None)
        if action == "conflicts":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["report"] = _split_state["sprint_store"].read_conflict_report(_split_state["sprint"].sprint_id, default={})
            if not _split_state["report"]:
                _split_state["report"] = _split_state["sprint_store"].detect_conflicts(
                    _split_state["sprint"],
                    task_store=_split_state["task_store"],
                    parent_plan_hashes=self._review_sprint_parent_plan_hashes(project_id, _split_state["task_store"], _split_state["sprint"]),
                    now=_interfaces_api_runtime._utc_now(),
                )
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "conflict_report": _split_state["report"]})
            return (True, None)
        if action == "conflicts-refresh":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["sprint"], _split_state["report"] = self._refresh_review_sprint_state(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"])
            self.project_store.append_event(project_id, "review_sprint_conflicts_refreshed", {"sprint_id": _split_state["sprint"].sprint_id, "conflict_count": len(_split_state["report"].get("conflicts", []))})
            self._send_json(self._review_sprint_response(_split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"]))
            return (True, None)
        if action == "recommendations":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["report"] = _split_state["sprint_store"].read_recommendation_report(_split_state["sprint"].sprint_id, default={})
            if not _split_state["report"]:
                _split_state["report"] = self._refresh_review_sprint_recommendations(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"])
            self._send_json(
                {
                    "ok": True,
                    "sprint": _split_state["sprint"].to_dict(),
                    "recommendation_report": _split_state["report"],
                    "summary": _interfaces_api_runtime.recommendation_report_summary(_split_state["report"]),
                }
            )
            return (True, None)
        return (False, None)

    def _handle_project_review_sprint_route_part_03(self, method: str, project_id: str, sprint_id: str, action: str, _split_state):
        if action == "recommendations-refresh":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["sprint"], _split_state["_conflict_report"] = self._refresh_review_sprint_state(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"])
            _split_state["report"] = self._refresh_review_sprint_recommendations(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"])
            self.project_store.append_event(project_id, "review_sprint_recommendations_refreshed", {"sprint_id": _split_state["sprint"].sprint_id, "recommended_count": len(_split_state["report"].get("recommended_order", []))})
            self._send_json(
                {
                    "ok": True,
                    "sprint": _split_state["sprint"].to_dict(),
                    "recommendation_report": _split_state["report"],
                    "summary": _interfaces_api_runtime.recommendation_report_summary(_split_state["report"]),
                }
            )
            return (True, None)
        if action == "metrics":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["report"] = self._get_or_refresh_sprint_metrics(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], refresh=False)
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "metrics_report": _split_state["report"], "summary": _interfaces_api_runtime.sprint_metrics_summary(_split_state["report"])})
            return (True, None)
        if action == "metrics-refresh":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["report"] = self._get_or_refresh_sprint_metrics(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], refresh=True)
            _split_state["sprint_store"].append_event(
                _split_state["sprint"].sprint_id,
                "review_sprint_metrics_refreshed",
                {"readiness": (_split_state["report"].get("risk_readiness") or {}).get("readiness") if isinstance(_split_state["report"].get("risk_readiness"), dict) else None},
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(
                project_id,
                "review_sprint_metrics_refreshed",
                {
                    "sprint_id": _split_state["sprint"].sprint_id,
                    "readiness": (_split_state["report"].get("risk_readiness") or {}).get("readiness") if isinstance(_split_state["report"].get("risk_readiness"), dict) else None,
                },
            )
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "metrics_report": _split_state["report"], "summary": _interfaces_api_runtime.sprint_metrics_summary(_split_state["report"])})
            return (True, None)
        if action == "judge-summary":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            summary = self._get_or_refresh_sprint_judge_summary(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], refresh=False)
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "judge_summary": summary})
            return (True, None)
        if action == "judge-summary-refresh":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["payload"] = self._optional_json_body()
            summary = self._refresh_review_sprint_judge_reports(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], _split_state["payload"])
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "judge_summary": summary})
            return (True, None)
        if action == "closeout":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["report"] = self._get_or_refresh_sprint_closeout(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], refresh=False)
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "closeout_report": _split_state["report"], "summary": _interfaces_api_runtime.closeout_report_summary(_split_state["report"])})
            return (True, None)
        if action == "closeout-refresh":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["report"] = self._get_or_refresh_sprint_closeout(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], refresh=True)
            self.project_store.append_event(
                project_id,
                "review_sprint_closeout_refreshed",
                {"sprint_id": _split_state["sprint"].sprint_id, "status": _split_state["report"].get("status"), "readiness": _split_state["report"].get("readiness")},
            )
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "closeout_report": _split_state["report"], "summary": _interfaces_api_runtime.closeout_report_summary(_split_state["report"])})
            return (True, None)
        if action == "signoff":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            record = _split_state["sprint_store"].read_signoff(_split_state["sprint"].sprint_id, default={})
            self._send_json({"ok": True, "sprint": _split_state["sprint"].to_dict(), "signoff": record, "summary": _interfaces_api_runtime.signoff_summary(record)})
            return (True, None)
        return (False, None)

    def _handle_project_review_sprint_route_part_04(self, method: str, project_id: str, sprint_id: str, action: str, _split_state):
        if action == "action-queues":
            return self._handle_review_sprint_action_queues(method, project_id, _split_state)
        if action.startswith("action-queue:"):
            return self._handle_review_sprint_action_queue(method, project_id, action, _split_state)
        return (False, None)

    def _handle_project_review_sprint_route_part_05(self, method: str, project_id: str, sprint_id: str, action: str, _split_state):
        if action.startswith("recommendation-context-pack:"):
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["task_id"] = action.split(":", 1)[1]
            _split_state["payload"] = self._optional_json_body()
            _split_state["result"] = self._save_review_sprint_recommendation_context_pack(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], _split_state["task_id"], _split_state["payload"])
            self._send_json(_split_state["result"], status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if action == "generate-local-candidates":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["payload"] = self._optional_json_body()
            _split_state["result"] = self._generate_review_sprint_local_candidates(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], _split_state["payload"])
            self._send_json(_split_state["result"], status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
            return (True, None)
        if action == "generate-provider-candidates":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["payload"] = self._expand_context_pack_payload(self._optional_json_body())
            _split_state["result"] = self._generate_review_sprint_provider_candidates(project_id, _split_state["sprint_store"], _split_state["task_store"], _split_state["sprint"], _split_state["payload"])
            self._send_json(_split_state["result"], status=_interfaces_api_runtime.HTTPStatus.ACCEPTED)
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review sprint route not found.")
        return (False, None)

    def _handle_project_review_sprint_route(self, method: str, project_id: str, sprint_id: str, action: str) -> None:
        _split_state: dict[str, JsonDocument] = {}
        try:
            _split_result = self._handle_project_review_sprint_route_part_01(method, project_id, sprint_id, action, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_project_review_sprint_route_part_02(method, project_id, sprint_id, action, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_project_review_sprint_route_part_03(method, project_id, sprint_id, action, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_project_review_sprint_route_part_04(method, project_id, sprint_id, action, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_project_review_sprint_route_part_05(method, project_id, sprint_id, action, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review sprint not found.")
        except (_interfaces_api_runtime.ReviewSprintStateError, _interfaces_api_runtime.ReviewTaskStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ProviderError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except (_interfaces_api_runtime.ReviewSprintError, _interfaces_api_runtime.ReviewTaskError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _get_or_refresh_project_review_metrics(self, project_id: str, *, refresh: bool) -> JsonDocument:
        project_dir = self.project_store.project_dir(project_id)
        metrics_store = _api_store_factories.review_metrics_store(project_dir)
        if not refresh:
            existing = metrics_store.read_project_metrics(default={})
            if existing:
                return existing
        try:
            project_document = self.project_store.sync_project(project_id, self.store.get_job)
        except FileNotFoundError:
            project_document = self.project_store.get_project(project_id)
        sprint_store = _api_store_factories.review_sprint_store(project_dir)
        task_store = _api_store_factories.review_task_store(project_dir)
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
                        queue_store=_api_store_factories.review_sprint_action_queue_store(sprint_store.sprint_dir(sprint.sprint_id)),
                        provider_usage_records=provider_records,
                        now=saved.get("created_at") or _interfaces_api_runtime._utc_now(),
                    )
                    metrics_store.write_sprint_metrics(sprint.sprint_id, sprint_report)
                except (OSError, ValueError, TypeError, FileNotFoundError, _interfaces_api_runtime.json.JSONDecodeError):
                    continue
        return saved
