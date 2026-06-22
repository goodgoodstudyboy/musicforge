from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.releases import stable_hash
from song_agent.trust_operations_assurance_watch import (
    TrustOperationsAssuranceWatchStateError,
    TrustOperationsAssuranceWatchStore,
    watch_hash,
    watch_manifest_hash,
)
from song_agent.trust_operations_assurance_watch_verifier import verify_trust_operations_assurance_watch_package
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from tests.test_trust_operations_continuous_assurance import _assurance_fixture, _doc_bytes, _read_doc, _rewrite_zip, _sync_manifest_file
from tests.test_trust_operations_hub import _has_blocker


def test_trust_operations_assurance_watch_lifecycle_and_hub_gate(tmp_path: Path) -> None:
    fixture, assurance_store, run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)

    manifest = watch_store.export_watch(queue_id)
    zip_info = watch_store.build_watch_zip(queue_id)
    verification = watch_store.verify_watch_zip(queue_id, {"strict": True, "require_clear": True, "require_current": True, **payload})
    missing_gate = verify_trust_operations_hub_package(
        fixture.hub_zip,
        strict=True,
        require_assurance_watch_clear=True,
        hub_verification_report_path=fixture.hub_verification,
        **fixture.base_hub_verify_payload,
    )
    hub_gate = verify_trust_operations_hub_package(
        fixture.hub_zip,
        strict=True,
        require_assurance_watch_clear=True,
        assurance_watch_package_path=watch_store.watch_zip_path(queue_id),
        assurance_watch_verification_report_path=watch_store.verification_report_path(queue_id),
        hub_verification_report_path=fixture.hub_verification,
        **fixture.base_hub_verify_payload,
    )

    assert assurance_store.read_run(run_id)["status"] == "passed"
    assert watch_store.read_queue(queue_id)["status"] == "clear"
    assert manifest["package_type"] == "musicforge_trust_operations_assurance_watch_manifest"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert _has_blocker(missing_gate, "toh_assurance_watch_package_required")
    assert hub_gate["status"] == "passed", hub_gate.get("blockers")


def test_assurance_watch_verifier_rejects_clear_queue_full_resign(tmp_path: Path) -> None:
    fixture, assurance_store, run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path, failed_assurance_report=True)
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)

    forged = verify_trust_operations_assurance_watch_package(
        _rewrite_zip(watch_store.watch_zip_path(queue_id), tmp_path / "watch-clear-full-resign.zip", _clear_watch_queue_full_resign),
        strict=True,
        require_clear=True,
        require_current=True,
        **_watch_verifier_payload(payload),
    )

    assert assurance_store.read_run(run_id)["status"] == "passed"
    assert watch_store.read_queue(queue_id)["status"] == "blocked"
    assert _has_blocker(forged, "toaw_watch_queue_rows_match_sources")
    assert _has_blocker(forged, "toaw_action_pack_semantics_match")


def test_assurance_watch_export_rejects_stale_source(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    report_path = Path(payload["assurance_verification_report_path"])
    report = read_json(report_path)
    report["status"] = "failed"
    write_json(report_path, report)

    with pytest.raises(TrustOperationsAssuranceWatchStateError):
        watch_store.export_watch(queue_id)


def test_assurance_watch_export_rejects_overdue_queue(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, _payload, queue_id = _watch_fixture(tmp_path)

    with pytest.raises(TrustOperationsAssuranceWatchStateError):
        watch_store.export_watch(queue_id, now="2099-01-01T00:00:00+00:00")


def test_assurance_watch_verifier_rejects_zip_edges(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)
    source_zip = watch_store.watch_zip_path(queue_id)

    extra = verify_trust_operations_assurance_watch_package(_rewrite_zip(source_zip, tmp_path / "extra.zip", lambda docs: docs.update({"docs/extra.txt": b"x"})), strict=True)
    duplicate = verify_trust_operations_assurance_watch_package(_duplicate_watch_zip(source_zip, tmp_path / "duplicate.zip"), strict=True)
    backslash = verify_trust_operations_assurance_watch_package(_backslash_watch_zip(tmp_path / "backslash.zip"), strict=True)
    redaction = verify_trust_operations_assurance_watch_package(
        _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b'\napi_key="sk-test-secret" C:\\Users\\demo\\githubkey.txt\n')),
        strict=True,
    )
    missing_current = verify_trust_operations_assurance_watch_package(source_zip, strict=True, require_current=True)

    assert _has_blocker(extra, "toaw_zip_allowed_entries")
    assert _has_blocker(duplicate, "toaw_zip_duplicate_entries")
    assert _has_blocker(backslash, "toaw_zip_entry_path_safe")
    assert _has_blocker(redaction, "toaw_redaction_scan")
    assert _has_blocker(missing_current, "toaw_assurance_archive_required")


def _watch_fixture(tmp_path: Path, *, failed_assurance_report: bool = False):
    fixture = _assurance_fixture(tmp_path)
    assurance_store = fixture.assurance_store
    run_id = assurance_store.refresh_run("hub", fixture.payload)["run"]["run_id"]
    assurance_store.export_archive(run_id)
    assurance_store.build_archive_zip(run_id)
    assurance_store.verify_archive_zip(run_id, {**fixture.assurance_verifier_payload, "strict": True, "require_passed": True, "require_current": True})
    report_path = assurance_store.verification_report_path(run_id)
    if failed_assurance_report:
        report = read_json(report_path)
        report["status"] = "failed"
        report_path = write_json(tmp_path / "failed-assurance-verification-report.json", report)
    payload = {
        "hub_id": "hub",
        "assurance_archive_path": assurance_store.archive_zip_path(run_id),
        "assurance_verification_report_path": report_path,
        "hub_package_path": fixture.hub_zip,
        "hub_verification_report_path": fixture.hub_verification,
    }
    watch_store = TrustOperationsAssuranceWatchStore(tmp_path / ".musicforge" / "trust-operations-assurance-watch", assurance_store=assurance_store, hub_store=assurance_store.hub_store)
    refreshed = watch_store.refresh_queue(payload)
    return fixture, assurance_store, run_id, watch_store, payload, refreshed["queue"]["queue_id"]


def _watch_verifier_payload(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if key != "hub_id"}


def _clear_watch_queue_full_resign(docs: dict[str, bytes]) -> None:
    queue = _read_doc(docs, "watch-queue.json")
    action_pack = _read_doc(docs, "drift-action-pack.json")
    manifest = _read_doc(docs, "trust-operations-assurance-watch-manifest.json")

    for row in queue.get("rows", []):
        row["latest_assurance_verified"] = True
        row["due_status"] = "not_due"
        row["drift_status"] = "clear"
        row["readiness"] = "clear"
        row["reasons"] = []
        row["action_ids"] = []
        row["integrity_hash"] = watch_hash(row)
    action_pack["actions"] = []
    action_pack["summary"] = {"action_count": 0, "blocking_count": 0, "manual_required_count": 0, "safe_auto_count": 0}
    action_pack["status"] = "clear"
    action_pack["integrity_hash"] = watch_hash(action_pack)
    queue["summary"] = {
        "hub_count": len(queue.get("rows", [])),
        "clear_count": len(queue.get("rows", [])),
        "due_count": 0,
        "overdue_count": 0,
        "stale_count": 0,
        "failed_count": 0,
        "blocking_action_count": 0,
        "manual_action_count": 0,
    }
    queue["status"] = "clear"
    queue["readiness"] = "clear"
    queue.setdefault("source", {})["drift_action_pack_hash"] = action_pack["integrity_hash"]
    queue["source_hash"] = stable_hash(queue["source"])
    queue["integrity_hash"] = watch_hash(queue)

    docs["drift-action-pack.json"] = _doc_bytes(action_pack)
    docs["watch-queue.json"] = _doc_bytes(queue)
    manifest["status"] = queue["status"]
    manifest["source_hash"] = queue["source_hash"]
    manifest.setdefault("source", {})["watch_queue_hash"] = queue["integrity_hash"]
    manifest.setdefault("source", {})["drift_action_pack_hash"] = action_pack["integrity_hash"]
    _sync_manifest_file(manifest, "watch-queue.json", docs["watch-queue.json"])
    _sync_manifest_file(manifest, "drift-action-pack.json", docs["drift-action-pack.json"])
    manifest["integrity_hash"] = watch_manifest_hash(manifest)
    docs["trust-operations-assurance-watch-manifest.json"] = _doc_bytes(manifest)


def _duplicate_watch_zip(source_zip: Path, target_zip: Path) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("watch-queue.json", src.read("watch-queue.json"))
    return target_zip


def _backslash_watch_zip(target_zip: Path) -> Path:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    data = target_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt")
    target_zip.write_bytes(data)
    return target_zip
