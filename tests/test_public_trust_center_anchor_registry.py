from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.test_public_trust_center import _backslash_zip, _duplicate_zip, _rewrite_zip, _trust_center_fixture

from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStateError, PublicTrustCenterAnchorRegistryStore, anchor_registry_manifest_hash
from song_agent.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package
from song_agent.public_trust_center_verifier import verify_public_trust_center_package
from song_agent.releases import stable_hash


def test_anchor_registry_roundtrip_and_ptc_binding(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, trust_store = _trust_center_fixture(tmp_path, monkeypatch)
    release = trust_store.release_store.create_release({"name": "Anchor Registry Fixture", "release_type": "demo_pack"})
    trust_store.release_store.write_signoff(release.release_id, {"status": "signed", "signed_by": "tester", "signed_at": "2026-06-13T00:00:00+00:00"})
    trust_store.release_store.update_signoff_summary(release.release_id, {"status": "signed"})
    trust_store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "release_ids": [release.release_id], "include_all_releases": False, "include_all_portfolios": False})
    trust_store.export_center("ptc-default")
    trust_store.build_zip("ptc-default")
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)

    registered = anchor_store.register_current_anchor("ptc-default", {"reason": "register anchor for tests"})
    entry_id = registered["entry"]["entry_id"]
    published = anchor_store.publish_entry("ptc-default", entry_id, {"reason": "publish anchor for tests"})
    report = anchor_store.refresh_report("ptc-default")
    manifest = anchor_store.export_registry("ptc-default")
    zip_info = anchor_store.build_zip("ptc-default")
    registry_verification = verify_public_trust_center_anchor_registry_package(anchor_store.zip_path("ptc-default"), strict=True, require_current=True, require_anchor_published=True, require_anchor_not_revoked=True)
    ptc_verification = verify_public_trust_center_package(
        trust_store.zip_path("ptc-default"),
        strict=True,
        require_distribution_ready=True,
        delivery_anchor_path=trust_store.delivery_anchor_path("ptc-default"),
        anchor_registry_path=anchor_store.zip_path("ptc-default"),
        require_anchor_registry_current=True,
        require_anchor_published=True,
        require_anchor_not_revoked=True,
    )

    assert published["registry"]["current_entry_id"] == entry_id
    assert report["status"] == "passed"
    assert manifest["package_type"] == "musicforge_public_trust_center_anchor_registry"
    assert zip_info["sha256"]
    assert registry_verification["status"] == "passed"
    assert ptc_verification["status"] == "failed"
    assert any(item["check_id"] == "ptc_require_distribution_ready" for item in ptc_verification["blockers"])
    assert not any(item["check_id"].startswith("ptc_anchor_registry") and item["status"] == "failed" for item in ptc_verification["checks"])
    anchor_store.zip_path("ptc-default").unlink()
    with pytest.raises(PublicTrustCenterAnchorRegistryStateError, match="ZIP already exists"):
        anchor_store.build_zip("ptc-default")
    shutil.rmtree(anchor_store.export_dir("ptc-default"))
    with pytest.raises(PublicTrustCenterAnchorRegistryStateError, match="export already exists"):
        anchor_store.export_registry("ptc-default")


