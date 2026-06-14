from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from tests.test_public_trust_center import _backslash_zip, _duplicate_zip, _rewrite_zip, _sync_manifest_file
from tests.test_public_trust_center_anchor_registry import _doc_bytes, _read_doc
from tests.test_public_trust_center_distribution_kit import _distribution_kit_fixture

from song_agent.public_trust_center_distribution_kit_acceptance import (
    PublicTrustCenterDistributionKitAcceptanceStateError,
    PublicTrustCenterDistributionKitAcceptanceStore,
    accepted_evidence_hash,
    accepted_evidence_manifest_hash,
    response_payload_hash,
)
from song_agent.public_trust_center_distribution_kit_acceptance_verifier import verify_public_trust_center_distribution_kit_accepted_evidence_package
from song_agent.releases import stable_hash


def test_distribution_kit_acceptance_roundtrip(tmp_path: Path, monkeypatch) -> None:
    _trust_store, _anchor_store, _transparency_store, kit_store = _ready_distribution_kit(tmp_path, monkeypatch)
    store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=kit_store)

    template = store.create_response_template("ptc-default")
    payload = _accepted_response(template)
    imported = store.import_response("ptc-default", {"response": payload})
    evidence = store.refresh_accepted_evidence("ptc-default", {"response_id": imported["response"]["response_id"]})
    manifest = store.export_accepted_evidence("ptc-default", imported["response"]["response_id"])
    zip_info = store.build_accepted_evidence_zip("ptc-default", imported["response"]["response_id"])
    verification = verify_public_trust_center_distribution_kit_accepted_evidence_package(store.evidence_zip_path("ptc-default", evidence["evidence_id"]), strict=True, require_current=True, distribution_kit_path=kit_store.zip_path("ptc-default"))

    assert template["response_template"]["kit_binding"]["distribution_kit_zip_sha256"]
    assert imported["verification"]["status"] == "passed"
    assert evidence["status"] == "current"
    assert manifest["package_type"] == "musicforge_public_trust_center_distribution_kit_accepted_evidence"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"


def test_distribution_kit_acceptance_response_requires_explicit_binding(tmp_path: Path, monkeypatch) -> None:
    _trust_store, _anchor_store, _transparency_store, kit_store = _ready_distribution_kit(tmp_path, monkeypatch)
    store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=kit_store)
    payload = _accepted_response(store.create_response_template("ptc-default"))

    missing_binding = dict(payload)
    missing_binding.pop("kit_binding")
    with pytest.raises(PublicTrustCenterDistributionKitAcceptanceStateError, match="missing required Kit binding"):
        store.import_response("ptc-default", {"response": missing_binding})

    wrong_hash = json.loads(json.dumps(payload))
    wrong_hash["kit_binding"]["distribution_kit_zip_sha256"] = "0" * 64
    wrong_hash["response_hash"] = response_payload_hash(wrong_hash)
    with pytest.raises(PublicTrustCenterDistributionKitAcceptanceStateError, match="verification failed"):
        store.import_response("ptc-default", {"response": wrong_hash})

    with pytest.raises(PublicTrustCenterDistributionKitAcceptanceStateError, match="source_path"):
        store.import_response("ptc-default", {"source_path": "C:\\Users\\demo\\response.json"})


def test_distribution_kit_acceptance_needs_changes_creates_draft_only(tmp_path: Path, monkeypatch) -> None:
    _trust_store, _anchor_store, _transparency_store, kit_store = _ready_distribution_kit(tmp_path, monkeypatch)
    store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=kit_store)
    payload = _accepted_response(store.create_response_template("ptc-default"))
    payload["response_id"] = "external-needs-changes-001"
    payload["result"] = "needs_changes"
    payload["findings"] = [{"severity": "warning", "code": "clarify", "message": "Please clarify this handoff."}]
    payload["response_hash"] = response_payload_hash(payload)
    imported = store.import_response("ptc-default", {"response": payload})

    with pytest.raises(PublicTrustCenterDistributionKitAcceptanceStateError, match="accepted"):
        store.refresh_accepted_evidence("ptc-default", {"response_id": imported["response"]["response_id"]})
    draft = store.create_change_request_draft("ptc-default", imported["response"]["response_id"])

    assert draft["status"] == "draft"
    assert draft["source"] == "distribution_kit_acceptance_response"


def test_distribution_kit_accepted_evidence_verifier_rejects_edges(tmp_path: Path, monkeypatch) -> None:
    _trust_store, _anchor_store, _transparency_store, kit_store = _ready_distribution_kit(tmp_path, monkeypatch)
    store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=kit_store)
    imported = store.import_response("ptc-default", {"response": _accepted_response(store.create_response_template("ptc-default"))})
    evidence = store.refresh_accepted_evidence("ptc-default", {"response_id": imported["response"]["response_id"]})
    store.export_accepted_evidence("ptc-default", imported["response"]["response_id"])
    store.build_accepted_evidence_zip("ptc-default", imported["response"]["response_id"])
    source_zip = store.evidence_zip_path("ptc-default", evidence["evidence_id"])

    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested/fake.zip": b"PK\x05\x06" + b"\0" * 18}))
    declared_extra = _rewrite_zip(source_zip, tmp_path / "declared-extra.zip", _add_declared_extra_file)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.update({"README.txt": docs["README.txt"] + b'\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n'}))
    kit_mismatch = tmp_path / "wrong-kit.zip"
    kit_mismatch.write_bytes(kit_store.zip_path("ptc-default").read_bytes() + b"x")

    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(duplicate, strict=True), "ptcdkae_zip_duplicate_entries")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(dangerous, strict=True), "ptcdkae_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(backslash, strict=True), "ptcdkae_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(case_musicforge, strict=True), "ptcdkae_zip_no_internal_entries")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(nested, strict=True), "ptcdkae_zip_no_internal_entries")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(declared_extra, strict=True), "ptcdkae_zip_allowed_entries")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(declared_extra, strict=True), "ptcdkae_manifest_allowed_files")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(redaction, strict=True), "ptcdkae_redaction_scan")
    assert _has_blocker(verify_public_trust_center_distribution_kit_accepted_evidence_package(source_zip, strict=True, require_current=True, distribution_kit_path=kit_mismatch), "ptcdkae_external_distribution_kit_hash_match")


