from __future__ import annotations

from song_agent.projectio import read_json, write_json
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_planning_rule_governance import test_planning_rule_governance_api_fix_plan_export_and_signoff  # noqa: F401
from tests.test_server_releases import _signed_project


def _impact_governed_release(server) -> tuple[str, str, str, str]:
    from tests.test_server_acceptance_fix_plan_reviews import _server_plan_with_closed_sprint

    project_id = _signed_project(server, "Impact Track")
    release_status, release = request_json(server, "POST", "/api/releases", {"name": "Impact Release", "release_type": "demo_pack", "primary_artist": "QA"})
    release_id = release["release"]["release_id"]
    request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
    plan_id, sprint_id, review_project_id, analytics_report_id = _server_plan_with_closed_sprint(server, scope={"type": "release", "release_id": release_id})
    review_status, review = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
    review_id = review["outcome_review"]["review_id"]
    ruleset_status, ruleset = request_json(server, "POST", "/api/acceptance/planning-rulesets", {"template": "synthetic_strict"})
    ruleset_id = ruleset["ruleset"]["ruleset_id"]
    sim_status, simulation = request_json(server, "POST", "/api/acceptance/planning-simulations", {"ruleset_id": ruleset_id, "scope": {"type": "release", "release_id": release_id}, "review_ids": [review_id]})
    promotion_status, promotion = request_json(server, "POST", "/api/acceptance/planning-rule-governance/promotions", {"ruleset_id": ruleset_id, "simulation_id": simulation["simulation"]["simulation_id"]})
    promotion_id = promotion["promotion"]["promotion_id"]
    request_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/approve", {"approved_by": "tester", "approval_note": "impact accepted"})
    promote_status, promoted = request_json(server, "POST", f"/api/acceptance/planning-rule-governance/promotions/{promotion_id}/promote", {"promoted_by": "tester"})
    version_id = promoted["version"]["version_id"]
    governed_status, governed = request_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics_report_id, "scope": {"type": "release", "release_id": release_id}, "max_items": 1})
    assert release_status == 201
    assert review_status == 201
    assert ruleset_status == 201
    assert sim_status == 201
    assert promotion_status == 201
    assert promote_status == 201
    assert governed_status == 201
    return release_id, version_id, review_project_id, sprint_id


def test_planning_rule_impact_api_export_and_signoff_gate(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, version_id, review_project_id, _sprint_id = _impact_governed_release(server)
        refresh_status, refreshed = request_json(server, "POST", "/api/acceptance/planning-rule-impact/reports", {"scope": {"type": "release", "release_id": release_id}})
        report_id = refreshed["impact_report"]["report_id"]
        list_status, listing = request_json(server, "GET", f"/api/acceptance/planning-rule-impact/reports?release_id={release_id}")
        detail_status, detail = request_json(server, "GET", f"/api/acceptance/planning-rule-impact/reports/{report_id}")
        latest_status, latest = request_json(server, "GET", f"/api/acceptance/planning-rule-impact/latest?release_id={release_id}")
        existing_status, existing = request_json(server, "POST", f"/api/acceptance/planning-rule-impact/reports/{report_id}/refresh")
        qa_status, _qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = request_json(server, "GET", f"/api/projects/{review_project_id}/export")
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{review_project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "force": True, "override_reason": "impact smoke remains warning", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})
        reset_status, _reset = request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "impact stale guard"})
        archive_status, archived = request_json(server, "POST", f"/api/acceptance/planning-rule-impact/reports/{report_id}/archive")
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert refreshed["summary"]["active_version_id"] == version_id
    assert list_status == 200
    assert listing["summary"]["report_count"] >= 1
    assert detail_status == 200
    assert detail["summary"]["report_id"] == report_id
    assert latest_status == 200
    assert latest["summary"]["report_id"] == report_id
    assert existing_status == 200
    assert existing["summary"]["report_id"] == report_id
    assert qa_status == 200
    assert export_status == 200
    assert export["manifest"]["planning_rule_impact"]["report_id"] == report_id
    assert any(file.get("path") == "planning-rule-impact-summary.json" for file in export["manifest"].get("files", []) if isinstance(file, dict))
    assert project_export_status == 200
    assert project_export["planning_rule_impact_summary"]["report_id"] == report_id
    assert final_export_status == 200
    assert final_export["final_export"]["planning_rule_impact"]["report_id"] == report_id
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["planning_rule_impact"]["status"] in {"passed", "warning"}
    assert reset_status == 200
    assert archive_status == 200
    assert archived["summary"]["status"] == "archived"


def test_planning_rule_impact_signoff_blocks_stale_and_allows_forced_rollback_recommendation(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _version_id, _project_id, sprint_id = _impact_governed_release(server)
        refresh_status, refreshed = request_json(server, "POST", "/api/acceptance/planning-rule-impact/reports", {"scope": {"type": "release", "release_id": release_id}})
        report_id = refreshed["impact_report"]["report_id"]
        report_path = tmp_path / ".musicforge" / "planning-rule-impact" / "reports" / report_id / "report.json"
        report = read_json(report_path)
        report["summary"]["recommendation"] = "rollback_recommended"
        report["summary"]["rollback_recommended"] = True
        report["status"] = "warning"
        write_json(report_path, report)
        rollback_status, rollback = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})
        forced_status, forced = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "force": True, "override_reason": "manual impact override", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})
        reset_status, _reset = request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "verify stale impact"})
        delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
        delta = read_json(delta_path)
        delta["summary"]["rating_delta"] = -9
        write_json(delta_path, delta)
        stale_status, stale = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "force": True, "override_reason": "cannot force stale", "require_planning_rule_impact": True, "planning_rule_impact_report_id": report_id})
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert rollback_status == 409
    assert "rollback" in rollback["error"].lower()
    assert forced_status == 200
    assert forced["signoff"]["acceptance_gate"]["planning_rule_impact"]["status"] == "warning"
    assert reset_status == 200
    assert stale_status == 409
    assert "stale" in stale["error"].lower()
