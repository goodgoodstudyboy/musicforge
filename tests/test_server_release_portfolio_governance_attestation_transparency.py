from __future__ import annotations

import base64
from pathlib import Path

from tests.test_release_portfolio_governance_attestation_portal_review import _response_payload
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_release_portfolio_governance_attestation_portal_review import _server_review_fixture

from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore


def test_server_attestation_transparency_api(tmp_path: Path, monkeypatch) -> None:
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
        refresh_pack_status, _refresh_pack = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/refresh", {"profile": "public_summary"})
        response_zip = review_store.build_response_zip(portfolio_id, _response_payload("accepted"))
        import_status, imported = request_json(
            server,
            "POST",
            f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/import",
            {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")},
        )
        response_id = imported["response"]["response_id"]
        accepted_refresh_status, _accepted_refresh = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/refresh", {"response_id": response_id})
        accepted_export_status, _accepted_export = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/export", {"profile": "public_summary"})
        accepted_zip_status, _accepted_zip = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/zip", {"profile": "public_summary"})
        accepted_verify_status, _accepted_verify = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/verify", {"strict": True, "require_current": True})
        portal_refresh_status, _portal_refresh = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/refresh", {"profile": "public_summary"})
        portal_refresh2_status, _portal_refresh2 = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal/refresh", {"profile": "public_summary"})

        refresh_status, refresh = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/refresh", {"require_accepted_evidence": True})
        export_status, export = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/export", {"profile": "public_summary"})
        zip_status, zip_data = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/zip", {"profile": "public_summary"})
        verify_status, verify = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/verify", {"strict": True, "require_current": True, "require_accepted_evidence": True, "require_contiguous_chain": True})
        get_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency")
        notices_status, notices = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/notices")
        notice_id = notices["notices"][0]["notice_id"]
        notice_status, notice = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency/notices/{notice_id}")
        download_status, body = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-transparency.zip")
    finally:
        stop_test_server(server)

    assert refresh_pack_status == 200
    assert import_status == 201
    assert accepted_refresh_status == 201
    assert accepted_export_status == 201
    assert accepted_zip_status == 200
    assert accepted_verify_status == 200
    assert portal_refresh_status == 200
    assert portal_refresh2_status == 200
    assert refresh_status == 201
    assert refresh["summary"]["external_review_status"] == "accepted"
    assert export_status == 201
    assert export["manifest"]["package_type"] == "release_portfolio_governance_attestation_transparency"
    assert zip_status == 200
    assert zip_data["zip"]["sha256"]
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"
    assert get_status == 200
    assert detail["summary"]["event_count"] >= 4
    assert notices_status == 200
    assert notice_status == 200
    assert notice["notice"]["notice_id"] == notice_id
    assert download_status == 200
    assert body.startswith(b"PK")
