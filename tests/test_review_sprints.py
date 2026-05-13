from __future__ import annotations

import json
import threading

import pytest

from song_agent.review_sprints import (
    ReviewSprintError,
    ReviewSprintStateError,
    ReviewSprintStore,
    review_sprint_export_summary,
    review_sprint_project_rollup,
    validate_review_sprint_id,
)
from song_agent.review_tasks import ReviewTaskStore, build_local_review_candidates
from tests.test_editor_audition import demo_song_plan
from tests.test_review_tasks import Preview, _audition


def test_create_review_sprint_summary_conflicts_and_sanitizes(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task_a = _task(task_store, plan, notes=r"bass too dense api_key=sk-secret-value C:\Users\demo\song.wav", track_ids=["track-003"])
    task_b = _task(task_store, plan, notes="drums also too dense", track_ids=["track-003"], audition_id="audition-002")
    sprint_store = ReviewSprintStore(tmp_path / "project")

    sprint = sprint_store.create_sprint(
        project_id="project-001",
        task_store=task_store,
        payload={"name": "Chorus sprint", "description": r"secret=sk-secret-value C:\Users\demo", "task_ids": [task_a.task_id, task_b.task_id]},
        now="2026-05-13T00:00:00+00:00",
    )
    report = sprint_store.read_conflict_report(sprint.sprint_id)
    summary = sprint_store.read_summary(sprint.sprint_id)
    serialized = json.dumps({"sprint": sprint.to_dict(), "summary": summary, "report": report}, ensure_ascii=False)

    assert sprint.sprint_id == "sprint-001"
    assert sprint.parent_version_id == "v001"
    assert sprint.counts["open"] == 2
    assert summary["task_count"] == 2
    assert report["conflicts"]
    assert any(conflict["kind"] == "same_section_track" for conflict in report["conflicts"])
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized
    assert sprint_store.read_events(sprint.sprint_id)[0]["event"] == "review_sprint_created"


def test_add_remove_reorder_duplicate_and_archive_guards(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task_a = _task(task_store, plan)
    task_b = _task(task_store, plan, audition_id="audition-002")
    task_c = _task(task_store, plan, audition_id="audition-003")
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task_a.task_id]})

    with pytest.raises(ReviewSprintError, match="already contains"):
        sprint_store.add_tasks(sprint, task_store=task_store, task_ids=[task_a.task_id])

    sprint = sprint_store.add_tasks(sprint, task_store=task_store, task_ids=[task_b.task_id, task_c.task_id], lane="arrangement", notes="fix first")
    assert [ref["task_id"] for ref in sprint.task_refs] == [task_a.task_id, task_b.task_id, task_c.task_id]
    assert sprint.task_refs[1]["lane"] == "arrangement"

    sprint = sprint_store.reorder_tasks(sprint, [task_c.task_id, task_a.task_id, task_b.task_id], task_store=task_store)
    assert [ref["task_id"] for ref in sprint.task_refs] == [task_c.task_id, task_a.task_id, task_b.task_id]
    assert [ref["order"] for ref in sprint.task_refs] == [1, 2, 3]

    sprint = sprint_store.remove_task(sprint, task_a.task_id, task_store=task_store)
    assert [ref["task_id"] for ref in sprint.task_refs] == [task_c.task_id, task_b.task_id]

    archived = sprint_store.archive_sprint(sprint)
    with pytest.raises(ReviewSprintStateError):
        sprint_store.add_tasks(archived, task_store=task_store, task_ids=[task_a.task_id])


def test_summary_counts_candidates_and_rollup(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    candidate, candidate_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    task_store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=False)
    task = task_store.update_counts(task)
    sprint_store = ReviewSprintStore(tmp_path / "project")

    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    export = review_sprint_export_summary(sprint, sprint_store.read_summary(sprint.sprint_id), sprint_store.read_conflict_report(sprint.sprint_id))
    rollup = review_sprint_project_rollup([export])

    assert sprint.counts["candidate_ready"] == 1
    assert sprint.counts["ready_candidate_count"] == 1
    assert sprint.counts["local_candidate_count"] == 1
    assert export["task_ids"] == [task.task_id]
    assert rollup["latest_sprint_id"] == sprint.sprint_id
    assert rollup["open_task_count"] == 0


def test_recommendation_report_round_trip_and_event(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})

    report = sprint_store.write_recommendation_report(
        sprint,
        {
            "schema_version": 1,
            "sprint_id": sprint.sprint_id,
            "recommended_order": [task.task_id],
            "source_summary": {"context_recommendation_count": 1},
            "secret": r"api_key=sk-secret-value C:\Users\demo\song.wav",
        },
        now="2026-05-14T00:00:00+00:00",
    )
    loaded = sprint_store.read_recommendation_report(sprint.sprint_id)
    serialized = json.dumps(loaded, ensure_ascii=False)

    assert sprint_store.recommendation_report_path(sprint.sprint_id).name == "recommendation-report.json"
    assert report["recommended_order"] == [task.task_id]
    assert loaded["sprint_id"] == sprint.sprint_id
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized
    assert sprint_store.read_events(sprint.sprint_id)[-1]["event"] == "review_sprint_recommendations_refreshed"


def test_conflict_detection_parent_mismatch_stale_and_follow_up(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task_a = _task(task_store, plan)
    task_b = _task(task_store, plan, parent_version_id="v002", audition_id="audition-002")
    task_c = task_store.update_task(
        type(task_a).from_dict({**_task(task_store, plan, audition_id="audition-003").to_dict(), "status": "needs_more_work", "follow_up_task_id": "review-task-999"})
    )
    sprint_store = ReviewSprintStore(tmp_path / "project")

    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"parent_version_id": "v001", "task_ids": [task_a.task_id, task_b.task_id, task_c.task_id]})
    report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes={"v001": "changed-hash"})
    kinds = {conflict["kind"] for conflict in report["conflicts"]}

    assert "parent_mismatch" in kinds
    assert "stale_task" in kinds
    assert "missing_follow_up" in kinds
    assert task_a.task_id in report["stale_task_ids"]


def test_invalid_ids_and_concurrent_creation(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(tmp_path / "project")
    created: list[str] = []

    with pytest.raises(ValueError):
        validate_review_sprint_id("../bad")

    def create_one():
        sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
        created.append(sprint.sprint_id)

    threads = [threading.Thread(target=create_one) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(created) == 5
    assert len(set(created)) == 5
    assert sorted(created) == [f"sprint-{index:03d}" for index in range(1, 6)]


def _task(task_store: ReviewTaskStore, plan, *, notes: str = "bass too dense", track_ids: list[str] | None = None, audition_id: str = "audition-001", parent_version_id: str = "v001"):
    marker_suffix = "".join(char for char in audition_id if char.isdigit())[-3:] or "001"
    review = {
        "rating": 4,
        "status": "needs_fix",
        "notes": notes,
        "markers": [{"marker_id": f"marker-{marker_suffix}", "beat": 1, "kind": "fix", "label": "fix point"}],
    }
    audition = _audition(review=review, range_data={"mode": "custom", "start_beat": 16.0, "end_beat": 48.0})
    audition = audition.__class__.from_dict(
        {
            **audition.to_dict(),
            "audition_id": audition_id,
            "parent_version_id": parent_version_id,
            "track_ids": track_ids or ["track-003"],
        }
    )
    return task_store.create_task(
        project_id="project-001",
        parent_version_id=parent_version_id,
        parent_plan=plan,
        preview=Preview(),
        audition=audition,
        audition_plan=plan,
        now="2026-05-13T00:00:00+00:00",
    )
