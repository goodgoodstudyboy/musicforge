from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.acceptance_diff import build_acceptance_diff
from song_agent.music_acceptance import AcceptanceStateError, AcceptanceStore
from song_agent.regression_songbook import BUILTIN_SONGBOOK_ID, BUILTIN_SONGBOOK_VERSION, list_regression_songs


def test_acceptance_suite_generate_health_review_report_signoff(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"name": "Developer Acceptance", "min_rating": 3})
    case = store.add_case(
        suite.suite_id,
        {
            "name": "upbeat pop",
            "request": {"title": "Acceptance Song", "language": "English", "style": "upbeat pop", "theme": "test", "duration_seconds": 90},
        },
    )

    generated = store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    health = store.run_health(suite.suite_id, case.case_id)
    review = store.write_review(
        suite.suite_id,
        case.case_id,
        {
            "rating": 4,
            "status": "accepted",
            "playback_confirmed": True,
            "notes": "Manual review confirms structure and MIDI playback are acceptable.",
            "audio_mode": "midi",
            "listened_by": "tester",
        },
    )
    report = store.build_report(suite.suite_id)
    signoff = store.signoff(suite.suite_id, {"signed_by": "tester"})

    assert generated.status == "generated"
    assert health["status"] in {"passed", "warning"}
    assert review["status"] == "accepted"
    assert report["status"] == "passed"
    assert signoff["status"] == "signed"
    assert (store.case_dir(suite.suite_id, case.case_id) / "song.mid").exists()

    with pytest.raises(AcceptanceStateError):
        store.write_review(
            suite.suite_id,
            case.case_id,
            {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "Cannot mutate signed suite.", "audio_mode": "midi"},
        )

    reset = store.reset_signoff(suite.suite_id, "revise review")
    assert reset["event"] == "acceptance_signoff_reset"


def test_acceptance_review_requires_playback_and_notes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({})
    case = store.add_case(suite.suite_id, {"request": {"title": "Review Guard", "language": "English", "style": "pop", "theme": "test", "duration_seconds": 90}})
    store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    store.run_health(suite.suite_id, case.case_id)

    with pytest.raises(ValueError):
        store.write_review(suite.suite_id, case.case_id, {"rating": 4, "status": "accepted", "playback_confirmed": False, "notes": "long enough note"})

    with pytest.raises(ValueError):
        store.write_review(suite.suite_id, case.case_id, {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "short"})


def test_acceptance_report_detects_source_and_report_tamper(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"min_rating": 3})
    case = store.add_case(suite.suite_id, {"request": {"title": "Tamper Guard", "language": "English", "style": "pop", "theme": "test", "duration_seconds": 90}})
    store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    store.run_health(suite.suite_id, case.case_id)
    store.write_review(
        suite.suite_id,
        case.case_id,
        {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "Review confirms generated MIDI is acceptable.", "audio_mode": "midi"},
    )
    report = store.build_report(suite.suite_id)
    assert report["verification"]["status"] == "passed"

    review_path = store.review_path(suite.suite_id, case.case_id)
    review = read_json(review_path)
    review["listened_by"] = "tampered-reviewer"
    write_json(review_path, review)
    source_failed = store.read_report(suite.suite_id)
    assert source_failed["status"] == "failed"
    assert source_failed["verification"]["source_status"] == "failed"

    store.write_review(
        suite.suite_id,
        case.case_id,
        {"rating": 4, "status": "accepted", "playback_confirmed": True, "notes": "Review confirms generated MIDI is acceptable.", "audio_mode": "midi"},
    )
    store.build_report(suite.suite_id)
    store.signoff(suite.suite_id, {"signed_by": "tester"})
    report_path = store.report_path(suite.suite_id)
    tampered_report = read_json(report_path)
    tampered_report["status"] = "passed" if tampered_report.get("status") != "passed" else "failed"
    write_json(report_path, tampered_report)
    content_failed = store.read_report(suite.suite_id)
    assert content_failed["status"] == "failed"
    assert content_failed["verification"]["content_status"] == "failed"
    signoff = store.read_signoff(suite.suite_id)
    assert signoff["report_integrity"]["status"] == "failed"


