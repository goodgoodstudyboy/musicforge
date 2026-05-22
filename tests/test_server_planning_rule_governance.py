from __future__ import annotations

from song_agent.projectio import read_json, write_json
from tests.test_server_acceptance_fix_plan_reviews import _server_plan_with_closed_sprint
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_releases import _signed_project


def test_planning_rule_governance_api_fix_plan_export_and_signoff(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Governance Track")
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Governance Release", "release_type": "demo_pack", "primary_artist": "QA"})
        release_id = release["release"]["release_id"]
        track_status, _track = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        missing_status, missing = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_planning_rule_governance": True})

        plan_id, sprint_id, review_project_id, analytics_report_id = _server_plan_with_closed_sprint(server, scope={"type": "release", "release_id": release_id}, planned_review_mode="synthetic")
        review_status, review = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
        review_id = review["outcome_review"]["review_id"]
        ruleset_status, ruleset = request_json(server, "POST", "/api/acceptance/planning-rulesets", {"template": "synthetic_strict"})
        ruleset_id = ruleset["ruleset"]["ruleset_id"]
        sim_status, simulation = request_json(server, "POST", "/api/acceptance/planning-simulations", {"ruleset_id": ruleset_id, "scope": {"type": "release", "release_id": release_id}, "review_ids": [review_id]})
        simulation_id = simulation["simulation"]["simulation_id"]
        promotion_status, promotion = request_json(server, "POST", "/api/acceptance/planning-rule-governance/promotions", {"ruleset_id": ruleset_id, "simulation_id": simulation_id, "note": "promote"})
        promotion_id = promotion["promotion"]["promotion_id"]
        approve_status, approved = request_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/approve", {"approved_by": "tester", "approval_note": "approved"})
        promote_status, promoted = request_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/promote", {"promoted_by": "tester"})
        version_id = promoted["version"]["version_id"]
        active_status, active = request_json(server, "GET", "/api/acceptance/planning-rule-governance/active")

        governed_plan_status, governed_plan = request_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics_report_id, "max_items": 1})
        qa_status, _qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = request_json(server, "GET", f"/api/projects/{review_project_id}/export")
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{review_project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "force": True, "override_reason": "acceptance smoke remains warning", "require_planning_rule_governance": True, "planning_rule_version_id": version_id})
        reset_status, _reset = request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "stale governance guard"})

        delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
        delta = read_json(delta_path)
        delta["summary"]["rating_delta"] = -8
        write_json(delta_path, delta)
        stale_sign_status, stale_sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_planning_rule_governance": True, "planning_rule_version_id": version_id})

        rollback_status, rolled = request_json(server, "POST", "/api/acceptance/planning-rule-governance/rollback", {"target_version_id": version_id, "reason": "same version rollback"})
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert track_status == 200
    assert missing_status == 409
    assert "missing" in missing["error"].lower()
    assert review_status == 201
    assert ruleset_status == 201
    assert sim_status == 201
    assert promotion_status == 201
    assert approve_status == 200
    assert approved["summary"]["status"] == "approved"
    assert promote_status == 201
    assert active_status == 200
    assert active["summary"]["active_version_id"] == version_id
    assert governed_plan_status == 201
    assert governed_plan["fix_plan"]["source"]["planning_rule_governance"]["planning_rule_version_id"] == version_id
    assert qa_status == 200
    assert export_status == 200
    assert export["manifest"]["planning_rule_governance"]["active_version_id"] == version_id
    assert project_export_status == 200
    assert project_export["planning_rule_governance_summary"]["active_version_id"] == version_id
    assert final_export_status == 200
    assert final_export["final_export"]["planning_rule_governance"]["active_version_id"] == version_id
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["planning_rule_governance"]["status"] == "passed"
    assert reset_status == 200
    assert stale_sign_status == 409
    assert "stale" in stale_sign["error"].lower()
    assert rollback_status == 200
    assert rolled["summary"]["active_version_id"] == version_id
