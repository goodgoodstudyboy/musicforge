from __future__ import annotations

import json
import sys
from pathlib import Path

from song_agent.cli import main
from tests.test_acceptance_fix_plan_reviews import _closed_planned_sprint


def test_acceptance_fix_plan_review_cli_refresh_json_and_report_out(tmp_path: Path, monkeypatch, capsys) -> None:
    _store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch)

    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-plan", "review", plan_id, "--refresh"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    output = capsys.readouterr().out
    assert "MusicForge acceptance-fix-plan review" in output
    assert f"plan: {plan_id}" in output

    report_path = tmp_path / "runs" / "fix-plan-review.json"
    monkeypatch.setattr(sys, "argv", ["song-agent", "acceptance-fix-plan", "review", plan_id, "--json", "--report-out", str(report_path)])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    data = json.loads(capsys.readouterr().out)
    saved = json.loads(report_path.read_text(encoding="utf-8"))

    assert data["summary"]["plan_id"] == plan_id
    assert data["summary"]["review_id"].startswith("afpr-")
    assert saved["summary"]["plan_id"] == plan_id
