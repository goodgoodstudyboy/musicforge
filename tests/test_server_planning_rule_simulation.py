from __future__ import annotations

from pathlib import Path

from song_agent.projectio import read_json, write_json
from tests.test_server_acceptance_fix_plan_reviews import _server_plan_with_closed_sprint
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_releases import _signed_project


def test_planning_rule_simulation_api_and_signoff_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Planning Simulation Track")
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Planning Simulation Release", "release_type": "demo_pack", "primary_artist": "QA"})
        release_id = release["release"]["release_id"]
        track_status, _track = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        plan_id, sprint_id, review_project_id, _analytics_report_id = _server_plan_with_closed_sprint(server, scope={"type": "release", "release_id": release_id}, planned_review_mode="synthetic")
        review_status, review = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
        review_id = review["outcome_review"]["review_id"]
        create_status, ruleset = request_json(server, "POST", "/api/acceptance/planning-rulesets", {"template": "synthetic_strict"})
        ruleset_id = ruleset["ruleset"]["ruleset_id"]
        list_status, listing = request_json(server, "GET", "/api/acceptance/planning-rulesets")
        clone_status, clone = request_json(server, "POST", f"/api/acceptance/planning-rulesets/{ruleset_id}/clone", {"name": "Clone"})
        validate_status, validation = request_json(server, "POST", f"/api/acceptance/planning-rulesets/{ruleset_id}/validate")
        sim_status, simulation = request_json(server, "POST", "/api/acceptance/planning-simulations", {"ruleset_id": ruleset_id, "scope": {"type": "global"}, "review_ids": [review_id]})
        simulation_id = simulation["simulation"]["simulation_id"]
        get_status, got = request_json(server, "GET", f"/api/acceptance/planning-simulations/{simulation_id}")
        qa_status, _qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = request_json(server, "GET", f"/api/projects/{review_project_id}/export")
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{review_project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "force": True, "override_reason": "acceptance smoke remains warning", "require_planning_rule_simulation": True, "planning_simulation_id": simulation_id})
        reset_status, _reset = request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": "stale simulation guard"})

        delta_path = tmp_path / ".musicforge" / "acceptance-fix-sprints" / sprint_id / "delta-report.json"
        delta = read_json(delta_path)
        delta["summary"]["rating_delta"] = -8
        write_json(delta_path, delta)
        stale_get_status, stale_get = request_json(server, "GET", f"/api/acceptance/planning-simulations/{simulation_id}")
        stale_sign_status, stale_sign = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "require_planning_rule_simulation": True, "planning_simulation_id": simulation_id})
        archive_status, archived = request_json(server, "POST", f"/api/acceptance/planning-simulations/{simulation_id}/archive")
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert track_status == 200
    assert review_status == 201
    assert create_status == 201
    assert list_status == 200
    assert listing["summary"]["ruleset_count"] >= 1
    assert clone_status == 201
    assert clone["ruleset"]["ruleset_id"] != ruleset_id
    assert validate_status == 200
    assert validation["validation"]["status"] == "passed"
    assert sim_status == 201
    assert simulation["summary"]["synthetic_penalty_applied_count"] >= 1
    assert get_status == 200
    assert got["summary"]["simulation_id"] == simulation_id
    assert qa_status == 200
    assert export_status == 200
    assert export["manifest"]["planning_rule_simulation"]["simulation_id"] == simulation_id
    assert project_export_status == 200
    assert project_export["planning_rule_simulation_summary"]["simulation_id"] == simulation_id
    assert final_export_status == 200
    assert final_export["final_export"]["planning_rule_simulation"]["simulation_id"] == simulation_id
    assert sign_status == 200
    assert signoff["signoff"]["acceptance_gate"]["planning_rule_simulation"]["status"] == "passed"
    assert reset_status == 200
    assert stale_get_status == 200
    assert stale_get["summary"]["stale"] is True
    assert stale_sign_status == 409
    assert "stale" in stale_sign["error"].lower()
    assert archive_status == 200
    assert archived["summary"]["status"] == "archived"
