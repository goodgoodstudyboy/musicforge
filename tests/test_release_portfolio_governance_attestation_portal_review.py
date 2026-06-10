from __future__ import annotations

import base64
import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_attestation_portal import _portal_fixture

from song_agent.release_portfolio_governance_attestation_portal_review import (
    ReleasePortfolioGovernanceAttestationPortalReviewStateError,
    ReleasePortfolioGovernanceAttestationPortalReviewStore,
    response_integrity_hash,
    response_payload_hash,
    review_manifest_hash,
    review_pack_integrity_ok,
)
from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
    verify_release_portfolio_governance_attestation_portal_response,
    verify_release_portfolio_governance_attestation_portal_review_pack,
)


def _review_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, *_rest, portal_store = _portal_fixture(tmp_path, monkeypatch)
    portal_store.refresh_report(portfolio_id)
    portal_store.export_portal(portfolio_id)
    portal_store.build_zip(portfolio_id)
    store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    return portfolio_id, portal_store, store


def _response_payload(decision: str = "accepted") -> dict:
    return {
        "reviewer": {"name": "External Reviewer", "organization": "QA"},
        "decision": decision,
        "reviewed_at": "2026-06-10T00:00:00+00:00",
        "rating": 5 if decision == "accepted" else 2,
        "notes": "Portal evidence reviewed.",
        "findings": [] if decision == "accepted" else [{"severity": "high", "status": "open", "message": "Reviewer requested a governance clarification."}],
        "attachment_summaries": [],
    }


