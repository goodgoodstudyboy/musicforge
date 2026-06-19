from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from song_agent.trust_operations_hub import TrustOperationsHubStateError, TrustOperationsHubStore
from song_agent.trust_operations_hub_runbook import TrustOperationsHubRunbookStateError, TrustOperationsHubRunbookStore, runbook_hash
from song_agent.trust_operations_hub_runbook_verifier import verify_trust_operations_hub_runbook_package
from tests.test_trust_operations_hub import _delivery_fixture, _fixture


def test_trust_operations_hub_runbook_safe_actions_and_verify(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    delivery = _delivery_fixture(tmp_path)
    hub_store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub_store.create_hub({"hub_id": "hub"})
    report_id = hub_store.refresh_report("hub", {**fixture.payload, **delivery.payload})["hub_report"]["report_id"]
    runbook_store = TrustOperationsHubRunbookStore(hub_store=hub_store, root=tmp_path / ".musicforge" / "trust-operations-runbooks")

    runbook = runbook_store.create_runbook("hub", report_id)
    result = runbook_store.run_safe_actions("hub", runbook["runbook_id"])
    manifest = runbook_store.export_runbook("hub", runbook["runbook_id"])
    runbook_store.build_zip("hub", runbook["runbook_id"])
    verification = verify_trust_operations_hub_runbook_package(runbook_store.zip_path("hub", runbook["runbook_id"]), strict=True, require_completed=True, require_no_blocked=True)

    assert result["summary"]["completed_count"] == 3
    assert result["summary"]["blocked_count"] == 0
    assert manifest["package_type"] == "musicforge_trust_operations_hub_runbook_manifest"
    assert verification["status"] == "passed", verification.get("blockers")


def test_trust_operations_hub_runbook_blocks_signed_hub(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    hub_store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub_store.create_hub({"hub_id": "hub"})
    report_id = hub_store.refresh_report("hub", fixture.payload)["hub_report"]["report_id"]
    hub_store.export_report("hub", report_id)
    hub_store.build_zip("hub", report_id)
    hub_store.verify_zip("hub", report_id, {**fixture.verify_payload, "strict": True, "require_ready": True, "require_current": True})
    hub_store.signoff("hub", report_id, {"signed_by": "qa", "reason": "Trust hub accepted."})
    runbook_store = TrustOperationsHubRunbookStore(hub_store=hub_store, root=tmp_path / ".musicforge" / "trust-operations-runbooks")

    with pytest.raises(TrustOperationsHubRunbookStateError):
        runbook_store.create_runbook("hub", report_id)


def test_trust_operations_hub_runbook_verifier_rejects_result_resign(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    hub_store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub_store.create_hub({"hub_id": "hub"})
    report_id = hub_store.refresh_report("hub", fixture.payload)["hub_report"]["report_id"]
    runbook_store = TrustOperationsHubRunbookStore(hub_store=hub_store, root=tmp_path / ".musicforge" / "trust-operations-runbooks")
    runbook = runbook_store.create_runbook("hub", report_id)
    runbook_store.run_safe_actions("hub", runbook["runbook_id"])
    runbook_store.export_runbook("hub", runbook["runbook_id"])
    runbook_store.build_zip("hub", runbook["runbook_id"])

    forged = verify_trust_operations_hub_runbook_package(
        _rewrite_zip(runbook_store.zip_path("hub", runbook["runbook_id"]), tmp_path / "result-resign.zip", _tamper_result_full_resign),
        strict=True,
        require_completed=True,
        require_no_blocked=True,
    )
    duplicate = verify_trust_operations_hub_runbook_package(_duplicate_zip(runbook_store.zip_path("hub", runbook["runbook_id"]), tmp_path / "duplicate.zip"), strict=True)
    dangerous = verify_trust_operations_hub_runbook_package(_rewrite_zip(runbook_store.zip_path("hub", runbook["runbook_id"]), tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"})), strict=True)

    assert _has_blocker(forged, "tohr_safe_results_match_events")
    assert _has_blocker(duplicate, "tohr_zip_duplicate_entries")
    assert _has_blocker(dangerous, "tohr_zip_entry_path_safe")


def test_trust_operations_hub_runbook_source_stale_blocks_export(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    hub_store = TrustOperationsHubStore(tmp_path / ".musicforge" / "trust-operations")
    hub_store.create_hub({"hub_id": "hub"})
    report_id = hub_store.refresh_report("hub", fixture.payload)["hub_report"]["report_id"]
    runbook_store = TrustOperationsHubRunbookStore(hub_store=hub_store, root=tmp_path / ".musicforge" / "trust-operations-runbooks")
    runbook = runbook_store.create_runbook("hub", report_id)
    state = json.loads(fixture.channel_state_path.read_text(encoding="utf-8"))
    state["current_publication"]["status"] = "revoked"
    fixture.channel_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises((TrustOperationsHubRunbookStateError, TrustOperationsHubStateError)):
        runbook_store.export_runbook("hub", runbook["runbook_id"])


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
        dst.writestr("runbook.json", src.read("runbook.json"))
    return target_zip


def _tamper_result_full_resign(docs: dict[str, bytes]) -> None:
    result = _read_doc(docs, "runbook-result.json")
    for item in result.get("results", []):
        if isinstance(item, dict) and item.get("status") == "completed":
            item["status"] = "manual_required"
            item["reason"] = "Forged into manual state."
            break
    result["status"] = "completed_with_manual_actions"
    result["summary"] = {
        "result_count": len(result.get("results", [])),
        "completed_count": sum(1 for item in result.get("results", []) if isinstance(item, dict) and item.get("status") == "completed"),
        "blocked_count": 0,
        "manual_required_count": sum(1 for item in result.get("results", []) if isinstance(item, dict) and item.get("status") == "manual_required"),
    }
    result["integrity_hash"] = runbook_hash(result)
    docs["runbook-result.json"] = _doc_bytes(result)
    manifest = _read_doc(docs, "trust-operations-hub-runbook-manifest.json")
    manifest["source"]["result_hash"] = result["integrity_hash"]
    _sync_manifest_file(manifest, "runbook-result.json", docs["runbook-result.json"])
    checksum = _read_doc(docs, "checksum/SHA256SUMS.json")
    _sync_file_record(checksum, "runbook-result.json", docs["runbook-result.json"])
    checksum["integrity_hash"] = runbook_hash(checksum)
    docs["checksum/SHA256SUMS.json"] = _doc_bytes(checksum)
    _sync_manifest_file(manifest, "checksum/SHA256SUMS.json", docs["checksum/SHA256SUMS.json"])
    docs["checksum/SHA256SUMS.txt"] = ("\n".join(f"{item.get('sha256')}  {item.get('path')}" for item in checksum.get("files", []) if isinstance(item, dict)) + "\n").encode("utf-8")
    _sync_manifest_file(manifest, "checksum/SHA256SUMS.txt", docs["checksum/SHA256SUMS.txt"])
    manifest["integrity_hash"] = runbook_hash(manifest)
    docs["trust-operations-hub-runbook-manifest.json"] = _doc_bytes(manifest)


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
