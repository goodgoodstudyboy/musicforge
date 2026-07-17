from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from song_agent.trust_operations_hub import TrustOperationsHubStore
from song_agent.trust_operations_hub_incident_verifier import verify_trust_operations_hub_incident_package
from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStateError, TrustOperationsIncidentStore, incident_hash, incident_manifest_hash
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from tests.test_trust_operations_hub import _copy_delivery_report, _delivery_fixture, _fixture


def test_trust_operations_incident_closeout_and_hub_gate(tmp_path: Path) -> None:
    hub_store, incident_store, fixture, delivery, second_distribution, report_id = _incident_fixture(tmp_path)
    board = incident_store.refresh_board("hub")["incident_board"]
    incidents = incident_store.list_incidents("hub")
    incident = next(item for item in incidents if item["detected_from"]["component_type"] == "distribution_verification")

    assert len(incidents) == 1
    incident_store.triage_incident("hub", incident["incident_id"], {"severity": "high", "owner": "ops", "notes": "Need second target verification."})
    plan = incident_store.create_plan("hub", incident["incident_id"])
    evidence = incident_store.add_evidence("hub", incident["incident_id"], {"component_type": "distribution_verification", "component_id": incident["detected_from"]["component_id"], "report": read_json(second_distribution)})
    fix = incident_store.verify_fix("hub", incident["incident_id"])
    closeout = incident_store.close_incident("hub", incident["incident_id"], {"closed_by": "ops", "reason": "Second distribution target verification passed."})
    manifest = incident_store.export_board("hub")
    zip_info = incident_store.build_zip("hub")
    verification = incident_store.verify_zip("hub", {"strict": True, "require_no_open_blocking": True, "require_current_hub": True, "hub_verification_report_path": hub_store.verification_report_path("hub", report_id)})
    hub_gate_missing = verify_trust_operations_hub_package(hub_store.zip_path("hub", report_id), strict=True, require_incident_closeout=True, **fixture.verify_kwargs(), **delivery.verify_kwargs())
    delivery_verify_kwargs = delivery.verify_kwargs()
    delivery_verify_kwargs["distribution_verification_paths"] = [delivery.verify_payload["distribution_verification_path"], second_distribution]
    delivery_verify_kwargs.pop("distribution_verification_path", None)
    hub_gate = verify_trust_operations_hub_package(
        hub_store.zip_path("hub", report_id),
        strict=True,
        require_incident_closeout=True,
        incident_board_package_path=incident_store.zip_path("hub"),
        incident_board_verification_report_path=incident_store.verification_report_path("hub"),
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
        **fixture.verify_kwargs(),
        **delivery_verify_kwargs,
    )

    assert board["summary"]["blocking_open_count"] >= 1
    assert plan["steps"]
    assert evidence["status"] == "passed"
    assert fix["status"] == "passed"
    assert closeout["status"] == "passed"
    assert manifest["package_type"] == "musicforge_trust_operations_hub_incident_manifest"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert _has_blocker(hub_gate_missing, "toh_incident_board_package_required")
    assert hub_gate["status"] == "passed", hub_gate.get("blockers")


def test_trust_operations_incident_verifier_rejects_tamper_and_zip_edges(tmp_path: Path) -> None:
    hub_store, incident_store, _fixture_obj, _delivery, second_distribution, report_id = _incident_fixture(tmp_path)
    incident = incident_store.list_incidents("hub")[0]
    incident_store.add_evidence("hub", incident["incident_id"], {"component_id": incident["detected_from"]["component_id"], "component_type": incident["detected_from"]["component_type"], "report": read_json(second_distribution)})
    incident_store.close_incident("hub", incident["incident_id"], {"reason": "External verification evidence is current.", "closed_by": "qa"})
    incident_store.export_board("hub")
    incident_store.build_zip("hub")
    source_zip = incident_store.zip_path("hub")

    open_full_resign = verify_trust_operations_hub_incident_package(_rewrite_zip(source_zip, tmp_path / "open.zip", _tamper_closed_to_open_full_resign), strict=True, require_no_open_blocking=True, hub_verification_report_path=hub_store.verification_report_path("hub", report_id), require_current_hub=True)
    extra = verify_trust_operations_hub_incident_package(_rewrite_zip(source_zip, tmp_path / "extra.zip", lambda docs: docs.update({"docs/extra.txt": b"x"})), strict=True)
    backslash = verify_trust_operations_hub_incident_package(_backslash_zip(tmp_path / "backslash.zip"), strict=True)
    duplicate = verify_trust_operations_hub_incident_package(_duplicate_zip(source_zip, tmp_path / "duplicate.zip"), strict=True)
    redaction = verify_trust_operations_hub_incident_package(_rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n")), strict=True)
    missing_external = verify_trust_operations_hub_incident_package(source_zip, strict=True, require_current_hub=True)

    assert _has_blocker(open_full_resign, "tohi_incident_status_matches_events")
    assert _has_blocker(extra, "tohi_zip_no_extra_entries")
    assert _has_blocker(backslash, "tohi_zip_entry_path_safe")
    assert _has_blocker(duplicate, "tohi_zip_no_duplicate_entries")
    assert _has_blocker(redaction, "tohi_redaction_scan")
    assert _has_blocker(missing_external, "tohi_hub_verification_required")


def test_trust_operations_incident_refuses_source_path_evidence(tmp_path: Path) -> None:
    _hub_store, incident_store, _fixture_obj, _delivery, _second_distribution, _report_id = _incident_fixture(tmp_path)
    incident = incident_store.list_incidents("hub")[0]
    with pytest.raises(TrustOperationsIncidentStateError):
        incident_store.add_evidence("hub", incident["incident_id"], {"source_path": str(tmp_path / "report.json"), "report": {"status": "passed"}})


def test_trust_operations_incident_rejects_forged_passed_evidence(tmp_path: Path) -> None:
    _hub_store, incident_store, _fixture_obj, _delivery, _second_distribution, _report_id = _incident_fixture(tmp_path)
    incident = incident_store.list_incidents("hub")[0]
    forged = {
        "package_type": "not_a_real_verification_package",
        "status": "passed",
        "zip_sha256": "0" * 64,
        "zip_size_bytes": 123,
        "manifest_hash": "1" * 64,
        "source_hash": "2" * 64,
        "summary": {"target_id": "target-002"},
    }

    with pytest.raises(TrustOperationsIncidentStateError):
        incident_store.add_evidence(
            "hub",
            incident["incident_id"],
            {
                "component_type": incident["detected_from"]["component_type"],
                "component_id": incident["detected_from"]["component_id"],
                "report": forged,
            },
        )

    fix = incident_store.verify_fix("hub", incident["incident_id"])
    assert fix["status"] == "failed"


def test_trust_operations_incident_verifier_rejects_forged_evidence_binding(tmp_path: Path) -> None:
    hub_store, incident_store, _fixture_obj, _delivery, second_distribution, report_id = _incident_fixture(tmp_path)
    incident = incident_store.list_incidents("hub")[0]
    incident_store.add_evidence("hub", incident["incident_id"], {"component_id": incident["detected_from"]["component_id"], "component_type": incident["detected_from"]["component_type"], "report": read_json(second_distribution)})
    incident_store.close_incident("hub", incident["incident_id"], {"reason": "External verification evidence is current.", "closed_by": "qa"})
    incident_store.export_board("hub")
    incident_store.build_zip("hub")

    forged = verify_trust_operations_hub_incident_package(
        _rewrite_zip(incident_store.zip_path("hub"), tmp_path / "forged-evidence.zip", _tamper_evidence_binding_full_resign),
        strict=True,
        require_no_open_blocking=True,
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
        require_current_hub=True,
    )

    assert _has_blocker(forged, "tohi_evidence_binding_integrity")


def _incident_fixture(tmp_path: Path):
    fixture = _fixture(tmp_path)
    delivery = _delivery_fixture(tmp_path)
    second_distribution = _copy_delivery_report(delivery.verify_payload["distribution_verification_path"], tmp_path / "target-002-verification.json", "target-002", "8" * 64)
    hub_store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub_store.create_hub({"hub_id": "hub"})
    payload = {
        **fixture.payload,
        **delivery.payload,
        "distribution_verification_paths": [delivery.verify_payload["distribution_verification_path"], second_distribution],
    }
    report_id = hub_store.refresh_report("hub", payload)["hub_report"]["report_id"]
    hub_store.export_report("hub", report_id)
    hub_store.build_zip("hub", report_id)
    # Generate a failed Hub verification that creates a verifier blocker for the missing second target.
    hub_store.verify_zip("hub", report_id, {**fixture.verify_payload, **delivery.verify_payload, "strict": True, "require_delivery_ready": True})
    incident_store = TrustOperationsIncidentStore(tmp_path / ".musicforge" / "trust-operations-incidents", hub_store=hub_store)
    incident_store.refresh_board("hub")
    return hub_store, incident_store, fixture, delivery, second_distribution, report_id


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item.get("check_id", "") for item in report.get("blockers", []))


def _rewrite_zip(source_zip: Path, target_zip: Path, mutate) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
    mutate(docs)
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name, data in docs.items():
            dst.writestr(name, data)
    return target_zip


def _duplicate_zip(source_zip: Path, target_zip: Path) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src, zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("incident-board.json", src.read("incident-board.json"))
    return target_zip


def _backslash_zip(target_zip: Path) -> Path:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    target_zip.write_bytes(target_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt"))
    return target_zip


def _tamper_closed_to_open_full_resign(docs: dict[str, bytes]) -> None:
    board = _read_doc(docs, "incident-board.json")
    report = _read_doc(docs, "incident-board-report.json")
    incidents_doc = _read_doc(docs, "incidents.json")
    manifest = _read_doc(docs, "trust-operations-incident-manifest.json")
    for incident in incidents_doc.get("incidents", []):
        if isinstance(incident, dict):
            incident["status"] = "open"
            incident["blocking"] = True
            incident["integrity_hash"] = incident_hash(incident)
            break
    board["summary"]["open_count"] = 1
    board["summary"]["blocking_open_count"] = 1
    board["summary"]["ready_for_hub_signoff"] = False
    board["status"] = "open"
    board["integrity_hash"] = incident_hash(board)
    report["summary"] = dict(board["summary"])
    report["status"] = "blocked"
    report.setdefault("source", {})["board_hash"] = board["integrity_hash"]
    incidents_doc["integrity_hash"] = incident_hash(incidents_doc)
    report["integrity_hash"] = incident_hash(report)
    docs["incident-board.json"] = _doc_bytes(board)
    docs["incident-board-report.json"] = _doc_bytes(report)
    docs["incidents.json"] = _doc_bytes(incidents_doc)
    for path in ("incident-board.json", "incident-board-report.json", "incidents.json"):
        _sync_manifest_file(manifest, path, docs[path])
    manifest["integrity"]["board_hash"] = board["integrity_hash"]
    manifest["integrity"]["report_hash"] = report["integrity_hash"]
    manifest["integrity_hash"] = incident_manifest_hash(manifest)
    docs["trust-operations-incident-manifest.json"] = _doc_bytes(manifest)


def _tamper_evidence_binding_full_resign(docs: dict[str, bytes]) -> None:
    evidence = _read_doc(docs, "evidence-index.json")
    closeouts = _read_doc(docs, "closeout-summary.json")
    manifest = _read_doc(docs, "trust-operations-incident-manifest.json")
    for row in evidence.get("evidence", []):
        if isinstance(row, dict):
            row["package_type"] = "not_a_real_verification_package"
            row["expected_package_type"] = "not_a_real_verification_package"
            row["verification_report_hash"] = "9" * 64
            row["expected_verification_report_hash"] = "9" * 64
            for check in row.get("binding_checks", []):
                if isinstance(check, dict):
                    check["status"] = "passed"
                    check["actual"] = check.get("expected")
            break
    evidence["summary"] = {"evidence_count": len(evidence.get("evidence", [])), "passed_count": 1, "failed_count": 0, "invalid_count": 0}
    evidence["integrity_hash"] = incident_hash(evidence)
    for closeout in closeouts.get("closeouts", []):
        if isinstance(closeout, dict):
            closeout.setdefault("source", {})["evidence_index_hash"] = evidence["integrity_hash"]
            closeout["integrity_hash"] = incident_hash(closeout)
    closeouts["integrity_hash"] = incident_hash(closeouts)
    docs["evidence-index.json"] = _doc_bytes(evidence)
    docs["closeout-summary.json"] = _doc_bytes(closeouts)
    _sync_manifest_file(manifest, "evidence-index.json", docs["evidence-index.json"])
    _sync_manifest_file(manifest, "closeout-summary.json", docs["closeout-summary.json"])
    manifest["integrity"]["evidence_index_hash"] = evidence["integrity_hash"]
    manifest["integrity"]["closeout_summary_hash"] = closeouts["integrity_hash"]
    manifest["integrity_hash"] = incident_manifest_hash(manifest)
    docs["trust-operations-incident-manifest.json"] = _doc_bytes(manifest)


def _sync_manifest_file(manifest: dict, path: str, data: bytes) -> None:
    for item in manifest.get("files", []) if isinstance(manifest.get("files"), list) else []:
        if isinstance(item, dict) and item.get("path") == path:
            item["size_bytes"] = len(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()


def _read_doc(docs: dict[str, bytes], path: str) -> dict:
    return json.loads(docs[path].decode("utf-8"))


def _doc_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
