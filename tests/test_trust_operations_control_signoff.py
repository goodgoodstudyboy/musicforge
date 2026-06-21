from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import write_json
from song_agent.trust_operations_control_signoff import TrustOperationsControlSignoffStateError, TrustOperationsControlSignoffStore, control_signoff_hash, control_signoff_manifest_hash
from song_agent.trust_operations_control_signoff_verifier import verify_trust_operations_control_signoff_archive_package
from song_agent.trust_operations_controls import TrustOperationsControlStore
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from tests.test_trust_operations_controls import _control_payload, _controls_fixture
from tests.test_trust_operations_hub import _has_blocker


def test_trust_operations_control_signoff_lifecycle_and_hub_gate(tmp_path: Path) -> None:
    hub_store, incident_store, knowledge_store, fixture, delivery, second_distribution, report_id = _controls_fixture(tmp_path)
    control_store, signoff_store, assessment_id, payload = _signoff_fixture(tmp_path, hub_store, incident_store, knowledge_store, report_id)

    signoff = signoff_store.sign("hub", assessment_id, {**payload, "signed_by": "reviewer", "reason": "Controls accepted."})
    manifest = signoff_store.export_archive("hub", payload)
    zip_info = signoff_store.build_archive_zip("hub")
    verification = signoff_store.verify_archive_zip("hub", {**payload, "strict": True, "require_signed": True, "require_current": True})

    delivery_kwargs = delivery.verify_kwargs()
    delivery_kwargs["distribution_verification_paths"] = [delivery.verify_payload["distribution_verification_path"], second_distribution]
    delivery_kwargs.pop("distribution_verification_path", None)
    missing_gate = verify_trust_operations_hub_package(
        hub_store.zip_path("hub", report_id),
        strict=True,
        require_trust_control_signoff=True,
        trust_control_package_path=control_store.zip_path("hub", assessment_id),
        trust_control_verification_report_path=control_store.verification_report_path("hub", assessment_id),
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
        incident_board_package_path=incident_store.zip_path("hub"),
        incident_board_verification_report_path=incident_store.verification_report_path("hub"),
        incident_knowledge_package_path=knowledge_store.zip_path("hub"),
        incident_knowledge_verification_report_path=knowledge_store.verification_report_path("hub"),
        **fixture.verify_kwargs(),
        **delivery_kwargs,
    )
    hub_gate = verify_trust_operations_hub_package(
        hub_store.zip_path("hub", report_id),
        strict=True,
        require_trust_controls=True,
        require_trust_control_signoff=True,
        trust_control_package_path=control_store.zip_path("hub", assessment_id),
        trust_control_verification_report_path=control_store.verification_report_path("hub", assessment_id),
        trust_control_signoff_archive_path=signoff_store.archive_zip_path("hub"),
        trust_control_signoff_verification_report_path=signoff_store.verification_report_path("hub"),
        hub_verification_report_path=hub_store.verification_report_path("hub", report_id),
        incident_board_package_path=incident_store.zip_path("hub"),
        incident_board_verification_report_path=incident_store.verification_report_path("hub"),
        incident_knowledge_package_path=knowledge_store.zip_path("hub"),
        incident_knowledge_verification_report_path=knowledge_store.verification_report_path("hub"),
        **fixture.verify_kwargs(),
        **delivery_kwargs,
    )

    assert signoff["status"] == "signed"
    assert manifest["package_type"] == "musicforge_trust_operations_control_signoff_manifest"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert _has_blocker(missing_gate, "toh_trust_control_signoff_archive_required")
    assert hub_gate["status"] == "passed", hub_gate.get("blockers")


