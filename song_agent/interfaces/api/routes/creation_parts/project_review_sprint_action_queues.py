from __future__ import annotations

from song_agent.interfaces.api.route_contexts.creation import CreationRouteContext
from song_agent.interfaces.bootstrap.api import creation_quality as _api_store_factories
from song_agent.platform.contracts.coercion import as_document as _as_document
from song_agent.platform.contracts.documents import normalize_json_value

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class CreationReviewSprintActionQueueRoutes(CreationRouteContext):
    def _handle_review_sprint_action_queues(self, method: str, project_id: str, state):
        queue_store = _api_store_factories.review_sprint_action_queue_store(state["sprint_store"].sprint_dir(state["sprint"].sprint_id))
        if method == "GET":
            queues = queue_store.list_queues(include_archived=True)
            self._send_json({"ok": True, "sprint": state["sprint"].to_dict(), "queues": [queue.to_dict() for queue in queues], "latest_queue": queues[0].to_dict() if queues else {}, "summary": _interfaces_api_runtime.action_queue_collection_summary(queues)})
            return (True, None)
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return (True, None)
        state["payload"] = self._optional_json_body()
        if bool(state["payload"].get("refresh_recommendations", True)):
            state["sprint"], state["_conflict_report"] = self._refresh_review_sprint_state(project_id, state["sprint_store"], state["task_store"], state["sprint"])
            state["report"] = self._refresh_review_sprint_recommendations(project_id, state["sprint_store"], state["task_store"], state["sprint"])
        else:
            state["report"] = state["sprint_store"].read_recommendation_report(state["sprint"].sprint_id, default={})
            if not state["report"]:
                state["report"] = self._refresh_review_sprint_recommendations(project_id, state["sprint_store"], state["task_store"], state["sprint"])
        queue = _interfaces_api_runtime.build_action_queue_from_recommendation_report(project_id=project_id, sprint=state["sprint"], recommendation_report=state["report"], name=str(state["payload"].get("name") or "") or None, settings=_as_document(state["payload"].get("settings")), now=_interfaces_api_runtime._utc_now())
        created = queue_store.create_queue(queue, now=_interfaces_api_runtime._utc_now())
        self.project_store.append_event(project_id, "review_sprint_action_queue_created", {"sprint_id": state["sprint"].sprint_id, "queue_id": created.queue_id, "item_count": len(created.items)})
        self._send_json({"ok": True, "sprint": state["sprint"].to_dict(), "queue": created.to_dict(), "summary": _interfaces_api_runtime.action_queue_summary(created)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        return (True, None)

    def _handle_review_sprint_action_queue(self, method: str, project_id: str, action: str, state):
        queue_id, queue_action = action.split(":", 2)[1:]
        queue_store = _api_store_factories.review_sprint_action_queue_store(state["sprint_store"].sprint_dir(state["sprint"].sprint_id))
        if queue_action == "detail":
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            queue = queue_store.read_queue(queue_id)
            if queue.project_id != project_id or queue.sprint_id != state["sprint"].sprint_id:
                raise FileNotFoundError(queue_id)
            self._send_json({"ok": True, "sprint": state["sprint"].to_dict(), "queue": queue.to_dict(), "events": normalize_json_value(queue_store.read_events(queue.queue_id)), "summary": _interfaces_api_runtime.action_queue_summary(queue)})
            return (True, None)
        if queue_action == "run":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            state["payload"] = self._optional_json_body()
            state["result"] = self._run_review_sprint_action_queue(project_id, state["sprint_store"], state["task_store"], state["sprint"], queue_store, queue_id, state["payload"])
            self._send_json(state["result"])
            return (True, None)
        if queue_action == "archive":
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            queue = queue_store.read_queue(queue_id)
            if queue.project_id != project_id or queue.sprint_id != state["sprint"].sprint_id:
                raise FileNotFoundError(queue_id)
            archived = queue_store.archive_queue(queue.queue_id, now=_interfaces_api_runtime._utc_now())
            self.project_store.append_event(project_id, "review_sprint_action_queue_archived", {"sprint_id": state["sprint"].sprint_id, "queue_id": archived.queue_id})
            self._send_json({"ok": True, "queue": archived.to_dict(), "summary": _interfaces_api_runtime.action_queue_summary(archived)})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Review sprint action queue route not found.")
        return (True, None)
