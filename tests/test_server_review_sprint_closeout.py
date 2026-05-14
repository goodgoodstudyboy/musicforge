from __future__ import annotations

import json
from http.client import HTTPConnection
from pathlib import Path

from song_agent.auth import AuthConfig
from song_agent.server import create_server
from song_agent.projectio import read_json, write_json
from tests.test_server_edits import request_json, request_payload, start_test_server, stop_test_server, wait_for_job
from tests.test_server_review_sprints import _create_two_review_tasks


def test_review_sprint_closeout_gate_force_signoff_export_and_final(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, first_task_id, _second_task_id = _create_two_review_tasks(server)
        sprint_status, sprint_data = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": [first_task_id]})
        sprint_id = sprint_data["sprint"]["sprint_id"]
        get_status, get_data = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout")
        close_status, close_error = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {})
        force_missing_status, force_missing = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {"force": True})
        force_status, forced = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/review-sprints/{sprint_id}/close",
            {"force": True, "override_reason": r"manual playback accepted api_key=sk-secret-value C:\Users\demo\song.wav", "notes": r"ok C:\Users\demo"},
        )
        signoff_status, signoff = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/signoff")
        refresh_after_status, refreshed_after = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout/refresh")
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        final_status, final_data = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001", "force": True})
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_audio": False, "include_stems": False, "include_stem_audio": False})
        serialized = json.dumps({"forced": forced, "signoff": signoff, "export": project_export, "final": final_export}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert sprint_status == 201
    assert get_status == 200
    assert get_data["summary"]["close_allowed"] is False
    assert close_status == 409
    assert "closeout gate failed" in close_error["error"]
    assert force_missing_status == 400
    assert "override_reason" in force_missing["error"]
    assert force_status == 200
    assert forced["sprint"]["status"] == "closed"
    assert forced["signoff"]["forced"] is True
    assert signoff_status == 200
    assert signoff["summary"]["status"] == "signed"
    assert refresh_after_status == 200
    assert refreshed_after["summary"]["status"] in {"failed", "warning", "passed"}
    assert signoff["signoff"]["signed_at"] == forced["signoff"]["signed_at"]
    assert export_status == 200
    assert project_export["review_sprints"][0]["closeout_summary"]["status"]
    assert project_export["review_sprints"][0]["signoff_summary"]["status"] == "signed"
    assert final_status == 200
    assert final_data["project"]["final_version_id"] == "v001"
    assert final_export_status == 200
    assert final_export["final_export"]["review_sprint_closeout"]["latest_sprint_id"] == sprint_id
    assert final_export["final_export"]["review_sprint_closeout"]["signed_sprint_count"] == 1
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized
    assert str(tmp_path) not in serialized


def test_review_sprint_closeout_gate_passes_after_apply_and_auth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MUSICFORGE_API_TOKEN", "secret-token")
    server = _start_auth_server("secret-token")
    headers = {"Authorization": "Bearer secret-token"}
    try:
        project_id, preview_id = _create_auth_preview(server, headers)
        first_task_id = _create_auth_task(server, project_id, preview_id, headers=headers)
        local_status, local = _request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{first_task_id}/candidates", {"strategies": ["balanced"], "render_midi": False}, headers=headers)
        candidate_id = local["candidates"][0]["candidate_id"]
        apply_status, applied = _request_json(server, "POST", f"/api/projects/{project_id}/review-tasks/{first_task_id}/candidates/{candidate_id}/apply", {"version_name": "Closeout Child"}, headers=headers)
        job = _wait_for_job(server, applied["job"]["job_id"], headers)
        sprint_status, sprint_data = _request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": [first_task_id]}, headers=headers)
        sprint_id = sprint_data["sprint"]["sprint_id"]
        metrics_status, _metrics = _request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/metrics/refresh", headers=headers)
        unauthorized_status, unauthorized = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout")
        close_status, closed = _request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {"selected_version_id": applied["version"]["version_id"]}, headers=headers)
    finally:
        stop_test_server(server)
        monkeypatch.delenv("MUSICFORGE_API_TOKEN", raising=False)

    assert local_status == 201
    assert apply_status == 202
    assert job["status"] == "completed"
    assert sprint_status == 201
    assert metrics_status == 200
    assert unauthorized_status == 401
    assert "Unauthorized" in unauthorized["error"]
    assert close_status == 200
    assert closed["closeout_summary"]["close_allowed"] is True
    assert closed["signoff_summary"]["status"] == "signed"
    assert closed["signoff"]["selected_version_id"] == applied["version"]["version_id"]


