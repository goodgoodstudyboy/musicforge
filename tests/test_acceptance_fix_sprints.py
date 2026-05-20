from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.acceptance_analytics import AcceptanceAnalyticsStore, AnalyticsScope
from song_agent.acceptance_fix_sprints import AcceptanceFixSprintStateError, AcceptanceFixSprintStore
from song_agent.music_acceptance import AcceptanceStore
from song_agent.projectio import read_json
from song_agent.projects import ProjectStore


def _suite_with_review(tmp_path: Path, *, status: str = "needs_fix") -> tuple[AcceptanceStore, AcceptanceAnalyticsStore, str, str, dict]:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    acceptance_store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance", project_store=project_store)
    suite = acceptance_store.create_suite({"name": "Fix Sprint Source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
    case = acceptance_store.add_case(
        suite.suite_id,
        {
            "song_id": "rap_beat_001",
            "request": {"title": "Fix Sprint Rap", "language": "English", "style": "rap beat hip-hop", "theme": "fix", "duration_seconds": 90},
        },
    )
    acceptance_store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    acceptance_store.run_health(suite.suite_id, case.case_id)
    acceptance_store.write_review(
        suite.suite_id,
        case.case_id,
        {
            "status": status,
            "rating": 2 if status != "accepted" else 5,
            "playback_confirmed": True,
            "review_mode": "manual",
            "audio_mode": "midi",
            "notes": "Hook and rhythm need a clearer lift.",
            "tags": ["hook", "rhythm"],
        },
    )
    acceptance_store.build_report(suite.suite_id)
    analytics_store = AcceptanceAnalyticsStore(acceptance_store=acceptance_store, project_store=project_store)
    report = analytics_store.refresh(AnalyticsScope.from_values(scope_type="suite", suite_id=suite.suite_id), now="2026-05-20T00:00:00+00:00")
    return acceptance_store, analytics_store, suite.suite_id, case.case_id, report


def test_fix_sprint_create_from_analytics_and_stale_guard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, analytics_store, suite_id, case_id, report = _suite_with_review(tmp_path)
    store = AcceptanceFixSprintStore(tmp_path / ".musicforge" / "acceptance-fix-sprints", acceptance_store=acceptance_store, analytics_store=analytics_store)

    sprint = store.create_from_analytics({"analytics_report_id": report["report_id"], "name": "Fix Sprint"})
    items = store.read_items(sprint.fix_sprint_id)

    acceptance_store.write_review(
        suite_id,
        case_id,
        {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual recheck accepted."},
    )

    assert sprint.status == "planned"
    assert len(items) == 1
    assert items[0].source["recommendation_id"] == "rec-001"
    assert store.read_sprint(sprint.fix_sprint_id).status == "stale"
    with pytest.raises(AcceptanceFixSprintStateError):
        store.create_review_tasks(sprint.fix_sprint_id)


def test_fix_sprint_waive_recheck_delta_and_close(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, analytics_store, _suite_id, _case_id, report = _suite_with_review(tmp_path)
    store = AcceptanceFixSprintStore(tmp_path / ".musicforge" / "acceptance-fix-sprints", acceptance_store=acceptance_store, analytics_store=analytics_store)
    sprint = store.create_from_analytics({"analytics_report_id": report["report_id"]})
    item = store.read_items(sprint.fix_sprint_id)[0]

    store.waive_item(sprint.fix_sprint_id, item.item_id, "covered by arrangement rewrite")
    recheck = store.create_recheck_suite(sprint.fix_sprint_id)
    recheck_suite_id = recheck["suite"]["suite_id"]
    recheck_case = acceptance_store.list_cases(recheck_suite_id)[0]
    acceptance_store.generate_case(recheck_suite_id, recheck_case.case_id, render_audio_mode="never")
    acceptance_store.run_health(recheck_suite_id, recheck_case.case_id)
    acceptance_store.write_review(
        recheck_suite_id,
        recheck_case.case_id,
        {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Recheck confirms the issue is resolved."},
    )
    acceptance_store.build_report(recheck_suite_id)
    delta = store.refresh_delta(sprint.fix_sprint_id)
    closeout = store.close(sprint.fix_sprint_id)

    assert delta["summary"]["status"] in {"improved", "unchanged"}
    assert closeout["status"] == "passed"
    assert store.read_sprint(sprint.fix_sprint_id).status == "closed"
    saved = read_json(tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint.fix_sprint_id / "closeout-report.json")
    assert saved["summary"]["status"] == "passed"
