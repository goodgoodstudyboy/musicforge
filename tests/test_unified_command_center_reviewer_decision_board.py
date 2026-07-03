from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore
from song_agent.unified_command_center_evidence_review import UnifiedCommandCenterEvidenceReviewStore
from song_agent.unified_command_center_reviewer_decision_board import (
    UnifiedCommandCenterReviewerDecisionBoardStateError,
    UnifiedCommandCenterReviewerDecisionBoardStore,
)
from song_agent.unified_command_center_reviewer_decision_board_verifier import verify_unified_command_center_reviewer_decision_board_package
from tests.test_unified_command_center_continuous_review import _ready_signed_ucc


def _board_fixture(tmp_path: Path):
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    continuous = review_store.create_plan(center_id, {"review_id": "uccrv-clear"})
    review_store.run_review(center_id, continuous["review_id"])
    review_store.build_zip(center_id, continuous["review_id"])
    review_store.verify_package(center_id, continuous["review_id"])

    evidence_store = UnifiedCommandCenterEvidenceReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store, review_store=review_store)
    review_id = "uccer-review"
    created = evidence_store.create_review(center_id, {"review_id": review_id, "continuous_review_id": continuous["review_id"], "release_check_report": tmp_path / "release-check.json"})
    replay = evidence_store.run_replay(center_id, review_id, {"release_check_report": tmp_path / "release-check.json"})
    zipped = evidence_store.build_zip(center_id, review_id)
    review_verify = evidence_store.verify_zip(center_id, review_id)
    accepted = []
    for response_id, role, organization in (("response-tech", "technical_reviewer", "QA"), ("response-owner", "release_owner", "Release")):
        response = evidence_store.import_response(
            center_id,
            review_id,
            {
                "response_id": response_id,
                "result": "accepted",
                "review_pack_id": review_id,
                "review_pack_zip_sha256": zipped["zip_sha256"],
                "review_pack_manifest_hash": review_verify["summary"]["manifest_hash"],
                "review_pack_source_hash": created["source"]["source_hash"],
                "replay_result_hash": replay["integrity_hash"],
                "reviewer": {"name": response_id, "organization": organization, "role": role},
                "findings": [],
            },
        )
        evidence = evidence_store.create_acceptance_evidence(center_id, review_id, response["response_id"])
        accepted.append(
            {
                "evidence_id": evidence["evidence_id"],
                "role": role,
                "organization": organization,
                "zip_path": evidence["zip_path"],
                "verification_report_path": str(evidence_store.accepted_evidence_verification_report_path(center_id, review_id, evidence["evidence_id"])),
                "response_verification_report_path": str(evidence_store.accepted_evidence_dir(center_id, review_id, evidence["evidence_id"]) / "response-verification-summary.json"),
            }
        )
    board_store = UnifiedCommandCenterReviewerDecisionBoardStore(store, evidence_review_store=evidence_store)
    return store, evidence_store, board_store, center_id, review_id, zipped, accepted


def test_reviewer_decision_board_lifecycle_and_guards(tmp_path: Path) -> None:
    _store, evidence_store, board_store, center_id, review_id, review_zip, accepted = _board_fixture(tmp_path)
    docs = board_store.create_board(center_id, {"board_id": "uccdb-board", "review_id": review_id, "accepted_evidence": accepted})

    assert docs["decision_report"]["status"] == "ready_for_signoff"
    signoff = board_store.signoff(center_id, "uccdb-board", {"signed_by": "chair"})
    zipped = board_store.build_zip(center_id, "uccdb-board")
    report = verify_unified_command_center_reviewer_decision_board_package(
        zipped["zip_path"],
        strict=True,
        require_signed=True,
        require_quorum=True,
        evidence_review_path=review_zip["zip_path"],
        evidence_review_verification_report_path=evidence_store.verification_report_path(center_id, review_id),
        accepted_evidence_paths=[row["zip_path"] for row in accepted],
        accepted_evidence_verification_report_paths=[row["verification_report_path"] for row in accepted],
        accepted_evidence_response_verification_report_paths=[row["response_verification_report_path"] for row in accepted],
    )
    gate = board_store.gate(center_id, required=True, board_id="uccdb-board")

    assert signoff["status"] == "signed"
    assert report["status"] == "passed", report["blockers"]
    assert gate["status"] == "passed"
    with pytest.raises(UnifiedCommandCenterReviewerDecisionBoardStateError):
        board_store.refresh_board(center_id, "uccdb-board", {})
    board_store.signoff_path(center_id, "uccdb-board").unlink()
    with pytest.raises(UnifiedCommandCenterReviewerDecisionBoardStateError):
        board_store.refresh_board(center_id, "uccdb-board", {})


def test_reviewer_decision_board_verifier_rejects_missing_external_and_declared_extra(tmp_path: Path) -> None:
    _store, evidence_store, board_store, center_id, review_id, review_zip, accepted = _board_fixture(tmp_path)
    board_store.create_board(center_id, {"board_id": "uccdb-board", "review_id": review_id, "accepted_evidence": accepted})
    board_store.signoff(center_id, "uccdb-board", {"signed_by": "chair"})
    zipped = board_store.build_zip(center_id, "uccdb-board")

    missing = verify_unified_command_center_reviewer_decision_board_package(
        zipped["zip_path"],
        strict=True,
        require_signed=True,
        require_quorum=True,
        evidence_review_path=review_zip["zip_path"],
        evidence_review_verification_report_path=evidence_store.verification_report_path(center_id, review_id),
        accepted_evidence_paths=[accepted[0]["zip_path"]],
        accepted_evidence_verification_report_paths=[accepted[0]["verification_report_path"]],
        accepted_evidence_response_verification_report_paths=[accepted[0]["response_verification_report_path"]],
    )
    tampered = tmp_path / "decision-board-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), tampered, _add_declared_extra)
    extra = verify_unified_command_center_reviewer_decision_board_package(tampered, strict=True)

    assert missing["status"] == "failed"
    assert "ucc_decision_board_accepted_evidence_external_binding" in missing["blockers"]
    assert extra["status"] == "failed"
    assert "ucc_decision_board_allowed_entries" in extra["blockers"]


def test_reviewer_decision_board_verifier_rejects_role_full_resign(tmp_path: Path) -> None:
    _store, evidence_store, board_store, center_id, review_id, review_zip, accepted = _board_fixture(tmp_path)
    board_store.create_board(center_id, {"board_id": "uccdb-board", "review_id": review_id, "accepted_evidence": accepted})
    board_store.signoff(center_id, "uccdb-board", {"signed_by": "chair"})
    zipped = board_store.build_zip(center_id, "uccdb-board")
    forged = tmp_path / "decision-board-forged-role.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged, _forge_release_owner_role)

    report = verify_unified_command_center_reviewer_decision_board_package(
        forged,
        strict=True,
        require_signed=True,
        require_quorum=True,
        evidence_review_path=review_zip["zip_path"],
        evidence_review_verification_report_path=evidence_store.verification_report_path(center_id, review_id),
        accepted_evidence_paths=[row["zip_path"] for row in accepted],
        accepted_evidence_verification_report_paths=[row["verification_report_path"] for row in accepted],
        accepted_evidence_response_verification_report_paths=[row["response_verification_report_path"] for row in accepted],
    )

    assert report["status"] == "failed"
    assert "ucc_decision_board_accepted_evidence_external_binding" in report["blockers"]


def test_reviewer_decision_board_blocks_payload_role_override_before_signoff(tmp_path: Path) -> None:
    _store, _evidence_store, board_store, center_id, review_id, _review_zip, accepted = _board_fixture(tmp_path)
    forged = dict(accepted[0])
    assert forged["role"] == "technical_reviewer"
    forged["role"] = "release_owner"

    docs = board_store.create_board(
        center_id,
        {
            "board_id": "uccdb-role-override",
            "review_id": review_id,
            "accepted_evidence": [forged],
            "policy": {
                "min_accepted_count": 1,
                "min_organization_count": 1,
                "required_roles": ["release_owner"],
            },
        },
    )

    item = docs["accepted_evidence_index"]["items"][0]
    assert item["status"] == "failed"
    assert item["role"] == "technical_reviewer"
    assert "accepted_evidence_role_mismatch" in item["blockers"]
    assert docs["decision_report"]["status"] == "blocked"
    with pytest.raises(UnifiedCommandCenterReviewerDecisionBoardStateError):
        board_store.signoff(center_id, "uccdb-role-override", {})


def test_reviewer_decision_board_signoff_does_not_reset_strict_policy(tmp_path: Path) -> None:
    _store, _evidence_store, board_store, center_id, review_id, _review_zip, accepted = _board_fixture(tmp_path)
    strict_policy = {
        "min_accepted_count": 2,
        "min_organization_count": 2,
        "required_roles": ["technical_reviewer", "release_owner", "security_reviewer"],
    }
    docs = board_store.create_board(
        center_id,
        {
            "board_id": "uccdb-strict-policy",
            "review_id": review_id,
            "accepted_evidence": accepted,
            "policy": strict_policy,
        },
    )

    assert docs["decision_report"]["status"] == "blocked"
    assert "quorum:required_roles" in docs["decision_report"]["blockers"]
    with pytest.raises(UnifiedCommandCenterReviewerDecisionBoardStateError):
        board_store.signoff(center_id, "uccdb-strict-policy", {"signed_by": "chair", "policy": {"required_roles": ["technical_reviewer", "release_owner"]}})
    with pytest.raises(UnifiedCommandCenterReviewerDecisionBoardStateError):
        board_store.signoff(center_id, "uccdb-strict-policy", {"signed_by": "chair"})
    stored = read_json(board_store.local_paths_path(center_id, "uccdb-strict-policy"))
    assert stored["policy"]["required_roles"] == ["technical_reviewer", "release_owner", "security_reviewer"]


def test_reviewer_decision_board_blocks_rejection_and_high_findings(tmp_path: Path) -> None:
    _store, _evidence_store, board_store, center_id, review_id, _review_zip, accepted = _board_fixture(tmp_path)
    rejected = {
        "response_id": "rejected-owner",
        "result": "rejected",
        "role": "release_owner",
        "organization": "Release",
        "reviewer": {"name": "Owner", "organization": "Release", "role": "release_owner"},
    }
    board_store.create_board(center_id, {"board_id": "uccdb-rejected", "review_id": review_id, "accepted_evidence": accepted, "responses": [rejected]})
    with pytest.raises(UnifiedCommandCenterReviewerDecisionBoardStateError):
        board_store.signoff(center_id, "uccdb-rejected", {})

    finding = {"severity": "high", "status": "open", "message": "Unresolved reviewer concern"}
    board_store.create_board(center_id, {"board_id": "uccdb-finding", "review_id": review_id, "accepted_evidence": accepted, "findings": [finding]})
    with pytest.raises(UnifiedCommandCenterReviewerDecisionBoardStateError):
        board_store.signoff(center_id, "uccdb-finding", {})


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


def _forge_release_owner_role(entries: dict[str, bytes]) -> dict[str, bytes]:
    accepted = json.loads(entries["accepted-evidence-index.json"].decode("utf-8"))
    for item in accepted.get("items", []):
        if item.get("role") == "release_owner":
            item["role"] = "security_reviewer"
            item.setdefault("reviewer", {})["role"] = "security_reviewer"
            item["item_hash"] = stable_hash(item)
    accepted["integrity_hash"] = stable_hash({key: value for key, value in accepted.items() if key != "integrity_hash"})
    entries["accepted-evidence-index.json"] = json.dumps(accepted, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["accepted_evidence_index_hash"] = accepted["integrity_hash"]
    _sync_manifest_file(manifest, "accepted-evidence-index.json", entries["accepted-evidence-index.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    for row in manifest.get("files", []):
        if row.get("path") == rel:
            row["sha256"] = _sha256_bytes(data)
            row["size_bytes"] = len(data)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
