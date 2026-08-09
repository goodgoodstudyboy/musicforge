from __future__ import annotations

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class CreationReviewTaskReportsLifecycleRoutes(CreationRouteContext):
    def _handle_project_review_task_route_part_03(self, method: str, project_id: str, task_id: str, action: str, state):
        if action in {"decision-report", "decision-report-refresh"}:
            return self._handle_review_task_decision_report(method, project_id, action, state)
        if action in {"judge-report", "judge-report-refresh"}:
            return self._handle_review_task_judge_report(method, project_id, action, state)
        if action in {"resolve", "needs-more-work", "archive"}:
            return self._handle_review_task_lifecycle(method, project_id, action, state)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review task route not found.")
        return (False, None)

    def _handle_review_task_decision_report(self, method: str, project_id: str, action: str, state):
        expected_method = "GET" if action == "decision-report" else "POST"
        if method != expected_method:
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return (True, None)
        state["candidates"] = state["task_store"].rank_candidates(state["task"])
        if action == "decision-report":
            state["decision_report"] = _interfaces_api_runtime._try_read_review_decision_report(state["task_store"], state["task"].task_id)
            if not state["decision_report"]:
                state["_document"], _parent, state["_parent_job"], state["parent_plan"] = self._project_edit_parent(project_id, state["task"].parent_version_id)
                state["judge_report"] = self._read_review_task_judge_report(project_id, state["task_store"], state["task"], state["candidates"], parent_plan=state["parent_plan"])
                state["decision_report"] = state["task_store"].write_decision_report(
                    state["task"],
                    _interfaces_api_runtime.build_review_decision_report(task=state["task"], candidates=state["candidates"], parent_plan=state["parent_plan"], now=_interfaces_api_runtime._utc_now(), judge_report=state["judge_report"]),
                    now=_interfaces_api_runtime._utc_now(),
                )
        else:
            payload = self._optional_json_body()
            state["_document"], _parent, state["_parent_job"], state["parent_plan"] = self._project_edit_parent(project_id, state["task"].parent_version_id)
            _interfaces_api_runtime.ensure_task_current(state["task"], state["parent_plan"])
            state["judge_report"] = self._read_review_task_judge_report(project_id, state["task_store"], state["task"], state["candidates"], parent_plan=state["parent_plan"])
            state["decision_report"] = state["task_store"].write_decision_report(
                state["task"],
                _interfaces_api_runtime.build_review_decision_report(task=state["task"], candidates=state["candidates"], parent_plan=state["parent_plan"], now=_interfaces_api_runtime._utc_now(), notes=str(payload.get("note") or ""), judge_report=state["judge_report"]),
                now=_interfaces_api_runtime._utc_now(),
            )
            self.project_store.append_event(project_id, "review_task_decision_report_refreshed", {"task_id": state["task"].task_id, "recommended_candidate_id": state["decision_report"].get("recommended_candidate_id")})
        self._send_json({"ok": True, "task": state["task"].to_dict(), "decision_report": state["decision_report"], "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(state["candidates"])})
        return (True, None)

    def _handle_review_task_judge_report(self, method: str, project_id: str, action: str, state):
        expected_method = "GET" if action == "judge-report" else "POST"
        if method != expected_method:
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return (True, None)
        if action == "judge-report-refresh":
            result = self._refresh_review_task_judge_report(project_id, state["task_store"], state["task"], self._optional_json_body())
            self._send_json(result)
            return (True, None)
        state["candidates"] = state["task_store"].rank_candidates(state["task"])
        state["judge_report"] = self._read_review_task_judge_report(project_id, state["task_store"], state["task"], state["candidates"])
        self._send_json({"ok": True, "task": state["task"].to_dict(), "judge_report": state["judge_report"], "summary": _interfaces_api_runtime.judge_report_summary(state["judge_report"]), "provider_summary": _interfaces_api_runtime.review_candidate_source_breakdown(state["candidates"])})
        return (True, None)

    def _handle_review_task_lifecycle(self, method: str, project_id: str, action: str, state):
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return (True, None)
        if action == "resolve":
            payload = self._optional_json_body()
            state["task"] = state["task_store"].update_task(_interfaces_api_runtime.mark_task_resolved(state["task"], str(payload.get("note") or ""), now=_interfaces_api_runtime._utc_now()), event="review_task_resolved", payload={"note": payload.get("note") or ""}, now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "review_task_resolved", {"task_id": state["task"].task_id, "candidate_id": state["task"].selected_candidate_id, "version_id": state["task"].applied_version_id})
            self._send_json({"ok": True, "task": state["task"].to_dict()})
        elif action == "needs-more-work":
            state["task"], follow_up = self._create_review_task_follow_up(project_id, state["task_store"], state["task"], self._optional_json_body())
            self._send_json({"ok": True, "task": state["task"].to_dict(), "follow_up_task": follow_up.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        else:
            state["task"] = state["task_store"].update_task(_interfaces_api_runtime.mark_task_archived(state["task"]), event="review_task_archived", payload={}, now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "review_task_archived", {"task_id": state["task"].task_id})
            self._send_json({"ok": True, "task": state["task"].to_dict()})
        return (True, None)
