from __future__ import annotations

import json
from pathlib import Path

from song_agent.edits import EditIntent, apply_edit_intent
from song_agent.projectio import write_json
from song_agent.projects import ProjectStore
from song_agent.renderers.midi import render_midi
from song_agent.review_sprint_actions import ReviewSprintActionQueueStore, build_action_queue_from_recommendation_report
from song_agent.review_sprint_metrics import (
    ReviewMetricsStore,
    build_project_review_metrics,
    build_sprint_metrics_report,
    project_review_metrics_summary,
    sprint_metrics_summary,
)
from song_agent.review_sprints import ReviewSprintStore
from song_agent.review_judge import build_judge_report
from song_agent.review_tasks import ReviewCandidate, ReviewTaskStore, build_local_review_candidates, build_review_decision_report
from song_agent.prompt_templates import PromptTemplateStore
from tests.test_editor_audition import demo_song_plan
from tests.test_review_sprint_actions import _report
from tests.test_review_sprints import _task


class SmokeJob:
    def __init__(self, job_id: str, run_dir: Path, request: dict[str, object]):
        now = "2026-05-14T00:00:00+00:00"
        self.job_id = job_id
        self.title = str(request.get("title") or job_id)
        self.output_dir = str(run_dir)
        self.status = "completed"
        self.created_at = now
        self.updated_at = now
        self.input_payload = dict(request)
        self.generation_mode = "local"
        self.pipeline_mode = "single"
        self.summary = {"title": self.title}
        self.artifacts = {"midi": str(run_dir / "renders" / "song.mid")}


def test_sprint_metrics_empty_sprint_no_data_and_sanitizes(tmp_path):
    project_dir = tmp_path / "project"
    task_store = ReviewTaskStore(project_dir)
    sprint_store = ReviewSprintStore(project_dir)
    sprint = sprint_store.create_sprint(
        project_id="project-001",
        task_store=task_store,
        payload={"name": r"Metrics api_key=sk-secret-value C:\Users\demo", "task_ids": []},
        now="2026-05-14T00:00:00+00:00",
    )
    project_document = _project_with_versions(tmp_path, "project-001")

    report = build_sprint_metrics_report(project_id="project-001", sprint=sprint, project_document=project_document, task_store=task_store, sprint_store=sprint_store, now="2026-05-14T00:01:00+00:00")
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["overview"]["task_count"] == 0
    assert report["risk_readiness"]["readiness"] == "no_data"
    assert report["quality_delta"]["status"] == "not_available"
    assert report["source_hash"]
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_sprint_metrics_candidate_funnel_queue_provider_quality_and_store(tmp_path):
    plan = demo_song_plan()
    project_document = _project_with_versions(tmp_path, "project-001")
    project_dir = Path(project_document.versions[0].output_dir).parents[1] / ".musicforge" / "projects" / "project-001"
    task_store = ReviewTaskStore(project_dir)
    task = _task(task_store, plan)
    local_candidate, local_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    local_candidate = task_store.create_candidate(task=task, candidate=local_candidate, candidate_plan=local_plan, validator=validator, summary=summary, render_midi_file=False)
    provider_candidate = task_store.create_candidate(
        task=task,
        candidate=ReviewCandidate.from_dict({**local_candidate.to_dict(), "candidate_id": "revcand-001", "candidate_type": "provider_review_patch", "strategy": "provider", "source": {"provider": {"type": "mock"}}, "rank": 1, "scores": {**local_candidate.scores, "combined": 100}}),
        candidate_plan=local_plan,
        validator=validator,
        summary=summary,
        render_midi_file=False,
    )
    task = task_store.update_counts(task)
    ranked = task_store.rank_candidates(task)
    decision = task_store.write_decision_report(task, build_review_decision_report(task=task, candidates=ranked, parent_plan=plan, now="2026-05-14T00:00:00+00:00"))
    template = PromptTemplateStore(tmp_path / "templates").get_template("provider-review-judge")
    judge = task_store.write_judge_report(
        task,
        build_judge_report(
            project_id="project-001",
            task=task,
            candidates=ranked,
            parent_plan=plan,
            template=template,
            provider_output={
                "recommended_candidate_id": provider_candidate.candidate_id,
                "candidate_scores": [
                    {
                        "candidate_id": provider_candidate.candidate_id,
                        "overall": 91,
                        "review_fit": 92,
                        "target_precision": 90,
                        "musicality": 88,
                        "novelty": 72,
                        "risk": 18,
                        "confidence": 0.82,
                        "reason": "Best fit for the review target.",
                        "risks": [],
                    },
                    {
                        "candidate_id": local_candidate.candidate_id,
                        "overall": 76,
                        "review_fit": 78,
                        "target_precision": 72,
                        "musicality": 80,
                        "novelty": 64,
                        "risk": 28,
                        "confidence": 0.7,
                        "reason": "Good local baseline.",
                        "risks": [],
                    },
                ],
                "comparison_summary": {"best_candidate_id": provider_candidate.candidate_id, "reason": "Provider candidate fits better.", "tradeoffs": []},
                "warnings": [],
            },
            provider_snapshot={"wire_api": "mock", "model": "mock-review", "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}},
            now="2026-05-14T00:01:00+00:00",
        ),
        now="2026-05-14T00:01:00+00:00",
    )
    child_version = _add_applied_version(project_document, task, provider_candidate, local_plan, tmp_path)
    task_store.update_candidate(type(provider_candidate).from_dict({**provider_candidate.to_dict(), "status": "applied"}))
    task = task_store.update_task(type(task).from_dict({**task.to_dict(), "status": "applied", "selected_candidate_id": provider_candidate.candidate_id, "applied_version_id": child_version.version_id, "applied_job_id": child_version.job_id}))
    sprint_store = ReviewSprintStore(project_dir)
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    report_payload = _report(sprint.sprint_id, task.task_id, action="apply_ready_candidate", context=True, recommended_candidate_id=provider_candidate.candidate_id)
    sprint_store.write_recommendation_report(sprint, report_payload, now="2026-05-14T00:00:00+00:00")
    queue_store = ReviewSprintActionQueueStore(sprint_store.sprint_dir(sprint.sprint_id))
    queue = queue_store.create_queue(build_action_queue_from_recommendation_report(project_id="project-001", sprint=sprint, recommendation_report=report_payload, now="2026-05-14T00:00:00+00:00"))
    queue = queue_store.update_queue(
        type(queue).from_dict({**queue.to_dict(), "items": [{**item.to_dict(), "status": "completed" if item.action == "save_recommended_context_pack" else item.status} for item in queue.items]}),
        now="2026-05-14T00:02:00+00:00",
    )
    provider_records = [
        {
            "project_id": "project-001",
            "source_type": "review_task_judge",
            "source_id": task.task_id,
            "group_id": task.task_id,
            "usage": {"operation": "provider_review_judge", "prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30, "status": "completed"},
        },
        {
            "project_id": "project-001",
            "source_type": "review_task",
            "source_id": task.task_id,
            "group_id": task.task_id,
            "usage": {"operation": "review_sprint_action_provider_candidates", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "status": "completed"},
        },
    ]

    report = build_sprint_metrics_report(project_id="project-001", sprint=sprint, project_document=project_document, task_store=task_store, sprint_store=sprint_store, queue_store=queue_store, provider_usage_records=provider_records, now="2026-05-14T00:03:00+00:00")
    summary = sprint_metrics_summary(report)
    store = ReviewMetricsStore(project_dir)
    store.write_sprint_metrics(sprint.sprint_id, report)
    loaded = store.read_sprint_metrics(sprint.sprint_id)

    assert report["candidate_funnel"]["provider_candidate_count"] == 1
    assert report["candidate_funnel"]["local_candidate_count"] == 1
    assert report["candidate_funnel"]["applied_candidate_count"] == 1
    assert report["manual_decisions"]["applied_from_decision_recommendation_count"] == 1
    assert report["action_queue_execution"]["completed_action_count"] == 1
    assert report["recommendation_adoption"]["saved_recommended_context_pack_count"] == 1
    assert report["provider_usage"]["total_tokens"] == 45
    assert report["judge_metrics"]["judged_task_count"] == 1
    assert report["judge_metrics"]["judge_provider_call_count"] == 1
    assert report["judge_metrics"]["judge_provider_tokens"] == 30
    assert report["judge_metrics"]["judge_recommendation_match_apply_count"] == 1
    assert report["judge_metrics"]["judge_apply_match_rate"] == 1.0
    assert report["quality_delta"]["latest_applied_version_id"] == child_version.version_id
    assert report["risk_readiness"]["readiness"] in {"needs_review", "ready_to_close"}
    assert summary["provider_tokens"] == 45
    assert summary["judge_metrics"]["judged_task_count"] == 1
    assert loaded["source_hash"] == report["source_hash"]
    assert decision["recommended_candidate_id"] == provider_candidate.candidate_id
    assert judge["recommended_candidate_id"] == provider_candidate.candidate_id

    task_store.update_candidate(type(provider_candidate).from_dict({**provider_candidate.to_dict(), "summary": "changed after judge"}))
    stale_report = build_sprint_metrics_report(project_id="project-001", sprint=sprint, project_document=project_document, task_store=task_store, sprint_store=sprint_store, queue_store=queue_store, provider_usage_records=provider_records, now="2026-05-14T00:04:00+00:00")
    assert stale_report["judge_metrics"]["judged_task_count"] == 0
    assert stale_report["judge_metrics"]["stale_judge_count"] == 1
    assert stale_report["judge_metrics"]["task_summaries"][0]["status"] == "stale"


def test_project_review_metrics_summarizes_sprints(tmp_path):
    plan = demo_song_plan()
    project_document = _project_with_versions(tmp_path, "project-001")
    project_dir = Path(project_document.versions[0].output_dir).parents[1] / ".musicforge" / "projects" / "project-001"
    task_store = ReviewTaskStore(project_dir)
    task = _task(task_store, plan)
    sprint_store = ReviewSprintStore(project_dir)
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    sprint_store.write_closeout_report(sprint, {"schema_version": 1, "sprint_id": sprint.sprint_id, "status": "failed", "readiness": "needs_candidates", "close_allowed": False, "blockers": ["open_tasks"], "warnings": []})

    report = build_project_review_metrics(project_id="project-001", project_document=project_document, sprint_store=sprint_store, task_store=task_store, provider_usage_records=[], now="2026-05-14T00:00:00+00:00")
    summary = project_review_metrics_summary(report)

    assert report["sprint_count"] == 1
    assert report["total_task_count"] == 1
    assert report["latest_readiness"] in {"needs_candidates", "needs_review", "blocked"}
    assert report["closeout_summary"]["closeout_report_count"] == 1
    assert report["closeout_summary"]["open_blocker_count"] == 1
    assert summary["latest_sprint_id"] == "sprint-001"
    assert summary["total_provider_tokens"] == 0
    assert summary["closeout_summary"]["latest_closeout_status"] == "failed"


def _project_with_versions(tmp_path: Path, project_id: str):
    root = tmp_path / ".musicforge" / "projects"
    store = ProjectStore(root)
    document = store.create_project(project_id)
    request = {"title": "Metrics Parent", "style": "synth pop", "theme": "metrics"}
    run_dir = tmp_path / "runs" / "parent"
    plan = demo_song_plan()
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
    render_midi(plan, run_dir / "renders" / "song.mid")
    return store.add_version_from_job(document.state.project_id, SmokeJob("parent-job", run_dir, request), name="Parent")


def _add_applied_version(project_document, task, candidate, candidate_plan, tmp_path: Path):
    store = ProjectStore(tmp_path / ".musicforge" / "projects")
    child_dir = tmp_path / "runs" / "child"
    intent = EditIntent.from_dict(candidate.intents[0])
    result = apply_edit_intent(candidate_plan, intent)
    write_json(child_dir / "data" / "song-plan.json", result.plan.to_dict())
    write_json(
        child_dir / "data" / "edit-metadata.json",
        {
            "review_task": {"task_id": task.task_id},
            "review_candidate": {"candidate_id": candidate.candidate_id},
            "review_judge": {"judge_recommended_candidate_id": candidate.candidate_id, "applied_matches_judge": True},
        },
    )
    render_midi(result.plan, child_dir / "renders" / "song.mid")
    document = store.add_version_from_job(project_document.state.project_id, SmokeJob("child-job", child_dir, {"title": "Metrics Child"}), name="Child", parent_version_id="v001", variant_type="section_edit")
    project_document.versions = document.versions
    project_document.state = document.state
    return document.versions[-1]