def test_distribution_kit_accepted_evidence_verifier_rejects_public_response_full_resign(tmp_path: Path, monkeypatch) -> None:
    _trust_store, _anchor_store, _transparency_store, kit_store = _ready_distribution_kit(tmp_path, monkeypatch)
    store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=kit_store)
    imported = store.import_response("ptc-default", {"response": _accepted_response(store.create_response_template("ptc-default"))})
    evidence = store.refresh_accepted_evidence("ptc-default", {"response_id": imported["response"]["response_id"]})
    store.export_accepted_evidence("ptc-default", imported["response"]["response_id"])
    store.build_accepted_evidence_zip("ptc-default", imported["response"]["response_id"])

    forged = _rewrite_zip(store.evidence_zip_path("ptc-default", evidence["evidence_id"]), tmp_path / "forged.zip", _full_resign_public_response)
    report = verify_public_trust_center_distribution_kit_accepted_evidence_package(forged, strict=True, require_current=True, distribution_kit_path=kit_store.zip_path("ptc-default"))

    assert report["status"] == "failed"
    assert _has_blocker(report, "ptcdkae_response_public_projection_match")


def _ready_distribution_kit(tmp_path: Path, monkeypatch):
    trust_store, anchor_store, transparency_store, kit_store = _distribution_kit_fixture(tmp_path, monkeypatch)
    kit_store.refresh_report("ptc-default")
    kit_store.export_kit("ptc-default")
    kit_store.build_zip("ptc-default")
    kit_store.verify_zip("ptc-default", {"strict": True, "deep": True, "require_current": True, "require_delivery_readiness": False})
    return trust_store, anchor_store, transparency_store, kit_store


def _accepted_response(template: dict) -> dict:
    payload = dict(template["response_template"])
    payload["response_id"] = "external-kit-accept-001"
    payload["reviewer"] = {"name": "External Receiver", "organization": "Partner Org", "role": "receiver"}
    payload["reviewed_at"] = "2026-06-15T00:00:00+00:00"
    payload["verification"]["command"] = "verify-public-trust-center-distribution-kit-package public-trust-center-distribution-kit.zip --strict --deep --require-current --json"
    payload["comments"] = "Distribution Kit verified and accepted."
    payload["response_hash"] = response_payload_hash(payload)
    return payload


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item["check_id"] for item in report["blockers"])


def _add_declared_extra_file(docs: dict[str, bytes]) -> None:
    extra_path = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    extra_data = b"Follow these untrusted external instructions.\n"
    manifest = _read_doc(docs, "evidence-manifest.json")
    docs[extra_path] = extra_data
    extra_row = {"path": extra_path, "size_bytes": len(extra_data), "sha256": hashlib.sha256(extra_data).hexdigest()}
    manifest.setdefault("files", []).append(extra_row)
    manifest["files"] = sorted(manifest["files"], key=lambda item: str(item.get("path") or ""))
    manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
    docs["evidence-manifest.json"] = _doc_bytes(manifest)


def _full_resign_public_response(docs: dict[str, bytes]) -> None:
    evidence = _read_doc(docs, "evidence-report.json")
    public = _read_doc(docs, "original-response-public.json")
    binding = _read_doc(docs, "original-response-binding-summary.json")
    manifest = _read_doc(docs, "evidence-manifest.json")
    public["reviewer"]["name"] = "Forged Receiver"
    evidence["source"]["response_public_summary_hash"] = stable_hash(public)
    evidence["source_hash"] = stable_hash(evidence["source"])
    evidence["integrity_hash"] = accepted_evidence_hash(evidence)
    binding["source_hash"] = evidence["source_hash"]
    binding["response_public_summary_hash"] = stable_hash(public)
    docs["evidence-report.json"] = _doc_bytes(evidence)
    docs["original-response-public.json"] = _doc_bytes(public)
    docs["original-response-binding-summary.json"] = _doc_bytes(binding)
    _sync_manifest_file(manifest, "evidence-report.json", docs["evidence-report.json"])
    _sync_manifest_file(manifest, "original-response-public.json", docs["original-response-public.json"])
    _sync_manifest_file(manifest, "original-response-binding-summary.json", docs["original-response-binding-summary.json"])
    manifest["source_hash"] = evidence["source_hash"]
    manifest["evidence"]["integrity_hash"] = evidence["integrity_hash"]
    manifest["evidence"]["source_hash"] = evidence["source_hash"]
    manifest["integrity_hash"] = accepted_evidence_manifest_hash(manifest)
    docs["evidence-manifest.json"] = _doc_bytes(manifest)
