from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.projectio import read_json, write_json
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_command_center import (
    UnifiedReleaseProgramContinuityCommandCenterStateError,
    UnifiedReleaseProgramContinuityCommandCenterStore,
)
from song_agent.unified_release_program_continuity_command_center_verifier import verify_unified_release_program_continuity_command_center_package
from tests.test_ga_readiness import _write_repo
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_unified_release_program_continuity_acceptance_change import _signed_acceptance
from tests.test_unified_release_program_vault import _sha256_bytes


def _prepared_command_center(tmp_path: Path):
    program_store, _distribution, _acceptance, change, program_id = _signed_acceptance(tmp_path)
    request = change.create_change_request(program_id)
    change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "owner"})
    change.reset_acceptance_signoff(program_id, request["change_request_id"], {"reset_by": "owner"})
    _acceptance.refresh_decision_board(program_id)
    _acceptance.signoff_acceptance(program_id, {"signed_by": "successor chair", "role": "program_owner"})
    _acceptance.build_archive_zip(program_id)
    _acceptance.verify_archive_zip(program_id)
    change.refresh_lifecycle_audit(program_id)
    change.build_archive_zip(program_id)
    change.verify_archive_zip(program_id)
    command = UnifiedReleaseProgramContinuityCommandCenterStore(program_store)
    return program_store, change, command, program_id


def test_continuity_command_center_happy_path_and_gate(tmp_path: Path) -> None:
    _program_store, _change, command, program_id = _prepared_command_center(tmp_path)

    report = command.refresh_command_center(program_id)
    zipped = command.build_zip(program_id)
    verified = command.verify_zip(program_id)
    gate = command.gate(program_id, required=True)

    assert report["status"] == "ready", report.get("blockers")
    assert Path(zipped["zip_path"]).exists()
    assert verified["status"] == "passed", verified.get("blockers")
    assert gate["status"] == "passed", gate


def test_continuity_command_center_verifier_rejects_declared_extra_and_trailing(tmp_path: Path) -> None:
    _program_store, _change, command, program_id = _prepared_command_center(tmp_path)
    zipped = command.build_zip(program_id)

    extra_zip = tmp_path / "command-center-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_continuity_command_center_package(extra_zip, strict=True, deep=True, require_ready=True, evidence_manifest_path=command.local_evidence_manifest_path(program_id))

    trailing_zip = tmp_path / "command-center-trailing.zip"
    trailing_zip.write_bytes(Path(zipped["zip_path"]).read_bytes() + b"tamper")
    trailing = verify_unified_release_program_continuity_command_center_package(trailing_zip, strict=True, deep=True, require_ready=True, evidence_manifest_path=command.local_evidence_manifest_path(program_id))

    assert extra["status"] == "failed"
    assert "urpccc_allowed_entries" in extra["blockers"]
    assert trailing["status"] == "failed"
    assert "urpccc_no_trailing_data" in trailing["blockers"]


def test_continuity_command_center_verifier_rechecks_runtime_evidence(tmp_path: Path) -> None:
    _program_store, change, command, program_id = _prepared_command_center(tmp_path)
    zipped = command.build_zip(program_id)

    archive = change.archive_zip_path(program_id)
    archive.write_bytes(archive.read_bytes() + b"tamper")
    report = verify_unified_release_program_continuity_command_center_package(
        zipped["zip_path"],
        strict=True,
        deep=True,
        require_ready=True,
        evidence_manifest_path=command.local_evidence_manifest_path(program_id),
    )

    assert report["status"] == "failed"
    assert any("continuity_acceptance_change_control" in blocker for blocker in report["blockers"])


def test_runtime_tamper_blocks_store_release_and_ga(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _program_store, change, command, program_id = _prepared_command_center(tmp_path)
    zipped = command.build_zip(program_id)
    verified = command.verify_zip(program_id)
    ga_root = tmp_path / "ga-repo"
    _write_repo(ga_root)
    ga_report = build_ga_readiness_report(
        repo_root=ga_root,
        allow_dirty=True,
        require_unified_release_program_continuity_command_center=True,
        unified_release_program_continuity_command_center_zip_path=zipped["zip_path"],
        unified_release_program_continuity_command_center_verification_report_path=command.verification_report_path(program_id),
        unified_release_program_continuity_command_center_external_evidence_manifest_path=command.local_evidence_manifest_path(program_id),
    )
    ga_path = tmp_path / "ga-command-center.json"
    write_ga_readiness_report(ga_report, ga_path)
    assert verified["status"] == "passed"
    assert next(row for row in ga_report["checks"] if row["check_id"] == "ga.unified_release_program_continuity_command_center")["status"] == "passed"

    archive = change.archive_zip_path(program_id)
    archive.write_bytes(archive.read_bytes() + b"tamper")
    refreshed = command.refresh_command_center(program_id)
    inventory = read_json(command.inventory_path(program_id))
    changed = next(row for row in inventory["items"] if row["component_type"] == "continuity_acceptance_change_control")
    gate = command.gate(program_id, required=True)

    assert refreshed["status"] == "blocked"
    assert changed["report_status"] == "passed"
    assert changed["runtime_status"] == "failed"
    assert changed["runtime_blockers"]
    assert changed["evidence_status"] == "runtime_failed"
    assert changed["current"] is False
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterStateError):
        command.export_package(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterStateError):
        command.build_zip(program_id)
    assert gate["status"] == "failed"

    server = start_test_server()
    try:
        create_status, created = request_json(server, "POST", "/api/releases", {"name": "Command Center gate release"})
        release_id = created["release"]["release_id"]
        signoff_status, _signoff = request_json(
            server,
            "POST",
            f"/api/releases/{release_id}/signoff",
            {
                "signed_by": "release owner",
                "force": True,
                "override_reason": "Runtime evidence must remain non-overridable.",
                "require_unified_release_program_continuity_command_center": True,
                "unified_release_program_id": program_id,
                "unified_release_program_continuity_command_center": str(command.zip_path(program_id)),
                "unified_release_program_continuity_command_center_verification_report": str(command.verification_report_path(program_id)),
                "unified_release_program_continuity_command_center_external_evidence_manifest": str(command.local_evidence_manifest_path(program_id)),
            },
        )
    finally:
        stop_test_server(server)
    assert create_status == 201
    assert signoff_status == 409

    ga_verification = verify_ga_readiness_report(
        ga_path,
        require_unified_release_program_continuity_command_center=True,
        unified_release_program_continuity_command_center_path=command.zip_path(program_id),
        unified_release_program_continuity_command_center_verification_report_path=command.verification_report_path(program_id),
        unified_release_program_continuity_command_center_external_evidence_manifest_path=command.local_evidence_manifest_path(program_id),
    )
    assert ga_verification["status"] == "failed"


def test_stale_component_verification_report_blocks_package_build(tmp_path: Path) -> None:
    _program_store, change, command, program_id = _prepared_command_center(tmp_path)
    command.build_zip(program_id)
    command.verify_zip(program_id)
    verification = read_json(change.verification_report_path(program_id))
    verification["zip_sha256"] = "f" * 64
    verification["integrity_hash"] = stable_hash({key: value for key, value in verification.items() if key != "integrity_hash"})
    write_json(change.verification_report_path(program_id), verification)

    refreshed = command.refresh_command_center(program_id)
    inventory = read_json(command.inventory_path(program_id))
    changed = next(row for row in inventory["items"] if row["component_type"] == "continuity_acceptance_change_control")

    assert refreshed["status"] == "blocked"
    assert changed["evidence_status"] == "stale"
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterStateError):
        command.export_package(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterStateError):
        command.build_zip(program_id)


def test_acceptance_reset_invalidates_current_command_center(tmp_path: Path) -> None:
    _program_store, change, command, program_id = _prepared_command_center(tmp_path)
    command.build_zip(program_id)
    command.verify_zip(program_id)

    request = change.create_change_request(program_id, {"reason": "Open a successor Acceptance Board."})
    change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "program owner"})
    change.reset_acceptance_signoff(program_id, request["change_request_id"], {"reset_by": "program owner"})

    gate = command.gate(program_id, required=True)
    refreshed = command.refresh_command_center(program_id)
    inventory = read_json(command.inventory_path(program_id))
    acceptance = next(row for row in inventory["items"] if row["component_type"] == "continuity_acceptance_board")

    assert gate["status"] == "failed"
    assert refreshed["status"] == "blocked"
    assert refreshed["current_generation_status"] == "reset_pending"
    assert acceptance["evidence_status"] == "reset_pending"
    assert acceptance["current"] is False
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterStateError):
        command.export_package(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterStateError):
        command.build_zip(program_id)


def test_continuity_command_center_verifier_rejects_wrong_external_package_type(tmp_path: Path) -> None:
    _program_store, change, command, program_id = _prepared_command_center(tmp_path)
    zipped = command.build_zip(program_id)

    verification = read_json(change.verification_report_path(program_id))
    verification["package_type"] = "musicforge_wrong_verification"
    verification["integrity_hash"] = stable_hash({key: value for key, value in verification.items() if key != "integrity_hash"})
    write_json(change.verification_report_path(program_id), verification)
    report = verify_unified_release_program_continuity_command_center_package(
        zipped["zip_path"],
        strict=True,
        deep=True,
        require_ready=True,
        evidence_manifest_path=command.local_evidence_manifest_path(program_id),
    )

    assert report["status"] == "failed"
    assert any(blocker.endswith("verification_package_type") for blocker in report["blockers"])


def test_continuity_command_center_run_safe_skips_unsupported_actions(tmp_path: Path) -> None:
    _program_store, _change, command, program_id = _prepared_command_center(tmp_path)
    command.refresh_command_center(program_id)
    runbook = read_json(command.runbook_path(program_id))
    runbook["actions"].append({"action_id": "unsupported", "action_type": "continuity_acceptance_change_control.reset", "mode": "safe"})
    runbook["integrity_hash"] = stable_hash({key: value for key, value in runbook.items() if key != "integrity_hash"})
    write_json(command.runbook_path(program_id), runbook)

    result = command.run_safe(program_id)

    assert result["summary"]["unsupported_count"] == 1
    assert any(row["status"] == "skipped_unsupported" for row in result["results"])


def test_continuity_command_center_cli_standalone_verify(tmp_path: Path) -> None:
    _program_store, _change, command, program_id = _prepared_command_center(tmp_path)
    zipped = command.build_zip(program_id)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-unified-release-program-continuity-command-center-package",
            str(zipped["zip_path"]),
            "--strict",
            "--deep",
            "--require-ready",
            "--evidence-manifest",
            str(command.local_evidence_manifest_path(program_id)),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "passed"


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/extra.txt"
    entries[rel] = b"unexpected command center file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries
