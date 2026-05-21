from __future__ import annotations

from pathlib import Path

from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_server_releases import _signed_project


def _server_plan_with_closed_sprint(server, *, scope: dict | None = None) -> tuple[str, str, str, str]:
    from tests.test_server_acceptance_fix_sprints import _project_with_acceptance_issue

    project_id, _suite_id, _case_id, analytics = _project_with_acceptance_issue(server)
    fix_status, fix = request_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics["report_id"]})
    seed_sprint_id = fix["fix_sprint"]["fix_sprint_id"]
    items_status, items = request_json(server, "GET", f"/api/acceptance/fix-sprints/{seed_sprint_id}/items")
    item_id = items["items"][0]["item_id"]
    request_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/items/{item_id}/waive", {"reason": "manual correction verified"})
    recheck_status, recheck = request_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
    recheck_suite_id = recheck["suite"]["suite_id"]
    detail_status, detail = request_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
    recheck_case_id = detail["cases"][0]["case_id"]
    request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
    request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
    request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Accepted."})
    request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
    request_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/delta/refresh")
    request_json(server, "POST", f"/api/acceptance/fix-sprints/{seed_sprint_id}/close", {"force": True, "override_reason": "waived issue was manually verified"})
    kb_status, kb = request_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})

    _project_id2, _suite_id2, _case_id2, analytics2 = _project_with_acceptance_issue(server)
    plan_payload = {"analytics_report_id": analytics2["report_id"], "kb_report_id": kb["knowledge_report"]["report_id"]}
    if scope:
        plan_payload["scope"] = scope
    create_status, created = request_json(server, "POST", "/api/acceptance/fix-plans", plan_payload)
    plan_id = created["fix_plan"]["plan_id"]
    sprint_status, sprint = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "Outcome Sprint"})
    planned_sprint_id = sprint["fix_sprint"]["fix_sprint_id"]
    planned_item_id = sprint["items"][0]["item_id"]
    request_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/items/{planned_item_id}/waive", {"reason": "manual rewrite verified"})
    planned_recheck_status, planned_recheck = request_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
    planned_suite_id = planned_recheck["suite"]["suite_id"]
    planned_detail_status, planned_detail = request_json(server, "GET", f"/api/acceptance/suites/{planned_suite_id}")
    planned_case_id = planned_detail["cases"][0]["case_id"]
    request_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/generate", {"render_audio": "never"})
    request_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/health")
    request_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/cases/{planned_case_id}/review", {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Accepted planned fix."})
    request_json(server, "POST", f"/api/acceptance/suites/{planned_suite_id}/report")
    request_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/delta/refresh")
    request_json(server, "POST", f"/api/acceptance/fix-sprints/{planned_sprint_id}/close", {"force": True, "override_reason": "waived issue was manually verified"})
    assert fix_status == 201
    assert items_status == 200
    assert recheck_status == 201
    assert detail_status == 200
    assert kb_status == 201
    assert create_status == 201
    assert sprint_status == 201
    assert planned_recheck_status == 201
    assert planned_detail_status == 200
    assert project_id
    return plan_id, planned_sprint_id, _project_id2, analytics2["report_id"]


def test_acceptance_fix_plan_review_api_refresh_list_archive_and_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        missing_status, missing = request_json(server, "GET", "/api/acceptance/fix-plans/afp-000001/outcome-review")
        plan_id, sprint_id, _project_id, _analytics_report_id = _server_plan_with_closed_sprint(server)
        refresh_status, refreshed = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
        review_id = refreshed["outcome_review"]["review_id"]
        get_status, got = request_json(server, "GET", f"/api/acceptance/fix-plans/{plan_id}/outcome-review")
        list_status, listing = request_json(server, "GET", "/api/acceptance/fix-plan-reviews")
        detail_status, detail = request_json(server, "GET", f"/api/acceptance/fix-plan-reviews/{review_id}")
        archive_status, archived = request_json(server, "POST", f"/api/acceptance/fix-plan-reviews/{review_id}/archive")
    finally:
        stop_test_server(server)

    assert missing_status == 200
    assert missing["summary"]["status"] == "missing"
    assert refresh_status == 201
    assert refreshed["summary"]["plan_id"] == plan_id
    assert refreshed["outcome_review"]["fix_sprint_id"] == sprint_id
    assert get_status == 200
    assert got["summary"]["review_id"] == review_id
    assert list_status == 200
    assert listing["summary"]["review_count"] >= 1
    assert detail_status == 200
    assert detail["summary"]["review_id"] == review_id
    assert archive_status == 200
    assert archived["summary"]["status"] == "archived"


def test_acceptance_fix_plan_review_export_and_release_signoff_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Outcome Review Release Track")
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Outcome Review Release", "release_type": "demo_pack", "primary_artist": "QA"})
        release_id = release["release"]["release_id"]
        track_status, _track = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        plan_id, _sprint_id, review_project_id, _analytics_report_id = _server_plan_with_closed_sprint(server, scope={"type": "release", "release_id": release_id})
        refresh_status, refreshed = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/outcome-review/refresh")
        review_id = refreshed["outcome_review"]["review_id"]
        qa_status, _qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = request_json(server, "GET", f"/api/projects/{review_project_id}/export")
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{review_project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "force": True, "override_reason": "acceptance analytics remains blocked in smoke", "require_acceptance_fix_plan_review": True, "acceptance_fix_plan_review_id": review_id})
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert release_status == 201
    assert track_status == 200
    assert qa_status == 200
    assert export_status == 200
    assert export["manifest"]["acceptance_fix_plan_review"]["review_id"] == review_id
    assert any(file.get("path") == "acceptance-fix-plan-review-summary.json" for file in export["manifest"].get("files", []) if isinstance(file, dict))
    assert project_export_status == 200
    assert project_export["acceptance_fix_plan_review_summary"]["review_id"] == review_id
    assert final_export_status == 200
    assert final_export["final_export"]["acceptance_fix_plan_review"]["review_id"] == review_id
    assert sign_status == 200
    assert signed["signoff"]["acceptance_gate"]["acceptance_fix_plan_review"]["status"] == "passed"
