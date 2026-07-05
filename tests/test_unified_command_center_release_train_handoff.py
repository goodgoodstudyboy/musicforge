from __future__ import annotations

import json
from pathlib import Path

from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore
from song_agent.unified_command_center_release_train_handoff import UnifiedCommandCenterReleaseTrainHandoffStateError, UnifiedCommandCenterReleaseTrainHandoffStore
from song_agent.unified_command_center_release_train_handoff_verifier import verify_unified_command_center_release_train_handoff_package
from song_agent.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore
from tests.test_unified_command_center_release_train import _sha256_bytes, _sync_manifest_file, _train_fixture


def _handoff_fixture(tmp_path: Path, policy: dict | None = None):
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "original train lead"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})

    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    request = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh train evidence"]})
    change_store.approve_request(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path, "approved_by": "train owner"})
    change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path, "reset_by": "train owner"})
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "successor train lead"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    change_store.build_zip(train_id)
    change_store.verify_package(
        train_id,
        {
            "strict": True,
            "require_reset_applied": True,
            "require_current_train": True,
            "external_evidence_manifest": manifest_path,
            "reset_proof": change_store.reset_proof_path(train_id, request["change_request_id"]),
        },
    )

    lifecycle_store = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    reset_proofs = [change_store.reset_proof_path(train_id, request["change_request_id"])]
    lifecycle_payload = {
        "external_evidence_manifest": manifest_path,
        "change_control_zip": change_store.zip_path(train_id),
        "change_control_verification_report": change_store.verification_report_path(train_id),
        "reset_proofs": reset_proofs,
    }
    lifecycle_store.refresh_report(train_id, lifecycle_payload)
    lifecycle_store.build_zip(train_id)
    lifecycle_store.verify_package(train_id, {"strict": True, "require_current_train": True, "require_change_control": True, **lifecycle_payload})

    handoff_store = UnifiedCommandCenterReleaseTrainHandoffStore(train_store, change_store, lifecycle_store)
    payload = {
        "external_evidence_manifest": manifest_path,
        "change_control_zip": change_store.zip_path(train_id),
        "change_control_verification_report": change_store.verification_report_path(train_id),
        "reset_proofs": reset_proofs,
        "lifecycle_zip": lifecycle_store.zip_path(train_id),
        "lifecycle_verification_report": lifecycle_store.verification_report_path(train_id),
    }
    create_payload = {"handoff_id": "rth-test", **payload}
    if policy is not None:
        create_payload["policy"] = policy
    handoff = handoff_store.create_handoff(train_id, create_payload)
    return handoff_store, handoff["handoff"]["handoff_id"], train_store, change_store, lifecycle_store, train_id, manifest_path, payload


def _verify_payload(handoff_store, handoff_id: str, train_store, change_store, lifecycle_store, train_id: str, manifest_path: Path, payload: dict) -> dict:
    return {
        "strict": True,
        "require_current": True,
        "require_lifecycle": True,
        "train_archive_path": train_store.zip_path(train_id),
        "train_archive_verification_report_path": train_store.verification_report_path(train_id),
        "train_signoff_binding_path": train_store.signoff_binding_path(train_id),
        "external_evidence_manifest_path": manifest_path,
        "change_control_zip_path": change_store.zip_path(train_id),
        "change_control_verification_report_path": change_store.verification_report_path(train_id),
        "reset_proof_paths": payload["reset_proofs"],
        "lifecycle_zip_path": lifecycle_store.zip_path(train_id),
        "lifecycle_verification_report_path": lifecycle_store.verification_report_path(train_id),
        "handoff_signoff_binding_path": handoff_store.signoff_binding_path(train_id, handoff_id),
    }


