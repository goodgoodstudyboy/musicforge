from __future__ import annotations

import sys
from pathlib import Path

from song_agent.cli import main
from song_agent.human_review_pack import HumanReviewPackStore
from song_agent.music_acceptance import AcceptanceStore


def test_cli_verify_human_review_pack_json_and_report_out(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    acceptance_store = AcceptanceStore(tmp_path / ".musicforge" / "acceptance")
    suite = acceptance_store.create_suite({"require_audio_if_renderer_configured": False})
    case = acceptance_store.add_case(suite.suite_id, {"request": {"title": "CLI HRP", "language": "English", "style": "pop", "theme": "cli", "duration_seconds": 90}})
    acceptance_store.generate_case(suite.suite_id, case.case_id, render_audio_mode="never")
    acceptance_store.run_health(suite.suite_id, case.case_id)
    pack_store = HumanReviewPackStore(acceptance_store)
    pack = pack_store.create_pack(suite.suite_id)["pack"]
    pack_store.build_zip(suite.suite_id, pack["pack_id"])
    report_path = tmp_path / "human-review-verification-report.json"

    monkeypatch.setattr(sys, "argv", ["song-agent", "verify-human-review-pack", str(pack_store.zip_path(suite.suite_id, pack["pack_id"])), "--json", "--report-out", str(report_path), "--strict"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert '"status": "passed"' in captured.out
    assert report_path.exists()
