from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center_release_train import (
    DEFAULT_REQUIRED_EVIDENCE,
    UnifiedCommandCenterReleaseTrainStateError,
    UnifiedCommandCenterReleaseTrainStore,
    write_external_evidence_manifest,
)
from song_agent.unified_command_center_release_train_verifier import verify_unified_command_center_release_train_package
from tests.test_unified_command_center_reviewer_decision_board import _board_fixture


def _train_fixture(tmp_path: Path):
    ucc_store, evidence_store, board_store, center_id, review_id, review_zip, accepted = _board_fixture(tmp_path)
    board_id = "uccdb-board"
    board_store.create_board(center_id, {"board_id": board_id, "review_id": review_id, "accepted_evidence": accepted})
    board_store.signoff(center_id, board_id, {"signed_by": "train decision chair"})
    board_zip = board_store.build_zip(center_id, board_id)
    board_store.verify_archive(
        center_id,
        board_id,
        {
            "strict": True,
            "require_signed": True,
            "require_quorum": True,
            "evidence_review": review_zip["zip_path"],
            "evidence_review_verification_report": evidence_store.verification_report_path(center_id, review_id),
            "accepted_evidence": [row["zip_path"] for row in accepted],
            "accepted_evidence_verification_reports": [row["verification_report_path"] for row in accepted],
            "accepted_evidence_response_verification_reports": [row["response_verification_report_path"] for row in accepted],
        },
    )
    train_store = UnifiedCommandCenterReleaseTrainStore(root=tmp_path / ".musicforge" / "unified-command-trains")
    train = train_store.create_train({"train_id": "uct-train", "required_evidence": DEFAULT_REQUIRED_EVIDENCE})
    train_store.add_item(train["train_id"], {"item_id": "item-001", "center_id": center_id})
    signoff_store = evidence_store.signoff_store
    handoff_store = evidence_store.handoff_store
    review_store = evidence_store.review_store
    rows = [
        _evidence_row("item-001", center_id, "ucc", ucc_store.zip_path(center_id), ucc_store.verification_report_path(center_id)),
        _evidence_row("item-001", center_id, "ucc_archive", signoff_store.archive_zip_path(center_id), signoff_store.archive_verification_report_path(center_id)),
        _evidence_row("item-001", center_id, "handoff", handoff_store.zip_path(center_id), handoff_store.verification_report_path(center_id)),
        _evidence_row("item-001", center_id, "continuous_review", review_store.zip_path(center_id, "uccrv-clear"), review_store.verification_report_path(center_id, "uccrv-clear")),
        _evidence_row("item-001", center_id, "evidence_review", Path(review_zip["zip_path"]), evidence_store.verification_report_path(center_id, review_id)),
        _evidence_row("item-001", center_id, "reviewer_decision_board", Path(board_zip["zip_path"]), board_store.verification_report_path(center_id, board_id)),
    ]
    manifest_path = tmp_path / "train-external-evidence.json"
    write_external_evidence_manifest(manifest_path, train_id=train["train_id"], items=rows)
    return train_store, train["train_id"], manifest_path, ucc_store, center_id


def _evidence_row(item_id: str, center_id: str, evidence_type: str, zip_path: Path, report_path: Path) -> dict:
    return {
        "item_id": item_id,
        "center_id": center_id,
        "evidence_type": evidence_type,
        "zip_path": str(zip_path),
        "verification_report_path": str(report_path),
    }


def test_release_train_lifecycle_signoff_and_delete_guard(tmp_path: Path) -> None:
    store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)

    report = store.refresh(train_id, {"external_evidence_manifest": manifest_path})
    signoff = store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "train lead"})
    zipped = store.build_zip(train_id)
    verification = verify_unified_command_center_release_train_package(
        zipped["zip_path"],
        strict=True,
        require_go=True,
        require_signed=True,
        external_evidence_manifest_path=manifest_path,
        signoff_binding_path=store.signoff_binding_path(train_id),
    )

    assert report["status"] == "go", report.get("blockers")
    assert signoff["status"] == "signed"
    assert verification["status"] == "passed", verification["blockers"]
    with pytest.raises(UnifiedCommandCenterReleaseTrainStateError):
        store.refresh(train_id, {"external_evidence_manifest": manifest_path})
    store.signoff_path(train_id).unlink()
    with pytest.raises(UnifiedCommandCenterReleaseTrainStateError):
        store.add_item(train_id, {"item_id": "item-002", "center_id": "ucc-other"})


