from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from song_agent.release_verifier import verify_release_zip, write_verification_report
from song_agent.releases import stable_hash
from tests.test_server_edits import request_json, request_payload, start_test_server, stop_test_server, wait_for_job


def test_verify_release_zip_valid_portable_sidecar_and_report_out(tmp_path, monkeypatch):
    zip_path = _build_release_zip(tmp_path, monkeypatch)
    external = tmp_path / "external"
    external.mkdir()
    copied_zip = external / "release-export.zip"
    shutil.copy2(zip_path, copied_zip)
    report_path = external / "release-verification-report.json"

    monkeypatch.chdir(external)
    report = verify_release_zip(copied_zip)
    write_verification_report(report, report_path)
    saved = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["status"] == "passed"
    assert report["summary"]["track_count"] == 2
    assert report["summary"]["blocker_count"] == 0
    assert saved["status"] == "passed"
    assert _check(report, "manifest_extra_entries")["status"] == "passed"
    with zipfile.ZipFile(copied_zip) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        signoff = json.loads(archive.read("release-signoff.json").decode("utf-8"))
    assert "release-signoff.json" not in {item["path"] for item in manifest["files"]}
    assert manifest["sidecars"]["release_signoff"]["path"] == "release-signoff.json"
    assert manifest["sidecars"]["release_signoff"]["payload_hash"]
    assert stable_hash({key: value for key, value in manifest.items() if key != "zip"}) == signoff["export_manifest_hash"]


def test_verify_release_zip_rejects_broken_zip(tmp_path):
    broken = tmp_path / "broken.zip"
    broken.write_text("not a zip", encoding="utf-8")

    report = verify_release_zip(broken)

    assert report["status"] == "failed"
    assert _check(report, "zip_open")["status"] == "failed"


def test_verify_release_zip_dangerous_duplicate_and_zip_bomb_guards(tmp_path, monkeypatch):
    zip_path = _build_release_zip(tmp_path, monkeypatch)

    dangerous = _rewrite_zip(zip_path, tmp_path / "dangerous.zip", {"../evil.txt": b"x"})
    backslash = _backslash_entry_zip(tmp_path / "backslash.zip")
    duplicate = tmp_path / "duplicate.zip"
    shutil.copy2(zip_path, duplicate)
    with zipfile.ZipFile(duplicate, "a") as archive:
        archive.writestr("README.txt", "duplicate")
    bomb = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", b"0" * (1024 * 1024 + 1))

    dangerous_report = verify_release_zip(dangerous)
    backslash_report = verify_release_zip(backslash)
    duplicate_report = verify_release_zip(duplicate)
    bomb_report = verify_release_zip(bomb, max_uncompressed_size_mb=1)

    assert dangerous_report["status"] == "failed"
    assert _check(dangerous_report, "zip_entry_path_safe")["status"] == "failed"
    assert backslash_report["status"] == "failed"
    assert _check(backslash_report, "zip_entry_path_safe")["status"] == "failed"
    assert duplicate_report["status"] == "failed"
    assert _check(duplicate_report, "zip_duplicate_entries")["status"] == "failed"
    assert bomb_report["status"] == "failed"
    assert _check(bomb_report, "zip_uncompressed_size_limit")["status"] == "failed"


def test_verify_release_zip_detects_manifest_hash_mismatch(tmp_path, monkeypatch):
    zip_path = _build_release_zip(tmp_path, monkeypatch)
    modified = _rewrite_zip(zip_path, tmp_path / "hash-mismatch.zip", {"tracks/01-release-verifier-track-one/song.mid": b"MThd\x00\x00\x00\x06\x00\x01\x00\x01\x01\xe0MTrk\x00\x00\x00\x04\x00\xff/\x00"})

    report = verify_release_zip(modified)

    assert report["status"] == "failed"
    assert _check(report, "manifest_file_hash_match")["status"] == "failed"


