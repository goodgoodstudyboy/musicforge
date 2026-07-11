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
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_command_center_acceptance import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore,
)
from song_agent.unified_release_program_continuity_command_center_acceptance_verifier import (
    RESPONSE_BINDING_PACKAGE_TYPE,
    RESPONSE_PACKAGE_TYPE,
    RESPONSE_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_command_center_acceptance_package,
)
from tests.test_ga_readiness import _write_repo
from tests.test_server_edits import request_json, start_test_server, stop_test_server
from tests.test_unified_release_program_continuity_distribution import _replace_zip_name_bytes, _write_with_extra_entry
from tests.test_unified_release_program_continuity_command_center_signoff import _prepared_signoff_store


def _prepared_acceptance(tmp_path: Path):
    program_store, _change, command, signoff, program_id = _prepared_signoff_store(tmp_path)
    signoff.signoff(program_id, {"signed_by": "program owner", "role": "release_owner"})
    signoff.build_archive_zip(program_id)
    signoff.verify_archive_zip(program_id)
    signoff.build_final_handoff_zip(program_id)
    signoff.verify_final_handoff_zip(program_id)
    store = UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore(program_store)
    review = store.create_review_pack(program_id)
    verified = store.verify_review_pack(program_id)
    assert verified["status"] == "passed", verified.get("blockers")
    return program_store, command, signoff, store, program_id, review


