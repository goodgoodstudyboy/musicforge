from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

import pytest

from song_agent.trust_operations_assurance_watch_signoff import (
    TrustOperationsAssuranceWatchSignoffStateError,
    TrustOperationsAssuranceWatchSignoffStore,
    watch_signoff_hash,
    watch_signoff_manifest_hash,
)
from song_agent.trust_operations_assurance_watch_signoff_verifier import verify_trust_operations_assurance_watch_signoff_archive_package
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package
from tests.test_trust_operations_assurance_watch import _watch_fixture
from tests.test_trust_operations_continuous_assurance import _doc_bytes, _read_doc, _rewrite_zip, _sync_manifest_file
from tests.test_trust_operations_hub import _has_blocker


def test_assurance_watch_signoff_lifecycle_and_hub_gate(tmp_path: Path) -> None:
    fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    signoff_store = _signoff_store(tmp_path, watch_store)
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)
    watch_store.verify_watch_zip(queue_id, {"strict": True, "require_clear": True, "require_current": True, **payload})

    closeout = signoff_store.refresh_closeout(queue_id, _signoff_payload(payload, watch_store, queue_id))
    signoff = signoff_store.sign(queue_id, {"signed_by": "reviewer", "role": "owner", "reason": "Watch queue clear and verified."})
    manifest = signoff_store.export_archive(queue_id, _signoff_payload(payload, watch_store, queue_id))
    zip_info = signoff_store.build_archive_zip(queue_id)
    verification = signoff_store.verify_archive_zip(queue_id, {"strict": True, "require_signed": True, "require_current": True, **_signoff_payload(payload, watch_store, queue_id)})
    missing_gate = verify_trust_operations_hub_package(
        fixture.hub_zip,
        strict=True,
        require_assurance_watch_signoff=True,
        hub_verification_report_path=fixture.hub_verification,
        **fixture.base_hub_verify_payload,
    )
    hub_gate = verify_trust_operations_hub_package(
        fixture.hub_zip,
        strict=True,
        require_assurance_watch_signoff=True,
        assurance_watch_package_path=watch_store.watch_zip_path(queue_id),
        assurance_watch_verification_report_path=watch_store.verification_report_path(queue_id),
        assurance_watch_signoff_archive_path=signoff_store.archive_zip_path(queue_id),
        assurance_watch_signoff_verification_report_path=signoff_store.verification_report_path(queue_id),
        continuous_assurance_archive_path=payload["assurance_archive_path"],
        continuous_assurance_verification_report_path=payload["assurance_verification_report_path"],
        hub_verification_report_path=fixture.hub_verification,
        **fixture.base_hub_verify_payload,
    )

    assert closeout["status"] == "passed"
    assert signoff["status"] == "signed"
    assert manifest["package_type"] == "musicforge_trust_operations_assurance_watch_signoff_manifest"
    assert zip_info["sha256"]
    assert verification["status"] == "passed", verification.get("blockers")
    assert _has_blocker(missing_gate, "toh_assurance_watch_signoff_archive_required")
    assert hub_gate["status"] == "passed", hub_gate.get("blockers")


def test_assurance_watch_signoff_history_blocks_delete_bypass_and_cr_reuse(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    signoff_store = _signed_fixture(tmp_path, watch_store, payload, queue_id)
    os.remove(signoff_store.signoff_path(queue_id))

    with pytest.raises(TrustOperationsAssuranceWatchSignoffStateError):
        signoff_store.export_archive(queue_id, _signoff_payload(payload, watch_store, queue_id))

    cr = signoff_store.create_change_request(queue_id, {"reason": "Refresh watch after evidence changes."})
    with pytest.raises(TrustOperationsAssuranceWatchSignoffStateError):
        signoff_store.reset_signoff(queue_id, cr["change_request_id"])
    approved = signoff_store.approve_change_request(queue_id, cr["change_request_id"])
    reset = signoff_store.reset_signoff(queue_id, approved["change_request_id"])
    assert reset["status"] == "reset"
    with pytest.raises(TrustOperationsAssuranceWatchSignoffStateError):
        signoff_store.reset_signoff(queue_id, approved["change_request_id"])


def test_assurance_watch_signoff_verifier_rejects_tampering(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path)
    signoff_store = _signed_fixture(tmp_path, watch_store, payload, queue_id, export=True, zip_it=True)
    verify_payload = _signoff_payload(payload, watch_store, queue_id)

    signed_by = verify_trust_operations_assurance_watch_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path(queue_id), tmp_path / "signed-by.zip", _tamper_signed_by),
        strict=True,
        require_signed=True,
        require_current=True,
        **verify_payload,
    )
    closeout = verify_trust_operations_assurance_watch_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path(queue_id), tmp_path / "closeout.zip", _tamper_closeout_clear),
        strict=True,
        require_signed=True,
        require_current=True,
        **verify_payload,
    )
    history = verify_trust_operations_assurance_watch_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path(queue_id), tmp_path / "history.zip", _tamper_history_remove_signed),
        strict=True,
        require_signed=True,
        require_current=True,
        **verify_payload,
    )
    extra = verify_trust_operations_assurance_watch_signoff_archive_package(_rewrite_zip(signoff_store.archive_zip_path(queue_id), tmp_path / "extra.zip", lambda docs: docs.update({"docs/notes.txt": b"x"})), strict=True)
    redaction = verify_trust_operations_assurance_watch_signoff_archive_package(
        _rewrite_zip(signoff_store.archive_zip_path(queue_id), tmp_path / "redaction.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b'\napi_key="sk-test-secret" C:\\Users\\demo\\githubkey.txt\n')),
        strict=True,
    )

    assert _has_blocker(signed_by, "toaws_signoff_payload_hash")
    assert _has_blocker(closeout, "toaws_closeout_integrity") or _has_blocker(closeout, "toaws_signoff_closeout_hash")
    assert _has_blocker(history, "toaws_history_signed_event") or _has_blocker(history, "toaws_manifest_history_hash")
    assert _has_blocker(extra, "toaws_zip_allowed_entries")
    assert _has_blocker(redaction, "toaws_redaction_scan")


def test_assurance_watch_signoff_blocks_failed_or_stale_watch(tmp_path: Path) -> None:
    _fixture, _assurance_store, _run_id, watch_store, payload, queue_id = _watch_fixture(tmp_path, failed_assurance_report=True)
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)
    watch_store.verify_watch_zip(queue_id, {"strict": True, "require_clear": True, **payload})
    signoff_store = _signoff_store(tmp_path, watch_store)

    closeout = signoff_store.refresh_closeout(queue_id, _signoff_payload(payload, watch_store, queue_id))

    assert closeout["status"] == "failed"
    with pytest.raises(TrustOperationsAssuranceWatchSignoffStateError):
        signoff_store.sign(queue_id, {"reason": "Trying to sign failed closeout."})