def test_release_train_blocks_duplicate_center_unless_explicit(tmp_path: Path) -> None:
    store, train_id, _manifest_path, _ucc_store, center_id = _train_fixture(tmp_path)

    with pytest.raises(UnifiedCommandCenterReleaseTrainStateError):
        store.add_item(train_id, {"item_id": "item-dup", "center_id": center_id})

    train = store.create_train({"train_id": "uct-duplicates", "allow_duplicate_center": True})
    store.add_item(train["train_id"], {"item_id": "item-a", "center_id": center_id})
    second = store.add_item(train["train_id"], {"item_id": "item-b", "center_id": center_id, "allow_duplicate_center": True})
    assert second["center_id"] == center_id


def test_release_train_external_manifest_reorder_ok_and_missing_failed(tmp_path: Path) -> None:
    store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    manifest = read_json(manifest_path)
    manifest["items"] = list(reversed(manifest["items"]))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    reordered = tmp_path / "train-external-reordered.json"
    reordered.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    store.signoff(train_id, {"external_evidence_manifest": reordered, "signed_by": "train lead"})
    zipped = store.build_zip(train_id)
    ok_report = verify_unified_command_center_release_train_package(zipped["zip_path"], strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=reordered, signoff_binding_path=store.signoff_binding_path(train_id))

    manifest["items"] = manifest["items"][:-1]
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    missing = tmp_path / "train-external-missing.json"
    missing.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    missing_report = verify_unified_command_center_release_train_package(zipped["zip_path"], strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=missing, signoff_binding_path=store.signoff_binding_path(train_id))

    assert ok_report["status"] == "passed", ok_report["blockers"]
    assert missing_report["status"] == "failed"
    assert "ucc_train_external_evidence_manifest_identity" in missing_report["blockers"]


def test_release_train_rejects_declared_extra_full_resign_and_stale_external_zip(tmp_path: Path) -> None:
    store, train_id, manifest_path, ucc_store, center_id = _train_fixture(tmp_path)
    store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "original signer"})
    zipped = store.build_zip(train_id)

    extra_zip = tmp_path / "train-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_command_center_release_train_package(extra_zip, strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path, signoff_binding_path=store.signoff_binding_path(train_id))

    missing_binding = verify_unified_command_center_release_train_package(Path(zipped["zip_path"]), strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path)

    forged_zip = tmp_path / "train-forged-signer.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _forge_train_signer)
    forged = verify_unified_command_center_release_train_package(forged_zip, strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path, signoff_binding_path=store.signoff_binding_path(train_id))

    full_resign_zip = tmp_path / "train-full-resign-signer.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), full_resign_zip, _full_resign_train_signer_with_binding)
    full_resign = verify_unified_command_center_release_train_package(full_resign_zip, strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=manifest_path, signoff_binding_path=store.signoff_binding_path(train_id))

    stale_ucc_zip = tmp_path / "ucc-stale.zip"
    _v76_rewrite_zip(ucc_store.zip_path(center_id), stale_ucc_zip, _add_declared_extra)
    manifest = read_json(manifest_path)
    for row in manifest["items"]:
        if row["evidence_type"] == "ucc":
            row["zip_path"] = str(stale_ucc_zip)
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    stale_manifest = tmp_path / "train-external-stale-ucc.json"
    stale_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    stale = verify_unified_command_center_release_train_package(zipped["zip_path"], strict=True, require_go=True, require_signed=True, external_evidence_manifest_path=stale_manifest, signoff_binding_path=store.signoff_binding_path(train_id))

    assert extra["status"] == "failed"
    assert "ucc_train_allowed_entries" in extra["blockers"]
    assert missing_binding["status"] == "failed"
    assert "ucc_train_external_signoff_binding_required" in missing_binding["blockers"]
    assert forged["status"] == "failed"
    assert "ucc_train_signoff_binding_signed_by" in forged["blockers"]
    assert full_resign["status"] == "failed"
    assert "ucc_train_external_signoff_binding_hash" in full_resign["blockers"]
    assert stale["status"] == "failed"
    assert any(blocker.startswith("ucc_train_external_evidence_binding") for blocker in stale["blockers"])


