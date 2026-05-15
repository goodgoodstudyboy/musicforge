from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.auth import AuthConfig
from song_agent.projectio import read_json
from song_agent.server import create_server
from tests.test_server_auth import TOKEN, request_json as auth_request_json, start_test_server as start_auth_server, stop_test_server as stop_auth_server
from tests.test_server_edits import request_json, start_test_server, stop_test_server, wait_for_job, request_payload


def test_delivery_qa_api_signoff_reset_and_exports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _final_project_with_export(server)
        missing_zip_status, missing_zip = request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        sign_block_status, sign_block = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {})
        force_missing_status, force_missing = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"force": True})
        force_status, forced = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"force": True, "override_reason": r"manual accepted C:\Users\demo api_key=sk-secret-value"})
        reset_missing_status, reset_missing = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {})
        reset_status, reset = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff/reset", {"reason": r"rebuilt zip C:\Users\demo"})
        zip_status, zipped = request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        qa_status, qa = request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        sign_status, signed = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"notes": "accepted for handoff"})
        duplicate_status, duplicate = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {})
        signoff_get_status, signoff_get = request_json(server, "GET", f"/api/projects/{project_id}/delivery-signoff")
        export_status, project_export = request_json(server, "GET", f"/api/projects/{project_id}/export")
        final_export_status, final_export = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
        history_path = Path(".musicforge") / "projects" / project_id / "delivery-signoff-history.jsonl"
        serialized = json.dumps({"forced": forced, "reset": reset, "signed": signed, "export": project_export, "final": final_export}, ensure_ascii=False)
    finally:
        stop_test_server(server)

    assert missing_zip_status == 200
    assert missing_zip["summary"]["handoff_allowed"] is False
    assert missing_zip["summary"]["readiness"] == "needs_zip"
    assert sign_block_status == 409
    assert "Delivery QA gate failed" in sign_block["error"]
    assert force_missing_status == 400
    assert "override_reason" in force_missing["error"]
    assert force_status == 200
    assert forced["summary"]["status"] == "force_signed"
    assert reset_missing_status == 400
    assert "reason" in reset_missing["error"]
    assert reset_status == 200
    assert reset["summary"]["status"] == "reset"
    assert history_path.exists()
    assert zip_status == 200
    assert zipped["zip"]["sha256"]
    assert qa_status == 200
    assert qa["summary"]["handoff_allowed"] is True
    assert qa["delivery_qa"]["zip"]["matches_manifest"] is True
    assert sign_status == 200
    assert signed["summary"]["status"] == "signed"
    assert duplicate_status == 409
    assert "already signed off" in duplicate["error"]
    assert signoff_get_status == 200
    assert signoff_get["summary"]["status"] == "signed"
    assert export_status == 200
    assert project_export["delivery_qa_summary"]["status"] in {"passed", "warning"}
    assert project_export["delivery_signoff_summary"]["status"] == "signed"
    assert final_export_status == 200
    assert final_export["final_export"]["delivery_qa"]["status"] in {"passed", "warning"}
    assert final_export["final_export"]["delivery_signoff"]["status"] == "signed"
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_delivery_qa_get_marks_stale_after_zip_changes_and_blocks_normal_sign(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _final_project_with_export(server)
        request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        refresh_status, refreshed = request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        with zipfile.ZipFile(Path(".musicforge") / "projects" / project_id / "final-export.zip", "a") as archive:
            archive.writestr("extra.txt", "extra")
        get_status, stale = request_json(server, "GET", f"/api/projects/{project_id}/delivery-qa")
        sign_status, sign_error = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {})
    finally:
        stop_test_server(server)

    assert refresh_status == 200
    assert refreshed["summary"]["handoff_allowed"] is True
    assert get_status == 200
    assert stale["delivery_qa"]["status"] == "stale"
    assert stale["summary"]["handoff_allowed"] is False
    assert sign_status == 409
    assert "Delivery QA gate failed" in sign_error["error"]


def test_delivery_qa_blocks_signoff_when_manifest_hides_missing_core_artifact(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        project_id = _final_project_with_export(server)
        project_dir = Path(".musicforge") / "projects" / project_id
        request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
        manifest_path = project_dir / "final-export" / "manifest.json"
        manifest = read_json(manifest_path)
        (project_dir / "final-export" / "song.mid").unlink()
        manifest["files"] = [file for file in manifest["files"] if file.get("path") != "song.mid"]
        from song_agent.final_export import build_final_export_zip
        from song_agent.projectio import write_json

        write_json(manifest_path, manifest)
        build_final_export_zip(project_dir, now="2026-05-15T00:02:00+00:00")
        qa_status, qa = request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
        sign_status, sign_error = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {})
    finally:
        stop_test_server(server)

    required = next(check for check in qa["delivery_qa"]["checks"] if check["check_id"] == "required_artifacts_exist")
    assert qa_status == 200
    assert qa["summary"]["handoff_allowed"] is False
    assert required["status"] == "failed"
    assert sign_status == 409
    assert "Delivery QA gate failed" in sign_error["error"]


def test_delivery_qa_auth_protected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    server = start_auth_server(AuthConfig(enabled=True, token=TOKEN))
    try:
        protected = [
            ("GET", "/api/projects/auth-project/delivery-qa", None),
            ("POST", "/api/projects/auth-project/delivery-qa/refresh", None),
            ("GET", "/api/projects/auth-project/delivery-signoff", None),
            ("POST", "/api/projects/auth-project/delivery-signoff", {}),
            ("POST", "/api/projects/auth-project/delivery-signoff/reset", {"reason": "x"}),
        ]
        statuses = [auth_request_json(server, method, path, payload)[0] for method, path, payload in protected]
    finally:
        stop_auth_server(server)

    assert statuses == [401, 401, 401, 401, 401]


def _final_project_with_export(server) -> str:
    _status, created = request_json(server, "POST", "/api/projects", {"name": "Delivery QA Project"})
    project_id = created["project"]["project_id"]
    first_status, first = request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload("Delivery QA Version"), "name": "Delivery QA Version"})
    assert first_status == 202
    wait_for_job(server, first["job"]["job_id"])
    final_status, final = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
    assert final_status == 200
    export_status, exported = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
    assert export_status == 200
    assert read_json(Path(".musicforge") / "projects" / project_id / "final-export" / "manifest.json")["version_id"] == final["project"]["final_version_id"]
    assert exported["final_export"]["version_id"] == "v001"
    return project_id
