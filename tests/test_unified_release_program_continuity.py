from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity import UnifiedReleaseProgramContinuityStateError, UnifiedReleaseProgramContinuityStore
from song_agent.unified_release_program_continuity_verifier import verify_unified_release_program_continuity_package
from tests.test_unified_release_program_vault import _sha256_bytes
from tests.test_unified_release_program_vault_operations import _prepared_vault_operations


def _prepared_continuity(tmp_path: Path):
    program_store, _vault_store, ops, program_id = _prepared_vault_operations(tmp_path)
    ops.signoff_operations(program_id, {"signed_by": "custody chair"})
    ops.build_archive_zip(program_id)
    ops.verify_archive_zip(program_id, {"deep": True, "require_signed": True, "require_current_vault": True})
    continuity = UnifiedReleaseProgramContinuityStore(program_store)
    continuity.init_policy(program_id)
    continuity.create_recovery_plan(program_id)
    drill = continuity.run_recovery_drill(program_id)
    assert drill["status"] == "passed", drill.get("blockers")
    runbook = continuity.generate_runbook(program_id)
    assert runbook["status"] == "ready", runbook
    return program_store, ops, continuity, program_id


def test_unified_release_program_continuity_happy_path(tmp_path: Path) -> None:
    _program_store, ops, continuity, program_id = _prepared_continuity(tmp_path)

    signoff = continuity.signoff_continuity(program_id, {"signed_by": "continuity lead"})
    zipped = continuity.build_archive_zip(program_id)
    report = continuity.verify_archive_zip(program_id, {"deep_restore": True, "require_signed": True, "require_current_vault_operations": True})
    standalone = verify_unified_release_program_continuity_package(
        zipped["zip_path"],
        strict=True,
        deep_restore=True,
        require_signed=True,
        require_current_vault_operations=True,
        signoff_binding_path=continuity.signoff_binding_path(program_id),
        vault_operations_archive_path=ops.archive_zip_path(program_id),
        vault_operations_verification_report_path=ops.verification_report_path(program_id),
        vault_operations_signoff_binding_path=ops.signoff_binding_path(program_id),
    )

    assert signoff["status"] == "signed"
    assert Path(zipped["zip_path"]).exists()
    assert report["status"] == "passed", report.get("blockers")
    assert standalone["status"] == "passed", standalone.get("blockers")
    with pytest.raises(UnifiedReleaseProgramContinuityStateError):
        continuity.run_recovery_drill(program_id)


def test_unified_release_program_continuity_requires_external_signoff_binding(tmp_path: Path) -> None:
    _program_store, ops, continuity, program_id = _prepared_continuity(tmp_path)
    continuity.signoff_continuity(program_id, {"signed_by": "continuity lead"})
    zipped = continuity.build_archive_zip(program_id)

    missing = verify_unified_release_program_continuity_package(
        zipped["zip_path"],
        strict=True,
        deep_restore=True,
        require_signed=True,
        require_current_vault_operations=True,
        vault_operations_archive_path=ops.archive_zip_path(program_id),
        vault_operations_verification_report_path=ops.verification_report_path(program_id),
        vault_operations_signoff_binding_path=ops.signoff_binding_path(program_id),
    )

    assert missing["status"] == "failed"
    assert "urpc_external_signoff_binding_required" in missing["blockers"]


def test_unified_release_program_continuity_rejects_declared_extra_and_signoff_full_resign(tmp_path: Path) -> None:
    _program_store, ops, continuity, program_id = _prepared_continuity(tmp_path)
    continuity.signoff_continuity(program_id, {"signed_by": "original signer"})
    zipped = continuity.build_archive_zip(program_id)

    extra_zip = tmp_path / "continuity-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_continuity_package(
        extra_zip,
        strict=True,
        deep_restore=True,
        require_signed=True,
        require_current_vault_operations=True,
        signoff_binding_path=continuity.signoff_binding_path(program_id),
        vault_operations_archive_path=ops.archive_zip_path(program_id),
        vault_operations_verification_report_path=ops.verification_report_path(program_id),
        vault_operations_signoff_binding_path=ops.signoff_binding_path(program_id),
    )
    assert extra["status"] == "failed"
    assert "urpc_allowed_entries" in extra["blockers"]
    assert "urpc_deep_preflight" in extra["blockers"]

    forged_zip = tmp_path / "continuity-forged-signoff.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _forge_signoff_signed_by)
    forged = verify_unified_release_program_continuity_package(
        forged_zip,
        strict=True,
        deep_restore=True,
        require_signed=True,
        require_current_vault_operations=True,
        signoff_binding_path=continuity.signoff_binding_path(program_id),
        vault_operations_archive_path=ops.archive_zip_path(program_id),
        vault_operations_verification_report_path=ops.verification_report_path(program_id),
        vault_operations_signoff_binding_path=ops.signoff_binding_path(program_id),
    )
    assert forged["status"] == "failed"
    assert "urpc_external_signoff_binding_hash" in forged["blockers"]


def test_unified_release_program_continuity_rejects_source_vault_operations_tamper_after_signoff(tmp_path: Path) -> None:
    _program_store, ops, continuity, program_id = _prepared_continuity(tmp_path)
    continuity.signoff_continuity(program_id, {"signed_by": "continuity lead"})
    with ops.archive_zip_path(program_id).open("ab") as fh:
        fh.write(b"tamper")

    with pytest.raises(UnifiedReleaseProgramContinuityStateError):
        continuity.build_archive_zip(program_id)


def test_unified_release_program_continuity_rejects_archive_trailing_bytes(tmp_path: Path) -> None:
    _program_store, ops, continuity, program_id = _prepared_continuity(tmp_path)
    continuity.signoff_continuity(program_id, {"signed_by": "continuity lead"})
    zipped = continuity.build_archive_zip(program_id)
    zip_path = Path(zipped["zip_path"])
    with zip_path.open("ab") as fh:
        fh.write(b"tamper")

    report = verify_unified_release_program_continuity_package(
        zip_path,
        strict=True,
        deep_restore=True,
        require_signed=True,
        require_current_vault_operations=True,
        signoff_binding_path=continuity.signoff_binding_path(program_id),
        vault_operations_archive_path=ops.archive_zip_path(program_id),
        vault_operations_verification_report_path=ops.verification_report_path(program_id),
        vault_operations_signoff_binding_path=ops.signoff_binding_path(program_id),
    )

    assert report["status"] == "failed"
    assert "urpc_no_trailing_data" in report["blockers"]

    with pytest.raises(UnifiedReleaseProgramContinuityStateError):
        continuity.build_archive_zip(program_id)


def test_unified_release_program_continuity_rejects_export_dir_tamper_before_zip(tmp_path: Path) -> None:
    _program_store, _ops, continuity, program_id = _prepared_continuity(tmp_path)
    continuity.signoff_continuity(program_id, {"signed_by": "continuity lead"})
    continuity.export_archive(program_id)
    signoff_path = continuity.export_dir(program_id) / "continuity-signoff.json"
    signoff = read_json(signoff_path)
    signoff["signed_by"] = "forged signer"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    write_json(signoff_path, signoff)

    with pytest.raises(UnifiedReleaseProgramContinuityStateError):
        continuity.build_archive_zip(program_id)


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[rel] = b"unexpected continuity file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_signoff_signed_by(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["continuity-signoff.json"].decode("utf-8"))
    binding = json.loads(entries["continuity-signoff-binding-summary.json"].decode("utf-8"))
    history = [json.loads(line) for line in entries["continuity-history.jsonl"].decode("utf-8").splitlines() if line.strip()]
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
    entries["continuity-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    entries["continuity-signoff-binding-summary.json"] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    entries["continuity-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in history) + "\n").encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    source = manifest.setdefault("source", {})
    source["signoff_hash"] = signoff["integrity_hash"]
    source["signoff_binding_hash"] = binding["integrity_hash"]
    for rel in ("continuity-signoff.json", "continuity-signoff-binding-summary.json", "continuity-history.jsonl"):
        data = entries[rel]
        for row in manifest.get("files", []):
            if row.get("path") == rel:
                row["size_bytes"] = len(data)
                row["sha256"] = _sha256_bytes(data)
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries
