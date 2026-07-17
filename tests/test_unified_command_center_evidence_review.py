from __future__ import annotations

import json
from pathlib import Path

from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore
from song_agent.unified_command_center_evidence_review import UnifiedCommandCenterEvidenceReviewStore
from song_agent.unified_command_center_evidence_review_verifier import (
    verify_unified_command_center_evidence_review_acceptance_package,
    verify_unified_command_center_evidence_review_package,
)
from tests.test_unified_command_center_continuous_review import _ready_signed_ucc


def test_unified_command_center_evidence_review_lifecycle(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    release_check_report = tmp_path / "release-check.json"
    continuous = review_store.create_plan(center_id, {"review_id": "uccrv-clear"})
    review_store.run_review(center_id, continuous["review_id"])
    review_store.build_zip(center_id, continuous["review_id"])
    continuous_verification = review_store.verify_package(center_id, continuous["review_id"])
    assert continuous_verification["status"] == "passed"

    evidence_store = UnifiedCommandCenterEvidenceReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store, review_store=review_store)
    created = evidence_store.create_review(center_id, {"review_id": "uccer-review", "continuous_review_id": continuous["review_id"], "release_check_report": release_check_report})
    replay = evidence_store.run_replay(center_id, "uccer-review", {"release_check_report": release_check_report})
    zipped = evidence_store.build_zip(center_id, "uccer-review")
    verification = evidence_store.verify_zip(center_id, "uccer-review")

    assert created["source"]["status"] == "draft"
    assert replay["status"] == "passed", replay.get("steps")
    assert Path(zipped["zip_path"]).exists()
    assert verification["status"] == "passed", verification.get("blockers")

    response = evidence_store.import_response(
        center_id,
        "uccer-review",
        {
            "response_id": "response-001",
            "result": "accepted",
            "review_pack_id": "uccer-review",
            "review_pack_zip_sha256": zipped["zip_sha256"],
            "review_pack_manifest_hash": verification["summary"]["manifest_hash"],
            "review_pack_source_hash": created["source"]["source_hash"],
            "replay_result_hash": replay["integrity_hash"],
            "reviewer": {"name": "External Reviewer", "organization": "QA", "role": "reviewer"},
            "findings": [],
        },
    )
    accepted = evidence_store.create_acceptance_evidence(center_id, "uccer-review", response["response_id"])
    accepted_verification = verify_unified_command_center_evidence_review_acceptance_package(
        accepted["zip_path"],
        strict=True,
        require_accepted=True,
        review_pack_path=zipped["zip_path"],
        review_pack_verification_report_path=evidence_store.verification_report_path(center_id, "uccer-review"),
        response_verification_report_path=evidence_store.accepted_evidence_dir(center_id, "uccer-review", accepted["evidence_id"]) / "response-verification-summary.json",
    )

    assert response["status"] == "current"
    assert accepted["status"] == "passed"
    assert accepted_verification["status"] == "passed", accepted_verification.get("blockers")

    response_verification = evidence_store.accepted_evidence_dir(center_id, "uccer-review", accepted["evidence_id"]) / "response-verification-summary.json"
    stale_gate = evidence_store.gate(
        center_id,
        required=True,
        review_id="uccer-review",
        require_accepted=True,
        acceptance_zip_path=tmp_path / "missing-accepted-evidence.zip",
        acceptance_verification_report_path=evidence_store.accepted_evidence_verification_report_path(center_id, "uccer-review", accepted["evidence_id"]),
        acceptance_response_verification_report_path=response_verification,
    )
    passed_gate = evidence_store.gate(
        center_id,
        required=True,
        review_id="uccer-review",
        require_accepted=True,
        acceptance_zip_path=accepted["zip_path"],
        acceptance_verification_report_path=evidence_store.accepted_evidence_verification_report_path(center_id, "uccer-review", accepted["evidence_id"]),
        acceptance_response_verification_report_path=response_verification,
    )

    assert stale_gate["status"] == "failed"
    assert passed_gate["status"] == "passed"


def test_evidence_review_verifier_rejects_declared_extra_and_missing_external(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    release_check_report = tmp_path / "release-check.json"
    continuous = review_store.create_plan(center_id, {"review_id": "uccrv-clear"})
    review_store.run_review(center_id, continuous["review_id"])
    review_store.build_zip(center_id, continuous["review_id"])
    review_store.verify_package(center_id, continuous["review_id"])
    evidence_store = UnifiedCommandCenterEvidenceReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store, review_store=review_store)
    evidence_store.create_review(center_id, {"review_id": "uccer-review", "continuous_review_id": continuous["review_id"], "release_check_report": release_check_report})
    evidence_store.run_replay(center_id, "uccer-review", {"release_check_report": release_check_report})
    zipped = evidence_store.build_zip(center_id, "uccer-review")

    missing = verify_unified_command_center_evidence_review_package(zipped["zip_path"], strict=True, require_replay_passed=True)
    assert missing["status"] == "failed"
    assert "ucc_review_ucc_external_binding_zip_required" in missing["blockers"]

    tampered = tmp_path / "evidence-review-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), tampered, _add_declared_extra)
    extra = verify_unified_command_center_evidence_review_package(tampered, strict=True)
    assert extra["status"] == "failed"
    assert "ucc_review_allowed_entries" in extra["blockers"]


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra_name = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra_name] = b"unexpected\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra_name, "size_bytes": len(entries[extra_name]), "sha256": _sha256_bytes(entries[extra_name])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