def test_anchor_registry_verifier_rejects_tamper_and_zip_edges(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, trust_store = _trust_center_fixture(tmp_path, monkeypatch)
    trust_store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    trust_store.export_center("ptc-default")
    trust_store.build_zip("ptc-default")
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    entry = anchor_store.register_current_anchor("ptc-default", {"reason": "register anchor"})["entry"]
    anchor_store.publish_entry("ptc-default", entry["entry_id"], {"reason": "publish anchor"})
    anchor_store.refresh_report("ptc-default")
    anchor_store.export_registry("ptc-default")
    anchor_store.build_zip("ptc-default")
    source_zip = anchor_store.zip_path("ptc-default")

    chain_tamper = _rewrite_zip(source_zip, tmp_path / "chain-tamper.zip", _tamper_anchor_registry_chain)
    signature_tamper = _rewrite_zip(source_zip, tmp_path / "signature-tamper.zip", _tamper_anchor_registry_signature)
    anchor_tamper = _rewrite_zip(source_zip, tmp_path / "anchor-tamper.zip", _tamper_anchor_registry_current_anchor)
    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    spoof = _rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_anchor_registry_manifest)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n'}))

    chain_report = verify_public_trust_center_anchor_registry_package(chain_tamper, strict=True)
    assert _has_blocker(chain_report, "ptcar_chain_events_match_registry") or _has_blocker(chain_report, "ptcar_chain_summary_event_count")
    assert _has_blocker(verify_public_trust_center_anchor_registry_package(signature_tamper, strict=True), "_signature")
    assert _has_blocker(verify_public_trust_center_anchor_registry_package(anchor_tamper, strict=True), "ptcar_current_anchor_matches_entry")
    assert _has_blocker(verify_public_trust_center_anchor_registry_package(duplicate, strict=True), "ptcar_zip_duplicate_entries")
    assert _has_blocker(verify_public_trust_center_anchor_registry_package(backslash, strict=True), "ptcar_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_anchor_registry_package(case_musicforge, strict=True), "ptcar_zip_no_nested_internal_entries")
    assert _has_blocker(verify_public_trust_center_anchor_registry_package(spoof, strict=True), "ptcar_manifest_zip_entries_reference_only")
    assert _has_blocker(verify_public_trust_center_anchor_registry_package(redaction, strict=True), "ptcar_redaction_scan")


def test_anchor_registry_revoked_current_fails_ptc_requirement(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, trust_store = _trust_center_fixture(tmp_path, monkeypatch)
    trust_store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    trust_store.export_center("ptc-default")
    trust_store.build_zip("ptc-default")
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    entry = anchor_store.register_current_anchor("ptc-default", {"reason": "register anchor"})["entry"]
    anchor_store.publish_entry("ptc-default", entry["entry_id"], {"reason": "publish anchor"})
    anchor_store.revoke_entry("ptc-default", entry["entry_id"], {"reason": "revoke anchor for test"})
    anchor_store.refresh_report("ptc-default")
    anchor_store.export_registry("ptc-default")
    anchor_store.build_zip("ptc-default")

    verification = verify_public_trust_center_package(
        trust_store.zip_path("ptc-default"),
        strict=True,
        require_delivery_readiness=True,
        delivery_anchor_path=trust_store.delivery_anchor_path("ptc-default"),
        anchor_registry_path=anchor_store.zip_path("ptc-default"),
        require_anchor_registry_current=True,
        require_anchor_not_revoked=True,
    )

    assert verification["status"] == "failed"
    assert any(item["check_id"] in {"ptc_anchor_registry_current_anchor", "ptc_anchor_registry_not_revoked", "ptcar_require_current"} for item in verification["blockers"])


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item["check_id"] for item in report["blockers"])


def _read_doc(docs: dict[str, bytes], name: str) -> dict:
    return json.loads(docs[name].decode("utf-8"))


def _doc_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _sync_manifest_file(manifest: dict, path: str, data: bytes) -> None:
    for item in manifest.get("files", []) if isinstance(manifest.get("files"), list) else []:
        if isinstance(item, dict) and item.get("path") == path:
            item["size_bytes"] = len(data)
            item["sha256"] = __import__("hashlib").sha256(data).hexdigest()


def _tamper_anchor_registry_chain(docs: dict[str, bytes]) -> None:
    chain = _read_doc(docs, "chain-of-custody.json")
    manifest = _read_doc(docs, "anchor-registry-manifest.json")
    chain.setdefault("summary", {})["event_count"] = 999
    chain["integrity_hash"] = stable_hash({key: value for key, value in chain.items() if key != "integrity_hash"})
    docs["chain-of-custody.json"] = _doc_bytes(chain)
    manifest.setdefault("chain_of_custody", {})["integrity_hash"] = chain["integrity_hash"]
    _sync_manifest_file(manifest, "chain-of-custody.json", docs["chain-of-custody.json"])
    manifest["integrity_hash"] = anchor_registry_manifest_hash(manifest)
    docs["anchor-registry-manifest.json"] = _doc_bytes(manifest)


def _tamper_anchor_registry_signature(docs: dict[str, bytes]) -> None:
    registry = _read_doc(docs, "registry.json")
    manifest = _read_doc(docs, "anchor-registry-manifest.json")
    entry = registry["entries"][0]
    entry.setdefault("signature", {})["key_id"] = "tampered-key"
    entry["integrity_hash"] = stable_hash({key: value for key, value in entry.items() if key != "integrity_hash"})
    registry["integrity_hash"] = stable_hash({key: value for key, value in registry.items() if key not in {"integrity_hash", "updated_at", "events"}})
    docs["registry.json"] = _doc_bytes(registry)
    docs[f"entries/{entry['entry_id']}.json"] = _doc_bytes(entry)
    _sync_manifest_file(manifest, "registry.json", docs["registry.json"])
    _sync_manifest_file(manifest, f"entries/{entry['entry_id']}.json", docs[f"entries/{entry['entry_id']}.json"])
    manifest.setdefault("registry", {})["integrity_hash"] = registry["integrity_hash"]
    manifest["integrity_hash"] = anchor_registry_manifest_hash(manifest)
    docs["anchor-registry-manifest.json"] = _doc_bytes(manifest)


def _tamper_anchor_registry_current_anchor(docs: dict[str, bytes]) -> None:
    current = _read_doc(docs, "current-anchor.json")
    manifest = _read_doc(docs, "anchor-registry-manifest.json")
    current["zip_sha256"] = "f" * 64
    current["anchor_hash"] = stable_hash({key: value for key, value in current.items() if key != "anchor_hash"})
    docs["current-anchor.json"] = _doc_bytes(current)
    _sync_manifest_file(manifest, "current-anchor.json", docs["current-anchor.json"])
    manifest["integrity_hash"] = anchor_registry_manifest_hash(manifest)
    docs["anchor-registry-manifest.json"] = _doc_bytes(manifest)


def _spoof_anchor_registry_manifest(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "anchor-registry-manifest.json")
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = anchor_registry_manifest_hash(manifest)
    docs["anchor-registry-manifest.json"] = _doc_bytes(manifest)
    docs["extra.txt"] = b"extra"
