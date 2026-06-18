from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json, write_json
from song_agent.public_trust_center_publication import publication_channel_state_hash
from song_agent.public_trust_center_publication_monitoring import verification_hash
from song_agent.trust_operations_hub import TrustOperationsHubStateError, TrustOperationsHubStore, hub_hash, hub_manifest_hash
from song_agent.trust_operations_hub_verifier import verify_trust_operations_hub_package


def test_trust_operations_hub_roundtrip_signoff_and_reset(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub = store.create_hub({"hub_id": "hub"})
    refreshed = store.refresh_report(hub["hub_id"], fixture.payload)
    report_id = refreshed["hub_report"]["report_id"]
    store.export_report("hub", report_id)
    store.build_zip("hub", report_id)
    verification = store.verify_zip("hub", report_id, {**fixture.verify_payload, "strict": True, "require_ready": True, "require_current": True, "require_publication_monitoring_clean": True})
    signoff = store.signoff("hub", report_id, {"signed_by": "qa", "reason": "Trust hub accepted."})

    signed_mutation = _blocked(lambda: store.export_report("hub", report_id)) and _blocked(lambda: store.build_zip("hub", report_id))
    cr = store.create_change_request("hub", {"change_request_id": "cr-1", "reason": "Refresh signed Hub evidence."})
    approved = store.approve_change_request("hub", cr["change_request_id"])
    reset = store.reset_signoff("hub", approved["change_request_id"])
    reuse = _blocked(lambda: store.reset_signoff("hub", approved["change_request_id"]))

    assert verification["status"] == "passed", verification.get("blockers")
    assert signoff["status"] == "signed"
    assert signed_mutation is True
    assert reset["status"] == "reset"
    assert reuse is True


def test_trust_operations_hub_signed_state_survives_deleted_signoff_file(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub = store.create_hub({"hub_id": "hub"})
    report_id = store.refresh_report(hub["hub_id"], fixture.payload)["hub_report"]["report_id"]
    store.export_report("hub", report_id)
    store.build_zip("hub", report_id)
    store.verify_zip("hub", report_id, {**fixture.verify_payload, "strict": True, "require_ready": True, "require_current": True})
    store.signoff("hub", report_id, {"signed_by": "qa", "reason": "Trust hub accepted."})
    store.signoff_path("hub").unlink()

    assert _blocked(lambda: store.refresh_report("hub", fixture.payload))
    assert _blocked(lambda: store.export_report("hub", report_id))
    assert _blocked(lambda: store.build_zip("hub", report_id))


def test_trust_operations_hub_require_signed_uses_external_sidecar(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub = store.create_hub({"hub_id": "hub"})
    report_id = store.refresh_report(hub["hub_id"], fixture.payload)["hub_report"]["report_id"]
    store.export_report("hub", report_id)
    store.build_zip("hub", report_id)
    zip_path = store.zip_path("hub", report_id)
    pre_sign = store.verify_zip("hub", report_id, {**fixture.verify_payload, "strict": True, "require_ready": True, "require_current": True})
    signoff = store.signoff("hub", report_id, {"signed_by": "qa", "reason": "Trust hub accepted."})

    missing = verify_trust_operations_hub_package(zip_path, strict=True, require_signed=True)
    hub_verification_path = store.verification_report_path("hub", report_id)
    signed = verify_trust_operations_hub_package(zip_path, strict=True, require_signed=True, hub_signoff_path=store.signoff_path("hub"), hub_verification_report_path=hub_verification_path, **fixture.verify_kwargs())
    old_zip = _rewrite_zip(zip_path, tmp_path / "old-zip.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b"\nold zip\n"))
    old_zip_report = verify_trust_operations_hub_package(old_zip, strict=True, require_signed=True, hub_signoff_path=store.signoff_path("hub"), hub_verification_report_path=hub_verification_path, **fixture.verify_kwargs())
    old_verification = read_json(hub_verification_path)
    old_verification["zip_sha256"] = "0" * 64
    old_verification_path = write_json(tmp_path / "old-hub-verification-report.json", old_verification)
    old_verification_report = verify_trust_operations_hub_package(zip_path, strict=True, require_signed=True, hub_signoff_path=store.signoff_path("hub"), hub_verification_report_path=old_verification_path, **fixture.verify_kwargs())
    forged_signoff = read_json(store.signoff_path("hub"))
    forged_signoff["source"]["verification_report_hash"] = "0" * 64
    forged_signoff["integrity_hash"] = hub_hash(forged_signoff)
    forged_signoff_path = write_json(tmp_path / "forged-signoff-verification.json", forged_signoff)
    forged_signoff_report = verify_trust_operations_hub_package(zip_path, strict=True, require_signed=True, hub_signoff_path=forged_signoff_path, hub_verification_report_path=hub_verification_path, **fixture.verify_kwargs())
    old_signoff = dict(signoff)
    old_signoff["source"]["zip_sha256"] = "1" * 64
    old_signoff["integrity_hash"] = hub_hash(old_signoff)
    old_signoff_path = write_json(tmp_path / "old-signoff.json", old_signoff)
    old_signoff_report = verify_trust_operations_hub_package(zip_path, strict=True, require_signed=True, hub_signoff_path=old_signoff_path, hub_verification_report_path=hub_verification_path, **fixture.verify_kwargs())

    assert pre_sign["status"] == "passed"
    assert _has_blocker(missing, "toh_hub_signoff_required")
    assert signed["status"] == "passed", signed.get("blockers")
    assert _has_blocker(old_zip_report, "toh_hub_signoff_zip_sha256")
    assert _has_blocker(old_verification_report, "toh_hub_signoff_verification_report_hash")
    assert _has_blocker(forged_signoff_report, "toh_hub_signoff_verification_report_hash")
    assert _has_blocker(old_signoff_report, "toh_hub_signoff_zip_sha256")


def test_trust_operations_hub_external_revoke_blocks_export_and_verify(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub = store.create_hub({"hub_id": "hub"})
    report_id = store.refresh_report(hub["hub_id"], fixture.payload)["hub_report"]["report_id"]
    store.export_report("hub", report_id)
    store.build_zip("hub", report_id)
    zip_path = store.zip_path("hub", report_id)

    state = read_json(fixture.channel_state_path)
    state["current_publication"]["status"] = "revoked"
    state["publications"][0]["status"] = "revoked"
    state["latest_event_hash"] = "revoked-event"
    state["integrity_hash"] = publication_channel_state_hash(state)
    write_json(fixture.channel_state_path, state)

    current = verify_trust_operations_hub_package(zip_path, strict=True, require_current=True, publication_channel_state_path=fixture.channel_state_path, public_trust_center_verification_path=fixture.ptc_verification_path, publication_monitoring_verification_path=fixture.monitoring_verification_path)

    assert _blocked(lambda: store.export_report("hub", report_id))
    assert _has_blocker(current, "toh_external_channel_state_hash")
    assert _has_blocker(current, "toh_external_channel_state_current")


def test_trust_operations_hub_verifier_rejects_tamper_and_zip_edges(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    source_zip = _ready_zip(tmp_path, fixture)

    matrix = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "matrix.zip", _tamper_matrix_full_resign), strict=True)
    blockers = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "blockers.zip", _clear_blockers_full_resign), strict=True)
    evidence = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "evidence.zip", _tamper_evidence_full_resign), strict=True)
    duplicate = verify_trust_operations_hub_package(_duplicate_zip(source_zip, tmp_path / "duplicate.zip"), strict=True)
    dangerous = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"})), strict=True)
    backslash = verify_trust_operations_hub_package(_backslash_zip(tmp_path / "backslash.zip"), strict=True)
    musicforge = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"})), strict=True)
    nested = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"nested.zip": b"PK\x05\x06" + b"\0" * 18})), strict=True)
    spoof = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_manifest_zip_entries), strict=True)
    redaction = verify_trust_operations_hub_package(_rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b"\napi_key=\"sk-secret-value\" C:\\Users\\demo\\githubkey.txt\n")), strict=True)

    assert _has_blocker(matrix, "toh_readiness_matrix_semantics_match")
    assert _has_blocker(blockers, "toh_blocker_register_matches_readiness")
    assert _has_blocker(evidence, "toh_verification_index_matches_evidence") or _has_blocker(evidence, "toh_readiness_matrix_semantics_match")
    assert _has_blocker(duplicate, "toh_zip_duplicate_entries")
    assert _has_blocker(dangerous, "toh_zip_entry_path_safe")
    assert _has_blocker(backslash, "toh_zip_entry_path_safe")
    assert _has_blocker(musicforge, "toh_zip_no_internal_entries")
    assert _has_blocker(nested, "toh_zip_nested_allowlist")
    assert _has_blocker(spoof, "toh_manifest_zip_entries_reference_only")
    assert _has_blocker(redaction, "toh_redaction_scan")


