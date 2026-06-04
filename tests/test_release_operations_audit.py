from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.projectio import read_json, write_json
from song_agent.release_operations import ReleaseOperationsStore, operations_report_integrity_hash
from song_agent.release_operations_audit import ReleaseOperationsAuditStore, audit_ledger_integrity_ok, audit_report_integrity_ok
from song_agent.release_operations_audit_verifier import verify_release_operations_audit_package
from song_agent.release_operations_archive_verifier import verify_release_operations_archive_package, write_release_operations_archive_verification_report
from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore, runbook_integrity_hash
from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore, operations_change_request_integrity_ok
from song_agent.releases import ReleaseStore


def _accepted_operations_fixture(tmp_path: Path, monkeypatch=None, *, verify_archive: bool = True):
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Audit Accepted", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    report = operations_store.refresh(release.release_id)
    report["current_stage"] = "accepted"
    report["next_stage"] = "archived"
    report["summary"]["blocker_count"] = 0
    report["summary"]["warning_count"] = 0
    report["blockers"] = []
    report["warnings"] = []
    report["domains"] = {"submission_evidence": {"required": False, "status": "not_required", "summary": {}}}
    report["verifier_summaries"] = {"release": {"status": "passed"}}
    report["package_summaries"] = {
        "release_zip": {"exists": True, "status": "exists", "sha256": "0" * 64},
        "distribution_packages": [],
        "submission_packages": [],
        "submission_evidence_packages": [],
    }
    report["source_hash"] = "audit-source"
    report["source"] = {"fixture": "accepted"}
    report["integrity_hash"] = operations_report_integrity_hash(report)
    write_json(operations_store.report_path(release.release_id), report)
    if monkeypatch is not None:
        monkeypatch.setattr(operations_store, "build_report", lambda release_id, persist=False, now=None: report)
        monkeypatch.setattr(operations_store, "refresh", lambda release_id, now=None: report)
    runbook = runbook_store.create_from_operations_report(release.release_id)
    runbook["status"] = "completed"
    runbook["items"] = []
    runbook["summary"] = {
        "total_count": 0,
        "safe_count": 0,
        "manual_count": 0,
        "completed_count": 0,
        "failed_count": 0,
        "blocked_count": 0,
        "manual_required_count": 0,
        "waived_count": 0,
        "pending_count": 0,
    }
    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    write_json(runbook_store.runbook_path(release.release_id, runbook["runbook_id"]), runbook)
    signoff_store.signoff(release.release_id, {"signed_by": "tester"})
    signoff_store.export_archive(release.release_id)
    signoff_store.build_archive_zip(release.release_id)
    if verify_archive:
        archive_report = verify_release_operations_archive_package(signoff_store.archive_zip_path(release.release_id), require_signed=True)
        write_release_operations_archive_verification_report(archive_report, signoff_store.operations_dir(release.release_id) / "operations-archive-verification-report.json")
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    return release_store, release, operations_store, runbook_store, signoff_store, audit_store


def test_operations_audit_refresh_export_zip_verify(tmp_path: Path, monkeypatch) -> None:
    _release_store, release, _operations_store, _runbook_store, _signoff_store, audit_store = _accepted_operations_fixture(tmp_path, monkeypatch)

    report = audit_store.refresh(release.release_id)
    entries = audit_store.read_ledger(release.release_id)
    manifest = audit_store.export_audit(release.release_id)
    zip_info = audit_store.build_zip(release.release_id)
    verify = verify_release_operations_audit_package(audit_store.zip_path(release.release_id), require_current=True, require_signed=True, require_archive=True)

    assert report["status"] == "passed"
    assert audit_report_integrity_ok(report)
    assert audit_ledger_integrity_ok(entries)
    assert any(item["event_type"] == "operations_signoff_signed" for item in entries)
    assert any(item["event_type"] == "operations_archive_exported" for item in entries)
    assert manifest["audit_report"]["ledger_hash"] == report["ledger_hash"]
    assert zip_info["sha256"]
    assert verify["status"] == "passed"


