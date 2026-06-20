from __future__ import annotations

import json
import zipfile
from pathlib import Path

from song_agent.projectio import read_json
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore, knowledge_hash, knowledge_manifest_hash
from song_agent.trust_operations_incident_knowledge_verifier import verify_trust_operations_incident_knowledge_package
from tests.test_trust_operations_hub_incidents import _has_blocker, _incident_fixture


def test_trust_operations_incident_knowledge_guard_lifecycle_and_hub_gate(tmp_path: Path) -> None:
    hub_store, incident_store, fixture, delivery, second_distribution, report_id = _closed_incident_fixture(tmp_path)
    store = TrustOperationsIncidentKnowledgeStore(tmp_path / ".musicforge" / "trust-operations-knowledge", hub_store=hub_store, incident_store=incident_store)

    refreshed = store.refresh("hub")
    entry = refreshed["entries"][0]
    guard = store.create_guard("hub", entry["entry_id"])
    run = store.run_guard("hub", guard["guard_id"])
    recurrence = store.refresh_recurrence("hub")
    manifest = store.export_knowledge("hub")
    zip_info = store.build_zip("hub")
    verification = store.verify_zip(
        "hub",
        {
            "strict": True,
            "require_guards_passed": True,
            "require_no_open_recurrence": True,
            "incident_board_verification_report_path": incident_store.verification_report_path("hub"),
            "hub_verification_report_path": hub_store.verification_report_path("hub", report_id),
        },
    )
    delivery_verify_kwargs = delivery.verify_kwargs()
    delivery_verify_kwargs["distribution_verification_paths"] = [delivery.verify_payload["distribution_verification_path"], second_distribution]
    delivery_verify_kwargs.pop("distribution_verification_path", None)
    hub_missing = verify_trust_operations_hub_package(
        hub_store.zip_path("hub", report_id),
        strict=True,
        require_incident_closeout=True,
        require_incident_regression_guards=True,
        incident_board_package_path=incident_store.zip_path("hub"),
        incident_board_verification_report_path=incident_store.verification_report_path("hub"),
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
        **fixture.verify_kwargs(),
        **delivery_verify_kwargs,
    )
    hub_gate = verify_trust_operations_hub_package(
        hub_store.zip_path("hub", report_id),
        strict=True,
        require_incident_closeout=True,
        require_incident_regression_guards=True,
        incident_board_package_path=incident_store.zip_path("hub"),
        incident_board_verification_report_path=incident_store.verification_report_path("hub"),
        incident_knowledge_package_path=store.zip_path("hub"),
        incident_knowledge_verification_report_path=store.verification_report_path("hub"),
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
        **fixture.verify_kwargs(),
        **delivery_verify_kwargs,
    )

    assert refreshed["knowledge_base"]["summary"]["entry_count"] == 1
    assert guard["guard_type"] == "external_report_coverage"
    assert run["status"] == "passed", run
    assert recurrence["status"] == "passed"
    assert manifest["package_type"] == "musicforge_trust_operations_incident_knowledge_manifest"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert _has_blocker(hub_missing, "toh_incident_knowledge_package_required")
    assert hub_gate["status"] == "passed", hub_gate.get("blockers")


def test_trust_operations_incident_knowledge_verifier_rejects_guard_removal_full_resign(tmp_path: Path) -> None:
    hub_store, incident_store, _fixture, _delivery, _second_distribution, report_id = _closed_incident_fixture(tmp_path)
    store = TrustOperationsIncidentKnowledgeStore(tmp_path / ".musicforge" / "trust-operations-knowledge", hub_store=hub_store, incident_store=incident_store)
    refreshed = store.refresh("hub")
    guard = store.create_guard("hub", refreshed["entries"][0]["entry_id"])
    store.run_guard("hub", guard["guard_id"])
    store.refresh_recurrence("hub")
    store.export_knowledge("hub")
    store.build_zip("hub")

    forged = verify_trust_operations_incident_knowledge_package(
        _rewrite_zip(store.zip_path("hub"), tmp_path / "knowledge-no-guard.zip", _remove_guard_full_resign),
        strict=True,
        require_guards_passed=True,
        require_no_open_recurrence=True,
        incident_board_verification_report_path=incident_store.verification_report_path("hub"),
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
    )
    extra = verify_trust_operations_incident_knowledge_package(_rewrite_zip(store.zip_path("hub"), tmp_path / "knowledge-extra.zip", lambda docs: docs.update({"docs/extra.txt": b"x"})), strict=True)

    assert _has_blocker(forged, "tohk_guards_cover_high_severity_entries")
    assert _has_blocker(extra, "tohk_zip_allowed_entries")


