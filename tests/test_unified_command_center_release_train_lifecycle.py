from __future__ import annotations

import json
from pathlib import Path

from song_agent.projectio import read_json
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore
from song_agent.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore
from song_agent.unified_command_center_release_train_lifecycle_verifier import verify_unified_command_center_release_train_lifecycle_package
from tests.test_unified_command_center_release_train import _sha256_bytes, _sync_manifest_file, _train_fixture


def test_release_train_lifecycle_no_reset_passes(tmp_path: Path) -> None:
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "train lead"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    lifecycle = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store)

    report = lifecycle.refresh_report(train_id, {"external_evidence_manifest": manifest_path})
    zipped = lifecycle.build_zip(train_id)
    verified = verify_unified_command_center_release_train_lifecycle_package(
        zipped["zip_path"],
        strict=True,
        require_current_train=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
    )

    assert report["status"] == "passed", report["blockers"]
    assert verified["status"] == "passed", verified["blockers"]


def test_release_train_lifecycle_reset_successor_and_missing_proof(tmp_path: Path) -> None:
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "original train lead"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    request = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh evidence"]})
    change_store.approve_request(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    proof = change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
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
    lifecycle = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    payload = {
        "external_evidence_manifest": manifest_path,
        "change_control_zip": change_store.zip_path(train_id),
        "change_control_verification_report": change_store.verification_report_path(train_id),
        "reset_proofs": [change_store.reset_proof_path(train_id, request["change_request_id"])],
    }

    report = lifecycle.refresh_report(train_id, payload)
    zipped = lifecycle.build_zip(train_id)
    verified = verify_unified_command_center_release_train_lifecycle_package(
        zipped["zip_path"],
        strict=True,
        require_current_train=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
        change_control_zip_path=change_store.zip_path(train_id),
        change_control_verification_report_path=change_store.verification_report_path(train_id),
        reset_proof_paths=[change_store.reset_proof_path(train_id, request["change_request_id"])],
    )
    missing_proof = verify_unified_command_center_release_train_lifecycle_package(
        zipped["zip_path"],
        strict=True,
        require_current_train=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
        change_control_zip_path=change_store.zip_path(train_id),
        change_control_verification_report_path=change_store.verification_report_path(train_id),
    )

    assert proof["status"] == "applied"
    assert report["status"] == "passed", report["blockers"]
    assert verified["status"] == "passed", verified["blockers"]
    assert missing_proof["status"] == "failed"
    assert "ucc_train_lifecycle_reset_semantics_001_proof" in missing_proof["blockers"]


def test_release_train_lifecycle_multiple_resets_pass(tmp_path: Path) -> None:
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "train lead 1"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)

    request_1 = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh evidence 1"]})
    change_store.approve_request(train_id, request_1["change_request_id"], {"external_evidence_manifest": manifest_path})
    proof_1 = change_store.reset_train_signoff(train_id, request_1["change_request_id"], {"external_evidence_manifest": manifest_path})
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "train lead 2"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})

    request_2 = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh evidence 2"]})
    change_store.approve_request(train_id, request_2["change_request_id"], {"external_evidence_manifest": manifest_path})
    proof_2 = change_store.reset_train_signoff(train_id, request_2["change_request_id"], {"external_evidence_manifest": manifest_path})
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "train lead 3"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})

    change_store.build_zip(train_id)
    change_verified = change_store.verify_package(
        train_id,
        {
            "strict": True,
            "require_reset_applied": True,
            "require_current_train": True,
            "external_evidence_manifest": manifest_path,
            "reset_proof": change_store.reset_proof_path(train_id, request_2["change_request_id"]),
        },
    )
    lifecycle = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    payload = {
        "external_evidence_manifest": manifest_path,
        "change_control_zip": change_store.zip_path(train_id),
        "change_control_verification_report": change_store.verification_report_path(train_id),
        "reset_proofs": [
            change_store.reset_proof_path(train_id, request_1["change_request_id"]),
            change_store.reset_proof_path(train_id, request_2["change_request_id"]),
        ],
    }
    report = lifecycle.refresh_report(train_id, payload)
    zipped = lifecycle.build_zip(train_id)
    verified = verify_unified_command_center_release_train_lifecycle_package(
        zipped["zip_path"],
        strict=True,
        require_current_train=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
        change_control_zip_path=change_store.zip_path(train_id),
        change_control_verification_report_path=change_store.verification_report_path(train_id),
        reset_proof_paths=[
            change_store.reset_proof_path(train_id, request_1["change_request_id"]),
            change_store.reset_proof_path(train_id, request_2["change_request_id"]),
        ],
    )

    assert proof_1["status"] == "applied"
    assert proof_2["status"] == "applied"
    assert change_verified["status"] == "passed", change_verified["blockers"]
    assert report["status"] == "passed", report["blockers"]
    assert report["summary"]["reset_count"] == 2
    assert verified["status"] == "passed", verified["blockers"]


