from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.projectio import write_json
from song_agent.release_operations import ReleaseOperationsStore, operations_report_integrity_hash
from song_agent.release_operations_audit import ReleaseOperationsAuditStore
from song_agent.release_operations_audit_verifier import verify_release_operations_audit_package, write_release_operations_audit_verification_report
from song_agent.release_operations_archive_verifier import verify_release_operations_archive_package, write_release_operations_archive_verification_report
from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore, reviewer_pack_manifest_integrity_ok, reviewer_report_integrity_ok
from song_agent.release_operations_reviewer_pack_verifier import verify_release_operations_reviewer_pack
from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore, runbook_integrity_hash
from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
from song_agent.releases import ReleaseStore


def accepted_reviewer_fixture(tmp_path: Path, monkeypatch=None, *, archive_verified: bool = True, audit_verified: bool = True):
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Reviewer Pack Release", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)

    report = operations_store.refresh(release.release_id)
    report["current_stage"] = "accepted"
    report["next_stage"] = "archived"
    report["summary"]["blocker_count"] = 0
    report["summary"]["warning_count"] = 0
    report["blockers"] = []
    report["warnings"] = []
    report["domains"] = {"submission_evidence": {"required": False, "status": "not_required", "summary": {}}}
    report["verifier_summaries"] = {"release": {"status": "passed"}}
    report["package_summaries"] = {"release_zip": {"exists": True, "status": "exists", "sha256": "0" * 64}, "distribution_packages": [], "submission_packages": [], "submission_evidence_packages": []}
    report["source_hash"] = "reviewer-pack-source"
    report["source"] = {"fixture": "accepted"}
    report["integrity_hash"] = operations_report_integrity_hash(report)
    write_json(operations_store.report_path(release.release_id), report)
    if monkeypatch is not None:
        monkeypatch.setattr(operations_store, "build_report", lambda release_id, persist=False, now=None: report)
        monkeypatch.setattr(operations_store, "refresh", lambda release_id, now=None: report)

    runbook = runbook_store.create_from_operations_report(release.release_id)
    runbook["status"] = "completed"
    runbook["items"] = []
    runbook["summary"] = {"total_count": 0, "safe_count": 0, "manual_count": 0, "completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0, "waived_count": 0, "pending_count": 0}
    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    write_json(runbook_store.runbook_path(release.release_id, runbook["runbook_id"]), runbook)

    signoff_store.signoff(release.release_id, {"signed_by": "tester"})
    signoff_store.export_archive(release.release_id)
    signoff_store.build_archive_zip(release.release_id)
    if archive_verified:
        archive_report = verify_release_operations_archive_package(signoff_store.archive_zip_path(release.release_id), require_signed=True)
        write_release_operations_archive_verification_report(archive_report, signoff_store.operations_dir(release.release_id) / "operations-archive-verification-report.json")
    audit_store.refresh(release.release_id)
    audit_store.export_audit(release.release_id)
    audit_store.build_zip(release.release_id)
    if audit_verified:
        audit_verification = verify_release_operations_audit_package(audit_store.zip_path(release.release_id), require_current=True, require_signed=True, require_archive=archive_verified)
        write_release_operations_audit_verification_report(audit_verification, audit_store.verification_report_path(release.release_id))
    return release, operations_store, runbook_store, signoff_store, audit_store, reviewer_store


def test_reviewer_pack_refresh_export_zip_and_verify(tmp_path: Path, monkeypatch) -> None:
    release, _operations_store, _runbook_store, _signoff_store, _audit_store, reviewer_store = accepted_reviewer_fixture(tmp_path, monkeypatch)

    report = reviewer_store.refresh(release.release_id)
    retrospective = reviewer_store.read_retrospective(release.release_id)
    manifest = reviewer_store.export_pack(release.release_id)
    zip_info = reviewer_store.build_zip(release.release_id)
    verification = verify_release_operations_reviewer_pack(reviewer_store.zip_path(release.release_id), strict=True, require_audit=True, require_signed=True, require_archive=True)

    assert report["status"] == "passed"
    assert reviewer_report_integrity_ok(report)
    assert retrospective["status"] in {"passed", "warning"}
    assert manifest["summary"]["status"] == "passed"
    assert reviewer_pack_manifest_integrity_ok(manifest)
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert "Reviewer Pack Release" in (reviewer_store.export_dir(release.release_id) / "REVIEWER_GUIDE.md").read_text(encoding="utf-8")


def test_reviewer_pack_requires_archive_verification(tmp_path: Path, monkeypatch) -> None:
    release, _operations_store, _runbook_store, _signoff_store, _audit_store, reviewer_store = accepted_reviewer_fixture(tmp_path, monkeypatch, archive_verified=False, audit_verified=False)

    report = reviewer_store.refresh(release.release_id)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "operations_audit_verification_missing" for item in report["blockers"])
    assert any(item["check_id"] == "operations_archive_verification_missing" for item in report["blockers"])


def test_reviewer_pack_requires_audit_package_verification(tmp_path: Path, monkeypatch) -> None:
    release, _operations_store, _runbook_store, _signoff_store, audit_store, reviewer_store = accepted_reviewer_fixture(tmp_path, monkeypatch, audit_verified=False)

    report = reviewer_store.refresh(release.release_id)
    reviewer_store.export_pack(release.release_id)
    reviewer_store.build_zip(release.release_id)
    verification = verify_release_operations_reviewer_pack(reviewer_store.zip_path(release.release_id), require_audit=True)

    assert report["status"] == "failed"
    assert report["summary"]["audit_package_verification_status"] == "missing"
    assert any(item["check_id"] == "operations_audit_verification_missing" for item in report["blockers"])
    assert any(item["check_id"] == "reviewer_pack_require_audit" and item["status"] == "failed" for item in verification["checks"])

    failed_audit = verify_release_operations_audit_package(audit_store.zip_path(release.release_id), require_current=True, require_signed=True, require_archive=True)
    failed_audit["status"] = "failed"
    write_release_operations_audit_verification_report(failed_audit, audit_store.verification_report_path(release.release_id))

    failed_report = reviewer_store.refresh(release.release_id)
    reviewer_store.export_pack(release.release_id)
    reviewer_store.build_zip(release.release_id)
    failed_verification = verify_release_operations_reviewer_pack(reviewer_store.zip_path(release.release_id), require_audit=True)

    assert failed_report["status"] == "failed"
    assert failed_report["summary"]["audit_package_verification_status"] == "failed"
    assert any(item["check_id"] == "operations_audit_verification_failed" for item in failed_report["blockers"])
    assert any(item["check_id"] == "reviewer_pack_require_audit" and item["status"] == "failed" for item in failed_verification["checks"])


def test_reviewer_pack_verifier_tamper_path_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    release, _operations_store, _runbook_store, _signoff_store, _audit_store, reviewer_store = accepted_reviewer_fixture(tmp_path, monkeypatch)
    reviewer_store.refresh(release.release_id)
    reviewer_store.export_pack(release.release_id)
    reviewer_store.build_zip(release.release_id)
    source_zip = reviewer_store.zip_path(release.release_id)

    tampered_zip = tmp_path / "tampered-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "reviewer-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["warning_count"] = 99
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    retro_zip = tmp_path / "tampered-retro.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(retro_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "retrospective-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("recommendations", []).append({"recommendation": "tampered"})
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    missing_zip = tmp_path / "missing-guide.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(missing_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename != "REVIEWER_GUIDE.md":
                dst.writestr(info.filename, src.read(info.filename))

    dangerous_zip = tmp_path / "dangerous-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../evil.txt", b"x")

    duplicate_zip = tmp_path / "duplicate-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    backslash_zip = tmp_path / "backslash-reviewer.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoof_zip = tmp_path / "spoof-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "reviewer-pack-manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction_zip = tmp_path / "redaction-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "REVIEWER_GUIDE.md":
                data += b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n"
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "reviewer_pack_report_integrity" for item in verify_release_operations_reviewer_pack(tampered_zip)["blockers"])
    assert any(item["check_id"] == "reviewer_pack_retrospective_integrity" for item in verify_release_operations_reviewer_pack(retro_zip)["blockers"])
    assert any(item["check_id"] == "reviewer_pack_zip_required_entries" for item in verify_release_operations_reviewer_pack(missing_zip)["blockers"])
    assert any(item["check_id"] == "reviewer_pack_zip_entry_path_safe" for item in verify_release_operations_reviewer_pack(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "reviewer_pack_zip_duplicate_entries" for item in verify_release_operations_reviewer_pack(duplicate_zip)["blockers"])
    assert any(item["check_id"] == "reviewer_pack_zip_entry_path_safe" for item in verify_release_operations_reviewer_pack(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_operations_reviewer_pack(spoof_zip, strict=True)
    assert any(item["check_id"] == "reviewer_pack_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "reviewer_pack_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "reviewer_pack_redaction_scan" for item in verify_release_operations_reviewer_pack(redaction_zip)["blockers"])
