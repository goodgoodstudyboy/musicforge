from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center import UnifiedCommandCenterStore
from song_agent.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStateError, UnifiedCommandCenterContinuousReviewStore
from song_agent.unified_command_center_continuous_review_verifier import verify_unified_command_center_continuous_review_package
from song_agent.unified_command_center_handoff import UnifiedCommandCenterHandoffStore
from song_agent.unified_command_center_signoff import UnifiedCommandCenterSignoffStore


def _release_check_report(path: Path, *, ok: bool = True) -> Path:
    payload = {"ok": ok, "summary": {"total": 1, "passed": 1 if ok else 0, "failed": 0 if ok else 1}, "results": [{"check_id": "synthetic.passed" if ok else "synthetic.failed", "status": "passed" if ok else "failed"}]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _ga_report(path: Path, *, status: str = "passed") -> Path:
    payload = {
        "package_type": "musicforge_ga_readiness_report",
        "status": status,
        "checks": [{"check_id": "ga.synthetic", "status": "passed" if status in {"passed", "ready"} else "failed"}],
    }
    payload["integrity_hash"] = stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _ready_signed_ucc(tmp_path: Path) -> tuple[UnifiedCommandCenterStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterHandoffStore, str]:
    release_check = _release_check_report(tmp_path / "release-check.json")
    store = UnifiedCommandCenterStore(root=tmp_path / ".musicforge" / "unified-command-centers")
    center = store.create(
        {
            "center_id": "ucc-review",
            "requirements": {
                "audio-command-center": False,
                "trust-operations-hub": False,
                "public-trust-center": False,
                "ga-readiness": False,
                "release-check": True,
            },
        }
    )
    evidence = {"release-check": {"report": release_check}}
    store.refresh(center["center_id"], evidence)
    store.build_zip(center["center_id"], evidence)
    assert store.verify_zip(center["center_id"], evidence=evidence, strict=True, require_ready=True)["status"] == "passed"
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    signoff_store.signoff(center["center_id"], {"signed_by": "release lead", "reason": "ready"})
    signoff_store.build_archive_zip(center["center_id"])
    assert signoff_store.verify_archive(center["center_id"])["status"] == "passed"
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    handoff_store.build_handoff_zip(center["center_id"])
    assert handoff_store.verify_handoff(center["center_id"])["status"] == "passed"
    return store, signoff_store, handoff_store, center["center_id"]


def test_unified_command_center_continuous_review_lifecycle(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)

    plan = review_store.create_plan(center_id, {"created_by": "qa"})
    result = review_store.run_review(center_id, plan["review_id"])
    zipped = review_store.build_zip(center_id, plan["review_id"])
    verification = review_store.verify_package(center_id, plan["review_id"])
    gate = review_store.gate(center_id, review_id=plan["review_id"])

    assert result["status"] == "passed", result["drift_report"].get("drifts")
    assert Path(zipped["zip_path"]).exists()
    assert verification["status"] == "passed", verification.get("blockers")
    assert gate["status"] == "passed", gate


def test_continuous_review_blocks_failed_external_ga_and_release_check(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    passed_ga = _ga_report(tmp_path / "ga-passed.json", status="passed")
    passed_release_check = _release_check_report(tmp_path / "release-check-passed.json", ok=True)
    plan = review_store.create_plan(center_id, {"ga_readiness_report": passed_ga, "release_check_report": passed_release_check})

    failed_ga = _ga_report(tmp_path / "ga-failed.json", status="failed")
    failed_release_check = _release_check_report(tmp_path / "release-check-failed.json", ok=False)
    result = review_store.run_review(
        center_id,
        plan["review_id"],
        {"ga_readiness_report": failed_ga, "release_check_report": failed_release_check},
    )
    zipped = review_store.build_zip(
        center_id,
        plan["review_id"],
        {"ga_readiness_report": failed_ga, "release_check_report": failed_release_check},
    )
    verification = verify_unified_command_center_continuous_review_package(
        zipped["zip_path"],
        strict=True,
        require_clear=True,
        require_current_review=True,
        ga_readiness_report_path=failed_ga,
        release_check_report_path=failed_release_check,
        archive_zip_path=signoff_store.archive_zip_path(center_id),
        archive_verification_report_path=signoff_store.archive_verification_report_path(center_id),
        handoff_zip_path=handoff_store.zip_path(center_id),
        handoff_verification_report_path=handoff_store.verification_report_path(center_id),
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
        signoff_binding_path=signoff_store.signoff_binding_path(center_id),
    )
    gate = review_store.gate(center_id, review_id=plan["review_id"])

    assert result["status"] == "failed"
    assert {row["component_type"] for row in result["drift_report"]["drifts"]} >= {"ga", "release_check"}
    assert verification["status"] == "failed"
    assert "ucc_review_require_clear" in verification["blockers"]
    assert "ucc_review_ga_status" in verification["blockers"]
    assert "ucc_review_release_check_status" in verification["blockers"]
    assert gate["status"] == "failed"


def test_continuous_review_blocks_failed_external_evidence_rows(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    plan = review_store.create_plan(
        center_id,
        {"external_evidence": [{"component": "distribution", "component_id": "target-001", "status": "passed"}]},
    )

    result = review_store.run_review(
        center_id,
        plan["review_id"],
        {"external_evidence": [{"component": "distribution", "component_id": "target-001", "status": "failed"}]},
    )
    zipped = review_store.build_zip(
        center_id,
        plan["review_id"],
        {"external_evidence": [{"component": "distribution", "component_id": "target-001", "status": "failed"}]},
    )
    verification = verify_unified_command_center_continuous_review_package(
        zipped["zip_path"],
        strict=True,
        require_clear=True,
        require_current_review=True,
        archive_zip_path=signoff_store.archive_zip_path(center_id),
        archive_verification_report_path=signoff_store.archive_verification_report_path(center_id),
        handoff_zip_path=handoff_store.zip_path(center_id),
        handoff_verification_report_path=handoff_store.verification_report_path(center_id),
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
        signoff_binding_path=signoff_store.signoff_binding_path(center_id),
    )

    assert result["status"] == "failed"
    assert "distribution" in {row["component_type"] for row in result["drift_report"]["drifts"]}
    assert verification["status"] == "failed"
    assert "ucc_review_external_evidence_status" in verification["blockers"]


def test_continuous_review_detects_archive_tamper_and_blocks_export(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    plan = review_store.create_plan(center_id, {})

    tampered_archive = tmp_path / "archive-extra.zip"
    _v76_rewrite_zip(signoff_store.archive_zip_path(center_id), tampered_archive, _add_declared_extra)
    result = review_store.run_review(center_id, plan["review_id"], {"archive_zip": tampered_archive})

    assert result["status"] == "failed"
    assert result["incident_board"]["summary"]["critical_count"] >= 1
    with pytest.raises(UnifiedCommandCenterContinuousReviewStateError):
        review_store.export_package(center_id, plan["review_id"])


def test_continuous_review_verifier_rejects_declared_extra(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    plan = review_store.create_plan(center_id, {})
    review_store.run_review(center_id, plan["review_id"])
    zipped = review_store.build_zip(center_id, plan["review_id"])
    tampered = tmp_path / "review-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), tampered, _add_declared_extra)

    result = verify_unified_command_center_continuous_review_package(
        tampered,
        strict=True,
        require_clear=True,
        require_recovery_drill=True,
        require_current_review=True,
        archive_zip_path=signoff_store.archive_zip_path(center_id),
        archive_verification_report_path=signoff_store.archive_verification_report_path(center_id),
        handoff_zip_path=handoff_store.zip_path(center_id),
        handoff_verification_report_path=handoff_store.verification_report_path(center_id),
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
        signoff_binding_path=signoff_store.signoff_binding_path(center_id),
    )

    assert result["status"] == "failed"
    assert "ucc_review_allowed_entries" in result["blockers"]


def test_continuous_review_full_resign_clear_fails_against_current_archive(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    plan = review_store.create_plan(center_id, {})
    tampered_archive = tmp_path / "archive-extra.zip"
    _v76_rewrite_zip(signoff_store.archive_zip_path(center_id), tampered_archive, _add_declared_extra)
    review_store.run_review(center_id, plan["review_id"], {"archive_zip": tampered_archive})
    zipped = review_store.build_zip(center_id, plan["review_id"], {"archive_zip": tampered_archive})
    forged = tmp_path / "review-forged-clear.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged, _forge_review_clear)

    result = verify_unified_command_center_continuous_review_package(
        forged,
        strict=True,
        require_clear=True,
        require_recovery_drill=True,
        require_current_review=True,
        archive_zip_path=tampered_archive,
        archive_verification_report_path=signoff_store.archive_verification_report_path(center_id),
        handoff_zip_path=handoff_store.zip_path(center_id),
        handoff_verification_report_path=handoff_store.verification_report_path(center_id),
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
        signoff_binding_path=signoff_store.signoff_binding_path(center_id),
    )

    assert result["status"] == "failed"
    assert "ucc_review_current_archive_status" in result["blockers"] or "ucc_review_current_archive_zip_binding" in result["blockers"]


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra] = b"unexpected\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra, "size_bytes": len(entries[extra]), "sha256": _sha256_bytes(entries[extra])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_review_clear(entries: dict[str, bytes]) -> dict[str, bytes]:
    drift = json.loads(entries["drift-report.json"].decode("utf-8"))
    drift["status"] = "passed"
    drift["drifts"] = []
    drift["summary"] = {"checked_count": 6, "drift_count": 0, "blocking_drift_count": 0, "warning_count": 0}
    drift["integrity_hash"] = stable_hash({key: value for key, value in drift.items() if key != "integrity_hash"})
    entries["drift-report.json"] = json.dumps(drift, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    board = json.loads(entries["incident-board.json"].decode("utf-8"))
    board["status"] = "clear"
    board["incidents"] = []
    board["summary"] = {"open_count": 0, "critical_count": 0, "change_request_draft_count": 0}
    board["integrity_hash"] = stable_hash({key: value for key, value in board.items() if key != "integrity_hash"})
    entries["incident-board.json"] = json.dumps(board, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    drill = json.loads(entries["recovery-drill-report.json"].decode("utf-8"))
    drill["status"] = "passed"
    for step in drill.get("steps", []):
        if isinstance(step, dict):
            step["status"] = "passed"
    drill["summary"] = {"step_count": len(drill.get("steps", [])), "failed_count": 0}
    drill["integrity_hash"] = stable_hash({key: value for key, value in drill.items() if key != "integrity_hash"})
    entries["recovery-drill-report.json"] = json.dumps(drill, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["status"] = "passed"
    manifest.setdefault("source", {})["drift_report_hash"] = drift["integrity_hash"]
    manifest.setdefault("source", {})["incident_board_hash"] = board["integrity_hash"]
    manifest.setdefault("source", {})["recovery_drill_hash"] = drill["integrity_hash"]
    _sync_manifest_file(manifest, "drift-report.json", entries["drift-report.json"])
    _sync_manifest_file(manifest, "incident-board.json", entries["incident-board.json"])
    _sync_manifest_file(manifest, "recovery-drill-report.json", entries["recovery-drill-report.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    for row in manifest.get("files", []):
        if isinstance(row, dict) and row.get("path") == rel:
            row["size_bytes"] = len(data)
            row["sha256"] = _sha256_bytes(data)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
