from __future__ import annotations

from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_trust_operations_incident_knowledge import _closed_incident_fixture


def test_trust_operations_incident_knowledge_api_lifecycle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hub_store, incident_store, _fixture_obj, _delivery, _second_distribution, report_id = _closed_incident_fixture(tmp_path)
    server = start_test_server()
    server.trust_operations_hub_store = hub_store
    server.trust_operations_incident_store = incident_store
    server.trust_operations_incident_knowledge_store = TrustOperationsIncidentKnowledgeStore(tmp_path / ".musicforge" / "server-trust-operations-knowledge", hub_store=hub_store, incident_store=incident_store)
    try:
        refresh_status, refresh = request_json(server, "POST", "/api/trust-operations/hubs/hub/knowledge/refresh", {})
        entry_id = refresh["entries"][0]["entry_id"]
        guard_status, guard = request_json(server, "POST", f"/api/trust-operations/hubs/hub/knowledge/entries/{entry_id}/guards", {})
        guard_id = guard["guard"]["guard_id"]
        run_status, run = request_json(server, "POST", f"/api/trust-operations/hubs/hub/knowledge/guards/{guard_id}/run", {})
        recurrence_status, recurrence = request_json(server, "POST", "/api/trust-operations/hubs/hub/knowledge/recurrence/refresh", {})
        export_status, exported = request_json(server, "POST", "/api/trust-operations/hubs/hub/knowledge/export", {})
        zip_status, zipped = request_json(server, "POST", "/api/trust-operations/hubs/hub/knowledge/zip", {})
        verify_status, verified = request_json(
            server,
            "POST",
            "/api/trust-operations/hubs/hub/knowledge/verify",
            {
                "strict": True,
                "require_guards_passed": True,
                "require_no_open_recurrence": True,
                "incident_board_verification_report_path": str(incident_store.verification_report_path("hub")),
                "hub_verification_report_path": str(hub_store.verification_report_path("hub", report_id)),
            },
        )
        download_status, body = request_bytes(server, "GET", "/api/trust-operations/hubs/hub/knowledge.zip")
    finally:
        stop_test_server(server)

    assert refresh_status == 201
    assert refresh["knowledge_base"]["summary"]["entry_count"] == 1
    assert guard_status == 201
    assert guard["guard"]["guard_type"] == "external_report_coverage"
    assert run_status == 200
    assert run["guard_run"]["status"] == "passed"
    assert recurrence_status == 200
    assert recurrence["recurrence"]["status"] == "passed"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "musicforge_trust_operations_incident_knowledge_manifest"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed", verified["verification"].get("blockers")
    assert download_status == 200
    assert body.startswith(b"PK")