def _closed_incident_fixture(tmp_path: Path):
    hub_store, incident_store, fixture, delivery, second_distribution, report_id = _incident_fixture(tmp_path)
    incident = incident_store.list_incidents("hub")[0]
    incident_store.add_evidence(
        "hub",
        incident["incident_id"],
        {
            "component_id": incident["detected_from"]["component_id"],
            "component_type": incident["detected_from"]["component_type"],
            "report": read_json(second_distribution),
        },
    )
    incident_store.close_incident("hub", incident["incident_id"], {"reason": "Second distribution target verification passed.", "closed_by": "qa"})
    incident_store.export_board("hub")
    incident_store.build_zip("hub")
    incident_store.verify_zip("hub", {"strict": True, "require_no_open_blocking": True, "require_current_hub": True, "hub_verification_report_path": hub_store.verification_report_path("hub", report_id)})
    return hub_store, incident_store, fixture, delivery, second_distribution, report_id


def _rewrite_zip(source_zip: Path, target_zip: Path, mutate) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
    mutate(docs)
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name, data in docs.items():
            dst.writestr(name, data)
    return target_zip


def _read_doc(docs: dict[str, bytes], name: str) -> dict:
    return json.loads(docs[name].decode("utf-8"))


def _doc_bytes(doc: dict) -> bytes:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _sync_manifest_file(manifest: dict, path: str, payload: bytes) -> None:
    import hashlib

    for row in manifest.get("files", []):
        if row.get("path") == path:
            row["size_bytes"] = len(payload)
            row["sha256"] = hashlib.sha256(payload).hexdigest()
            return


def _remove_guard_full_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "knowledge-report.json")
    guards = _read_doc(docs, "regression-guards.json")
    runs = _read_doc(docs, "guard-run-summary.json")
    manifest = _read_doc(docs, "trust-operations-knowledge-manifest.json")
    guards["guards"] = []
    guards["summary"] = {"guard_count": 0, "active_guard_count": 0, "manual_required_guard_count": 0, "archived_guard_count": 0}
    guards["integrity_hash"] = knowledge_hash(guards)
    runs["runs"] = []
    runs["summary"] = {"run_count": 0, "passed_count": 0, "failed_count": 0, "manual_required_count": 0}
    runs["integrity_hash"] = knowledge_hash(runs)
    report["source"]["guards_hash"] = guards["integrity_hash"]
    report["source"]["guard_run_summary_hash"] = runs["integrity_hash"]
    report["summary"]["guard_count"] = 0
    report["summary"]["guards_passed_count"] = 0
    report["status"] = "warning"
    report["integrity_hash"] = knowledge_hash(report)
    docs["regression-guards.json"] = _doc_bytes(guards)
    docs["guard-run-summary.json"] = _doc_bytes(runs)
    docs["knowledge-report.json"] = _doc_bytes(report)
    for path in ("regression-guards.json", "guard-run-summary.json", "knowledge-report.json"):
        _sync_manifest_file(manifest, path, docs[path])
    manifest["integrity"]["guards_hash"] = guards["integrity_hash"]
    manifest["integrity"]["guard_run_summary_hash"] = runs["integrity_hash"]
    manifest["integrity"]["knowledge_report_hash"] = report["integrity_hash"]
    manifest["integrity_hash"] = knowledge_manifest_hash(manifest)
    docs["trust-operations-knowledge-manifest.json"] = _doc_bytes(manifest)

