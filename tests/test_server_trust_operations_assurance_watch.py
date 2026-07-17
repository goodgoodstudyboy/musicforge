from __future__ import annotations

from pathlib import Path

from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_trust_operations_continuous_assurance import _assurance_fixture


def test_trust_operations_assurance_watch_api_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = _assurance_fixture(tmp_path)
    assurance_store = fixture.assurance_store
    run_id = assurance_store.refresh_run("hub", fixture.payload)["run"]["run_id"]
    assurance_store.export_archive(run_id)
    assurance_store.build_archive_zip(run_id)
    assurance_store.verify_archive_zip(run_id, {**fixture.assurance_verifier_payload, "strict": True, "require_passed": True, "require_current": True})
    payload = {
        "hub_id": "hub",
        "assurance_archive_path": str(assurance_store.archive_zip_path(run_id)),
        "assurance_verification_report_path": str(assurance_store.verification_report_path(run_id)),
        "hub_package_path": str(fixture.hub_zip),
        "hub_verification_report_path": str(fixture.hub_verification),
    }
    server = start_test_server()
    server.trust_operations_hub_store = assurance_store.hub_store
    server.trust_operations_assurance_store = TrustOperationsAssuranceStore(
        tmp_path / ".musicforge" / "server-trust-operations-assurance",
        hub_store=assurance_store.hub_store,
    )
    server.trust_operations_assurance_watch_store = TrustOperationsAssuranceWatchStore(
        tmp_path / ".musicforge" / "server-trust-operations-assurance-watch",
        assurance_store=assurance_store,
        hub_store=assurance_store.hub_store,
    )
    try:
        schedule_status, schedule = request_json(server, "GET", "/api/trust-operations/assurance-watch/schedule")
        refresh_status, refreshed = request_json(server, "POST", "/api/trust-operations/assurance-watch/queues", payload)
        queue_id = refreshed["queue"]["queue_id"]
        export_status, exported = request_json(server, "POST", f"/api/trust-operations/assurance-watch/queues/{queue_id}/export", payload)
        zip_status, zipped = request_json(server, "POST", f"/api/trust-operations/assurance-watch/queues/{queue_id}/zip", payload)
        verify_status, verified = request_json(server, "POST", f"/api/trust-operations/assurance-watch/queues/{queue_id}/verify", {"strict": True, "require_clear": True, "require_current": True, **payload})
        detail_status, detail = request_json(server, "GET", f"/api/trust-operations/assurance-watch/queues/{queue_id}")
        download_status, body = request_bytes(server, "GET", f"/api/trust-operations/assurance-watch/queues/{queue_id}/download")
    finally:
        stop_test_server(server)

    assert schedule_status == 200
    assert schedule["schedule"]["schedule_id"] == "default"
    assert refresh_status == 201
    assert refreshed["queue"]["status"] == "clear"
    assert export_status == 201
    assert exported["manifest"]["package_type"] == "musicforge_trust_operations_assurance_watch_manifest"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["verification"]["status"] == "passed", verified["verification"].get("blockers")
    assert detail_status == 200
    assert detail["queue"]["queue_id"] == queue_id
    assert download_status == 200
    assert body.startswith(b"PK")
