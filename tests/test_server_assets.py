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


def request_bytes(server, method, path):
    connection = HTTPConnection(server.server_address[0], server.server_address[1], timeout=10)
    connection.request(method, path)
    response = connection.getresponse()
    data = response.read()
    connection.close()
    return response.status, data


def wait_for_job(server, job_id):
    for _ in range(120):
        status, job = request_json(server, "GET", f"/api/jobs/{job_id}")
        assert status == 200
        if job["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def request_payload(title="Asset Parent") -> dict[str, object]:
    return {
        "title": title,
        "language": "English",
        "style": "synth pop",
        "theme": "asset api",
    }


def create_project_version(server):
    _status, created = request_json(server, "POST", "/api/projects", {"name": "Asset Project"})
    project_id = created["project"]["project_id"]
    status, version_data = request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload(), "name": "Parent"})
    assert status == 202
    job = wait_for_job(server, version_data["job"]["job_id"])
    assert job["status"] == "completed"
    return project_id, job


def test_asset_api_extracts_renders_updates_and_deletes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        empty_status, empty = request_json(server, "GET", "/api/assets")
        project_id, _job = create_project_version(server)
        extract_status, extracted = request_json(
            server,
            "POST",
            "/api/assets/extract/from-project-version",
            {
                "project_id": project_id,
                "version_id": "v001",
                "asset_types": ["motif", "chord_progression"],
                "section_name": "chorus",
                "tags": ["chorus", "asset"],
                "favorite": True,
            },
        )
        asset_id = extracted["assets"][0]["asset_id"]
        list_status, listed = request_json(server, "GET", "/api/assets?type=motif&favorite=1")
        detail_status, detail = request_json(server, "GET", f"/api/assets/{asset_id}")
        update_status, updated = request_json(server, "POST", f"/api/assets/{asset_id}", {"name": "Saved Motif", "tags": ["saved"]})
        midi_render_status, midi_render = request_json(server, "POST", f"/api/assets/{asset_id}/render-midi")
        midi_status, midi = request_bytes(server, "GET", f"/api/assets/{asset_id}/midi")
        audio_status, audio = request_json(server, "POST", f"/api/assets/{asset_id}/render-audio")
        hide_status, hidden = request_json(server, "POST", f"/api/assets/{asset_id}/hide")
        hidden_list_status, hidden_list = request_json(server, "GET", "/api/assets")
        include_hidden_status, include_hidden = request_json(server, "GET", "/api/assets?include_hidden=1")
        unhide_status, unhidden = request_json(server, "POST", f"/api/assets/{asset_id}/unhide")
        unfav_status, unfav = request_json(server, "POST", f"/api/assets/{asset_id}/unfavorite")
        delete_status, deleted = request_json(server, "POST", f"/api/assets/{asset_id}/delete")
        missing_status, missing = request_json(server, "GET", f"/api/assets/{asset_id}")
    finally:
        stop_test_server(server)

    assert empty_status == 200
    assert empty["assets"] == []
    assert extract_status == 201
    assert [asset["asset_type"] for asset in extracted["assets"]] == ["motif", "chord_progression"]
    assert "song_plan_sha256" in extracted["assets"][0]["source"]
    assert list_status == 200
    assert listed["count"] == 1
    assert detail_status == 200
    assert detail["asset"]["asset_id"] == asset_id
    assert update_status == 200
    assert updated["asset"]["name"] == "Saved Motif"
    assert midi_render_status == 200
    assert midi_render["asset"]["preview"]["midi_status"] == "completed"
    assert midi_status == 200
    assert midi.startswith(b"MThd")
    assert audio_status == 400
    assert "soundfont_path is required" in audio["error"]
    assert hide_status == 200
    assert hidden["asset"]["hidden"] is True
    assert hidden_list_status == 200
    assert all(asset["asset_id"] != asset_id for asset in hidden_list["assets"])
    assert include_hidden_status == 200
    assert include_hidden["assets"][0]["asset_id"] == asset_id
    assert unhide_status == 200
    assert unhidden["asset"]["hidden"] is False
    assert unfav_status == 200
    assert unfav["asset"]["favorite"] is False
    assert delete_status == 200
    assert deleted["deleted"] is True
    assert missing_status == 404
    assert missing["error"] == "Asset not found."