def test_review_sprint_closeout_does_not_treat_latest_version_as_delivery_confirmation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, first_task_id, _second_task_id = _create_two_review_tasks(server)
        project_path = Path(".musicforge") / "projects" / project_id / "project.json"
        project_data = read_json(project_path)
        write_json(project_path, {**project_data, "selected_version_id": None, "final_version_id": None, "latest_version_id": "v001"})
        task_path = Path(".musicforge") / "projects" / project_id / "review-tasks" / first_task_id / "task.json"
        task_data = read_json(task_path)
        write_json(task_path, {**task_data, "status": "resolved", "selected_candidate_id": None, "applied_version_id": None})
        sprint_status, sprint_data = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": [first_task_id]})
        sprint_id = sprint_data["sprint"]["sprint_id"]
        refresh_status, refreshed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout/refresh")
        close_status, close_error = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/close", {})
        missing_check = next(check for check in refreshed["closeout_report"]["checks"] if check["check_id"] == "missing_applied_version")
    finally:
        stop_test_server(server)

    assert sprint_status == 201
    assert refresh_status == 200
    assert refreshed["closeout_report"]["recommended_final_version"] == {}
    assert missing_check["status"] == "failed"
    assert refreshed["summary"]["close_allowed"] is False
    assert close_status == 409
    assert "closeout gate failed" in close_error["error"]


def test_review_sprint_closeout_get_marks_stale_without_refresh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, first_task_id, _second_task_id = _create_two_review_tasks(server)
        sprint_status, sprint_data = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints", {"task_ids": [first_task_id]})
        sprint_id = sprint_data["sprint"]["sprint_id"]
        refresh_status, refreshed = request_json(server, "POST", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout/refresh")
        task_path = Path(".musicforge") / "projects" / project_id / "review-tasks" / first_task_id / "task.json"
        task_data = read_json(task_path)
        write_json(task_path, {**task_data, "status": "stale"})
        get_status, get_data = request_json(server, "GET", f"/api/projects/{project_id}/review-sprints/{sprint_id}/closeout")
    finally:
        stop_test_server(server)

    assert sprint_status == 201
    assert refresh_status == 200
    assert refreshed["closeout_report"]["source_hash"]
    assert get_status == 200
    assert get_data["closeout_report"]["status"] == "stale"
    assert get_data["summary"]["close_allowed"] is False


def _request_json(server, method, path, payload=None, headers=None):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    body = None
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
        request_headers["Content-Length"] = str(len(body))
    connection.request(method, path, body=body, headers=request_headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    if response.getheader("Content-Type", "").startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8"))
    return response.status, data


def _start_auth_server(token: str):
    import threading

    server = create_server("127.0.0.1", 0, auth_config=AuthConfig(enabled=True, token=token))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _create_auth_preview(server, headers):
    created_status, created = _request_json(server, "POST", "/api/projects", {"name": "Auth Closeout Project"}, headers=headers)
    assert created_status == 201
    project_id = created["project"]["project_id"]
    version_status, version_data = _request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload(), "name": "Parent"}, headers=headers)
    assert version_status == 202
    job = _wait_for_job(server, version_data["job"]["job_id"], headers)
    assert job["status"] == "completed"
    state_status, state = _request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/editor-state", headers=headers)
    assert state_status == 200
    note_id = state["tracks"][0]["notes"][0]["note_id"]
    preview_status, preview_data = _request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/versions/v001/editor-preview",
        {"patch": {"schema_version": 1, "base_plan_hash": state["base_plan_hash"], "label": "Closeout patch", "operations": [{"op": "update_note", "track_id": "track-001", "note_id": note_id, "patch": {"velocity": 99}}]}, "render_midi": True},
        headers=headers,
    )
    assert preview_status == 201
    return project_id, preview_data["preview"]["preview_id"]


def _create_auth_task(server, project_id: str, preview_id: str, *, headers):
    create_status, created = _request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions", {"source": "preview", "range": {"mode": "custom", "start_beat": 16.0, "end_beat": 48.0}, "track_mode": "solo", "track_ids": ["track-003"]}, headers=headers)
    assert create_status == 201
    audition_id = created["audition"]["audition_id"]
    review_status, _review = _request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review", {"rating": 4, "status": "needs_fix", "notes": "closeout task"}, headers=headers)
    assert review_status == 200
    marker_status, _marker = _request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/markers", {"beat": 1, "kind": "fix", "label": "closeout fix"}, headers=headers)
    assert marker_status == 201
    task_status, task_data = _request_json(server, "POST", f"/api/projects/{project_id}/editor-previews/{preview_id}/auditions/{audition_id}/review-task", {}, headers=headers)
    assert task_status == 201
    return task_data["task"]["task_id"]


def _wait_for_job(server, job_id: str, headers):
    import time

    for _ in range(120):
        status, job = _request_json(server, "GET", f"/api/jobs/{job_id}", headers=headers)
        assert status == 200
        if job.get("status") in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise TimeoutError(job_id)
