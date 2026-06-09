from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_evidence_vault import _signed_final_board_vault_fixture

from song_agent.release_portfolio_governance_attestation import (
    ReleasePortfolioGovernanceAttestationStateError,
    ReleasePortfolioGovernanceAttestationStore,
    attestation_certificate_hash,
    attestation_manifest_hash,
    attestation_report_integrity_ok,
)
from song_agent.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation
from song_agent.release_portfolio_governance_evidence_vault_verifier import (
    verify_release_portfolio_governance_evidence_vault_package,
    write_release_portfolio_governance_evidence_vault_verification_report,
)


def _attestation_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store = _signed_final_board_vault_fixture(tmp_path, monkeypatch)
    vault_store.refresh_report(portfolio_id)
    vault_store.export_vault(portfolio_id)
    vault_store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_evidence_vault_package(vault_store.zip_path(portfolio_id), strict=True, deep=True, require_final_board=True, require_reviewer_pack=True, require_audit=True, require_archives=True)
    write_release_portfolio_governance_evidence_vault_verification_report(verification, vault_store.verification_report_path(portfolio_id))
    store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=audit_store.portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    return portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store, store


def test_attestation_refresh_export_zip_verify(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _attestation_fixture(tmp_path, monkeypatch)
    report = store.refresh_report(portfolio_id)
    manifest = store.export_attestation(portfolio_id)
    zip_info = store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_attestation(store.zip_path(portfolio_id), strict=True, require_vault=True, require_final_board=True)

    assert report["status"] == "passed"
    assert attestation_report_integrity_ok(report)
    assert manifest["package_type"] == "release_portfolio_governance_public_attestation"
    assert manifest["integrity_hash"] == attestation_manifest_hash(manifest)
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    with zipfile.ZipFile(store.zip_path(portfolio_id), "r") as archive:
        assert not any(name.endswith(".zip") or name.startswith("nested/") for name in archive.namelist())


def test_attestation_blocks_delete_rebuild_same_vault(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _attestation_fixture(tmp_path, monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_attestation(portfolio_id)
    store.build_zip(portfolio_id)

    with pytest.raises(ReleasePortfolioGovernanceAttestationStateError, match="already exists"):
        store.export_attestation(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationStateError, match="already exists"):
        store.build_zip(portfolio_id)
    shutil.rmtree(store.export_dir(portfolio_id))
    store.zip_path(portfolio_id).unlink()
    with pytest.raises(ReleasePortfolioGovernanceAttestationStateError, match="already exists"):
        store.export_attestation(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationStateError, match="already exists"):
        store.build_zip(portfolio_id)


def test_attestation_blocks_stale_vault_verification(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, vault_store, store = _attestation_fixture(tmp_path, monkeypatch)
    report = store.refresh_report(portfolio_id)
    assert report["status"] == "passed"
    old_verification = vault_store.verification_report_path(portfolio_id).read_text(encoding="utf-8")
    vault_store.zip_path(portfolio_id).write_bytes(vault_store.zip_path(portfolio_id).read_bytes() + b"tampered")
    vault_store.verification_report_path(portfolio_id).write_text(old_verification, encoding="utf-8")
    stale = store.refresh_report(portfolio_id)
    assert stale["status"] == "failed"
    assert any(item["check_id"] == "evidence_vault_verification_current" for item in stale["blockers"])


def test_attestation_verifier_catches_tamper_nested_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _attestation_fixture(tmp_path, monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_attestation(portfolio_id)
    store.build_zip(portfolio_id)
    source_zip = store.zip_path(portfolio_id)

    cert_tamper = tmp_path / "cert-tamper.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(cert_tamper, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "certificate.json":
                payload = json.loads(data.decode("utf-8"))
                payload["governance_status"] = "failed"
                payload["payload_hash"] = attestation_certificate_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    nested_zip = tmp_path / "nested.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(nested_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("nested/fake.zip", b"PK\x05\x06" + b"\0" * 18)

    spoof_zip = tmp_path / "spoof.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction_zip = tmp_path / "redaction.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "certificate.md":
                data += b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n"
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "attestation_manifest_certificate_hash" for item in verify_release_portfolio_governance_attestation(cert_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "attestation_zip_no_nested_packages" for item in verify_release_portfolio_governance_attestation(nested_zip, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_attestation(spoof_zip, strict=True)
    assert any(item["check_id"] == "attestation_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "attestation_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "attestation_redaction_scan" for item in verify_release_portfolio_governance_attestation(redaction_zip)["blockers"])


def test_attestation_verifier_rejects_vault_fingerprint_desync_from_report_source(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _attestation_fixture(tmp_path, monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_attestation(portfolio_id)
    store.build_zip(portfolio_id)
    source_zip = store.zip_path(portfolio_id)
    tampered_zip = tmp_path / "vault-fingerprint-desync.zip"
    fake_vault = {
        "zip_sha256": "a" * 64,
        "zip_size_bytes": 123456,
        "manifest_hash": "b" * 64,
        "verification_hash": "c" * 64,
        "verification_status": "passed",
        "deep_verification_status": "passed",
    }

    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        rewritten: dict[str, bytes] = {}
        for info in src.infolist():
            rewritten[info.filename] = src.read(info.filename)
        certificate = json.loads(rewritten["certificate.json"].decode("utf-8"))
        certificate["evidence_vault"] = fake_vault
        certificate["payload_hash"] = attestation_certificate_hash(certificate)
        certificate_bytes = json.dumps(certificate, ensure_ascii=False, indent=2).encode("utf-8")
        manifest = json.loads(rewritten["manifest.json"].decode("utf-8"))
        manifest["evidence_vault"] = fake_vault
        manifest.setdefault("certificate", {})["payload_hash"] = certificate["payload_hash"]
        for row in manifest.get("files", []):
            if isinstance(row, dict) and row.get("path") == "certificate.json":
                row["size_bytes"] = len(certificate_bytes)
                import hashlib

                row["sha256"] = hashlib.sha256(certificate_bytes).hexdigest()
        manifest["integrity_hash"] = attestation_manifest_hash(manifest)
        rewritten["certificate.json"] = certificate_bytes
        rewritten["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        for info in src.infolist():
            dst.writestr(info.filename, rewritten[info.filename])

    result = verify_release_portfolio_governance_attestation(tampered_zip, strict=True, require_vault=True, require_final_board=True)

    assert any(item["check_id"] == "attestation_source_evidence_vault_zip_sha256" for item in result["blockers"])
    assert any(item["check_id"] == "attestation_source_evidence_vault_zip_size_bytes" for item in result["blockers"])
    assert any(item["check_id"] == "attestation_source_evidence_vault_manifest_hash" for item in result["blockers"])
    assert any(item["check_id"] == "attestation_source_evidence_vault_verification_hash" for item in result["blockers"])


def test_attestation_verifier_rejects_case_variant_musicforge_entry_declared_in_manifest(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _attestation_fixture(tmp_path, monkeypatch)
    store.refresh_report(portfolio_id)
    store.export_attestation(portfolio_id)
    store.build_zip(portfolio_id)
    source_zip = store.zip_path(portfolio_id)
    tampered_zip = tmp_path / "case-variant-musicforge.zip"
    internal_bytes = b"internal"

    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                import hashlib

                payload.setdefault("files", []).append({"path": ".MusicForge/internal.json", "size_bytes": len(internal_bytes), "sha256": hashlib.sha256(internal_bytes).hexdigest()})
                payload["integrity_hash"] = attestation_manifest_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr(".MusicForge/internal.json", internal_bytes)

    result = verify_release_portfolio_governance_attestation(tampered_zip, strict=True)

    assert any(item["check_id"] == "attestation_zip_no_nested_packages" for item in result["blockers"])
