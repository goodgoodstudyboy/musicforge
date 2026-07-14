from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from song_agent.platform.persistence.program import write_program_json
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_handoff import (
    UnifiedReleaseProgramHandoffStateError,
    UnifiedReleaseProgramHandoffStore,
    write_handoff_external_evidence_manifest,
)
from song_agent.unified_release_program_handoff_verifier import verify_unified_release_program_handoff_package
from tests.test_unified_release_program_operations import _ops_payload, _signed_program


def _program_ops_handoff(tmp_path: Path):
    program_store, program_id, manifest_path = _signed_program(tmp_path)
    from song_agent.unified_release_program_operations import UnifiedReleaseProgramOperationsStore

    ops_store = UnifiedReleaseProgramOperationsStore(program_store)
    payload = _ops_payload(program_store, program_id, manifest_path)
    ops_store.build_operations_archive_zip(program_id, payload)
    ops_store.verify_operations_archive_zip(program_id, payload)
    store = UnifiedReleaseProgramHandoffStore(program_store)
    evidence_manifest = tmp_path / "handoff-external-evidence.json"
    _write_handoff_manifest(store, program_store, ops_store, program_id, manifest_path, evidence_manifest)
    return store, program_store, ops_store, program_id, manifest_path, evidence_manifest


def _write_handoff_manifest(store, program_store, ops_store, program_id: str, program_manifest_path: Path, out: Path, accepted: list[dict] | None = None) -> Path:
    rows = [
        {
            "evidence_id": "program-current",
            "evidence_type": "unified_release_program",
            "component_id": program_id,
            "program_zip": str(program_store.zip_path(program_id)),
            "program_verification_report": str(program_store.verification_report_path(program_id)),
            "program_signoff_binding": str(program_store.signoff_binding_path(program_id)),
            "program_external_evidence_manifest": str(program_manifest_path),
        },
        {
            "evidence_id": "program-operations",
            "evidence_type": "unified_release_program_operations",
            "component_id": program_id,
            "operations_zip": str(ops_store.archive_zip_path(program_id)),
            "operations_verification_report": str(ops_store.archive_verification_report_path(program_id)),
            "program_zip": str(program_store.zip_path(program_id)),
            "program_verification_report": str(program_store.verification_report_path(program_id)),
            "program_signoff_binding": str(program_store.signoff_binding_path(program_id)),
            "program_external_evidence_manifest": str(program_manifest_path),
        },
    ]
    rows.extend(accepted or [])
    write_handoff_external_evidence_manifest(out, program_id=program_id, handoff_id="uph-000001", items=rows)
    return out


def _review_response(store: UnifiedReleaseProgramHandoffStore, program_id: str, review_pack_id: str, *, role: str = "release_owner", organization: str = "release-team", decision: str = "accepted") -> dict:
    pack_report = read_json(store.review_pack_dir(program_id, review_pack_id) / "review-pack-report.json")
    zip_path = store.review_pack_zip_path(program_id, review_pack_id)
    payload = {
        "schema_version": 1,
        "response_type": "musicforge_unified_release_program_review_response",
        "review_pack_id": review_pack_id,
        "review_pack_source_hash": pack_report["source_hash"],
        "review_pack_zip_sha256": _sha256_path(zip_path),
        "review_pack_manifest_hash": _manifest_hash(zip_path),
        "program_id": program_id,
        "handoff_id": pack_report["handoff_id"],
        "reviewer_id": f"rev-{role}",
        "reviewer_name": f"{role} reviewer",
        "reviewer_role": role,
        "organization": organization,
        "decision": decision,
        "findings": [],
        "notes": "Reviewed.",
    }
    payload["payload_hash"] = stable_hash({key: value for key, value in payload.items() if key not in {"payload_hash", "integrity_hash", "response_id", "status", "imported_at"}})
    return payload


def _accepted_manifest_row(store: UnifiedReleaseProgramHandoffStore, program_id: str, evidence_id: str, response_id: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "evidence_type": "program_accepted_evidence",
        "component_id": "uph-000001",
        "accepted_evidence_zip": str(store.accepted_evidence_zip_path(program_id, evidence_id)),
        "accepted_evidence_verification_report": str(store.accepted_evidence_verification_report_path(program_id, evidence_id)),
        "response_verification_report": str(store.response_verification_path(program_id, response_id)),
        "response_binding_summary": str(store.response_binding_path(program_id, response_id)),
    }


