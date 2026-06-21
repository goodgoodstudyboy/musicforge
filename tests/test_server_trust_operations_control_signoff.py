from __future__ import annotations

from pathlib import Path

from song_agent.trust_operations_control_signoff import TrustOperationsControlSignoffStore
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_trust_operations_control_signoff import _signoff_fixture
from tests.test_trust_operations_controls import _controls_fixture


def test_trust_operations_control_signoff_api_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    hub_store, incident_store, knowledge_store, _fixture, _delivery, _second_distribution, report_id = _controls_fixture(tmp_path)
    control_store, _signoff_store, assessment_id, payload = _signoff_fixture(tmp_path, hub_store, incident_store, knowledge_store, report_id)
    server = start_test_server()
    server.trust_operations_hub_store = hub_store
    server.trust_operations_incident_store = incident_store
    server.trust_operations_incident_knowledge_store = knowledge_store
    server.trust_operations_control_store = control_store
    server.trust_operations_control_signoff_store = TrustOperationsControlSignoffStore(
        tmp_path / ".musicforge" / "server-trust-operations-control-signoffs",
        control_store=control_store,
        hub_store=hub_store,
        incident_store=incident_store,
        knowledge_store=knowledge_store,
    )
    try:
        sign_status, signed = request_json(server, "POST", "/api/trust-operations/control-signoff/hub/sign", {"assessment_id": assessment_id, "signed_by": "server-test", **{key: str(value) for key, value in payload.items()}})
        export_status, exported = request_json(server, "POST", "/api/trust-operations/control-signoff/hub/export", {key: str(value) for key, value in payload.items()})
        zip_status, zipped = request_json(server, "POST", "/api/trust-operations/control-signoff/hub/zip")
        verify_status, verified = request_json(server, "POST", "/api/trust-operations/control-signoff/hub/verify", {"strict": True, "require_signed": True, "require_current": True, **{key: str(value) for key, value in payload.items()}})
        summary_status, summary = request_json(server, "GET", "/api/trust-operations/control-signoff/hub")
        download_status, body = request_bytes(server, "GET", "/api/trust-operations/control-signoff/hub/download")
    finally:
        stop_test_server(server)

    assert sign_status == 201
    assert signed["signoff"]["status"] == "signed"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "musicforge_trust_operations_control_signoff_manifest"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed", verified["verification"].get("blockers")
    assert summary_status == 200
    assert summary["signoff"]["status"] == "signed"
    assert download_status == 200
    assert body.startswith(b"PK")
