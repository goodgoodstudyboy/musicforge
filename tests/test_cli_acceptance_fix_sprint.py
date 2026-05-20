from __future__ import annotations

import sys
from pathlib import Path

from song_agent.acceptance_analytics import AcceptanceAnalyticsStore, AnalyticsScope
from song_agent.cli import main
from song_agent.music_acceptance import AcceptanceStore


def test_acceptance_fix_sprint_cli_create_show_and_error(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = acceptance_store.create_suite({"name": "CLI Fix Source", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
    case = acceptance_store.add_case(
        suite.suite_id,
        {"song_id": "rap_beat_001", "request": {"title": "CLI Fix", "language": "English", "style": "rap beat hip-hop", "theme": "cli", "duration_seconds": 90}},
    )
    acceptance_store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    acceptance_store.run_health(suite.suite_id, case.case_id)
    acceptance_store.write_review(
        suite.suite_id,
        case.case_id,
        {"status": "needs_fix", "rating": 2, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "CLI hook fix", "tags": ["hook"]},
    )
    acceptance_store.build_report(suite.suite_id)
    report = AcceptanceAnalyticsStore(acceptance_store=acceptance_store).refresh(AnalyticsScope.from_values(scope_type="suite", suite_id=suite.suite_id))

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-sprint", "create", "--analytics-report-id", report["report_id"]])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    output = capsys.readouterr().out
    assert "MusicForge acceptance-fix-sprint" in output
    assert "status: planned" in output

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-sprint", "show", "afs-000001"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert "afs-000001" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-sprint", "show", "afs-999999"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 1
    assert "error:" in capsys.readouterr().err
