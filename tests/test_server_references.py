from __future__ import annotations

import base64
import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

from song_agent.server import create_server


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def midi_bytes() -> bytes:
    return b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff/\x00"


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


def request_payload(title="Reference Song") -> dict[str, object]:
    return {
        "title": title,
        "language": "English",
        "style": "synth pop",
        "theme": "reference api",
    }


def import_reference(server, reference_type="style_note", filename="style.md", content=b"Use a bright chorus."):
    status, data = request_json(
        server,
        "POST",
        "/api/references/import",
        {
            "reference_type": reference_type,
            "filename": filename,
            "title": "Reference Seed",
            "tags": ["seed"],
            "content_base64": b64(content),
            "metadata": {"path": "C:/secret", "note": "safe"},
        },
    )
    assert status in {200, 201}
    return data["reference"]


def test_reference_api_imports_lists_updates_downloads_and_deletes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        empty_status, empty = request_json(server, "GET", "/api/references")
        reference = import_reference(server)
        reference_id = reference["reference_id"]
        list_status, listed = request_json(server, "GET", "/api/references?type=style_note&tag=seed")
        detail_status, detail = request_json(server, "GET", f"/api/references/{reference_id}")
        update_status, updated = request_json(server, "POST", f"/api/references/{reference_id}", {"title": "Saved Reference", "favorite": True})
        file_status, file_data = request_bytes(server, "GET", f"/api/references/{reference_id}/file")
        hide_status, hidden = request_json(server, "POST", f"/api/references/{reference_id}/hide")
        hidden_list_status, hidden_list = request_json(server, "GET", "/api/references")
        include_hidden_status, include_hidden = request_json(server, "GET", "/api/references?include_hidden=1")
        unhide_status, unhidden = request_json(server, "POST", f"/api/references/{reference_id}/unhide")
        unfav_status, unfav = request_json(server, "POST", f"/api/references/{reference_id}/unfavorite")
        delete_status, deleted = request_json(server, "POST", f"/api/references/{reference_id}/delete")
        missing_status, missing = request_json(server, "GET", f"/api/references/{reference_id}")
    finally:
        stop_test_server(server)

    assert empty_status == 200
    assert empty["references"] == []
    assert reference["file_url"] == f"/api/references/{reference_id}/file"
    assert reference["metadata"] == {"note": "safe"}
    assert list_status == 200
    assert listed["count"] == 1
    assert detail_status == 200
    assert detail["reference"]["reference_id"] == reference_id
    assert update_status == 200
    assert updated["reference"]["title"] == "Saved Reference"
    assert file_status == 200
    assert file_data == b"Use a bright chorus."
    assert hide_status == 200
    assert hidden["reference"]["hidden"] is True
    assert hidden_list_status == 200
    assert hidden_list["references"] == []
    assert include_hidden_status == 200
    assert include_hidden["references"][0]["reference_id"] == reference_id
    assert unhide_status == 200
    assert unhidden["reference"]["hidden"] is False
    assert unfav_status == 200
    assert unfav["reference"]["favorite"] is False
    assert delete_status == 200
    assert deleted["deleted"] is True
    assert missing_status == 404
    assert missing["error"] == "Reference not found."


def test_reference_duplicate_invalid_and_create_asset_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        text_ref = import_reference(server, "lyrics_text", "hook.txt", b"Sing the saved line")
        duplicate_status, duplicate = request_json(
            server,
            "POST",
            "/api/references/import",
            {"reference_type": "lyrics_text", "filename": "copy.txt", "content_base64": b64(b"Sing the saved line")},
        )
        bad_status, bad = request_json(
            server,
            "POST",
            "/api/references/import",
            {"reference_type": "audio_wav", "filename": "bad.mp3", "content_base64": b64(b"ID3")},
        )
        asset_status, asset = request_json(server, "POST", f"/api/references/{text_ref['reference_id']}/create-asset", {"asset_type": "lyric_hook"})
        midi_ref = import_reference(server, "midi", "seed.mid", midi_bytes())
        midi_asset_status, midi_asset = request_json(server, "POST", f"/api/references/{midi_ref['reference_id']}/create-asset", {"asset_type": "motif"})
    finally:
        stop_test_server(server)

    assert duplicate_status == 200
    assert duplicate["duplicate"] is True
    assert duplicate["reference"]["reference_id"] == text_ref["reference_id"]
    assert bad_status == 400
    assert "does not support" in bad["error"]
    assert asset_status == 201
    assert asset["asset"]["asset_type"] == "lyric_hook"
    assert asset["asset"]["content"]["text"] == "Sing the saved line"
    assert midi_asset_status == 201
    assert midi_asset["asset"]["content"]["midi_sha256"] == midi_ref["sha256"]


