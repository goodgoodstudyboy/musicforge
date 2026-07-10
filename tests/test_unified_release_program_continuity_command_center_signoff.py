from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_command_center_signoff import (
    RESET_ACTION,
    UnifiedReleaseProgramContinuityCommandCenterSignoffStateError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffStore,
)
from song_agent.unified_release_program_continuity_command_center_signoff_verifier import (
    verify_unified_release_program_continuity_command_center_signoff_package,
)
from tests.test_unified_release_program_continuity_command_center import _prepared_command_center
from tests.test_ga_readiness import _write_repo
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_unified_release_program_vault import _sha256_bytes


def _prepared_signoff_store(tmp_path: Path):
    program_store, change, command, program_id = _prepared_command_center(tmp_path)
    command.build_zip(program_id)
    verified = command.verify_zip(program_id)
    assert verified["status"] == "passed", verified.get("blockers")
    signoff = UnifiedReleaseProgramContinuityCommandCenterSignoffStore(program_store)
    return program_store, change, command, signoff, program_id


def test_command_center_signoff_archive_handoff_happy_path(tmp_path: Path) -> None:
    _program, _change, command, store, program_id = _prepared_signoff_store(tmp_path)

    preflight = store.preflight(program_id)
    signed = store.signoff(program_id, {"signed_by": "program owner", "role": "release_owner"})
    archive = store.build_archive_zip(program_id)
    archive_verification = store.verify_archive_zip(program_id)
    handoff = store.build_final_handoff_zip(program_id)
    handoff_verification = store.verify_final_handoff_zip(program_id)
    gate = store.gate(program_id, required=True)

    assert preflight["status"] == "passed", preflight
    assert signed["status"] == "signed"
    assert Path(archive["zip_path"]).is_file()
    assert archive_verification["status"] == "passed", archive_verification.get("blockers")
    assert Path(handoff["zip_path"]).is_file()
    assert handoff_verification["status"] == "passed", handoff_verification.get("blockers")
    assert gate["status"] == "passed", gate
    assert read_json(store.signoff_binding_path(program_id))["command_center_zip_sha256"] == read_json(command.verification_report_path(program_id))["zip_sha256"]


def test_signoff_archive_requires_independent_binding_and_rejects_full_resign(tmp_path: Path) -> None:
    _program, _change, _command, store, program_id = _prepared_signoff_store(tmp_path)
    store.signoff(program_id, {"signed_by": "original signer", "role": "release_owner"})
    archived = store.build_archive_zip(program_id)

    missing = verify_unified_release_program_continuity_command_center_signoff_package(
        archived["zip_path"],
        strict=True,
        require_signed=True,
        command_center_zip_path=store.command_store.zip_path(program_id),
        command_center_verification_report_path=store.command_store.verification_report_path(program_id),
        command_center_external_evidence_manifest_path=store.command_store.local_evidence_manifest_path(program_id),
    )
    forged_zip = tmp_path / "full-resign.zip"
    _v76_rewrite_zip(Path(archived["zip_path"]), forged_zip, _full_resign_signed_by)
    forged = verify_unified_release_program_continuity_command_center_signoff_package(
        forged_zip,
        strict=True,
        require_signed=True,
        signoff_binding_path=store.signoff_binding_path(program_id),
        command_center_zip_path=store.command_store.zip_path(program_id),
        command_center_verification_report_path=store.command_store.verification_report_path(program_id),
        command_center_external_evidence_manifest_path=store.command_store.local_evidence_manifest_path(program_id),
    )

    assert missing["status"] == "failed"
    assert "urpcccs_external_signoff_binding_required" in missing["blockers"]
    assert forged["status"] == "failed"
    assert "urpcccs_external_signoff_binding_match" in forged["blockers"]


def test_signed_source_tamper_and_deleted_artifacts_are_blocked_before_build(tmp_path: Path) -> None:
    _program, change, _command, store, program_id = _prepared_signoff_store(tmp_path)
    store.signoff(program_id, {"signed_by": "owner"})
    store.build_archive_zip(program_id)

    store.signoff_path(program_id).unlink()
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.signoff(program_id, {"signed_by": "forged"})
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.build_archive_zip(program_id)

    # Restore the signed file only to exercise bottom-evidence drift independently.
    history_copy = store.archive_dir(program_id) / "command-center-signoff.json"
    write_json(store.signoff_path(program_id), read_json(history_copy))
    source_archive = change.archive_zip_path(program_id)
    source_archive.write_bytes(source_archive.read_bytes() + b"tamper")
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.build_archive_zip(program_id)
    assert store.gate(program_id, required=True)["status"] == "failed"


def test_deleted_history_cannot_reopen_signed_state(tmp_path: Path) -> None:
    _program, _change, _command, store, program_id = _prepared_signoff_store(tmp_path)
    store.signoff(program_id, {"signed_by": "first owner"})
    store.build_archive_zip(program_id)
    store.verify_archive_zip(program_id)

    store.history_path(program_id).unlink()

    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.signoff(program_id, {"signed_by": "forged successor"})
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.build_archive_zip(program_id)
    assert store.gate(program_id, required=True)["status"] == "failed"


def test_archive_and_export_tamper_cannot_be_silently_rebuilt(tmp_path: Path) -> None:
    _program, _change, _command, store, program_id = _prepared_signoff_store(tmp_path)
    store.signoff(program_id, {"signed_by": "owner"})
    store.export_archive(program_id)
    signoff_doc = store.archive_dir(program_id) / "command-center-signoff.json"
    signoff_doc.write_text(signoff_doc.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.build_archive_zip(program_id)

    # Restore the exact frozen file, then check an already-built ZIP.
    write_json(signoff_doc, read_json(store.signoff_path(program_id)))
    store.build_archive_zip(program_id)
    store.archive_zip_path(program_id).write_bytes(store.archive_zip_path(program_id).read_bytes() + b"tamper")
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.build_archive_zip(program_id)


def test_change_request_is_action_scoped_single_use_and_allows_successor(tmp_path: Path) -> None:
    _program, _change, command, store, program_id = _prepared_signoff_store(tmp_path)
    first = store.signoff(program_id, {"signed_by": "first owner"})
    store.build_archive_zip(program_id)
    store.verify_archive_zip(program_id)

    wrong = store.create_change_request(program_id, {"allowed_actions": ["refresh_command_center"]})
    store.approve_change_request(program_id, wrong["change_request_id"], {"approved_by": "chair"})
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.reset_signoff(program_id, wrong["change_request_id"])

    request = store.create_change_request(program_id, {"allowed_actions": [RESET_ACTION]})
    store.approve_change_request(program_id, request["change_request_id"], {"approved_by": "chair"})
    proof = store.reset_signoff(program_id, request["change_request_id"], {"reset_by": "owner"})
    assert proof["status"] == "applied"
    assert store.gate(program_id, required=True)["status"] == "failed"
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.reset_signoff(program_id, request["change_request_id"])
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
        store.build_archive_zip(program_id)

    # Re-verifying the still-current Command Center permits an explicitly new signoff generation.
    command.verify_zip(program_id)
    successor = store.signoff(program_id, {"signed_by": "successor owner"})
    assert successor["status"] == "signed"
    assert successor["integrity_hash"] != first["integrity_hash"]
    assert store.build_archive_zip(program_id)["status"] == "passed"
    assert store.verify_archive_zip(program_id)["status"] == "passed"


def test_reset_rejects_semantically_resigned_approval(tmp_path: Path) -> None:
    _program, _change, _command, store, program_id = _prepared_signoff_store(tmp_path)
    store.signoff(program_id, {"signed_by": "first owner"})
    request = store.create_change_request(program_id, {"allowed_actions": [RESET_ACTION]})
    store.approve_change_request(program_id, request["change_request_id"], {"approved_by": "chair"})
    approval_path = store.change_approval_path(program_id, request["change_request_id"])
    original = read_json(approval_path)

    variants = []
    wrong_target = json.loads(json.dumps(original))
    wrong_target["target"]["signoff_hash"] = "f" * 64
    variants.append(wrong_target)
    wrong_program = json.loads(json.dumps(original))
    wrong_program["program_id"] = "urp-forged"
    variants.append(wrong_program)
    wrong_request = json.loads(json.dumps(original))
    wrong_request["change_request_id"] = "uccscr-forged"
    variants.append(wrong_request)
    wrong_source = json.loads(json.dumps(original))
    wrong_source["source"] = {"source_hash": "e" * 64}
    variants.append(wrong_source)

    for approval in variants:
        approval["payload_hash"] = stable_hash(
            {key: value for key, value in approval.items() if key not in {"payload_hash", "integrity_hash"}}
        )
        approval["integrity_hash"] = stable_hash(
            {key: value for key, value in approval.items() if key != "integrity_hash"}
        )
        write_json(approval_path, approval)
        with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterSignoffStateError):
            store.reset_signoff(program_id, request["change_request_id"])

    write_json(approval_path, original)
    assert store.reset_signoff(program_id, request["change_request_id"])["status"] == "applied"


def test_signoff_cli_api_release_and_ga_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _program, _change, command, store, program_id = _prepared_signoff_store(tmp_path)
    server = start_test_server()
    try:
        status_code, state = request_json(server, "GET", f"/api/unified-release-programs/{program_id}/continuity-command-center-signoff")
        sign_code, signed = request_json(server, "POST", f"/api/unified-release-programs/{program_id}/continuity-command-center-signoff/sign", {"signed_by": "API owner", "role": "release_owner"})
        zip_code, _zipped = request_json(server, "POST", f"/api/unified-release-programs/{program_id}/continuity-command-center-signoff/zip", {})
        verify_code, verified = request_json(server, "POST", f"/api/unified-release-programs/{program_id}/continuity-command-center-signoff/verify", {})
        release_code, created = request_json(server, "POST", "/api/releases", {"name": "v12.10 gate release"})
        blocked_code, _blocked = request_json(
            server,
            "POST",
            f"/api/releases/{created['release']['release_id']}/signoff",
            {
                "signed_by": "release owner",
                "force": True,
                "override_reason": "The signoff gate remains non-overridable.",
                "require_unified_release_program_continuity_command_center_signoff": True,
                "unified_release_program_id": program_id,
                "unified_release_program_continuity_command_center_signoff_archive": str(tmp_path / "missing-archive.zip"),
                "unified_release_program_continuity_command_center_signoff_verification_report": str(store.archive_verification_report_path(program_id)),
                "unified_release_program_continuity_command_center_signoff_binding": str(store.signoff_binding_path(program_id)),
                "unified_release_program_continuity_command_center": str(command.zip_path(program_id)),
                "unified_release_program_continuity_command_center_verification_report": str(command.verification_report_path(program_id)),
                "unified_release_program_continuity_command_center_external_evidence_manifest": str(command.local_evidence_manifest_path(program_id)),
            },
        )
    finally:
        stop_test_server(server)
    assert status_code == 200 and state["status"] == "unsigned"
    assert sign_code == 200 and signed["status"] == "signed"
    assert zip_code == 200
    assert verify_code == 200 and verified["status"] == "passed"
    assert release_code == 201
    assert blocked_code == 409

    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)
    managed = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "unified-release-program-continuity-command-center-signoff", "status", program_id, "--json"],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert managed.returncode == 0, managed.stderr
    assert json.loads(managed.stdout)["status"] == "signed"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "verify-unified-release-program-continuity-command-center-signoff-package",
            str(store.archive_zip_path(program_id)),
            "--strict",
            "--require-signed",
            "--signoff-binding",
            str(store.signoff_binding_path(program_id)),
            "--command-center",
            str(command.zip_path(program_id)),
            "--command-center-verification-report",
            str(command.verification_report_path(program_id)),
            "--command-center-evidence-manifest",
            str(command.local_evidence_manifest_path(program_id)),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=repo_root,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "passed"

    ga_root = tmp_path / "ga-repo"
    _write_repo(ga_root)
    ga_report = build_ga_readiness_report(
        repo_root=ga_root,
        allow_dirty=True,
        require_unified_release_program_continuity_command_center_signoff=True,
        unified_release_program_continuity_command_center_signoff_archive_path=store.archive_zip_path(program_id),
        unified_release_program_continuity_command_center_signoff_verification_report_path=store.archive_verification_report_path(program_id),
        unified_release_program_continuity_command_center_signoff_binding_path=store.signoff_binding_path(program_id),
        unified_release_program_continuity_command_center_zip_path=command.zip_path(program_id),
        unified_release_program_continuity_command_center_verification_report_path=command.verification_report_path(program_id),
        unified_release_program_continuity_command_center_external_evidence_manifest_path=command.local_evidence_manifest_path(program_id),
    )
    ga_path = write_ga_readiness_report(ga_report, tmp_path / "ga-v1210.json")
    ga_verification = verify_ga_readiness_report(
        ga_path,
        require_unified_release_program_continuity_command_center_signoff=True,
        unified_release_program_continuity_command_center_signoff_archive_path=store.archive_zip_path(program_id),
        unified_release_program_continuity_command_center_signoff_verification_report_path=store.archive_verification_report_path(program_id),
        unified_release_program_continuity_command_center_signoff_binding_path=store.signoff_binding_path(program_id),
        unified_release_program_continuity_command_center_path=command.zip_path(program_id),
        unified_release_program_continuity_command_center_verification_report_path=command.verification_report_path(program_id),
        unified_release_program_continuity_command_center_external_evidence_manifest_path=command.local_evidence_manifest_path(program_id),
    )
    assert next(row for row in ga_report["checks"] if row["check_id"] == "ga.unified_release_program_continuity_command_center_signoff")["status"] == "passed"
    assert ga_verification["status"] != "failed", ga_verification.get("blockers")


