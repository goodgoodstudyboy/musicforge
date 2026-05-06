from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

from song_agent.server import create_server


def start_test_server():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def stop_test_server(server):
    server.shutdown()
    server.server_close()


def request_json(server, method, path, payload=None):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    if response.getheader("Content-Type", "").startswith("application/json"):
        return response.status, json.loads(data.decode("utf-8"))
    return response.status, data


def wait_for_job(server, job_id):
    for _ in range(120):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def request_payload(title="Edit Parent") -> dict[str, object]:
    return {
        "title": title,
        "language": "English",
        "style": "synth pop",
        "theme": "edit api",
    }


def create_project_version(server):
    _status, created = request_json(server, "POST", "/api/projects", {"name": "Edit Project"})
    project_id = created["project"]["project_id"]
    version_status, version_data = request_json(
        server,
        "POST",
        f"/api/projects/{project_id}/versions",
        {"request": request_payload(), "name": "Parent"},
    )
    assert version_status == 202
    parent_job = wait_for_job(server, version_data["job"]["job_id"])
    assert parent_job["status"] == "completed"
    return project_id, parent_job


def test_project_edit_api_creates_child_version_and_preserves_parent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, parent_job = create_project_version(server)
        parent_plan_path = Path(parent_job["output_dir"]) / "data" / "song-plan.json"
        parent_before = parent_plan_path.read_bytes()
        edit_status, edit_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "edit_type": "section_energy",
                "target": {"section_name": "chorus"},
                "instruction": "Make chorus stronger.",
                "preserve": ["tempo", "key", "structure"],
                "strength": 8,
                "name": "Chorus lift",
                "note": "local edit",
            },
        )
        edit_job = wait_for_job(server, edit_data["job"]["job_id"])
        detail_status, detail = request_json(server, "GET", f"/api/projects/{project_id}")
        edit_view_status, edit_view = request_json(server, "GET", f"/api/jobs/{edit_job['job_id']}/edit")
        version_edit_status, version_edit = request_json(server, "GET", f"/api/projects/{project_id}/versions/v002/edit")
        diff_status, diff = request_json(server, "GET", f"/api/projects/{project_id}/diff?left=v001&right=v002")
        events_status, events = request_json(server, "GET", f"/api/projects/{project_id}/events")
    finally:
        stop_test_server(server)

    assert edit_status == 202
    assert edit_data["version"]["version_id"] == "v002"
    assert edit_data["version"]["parent_version_id"] == "v001"
    assert edit_data["version"]["variant_type"] == "section_edit"
    assert edit_job["status"] == "completed"
    assert edit_job["job_type"] == "edit"
    assert edit_job["artifacts"]["edit_metadata"].endswith("edit-metadata.json")
    assert (Path(edit_job["output_dir"]) / "data" / "edit-metadata.json").exists()
    assert (Path(edit_job["output_dir"]) / "renders" / "song.mid").read_bytes().startswith(b"MThd")
    assert parent_plan_path.read_bytes() == parent_before
    assert detail_status == 200
    assert detail["project"]["version_count"] == 2
    assert edit_view_status == 200
    assert edit_view["edit"]["edit_type"] == "section_energy"
    assert version_edit_status == 200
    assert version_edit["edit"]["parent_version_id"] == "v001"
    assert diff_status == 200
    assert diff["changed"]["edit"]["right"]["edit_type"] == "section_energy"
    assert diff["changed"]["tracks"]
    assert events_status == 200
    assert any(event["type"] == "version_edit_created" for event in events["events"])


def test_project_edit_targets_and_validation_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, parent_job = create_project_version(server)
        targets_status, targets = request_json(server, "GET", f"/api/projects/{project_id}/versions/v001/edit-targets")
        missing_section_status, missing_section = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {"edit_type": "section_energy", "target": {"section_name": "bridge"}},
        )
        provider_status, provider = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {"edit_type": "section_energy", "target": {"section_name": "chorus"}, "provider_mode": "provider"},
        )
        bad_chord_status, bad_chord = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "edit_type": "section_harmony",
                "target": {"section_name": "chorus", "field": "chords"},
                "payload": {"chords": ["Hmaj7", "Cmaj7"]},
            },
        )
        job_edit_status, job_edit = request_json(server, "GET", f"/api/jobs/{parent_job['job_id']}/edit")
    finally:
        stop_test_server(server)

    assert targets_status == 200
    assert {section["name"] for section in targets["sections"]} >= {"verse", "chorus"}
    assert {track["name"] for track in targets["tracks"]} >= {"melody", "drums"}
    assert "lyrics_rewrite" in targets["supported_edit_types"]
    assert missing_section_status == 400
    assert "Section not found" in missing_section["error"]
    assert provider_status == 400
    assert "Provider-backed edit" in provider["error"]
    assert bad_chord_status == 400
    assert "Unsupported chord names: Hmaj7" in bad_chord["error"]
    assert job_edit_status == 404
    assert job_edit["error"] == "Edit metadata not found."


