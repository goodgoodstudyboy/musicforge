from __future__ import annotations

from pathlib import Path

from tests.test_release_portfolio_governance_final_board import _accepted_response
from tests.test_release_portfolio_governance_signoff import _manual_acknowledgements
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_server_release_portfolio_governance_final_board_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        from tests.test_release_portfolio_governance import governance_fixture

        _release, _second, portfolio, _store = governance_fixture(Path(".musicforge"), monkeypatch)
        portfolio_id = portfolio["portfolio_id"]
        create_status, created = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-queues", {})
        queue_id = created["queue"]["queue_id"]
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/run-safe", {})
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export")
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/export/zip")
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/verify", {"strict": True, "require_manual_actions": True})
        ack = _manual_acknowledgements(server.release_portfolio_governance_store, queue_id)
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/signoff", {"signed_by": "server-test", "manual_acknowledgements": ack})
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/archive/export")
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/archive/zip")
        request_json(server, "POST", f"/api/release-portfolio-governance-queues/{queue_id}/archive/verify", {"strict": True, "require_signed": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/refresh")
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/refresh", {})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/export")
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/zip")
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/verify", {"strict": True, "require_signed": True, "require_archives": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-reviewer-pack/refresh", {})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-reviewer-pack/export")
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-reviewer-pack/zip")
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-reviewer-pack/verify", {"strict": True, "require_audit": True, "require_signed": True, "require_archives": True})

        missing_response_status, missing_response = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/refresh", {"require_reviewer_response": True})
        import_status, imported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/reviewer-responses/import", _accepted_response())
        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board")
        signoff_status, signed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/signoff", {"signed_by": "server-test"})
        export_status, exported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/archive/export")
        zip_status, zipped = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/archive/zip")
        verify_status, verified = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/archive/verify", {"strict": True, "require_signed": True, "require_reviewer_pack": True, "require_audit": True, "require_archives": True, "require_reviewer_response": True})
        rebuild_status, rebuild = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/archive/zip")
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board.zip")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert missing_response_status == 200
    assert missing_response["summary"]["status"] == "failed"
    assert import_status == 201
    assert imported["summary"]["reviewer_response_status"] == "accepted"
    assert detail_status == 200
    assert detail["summary"]["status"] == "passed"
    assert signoff_status == 200
    assert signed["summary"]["status"] == "signed"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "release_portfolio_governance_final_board_archive"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert rebuild_status == 409
    assert "already exists" in rebuild.get("error", "")
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