def test_control_signoff_history_blocks_delete_bypass_and_cr_reuse(tmp_path: Path) -> None:
    hub_store, incident_store, knowledge_store, _fixture, _delivery, _second_distribution, report_id = _controls_fixture(tmp_path)
    _control_store, signoff_store, assessment_id, payload = _signoff_fixture(tmp_path, hub_store, incident_store, knowledge_store, report_id)
    signoff_store.sign("hub", assessment_id, payload)
    os.remove(signoff_store.signoff_path("hub"))

    with pytest.raises(TrustOperationsControlSignoffStateError):
        signoff_store.export_archive("hub", payload)

    cr = signoff_store.create_change_request("hub", {"reason": "Refresh controls after source changes."})
    with pytest.raises(TrustOperationsControlSignoffStateError):
        signoff_store.reset_signoff("hub", cr["change_request_id"])
    approved = signoff_store.approve_change_request("hub", cr["change_request_id"])
    reset = signoff_store.reset_signoff("hub", approved["change_request_id"])
    assert reset["status"] == "reset"
    with pytest.raises(TrustOperationsControlSignoffStateError):
        signoff_store.reset_signoff("hub", approved["change_request_id"])


def test_control_signoff_verifier_rejects_tampering(tmp_path: Path) -> None:
    hub_store, incident_store, knowledge_store, _fixture, _delivery, _second_distribution, report_id = _controls_fixture(tmp_path)
    control_store, signoff_store, assessment_id, payload = _signoff_fixture(tmp_path, hub_store, incident_store, knowledge_store, report_id)
    signoff_store.sign("hub", assessment_id, payload)
    signoff_store.export_archive("hub", payload)
    signoff_store.build_archive_zip("hub")

    signed_by = verify_trust_operations_control_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path("hub"), tmp_path / "signed-by.zip", _tamper_signed_by),
        strict=True,
        require_signed=True,
        require_current=True,
        control_package_path=control_store.zip_path("hub", assessment_id),
        control_verification_report_path=control_store.verification_report_path("hub", assessment_id),
        **payload,
    )
    source = verify_trust_operations_control_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path("hub"), tmp_path / "source.zip", _tamper_source_summary),
        strict=True,
        require_signed=True,
        require_current=True,
        control_package_path=control_store.zip_path("hub", assessment_id),
        control_verification_report_path=control_store.verification_report_path("hub", assessment_id),
        **payload,
    )
    history = verify_trust_operations_control_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path("hub"), tmp_path / "history.zip", _tamper_history_remove_signed),
        strict=True,
        require_signed=True,
        require_current=True,
        control_package_path=control_store.zip_path("hub", assessment_id),
        control_verification_report_path=control_store.verification_report_path("hub", assessment_id),
        **payload,
    )
    critical = verify_trust_operations_control_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path("hub"), tmp_path / "critical.zip", _tamper_critical_exception),
        strict=True,
        require_signed=True,
    )
    extra = verify_trust_operations_control_signoff_archive_package(_rewrite_zip(signoff_store.archive_zip_path("hub"), tmp_path / "extra.zip", lambda docs: docs.update({"docs/extra.txt": b"x"})), strict=True)

    assert _has_blocker(signed_by, "tocs_report_signoff_hash") or _has_blocker(signed_by, "tocs_manifest_signoff_hash")
    assert _has_blocker(source, "tocs_source_matches_signoff") or _has_blocker(source, "tocs_control_verification_report_hash")
    assert _has_blocker(history, "tocs_history_signed_event") or _has_blocker(history, "tocs_manifest_history_hash")
    assert _has_blocker(critical, "tocs_exception_no_forbidden_approvals")
    assert _has_blocker(extra, "tocs_zip_allowed_entries")


def _signoff_fixture(tmp_path: Path, hub_store, incident_store, knowledge_store, report_id: str):
    control_store = TrustOperationsControlStore(tmp_path / ".musicforge" / "trust-operations-controls", hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    payload = _control_payload(hub_store, incident_store, knowledge_store, report_id)
    control_store.refresh_catalog("hub", payload)
    policy = control_store.create_policy_bundle("hub", {"policy_id": "toc-policy-000001"})
    assessment = control_store.assess_policy("hub", policy["policy_id"], payload)
    assessment_id = assessment["assessment"]["assessment_id"]
    control_store.export_controls("hub", assessment_id)
    control_store.build_zip("hub", assessment_id)
    verification = control_store.verify_zip("hub", assessment_id, {**payload, "strict": True, "require_policy_passed": True})
    assert verification["status"] == "passed", verification.get("blockers")
    signoff_store = TrustOperationsControlSignoffStore(tmp_path / ".musicforge" / "trust-operations-control-signoffs", control_store=control_store, hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    return control_store, signoff_store, assessment_id, payload


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


def _resign_archive_docs(docs: dict[str, bytes]) -> None:
    signoff = _read_doc(docs, "control-signoff.json")
    exceptions = _read_doc(docs, "control-exceptions.json")
    change_requests = _read_doc(docs, "control-change-requests.json")
    report = _read_doc(docs, "control-signoff-report.json")
    source = _read_doc(docs, "source-verification-summary.json")
    manifest = _read_doc(docs, "trust-operations-control-signoff-manifest.json")
    for name, doc in {
        "control-signoff.json": signoff,
        "control-exceptions.json": exceptions,
        "control-change-requests.json": change_requests,
        "control-signoff-report.json": report,
        "source-verification-summary.json": source,
    }.items():
        doc["integrity_hash"] = control_signoff_hash(doc)
        docs[name] = _doc_bytes(doc)
        _sync_manifest_file(manifest, name, docs[name])
    history = docs["control-signoff-history.jsonl"]
    _sync_manifest_file(manifest, "control-signoff-history.jsonl", history)
    manifest["source"] = {
        "signoff_hash": signoff.get("integrity_hash"),
        "history_hash": manifest["source"].get("history_hash"),
        "exceptions_hash": exceptions.get("integrity_hash"),
        "change_requests_hash": change_requests.get("integrity_hash"),
        "report_hash": report.get("integrity_hash"),
        "source_verification_summary_hash": source.get("integrity_hash"),
    }
    manifest["integrity_hash"] = control_signoff_manifest_hash(manifest)
    docs["trust-operations-control-signoff-manifest.json"] = _doc_bytes(manifest)


def _tamper_signed_by(docs: dict[str, bytes]) -> None:
    signoff = _read_doc(docs, "control-signoff.json")
    signoff["signed_by"] = "tampered-reviewer"
    docs["control-signoff.json"] = _doc_bytes(signoff)
    _resign_archive_docs(docs)


def _tamper_source_summary(docs: dict[str, bytes]) -> None:
    source = _read_doc(docs, "source-verification-summary.json")
    source["source"]["control_zip_sha256"] = "0" * 64
    docs["source-verification-summary.json"] = _doc_bytes(source)
    _resign_archive_docs(docs)


def _tamper_history_remove_signed(docs: dict[str, bytes]) -> None:
    docs["control-signoff-history.jsonl"] = b""
    manifest = _read_doc(docs, "trust-operations-control-signoff-manifest.json")
    manifest["source"]["history_hash"] = "0" * 64
    docs["trust-operations-control-signoff-manifest.json"] = _doc_bytes(manifest)
    _resign_archive_docs(docs)


def _tamper_critical_exception(docs: dict[str, bytes]) -> None:
    exceptions = _read_doc(docs, "control-exceptions.json")
    exception = {
        "schema_version": 1,
        "package_type": "musicforge_trust_operations_control_exception",
        "exception_id": "tocs-exc-forged",
        "hub_id": "hub",
        "control_id": "toc-baseline-redaction-clean",
        "status": "approved",
        "risk": {"severity": "critical", "required": True},
        "source": {},
        "approval": {"decision": "approved"},
    }
    exception["integrity_hash"] = control_signoff_hash(exception)
    exceptions["exceptions"].append(exception)
    exceptions["summary"]["exception_count"] = len(exceptions["exceptions"])
    exceptions["summary"]["approved_count"] = sum(1 for row in exceptions["exceptions"] if row.get("status") == "approved")
    docs["control-exceptions.json"] = _doc_bytes(exceptions)
    _resign_archive_docs(docs)
