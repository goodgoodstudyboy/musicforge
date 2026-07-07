from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_vault_operations import UnifiedReleaseProgramVaultOperationsStateError, UnifiedReleaseProgramVaultOperationsStore
from song_agent.unified_release_program_vault_operations_verifier import verify_unified_release_program_vault_operations_package
from tests.test_unified_release_program_vault import _sha256_bytes, _signed_handoff_with_accepted_evidence


def _prepared_vault_operations(tmp_path: Path):
    program_store, vault_store, program_id = _signed_handoff_with_accepted_evidence(tmp_path)
    vault_store.refresh_vault(program_id)
    vault_store.build_vault_zip(program_id)
    vault_verification = vault_store.verify_vault_zip(program_id, {"deep": True, "require_anchor": True})
    assert vault_verification["status"] == "passed", vault_verification.get("blockers")

    ops = UnifiedReleaseProgramVaultOperationsStore(program_store)
    ops.init_policy(program_id)
    ops.register_vault(program_id)
    review = ops.run_custody_review(program_id)
    assert review["status"] == "passed", review.get("blockers")
    transfer = ops.create_transfer_pack(program_id)
    assert transfer["status"] == "ready", transfer.get("blockers")
    return program_store, vault_store, ops, program_id


def test_unified_release_program_vault_operations_happy_path(tmp_path: Path) -> None:
    _program_store, _vault_store, ops, program_id = _prepared_vault_operations(tmp_path)

    signoff = ops.signoff_operations(program_id, {"signed_by": "custody chair"})
    zipped = ops.build_archive_zip(program_id)
    report = ops.verify_archive_zip(program_id, {"deep": True, "require_signed": True, "require_current_vault": True})
    standalone = verify_unified_release_program_vault_operations_package(
        zipped["zip_path"],
        strict=True,
        deep=True,
        require_signed=True,
        require_current_vault=True,
        signoff_binding_path=ops.signoff_binding_path(program_id),
    )

    assert signoff["status"] == "signed"
    assert Path(zipped["zip_path"]).exists()
    assert report["status"] == "passed", report.get("blockers")
    assert standalone["status"] == "passed", standalone.get("blockers")
    with pytest.raises(UnifiedReleaseProgramVaultOperationsStateError):
        ops.run_custody_review(program_id)


def test_unified_release_program_vault_operations_requires_external_signoff_binding(tmp_path: Path) -> None:
    _program_store, _vault_store, ops, program_id = _prepared_vault_operations(tmp_path)
    ops.signoff_operations(program_id, {"signed_by": "custody chair"})
    zipped = ops.build_archive_zip(program_id)

    missing = verify_unified_release_program_vault_operations_package(
        zipped["zip_path"],
        strict=True,
        deep=True,
        require_signed=True,
        require_current_vault=True,
    )

    assert missing["status"] == "failed"
    assert "urpvo_external_signoff_binding_required" in missing["blockers"]


def test_unified_release_program_vault_operations_rejects_declared_extra_and_signoff_full_resign(tmp_path: Path) -> None:
    _program_store, _vault_store, ops, program_id = _prepared_vault_operations(tmp_path)
    ops.signoff_operations(program_id, {"signed_by": "original signer"})
    zipped = ops.build_archive_zip(program_id)

    extra_zip = tmp_path / "vault-ops-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_vault_operations_package(extra_zip, strict=True, deep=True, require_signed=True, require_current_vault=True, signoff_binding_path=ops.signoff_binding_path(program_id))
    assert extra["status"] == "failed"
    assert "urpvo_allowed_entries" in extra["blockers"]
    assert "urpvo_deep_preflight" in extra["blockers"]

    forged_zip = tmp_path / "vault-ops-forged-signoff.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _forge_signoff_signed_by)
    forged = verify_unified_release_program_vault_operations_package(forged_zip, strict=True, deep=True, require_signed=True, require_current_vault=True, signoff_binding_path=ops.signoff_binding_path(program_id))
    assert forged["status"] == "failed"
    assert "urpvo_external_signoff_binding_hash" in forged["blockers"]


def test_unified_release_program_vault_operations_signed_mutation_and_revoke_gate(tmp_path: Path) -> None:
    _program_store, _vault_store, ops, program_id = _prepared_vault_operations(tmp_path)

    revoked = ops.revoke_vault(program_id, {"reason": "custody breach"})
    assert revoked["status"] == "revoked"
    with pytest.raises(UnifiedReleaseProgramVaultOperationsStateError):
        ops.signoff_operations(program_id, {"signed_by": "custody chair"})


