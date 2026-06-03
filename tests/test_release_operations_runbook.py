from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.release_operations import ReleaseOperationsStore
from song_agent.release_operations_runbook import (
    ReleaseOperationsRunbookStateError,
    ReleaseOperationsRunbookStore,
)
from song_agent.release_operations_runbook_verifier import verify_release_operations_runbook_package
from song_agent.releases import ReleaseStore


def _store(tmp_path: Path) -> tuple[ReleaseStore, ReleaseOperationsRunbookStore]:
    release_store = ReleaseStore(tmp_path / "releases")
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    return release_store, runbook_store


def _make_release_runbook(tmp_path: Path) -> tuple[ReleaseStore, ReleaseOperationsRunbookStore, str, dict]:
    release_store, runbook_store = _store(tmp_path)
    release = release_store.create_release({"name": "Runbook Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
    runbook = runbook_store.create_from_operations_report(release.release_id)
    return release_store, runbook_store, release.release_id, runbook


def _zip_copy_with_mutation(source: Path, target: Path, mutator) -> Path:
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            name, data = mutator(info.filename, data)
            dst.writestr(name, data)
    return target


def test_release_operations_runbook_marks_manual_actions_blocked(tmp_path: Path) -> None:
    _release_store, runbook_store, release_id, runbook = _make_release_runbook(tmp_path)

    assert runbook["status"] == "ready"
    assert runbook["summary"]["manual_required_count"] >= 1
    assert runbook["summary"]["safe_count"] >= 1
    assert any(item["action_type"] == "release.add_track" and item["risk"] == "manual_required" for item in runbook["items"])

    rerun = runbook_store.run_safe_actions(release_id, runbook["runbook_id"])

    assert rerun["status"] == "failed"
    assert rerun["summary"]["failed_count"] >= 1
    assert rerun["summary"]["manual_required_count"] >= 1
    assert all(item["status"] != "completed" for item in rerun["items"] if item["risk"] == "manual_required")


def test_release_operations_runbook_stale_blocks_safe_run(tmp_path: Path) -> None:
    release_store, runbook_store, release_id, runbook = _make_release_runbook(tmp_path)
    release_store.update_release(release_id, {"name": "Runbook Release Changed"})

    with pytest.raises(ReleaseOperationsRunbookStateError):
        runbook_store.run_safe_actions(release_id, runbook["runbook_id"])

    stale = runbook_store.get_runbook(release_id, runbook["runbook_id"])
    assert stale["status"] == "stale"
    assert all(item["status"] in {"manual_required", "stale"} for item in stale["items"])


def test_release_operations_runbook_package_verifies_and_catches_tamper(tmp_path: Path) -> None:
    _release_store, runbook_store, release_id, runbook = _make_release_runbook(tmp_path)
    runbook_store.export_runbook(release_id, runbook["runbook_id"])
    runbook_store.build_zip(release_id, runbook["runbook_id"])
    source_zip = runbook_store.zip_path(release_id, runbook["runbook_id"])

    passed = verify_release_operations_runbook_package(source_zip, require_current=True)

    assert passed["status"] == "passed"

    tampered_zip = tmp_path / "runbook-tampered.zip"

    def tamper(name: str, data: bytes) -> tuple[str, bytes]:
        if name == "runbook.json":
            payload = json.loads(data.decode("utf-8"))
            payload["summary"]["manual_required_count"] = 0
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return name, data

    _zip_copy_with_mutation(source_zip, tampered_zip, tamper)
    tampered = verify_release_operations_runbook_package(tampered_zip)

    assert tampered["status"] == "failed"
    assert any(item["check_id"] == "runbook_integrity" for item in tampered["blockers"])


def test_release_operations_runbook_verifier_catches_zip_path_spoof_and_redaction(tmp_path: Path) -> None:
    _release_store, runbook_store, release_id, runbook = _make_release_runbook(tmp_path)
    runbook_store.export_runbook(release_id, runbook["runbook_id"])
    runbook_store.build_zip(release_id, runbook["runbook_id"])
    source_zip = runbook_store.zip_path(release_id, runbook["runbook_id"])

    dangerous_zip = tmp_path / "dangerous.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../outside.txt", b"x")

    backslash_zip = tmp_path / "backslash.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoofed_zip = tmp_path / "spoofed.zip"

    def spoof(name: str, data: bytes) -> tuple[str, bytes]:
        if name == "runbook-manifest.json":
            manifest = json.loads(data.decode("utf-8"))
            manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
            data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        return name, data

    _zip_copy_with_mutation(source_zip, spoofed_zip, spoof)
    with zipfile.ZipFile(spoofed_zip, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra.txt", b"x")

    redacted_zip = tmp_path / "redaction.zip"

    def redact(name: str, data: bytes) -> tuple[str, bytes]:
        if name == "README.txt":
            data += b"\nC:\\Users\\demo\\secret.txt api_key=sk-secret-value\n"
        return name, data

    _zip_copy_with_mutation(source_zip, redacted_zip, redact)

    dangerous = verify_release_operations_runbook_package(dangerous_zip, strict=True)
    backslash = verify_release_operations_runbook_package(backslash_zip, strict=True)
    spoofed = verify_release_operations_runbook_package(spoofed_zip, strict=True)
    redaction = verify_release_operations_runbook_package(redacted_zip)

    assert dangerous["status"] == "failed"
    assert any(item["check_id"] == "runbook_zip_entry_path_safe" for item in dangerous["blockers"])
    assert backslash["status"] == "failed"
    assert any(item["check_id"] == "runbook_zip_entry_path_safe" for item in backslash["blockers"])
    assert spoofed["status"] == "failed"
    assert any(item["check_id"] == "runbook_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "runbook_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert redaction["status"] == "failed"
    assert any(item["check_id"] == "runbook_redaction_scan" for item in redaction["blockers"])