def test_unified_release_program_handoff_happy_path_and_signed_guards(tmp_path: Path) -> None:
    store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest = _program_ops_handoff(tmp_path)

    report = store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    pack = store.export_review_pack(program_id, {"audience": "release_owner"})
    zipped_pack = store.build_review_pack_zip(program_id, pack["review_pack_id"])
    response = store.import_response(program_id, _review_response(store, program_id, pack["review_pack_id"]))
    accepted = store.create_accepted_evidence(program_id, response["response"]["response_id"])
    evidence_id = accepted["evidence"]["evidence_id"]
    _write_handoff_manifest(store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest, [_accepted_manifest_row(store, program_id, evidence_id, response["response"]["response_id"])])
    refreshed = store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    board = store.refresh_decision_board(program_id, {})
    signoff = store.signoff_handoff(program_id, {"signed_by": "handoff chair", "role": "release_owner"})
    zipped = store.build_handoff_archive_zip(program_id)
    verified = store.verify_handoff_archive_zip(program_id, {"external_evidence_manifest": evidence_manifest, "handoff_signoff_binding": store.signoff_binding_path(program_id)})

    assert report["status"] == "ready_for_review"
    assert Path(zipped_pack["zip_path"]).exists()
    assert refreshed["status"] == "ready_for_signoff"
    assert board["status"] == "ready_for_signoff"
    assert signoff["status"] == "signed"
    assert zipped["status"] == "passed"
    assert verified["status"] == "passed", verified.get("blockers")
    with pytest.raises(UnifiedReleaseProgramHandoffStateError):
        store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    with pytest.raises(UnifiedReleaseProgramHandoffStateError):
        store.import_response(program_id, _review_response(store, program_id, pack["review_pack_id"]))


def test_unified_release_program_handoff_rejects_response_without_binding(tmp_path: Path) -> None:
    store, _program_store, _ops_store, program_id, _program_manifest_path, evidence_manifest = _program_ops_handoff(tmp_path)
    store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    pack = store.export_review_pack(program_id, {"audience": "release_owner"})
    store.build_review_pack_zip(program_id, pack["review_pack_id"])
    response = _review_response(store, program_id, pack["review_pack_id"])
    response.pop("review_pack_source_hash")

    with pytest.raises(UnifiedReleaseProgramHandoffStateError):
        store.import_response(program_id, response)


def test_unified_release_program_handoff_blocks_role_forge_before_signoff(tmp_path: Path) -> None:
    store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest = _program_ops_handoff(tmp_path)
    store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    pack = store.export_review_pack(program_id, {"audience": "technical_reviewer"})
    store.build_review_pack_zip(program_id, pack["review_pack_id"])
    response = store.import_response(program_id, _review_response(store, program_id, pack["review_pack_id"], role="technical_reviewer"))
    accepted = store.create_accepted_evidence(program_id, response["response"]["response_id"])
    evidence_id = accepted["evidence"]["evidence_id"]
    report_path = store.accepted_evidence_dir(program_id, evidence_id) / "accepted-evidence-report.json"
    forged = read_json(report_path)
    forged["reviewer"]["role"] = "release_owner"
    forged["public_summary"]["role"] = "release_owner"
    forged["integrity_hash"] = stable_hash({key: value for key, value in forged.items() if key != "integrity_hash"})
    write_program_json(report_path, forged)
    _write_handoff_manifest(store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest, [_accepted_manifest_row(store, program_id, evidence_id, response["response"]["response_id"])])

    store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    board = store.refresh_decision_board(program_id, {"policy": {"required_roles": ["release_owner"], "minimum_acceptances": 1, "minimum_organizations": 1}})

    assert board["status"] == "blocked"
    assert any(row["reason"] == "accepted_evidence_role_mismatch" for row in board["conflicts"])
    with pytest.raises(UnifiedReleaseProgramHandoffStateError):
        store.signoff_handoff(program_id, {"signed_by": "chair", "role": "release_owner"})


@pytest.mark.parametrize(
    ("decision", "reason"),
    [
        ("rejected", "rejected_response_present"),
        ("needs_changes", "needs_changes_response_present"),
    ],
)
def test_unified_release_program_handoff_blocks_negative_responses_before_signoff(tmp_path: Path, decision: str, reason: str) -> None:
    store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest = _program_ops_handoff(tmp_path)
    store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    pack = store.export_review_pack(program_id, {"audience": "release_owner"})
    store.build_review_pack_zip(program_id, pack["review_pack_id"])
    accepted_response = store.import_response(program_id, _review_response(store, program_id, pack["review_pack_id"], role="release_owner", decision="accepted"))
    accepted = store.create_accepted_evidence(program_id, accepted_response["response"]["response_id"])
    store.import_response(program_id, _review_response(store, program_id, pack["review_pack_id"], role="technical_reviewer", organization="qa-team", decision=decision))
    evidence_id = accepted["evidence"]["evidence_id"]
    _write_handoff_manifest(store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest, [_accepted_manifest_row(store, program_id, evidence_id, accepted_response["response"]["response_id"])])

    refreshed = store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    board = store.refresh_decision_board(
        program_id,
        {"policy": {"required_roles": ["release_owner"], "minimum_acceptances": 1, "minimum_organizations": 1, "block_on_rejected": True, "block_on_needs_changes": True}},
    )

    assert refreshed["status"] == "ready_for_review"
    assert board["status"] == "blocked"
    assert any(row["reason"] == reason for row in board["conflicts"])
    with pytest.raises(UnifiedReleaseProgramHandoffStateError):
        store.signoff_handoff(program_id, {"signed_by": "chair", "role": "release_owner"})