def test_attestation_portal_review_pack_response_roundtrip(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, store = _review_fixture(tmp_path, monkeypatch)

    pack = store.refresh_pack(portfolio_id)
    manifest = store.export_pack(portfolio_id)
    zip_info = store.build_pack_zip(portfolio_id)
    pack_verification = verify_release_portfolio_governance_attestation_portal_review_pack(store.pack_zip_path(portfolio_id), strict=True, require_current=True)
    response_zip = store.build_response_zip(portfolio_id, _response_payload())
    response_verification = verify_release_portfolio_governance_attestation_portal_response(response_zip, strict=True, require_current=True, require_pack=True)
    imported = store.import_response(portfolio_id, {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})

    assert pack["status"] == "ready"
    assert review_pack_integrity_ok(pack)
    assert manifest["package_type"] == "release_portfolio_governance_attestation_portal_review_pack"
    assert zip_info["sha256"]
    assert pack_verification["status"] == "passed"
    assert response_verification["status"] == "passed"
    assert imported["response"]["status"] == "accepted"
    assert imported["verification"]["status"] == "passed"


def test_attestation_portal_review_response_needs_changes_creates_change_request(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, store = _review_fixture(tmp_path, monkeypatch)
    store.refresh_pack(portfolio_id)
    store.export_pack(portfolio_id)
    store.build_pack_zip(portfolio_id)
    response_zip = store.build_response_zip(portfolio_id, _response_payload("needs_changes"))

    imported = store.import_response(portfolio_id, {"content_base64": base64.b64encode(response_zip.read_bytes()).decode("ascii")})
    response_id = imported["response"]["response_id"]
    first = store.create_change_request(portfolio_id, response_id, {"created_by": "reviewer"})
    second = store.create_change_request(portfolio_id, response_id, {"created_by": "reviewer"})

    assert imported["response"]["decision"] == "needs_changes"
    assert imported["verification"]["status"] == "passed"
    assert first["existing"] is False
    assert first["change_request"]["status"] == "draft"
    assert second["existing"] is True
    assert second["change_request"]["change_request_id"] == first["change_request"]["change_request_id"]


def test_attestation_portal_review_import_rejects_source_path(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, store = _review_fixture(tmp_path, monkeypatch)
    store.refresh_pack(portfolio_id)

    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalReviewStateError, match="source_path"):
        store.import_response(portfolio_id, {"source_path": str(tmp_path / "response.json")})


def test_attestation_portal_review_import_requires_external_source_binding(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, store = _review_fixture(tmp_path, monkeypatch)
    pack = store.refresh_pack(portfolio_id)
    bare = _response_payload()
    missing_pack_id = {**bare, "review_pack_source_hash": pack["source_hash"]}
    missing_source_hash = {**bare, "review_pack_id": pack["review_pack_id"]}
    wrong_source_hash = {**_response_payload("needs_changes"), "review_pack_id": pack["review_pack_id"], "review_pack_source_hash": "0" * 64}
    wrong_source_hash["payload_hash"] = response_payload_hash(wrong_source_hash)
    wrong_source_hash["integrity_hash"] = response_integrity_hash(wrong_source_hash)

    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalReviewStateError, match="review_pack_id"):
        store.import_response(portfolio_id, {"content_base64": base64.b64encode(json.dumps(missing_pack_id).encode("utf-8")).decode("ascii")})
    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalReviewStateError, match="review_pack_source_hash"):
        store.import_response(portfolio_id, {"content_base64": base64.b64encode(json.dumps(missing_source_hash).encode("utf-8")).decode("ascii")})

    imported = store.import_response(portfolio_id, {"content_base64": base64.b64encode(json.dumps(wrong_source_hash).encode("utf-8")).decode("ascii")})

    assert imported["response"]["status"] == "stale"
    assert imported["verification"]["status"] == "failed"
    with pytest.raises(ReleasePortfolioGovernanceAttestationPortalReviewStateError, match="stale"):
        store.create_change_request(portfolio_id, imported["response"]["response_id"])


def test_attestation_portal_review_verifiers_catch_tamper_and_paths(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _portal_store, store = _review_fixture(tmp_path, monkeypatch)
    store.refresh_pack(portfolio_id)
    store.export_pack(portfolio_id)
    store.build_pack_zip(portfolio_id)
    source_zip = store.pack_zip_path(portfolio_id)

    report_tamper = _rewrite_zip(source_zip, tmp_path / "pack-tamper.zip", _tamper_pack_portal_summary)
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    response_zip = store.build_response_zip(portfolio_id, _response_payload())
    response_tamper = _rewrite_zip(response_zip, tmp_path / "response-tamper.zip", _tamper_response_decision_without_hash)

    tampered_pack = verify_release_portfolio_governance_attestation_portal_review_pack(report_tamper, strict=True, require_current=True)
    nested_pack = verify_release_portfolio_governance_attestation_portal_review_pack(nested, strict=True)
    case_pack = verify_release_portfolio_governance_attestation_portal_review_pack(case_musicforge, strict=True)
    tampered_response = verify_release_portfolio_governance_attestation_portal_response(response_tamper, strict=True, require_current=True, require_pack=True)

    assert any(item["check_id"] == "portal_review_pack_data_portal_verification_zip_sha256" for item in tampered_pack["blockers"])
    assert any(item["check_id"] == "portal_review_pack_zip_no_nested_or_internal_entries" for item in nested_pack["blockers"])
    assert any(item["check_id"] == "portal_review_pack_zip_no_nested_or_internal_entries" for item in case_pack["blockers"])
    assert any(item["check_id"] == "portal_review_response_payload_hash" for item in tampered_response["blockers"])


def _rewrite_zip(source_zip: Path, target_zip: Path, mutate) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
        mutate(docs)
        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for name, data in docs.items():
                dst.writestr(name, data)
    return target_zip


def _tamper_pack_portal_summary(docs: dict[str, bytes]) -> None:
    summary = _read_doc(docs, "data/portal-verification-summary.json")
    manifest = _read_doc(docs, "review-pack-manifest.json")
    summary["zip_sha256"] = "0" * 64
    docs["data/portal-verification-summary.json"] = _doc_bytes(summary)
    _sync_manifest_file(manifest, "data/portal-verification-summary.json", docs["data/portal-verification-summary.json"])
    manifest["integrity_hash"] = review_manifest_hash(manifest)
    docs["review-pack-manifest.json"] = _doc_bytes(manifest)


def _tamper_response_decision_without_hash(docs: dict[str, bytes]) -> None:
    response = _read_doc(docs, "review-response.json")
    manifest = _read_doc(docs, "response-manifest.json")
    response["decision"] = "rejected"
    response["integrity_hash"] = response_integrity_hash(response)
    docs["review-response.json"] = _doc_bytes(response)
    _sync_manifest_file(manifest, "review-response.json", docs["review-response.json"])
    manifest["integrity_hash"] = review_manifest_hash(manifest)
    docs["response-manifest.json"] = _doc_bytes(manifest)


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
