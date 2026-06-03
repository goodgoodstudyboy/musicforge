from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.release_operations import ReleaseOperationsStore, operations_report_integrity_ok
from song_agent.release_operations_verifier import verify_release_operations_package
from song_agent.releases import ReleaseStore


def test_release_operations_empty_release_exports_and_verifies(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Empty", "release_type": "single_pack", "primary_artist": "MusicForge"})
    store = ReleaseOperationsStore(release_store=release_store)

    report = store.refresh(release.release_id)
    manifest = store.export_operations(release.release_id)
    zip_info = store.build_zip(release.release_id)
    verify = verify_release_operations_package(store.zip_path(release.release_id))

    assert report["current_stage"] == "draft"
    assert report["next_stage"] == "project_ready"
    assert report["summary"]["blocker_count"] >= 1
    assert operations_report_integrity_ok(report)
    assert manifest["report"]["integrity_hash"] == report["integrity_hash"]
    assert zip_info["entry_count"] >= 6
    assert verify["status"] == "passed"


def test_release_operations_source_hash_marks_stale(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Stale", "release_type": "single_pack", "primary_artist": "MusicForge"})
    store = ReleaseOperationsStore(release_store=release_store)
    report = store.refresh(release.release_id)

    release_store.update_release(release.release_id, {"name": "Ops Stale Changed"})

    assert store.report_is_stale(release.release_id, report)
    overview = store.overview(release.release_id)
    assert overview["stale"] is True


def test_release_operations_verifier_catches_report_tamper_and_redaction(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Tamper", "release_type": "single_pack", "primary_artist": "MusicForge"})
    store = ReleaseOperationsStore(release_store=release_store)
    store.refresh(release.release_id)
    store.export_operations(release.release_id)
    store.build_zip(release.release_id)
    source_zip = store.zip_path(release.release_id)

    tampered_zip = tmp_path / "tampered.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["blocker_count"] = 0
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    redacted_zip = tmp_path / "redaction.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redacted_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "README.txt":
                data += b"\nC:\\Users\\demo\\secret.txt api_key=sk-secret-value\n"
            dst.writestr(info.filename, data)

    tampered = verify_release_operations_package(tampered_zip)
    redaction = verify_release_operations_package(redacted_zip)

    assert tampered["status"] == "failed"
    assert any(item["check_id"] == "operations_report_integrity" for item in tampered["blockers"])
    assert redaction["status"] == "failed"
    assert any(item["check_id"] == "operations_redaction_scan" for item in redaction["blockers"])


def test_release_operations_verifier_catches_zip_path_and_spoofed_entries(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Zip Guard", "release_type": "single_pack", "primary_artist": "MusicForge"})
    store = ReleaseOperationsStore(release_store=release_store)
    store.refresh(release.release_id)
    store.export_operations(release.release_id)
    store.build_zip(release.release_id)
    source_zip = store.zip_path(release.release_id)

    dangerous_zip = tmp_path / "dangerous.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info))
        dst.writestr("../outside.txt", b"x")

    backslash_zip = tmp_path / "backslash.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoofed_zip = tmp_path / "spoofed.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoofed_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info)
            if info.filename == "operations-manifest.json":
                manifest = json.loads(data.decode("utf-8"))
                manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    dangerous = verify_release_operations_package(dangerous_zip, strict=True)
    backslash = verify_release_operations_package(backslash_zip, strict=True)
    spoofed = verify_release_operations_package(spoofed_zip, strict=True)

    assert dangerous["status"] == "failed"
    assert any(item["check_id"] == "zip_entry_path_safe" for item in dangerous["blockers"])
    assert backslash["status"] == "failed"
    assert any(item["check_id"] == "zip_entry_path_safe" for item in backslash["blockers"])
    assert spoofed["status"] == "failed"
    assert any(item["check_id"] == "operations_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "operations_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
