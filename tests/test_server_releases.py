from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.auth import AuthConfig
from song_agent.projectio import read_json, write_json
from song_agent.releases import stable_hash
from tests.test_server_auth import TOKEN, request_json as auth_request_json, start_test_server as start_auth_server, stop_test_server as stop_auth_server
from tests.test_server_edits import request_bytes, request_json, request_payload, start_test_server, stop_test_server, wait_for_job


def test_release_workspace_api_qa_export_zip_signoff_and_reset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        first_project = _signed_project(server, "Release Track One")
        second_project = _signed_project(server, "Release Track Two")

        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Release API EP", "release_type": "ep", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        first_track_status, first_track = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        second_track_status, second_track = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second_project})
        list_status, listed = request_json(server, "GET", "/api/releases")
        detail_status, detail = request_json(server, "GET", f"/api/releases/{release_id}")
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        list_after_qa_status, list_after_qa = request_json(server, "GET", "/api/releases")
        sign_before_export_status, sign_before_export = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {})
        export_status, exported = request_json(server, "POST", f"/api/releases/{release_id}/export")
        sign_before_zip_status, sign_before_zip = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {})
        zip_status, zipped = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        zip_download_status, zip_bytes = request_bytes(server, "GET", f"/api/releases/{release_id}/export.zip")
        qa_after_zip_status, qa_after_zip = request_json(server, "GET", f"/api/releases/{release_id}/qa")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "notes": r"accepted C:\Users\demo api_key=sk-secret-value"})
        export_after_sign_status, export_after_sign = request_json(server, "GET", f"/api/releases/{release_id}/export")
        with zipfile.ZipFile(Path(".musicforge") / "releases" / release_id / "release-export.zip") as archive:
            zipped_signoff = json.loads(archive.read("release-signoff.json").decode("utf-8"))
            zipped_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        disk_manifest = read_json(Path(".musicforge") / "releases" / release_id / "release-export" / "manifest.json")
        expected_manifest_hash = stable_hash({key: value for key, value in disk_manifest.items() if key != "zip"})
        blocked_track_status, blocked_track = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        reset_missing_status, reset_missing = request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {})
        reset_status, reset = request_json(server, "POST", f"/api/releases/{release_id}/signoff/reset", {"reason": r"rebuild release C:\Users\demo"})
        add_after_reset_status, add_after_reset = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project, "title": "Bonus"})
        serialized = json.dumps({"signed": signed, "reset": reset, "exported": exported}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert first_track_status == 200
    assert second_track_status == 200
    assert len(second_track["release"]["tracks"]) == 2
    assert list_status == 200
    assert listed["releases"][0]["release_id"] == release_id
    assert detail_status == 200
    assert detail["summary"]["track_count"] == 2
    assert qa_status == 200
    assert qa["summary"]["status"] in {"passed", "warning"}
    assert list_after_qa_status == 200
    assert list_after_qa["releases"][0]["qa_summary"]["status"] in {"passed", "warning"}
    assert sign_before_export_status == 409
    assert "Release Export" in sign_before_export["error"]
    assert export_status == 200
    assert exported["summary"]["track_count"] == 2
    assert all(file.get("path") and not str(file.get("path")).startswith(("/", "\\")) for file in exported["manifest"]["files"])
    assert any(file["path"].endswith("/song.mid") for file in exported["manifest"]["files"])
    assert sign_before_zip_status == 409
    assert "Release ZIP" in sign_before_zip["error"]
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert "path" not in zipped["zip"]
    assert zip_download_status == 200
    assert zip_bytes.startswith(b"PK")
    assert qa_after_zip_status == 200
    assert qa_after_zip["release_qa"]["status"] in {"passed", "warning"}
    assert sign_status == 200
    assert signed["summary"]["status"] == "signed"
    assert export_after_sign_status == 200
    assert export_after_sign["manifest"]["summary"]["signoff_status"] == "signed"
    assert zipped_signoff["status"] == "signed"
    assert signed["signoff"]["export_manifest_hash"] == expected_manifest_hash
    assert zipped_signoff["export_manifest_hash"] == expected_manifest_hash
    assert stable_hash({key: value for key, value in zipped_manifest.items() if key != "zip"}) == expected_manifest_hash
    assert disk_manifest["zip"]["entry_count"] == len(zipped_manifest["zip"]["entries"])
    assert "sha256" not in disk_manifest["zip"]
    assert blocked_track_status == 409
    assert "signed" in blocked_track["error"].lower()
    assert reset_missing_status == 400
    assert "reason" in reset_missing["error"]
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
    assert add_after_reset_status == 200
    assert add_after_reset["summary"]["track_count"] == 3
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_project_add_to_release_and_release_qa_stale_after_project_export_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Release Project Entry")
        release_status, release_data = request_json(server, "POST", "/api/releases", {"name": "Project Entry Pack", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = release_data["release"]["release_id"]
        targets_status, targets = request_json(server, "GET", f"/api/projects/{project_id}/release-targets")
        add_status, added = request_json(server, "POST", f"/api/projects/{project_id}/add-to-release", {"release_id": release_id})
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")

        project_dir = Path(".musicforge") / "projects" / project_id
        manifest_path = project_dir / "final-export" / "manifest.json"
        manifest = read_json(manifest_path)
        (project_dir / "final-export" / "song.mid").unlink()
        manifest["files"] = [file for file in manifest["files"] if file.get("path") != "song.mid"]
        write_json(manifest_path, manifest)

        stale_status, stale = request_json(server, "GET", f"/api/releases/{release_id}/qa")
        refresh_status, refreshed = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        core_check = next(check for check in refreshed["release_qa"]["track_checks"] if check["check_id"] == "final_export_core_files")
    finally:
        stop_test_server(server)

    assert release_status == 201
    assert targets_status == 200
    assert targets["releases"][0]["release_id"] == release_id
    assert add_status == 200
    assert added["release"]["tracks"][0]["project_id"] == project_id
    assert qa_status == 200
    assert qa["summary"]["status"] in {"passed", "warning"}
    assert stale_status == 200
    assert stale["release_qa"]["status"] == "stale"
    assert refresh_status == 200
    assert refreshed["summary"]["status"] == "failed"
    assert core_check["status"] == "failed"


def test_release_signoff_blocks_non_manual_release_candidate_acceptance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Acceptance Gate Track")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Acceptance Gate Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")

        suite_status, suite_data = request_json(server, "POST", "/api/acceptance/suites", {"name": "RC Synthetic", "profile_id": "release_candidate", "require_audio_if_renderer_configured": False})
        suite_id = suite_data["suite"]["suite_id"]
        case_status, case_data = request_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases",
            {"song_id": "upbeat_pop_001", "request": {"title": "Gate Song", "language": "English", "style": "upbeat pop", "theme": "gate", "duration_seconds": 90}},
        )
        case_id = case_data["case"]["case_id"]
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Synthetic release candidate review should be blocked.", "audio_mode": "midi", "review_mode": "synthetic"})
        report_status, report = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        sign_status, signoff = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "acceptance_suite_id": suite_id})
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert suite_status == 201
    assert case_status == 201
    assert report_status == 200
    assert report["summary"]["release_ready"] is False
    assert sign_status == 409
    assert "Acceptance suite" in signoff["error"]


