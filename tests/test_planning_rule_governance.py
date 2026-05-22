from __future__ import annotations

import pytest

from song_agent.acceptance_fix_planning import AcceptanceFixPlanningStore
from song_agent.planning_rule_governance import PlanningRuleGovernanceStateError, PlanningRuleGovernanceStore
from song_agent.planning_rule_simulation import PlanningRuleSimulationStore
from song_agent.projectio import read_json, write_json
from tests.test_acceptance_fix_plan_reviews import _closed_planned_sprint
from tests.test_acceptance_fix_planning import _planning_sources


def _governance_sources(tmp_path, monkeypatch):
    review_store, _plan_store, _fix_store, plan_id, sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="synthetic")
    review = review_store.refresh_for_plan(plan_id)
    simulation_store = PlanningRuleSimulationStore(tmp_path / ".musicforge" / "planning-rule-simulations", review_store=review_store, project_store=review_store.project_store)
    ruleset = simulation_store.create_ruleset({"template": "synthetic_strict"})
    simulation = simulation_store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]})
    governance = PlanningRuleGovernanceStore(tmp_path / ".musicforge" / "planning-rule-governance", simulation_store=simulation_store, project_store=review_store.project_store)
    return governance, simulation_store, ruleset, simulation, sprint_id


def test_planning_rule_governance_promote_rollback_and_freeze(tmp_path, monkeypatch) -> None:
    governance, simulation_store, ruleset, simulation, _sprint_id = _governance_sources(tmp_path, monkeypatch)

    promotion = governance.create_promotion({"ruleset_id": ruleset.ruleset_id, "simulation_id": simulation.simulation_id, "note": "strict synthetic"})
    assert promotion.status == "pending"
    with pytest.raises(PlanningRuleGovernanceStateError):
        governance.promote(promotion.promotion_id)

    approved = governance.approve_promotion(promotion.promotion_id, {"approved_by": "tester", "approval_note": "mixed warning accepted"})
    promoted = governance.promote(approved.promotion_id, {"promoted_by": "tester"})
    version = promoted["version"]
    active = governance.active_summary()

    assert version.status == "active"
    assert active["active_version_id"] == version.version_id
    assert governance.version_integrity_ok(version)

    simulation_store.archive_ruleset(ruleset.ruleset_id)
    assert governance.frozen_ruleset(version.version_id)["ruleset_id"] == ruleset.ruleset_id
    assert governance.version_evidence_is_stale(version) is False

    ruleset2 = simulation_store.create_ruleset({"template": "manual_conservative"})
    review_id = simulation.source["review_ids"][0]
    simulation2 = simulation_store.create_simulation({"ruleset_id": ruleset2.ruleset_id, "review_ids": [review_id]})
    promotion2 = governance.create_promotion({"ruleset_id": ruleset2.ruleset_id, "simulation_id": simulation2.simulation_id})
    approved2 = governance.approve_promotion(promotion2.promotion_id, {"approval_note": "second active"})
    promoted2 = governance.promote(approved2.promotion_id)
    assert promoted2["version"].previous_version_id == version.version_id
    assert governance.read_version(version.version_id).status == "superseded"

    rolled = governance.rollback({"target_version_id": version.version_id, "reason": "restore strict synthetic"})
    assert rolled["version"].version_id == version.version_id
    assert governance.active_summary()["active_version_id"] == version.version_id
    assert governance.read_version(promoted2["version"].version_id).status == "rolled_back"


def test_planning_rule_governance_stale_promotion_blocks_approval(tmp_path, monkeypatch) -> None:
    governance, _simulation_store, ruleset, simulation, sprint_id = _governance_sources(tmp_path, monkeypatch)
    promotion = governance.create_promotion({"ruleset_id": ruleset.ruleset_id, "simulation_id": simulation.simulation_id})

    delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
    delta = read_json(delta_path)
    delta["summary"]["rating_delta"] = -8
    write_json(delta_path, delta)

    stale = governance.read_promotion(promotion.promotion_id)
    assert stale.status == "stale"
    with pytest.raises(PlanningRuleGovernanceStateError, match="stale"):
        governance.approve_promotion(promotion.promotion_id, {"approval_note": "no"})


def test_fix_plan_records_active_governance_version_and_legacy_default(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _acceptance_store, analytics_store, kb_store, plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)
    legacy = plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"]})
    assert legacy.source["planning_rule_governance"]["governance_status"] == "legacy_default"

    governance, _simulation_store, ruleset, simulation, _sprint_id = _governance_sources(tmp_path, monkeypatch)
    promotion = governance.create_promotion({"ruleset_id": ruleset.ruleset_id, "simulation_id": simulation.simulation_id})
    approved = governance.approve_promotion(promotion.promotion_id, {"approval_note": "record active"})
    version = governance.promote(approved.promotion_id)["version"]
    governed_store = AcceptanceFixPlanningStore(tmp_path / ".musicforge" / "fix-plans", analytics_store=analytics_store, kb_store=kb_store, fix_sprint_store=kb_store.fix_sprint_store, project_store=analytics_store.project_store)
    governed_store.planning_rule_governance_store = governance
    governed = governed_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"]})

    assert governed.source["planning_rule_governance"]["planning_rule_version_id"] == version.version_id
    assert governed.summary["generated_with_active_rules"] is True
    assert legacy.source["planning_rule_governance"]["governance_status"] == "legacy_default"
