from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_acceptance import UnifiedReleaseProgramContinuityAcceptanceStateError
from song_agent.unified_release_program_continuity_acceptance_change import (
    RESET_ACTION,
    UnifiedReleaseProgramContinuityAcceptanceChangeStateError,
    UnifiedReleaseProgramContinuityAcceptanceChangeStore,
)
from song_agent.unified_release_program_continuity_acceptance_change_verifier import verify_unified_release_program_continuity_acceptance_change_package
from tests.test_unified_release_program_continuity_acceptance import _accepted_pair, _prepared_acceptance
from tests.test_unified_release_program_vault import _sha256_bytes


def _signed_acceptance(tmp_path: Path):
    program_store, distribution, acceptance, program_id, zipped = _prepared_acceptance(tmp_path)
    _accepted_pair(distribution, acceptance, program_id, zipped)
    acceptance.refresh_decision_board(program_id)
    acceptance.signoff_acceptance(program_id, {"signed_by": "continuity chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    acceptance.verify_archive_zip(program_id)
    change = UnifiedReleaseProgramContinuityAcceptanceChangeStore(program_store)
    return program_store, distribution, acceptance, change, program_id


def test_continuity_acceptance_change_reset_and_successor_lifecycle(tmp_path: Path) -> None:
    _program_store, _distribution, acceptance, change, program_id = _signed_acceptance(tmp_path)

    request = change.create_change_request(program_id, {"reason": "Need successor board."})
    approval = change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "owner"})
    proof = change.reset_acceptance_signoff(program_id, request["change_request_id"], {"reset_by": "owner"})

    assert approval["status"] == "approved"
    assert proof["status"] == "applied"
    assert acceptance.latest_signoff_state(program_id)["status"] == "reset"
    assert change.gate(program_id, required=True)["status"] == "failed"
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceStateError):
        acceptance.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceChangeStateError):
        change.reset_acceptance_signoff(program_id, request["change_request_id"], {"reset_by": "owner"})

    acceptance.refresh_decision_board(program_id)
    successor = acceptance.signoff_acceptance(program_id, {"signed_by": "successor chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    acceptance.verify_archive_zip(program_id)
    change_archive = change.build_archive_zip(program_id)
    verified = change.verify_archive_zip(program_id)
    gate = change.gate(program_id, required=True)

    assert successor["status"] == "signed"
    assert Path(change_archive["zip_path"]).exists()
    assert verified["status"] == "passed", verified.get("blockers")
    assert gate["status"] == "passed", gate


def test_continuity_acceptance_change_reset_requires_allowed_action(tmp_path: Path) -> None:
    _program_store, _distribution, _acceptance, change, program_id = _signed_acceptance(tmp_path)

    request = change.create_change_request(
        program_id,
        {
            "change_request_id": "cr-wrong-action",
            "change_type": "reset_continuity_acceptance_signoff",
            "allowed_actions": ["refresh_continuity_acceptance_report"],
        },
    )
    change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "owner", "approved_actions": ["refresh_continuity_acceptance_report"]})

    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceChangeStateError):
        change.reset_acceptance_signoff(program_id, request["change_request_id"])


def test_continuity_acceptance_change_verifier_rejects_declared_extra(tmp_path: Path) -> None:
    _program_store, _distribution, acceptance, change, program_id = _signed_acceptance(tmp_path)
    request = change.create_change_request(program_id)
    change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "owner"})
    change.reset_acceptance_signoff(program_id, request["change_request_id"])
    acceptance.refresh_decision_board(program_id)
    acceptance.signoff_acceptance(program_id, {"signed_by": "successor chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    acceptance.verify_archive_zip(program_id)
    zipped = change.build_archive_zip(program_id)

    extra_zip = tmp_path / "change-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    report = verify_unified_release_program_continuity_acceptance_change_package(extra_zip, strict=True)

    assert report["status"] == "failed"
    assert "urpca_cc_allowed_entries" in report["blockers"]


def test_continuity_acceptance_change_blocks_current_acceptance_tamper(tmp_path: Path) -> None:
    _program_store, _distribution, acceptance, change, program_id = _signed_acceptance(tmp_path)
    request = change.create_change_request(program_id)
    change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "owner"})
    change.reset_acceptance_signoff(program_id, request["change_request_id"])
    acceptance.refresh_decision_board(program_id)
    acceptance.signoff_acceptance(program_id, {"signed_by": "successor chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    acceptance.verify_archive_zip(program_id)
    change.build_archive_zip(program_id)
    change.verify_archive_zip(program_id)

    signoff = read_json(acceptance.signoff_path(program_id))
    signoff["signed_by"] = "tampered successor"
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    write_json(acceptance.signoff_path(program_id), signoff)

    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceChangeStateError):
        change.build_archive_zip(program_id)


def test_continuity_acceptance_change_rejects_reset_proof_full_resign(tmp_path: Path) -> None:
    _program_store, _distribution, acceptance, change, program_id = _signed_acceptance(tmp_path)
    request = change.create_change_request(program_id)
    change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "owner"})
    proof = change.reset_acceptance_signoff(program_id, request["change_request_id"])
    acceptance.refresh_decision_board(program_id)
    acceptance.signoff_acceptance(program_id, {"signed_by": "successor chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    acceptance.verify_archive_zip(program_id)
    zipped = change.build_archive_zip(program_id)

    tampered_zip = tmp_path / "reset-proof-resigned.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), tampered_zip, lambda entries: _tamper_reset_proof(entries, str(proof["reset_id"])))
    offline = verify_unified_release_program_continuity_acceptance_change_package(tampered_zip, strict=True)

    assert offline["status"] == "failed"
    assert any(blocker.startswith(f"urpca_cc_reset_{str(proof['reset_id']).replace('-', '_')}_target_") for blocker in offline["blockers"])

    local_proof = read_json(change.reset_proof_path(program_id, str(proof["reset_id"])))
    local_proof["previous_signoff_hash"] = "f" * 64
    local_proof["previous_archive_zip_sha256"] = "e" * 64
    local_proof["integrity_hash"] = stable_hash({key: value for key, value in local_proof.items() if key != "integrity_hash"})
    write_json(change.reset_proof_path(program_id, str(proof["reset_id"])), local_proof)
    local_binding = read_json(change.reset_binding_path(program_id, str(proof["reset_id"])))
    local_binding["reset_proof_hash"] = local_proof["integrity_hash"]
    local_binding["integrity_hash"] = stable_hash({key: value for key, value in local_binding.items() if key != "integrity_hash"})
    write_json(change.reset_binding_path(program_id, str(proof["reset_id"])), local_binding)

    with pytest.raises(UnifiedReleaseProgramContinuityAcceptanceChangeStateError):
        change.build_archive_zip(program_id)


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/extra.txt"
    entries[rel] = b"unexpected change-control file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _tamper_reset_proof(entries: dict[str, bytes], reset_id: str) -> dict[str, bytes]:
    proof_path = f"rp/{reset_id}/proof.json"
    binding_path = f"rp/{reset_id}/binding.json"
    proof = json.loads(entries[proof_path].decode("utf-8"))
    proof["previous_signoff_hash"] = "f" * 64
    proof["previous_archive_zip_sha256"] = "e" * 64
    proof["integrity_hash"] = stable_hash({key: value for key, value in proof.items() if key != "integrity_hash"})
    entries[proof_path] = json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    binding = json.loads(entries[binding_path].decode("utf-8"))
    binding["reset_proof_hash"] = proof["integrity_hash"]
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries[binding_path] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    for row in manifest["files"]:
        rel = row["path"]
        row["sha256"] = _sha256_bytes(entries[rel])
        row["size_bytes"] = len(entries[rel])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries
