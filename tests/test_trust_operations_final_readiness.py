from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

from song_agent.trust_operations_final_readiness import (
    TrustOperationsFinalReadinessStateError,
    TrustOperationsFinalReadinessStore,
    final_readiness_hash,
    final_readiness_manifest_hash,
)
from song_agent.trust_operations_final_readiness_verifier import verify_trust_operations_final_handoff_package
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
from tests.test_trust_operations_continuous_assurance import _assurance_fixture
from tests.test_trust_operations_assurance_watch_signoff import _signoff_payload, _signed_fixture


def test_final_readiness_lifecycle_and_hub_gate(tmp_path: Path) -> None:
    fixture, watch_store, signoff_store, source, queue_id = _final_fixture(tmp_path)
    store = TrustOperationsFinalReadinessStore(tmp_path / ".musicforge" / "trust-operations-final-readiness")

    refreshed = store.refresh_report(source)
    certificate = store.create_certificate()
    signoff = store.sign({"signed_by": "reviewer", "role": "owner", "reason": "Final handoff is verified."})
    manifest = store.export_handoff(source)
    zip_info = store.build_handoff_zip()
    verification = store.verify_handoff_zip({"strict": True, "require_signed": True, "require_current": True, **source})
    hub_gate = verify_trust_operations_hub_package(
        fixture.hub_zip,
        strict=True,
        require_final_readiness=True,
        hub_verification_report_path=fixture.hub_verification,
        final_handoff_package_path=store.handoff_zip_path(),
        final_handoff_verification_report_path=store.verification_report_path(),
        assurance_watch_signoff_archive_path=signoff_store.archive_zip_path(queue_id),
        assurance_watch_signoff_verification_report_path=signoff_store.verification_report_path(queue_id),
        **fixture.base_hub_verify_payload,
    )

    assert refreshed["report"]["status"] == "ready"
    assert certificate["status"] == "ready"
    assert signoff["status"] == "signed"
    assert manifest["source"]["signoff_hash"] == signoff["integrity_hash"]
    assert zip_info["sha256"] == verification["zip_sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert hub_gate["status"] == "passed", hub_gate.get("blockers")


def test_final_readiness_signed_history_blocks_delete_bypass_and_reuse(tmp_path: Path) -> None:
    fixture, _watch_store, _signoff_store, source, _queue_id = _final_fixture(tmp_path)
    store = TrustOperationsFinalReadinessStore(tmp_path / ".musicforge" / "trust-operations-final-readiness")
    store.refresh_report(source)
    store.create_certificate()
    signoff = store.sign({"reason": "Final handoff verified before reset test."})
    os.remove(store.signoff_path())

    with pytest.raises(TrustOperationsFinalReadinessStateError):
        store.export_handoff(source)

    cr = store.create_change_request({"reason": "Refresh final handoff after evidence changes."})
    with pytest.raises(TrustOperationsFinalReadinessStateError):
        store.reset_signoff(cr["change_request_id"])
    store.approve_change_request(cr["change_request_id"], {"approved_by": "reviewer"})
    reset = store.reset_signoff(cr["change_request_id"])
    assert reset["status"] == "reset"
    with pytest.raises(TrustOperationsFinalReadinessStateError):
        store.reset_signoff(cr["change_request_id"])
    assert signoff["integrity_hash"]
    assert fixture.hub_zip.exists()


def test_final_readiness_verifier_rejects_full_resign_signoff(tmp_path: Path) -> None:
    _fixture, _watch_store, _signoff_store, source, _queue_id = _final_fixture(tmp_path)
    store = TrustOperationsFinalReadinessStore(tmp_path / ".musicforge" / "trust-operations-final-readiness")
    store.refresh_report(source)
    store.create_certificate()
    store.sign({"reason": "Final handoff verified before tamper test."})
    store.export_handoff(source)
    store.build_handoff_zip()

    tampered = _rewrite_zip(store.handoff_zip_path(), tmp_path / "tampered-final.zip", _tamper_signoff_full_resign)
    report = verify_trust_operations_final_handoff_package(tampered, strict=True, require_signed=True)

    assert _has_blocker(report, "tofr_history_signoff_payload_binding")


def _final_fixture(tmp_path: Path):
    fixture = _assurance_fixture(tmp_path)
    assurance_store = fixture.assurance_store
    run_id = assurance_store.refresh_run("hub", fixture.payload)["run"]["run_id"]
    assurance_store.export_archive(run_id)
    assurance_store.build_archive_zip(run_id)
    assurance_store.verify_archive_zip(run_id, {**fixture.assurance_verifier_payload, "strict": True, "require_passed": True, "require_current": True})
    watch_payload = {
        "hub_id": "hub",
        "assurance_archive_path": assurance_store.archive_zip_path(run_id),
        "assurance_verification_report_path": assurance_store.verification_report_path(run_id),
        "hub_package_path": fixture.hub_zip,
        "hub_verification_report_path": fixture.hub_verification,
    }
    watch_store = TrustOperationsAssuranceWatchStore(tmp_path / ".musicforge" / "trust-operations-assurance-watch", assurance_store=assurance_store, hub_store=assurance_store.hub_store)
    queue_id = watch_store.refresh_queue(watch_payload)["queue"]["queue_id"]
    signoff_store = _signed_fixture(tmp_path, watch_store, watch_payload, queue_id, export=True, zip_it=True)
    signoff_store.verify_archive_zip(queue_id, {"strict": True, "require_signed": True, "require_current": True, **_signoff_payload(watch_payload, watch_store, queue_id)})
    source = _final_source(fixture, watch_payload, watch_store, signoff_store, queue_id)
    return fixture, watch_store, signoff_store, source, queue_id


def _final_source(fixture, watch_payload: dict, watch_store, signoff_store, queue_id: str) -> dict:
    return {
        **fixture.payload,
        **fixture.assurance_verifier_payload,
        "hub_package_path": watch_payload["hub_package_path"],
        "hub_verification_report_path": watch_payload["hub_verification_report_path"],
        "continuous_assurance_archive_path": watch_payload["assurance_archive_path"],
        "continuous_assurance_verification_report_path": watch_payload["assurance_verification_report_path"],
        "assurance_watch_package_path": watch_store.watch_zip_path(queue_id),
        "assurance_watch_verification_report_path": watch_store.verification_report_path(queue_id),
        "assurance_watch_signoff_archive_path": signoff_store.archive_zip_path(queue_id),
        "assurance_watch_signoff_verification_report_path": signoff_store.verification_report_path(queue_id),
    }


def _rewrite_zip(source_zip: Path, target_zip: Path, mutate) -> Path:
    with zipfile.ZipFile(source_zip, "r") as src:
        docs = {info.filename: src.read(info.filename) for info in src.infolist()}
    mutate(docs)
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name, data in docs.items():
            dst.writestr(name, data)
    return target_zip


def _tamper_signoff_full_resign(docs: dict[str, bytes]) -> None:
    signoff = _read_doc(docs, "final-handoff-signoff.json")
    signoff["signed_by"] = "tampered-reviewer"
    signoff["payload_hash"] = _signoff_payload_hash(signoff)
    signoff["integrity_hash"] = final_readiness_hash(signoff)
    docs["final-handoff-signoff.json"] = _doc_bytes(signoff)
    manifest = _read_doc(docs, "trust-operations-final-readiness-manifest.json")
    rows = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    for row in rows:
        if row.get("path") == "final-handoff-signoff.json":
            row["sha256"] = _sha256_bytes(docs["final-handoff-signoff.json"])
            row["size_bytes"] = len(docs["final-handoff-signoff.json"])
    manifest["source"]["signoff_hash"] = signoff["integrity_hash"]
    manifest["integrity_hash"] = final_readiness_manifest_hash(manifest)
    docs["trust-operations-final-readiness-manifest.json"] = _doc_bytes(manifest)


def _signoff_payload_hash(signoff: dict) -> str:
    from song_agent.releases import stable_hash

    return stable_hash(
        {
            "signoff_id": signoff.get("signoff_id"),
            "signed_by": signoff.get("signed_by"),
            "role": signoff.get("role"),
            "reason": signoff.get("reason"),
            "source": signoff.get("source"),
            "decision": signoff.get("decision"),
        }
    )


def _read_doc(docs: dict[str, bytes], name: str) -> dict:
    import json

    return json.loads(docs[name].decode("utf-8"))


def _doc_bytes(doc: dict) -> bytes:
    import json

    return json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(item.get("check_id") == check_id for item in report.get("blockers", []))
