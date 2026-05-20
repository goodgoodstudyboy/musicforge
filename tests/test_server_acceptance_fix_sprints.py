from __future__ import annotations

from pathlib import Path

from song_agent.projectio import read_json, write_json
from tests.test_server_acceptance_analytics import _acceptance_case
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job
from tests.test_server_releases import _signed_project


def _project_with_acceptance_issue(server) -> tuple[str, str, str, dict]:
    created_status, created = request_json(server, "POST", "/api/projects", {"name": "Fix Sprint API Project"})
    assert created_status == 201
    project_id = created["project"]["project_id"]
    version_status, version_data = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/versions",
        {"request": {"title": "Fix Sprint API", "language": "English", "style": "rap beat hip-hop", "theme": "fix sprint"}, "name": "v1"},
    )
    assert version_status == 202
    assert wait_for_job(server, version_data["job"]["job_id"])["status"] == "completed"
    request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
    request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
    suite_id, case_id = _acceptance_case(server, project_id=project_id)
    refresh_status, refreshed = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/analytics/refresh")
    assert refresh_status == 201
    return project_id, suite_id, case_id, refreshed["analytics"]


def test_acceptance_fix_sprint_api_creates_tasks_and_blocks_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, suite_id, case_id, analytics = _project_with_acceptance_issue(server)
        create_status, created = request_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics["report_id"], "name": "API Fix Sprint"})
        fix_sprint_id = created["fix_sprint"]["fix_sprint_id"]
        tasks_status, tasks = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-review-tasks")
        duplicate_status, duplicate = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-review-tasks")
        list_status, listing = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks")

        _project_id2, suite_id2, case_id2, analytics2 = _project_with_acceptance_issue(server)
        stale_create_status, stale_created = request_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics2["report_id"]})
        stale_sprint_id = stale_created["fix_sprint"]["fix_sprint_id"]
        request_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id2}/cases/{case_id2}/review",
            {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual reviewer accepted the stale case."},
        )
        stale_task_status, stale_task = request_json(server, "POST", f"/api/acceptance/fix-sprints/{stale_sprint_id}/create-review-tasks")
    finally:
        stop_test_server(server)

    assert suite_id
    assert case_id
    assert create_status == 201
    assert created["summary"]["item_count"] == 1
    assert tasks_status == 201
    assert tasks["results"][0]["status"] == "created"
    assert duplicate_status == 200
    assert duplicate["results"][0]["status"] == "existing"
    assert list_status == 200
    assert listing["tasks"][0]["source"]["source_type"] == "acceptance_fix_sprint"
    assert stale_create_status == 201
    assert stale_task_status == 409
    assert "stale" in stale_task["error"].lower()


def test_acceptance_fix_sprint_closeout_and_release_evidence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Fix Sprint Release Track")
        suite_id, _case_id = _acceptance_case(server, project_id=project_id)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Fix Sprint Release", "release_type": "demo_pack", "primary_artist": "QA"})
        release_id = release["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        analytics_status, analytics_data = request_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
        fix_status, fix_data = request_json(server, "POST", "/api/acceptance/fix-sprints", {"analytics_report_id": analytics_data["analytics"]["report_id"], "scope": {"type": "release", "release_id": release_id}})
        fix_sprint_id = fix_data["fix_sprint"]["fix_sprint_id"]
        task_status, task_data = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-review-tasks")
        task_id = task_data["results"][0]["task_id"]
        task_path = Path(".musicforge") / "projects" / project_id / "review-tasks" / task_id / "task.json"
        task = read_json(task_path)
        task["status"] = "resolved"
        task["resolution_note"] = "Acceptance-driven fix completed."
        write_json(task_path, task)
        request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/refresh-status")
        recheck_status, recheck = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/create-recheck-suite", {"profile_id": "developer_manual"})
        recheck_suite_id = recheck["suite"]["suite_id"]
        detail_status, detail = request_json(server, "GET", f"/api/acceptance/suites/{recheck_suite_id}")
        recheck_case_id = detail["cases"][0]["case_id"]
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/generate", {"render_audio": "never"})
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/health")
        request_json(
            server,
            "POST",
            f"/api/acceptance/suites/{recheck_suite_id}/cases/{recheck_case_id}/review",
            {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Recheck accepted."},
        )
        request_json(server, "POST", f"/api/acceptance/suites/{recheck_suite_id}/report")
        delta_status, delta = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/delta/refresh")
        close_status, closeout = request_json(server, "POST", f"/api/acceptance/fix-sprints/{fix_sprint_id}/close")
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        project_export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "force": True, "override_reason": "acceptance analytics remains blocked in smoke", "require_acceptance_fix_sprint": True})
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert analytics_status == 201
    assert fix_status == 201
    assert task_status == 201
    assert recheck_status == 201
    assert detail_status == 200
    assert delta_status == 200
    assert delta["summary"]["fixed_item_count"] == 1
    assert close_status == 200
    assert closeout["summary"]["status"] == "passed"
    assert export_status == 200
    assert export["manifest"]["acceptance_fix_sprint"]["status"] == "closed"
    assert project_export_status == 200
    assert project_export["acceptance_fix_sprint_summary"]["status"] == "closed"
    assert final_export_status == 200
    assert final_export["final_export"]["acceptance_fix_sprint"]["status"] == "closed"
    assert sign_status == 200
    assert signed["signoff"]["acceptance_gate"]["acceptance_fix_sprint"]["status"] == "passed"
