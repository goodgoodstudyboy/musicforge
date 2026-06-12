from __future__ import annotations

import base64
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from tests.test_release_portfolio_governance_attestation_transparency import _transparency_fixture

from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import (
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError,
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore,
    ack_evidence_hash,
    ack_manifest_hash,
    response_payload_hash,
    response_template,
)
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import verify_release_portfolio_governance_attestation_transparency_acknowledgement_package


def _ack_fixture(tmp_path: Path, monkeypatch):
    portfolio_id, _portal_store, _accepted_store, transparency_store = _transparency_fixture(tmp_path, monkeypatch)
    transparency_store.refresh_feed(portfolio_id, {"require_accepted_evidence": True})
    transparency_store.export_transparency(portfolio_id)
    transparency_store.build_zip(portfolio_id)
    transparency_store.verify_transparency(portfolio_id, {"strict": True, "require_current": True, "require_accepted_evidence": True, "require_contiguous_chain": True})
    store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(transparency_store=transparency_store)
    return portfolio_id, transparency_store, store


def test_transparency_acknowledgement_pack_response_and_evidence_roundtrip(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _transparency_store, store = _ack_fixture(tmp_path, monkeypatch)

    pack = store.refresh_pack(portfolio_id)
    manifest = store.export_pack(portfolio_id)
    zip_info = store.build_pack_zip(portfolio_id)
    pack_report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(store.pack_zip_path(portfolio_id), strict=True, require_pack=True, require_transparency=True)
    payload = _accepted_response(pack)
    imported = store.import_response(portfolio_id, {"content": payload})
    evidence = store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    evidence_manifest = store.export_evidence(portfolio_id)
    evidence_zip = store.build_evidence_zip(portfolio_id)
    evidence_report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(store.evidence_zip_path(portfolio_id), strict=True, require_response=True, require_accepted=True)

    assert pack["status"] == "ready"
    assert manifest["package_type"] == "release_portfolio_governance_attestation_transparency_acknowledgement_pack"
    assert zip_info["sha256"]
    assert pack_report["status"] == "passed"
    assert imported["verification"]["status"] == "passed"
    assert evidence["status"] == "current"
    assert evidence_manifest["package_type"] == "release_portfolio_governance_attestation_transparency_acknowledgement_evidence"
    assert evidence_zip["sha256"]
    assert evidence_report["status"] == "passed"


def test_transparency_acknowledgement_response_must_bind_source_explicitly(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _transparency_store, store = _ack_fixture(tmp_path, monkeypatch)
    pack = store.refresh_pack(portfolio_id)
    payload = _accepted_response(pack)

    missing_source = dict(payload)
    missing_source.pop("review_pack_source_hash")
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="missing required source binding"):
        store.import_response(portfolio_id, {"content": missing_source})

    wrong_source = dict(payload)
    wrong_source["transparency_zip_sha256"] = "0" * 64
    wrong_source["response_hash"] = response_payload_hash(wrong_source)
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="verification failed"):
        store.import_response(portfolio_id, {"content": wrong_source})


def test_transparency_acknowledgement_needs_changes_creates_change_request_only(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _transparency_store, store = _ack_fixture(tmp_path, monkeypatch)
    pack = store.refresh_pack(portfolio_id)
    payload = _accepted_response(pack)
    payload["review_status"] = "needs_changes"
    payload["concerns"] = [{"notice_id": payload["reviewed_notice_ids"][0], "severity": "warning", "message": "Please clarify this notice."}]
    payload["response_hash"] = response_payload_hash(payload)
    imported = store.import_response(portfolio_id, {"content_base64": base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")})

    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="accepted"):
        store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    cr = store.create_change_request(portfolio_id, imported["response"]["response_id"])

    assert cr["status"] == "draft"
    assert cr["source"] == "transparency_acknowledgement_response"


def test_transparency_acknowledgement_stale_pack_blocks_export_and_zip(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, transparency_store, store = _ack_fixture(tmp_path, monkeypatch)
    store.refresh_pack(portfolio_id)
    transparency_store.zip_path(portfolio_id).write_bytes(transparency_store.zip_path(portfolio_id).read_bytes() + b"changed")

    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="stale"):
        store.export_pack(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="stale"):
        store.build_pack_zip(portfolio_id)


def test_transparency_acknowledgement_blocks_delete_rebuild_same_state(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _transparency_store, store = _ack_fixture(tmp_path, monkeypatch)
    store.refresh_pack(portfolio_id)
    store.export_pack(portfolio_id)
    store.build_pack_zip(portfolio_id)

    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="already exists"):
        store.export_pack(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="already exists"):
        store.build_pack_zip(portfolio_id)
    shutil.rmtree(store.pack_export_dir(portfolio_id))
    store.pack_zip_path(portfolio_id).unlink()
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="already exists"):
        store.export_pack(portfolio_id)
    with pytest.raises(ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError, match="already exists"):
        store.build_pack_zip(portfolio_id)


def test_transparency_acknowledgement_verifier_catches_paths_and_spoof(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _transparency_store, store = _ack_fixture(tmp_path, monkeypatch)
    store.refresh_pack(portfolio_id)
    store.export_pack(portfolio_id)
    store.build_pack_zip(portfolio_id)
    source_zip = store.pack_zip_path(portfolio_id)

    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    spoof = _rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_pack_manifest_zip_entries)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n'}))

    assert any(item["check_id"] == "ack_zip_duplicate_entries" for item in verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(duplicate, strict=True)["blockers"])
    assert any(item["check_id"] == "ack_zip_entry_path_safe" for item in verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(dangerous, strict=True)["blockers"])
    assert any(item["check_id"] == "ack_zip_entry_path_safe" for item in verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(backslash, strict=True)["blockers"])
    assert any(item["check_id"] == "ack_zip_no_nested_packages" for item in verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(case_musicforge, strict=True)["blockers"])
    assert any(item["check_id"] == "ack_zip_no_nested_packages" for item in verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(nested, strict=True)["blockers"])
    assert any(item["check_id"] == "ack_pack_manifest_zip_entries_reference_only" for item in verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(spoof, strict=True)["blockers"])
    assert any(item["check_id"] == "ack_redaction_scan" for item in verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(redaction, strict=True)["blockers"])


def test_transparency_acknowledgement_verifier_rejects_full_resigned_evidence_public_summary(tmp_path: Path, monkeypatch) -> None:
    portfolio_id, _transparency_store, store = _ack_fixture(tmp_path, monkeypatch)
    pack = store.refresh_pack(portfolio_id)
    imported = store.import_response(portfolio_id, {"content": _accepted_response(pack)})
    store.refresh_evidence(portfolio_id, {"response_id": imported["response"]["response_id"]})
    store.export_evidence(portfolio_id)
    store.build_evidence_zip(portfolio_id)

    forged = _rewrite_zip(store.evidence_zip_path(portfolio_id), tmp_path / "forged-evidence.zip", _full_resign_evidence_public_summary)
    report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(forged, strict=True, require_response=True, require_accepted=True)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "ack_evidence_original_response_public_summary" for item in report["blockers"])


