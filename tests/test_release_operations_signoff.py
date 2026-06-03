from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import write_json
from song_agent.release_operations import ReleaseOperationsStore
from song_agent.release_operations_archive_verifier import verify_release_operations_archive_package
from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
from song_agent.release_operations_signoff import (
    ReleaseOperationsSignoffStateError,
    ReleaseOperationsSignoffStore,
    operations_change_request_integrity_ok,
    operations_signoff_integrity_ok,
)
from song_agent.releases import ReleaseStore


def test_operations_signoff_requires_accepted_stage(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Signoff Draft", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_store.refresh(release.release_id)

    gate = store.gate(release.release_id, {})

    assert gate["status"] == "failed"
    assert gate["signable"] is False
    assert any(item["check_id"] == "operations_accepted_stage" for item in gate["blockers"])
    with pytest.raises(ReleaseOperationsSignoffStateError):
        store.signoff(release.release_id, {"signed_by": "tester"})
    with pytest.raises(ReleaseOperationsSignoffStateError):
        store.signoff(release.release_id, {"signed_by": "tester", "force": True, "override_reason": "force cannot bypass missing accepted stage"})


def test_operations_signoff_archive_export_verify_and_tamper(tmp_path: Path, monkeypatch) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Accepted", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    report = operations_store.refresh(release.release_id)
    report["current_stage"] = "accepted"
    report["next_stage"] = "archived"
    report["summary"]["blocker_count"] = 0
    report["summary"]["warning_count"] = 0
    report["blockers"] = []
    report["warnings"] = []
    report["domains"] = {"submission_evidence": {"required": False, "status": "not_required", "summary": {}}}
    report["verifier_summaries"] = {"release": {"status": "passed"}}
    report["package_summaries"] = {"release_zip": {"exists": True, "status": "exists", "sha256": "0" * 64}, "distribution_packages": [], "submission_packages": [], "submission_evidence_packages": []}
    report["source_hash"] = "accepted-source"
    report["source"] = {"fixture": "accepted"}
    from song_agent.release_operations import operations_report_integrity_hash

    report["integrity_hash"] = operations_report_integrity_hash(report)
    write_json(operations_store.report_path(release.release_id), report)
    monkeypatch.setattr(operations_store, "build_report", lambda release_id, persist=False, now=None: report)
    monkeypatch.setattr(operations_store, "refresh", lambda release_id, now=None: report)
    runbook = runbook_store.create_from_operations_report(release.release_id)
    runbook["status"] = "completed"
    runbook["items"] = []
    runbook["summary"] = {"total_count": 0, "safe_count": 0, "manual_count": 0, "completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0, "waived_count": 0, "pending_count": 0}
    from song_agent.release_operations_runbook import runbook_integrity_hash

    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    write_json(runbook_store.runbook_path(release.release_id, runbook["runbook_id"]), runbook)

    signed = store.signoff(release.release_id, {"signed_by": "tester"})
    manifest = store.export_archive(release.release_id)
    zip_info = store.build_archive_zip(release.release_id)
    verify = verify_release_operations_archive_package(store.archive_zip_path(release.release_id), require_signed=True)

    assert operations_signoff_integrity_ok(signed)
    assert signed["status"] == "signed"
    assert manifest["operations_signoff"]["payload_hash"] == signed["payload_hash"]
    assert zip_info["sha256"]
    assert verify["status"] == "passed"

    tampered_zip = tmp_path / "tampered-archive.zip"
    with zipfile.ZipFile(store.archive_zip_path(release.release_id), "r") as src, zipfile.ZipFile(tampered_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "operations-signoff.json":
                payload = json.loads(data.decode("utf-8"))
                payload["signed_by"] = "tampered"
                data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            dst.writestr(info.filename, data)

    tampered = verify_release_operations_archive_package(tampered_zip, require_signed=True)

    assert tampered["status"] == "failed"
    assert any(item["check_id"] == "operations_archive_signoff_payload_hash" for item in tampered["blockers"])


def test_operations_signoff_requires_force_for_warnings(tmp_path: Path, monkeypatch) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Warning", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    report = operations_store.refresh(release.release_id)
    report["current_stage"] = "accepted"
    report["next_stage"] = "archived"
    report["summary"]["blocker_count"] = 0
    report["summary"]["warning_count"] = 1
    report["blockers"] = []
    report["warnings"] = [{"warning_id": "wrn-001", "check_id": "minor_warning", "message": "Minor warning"}]
    report["domains"] = {"submission_evidence": {"required": False, "status": "not_required", "summary": {}}}
    report["verifier_summaries"] = {"release": {"status": "warning"}}
    report["package_summaries"] = {"release_zip": {"exists": True, "status": "exists", "sha256": "0" * 64}, "distribution_packages": [], "submission_packages": [], "submission_evidence_packages": []}
    report["source_hash"] = "warning-source"
    report["source"] = {"fixture": "warning"}
    from song_agent.release_operations import operations_report_integrity_hash

    report["integrity_hash"] = operations_report_integrity_hash(report)
    write_json(operations_store.report_path(release.release_id), report)
    monkeypatch.setattr(operations_store, "build_report", lambda release_id, persist=False, now=None: report)
    monkeypatch.setattr(operations_store, "refresh", lambda release_id, now=None: report)
    runbook = runbook_store.create_from_operations_report(release.release_id)
    runbook["status"] = "completed"
    runbook["items"] = []
    runbook["summary"] = {"total_count": 0, "safe_count": 0, "manual_count": 0, "completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0, "waived_count": 0, "pending_count": 0}
    from song_agent.release_operations_runbook import runbook_integrity_hash

    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    write_json(runbook_store.runbook_path(release.release_id, runbook["runbook_id"]), runbook)

    gate = store.gate(release.release_id, {})
    force_gate = store.gate(release.release_id, {"force": True, "override_reason": "accept known warning"})

    assert gate["signable"] is False
    assert force_gate["signable"] is True
    signed = store.signoff(release.release_id, {"signed_by": "tester", "force": True, "override_reason": "accept known warning"})
    assert signed["status"] == "force_signed"


def test_operations_change_request_lifecycle_and_integrity(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Change", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)

    change = store.create_change_request(release.release_id, {"reason": "Fix platform metadata typo", "scope": ["metadata", "release_export"], "created_by": "tester"})
    submitted = store.update_change_request_status(release.release_id, change["change_request_id"], "submit")
    approved = store.update_change_request_status(release.release_id, change["change_request_id"], "approve", {"approved_by": "reviewer", "notes": "approved"})

    assert submitted["status"] == "submitted"
    assert approved["status"] == "approved"
    assert operations_change_request_integrity_ok(approved)
    assert store.change_request_summary(release.release_id)["approved_count"] == 1


def test_operations_reset_requires_approved_change_request_and_marks_applied(tmp_path: Path, monkeypatch) -> None:
    release_store = ReleaseStore(tmp_path / "releases")
    release = release_store.create_release({"name": "Ops Reset", "release_type": "single_pack", "primary_artist": "MusicForge"})
    operations_store = ReleaseOperationsStore(release_store=release_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    report = operations_store.refresh(release.release_id)
    report["current_stage"] = "accepted"
    report["next_stage"] = "archived"
    report["summary"]["blocker_count"] = 0
    report["summary"]["warning_count"] = 0
    report["blockers"] = []
    report["warnings"] = []
    report["domains"] = {"submission_evidence": {"required": False, "status": "not_required", "summary": {}}}
    report["verifier_summaries"] = {"release": {"status": "passed"}}
    report["package_summaries"] = {"release_zip": {"exists": True, "status": "exists", "sha256": "0" * 64}, "distribution_packages": [], "submission_packages": [], "submission_evidence_packages": []}
    report["source_hash"] = "reset-source"
    report["source"] = {"fixture": "reset"}
    from song_agent.release_operations import operations_report_integrity_hash

    report["integrity_hash"] = operations_report_integrity_hash(report)
    write_json(operations_store.report_path(release.release_id), report)
    monkeypatch.setattr(operations_store, "build_report", lambda release_id, persist=False, now=None: report)
    monkeypatch.setattr(operations_store, "refresh", lambda release_id, now=None: report)
    runbook = runbook_store.create_from_operations_report(release.release_id)
    runbook["status"] = "completed"
    runbook["items"] = []
    runbook["summary"] = {"total_count": 0, "safe_count": 0, "manual_count": 0, "completed_count": 0, "failed_count": 0, "blocked_count": 0, "manual_required_count": 0, "waived_count": 0, "pending_count": 0}
    from song_agent.release_operations_runbook import runbook_integrity_hash

    runbook["integrity_hash"] = runbook_integrity_hash(runbook)
    write_json(runbook_store.runbook_path(release.release_id, runbook["runbook_id"]), runbook)
    store.signoff(release.release_id, {"signed_by": "tester"})

    with pytest.raises(ReleaseOperationsSignoffStateError, match="Change Request"):
        store.reset_signoff(release.release_id, {"reason": "Reset without change request"})

    draft = store.create_change_request(release.release_id, {"reason": "Draft reset request", "scope": ["operations"], "created_by": "tester"})
    submitted = store.create_change_request(release.release_id, {"reason": "Submitted reset request", "scope": ["operations"], "created_by": "tester"})
    submitted = store.update_change_request_status(release.release_id, submitted["change_request_id"], "submit")
    rejected = store.create_change_request(release.release_id, {"reason": "Rejected reset request", "scope": ["operations"], "created_by": "tester"})
    rejected = store.update_change_request_status(release.release_id, rejected["change_request_id"], "reject", {"reason": "Rejected by reviewer"})
    cancelled = store.create_change_request(release.release_id, {"reason": "Cancelled reset request", "scope": ["operations"], "created_by": "tester"})
    cancelled = store.update_change_request_status(release.release_id, cancelled["change_request_id"], "cancel")
    approved = store.create_change_request(release.release_id, {"reason": "Approved reset request", "scope": ["operations"], "created_by": "tester"})
    approved = store.update_change_request_status(release.release_id, approved["change_request_id"], "approve", {"approved_by": "reviewer"})

    for change in (draft, submitted, rejected, cancelled):
        with pytest.raises(ReleaseOperationsSignoffStateError, match="approved"):
            store.reset_signoff(release.release_id, {"reason": "Reset with invalid status", "change_request_id": change["change_request_id"]})

    tampered = {**approved, "reason": "tampered"}
    write_json(store.change_request_path(release.release_id, approved["change_request_id"]), tampered)
    with pytest.raises(ReleaseOperationsSignoffStateError, match="integrity"):
        store.reset_signoff(release.release_id, {"reason": "Reset with tampered request", "change_request_id": approved["change_request_id"]})
    write_json(store.change_request_path(release.release_id, approved["change_request_id"]), approved)

    reset = store.reset_signoff(release.release_id, {"reason": "Reset with approved request", "change_request_id": approved["change_request_id"]})
    applied = store.get_change_request(release.release_id, approved["change_request_id"])

    assert reset["status"] == "reset"
    assert reset["change_request_id"] == approved["change_request_id"]
    assert applied["status"] == "applied"
    assert applied["applied_signoff_reset_hash"] == reset["payload_hash"]
    assert operations_change_request_integrity_ok(applied)
    with pytest.raises(ReleaseOperationsSignoffStateError, match="approved"):
        store.reset_signoff(release.release_id, {"reason": "Reuse same request blocked", "change_request_id": approved["change_request_id"]})
