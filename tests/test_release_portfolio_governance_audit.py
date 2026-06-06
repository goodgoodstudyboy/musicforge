from __future__ import annotations

import json
import zipfile
from pathlib import Path

from tests.test_release_portfolio_governance_signoff import _manual_acknowledgements, _prepared_queue

from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore, audit_ledger_integrity_ok, audit_manifest_integrity_hash, audit_report_integrity_ok
from song_agent.release_portfolio_governance_audit_verifier import verify_release_portfolio_governance_audit_package
from song_agent.release_portfolio_governance_archive_verifier import verify_release_portfolio_governance_archive_package, write_release_portfolio_governance_archive_verification_report


def _accepted_governance_fixture(tmp_path: Path, monkeypatch):
    queue_id, governance_store, signoff_store = _prepared_queue(tmp_path, monkeypatch)
    signoff_store.signoff(queue_id, {"signed_by": "tester", "manual_acknowledgements": _manual_acknowledgements(governance_store, queue_id)})
    signoff_store.export_archive(queue_id)
    signoff_store.build_archive_zip(queue_id)
    archive_verification = verify_release_portfolio_governance_archive_package(signoff_store.archive_zip_path(queue_id), require_signed=True)
    write_release_portfolio_governance_archive_verification_report(archive_verification, signoff_store.archive_verification_report_path(queue_id))
    queue = governance_store.get_queue(queue_id)
    audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=governance_store.portfolio_store, governance_store=governance_store, signoff_store=signoff_store)
    return queue["portfolio_id"], queue_id, governance_store, signoff_store, audit_store


def test_portfolio_governance_audit_refresh_export_zip_verify(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, queue_id, _governance_store, _signoff_store, audit_store = _accepted_governance_fixture(tmp_path, monkeypatch)

    report = audit_store.refresh(portfolio_id)
    entries = audit_store.read_ledger(portfolio_id)
    manifest = audit_store.export_audit(portfolio_id)
    zip_info = audit_store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_audit_package(audit_store.zip_path(portfolio_id), require_signed=True, require_archives=True)

    assert report["status"] == "passed"
    assert audit_report_integrity_ok(report)
    assert audit_ledger_integrity_ok(entries)
    assert any(item["event_type"] == "governance_signoff_signed" for item in entries)
    assert any(item["event_type"] == "governance_archive_verified" for item in entries)
    assert manifest["audit_report"]["ledger_hash"] == report["ledger_hash"]
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert report["coverage"]["signed_queue_count"] == 1
    assert report["coverage"]["archive_verified_count"] == 1
    assert report["queue_summaries"][0]["queue_id"] == queue_id


def test_portfolio_governance_audit_requires_verified_archive_evidence(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, queue_id, _governance_store, signoff_store, audit_store = _accepted_governance_fixture(tmp_path, monkeypatch)
    signoff_store.archive_verification_report_path(queue_id).unlink()

    report = audit_store.refresh(portfolio_id)
    audit_store.export_audit(portfolio_id)
    audit_store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_audit_package(audit_store.zip_path(portfolio_id), require_signed=True, require_archives=True)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "governance_archive_verification_missing" for item in report["blockers"])
    assert verification["status"] == "failed"
    assert any(item["check_id"] == "portfolio_governance_audit_require_archives" for item in verification["blockers"])


def test_portfolio_governance_audit_blocks_stale_archive_verification_report(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, queue_id, _governance_store, signoff_store, audit_store = _accepted_governance_fixture(tmp_path, monkeypatch)
    old_report = signoff_store.archive_verification_report_path(queue_id).read_text(encoding="utf-8")
    old_sha = json.loads(old_report)["zip_sha256"]

    new_zip = signoff_store.build_archive_zip(queue_id)
    signoff_store.archive_verification_report_path(queue_id).write_text(old_report, encoding="utf-8")

    report = audit_store.refresh(portfolio_id)

    assert old_sha != new_zip["sha256"]
    assert report["status"] == "failed"
    assert any(item["check_id"] == "governance_archive_verification_zip_sha256" for item in report["blockers"])


def test_portfolio_governance_audit_reset_cr_causality(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, queue_id, governance_store, signoff_store, audit_store = _accepted_governance_fixture(tmp_path, monkeypatch)
    change = signoff_store.create_change_request(queue_id, {"reason": "Approved governance audit reset", "requested_by": "tester"})
    approved = signoff_store.update_change_request_status(queue_id, change["change_request_id"], "approve", {"approved_by": "reviewer"})
    reset = signoff_store.reset_signoff(queue_id, {"reason": "Reset with approved governance audit request", "change_request_id": approved["change_request_id"]})
    governance_store.export_queue(queue_id)
    governance_store.build_zip(queue_id)

    report = audit_store.refresh(portfolio_id)
    entries = audit_store.read_ledger(portfolio_id)
    reset_entries = [item for item in entries if item["event_type"] == "governance_signoff_reset"]
    applied_entries = [item for item in entries if item["event_type"] == "governance_change_request_applied"]

    assert report["status"] == "passed"
    assert reset_entries
    assert applied_entries
    assert reset_entries[-1]["source"]["payload_hash"] == reset["integrity_hash"]
    assert reset_entries[-1]["causal_refs"][0]["id"] == approved["change_request_id"]


def test_portfolio_governance_audit_verifier_catches_tamper_missing_reorder_and_redaction(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, audit_store = _accepted_governance_fixture(tmp_path, monkeypatch)
    audit_store.refresh(portfolio_id)
    audit_store.export_audit(portfolio_id)
    audit_store.build_zip(portfolio_id)
    source_zip = audit_store.zip_path(portfolio_id)

    tampered_zip = tmp_path / "tampered-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "portfolio-governance-audit-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["queue_count"] = 99
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    missing_zip = tmp_path / "missing-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(missing_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename != "portfolio-governance-audit-ledger.jsonl":
                dst.writestr(info.filename, src.read(info.filename))

    reorder_zip = tmp_path / "reorder-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(reorder_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "portfolio-governance-audit-ledger.jsonl":
                lines = data.decode("utf-8").splitlines()
                data = ("\n".join(reversed(lines)) + "\n").encode("utf-8")
            dst.writestr(info.filename, data)

    redaction_zip = tmp_path / "redaction-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "README.txt":
                data += b"\nC:\\Users\\demo\\githubkey.txt api_key=sk-secret-value\n"
            dst.writestr(info.filename, data)

    tampered = verify_release_portfolio_governance_audit_package(tampered_zip)
    missing = verify_release_portfolio_governance_audit_package(missing_zip)
    reordered = verify_release_portfolio_governance_audit_package(reorder_zip)
    redaction = verify_release_portfolio_governance_audit_package(redaction_zip)

    wrong_type_zip = tmp_path / "wrong-type-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(wrong_type_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload["package_type"] = "wrong_package_type"
                payload["integrity_hash"] = audit_manifest_integrity_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
    wrong_type = verify_release_portfolio_governance_audit_package(wrong_type_zip)

    assert any(item["check_id"] == "portfolio_governance_audit_report_integrity" for item in tampered["blockers"])
    assert any(item["check_id"] == "portfolio_governance_audit_zip_required_entries" for item in missing["blockers"])
    assert any(item["check_id"] == "portfolio_governance_audit_ledger_chain" for item in reordered["blockers"])
    assert any(item["check_id"] == "portfolio_governance_audit_redaction_scan" for item in redaction["blockers"])
    assert any(item["check_id"] == "portfolio_governance_audit_manifest_package_type" for item in wrong_type["blockers"])


def test_portfolio_governance_audit_verifier_catches_zip_path_duplicate_and_spoof(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, audit_store = _accepted_governance_fixture(tmp_path, monkeypatch)
    audit_store.refresh(portfolio_id)
    audit_store.export_audit(portfolio_id)
    audit_store.build_zip(portfolio_id)
    source_zip = audit_store.zip_path(portfolio_id)

    dangerous_zip = tmp_path / "dangerous-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../outside.txt", b"x")

    duplicate_zip = tmp_path / "duplicate-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    backslash_zip = tmp_path / "backslash-governance-audit.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoof_zip = tmp_path / "spoof-governance-audit.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    assert any(item["check_id"] == "portfolio_governance_audit_zip_entry_path_safe" for item in verify_release_portfolio_governance_audit_package(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_audit_zip_duplicate_entries" for item in verify_release_portfolio_governance_audit_package(duplicate_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portfolio_governance_audit_zip_entry_path_safe" for item in verify_release_portfolio_governance_audit_package(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_audit_package(spoof_zip, strict=True)
    assert any(item["check_id"] == "portfolio_governance_audit_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "portfolio_governance_audit_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
