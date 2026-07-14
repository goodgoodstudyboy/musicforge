from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent import __version__
from song_agent.ga_readiness import REQUIRED_DOCS, build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.projectio import read_json, write_json
from song_agent.platform.persistence.program import write_program_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_acceptance import (
    UnifiedReleaseProgramContinuityAcceptanceStateError,
    UnifiedReleaseProgramContinuityAcceptanceStore,
)
from song_agent.unified_release_program_continuity_acceptance_verifier import verify_unified_release_program_continuity_acceptance_package
from tests.test_unified_release_program_continuity_distribution import _prepared_kit
from tests.test_unified_release_program_vault import _sha256_bytes


def _prepared_acceptance(tmp_path: Path):
    program_store, _ops, _continuity, distribution, program_id, zipped = _prepared_kit(tmp_path)
    store = UnifiedReleaseProgramContinuityAcceptanceStore(program_store)
    return program_store, distribution, store, program_id, zipped


def _response(distribution, program_id: str, zipped: dict, *, receiver_id: str, role: str, organization: str, decision: str = "accepted") -> dict:
    verification = read_json(distribution.verification_report_path(program_id))
    response_id = f"response-{receiver_id}"
    response = {
        "schema_version": 1,
        "package_type": "musicforge_unified_release_program_continuity_acceptance_response",
        "program_id": program_id,
        "response_id": response_id,
        "kit_sha256": zipped["zip_sha256"],
        "kit_manifest_hash": zipped["manifest_hash"],
        "kit_verification_report_hash": verification["integrity_hash"],
        "receiver_id": receiver_id,
        "receiver_role": role,
        "organization": organization,
        "decision": decision,
        "reviewed_at": "2026-07-08T00:00:00Z",
        "notes": "Reviewed.",
        "findings": [],
    }
    response["payload_hash"] = stable_hash({key: value for key, value in response.items() if key not in {"payload_hash", "integrity_hash", "status", "imported_at"}})
    public = {
        "schema_version": 1,
        "package_type": "musicforge_unified_release_program_continuity_acceptance_response_public_projection",
        "program_id": program_id,
        "response_id": response_id,
        "receiver_id": receiver_id,
        "receiver_role": role,
        "organization": organization,
        "decision": decision,
        "reviewed_at": response["reviewed_at"],
        "notes": response["notes"],
    }
    response_verification = {
        "schema_version": 1,
        "package_type": "musicforge_unified_release_program_continuity_acceptance_response_verification",
        "program_id": program_id,
        "response_id": response_id,
        "status": "passed",
        "payload_hash": response["payload_hash"],
        "receiver_public_projection_hash": stable_hash(public),
        "kit_sha256": response["kit_sha256"],
        "kit_manifest_hash": response["kit_manifest_hash"],
        "kit_verification_report_hash": response["kit_verification_report_hash"],
        "receiver_id": receiver_id,
        "receiver_role": role,
        "organization": organization,
        "decision": decision,
        "redaction_status": "passed",
    }
    response_verification["integrity_hash"] = stable_hash({key: value for key, value in response_verification.items() if key != "integrity_hash"})
    binding = {
        "schema_version": 1,
        "package_type": "musicforge_unified_release_program_continuity_acceptance_response_binding_summary",
        "program_id": program_id,
        "response_id": response_id,
        "receiver_id": receiver_id,
        "receiver_role": role,
        "organization": organization,
        "decision": decision,
        "payload_hash": response["payload_hash"],
        "kit_sha256": response["kit_sha256"],
        "kit_manifest_hash": response["kit_manifest_hash"],
        "kit_verification_report_hash": response["kit_verification_report_hash"],
        "verification_report_hash": response_verification["integrity_hash"],
    }
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    return {"response": response, "response_verification_report": response_verification, "response_binding_summary": binding}


def _accepted_pair(distribution, store: UnifiedReleaseProgramContinuityAcceptanceStore, program_id: str, zipped: dict) -> tuple[dict, dict]:
    first = store.import_response(program_id, _response(distribution, program_id, zipped, receiver_id="receiver-001", role="recovery_owner", organization="Recovery Org"))
    second = store.import_response(program_id, _response(distribution, program_id, zipped, receiver_id="receiver-002", role="external_custodian", organization="Custody Org"))
    accepted_first = store.create_accepted_evidence(program_id, first["response"]["response_id"])
    accepted_second = store.create_accepted_evidence(program_id, second["response"]["response_id"])
    return accepted_first, accepted_second


def test_continuity_acceptance_happy_path_and_signed_guard(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    _accepted_pair(distribution, store, program_id, zipped)

    board = store.refresh_decision_board(program_id)
    signoff = store.signoff_acceptance(program_id, {"signed_by": "continuity chair", "role": "program_owner"})
    zipped_archive = store.build_archive_zip(program_id)
    verified = store.verify_archive_zip(program_id)
    gate = store.gate(program_id, required=True)

    assert board["status"] == "ready_for_signoff"
    assert signoff["status"] == "signed"
    assert Path(zipped_archive["zip_path"]).exists()
    assert verified["status"] == "passed", verified.get("blockers")
    assert gate["status"] == "passed", gate
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.import_response(program_id, _response(distribution, program_id, zipped, receiver_id="receiver-003", role="observer", organization="Late Org"))


def test_continuity_acceptance_rejects_response_without_binding(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    payload = _response(distribution, program_id, zipped, receiver_id="receiver-001", role="recovery_owner", organization="Recovery Org")
    payload["response"].pop("kit_verification_report_hash")

    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.import_response(program_id, payload)


def test_continuity_acceptance_rejects_payload_self_reported_role_without_external_proof(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    payload = dict(_response(distribution, program_id, zipped, receiver_id="receiver-001", role="external_custodian", organization="Forged Org")["response"])

    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.import_response(program_id, payload)


def test_continuity_acceptance_blocks_stale_kit_after_response(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    _accepted_pair(distribution, store, program_id, zipped)

    kit_path = distribution.kit_zip_path(program_id)
    kit_path.write_bytes(kit_path.read_bytes() + b"tamper")
    tampered = distribution.verify_kit(program_id, {"deep": True})
    assert tampered["status"] == "failed"
    rebuilt = distribution.build_kit_zip(program_id)
    if rebuilt["zip_sha256"] == zipped["zip_sha256"]:
        rebuilt = distribution.build_kit_zip(program_id)
    assert rebuilt["zip_sha256"] != zipped["zip_sha256"]
    distribution.verify_kit(program_id, {"deep": True})

    board = store.refresh_decision_board(program_id)

    assert board["status"] == "blocked"
    assert any(row.get("reason") == "accepted_evidence_stale_kit" for row in board.get("conflicts", []))
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.signoff_acceptance(program_id, {"signed_by": "chair", "role": "program_owner"})


def test_continuity_acceptance_blocks_role_forge_before_signoff(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    response = store.import_response(program_id, _response(distribution, program_id, zipped, receiver_id="receiver-001", role="recovery_owner", organization="Recovery Org"))
    accepted = store.create_accepted_evidence(program_id, response["response"]["response_id"])
    evidence_id = accepted["evidence"]["evidence_id"]
    evidence_path = store.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence.json"
    forged = read_json(evidence_path)
    forged["receiver_role"] = "external_custodian"
    forged["integrity_hash"] = stable_hash({key: value for key, value in forged.items() if key != "integrity_hash"})
    write_program_json(evidence_path, forged)

    board = store.refresh_decision_board(program_id, {"policy": {"min_accepted_receipts": 1, "min_organizations": 1, "required_roles": ["external_custodian"]}})

    assert board["status"] == "blocked"
    assert any(row.get("reason") == "accepted_evidence_role_mismatch" for row in board.get("conflicts", []))
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.signoff_acceptance(program_id, {"signed_by": "chair", "role": "program_owner"})


def test_continuity_acceptance_blocks_signed_response_source_tamper_before_archive(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    _accepted_pair(distribution, store, program_id, zipped)
    store.refresh_decision_board(program_id)
    store.signoff_acceptance(program_id, {"signed_by": "continuity chair", "role": "program_owner"})

    response_path = store.response_path(program_id, "response-receiver-001")
    tampered = read_json(response_path)
    tampered["notes"] = "polluted after signoff"
    tampered["integrity_hash"] = stable_hash({key: value for key, value in tampered.items() if key != "integrity_hash"})
    write_json(response_path, tampered)

    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.build_archive_zip(program_id)


def test_continuity_acceptance_blocks_signed_accepted_evidence_tamper_before_archive(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    accepted_first, _accepted_second = _accepted_pair(distribution, store, program_id, zipped)
    store.refresh_decision_board(program_id)
    store.signoff_acceptance(program_id, {"signed_by": "continuity chair", "role": "program_owner"})

    evidence_id = accepted_first["evidence"]["evidence_id"]
    evidence_path = store.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence.json"
    tampered = read_json(evidence_path)
    tampered["organization"] = "Polluted Org"
    tampered["integrity_hash"] = stable_hash({key: value for key, value in tampered.items() if key != "integrity_hash"})
    write_json(evidence_path, tampered)

    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.build_archive_zip(program_id)


@pytest.mark.parametrize(
    ("decision", "reason"),
    [
        ("rejected", "rejected_response_present"),
        ("needs_changes", "needs_changes_response_present"),
    ],
)
def test_continuity_acceptance_blocks_negative_responses(tmp_path: Path, decision: str, reason: str) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    _accepted_pair(distribution, store, program_id, zipped)
    store.import_response(program_id, _response(distribution, program_id, zipped, receiver_id="receiver-003", role="observer", organization="Third Org", decision=decision))

    board = store.refresh_decision_board(program_id)

    assert board["status"] == "blocked"
    assert any(row.get("reason") == reason for row in board.get("conflicts", []))
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        store.signoff_acceptance(program_id, {"signed_by": "chair", "role": "program_owner"})


def test_continuity_acceptance_verifier_rejects_declared_extra_and_full_resign(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    _accepted_pair(distribution, store, program_id, zipped)
    store.refresh_decision_board(program_id)
    store.signoff_acceptance(program_id, {"signed_by": "original chair", "role": "program_owner"})
    archive = store.build_archive_zip(program_id)

    extra_zip = tmp_path / "acceptance-extra.zip"
    _v76_rewrite_zip(Path(archive["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_continuity_acceptance_package(extra_zip, strict=True)

    forged_zip = tmp_path / "acceptance-forged.zip"
    _v76_rewrite_zip(Path(archive["zip_path"]), forged_zip, _full_resign_signer)
    forged = verify_unified_release_program_continuity_acceptance_package(
        forged_zip,
        strict=True,
        require_current_kit=True,
        require_signed=True,
        require_quorum=True,
        continuity_kit_path=distribution.kit_zip_path(program_id),
        continuity_kit_verification_report_path=distribution.verification_report_path(program_id),
        signoff_binding_path=store.signoff_binding_path(program_id),
    )

    assert extra["status"] == "failed"
    assert "urpca_allowed_entries" in extra["blockers"]
    assert forged["status"] == "failed"
    assert "urpca_external_signoff_binding_hash" in forged["blockers"]


def test_ga_verifier_requires_current_continuity_acceptance_binding(tmp_path: Path) -> None:
    _program_store, distribution, store, program_id, zipped = _prepared_acceptance(tmp_path)
    _accepted_pair(distribution, store, program_id, zipped)
    store.refresh_decision_board(program_id)
    store.signoff_acceptance(program_id, {"signed_by": "continuity chair", "role": "program_owner"})
    store.build_archive_zip(program_id)
    store.verify_archive_zip(program_id)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "pyproject.toml").write_text(f'[project]\nversion = "{__version__}"\n', encoding="utf-8")
    (repo_root / "CHANGELOG.md").write_text(f"# Changelog\n\n## v{__version__}\n", encoding="utf-8")
    for rel in REQUIRED_DOCS:
        doc = repo_root / rel
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# Test doc\n", encoding="utf-8")
    report = build_ga_readiness_report(
        repo_root=repo_root,
        require_unified_release_program_continuity_kit=True,
        unified_release_program_continuity_kit_zip_path=distribution.kit_zip_path(program_id),
        unified_release_program_continuity_kit_verification_report_path=distribution.verification_report_path(program_id),
        require_unified_release_program_continuity_acceptance=True,
        unified_release_program_continuity_acceptance_zip_path=store.archive_zip_path(program_id),
        unified_release_program_continuity_acceptance_verification_report_path=store.verification_report_path(program_id),
        unified_release_program_continuity_acceptance_signoff_binding_path=store.signoff_binding_path(program_id),
    )
    report_path = write_ga_readiness_report(report, tmp_path / "ga-readiness-report.json")

    verification = verify_ga_readiness_report(
        report_path,
        require_unified_release_program_continuity_kit=True,
        unified_release_program_continuity_kit_path=distribution.kit_zip_path(program_id),
        unified_release_program_continuity_kit_verification_report_path=distribution.verification_report_path(program_id),
        require_unified_release_program_continuity_acceptance=True,
        unified_release_program_continuity_acceptance_path=store.archive_zip_path(program_id),
        unified_release_program_continuity_acceptance_verification_report_path=store.verification_report_path(program_id),
        unified_release_program_continuity_acceptance_signoff_binding_path=store.signoff_binding_path(program_id),
    )

    checks = {check["check_id"]: check for check in verification["checks"]}
    assert verification["status"] != "failed", verification.get("checks")
    assert checks["ga_readiness_unified_release_program_continuity_acceptance_verification_status"]["status"] == "passed"
    assert checks["ga_readiness_unified_release_program_continuity_acceptance_zip_binding"]["status"] == "passed"
    assert checks["ga_readiness_unified_release_program_continuity_acceptance_ga_binding"]["status"] == "passed"


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[rel] = b"unexpected continuity acceptance file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _full_resign_signer(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["signoff/continuity-acceptance-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged chair"
    signoff["role"] = "forged_role"
    signoff["reason"] = "forged reason"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["signoff/continuity-acceptance-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    history_rows = []
    previous = ""
    for line in entries["signoff/continuity-acceptance-history.jsonl"].decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "continuity_acceptance_signoff_created":
            event["signed_by"] = signoff["signed_by"]
            event["role"] = signoff["role"]
            event["reason"] = signoff["reason"]
            event["signoff_hash"] = signoff["integrity_hash"]
            event["signoff_payload_hash"] = signoff["payload_hash"]
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        history_rows.append(event)
    entries["signoff/continuity-acceptance-history.jsonl"] = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in history_rows).encode("utf-8")
    binding = json.loads(entries["signoff/continuity-acceptance-signoff-binding-summary.json"].decode("utf-8"))
    binding["signed_by"] = signoff["signed_by"]
    binding["role"] = signoff["role"]
    binding["reason"] = signoff["reason"]
    binding["signoff_hash"] = signoff["integrity_hash"]
    binding["signoff_payload_hash"] = signoff["payload_hash"]
    binding["history_event_hash"] = history_rows[-1]["event_hash"]
    binding["history_event_payload_hash"] = history_rows[-1]["payload_hash"]
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["signoff/continuity-acceptance-signoff-binding-summary.json"] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    for row in manifest["files"]:
        if row["path"] in {
            "signoff/continuity-acceptance-signoff.json",
            "signoff/continuity-acceptance-signoff-binding-summary.json",
            "signoff/continuity-acceptance-history.jsonl",
        }:
            row["sha256"] = _sha256_bytes(entries[row["path"]])
            row["size_bytes"] = len(entries[row["path"]])
    manifest["source"]["signoff_hash"] = signoff["integrity_hash"]
    manifest["source"]["signoff_binding_hash"] = binding["integrity_hash"]
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries
