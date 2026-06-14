from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tests.test_public_trust_center import _backslash_zip, _duplicate_zip, _rewrite_zip, _sync_manifest_file, _trust_center_fixture
from tests.test_public_trust_center_anchor_registry import _doc_bytes, _read_doc

from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
from song_agent.public_trust_center_anchor_registry_verifier import verify_public_trust_center_anchor_registry_package, write_public_trust_center_anchor_registry_verification_report
from song_agent.public_trust_center_anchor_transparency import (
    PublicTrustCenterAnchorTransparencyStateError,
    PublicTrustCenterAnchorTransparencyStore,
    anchor_checkpoint_hash,
    anchor_transparency_event_hash,
    anchor_transparency_manifest_hash,
    anchor_transparency_report_hash,
)
from song_agent.public_trust_center_anchor_transparency_verifier import verify_public_trust_center_anchor_transparency_package
from song_agent.public_trust_center_verifier import verify_public_trust_center_package
from song_agent.releases import stable_hash


def test_anchor_transparency_roundtrip_and_ptc_checkpoint_binding(tmp_path: Path, monkeypatch) -> None:
    _portfolio_id, trust_store, anchor_store, transparency_store = _anchor_transparency_fixture(tmp_path, monkeypatch)

    report = transparency_store.refresh_report("ptc-default")
    checkpoint = transparency_store.create_checkpoint("ptc-default")
    manifest = transparency_store.export_transparency("ptc-default")
    zip_info = transparency_store.build_zip("ptc-default")
    verification = verify_public_trust_center_anchor_transparency_package(
        transparency_store.zip_path("ptc-default"),
        strict=True,
        checkpoint_path=transparency_store.current_checkpoint_path("ptc-default"),
        anchor_registry_path=anchor_store.zip_path("ptc-default"),
        require_current_checkpoint=True,
        require_published_anchor=True,
        require_not_revoked=True,
    )
    ptc_verification = verify_public_trust_center_package(
        trust_store.zip_path("ptc-default"),
        strict=True,
        require_delivery_readiness=True,
        delivery_anchor_path=trust_store.delivery_anchor_path("ptc-default"),
        anchor_registry_path=anchor_store.zip_path("ptc-default"),
        anchor_transparency_path=transparency_store.zip_path("ptc-default"),
        anchor_checkpoint_path=transparency_store.current_checkpoint_path("ptc-default"),
        require_anchor_registry_current=True,
        require_anchor_published=True,
        require_anchor_not_revoked=True,
        require_anchor_transparency_current=True,
        require_anchor_checkpoint=True,
    )

    assert report["status"] == "current"
    assert checkpoint["latest_event_hash"] == report["source"]["latest_event_hash"]
    assert manifest["package_type"] == "musicforge_public_trust_center_anchor_transparency"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert ptc_verification["status"] == "failed"
    assert any(item["check_id"] == "ptc_anchor_transparency_verification_status" for item in ptc_verification["checks"])
    assert all(not item["check_id"].startswith("ptc_anchor_transparency") for item in ptc_verification["blockers"])

    transparency_store.zip_path("ptc-default").unlink()
    with pytest.raises(PublicTrustCenterAnchorTransparencyStateError, match="ZIP already exists"):
        transparency_store.build_zip("ptc-default")
    shutil.rmtree(transparency_store.export_dir("ptc-default"))
    with pytest.raises(PublicTrustCenterAnchorTransparencyStateError, match="export already exists"):
        transparency_store.export_transparency("ptc-default")