def test_operations_audit_requires_verified_archive_evidence(tmp_path: Path, monkeypatch) -> None:
    _release_store, release, _operations_store, _runbook_store, _signoff_store, audit_store = _accepted_operations_fixture(tmp_path, monkeypatch, verify_archive=False)

    report = audit_store.refresh(release.release_id)
    audit_store.export_audit(release.release_id)
    audit_store.build_zip(release.release_id)
    verify = verify_release_operations_audit_package(audit_store.zip_path(release.release_id), require_current=True, require_archive=True)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "operations_archive_verifier_missing" for item in report["blockers"])
    assert verify["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_require_archive" for item in verify["blockers"])


def test_operations_audit_tracks_change_request_reset_causality(tmp_path: Path, monkeypatch) -> None:
    _release_store, release, _operations_store, _runbook_store, signoff_store, audit_store = _accepted_operations_fixture(tmp_path, monkeypatch)
    change = signoff_store.create_change_request(release.release_id, {"reason": "Approved audit reset", "scope": ["operations"], "created_by": "tester"})
    approved = signoff_store.update_change_request_status(release.release_id, change["change_request_id"], "approve", {"approved_by": "reviewer"})
    reset = signoff_store.reset_signoff(release.release_id, {"reason": "Approved audit reset", "change_request_id": approved["change_request_id"]})
    applied = signoff_store.get_change_request(release.release_id, approved["change_request_id"])

    report = audit_store.refresh(release.release_id)
    entries = audit_store.read_ledger(release.release_id)
    reset_entries = [item for item in entries if item["event_type"] == "operations_signoff_reset"]

    assert report["status"] == "passed"
    assert reset_entries
    assert reset_entries[-1]["causal_refs"][0]["id"] == approved["change_request_id"]
    assert reset_entries[-1]["causal_refs"][0]["entry_id"]
    assert applied["status"] == "applied"
    assert applied["applied_signoff_reset_hash"] == reset["payload_hash"]
    assert operations_change_request_integrity_ok(applied)


def test_operations_audit_verifier_checks_history_reset_after_resign(tmp_path: Path, monkeypatch) -> None:
    _release_store, release, _operations_store, _runbook_store, signoff_store, audit_store = _accepted_operations_fixture(tmp_path, monkeypatch)
    change = signoff_store.create_change_request(release.release_id, {"reason": "Approved audit reset", "scope": ["operations"], "created_by": "tester"})
    approved = signoff_store.update_change_request_status(release.release_id, change["change_request_id"], "approve", {"approved_by": "reviewer"})
    reset = signoff_store.reset_signoff(release.release_id, {"reason": "Approved audit reset", "change_request_id": approved["change_request_id"]})
    signoff_store.signoff(release.release_id, {"signed_by": "tester-again"})
    applied = signoff_store.get_change_request(release.release_id, approved["change_request_id"])

    audit_store.refresh(release.release_id)
    entries = audit_store.read_ledger(release.release_id)
    audit_store.export_audit(release.release_id)
    audit_store.build_zip(release.release_id)
    source_zip = audit_store.zip_path(release.release_id)
    history_reset = [item for item in entries if item["event_type"] == "operations_signoff_history_reset"]
    release_reset = [item for item in entries if item["event_type"] == "release_event_operations_signoff_reset"]

    assert history_reset
    assert release_reset
    assert history_reset[-1]["evidence_ref"]["payload_hash"] == reset["payload_hash"]
    assert release_reset[-1]["evidence_ref"]["payload_hash"] == reset["payload_hash"]
    assert applied["applied_signoff_reset_hash"] == reset["payload_hash"]
    assert verify_release_operations_audit_package(source_zip, require_current=True, require_archive=True)["status"] == "passed"

    tampered_zip = tmp_path / "history-cr-mismatch-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "change-request-ledger.json":
                payload = json.loads(data.decode("utf-8"))
                payload["change_requests"][0]["applied_signoff_reset_hash"] = "f" * 64
                payload["change_requests"][0]["integrity_hash"] = "0" * 64
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    tampered = verify_release_operations_audit_package(tampered_zip, require_current=True, require_archive=True)

    assert tampered["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_change_request_reset_causality" for item in tampered["blockers"])