def test_release_train_handoff_signed_flow_and_acceptance(tmp_path: Path) -> None:
    handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload = _handoff_fixture(tmp_path)
    report = handoff_store.refresh_report(train_id, handoff_id, payload)
    zipped = handoff_store.build_zip(train_id, handoff_id)
    verify_payload = _verify_payload(handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload)
    verified = verify_unified_command_center_release_train_handoff_package(zipped["zip_path"], **{key: value for key, value in verify_payload.items() if key != "handoff_signoff_binding_path"})

    response = handoff_store.import_response(
        train_id,
        handoff_id,
        {
            "reviewer": {"name": "external board", "organization": "reviewer org", "role": "release_owner"},
            "organization": "reviewer org",
            "role": "release_owner",
            "decision": "accepted",
            "reviewed_at": "2026-07-05T00:00:00Z",
            "handoff_id": handoff_id,
            "train_id": train_id,
            "handoff_zip_sha256": zipped["zip_sha256"],
            "handoff_manifest_hash": zipped["manifest"]["integrity_hash"],
            "handoff_source_hash": report["source_hash"],
            "handoff_verification_report_hash": handoff_store.verify_package(train_id, handoff_id, verify_payload)["integrity_hash"],
        },
    )
    response_doc = response["response"]
    evidence = handoff_store.create_accepted_evidence(train_id, handoff_id, response_doc["response_id"])
    signed = handoff_store.signoff(
        train_id,
        handoff_id,
        {
            **payload,
            "policy": {"require_external_acceptance": True},
            "signed_by": "handoff chair",
            "role": "release_train_owner",
            "reason": "External handoff accepted.",
        },
    )
    signed_zip = handoff_store.build_zip(train_id, handoff_id)
    signed_verify = verify_unified_command_center_release_train_handoff_package(
        signed_zip["zip_path"],
        require_signed=True,
        require_accepted=True,
        accepted_evidence_dir=handoff_store.responses_dir(train_id, handoff_id),
        **verify_payload,
    )

    assert report["status"] == "ready", report["blockers"]
    assert verified["status"] == "passed", verified["blockers"]
    assert response_doc["decision"] == "accepted"
    assert evidence["package_type"] == "musicforge_release_train_handoff_accepted_evidence"
    assert signed["status"] == "signed"
    assert signed_verify["status"] == "passed", signed_verify["blockers"]


def test_release_train_handoff_rejects_accepted_evidence_role_forgery(tmp_path: Path) -> None:
    strict_policy = {
        "require_external_acceptance": True,
        "quorum": {"min_accepted": 1, "min_organizations": 1, "required_roles": ["release_owner"]},
    }
    handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload = _handoff_fixture(tmp_path, policy=strict_policy)
    report = handoff_store.refresh_report(train_id, handoff_id, payload)
    zipped = handoff_store.build_zip(train_id, handoff_id)
    verify_payload = _verify_payload(handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload)
    verification = handoff_store.verify_package(train_id, handoff_id, verify_payload)
    response = handoff_store.import_response(
        train_id,
        handoff_id,
        {
            "reviewer": {"name": "technical reviewer", "organization": "reviewer org", "role": "technical_reviewer"},
            "decision": "accepted",
            "reviewed_at": "2026-07-05T00:00:00Z",
            "handoff_id": handoff_id,
            "train_id": train_id,
            "handoff_zip_sha256": zipped["zip_sha256"],
            "handoff_manifest_hash": zipped["manifest"]["integrity_hash"],
            "handoff_source_hash": report["source_hash"],
            "handoff_verification_report_hash": verification["integrity_hash"],
        },
    )
    response_id = response["response"]["response_id"]
    handoff_store.create_accepted_evidence(train_id, handoff_id, response_id)

    try:
        handoff_store.signoff(train_id, handoff_id, {**payload, "signed_by": "handoff chair"})
    except UnifiedCommandCenterReleaseTrainHandoffStateError:
        pass
    else:  # pragma: no cover - explicit assertion clarity
        raise AssertionError("technical_reviewer accepted evidence must not satisfy release_owner quorum")

    evidence_path = handoff_store.response_dir(train_id, handoff_id, response_id) / "accepted-evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["public_summary"]["reviewer_role"] = "release_owner"
    evidence["integrity_hash"] = stable_hash({key: value for key, value in evidence.items() if key != "integrity_hash"})
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    try:
        handoff_store.signoff(train_id, handoff_id, {**payload, "signed_by": "handoff chair"})
    except UnifiedCommandCenterReleaseTrainHandoffStateError:
        pass
    else:  # pragma: no cover - explicit assertion clarity
        raise AssertionError("forged accepted-evidence public_summary role must not satisfy quorum")

    forged_report = handoff_store.refresh_report(train_id, handoff_id, payload)
    handoff_store.export_handoff(train_id, handoff_id)
    forged_verify = verify_unified_command_center_release_train_handoff_package(
        handoff_store.build_zip(train_id, handoff_id)["zip_path"],
        require_accepted=True,
        accepted_evidence_dir=handoff_store.responses_dir(train_id, handoff_id),
        **verify_payload,
    )

    assert forged_report["status"] == "blocked"
    assert forged_report["summary"]["blocker_count"] >= 1
    assert forged_verify["status"] == "failed"
    assert "ucc_train_handoff_accepted_evidence_external_sidecars_valid" in forged_verify["blockers"]


