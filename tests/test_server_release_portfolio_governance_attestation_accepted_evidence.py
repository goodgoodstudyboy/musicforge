from __future__ import annotations

import base64
from pathlib import Path

from tests.test_release_portfolio_governance_attestation_portal_review import _response_payload
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_release_portfolio_governance_attestation_portal_review import _server_review_fixture

from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore


def test_server_attestation_accepted_evidence_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        portfolio_id = _server_review_fixture(server, tmp_path, monkeypatch)
        review_store = server.release_portfolio_governance_attestation_portal_review_store
        server.release_portfolio_governance_attestation_accepted_evidence_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
        refresh_pack_status, _refresh_pack = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/pack/refresh", {"profile": "public_summary"})
        response_zip = review_store.build_response_zip(portfolio_id, _response_payload("accepted"))
        import_status, imported = request_json(
            server,
            "POST",
            f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-portal-review/responses/import",
            {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")},
        )
        response_id = imported["response"]["response_id"]
        refresh_status, refresh = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/refresh", {"response_id": response_id})
        export_status, export = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/export", {"profile": "public_summary"})
        zip_status, zip_data = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/zip", {"profile": "public_summary"})
        verify_status, verify = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/verify", {"strict": True, "require_current": True})
        get_status, detail = request_json(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence")
        download_status, body = request_bytes(server, "GET", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence.zip")
        rejected_zip = review_store.build_response_zip(portfolio_id, _response_payload("rejected"))
        rejected_import = review_store.import_response(portfolio_id, {"content_base64": base64.b64encode(rejected_zip.read_bytes()).decode("ascii")})
        rejected_status, rejected = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/refresh", {"response_id": rejected_import["response"]["response_id"]})
        archive_short_status, archive_short = request_json(server, "POST", f"/api/release-portfolio-audits/{portfolio_id}/governance-attestation-accepted-evidence/archive", {"reason": "short"})
    finally:
        stop_test_server(server)

    assert refresh_pack_status == 200
    assert import_status == 201
    assert refresh_status == 201
    assert refresh["summary"]["external_review_status"] == "accepted"
    assert export_status == 201
    assert export["manifest"]["package_type"] == "release_portfolio_governance_attestation_accepted_evidence"
    assert zip_status == 200
    assert zip_data["zip"]["sha256"]
    assert verify_status == 200
    assert verify["verification"]["status"] == "passed"
    assert get_status == 200
    assert detail["summary"]["accepted_evidence_id"]
    assert download_status == 200
    assert body.startswith(b"PK")
    assert rejected_status == 409
    assert "accepted" in rejected["error"]
    assert archive_short_status == 409
    assert "reason" in archive_short["error"]