def test_operations_audit_verifier_catches_tamper_missing_reorder_and_redaction(tmp_path: Path, monkeypatch) -> None:
    _release_store, release, _operations_store, _runbook_store, _signoff_store, audit_store = _accepted_operations_fixture(tmp_path, monkeypatch)
    audit_store.refresh(release.release_id)
    audit_store.export_audit(release.release_id)
    audit_store.build_zip(release.release_id)
    source_zip = audit_store.zip_path(release.release_id)

    tampered_zip = tmp_path / "tampered-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-audit-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["entry_count"] = 1
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    missing_zip = tmp_path / "missing-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(missing_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename != "operations-audit-ledger.jsonl":
                dst.writestr(info.filename, src.read(info.filename))

    reorder_zip = tmp_path / "reorder-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(reorder_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-audit-ledger.jsonl":
                lines = data.decode("utf-8").splitlines()
                data = ("\n".join(reversed(lines)) + "\n").encode("utf-8")
            dst.writestr(info.filename, data)

    redaction_zip = tmp_path / "redaction-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "README.txt":
                data += b"\nC:\\Users\\demo\\githubkey.txt api_key=sk-secret-value\n"
            dst.writestr(info.filename, data)

    tampered = verify_release_operations_audit_package(tampered_zip)
    missing = verify_release_operations_audit_package(missing_zip)
    reordered = verify_release_operations_audit_package(reorder_zip)
    redaction = verify_release_operations_audit_package(redaction_zip)

    assert tampered["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_report_integrity" for item in tampered["blockers"])
    assert missing["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_zip_required_entries" for item in missing["blockers"])
    assert reordered["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_ledger_chain" for item in reordered["blockers"])
    assert redaction["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_redaction_scan" for item in redaction["blockers"])


def test_operations_audit_verifier_catches_zip_path_duplicate_and_spoof(tmp_path: Path, monkeypatch) -> None:
    _release_store, release, _operations_store, _runbook_store, _signoff_store, audit_store = _accepted_operations_fixture(tmp_path, monkeypatch)
    audit_store.refresh(release.release_id)
    audit_store.export_audit(release.release_id)
    audit_store.build_zip(release.release_id)
    source_zip = audit_store.zip_path(release.release_id)

    dangerous_zip = tmp_path / "dangerous-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../outside.txt", b"x")

    duplicate_zip = tmp_path / "duplicate-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    backslash_zip = tmp_path / "backslash-audit.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoofed_zip = tmp_path / "spoofed-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoofed_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-audit-manifest.json":
                manifest = json.loads(data.decode("utf-8"))
                manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    dangerous = verify_release_operations_audit_package(dangerous_zip, strict=True)
    duplicate = verify_release_operations_audit_package(duplicate_zip, strict=True)
    backslash = verify_release_operations_audit_package(backslash_zip, strict=True)
    spoofed = verify_release_operations_audit_package(spoofed_zip, strict=True)

    assert dangerous["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_zip_entry_path_safe" for item in dangerous["blockers"])
    assert duplicate["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_zip_duplicate_entries" for item in duplicate["blockers"])
    assert backslash["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_zip_entry_path_safe" for item in backslash["blockers"])
    assert spoofed["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "operations_audit_manifest_zip_entries_reference_only" for item in spoofed["warnings"])


def test_operations_audit_verifier_catches_change_request_reset_mismatch(tmp_path: Path, monkeypatch) -> None:
    _release_store, release, _operations_store, _runbook_store, signoff_store, audit_store = _accepted_operations_fixture(tmp_path, monkeypatch)
    change = signoff_store.create_change_request(release.release_id, {"reason": "Approved audit reset", "scope": ["operations"], "created_by": "tester"})
    approved = signoff_store.update_change_request_status(release.release_id, change["change_request_id"], "approve", {"approved_by": "reviewer"})
    signoff_store.reset_signoff(release.release_id, {"reason": "Approved audit reset", "change_request_id": approved["change_request_id"]})
    audit_store.refresh(release.release_id)
    audit_store.export_audit(release.release_id)
    audit_store.build_zip(release.release_id)
    source_zip = audit_store.zip_path(release.release_id)

    tampered_zip = tmp_path / "cr-mismatch-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "change-request-ledger.json":
                payload = json.loads(data.decode("utf-8"))
                payload["change_requests"][0]["applied_signoff_reset_hash"] = "f" * 64
                payload["change_requests"][0]["integrity_hash"] = "0" * 64
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    report = verify_release_operations_audit_package(tampered_zip)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_change_request_reset_causality" for item in report["blockers"])
