from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_attestation_portal_review import _response_payload, _review_fixture

from song_agent.release_portfolio_governance_attestation_accepted_evidence import (
    ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError,
    ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore,
    accepted_evidence_hash,
    accepted_evidence_integrity_ok,
    accepted_evidence_manifest_hash,
)
from song_agent.release_portfolio_governance_attestation_accepted_evidence_verifier import verify_release_portfolio_governance_attestation_accepted_evidence
from song_agent.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal
from song_agent.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry


def _accepted_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, portal_store, review_store = _review_fixture(tmp_path, monkeypatch)
    review_store.refresh_pack(portfolio_id)
    review_store.export_pack(portfolio_id)
    review_store.build_pack_zip(portfolio_id)
    response_zip = review_store.build_response_zip(portfolio_id, _response_payload())
    imported = review_store.import_response(portfolio_id, {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
    store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    return portfolio_id, portal_store, review_store, store, imported


def test_attestation_accepted_evidence_roundtrip_and_public_summaries(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, portal_store, review_store, store, imported = _accepted_fixture(tmp_path, monkeypatch)

    evidence = store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    manifest = store.export_evidence(portfolio_id)
    zip_info = store.build_zip(portfolio_id)
    verification = verify_release_portfolio_governance_attestation_accepted_evidence(store.zip_path(portfolio_id), strict=True, require_current=True)
    store.verify_evidence(portfolio_id, {"strict": True, "require_current": True})

    registry_store = portal_store.registry_store
    registry_manifest = registry_store.export_registry(portfolio_id)
    registry_store.build_zip(portfolio_id)
    registry_verification = verify_release_portfolio_governance_attestation_registry(registry_store.zip_path(portfolio_id), strict=True, require_current=True, require_published=True, require_accepted_evidence=True)

    portal_store.refresh_report(portfolio_id)
    # Registry ZIP evidence changed above, so refresh once more before exporting
    # the Portal snapshot that binds registry verification fingerprints.
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    portal_verification = verify_release_portfolio_governance_attestation_portal(portal_store.zip_path(portfolio_id), strict=True, require_current=True, require_registry=True, require_attestation=True, require_accepted_evidence=True)

    assert evidence["status"] == "current"
    assert accepted_evidence_integrity_ok(evidence)
    assert manifest["package_type"] == "release_portfolio_governance_attestation_accepted_evidence"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"
    assert registry_manifest["external_review"]["external_review_status"] == "accepted"
    assert registry_verification["status"] == "passed"
    assert portal_verification["status"] == "passed"


@pytest.mark.parametrize("decision", ["needs_changes", "rejected"])
def test_attestation_accepted_evidence_rejects_non_accepted_responses(tmp_path: Path, monkeypatch, decision: str) -> None:
    portfolio_id, _portal_store, review_store = _review_fixture(tmp_path, monkeypatch)
    review_store.refresh_pack(portfolio_id)
    response_zip = review_store.build_response_zip(portfolio_id, _response_payload(decision))
    imported = review_store.import_response(portfolio_id, {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
    store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)

    with pytest.raises(ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError, match="accepted"):
        store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})


def test_attestation_accepted_evidence_rejects_stale_response(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, review_store = _review_fixture(tmp_path, monkeypatch)
    pack = review_store.refresh_pack(portfolio_id)
    stale = {**_response_payload(), "review_pack_id": pack["review_pack_id"], "review_pack_source_hash": "0" * 64}
    imported = review_store.import_response(portfolio_id, {"content_base64": base64.b64encode(json.dumps(stale).encode("utf-8")).decode("ascii")})
    store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)

    with pytest.raises(ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError, match="current"):
        store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})


def test_attestation_accepted_evidence_verifier_catches_tamper_and_paths(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, _review_store, store, imported = _accepted_fixture(tmp_path, monkeypatch)
    store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    store.export_evidence(portfolio_id)
    store.build_zip(portfolio_id)
    source_zip = store.zip_path(portfolio_id)

    report_tamper = _rewrite_zip(source_zip, tmp_path / "report-tamper.zip", _tamper_report_and_resign)
    summary_tamper = _rewrite_zip(source_zip, tmp_path / "summary-tamper.zip", _tamper_summary_and_resign)
    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n'}))

    assert any(item["check_id"] == "accepted_evidence_report_source_hash" for item in verify_release_portfolio_governance_attestation_accepted_evidence(report_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "accepted_evidence_summary_public_status" for item in verify_release_portfolio_governance_attestation_accepted_evidence(summary_tamper, strict=True)["blockers"])
    assert any(item["check_id"] == "accepted_evidence_zip_duplicate_entries" for item in verify_release_portfolio_governance_attestation_accepted_evidence(duplicate, strict=True)["blockers"])
    assert any(item["check_id"] == "accepted_evidence_zip_entry_path_safe" for item in verify_release_portfolio_governance_attestation_accepted_evidence(dangerous, strict=True)["blockers"])
    assert any(item["check_id"] == "accepted_evidence_zip_no_nested_or_internal_entries" for item in verify_release_portfolio_governance_attestation_accepted_evidence(case_musicforge, strict=True)["blockers"])
    assert any(item["check_id"] == "accepted_evidence_zip_no_nested_or_internal_entries" for item in verify_release_portfolio_governance_attestation_accepted_evidence(nested, strict=True)["blockers"])
    assert any(item["check_id"] == "accepted_evidence_redaction_scan" for item in verify_release_portfolio_governance_attestation_accepted_evidence(redaction, strict=True)["blockers"])


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


def _tamper_report_and_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "accepted-evidence-report.json")
    manifest = _read_doc(docs, "accepted-evidence-manifest.json")
    report["source"]["response_verification_hash"] = "0" * 64
    report["integrity_hash"] = accepted_evidence_hash(report)
    docs["accepted-evidence-report.json"] = _doc_bytes(report)
    _sync_manifest_file(manifest, "accepted-evidence-report.json", docs["accepted-evidence-report.json"])
    manifest["accepted_evidence"]["integrity_hash"] = report["integrity_hash"]
    manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
    docs["accepted-evidence-manifest.json"] = _doc_bytes(manifest)


def _tamper_summary_and_resign(docs: dict[str, bytes]) -> None:
    summary = _read_doc(docs, "accepted-evidence-summary.json")
    manifest = _read_doc(docs, "accepted-evidence-manifest.json")
    summary["summary"]["external_review_status"] = "missing"
    summary["public_summary"]["external_review_status"] = "missing"
    docs["accepted-evidence-summary.json"] = _doc_bytes(summary)
    _sync_manifest_file(manifest, "accepted-evidence-summary.json", docs["accepted-evidence-summary.json"])
    manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
    docs["accepted-evidence-manifest.json"] = _doc_bytes(manifest)


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
