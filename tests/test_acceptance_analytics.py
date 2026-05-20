from __future__ import annotations

from pathlib import Path

from song_agent.acceptance_analytics import AcceptanceAnalyticsStore, AnalyticsScope
from song_agent.music_acceptance import AcceptanceStore


def _suite_with_review(tmp_path: Path, *, status: str = "needs_fix", review_mode: str = "manual", notes: str | None = None, tags: list[str] | None = None) -> tuple[AcceptanceStore, str, str]:
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"name": "Analytics Suite", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
    case = store.add_case(
        suite.suite_id,
        {
            "song_id": "rap_beat_001",
            "request": {"title": "Analytics Rap", "language": "English", "style": "rap beat hip-hop", "theme": "flow", "duration_seconds": 90},
        },
    )
    store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    store.run_health(suite.suite_id, case.case_id)
    store.write_review(
        suite.suite_id,
        case.case_id,
        {
            "status": status,
            "rating": 2 if status != "accepted" else 5,
            "playback_confirmed": True,
            "review_mode": review_mode,
            "listened_by": "qa reviewer",
            "audio_mode": "midi",
            "notes": notes or "Hook and rhythm need more lift; source path C:\\Users\\secret\\song.mid should be redacted.",
            "tags": tags or ["hook", "rhythm"],
            "markers": [{"beat": 8, "severity": "warning", "label": "hook", "note": "Hook is not memorable enough."}],
        },
    )
    store.build_report(suite.suite_id)
    return store, suite.suite_id, case.case_id


def test_acceptance_analytics_empty_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceAnalyticsStore(acceptance_store=AcceptanceStore(tmp_path / ".musicforge" / "acceptance"))

    report = store.refresh(AnalyticsScope())

    assert report["summary"]["readiness_status"] == "empty"
    assert report["source_summary"]["suite_count"] == 0
    assert report["songbook_heatmap"]


def test_acceptance_analytics_aggregates_issues_heatmap_and_recommendations(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_id = _suite_with_review(tmp_path)
    store = AcceptanceAnalyticsStore(acceptance_store=acceptance_store)

    report = store.refresh(AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id))
    rap = next(item for item in report["songbook_heatmap"] if item["song_id"] == "rap_beat_001")

    assert report["summary"]["readiness_status"] in {"needs_work", "blocked"}
    assert report["summary"]["needs_fix_count"] == 1
    assert report["summary"]["manual_coverage_rate"] == 1.0
    assert rap["top_issues"][:2] == ["hook", "rhythm"]
    assert rap["weakness_score"] >= 30
    assert report["recommendations"][0]["manual_required"] is True
    assert "C:\\Users" not in report["issue_taxonomy"][0]["example_excerpt"]


def test_acceptance_analytics_synthetic_review_not_manual_coverage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, _case_id = _suite_with_review(tmp_path, status="accepted", review_mode="synthetic", notes="Synthetic review confirms basic MIDI smoke playback.", tags=[])
    store = AcceptanceAnalyticsStore(acceptance_store=acceptance_store)

    report = store.refresh(AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id))

    assert report["summary"]["synthetic_review_count"] == 1
    assert report["summary"]["manual_coverage_rate"] == 0.0
    assert "manual_review_coverage_incomplete" in report["warnings"]


def test_acceptance_analytics_stale_after_source_change(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store, suite_id, case_id = _suite_with_review(tmp_path)
    store = AcceptanceAnalyticsStore(acceptance_store=acceptance_store)
    report = store.refresh(AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id), now="2026-05-20T00:00:00+00:00")

    acceptance_store.write_review(
        suite_id,
        case_id,
        {
            "status": "accepted",
            "rating": 5,
            "playback_confirmed": True,
            "review_mode": "manual",
            "audio_mode": "midi",
            "notes": "Manual follow-up confirms the revised hook and rhythm now work.",
        },
    )
    detail = store.get_report(report["report_id"])

    assert detail["stale"] is True
    assert detail["stale_reason"] == "source_changed"
