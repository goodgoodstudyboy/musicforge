from __future__ import annotations

from pathlib import Path

from tests.test_release_portfolio_governance_final_board import _accepted_response
from tests.test_release_portfolio_governance_signoff import _manual_acknowledgements
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_server_release_portfolio_governance_evidence_vault_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        from tests.test_release_portfolio_governance import governance_fixture

        _release, _second, portfolio, _store = governance_fixture(Path(".musicforge"), monkeypatch)
        portfolio_id = portfolio["portfolio_id"]
        _status, created = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-queues", {})
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
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/reviewer-responses/import", _accepted_response())
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/refresh", {"require_reviewer_response": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/signoff", {"signed_by": "server-test"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/archive/export")
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/archive/zip")
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-final-board/archive/verify", {"strict": True, "require_signed": True, "require_reviewer_pack": True, "require_audit": True, "require_archives": True, "require_reviewer_response": True})

        refresh_status, refreshed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-evidence-vault/refresh", {})
        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-evidence-vault")
        export_status, exported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-evidence-vault/export")
        zip_status, zipped = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-evidence-vault/zip")
        verify_status, verified = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-evidence-vault/verify", {"strict": True, "deep": True, "require_final_board": True, "require_reviewer_pack": True, "require_audit": True, "require_archives": True})
        att_refresh_status, att_refreshed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation/refresh", {"profile": "public_summary"})
        att_detail_status, att_detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation")
        att_export_status, att_exported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation/export", {"profile": "public_summary"})
        att_zip_status, att_zipped = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation/zip", {"profile": "public_summary"})
        att_verify_status, att_verified = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation/verify", {"profile": "public_summary", "strict": True, "require_vault": True, "require_final_board": True})
        att_rebuild_status, att_rebuild = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation/zip", {"profile": "public_summary"})
        att_download_status, att_zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation.zip")
        registry_register_status, registry_registered = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/register-current", {"profile": "public_summary"})
        registry_entry_id = registry_registered["entry"]["entry_id"]
        registry_publish_status, registry_published = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/entries/{registry_entry_id}/publish", {"profile": "public_summary"})
        registry_detail_status, registry_detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry")
        registry_refresh_status, registry_refreshed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/refresh", {"profile": "public_summary"})
        registry_export_status, registry_exported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/export", {"profile": "public_summary"})
        registry_zip_status, registry_zipped = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/zip", {"profile": "public_summary"})
        registry_verify_status, registry_verified = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/verify", {"profile": "public_summary", "strict": True, "require_current": True, "require_published": True, "require_no_revoked_current": True})
        registry_rebuild_status, registry_rebuild = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/zip", {"profile": "public_summary"})
        registry_download_status, registry_zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry.zip")
        portal_refresh_status, portal_refreshed = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/refresh", {"profile": "public_summary"})
        portal_detail_status, portal_detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal")
        portal_export_status, portal_exported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/export", {"profile": "public_summary"})
        portal_zip_status, portal_zipped = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/zip", {"profile": "public_summary"})
        portal_verify_status, portal_verified = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/verify", {"profile": "public_summary", "strict": True, "require_current": True, "require_registry": True, "require_attestation": True})
        portal_rebuild_status, portal_rebuild = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/zip", {"profile": "public_summary"})
        portal_download_status, portal_zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal.zip")
        rebuild_status, rebuild = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-evidence-vault/zip")
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-evidence-vault.zip")
    finally:
        stop_test_server(server)

    assert refresh_status == 200
    assert refreshed["summary"]["status"] == "passed"
    assert detail_status == 200
    assert detail["summary"]["status"] == "passed"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "release_portfolio_governance_evidence_vault"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed"
    assert att_refresh_status == 200
    assert att_refreshed["summary"]["status"] == "passed"
    assert att_detail_status == 200
    assert att_detail["certificate"]["certificate_id"] == "pgc-000001"
    assert att_export_status == 201
    assert att_exported["manifest"]["package_type"] == "release_portfolio_governance_public_attestation"
    assert att_zip_status == 200
    assert att_zipped["zip"]["sha256"]
    assert att_verify_status == 200
    assert att_verified["verification"]["status"] == "passed"
    assert att_rebuild_status == 409
    assert "already exists" in att_rebuild.get("error", "")
    assert att_download_status == 200
    assert att_zip_bytes.startswith(b"PK")
    assert registry_register_status == 201
    assert registry_registered["entry"]["status"] == "draft"
    assert registry_publish_status == 200
    assert registry_published["summary"]["current_entry_id"] == registry_entry_id
    assert registry_detail_status == 200
    assert registry_detail["summary"]["current_entry_id"] == registry_entry_id
    assert registry_refresh_status == 200
    assert registry_refreshed["report"]["status"] == "passed"
    assert registry_export_status == 201
    assert registry_exported["manifest"]["package_type"] == "release_portfolio_governance_attestation_registry"
    assert registry_zip_status == 200
    assert registry_zipped["zip"]["sha256"]
    assert registry_verify_status == 200
    assert registry_verified["verification"]["status"] == "passed"
    assert registry_rebuild_status == 409
    assert "already exists" in registry_rebuild.get("error", "")
    assert registry_download_status == 200
    assert registry_zip_bytes.startswith(b"PK")
    assert portal_refresh_status == 200
    assert portal_refreshed["summary"]["status"] == "passed"
    assert portal_detail_status == 200
    assert portal_detail["summary"]["status"] == "passed"
    assert portal_export_status == 201
    assert portal_exported["manifest"]["package_type"] == "release_portfolio_governance_attestation_portal"
    assert portal_zip_status == 200
    assert portal_zipped["zip"]["sha256"]
    assert portal_verify_status == 200
    assert portal_verified["verification"]["status"] == "passed"
    assert portal_rebuild_status == 409
    assert "already exists" in portal_rebuild.get("error", "")
    assert portal_download_status == 200
    assert portal_zip_bytes.startswith(b"PK")
    assert rebuild_status == 409
    assert "already exists" in rebuild.get("error", "")
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
