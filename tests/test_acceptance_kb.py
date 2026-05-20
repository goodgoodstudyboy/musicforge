from __future__ import annotations

from pathlib import Path

from song_agent.acceptance_fix_sprints import AcceptanceFixSprintStore
from song_agent.acceptance_kb import AcceptanceKnowledgeBaseStore, effectiveness_score
from tests.test_acceptance_fix_sprints import _suite_with_review


def _closed_fix_sprint(tmp_path: Path, monkeypatch) -> tuple[AcceptanceKnowledgeBaseStore, str]:
    monkeypatch.chdir(tmp_path)
    acceptance_store, analytics_store, _suite_id, _case_id, report = _suite_with_review(tmp_path)
    fix_store = AcceptanceFixSprintStore(tmp_path / ".musicforge" / "acceptance-fix-sprints", acceptance_store=acceptance_store, analytics_store=analytics_store)
    sprint = fix_store.create_from_analytics({"analytics_report_id": report["report_id"]})
    item = fix_store.read_items(sprint.fix_sprint_id)[0]
    fix_store.waive_item(sprint.fix_sprint_id, item.item_id, "covered by manual rewrite")
    recheck = fix_store.create_recheck_suite(sprint.fix_sprint_id)
    recheck_suite_id = recheck["suite"]["suite_id"]
    recheck_case = acceptance_store.list_cases(recheck_suite_id)[0]
    acceptance_store.generate_case(recheck_suite_id, recheck_case.case_id, render_audio_mode="never")
    acceptance_store.run_health(recheck_suite_id, recheck_case.case_id)
    acceptance_store.write_review(
        recheck_suite_id,
        recheck_case.case_id,
        {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Accepted after rewrite with local-path-marker and masked-key-marker."},
    )
    acceptance_store.build_report(recheck_suite_id)
    fix_store.refresh_delta(sprint.fix_sprint_id)
    fix_store.close(sprint.fix_sprint_id, {"force": True, "override_reason": "waived issue was manually verified"})
    return AcceptanceKnowledgeBaseStore(tmp_path / ".musicforge" / "acceptance-kb", fix_sprint_store=fix_store), sprint.fix_sprint_id


def test_acceptance_kb_refresh_builds_entry_patterns_and_recommendation(tmp_path: Path, monkeypatch) -> None:
    store, fix_sprint_id = _closed_fix_sprint(tmp_path, monkeypatch)

    report = store.refresh(now="2026-05-21T00:00:00+00:00")
    second = store.refresh(now="2026-05-21T00:01:00+00:00")
    entries = store.search_entries({"issue_type": "hook"})
    recommendation = store.recommend({"issue_types": ["hook"], "style": "rap", "song_id": "rap_beat_001"})

    assert report["summary"]["entry_count"] == 1
    assert second["summary"]["entry_count"] == 1
    assert entries[0].source["fix_sprint_id"] == fix_sprint_id
    assert entries[0].fix["waived_count"] == 1
    assert entries[0].outcome["effectiveness_score"] > 0
    assert report["issue_patterns"][0]["issue_type"] == "hook"
    assert recommendation["status"] == "available"
    assert "suggested_next_actions" in recommendation
    serialized = str(entries[0].to_dict())
    assert "masked-key-marker" not in serialized
    assert "local-path-marker" not in serialized


def test_acceptance_kb_hide_excludes_default_search(tmp_path: Path, monkeypatch) -> None:
    store, _fix_sprint_id = _closed_fix_sprint(tmp_path, monkeypatch)
    store.refresh()
    entry = store.search_entries({"issue_type": "hook"})[0]

    store.hide_entry(entry.entry_id)

    assert store.search_entries({"issue_type": "hook"}) == []
    assert len(store.search_entries({"issue_type": "hook"}, include_hidden=True)) == 1


def test_effectiveness_score_penalizes_force_waiver_and_open_items() -> None:
    base = effectiveness_score({"before_readiness": "blocked", "after_readiness": "ready", "rating_delta": 3, "issue_count_delta": -3}, task_statuses=["resolved"], open_item_count=0, waived_count=0, forced=False)
    penalized = effectiveness_score({"before_readiness": "blocked", "after_readiness": "ready", "rating_delta": 3, "issue_count_delta": -3}, task_statuses=["resolved"], open_item_count=1, waived_count=1, forced=True)

    assert base == 95
    assert penalized < base
