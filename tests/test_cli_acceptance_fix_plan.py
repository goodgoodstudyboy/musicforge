from __future__ import annotations

import sys
from pathlib import Path

from song_agent.cli import main
from tests.test_acceptance_fix_planning import _planning_sources


def test_acceptance_fix_plan_cli_create_show_recommend_and_sprint(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    _acceptance_store, _analytics_store, _kb_store, _plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-plan", "create", "--analytics-report-id", report["report_id"], "--kb-report-id", kb_report["report_id"]])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    output = capsys.readouterr().out
    assert "MusicForge acceptance-fix-plan" in output
    assert "plan: afp-000001" in output

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-plan", "recommend", "--analytics-report-id", report["report_id"], "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert '"planned_item_count": 1' in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-plan", "show", "afp-000001"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert "status:" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-plan", "create-fix-sprint", "afp-000001"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert "created_fix_sprint: afs-000002" in capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-plan", "create-fix-sprint", "afp-000001"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 1
    assert "already created" in capsys.readouterr().err