def _ready_zip(tmp_path: Path, fixture: "_Fixture") -> Path:
    store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations-ready")
    hub = store.create_hub({"hub_id": "hub"})
    report_id = store.refresh_report(hub["hub_id"], fixture.payload)["hub_report"]["report_id"]
    store.export_report("hub", report_id)
    store.build_zip("hub", report_id)
    return store.zip_path("hub", report_id)


class _Fixture:
    def __init__(self, channel_state_path: Path, ptc_verification_path: Path, monitoring_verification_path: Path) -> None:
        self.channel_state_path = channel_state_path
        self.ptc_verification_path = ptc_verification_path
        self.monitoring_verification_path = monitoring_verification_path
        self.payload = {
            "publication_channel_state_path": channel_state_path,
            "public_trust_center_verification_path": ptc_verification_path,
            "publication_monitoring_verification_path": monitoring_verification_path,
        }
        self.verify_payload = {
            "publication_channel_state_path": channel_state_path,
            "public_trust_center_verification_path": ptc_verification_path,
            "publication_monitoring_verification_path": monitoring_verification_path,
        }

    def verify_kwargs(self) -> dict[str, Path]:
        return {
            "publication_channel_state_path": self.channel_state_path,
            "public_trust_center_verification_path": self.ptc_verification_path,
            "publication_monitoring_verification_path": self.monitoring_verification_path,
        }


def _fixture(tmp_path: Path) -> _Fixture:
    root = tmp_path / "external"
    root.mkdir(parents=True, exist_ok=True)
    state = {
        "package_type": "musicforge_public_trust_center_publication_channel_state",
        "center_id": "ptc-default",
        "channel_id": "public-release",
        "current_publication": {"publication_id": "pub-1", "status": "ready", "source_hash": "a" * 64, "report_hash": "b" * 64},
        "publications": [{"publication_id": "pub-1", "status": "ready", "source_hash": "a" * 64, "report_hash": "b" * 64, "manifest_hash": "c" * 64, "zip_sha256": "d" * 64, "latest_event_hash": "e" * 64}],
        "events": [{"event_id": "evt-1", "event_hash": "e" * 64}],
        "event_count": 1,
        "latest_event_hash": "e" * 64,
    }
    state["integrity_hash"] = publication_channel_state_hash(state)
    state_path = write_json(root / "publication-channel-state.json", state)
    ptc = {"package_type": "musicforge_public_trust_center_verification", "status": "passed", "zip_sha256": "1" * 64, "manifest_hash": "2" * 64, "source_hash": "3" * 64, "summary": {"readiness": "ready"}, "checks": []}
    ptc_path = write_json(root / "ptc-verification-report.json", ptc)
    monitoring = {"package_type": "musicforge_public_trust_center_publication_monitoring_verification", "status": "passed", "zip_sha256": "4" * 64, "manifest_hash": "5" * 64, "source_hash": "6" * 64, "summary": {"status": "passed", "critical_incidents": 0, "open_incidents": 0}, "checks": []}
    monitoring_path = write_json(root / "monitoring-verification-report.json", monitoring)
    assert verification_hash(read_json(ptc_path))
    assert verification_hash(read_json(monitoring_path))
    return _Fixture(state_path, ptc_path, monitoring_path)


