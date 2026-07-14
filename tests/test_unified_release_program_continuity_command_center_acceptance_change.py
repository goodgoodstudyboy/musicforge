from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
from song_agent.ga_readiness_verifier import verify_ga_readiness_report
from song_agent.projectio import read_json, write_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_command_center_acceptance_change import (
    RESET_ACTION,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore,
)
from song_agent.unified_release_program_continuity_command_center_acceptance_change_verifier import (
    verify_unified_release_program_continuity_command_center_acceptance_change_package,
)
from song_agent.unified_release_program_continuity_command_center_acceptance import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError,
)
from tests.test_unified_release_program_continuity_command_center_acceptance import (
    _accepted_pair,
    _ga_build_kwargs,
    _ga_verify_kwargs,
    _prepared_acceptance,
    _runtime_paths,
)
from tests.test_ga_readiness import _write_repo
from tests.test_server_edits import request_json, start_test_server, stop_test_server


def _prepared_change(tmp_path: Path):
    program_store, _command, _signoff, acceptance, program_id, _review = _prepared_acceptance(tmp_path)
    _accepted_pair(acceptance, program_id)
    acceptance.refresh_board(program_id)
    acceptance.signoff(program_id, {"signed_by": "receiver chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    verified = acceptance.verify_archive_zip(program_id)
    assert verified["status"] == "passed", verified.get("blockers")
    change = UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore(program_store)
    return program_store, acceptance, change, program_id


def _prepare_successor_evidence(acceptance, program_id: str) -> None:
    acceptance.create_review_pack(program_id)
    verified = acceptance.verify_review_pack(program_id)
    assert verified["status"] == "passed", verified.get("blockers")
    _accepted_pair(acceptance, program_id)


def test_receiver_acceptance_change_control_lifecycle_and_security_guards(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _program, acceptance, change, program_id = _prepared_change(tmp_path)

    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError):
        change.create_change_request(
            program_id,
            {
                "change_request_id": "cr-wrong-action",
                "change_type": "reset_receiver_acceptance_signoff",
                "allowed_actions": ["refresh_receiver_acceptance_report"],
            },
        )

    request = change.create_change_request(program_id)
    approval = change.approve_change_request(program_id, request["change_request_id"], {"approved_by": "program owner"})
    approval_path = change.approval_path(program_id, request["change_request_id"])
    forged_approval = json.loads(json.dumps(approval))
    forged_approval["target"]["acceptance_signoff_hash"] = "f" * 64
    forged_approval["payload_hash"] = stable_hash(
        {key: value for key, value in forged_approval.items() if key not in {"payload_hash", "integrity_hash"}}
    )
    forged_approval["integrity_hash"] = _integrity_hash(forged_approval)
    write_json(approval_path, forged_approval)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError):
        change.reset_receiver_acceptance_signoff(program_id, request["change_request_id"])
    write_json(approval_path, approval)

    proof = change.reset_receiver_acceptance_signoff(program_id, request["change_request_id"])
    assert proof["status"] == "applied"
    assert acceptance.latest_signoff_state(program_id)["status"] == "reset_pending"
    assert change.gate(program_id, required=True)["status"] == "failed"
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError):
        change.reset_receiver_acceptance_signoff(program_id, request["change_request_id"])

    server = start_test_server()
    try:
        status_code, change_status = request_json(
            server,
            "GET",
            f"/api/unified-release-programs/{program_id}/continuity-command-center-acceptance/change-control",
        )
        create_code, release = request_json(server, "POST", "/api/releases", {"name": "v12.12 reset pending"})
        blocked_release_code, _blocked_release = request_json(
            server,
            "POST",
            f"/api/releases/{release['release']['release_id']}/signoff",
            {
                "signed_by": "release owner",
                "force": True,
                "override_reason": "Reset pending remains non-overridable.",
                "require_unified_release_program_continuity_command_center_acceptance_change_control": True,
                "unified_release_program_id": program_id,
            },
        )
    finally:
        stop_test_server(server)
    assert status_code == 200
    assert change_status["status"] == "needs_successor_signoff"
    assert create_code == 201
    assert blocked_release_code == 409

    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        acceptance.refresh_board(
            program_id,
            {"policy": {"min_accepted_count": 1, "min_organization_count": 1, "required_roles": []}},
        )
    stale_board = acceptance.refresh_board(program_id)
    assert stale_board["status"] == "blocked"
    _prepare_successor_evidence(acceptance, program_id)
    acceptance.refresh_board(program_id)
    successor = acceptance.signoff(program_id, {"signed_by": "successor chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    acceptance.verify_archive_zip(program_id)
    lifecycle = change.refresh_lifecycle_audit(program_id)
    archived = change.build_archive_zip(program_id)
    verified = change.verify_archive_zip(program_id)
    gate = change.gate(program_id, required=True)

    assert successor["status"] == "signed"
    assert lifecycle["status"] == "passed"
    assert lifecycle["summary"]["reset_count"] == 1
    assert Path(archived["zip_path"]).is_file()
    assert verified["status"] == "passed", verified.get("blockers")
    assert gate["status"] == "passed", gate
    assert change.build_archive_zip(program_id)["status"] == "passed"

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "song_agent.cli",
            "unified-release-program-continuity-command-center-acceptance-change",
            "status",
            program_id,
            "--json",
        ],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)["status"] == "passed"

    paths = _runtime_paths(acceptance, program_id)
    release_paths = {
        **paths,
        "unified_release_program_continuity_command_center_acceptance_change_archive": str(change.archive_zip_path(program_id)),
        "unified_release_program_continuity_command_center_acceptance_change_verification_report": str(change.verification_report_path(program_id)),
        "unified_release_program_continuity_command_center_acceptance_previous_root": str(change.generations_dir(program_id)),
    }
    server = start_test_server()
    try:
        create_code, release = request_json(server, "POST", "/api/releases", {"name": "v12.12 successor ready"})
        ready_release_code, _ready_release = request_json(
            server,
            "POST",
            f"/api/releases/{release['release']['release_id']}/signoff",
            {
                "signed_by": "release owner",
                "force": True,
                "override_reason": "Receiver Acceptance lifecycle is current.",
                "require_unified_release_program_continuity_command_center_acceptance_change_control": True,
                "unified_release_program_id": program_id,
                **release_paths,
            },
            timeout=600,
        )
    finally:
        stop_test_server(server)
    assert create_code == 201
    assert ready_release_code == 200

    ga_root = tmp_path / "ga-repo"
    _write_repo(ga_root)
    ga_build_args = _ga_build_kwargs(paths)
    ga_build_args.update(
        {
            "require_unified_release_program_continuity_command_center_acceptance_change_control": True,
            "unified_release_program_continuity_command_center_acceptance_change_archive_path": change.archive_zip_path(program_id),
            "unified_release_program_continuity_command_center_acceptance_change_verification_report_path": change.verification_report_path(program_id),
            "unified_release_program_continuity_command_center_acceptance_previous_root": change.generations_dir(program_id),
        }
    )
    ga_report = build_ga_readiness_report(repo_root=ga_root, allow_dirty=True, **ga_build_args)
    ga_path = tmp_path / "ga-v1212.json"
    write_ga_readiness_report(ga_report, ga_path)
    ga_verify_args = _ga_verify_kwargs(paths)
    ga_verify_args.update(
        {
            "require_unified_release_program_continuity_command_center_acceptance_change_control": True,
            "unified_release_program_continuity_command_center_acceptance_change_path": change.archive_zip_path(program_id),
            "unified_release_program_continuity_command_center_acceptance_change_verification_report_path": change.verification_report_path(program_id),
            "unified_release_program_continuity_command_center_acceptance_previous_root": change.generations_dir(program_id),
        }
    )
    ga_verification = verify_ga_readiness_report(ga_path, **ga_verify_args)
    ga_check = next(
        row
        for row in ga_report["checks"]
        if row["check_id"] == "ga.unified_release_program_continuity_command_center_acceptance_change_control"
    )
    assert ga_check["status"] == "passed", ga_check
    assert ga_verification["status"] != "failed", ga_verification.get("checks")

    forged_zip = tmp_path / "receiver-acceptance-change-full-resign.zip"
    _v76_rewrite_zip(
        Path(archived["zip_path"]),
        forged_zip,
        lambda entries: _full_resign_previous_archive(entries, str(proof["reset_id"])),
    )
    internally_consistent = verify_unified_release_program_continuity_command_center_acceptance_change_package(
        forged_zip,
        strict=True,
    )
    externally_bound = verify_unified_release_program_continuity_command_center_acceptance_change_package(
        forged_zip,
        strict=True,
        require_reset_proofs=True,
        previous_acceptance_root=change.generations_dir(program_id),
    )

    assert internally_consistent["status"] == "passed", internally_consistent.get("blockers")
    assert externally_bound["status"] == "failed"
    assert any(blocker.endswith("_archive_hash") for blocker in externally_bound["blockers"])

    event_order_zip = tmp_path / "receiver-acceptance-change-event-order.zip"
    _v76_rewrite_zip(
        Path(archived["zip_path"]),
        event_order_zip,
        lambda entries: _full_resign_event_order(entries, str(proof["reset_id"])),
    )
    event_order = verify_unified_release_program_continuity_command_center_acceptance_change_package(
        event_order_zip,
        strict=True,
    )
    assert event_order["status"] == "failed"
    assert any(blocker.endswith("_order") for blocker in event_order["blockers"])

    extra_zip = tmp_path / "receiver-acceptance-change-extra.zip"
    _v76_rewrite_zip(Path(archived["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_continuity_command_center_acceptance_change_package(extra_zip, strict=True)
    trailing_zip = tmp_path / "receiver-acceptance-change-trailing.zip"
    trailing_zip.write_bytes(Path(archived["zip_path"]).read_bytes() + b"tamper")
    trailing = verify_unified_release_program_continuity_command_center_acceptance_change_package(trailing_zip, strict=True)

    second_request = change.create_change_request(program_id, {"reason": "Second controlled receiver transition."})
    change.approve_change_request(program_id, second_request["change_request_id"], {"approved_by": "program owner"})
    second_proof = change.reset_receiver_acceptance_signoff(program_id, second_request["change_request_id"])
    assert acceptance.refresh_board(program_id)["status"] == "blocked"
    _prepare_successor_evidence(acceptance, program_id)
    acceptance.refresh_board(program_id)
    acceptance.signoff(program_id, {"signed_by": "third receiver chair", "role": "program_owner"})
    acceptance.build_archive_zip(program_id)
    acceptance.verify_archive_zip(program_id)
    second_lifecycle = change.refresh_lifecycle_audit(program_id)
    second_archive = change.build_archive_zip(program_id)
    second_verification = change.verify_archive_zip(program_id)
    assert second_lifecycle["status"] == "passed"
    assert second_lifecycle["summary"]["reset_count"] == 2
    assert read_json(change.current_generation_path(program_id))["generation"] == 3
    assert Path(second_archive["zip_path"]).is_file()
    assert second_verification["status"] == "passed", second_verification.get("blockers")
    assert change.gate(program_id, required=True)["status"] == "passed"

    proof = second_proof
    local_proof = read_json(change.reset_proof_path(program_id, str(proof["reset_id"])))
    local_proof["previous_signoff_hash"] = "f" * 64
    local_proof["integrity_hash"] = _integrity_hash(local_proof)
    write_json(change.reset_proof_path(program_id, str(proof["reset_id"])), local_proof)
    local_binding = read_json(change.reset_binding_path(program_id, str(proof["reset_id"])))
    local_binding["reset_proof_hash"] = local_proof["integrity_hash"]
    local_binding["integrity_hash"] = _integrity_hash(local_binding)
    write_json(change.reset_binding_path(program_id, str(proof["reset_id"])), local_binding)

    assert extra["status"] == "failed"
    assert "urpcccacc_allowed_entries" in extra["blockers"]
    assert trailing["status"] == "failed"
    assert "urpcccacc_no_trailing_data" in trailing["blockers"]
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError):
        change.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError):
        change.build_archive_zip(program_id)
    assert change.gate(program_id, required=True)["status"] == "failed"


def _full_resign_previous_archive(entries: dict[str, bytes], reset_id: str) -> dict[str, bytes]:
    request_path = next(path for path in entries if path.startswith("cr/") and path.endswith("/request.json"))
    prefix = request_path.removesuffix("request.json")
    request = _json_entry(entries, request_path)
    approval = _json_entry(entries, f"{prefix}approval.json")
    request_binding = _json_entry(entries, f"{prefix}binding.json")
    proof_path = f"rp/{reset_id}/proof.json"
    reset_binding_path = f"rp/{reset_id}/binding.json"
    proof = _json_entry(entries, proof_path)
    reset_binding = _json_entry(entries, reset_binding_path)
    forged_archive_hash = "e" * 64
    approved_request_hash = "a" * 64

    for doc in (request, approval, request_binding):
        doc["target"]["acceptance_archive_zip_sha256"] = forged_archive_hash
        doc["source"]["archive_zip_sha256"] = forged_archive_hash
        doc["source"]["integrity_hash"] = _integrity_hash(doc["source"])
    approval["request_hash"] = approved_request_hash
    approval["payload_hash"] = stable_hash(
        {key: value for key, value in approval.items() if key not in {"payload_hash", "integrity_hash"}}
    )
    approval["integrity_hash"] = _integrity_hash(approval)

    request_binding["request_hash"] = approved_request_hash
    request_binding["approval_hash"] = approval["integrity_hash"]
    request_binding["integrity_hash"] = _integrity_hash(request_binding)

    proof["request_hash"] = approved_request_hash
    proof["approval_hash"] = approval["integrity_hash"]
    proof["cr_binding_report_hash"] = request_binding["integrity_hash"]
    proof["previous_archive_zip_sha256"] = forged_archive_hash
    proof["source"]["archive_zip_sha256"] = forged_archive_hash
    proof["source"]["integrity_hash"] = _integrity_hash(proof["source"])
    proof["integrity_hash"] = _integrity_hash(proof)

    request["approved_request_hash"] = approved_request_hash
    request["approval_hash"] = approval["integrity_hash"]
    request["reset_proof_hash"] = proof["integrity_hash"]
    request["integrity_hash"] = _integrity_hash(request)

    reset_binding.update(
        {
            "request_hash": approved_request_hash,
            "approval_hash": approval["integrity_hash"],
            "cr_binding_report_hash": request_binding["integrity_hash"],
            "reset_proof_hash": proof["integrity_hash"],
            "previous_archive_zip_sha256": forged_archive_hash,
        }
    )

    events = [json.loads(line) for line in entries["events.jsonl"].decode("utf-8").splitlines() if line.strip()]
    for event in events:
        if event.get("event_type") == "receiver_acceptance_change_request_submitted":
            event["request_hash"] = approved_request_hash
        elif event.get("event_type") == "receiver_acceptance_change_request_approved":
            event["request_hash"] = approved_request_hash
            event["approval_hash"] = approval["integrity_hash"]
        elif event.get("event_type") == "receiver_acceptance_signoff_reset_applied":
            event["request_hash"] = request["integrity_hash"]
            event["approval_hash"] = approval["integrity_hash"]
            event["reset_proof_hash"] = proof["integrity_hash"]
        elif event.get("event_type") == "successor_receiver_acceptance_signed":
            event["reset_proof_hash"] = proof["integrity_hash"]
    previous_event_hash = ""
    reset_lifecycle_event_hash = None
    for event in events:
        event["previous_event_hash"] = previous_event_hash
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous_event_hash = event["event_hash"]
        if event.get("event_type") == "receiver_acceptance_signoff_reset_applied":
            reset_lifecycle_event_hash = event["event_hash"]
    reset_binding["lifecycle_event_hash"] = reset_lifecycle_event_hash
    reset_binding["integrity_hash"] = _integrity_hash(reset_binding)

    request_index = _json_entry(entries, "request-index.json")
    request_index["items"][0].update(
        {
            "request_hash": request["integrity_hash"],
            "approval_hash": approval["integrity_hash"],
            "binding_hash": request_binding["integrity_hash"],
            "reset_proof_hash": proof["integrity_hash"],
        }
    )
    request_index["integrity_hash"] = _integrity_hash(request_index)
    reset_index = _json_entry(entries, "reset-index.json")
    reset_index["items"][0].update(
        {
            "reset_proof_hash": proof["integrity_hash"],
            "binding_hash": reset_binding["integrity_hash"],
        }
    )
    reset_index["integrity_hash"] = _integrity_hash(reset_index)
    state = _json_entry(entries, "state.json")
    state["latest_reset_proof_hash"] = proof["integrity_hash"]
    state["integrity_hash"] = _integrity_hash(state)
    lifecycle = _json_entry(entries, "lifecycle.json")
    lifecycle["source"].update(
        {
            "state_hash": state["integrity_hash"],
            "change_request_index_hash": request_index["integrity_hash"],
            "reset_proof_index_hash": reset_index["integrity_hash"],
            "event_hashes": [event["event_hash"] for event in events],
        }
    )
    lifecycle["integrity_hash"] = _integrity_hash(lifecycle)
    current_generation = _json_entry(entries, "generation.json")
    current_generation["reset_proof_hash"] = proof["integrity_hash"]
    current_generation["integrity_hash"] = _integrity_hash(current_generation)

    generation_verification = _json_entry(entries, "gen/g000001/verification.json")
    generation_verification["archive_zip_sha256"] = forged_archive_hash
    generation_verification["integrity_hash"] = _integrity_hash(generation_verification)
    generation_source = _json_entry(entries, "gen/g000001/source.json")
    generation_source["source"]["archive_zip_sha256"] = forged_archive_hash
    generation_source["source"]["integrity_hash"] = _integrity_hash(generation_source["source"])
    generation_source["integrity_hash"] = _integrity_hash(generation_source)

    for path, doc in (
        (request_path, request),
        (f"{prefix}approval.json", approval),
        (f"{prefix}binding.json", request_binding),
        (proof_path, proof),
        (reset_binding_path, reset_binding),
        ("request-index.json", request_index),
        ("reset-index.json", reset_index),
        ("state.json", state),
        ("lifecycle.json", lifecycle),
        ("generation.json", current_generation),
        ("gen/g000001/verification.json", generation_verification),
        ("gen/g000001/source.json", generation_source),
    ):
        entries[path] = _json_bytes(doc)
    entries["events.jsonl"] = ("\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events) + "\n").encode("utf-8")

    manifest = _json_entry(entries, "manifest.json")
    manifest["source"].update(
        {
            "change_control_state_hash": state["integrity_hash"],
            "change_request_index_hash": request_index["integrity_hash"],
            "reset_proof_index_hash": reset_index["integrity_hash"],
            "current_generation_hash": current_generation["integrity_hash"],
            "lifecycle_report_hash": lifecycle["integrity_hash"],
            "latest_reset_proof_hash": proof["integrity_hash"],
        }
    )
    for row in manifest["files"]:
        data = entries[row["path"]]
        row["size_bytes"] = len(data)
        row["sha256"] = hashlib.sha256(data).hexdigest()
    manifest["integrity_hash"] = _integrity_hash(manifest)
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/extra.txt"
    entries[rel] = b"unexpected change-control file\n"
    manifest = _json_entry(entries, "manifest.json")
    manifest["files"].append(
        {"path": rel, "size_bytes": len(entries[rel]), "sha256": hashlib.sha256(entries[rel]).hexdigest()}
    )
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = _integrity_hash(manifest)
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _full_resign_redaction(entries: dict[str, bytes]) -> dict[str, bytes]:
    entries["README.txt"] = b"api_key=super-secret-value\n"
    manifest = _json_entry(entries, "manifest.json")
    row = next(item for item in manifest["files"] if item.get("path") == "README.txt")
    row["size_bytes"] = len(entries["README.txt"])
    row["sha256"] = hashlib.sha256(entries["README.txt"]).hexdigest()
    manifest["integrity_hash"] = _integrity_hash(manifest)
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _full_resign_event_order(entries: dict[str, bytes], reset_id: str) -> dict[str, bytes]:
    events = [json.loads(line) for line in entries["events.jsonl"].decode("utf-8").splitlines() if line.strip()]
    reset_index = next(index for index, event in enumerate(events) if event.get("event_type") == "receiver_acceptance_signoff_reset_applied")
    successor_index = next(index for index, event in enumerate(events) if event.get("event_type") == "successor_receiver_acceptance_signed")
    events[reset_index], events[successor_index] = events[successor_index], events[reset_index]
    previous = ""
    reset_event_hash = None
    for event in events:
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        if event.get("event_type") == "receiver_acceptance_signoff_reset_applied":
            reset_event_hash = event["event_hash"]
    entries["events.jsonl"] = ("\n".join(json.dumps(event, ensure_ascii=False, sort_keys=True) for event in events) + "\n").encode("utf-8")

    binding_path = f"rp/{reset_id}/binding.json"
    binding = _json_entry(entries, binding_path)
    binding["lifecycle_event_hash"] = reset_event_hash
    binding["integrity_hash"] = _integrity_hash(binding)
    entries[binding_path] = _json_bytes(binding)
    reset_index_doc = _json_entry(entries, "reset-index.json")
    next(row for row in reset_index_doc["items"] if row.get("reset_id") == reset_id)["binding_hash"] = binding["integrity_hash"]
    reset_index_doc["integrity_hash"] = _integrity_hash(reset_index_doc)
    entries["reset-index.json"] = _json_bytes(reset_index_doc)
    lifecycle = _json_entry(entries, "lifecycle.json")
    lifecycle["source"]["reset_proof_index_hash"] = reset_index_doc["integrity_hash"]
    lifecycle["source"]["event_hashes"] = [event["event_hash"] for event in events]
    lifecycle["integrity_hash"] = _integrity_hash(lifecycle)
    entries["lifecycle.json"] = _json_bytes(lifecycle)

    manifest = _json_entry(entries, "manifest.json")
    manifest["source"]["reset_proof_index_hash"] = reset_index_doc["integrity_hash"]
    manifest["source"]["lifecycle_report_hash"] = lifecycle["integrity_hash"]
    for row in manifest["files"]:
        data = entries[row["path"]]
        row["size_bytes"] = len(data)
        row["sha256"] = hashlib.sha256(data).hexdigest()
    manifest["integrity_hash"] = _integrity_hash(manifest)
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _json_entry(entries: dict[str, bytes], path: str) -> dict:
    return json.loads(entries[path].decode("utf-8"))


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _integrity_hash(value: dict) -> str:
    return stable_hash({key: item for key, item in value.items() if key != "integrity_hash"})