def test_unified_release_program_handoff_verifier_rejects_declared_extra_and_full_resign(tmp_path: Path) -> None:
    store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest = _program_ops_handoff(tmp_path)
    store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    pack = store.export_review_pack(program_id, {"audience": "release_owner"})
    store.build_review_pack_zip(program_id, pack["review_pack_id"])
    response = store.import_response(program_id, _review_response(store, program_id, pack["review_pack_id"]))
    accepted = store.create_accepted_evidence(program_id, response["response"]["response_id"])
    evidence_id = accepted["evidence"]["evidence_id"]
    _write_handoff_manifest(store, program_store, ops_store, program_id, program_manifest_path, evidence_manifest, [_accepted_manifest_row(store, program_id, evidence_id, response["response"]["response_id"])])
    store.refresh_handoff(program_id, {"external_evidence_manifest": evidence_manifest})
    store.refresh_decision_board(program_id, {})
    store.signoff_handoff(program_id, {"signed_by": "original handoff chair", "role": "release_owner"})
    zipped = store.build_handoff_archive_zip(program_id)

    extra_zip = tmp_path / "handoff-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_handoff_package(extra_zip, strict=True)

    forged_zip = tmp_path / "handoff-forged.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _full_resign_handoff_signer)
    forged = verify_unified_release_program_handoff_package(
        forged_zip,
        strict=True,
        require_current=True,
        require_accepted=True,
        require_signed=True,
        external_evidence_manifest_path=evidence_manifest,
        handoff_signoff_binding_path=store.signoff_binding_path(program_id),
    )

    assert extra["status"] == "failed"
    assert "urph_allowed_entries" in extra["blockers"]
    assert forged["status"] == "failed"
    assert "urph_external_signoff_binding_hash" in forged["blockers"]


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra] = b"unexpected handoff file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra, "size_bytes": len(entries[extra]), "sha256": _sha256_bytes(entries[extra])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _full_resign_handoff_signer(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["program-handoff-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged handoff chair"
    signoff["role"] = "forged_role"
    signoff["reason"] = "forged reason"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["program-handoff-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    history_rows = []
    previous = ""
    signoff_event = None
    for line in entries["program-handoff-history.jsonl"].decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "unified_release_program_handoff_signoff_created":
            event["signed_by"] = signoff["signed_by"]
            event["role"] = signoff["role"]
            event["reason"] = signoff["reason"]
            event["signoff_hash"] = signoff["integrity_hash"]
            event["signoff_payload_hash"] = signoff["payload_hash"]
            signoff_event = event
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        history_rows.append(event)
    entries["program-handoff-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in history_rows) + "\n").encode("utf-8")
    binding = json.loads(entries["program-handoff-signoff-binding-summary.json"].decode("utf-8"))
    binding["signed_by"] = signoff["signed_by"]
    binding["role"] = signoff["role"]
    binding["reason"] = signoff["reason"]
    binding["signoff_hash"] = signoff["integrity_hash"]
    binding["signoff_payload_hash"] = signoff["payload_hash"]
    if signoff_event:
        binding["latest_history_event_hash"] = signoff_event["event_hash"]
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["program-handoff-signoff-binding-summary.json"] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["source"]["handoff_signoff_hash"] = signoff["integrity_hash"]
    manifest["source"]["handoff_signoff_binding_hash"] = binding["integrity_hash"]
    _sync_manifest_file(manifest, "program-handoff-signoff.json", entries["program-handoff-signoff.json"])
    _sync_manifest_file(manifest, "program-handoff-history.jsonl", entries["program-handoff-history.jsonl"])
    _sync_manifest_file(manifest, "program-handoff-signoff-binding-summary.json", entries["program-handoff-signoff-binding-summary.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    files = [row for row in manifest.get("files", []) if row.get("path") != rel]
    files.append({"path": rel, "size_bytes": len(data), "sha256": _sha256_bytes(data)})
    manifest["files"] = sorted(files, key=lambda row: row.get("path") or "")


def _manifest_hash(path: Path) -> str:
    import zipfile

    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read("manifest.json").decode("utf-8"))["integrity_hash"]


def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
