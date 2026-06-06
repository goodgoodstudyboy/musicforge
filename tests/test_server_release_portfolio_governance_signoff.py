from __future__ import annotations

from pathlib import Path

from tests.test_release_portfolio_governance_signoff import _manual_acknowledgements
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_server_release_portfolio_governance_signoff_archive_and_change_request_api(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        from tests.test_release_portfolio_governance import governance_fixture

        _release, _second, portfolio, _store = governance_fixture(Path(".musicforge"), monkeypatch)
        portfolio_id = portfolio["portfolio_id"]
        create_status, created = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-queues", {})
        queue_id = created["queue"]["queue_id"]
        run_status, _ran = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/run-safe", {})
        export_status, _exported = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export")
        zip_status, _zipped = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export/zip")
        verify_status, _verified = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/verify", {"strict": True, "require_manual_actions": True})
        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}")
        missing_ack_status, missing_ack = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/signoff", {"signed_by": "server-test"})
        ack = _manual_acknowledgements(server.release_portfolio_governance_store, queue_id)
        sign_status, signed = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/signoff", {"signed_by": "server-test", "manual_acknowledgements": ack})
        signed_run_status, signed_run = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/run-safe", {})
        signed_export_status, signed_export = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export")
        signed_zip_status, signed_zip = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export/zip")
        archive_export_status, archive_export = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/archive/export")
        archive_zip_status, archive_zip = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/archive/zip")
        archive_verify_status, archive_verify = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/archive/verify", {"strict": True, "require_signed": True})
        download_status, archive_bytes = request_bytes(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}/archive.zip")
        reset_missing_cr_status, reset_missing_cr = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/signoff/reset", {"reason": "Reset without approved change request"})
        cr_status, cr = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/change-requests", {"reason": "Need to correct governance archive", "requested_by": "server-test"})
        cr_id = cr["change_request"]["change_request_id"]
        approve_status, approved = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/change-requests/{cr_id}/approve", {"approved_by": "reviewer"})
        reset_status, reset = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/signoff/reset", {"reason": "Reset with approved governance change", "change_request_id": cr_id})
        reuse_status, reuse = request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/signoff/reset", {"reason": "Reuse same governance change", "change_request_id": cr_id})
        cr_detail_status, cr_detail = request_json(server, "GET", f"/api/release-portfolio-governance-queues/{queue_id}/change-requests/{cr_id}")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert run_status == 200
    assert export_status == 201
    assert zip_status == 200
    assert verify_status == 200
    assert detail_status == 200
    assert detail["signoff_summary"]["status"] == "not_signed"
    assert missing_ack_status == 409
    assert "acknowledgement" in missing_ack["error"].lower()
    assert sign_status == 200
    assert signed["summary"]["status"] == "signed"
    assert signed_run_status == 409
    assert "immutable" in signed_run["error"].lower()
    assert signed_export_status == 409
    assert "immutable" in signed_export["error"].lower()
    assert signed_zip_status == 409
    assert "immutable" in signed_zip["error"].lower()
    assert archive_export_status == 201
    assert archive_export["manifest"]["sidecars"]["governance_signoff"]["payload_hash"]
    assert archive_zip_status == 200
    assert archive_zip["zip"]["sha256"]
    assert archive_verify_status == 200
    assert archive_verify["summary"]["status"] == "passed"
    assert download_status == 200
    assert archive_bytes.startswith(b"PK")
    assert reset_missing_cr_status == 409
    assert "change request" in reset_missing_cr["error"].lower()
    assert cr_status == 201
    assert approve_status == 200
    assert approved["change_request"]["status"] == "approved"
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
    assert reuse_status == 409
    assert "approved" in reuse["error"].lower()
    assert cr_detail_status == 200
    assert cr_detail["change_request"]["status"] == "applied"
