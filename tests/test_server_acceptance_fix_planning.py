from __future__ import annotations

from pathlib import Path

from tests.test_server_acceptance_fix_sprints import _project_with_acceptance_issue
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def test_acceptance_fix_plan_api_create_sprint_and_stale_guard(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, suite_id, case_id, analytics = _project_with_acceptance_issue(server)
        fix_status, fix = request_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics["report_id"]})
        fix_sprint_id = fix["fix_sprint"]["fix_sprint_id"]
        items_status, items = request_json(server, "GET", f"/api/acceptance/fix-sprints/{fix_sprint_id}/items")
        item_id = items["items"][0]["item_id"]
        request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/items/{item_id}/waive", {"reason": "manual correction verified"})
        recheck_status, recheck = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck["suite"]["suite_id"]
        detail_status, detail = request_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = detail["cases"][0]["case_id"]
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review", {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Accepted."})
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/delta/refresh")
        close_status, _close = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/close", {"force": True, "override_reason": "waived issue was manually verified"})
        kb_status, kb = request_json(server, "POST", "/api/acceptance/kb/refresh", {"type": "global"})

        _project_id2, _suite_id2, _case_id2, analytics2 = _project_with_acceptance_issue(server)
        preview_status, preview = request_json(server, "POST", "/api/acceptance/fix-plans/recommend", {"analytics_report_id": analytics2["report_id"], "kb_report_id": kb["knowledge_report"]["report_id"]})
        create_status, created = request_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2["report_id"], "kb_report_id": kb["knowledge_report"]["report_id"]})
        plan_id = created["fix_plan"]["plan_id"]
        list_status, listing = request_json(server, "GET", "/api/acceptance/fix-plans")
        detail_plan_status, detail_plan = request_json(server, "GET", f"/api/acceptance/fix-plans/{plan_id}")
        sprint_status, sprint = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "API Planned Sprint"})
        repeat_sprint_status, repeat_sprint = request_json(server, "POST", f"/api/acceptance/fix-plans/{plan_id}/create-fix-sprint", {"name": "Duplicate Planned Sprint"})
        repeat_detail_status, repeat_detail = request_json(server, "GET", f"/api/acceptance/fix-plans/{plan_id}")

        stale_create_status, stale_created = request_json(server, "POST", "/api/acceptance/fix-plans", {"analytics_report_id": analytics2["report_id"], "kb_report_id": kb["knowledge_report"]["report_id"]})
        stale_plan_id = stale_created["fix_plan"]["plan_id"]
        entries_status, entries = request_json(server, "GET", "/api/acceptance/kb/entries")
        entry_id = entries["entries"][0]["entry_id"]
        hide_status, _hidden = request_json(server, "POST", f"/api/acceptance/kb/entries/{entry_id}/hide")
        stale_sprint_status, stale_sprint = request_json(server, "POST", f"/api/acceptance/fix-plans/{stale_plan_id}/create-fix-sprint")

        hide_entry_id = kb["knowledge_report"]["issue_patterns"][0]["issue_type"]
    finally:
        stop_test_server(server)

    assert project_id
    assert suite_id
    assert case_id
    assert fix_status == 201
    assert items_status == 200
    assert recheck_status == 201
    assert detail_status == 200
    assert close_status == 200
    assert kb_status == 201
    assert preview_status == 200
    assert preview["summary"]["planned_item_count"] == 1
    assert create_status == 201
    assert created["summary"]["kb_match_count"] >= 1
    assert list_status == 200
    assert listing["summary"]["plan_count"] >= 1
    assert detail_plan_status == 200
    assert detail_plan["fix_plan"]["plan_id"] == plan_id
    assert sprint_status == 201
    assert sprint["fix_sprint"]["source"]["source_type"] == "acceptance_fix_plan"
    assert repeat_sprint_status == 409
    assert "already created" in repeat_sprint["error"]
    assert repeat_detail_status == 200
    assert repeat_detail["fix_plan"]["execution"]["created_fix_sprint_id"] == sprint["fix_sprint"]["fix_sprint_id"]
    assert stale_create_status == 201
    assert entries_status == 200
    assert hide_status == 200
    assert stale_sprint_status == 409
    assert "stale" in stale_sprint["error"].lower()
    assert hide_entry_id == "hook"
