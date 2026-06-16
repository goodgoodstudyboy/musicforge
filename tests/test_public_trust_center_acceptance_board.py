from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.test_public_trust_center import _backslash_zip, _duplicate_zip, _rewrite_zip, _sync_manifest_file
from tests.test_public_trust_center_anchor_registry import _doc_bytes, _read_doc
from tests.test_public_trust_center_distribution_kit_acceptance import _accepted_response, _ready_distribution_kit

from song_agent.public_trust_center_acceptance_board import (
    PublicTrustCenterAcceptanceBoardStateError,
    PublicTrustCenterAcceptanceBoardStore,
    acceptance_board_manifest_hash,
    acceptance_board_report_hash,
    sidecar_hash,
)
from song_agent.public_trust_center_acceptance_board_verifier import verify_public_trust_center_acceptance_board_package
from song_agent.public_trust_center_acceptance_board_signoff_verifier import verify_public_trust_center_acceptance_board_signoff_archive_package
from song_agent.public_trust_center_distribution_kit_acceptance import (
    PublicTrustCenterDistributionKitAcceptanceStore,
    response_payload_hash,
)
from song_agent.releases import stable_hash


def test_acceptance_board_roundtrip_ready(tmp_path: Path, monkeypatch) -> None:
    board_store, kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch)

    report = board_store.refresh_report("ptc-default")
    manifest = board_store.export_board("ptc-default")
    zip_info = board_store.build_zip("ptc-default")
    verification = verify_public_trust_center_acceptance_board_package(
        board_store.zip_path("ptc-default"),
        strict=True,
        require_ready=True,
        require_quorum=True,
        require_no_conflicts=True,
        min_accepted_count=2,
        min_accepted_organizations=2,
        required_roles=["legal", "distribution_partner"],
        distribution_kit_path=kit_store.zip_path("ptc-default"),
        accepted_evidence_dir=acceptance_store.accepted_evidence_root("ptc-default"),
    )

    assert report["readiness"] == "ready"
    assert report["summary"]["accepted_count"] == 2
    assert report["summary"]["accepted_organization_count"] == 2
    assert manifest["package_type"] == "musicforge_public_trust_center_acceptance_board"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"


def test_acceptance_board_blocks_missing_role_and_negative_responses(tmp_path: Path, monkeypatch) -> None:
    board_store, _kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch, second_role="receiver")

    missing_role = board_store.refresh_report("ptc-default")
    assert missing_role["readiness"] == "blocked"
    assert missing_role["summary"]["required_roles_status"] == "failed"

    _import_response(acceptance_store, "ptc-default", "needs-change-001", result="needs_changes", organization="Needs Org", role="legal")
    needs_changes = board_store.refresh_report("ptc-default")
    assert needs_changes["readiness"] == "needs_changes"
    assert needs_changes["summary"]["needs_changes_count"] == 1

    _import_response(acceptance_store, "ptc-default", "rejected-001", result="rejected", organization="Reject Org", role="distribution_partner")
    rejected = board_store.refresh_report("ptc-default")
    assert rejected["readiness"] == "rejected"
    assert rejected["summary"]["rejected_count"] == 1


def test_acceptance_board_stale_source_blocks_export_and_zip(tmp_path: Path, monkeypatch) -> None:
    board_store, _kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch)
    board_store.refresh_report("ptc-default")
    first_response = acceptance_store.list_responses("ptc-default")[0]["response_id"]
    response_path = acceptance_store.response_path("ptc-default", first_response)
    response = json.loads(response_path.read_text(encoding="utf-8"))
    response["review_mode"] = "synthetic"
    response_path.write_text(json.dumps(response, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="stale"):
        board_store.export_board("ptc-default")
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="stale"):
        board_store.build_zip("ptc-default")


