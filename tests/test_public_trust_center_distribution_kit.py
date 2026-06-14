from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_public_trust_center import _backslash_zip, _duplicate_zip, _rewrite_zip, _sync_manifest_file
from tests.test_public_trust_center_anchor_registry import _doc_bytes, _read_doc
from tests.test_public_trust_center_anchor_transparency import _anchor_transparency_fixture

from song_agent.public_trust_center_distribution_kit import (
    PublicTrustCenterDistributionKitStateError,
    PublicTrustCenterDistributionKitStore,
    distribution_kit_manifest_hash,
)
from song_agent.public_trust_center_distribution_kit_verifier import verify_public_trust_center_distribution_kit_package
from song_agent.public_trust_center_anchor_transparency_verifier import (
    verify_public_trust_center_anchor_transparency_package,
    write_public_trust_center_anchor_transparency_verification_report,
)


def test_distribution_kit_roundtrip_and_deep_verify(tmp_path: Path, monkeypatch) -> None:
    trust_store, anchor_store, transparency_store, kit_store = _distribution_kit_fixture(tmp_path, monkeypatch)

    report = kit_store.refresh_report("ptc-default")
    manifest = kit_store.export_kit("ptc-default")
    zip_info = kit_store.build_zip("ptc-default")
    verification = verify_public_trust_center_distribution_kit_package(kit_store.zip_path("ptc-default"), strict=True, deep=True, require_current=True, require_delivery_readiness=False)

    assert report["status"] == "ready"
    assert manifest["package_type"] == "musicforge_public_trust_center_distribution_kit"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    with zipfile.ZipFile(kit_store.zip_path("ptc-default"), "r") as archive:
        names = archive.namelist()
    assert "packages/public-trust-center.zip" in names
    assert "packages/public-trust-center-anchor-registry.zip" in names
    assert "packages/public-trust-center-anchor-transparency.zip" in names
    assert trust_store.zip_path("ptc-default").exists()
    assert anchor_store.zip_path("ptc-default").exists()
    assert transparency_store.zip_path("ptc-default").exists()


def test_distribution_kit_rejects_tamper_and_zip_edges(tmp_path: Path, monkeypatch) -> None:
    _trust_store, _anchor_store, _transparency_store, kit_store = _distribution_kit_fixture(tmp_path, monkeypatch)
    kit_store.refresh_report("ptc-default")
    kit_store.export_kit("ptc-default")
    kit_store.build_zip("ptc-default")
    source_zip = kit_store.zip_path("ptc-default")

    ptc_tamper = _rewrite_zip(source_zip, tmp_path / "ptc-tamper.zip", lambda docs: docs.update({"packages/public-trust-center.zip": docs["packages/public-trust-center.zip"] + b"x"}))
    anchor_tamper = _rewrite_zip(source_zip, tmp_path / "anchor-tamper.zip", lambda docs: docs.update({"anchors/public-trust-center.delivery-anchor.json": docs["anchors/public-trust-center.delivery-anchor.json"].replace(b"anchor_hash", b"anchor_bad_")}))
    checkpoint_tamper = _rewrite_zip(source_zip, tmp_path / "checkpoint-tamper.zip", lambda docs: docs.update({"anchors/ptc-anchor-checkpoint-current.json": _tamper_checkpoint(docs["anchors/ptc-anchor-checkpoint-current.json"])}))
    registry_tamper = _rewrite_zip(source_zip, tmp_path / "registry-tamper.zip", lambda docs: docs.update({"packages/public-trust-center-anchor-registry.zip": docs["packages/public-trust-center-anchor-registry.zip"] + b"x"}))
    transparency_tamper = _rewrite_zip(source_zip, tmp_path / "transparency-tamper.zip", lambda docs: docs.update({"packages/public-trust-center-anchor-transparency.zip": docs["packages/public-trust-center-anchor-transparency.zip"] + b"x"}))
    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"packages/extra.zip": b"PK\x05\x06" + b"\0" * 18}))
    spoof = _rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_kit_manifest)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n'}))

    assert _has_blocker(verify_public_trust_center_distribution_kit_package(ptc_tamper, strict=True, deep=True, require_delivery_readiness=False), "ptcdk_manifest_file_hashes")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(anchor_tamper, strict=True, deep=True, require_delivery_readiness=False), "ptcdk_manifest_file_hashes")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(checkpoint_tamper, strict=True, deep=True, require_delivery_readiness=False), "ptcdk_manifest_file_hashes")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(registry_tamper, strict=True, deep=True, require_delivery_readiness=False), "ptcdk_manifest_file_hashes")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(transparency_tamper, strict=True, deep=True, require_delivery_readiness=False), "ptcdk_manifest_file_hashes")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(duplicate, strict=True), "ptcdk_zip_duplicate_entries")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(dangerous, strict=True), "ptcdk_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(backslash, strict=True), "ptcdk_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(case_musicforge, strict=True), "ptcdk_zip_no_internal_entries")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(nested, strict=True), "ptcdk_zip_nested_allowlist")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(spoof, strict=True), "ptcdk_manifest_zip_entries_reference_only")
    assert _has_blocker(verify_public_trust_center_distribution_kit_package(redaction, strict=True), "ptcdk_redaction_scan")


