from __future__ import annotations

import base64
import json
from pathlib import Path

from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_release_portfolio_governance_attestation_transparency_acknowledgement import _server_review_fixture
from tests.test_server_release_portfolio_governance_attestation_transparency import _response_payload

from song_agent.public_trust_center import PublicTrustCenterStore
from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, response_payload_hash, response_template


def test_server_public_trust_center_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        portfolio_id = _server_review_fixture(server, tmp_path, monkeypatch)
        review_store = server.release_portfolio_governance_attestation_portal_review_store
        server.release_portfolio_governance_attestation_accepted_evidence_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
        server.release_portfolio_governance_attestation_transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
            attestation_store=server.release_portfolio_governance_attestation_store,
            registry_store=server.release_portfolio_governance_attestation_registry_store,
            portal_store=server.release_portfolio_governance_attestation_portal_store,
            accepted_evidence_store=server.release_portfolio_governance_attestation_accepted_evidence_store,
        )
        server.release_portfolio_governance_attestation_transparency_acknowledgement_store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(
            transparency_store=server.release_portfolio_governance_attestation_transparency_store,
        )
        ack_store = server.release_portfolio_governance_attestation_transparency_acknowledgement_store
        server.public_trust_center_store = PublicTrustCenterStore(
            release_store=server.release_store,
            portfolio_store=server.release_portfolio_audit_store,
            registry_store=server.release_portfolio_governance_attestation_registry_store,
            portal_store=server.release_portfolio_governance_attestation_portal_store,
            transparency_store=server.release_portfolio_governance_attestation_transparency_store,
            acknowledgement_store=ack_store,
        )
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/refresh", {"profile": "public_summary"})
        response_zip = review_store.build_response_zip(portfolio_id, _response_payload("accepted"))
        _portal_import_status, portal_imported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/import", {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
        portal_response_id = portal_imported["response"]["response_id"]
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/refresh", {"response_id": portal_response_id})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/export", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/zip", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/verify", {"strict": True, "require_current": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/refresh", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/export", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/zip", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-registry/verify", {"strict": True, "require_current": True, "require_published": True, "require_accepted_evidence": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/refresh", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/export", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/zip", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/verify", {"strict": True, "require_current": True, "require_registry": True, "require_attestation": True, "require_accepted_evidence": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/refresh", {"require_accepted_evidence": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/export", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/zip", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/verify", {"strict": True, "require_current": True, "require_accepted_evidence": True, "require_contiguous_chain": True})
        refresh_pack_status, refresh_pack = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/pack/refresh", {"profile": "public_summary"})
        assert refresh_pack_status == 201, refresh_pack
        payload = response_template(refresh_pack["pack"])
        payload["response_id"] = "external-ack-server-001"
        payload["reviewer"] = {"name": "External Reviewer", "organization": "Review Org", "role": "reviewer"}
        payload["comments"] = "Transparency feed and notices reviewed."
        payload["submitted_at"] = "2026-06-12T00:00:00+00:00"
        payload["response_hash"] = response_payload_hash(payload)
        import_status, imported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/responses/import", {"content_base64": base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")})
        assert import_status == 201, imported
        response_id = imported["response"]["response_id"]
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/refresh", {"response_id": response_id})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/export", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/zip", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/verify", {"strict": True, "require_accepted": True})

        create_status, created = request_json(server, "POST", "/api/public-trust-centers", {"center_id": "ptc-default", "portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
        list_status, listed = request_json(server, "GET", "/api/public-trust-centers")
        refresh_status, refresh = request_json(server, "POST", "/api/public-trust-centers/ptc-default/refresh", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
        export_status, export = request_json(server, "POST", "/api/public-trust-centers/ptc-default/export")
        zip_status, zipped = request_json(server, "POST", "/api/public-trust-centers/ptc-default/zip")
        verify_status, verify = request_json(server, "POST", "/api/public-trust-centers/ptc-default/verify", {"strict": True, "require_registry_current": True, "require_portal_current": True, "require_transparency_current": True, "require_acknowledgement_current": True})
        detail_status, detail = request_json(server, "GET", "/api/public-trust-centers/ptc-default")
        archive_status, archive = request_json(server, "POST", "/api/public-trust-centers/ptc-default/archive")
        download_status, body = request_bytes(server, "GET", "/api/public-trust-centers/ptc-default.zip")
    finally:
        stop_test_server(server)

    assert import_status == 201
    assert create_status == 201
    assert created["center"]["center_id"] == "ptc-default"
    assert list_status == 200
    assert listed["summary"]["count"] >= 1
    assert refresh_status == 201
    assert refresh["summary"]["status"] == "passed"
    assert export_status == 201
    assert export["manifest"]["package_type"] == "musicforge_public_trust_center"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"
    assert detail_status == 200
    assert detail["summary"]["status"] == "passed"
    assert archive_status == 200
    assert archive["archive"]["zip_sha256"]
    assert download_status == 200
    assert body.startswith(b"PK")
