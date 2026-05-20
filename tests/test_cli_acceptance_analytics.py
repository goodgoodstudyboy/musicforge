from __future__ import annotations

import sys
from pathlib import Path

import pytest

from song_agent.cli import main
from song_agent.music_acceptance import AcceptanceStore


def test_cli_acceptance_analytics_json_and_report_out(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = store.create_suite({"profile_id": "developer_manual", "require_audio_if_renderer_configured": False})
    case = store.add_case(suite.suite_id, {"song_id": "upbeat_pop_001", "request": {"title": "CLI Analytics", "language": "English", "style": "upbeat pop", "theme": "cli"}})
    store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    store.run_health(suite.suite_id, case.case_id)
    store.write_review(suite.suite_id, case.case_id, {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual CLI analytics review confirms playback and hook quality."})
    store.build_report(suite.suite_id)
    report_out = tmp_path / "analytics.json"

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-analytics", "--scope", "suite", "--suite-id", suite.suite_id, "--refresh", "--json", "--report-out", str(report_out)])
    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    assert report_out.exists()
    output = capsys.readouterr().out
    assert '"schema_version": "acceptance_analytics.v1"' in output
    assert '"suite_id": "' + suite.suite_id + '"' in output