def _accepted_response(pack: dict) -> dict:
    payload = response_template(pack)
    payload["response_id"] = "external-ack-001"
    payload["reviewer"] = {"name": "External Reviewer", "organization": "Review Org", "role": "reviewer"}
    payload["comments"] = "Transparency feed and notices reviewed."
    payload["submitted_at"] = "2026-06-11T00:00:00+00:00"
    payload["response_hash"] = response_payload_hash(payload)
    return payload


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


def _spoof_pack_manifest_zip_entries(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "acknowledgement-pack-manifest.json")
    docs["extra.txt"] = b"extra"
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = ack_manifest_hash(manifest)
    docs["acknowledgement-pack-manifest.json"] = _doc_bytes(manifest)


def _full_resign_evidence_public_summary(docs: dict[str, bytes]) -> None:
    evidence = _read_doc(docs, "acknowledgement-evidence.json")
    summary = _read_doc(docs, "acknowledgement-evidence-summary.json")
    response_binding = _read_doc(docs, "data/response-binding-summary.json")
    public = _read_doc(docs, "data/public-summary.json")
    manifest = _read_doc(docs, "acknowledgement-evidence-manifest.json")
    evidence["public_summary"]["reviewer_name"] = "Forged Reviewer"
    evidence["public_summary"]["reviewer_organization"] = "Forged Org"
    forged_summary_hash = _stable_hash_for_test(evidence["public_summary"])
    evidence.setdefault("source", {})["response_public_summary_hash"] = forged_summary_hash
    evidence["source_hash"] = _stable_hash_for_test(evidence["source"])
    evidence["integrity_hash"] = ack_evidence_hash(evidence)
    summary["public_summary"] = evidence["public_summary"]
    summary.setdefault("summary", {})["reviewer_name"] = evidence["public_summary"]["reviewer_name"]
    response_binding["source_hash"] = evidence["source_hash"]
    response_binding["response_public_summary_hash"] = forged_summary_hash
    docs["acknowledgement-evidence.json"] = _doc_bytes(evidence)
    docs["acknowledgement-evidence-summary.json"] = _doc_bytes(summary)
    docs["data/response-binding-summary.json"] = _doc_bytes(response_binding)
    public["public_summary"] = evidence["public_summary"]
    public["source_hash"] = evidence["source_hash"]
    docs["data/public-summary.json"] = _doc_bytes(public)
    _sync_manifest_file(manifest, "acknowledgement-evidence.json", docs["acknowledgement-evidence.json"])
    _sync_manifest_file(manifest, "acknowledgement-evidence-summary.json", docs["acknowledgement-evidence-summary.json"])
    _sync_manifest_file(manifest, "data/response-binding-summary.json", docs["data/response-binding-summary.json"])
    _sync_manifest_file(manifest, "data/public-summary.json", docs["data/public-summary.json"])
    manifest["source_hash"] = evidence["source_hash"]
    manifest["acknowledgement"]["integrity_hash"] = evidence["integrity_hash"]
    manifest["acknowledgement"]["source_hash"] = evidence["source_hash"]
    manifest["integrity_hash"] = ack_manifest_hash(manifest)
    docs["acknowledgement-evidence-manifest.json"] = _doc_bytes(manifest)


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


def _stable_hash_for_test(payload: dict) -> str:
    from song_agent.releases import stable_hash

    return stable_hash(payload)