def _response_proof(
    store: UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore,
    program_id: str,
    *,
    response_id: str,
    reviewer: str,
    organization: str,
    role: str,
    decision: str = "accepted",
    findings: list[dict] | None = None,
) -> dict:
    source = store._current_review_source(program_id, {})
    response = {
        "schema_version": 1,
        "package_type": RESPONSE_PACKAGE_TYPE,
        "program_id": program_id,
        "response_id": response_id,
        "review_pack_id": source["review_pack_id"],
        "review_pack_source_hash": source["review_pack_source_hash"],
        "review_pack_zip_sha256": source["review_pack_zip_sha256"],
        "review_pack_manifest_hash": source["review_pack_manifest_hash"],
        "review_pack_verification_report_hash": source["review_pack_verification_report_hash"],
        "command_center_signoff_archive_zip_sha256": source["command_center_signoff_archive_zip_sha256"],
        "command_center_signoff_archive_manifest_hash": source["command_center_signoff_archive_manifest_hash"],
        "command_center_signoff_archive_verification_report_hash": source["command_center_signoff_archive_verification_report_hash"],
        "command_center_final_handoff_zip_sha256": source["command_center_final_handoff_zip_sha256"],
        "command_center_final_handoff_manifest_hash": source["command_center_final_handoff_manifest_hash"],
        "command_center_final_handoff_verification_report_hash": source["command_center_final_handoff_verification_report_hash"],
        "command_center_signoff_binding_hash": source["command_center_signoff_binding_hash"],
        "reviewer": reviewer,
        "organization": organization,
        "role": role,
        "decision": decision,
        "findings": findings or [],
        "created_at": "2026-07-11T00:00:00Z",
    }
    response["payload_hash"] = stable_hash({key: value for key, value in response.items() if key not in {"payload_hash", "integrity_hash"}})
    response["integrity_hash"] = stable_hash({key: value for key, value in response.items() if key != "integrity_hash"})
    public = {
        "schema_version": 1,
        "package_type": f"{RESPONSE_PACKAGE_TYPE}_public_projection",
        "program_id": program_id,
        "response_id": response_id,
        "reviewer": reviewer,
        "organization": organization,
        "role": role,
        "decision": decision,
        "findings": findings or [],
        "created_at": response["created_at"],
    }
    response_sha256 = hashlib.sha256((json.dumps(response, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).hexdigest()
    proof = {
        "schema_version": 1,
        "program_id": program_id,
        "response_id": response_id,
        "status": "passed",
        "response_sha256": response_sha256,
        "response_payload_hash": response["payload_hash"],
        "response_public_projection_hash": stable_hash(public),
        "reviewer_identity_hash": stable_hash({"reviewer": reviewer, "organization": organization, "role": role}),
        "decision_hash": stable_hash({"decision": decision}),
        "findings_hash": stable_hash({"findings": findings or []}),
        "reviewer": reviewer,
        "organization": organization,
        "role": role,
        "decision": decision,
        **{key: response[key] for key in (
            "review_pack_id",
            "review_pack_source_hash",
            "review_pack_zip_sha256",
            "review_pack_manifest_hash",
            "review_pack_verification_report_hash",
            "command_center_signoff_archive_zip_sha256",
            "command_center_signoff_archive_manifest_hash",
            "command_center_signoff_archive_verification_report_hash",
            "command_center_final_handoff_zip_sha256",
            "command_center_final_handoff_manifest_hash",
            "command_center_final_handoff_verification_report_hash",
            "command_center_signoff_binding_hash",
        )},
    }
    verification = {**proof, "package_type": RESPONSE_VERIFICATION_PACKAGE_TYPE}
    verification["integrity_hash"] = stable_hash({key: value for key, value in verification.items() if key != "integrity_hash"})
    binding = {**proof, "package_type": RESPONSE_BINDING_PACKAGE_TYPE, "response_verification_report_hash": verification["integrity_hash"]}
    binding.pop("status", None)
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    return {"response": response, "response_verification_report": verification, "response_binding_summary": binding}


def _accepted_pair(store, program_id: str) -> None:
    for response_id, reviewer, organization, role in (
        ("receiver-001", "Continuity Receiver", "Continuity Org", "continuity_owner"),
        ("receiver-002", "Operations Receiver", "Operations Org", "operations_owner"),
    ):
        store.import_response(program_id, _response_proof(store, program_id, response_id=response_id, reviewer=reviewer, organization=organization, role=role))
        store.create_accepted_evidence(program_id, response_id)


def _runtime_paths(store: UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore, program_id: str) -> dict[str, str]:
    signoff = store.signoff_store
    command = signoff.command_store
    return {
        "unified_release_program_continuity_command_center_acceptance_archive": str(store.archive_zip_path(program_id)),
        "unified_release_program_continuity_command_center_acceptance_verification_report": str(store.archive_verification_report_path(program_id)),
        "unified_release_program_continuity_command_center_acceptance_signoff_binding": str(store.signoff_binding_path(program_id)),
        "unified_release_program_continuity_command_center_acceptance_review_pack": str(store.review_pack_zip_path(program_id)),
        "unified_release_program_continuity_command_center_acceptance_review_pack_verification_report": str(store.review_pack_verification_report_path(program_id)),
        "unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir": str(store.accepted_evidence_root(program_id)),
        "unified_release_program_continuity_command_center_acceptance_response_proof_dir": str(store.responses_dir(program_id)),
        "unified_release_program_continuity_command_center_signoff_archive": str(signoff.archive_zip_path(program_id)),
        "unified_release_program_continuity_command_center_signoff_verification_report": str(signoff.archive_verification_report_path(program_id)),
        "unified_release_program_continuity_command_center_final_handoff": str(signoff.final_handoff_zip_path(program_id)),
        "unified_release_program_continuity_command_center_final_handoff_verification_report": str(signoff.final_handoff_verification_report_path(program_id)),
        "unified_release_program_continuity_command_center_signoff_binding": str(signoff.signoff_binding_path(program_id)),
        "unified_release_program_continuity_command_center": str(command.zip_path(program_id)),
        "unified_release_program_continuity_command_center_verification_report": str(command.verification_report_path(program_id)),
        "unified_release_program_continuity_command_center_external_evidence_manifest": str(command.local_evidence_manifest_path(program_id)),
    }


def _ga_build_kwargs(paths: dict[str, str]) -> dict[str, str | bool]:
    mapped = {key if key.endswith("_dir") else f"{key}_path": value for key, value in paths.items()}
    mapped["unified_release_program_continuity_command_center_zip_path"] = mapped.pop(
        "unified_release_program_continuity_command_center_path"
    )
    return {"require_unified_release_program_continuity_command_center_acceptance": True, **mapped}


def _ga_verify_kwargs(paths: dict[str, str]) -> dict[str, str | bool]:
    mapped = _ga_build_kwargs(paths)
    mapped["unified_release_program_continuity_command_center_acceptance_path"] = mapped.pop(
        "unified_release_program_continuity_command_center_acceptance_archive_path"
    )
    mapped["unified_release_program_continuity_command_center_path"] = mapped.pop(
        "unified_release_program_continuity_command_center_zip_path"
    )
    return mapped


def test_receiver_acceptance_happy_path_cli_api_release_and_ga_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _program, _command, _signoff, store, program_id, _review = _prepared_acceptance(tmp_path)

    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root)
    cli = subprocess.run(
        [sys.executable, "-m", "song_agent.cli", "unified-release-program-continuity-command-center-acceptance", "status", program_id, "--json"],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert cli.returncode == 0, cli.stderr
    assert json.loads(cli.stdout)["status"] == "not_configured"

    server = start_test_server()
    try:
        status_code, status = request_json(server, "GET", f"/api/unified-release-programs/{program_id}/continuity-command-center-acceptance")
        path_code, _path_error = request_json(server, "POST", f"/api/unified-release-programs/{program_id}/continuity-command-center-acceptance/responses/import", {"source_path": "C:\\Users\\demo\\response.json"})
        assert status_code == 200 and status["status"] == "not_configured"
        assert path_code == 400

        _accepted_pair(store, program_id)
        board = store.refresh_board(program_id)
        signed = store.signoff(program_id, {"signed_by": "receiver chair", "role": "program_owner"})
        archived = store.build_archive_zip(program_id)
        verified = store.verify_archive_zip(program_id)
        gate = store.gate(program_id, required=True)
        paths = _runtime_paths(store, program_id)
        release_code, created = request_json(server, "POST", "/api/releases", {"name": "v12.11 acceptance gate"})
        release_gate_code, _release_signoff = request_json(
            server,
            "POST",
            f"/api/releases/{created['release']['release_id']}/signoff",
            {
                "signed_by": "release owner",
                "force": True,
                "override_reason": "Receiver Acceptance remains non-overridable.",
                "require_unified_release_program_continuity_command_center_acceptance": True,
                "unified_release_program_id": program_id,
                **paths,
            },
        )
    finally:
        stop_test_server(server)

    assert board["status"] == "ready_for_signoff", board.get("conflicts")
    assert signed["status"] == "signed"
    assert Path(archived["zip_path"]).is_file()
    assert verified["status"] == "passed", verified.get("blockers")
    assert gate["status"] == "passed", gate
    assert release_code == 201
    assert release_gate_code == 200

    ga_root = tmp_path / "ga-repo"
    _write_repo(ga_root)
    ga_report = build_ga_readiness_report(repo_root=ga_root, allow_dirty=True, **_ga_build_kwargs(paths))
    ga_path = tmp_path / "ga-v1211.json"
    write_ga_readiness_report(ga_report, ga_path)
    ga_verification = verify_ga_readiness_report(ga_path, **_ga_verify_kwargs(paths))
    ga_check = next(row for row in ga_report["checks"] if row["check_id"] == "ga.unified_release_program_continuity_command_center_acceptance")
    assert ga_check["status"] == "passed", ga_check
    assert ga_verification["status"] != "failed", ga_verification.get("checks")


def test_receiver_response_requires_external_proof_and_rejects_role_mismatch(tmp_path: Path) -> None:
    _program, _command, _signoff, store, program_id, _review = _prepared_acceptance(tmp_path)
    complete = _response_proof(store, program_id, response_id="receiver-001", reviewer="Reviewer", organization="Org", role="technical_reviewer")

    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.import_response(program_id, complete["response"])

    forged = json.loads(json.dumps(complete))
    forged["response"]["role"] = "continuity_owner"
    forged["response"]["payload_hash"] = stable_hash({key: value for key, value in forged["response"].items() if key not in {"payload_hash", "integrity_hash"}})
    forged["response"]["integrity_hash"] = stable_hash({key: value for key, value in forged["response"].items() if key != "integrity_hash"})
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.import_response(program_id, forged)


@pytest.mark.parametrize("decision", ["rejected", "needs_changes"])
def test_negative_response_blocks_board_and_signoff(tmp_path: Path, decision: str) -> None:
    _program, _command, _signoff, store, program_id, _review = _prepared_acceptance(tmp_path)
    _accepted_pair(store, program_id)
    store.import_response(
        program_id,
        _response_proof(store, program_id, response_id=f"receiver-{decision}", reviewer="Negative Reviewer", organization="Third Org", role="observer", decision=decision),
    )

    board = store.refresh_board(program_id)

    assert board["status"] == "blocked"
    assert any(row.get("reason") == f"{decision}_response_present" for row in board.get("conflicts") or [])
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.signoff(program_id, {"signed_by": "chair"})


def test_stale_handoff_blocks_board_and_signoff(tmp_path: Path) -> None:
    _program, _command, signoff, store, program_id, _review = _prepared_acceptance(tmp_path)
    _accepted_pair(store, program_id)
    handoff = signoff.final_handoff_zip_path(program_id)
    handoff.write_bytes(handoff.read_bytes() + b"tamper")

    board = store.refresh_board(program_id)

    assert board["status"] == "blocked"
    assert any(row.get("reason") == "review_pack_runtime_failed" for row in board.get("conflicts") or [])
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.signoff(program_id, {"signed_by": "chair"})


def test_deleted_history_and_signed_source_tamper_are_blocked(tmp_path: Path) -> None:
    _program, _command, _signoff, store, program_id, _review = _prepared_acceptance(tmp_path)
    _accepted_pair(store, program_id)
    store.refresh_board(program_id)
    store.signoff(program_id, {"signed_by": "receiver chair"})
    store.build_archive_zip(program_id)
    store.verify_archive_zip(program_id)

    history = store.history_path(program_id).read_text(encoding="utf-8")
    store.history_path(program_id).unlink()
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.signoff(program_id, {"signed_by": "forged"})
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.build_archive_zip(program_id)
    assert store.gate(program_id, required=True)["status"] == "failed"
    store.history_path(program_id).write_text(history, encoding="utf-8")

    response_path = store.response_path(program_id, "receiver-001")
    tampered = read_json(response_path)
    tampered["findings"] = [{"severity": "critical", "summary": "polluted"}]
    tampered["payload_hash"] = stable_hash({key: value for key, value in tampered.items() if key not in {"payload_hash", "integrity_hash"}})
    tampered["integrity_hash"] = stable_hash({key: value for key, value in tampered.items() if key != "integrity_hash"})
    write_json(response_path, tampered)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.export_archive(program_id)
    with pytest.raises(UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError):
        store.build_archive_zip(program_id)


def test_archive_verifier_requires_external_binding_and_rejects_trailing_data(tmp_path: Path) -> None:
    _program, _command, _signoff, store, program_id, _review = _prepared_acceptance(tmp_path)
    _accepted_pair(store, program_id)
    store.refresh_board(program_id)
    store.signoff(program_id, {"signed_by": "receiver chair"})
    archived = store.build_archive_zip(program_id)

    missing = verify_unified_release_program_continuity_command_center_acceptance_package(
        archived["zip_path"], strict=True, require_signed=True
    )
    trailing_path = tmp_path / "receiver-acceptance-trailing.zip"
    trailing_path.write_bytes(Path(archived["zip_path"]).read_bytes() + b"tamper")
    trailing = verify_unified_release_program_continuity_command_center_acceptance_package(trailing_path, strict=True)
    forged_path = tmp_path / "receiver-acceptance-full-resign.zip"
    _v76_rewrite_zip(Path(archived["zip_path"]), forged_path, _full_resign_signed_by)
    forged = verify_unified_release_program_continuity_command_center_acceptance_package(
        forged_path,
        strict=True,
        require_signed=True,
        signoff_binding_path=store.signoff_binding_path(program_id),
    )
    extra_path = tmp_path / "receiver-acceptance-extra.zip"
    _v76_rewrite_zip(Path(archived["zip_path"]), extra_path, _add_declared_extra)
    extra = verify_unified_release_program_continuity_command_center_acceptance_package(extra_path, strict=True)
    musicforge_path = tmp_path / "receiver-acceptance-musicforge.zip"
    _write_with_extra_entry(Path(archived["zip_path"]), musicforge_path, ".MusicForge/internal.json", b"{}")
    musicforge = verify_unified_release_program_continuity_command_center_acceptance_package(musicforge_path, strict=True)
    backslash_path = tmp_path / "receiver-acceptance-backslash.zip"
    _replace_zip_name_bytes(Path(archived["zip_path"]), backslash_path, b"README.txt", b"README\\txt")
    backslash = verify_unified_release_program_continuity_command_center_acceptance_package(backslash_path, strict=True)

    assert missing["status"] == "failed"
    assert "urpccca_external_signoff_binding_required" in missing["blockers"]
    assert trailing["status"] == "failed"
    assert "urpccca_no_trailing_data" in trailing["blockers"]
    assert forged["status"] == "failed"
    assert "urpccca_external_signoff_binding_hash" in forged["blockers"]
    assert extra["status"] == "failed"
    assert musicforge["status"] == "failed"
    assert backslash["status"] == "failed"


def _full_resign_signed_by(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["receiver-acceptance-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged receiver"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["receiver-acceptance-signoff.json"] = _json_bytes(signoff)

    history = [json.loads(line) for line in entries["receiver-acceptance-history.jsonl"].decode("utf-8").splitlines() if line.strip()]
    previous = ""
    signoff_event_hash = ""
    for event in history:
        if event.get("event_type") == "receiver_acceptance_signoff_created":
            event["signed_by"] = "forged receiver"
            event["signoff_hash"] = signoff["integrity_hash"]
            event["signoff_payload_hash"] = signoff["payload_hash"]
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        if event.get("event_type") == "receiver_acceptance_signoff_created":
            signoff_event_hash = event["event_hash"]
    entries["receiver-acceptance-history.jsonl"] = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in history).encode("utf-8")

    binding = json.loads(entries["receiver-acceptance-signoff-binding-summary.json"].decode("utf-8"))
    binding.update({"signed_by": "forged receiver", "signoff_hash": signoff["integrity_hash"], "signoff_payload_hash": signoff["payload_hash"], "history_event_hash": signoff_event_hash})
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["receiver-acceptance-signoff-binding-summary.json"] = _json_bytes(binding)

    state = json.loads(entries["receiver-acceptance-state.json"].decode("utf-8"))
    state.update({"signoff_hash": signoff["integrity_hash"], "signoff_binding_hash": binding["integrity_hash"], "signoff_event_hash": signoff_event_hash})
    state["integrity_hash"] = stable_hash({key: value for key, value in state.items() if key != "integrity_hash"})
    entries["receiver-acceptance-state.json"] = _json_bytes(state)

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["source"].update({"signoff_hash": signoff["integrity_hash"], "signoff_binding_hash": binding["integrity_hash"], "state_hash": state["integrity_hash"]})
    for row in manifest["files"]:
        data = entries[row["path"]]
        row.update({"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[rel] = b"unexpected Receiver Acceptance file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": hashlib.sha256(entries[rel]).hexdigest()})
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = _json_bytes(manifest)
    return entries


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