def test_release_candidate_requires_complete_songbook_coverage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"profile_id": "release_candidate", "require_audio_if_renderer_configured": False})
    case = store.add_case(
        suite.suite_id,
        {
            "song_id": "upbeat_pop_001",
            "request": {"title": "Manual Gate", "language": "English", "style": "upbeat pop", "theme": "test", "duration_seconds": 90},
        },
    )
    store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    store.run_health(suite.suite_id, case.case_id)
    store.write_review(
        suite.suite_id,
        case.case_id,
        {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Synthetic review should not make this release-ready.", "audio_mode": "midi", "review_mode": "synthetic"},
    )
    synthetic_report = store.build_report(suite.suite_id)
    assert synthetic_report["status"] == "failed"
    assert synthetic_report["summary"]["acceptance_status"] == "failed"
    assert any("manual review required" in blocker for blocker in synthetic_report["blockers"])

    store.write_review(
        suite.suite_id,
        case.case_id,
        {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Manual playback review confirms this regression song is acceptable.", "audio_mode": "midi", "review_mode": "manual"},
    )
    incomplete_report = store.build_report(suite.suite_id)
    assert incomplete_report["status"] == "failed"
    assert incomplete_report["summary"]["acceptance_status"] == "failed"
    assert incomplete_report["summary"]["release_ready"] is False
    assert incomplete_report["summary"]["expected_case_count"] == 12
    assert incomplete_report["summary"]["songbook_coverage_status"] == "incomplete"
    assert "sad_ballad_001" in incomplete_report["summary"]["missing_song_ids"]
    assert any("complete regression songbook coverage" in blocker for blocker in incomplete_report["blockers"])


def test_release_candidate_full_songbook_can_be_release_ready_and_diff_tracks_song_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"profile_id": "release_candidate", "require_audio_if_renderer_configured": False})
    for song in list_regression_songs():
        case = store.add_case(
            suite.suite_id,
            {
                "name": song["title"],
                "song_id": song["song_id"],
                "songbook_id": BUILTIN_SONGBOOK_ID,
                "songbook_version": BUILTIN_SONGBOOK_VERSION,
                "expectations": song["expectations"],
                "request": song["request"],
            },
        )
        store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
        store.run_health(suite.suite_id, case.case_id)
        store.write_review(
            suite.suite_id,
            case.case_id,
            {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Manual playback review confirms this regression song is acceptable.", "audio_mode": "midi", "review_mode": "manual"},
        )

    manual_report = store.build_report(suite.suite_id)
    assert manual_report["summary"]["acceptance_status"] == "release_ready_passed"
    assert manual_report["summary"]["release_ready"] is True
    assert manual_report["summary"]["songbook_coverage_status"] == "complete"
    assert manual_report["summary"]["missing_song_ids"] == []
    assert manual_report["summary"]["duplicate_song_ids"] == []
    diff = build_acceptance_diff(manual_report, manual_report)
    assert diff["status"] == "passed"
    assert diff["summary"]["song_count"] == 12
    assert diff["songs"][0]["song_id"] == "acoustic_folk_001"


def test_release_candidate_duplicate_song_id_blocks_coverage(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"profile_id": "release_candidate", "require_audio_if_renderer_configured": False})
    for index in range(12):
        case = store.add_case(
            suite.suite_id,
            {
                "name": f"Duplicate {index}",
                "song_id": "upbeat_pop_001",
                "request": {"title": f"Duplicate {index}", "language": "English", "style": "upbeat pop", "theme": "duplicate", "duration_seconds": 90},
            },
        )
        store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
        store.run_health(suite.suite_id, case.case_id)
        store.write_review(
            suite.suite_id,
            case.case_id,
            {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Manual playback review confirms this duplicate song is acceptable.", "audio_mode": "midi", "review_mode": "manual"},
        )

    report = store.build_report(suite.suite_id)

    assert report["status"] == "failed"
    assert report["summary"]["songbook_coverage_status"] == "incomplete"
    assert report["summary"]["duplicate_song_ids"] == ["upbeat_pop_001"]
    assert "sad_ballad_001" in report["summary"]["missing_song_ids"]


def test_legacy_acceptance_mode_defaults_to_developer_manual(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")

    suite = store.create_suite({"name": "Legacy Suite", "mode": "developer_self_test"})

    assert suite.profile_id == "developer_manual"
    assert suite.mode == "developer_self_test"
