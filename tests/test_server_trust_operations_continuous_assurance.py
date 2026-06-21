from __future__ import annotations

from pathlib import Path

from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_trust_operations_continuous_assurance import _assurance_fixture


def test_trust_operations_assurance_api_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = _assurance_fixture(tmp_path)
    server = start_test_server()
    server.trust_operations_hub_store = fixture.assurance_store.hub_store
    server.trust_operations_assurance_store = TrustOperationsAssuranceStore(
        tmp_path / ".musicforge" / "server-trust-operations-assurance",
        hub_store=fixture.assurance_store.hub_store,
    )
    payload = {"hub_id": "hub", **_jsonable(fixture.payload)}
    verify_payload = _jsonable(fixture.assurance_verifier_payload)
    try:
        refresh_status, refreshed = request_json(server, "POST", "/api/trust-operations/assurance/runs", payload)
        run_id = refreshed["run"]["run_id"]
        export_status, exported = request_json(server, "POST", f"/api/trust-operations/assurance/runs/{run_id}/export")
        zip_status, zipped = request_json(server, "POST", f"/api/trust-operations/assurance/runs/{run_id}/zip")
        verify_status, verified = request_json(server, "POST", f"/api/trust-operations/assurance/runs/{run_id}/verify", {"strict": True, "require_passed": True, "require_current": True, **verify_payload})
        summary_status, summary = request_json(server, "GET", f"/api/trust-operations/assurance/runs/{run_id}")
        download_status, body = request_bytes(server, "GET", f"/api/trust-operations/assurance/runs/{run_id}/download")
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert refreshed["run"]["status"] == "passed", refreshed["run"].get("checks")
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "musicforge_trust_operations_continuous_assurance_manifest"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed", verified["verification"].get("blockers")
    assert summary_status == 200
    assert summary["run"]["status"] == "passed"
    assert download_status == 200
    assert body.startswith(b"PK")


def _jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value
