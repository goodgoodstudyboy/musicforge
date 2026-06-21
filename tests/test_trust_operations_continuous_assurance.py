from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.trust_operations_continuous_assurance import (
    TrustOperationsAssuranceStateError,
    TrustOperationsAssuranceStore,
    assurance_hash,
    assurance_manifest_hash,
)
from song_agent.trust_operations_continuous_assurance_verifier import verify_trust_operations_assurance_package
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from tests.test_trust_operations_control_signoff import _signoff_fixture
from tests.test_trust_operations_controls import _controls_fixture
from tests.test_trust_operations_hub import _has_blocker


def test_trust_operations_continuous_assurance_lifecycle_and_hub_gate(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    store = fixture.assurance_store

    refreshed = store.refresh_run("hub", fixture.payload)
    run_id = refreshed["run"]["run_id"]
    manifest = store.export_archive(run_id)
    zip_info = store.build_archive_zip(run_id)
    verification = store.verify_archive_zip(run_id, {**fixture.assurance_verifier_payload, "strict": True, "require_passed": True, "require_current": True})

    missing = verify_trust_operations_hub_package(
        fixture.hub_zip,
        strict=True,
        require_continuous_assurance=True,
        hub_verification_report_path=fixture.hub_verification,
        **fixture.base_hub_verify_payload,
    )
    gate = verify_trust_operations_hub_package(
        fixture.hub_zip,
        strict=True,
        require_continuous_assurance=True,
        continuous_assurance_archive_path=store.archive_zip_path(run_id),
        continuous_assurance_verification_report_path=store.verification_report_path(run_id),
        hub_verification_report_path=fixture.hub_verification,
        **fixture.base_hub_verify_payload,
    )

    assert refreshed["run"]["status"] == "passed", refreshed["run"]["checks"]
    assert manifest["package_type"] == "musicforge_trust_operations_continuous_assurance_manifest"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert _has_blocker(missing, "toh_continuous_assurance_archive_required")
    assert gate["status"] == "passed", gate.get("blockers")


def test_assurance_verifier_rejects_full_resign_summary_forgery(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    store = fixture.assurance_store
    run_id = store.refresh_run("hub", fixture.payload)["run"]["run_id"]
    store.export_archive(run_id)
    store.build_archive_zip(run_id)

    forged = verify_trust_operations_assurance_package(
        _rewrite_zip(store.archive_zip_path(run_id), tmp_path / "assurance-full-resign.zip", _tamper_report_summary_full_resign),
        strict=True,
        require_passed=True,
        require_current=True,
        **fixture.assurance_verifier_payload,
    )

    assert _has_blocker(forged, "toa_report_summary_matches_run")


def test_assurance_export_rejects_stale_external_report(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    store = fixture.assurance_store
    run_id = store.refresh_run("hub", fixture.payload)["run"]["run_id"]

    report = read_json(fixture.hub_verification)
    report["zip_sha256"] = "0" * 64
    write_json(fixture.hub_verification, report)

    with pytest.raises(TrustOperationsAssuranceStateError):
        store.export_archive(run_id)


def test_assurance_blocks_failed_delivery_verification(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    report = read_json(fixture.assurance_verifier_payload["release_verification_paths"][0])
    report["status"] = "failed"
    write_json(fixture.assurance_verifier_payload["release_verification_paths"][0], report)

    run = fixture.assurance_store.refresh_run("hub", fixture.payload)["run"]

    assert run["status"] == "failed"
    assert run["summary"]["blocking_failed_count"] >= 1
    assert _check_failed(run, "toa_delivery_release")


def test_assurance_blocks_failed_second_distribution_verification(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    second_distribution = fixture.assurance_verifier_payload["distribution_verification_paths"][1]
    report = read_json(second_distribution)
    report["status"] = "failed"
    write_json(second_distribution, report)

    run = fixture.assurance_store.refresh_run("hub", fixture.payload)["run"]

    assert run["status"] == "failed"
    assert _check_failed(run, "toa_delivery_distribution")


def test_assurance_policy_can_require_missing_delivery_verification(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    policy = fixture.assurance_store.write_policy({"policy_id": "delivery-required", "requirements": {"require_delivery_ready": True}})
    payload = {
        key: value
        for key, value in fixture.payload.items()
        if key
        not in {
            "release_verification_path",
            "release_verification_paths",
            "distribution_verification_path",
            "distribution_verification_paths",
            "submission_verification_path",
            "submission_verification_paths",
            "submission_evidence_verification_path",
            "submission_evidence_verification_paths",
            "release_operations_verification_path",
            "release_operations_verification_paths",
        }
    }

    run = fixture.assurance_store.refresh_run("hub", payload, policy_id=policy["policy_id"])["run"]

    assert run["status"] == "failed"
    assert _check_failed(run, "toa_delivery_release_verification_present")
    assert _check_failed(run, "toa_delivery_distribution_verification_present")


def test_assurance_verifier_rejects_zip_edges(tmp_path: Path) -> None:
    fixture = _assurance_fixture(tmp_path)
    store = fixture.assurance_store
    run_id = store.refresh_run("hub", fixture.payload)["run"]["run_id"]
    store.export_archive(run_id)
    store.build_archive_zip(run_id)
    source_zip = store.archive_zip_path(run_id)

    extra = verify_trust_operations_assurance_package(_rewrite_zip(source_zip, tmp_path / "extra.zip", lambda docs: docs.update({"docs/extra.txt": b"x"})), strict=True)
    duplicate = verify_trust_operations_assurance_package(_duplicate_zip(source_zip, tmp_path / "duplicate.zip"), strict=True)
    backslash = verify_trust_operations_assurance_package(_backslash_zip(tmp_path / "backslash.zip"), strict=True)
    redaction = verify_trust_operations_assurance_package(_rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b'\napi_key="sk-test-secret" C:\\Users\\demo\\githubkey.txt\n')), strict=True)

    assert _has_blocker(extra, "toa_zip_allowed_entries")
    assert _has_blocker(duplicate, "toa_zip_duplicate_entries")
    assert _has_blocker(backslash, "toa_zip_entry_path_safe")
    assert _has_blocker(redaction, "toa_redaction_scan")


class _AssuranceFixture:
    def __init__(
        self,
        assurance_store: TrustOperationsAssuranceStore,
        payload: dict,
        base_hub_verify_payload: dict,
        hub_zip: Path,
        hub_verification: Path,
        assurance_verifier_payload: dict,
    ) -> None:
        self.assurance_store = assurance_store
        self.payload = payload
        self.base_hub_verify_payload = base_hub_verify_payload
        self.hub_zip = hub_zip
        self.hub_verification = hub_verification
        self.assurance_verifier_payload = assurance_verifier_payload


def _assurance_fixture(tmp_path: Path) -> _AssuranceFixture:
    hub_store, incident_store, knowledge_store, fixture, delivery, second_distribution, report_id = _controls_fixture(tmp_path)
    control_store, signoff_store, assessment_id, payload = _signoff_fixture(tmp_path, hub_store, incident_store, knowledge_store, report_id)
    signoff_store.sign("hub", assessment_id, {**payload, "signed_by": "reviewer", "reason": "Control signoff accepted for assurance."})
    signoff_store.export_archive("hub", payload)
    signoff_store.build_archive_zip("hub")
    signoff_store.verify_archive_zip("hub", {**payload, "strict": True, "require_signed": True, "require_current": True})

    delivery_kwargs = delivery.verify_kwargs()
    delivery_kwargs["distribution_verification_paths"] = [delivery.verify_payload["distribution_verification_path"], second_distribution]
    delivery_kwargs.pop("distribution_verification_path", None)
    hub_store.verify_zip(
        "hub",
        report_id,
        {
            **fixture.verify_payload,
            **delivery_kwargs,
            "strict": True,
            "require_delivery_ready": True,
            "require_current": True,
            "require_publication_monitoring_clean": True,
        },
    )
    assurance_payload = {
        **payload,
        "control_package_path": control_store.zip_path("hub", assessment_id),
        "control_verification_report_path": control_store.verification_report_path("hub", assessment_id),
        "control_signoff_archive_path": signoff_store.archive_zip_path("hub"),
        "control_signoff_verification_report_path": signoff_store.verification_report_path("hub"),
        **delivery_kwargs,
    }
    base_hub_verify_payload = {**fixture.verify_kwargs()}
    assurance_verifier_payload = {
        **assurance_payload,
        "release_verification_paths": [delivery.verify_payload["release_verification_path"]],
        "submission_verification_paths": [delivery.verify_payload["submission_verification_path"]],
        "submission_evidence_verification_paths": [delivery.verify_payload["submission_evidence_verification_path"]],
        "release_operations_verification_paths": [delivery.verify_payload["release_operations_verification_path"]],
    }
    for key in (
        "release_verification_path",
        "distribution_verification_path",
        "submission_verification_path",
        "submission_evidence_verification_path",
        "release_operations_verification_path",
    ):
        assurance_verifier_payload.pop(key, None)
    store = TrustOperationsAssuranceStore(tmp_path / ".musicforge" / "trust-operations-assurance", hub_store=hub_store)
    return _AssuranceFixture(
        store,
        assurance_payload,
        base_hub_verify_payload,
        hub_store.zip_path("hub", report_id),
        hub_store.verification_report_path("hub", report_id),
        assurance_verifier_payload,
    )


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
            data = src.read(info)
            dst.writestr(info.filename, data)
        dst.writestr("assurance-report.json", src.read("assurance-report.json"))
    return target_zip


def _backslash_zip(target_zip: Path) -> Path:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    data = target_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt")
    target_zip.write_bytes(data)
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


def _check_failed(run: dict, check_id_prefix: str) -> bool:
    return any(
        isinstance(check, dict) and str(check.get("check_id") or "").startswith(check_id_prefix) and check.get("status") == "failed"
        for check in run.get("checks", [])
    )


def _tamper_report_summary_full_resign(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "assurance-report.json")
    report["summary"] = {"check_count": 0, "passed_count": 0, "blocking_failed_count": 0, "warning_count": 0, "score": 100}
    report["integrity_hash"] = assurance_hash(report)
    docs["assurance-report.json"] = _doc_bytes(report)
    manifest = _read_doc(docs, "trust-operations-assurance-manifest.json")
    manifest["source"]["report_hash"] = report["integrity_hash"]
    _sync_manifest_file(manifest, "assurance-report.json", docs["assurance-report.json"])
    manifest["integrity_hash"] = assurance_manifest_hash(manifest)
    docs["trust-operations-assurance-manifest.json"] = _doc_bytes(manifest)
