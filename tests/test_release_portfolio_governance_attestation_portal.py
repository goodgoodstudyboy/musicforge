from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_attestation_registry import _registry_fixture

from song_agent.release_portfolio_governance_attestation_portal import (
    ReleasePortfolioGovernanceAttestationPortalStateError,
    ReleasePortfolioGovernanceAttestationPortalStore,
    portal_manifest_hash,
    portal_report_hash,
    portal_report_integrity_ok,
)
from song_agent.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal
from song_agent.releases import stable_hash


def _portal_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store, attestation_store, registry_store = _registry_fixture(tmp_path, monkeypatch)
    entry = registry_store.register_current_attestation(portfolio_id)["entry"]
    registry_store.publish_entry(portfolio_id, entry["entry_id"], {"published_by": "tester"})
    registry_store.refresh_report(portfolio_id)
    registry_store.export_registry(portfolio_id)
    registry_store.build_zip(portfolio_id)
    portal_store = ReleasePortfolioGovernanceAttestationPortalStore(registry_store=registry_store, attestation_store=attestation_store)
    return portfolio_id, queue_id, governance_store, signoff_store, audit_store, reviewer_store, final_board_store, vault_store, attestation_store, registry_store, portal_store


def test_attestation_portal_refresh_export_verify(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, portal_store = _portal_fixture(tmp_path, monkeypatch)

    report = portal_store.refresh_report(portfolio_id)
    manifest = portal_store.export_portal(portfolio_id)
    zip_info = portal_store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_attestation_portal(portal_store.zip_path(portfolio_id), strict=True, require_current=True, require_registry=True, require_attestation=True)

    assert report["status"] == "passed"
    assert portal_report_integrity_ok(report)
    assert manifest["package_type"] == "release_portfolio_governance_attestation_portal"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    with zipfile.ZipFile(portal_store.zip_path(portfolio_id), "r") as archive:
        names = archive.namelist()
        index = archive.read("index.html").decode("utf-8")
    assert "index.html" in names
    assert "portal-manifest.json" in names
    assert "data/portal-summary.json" in names
    assert "<script" not in index.lower()
    assert "https://" not in index.lower()


def test_attestation_portal_blocks_delete_rebuild_same_state(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, portal_store = _portal_fixture(tmp_path, monkeypatch)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)

    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalStateError, match="already exists"):
        portal_store.export_portal(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalStateError, match="already exists"):
        portal_store.build_zip(portfolio_id)
    shutil.rmtree(portal_store.export_dir(portfolio_id))
    portal_store.zip_path(portfolio_id).unlink()
    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalStateError, match="already exists"):
        portal_store.export_portal(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalStateError, match="already exists"):
        portal_store.build_zip(portfolio_id)


def test_attestation_portal_verifier_catches_resigned_report_and_data_tamper(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, portal_store = _portal_fixture(tmp_path, monkeypatch)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)

    report_tamper = _rewrite_portal_zip(portal_store.zip_path(portfolio_id), tmp_path / "report-source.zip", _tamper_report_source_and_resign)
    data_tamper = _rewrite_portal_zip(portal_store.zip_path(portfolio_id), tmp_path / "data-current.zip", _tamper_current_summary_and_resign_manifest)

    report_verification = verify_release_portfolio_governance_attestation_portal(report_tamper, strict=True, require_current=True, require_registry=True, require_attestation=True)
    data_verification = verify_release_portfolio_governance_attestation_portal(data_tamper, strict=True, require_current=True, require_registry=True, require_attestation=True)

    assert any(item["check_id"] == "portal_manifest_registry_zip_sha256" for item in report_verification["blockers"])
    assert any(item["check_id"] == "portal_data_current_attestation_attestation_zip_sha256" for item in data_verification["blockers"])


