from __future__ import annotations

from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_release_operations_audit_api_refresh_export_zip_verify(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        create_status, release_data = request_json(server, "POST", "/api/releases", {"name": "Audit API Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
        release_id = release_data["release"]["release_id"]
        get_status, initial = request_json(server, "GET", f"/api/releases/{release_id}/operations/audit")
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/operations/audit/refresh")
        entries_status, entries = request_json(server, "GET", f"/api/releases/{release_id}/operations/audit/entries")
        graph_status, graph = request_json(server, "GET", f"/api/releases/{release_id}/operations/audit/graph")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/operations/audit/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/operations/audit/export/zip")
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/operations/audit/verify", {"strict": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/operations/audit.zip")
    finally:
        stop_test_server(server)

    assert create_status == 201
    assert get_status == 200
    assert initial["summary"]["status"] == "missing"
    assert refresh_status == 200
    assert refreshed["summary"]["entry_count"] >= 1
    assert entries_status == 200
    assert entries["entries"]
    assert graph_status == 200
    assert graph["graph"]["nodes"]
    assert export_status == 201
    assert exported["manifest"]["audit_report"]["ledger_hash"] == refreshed["report"]["ledger_hash"]
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert verify_status == 200
    assert verified["summary"]["status"] in {"passed", "warning"}
    assert download_status == 200
    assert zip_bytes.startswith(b"PK")
