from __future__ import annotations

from song_agent.trust_operations_controls import TrustOperationsControlStore
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_trust_operations_controls import _control_payload, _controls_fixture


def test_trust_operations_controls_api_lifecycle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hub_store, incident_store, knowledge_store, _fixture, _delivery, _second_distribution, report_id = _controls_fixture(tmp_path)
    control_store = TrustOperationsControlStore(tmp_path / ".musicforge" / "server-trust-operations-controls", hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    payload = {key: str(value) for key, value in _control_payload(hub_store, incident_store, knowledge_store, report_id).items()}
    server = start_test_server()
    server.trust_operations_hub_store = hub_store
    server.trust_operations_incident_store = incident_store
    server.trust_operations_incident_knowledge_store = knowledge_store
    server.trust_operations_control_store = control_store
    try:
        refresh_status, refresh = request_json(server, "POST", "/api/trust-operations/hubs/hub/controls/catalog/refresh", payload)
        policy_status, policy = request_json(server, "POST", "/api/trust-operations/hubs/hub/controls/policies", {"policy_id": "toc-policy-000001"})
        assess_status, assessed = request_json(server, "POST", "/api/trust-operations/hubs/hub/controls/assess", {**payload, "policy_id": "toc-policy-000001"})
        assessment_id = assessed["assessment"]["assessment_id"]
        export_status, exported = request_json(server, "POST", f"/api/trust-operations/hubs/hub/controls/assessments/{assessment_id}/export", {})
        zip_status, zipped = request_json(server, "POST", f"/api/trust-operations/hubs/hub/controls/assessments/{assessment_id}/zip", {})
        verify_status, verified = request_json(server, "POST", f"/api/trust-operations/hubs/hub/controls/assessments/{assessment_id}/verify", {**payload, "strict": True, "require_policy_passed": True})
        download_status, body = request_bytes(server, "GET", f"/api/trust-operations/hubs/hub/controls/{assessment_id}.zip")
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert refresh["catalog"]["summary"]["control_count"] == 11
    assert policy_status == 201
    assert policy["policy"]["policy_id"] == "toc-policy-000001"
    assert assess_status == 201
    assert assessed["assessment"]["status"] == "passed"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "musicforge_trust_operations_control_manifest"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed", verified["verification"].get("blockers")
    assert download_status == 200
    assert body.startswith(b"PK")
