from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_audit import _accepted_governance_fixture

from song_agent.projectio import write_json
from song_agent.release_portfolio_governance_audit_verifier import verify_release_portfolio_governance_audit_package, write_release_portfolio_governance_audit_verification_report
from song_agent.release_portfolio_governance_reviewer_pack import (
    ReleasePortfolioGovernanceReviewerPackStateError,
    ReleasePortfolioGovernanceReviewerPackStore,
    evidence_index_integrity_ok,
    retrospective_report_integrity_ok,
    reviewer_pack_manifest_integrity_hash,
    reviewer_pack_manifest_integrity_ok,
    reviewer_report_integrity_ok,
    timeline_integrity_ok,
)
from song_agent.release_portfolio_governance_reviewer_pack_verifier import verify_release_portfolio_governance_reviewer_pack


def _accepted_reviewer_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, queue_id, governance_store, signoff_store, audit_store = _accepted_governance_fixture(tmp_path, monkeypatch)
    audit_store.refresh(portfolio_id)
    audit_store.export_audit(portfolio_id)
    audit_store.build_zip(portfolio_id)
    audit_verification = verify_release_portfolio_governance_audit_package(audit_store.zip_path(portfolio_id), strict=True, require_signed=True, require_archives=True)
    write_release_portfolio_governance_audit_verification_report(audit_verification, audit_store.verification_report_path(portfolio_id))
    reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=audit_store)
    return portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store


def test_portfolio_governance_reviewer_pack_refresh_export_zip_verify(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, reviewer_store = _accepted_reviewer_fixture(tmp_path, monkeypatch)

    report = reviewer_store.refresh(portfolio_id)
    retrospective = reviewer_store.read_retrospective(portfolio_id)
    evidence = reviewer_store.read_evidence_index(portfolio_id)
    timeline = reviewer_store.read_timeline(portfolio_id)
    manifest = reviewer_store.export_pack(portfolio_id)
    zip_info = reviewer_store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_reviewer_pack(reviewer_store.zip_path(portfolio_id), strict=True, require_audit=True, require_signed=True, require_archives=True)

    assert report["status"] == "passed"
    assert reviewer_report_integrity_ok(report)
    assert retrospective_report_integrity_ok(retrospective)
    assert evidence_index_integrity_ok(evidence)
    assert timeline_integrity_ok(timeline)
    assert manifest["package_type"] == "release_portfolio_governance_reviewer_pack"
    assert reviewer_pack_manifest_integrity_ok(manifest)
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert verification["summary"]["portfolio_id"] == portfolio_id


def test_portfolio_governance_reviewer_pack_blocks_stale_source_export_and_zip(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, audit_store, reviewer_store = _accepted_reviewer_fixture(tmp_path, monkeypatch)
    reviewer_store.refresh(portfolio_id)
    reviewer_store.export_pack(portfolio_id)
    reviewer_store.build_zip(portfolio_id)
    audit_store.verification_report_path(portfolio_id).unlink()

    assert reviewer_store.report_is_stale(portfolio_id) is True
    with pytest.raises(ReleasePortfolioGovernanceReviewerPackStateError, match="stale"):
        reviewer_store.export_pack(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceReviewerPackStateError, match="stale"):
        reviewer_store.build_zip(portfolio_id)


def test_portfolio_governance_reviewer_pack_requires_audit_verification(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, audit_store, reviewer_store = _accepted_reviewer_fixture(tmp_path, monkeypatch)
    audit_store.verification_report_path(portfolio_id).unlink()

    report = reviewer_store.refresh(portfolio_id)
    reviewer_store.export_pack(portfolio_id)
    reviewer_store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_reviewer_pack(reviewer_store.zip_path(portfolio_id), require_audit=True)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "governance_audit_verification_missing" for item in report["blockers"])
    assert verification["status"] == "failed"
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_require_audit" for item in verification["blockers"])


def test_portfolio_governance_reviewer_pack_verifier_catches_tamper_package_type_path_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, reviewer_store = _accepted_reviewer_fixture(tmp_path, monkeypatch)
    reviewer_store.refresh(portfolio_id)
    reviewer_store.export_pack(portfolio_id)
    reviewer_store.build_zip(portfolio_id)
    source_zip = reviewer_store.zip_path(portfolio_id)

    tampered_zip = tmp_path / "tampered-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "reviewer-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["queue_count"] = 99
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    wrong_type_zip = tmp_path / "wrong-type-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(wrong_type_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload["package_type"] = "wrong_package_type"
                payload["integrity_hash"] = reviewer_pack_manifest_integrity_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    dangerous_zip = tmp_path / "dangerous-reviewer.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../outside.txt", b"x")

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
            if info.filename == "manifest.json":
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

    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_report_integrity" for item in verify_release_portfolio_governance_reviewer_pack(tampered_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_manifest_package_type" for item in verify_release_portfolio_governance_reviewer_pack(wrong_type_zip)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_zip_entry_path_safe" for item in verify_release_portfolio_governance_reviewer_pack(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_zip_duplicate_entries" for item in verify_release_portfolio_governance_reviewer_pack(duplicate_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_zip_entry_path_safe" for item in verify_release_portfolio_governance_reviewer_pack(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_reviewer_pack(spoof_zip, strict=True)
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "portfolio_governance_reviewer_pack_redaction_scan" for item in verify_release_portfolio_governance_reviewer_pack(redaction_zip)["blockers"])