def test_acceptance_board_verifier_rejects_edges_and_full_resign(tmp_path: Path, monkeypatch) -> None:
    board_store, kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch)
    board_store.refresh_report("ptc-default")
    board_store.export_board("ptc-default")
    board_store.build_zip("ptc-default")
    source_zip = board_store.zip_path("ptc-default")

    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    declared_extra = _rewrite_zip(source_zip, tmp_path / "declared-extra.zip", _add_declared_extra_file)
    full_resign = _rewrite_zip(source_zip, tmp_path / "full-resign.zip", _tamper_participant_and_resign)
    kit_mismatch = tmp_path / "wrong-kit.zip"
    kit_mismatch.write_bytes(kit_store.zip_path("ptc-default").read_bytes() + b"x")

    assert _has_blocker(verify_public_trust_center_acceptance_board_package(duplicate, strict=True), "ptcab_zip_duplicate_entries")
    assert _has_blocker(verify_public_trust_center_acceptance_board_package(dangerous, strict=True), "ptcab_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_acceptance_board_package(backslash, strict=True), "ptcab_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_acceptance_board_package(declared_extra, strict=True), "ptcab_zip_allowed_entries")
    assert _has_blocker(verify_public_trust_center_acceptance_board_package(full_resign, strict=True, require_ready=True), "ptcab_response_proofs_match")
    assert _has_blocker(
        verify_public_trust_center_acceptance_board_package(
            source_zip,
            strict=True,
            require_ready=True,
            distribution_kit_path=kit_mismatch,
            accepted_evidence_dir=acceptance_store.accepted_evidence_root("ptc-default"),
        ),
        "ptcab_external_distribution_kit_hash",
    )


def test_acceptance_board_verifier_rejects_role_full_resign_with_external_evidence(tmp_path: Path, monkeypatch) -> None:
    board_store, kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch, second_role="receiver")
    blocked = board_store.refresh_report("ptc-default")
    board_store.export_board("ptc-default")
    board_store.build_zip("ptc-default")

    assert blocked["readiness"] == "blocked"
    assert blocked["summary"]["required_roles_status"] == "failed"

    forged = _rewrite_zip(
        board_store.zip_path("ptc-default"),
        tmp_path / "forged-role.zip",
        lambda docs: _forge_second_participant_role_and_resign(docs, "distribution_partner"),
    )
    package_only = verify_public_trust_center_acceptance_board_package(
        forged,
        strict=True,
        require_ready=True,
        require_quorum=True,
        require_no_conflicts=True,
        min_accepted_count=2,
        min_accepted_organizations=2,
        required_roles=["legal", "distribution_partner"],
        distribution_kit_path=kit_store.zip_path("ptc-default"),
    )
    anchored = verify_public_trust_center_acceptance_board_package(
        forged,
        strict=True,
        require_ready=True,
        require_quorum=True,
        require_no_conflicts=True,
        min_accepted_count=2,
        min_accepted_organizations=2,
        required_roles=["legal", "distribution_partner"],
        distribution_kit_path=kit_store.zip_path("ptc-default"),
        accepted_evidence_dir=acceptance_store.accepted_evidence_root("ptc-default"),
    )

    assert package_only["status"] == "failed"
    assert _has_blocker(package_only, "ptcab_external_accepted_evidence_dir_required")
    assert _has_blocker(anchored, "ptcab_participant_external_response_binding")


def test_acceptance_board_signoff_archive_roundtrip_and_immutability(tmp_path: Path, monkeypatch) -> None:
    board_store, kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch)
    board_store.refresh_report("ptc-default")
    board_store.export_board("ptc-default")
    board_store.build_zip("ptc-default")

    signoff = board_store.signoff("ptc-default", {"signed_by": "Reviewer", "reason": "Board quorum is ready for release."})

    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="signed"):
        board_store.refresh_report("ptc-default")
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="signed"):
        board_store.export_board("ptc-default")
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="signed"):
        board_store.build_zip("ptc-default")
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="signed"):
        board_store.create_signoff_draft("ptc-default", {"source": "test"})

    manifest = board_store.export_signoff_archive("ptc-default")
    zip_info = board_store.build_signoff_archive_zip("ptc-default")
    verification = verify_public_trust_center_acceptance_board_signoff_archive_package(
        board_store.signoff_archive_zip_path("ptc-default"),
        strict=True,
        require_signed=True,
        require_current=True,
        require_ready=True,
        board_zip_path=board_store.zip_path("ptc-default"),
        board_verification_report_path=board_store.verification_report_path("ptc-default"),
        distribution_kit_path=kit_store.zip_path("ptc-default"),
        accepted_evidence_dir=acceptance_store.accepted_evidence_root("ptc-default"),
    )

    assert signoff["status"] == "signed"
    assert manifest["package_type"] == "musicforge_public_trust_center_acceptance_board_signoff_archive"
    assert zip_info["sha256"]
    assert verification["status"] == "passed"

    # Deleting generated artifacts must not allow silent rebuild after signoff archive history exists.
    for path in [board_store.signoff_archive_zip_path("ptc-default"), board_store.signoff_archive_dir("ptc-default")]:
        if path.is_dir():
            import shutil

            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="already exported"):
        board_store.export_signoff_archive("ptc-default")
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="already built"):
        board_store.build_signoff_archive_zip("ptc-default")


def test_acceptance_board_signoff_reset_requires_approved_change_request(tmp_path: Path, monkeypatch) -> None:
    board_store, _kit_store, _acceptance_store = _ready_board(tmp_path, monkeypatch)
    board_store.refresh_report("ptc-default")
    board_store.export_board("ptc-default")
    board_store.build_zip("ptc-default")
    board_store.signoff("ptc-default", {"signed_by": "Reviewer", "reason": "Board quorum is ready for release."})

    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="Change Request"):
        board_store.reset_signoff("ptc-default", {"reason": "Reset without approved change request."})

    change = board_store.create_change_request("ptc-default", {"reason": "Need to revise signed board evidence."})
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="approved"):
        board_store.reset_signoff("ptc-default", {"change_request_id": change["change_request_id"], "reason": "Draft cannot reset."})

    approved = board_store.approve_change_request("ptc-default", change["change_request_id"], {"reason": "Approved reset."})
    reset = board_store.reset_signoff("ptc-default", {"change_request_id": approved["change_request_id"], "reason": "Reset with approved CR."})

    assert reset["status"] == "reset"
    assert board_store.read_signoff("ptc-default", default={}) == {}
    with pytest.raises(PublicTrustCenterAcceptanceBoardStateError, match="missing"):
        board_store.reset_signoff("ptc-default", {"change_request_id": approved["change_request_id"], "reason": "Reuse CR."})


def test_acceptance_board_signoff_archive_verifier_rejects_external_evidence_replacement(tmp_path: Path, monkeypatch) -> None:
    board_store, kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch)
    board_store.refresh_report("ptc-default")
    board_store.export_board("ptc-default")
    board_store.build_zip("ptc-default")
    board_store.signoff("ptc-default", {"signed_by": "Reviewer", "reason": "Board quorum is ready for release."})
    board_store.export_signoff_archive("ptc-default")
    board_store.build_signoff_archive_zip("ptc-default")

    evidence_zip = next(acceptance_store.accepted_evidence_root("ptc-default").rglob("accepted-evidence.zip"))
    evidence_zip.write_bytes(evidence_zip.read_bytes() + b"tamper")
    verification = verify_public_trust_center_acceptance_board_signoff_archive_package(
        board_store.signoff_archive_zip_path("ptc-default"),
        strict=True,
        require_signed=True,
        require_current=True,
        require_ready=True,
        board_zip_path=board_store.zip_path("ptc-default"),
        board_verification_report_path=board_store.verification_report_path("ptc-default"),
        distribution_kit_path=kit_store.zip_path("ptc-default"),
        accepted_evidence_dir=acceptance_store.accepted_evidence_root("ptc-default"),
    )

    assert verification["status"] == "failed"
    assert _has_blocker(verification, "ptcabs_external_accepted_evidence_binding")


def _ready_board(tmp_path: Path, monkeypatch, *, second_role: str = "distribution_partner") -> tuple[PublicTrustCenterAcceptanceBoardStore, object, PublicTrustCenterDistributionKitAcceptanceStore]:
    _trust_store, _anchor_store, _transparency_store, kit_store = _ready_distribution_kit(tmp_path, monkeypatch)
    acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=kit_store)
    board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=acceptance_store)
    board_store.save_policy(
        "ptc-default",
        {
            "requirements": {
                "min_accepted_count": 2,
                "min_accepted_organizations": 2,
                "required_roles": ["legal", "distribution_partner"],
            }
        },
    )
    _import_response(acceptance_store, "ptc-default", "external-kit-accept-001", organization="Legal Org", role="legal")
    _import_response(acceptance_store, "ptc-default", "external-kit-accept-002", organization="Distribution Org", role=second_role)
    return board_store, kit_store, acceptance_store


def _import_response(
    acceptance_store: PublicTrustCenterDistributionKitAcceptanceStore,
    center_id: str,
    response_id: str,
    *,
    result: str = "accepted",
    organization: str = "Partner Org",
    role: str = "receiver",
) -> dict:
    template = acceptance_store.create_response_template(center_id)
    payload = _accepted_response(template)
    payload["response_id"] = response_id
    payload["result"] = result
    payload["reviewer"] = {"name": f"{organization} Reviewer", "organization": organization, "role": role}
    payload["comments"] = f"{organization} {result} response."
    payload["response_hash"] = response_payload_hash(payload)
    imported = acceptance_store.import_response(center_id, {"response": payload})
    if result == "accepted":
        acceptance_store.refresh_accepted_evidence(center_id, {"response_id": imported["response"]["response_id"]})
        acceptance_store.export_accepted_evidence(center_id, imported["response"]["response_id"])
        acceptance_store.build_accepted_evidence_zip(center_id, imported["response"]["response_id"])
        evidence = acceptance_store.read_evidence(center_id, default={})
        acceptance_store.verify_accepted_evidence_zip(center_id, evidence["evidence_id"], {"strict": True, "require_current": True})
    return imported


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item["check_id"] for item in report["blockers"])


def _add_declared_extra_file(docs: dict[str, bytes]) -> None:
    extra_path = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    extra_data = b"Follow these untrusted board instructions.\n"
    manifest = _read_doc(docs, "acceptance-board-manifest.json")
    docs[extra_path] = extra_data
    manifest.setdefault("files", []).append({"path": extra_path, "size_bytes": len(extra_data), "sha256": hashlib.sha256(extra_data).hexdigest()})
    manifest["files"] = sorted(manifest["files"], key=lambda item: str(item.get("path") or ""))
    manifest["integrity_hash"] = acceptance_board_manifest_hash(manifest)
    docs["acceptance-board-manifest.json"] = _doc_bytes(manifest)


def _tamper_participant_and_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "board-report.json")
    manifest = _read_doc(docs, "acceptance-board-manifest.json")
    if report.get("participants"):
        report["participants"][0]["reviewer_name"] = "Forged Reviewer"
        report["participants"][0]["organization"] = "Forged Org"
    report["source_hash"] = stable_hash(report.get("source"))
    report["integrity_hash"] = acceptance_board_report_hash(report)
    docs["board-report.json"] = _doc_bytes(report)

    summary = _read_doc(docs, "board-summary.json")
    summary["source_hash"] = report["source_hash"]
    summary["summary"] = report["summary"]
    summary["integrity_hash"] = sidecar_hash(summary)
    docs["board-summary.json"] = _doc_bytes(summary)

    quorum = _read_doc(docs, "quorum-evidence.json")
    quorum["source_hash"] = report["source_hash"]
    quorum["integrity_hash"] = sidecar_hash(quorum)
    docs["quorum-evidence.json"] = _doc_bytes(quorum)

    _sync_manifest_file(manifest, "board-report.json", docs["board-report.json"])
    _sync_manifest_file(manifest, "board-summary.json", docs["board-summary.json"])
    _sync_manifest_file(manifest, "quorum-evidence.json", docs["quorum-evidence.json"])
    manifest["source_hash"] = report["source_hash"]
    manifest.setdefault("board_report", {})["integrity_hash"] = report["integrity_hash"]
    manifest.setdefault("board_report", {})["source_hash"] = report["source_hash"]
    manifest["integrity_hash"] = acceptance_board_manifest_hash(manifest)
    docs["acceptance-board-manifest.json"] = _doc_bytes(manifest)


def _forge_second_participant_role_and_resign(docs: dict[str, bytes], role: str) -> None:
    report = _read_doc(docs, "board-report.json")
    manifest = _read_doc(docs, "acceptance-board-manifest.json")
    participants = report.get("participants") if isinstance(report.get("participants"), list) else []
    if len(participants) < 2:
        return
    response_id = str(participants[1].get("response_id") or "")
    participants[1]["role"] = role
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    summary["required_roles_status"] = "passed"
    report["readiness"] = "ready"
    report["status"] = "passed"
    report["warnings"] = []
    report["summary"] = summary
    report["checks"] = _pass_board_checks(report.get("checks"))
    report["source_hash"] = stable_hash(report.get("source"))
    report["integrity_hash"] = acceptance_board_report_hash(report)
    docs["board-report.json"] = _doc_bytes(report)

    board_summary = _read_doc(docs, "board-summary.json")
    board_summary["source_hash"] = report["source_hash"]
    board_summary["summary"] = report["summary"]
    board_summary["readiness"] = "ready"
    board_summary["status"] = "passed"
    board_summary["integrity_hash"] = sidecar_hash(board_summary)
    docs["board-summary.json"] = _doc_bytes(board_summary)

    quorum = _read_doc(docs, "quorum-evidence.json")
    quorum["source_hash"] = report["source_hash"]
    quorum.setdefault("decision", {})["readiness"] = "ready"
    quorum.setdefault("decision", {})["required_roles_status"] = "passed"
    quorum.setdefault("required_roles", {})[role] = "passed"
    quorum["integrity_hash"] = sidecar_hash(quorum)
    docs["quorum-evidence.json"] = _doc_bytes(quorum)

    conflict = _read_doc(docs, "conflict-report.json")
    conflict["source_hash"] = report["source_hash"]
    conflict["status"] = "passed"
    conflict["conflicts"] = []
    conflict["integrity_hash"] = acceptance_board_report_hash(conflict)
    docs["conflict-report.json"] = _doc_bytes(conflict)

    binding_path = f"response-proofs/{response_id}-binding-proof.json"
    verification_path = f"response-proofs/{response_id}-verification-summary.json"
    if binding_path in docs:
        binding = _read_doc(docs, binding_path)
        binding.setdefault("public_response", {}).setdefault("reviewer", {})["role"] = role
        binding["response_public_summary_hash"] = stable_hash(binding.get("public_response") or {})
        docs[binding_path] = _doc_bytes(binding)
    if verification_path in docs:
        verification = _read_doc(docs, verification_path)
        public = _read_doc(docs, binding_path).get("public_response") if binding_path in docs else {}
        verification["response_public_summary_hash"] = stable_hash(public if isinstance(public, dict) else {})
        docs[verification_path] = _doc_bytes(verification)

    for path in [
        "board-report.json",
        "board-summary.json",
        "quorum-evidence.json",
        "conflict-report.json",
        binding_path,
        verification_path,
    ]:
        if path in docs:
            _sync_manifest_file(manifest, path, docs[path])
    manifest["source_hash"] = report["source_hash"]
    manifest.setdefault("board_report", {})["integrity_hash"] = report["integrity_hash"]
    manifest.setdefault("board_report", {})["source_hash"] = report["source_hash"]
    manifest.setdefault("conflict_report", {})["integrity_hash"] = conflict["integrity_hash"]
    manifest.setdefault("conflict_report", {})["source_hash"] = report["source_hash"]
    manifest["integrity_hash"] = acceptance_board_manifest_hash(manifest)
    docs["acceptance-board-manifest.json"] = _doc_bytes(manifest)


def _pass_board_checks(checks: object) -> list[dict]:
    rows: list[dict] = []
    for item in checks if isinstance(checks, list) else []:
        if isinstance(item, dict):
            row = dict(item)
            row["status"] = "passed"
            rows.append(row)
    return rows