def _blocked(fn) -> bool:
    with pytest.raises(TrustOperationsHubStateError):
        fn()
    return True


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
            data = src.read(info)
            dst.writestr(info.filename, data)
        dst.writestr("hub-report.json", src.read("hub-report.json"))
    return target_zip


def _backslash_zip(target_zip: Path) -> Path:
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra/name.txt", b"x")
    data = target_zip.read_bytes().replace(b"extra/name.txt", b"extra\\name.txt")
    target_zip.write_bytes(data)
    return target_zip


def _tamper_matrix_full_resign(docs: dict[str, bytes]) -> None:
    matrix = _read_doc(docs, "readiness-matrix.json")
    for index, row in enumerate(matrix.get("rows", [])):
        if isinstance(row, dict) and index == 0:
            row["status"] = "blocked"
            row["summary"] = "Forged blocker inserted without matching evidence."
    matrix["summary"] = {"row_count": len(matrix.get("rows", [])), "ready_count": max(0, len(matrix.get("rows", [])) - 1), "blocked_count": 1, "warning_count": 0, "stale_count": 0, "missing_count": 0}
    matrix["integrity_hash"] = hub_hash(matrix)
    docs["readiness-matrix.json"] = _doc_bytes(matrix)
    _resign_hub_docs(docs)


def _clear_blockers_full_resign(docs: dict[str, bytes]) -> None:
    matrix = _read_doc(docs, "readiness-matrix.json")
    for index, row in enumerate(matrix.get("rows", [])):
        if isinstance(row, dict) and index == 0:
            row["status"] = "blocked"
            row["summary"] = "Forged blocker inserted and then hidden."
    matrix["summary"] = {"row_count": len(matrix.get("rows", [])), "ready_count": max(0, len(matrix.get("rows", [])) - 1), "blocked_count": 1, "warning_count": 0, "stale_count": 0, "missing_count": 0}
    matrix["integrity_hash"] = hub_hash(matrix)
    docs["readiness-matrix.json"] = _doc_bytes(matrix)
    blockers = _read_doc(docs, "blocker-register.json")
    blockers["blockers"] = []
    blockers["summary"] = {"blocker_count": 0, "critical_count": 0, "high_count": 0}
    blockers["integrity_hash"] = hub_hash(blockers)
    docs["blocker-register.json"] = _doc_bytes(blockers)
    _resign_hub_docs(docs)


def _tamper_evidence_full_resign(docs: dict[str, bytes]) -> None:
    evidence = _read_doc(docs, "evidence-binding-index.json")
    for row in evidence.get("evidence", []):
        if isinstance(row, dict) and row.get("component_type") == "publication_monitoring_verification":
            row["status"] = "failed"
            row.setdefault("summary", {})["critical_incidents"] = 1
    evidence["summary"] = {"evidence_count": len(evidence.get("evidence", [])), "failed_count": 1, "stale_count": 0}
    evidence["integrity_hash"] = hub_hash(evidence)
    docs["evidence-binding-index.json"] = _doc_bytes(evidence)
    _resign_hub_docs(docs)


def _spoof_manifest_zip_entries(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "trust-operations-hub-manifest.json")
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = hub_manifest_hash(manifest)
    docs["trust-operations-hub-manifest.json"] = _doc_bytes(manifest)