def test_edit_preset_api_and_project_edit_with_preset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        list_status, listed = request_json(server, "GET", "/api/edit-presets")
        create_status, created = request_json(
            server,
            "POST",
            "/api/edit-presets",
            {
                "preset_id": "custom-hook-lift",
                "name": "Custom Hook Lift",
                "description": "Lift hook energy",
                "edit_type": "section_energy",
                "strength": 0.8,
                "target_defaults": {"section_role": "chorus", "section_index": -1},
                "preserve": ["tempo", "key", "structure"],
            },
        )
        read_status, read_back = request_json(server, "GET", "/api/edit-presets/custom-hook-lift")
        project_id, _parent_job = create_project_version(server)
        edit_status, edit_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "preset_id": "custom-hook-lift",
                "intent": {"strength": 7},
                "name": "Preset child",
            },
        )
        edit_job = wait_for_job(server, edit_data["job"]["job_id"])
        metadata_status, metadata = request_json(server, "GET", f"/api/projects/{project_id}/versions/v002/edit")
        delete_status, deleted = request_json(server, "POST", "/api/edit-presets/custom-hook-lift/delete")
        builtin_delete_status, builtin_delete = request_json(server, "POST", "/api/edit-presets/lift-final-chorus/delete")
    finally:
        stop_test_server(server)

    assert list_status == 200
    assert listed["built_in_count"] >= 7
    assert create_status == 201
    assert created["preset"]["preset_id"] == "custom-hook-lift"
    assert read_status == 200
    assert read_back["preset"]["name"] == "Custom Hook Lift"
    assert edit_status == 202
    assert edit_data["edit"]["preset"]["preset_id"] == "custom-hook-lift"
    assert edit_job["status"] == "completed"
    assert metadata_status == 200
    assert metadata["edit"]["preset"]["name"] == "Custom Hook Lift"
    assert metadata["edit"]["strength"] == 7
    assert delete_status == 200
    assert deleted["user_count"] == 0
    assert builtin_delete_status == 409
    assert "Built-in presets cannot be deleted" in builtin_delete["error"]


def test_edit_preset_api_rejects_invalid_harmony_chord(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        status, data = request_json(
            server,
            "POST",
            "/api/edit-presets",
            {
                "preset_id": "bad-harmony",
                "name": "Bad Harmony",
                "edit_type": "section_harmony",
                "payload": {"chords": ["Hmaj7", "Cmaj7"]},
            },
        )
    finally:
        stop_test_server(server)

    assert status == 400
    assert "Unsupported chord names: Hmaj7" in data["error"]


def test_project_edit_requires_completed_parent_and_existing_plan(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        _status, created = request_json(server, "POST", "/api/projects", {"name": "Queued Edit Project"})
        project_id = created["project"]["project_id"]
        job = server.job_store.create_job(request_payload("Queued Parent"), start_immediately=False)
        request_json(server, "POST", f"/api/projects/{project_id}/versions/from-job", {"job_id": job.job_id})
        queued_status, queued = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {"edit_type": "section_energy", "target": {"section_name": "chorus"}},
        )
        server.job_store._update_job(job, status="completed", step="completed")
        missing_plan_status, missing_plan = request_json(
            server,
            "GET",
            f"/api/projects/{project_id}/versions/v001/edit-targets",
        )
    finally:
        stop_test_server(server)

    assert queued_status == 409
    assert queued["error"] == "Parent version must be completed before editing."
    assert missing_plan_status == 409
    assert missing_plan["error"] == "song-plan.json is not available for this version."


def test_cancelled_edit_job_does_not_start(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        status, data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit",
            {
                "edit_type": "lyrics_rewrite",
                "target": {"section_name": "verse", "field": "lyrics"},
                "payload": {"lyrics": "edited line"},
                "start_immediately": False,
            },
        )
        job_id = data["job"]["job_id"]
        cancel_status, _cancel = request_json(server, "POST", f"/api/jobs/{job_id}/cancel")
        started = server.job_store.start_job(job_id)
        final_status, final = request_json(server, "GET", f"/api/jobs/{job_id}")
    finally:
        stop_test_server(server)

    assert status == 202
    assert cancel_status == 200
    assert started is False
    assert final_status == 200
    assert final["status"] == "cancelled"
    assert not (Path(final["output_dir"]) / "data" / "song-plan.json").exists()
