from __future__ import annotations

import json

from song_agent.assets import AssetStore
from song_agent.library_index import build_library_index
from song_agent.review_sprint_recommendations import (
    build_review_sprint_recommendation_report,
    recommendation_report_summary,
    recommend_review_sprint_task_action,
)
from song_agent.review_sprints import ReviewSprintStore
from song_agent.review_tasks import ReviewTaskStore, build_local_review_candidates, build_review_decision_report
from song_agent.references import ReferenceStore
from tests.test_editor_audition import demo_song_plan
from tests.test_review_sprints import _task


def test_recommendation_actions_cover_task_states_and_ordering(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    open_task = _task(task_store, plan, notes="open bass task")
    provider_gap_task = _task(task_store, plan, notes="local only bass", audition_id="audition-002")
    applied_task = _task(task_store, plan, notes="applied task", audition_id="audition-003")
    stale_task = _task(task_store, plan, notes="stale task", audition_id="audition-004")
    followup_task = _task(task_store, plan, notes="needs more work", audition_id="audition-005")
    _add_local_candidate(task_store, provider_gap_task, plan)
    applied_task = task_store.update_task(type(applied_task).from_dict({**applied_task.to_dict(), "status": "applied", "selected_candidate_id": "revcand-001", "applied_version_id": "v002"}))
    stale_task = task_store.update_task(type(stale_task).from_dict({**stale_task.to_dict(), "status": "stale"}))
    followup_task = task_store.update_task(type(followup_task).from_dict({**followup_task.to_dict(), "status": "needs_more_work", "follow_up_task_id": "review-task-999"}))
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [open_task.task_id, provider_gap_task.task_id, applied_task.task_id, stale_task.task_id, followup_task.task_id]})
    conflict_report = sprint_store.detect_conflicts(sprint, task_store=task_store, parent_plan_hashes={"v001": "changed"})
    sprint_store.refresh_summary(sprint, task_store=task_store)

    report = build_review_sprint_recommendation_report(project_id="project-001", sprint=sprint, task_store=task_store, sprint_store=sprint_store, now="2026-05-14T00:00:00+00:00")
    by_task = {item["task_id"]: item for item in report["recommended_actions"]}

    assert by_task[open_task.task_id]["action"] == "skip_stale"
    assert by_task[provider_gap_task.task_id]["action"] == "skip_stale"
    assert by_task[applied_task.task_id]["action"] == "skip_stale"
    assert by_task[stale_task.task_id]["action"] == "skip_stale"
    assert by_task[followup_task.task_id]["action"] == "skip_stale"
    assert report["recommended_order"] == []
    assert report["sprint_level_recommendation"]["ready_to_close"] is False
    assert all("priority" in item["score_breakdown"] for item in report["recommended_actions"])
    assert conflict_report["stale_task_ids"]


def test_recommendation_actions_without_stale_conflicts(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    open_task = _task(task_store, plan, notes="no candidates")
    provider_gap_task = _task(task_store, plan, notes="local candidate only", audition_id="audition-002")
    ready_task = _task(task_store, plan, notes="ready to apply", audition_id="audition-003")
    applied_task = _task(task_store, plan, notes="already applied", audition_id="audition-004")
    followup_task = _task(task_store, plan, notes="needs more work", audition_id="audition-005")
    _add_local_candidate(task_store, provider_gap_task, plan)
    _add_local_candidate(task_store, ready_task, plan, write_decision=True)
    applied_task = task_store.update_task(type(applied_task).from_dict({**applied_task.to_dict(), "status": "applied", "selected_candidate_id": "revcand-001", "applied_version_id": "v002"}))
    followup_task = task_store.update_task(type(followup_task).from_dict({**followup_task.to_dict(), "status": "needs_more_work", "follow_up_task_id": "review-task-999"}))
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [open_task.task_id, provider_gap_task.task_id, ready_task.task_id, applied_task.task_id, followup_task.task_id]})

    report = build_review_sprint_recommendation_report(project_id="project-001", sprint=sprint, task_store=task_store, sprint_store=sprint_store, now="2026-05-14T00:00:00+00:00")
    by_task = {item["task_id"]: item for item in report["recommended_actions"]}

    assert by_task[open_task.task_id]["action"] == "generate_local"
    assert by_task[provider_gap_task.task_id]["action"] == "generate_provider"
    assert by_task[ready_task.task_id]["action"] == "generate_provider"
    assert by_task[applied_task.task_id]["action"] == "resolve"
    assert by_task[followup_task.task_id]["action"] == "add_follow_up"
    assert report["recommended_order"][0] in {provider_gap_task.task_id, ready_task.task_id}
    assert recommendation_report_summary(report)["open_recommendation_count"] >= 5


def test_direct_recommendation_prefers_conflict_over_provider_gap(tmp_path):
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan)
    _add_local_candidate(task_store, task, plan)
    candidates = task_store.list_candidates(task.task_id)

    action = recommend_review_sprint_task_action(
        task=task,
        candidates=candidates,
        decision_report={},
        conflicts=[{"severity": "blocking", "kind": "parent_mismatch", "task_ids": [task.task_id], "message": "blocking"}],
        ref_order=1,
    )

    assert action["action"] == "inspect_conflict"
    assert action["score_breakdown"]["conflict"] < 0


def test_recommendation_report_redacts_and_recommends_context(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plan = demo_song_plan()
    task_store = ReviewTaskStore(tmp_path / "project")
    task = _task(task_store, plan, notes=r"bass arrangement api_key=sk-secret-value C:\Users\demo\seed.wav")
    sprint_store = ReviewSprintStore(tmp_path / "project")
    sprint = sprint_store.create_sprint(project_id="project-001", task_store=task_store, payload={"task_ids": [task.task_id]})
    asset_store = AssetStore()
    reference_store = ReferenceStore()
    asset = asset_store.create_asset(
        {
            "asset_type": "bass_pattern",
            "name": "Warm bass review helper",
            "tags": ["bass", "review"],
            "style": "synth pop",
            "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
        }
    )
    reference, _duplicate = reference_store.import_reference(
        {
            "reference_type": "style_note",
            "filename": "bass.md",
            "title": "Bass reference",
            "tags": ["bass"],
            "content_base64": "YmFzcyBhcnJhbmdlbWVudCByZWZlcmVuY2U=",
        }
    )
    index = build_library_index(asset_store, reference_store)

    report = build_review_sprint_recommendation_report(project_id="project-001", sprint=sprint, task_store=task_store, sprint_store=sprint_store, library_index=index, now="2026-05-14T00:00:00+00:00")
    preview = report["recommended_actions"][0]["context_pack_preview"]
    serialized = json.dumps(report, ensure_ascii=False)

    assert preview["asset_refs"][0]["asset_id"] == asset.asset_id
    assert preview["reference_refs"][0]["reference_id"] == reference.reference_id
    assert report["source_summary"]["context_recommendation_count"] == 1
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def _add_local_candidate(task_store: ReviewTaskStore, task, plan, *, write_decision: bool = False):
    candidate, candidate_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    task_store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary, render_midi_file=False)
    updated = task_store.update_counts(task)
    ranked = task_store.rank_candidates(updated)
    if write_decision:
        task_store.write_decision_report(updated, build_review_decision_report(task=updated, candidates=ranked, parent_plan=plan, now="2026-05-14T00:00:00+00:00"))
    return updated