def _full_resign_signed_by(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["command-center-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged signer"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["command-center-signoff.json"] = _json_bytes(signoff)

    history = [json.loads(line) for line in entries["command-center-signoff-history.jsonl"].decode("utf-8").splitlines() if line.strip()]
    previous = ""
    signoff_event_hash = ""
    for event in history:
        if event.get("event_type") == "command_center_signoff_created":
            event["signed_by"] = "forged signer"
            event["signoff_hash"] = signoff["integrity_hash"]
            event["signoff_payload_hash"] = signoff["payload_hash"]
        if event.get("signoff_hash") and event.get("event_type") != "command_center_signoff_created":
            event["signoff_hash"] = signoff["integrity_hash"]
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        if event.get("event_type") == "command_center_signoff_created":
            signoff_event_hash = event["event_hash"]
    entries["command-center-signoff-history.jsonl"] = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in history).encode("utf-8")

    binding = json.loads(entries["command-center-signoff-binding-summary.json"].decode("utf-8"))
    binding["signed_by"] = "forged signer"
    binding["signoff_hash"] = signoff["integrity_hash"]
    binding["signoff_payload_hash"] = signoff["payload_hash"]
    binding["history_event_hash"] = signoff_event_hash
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["command-center-signoff-binding-summary.json"] = _json_bytes(binding)

    state = json.loads(entries["command-center-signoff-state.json"].decode("utf-8"))
    state["signoff_hash"] = signoff["integrity_hash"]
    state["signoff_binding_hash"] = binding["integrity_hash"]
    state["signoff_event_hash"] = signoff_event_hash
    state["integrity_hash"] = stable_hash({key: value for key, value in state.items() if key != "integrity_hash"})
    entries["command-center-signoff-state.json"] = _json_bytes(state)

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["source"]["signoff_hash"] = signoff["integrity_hash"]
    manifest["source"]["signoff_binding_hash"] = binding["integrity_hash"]
    for row in manifest["files"]:
        data = entries[row["path"]]
        row["sha256"] = _sha256_bytes(data)
        row["size_bytes"] = len(data)
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[rel] = b"unexpected signoff archive file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
