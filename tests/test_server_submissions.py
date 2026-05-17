from __future__ import annotations

import base64
from pathlib import Path

from tests.test_distribution import _png
from tests.test_server_distribution import _signed_release
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_submission_api_end_to_end_and_signed_mutation_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _signed_release(server)
        target_status, target_data = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Submission Pitch"})
        target_id = target_data["target"]["target_id"]
        artwork_status, artwork = request_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
        update_status, _updated = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork["artwork"]["artwork_id"]}})
        dist_qa_status, _dist_qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        dist_export_status, _dist_export = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        dist_zip_status, _dist_zip = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, _dist_sign = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "server-test"})
        list_empty_status, list_empty = request_json(server, "GET", f"/api/releases/{release_id}/submissions")
        create_status, created = request_json(server, "POST", f"/api/releases/{release_id}/submissions", {"name": "Server Submission", "target_ids": [target_id]})
        submission_id = created["submission"]["submission_id"]
        item_id = created["submission"]["items"][0]["item_id"]
        get_status, got = request_json(server, "GET", f"/api/releases/{release_id}/submissions/{submission_id}")
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/qa/refresh")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export/zip")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/signoff", {"signed_by": "server-test"})
        blocked_add_status, blocked_add = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/targets", {"target_id": target_id})
        blocked_export_status, blocked_export = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        blocked_zip_status, blocked_zip = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export/zip")
        submitted_status, submitted = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/record-submission", {"external_reference": "DSP-1"})
        feedback_status, feedback = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/record-feedback", {"status": "needs_changes", "message": "Revise metadata"})
        accepted_status, accepted = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/accepted", {"external_reference": "DSP-1"})
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/verify", {"deep": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/submissions/{submission_id}/export.zip")
        reset_status, reset = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/signoff/reset", {"reason": "submission rebuild"})
        qa_after_reset_status, _qa_after_reset = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/qa/refresh")
        export_after_reset_status, _after_reset = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
    finally:
        stop_test_server(server)

    assert target_status == 201
    assert artwork_status == 201
    assert update_status == 200
    assert dist_qa_status == 200
    assert dist_export_status == 201
    assert dist_zip_status == 200
    assert dist_sign_status == 200
    assert list_empty_status == 200
    assert list_empty["summary"]["submission_count"] == 0
    assert create_status == 201
    assert created["summary"]["item_count"] == 1
    assert get_status == 200
    assert got["submission"]["submission_id"] == submission_id
    assert qa_status == 200
    assert qa["summary"]["status"] in {"passed", "warning"}
    assert export_status == 201
    assert exported["summary"]["status"] == "exported"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert sign_status == 200
    assert signed["summary"]["status"] == "signed"
    assert blocked_add_status == 409
    assert blocked_export_status == 409
    assert blocked_zip_status == 409
    assert "signed" in blocked_add["error"].lower()
    assert "signed" in blocked_export["error"].lower()
    assert "signed" in blocked_zip["error"].lower()
    assert submitted_status == 200
    assert submitted["summary"]["status"] == "submitted"
    assert feedback_status == 200
    assert feedback["summary"]["status"] == "needs_changes"
    assert accepted_status == 200
    assert accepted["summary"]["status"] == "accepted"
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
    assert qa_after_reset_status == 200
    assert export_after_reset_status == 201