def test_verify_release_zip_does_not_trust_manifest_zip_entries_for_extras(tmp_path, monkeypatch):
    zip_path = _build_release_zip(tmp_path, monkeypatch)

    def mutate_manifest(data: bytes) -> bytes:
        manifest = json.loads(data.decode("utf-8"))
        manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
        return json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

    modified = _rewrite_zip(zip_path, tmp_path / "spoofed-extra.zip", {"extra.txt": b"extra"}, transforms={"manifest.json": mutate_manifest})

    report = verify_release_zip(modified)
    strict_report = verify_release_zip(modified, strict=True)

    assert report["status"] == "warning"
    assert _check(report, "manifest_extra_entries")["status"] == "warning"
    assert _check(report, "manifest_zip_entries_reference_only")["status"] == "warning"
    assert strict_report["status"] == "failed"
    assert _check(strict_report, "manifest_extra_entries")["status"] == "failed"


def test_verify_release_zip_detects_redaction_and_signoff_hash_mismatch(tmp_path, monkeypatch):
    zip_path = _build_release_zip(tmp_path, monkeypatch)

    def pollute_release(data: bytes) -> bytes:
        release = json.loads(data.decode("utf-8"))
        release["notes"] = r"C:\Users\demo\secret.zip api_key=sk-secret-value"
        return json.dumps(release, ensure_ascii=False, indent=2).encode("utf-8")

    def mutate_signoff(data: bytes) -> bytes:
        signoff = json.loads(data.decode("utf-8"))
        signoff["export_manifest_hash"] = "0" * 64
        return json.dumps(signoff, ensure_ascii=False, indent=2).encode("utf-8")

    polluted = _rewrite_zip(zip_path, tmp_path / "polluted.zip", transforms={"release.json": pollute_release})
    mismatched = _rewrite_zip(zip_path, tmp_path / "signoff-mismatch.zip", transforms={"release-signoff.json": mutate_signoff})

    polluted_report = verify_release_zip(polluted)
    mismatched_report = verify_release_zip(mismatched)

    assert polluted_report["status"] == "failed"
    assert _check(polluted_report, "redaction_scan")["status"] == "failed"
    assert mismatched_report["status"] == "failed"
    assert _check(mismatched_report, "signoff_manifest_hash")["status"] == "failed"


def test_verify_release_zip_detects_tampered_signoff_display_fields(tmp_path, monkeypatch):
    zip_path = _build_release_zip(tmp_path, monkeypatch)

    def tamper_signoff(data: bytes) -> bytes:
        signoff = json.loads(data.decode("utf-8"))
        signoff["signed_by"] = "tampered-reviewer"
        signoff["signed_at"] = "2099-01-01T00:00:00+00:00"
        return json.dumps(signoff, ensure_ascii=False, indent=2).encode("utf-8")

    tampered = _rewrite_zip(zip_path, tmp_path / "tampered-signoff.zip", transforms={"release-signoff.json": tamper_signoff})

    report = verify_release_zip(tampered)

    assert report["status"] == "failed"
    assert _check(report, "signoff_manifest_hash")["status"] == "passed"
    assert _check(report, "signoff_sidecar_payload_hash")["status"] == "failed"


def test_verify_release_zip_track_core_and_optional_requirements(tmp_path, monkeypatch):
    zip_path = _build_release_zip(tmp_path, monkeypatch)
    without_midi = _rewrite_zip(zip_path, tmp_path / "missing-midi.zip", remove={"tracks/01-release-verifier-track-one/song.mid"})

    missing_report = verify_release_zip(without_midi)
    audio_report = verify_release_zip(zip_path, require_audio=True)
    stems_report = verify_release_zip(zip_path, require_stems=True)

    assert missing_report["status"] == "failed"
    assert _track_check(missing_report, "track_core_files")["status"] == "failed"
    assert audio_report["status"] == "failed"
    assert _track_check(audio_report, "track_optional_audio")["status"] == "failed"
    assert stems_report["status"] == "failed"
    assert _track_check(stems_report, "track_optional_stems")["status"] == "failed"


def _build_release_zip(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.chdir(tmp_path)
    server = start_test_server()
    try:
        first_project = _signed_project(server, "Release Verifier Track One")
        second_project = _signed_project(server, "Release Verifier Track Two")
        created_status, created = request_json(server, "POST", "/api/releases", {"name": "Release Verifier EP", "release_type": "ep", "primary_artist": "MusicForge"})
        assert created_status == 201
        release_id = created["release"]["release_id"]
        first_status, _first = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": first_project})
        second_status, _second = request_json(server, "POST", f"/api/releases/{release_id}/tracks", {"project_id": second_project})
        qa_status, qa = request_json(server, "POST", f"/api/releases/{release_id}/qa/refresh")
        export_status, _exported = request_json(server, "POST", f"/api/releases/{release_id}/export")
        zip_status, _zipped = request_json(server, "POST", f"/api/releases/{release_id}/export/zip")
        sign_status, signed = request_json(server, "POST", f"/api/releases/{release_id}/signoff", {"signed_by": "verifier-test"})
        assert first_status == 200
        assert second_status == 200
        assert qa_status == 200
        assert qa["summary"]["status"] in {"passed", "warning"}
        assert export_status == 200
        assert zip_status == 200
        assert sign_status == 200
        assert signed["summary"]["status"] == "signed"
        return Path(".musicforge") / "releases" / release_id / "release-export.zip"
    finally:
        stop_test_server(server)


def _signed_project(server, title: str) -> str:
    created_status, created = request_json(server, "POST", "/api/projects", {"name": title})
    assert created_status == 201
    project_id = created["project"]["project_id"]
    version_status, version_data = request_json(server, "POST", f"/api/projects/{project_id}/versions", {"request": request_payload(title), "name": title})
    assert version_status == 202
    job = wait_for_job(server, version_data["job"]["job_id"])
    assert job["status"] == "completed"
    final_status, _final = request_json(server, "POST", f"/api/projects/{project_id}/final", {"version_id": "v001"})
    export_status, _exported = request_json(server, "POST", f"/api/projects/{project_id}/final-export", {"include_stems": False, "include_stem_audio": False})
    zip_status, _zipped = request_json(server, "POST", f"/api/projects/{project_id}/final-export/zip")
    qa_status, qa = request_json(server, "POST", f"/api/projects/{project_id}/delivery-qa/refresh")
    sign_status, signoff = request_json(server, "POST", f"/api/projects/{project_id}/delivery-signoff", {"signed_by": "verifier-test"})
    assert final_status == 200
    assert export_status == 200
    assert zip_status == 200
    assert qa_status == 200
    assert qa["summary"]["handoff_allowed"] is True
    assert sign_status == 200
    assert signoff["summary"]["status"] == "signed"
    return project_id


def _rewrite_zip(source: Path, target: Path, additions: dict[str, bytes] | None = None, transforms: dict[str, object] | None = None, remove: set[str] | None = None) -> Path:
    additions = additions or {}
    transforms = transforms or {}
    remove = remove or set()
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename in remove or info.filename in additions:
                continue
            data = src.read(info)
            transform = transforms.get(info.filename)
            if transform is not None:
                data = transform(data)  # type: ignore[operator]
            dst.writestr(info.filename, data)
        for name, data in additions.items():
            dst.writestr(name, data)
    return target


def _backslash_entry_zip(target: Path) -> Path:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    data = target.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt")
    target.write_bytes(data)
    return target


def _check(report: dict, check_id: str) -> dict:
    for check in report["checks"]:
        if check["check_id"] == check_id:
            return check
    raise AssertionError(f"missing check {check_id}")


def _track_check(report: dict, check_id: str) -> dict:
    for check in report["track_checks"]:
        if check["check_id"] == check_id:
            return check
    raise AssertionError(f"missing track check {check_id}")
