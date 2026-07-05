from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStateError
from song_agent.unified_command_center_release_train_change_control import (
    UnifiedCommandCenterReleaseTrainChangeControlStateError,
    UnifiedCommandCenterReleaseTrainChangeControlStore,
)
from song_agent.unified_command_center_release_train_change_control_verifier import verify_unified_command_center_release_train_change_control_package
from tests.test_unified_command_center_release_train import _train_fixture


def test_release_train_change_control_reset_resign_and_verify(tmp_path: Path) -> None:
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "original train lead"})
    first_zip = train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})

    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    request = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "requested_by": "operator", "change": ["refresh UCC evidence"]})
    approval = change_store.approve_request(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path, "approved_by": "train owner"})
    proof = change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path, "reset_by": "train owner"})

    assert approval["status"] == "approved"
    assert proof["status"] == "applied"
    assert train_store.latest_signoff_state(train_id)["status"] == "reset"
    assert (train_store.archive_history_signoff_dir(train_id, proof["previous_signoff_hash"]) / "archive" / Path(first_zip["zip_path"]).name).exists()
    assert train_store.gate(train_id, external_evidence_manifest_path=manifest_path)["status"] == "failed"
    with pytest.raises(UnifiedCommandCenterReleaseTrainChangeControlStateError):
        change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})

    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "successor train lead"})
    second_zip = train_store.build_zip(train_id)
    train_report = train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    assert Path(second_zip["zip_path"]).exists()
    assert train_report["status"] == "passed", train_report.get("blockers")

    zipped = change_store.build_zip(train_id)
    report = verify_unified_command_center_release_train_change_control_package(
        zipped["zip_path"],
        strict=True,
        require_reset_applied=True,
        require_current_train=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
        reset_proof_path=change_store.reset_proof_path(train_id, request["change_request_id"]),
    )
    assert report["status"] == "passed", report.get("blockers")

    missing_proof = verify_unified_command_center_release_train_change_control_package(
        zipped["zip_path"],
        strict=True,
        require_reset_applied=True,
        require_current_train=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
    )
    assert missing_proof["status"] == "failed"
    assert "ucc_train_change_control_external_reset_proof_required" in missing_proof["blockers"]


def test_release_train_change_control_rejects_declared_extra_and_forged_reset(tmp_path: Path) -> None:
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "original train lead"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    request = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh"]})
    change_store.approve_request(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "successor"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    zipped = change_store.build_zip(train_id)

    extra_zip = tmp_path / "change-control-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_change_control_extra)
    extra = verify_unified_command_center_release_train_change_control_package(extra_zip, strict=True, require_reset_applied=True, reset_proof_path=change_store.reset_proof_path(train_id, request["change_request_id"]))
    assert extra["status"] == "failed"
    assert "ucc_train_change_control_allowed_entries" in extra["blockers"]

    forged_zip = tmp_path / "change-control-forged-reset.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _forge_change_control_applied_reset)
    forged = verify_unified_command_center_release_train_change_control_package(forged_zip, strict=True, require_reset_applied=True, reset_proof_path=change_store.reset_proof_path(train_id, request["change_request_id"]))
    assert forged["status"] == "failed"
    assert "ucc_train_change_control_external_reset_proof_hash" in forged["blockers"]


def test_release_train_change_control_reset_blocks_signed_mutation_until_re_sign(tmp_path: Path) -> None:
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    with pytest.raises(UnifiedCommandCenterReleaseTrainStateError):
        train_store.refresh(train_id, {"external_evidence_manifest": manifest_path})

    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    request = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh"]})
    change_store.approve_request(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})

    refreshed = train_store.refresh(train_id, {"external_evidence_manifest": manifest_path})
    assert refreshed["status"] == "go"


def _add_declared_change_control_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra_name = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra_name] = b"unexpected\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra_name, "size_bytes": len(entries[extra_name]), "sha256": _sha256_bytes(entries[extra_name])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_change_control_applied_reset(entries: dict[str, bytes]) -> dict[str, bytes]:
    summaries = json.loads(entries["change-request-summaries.json"].decode("utf-8"))
    summaries["requests"][0]["reset_proof_hash"] = "f" * 64
    summaries["integrity_hash"] = stable_hash({key: value for key, value in summaries.items() if key != "integrity_hash"})
    entries["change-request-summaries.json"] = json.dumps(summaries, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    report = json.loads(entries["change-control-report.json"].decode("utf-8"))
    report["summary"] = summaries["summary"]
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    entries["change-control-report.json"] = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["summaries_hash"] = summaries["integrity_hash"]
    manifest.setdefault("source", {})["report_hash"] = report["integrity_hash"]
    _sync_manifest_file(manifest, "change-request-summaries.json", entries["change-request-summaries.json"])
    _sync_manifest_file(manifest, "change-control-report.json", entries["change-control-report.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    for row in manifest.get("files", []):
        if row.get("path") == rel:
            row["size_bytes"] = len(data)
            row["sha256"] = _sha256_bytes(data)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
