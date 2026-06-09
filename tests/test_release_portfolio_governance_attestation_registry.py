from __future__ import annotations

import json
import shutil
import zipfile
import hashlib
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_attestation import _attestation_fixture

from song_agent.release_portfolio_governance_attestation_registry import (
    ReleasePortfolioGovernanceAttestationRegistryStateError,
    ReleasePortfolioGovernanceAttestationRegistryStore,
    registry_hash,
    registry_manifest_hash,
    registry_report_hash,
    registry_report_integrity_ok,
)
from song_agent.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry
from song_agent.releases import stable_hash


def _registry_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store, attestation_store = _attestation_fixture(tmp_path, monkeypatch)
    attestation_store.refresh_report(portfolio_id)
    attestation_store.export_attestation(portfolio_id)
    attestation_store.build_zip(portfolio_id)
    store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
    return portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store, attestation_store, store


def test_attestation_registry_register_publish_export_verify(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _registry_fixture(tmp_path, monkeypatch)
    registered = store.register_current_attestation(portfolio_id)
    entry_id = registered["entry"]["entry_id"]
    duplicate = store.register_current_attestation(portfolio_id)
    published = store.publish_entry(portfolio_id, entry_id, {"published_by": "tester"})
    report = store.refresh_report(portfolio_id)
    manifest = store.export_registry(portfolio_id)
    zip_info = store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_attestation_registry(store.zip_path(portfolio_id), strict=True, require_current=True, require_published=True)

    assert duplicate["existing"] is True
    assert published["registry"]["current_entry_id"] == entry_id
    assert report["status"] == "passed"
    assert registry_report_integrity_ok(report)
    assert manifest["package_type"] == "release_portfolio_governance_attestation_registry"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    with zipfile.ZipFile(store.zip_path(portfolio_id), "r") as archive:
        names = archive.namelist()
    assert "registry.json" in names
    assert not any(name.endswith(".zip") or name.startswith("nested/") for name in names)


def test_attestation_registry_publish_requires_explicit_supersede_and_revoke_clears_current(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, attestation_store, store = _registry_fixture(tmp_path, monkeypatch)
    first = store.register_current_attestation(portfolio_id)["entry"]
    store.publish_entry(portfolio_id, first["entry_id"], {"published_by": "tester"})

    # Simulate a newer attestation package by appending deterministic bytes and re-registering.
    attestation_store.zip_path(portfolio_id).write_bytes(attestation_store.zip_path(portfolio_id).read_bytes() + b"new-attestation")
    second = store.register_current_attestation(portfolio_id)["entry"]
    with pytest.raises(ReleasePortfolioGovernanceAttestationRegistryStateError, match="supersede_current"):
        store.publish_entry(portfolio_id, second["entry_id"], {"published_by": "tester"})

    published = store.publish_entry(portfolio_id, second["entry_id"], {"published_by": "tester", "supersede_current": True})
    first_after = store.get_entry(portfolio_id, first["entry_id"])
    revoked = store.revoke_entry(portfolio_id, second["entry_id"], {"revoked_by": "tester", "reason": "Replacing public proof after governance update."})
    report = store.refresh_report(portfolio_id)
    store.export_registry(portfolio_id)
    store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_attestation_registry(store.zip_path(portfolio_id), strict=True, require_current=True)

    assert published["registry"]["current_entry_id"] == second["entry_id"]
    assert first_after["status"] == "superseded"
    assert first_after["superseded_by_entry_id"] == second["entry_id"]
    assert revoked["registry"]["current_entry_id"] is None
    assert report["status"] == "passed"
    assert verification["status"] == "failed"
    assert any(item["check_id"] == "registry_require_current" for item in verification["blockers"])
    with pytest.raises(ReleasePortfolioGovernanceAttestationRegistryStateError, match="cannot be published"):
        store.publish_entry(portfolio_id, second["entry_id"], {"published_by": "tester"})


def test_attestation_registry_blocks_delete_rebuild_same_state(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _registry_fixture(tmp_path, monkeypatch)
    entry = store.register_current_attestation(portfolio_id)["entry"]
    store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "tester"})
    store.refresh_report(portfolio_id)
    store.export_registry(portfolio_id)
    store.build_zip(portfolio_id)

    with pytest.raises(ReleasePortfolioGovernanceAttestationRegistryStateError, match="already exists"):
        store.export_registry(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationRegistryStateError, match="already exists"):
        store.build_zip(portfolio_id)
    shutil.rmtree(store.export_dir(portfolio_id))
    store.zip_path(portfolio_id).unlink()
    with pytest.raises(ReleasePortfolioGovernanceAttestationRegistryStateError, match="already exists"):
        store.export_registry(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationRegistryStateError, match="already exists"):
        store.build_zip(portfolio_id)


def test_attestation_registry_verifier_catches_tamper_paths_spoof_and_redaction(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _registry_fixture(tmp_path, monkeypatch)
    entry = store.register_current_attestation(portfolio_id)["entry"]
    store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "tester"})
    store.refresh_report(portfolio_id)
    store.export_registry(portfolio_id)
    store.build_zip(portfolio_id)
    source_zip = store.zip_path(portfolio_id)

    registry_tamper = tmp_path / "registry-tamper.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(registry_tamper, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "registry.json":
                payload = json.loads(data.decode("utf-8"))
                payload["current_entry_id"] = "missing-entry"
                payload["integrity_hash"] = registry_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    wrong_type = tmp_path / "wrong-type.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(wrong_type, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload["package_type"] = "wrong_package_type"
                payload["integrity_hash"] = registry_manifest_hash(payload)
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    case_musicforge = tmp_path / "case-musicforge.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(case_musicforge, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr(".MusicForge/internal.json", b"internal")

    nested = tmp_path / "nested.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(nested, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("nested/fake.zip", b"PK\x05\x06" + b"\0" * 18)

    spoof = tmp_path / "spoof.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(spoof, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "manifest.json":
                payload = json.loads(data.decode("utf-8"))
                payload.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("extra.txt", b"extra")

    redaction = tmp_path / "redaction.zip"
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(redaction, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "README.txt":
                data += b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n"
            dst.writestr(info.filename, data)

    assert any(item["check_id"] == "registry_current_entry_exists" for item in verify_release_portfolio_governance_attestation_registry(registry_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "registry_manifest_package_type" for item in verify_release_portfolio_governance_attestation_registry(wrong_type, strict=True)["blockers"])
    assert any(item["check_id"] == "registry_zip_no_nested_packages" for item in verify_release_portfolio_governance_attestation_registry(case_musicforge, strict=True)["blockers"])
    assert any(item["check_id"] == "registry_zip_no_nested_packages" for item in verify_release_portfolio_governance_attestation_registry(nested, strict=True)["blockers"])
    spoofed = verify_release_portfolio_governance_attestation_registry(spoof, strict=True)
    assert any(item["check_id"] == "registry_manifest_extra_entries" for item in spoofed["blockers"])
    assert any(item["check_id"] == "registry_manifest_zip_entries_reference_only" for item in spoofed["warnings"])
    assert any(item["check_id"] == "registry_redaction_scan" for item in verify_release_portfolio_governance_attestation_registry(redaction)["blockers"])


def test_attestation_registry_verifier_binds_report_source_to_registry(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _registry_fixture(tmp_path, monkeypatch)
    entry = store.register_current_attestation(portfolio_id)["entry"]
    store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "tester"})
    store.refresh_report(portfolio_id)
    store.export_registry(portfolio_id)
    store.build_zip(portfolio_id)

    tampered = _rewrite_registry_package(
        store.zip_path(portfolio_id),
        tmp_path / "report-source-resigned.zip",
        mutate=lambda docs: _tamper_report_source_and_resign(docs),
    )
    verification = verify_release_portfolio_governance_attestation_registry(tampered, strict=True, require_current=True, require_published=True)

    assert verification["status"] == "failed"
    assert any(item["check_id"] == "registry_report_source_current_attestation_zip_sha256" for item in verification["blockers"])


def test_attestation_registry_verifier_binds_package_index_to_registry(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, store = _registry_fixture(tmp_path, monkeypatch)
    entry = store.register_current_attestation(portfolio_id)["entry"]
    store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "tester"})
    store.refresh_report(portfolio_id)
    store.export_registry(portfolio_id)
    store.build_zip(portfolio_id)

    tampered = _rewrite_registry_package(
        store.zip_path(portfolio_id),
        tmp_path / "package-index-resigned.zip",
        mutate=lambda docs: _tamper_package_index_and_resign(docs),
    )
    verification = verify_release_portfolio_governance_attestation_registry(tampered, strict=True, require_current=True, require_published=True)

    assert verification["status"] == "failed"
    assert any(item["check_id"] == "registry_package_index_items_match_registry" for item in verification["blockers"])


def _rewrite_registry_package(source_zip: Path, target_zip: Path, *, mutate) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
        mutate(docs)
        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                dst.writestr(info.filename, docs[info.filename])
    return target_zip


def _tamper_report_source_and_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "registry-report.json")
    package_index = _read_doc(docs, "package-index.json")
    chain = _read_doc(docs, "chain-of-custody.json")
    manifest = _read_doc(docs, "manifest.json")

    report.setdefault("source", {})["current_attestation_zip_sha256"] = "0" * 64
    report["source_hash"] = stable_hash(report["source"])
    report["integrity_hash"] = registry_report_hash(report)

    package_index["source_hash"] = report["source_hash"]
    package_index["integrity_hash"] = stable_hash({key: value for key, value in package_index.items() if key != "integrity_hash"})
    chain["source_hash"] = report["source_hash"]
    chain["integrity_hash"] = stable_hash({key: value for key, value in chain.items() if key != "integrity_hash"})

    docs["registry-report.json"] = _doc_bytes(report)
    docs["package-index.json"] = _doc_bytes(package_index)
    docs["chain-of-custody.json"] = _doc_bytes(chain)
    manifest["source_hash"] = report["source_hash"]
    manifest.setdefault("registry_report", {})["source_hash"] = report["source_hash"]
    manifest.setdefault("registry_report", {})["integrity_hash"] = report["integrity_hash"]
    _sync_manifest_file(manifest, "registry-report.json", docs["registry-report.json"])
    _sync_manifest_file(manifest, "package-index.json", docs["package-index.json"])
    _sync_manifest_file(manifest, "chain-of-custody.json", docs["chain-of-custody.json"])
    manifest["integrity_hash"] = registry_manifest_hash(manifest)
    docs["manifest.json"] = _doc_bytes(manifest)


def _tamper_package_index_and_resign(docs: dict[str, bytes]) -> None:
    package_index = _read_doc(docs, "package-index.json")
    manifest = _read_doc(docs, "manifest.json")
    package_index.setdefault("items", [])[0]["attestation_zip_sha256"] = "1" * 64
    package_index["integrity_hash"] = stable_hash({key: value for key, value in package_index.items() if key != "integrity_hash"})
    docs["package-index.json"] = _doc_bytes(package_index)
    _sync_manifest_file(manifest, "package-index.json", docs["package-index.json"])
    manifest["integrity_hash"] = registry_manifest_hash(manifest)
    docs["manifest.json"] = _doc_bytes(manifest)


def _read_doc(docs: dict[str, bytes], name: str) -> dict:
    return json.loads(docs[name].decode("utf-8"))


def _doc_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _sync_manifest_file(manifest: dict, path: str, data: bytes) -> None:
    for item in manifest.get("files", []) if isinstance(manifest.get("files"), list) else []:
        if isinstance(item, dict) and item.get("path") == path:
            item["size_bytes"] = len(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()
            return
    raise AssertionError(f"manifest file row missing: {path}")