def _signoff_store(tmp_path: Path, watch_store) -> TrustOperationsAssuranceWatchSignoffStore:
    return TrustOperationsAssuranceWatchSignoffStore(tmp_path / ".musicforge" / "trust-operations-assurance-watch-signoffs", watch_store=watch_store, assurance_store=watch_store.assurance_store, hub_store=watch_store.hub_store)


def _signed_fixture(tmp_path: Path, watch_store, payload: dict, queue_id: str, *, export: bool = False, zip_it: bool = False) -> TrustOperationsAssuranceWatchSignoffStore:
    watch_store.export_watch(queue_id)
    watch_store.build_watch_zip(queue_id)
    watch_store.verify_watch_zip(queue_id, {"strict": True, "require_clear": True, "require_current": True, **payload})
    signoff_store = _signoff_store(tmp_path, watch_store)
    signoff_store.refresh_closeout(queue_id, _signoff_payload(payload, watch_store, queue_id))
    signoff_store.sign(queue_id, {"signed_by": "reviewer", "role": "owner", "reason": "Watch queue clear and verified."})
    if export:
        signoff_store.export_archive(queue_id, _signoff_payload(payload, watch_store, queue_id))
    if zip_it:
        signoff_store.build_archive_zip(queue_id)
    return signoff_store


def _signoff_payload(payload: dict, watch_store, queue_id: str) -> dict:
    return {
        "watch_package_path": watch_store.watch_zip_path(queue_id),
        "watch_verification_report_path": watch_store.verification_report_path(queue_id),
        "hub_package_path": payload["hub_package_path"],
        "hub_verification_report_path": payload["hub_verification_report_path"],
        "continuous_assurance_report_path": payload["assurance_verification_report_path"],
    }


def _resign_archive_docs(docs: dict[str, bytes]) -> None:
    closeout = _read_doc(docs, "watch-closeout.json")
    signoff = _read_doc(docs, "watch-signoff.json")
    queue_summary = _read_doc(docs, "watch-queue-summary.json")
    action_summary = _read_doc(docs, "drift-action-pack-summary.json")
    external = _read_doc(docs, "external-verification-summary.json")
    change_requests = _read_doc(docs, "change-requests.json")
    manifest = _read_doc(docs, "trust-operations-assurance-watch-signoff-manifest.json")
    for name, doc in {
        "watch-closeout.json": closeout,
        "watch-signoff.json": signoff,
        "watch-queue-summary.json": queue_summary,
        "drift-action-pack-summary.json": action_summary,
        "external-verification-summary.json": external,
        "change-requests.json": change_requests,
    }.items():
        doc["integrity_hash"] = watch_signoff_hash(doc)
        docs[name] = _doc_bytes(doc)
        _sync_manifest_file(manifest, name, docs[name])
    history = docs["watch-signoff-history.jsonl"]
    _sync_manifest_file(manifest, "watch-signoff-history.jsonl", history)
    manifest["source"]["closeout_hash"] = closeout.get("integrity_hash")
    manifest["source"]["signoff_hash"] = signoff.get("integrity_hash")
    manifest["source"]["queue_summary_hash"] = queue_summary.get("integrity_hash")
    manifest["source"]["drift_action_pack_summary_hash"] = action_summary.get("integrity_hash")
    manifest["source"]["external_verification_summary_hash"] = external.get("integrity_hash")
    manifest["source"]["change_requests_hash"] = change_requests.get("integrity_hash")
    manifest["integrity_hash"] = watch_signoff_manifest_hash(manifest)
    docs["trust-operations-assurance-watch-signoff-manifest.json"] = _doc_bytes(manifest)


def _tamper_signed_by(docs: dict[str, bytes]) -> None:
    signoff = _read_doc(docs, "watch-signoff.json")
    signoff["signed_by"] = "tampered-reviewer"
    docs["watch-signoff.json"] = _doc_bytes(signoff)
    _resign_archive_docs(docs)


def _tamper_closeout_clear(docs: dict[str, bytes]) -> None:
    closeout = _read_doc(docs, "watch-closeout.json")
    closeout["summary"]["watch_clear"] = False
    docs["watch-closeout.json"] = _doc_bytes(closeout)
    _resign_archive_docs(docs)


def _tamper_history_remove_signed(docs: dict[str, bytes]) -> None:
    docs["watch-signoff-history.jsonl"] = b""
    manifest = _read_doc(docs, "trust-operations-assurance-watch-signoff-manifest.json")
    manifest["source"]["history_hash"] = "0" * 64
    docs["trust-operations-assurance-watch-signoff-manifest.json"] = _doc_bytes(manifest)
    _resign_archive_docs(docs)
