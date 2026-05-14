from __future__ import annotations

import json

import pytest

from song_agent.projects import ProjectDocument, ProjectState, ProjectVersion
from song_agent.review_sprint_actions import ReviewSprintActionQueueStore, build_action_queue_from_recommendation_report
from song_agent.review_sprint_closeout import build_closeout_report, build_signoff_record, closeout_report_summary, closeout_source_hash
from song_agent.review_sprints import ReviewSprintStore
from song_agent.review_tasks import ReviewTaskStore, ReviewTask, build_local_review_candidates
from tests.test_editor_audition import demo_song_plan
from tests.test_review_sprint_actions import _report
from tests.test_review_sprints import _task


def test_closeout_blocks_open_task_and_requires_force_reason(tmp_path):
    plan = demo_song_plan()
    project_dir = tmp_path / "project"
    task_store = ReviewTaskStore(project_dir)
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(project_dir)
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    report = build_closeout_report(
        project_id="project-001",
        sprint=sprint,
        project_document=_document(),
        task_store=task_store,
        sprint_store=sprint_store,
        queue_store=ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id)),
        metrics_report={"risk_readiness": {"readiness": "needs_candidates"}},
        now="2026-05-15T00:00:00+00:00",
    )

    assert report["status"] == "failed"
    assert report["close_allowed"] is False
    assert any(check["check_id"] == "open_tasks" and check["status"] == "failed" for check in report["checks"])
    with pytest.raises(ValueError, match="override_reason"):
        build_signoff_record(project_id="project-001", sprint=sprint, closeout_report=report, payload={"force": True})


def test_closeout_passes_resolved_applied_sprint_and_stale_hash_changes(tmp_path):
    plan = demo_song_plan()
    project_dir = tmp_path / "project"
    task_store = ReviewTaskStore(project_dir)
    task = _task(task_store, plan)
    candidate, candidate_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    stored = task_store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=False)
    task = task_store.update_task(ReviewTask.from_dict({**task_store.update_counts(task).to_dict(), "status": "resolved", "selected_candidate_id": stored.candidate_id, "applied_version_id": "v002"}))
    sprint_store = ReviewSprintStore(project_dir)
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    sprint = sprint_store.refresh_summary(sprint, task_store=task_store)
    metrics = {"risk_readiness": {"readiness": "ready_to_close"}, "overview": {"completion_rate": 1.0}, "quality_delta": {"overall_delta": 2}, "provider_usage": {"total_tokens": 0}}
    document = _document(version_ids=["v001", "v002"], selected_version_id="v002")

    report = build_closeout_report(
        project_id="project-001",
        sprint=sprint,
        project_document=document,
        task_store=task_store,
        sprint_store=sprint_store,
        queue_store=ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id)),
        metrics_report=metrics,
        now="2026-05-15T00:00:00+00:00",
    )
    first_hash = report["source_hash"]
    task_store.update_task(ReviewTask.from_dict({**task.to_dict(), "status": "stale"}))
    changed_hash = closeout_source_hash(
        sprint=sprint,
        project_document=document,
        task_store=task_store,
        sprint_store=sprint_store,
        queue_store=ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id)),
        metrics_report=metrics,
    )

    assert report["close_allowed"] is True
    assert report["recommended_final_version"]["version_id"] == "v002"
    assert first_hash != changed_hash


def test_closeout_warnings_and_sanitized_signoff(tmp_path):
    plan = demo_song_plan()
    project_dir = tmp_path / "project"
    task_store = ReviewTaskStore(project_dir)
    task = _task(task_store, plan)
    task = task_store.update_task(ReviewTask.from_dict({**task.to_dict(), "status": "resolved", "applied_version_id": "v002"}))
    sprint_store = ReviewSprintStore(project_dir)
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    recommendation = _report(sprint.sprint_id, task.task_id, action="apply_ready_candidate", recommended_candidate_id="revcand-001")
    queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
    queue_store.create_queue(build_action_queue_from_recommendation_report(project_id="project-001", sprint=sprint, recommendation_report=recommendation))

    report = build_closeout_report(
        project_id="project-001",
        sprint=sprint,
        project_document=_document(version_ids=["v001", "v002"], selected_version_id="v002"),
        task_store=task_store,
        sprint_store=sprint_store,
        queue_store=queue_store,
        metrics_report={"risk_readiness": {"readiness": "ready_to_close"}, "overview": {"completion_rate": 1.0}, "quality_delta": {"overall_delta": 0}},
        judge_summary={"stale_judge_count": 0},
        recommendation_report=recommendation,
        now="2026-05-15T00:00:00+00:00",
    )
    signoff = build_signoff_record(
        project_id="project-001",
        sprint=sprint,
        closeout_report=report,
        payload={"force": True, "override_reason": r"heard locally api_key=sk-secret-value C:\Users\demo\song.wav", "notes": r"accepted C:\Users\demo"},
    )
    serialized = json.dumps({"report": report, "signoff": signoff}, ensure_ascii=False)

    assert report["status"] == "warning"
    assert any(check["check_id"] == "unresolved_manual_required" and check["status"] == "warning" for check in report["checks"])
    assert closeout_report_summary(report)["warning_count"] >= 1
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def _document(*, version_ids: list[str] | None = None, selected_version_id: str | None = None) -> ProjectDocument:
    version_ids = version_ids or ["v001"]
    versions = [
        ProjectVersion(
            version_id=version_id,
            project_id="project-001",
            index=index,
            name=version_id,
            job_id=f"job-{index:03d}",
            output_dir="",
            status="completed",
            created_at="2026-05-15T00:00:00+00:00",
            updated_at="2026-05-15T00:00:00+00:00",
            quality_score=80 + index,
        )
        for index, version_id in enumerate(version_ids, start=1)
    ]
    return ProjectDocument(
        state=ProjectState(
            project_id="project-001",
            name="Project",
            selected_version_id=selected_version_id,
            latest_version_id=version_ids[-1],
            version_count=len(version_ids),
        ),
        versions=versions,
    )
