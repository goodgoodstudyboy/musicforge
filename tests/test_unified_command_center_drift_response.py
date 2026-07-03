from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore
from song_agent.unified_command_center_drift_response import UnifiedCommandCenterDriftResponseStateError, UnifiedCommandCenterDriftResponseStore
from song_agent.unified_command_center_drift_response_verifier import verify_unified_command_center_drift_response_package
from tests.test_unified_command_center_continuous_review import _ready_signed_ucc


def test_unified_command_center_drift_response_lifecycle(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    response_store = UnifiedCommandCenterDriftResponseStore(store, signoff_store=signoff_store, handoff_store=handoff_store, review_store=review_store)

    failed_plan = review_store.create_plan(center_id, {"review_id": "uccrv-failed", "external_evidence": [{"component": "distribution", "component_id": "target-001", "status": "passed"}]})
    failed_review = review_store.run_review(center_id, failed_plan["review_id"], {"external_evidence": [{"component": "distribution", "component_id": "target-001", "status": "failed"}]})
    failed_zip = review_store.build_zip(center_id, failed_plan["review_id"], {"external_evidence": [{"component": "distribution", "component_id": "target-001", "status": "failed"}]})
    failed_verification = review_store.verify_package(center_id, failed_plan["review_id"])
    assert failed_review["status"] == "failed"
    assert failed_verification["status"] == "failed"

    created = response_store.create_response(center_id, {"source_review_id": failed_plan["review_id"], "created_by": "qa"})
    response_id = created["case"]["response_id"]
    response_store.run_safe(center_id, response_id)
    with pytest.raises(UnifiedCommandCenterDriftResponseStateError):
        response_store.closeout(center_id, response_id, {"closed_by": "qa"})

    for index, manual_item in enumerate([row for row in created["queue"]["items"] if not row.get("safe")], start=1):
        response_store.bind_change_request(center_id, response_id, {"item_id": manual_item["item_id"], "change_request_id": f"cr-{index:03d}", "status": "approved", "approved_by": "reviewer"})
    clear_plan = review_store.create_plan(center_id, {"review_id": "uccrv-clear"})
    clear_review = review_store.run_review(center_id, clear_plan["review_id"])
    clear_zip = review_store.build_zip(center_id, clear_plan["review_id"])
    clear_verification = review_store.verify_package(center_id, clear_plan["review_id"])
    assert clear_review["status"] == "passed"
    assert clear_verification["status"] == "passed"

    recheck = response_store.bind_recheck(center_id, response_id, {"recheck_review_id": clear_plan["review_id"]})
    closeout = response_store.closeout(center_id, response_id, {"closed_by": "qa", "reason": "clear"})
    zipped = response_store.build_zip(center_id, response_id)
    verification = response_store.verify_package(center_id, response_id)
    gate = response_store.gate(center_id, response_id=response_id)

    assert recheck["status"] == "passed"
    assert closeout["status"] == "closed", closeout.get("blockers")
    assert Path(zipped["zip_path"]).exists()
    assert verification["status"] == "passed", verification.get("blockers")
    assert gate["status"] == "passed"

    standalone = verify_unified_command_center_drift_response_package(
        zipped["zip_path"],
        strict=True,
        require_closed=True,
        require_recheck_clear=True,
        require_current_review=True,
        source_review_zip_path=failed_zip["zip_path"],
        source_review_verification_report_path=review_store.verification_report_path(center_id, failed_plan["review_id"]),
        recheck_review_zip_path=clear_zip["zip_path"],
        recheck_review_verification_report_path=review_store.verification_report_path(center_id, clear_plan["review_id"]),
        archive_zip_path=signoff_store.archive_zip_path(center_id),
        archive_verification_report_path=signoff_store.archive_verification_report_path(center_id),
        handoff_zip_path=handoff_store.zip_path(center_id),
        handoff_verification_report_path=handoff_store.verification_report_path(center_id),
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
        signoff_binding_path=signoff_store.signoff_binding_path(center_id),
        change_request_binding_report_path=response_store.cr_binding_report_path(center_id, response_id),
    )
    assert standalone["status"] == "passed", standalone.get("blockers")


def test_drift_response_verifier_rejects_declared_extra_and_full_resign(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    response_store = UnifiedCommandCenterDriftResponseStore(store, signoff_store=signoff_store, handoff_store=handoff_store, review_store=review_store)

    failed_plan = review_store.create_plan(center_id, {"review_id": "uccrv-failed", "external_evidence": [{"component": "distribution", "status": "passed"}]})
    review_store.run_review(center_id, failed_plan["review_id"], {"external_evidence": [{"component": "distribution", "status": "failed"}]})
    failed_zip = review_store.build_zip(center_id, failed_plan["review_id"], {"external_evidence": [{"component": "distribution", "status": "failed"}]})
    review_store.verify_package(center_id, failed_plan["review_id"])
    response_id = response_store.create_response(center_id, {"source_review_id": failed_plan["review_id"]})["case"]["response_id"]
    response_store.run_safe(center_id, response_id)
    for index, manual_item in enumerate([row for row in read_json(response_store.queue_path(center_id, response_id))["items"] if not row.get("safe")], start=1):
        response_store.bind_change_request(center_id, response_id, {"item_id": manual_item["item_id"], "change_request_id": f"cr-{index:03d}", "status": "approved"})
    clear_plan = review_store.create_plan(center_id, {"review_id": "uccrv-clear"})
    review_store.run_review(center_id, clear_plan["review_id"])
    clear_zip = review_store.build_zip(center_id, clear_plan["review_id"])
    review_store.verify_package(center_id, clear_plan["review_id"])
    response_store.bind_recheck(center_id, response_id, {"recheck_review_id": clear_plan["review_id"]})
    response_store.closeout(center_id, response_id, {"closed_by": "qa"})
    zipped = response_store.build_zip(center_id, response_id)

    extra_zip = tmp_path / "response-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_command_center_drift_response_package(extra_zip, strict=True, require_closed=True)
    assert extra["status"] == "failed"
    assert "ucc_drift_response_allowed_entries" in extra["blockers"]

    forged_zip = tmp_path / "response-forged.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _forge_closed_without_recheck)
    forged = verify_unified_command_center_drift_response_package(
        forged_zip,
        strict=True,
        require_closed=True,
        require_recheck_clear=True,
        require_current_review=True,
        source_review_zip_path=failed_zip["zip_path"],
        source_review_verification_report_path=review_store.verification_report_path(center_id, failed_plan["review_id"]),
        recheck_review_zip_path=clear_zip["zip_path"],
        recheck_review_verification_report_path=review_store.verification_report_path(center_id, clear_plan["review_id"]),
        archive_zip_path=signoff_store.archive_zip_path(center_id),
        archive_verification_report_path=signoff_store.archive_verification_report_path(center_id),
        handoff_zip_path=handoff_store.zip_path(center_id),
        handoff_verification_report_path=handoff_store.verification_report_path(center_id),
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
        signoff_binding_path=signoff_store.signoff_binding_path(center_id),
        change_request_binding_report_path=response_store.cr_binding_report_path(center_id, response_id),
    )
    assert forged["status"] == "failed"
    assert "ucc_drift_response_require_recheck_clear" in forged["blockers"]


def test_drift_response_verifier_requires_external_cr_proof(tmp_path: Path) -> None:
    store, signoff_store, handoff_store, center_id = _ready_signed_ucc(tmp_path)
    review_store = UnifiedCommandCenterContinuousReviewStore(store, signoff_store=signoff_store, handoff_store=handoff_store)
    response_store = UnifiedCommandCenterDriftResponseStore(store, signoff_store=signoff_store, handoff_store=handoff_store, review_store=review_store)

    failed_plan = review_store.create_plan(
        center_id,
        {
            "review_id": "uccrv-failed",
            "external_evidence": [
                {"component": "distribution", "component_id": "target-001", "status": "passed"},
                {"component": "distribution", "component_id": "target-002", "status": "passed"},
            ],
        },
    )
    review_store.run_review(
        center_id,
        failed_plan["review_id"],
        {
            "external_evidence": [
                {"component": "distribution", "component_id": "target-001", "status": "failed"},
                {"component": "distribution", "component_id": "target-002", "status": "failed"},
            ],
        },
    )
    failed_zip = review_store.build_zip(
        center_id,
        failed_plan["review_id"],
        {
            "external_evidence": [
                {"component": "distribution", "component_id": "target-001", "status": "failed"},
                {"component": "distribution", "component_id": "target-002", "status": "failed"},
            ],
        },
    )
    review_store.verify_package(center_id, failed_plan["review_id"])
    response_id = response_store.create_response(center_id, {"source_review_id": failed_plan["review_id"]})["case"]["response_id"]
    response_store.run_safe(center_id, response_id)
    manual_items = [row for row in read_json(response_store.queue_path(center_id, response_id))["items"] if not row.get("safe")]
    for index, manual_item in enumerate(manual_items, start=1):
        response_store.bind_change_request(center_id, response_id, {"item_id": manual_item["item_id"], "change_request_id": f"cr-{index:03d}", "status": "approved"})
    clear_plan = review_store.create_plan(center_id, {"review_id": "uccrv-clear"})
    review_store.run_review(center_id, clear_plan["review_id"])
    clear_zip = review_store.build_zip(center_id, clear_plan["review_id"])
    review_store.verify_package(center_id, clear_plan["review_id"])
    response_store.bind_recheck(center_id, response_id, {"recheck_review_id": clear_plan["review_id"]})
    response_store.closeout(center_id, response_id, {"closed_by": "qa"})
    zipped = response_store.build_zip(center_id, response_id)

    common = {
        "strict": True,
        "require_closed": True,
        "require_recheck_clear": True,
        "require_current_review": True,
        "source_review_zip_path": failed_zip["zip_path"],
        "source_review_verification_report_path": review_store.verification_report_path(center_id, failed_plan["review_id"]),
        "recheck_review_zip_path": clear_zip["zip_path"],
        "recheck_review_verification_report_path": review_store.verification_report_path(center_id, clear_plan["review_id"]),
        "archive_zip_path": signoff_store.archive_zip_path(center_id),
        "archive_verification_report_path": signoff_store.archive_verification_report_path(center_id),
        "handoff_zip_path": handoff_store.zip_path(center_id),
        "handoff_verification_report_path": handoff_store.verification_report_path(center_id),
        "command_center_zip_path": store.zip_path(center_id),
        "command_center_verification_report_path": store.verification_report_path(center_id),
        "signoff_binding_path": signoff_store.signoff_binding_path(center_id),
    }
    missing = verify_unified_command_center_drift_response_package(zipped["zip_path"], **common)
    assert missing["status"] == "failed"
    assert "ucc_drift_response_cr_proof_required" in missing["blockers"]

    forged_zip = tmp_path / "forged-cr.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _forge_cr_binding)
    forged = verify_unified_command_center_drift_response_package(forged_zip, change_request_binding_report_path=response_store.cr_binding_report_path(center_id, response_id), **common)
    assert forged["status"] == "failed"
    assert "ucc_drift_response_cr_proof_bindings_binding" in forged["blockers"]

    wrong_report = tmp_path / "wrong-cr-report.json"
    _write_modified_cr_report(response_store.cr_binding_report_path(center_id, response_id), wrong_report, "wrong_item")
    wrong = verify_unified_command_center_drift_response_package(zipped["zip_path"], change_request_binding_report_path=wrong_report, **common)
    assert wrong["status"] == "failed"
    assert "ucc_drift_response_cr_proof_item_coverage" in wrong["blockers"]

    reused_report = tmp_path / "reused-cr-report.json"
    _write_modified_cr_report(response_store.cr_binding_report_path(center_id, response_id), reused_report, "reused_cr")
    reused = verify_unified_command_center_drift_response_package(zipped["zip_path"], change_request_binding_report_path=reused_report, **common)
    assert reused["status"] == "failed"
    assert "ucc_drift_response_cr_proof_unique_change_requests" in reused["blockers"]


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra] = b"unexpected\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"entry": extra, "size_bytes": len(entries[extra]), "sha256": _sha256_bytes(entries[extra])})
    manifest["files"] = sorted(files, key=lambda row: row.get("entry") or row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_closed_without_recheck(entries: dict[str, bytes]) -> dict[str, bytes]:
    recheck = json.loads(entries["recheck-summary.json"].decode("utf-8"))
    recheck["status"] = "missing"
    recheck["review"] = {}
    recheck["summary"] = {"recheck_bound": False, "status": "missing"}
    recheck["integrity_hash"] = stable_hash({key: value for key, value in recheck.items() if key != "integrity_hash"})
    entries["recheck-summary.json"] = json.dumps(recheck, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    closeout = json.loads(entries["closeout-report.json"].decode("utf-8"))
    closeout["status"] = "closed"
    closeout["recheck_status"] = "passed"
    closeout["blockers"] = []
    closeout["summary"]["blocker_count"] = 0
    closeout.setdefault("bindings", {})["recheck_summary_hash"] = recheck["integrity_hash"]
    closeout["integrity_hash"] = stable_hash({key: value for key, value in closeout.items() if key != "integrity_hash"})
    entries["closeout-report.json"] = json.dumps(closeout, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["recheck_summary_hash"] = recheck["integrity_hash"]
    manifest.setdefault("source", {})["closeout_report_hash"] = closeout["integrity_hash"]
    _sync_manifest_file(manifest, "recheck-summary.json", entries["recheck-summary.json"])
    _sync_manifest_file(manifest, "closeout-report.json", entries["closeout-report.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    for row in manifest.get("files", []):
        if isinstance(row, dict) and (row.get("entry") == rel or row.get("path") == rel):
            row["size_bytes"] = len(data)
            row["sha256"] = _sha256_bytes(data)


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _forge_cr_binding(entries: dict[str, bytes]) -> dict[str, bytes]:
    cr_bindings = json.loads(entries["change-request-bindings.json"].decode("utf-8"))
    cr_bindings["items"][0]["change_request_id"] = "cr-forged"
    cr_bindings["items"][0]["approved_by"] = "forged-reviewer"
    cr_bindings["items"][0]["approval_hash"] = stable_hash(
        {
            "change_request_id": cr_bindings["items"][0].get("change_request_id"),
            "status": cr_bindings["items"][0].get("status"),
            "approved_by": cr_bindings["items"][0].get("approved_by"),
            "approved_at": cr_bindings["items"][0].get("approved_at"),
            "reason": cr_bindings["items"][0].get("reason"),
            "evidence_hash": cr_bindings["items"][0].get("evidence_hash"),
        }
    )
    cr_bindings["items"][0]["binding_hash"] = stable_hash({key: value for key, value in cr_bindings["items"][0].items() if key != "binding_hash"})
    cr_bindings["integrity_hash"] = stable_hash({key: value for key, value in cr_bindings.items() if key != "integrity_hash"})
    entries["change-request-bindings.json"] = json.dumps(cr_bindings, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    closeout = json.loads(entries["closeout-report.json"].decode("utf-8"))
    closeout.setdefault("bindings", {})["change_request_bindings_hash"] = cr_bindings["integrity_hash"]
    closeout["integrity_hash"] = stable_hash({key: value for key, value in closeout.items() if key != "integrity_hash"})
    entries["closeout-report.json"] = json.dumps(closeout, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["change_request_bindings_hash"] = cr_bindings["integrity_hash"]
    manifest.setdefault("source", {})["closeout_report_hash"] = closeout["integrity_hash"]
    _sync_manifest_file(manifest, "change-request-bindings.json", entries["change-request-bindings.json"])
    _sync_manifest_file(manifest, "closeout-report.json", entries["closeout-report.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _write_modified_cr_report(source: Path, target: Path, mode: str) -> None:
    report = read_json(source)
    items = [row for row in report.get("items", []) if isinstance(row, dict)]
    if mode == "wrong_item":
        items[0]["item_id"] = "item-wrong"
    if mode == "reused_cr":
        reused = str(items[0].get("change_request_id") or "cr-reused")
        for row in items:
            row["change_request_id"] = reused
    for row in items:
        row["proof_hash"] = stable_hash({key: value for key, value in row.items() if key != "proof_hash"})
    report["items"] = items
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
