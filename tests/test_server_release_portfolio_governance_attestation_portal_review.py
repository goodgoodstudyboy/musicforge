from __future__ import annotations

import base64
import json
from pathlib import Path

from tests.test_release_portfolio_governance_attestation_portal_review import _response_payload
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_release_portfolio_governance_attestation_registry import _registry_fixture

from song_agent.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore
from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore


def _server_review_fixture(server, tmp_path: Path, monkeypatch):
    portfolio_id, _queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store, attestation_store, registry_store = _registry_fixture(tmp_path, monkeypatch)
    entry = registry_store.register_current_attestation(portfolio_id)["entry"]
    registry_store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "server-test"})
    registry_store.refresh_report(portfolio_id)
    registry_store.export_registry(portfolio_id)
    registry_store.build_zip(portfolio_id)
    portal_store = ReleasePortfolioGovernanceAttestationPortalStore(registry_store=registry_store, attestation_store=attestation_store)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    server.release_portfolio_audit_store = audit_store
    server.release_portfolio_governance_store = governance_store
    server.release_portfolio_governance_signoff_store = signoff_store
    server.release_portfolio_governance_audit_store = audit_store
    server.release_portfolio_governance_reviewer_pack_store = reviewer_store
    server.release_portfolio_governance_final_board_store = final_board_store
    server.release_portfolio_governance_evidence_vault_store = vault_store
    server.release_portfolio_governance_attestation_store = attestation_store
    server.release_portfolio_governance_attestation_registry_store = registry_store
    server.release_portfolio_governance_attestation_portal_store = portal_store
    server.release_portfolio_governance_attestation_portal_review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    return portfolio_id


def test_server_attestation_portal_review_pack_response_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        portfolio_id = _server_review_fixture(server, tmp_path, monkeypatch)
        refresh_status, refresh = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/refresh", {"profile": "public_summary"})
        export_status, export = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/export", {"profile": "public_summary"})
        zip_status, zip_data = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/zip", {"profile": "public_summary"})
        verify_status, verify = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/verify", {"strict": True, "require_current": True})
        download_status, body = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review-pack.zip")
        response_zip = server.release_portfolio_governance_attestation_portal_review_store.build_response_zip(portfolio_id, _response_payload("needs_changes"))
        import_status, imported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/import", {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
        response_id = imported["response"]["response_id"]
        detail_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/{response_id}")
        cr_status, cr = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/{response_id}/create-change-request", {"created_by": "server-test"})
        source_path_status, source_path = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/import", {"source_path": str(tmp_path / "response.json")})
        bare_payload = {
            "reviewer": {"name": "Bare Reviewer"},
            "decision": "accepted",
            "reviewed_at": "2026-06-10T00:00:00+00:00",
            "rating": 5,
            "notes": "missing source binding",
            "findings": [],
            "attachment_summaries": [],
        }
        bare_status, bare = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/import", {"content_base64": base64.b64encode(json.dumps(bare_payload).encode("utf-8")).decode("ascii")})
    finally:
        stop_test_server(server)

    assert refresh_status == 200
    assert refresh["summary"]["status"] == "ready"
    assert export_status == 201
    assert export["manifest"]["package_type"] == "release_portfolio_governance_attestation_portal_review_pack"
    assert zip_status == 200
    assert zip_data["zip"]["sha256"]
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"
    assert download_status == 200
    assert body.startswith(b"PK")
    assert import_status == 201
    assert imported["verification"]["status"] == "passed"
    assert detail_status == 200
    assert detail["response"]["response_id"] == response_id
    assert cr_status == 201
    assert cr["change_request"]["status"] == "draft"
    assert source_path_status == 409
    assert "source_path" in source_path["error"]
    assert bare_status == 409
    assert "review_pack_id" in bare["error"]
