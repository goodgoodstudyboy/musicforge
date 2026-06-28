from __future__ import annotations

from http.client import HTTPConnection
import json
from pathlib import Path

from tests.test_release_audio_baseline_response import _prepare_regression_pair
from tests.test_server_releases import start_test_server, stop_test_server


def _post_json(server, path: str, payload: dict) -> tuple[int, dict]:
    conn = HTTPConnection(server.server_address[0], server.server_address[1], timeout=20)
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    return response.status, json.loads(data) if data else {}


def test_release_audio_response_api_and_release_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store, current_release_id, _current_timeline_id, _current_store, regression_store = _prepare_regression_pair(server, "Server Response Gate Track")
        regression_store.refresh_report(current_release_id)
        regression_store.signoff(current_release_id, {"signed_by": "QA", "role": "developer"})
        regression_store.build_zip(current_release_id)
        regression_store.verify_zip(current_release_id, strict=True, require_passed=True, require_signed=True, require_current=True, require_baseline_current=True)

        status, created = _post_json(server, f"/api/audio-baselines", {
            "release_id": baseline_release_id,
            "timeline": str(baseline_store.zip_path(baseline_release_id, baseline_timeline_id)),
            "timeline_verification_report": str(baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id)),
            "certification": str(baseline_store.certification_store.zip_path(baseline_release_id)),
            "certification_verification_report": str(baseline_store.certification_store.verification_report_path(baseline_release_id)),
        })
        baseline_id = created["baseline"]["baseline_id"]
        approve_status, _ = _post_json(server, f"/api/audio-baselines/{baseline_id}/approve", {"approved_by": "QA", "reason": "baseline approved"})
        activate_status, _ = _post_json(server, f"/api/audio-baselines/{baseline_id}/activate", {})

        create_status, create_body = _post_json(server, f"/api/releases/{current_release_id}/audio-regression-response/create", {})
        closeout_status, closeout_body = _post_json(server, f"/api/releases/{current_release_id}/audio-regression-response/closeout", {"closed_by": "QA", "reason": "recheck passed"})
        signoff_status, _ = _post_json(server, f"/api/releases/{current_release_id}/audio-regression-response/signoff", {"signed_by": "QA", "role": "developer"})
        zip_status, _ = _post_json(server, f"/api/releases/{current_release_id}/audio-regression-response/zip", {})
        verify_status, verify_body = _post_json(server, f"/api/releases/{current_release_id}/audio-regression-response/verify", {"strict": True, "require_closed": True, "require_signed": True, "require_regression_current": True})
        baseline_gate = server.release_audio_baseline_governance_store.gate(baseline_release_id, baseline_id=baseline_id, required=True)
        response_gate = server.release_audio_regression_response_store.gate(current_release_id, required=True, require_signed=True)
    finally:
        stop_test_server(server)

    assert status == 201
    assert approve_status == 200
    assert activate_status == 200
    assert create_status == 201
    assert create_body["plan"]["status"] == "closed"
    assert closeout_status == 200
    assert closeout_body["closeout"]["status"] == "closed"
    assert signoff_status == 201
    assert zip_status == 200
    assert verify_status == 200
    assert verify_body["verification"]["status"] == "passed"
    assert baseline_gate["status"] == "passed"
    assert response_gate["status"] == "passed"


def test_release_signoff_rejects_unrelated_audio_baseline(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        baseline_release_id, baseline_timeline_id, baseline_store, current_release_id, *_ = _prepare_regression_pair(server, "Server Wrong Baseline Track")
        status, created = _post_json(
            server,
            "/api/audio-baselines",
            {
                "release_id": baseline_release_id,
                "timeline": str(baseline_store.zip_path(baseline_release_id, baseline_timeline_id)),
                "timeline_verification_report": str(baseline_store.verification_report_path(baseline_release_id, baseline_timeline_id)),
                "certification": str(baseline_store.certification_store.zip_path(baseline_release_id)),
                "certification_verification_report": str(baseline_store.certification_store.verification_report_path(baseline_release_id)),
            },
        )
        baseline_id = created["baseline"]["baseline_id"]
        _post_json(server, f"/api/audio-baselines/{baseline_id}/approve", {"approved_by": "QA", "reason": "baseline approved"})
        _post_json(server, f"/api/audio-baselines/{baseline_id}/activate", {})
        signoff_status, signoff_body = _post_json(
            server,
            f"/api/releases/{current_release_id}/signoff",
            {"require_release_audio_baseline_governance": True, "release_audio_baseline_id": baseline_id, "force": True, "override_reason": "must not bypass baseline mismatch"},
        )
    finally:
        stop_test_server(server)

    assert status == 201
    assert signoff_status == 409
    gate = signoff_body["acceptance_gate"]["release_audio_baseline_governance"]
    assert gate["status"] == "failed"
    assert gate["hard_block"] is True
    assert "track_identity_set_mismatch" in gate["preflight"]["reasons"]
