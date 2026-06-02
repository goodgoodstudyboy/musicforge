from __future__ import annotations

import base64

from tests.test_server_distribution import _signed_release
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_submissions import _png


def test_submission_evidence_api_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _signed_release(server)
        target_status, target_data = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Evidence Target"})
        target_id = target_data["target"]["target_id"]
        artwork_status, artwork = request_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork["artwork"]["artwork_id"]}})
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, _dist_sign = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "server-test"})
        create_status, created = request_json(server, "POST", f"/api/releases/{release_id}/submissions", {"name": "Evidence Submission", "target_ids": [target_id]})
        submission_id = created["submission"]["submission_id"]
        item_id = created["submission"]["items"][0]["item_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export/zip")
        unsigned_attachment_status, unsigned_attachment = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/evidence/attachments",
            {"filename": "receipt.txt", "content_type": "text/plain", "content_base64": base64.b64encode(b"receipt").decode("ascii")},
        )
        sign_status, _sign = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/signoff", {"signed_by": "server-test"})
        source_path_status, source_path = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/evidence/attachments",
            {"filename": "receipt.txt", "content_type": "text/plain", "source_path": "C:\\Users\\demo\\receipt.txt"},
        )
        attachment_status, attachment = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/evidence/attachments",
            {"filename": "receipt.txt", "content_type": "text/plain", "content_base64": base64.b64encode(b"receipt").decode("ascii")},
        )
        receipt_status, receipt = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/evidence/submission-receipt",
            {"external_reference": "DSP-1", "attachment_ids": [attachment["attachment"]["attachment_id"]]},
        )
        feedback_status, feedback = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/record-feedback",
            {"status": "needs_changes", "message": "metadata"},
        )
        accepted_status, accepted = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/accepted", {"external_reference": "DSP-1"})
        report_status, report = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/report/refresh")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/export/zip")
        signoff_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/signoff", {"signed_by": "server-test", "require_submitted": True, "require_accepted": True})
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/verify", {"deep": True, "require_submitted": True, "require_accepted": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/export.zip")
        blocked_feedback_status, blocked_feedback = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/record-feedback",
            {"status": "needs_changes", "message": "late"},
        )
        reset_status, reset = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/signoff/reset", {"reason": "new platform message"})
    finally:
        stop_test_server(server)

    assert target_status == 201
    assert artwork_status == 201
    assert dist_sign_status == 200
    assert create_status == 201
    assert unsigned_attachment_status == 409
    assert "signed" in unsigned_attachment["error"].lower()
    assert sign_status == 200
    assert source_path_status == 400
    assert "source_path" in source_path["error"]
    assert attachment_status == 201
    assert receipt_status == 201
    assert receipt["summary"]["status"] == "submitted"
    assert feedback_status == 200
    assert feedback["evidence"]["evidence_type"] == "needs_changes_notice"
    assert accepted_status == 200
    assert accepted["evidence"]["evidence_type"] == "acceptance_confirmation"
    assert report_status == 200
    assert report["summary"]["status"] == "passed"
    assert export_status == 201
    assert exported["summary"]["accepted_count"] == 1
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert signoff_status == 200
    assert signed["summary"]["status"] == "signed"
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
    assert blocked_feedback_status == 409
    assert "signed" in blocked_feedback["error"].lower()
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