def test_attestation_portal_verifier_catches_html_and_zip_safety(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, *_rest, portal_store = _portal_fixture(tmp_path, monkeypatch)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    source_zip = portal_store.zip_path(portfolio_id)

    script_zip = _rewrite_portal_zip(source_zip, tmp_path / "script.zip", lambda docs: _append_html(docs, "index.html", "<script>alert(1)</script>"))
    remote_zip = _rewrite_portal_zip(source_zip, tmp_path / "remote.zip", lambda docs: _append_html(docs, "index.html", '<a href="https://example.com">x</a>'))
    wrong_type = _rewrite_portal_zip(source_zip, tmp_path / "wrong-type.zip", _tamper_manifest_package_type)
    nested = _rewrite_portal_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    case_musicforge = _rewrite_portal_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))

    assert any(item["check_id"].startswith("portal_html_index.html_safe") for item in verify_release_portfolio_governance_attestation_portal(script_zip, strict=True)["blockers"])
    assert any(item["check_id"].startswith("portal_html_index.html_safe") for item in verify_release_portfolio_governance_attestation_portal(remote_zip, strict=True)["blockers"])
    assert any(item["check_id"] == "portal_manifest_package_type" for item in verify_release_portfolio_governance_attestation_portal(wrong_type, strict=True)["blockers"])
    assert any(item["check_id"] == "portal_zip_no_nested_packages" for item in verify_release_portfolio_governance_attestation_portal(nested, strict=True)["blockers"])
    assert any(item["check_id"] == "portal_zip_no_nested_packages" for item in verify_release_portfolio_governance_attestation_portal(case_musicforge, strict=True)["blockers"])


def _rewrite_portal_zip(source_zip: Path, target_zip: Path, mutate) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
        mutate(docs)
        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for name, data in docs.items():
                dst.writestr(name, data)
    return target_zip


def _tamper_report_source_and_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "portal-report.json")
    manifest = _read_doc(docs, "portal-manifest.json")
    portal_summary = _read_doc(docs, "data/portal-summary.json")
    registry_summary = _read_doc(docs, "data/registry-summary.json")
    current_summary = _read_doc(docs, "data/current-attestation-summary.json")
    commands = _read_doc(docs, "data/verification-commands.json")
    report.setdefault("source", {})["registry_zip_sha256"] = "0" * 64
    report["source_hash"] = stable_hash(report["source"])
    report["integrity_hash"] = portal_report_hash(report)
    for payload in (portal_summary, registry_summary, current_summary, commands):
        payload["source_hash"] = report["source_hash"]
    docs["portal-report.json"] = _doc_bytes(report)
    docs["data/portal-summary.json"] = _doc_bytes(portal_summary)
    docs["data/registry-summary.json"] = _doc_bytes(registry_summary)
    docs["data/current-attestation-summary.json"] = _doc_bytes(current_summary)
    docs["data/verification-commands.json"] = _doc_bytes(commands)
    manifest["source_hash"] = report["source_hash"]
    manifest.setdefault("portal_report", {})["source_hash"] = report["source_hash"]
    manifest.setdefault("portal_report", {})["integrity_hash"] = report["integrity_hash"]
    for item in manifest.get("pages", []):
        if isinstance(item, dict):
            item["source_hash"] = report["source_hash"]
    for path in ("portal-report.json", "data/portal-summary.json", "data/registry-summary.json", "data/current-attestation-summary.json", "data/verification-commands.json"):
        _sync_manifest_file(manifest, path, docs[path])
    manifest["integrity_hash"] = portal_manifest_hash(manifest)
    docs["portal-manifest.json"] = _doc_bytes(manifest)


def _tamper_current_summary_and_resign_manifest(docs: dict[str, bytes]) -> None:
    current = _read_doc(docs, "data/current-attestation-summary.json")
    manifest = _read_doc(docs, "portal-manifest.json")
    current["attestation_zip_sha256"] = "1" * 64
    docs["data/current-attestation-summary.json"] = _doc_bytes(current)
    _sync_manifest_file(manifest, "data/current-attestation-summary.json", docs["data/current-attestation-summary.json"])
    manifest["integrity_hash"] = portal_manifest_hash(manifest)
    docs["portal-manifest.json"] = _doc_bytes(manifest)


def _append_html(docs: dict[str, bytes], path: str, snippet: str) -> None:
    manifest = _read_doc(docs, "portal-manifest.json")
    text = docs[path].decode("utf-8") + snippet
    docs[path] = text.encode("utf-8")
    _sync_manifest_file(manifest, path, docs[path])
    for item in manifest.get("pages", []):
        if isinstance(item, dict) and item.get("path") == path:
            item["content_hash"] = hashlib.sha256(docs[path]).hexdigest()
    manifest["integrity_hash"] = portal_manifest_hash(manifest)
    docs["portal-manifest.json"] = _doc_bytes(manifest)


def _tamper_manifest_package_type(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "portal-manifest.json")
    manifest["package_type"] = "wrong_package_type"
    manifest["integrity_hash"] = portal_manifest_hash(manifest)
    docs["portal-manifest.json"] = _doc_bytes(manifest)


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