def test_release_train_handoff_rejects_declared_extra_and_full_resign(tmp_path: Path) -> None:
    handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload = _handoff_fixture(tmp_path)
    handoff_store.signoff(train_id, handoff_id, {**payload, "signed_by": "original handoff signer"})
    zipped = handoff_store.build_zip(train_id, handoff_id)
    verify_payload = _verify_payload(handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload)

    extra_zip = tmp_path / "handoff-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_handoff_extra)
    extra = verify_unified_command_center_release_train_handoff_package(extra_zip, strict=True)

    forged_zip = tmp_path / "handoff-full-resign.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _full_resign_handoff_signer)
    forged = verify_unified_command_center_release_train_handoff_package(forged_zip, require_signed=True, **verify_payload)

    missing_external_binding = verify_unified_command_center_release_train_handoff_package(
        zipped["zip_path"],
        strict=True,
        require_signed=True,
        require_current=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
        change_control_zip_path=change_store.zip_path(train_id),
        change_control_verification_report_path=change_store.verification_report_path(train_id),
        reset_proof_paths=payload["reset_proofs"],
        lifecycle_zip_path=lifecycle_store.zip_path(train_id),
        lifecycle_verification_report_path=lifecycle_store.verification_report_path(train_id),
    )

    assert extra["status"] == "failed"
    assert "ucc_train_handoff_allowed_entries" in extra["blockers"]
    assert forged["status"] == "failed"
    assert "ucc_train_handoff_external_signoff_binding_hash" in forged["blockers"]
    assert missing_external_binding["status"] == "failed"
    assert "ucc_train_handoff_external_signoff_binding_required" in missing_external_binding["blockers"]


def _add_declared_handoff_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra_name = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra_name] = b"unexpected handoff instruction\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra_name, "size_bytes": len(entries[extra_name]), "sha256": _sha256_bytes(entries[extra_name])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _full_resign_handoff_signer(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["handoff-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged handoff signer"
    signoff["role"] = "forged_role"
    signoff["reason"] = "forged handoff signoff"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["handoff-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    previous = ""
    signoff_event = None
    events = []
    for line in entries["handoff-history.jsonl"].decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "ucc_release_train_handoff_signoff_created":
            event["signed_by"] = signoff["signed_by"]
            event["role"] = signoff["role"]
            event["reason"] = signoff["reason"]
            event["signoff_hash"] = signoff["integrity_hash"]
            event["signoff_payload_hash"] = signoff["payload_hash"]
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        events.append(event)
        if event.get("event_type") == "ucc_release_train_handoff_signoff_created":
            signoff_event = event
    entries["handoff-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in events) + "\n").encode("utf-8")

    binding = json.loads(entries["handoff-signoff-binding-summary.json"].decode("utf-8"))
    binding["signed_by"] = signoff["signed_by"]
    binding["role"] = signoff["role"]
    binding["reason"] = signoff["reason"]
    binding["signoff_hash"] = signoff["integrity_hash"]
    binding["signoff_payload_hash"] = signoff["payload_hash"]
    if signoff_event:
        binding["history_event_hash"] = signoff_event["event_hash"]
        binding["history_event_payload_hash"] = signoff_event["payload_hash"]
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["handoff-signoff-binding-summary.json"] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["signoff_hash"] = signoff["integrity_hash"]
    manifest.setdefault("source", {})["signoff_binding_hash"] = binding["integrity_hash"]
    _sync_manifest_file(manifest, "handoff-signoff.json", entries["handoff-signoff.json"])
    _sync_manifest_file(manifest, "handoff-history.jsonl", entries["handoff-history.jsonl"])
    _sync_manifest_file(manifest, "handoff-signoff-binding-summary.json", entries["handoff-signoff-binding-summary.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries
