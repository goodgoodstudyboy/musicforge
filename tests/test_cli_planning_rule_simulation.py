from __future__ import annotations

import json
import sys
from pathlib import Path

from song_agent.cli import main
from tests.test_acceptance_fix_plan_reviews import _closed_planned_sprint


def test_planning_rule_simulation_cli_create_run_show(tmp_path: Path, monkeypatch, capsys) -> None:
    review_store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="synthetic")
    review = review_store.refresh_for_plan(plan_id)

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-ruleset", "create", "--template", "synthetic_strict", "--name", "Synthetic Strict", "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    ruleset_data = json.loads(capsys.readouterr().out)
    ruleset_id = ruleset_data["ruleset"]["ruleset_id"]

    report_path = tmp_path / "runs" / "planning-simulation.json"
    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-simulation", "run", "--ruleset-id", ruleset_id, "--review-id", review.review_id, "--json", "--report-out", str(report_path)])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    sim_data = json.loads(capsys.readouterr().out)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    simulation_id = sim_data["simulation"]["simulation_id"]

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-simulation", "show", simulation_id])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    output = capsys.readouterr().out

    assert sim_data["summary"]["synthetic_penalty_applied_count"] == 1
    assert saved["summary"]["simulation_id"] == simulation_id
    assert "MusicForge planning-simulation" in output
    assert f"simulation: {simulation_id}" in output
