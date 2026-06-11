from __future__ import annotations

import base64
import json
from pathlib import Path

from tests.test_release_portfolio_governance_attestation_transparency_acknowledgement import _accepted_response
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_release_portfolio_governance_attestation_transparency import _response_payload, _server_review_fixture

from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore


def test_server_attestation_transparency_acknowledgement_api(tmp_path: Path, monkeypatch) -> None:
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

        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/refresh", {"profile": "public_summary"})
        response_zip = review_store.build_response_zip(portfolio_id, _response_payload("accepted"))
        _status, imported = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/import", {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
        response_id = imported["response"]["response_id"]
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/refresh", {"response_id": response_id})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/export", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/zip", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/verify", {"strict": True, "require_current": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/refresh", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/refresh", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/refresh", {"require_accepted_evidence": True})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/export", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/zip", {"profile": "public_summary"})
        request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/verify", {"strict": True, "require_current": True, "require_accepted_evidence": True, "require_contiguous_chain": True})

        refresh_status, refresh = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/pack/refresh", {"profile": "public_summary"})
        export_status, export = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/pack/export", {"profile": "public_summary"})
        zip_status, zip_data = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/pack/zip", {"profile": "public_summary"})
        verify_status, verify = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/pack/verify", {"strict": True, "require_transparency": True})
        payload = _accepted_response(refresh["pack"])
        import_status, ack_import = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/responses/import", {"content_base64": base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")})
        bad = dict(payload)
        bad.pop("review_pack_source_hash")
        bad_status, _bad = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/responses/import", {"content": bad})
        ack_response_id = ack_import["response"]["response_id"]
        evidence_status, evidence = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/refresh", {"response_id": ack_response_id})
        evidence_export_status, _evidence_export = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/export", {"profile": "public_summary"})
        evidence_zip_status, _evidence_zip = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/zip", {"profile": "public_summary"})
        evidence_verify_status, evidence_verify = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement/evidence/verify", {"strict": True, "require_accepted": True})
        get_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement")
        download_pack_status, pack_body = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement-pack.zip")
        download_evidence_status, evidence_body = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency-acknowledgement-evidence.zip")
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert refresh["pack"]["status"] == "ready"
    assert export_status == 201
    assert export["manifest"]["package_type"] == "release_portfolio_governance_attestation_transparency_acknowledgement_pack"
    assert zip_status == 200
    assert zip_data["zip"]["sha256"]
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"
    assert import_status == 201
    assert bad_status == 409
    assert evidence_status == 201
    assert evidence["acknowledgement_evidence"]["status"] == "current"
    assert evidence_export_status == 201
    assert evidence_zip_status == 200
    assert evidence_verify_status == 200
    assert evidence_verify["verification"]["status"] == "passed"
    assert get_status == 200
    assert detail["evidence_summary"]["external_review_status"] == "accepted"
    assert download_pack_status == 200 and pack_body.startswith(b"PK")
    assert download_evidence_status == 200 and evidence_body.startswith(b"PK")
