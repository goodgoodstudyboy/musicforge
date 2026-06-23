from __future__ import annotations

import json

from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_trust_operations_final_readiness import _final_fixture


def _jsonable(value):
    return json.loads(json.dumps(value, default=str))


def test_trust_operations_final_readiness_api_lifecycle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _fixture, _watch_store, _signoff_store, source, _queue_id = _final_fixture(tmp_path)
    payload = _jsonable(source)
    server = start_test_server()
    try:
        summary_status, summary = request_json(server, "GET", "/api/trust-operations/final-readiness")
        refresh_status, refreshed = request_json(server, "POST", "/api/trust-operations/final-readiness/refresh", payload)
        certificate_status, certificated = request_json(server, "POST", "/api/trust-operations/final-readiness/certificate", {})
        sign_status, signed = request_json(
            server,
            "POST",
            "/api/trust-operations/final-readiness/sign",
            {"signed_by": "server-reviewer", "role": "owner", "reason": "Final handoff accepted for server test."},
        )
        export_status, exported = request_json(server, "POST", "/api/trust-operations/final-readiness/export", payload)
        zip_status, zipped = request_json(server, "POST", "/api/trust-operations/final-readiness/zip", {})
        verify_status, verified = request_json(server, "POST", "/api/trust-operations/final-readiness/verify", {**payload, "strict": True, "require_signed": True, "require_current": True})
        download_status, zip_bytes = request_bytes(server, "GET", "/api/trust-operations/final-readiness/download")
    finally:
        stop_test_server(server)

    assert summary_status == 200
    assert summary["status"] == "unsigned"
    assert refresh_status == 201
    assert refreshed["report"]["status"] == "ready"
    assert certificate_status == 201
    assert certificated["certificate"]["status"] == "ready"
    assert sign_status == 201
    assert signed["signoff"]["status"] == "signed"
    assert export_status == 201
    assert exported["manifest"]["integrity_hash"]
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed"
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