def test_unified_release_program_vault_operations_rejects_resigned_registry_current_vault(tmp_path: Path) -> None:
    _program_store, _vault_store, ops, program_id = _prepared_vault_operations(tmp_path)
    registry = read_json(ops.registry_path(program_id))
    current_id = registry["current_generation_id"]
    for row in registry["generations"]:
        if row.get("generation_id") == current_id:
            row["vault"]["vault_zip_sha256"] = "0" * 64
            break
    registry["summary"]["current_vault_zip_sha256"] = "0" * 64
    registry["integrity_hash"] = stable_hash({key: value for key, value in registry.items() if key != "integrity_hash"})
    write_json(ops.registry_path(program_id), registry)

    review = ops.run_custody_review(program_id)
    transfer = ops.create_transfer_pack(program_id)

    assert review["status"] == "failed"
    assert "registry_current_vault_zip_sha256" in review["blockers"]
    assert transfer["status"] == "blocked"
    with pytest.raises(UnifiedReleaseProgramVaultOperationsStateError):
        ops.signoff_operations(program_id, {"signed_by": "custody chair"})


def test_unified_release_program_vault_operations_rejects_source_vault_tamper_after_signoff(tmp_path: Path) -> None:
    _program_store, vault_store, ops, program_id = _prepared_vault_operations(tmp_path)
    ops.signoff_operations(program_id, {"signed_by": "custody chair"})
    with vault_store.zip_path(program_id).open("ab") as fh:
        fh.write(b"tamper")

    with pytest.raises(UnifiedReleaseProgramVaultOperationsStateError):
        ops.build_archive_zip(program_id)


def test_unified_release_program_vault_operations_rejects_archive_trailing_bytes(tmp_path: Path) -> None:
    _program_store, _vault_store, ops, program_id = _prepared_vault_operations(tmp_path)
    ops.signoff_operations(program_id, {"signed_by": "custody chair"})
    zipped = ops.build_archive_zip(program_id)
    zip_path = Path(zipped["zip_path"])
    with zip_path.open("ab") as fh:
        fh.write(b"tamper")

    report = verify_unified_release_program_vault_operations_package(
        zip_path,
        strict=True,
        deep=True,
        require_signed=True,
        require_current_vault=True,
        signoff_binding_path=ops.signoff_binding_path(program_id),
    )

    assert report["status"] == "failed"
    assert "urpvo_no_trailing_data" in report["blockers"]



def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[rel] = b"unexpected vault operations file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_signoff_signed_by(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["vault-operations-signoff.json"].decode("utf-8"))
    binding = json.loads(entries["vault-operations-signoff-binding-summary.json"].decode("utf-8"))
    history = [json.loads(line) for line in entries["vault-operations-history.jsonl"].decode("utf-8").splitlines() if line.strip()]
    signoff["signed_by"] = "forged signer"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    binding["signed_by"] = "forged signer"
    binding["signoff_hash"] = signoff["integrity_hash"]
    binding["signoff_payload_hash"] = signoff["payload_hash"]
    if history:
        history[-1]["signed_by"] = "forged signer"
        history[-1]["signoff_hash"] = signoff["integrity_hash"]
        history[-1]["payload_hash"] = stable_hash({key: value for key, value in history[-1].items() if key not in {"payload_hash", "event_hash"}})
        history[-1]["event_hash"] = stable_hash({key: value for key, value in history[-1].items() if key != "event_hash"})
        binding["latest_history_event_hash"] = history[-1]["event_hash"]
        binding["latest_history_payload_hash"] = history[-1]["payload_hash"]
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["vault-operations-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    entries["vault-operations-signoff-binding-summary.json"] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    entries["vault-operations-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in history) + "\n").encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    source = manifest.setdefault("source", {})
    source["signoff_hash"] = signoff["integrity_hash"]
    source["signoff_binding_hash"] = binding["integrity_hash"]
    for rel in ("vault-operations-signoff.json", "vault-operations-signoff-binding-summary.json", "vault-operations-history.jsonl"):
        data = entries[rel]
        for row in manifest.get("files", []):
            if row.get("path") == rel:
                row["size_bytes"] = len(data)
                row["sha256"] = _sha256_bytes(data)
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries
