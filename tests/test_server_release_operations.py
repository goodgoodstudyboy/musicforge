from __future__ import annotations

import base64

from tests.test_server_distribution import _signed_release
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_submissions import _png


def test_release_operations_api_end_to_end_and_read_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _signed_release(server)
        target_status, target_data = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Ops Target"})
        target_id = target_data["target"]["target_id"]
        artwork_status, artwork = request_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork["artwork"]["artwork_id"]}})
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, _dist_sign = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "server-test"})
        create_status, created = request_json(server, "POST", f"/api/releases/{release_id}/submissions", {"name": "Ops Submission", "target_ids": [target_id]})
        submission_id = created["submission"]["submission_id"]
        item_id = created["submission"]["items"][0]["item_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export/zip")
        sub_sign_status, _sub_sign = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/signoff", {"signed_by": "server-test"})
        before_release_status, before_release = request_json(server, "GET", f"/api/releases/{release_id}")
        before_target_status, before_target = request_json(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}")
        before_submission_status, before_submission = request_json(server, "GET", f"/api/releases/{release_id}/submissions/{submission_id}")
        overview_status, overview = request_json(server, "GET", f"/api/releases/{release_id}/operations")
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/operations/refresh")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/operations/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/operations/export/zip")
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/operations/verify", {"require_submission_evidence": False})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/operations/export.zip")
        after_release_status, after_release = request_json(server, "GET", f"/api/releases/{release_id}")
        after_target_status, after_target = request_json(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}")
        after_submission_status, after_submission = request_json(server, "GET", f"/api/releases/{release_id}/submissions/{submission_id}")
    finally:
        stop_test_server(server)

    assert target_status == 201
    assert artwork_status == 201
    assert dist_sign_status == 200
    assert create_status == 201
    assert sub_sign_status == 200
    assert before_release_status == 200
    assert before_target_status == 200
    assert before_submission_status == 200
    assert overview_status == 200
    assert overview["report"]["current_stage"] in {"submission_ready", "submitted"}
    assert refresh_status == 200
    assert refreshed["summary"]["current_stage"] in {"submission_ready", "submitted"}
    assert export_status == 201
    assert exported["manifest"]["report"]["integrity_hash"]
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
    assert after_release_status == 200
    assert after_target_status == 200
    assert after_submission_status == 200
    assert after_release["release"]["status"] == before_release["release"]["status"]
    assert after_target["target"]["status"] == before_target["target"]["status"]
    assert after_submission["submission"]["status"] == before_submission["submission"]["status"]
    assert item_id
