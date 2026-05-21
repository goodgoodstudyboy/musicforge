from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.planning_rule_simulation import PlanningRuleSimulationStateError, PlanningRuleSimulationStore, planning_simulation_summary
from song_agent.projectio import read_json, write_json
from tests.test_acceptance_fix_plan_reviews import _closed_planned_sprint


def _synthetic_outcome_review(tmp_path: Path, monkeypatch):
    review_store, _plan_store, _fix_store, plan_id, sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="synthetic")
    review = review_store.refresh_for_plan(plan_id, now="2026-05-21T02:00:00+00:00")
    store = PlanningRuleSimulationStore(tmp_path / ".musicforge" / "planning-rule-simulations", review_store=review_store, project_store=review_store.project_store)
    return store, review_store, review, sprint_id


def test_planning_rule_simulation_synthetic_penalty_and_stale_guard(tmp_path: Path, monkeypatch) -> None:
    store, _review_store, review, sprint_id = _synthetic_outcome_review(tmp_path, monkeypatch)

    ruleset = store.create_ruleset({"template": "synthetic_strict", "description": "Synthetic strict local-path-marker masked-key-marker"}, now="2026-05-21T02:01:00+00:00")
    simulation = store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]}, now="2026-05-21T02:02:00+00:00")
    item = simulation.review_results[0]["item_results"][0]
    summary = planning_simulation_summary(simulation)

    assert simulation.status in {"ready", "warning"}
    assert item["simulated_planning_score"] < item["baseline_planning_score"]
    assert "synthetic_penalty" in item["applied_effects"]
    assert summary["synthetic_penalty_applied_count"] == 1
    assert "local-path-marker" not in str(summary)
    assert "masked-key-marker" not in str(summary)

    delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
    delta = read_json(delta_path)
    delta["summary"]["rating_delta"] = -7
    write_json(delta_path, delta)

    stale = store.read_simulation(simulation.simulation_id)
    assert stale.status == "stale"
    assert stale.summary["stale"] is True


def test_planning_rule_simulation_manual_bonus_and_archive_guards(tmp_path: Path, monkeypatch) -> None:
    review_store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="manual")
    review = review_store.refresh_for_plan(plan_id)
    store = PlanningRuleSimulationStore(tmp_path / ".musicforge" / "planning-rule-simulations", review_store=review_store, project_store=review_store.project_store)
    ruleset = store.create_ruleset({"template": "manual_conservative"})
    simulation = store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]})
    item = simulation.review_results[0]["item_results"][0]

    assert "manual_bonus" in item["applied_effects"]
    assert item["simulated_planning_score"] >= item["baseline_planning_score"]

    archived = store.archive_ruleset(ruleset.ruleset_id)
    assert archived.status == "archived"
    with pytest.raises(PlanningRuleSimulationStateError):
        store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]})


def test_planning_rule_simulation_explicit_stale_review_rejected(tmp_path: Path, monkeypatch) -> None:
    store, _review_store, review, sprint_id = _synthetic_outcome_review(tmp_path, monkeypatch)
    ruleset = store.create_ruleset({"template": "synthetic_strict"})
    delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
    delta = read_json(delta_path)
    delta["summary"]["rating_delta"] = -6
    write_json(delta_path, delta)

    with pytest.raises(PlanningRuleSimulationStateError, match="stale"):
        store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]})


def test_planning_rule_simulation_refresh_rejects_stale_source_review(tmp_path: Path, monkeypatch) -> None:
    store, _review_store, review, sprint_id = _synthetic_outcome_review(tmp_path, monkeypatch)
    ruleset = store.create_ruleset({"template": "synthetic_strict"})
    simulation = store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]})

    delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
    delta = read_json(delta_path)
    delta["summary"]["rating_delta"] = -6
    write_json(delta_path, delta)

    with pytest.raises(PlanningRuleSimulationStateError, match="stale"):
        store.refresh_simulation(simulation.simulation_id)