def test_release_train_lifecycle_rejects_declared_extra_and_full_resign_reset_count(tmp_path: Path) -> None:
    train_store, train_id, manifest_path, _ucc_store, _center_id = _train_fixture(tmp_path)
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "original train lead"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    request = change_store.create_request(train_id, {"external_evidence_manifest": manifest_path, "change": ["refresh evidence"]})
    change_store.approve_request(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    change_store.reset_train_signoff(train_id, request["change_request_id"], {"external_evidence_manifest": manifest_path})
    train_store.signoff(train_id, {"external_evidence_manifest": manifest_path, "signed_by": "successor train lead"})
    train_store.build_zip(train_id)
    train_store.verify_archive(train_id, {"external_evidence_manifest": manifest_path, "strict": True, "require_go": True, "require_signed": True})
    change_store.build_zip(train_id)
    change_store.verify_package(train_id, {"strict": True, "require_reset_applied": True, "require_current_train": True, "external_evidence_manifest": manifest_path, "reset_proof": change_store.reset_proof_path(train_id, request["change_request_id"])})
    lifecycle = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    payload = {"external_evidence_manifest": manifest_path, "change_control_zip": change_store.zip_path(train_id), "change_control_verification_report": change_store.verification_report_path(train_id), "reset_proofs": [change_store.reset_proof_path(train_id, request["change_request_id"])]}
    lifecycle.refresh_report(train_id, payload)
    zipped = lifecycle.build_zip(train_id)

    extra_zip = tmp_path / "lifecycle-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_lifecycle_extra)
    extra = verify_unified_command_center_release_train_lifecycle_package(extra_zip, strict=True)

    forged_zip = tmp_path / "lifecycle-full-resign-reset-count.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _forge_lifecycle_reset_count)
    forged = verify_unified_command_center_release_train_lifecycle_package(
        forged_zip,
        strict=True,
        require_current_train=True,
        train_archive_path=train_store.zip_path(train_id),
        train_archive_verification_report_path=train_store.verification_report_path(train_id),
        train_signoff_binding_path=train_store.signoff_binding_path(train_id),
        external_evidence_manifest_path=manifest_path,
        change_control_zip_path=change_store.zip_path(train_id),
        change_control_verification_report_path=change_store.verification_report_path(train_id),
        reset_proof_paths=[change_store.reset_proof_path(train_id, request["change_request_id"])],
    )

    assert extra["status"] == "failed"
    assert "ucc_train_lifecycle_allowed_entries" in extra["blockers"]
    assert forged["status"] == "failed"
    assert "ucc_train_lifecycle_report_reset_count" in forged["blockers"]


def _add_declared_lifecycle_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra_name = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra_name] = b"unexpected lifecycle instructions\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra_name, "size_bytes": len(entries[extra_name]), "sha256": _sha256_bytes(entries[extra_name])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_lifecycle_reset_count(entries: dict[str, bytes]) -> dict[str, bytes]:
    report = json.loads(entries["lifecycle-report.json"].decode("utf-8"))
    report["summary"]["reset_count"] = 0
    report["summary"]["applied_change_request_count"] = 0
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    entries["lifecycle-report.json"] = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["report_hash"] = report["integrity_hash"]
    manifest.setdefault("summary", {})["reset_count"] = 0
    manifest.setdefault("summary", {})["applied_change_request_count"] = 0
    _sync_manifest_file(manifest, "lifecycle-report.json", entries["lifecycle-report.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries
