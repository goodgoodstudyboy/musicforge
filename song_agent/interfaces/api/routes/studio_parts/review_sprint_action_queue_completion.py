from __future__ import annotations

from song_agent.application.http_ports import studio as studio_ports
from song_agent.interfaces.api.route_contexts.studio import StudioRouteContext
from song_agent.platform.contracts.documents import JsonDocument, normalize_json_value

import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class StudioReviewSprintActionQueueCompletion(StudioRouteContext):
    def _complete_review_sprint_action_queue(
        self,
        project_id: str,
        sprint_store: studio_ports.ReviewSprintStore,
        task_store: studio_ports.ReviewTaskStore,
        sprint: studio_ports.ReviewSprint,
        queue_store: studio_ports.ReviewSprintActionQueueStore,
        queue: studio_ports.SprintActionQueue,
        results: list[JsonDocument],
    ) -> JsonDocument:
        completed_status = "pending" if queue.status == "running" else queue.status
        queue = queue_store.update_queue(
            _interfaces_api_runtime.replace(queue, status=completed_status),
            event="queue_run_completed",
            payload={"result_count": len(results)},
            now=_interfaces_api_runtime._utc_now(),
        )
        self.project_store.append_event(project_id, "review_sprint_action_queue_completed", {"sprint_id": sprint.sprint_id, "queue_id": queue.queue_id, "status": queue.status})
        refreshed_sprint = sprint_store.read_sprint(sprint.sprint_id)
        response = self._review_sprint_response(sprint_store, task_store, refreshed_sprint)
        response.update(
            {
                "queue": queue.to_dict(),
                "queue_events": normalize_json_value(queue_store.read_events(queue.queue_id)),
                "results": normalize_json_value(_interfaces_api_runtime.sanitize_metadata(results)),
                "action_queue_summary": _interfaces_api_runtime.action_queue_summary(queue),
            }
        )
        return response
