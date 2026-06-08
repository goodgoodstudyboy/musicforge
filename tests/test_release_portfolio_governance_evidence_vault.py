from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_final_board import _accepted_final_board_fixture, _accepted_response

from song_agent.release_portfolio_governance_evidence_vault import (
    ReleasePortfolioGovernanceEvidenceVaultStateError,
    ReleasePortfolioGovernanceEvidenceVaultStore,
    evidence_vault_manifest_hash,
    evidence_vault_report_integrity_ok,
)
from song_agent.release_portfolio_governance_evidence_vault_verifier import (
    verify_release_portfolio_governance_evidence_vault_package,
    write_release_portfolio_governance_evidence_vault_verification_report,
)
from song_agent.release_portfolio_governance_final_board_verifier import (
    verify_release_portfolio_governance_final_board_package,
    write_release_portfolio_governance_final_board_verification_report,
)
from song_agent.release_portfolio_governance_reviewer_pack_verifier import (
    verify_release_portfolio_governance_reviewer_pack,
    write_release_portfolio_governance_reviewer_pack_verification_report,
)


def _signed_final_board_vault_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store = _accepted_final_board_fixture(tmp_path, monkeypatch)
    final_board_store.import_reviewer_response(portfolio_id, _accepted_response())
    final_board_store.refresh_report(portfolio_id, {"require_reviewer_response": True})
    final_board_store.signoff(portfolio_id, {"signed_by": "owner", "reason": "Portfolio governance final board accepted."})
    final_board_store.export_archive(portfolio_id)
    final_board_store.build_archive_zip(portfolio_id)
    verification = verify_release_portfolio_governance_final_board_package(
        final_board_store.archive_zip_path(portfolio_id),
        strict=True,
        require_signed=True,
        require_reviewer_pack=True,
        require_audit=True,
        require_archives=True,
        require_reviewer_response=True,
    )
    write_release_portfolio_governance_final_board_verification_report(verification, final_board_store.verification_report_path(portfolio_id))
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=audit_store.portfolio_store,
        governance_store=governance_store,
        signoff_store=signoff_store,
        audit_store=audit_store,
        reviewer_pack_store=reviewer_store,
        final_board_store=final_board_store,
    )
    return portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store


def test_evidence_vault_refresh_export_zip_verify_deep(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, _final_board_store, store = _signed_final_board_vault_fixture(tmp_path, monkeypatch)

    report = store.refresh_report(portfolio_id)
    manifest = store.export_vault(portfolio_id)
    zip_info = store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_evidence_vault_package(
        store.zip_path(portfolio_id),
        strict=True,
        deep=True,
        require_final_board=True,
        require_reviewer_pack=True,
        require_audit=True,
        require_archives=True,
    )
    write_release_portfolio_governance_evidence_vault_verification_report(verification, store.verification_report_path(portfolio_id))

    assert report["status"] == "passed"
    assert evidence_vault_report_integrity_ok(report)
    assert manifest["package_type"] == "release_portfolio_governance_evidence_vault"
    assert manifest["integrity_hash"] == evidence_vault_manifest_hash(manifest)
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert verification["summary"]["deep_verification_status"] == "passed"
    assert any(item["role"] == "governance_archive" for item in manifest["nested_packages"])
    assert store.summary(portfolio_id)["verification_status"] == "passed"


def test_evidence_vault_blocks_delete_rebuild_for_same_final_board_signoff(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, _final_board_store, store = _signed_final_board_vault_fixture(tmp_path, monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_vault(portfolio_id)
    store.build_zip(portfolio_id)

    with pytest.raises(ReleasePortfolioGovernanceEvidenceVaultStateError, match="already exists"):
        store.export_vault(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceEvidenceVaultStateError, match="already exists"):
        store.build_zip(portfolio_id)
    shutil.rmtree(store.export_dir(portfolio_id))
    store.zip_path(portfolio_id).unlink()
    with pytest.raises(ReleasePortfolioGovernanceEvidenceVaultStateError, match="already exists"):
        store.export_vault(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceEvidenceVaultStateError, match="already exists"):
        store.build_zip(portfolio_id)


def test_evidence_vault_blocks_stale_nested_verification(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, reviewer_store, _final_board_store, store = _signed_final_board_vault_fixture(tmp_path, monkeypatch)
    old_reviewer_verification = reviewer_store.verification_report_path(portfolio_id).read_text(encoding="utf-8")
    reviewer_store.build_zip(portfolio_id, now="2026-06-08T12:00:00+00:00")
    reviewer_store.verification_report_path(portfolio_id).write_text(old_reviewer_verification, encoding="utf-8")

    report = store.refresh_report(portfolio_id)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "governance-reviewer-pack_verification_current" for item in report["blockers"])
    assert any(item["check_id"] == "final_board_report_current" for item in report["blockers"])
    with pytest.raises(ReleasePortfolioGovernanceEvidenceVaultStateError, match="Final Board|Reviewer Pack|verification"):
        store.export_vault(portfolio_id)


def test_evidence_vault_verifier_catches_tamper_paths_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _queue_id, _governance_store, _signoff_store, _audit_store, _reviewer_store, _final_board_store, store = _signed_final_board_vault_fixture(tmp_path, monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_vault(portfolio_id)
    store.build_zip(portfolio_id)
    source_zip = store.zip_path(portfolio_id)

    tampered_zip = tmp_path / "tampered-vault.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "nested/final-board/portfolio-governance-final-board-archive.zip":
                data = data + b"tampered"
            dst.writestr(info.filename, data)

    wrong_type_zip = tmp_path / "wrong-type-vault.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(wrong_type_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload["package_type"] = "wrong_package_type"
                payload["integrity_hash"] = evidence_vault_manifest_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    dangerous_zip = tmp_path / "dangerous-vault.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(dangerous_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("../outside.txt", b"x")

    duplicate_zip = tmp_path / "duplicate-vault.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(duplicate_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("README.txt", b"duplicate")

    backslash_zip = tmp_path / "backslash-vault.zip"
    with zipfile.ZipFile(backslash_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))

    spoof_zip = tmp_path / "spoof-vault.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction_zip = tmp_path / "redaction-vault.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "evidence-vault.md":
                data += b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n"
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "evidence_vault_nested_package_sha256" for item in verify_release_portfolio_governance_evidence_vault_package(tampered_zip)["blockers"])
    assert any(item["check_id"] == "evidence_vault_manifest_package_type" for item in verify_release_portfolio_governance_evidence_vault_package(wrong_type_zip)["blockers"])
    assert any(item["check_id"] == "evidence_vault_zip_entry_path_safe" for item in verify_release_portfolio_governance_evidence_vault_package(dangerous_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "evidence_vault_zip_duplicate_entries" for item in verify_release_portfolio_governance_evidence_vault_package(duplicate_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "evidence_vault_zip_entry_path_safe" for item in verify_release_portfolio_governance_evidence_vault_package(backslash_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_evidence_vault_package(spoof_zip, strict=True)
    assert any(item["check_id"] == "evidence_vault_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "evidence_vault_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "evidence_vault_redaction_scan" for item in verify_release_portfolio_governance_evidence_vault_package(redaction_zip)["blockers"])
