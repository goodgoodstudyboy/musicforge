from __future__ import annotations

from pathlib import Path

from tests.test_release_operations_reviewer_pack import accepted_reviewer_fixture
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server


def test_server_release_operations_reviewer_pack_routes(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release, *_ = accepted_reviewer_fixture(Path(".musicforge"), monkeypatch)
        release_id = release.release_id

        get_status, initial = request_json(server, "GET", f"/api/releases/{release_id}/operations/reviewer-pack")
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/operations/reviewer-pack/refresh")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/operations/reviewer-pack/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/operations/reviewer-pack/export/zip")
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/operations/reviewer-pack/verify", {"strict": True, "require_audit": True, "require_signed": True, "require_archive": True})
        download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/operations/reviewer-pack.zip")

        assert get_status == 200
        assert initial["summary"]["status"] in {"missing", "passed"}
        assert refresh_status == 200
        assert refreshed["summary"]["status"] == "passed"
        assert export_status == 201
        assert exported["summary"]["status"] == "passed"
        assert zip_status == 200
        assert zipped["zip"]["sha256"]
        assert verify_status == 200
        assert verified["summary"]["status"] == "passed"
        assert download_status == 200
        assert zip_bytes.startswith(b"PK")
    finally:
        stop_test_server(server)