def test_extract_asset_from_job_candidate_and_use_in_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        job_status, job = request_json(server, "POST", "/api/jobs", request_payload("Asset Job"))
        completed_job = wait_for_job(server, job["job_id"])
        job_extract_status, job_extracted = request_json(
            server,
            "POST",
            "/api/assets/extract/from-job",
            {"job_id": completed_job["job_id"], "asset_types": ["chord_progression"], "section_name": "chorus"},
        )
        asset_id = job_extracted["assets"][0]["asset_id"]
        ref_payload = [{"asset_id": asset_id, "role": "chord_reference", "strength": 0.9}]
        project_id, _parent_job = create_project_version(server)
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        create_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates",
            {"instruction": "Make the chorus brighter.", "candidate_count": 2, "asset_refs": ref_payload},
        )
        group_id = created["group"]["group_id"]
        candidate_id = created["group"]["ranking"][0]["candidate_id"]
        candidate_extract_status, candidate_extracted = request_json(
            server,
            "POST",
            "/api/assets/extract/from-candidate",
            {
                "project_id": project_id,
                "candidate_group_id": group_id,
                "candidate_id": candidate_id,
                "asset_types": ["motif"],
                "section_name": "chorus",
            },
        )
        version_status, version_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": request_payload("Asset Referenced Version"), "asset_refs": ref_payload},
        )
        version_job = wait_for_job(server, version_data["job"]["job_id"])
        usage_status, usage_asset = request_json(server, "GET", f"/api/assets/{asset_id}")
    finally:
        stop_test_server(server)

    assert job_status == 202
    assert job_extract_status == 201
    assert job_extracted["assets"][0]["source"]["source_type"] == "job"
    assert create_status == 201
    assert created["group"]["source"]["asset_refs"][0]["asset_id"] == asset_id
    assert candidate_extract_status == 201
    assert candidate_extracted["assets"][0]["source"]["candidate_group_id"] == group_id
    assert version_status == 202
    assert "asset_refs" in version_job["artifacts"]
    asset_refs_path = Path(version_job["output_dir"]) / "data" / "asset-refs.json"
    snapshot = json.loads(asset_refs_path.read_text(encoding="utf-8"))
    assert snapshot["asset_refs"][0]["asset_id"] == asset_id
    assert usage_status == 200
    assert usage_asset["asset"]["usage_count"] >= 2
    serialized = json.dumps({"created": created, "snapshot": snapshot, "asset": usage_asset})
    assert str(tmp_path) not in serialized


def test_prompt_ab_rollback_does_not_count_asset_usage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id, _parent_job = create_project_version(server)
        extract_status, extracted = request_json(
            server,
            "POST",
            "/api/assets/extract/from-project-version",
            {
                "project_id": project_id,
                "version_id": "v001",
                "asset_types": ["motif"],
                "section_name": "chorus",
            },
        )
        asset_id = extracted["assets"][0]["asset_id"]
        request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        failed_status, failed = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates/ab",
            {
                "instruction": "Compare two prompts.",
                "candidate_count": 2,
                "template_ids": ["provider-edit-candidates", "missing-template"],
                "asset_refs": [{"asset_id": asset_id, "role": "motif_reference", "strength": 0.7}],
            },
        )
        asset_status, asset = request_json(server, "GET", f"/api/assets/{asset_id}")
        groups_status, groups = request_json(server, "GET", f"/api/projects/{project_id}/candidate-groups")
    finally:
        stop_test_server(server)

    assert extract_status == 201
    assert failed_status == 404
    assert "Provider edit resource not found" in failed["error"]
    assert asset_status == 200
    assert asset["asset"]["usage_count"] == 0
    assert groups_status == 200
    assert groups["groups"] == []
