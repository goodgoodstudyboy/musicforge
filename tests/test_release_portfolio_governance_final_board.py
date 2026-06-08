from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_reviewer_pack import _accepted_reviewer_fixture

from song_agent.release_portfolio_governance_final_board import (
    ReleasePortfolioGovernanceFinalBoardStateError,
    ReleasePortfolioGovernanceFinalBoardStore,
    final_board_archive_manifest_hash,
    final_board_report_integrity_ok,
    final_board_response_integrity_ok,
    final_board_signoff_integrity_ok,
)
from song_agent.release_portfolio_governance_final_board_verifier import verify_release_portfolio_governance_final_board_package
from song_agent.release_portfolio_governance_audit_verifier import verify_release_portfolio_governance_audit_package, write_release_portfolio_governance_audit_verification_report
from song_agent.release_portfolio_governance_reviewer_pack_verifier import verify_release_portfolio_governance_reviewer_pack, write_release_portfolio_governance_reviewer_pack_verification_report


def _accepted_final_board_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store = _accepted_reviewer_fixture(tmp_path, monkeypatch)
    audit_store.portfolio_store.refresh(portfolio_id)
    audit_store.refresh(portfolio_id)
    audit_store.export_audit(portfolio_id)
    audit_store.build_zip(portfolio_id)
    audit_verification = verify_release_portfolio_governance_audit_package(audit_store.zip_path(portfolio_id), strict=True, require_signed=True, require_archives=True)
    write_release_portfolio_governance_audit_verification_report(audit_verification, audit_store.verification_report_path(portfolio_id))
    reviewer_store.refresh(portfolio_id)
    reviewer_store.export_pack(portfolio_id)
    reviewer_store.build_zip(portfolio_id)
    reviewer_verification = verify_release_portfolio_governance_reviewer_pack(reviewer_store.zip_path(portfolio_id), strict=True, require_audit=True, require_signed=True, require_archives=True)
    write_release_portfolio_governance_reviewer_pack_verification_report(reviewer_verification, reviewer_store.verification_report_path(portfolio_id))
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=audit_store.portfolio_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    return portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store


def _accepted_response() -> dict:
    return {
        "reviewer": {"name": "External Reviewer", "organization": "Partner", "role": "governance_reviewer"},
        "decision": "accepted",
        "findings": [{"finding_id": "finding-001", "severity": "low", "status": "closed", "category": "general", "message": "Reviewed.", "resolution_note": "Accepted."}],
        "notes": "Portfolio governance evidence accepted.",
    }


def test_final_board_refresh_response_signoff_archive_verify(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, store = _accepted_final_board_fixture(tmp_path, monkeypatch)

    report = store.refresh_report(portfolio_id)
    response = store.import_reviewer_response(portfolio_id, _accepted_response())
    refreshed = store.refresh_report(portfolio_id, {"require_reviewer_response": True})
    signoff = store.signoff(portfolio_id, {"signed_by": "owner", "reason": "Portfolio governance evidence reviewed."})
    manifest = store.export_archive(portfolio_id)
    zip_info = store.build_archive_zip(portfolio_id)
    verification = verify_release_portfolio_governance_final_board_package(store.archive_zip_path(portfolio_id), strict=True, require_signed=True, require_reviewer_pack=True, require_audit=True, require_archives=True, require_reviewer_response=True)

    assert report["status"] == "passed"
    assert final_board_report_integrity_ok(report)
    assert response["decision"] == "accepted"
    assert final_board_response_integrity_ok(response)
    assert refreshed["summary"]["reviewer_response_status"] == "accepted"
    assert signoff["status"] == "signed"
    assert final_board_signoff_integrity_ok(signoff)
    assert manifest["package_type"] == "release_portfolio_governance_final_board_archive"
    assert manifest["integrity_hash"] == final_board_archive_manifest_hash(manifest)
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError, match="already exists"):
        store.export_archive(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError, match="already exists"):
        store.build_archive_zip(portfolio_id)
    shutil.rmtree(store.export_dir(portfolio_id))
    store.archive_zip_path(portfolio_id).unlink()
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError, match="already exists"):
        store.export_archive(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError, match="already exists"):
        store.build_archive_zip(portfolio_id)


def test_final_board_blocks_stale_reviewer_and_audit_verification(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, audit_store, reviewer_store, store = _accepted_final_board_fixture(tmp_path, monkeypatch)
    store.refresh_report(portfolio_id)

    old_reviewer_verification = reviewer_store.verification_report_path(portfolio_id).read_text(encoding="utf-8")
    reviewer_store.build_zip(portfolio_id, now="2026-06-08T12:00:00+00:00")
    reviewer_store.verification_report_path(portfolio_id).write_text(old_reviewer_verification, encoding="utf-8")
    stale_reviewer = store.refresh_report(portfolio_id)

    assert stale_reviewer["status"] == "failed"
    assert any(item["check_id"] == "governance_reviewer_pack_verification_current" for item in stale_reviewer["blockers"])
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError, match="Reviewer Pack"):
        store.signoff(portfolio_id, {"signed_by": "owner"})

    reviewer_verification = verify_release_portfolio_governance_reviewer_pack(reviewer_store.zip_path(portfolio_id), strict=True, require_audit=True, require_signed=True, require_archives=True)
    write_release_portfolio_governance_reviewer_pack_verification_report(reviewer_verification, reviewer_store.verification_report_path(portfolio_id))
    old_audit_verification = audit_store.verification_report_path(portfolio_id).read_text(encoding="utf-8")
    audit_store.build_zip(portfolio_id, now="2026-06-08T12:30:00+00:00")
    audit_store.verification_report_path(portfolio_id).write_text(old_audit_verification, encoding="utf-8")
    stale_audit = store.refresh_report(portfolio_id)

    assert stale_audit["status"] == "failed"
    assert any(item["check_id"] == "governance_audit_verification_current" for item in stale_audit["blockers"])


def test_final_board_response_and_reset_guards(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, store = _accepted_final_board_fixture(tmp_path, monkeypatch)
    store.import_reviewer_response(portfolio_id, {"decision": "needs_changes", "reviewer": {"name": "Reviewer"}, "findings": [{"status": "open", "message": "Fix required."}]})
    report = store.refresh_report(portfolio_id)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "reviewer_response_closed" for item in report["blockers"])
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError):
        store.import_reviewer_response(portfolio_id, {"source_path": "C:\\Users\\demo\\response.json", "decision": "accepted"})

    # A current accepted response clears the previous needs_changes decision.
    store.import_reviewer_response(portfolio_id, _accepted_response())
    report = store.refresh_report(portfolio_id)
    assert report["status"] == "passed"
    store.signoff(portfolio_id, {"signed_by": "owner"})
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError, match="approved"):
        store.reset_signoff(portfolio_id, {"reason": "Reset without approved change"})
    cr = store.create_change_request(portfolio_id, {"reason": "Reviewer requested final board update."})
    approved = store.update_change_request_status(portfolio_id, cr["change_request_id"], "approve", {"approved_by": "owner"})
    reset = store.reset_signoff(portfolio_id, {"reason": "Reset with approved final board change.", "change_request_id": approved["change_request_id"]})
    assert reset["status"] == "reset"
    with pytest.raises(ReleasePortfolioGovernanceFinalBoardStateError, match="approved"):
        store.reset_signoff(portfolio_id, {"reason": "Reuse final board change request.", "change_request_id": approved["change_request_id"]})


def test_final_board_verifier_catches_tamper_paths_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, store = _accepted_final_board_fixture(tmp_path, monkeypatch)
    store.import_reviewer_response(portfolio_id, _accepted_response())
    store.refresh_report(portfolio_id)
    store.signoff(portfolio_id, {"signed_by": "owner"})
    store.export_archive(portfolio_id)
    store.build_archive_zip(portfolio_id)
    source_zip = store.archive_zip_path(portfolio_id)

    tampered_zip = tmp_path / "tampered-final-board.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "final-board-report.json":
                payload = json.loads(data.decode("utf-8"))
                payload["summary"]["queue_count"] = 99
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    wrong_type_zip = tmp_path / "wrong-type-final-board.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(wrong_type_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload["package_type"] = "wrong_package_type"
                payload["integrity_hash"] = final_board_archive_manifest_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    dangerous_zip = tmp_path / "dangerous-final-board.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../outside.txt", b"x")

    duplicate_zip = tmp_path / "duplicate-final-board.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    backslash_zip = tmp_path / "backslash-final-board.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoof_zip = tmp_path / "spoof-final-board.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction_zip = tmp_path / "redaction-final-board.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "final-board.md":
                data += b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n"
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "final_board_report_integrity" for item in verify_release_portfolio_governance_final_board_package(tampered_zip)["blockers"])
    assert any(item["check_id"] == "final_board_manifest_package_type" for item in verify_release_portfolio_governance_final_board_package(wrong_type_zip)["blockers"])
    assert any(item["check_id"] == "final_board_zip_entry_path_safe" for item in verify_release_portfolio_governance_final_board_package(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "final_board_zip_duplicate_entries" for item in verify_release_portfolio_governance_final_board_package(duplicate_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "final_board_zip_entry_path_safe" for item in verify_release_portfolio_governance_final_board_package(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_final_board_package(spoof_zip, strict=True)
    assert any(item["check_id"] == "final_board_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "final_board_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "final_board_redaction_scan" for item in verify_release_portfolio_governance_final_board_package(redaction_zip)["blockers"])
