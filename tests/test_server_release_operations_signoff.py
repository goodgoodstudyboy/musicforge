from __future__ import annotations

import base64

from tests.test_server_distribution import _signed_release
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_submissions import _png


def test_release_operations_signoff_archive_and_change_request_api(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _signed_release(server)
        target_status, target_data = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Ops Archive Target"})
        target_id = target_data["target"]["target_id"]
        artwork_status, artwork = request_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork["artwork"]["artwork_id"]}})
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        dist_sign_status, _dist_sign = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "server-test"})
        create_status, created = request_json(server, "POST", f"/api/releases/{release_id}/submissions", {"name": "Ops Archive Submission", "target_ids": [target_id]})
        submission_id = created["submission"]["submission_id"]
        item_id = created["submission"]["items"][0]["item_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/export/zip")
        sub_sign_status, _sub_sign = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/signoff", {"signed_by": "server-test"})
        attachment_status, attachment = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/evidence/attachments",
            {"filename": "receipt.txt", "content_type": "text/plain", "content_base64": base64.b64encode(b"receipt").decode("ascii")},
        )
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/evidence/submission-receipt", {"external_reference": "DSP-OPS", "attachment_ids": [attachment["attachment"]["attachment_id"]]})
        accepted_status, _accepted = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/items/{item_id}/accepted", {"external_reference": "DSP-OPS"})
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/report/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/export")
        request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/export/zip")
        evidence_sign_status, _evidence_sign = request_json(server, "POST", f"/api/releases/{release_id}/submissions/{submission_id}/evidence/signoff", {"signed_by": "server-test", "require_submitted": True, "require_accepted": True})
        runbook_create_status, runbook_created = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks", {})
        runbook_id = runbook_created["runbook"]["runbook_id"]
        run_status, _ran = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks/{runbook_id}/run-safe", {})
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/operations/refresh")
        pre_sign_status, pre_sign = request_json(server, "GET", f"/api/releases/{release_id}/operations/signoff")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/operations/signoff", {"signed_by": "ops-test", "force": True, "override_reason": "Accept operations warning for archive API regression"})
        duplicate_status, duplicate = request_json(server, "POST", f"/api/releases/{release_id}/operations/signoff", {"signed_by": "ops-test"})
        overview_status, overview = request_json(server, "GET", f"/api/releases/{release_id}/operations")
        archive_export_status, archive_export = request_json(server, "POST", f"/api/releases/{release_id}/operations/archive/export")
        archive_zip_status, archive_zip = request_json(server, "POST", f"/api/releases/{release_id}/operations/archive/export/zip")
        archive_verify_status, archive_verify = request_json(server, "POST", f"/api/releases/{release_id}/operations/archive/verify", {"require_signed": True})
        download_status, archive_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/operations/archive.zip")
        evidence_signoff_path = server.submission_evidence_store.signoff_path(release_id, submission_id)
        evidence_signoff = server.submission_evidence_store.read_signoff(release_id, submission_id, default={})
        evidence_signoff["status"] = "reset"
        from song_agent.projectio import write_json

        write_json(evidence_signoff_path, evidence_signoff)
        stale_overview_status, stale_overview = request_json(server, "GET", f"/api/releases/{release_id}/operations")
        reset_missing_status, reset_missing = request_json(server, "POST", f"/api/releases/{release_id}/operations/signoff/reset", {"reason": "short"})
        cr_status, cr = request_json(server, "POST", f"/api/releases/{release_id}/operations/change-requests", {"reason": "Fix metadata typo after archive", "scope": ["metadata", "release_export"], "created_by": "server-test"})
        cr_id = cr["change_request"]["change_request_id"]
        approve_status, approved = request_json(server, "POST", f"/api/releases/{release_id}/operations/change-requests/{cr_id}/approve", {"approved_by": "reviewer", "notes": "approved"})
        reset_status, reset = request_json(server, "POST", f"/api/releases/{release_id}/operations/signoff/reset", {"reason": "Reset for approved metadata change", "change_request_id": cr_id})
    finally:
        stop_test_server(server)

    assert target_status == 201
    assert artwork_status == 201
    assert dist_sign_status == 200
    assert create_status == 201
    assert sub_sign_status == 200
    assert attachment_status == 201
    assert accepted_status == 200
    assert evidence_sign_status == 200
    assert runbook_create_status == 201
    assert run_status == 200
    assert refresh_status == 200
    assert refreshed["summary"]["current_stage"] == "accepted"
    assert pre_sign_status == 200
    assert pre_sign["gate"]["signable"] is False
    assert pre_sign["gate"]["warnings"]
    assert sign_status == 200
    assert signed["summary"]["status"] == "force_signed"
    assert duplicate_status == 409
    assert "already" in duplicate["error"].lower()
    assert overview_status == 200
    assert overview["report"]["current_stage"] == "archived"
    assert archive_export_status == 201
    assert archive_export["manifest"]["operations_signoff"]["payload_hash"]
    assert archive_zip_status == 200
    assert archive_zip["zip"]["sha256"]
    assert archive_verify_status == 200
    assert archive_verify["summary"]["status"] == "passed"
    assert download_status == 200
    assert archive_bytes.startswith(b"PK")
    assert stale_overview_status == 200
    assert next(item for item in stale_overview["report"]["stage_statuses"] if item["stage"] == "archived")["status"] == "failed"
    assert reset_missing_status == 409
    assert "reason" in reset_missing["error"].lower()
    assert cr_status == 201
    assert approve_status == 200
    assert approved["change_request"]["status"] == "approved"
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
