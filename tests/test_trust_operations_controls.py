from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from song_agent.projectio import read_json
from song_agent.trust_operations_controls import TrustOperationsControlStore, control_hash, control_manifest_hash
from song_agent.trust_operations_controls_verifier import verify_trust_operations_control_package
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore
from tests.test_trust_operations_hub import _has_blocker
from tests.test_trust_operations_incident_knowledge import _closed_incident_fixture


def test_trust_operations_controls_lifecycle_and_hub_gate(tmp_path: Path) -> None:
    hub_store, incident_store, knowledge_store, fixture, delivery, second_distribution, report_id = _controls_fixture(tmp_path)
    store = TrustOperationsControlStore(tmp_path / ".musicforge" / "trust-operations-controls", hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    payload = _control_payload(hub_store, incident_store, knowledge_store, report_id)

    catalog = store.refresh_catalog("hub", payload)
    policy = store.create_policy_bundle("hub", {"policy_id": "toc-policy-000001"})
    assessment = store.assess_policy("hub", policy["policy_id"], payload)
    assessment_id = assessment["assessment"]["assessment_id"]
    manifest = store.export_controls("hub", assessment_id)
    zip_info = store.build_zip("hub", assessment_id)
    verification = store.verify_zip("hub", assessment_id, {**payload, "strict": True, "require_policy_passed": True})
    delivery_kwargs = delivery.verify_kwargs()
    delivery_kwargs["distribution_verification_paths"] = [delivery.verify_payload["distribution_verification_path"], second_distribution]
    delivery_kwargs.pop("distribution_verification_path", None)
    hub_gate = verify_trust_operations_hub_package(
        hub_store.zip_path("hub", report_id),
        strict=True,
        require_trust_controls=True,
        trust_control_package_path=store.zip_path("hub", assessment_id),
        trust_control_verification_report_path=store.verification_report_path("hub", assessment_id),
        incident_board_package_path=incident_store.zip_path("hub"),
        incident_board_verification_report_path=incident_store.verification_report_path("hub"),
        incident_knowledge_package_path=knowledge_store.zip_path("hub"),
        incident_knowledge_verification_report_path=knowledge_store.verification_report_path("hub"),
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
        **fixture.verify_kwargs(),
        **delivery_kwargs,
    )

    assert catalog["summary"]["baseline_count"] == 10
    assert catalog["summary"]["derived_count"] == 1
    assert assessment["assessment"]["status"] == "passed", assessment["blocker_summary"]
    assert manifest["package_type"] == "musicforge_trust_operations_control_manifest"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert hub_gate["status"] == "passed", hub_gate.get("blockers")


def test_trust_operations_controls_reject_full_resign_attacks(tmp_path: Path) -> None:
    hub_store, incident_store, knowledge_store, _fixture, _delivery, _second_distribution, report_id = _controls_fixture(tmp_path)
    store = TrustOperationsControlStore(tmp_path / ".musicforge" / "trust-operations-controls", hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    payload = _control_payload(hub_store, incident_store, knowledge_store, report_id)
    store.refresh_catalog("hub", payload)
    policy = store.create_policy_bundle("hub", {"policy_id": "toc-policy-000001"})
    assessment = store.assess_policy("hub", policy["policy_id"], payload)
    assessment_id = assessment["assessment"]["assessment_id"]
    store.export_controls("hub", assessment_id)
    store.build_zip("hub", assessment_id)

    result_resign = verify_trust_operations_control_package(_rewrite_zip(store.zip_path("hub", assessment_id), tmp_path / "result-resign.zip", _tamper_result_full_resign), strict=True, require_policy_passed=True, **payload)
    downgrade = verify_trust_operations_control_package(_rewrite_zip(store.zip_path("hub", assessment_id), tmp_path / "downgrade.zip", _downgrade_derived_control_full_resign), strict=True, require_policy_passed=True, **payload)
    binding = verify_trust_operations_control_package(_rewrite_zip(store.zip_path("hub", assessment_id), tmp_path / "binding.zip", _swap_binding_full_resign), strict=True, require_policy_passed=True, **payload)
    extra = verify_trust_operations_control_package(_rewrite_zip(store.zip_path("hub", assessment_id), tmp_path / "extra.zip", lambda docs: docs.update({"docs/extra.txt": b"x"})), strict=True)

    assert _has_blocker(result_resign, "tohc_control_results_semantics_match")
    assert _has_blocker(downgrade, "tohc_knowledge_derived_control_fact_binding")
    assert _has_blocker(binding, "tohc_hub_binding_report_hash") or _has_blocker(binding, "tohc_hub_binding_zip_sha256")
    assert _has_blocker(extra, "tohc_zip_allowed_entries")


def _controls_fixture(tmp_path: Path):
    hub_store, incident_store, fixture, delivery, second_distribution, report_id = _closed_incident_fixture(tmp_path)
    knowledge_store = TrustOperationsIncidentKnowledgeStore(tmp_path / ".musicforge" / "trust-operations-knowledge", hub_store=hub_store, incident_store=incident_store)
    refreshed = knowledge_store.refresh("hub")
    guard = knowledge_store.create_guard("hub", refreshed["entries"][0]["entry_id"])
    knowledge_store.run_guard("hub", guard["guard_id"])
    knowledge_store.refresh_recurrence("hub")
    knowledge_store.export_knowledge("hub")
    knowledge_store.build_zip("hub")
    knowledge_store.verify_zip(
        "hub",
        {
            "strict": True,
            "require_guards_passed": True,
            "require_no_open_recurrence": True,
            "incident_board_package_path": incident_store.zip_path("hub"),
            "incident_board_verification_report_path": incident_store.verification_report_path("hub"),
            "hub_verification_report_path": hub_store.verification_report_path("hub", report_id),
        },
    )
    return hub_store, incident_store, knowledge_store, fixture, delivery, second_distribution, report_id


def _control_payload(hub_store, incident_store, knowledge_store, report_id: str) -> dict[str, Path]:
    return {
        "hub_package_path": hub_store.zip_path("hub", report_id),
        "hub_verification_report_path": hub_store.verification_report_path("hub", report_id),
        "incident_board_package_path": incident_store.zip_path("hub"),
        "incident_board_verification_report_path": incident_store.verification_report_path("hub"),
        "incident_knowledge_package_path": knowledge_store.zip_path("hub"),
        "incident_knowledge_verification_report_path": knowledge_store.verification_report_path("hub"),
    }


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
    for row in manifest.get("files", []):
        if row.get("path") == path:
            row["size_bytes"] = len(payload)
            row["sha256"] = hashlib.sha256(payload).hexdigest()
            return


def _resign_control_docs(docs: dict[str, bytes]) -> None:
    catalog = _read_doc(docs, "control-catalog.json")
    policy = _read_doc(docs, "policy-bundle.json")
    assessment = _read_doc(docs, "control-assessment-report.json")
    results = _read_doc(docs, "control-results.json")
    bindings = _read_doc(docs, "evidence-bindings.json")
    blockers = _read_doc(docs, "blocker-summary.json")
    actions = _read_doc(docs, "manual-actions.json")
    manifest = _read_doc(docs, "trust-operations-controls-manifest.json")
    for name, doc in {
        "control-catalog.json": catalog,
        "policy-bundle.json": policy,
        "control-assessment-report.json": assessment,
        "control-results.json": results,
        "evidence-bindings.json": bindings,
        "blocker-summary.json": blockers,
        "manual-actions.json": actions,
    }.items():
        doc["integrity_hash"] = control_hash(doc)
        docs[name] = _doc_bytes(doc)
        _sync_manifest_file(manifest, name, docs[name])
    manifest["source"] = {
        "catalog_hash": catalog["integrity_hash"],
        "policy_hash": policy["integrity_hash"],
        "assessment_hash": assessment["integrity_hash"],
        "control_results_hash": results["integrity_hash"],
        "evidence_bindings_hash": bindings["integrity_hash"],
        "blocker_summary_hash": blockers["integrity_hash"],
        "manual_actions_hash": actions["integrity_hash"],
    }
    manifest["integrity_hash"] = control_manifest_hash(manifest)
    docs["trust-operations-controls-manifest.json"] = _doc_bytes(manifest)


def _tamper_result_full_resign(docs: dict[str, bytes]) -> None:
    results = _read_doc(docs, "control-results.json")
    result = results["results"][0]
    result["status"] = "failed" if result["status"] == "passed" else "passed"
    result["message"] = "Forged result status."
    result["integrity_hash"] = control_hash(result)
    results["summary"]["passed_count"] = sum(1 for row in results["results"] if row.get("status") == "passed")
    results["summary"]["failed_count"] = sum(1 for row in results["results"] if row.get("status") == "failed")
    results["summary"]["required_failed_count"] = sum(1 for row in results["results"] if row.get("required") and row.get("status") != "passed")
    docs["control-results.json"] = _doc_bytes(results)
    _resign_control_docs(docs)


def _downgrade_derived_control_full_resign(docs: dict[str, bytes]) -> None:
    catalog = _read_doc(docs, "control-catalog.json")
    policy = _read_doc(docs, "policy-bundle.json")
    results = _read_doc(docs, "control-results.json")
    for control in catalog["controls"]:
        if control.get("source", {}).get("source_type") == "knowledge_entry":
            control["severity"] = "low"
            control["category"] = "benign_documentation_issue"
            control["scope"]["failure_mode"] = "operator_note"
            control["integrity_hash"] = control_hash(control)
            for result in results["results"]:
                if result.get("control_id") == control["control_id"]:
                    result["severity"] = "low"
                    result["control_hash"] = control["integrity_hash"]
                    result["integrity_hash"] = control_hash(result)
            break
    catalog["summary"]["high_count"] = sum(1 for row in catalog["controls"] if row.get("severity") == "high")
    catalog["summary"]["critical_count"] = sum(1 for row in catalog["controls"] if row.get("severity") == "critical")
    policy["source"]["catalog_hash"] = control_hash(catalog)
    docs["control-catalog.json"] = _doc_bytes(catalog)
    docs["policy-bundle.json"] = _doc_bytes(policy)
    docs["control-results.json"] = _doc_bytes(results)
    _resign_control_docs(docs)


def _swap_binding_full_resign(docs: dict[str, bytes]) -> None:
    bindings = _read_doc(docs, "evidence-bindings.json")
    assessment = _read_doc(docs, "control-assessment-report.json")
    for row in bindings["bindings"]:
        if row.get("evidence_type") == "hub_verification":
            row["verification_report_hash"] = "0" * 64
            row["zip_sha256"] = "1" * 64
            row["manifest_hash"] = "2" * 64
            break
    bindings["integrity_hash"] = control_hash(bindings)
    assessment["source"]["evidence_bindings_hash"] = bindings["integrity_hash"]
    docs["evidence-bindings.json"] = _doc_bytes(bindings)
    docs["control-assessment-report.json"] = _doc_bytes(assessment)
    _resign_control_docs(docs)