def test_anchor_transparency_verifier_rejects_tamper_and_zip_edges(tmp_path: Path, monkeypatch) -> None:
    _portfolio_id, _trust_store, anchor_store, transparency_store = _anchor_transparency_fixture(tmp_path, monkeypatch)
    transparency_store.refresh_report("ptc-default")
    transparency_store.export_transparency("ptc-default")
    transparency_store.build_zip("ptc-default")
    source_zip = transparency_store.zip_path("ptc-default")

    ledger_tamper = _rewrite_zip(source_zip, tmp_path / "ledger-tamper.zip", _tamper_ledger_first_event)
    full_resign = _rewrite_zip(source_zip, tmp_path / "full-resign.zip", _tamper_report_ledger_full_resign_without_checkpoint)
    checkpoint_tamper = _rewrite_zip(source_zip, tmp_path / "checkpoint-tamper.zip", _tamper_checkpoint_anchor)
    registry_summary_tamper = _rewrite_zip(source_zip, tmp_path / "registry-summary-tamper.zip", _tamper_registry_verification_summary)
    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    spoof = _rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_transparency_manifest)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n'}))

    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(ledger_tamper, strict=True), "ptcat_ledger_hash")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(full_resign, strict=True), "ptcat_current_checkpoint_latest_event")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(checkpoint_tamper, strict=True), "ptcat_current_checkpoint_current_anchor_hash")
    assert _has_blocker(
        verify_public_trust_center_anchor_transparency_package(registry_summary_tamper, strict=True, anchor_registry_path=anchor_store.zip_path("ptc-default")),
        "ptcat_registry_verification_zip_sha256",
    )
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(duplicate, strict=True), "ptcat_zip_duplicate_entries")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(dangerous, strict=True), "ptcat_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(backslash, strict=True), "ptcat_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(case_musicforge, strict=True), "ptcat_zip_no_nested_internal_entries")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(nested, strict=True), "ptcat_zip_no_nested_internal_entries")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(spoof, strict=True), "ptcat_manifest_zip_entries_reference_only")
    assert _has_blocker(verify_public_trust_center_anchor_transparency_package(redaction, strict=True), "ptcat_redaction_scan")


def test_anchor_transparency_export_rejects_current_registry_stale(tmp_path: Path, monkeypatch) -> None:
    _portfolio_id, _trust_store, anchor_store, transparency_store = _anchor_transparency_fixture(tmp_path, monkeypatch)
    report = transparency_store.refresh_report("ptc-default")
    entry_id = str(report["source"]["current_entry_id"])
    anchor_store.revoke_entry("ptc-default", entry_id, {"reason": "stale transparency export"})

    with pytest.raises(PublicTrustCenterAnchorTransparencyStateError, match="stale"):
        transparency_store.export_transparency("ptc-default")


def test_anchor_transparency_zip_rejects_current_registry_stale(tmp_path: Path, monkeypatch) -> None:
    _portfolio_id, _trust_store, anchor_store, transparency_store = _anchor_transparency_fixture(tmp_path, monkeypatch)
    report = transparency_store.refresh_report("ptc-default")
    transparency_store.export_transparency("ptc-default")
    entry_id = str(report["source"]["current_entry_id"])
    anchor_store.revoke_entry("ptc-default", entry_id, {"reason": "stale transparency zip"})

    with pytest.raises(PublicTrustCenterAnchorTransparencyStateError, match="stale"):
        transparency_store.build_zip("ptc-default")


def _anchor_transparency_fixture(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    portfolio_id, _ack_store, trust_store = _trust_center_fixture(tmp_path, monkeypatch)
    trust_store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    trust_store.export_center("ptc-default")
    trust_store.build_zip("ptc-default")
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    entry = anchor_store.register_current_anchor("ptc-default", {"reason": "register transparency anchor"})["entry"]
    anchor_store.publish_entry("ptc-default", entry["entry_id"], {"reason": "publish transparency anchor"})
    anchor_store.refresh_report("ptc-default")
    anchor_store.export_registry("ptc-default")
    anchor_store.build_zip("ptc-default")
    registry_verification = verify_public_trust_center_anchor_registry_package(anchor_store.zip_path("ptc-default"), strict=True, require_current=True, require_anchor_published=True, require_anchor_not_revoked=True)
    write_public_trust_center_anchor_registry_verification_report(registry_verification, anchor_store.verification_report_path("ptc-default"))
    transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    return portfolio_id, trust_store, anchor_store, transparency_store


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item["check_id"] for item in report["blockers"])


def _sync_transparency_manifest_file(manifest: dict, path: str, data: bytes) -> None:
    _sync_manifest_file(manifest, path, data)


def _tamper_ledger_first_event(docs: dict[str, bytes]) -> None:
    lines = docs["ledger.jsonl"].decode("utf-8").splitlines()
    event = json.loads(lines[0])
    event["event_type"] = "anchor_revoked"
    event["event_hash"] = anchor_transparency_event_hash(event)
    lines[0] = json.dumps(event, ensure_ascii=False, sort_keys=True)
    docs["ledger.jsonl"] = ("\n".join(lines) + "\n").encode("utf-8")
    manifest = _read_doc(docs, "anchor-transparency-manifest.json")
    _sync_transparency_manifest_file(manifest, "ledger.jsonl", docs["ledger.jsonl"])
    manifest["integrity_hash"] = anchor_transparency_manifest_hash(manifest)
    docs["anchor-transparency-manifest.json"] = _doc_bytes(manifest)


def _tamper_report_ledger_full_resign_without_checkpoint(docs: dict[str, bytes]) -> None:
    events = [json.loads(line) for line in docs["ledger.jsonl"].decode("utf-8").splitlines() if line.strip()]
    manifest = _read_doc(docs, "anchor-transparency-manifest.json")
    report = _read_doc(docs, "anchor-transparency-report.json")
    events[0]["event_type"] = "anchor_revoked"
    previous = None
    for index, event in enumerate(events, start=1):
        event["sequence"] = index
        event["previous_event_hash"] = previous
        event["event_hash"] = anchor_transparency_event_hash(event)
        previous = event["event_hash"]
    docs["ledger.jsonl"] = ("".join(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n" for event in events)).encode("utf-8")
    report["source"]["latest_event_hash"] = events[-1]["event_hash"]
    report["source"]["latest_sequence"] = events[-1]["sequence"]
    report["source"]["ledger_hash"] = stable_hash(events)
    report["source_hash"] = stable_hash(report["source"])
    report["integrity_hash"] = anchor_transparency_report_hash(report)
    docs["anchor-transparency-report.json"] = _doc_bytes(report)
    _sync_transparency_manifest_file(manifest, "ledger.jsonl", docs["ledger.jsonl"])
    _sync_transparency_manifest_file(manifest, "anchor-transparency-report.json", docs["anchor-transparency-report.json"])
    manifest["source_hash"] = report["source_hash"]
    manifest["report"]["source_hash"] = report["source_hash"]
    manifest["report"]["integrity_hash"] = report["integrity_hash"]
    manifest["ledger"]["hash"] = report["source"]["ledger_hash"]
    manifest["ledger"]["latest_event_hash"] = report["source"]["latest_event_hash"]
    manifest["integrity_hash"] = anchor_transparency_manifest_hash(manifest)
    docs["anchor-transparency-manifest.json"] = _doc_bytes(manifest)


def _tamper_checkpoint_anchor(docs: dict[str, bytes]) -> None:
    checkpoint = _read_doc(docs, "checkpoints/ptc-anchor-checkpoint-current.json")
    manifest = _read_doc(docs, "anchor-transparency-manifest.json")
    checkpoint["current_anchor_hash"] = "f" * 64
    checkpoint["signature"]["payload_hash"] = stable_hash({key: value for key, value in checkpoint.items() if key not in {"signature", "integrity_hash"}})
    checkpoint["signature"]["signature_hash"] = stable_hash({key: value for key, value in checkpoint["signature"].items() if key != "signature_hash"})
    checkpoint["integrity_hash"] = anchor_checkpoint_hash(checkpoint)
    docs["checkpoints/ptc-anchor-checkpoint-current.json"] = _doc_bytes(checkpoint)
    _sync_transparency_manifest_file(manifest, "checkpoints/ptc-anchor-checkpoint-current.json", docs["checkpoints/ptc-anchor-checkpoint-current.json"])
    manifest.setdefault("checkpoint", {})["integrity_hash"] = checkpoint["integrity_hash"]
    manifest["integrity_hash"] = anchor_transparency_manifest_hash(manifest)
    docs["anchor-transparency-manifest.json"] = _doc_bytes(manifest)


def _tamper_registry_verification_summary(docs: dict[str, bytes]) -> None:
    summary = _read_doc(docs, "registry-verification-summary.json")
    manifest = _read_doc(docs, "anchor-transparency-manifest.json")
    summary["zip_sha256"] = "0" * 64
    docs["registry-verification-summary.json"] = _doc_bytes(summary)
    _sync_transparency_manifest_file(manifest, "registry-verification-summary.json", docs["registry-verification-summary.json"])
    manifest.setdefault("registry_verification_summary", {})["hash"] = stable_hash(summary)
    manifest["integrity_hash"] = anchor_transparency_manifest_hash(manifest)
    docs["anchor-transparency-manifest.json"] = _doc_bytes(manifest)


def _spoof_transparency_manifest(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "anchor-transparency-manifest.json")
    manifest.setdefault("zip", {})["entries"] = list(manifest.get("zip", {}).get("entries") or []) + ["extra.txt"]
    manifest["integrity_hash"] = anchor_transparency_manifest_hash(manifest)
    docs["anchor-transparency-manifest.json"] = _doc_bytes(manifest)
    docs["extra.txt"] = b"extra"