def test_release_signoff_blocks_incomplete_manual_release_candidate_acceptance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _signed_project(server, "Acceptance Gate Manual Track")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Acceptance Gate Manual Release", "release_type": "demo_pack", "primary_artist": "MusicForge"})
        release_id = created["release"]["release_id"]
        request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": project_id})
        request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        request_json(server, "POST", f"/api/releases/{release_id}/export")
        request_json(server, "POST", f"/api/releases/{release_id}/export/zip")

        suite_status, suite_data = request_json(server, "POST", "/api/acceptance/suites", {"name": "RC Manual", "profile_id": "release_candidate", "require_audio_if_renderer_configured": False})
        suite_id = suite_data["suite"]["suite_id"]
        case_status, case_data = request_json(
            server,
            "POST",
            f"/api/acceptance/suites/{suite_id}/cases",
            {"song_id": "upbeat_pop_001", "request": {"title": "Gate Manual Song", "language": "English", "style": "upbeat pop", "theme": "gate", "duration_seconds": 90}},
        )
        case_id = case_data["case"]["case_id"]
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/generate", {"render_audio": "never"})
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/health")
        request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/cases/{case_id}/review", {"rating": 5, "status": "accepted", "playback_confirmed": True, "notes": "Manual release candidate review.", "audio_mode": "midi", "review_mode": "manual"})
        report_status, report = request_json(server, "POST", f"/api/acceptance/suites/{suite_id}/report")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "tester", "acceptance_suite_id": suite_id})
    finally:
        stop_test_server(server)

    assert created_status == 201
    assert suite_status == 201
    assert case_status == 201
    assert report_status == 200
    assert report["summary"]["acceptance_status"] == "failed"
    assert report["summary"]["songbook_coverage_status"] == "incomplete"
    assert report["summary"]["release_ready"] is False
    assert "sad_ballad_001" in report["summary"]["missing_song_ids"]
    assert sign_status == 409
    assert "Acceptance suite" in signed["error"]


def test_release_auth_protected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_auth_server(AuthConfig(enabled=True, token=TOKEN))
    try:
        protected = [
            ("GET", "/api/releases", None),
            ("POST", "/api/releases", {"name": "Auth Release"}),
            ("GET", "/api/releases/release-000001", None),
            ("PATCH", "/api/releases/release-000001", {"name": "x"}),
            ("POST", "/api/releases/release-000001/tracks", {"project_id": "auth-project"}),
            ("POST", "/api/releases/release-000001/tracks/reorder", {"track_ids": []}),
            ("POST", "/api/releases/release-000001/tracks/track-000001/refresh", None),
            ("POST", "/api/releases/release-000001/tracks/track-000001/remove", None),
            ("GET", "/api/releases/release-000001/qa", None),
            ("POST", "/api/releases/release-000001/qa/refresh", None),
            ("GET", "/api/releases/release-000001/export", None),
            ("POST", "/api/releases/release-000001/export", None),
            ("POST", "/api/releases/release-000001/export/zip", None),
            ("GET", "/api/releases/release-000001/export.zip", None),
            ("GET", "/api/releases/release-000001/signoff", None),
            ("POST", "/api/releases/release-000001/signoff", {}),
            ("POST", "/api/releases/release-000001/signoff/reset", {"reason": "x"}),
            ("GET", "/api/releases/release-000001/events", None),
            ("GET", "/api/projects/auth-project/release-targets", None),
            ("POST", "/api/projects/auth-project/add-to-release", {"release_id": "release-000001"}),
        ]
        statuses = [auth_request_json(server, method, path, payload)[0] for method, path, payload in protected]
    finally:
        stop_auth_server(server)

    assert statuses == [401] * len(protected)


def _signed_project(server, title: str) -> str:
    created_status, created = request_json(server, "POST", "/api/projects", {"name": title})
    assert created_status == 201
    project_id = created["project"]["project_id"]
    version_status, version_data = request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload(title), "name": title})
    assert version_status == 202
    job = wait_for_job(server, version_data["job"]["job_id"])
    assert job["status"] == "completed"
    final_status, _final = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
    assert final_status == 200
    export_status, _exported = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
    assert export_status == 200
    zip_status, _zipped = request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
    assert zip_status == 200
    qa_status, qa = request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
    assert qa_status == 200
    assert qa["summary"]["handoff_allowed"] is True
    sign_status, signoff = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "server-test"})
    assert sign_status == 200
    assert signoff["summary"]["status"] == "signed"
    return project_id
