from __future__ import annotations

from tests.test_release_audio_certification import _prepare_certified_release
from tests.test_server_releases import request_json, start_test_server, stop_test_server


def test_release_audio_certification_api_refresh_signoff_zip_verify(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _campaign_id, _store = _prepare_certified_release(server, "Certification API Track")
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/audio-certification/refresh")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/audio-certification/signoff", {"signed_by": "QA", "role": "developer"})
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/audio-certification/zip")
        verify_status, verified = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/audio-certification/verify",
            {"strict": True, "require_passed": True, "require_signed": True, "require_real_audio": True, "require_manual_review": True, "require_remediation_when_needed": True},
        )
        detail_status, detail = request_json(server, "GET", f"/api/releases/{release_id}/audio-certification")
    finally:
        stop_test_server(server)

    assert refresh_status == 200
    assert refreshed["report"]["status"] == "passed"
    assert sign_status == 201
    assert signed["status"] == "signed"
    assert zip_status == 200
    assert zipped["zip_sha256"]
    assert verify_status == 200
    assert verified["status"] == "passed", verified.get("blockers")
    assert detail_status == 200
    assert detail["report"]["status"] == "passed"
    assert detail["signoff"]["status"] == "signed"
