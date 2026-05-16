from __future__ import annotations

import base64

from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_releases import _signed_project


def test_distribution_api_end_to_end_and_signed_mutation_guard(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        release_id = _signed_release(server)
        profiles_status, profiles = request_json(server, "GET", "/api/distribution/profiles")
        target_status, target_data = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets", {"profile_id": "demo_pitch", "name": "Pitch"})
        target_id = target_data["target"]["target_id"]
        artwork_status, artwork = request_json(server, "POST", f"/api/releases/{release_id}/distribution/artwork/import", {"filename": "cover.png", "content_base64": base64.b64encode(_png(1400, 1400)).decode("ascii")})
        update_status, _updated = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}", {"options": {"artwork_id": artwork["artwork"]["artwork_id"]}})
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export/zip")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff", {"signed_by": "server-test"})
        verify_status, verified = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/verify", {"require_artwork": True})
        blocked_export_status, blocked_export = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
        blocked_qa_status, blocked_qa = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/qa/refresh")
        zip_download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/distribution/targets/{target_id}/export.zip")
        reset_status, reset = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/signoff/reset", {"reason": "rebuild distribution"})
        export_after_reset_status, _after = request_json(server, "POST", f"/api/releases/{release_id}/distribution/targets/{target_id}/export")
    finally:
        stop_test_server(server)

    assert profiles_status == 200
    assert any(item["profile_id"] == "demo_pitch" for item in profiles["profiles"])
    assert target_status == 201
    assert artwork_status == 201
    assert update_status == 200
    assert qa_status == 200
    assert qa["summary"]["status"] in {"passed", "warning"}
    assert export_status == 201
    assert exported["summary"]["status"] == "exported"
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert sign_status == 200
    assert signed["summary"]["status"] == "signed"
    assert verify_status == 200
    assert verified["summary"]["status"] == "passed"
    assert blocked_export_status == 409
    assert blocked_qa_status == 409
    assert "signed" in blocked_export["error"].lower()
    assert "signed" in blocked_qa["error"].lower()
    assert zip_download_status == 200
    assert zip_bytes.startswith(b"PK")
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
    assert export_after_reset_status == 201


def _signed_release(server) -> str:
    project_id = _signed_project(server, "Distribution API Song")
    created_status, created = request_json(server, "POST", "/api/releases", {"name": "Distribution API Pack", "release_type": "demo_pack", "primary_artist": "MusicForge"})
    release_id = created["release"]["release_id"]
    add_status, _added = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
    init_status, initialized = request_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
    metadata = initialized["metadata"]
    metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
    metadata["tracks"][0].update({"isrc": "USABC2600001", "lyrics": "Clean lyric", "credits": [{"role": "composer", "name": "Writer"}], "confirmed": True})
    save_status, _saved = request_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
    metadata_qa_status, _metadata_qa = request_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
    qa_status, _qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
    export_status, _export = request_json(server, "POST", f"/api/releases/{release_id}/export")
    metadata_export_status, _metadata_export = request_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
    sign_status, _signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "release-test"})
    assert created_status == 201
    assert add_status == 200
    assert init_status == 200
    assert save_status == 200
    assert metadata_qa_status == 200
    assert qa_status == 200
    assert export_status == 200
    assert metadata_export_status == 200
    assert sign_status == 200
    return release_id


def _png(width: int, height: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4, "big") + b"IHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00" + b"\x00" * 16
