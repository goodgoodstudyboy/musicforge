from __future__ import annotations

from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_release_operations_runbook_api_lifecycle_and_stale_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        create_release_status, release_data = request_json(server, "POST", "/api/releases", {"name": "Runbook API Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release_data["release"]["release_id"]
        create_status, created = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks", {})
        runbook_id = created["runbook"]["runbook_id"]
        list_status, listed = request_json(server, "GET", f"/api/releases/{release_id}/operations/runbooks")
        detail_status, detail = request_json(server, "GET", f"/api/releases/{release_id}/operations/runbooks/{runbook_id}")
        run_status, ran = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks/{runbook_id}/run-safe", {})
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks/{runbook_id}/export", {})
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks/{runbook_id}/export/zip", {})
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks/{runbook_id}/verify", {"require_current": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/operations/runbooks/{runbook_id}/export.zip")

        stale_status, stale_created = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks", {})
        stale_runbook_id = stale_created["runbook"]["runbook_id"]
        server.release_store.update_release(release_id, {"name": "Runbook API Release Changed"})
        stale_run_status, stale_run = request_json(server, "POST", f"/api/releases/{release_id}/operations/runbooks/{stale_runbook_id}/run-safe", {})
    finally:
        stop_test_server(server)

    assert create_release_status == 201
    assert create_status == 201
    assert created["summary"]["manual_required_count"] >= 1
    assert list_status == 200
    assert len(listed["runbooks"]) == 1
    assert detail_status == 200
    assert detail["runbook"]["runbook_id"] == runbook_id
    assert run_status == 200
    assert ran["summary"]["manual_required_count"] >= 1
    assert ran["summary"]["status"] in {"blocked", "failed"}
    assert export_status == 201
    assert exported["manifest"]["runbook"]["integrity_hash"]
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
    assert stale_status == 201
    assert stale_run_status == 409
    assert "stale" in stale_run.get("error", "").lower()
