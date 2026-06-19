from __future__ import annotations

from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_trust_operations_hub_incidents import _incident_fixture


def test_trust_operations_hub_incidents_api_lifecycle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hub_store, _incident_store, _fixture_obj, _delivery, second_distribution, report_id = _incident_fixture(tmp_path)
    server = start_test_server()
    server.trust_operations_hub_store = hub_store
    server.trust_operations_incident_store = TrustOperationsIncidentStore(tmp_path / ".musicforge" / "server-trust-operations-incidents", hub_store=hub_store)
    try:
        refresh_status, refresh = request_json(server, "POST", "/api/trust-operations/hubs/hub/incidents/refresh", {})
        list_status, listed = request_json(server, "GET", "/api/trust-operations/hubs/hub/incidents")
        incident = listed["incidents"][0]
        incident_id = incident["incident_id"]
        detected_from = incident["detected_from"]
        triage_status, triage = request_json(server, "POST", f"/api/trust-operations/hubs/hub/incidents/{incident_id}/triage", {"severity": "high", "owner": "ops", "notes": "Need second target evidence."})
        plan_status, plan = request_json(server, "POST", f"/api/trust-operations/hubs/hub/incidents/{incident_id}/plan", {})
        evidence_status, evidence = request_json(
            server,
            "POST",
            f"/api/trust-operations/hubs/hub/incidents/{incident_id}/evidence",
            {
                "component_type": detected_from["component_type"],
                "component_id": detected_from["component_id"],
                "content_base64": __import__("base64").b64encode(second_distribution.read_bytes()).decode("ascii"),
            },
        )
        fix_status, fix = request_json(server, "POST", f"/api/trust-operations/hubs/hub/incidents/{incident_id}/verify-fix", {})
        close_status, close = request_json(server, "POST", f"/api/trust-operations/hubs/hub/incidents/{incident_id}/close", {"reason": "Second distribution target verification passed.", "closed_by": "ops"})
        export_status, exported = request_json(server, "POST", "/api/trust-operations/hubs/hub/incidents/export", {})
        zip_status, zipped = request_json(server, "POST", "/api/trust-operations/hubs/hub/incidents/zip", {})
        verify_status, verified = request_json(
            server,
            "POST",
            "/api/trust-operations/hubs/hub/incidents/verify",
            {"strict": True, "require_no_open_blocking": True, "require_current_hub": True, "hub_verification_report_path": str(hub_store.verification_report_path("hub", report_id))},
        )
        download_status, body = request_bytes(server, "GET", "/api/trust-operations/hubs/hub/incidents.zip")
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert refresh["incident_board"]["summary"]["blocking_open_count"] == 1
    assert list_status == 200
    assert len(listed["incidents"]) == 1
    assert triage_status == 200
    assert triage["incident"]["status"] == "triaged"
    assert plan_status == 201
    assert plan["plan"]["steps"]
    assert evidence_status == 201
    assert evidence["evidence"]["status"] == "passed"
    assert fix_status == 200
    assert fix["result"]["status"] == "passed"
    assert close_status == 200
    assert close["closeout"]["status"] == "passed"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "musicforge_trust_operations_hub_incident_manifest"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed", verified["verification"].get("blockers")
    assert download_status == 200
    assert body.startswith(b"PK")


def test_trust_operations_hub_incidents_api_rejects_source_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hub_store, _incident_store, _fixture_obj, _delivery, _second_distribution, _report_id = _incident_fixture(tmp_path)
    server = start_test_server()
    server.trust_operations_hub_store = hub_store
    server.trust_operations_incident_store = TrustOperationsIncidentStore(tmp_path / ".musicforge" / "server-trust-operations-incidents", hub_store=hub_store)
    try:
        request_json(server, "POST", "/api/trust-operations/hubs/hub/incidents/refresh", {})
        listed_status, listed = request_json(server, "GET", "/api/trust-operations/hubs/hub/incidents")
        incident_id = listed["incidents"][0]["incident_id"]
        evidence_status, evidence = request_json(server, "POST", f"/api/trust-operations/hubs/hub/incidents/{incident_id}/evidence", {"source_path": str(tmp_path / "report.json"), "report": {"status": "passed"}})
    finally:
        stop_test_server(server)

    assert listed_status == 200
    assert evidence_status == 409
    assert "source_path" in evidence["error"]
