from __future__ import annotations

import json
import sys

from song_agent.cli import main
from song_agent.planning_rule_governance import PlanningRuleGovernanceStore
from song_agent.planning_rule_simulation import PlanningRuleSimulationStore
from tests.test_acceptance_fix_plan_reviews import _closed_planned_sprint


def test_planning_rule_impact_cli_refresh_list_show_refresh_archive(tmp_path, monkeypatch, capsys) -> None:
    review_store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="manual")
    review = review_store.refresh_for_plan(plan_id)
    simulation_store = PlanningRuleSimulationStore(tmp_path / ".musicforge" / "planning-rule-simulations", review_store=review_store, project_store=review_store.project_store)
    ruleset = simulation_store.create_ruleset({"template": "synthetic_strict"})
    simulation = simulation_store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]})
    governance = PlanningRuleGovernanceStore(tmp_path / ".musicforge" / "planning-rule-governance", simulation_store=simulation_store, project_store=review_store.project_store)
    promotion = governance.create_promotion({"ruleset_id": ruleset.ruleset_id, "simulation_id": simulation.simulation_id})
    governance.promote(governance.approve_promotion(promotion.promotion_id, {"approval_note": "cli impact"}).promotion_id)

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-impact", "refresh", "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    report_id = json.loads(capsys.readouterr().out)["impact_report"]["report_id"]

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-impact", "list", "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert json.loads(capsys.readouterr().out)["summary"]["report_count"] >= 1

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-impact", "show", report_id, "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert json.loads(capsys.readouterr().out)["summary"]["report_id"] == report_id

    out_path = tmp_path / "impact-refresh.json"
    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-impact", "refresh-existing", report_id, "--report-out", str(out_path), "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert out_path.exists()
    capsys.readouterr()

    monkeypatch.setattr(sys, "argv", ["song-agent", "planning-rule-impact", "archive", report_id, "--json"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0
    assert json.loads(capsys.readouterr().out)["summary"]["status"] == "archived"
