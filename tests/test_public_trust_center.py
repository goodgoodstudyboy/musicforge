from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_attestation_transparency_acknowledgement import _accepted_response, _ack_fixture

from song_agent.public_trust_center import (
    PublicTrustCenterStateError,
    PublicTrustCenterStore,
    public_trust_center_manifest_hash,
    public_trust_center_report_hash,
)
from song_agent.public_trust_center_verifier import verify_public_trust_center_package
from song_agent.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal, write_release_portfolio_governance_attestation_portal_verification_report
from song_agent.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry, write_release_portfolio_governance_attestation_registry_verification_report
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import (
    verify_release_portfolio_governance_attestation_transparency_acknowledgement_package,
    write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
)
from song_agent.releases import ReleaseStore, stable_hash


def _trust_center_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, _transparency_store, ack_store = _ack_fixture(tmp_path, monkeypatch)
    registry_store = ack_store.transparency_store.registry_store
    if not registry_store.read_registry(portfolio_id, default={}).get("current_entry_id"):
        entry = registry_store.register_current_attestation(portfolio_id)["entry"]
        registry_store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "tester"})
    registry_store.refresh_report(portfolio_id)
    if not (registry_store.export_dir(portfolio_id) / "manifest.json").exists():
        registry_store.export_registry(portfolio_id)
    if not registry_store.zip_path(portfolio_id).exists():
        registry_store.build_zip(portfolio_id)
    registry_report = verify_release_portfolio_governance_attestation_registry(registry_store.zip_path(portfolio_id), strict=True, require_current=True, require_published=True)
    write_release_portfolio_governance_attestation_registry_verification_report(registry_report, registry_store.verification_report_path(portfolio_id))
    portal_store = ack_store.transparency_store.portal_store
    portal_store.refresh_report(portfolio_id)
    if not (portal_store.export_dir(portfolio_id) / "portal-manifest.json").exists():
        portal_store.export_portal(portfolio_id)
    if not portal_store.zip_path(portfolio_id).exists():
        portal_store.build_zip(portfolio_id)
    portal_report = verify_release_portfolio_governance_attestation_portal(portal_store.zip_path(portfolio_id), strict=True, require_current=True, require_registry=True, require_attestation=True)
    write_release_portfolio_governance_attestation_portal_verification_report(portal_report, portal_store.verification_report_path(portfolio_id))
    ack_store.transparency_store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    ack_store.transparency_store.export_transparency(portfolio_id)
    ack_store.transparency_store.build_zip(portfolio_id)
    ack_store.transparency_store.verify_transparency(portfolio_id, {"strict": True, "require_current": True, "require_accepted_evidence": True, "require_contiguous_chain": True})
    pack = ack_store.refresh_pack(portfolio_id)
    imported = ack_store.import_response(portfolio_id, {"content": _accepted_response(pack)})
    ack_store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    ack_store.export_evidence(portfolio_id)
    ack_store.build_evidence_zip(portfolio_id)
    ack_report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(ack_store.evidence_zip_path(portfolio_id), strict=True, require_accepted=True)
    write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(ack_report, ack_store.evidence_verification_report_path(portfolio_id))
    store = PublicTrustCenterStore(
        release_store=ReleaseStore(),
        portfolio_store=ack_store.transparency_store.attestation_store.portfolio_store,
        registry_store=ack_store.transparency_store.registry_store,
        portal_store=ack_store.transparency_store.portal_store,
        transparency_store=ack_store.transparency_store,
        acknowledgement_store=ack_store,
    )
    return portfolio_id, ack_store, store


def test_public_trust_center_roundtrip_and_verifier(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _ack_store, store = _trust_center_fixture(tmp_path, monkeypatch)

    report = store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    manifest = store.export_center("ptc-default")
    zip_info = store.build_zip("ptc-default")
    verification = verify_public_trust_center_package(store.zip_path("ptc-default"), strict=True, require_registry_current=True, require_portal_current=True, require_transparency_current=True, require_acknowledgement_current=True)

    assert report["status"] == "passed"
    assert report["summary"]["portfolio_count"] == 1
    assert manifest["package_type"] == "musicforge_public_trust_center"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    with zipfile.ZipFile(store.zip_path("ptc-default"), "r") as archive:
        names = archive.namelist()
        index = archive.read("index.html").decode("utf-8")
    assert "trust-center-manifest.json" in names
    assert "data/package-index.json" in names
    assert "data/public-package-verification-index.json" in names
    assert "nested/fake.zip" not in names
    assert "<script" not in index.lower()


def test_public_trust_center_stale_source_blocks_export_and_zip(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, ack_store, store = _trust_center_fixture(tmp_path, monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    ack_store.evidence_zip_path(portfolio_id).write_bytes(ack_store.evidence_zip_path(portfolio_id).read_bytes() + b"changed")

    with pytest.raises(PublicTrustCenterStateError, match="stale"):
        store.export_center("ptc-default")
    with pytest.raises(PublicTrustCenterStateError, match="stale"):
        store.build_zip("ptc-default")


def test_public_trust_center_blocks_delete_rebuild_same_state(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _ack_store, store = _trust_center_fixture(tmp_path, monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    store.export_center("ptc-default")
    store.build_zip("ptc-default")

    with pytest.raises(PublicTrustCenterStateError, match="already exists"):
        store.export_center("ptc-default")
    with pytest.raises(PublicTrustCenterStateError, match="already exists"):
        store.build_zip("ptc-default")
    shutil.rmtree(store.export_dir("ptc-default"))
    store.zip_path("ptc-default").unlink()
    with pytest.raises(PublicTrustCenterStateError, match="already exists"):
        store.export_center("ptc-default")
    with pytest.raises(PublicTrustCenterStateError, match="already exists"):
        store.build_zip("ptc-default")


def test_public_trust_center_verifier_catches_full_resign_and_paths(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _ack_store, store = _trust_center_fixture(tmp_path, monkeypatch)
    store.refresh_report("ptc-default", {"portfolio_ids": [portfolio_id], "include_all_releases": False, "include_all_portfolios": False})
    store.export_center("ptc-default")
    store.build_zip("ptc-default")
    source_zip = store.zip_path("ptc-default")

    report_tamper = _rewrite_zip(source_zip, tmp_path / "report-tamper.zip", _tamper_report_summary_and_resign)
    data_tamper = _rewrite_zip(source_zip, tmp_path / "data-tamper.zip", _tamper_data_package_index_and_resign)
    html_tamper = _rewrite_zip(source_zip, tmp_path / "html-tamper.zip", lambda docs: _tamper_html_and_resign(docs, "index.html"))
    fingerprint_tamper = _rewrite_zip(source_zip, tmp_path / "fingerprint-tamper.zip", _tamper_package_fingerprint_full_resign)
    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    spoof = _rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_manifest_zip_entries)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n'}))

    assert any(item["check_id"] == "ptc_report_summary_release_count" for item in verify_public_trust_center_package(report_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_data_package_index_json_semantics" for item in verify_public_trust_center_package(data_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_html_index.html_semantics" for item in verify_public_trust_center_package(html_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_full_resign_package_fingerprint" for item in verify_public_trust_center_package(fingerprint_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_zip_duplicate_entries" for item in verify_public_trust_center_package(duplicate, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_zip_entry_path_safe" for item in verify_public_trust_center_package(dangerous, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_zip_entry_path_safe" for item in verify_public_trust_center_package(backslash, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_zip_no_nested_internal_entries" for item in verify_public_trust_center_package(case_musicforge, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_zip_no_nested_internal_entries" for item in verify_public_trust_center_package(nested, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_manifest_zip_entries_reference_only" for item in verify_public_trust_center_package(spoof, strict=True)["blockers"])
    assert any(item["check_id"] == "ptc_redaction_scan" for item in verify_public_trust_center_package(redaction, strict=True)["blockers"])


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


def _tamper_report_summary_and_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "trust-center-report.json")
    manifest = _read_doc(docs, "trust-center-manifest.json")
    report.setdefault("summary", {})["release_count"] = 999
    report["integrity_hash"] = public_trust_center_report_hash(report)
    docs["trust-center-report.json"] = _doc_bytes(report)
    manifest.setdefault("trust_center_report", {})["integrity_hash"] = report["integrity_hash"]
    _sync_manifest_file(manifest, "trust-center-report.json", docs["trust-center-report.json"])
    manifest["integrity_hash"] = public_trust_center_manifest_hash(manifest)
    docs["trust-center-manifest.json"] = _doc_bytes(manifest)


def _tamper_data_package_index_and_resign(docs: dict[str, bytes]) -> None:
    package = _read_doc(docs, "data/package-index.json")
    manifest = _read_doc(docs, "trust-center-manifest.json")
    if package.get("packages"):
        package["packages"][0]["zip_sha256"] = "0" * 64
    docs["data/package-index.json"] = _doc_bytes(package)
    manifest.setdefault("data", {})["package_index_hash"] = stable_hash(package)
    _sync_manifest_file(manifest, "data/package-index.json", docs["data/package-index.json"])
    manifest["integrity_hash"] = public_trust_center_manifest_hash(manifest)
    docs["trust-center-manifest.json"] = _doc_bytes(manifest)


def _tamper_html_and_resign(docs: dict[str, bytes], page: str) -> None:
    manifest = _read_doc(docs, "trust-center-manifest.json")
    docs[page] = docs[page].replace(b"MusicForge Public Trust Center", b"Forged Public Trust Center")
    for row in manifest.get("pages", []) if isinstance(manifest.get("pages"), list) else []:
        if isinstance(row, dict) and row.get("path") == page:
            row["content_hash"] = hashlib.sha256(docs[page]).hexdigest()
    _sync_manifest_file(manifest, page, docs[page])
    manifest["integrity_hash"] = public_trust_center_manifest_hash(manifest)
    docs["trust-center-manifest.json"] = _doc_bytes(manifest)


def _tamper_package_fingerprint_full_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "trust-center-report.json")
    manifest = _read_doc(docs, "trust-center-manifest.json")
    trust_data = _read_doc(docs, "data/trust-center-data.json")
    package_index = _read_doc(docs, "data/package-index.json")
    verification_index = _read_doc(docs, "data/verification-index.json")
    old_source_hash = report["source_hash"]
    if report.get("source", {}).get("public_package_fingerprints"):
        report["source"]["public_package_fingerprints"][0]["zip_sha256"] = "f" * 64
        report["package_index"][0]["zip_sha256"] = "f" * 64
        package_index["packages"][0]["zip_sha256"] = "f" * 64
        trust_data["packages"][0]["zip_sha256"] = "f" * 64
    if report.get("source", {}).get("verification_fingerprints"):
        report["source"]["verification_fingerprints"][0]["zip_sha256"] = "f" * 64
        verification_index["verifications"][0]["zip_sha256"] = "f" * 64
        trust_data["verifications"][0]["zip_sha256"] = "f" * 64
    report["source_hash"] = stable_hash(report["source"])
    for payload in (trust_data, package_index, verification_index):
        payload["source_hash"] = report["source_hash"]
    report["integrity_hash"] = public_trust_center_report_hash(report)
    docs["trust-center-report.json"] = _doc_bytes(report)
    docs["data/trust-center-data.json"] = _doc_bytes(trust_data)
    docs["data/package-index.json"] = _doc_bytes(package_index)
    docs["data/verification-index.json"] = _doc_bytes(verification_index)
    for page in ("index.html", "releases.html", "portfolios.html", "evidence.html", "risk.html", "verify.html"):
        text = docs[page].decode("utf-8").replace(old_source_hash, report["source_hash"]).replace("data-report-integrity=\"" + manifest["trust_center_report"]["integrity_hash"] + "\"", "data-report-integrity=\"" + report["integrity_hash"] + "\"")
        docs[page] = text.encode("utf-8")
    manifest["source_hash"] = report["source_hash"]
    manifest.setdefault("trust_center_report", {})["source_hash"] = report["source_hash"]
    manifest.setdefault("trust_center_report", {})["integrity_hash"] = report["integrity_hash"]
    manifest.setdefault("data", {})["trust_center_data_hash"] = stable_hash(trust_data)
    manifest.setdefault("data", {})["package_index_hash"] = stable_hash(package_index)
    manifest.setdefault("data", {})["verification_index_hash"] = stable_hash(verification_index)
    for row in manifest.get("pages", []) if isinstance(manifest.get("pages"), list) else []:
        if isinstance(row, dict) and row.get("path") in docs:
            row["source_hash"] = report["source_hash"]
            row["content_hash"] = hashlib.sha256(docs[row["path"]]).hexdigest()
    for path in ("trust-center-report.json", "data/trust-center-data.json", "data/package-index.json", "data/verification-index.json", "index.html", "releases.html", "portfolios.html", "evidence.html", "risk.html", "verify.html"):
        _sync_manifest_file(manifest, path, docs[path])
    manifest["integrity_hash"] = public_trust_center_manifest_hash(manifest)
    docs["trust-center-manifest.json"] = _doc_bytes(manifest)


def _spoof_manifest_zip_entries(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "trust-center-manifest.json")
    docs["extra.txt"] = b"extra"
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = public_trust_center_manifest_hash(manifest)
    docs["trust-center-manifest.json"] = _doc_bytes(manifest)


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
    raise AssertionError(f"manifest row missing: {path}")
