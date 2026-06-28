from __future__ import annotations

from http.client import HTTPConnection
import json

from tests.test_release_audio_regression import _prepare_signed_timeline
from tests.test_server_releases import start_test_server, stop_test_server


def _post_json(server, path: str, payload: dict | None = None):
    conn = HTTPConnection(server.server_address[0], server.server_address[1], timeout=20)
    body = json.dumps(payload or {}).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    return response.status, json.loads(data) if data else {}


def _get_json(server, path: str):
    conn = HTTPConnection(server.server_address[0], server.server_address[1], timeout=20)
    conn.request("GET", path)
    response = conn.getresponse()
    data = response.read().decode("utf-8")
    conn.close()
    return response.status, json.loads(data) if data else {}


def test_audio_quality_observatory_api_and_release_gate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id, _timeline_id, _timeline_store = _prepare_signed_timeline(server, "Quality Observatory API Track")
        create_status, create_body = _post_json(server, "/api/audio-quality-observatories", {"release_ids": [release_id]})
        observatory_id = create_body["observatory"]["observatory_id"]
        refresh_status, refresh_body = _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/refresh")
        zip_status, zip_body = _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/zip")
        verify_status, verify_body = _post_json(server, f"/api/audio-quality-observatories/{observatory_id}/verify", {"strict": True, "require_current_evidence": True, "require_no_critical_risk": True})
        get_status, get_body = _get_json(server, f"/api/audio-quality-observatories/{observatory_id}")
        signoff_status, signoff_body = _post_json(server, f"/api/releases/{release_id}/signoff", {"require_release_audio_quality_observatory": True, "release_audio_quality_observatory_id": observatory_id, "force": True, "override_reason": "quality observatory gate smoke"})
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert refresh_status == 200
    assert refresh_body["status"] == "passed"
    assert zip_status == 200
    assert zip_body["status"] == "passed"
    assert verify_status == 200
    assert verify_body["status"] == "passed", verify_body["verification"].get("blockers")
    assert get_status == 200
    assert get_body["summary_report"]["status"] == "passed"
    assert signoff_status == 200, signoff_body
    assert signoff_body["signoff"]["acceptance_gate"]["release_audio_quality_observatory"]["status"] == "passed"
