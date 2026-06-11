from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_attestation_accepted_evidence import _accepted_fixture

from song_agent.release_portfolio_governance_attestation_transparency import (
    ReleasePortfolioGovernanceAttestationTransparencyStateError,
    ReleasePortfolioGovernanceAttestationTransparencyStore,
    transparency_event_hash,
    transparency_feed_hash,
    transparency_manifest_hash,
    transparency_notice_hash,
    transparency_report_hash,
)
from song_agent.release_portfolio_governance_attestation_transparency_verifier import verify_release_portfolio_governance_attestation_transparency


def _transparency_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, portal_store, _review_store, accepted_store, imported = _accepted_fixture(tmp_path, monkeypatch)
    accepted_store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    accepted_store.export_evidence(portfolio_id)
    accepted_store.build_zip(portfolio_id)
    accepted_store.verify_evidence(portfolio_id, {"strict": True, "require_current": True})
    registry_store = portal_store.registry_store
    registry_store.export_registry(portfolio_id)
    registry_store.build_zip(portfolio_id)
    portal_store.refresh_report(portfolio_id)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    return portfolio_id, portal_store, accepted_store, store


def test_attestation_transparency_roundtrip_and_verifier(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, _accepted_store, store = _transparency_fixture(tmp_path, monkeypatch)

    feed = store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    manifest = store.export_transparency(portfolio_id)
    zip_info = store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_attestation_transparency(store.zip_path(portfolio_id), strict=True, require_current=True, require_accepted_evidence=True, require_contiguous_chain=True)
    stored_verification = store.verify_transparency(portfolio_id, {"strict": True, "require_current": True, "require_accepted_evidence": True, "require_contiguous_chain": True})
    notices = store.list_notices(portfolio_id)

    assert feed["status"] == "current"
    assert feed["events"][0]["event_type"] == "registry_current_published"
    assert feed["summary"]["external_review_status"] == "accepted"
    assert manifest["package_type"] == "release_portfolio_governance_attestation_transparency"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert stored_verification["status"] == "passed"
    assert len(notices) >= 3
    assert store.get_notice(portfolio_id, notices[0]["notice_id"])["notice_id"] == notices[0]["notice_id"]


def test_attestation_transparency_verifier_catches_tamper_and_paths(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, _accepted_store, store = _transparency_fixture(tmp_path, monkeypatch)
    store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    store.export_transparency(portfolio_id)
    store.build_zip(portfolio_id)
    source_zip = store.zip_path(portfolio_id)

    event_tamper = _rewrite_zip(source_zip, tmp_path / "event-tamper.zip", _tamper_event_and_resign)
    data_tamper = _rewrite_zip(source_zip, tmp_path / "data-tamper.zip", _tamper_package_fingerprint_and_resign)
    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    spoof = _rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_manifest_zip_entries)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key="sk-secret-value" C:\\Users\\demo\\githubkey.txt\n'}))

    assert any(item["check_id"] == "transparency_event_chain_contiguous" for item in verify_release_portfolio_governance_attestation_transparency(event_tamper, strict=True, require_contiguous_chain=True)["blockers"])
    assert any(item["check_id"] == "transparency_data_package_registry_zip_sha256" for item in verify_release_portfolio_governance_attestation_transparency(data_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "transparency_zip_duplicate_entries" for item in verify_release_portfolio_governance_attestation_transparency(duplicate, strict=True)["blockers"])
    assert any(item["check_id"] == "transparency_zip_entry_path_safe" for item in verify_release_portfolio_governance_attestation_transparency(dangerous, strict=True)["blockers"])
    assert any(item["check_id"] == "transparency_zip_entry_path_safe" for item in verify_release_portfolio_governance_attestation_transparency(backslash, strict=True)["blockers"])
    assert any(item["check_id"] == "transparency_zip_no_nested_or_internal_entries" for item in verify_release_portfolio_governance_attestation_transparency(case_musicforge, strict=True)["blockers"])
    assert any(item["check_id"] == "transparency_zip_no_nested_or_internal_entries" for item in verify_release_portfolio_governance_attestation_transparency(nested, strict=True)["blockers"])
    assert any(item["check_id"] == "transparency_manifest_zip_entries_reference_only" for item in verify_release_portfolio_governance_attestation_transparency(spoof, strict=True)["blockers"])
    assert any(item["check_id"] == "transparency_redaction_scan" for item in verify_release_portfolio_governance_attestation_transparency(redaction, strict=True)["blockers"])


def test_attestation_transparency_verifier_rejects_full_resigned_event_semantics(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, _accepted_store, store = _transparency_fixture(tmp_path, monkeypatch)
    store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    store.export_transparency(portfolio_id)
    store.build_zip(portfolio_id)

    event_full_resign = _rewrite_zip(store.zip_path(portfolio_id), tmp_path / "event-full-resign.zip", _full_resign_event_semantics)
    report = verify_release_portfolio_governance_attestation_transparency(event_full_resign, strict=True, require_current=True, require_accepted_evidence=True, require_contiguous_chain=True)

    assert any(item["check_id"] == "transparency_event_semantics_match" for item in report["blockers"])


def test_attestation_transparency_verifier_rejects_full_resigned_notice_semantics(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, _accepted_store, store = _transparency_fixture(tmp_path, monkeypatch)
    store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    store.export_transparency(portfolio_id)
    store.build_zip(portfolio_id)

    notice_full_resign = _rewrite_zip(store.zip_path(portfolio_id), tmp_path / "notice-full-resign.zip", _full_resign_notice_semantics)
    report = verify_release_portfolio_governance_attestation_transparency(notice_full_resign, strict=True, require_current=True, require_accepted_evidence=True, require_contiguous_chain=True)

    assert any(item["check_id"] == "transparency_notice_semantics_match" for item in report["blockers"])


def test_attestation_transparency_stale_feed_blocks_export_and_zip(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, portal_store, _accepted_store, store = _transparency_fixture(tmp_path, monkeypatch)
    store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    portal_store.zip_path(portfolio_id).write_bytes(portal_store.zip_path(portfolio_id).read_bytes() + b"changed")

    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyStateError, match="stale"):
        store.export_transparency(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyStateError, match="stale"):
        store.build_zip(portfolio_id)


def test_attestation_transparency_blocks_delete_rebuild_same_state(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, _accepted_store, store = _transparency_fixture(tmp_path, monkeypatch)
    store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    store.export_transparency(portfolio_id)
    store.build_zip(portfolio_id)

    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyStateError, match="already exists"):
        store.export_transparency(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyStateError, match="already exists"):
        store.build_zip(portfolio_id)
    shutil.rmtree(store.export_dir(portfolio_id))
    store.zip_path(portfolio_id).unlink()
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyStateError, match="already exists"):
        store.export_transparency(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyStateError, match="already exists"):
        store.build_zip(portfolio_id)


def _rewrite_zip(source_zip: Path, target_zip: Path, mutate) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
    mutate(docs)
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name, data in docs.items():
            dst.writestr(name, data)
    return target_zip


def _duplicate_zip(source_zip: Path, target_zip: Path) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = [(info.filename, src.read(info.filename)) for info in src.infolist()]
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name, data in docs:
            dst.writestr(name, data)
        dst.writestr(docs[0][0], docs[0][1])
    return target_zip


def _backslash_zip(target_zip: Path) -> Path:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    target_zip.write_bytes(target_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))
    return target_zip


def _tamper_event_and_resign(docs: dict[str, bytes]) -> None:
    feed = _read_doc(docs, "transparency-feed.json")
    manifest = _read_doc(docs, "transparency-manifest.json")
    feed["events"][0]["summary"]["message"] = "tampered"
    # Re-sign feed but leave the event hash itself stale.
    feed["integrity_hash"] = transparency_feed_hash(feed)
    docs["transparency-feed.json"] = _doc_bytes(feed)
    _sync_manifest_file(manifest, "transparency-feed.json", docs["transparency-feed.json"])
    manifest["feed"]["integrity_hash"] = feed["integrity_hash"]
    manifest["integrity_hash"] = transparency_manifest_hash(manifest)
    docs["transparency-manifest.json"] = _doc_bytes(manifest)


def _tamper_package_fingerprint_and_resign(docs: dict[str, bytes]) -> None:
    package = _read_doc(docs, "data/package-fingerprints.json")
    manifest = _read_doc(docs, "transparency-manifest.json")
    package["registry_zip_sha256"] = "0" * 64
    docs["data/package-fingerprints.json"] = _doc_bytes(package)
    _sync_manifest_file(manifest, "data/package-fingerprints.json", docs["data/package-fingerprints.json"])
    manifest["integrity_hash"] = transparency_manifest_hash(manifest)
    docs["transparency-manifest.json"] = _doc_bytes(manifest)


def _full_resign_event_semantics(docs: dict[str, bytes]) -> None:
    feed = _read_doc(docs, "transparency-feed.json")
    first = feed["events"][0]
    first["event_type"] = "registry_current_revoked"
    first["severity"] = "warning"
    first["summary"]["public_references"] = {"current_entry_id": first["source"].get("registry_current_entry_id")}
    _resign_event_chain(feed)
    _resign_feed_report_manifest(docs, feed)


def _full_resign_notice_semantics(docs: dict[str, bytes]) -> None:
    feed = _read_doc(docs, "transparency-feed.json")
    notice = feed["notices"][0]
    notice["notice_type"] = "registry_current_revoked"
    notice["severity"] = "warning"
    notice["public_references"] = {"current_entry_id": feed["events"][0]["source"].get("registry_current_entry_id")}
    notice["integrity_hash"] = transparency_notice_hash(notice)
    docs[f"notices/{notice['notice_id']}.json"] = _doc_bytes(notice)
    _resign_feed_report_manifest(docs, feed)


def _resign_event_chain(feed: dict) -> None:
    previous = ""
    for event in feed.get("events", []):
        event["previous_event_hash"] = previous
        event["event_hash"] = transparency_event_hash(event)
        previous = event["event_hash"]


def _resign_feed_report_manifest(docs: dict[str, bytes], feed: dict) -> None:
    report = _read_doc(docs, "transparency-report.json")
    manifest = _read_doc(docs, "transparency-manifest.json")
    feed["integrity_hash"] = transparency_feed_hash(feed)
    report["source"]["feed_hash"] = feed["integrity_hash"]
    report["source_hash"] = _stable_hash(report["source"])
    report["summary"] = feed.get("summary", {})
    report["integrity_hash"] = transparency_report_hash(report)
    docs["transparency-feed.json"] = _doc_bytes(feed)
    docs["transparency-report.json"] = _doc_bytes(report)
    _sync_manifest_file(manifest, "transparency-feed.json", docs["transparency-feed.json"])
    _sync_manifest_file(manifest, "transparency-report.json", docs["transparency-report.json"])
    manifest["feed"]["integrity_hash"] = feed["integrity_hash"]
    manifest["report"]["integrity_hash"] = report["integrity_hash"]
    manifest["report"]["source_hash"] = report["source_hash"]
    for notice in feed.get("notices", []):
        notice_path = f"notices/{notice.get('notice_id')}.json"
        if notice_path in docs:
            _sync_manifest_file(manifest, notice_path, docs[notice_path])
    manifest["integrity_hash"] = transparency_manifest_hash(manifest)
    docs["transparency-manifest.json"] = _doc_bytes(manifest)


def _stable_hash(value: dict) -> str:
    from song_agent.releases import stable_hash

    return stable_hash(value)


def _spoof_manifest_zip_entries(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "transparency-manifest.json")
    docs["extra.txt"] = b"extra"
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = transparency_manifest_hash(manifest)
    docs["transparency-manifest.json"] = _doc_bytes(manifest)


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
