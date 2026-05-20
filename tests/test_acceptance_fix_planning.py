from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.acceptance_fix_planning import AcceptanceFixPlanStateError, AcceptanceFixPlanningStore
from song_agent.acceptance_kb import AcceptanceKnowledgeBaseStore
from tests.test_acceptance_fix_sprints import _suite_with_review
from tests.test_acceptance_kb import _closed_fix_sprint


def _planning_sources(tmp_path: Path, monkeypatch):
    kb_store, _fix_sprint_id = _closed_fix_sprint(tmp_path, monkeypatch)
    kb_report = kb_store.refresh(now="2026-05-21T00:00:00+00:00")
    acceptance_store, analytics_store, suite_id, case_id, report = _suite_with_review(tmp_path)
    plan_store = AcceptanceFixPlanningStore(tmp_path / ".musicforge" / "fix-plans", analytics_store=analytics_store, kb_store=kb_store, fix_sprint_store=kb_store.fix_sprint_store, project_store=analytics_store.project_store)
    return acceptance_store, analytics_store, kb_store, plan_store, suite_id, case_id, report, kb_report


def test_fix_plan_create_matches_kb_and_creates_sprint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _acceptance_store, _analytics_store, _kb_store, plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)

    plan = plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"], "max_items": 5}, now="2026-05-21T00:10:00+00:00")
    result = plan_store.create_fix_sprint(plan.plan_id, {"name": "Planned Sprint"}, now="2026-05-21T00:11:00+00:00")

    assert plan.status in {"ready", "warning"}
    assert plan.summary["planned_item_count"] == 1
    assert plan.summary["kb_match_count"] >= 1
    assert plan.planned_items[0]["knowledge"]["top_entry_ids"]
    assert result["fix_sprint"]["source"]["source_type"] == "acceptance_fix_plan"
    assert result["fix_sprint"]["source"]["fix_plan_id"] == plan.plan_id
    assert result["items"][0]["source"]["source_type"] == "planned_item"
    assert result["plan"]["status"] == "used"


def test_fix_plan_hidden_kb_default_excluded_and_explicit_included(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _acceptance_store, _analytics_store, kb_store, plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)
    entry = kb_store.search_entries({"issue_type": "hook"})[0]
    kb_store.hide_entry(entry.entry_id)
    kb_store.refresh(now="2026-05-21T00:01:00+00:00")

    default_plan = plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"]})
    hidden_plan = plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"], "include_hidden_kb": True})

    assert default_plan.summary["kb_match_count"] == 0
    assert "no_kb_history" in default_plan.warnings
    assert hidden_plan.summary["kb_match_count"] >= 1
    assert "hidden_entries_included" in hidden_plan.warnings


def test_fix_plan_stale_source_blocks_create_fix_sprint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, _analytics_store, _kb_store, plan_store, suite_id, case_id, report, _kb_report = _planning_sources(tmp_path, monkeypatch)
    plan = plan_store.create({"analytics_report_id": report["report_id"]})

    acceptance_store.write_review(
        suite_id,
        case_id,
        {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual follow-up accepted."},
    )

    assert plan_store.read_plan(plan.plan_id).status == "stale"
    with pytest.raises(AcceptanceFixPlanStateError):
        plan_store.create_fix_sprint(plan.plan_id)
