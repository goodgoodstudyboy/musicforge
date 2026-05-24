from __future__ import annotations

from song_agent.acceptance_fix_planning import AcceptanceFixPlanningStore
from song_agent.planning_rule_governance import PlanningRuleGovernanceStore
from song_agent.planning_rule_impact import PlanningRuleImpactStore, planning_rule_impact_summary
from song_agent.planning_rule_simulation import PlanningRuleSimulationStore
from song_agent.projectio import read_json, write_json
from tests.test_acceptance_fix_plan_reviews import _closed_planned_sprint
from tests.test_acceptance_fix_planning import _planning_sources


def _active_governance(tmp_path, monkeypatch, *, template: str = "synthetic_strict"):
    review_store, _plan_store, _fix_store, plan_id, _sprint_id = _closed_planned_sprint(tmp_path, monkeypatch, review_mode="manual")
    review = review_store.refresh_for_plan(plan_id)
    simulation_store = PlanningRuleSimulationStore(tmp_path / ".musicforge" / "planning-rule-simulations", review_store=review_store, project_store=review_store.project_store)
    ruleset = simulation_store.create_ruleset({"template": template})
    simulation = simulation_store.create_simulation({"ruleset_id": ruleset.ruleset_id, "review_ids": [review.review_id]})
    governance = PlanningRuleGovernanceStore(tmp_path / ".musicforge" / "planning-rule-governance", simulation_store=simulation_store, project_store=review_store.project_store)
    promotion = governance.create_promotion({"ruleset_id": ruleset.ruleset_id, "simulation_id": simulation.simulation_id})
    approved = governance.approve_promotion(promotion.promotion_id, {"approval_note": "impact evidence"})
    version = governance.promote(approved.promotion_id)["version"]
    return governance, review_store, review_store.plan_store, version


def _governed_review(tmp_path, monkeypatch, governance: PlanningRuleGovernanceStore, review_mode: str = "manual"):
    monkeypatch.chdir(tmp_path)
    acceptance_store, analytics_store, kb_store, base_plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)
    plan_store = AcceptanceFixPlanningStore(tmp_path / ".musicforge" / "fix-plans", analytics_store=analytics_store, kb_store=kb_store, fix_sprint_store=base_plan_store.fix_sprint_store, project_store=analytics_store.project_store)
    plan_store.planning_rule_governance_store = governance
    plan = plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"], "max_items": 3})
    created = plan_store.create_fix_sprint(plan.plan_id, {"name": "Impact Sprint"})
    sprint_id = created["fix_sprint"]["fix_sprint_id"]
    fix_store = plan_store.fix_sprint_store
    item = fix_store.read_items(sprint_id)[0]
    fix_store.waive_item(sprint_id, item.item_id, "impact verified")
    recheck = fix_store.create_recheck_suite(sprint_id, {"profile_id": "developer_manual"})
    suite_id = recheck["suite"]["suite_id"]
    case = acceptance_store.list_cases(suite_id)[0]
    acceptance_store.generate_case(suite_id, case.case_id, render_audio_mode="never")
    acceptance_store.run_health(suite_id, case.case_id)
    acceptance_store.write_review(suite_id, case.case_id, {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": review_mode, "audio_mode": "midi", "notes": "Impact accepted."})
    acceptance_store.build_report(suite_id)
    fix_store.refresh_delta(sprint_id)
    fix_store.close(sprint_id, {"force": True, "override_reason": "waived issue was verified"})
    review_store = governance.simulation_store.review_store
    review_store.plan_store = plan_store
    review_store.fix_sprint_store = fix_store
    review_store.kb_store = kb_store
    review = review_store.refresh_for_plan(plan.plan_id)
    return plan, review, fix_store


def test_planning_rule_impact_reports_adoption_and_manual_warning(tmp_path, monkeypatch) -> None:
    governance, review_store, plan_store, version = _active_governance(tmp_path, monkeypatch)
    _governed_review(tmp_path, monkeypatch, governance, review_mode="manual")
    _governed_review(tmp_path, monkeypatch, governance, review_mode="synthetic")
    store = PlanningRuleImpactStore(tmp_path / ".musicforge" / "planning-rule-impact", governance_store=governance, plan_store=plan_store, review_store=review_store, project_store=review_store.project_store)

    report = store.refresh({"scope": {"type": "global"}})
    summary = planning_rule_impact_summary(report)

    assert report.active_version["version_id"] == version.version_id
    assert summary["observed_plan_count"] >= 2
    assert summary["observed_review_count"] >= 2
    assert summary["manual_review_count"] >= 1
    assert summary["synthetic_review_count"] >= 1
    assert summary["recommendation"] in {"candidate_improving", "continue_monitoring", "increase_manual_review", "rollback_watch", "insufficient_data"}
    assert store.report_is_stale(report) is False
    assert store.report_integrity_ok(report) is True


def test_planning_rule_impact_stale_after_active_switch_and_source_pollution(tmp_path, monkeypatch) -> None:
    governance, review_store, plan_store, version = _active_governance(tmp_path, monkeypatch)
    _governed_review(tmp_path, monkeypatch, governance, review_mode="manual")
    store = PlanningRuleImpactStore(tmp_path / ".musicforge" / "planning-rule-impact", governance_store=governance, plan_store=plan_store, review_store=review_store, project_store=review_store.project_store)
    report = store.refresh({"scope": {"type": "global"}})

    assert store.report_is_stale(report) is False
    version_path = governance.version_dir(version.version_id) / "version.json"
    polluted = read_json(version_path)
    polluted["approval"]["approved_by"] = "tampered-impact-reviewer"
    write_json(version_path, polluted)
    assert store.report_is_stale(report) is True


def test_planning_rule_impact_integrity_detects_derived_report_tampering(tmp_path, monkeypatch) -> None:
    governance, review_store, plan_store, _version = _active_governance(tmp_path, monkeypatch)
    _governed_review(tmp_path, monkeypatch, governance, review_mode="manual")
    store = PlanningRuleImpactStore(tmp_path / ".musicforge" / "planning-rule-impact", governance_store=governance, plan_store=plan_store, review_store=review_store, project_store=review_store.project_store)
    report = store.refresh({"scope": {"type": "global"}})
    report_path = store.report_dir(report.report_id) / "report.json"
    tampered = read_json(report_path)
    tampered["summary"]["recommendation"] = "candidate_improving"
    tampered["summary"]["manual_review_count"] = 99
    tampered["warnings"] = []
    write_json(report_path, tampered)
    loaded = store.get_report(report.report_id)

    assert store.report_is_stale(loaded) is False
    assert store.report_integrity_ok(loaded) is False
    assert planning_rule_impact_summary(loaded)["integrity_ok"] is False


def test_planning_rule_impact_no_active_version_is_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _acceptance_store, analytics_store, kb_store, plan_store, _suite_id, _case_id, report, kb_report = _planning_sources(tmp_path, monkeypatch)
    plan_store.create({"analytics_report_id": report["report_id"], "kb_report_id": kb_report["report_id"]})
    governance = PlanningRuleGovernanceStore(tmp_path / ".musicforge" / "planning-rule-governance", project_store=analytics_store.project_store)
    store = PlanningRuleImpactStore(tmp_path / ".musicforge" / "planning-rule-impact", governance_store=governance, plan_store=plan_store, project_store=analytics_store.project_store)

    impact = store.refresh({"scope": {"type": "global"}})

    assert impact.status == "missing"
    assert impact.summary["recommendation"] == "insufficient_data"