def test_release_train_dependency_cycle_blocks_signoff(tmp_path: Path) -> None:
    store, _train_id, manifest_path, _ucc_store, center_id = _train_fixture(tmp_path)
    train = store.create_train({"train_id": "uct-cycle"})
    store.add_item(train["train_id"], {"item_id": "a", "center_id": f"{center_id}-a", "depends_on": ["b"], "required_evidence": []})
    store.add_item(train["train_id"], {"item_id": "b", "center_id": f"{center_id}-b", "depends_on": ["a"], "required_evidence": []})
    report = store.refresh(train["train_id"], {"external_evidence_manifest": manifest_path})

    assert report["status"] == "no_go"
    assert "dependency:cycle" in report["blockers"]
    with pytest.raises(UnifiedCommandCenterReleaseTrainStateError):
        store.signoff(train["train_id"], {"external_evidence_manifest": manifest_path})


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra_name = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra_name] = b"unexpected\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra_name, "size_bytes": len(entries[extra_name]), "sha256": _sha256_bytes(entries[extra_name])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_train_signer(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["train-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged signer"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["train-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    history_rows = []
    previous = ""
    for line in entries["train-history.jsonl"].decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "ucc_release_train_signoff_created":
            event["signed_by"] = "forged signer"
            event["signoff_hash"] = signoff["integrity_hash"]
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        history_rows.append(event)
    entries["train-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in history_rows) + "\n").encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["train_signoff_hash"] = signoff["integrity_hash"]
    _sync_manifest_file(manifest, "train-signoff.json", entries["train-signoff.json"])
    _sync_manifest_file(manifest, "train-history.jsonl", entries["train-history.jsonl"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _full_resign_train_signer_with_binding(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["train-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged signer"
    signoff["role"] = "forged_role"
    signoff["reason"] = "forged release train signoff"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["train-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    history_rows = []
    previous = ""
    signoff_event = None
    for line in entries["train-history.jsonl"].decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "ucc_release_train_signoff_created":
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
        if event.get("event_type") == "ucc_release_train_signoff_created":
            signoff_event = event
    entries["train-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in history_rows) + "\n").encode("utf-8")

    binding = json.loads(entries["train-signoff-binding-summary.json"].decode("utf-8"))
    binding["signed_by"] = signoff["signed_by"]
    binding["role"] = signoff["role"]
    binding["reason"] = signoff["reason"]
    binding["signoff_hash"] = signoff["integrity_hash"]
    binding["signoff_payload_hash"] = signoff["payload_hash"]
    if signoff_event:
        binding["history_event_hash"] = signoff_event["event_hash"]
        binding["history_event_payload_hash"] = signoff_event["payload_hash"]
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["train-signoff-binding-summary.json"] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["train_signoff_hash"] = signoff["integrity_hash"]
    manifest.setdefault("source", {})["train_signoff_binding_hash"] = binding["integrity_hash"]
    _sync_manifest_file(manifest, "train-signoff.json", entries["train-signoff.json"])
    _sync_manifest_file(manifest, "train-history.jsonl", entries["train-history.jsonl"])
    _sync_manifest_file(manifest, "train-signoff-binding-summary.json", entries["train-signoff-binding-summary.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    for row in manifest.get("files", []):
        if row.get("path") == rel:
            row["sha256"] = _sha256_bytes(data)
            row["size_bytes"] = len(data)
            return
    raise AssertionError(f"manifest row missing: {rel}")


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