def test_distribution_kit_stale_source_blocks_export(tmp_path: Path, monkeypatch) -> None:
    _trust_store, anchor_store, _transparency_store, kit_store = _distribution_kit_fixture(tmp_path, monkeypatch)
    report = kit_store.refresh_report("ptc-default")
    entry_id = str(report["source"].get("center_id") and anchor_store.read_registry("ptc-default")["current_entry_id"])
    anchor_store.revoke_entry("ptc-default", entry_id, {"reason": "stale kit"})

    with pytest.raises(PublicTrustCenterDistributionKitStateError, match="stale"):
        kit_store.export_kit("ptc-default")


def test_distribution_kit_stale_source_blocks_zip(tmp_path: Path, monkeypatch) -> None:
    _trust_store, anchor_store, _transparency_store, kit_store = _distribution_kit_fixture(tmp_path, monkeypatch)
    report = kit_store.refresh_report("ptc-default")
    kit_store.export_kit("ptc-default")
    entry_id = str(report["source"].get("center_id") and anchor_store.read_registry("ptc-default")["current_entry_id"])
    anchor_store.revoke_entry("ptc-default", entry_id, {"reason": "stale kit zip"})

    with pytest.raises(PublicTrustCenterDistributionKitStateError, match="stale"):
        kit_store.build_zip("ptc-default")


def _distribution_kit_fixture(tmp_path: Path, monkeypatch):
    _portfolio_id, trust_store, anchor_store, transparency_store = _anchor_transparency_fixture(tmp_path, monkeypatch)
    transparency_store.refresh_report("ptc-default")
    transparency_store.create_checkpoint("ptc-default")
    transparency_store.export_transparency("ptc-default")
    transparency_store.build_zip("ptc-default")
    transparency_report = verify_public_trust_center_anchor_transparency_package(
        transparency_store.zip_path("ptc-default"),
        strict=True,
        checkpoint_path=transparency_store.current_checkpoint_path("ptc-default"),
        anchor_registry_path=anchor_store.zip_path("ptc-default"),
        require_current_checkpoint=True,
        require_published_anchor=True,
        require_not_revoked=True,
    )
    write_public_trust_center_anchor_transparency_verification_report(transparency_report, transparency_store.verification_report_path("ptc-default"))
    trust_store.verify_zip(
        "ptc-default",
        {
            "strict": True,
            "require_delivery_readiness": False,
            "anchor_registry_path": anchor_store.zip_path("ptc-default"),
            "anchor_transparency_path": transparency_store.zip_path("ptc-default"),
            "anchor_checkpoint_path": transparency_store.current_checkpoint_path("ptc-default"),
            "require_anchor_registry_current": True,
            "require_anchor_published": True,
            "require_anchor_not_revoked": True,
            "require_anchor_transparency_current": True,
            "require_anchor_checkpoint": True,
        },
    )
    kit_store = PublicTrustCenterDistributionKitStore(
        trust_center_store=trust_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=transparency_store,
    )
    return trust_store, anchor_store, transparency_store, kit_store


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item["check_id"] for item in report["blockers"])


def _tamper_checkpoint(data: bytes) -> bytes:
    doc = json.loads(data.decode("utf-8"))
    doc["current_anchor_hash"] = "0" * 64
    return json.dumps(doc, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _spoof_kit_manifest(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "distribution-kit-manifest.json")
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = distribution_kit_manifest_hash(manifest)
    docs["distribution-kit-manifest.json"] = _doc_bytes(manifest)
