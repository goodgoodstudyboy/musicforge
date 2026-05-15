from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.release_verifier import verify_release_zip
from tests.test_server_edits import request_bytes, request_json, start_test_server, stop_test_server
from tests.test_server_releases import _signed_project


def test_release_metadata_api_init_save_qa_export_and_download(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Server Metadata Song")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Server Metadata Pack", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        add_status, added = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id, "title": "Server Metadata Song"})
        init_status, initialized = request_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
        metadata = initialized["metadata"]
        metadata["release"].update({"upc": "123456789012", "copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
        metadata["tracks"][0].update({"isrc": "USABC2600001", "lyrics": "Server lyric line", "credits": [{"role": "composer", "name": "Server Writer", "source": "user"}], "confirmed": True})
        save_status, saved = request_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
        release_qa_status, release_qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/export")
        metadata_export_status, metadata_export = request_json(server, "POST", f"/api/releases/{release_id}/metadata/export")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "metadata-server-test"})
        platform_status, platform_csv = request_bytes(server, "GET", f"/api/releases/{release_id}/metadata/platform.csv")
        credits_status, credits_csv = request_bytes(server, "GET", f"/api/releases/{release_id}/metadata/credits.csv")
        zip_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/export.zip")
        get_status, got = request_json(server, "GET", f"/api/releases/{release_id}/metadata")
        zip_path = Path(".musicforge") / "releases" / release_id / "release-export.zip"
        report = verify_release_zip(zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            release_metadata = json.loads(archive.read("release-metadata.json").decode("utf-8"))
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert add_status == 200
    assert init_status == 200
    assert initialized["metadata"]["release"]["title"] == "Server Metadata Pack"
    assert save_status == 200
    assert saved["summary"]["qa_status"] == "passed"
    assert qa_status == 200
    assert qa["summary"]["status"] == "passed"
    assert release_qa_status == 200
    assert release_qa["summary"]["status"] in {"passed", "warning"}
    assert export_status == 200
    assert exported["manifest"]["metadata"]["exists"] is True
    assert metadata_export_status == 200
    assert metadata_export["summary"]["status"] == "exported"
    assert sign_status == 200
    assert signoff["summary"]["status"] == "signed"
    assert platform_status == 200
    assert b"USABC2600001" in platform_csv
    assert credits_status == 200
    assert b"Server Writer" in credits_csv
    assert zip_status == 200
    assert zip_bytes.startswith(b"PK")
    assert get_status == 200
    assert got["metadata"]["tracks"][0]["isrc"] == "USABC2600001"
    assert "release-metadata.json" in names
    assert "lyrics/01-server-metadata-song.txt" in names
    assert release_metadata["tracks"][0]["credits"][0]["name"] == "Server Writer"
    assert report["status"] == "passed"


def test_release_metadata_api_rejects_signed_release_mutation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Signed Metadata Song")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Signed Metadata Pack", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        add_status, _added = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        init_status, initialized = request_json(server, "POST", f"/api/releases/{release_id}/metadata/init")
        metadata = initialized["metadata"]
        metadata["release"].update({"copyright": "2026 MusicForge", "phonographic_copyright": "2026 MusicForge", "confirmed": True})
        metadata["tracks"][0].update({"lyrics": "Clean lyric", "credits": [{"role": "composer", "name": "Writer"}], "confirmed": True})
        save_status, _saved = request_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
        qa_status, _qa = request_json(server, "POST", f"/api/releases/{release_id}/metadata/qa/refresh")
        release_qa_status, _release_qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _export = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zip = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, _signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "server-test"})
        mutate_status, mutate = request_json(server, "POST", f"/api/releases/{release_id}/metadata", metadata)
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert add_status == 200
    assert init_status == 200
    assert save_status == 200
    assert qa_status == 200
    assert release_qa_status == 200
    assert export_status == 200
    assert zip_status == 200
    assert sign_status == 200
    assert mutate_status == 409
    assert "signed" in mutate["error"].lower()