def test_project_reference_link_and_job_reference_snapshot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        reference = import_reference(server)
        ref_payload = [{"reference_id": reference["reference_id"], "role": "style", "strength": 0.9}]
        project_status, created_project = request_json(server, "POST", "/api/projects", {"name": "Reference Project"})
        project_id = created_project["project"]["project_id"]
        link_status, linked = request_json(server, "POST", f"/api/projects/{project_id}/references/link", {"reference_id": reference["reference_id"]})
        list_status, project_refs = request_json(server, "GET", f"/api/projects/{project_id}/references")
        version_status, version_data = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions",
            {"request": request_payload(), "reference_refs": ref_payload},
        )
        job = wait_for_job(server, version_data["job"]["job_id"])
        detail_status, detail = request_json(server, "GET", f"/api/references/{reference['reference_id']}")
        unlink_status, unlinked = request_json(server, "POST", f"/api/projects/{project_id}/references/unlink", {"reference_id": reference["reference_id"]})
    finally:
        stop_test_server(server)

    assert project_status == 201
    assert link_status == 200
    assert linked["reference"]["linked_project_ids"] == [project_id]
    assert list_status == 200
    assert project_refs["references"][0]["reference_id"] == reference["reference_id"]
    assert version_status == 202
    assert "reference_refs" in job["artifacts"]
    snapshot_path = Path(job["output_dir"]) / "data" / "reference-refs.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot["reference_refs"][0]["reference_id"] == reference["reference_id"]
    assert detail_status == 200
    assert detail["reference"]["usage_count"] == 1
    assert unlink_status == 200
    assert unlinked["reference"]["linked_project_ids"] == []
    serialized = json.dumps({"snapshot": snapshot, "reference": detail})
    assert str(tmp_path) not in serialized


def test_reference_refs_feed_provider_candidates_and_prompt_ab_usage(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        reference = import_reference(server)
        ref_payload = [{"reference_id": reference["reference_id"], "role": "style", "strength": 0.7}]
        project_status, created_project = request_json(server, "POST", "/api/projects", {"name": "Reference Candidate Project"})
        project_id = created_project["project"]["project_id"]
        version_status, version_data = request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload("Reference Parent")})
        parent_job = wait_for_job(server, version_data["job"]["job_id"])
        provider_status, _provider = request_json(server, "POST", "/api/provider", {"wire_api": "mock", "model": "mock-main"})
        candidate_status, created = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates",
            {"instruction": "Make the chorus brighter.", "candidate_count": 2, "reference_refs": ref_payload},
        )
        ab_status, ab = request_json(
            server,
            "POST",
            f"/api/projects/{project_id}/versions/v001/edit-candidates/ab",
            {"instruction": "Compare prompts.", "candidate_count": 2, "template_ids": ["provider-edit-candidates", "provider-edit-intent"], "reference_refs": ref_payload},
        )
        ref_status, ref_detail = request_json(server, "GET", f"/api/references/{reference['reference_id']}")
    finally:
        stop_test_server(server)

    assert project_status == 201
    assert version_status == 202
    assert parent_job["status"] == "completed"
    assert provider_status == 200
    assert candidate_status == 201
    assert created["group"]["source"]["reference_refs"][0]["reference_id"] == reference["reference_id"]
    assert ab_status == 201
    assert len(ab["groups"]) == 2
    assert ref_status == 200
    assert ref_detail["reference"]["usage_count"] >= 3