def _resign_hub_docs(docs: dict[str, bytes]) -> None:
    report = _read_doc(docs, "hub-report.json")
    matrix = _read_doc(docs, "readiness-matrix.json")
    blockers = _read_doc(docs, "blocker-register.json")
    actions = _read_doc(docs, "manual-action-queue.json")
    evidence = _read_doc(docs, "evidence-binding-index.json")
    verifications = _read_doc(docs, "verification-summary-index.json")
    source_state = _read_doc(docs, "source-state.json")
    signoff = _read_doc(docs, "signoff-summary.json")
    checksum = _read_doc(docs, "checksum/SHA256SUMS.json")
    manifest = _read_doc(docs, "trust-operations-hub-manifest.json")
    report["source"] = {
        "hub_hash": report.get("source", {}).get("hub_hash"),
        "source_state_hash": source_state.get("integrity_hash"),
        "readiness_matrix_hash": matrix.get("integrity_hash"),
        "blocker_register_hash": blockers.get("integrity_hash"),
        "manual_action_queue_hash": actions.get("integrity_hash"),
        "evidence_binding_index_hash": evidence.get("integrity_hash"),
        "verification_summary_index_hash": verifications.get("integrity_hash"),
    }
    report["readiness"] = {"overall_status": report.get("status"), **matrix.get("summary", {})}
    report["status"] = "ready" if matrix.get("summary", {}).get("blocked_count") == 0 and matrix.get("summary", {}).get("missing_count") == 0 and matrix.get("summary", {}).get("stale_count") == 0 and blockers.get("summary", {}).get("blocker_count") == 0 else "blocked"
    report["integrity_hash"] = hub_hash(report)
    docs["hub-report.json"] = _doc_bytes(report)
    manifest["source"] = {
        "hub_report_hash": report.get("integrity_hash"),
        "readiness_matrix_hash": matrix.get("integrity_hash"),
        "blocker_register_hash": blockers.get("integrity_hash"),
        "manual_action_queue_hash": actions.get("integrity_hash"),
        "evidence_binding_index_hash": evidence.get("integrity_hash"),
        "verification_summary_index_hash": verifications.get("integrity_hash"),
        "source_state_hash": source_state.get("integrity_hash"),
        "signoff_summary_hash": signoff.get("integrity_hash"),
    }
    for path in ("hub-report.json", "readiness-matrix.json", "blocker-register.json", "manual-action-queue.json", "evidence-binding-index.json"):
        _sync_file_record(checksum, path, docs[path])
    checksum["integrity_hash"] = hub_hash(checksum)
    docs["checksum/SHA256SUMS.json"] = _doc_bytes(checksum)
    _sync_manifest_file(manifest, "checksum/SHA256SUMS.json", docs["checksum/SHA256SUMS.json"])
    docs["checksum/SHA256SUMS.txt"] = ("\n".join(f"{item.get('sha256')}  {item.get('path')}" for item in checksum.get("files", []) if isinstance(item, dict)) + "\n").encode("utf-8")
    _sync_manifest_file(manifest, "checksum/SHA256SUMS.txt", docs["checksum/SHA256SUMS.txt"])
    for path in ("hub-report.json", "readiness-matrix.json", "blocker-register.json", "manual-action-queue.json", "evidence-binding-index.json"):
        _sync_manifest_file(manifest, path, docs[path])
    manifest["integrity_hash"] = hub_manifest_hash(manifest)
    docs["trust-operations-hub-manifest.json"] = _doc_bytes(manifest)


def _sync_file_record(payload: dict, path: str, data: bytes) -> None:
    for item in payload.get("files", []) if isinstance(payload.get("files"), list) else []:
        if isinstance(item, dict) and item.get("path") == path:
            item["size_bytes"] = len(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()


def _sync_manifest_file(manifest: dict, path: str, data: bytes) -> None:
    for item in manifest.get("files", []) if isinstance(manifest.get("files"), list) else []:
        if isinstance(item, dict) and item.get("path") == path:
            item["size_bytes"] = len(data)
            item["sha256"] = hashlib.sha256(data).hexdigest()


def _read_doc(docs: dict[str, bytes], path: str) -> dict:
    return json.loads(docs[path].decode("utf-8"))


def _doc_bytes(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
