from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.acceptance_fix_plan_reviews import AcceptanceFixPlanReviewStateError, AcceptanceFixPlanReviewStore
from song_agent.projectio import read_json, write_json
from tests.test_acceptance_fix_planning import _planning_sources


def _closed_planned_sprint(tmp_path: Path, monkeypatch, *, review_mode: str = "manual"):
    monkeypatch.chdir(tmp_path)
    acceptance_store, _analytics_store, kb_store, plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)
    plan = plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"], "max_items": 5}, now="2026-05-21T01:00:00+00:00")
    created = plan_store.create_fix_sprint(plan.plan_id, {"name": "Planned Sprint"}, now="2026-05-21T01:01:00+00:00")
    sprint_id = created["fix_sprint"]["fix_sprint_id"]
    fix_store = plan_store.fix_sprint_store
    item = fix_store.read_items(sprint_id)[0]
    fix_store.waive_item(sprint_id, item.item_id, "covered by manual rewrite", now="2026-05-21T01:02:00+00:00")
    recheck = fix_store.create_recheck_suite(sprint_id, {"profile_id": "developer_manual"}, now="2026-05-21T01:03:00+00:00")
    suite_id = recheck["suite"]["suite_id"]
    recheck_case = acceptance_store.list_cases(suite_id)[0]
    acceptance_store.generate_case(suite_id, recheck_case.case_id, render_audio_mode="never")
    acceptance_store.run_health(suite_id, recheck_case.case_id)
    acceptance_store.write_review(
        suite_id,
        recheck_case.case_id,
        {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": review_mode, "audio_mode": "midi", "notes": "Accepted after planned rewrite with local-path-marker and masked-key-marker."},
    )
    acceptance_store.build_report(suite_id)
    fix_store.refresh_delta(sprint_id, now="2026-05-21T01:04:00+00:00")
    fix_store.close(sprint_id, {"force": True, "override_reason": "waived issue was manually verified"}, now="2026-05-21T01:05:00+00:00")
    store = AcceptanceFixPlanReviewStore(tmp_path / ".musicforge" / "fix-plan-reviews", plan_store=plan_store, fix_sprint_store=fix_store, kb_store=kb_store, project_store=plan_store.project_store)
    return store, plan_store, fix_store, plan.plan_id, sprint_id


def test_fix_plan_outcome_review_ready_and_stale_guard(tmp_path: Path, monkeypatch) -> None:
    store, _plan_store, _fix_store, plan_id, sprint_id = _closed_planned_sprint(tmp_path, monkeypatch)

    review = store.refresh_for_plan(plan_id, now="2026-05-21T01:06:00+00:00")
    saved = store.read_review(review.review_id)
    delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
    delta = read_json(delta_path)
    delta["summary"]["rating_delta"] = -5
    write_json(delta_path, delta)
    stale = store.read_review(review.review_id)

    assert review.status == "warning"
    assert review.summary["plan_effectiveness_score"] > 0
    assert review.summary["kb_evidence_helpfulness"] in {"mixed_positive", "positive", "neutral", "negative"}
    assert review.item_outcomes[0]["planned_item_id"] == "afpi-000001"
    assert saved.source["source_hash"] == review.source["source_hash"]
    assert stale.status == "stale"


def test_fix_plan_outcome_review_requires_used_closed_sprint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _acceptance_store, _analytics_store, kb_store, plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)
    plan = plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"]})
    store = AcceptanceFixPlanReviewStore(tmp_path / ".musicforge" / "fix-plan-reviews", plan_store=plan_store, fix_sprint_store=plan_store.fix_sprint_store, kb_store=kb_store, project_store=plan_store.project_store)

    with pytest.raises(AcceptanceFixPlanReviewStateError, match="requires a used plan"):
        store.refresh_for_plan(plan.plan_id)


def test_fix_plan_outcome_review_sanitizes_sensitive_notes(tmp_path: Path, monkeypatch) -> None:
    store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch)

    review = store.refresh_for_plan(plan_id)
    serialized = str(review.to_dict())

    assert "local-path-marker" not in serialized
    assert "masked-key-marker" not in serialized


def test_fix_plan_outcome_review_marks_synthetic_only_recheck(tmp_path: Path, monkeypatch) -> None:
    store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="synthetic")

    review = store.refresh_for_plan(plan_id, now="2026-05-21T01:06:00+00:00")

    assert review.status == "warning"
    assert review.summary["manual_recheck_confirmed"] is False
    assert review.summary["synthetic_only"] is True
    assert review.summary["manual_accepted_count"] == 0
    assert review.summary["synthetic_accepted_count"] == 1
    assert review.summary["manual_review_count"] == 0
    assert review.summary["synthetic_review_count"] == 1
    assert "synthetic_only_recheck" in review.warnings
