from __future__ import annotations

import json
import threading

from song_agent.review_sprint_actions import (
    ReviewSprintActionQueueStore,
    action_queue_collection_summary,
    build_action_queue_from_recommendation_report,
    queue_report_is_stale,
    recommendation_report_hash,
)
from song_agent.review_sprints import ReviewSprintStore
from song_agent.review_tasks import ReviewTaskStore
from tests.test_editor_audition import demo_song_plan
from tests.test_review_sprints import _task


def test_action_queue_builds_safe_manual_and_context_items(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(
        project_id="project-001",
        task_store=task_store,
        payload={"task_ids": [task.task_id], "settings": {"provider_candidate_count": 4}},
    )
    report = _report(
        sprint.sprint_id,
        task.task_id,
        action="generate_provider",
        context=True,
        recommended_candidate_id="revcand-002",
    )

    queue = build_action_queue_from_recommendation_report(project_id="project-001", sprint=sprint, recommendation_report=report, now="2026-05-14T00:00:00+00:00")
    by_action = {item.action: item for item in queue.items}

    assert [item.action for item in queue.items] == ["save_recommended_context_pack", "generate_provider_candidates"]
    assert by_action["save_recommended_context_pack"].safety == "auto_safe"
    assert by_action["generate_provider_candidates"].safety == "provider_safe"
    assert by_action["generate_provider_candidates"].input["candidate_count"] == 4
    assert by_action["generate_provider_candidates"].input["template_id"] == "provider-review-candidates"
    assert queue.created_from["recommendation_report_hash"] == recommendation_report_hash(report)
    assert queue.summary["pending"] == 2


def test_manual_and_blocked_actions_are_not_executable(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    report = _report(sprint.sprint_id, task.task_id, action="apply_ready_candidate", recommended_candidate_id="revcand-001")

    queue = build_action_queue_from_recommendation_report(project_id="project-001", sprint=sprint, recommendation_report=report)
    item = queue.items[0]

    assert item.action == "manual_apply_candidate"
    assert item.status == "manual_required"
    assert item.safety == "manual_required"
    assert item.result["candidate_id"] == "revcand-001"
    assert "ReviewTask candidate apply endpoint" in item.result["message"]
    assert queue.status == "completed_with_warnings"
    assert queue.summary["manual_required"] == 1


def test_report_hash_stale_detection(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    report = _report(sprint.sprint_id, task.task_id, action="generate_local")
    queue = build_action_queue_from_recommendation_report(project_id="project-001", sprint=sprint, recommendation_report=report)

    assert queue_report_is_stale(queue, report) is False
    assert queue_report_is_stale(queue, {**report, "created_at": "2026-05-14T01:00:00+00:00"}) is True


def test_action_queue_store_round_trip_events_archive_and_sanitizes(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan, notes=r"api_key=sk-secret-value C:\Users\demo\song.wav")
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    report = _report(sprint.sprint_id, task.task_id, action="generate_local", reason=r"api_key=sk-secret-value C:\Users\demo\song.wav")
    queue = build_action_queue_from_recommendation_report(project_id="project-001", sprint=sprint, recommendation_report=report)
    store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))

    created = store.create_queue(queue, now="2026-05-14T00:00:00+00:00")
    store.append_event(created.queue_id, "custom_event", {"token": "sk-secret-value", "path": r"C:\Users\demo\song.wav"}, now="2026-05-14T00:01:00+00:00")
    loaded = store.read_queue(created.queue_id)
    archived = store.archive_queue(created.queue_id, now="2026-05-14T00:02:00+00:00")
    serialized = json.dumps({"queue": loaded.to_dict(), "events": store.read_events(created.queue_id)}, ensure_ascii=False)

    assert created.queue_id == "queue-001"
    assert created.items[0].item_id == "item-001"
    assert loaded.items[0].reason
    assert store.list_queues() == []
    assert store.list_queues(include_archived=True)[0].status == "archived"
    assert archived.archived_at == "2026-05-14T00:02:00+00:00"
    assert "sk-secret-value" not in serialized
    assert "api_key" not in serialized
    assert "C:\\Users" not in serialized


def test_action_queue_store_concurrent_ids_and_collection_summary(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    report = _report(sprint.sprint_id, task.task_id, action="generate_local")
    store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
    created: list[str] = []

    def create_one() -> None:
        queue = build_action_queue_from_recommendation_report(project_id="project-001", sprint=sprint, recommendation_report=report)
        created.append(store.create_queue(queue).queue_id)

    threads = [threading.Thread(target=create_one) for _ in range(24)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    queues = store.list_queues()
    summary = action_queue_collection_summary(queues)

    assert len(created) == 24
    assert len(set(created)) == 24
    assert sorted(created) == [f"queue-{index:03d}" for index in range(1, 25)]
    assert summary["queue_count"] == 24
    assert summary["latest_queue_id"].startswith("queue-")


def _report(
    sprint_id: str,
    task_id: str,
    *,
    action: str,
    context: bool = False,
    recommended_candidate_id: str | None = None,
    reason: str = "Review sprint action queue test.",
) -> dict[str, object]:
    preview = {
        "query": {"goal": "review_task_candidate_generation"},
        "asset_refs": [{"asset_id": "asset-001", "source_hash": "asset-hash"}],
        "reference_refs": [{"reference_id": "ref-001", "source_hash": "ref-hash"}],
    }
    return {
        "schema_version": 1,
        "project_id": "project-001",
        "sprint_id": sprint_id,
        "created_at": "2026-05-14T00:00:00+00:00",
        "recommended_order": [task_id],
        "recommended_actions": [
            {
                "task_id": task_id,
                "rank": 1,
                "sprint_order": 1,
                "priority": 80,
                "status": "open",
                "action": action,
                "score": 90,
                "reason": reason,
                "score_breakdown": {"priority": 20, "status": 18},
                "candidate_summary": {"recommended_candidate_id": recommended_candidate_id},
                "context_pack_preview": preview if context else {"query": {}, "asset_refs": [], "reference_refs": []},
            }
        ],
        "sprint_level_recommendation": {"next_action": action, "ready_to_close": False},
        "source_summary": {"task_count": 1, "context_recommendation_count": 1 if context else 0},
    }
