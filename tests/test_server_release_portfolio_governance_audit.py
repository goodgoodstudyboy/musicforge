from __future__ import annotations

from pathlib import Path

from tests.test_release_portfolio_governance_signoff import _manual_acknowledgements
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_server_release_portfolio_governance_audit_routes(tmp_path, monkeypatch) -> None:
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

        refresh_status, refreshed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/refresh", {})
        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit")
        ledger_status, ledger = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/ledger?limit=3")
        export_status, exported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/export")
        zip_status, zipped = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/zip")
        verify_status, verified = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit/verify", {"strict": True, "require_signed": True, "require_archives": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-audit.zip")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert refresh_status == 200
    assert refreshed["summary"]["status"] == "passed"
    assert detail_status == 200
    assert detail["summary"]["signed_queue_count"] == 1
    assert ledger_status == 200
    assert ledger["summary"]["entry_count"] == 3
    assert export_status == 201
    assert exported["manifest"]["audit_report"]["ledger_hash"]
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
