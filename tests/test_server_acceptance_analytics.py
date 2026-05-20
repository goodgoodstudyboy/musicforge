from __future__ import annotations

from pathlib import Path

from song_agent.auth import AuthConfig
from song_agent.server import create_server
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job


TOKEN = "analytics-token"


def _acceptance_case(server, *, project_id: str | None = None) -> tuple[str, str]:
    payload = {"name": "Analytics API", "profile_id": "developer_manual", "require_audio_if_renderer_configured": False}
    _status, created = request_json(server, "POST", "/api/acceptance/suites", payload)
    suite_id = created["suite"]["suite_id"]
    case_payload = {
        "song_id": "rap_beat_001",
        "request": {"title": "Analytics API Song", "language": "English", "style": "rap beat hip-hop", "theme": "api", "duration_seconds": 90},
    }
    if project_id:
        case_payload["project_id"] = project_id
        case_payload["version_id"] = "v001"
        case_payload["source_type"] = "project_version"
    case_status, case_data = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases", case_payload)
    case_id = case_data["case"]["case_id"]
    if not project_id:
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
    else:
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
    request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
    request_json(
        server,
        "POST",
        f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
        {
            "status": "needs_fix",
            "rating": 2,
            "playback_confirmed": True,
            "review_mode": "manual",
            "audio_mode": "midi",
            "notes": "Hook and rhythm need more confidence in the generated review.",
            "tags": ["hook", "rhythm"],
        },
    )
    request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
    assert case_status == 201
    return suite_id, case_id


def test_acceptance_analytics_api_global_suite_and_stale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        suite_id, case_id = _acceptance_case(server)
        refresh_status, refreshed = request_json(server, "POST", "/api/acceptance/analytics/refresh", {"scope": "global"})
        report_id = refreshed["analytics"]["report_id"]
        get_status, latest = request_json(server, "GET", "/api/acceptance/analytics")
        suite_status, suite_report = request_json(server, "GET", f"/api/acceptance/suites/{suite_id}/analytics")
        request_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review",
            {"status": "accepted", "rating": 5, "playback_confirmed": True, "review_mode": "manual", "audio_mode": "midi", "notes": "Manual reviewer confirms the hook and rhythm are now acceptable."},
        )
        detail_status, detail = request_json(server, "GET", f"/api/acceptance/analytics/reports/{report_id}")
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert refreshed["summary"]["readiness_status"] in {"needs_work", "blocked"}
    assert get_status == 200
    assert latest["analytics"]["report_id"] == report_id
    assert suite_status == 200
    assert suite_report["analytics"]["scope"]["suite_id"] == suite_id
    assert detail_status == 200
    assert detail["analytics"]["stale"] is True


def test_acceptance_analytics_recommendation_create_review_task(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        created_status, created = request_json(server, "POST", "/api/projects", {"name": "Analytics Project"})
        project_id = created["project"]["project_id"]
        version_status, version_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": {"title": "Analytics Project", "language": "English", "style": "rap beat hip-hop", "theme": "analytics"}, "name": "v1"},
        )
        job = wait_for_job(server, version_data["job"]["job_id"])
        request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
        request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        suite_id, _case_id = _acceptance_case(server, project_id=project_id)
        refresh_status, refreshed = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/analytics/refresh")
        report_id = refreshed["analytics"]["report_id"]
        recommendation_id = next(item["recommendation_id"] for item in refreshed["analytics"]["recommendations"] if item["type"] == "create_review_task")
        create_task_status, task = request_json(server, "POST", f"/api/acceptance/analytics/reports/{report_id}/recommendations/{recommendation_id}/create-review-task", {})
        duplicate_status, duplicate = request_json(server, "POST", f"/api/acceptance/analytics/reports/{report_id}/recommendations/{recommendation_id}/create-review-task", {})
        list_status, listing = request_json(server, "GET", f"/api/projects/{project_id}/review-tasks")
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert version_status == 202
    assert job["status"] == "completed"
    assert refresh_status == 201
    assert create_task_status == 201
    assert task["status"] == "created"
    assert duplicate_status == 200
    assert duplicate["status"] == "existing"
    assert list_status == 200
    assert listing["tasks"][0]["source"]["source_type"] == "acceptance_analytics"


def test_acceptance_analytics_release_scope_and_auth(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        suite_id, _case_id = _acceptance_case(server)
        release_status, release = request_json(server, "POST", "/api/releases", {"name": "Analytics Release", "release_type": "demo_pack", "primary_artist": "QA"})
        release_id = release["release"]["release_id"]
        release_refresh_status, release_refresh = request_json(server, "POST", f"/api/releases/{release_id}/acceptance-analytics/refresh")
    finally:
        stop_test_server(server)

    auth_server = create_server("127.0.0.1", 0, auth_config=AuthConfig(enabled=True, token=TOKEN))
    try:
        import threading

        thread = threading.Thread(target=auth_server.serve_forever, daemon=True)
        thread.start()
        unauthorized_status, _unauthorized = request_json(auth_server, "GET", "/api/acceptance/analytics")
    finally:
        stop_test_server(auth_server)

    assert suite_id
    assert release_status == 201
    assert release_refresh_status == 201
    assert release_refresh["analytics"]["scope"]["release_id"] == release_id
    assert unauthorized_status == 401
