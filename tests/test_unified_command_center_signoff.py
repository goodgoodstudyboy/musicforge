from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.release_checks import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_command_center import UnifiedCommandCenterStateError, UnifiedCommandCenterStore
from song_agent.unified_command_center_archive_verifier import verify_unified_command_center_archive_package
from song_agent.unified_command_center_handoff import UnifiedCommandCenterHandoffStore
from song_agent.unified_command_center_handoff_verifier import verify_unified_command_center_handoff_package
from song_agent.unified_command_center_signoff import UnifiedCommandCenterSignoffStateError, UnifiedCommandCenterSignoffStore


def _release_check_report(path: Path) -> Path:
    payload = {
        "ok": True,
        "summary": {"total": 1, "passed": 1, "failed": 0},
        "results": [{"check_id": "synthetic.passed", "status": "passed"}],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _store(tmp_path: Path) -> UnifiedCommandCenterStore:
    return UnifiedCommandCenterStore(root=tmp_path / ".musicforge" / "unified-command-centers")


def _ready_center(tmp_path: Path) -> tuple[UnifiedCommandCenterStore, str, dict]:
    release_check = _release_check_report(tmp_path / "release-check.json")
    store = _store(tmp_path)
    center = store.create(
        {
            "center_id": "ucc-test",
            "requirements": {
                "audio-command-center": False,
                "trust-operations-hub": False,
                "public-trust-center": False,
                "ga-readiness": False,
                "release-check": True,
            },
        }
    )
    evidence = {"release-check": {"report": release_check}}
    store.refresh(center["center_id"], evidence)
    store.build_zip(center["center_id"], evidence)
    verification = store.verify_zip(center["center_id"], evidence=evidence, strict=True, require_ready=True)
    assert verification["status"] == "passed"
    return store, center["center_id"], evidence


def test_unified_command_center_signoff_archive_handoff_lifecycle(tmp_path: Path) -> None:
    store, center_id, evidence = _ready_center(tmp_path)
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)

    signoff = signoff_store.signoff(center_id, {"signed_by": "release lead", "reason": "ready for handoff"})
    assert signoff["status"] == "signed"

    for action in (
        lambda: store.refresh(center_id, evidence),
        lambda: store.run_safe(center_id, evidence),
        lambda: store.export_package(center_id, evidence),
        lambda: store.build_zip(center_id, evidence),
    ):
        with pytest.raises(UnifiedCommandCenterStateError):
            action()

    archive_zip = signoff_store.build_archive_zip(center_id)
    archive_report = signoff_store.verify_archive(center_id)
    handoff_zip = handoff_store.build_handoff_zip(center_id)
    handoff_report = handoff_store.verify_handoff(center_id)

    assert Path(archive_zip["zip_path"]).exists()
    assert archive_report["status"] == "passed"
    assert Path(handoff_zip["zip_path"]).exists()
    assert handoff_report["status"] == "passed"


def test_unified_command_center_delete_signoff_file_does_not_reopen(tmp_path: Path) -> None:
    store, center_id, evidence = _ready_center(tmp_path)
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    signoff_store.signoff(center_id, {"signed_by": "release lead"})
    signoff_store.signoff_path(center_id).unlink()

    with pytest.raises(UnifiedCommandCenterStateError):
        store.refresh(center_id, evidence)

    with pytest.raises(UnifiedCommandCenterStateError):
        signoff_store.signoff(center_id, {"signed_by": "second signer"})


def test_unified_command_center_reset_requires_single_use_approved_change_request(tmp_path: Path) -> None:
    store, center_id, evidence = _ready_center(tmp_path)
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    signoff_store.signoff(center_id, {"signed_by": "release lead"})

    draft = signoff_store.create_change_request(center_id, {"reason": "Refresh final evidence"})
    with pytest.raises(UnifiedCommandCenterSignoffStateError):
        signoff_store.reset_signoff(center_id, draft["change_request_id"], {"reason": "not approved"})

    approved = signoff_store.approve_change_request(center_id, draft["change_request_id"], {"approved_by": "reviewer"})
    reset = signoff_store.reset_signoff(center_id, approved["change_request_id"], {"reason": "approved reset"})
    assert reset["status"] == "reset"
    assert store.refresh(center_id, evidence)["status"] == "ready"

    with pytest.raises(Exception):
        signoff_store.reset_signoff(center_id, approved["change_request_id"], {"reason": "reuse"})


def test_unified_command_center_archive_and_handoff_reject_declared_extra(tmp_path: Path) -> None:
    store, center_id, _evidence = _ready_center(tmp_path)
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    signoff_store.signoff(center_id, {"signed_by": "release lead"})
    archive_zip = signoff_store.build_archive_zip(center_id)
    signoff_store.verify_archive(center_id)
    handoff_zip = handoff_store.build_handoff_zip(center_id)
    handoff_store.verify_handoff(center_id)

    archive_tampered = tmp_path / "archive-extra.zip"
    handoff_tampered = tmp_path / "handoff-extra.zip"
    _v76_rewrite_zip(Path(archive_zip["zip_path"]), archive_tampered, _add_archive_extra)
    _v76_rewrite_zip(Path(handoff_zip["zip_path"]), handoff_tampered, _add_handoff_extra)

    archive_result = verify_unified_command_center_archive_package(
        archive_tampered,
        strict=True,
        require_signed=True,
        require_current_ucc=True,
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
        signoff_binding_path=signoff_store.signoff_binding_path(center_id),
    )
    handoff_result = verify_unified_command_center_handoff_package(
        handoff_tampered,
        strict=True,
        require_archive=True,
        archive_zip_path=signoff_store.archive_zip_path(center_id),
        archive_verification_report_path=signoff_store.archive_verification_report_path(center_id),
    )

    assert archive_result["status"] == "failed"
    assert "ucc_archive_allowed_entries" in archive_result["blockers"]
    assert handoff_result["status"] == "failed"
    assert "ucc_handoff_allowed_entries" in handoff_result["blockers"]


def test_unified_command_center_archive_rejects_signoff_full_resign(tmp_path: Path) -> None:
    store, center_id, _evidence = _ready_center(tmp_path)
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    signoff_store.signoff(center_id, {"signed_by": "original signer"})
    archive_zip = signoff_store.build_archive_zip(center_id)
    tampered = tmp_path / "archive-forged-signer.zip"
    _v76_rewrite_zip(Path(archive_zip["zip_path"]), tampered, _forge_archive_signer)

    result = verify_unified_command_center_archive_package(
        tampered,
        strict=True,
        require_signed=True,
        require_current_ucc=True,
        command_center_zip_path=store.zip_path(center_id),
        command_center_verification_report_path=store.verification_report_path(center_id),
    )

    assert result["status"] == "failed"
    assert "ucc_archive_signoff_binding_signed_by" in result["blockers"]


def _add_archive_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    return _add_declared_extra(entries, "manifest.json", "docs/UNTRUSTED-INSTRUCTIONS.txt")


def _add_handoff_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    return _add_declared_extra(entries, "manifest.json", "docs/UNTRUSTED-INSTRUCTIONS.txt")


def _add_declared_extra(entries: dict[str, bytes], manifest_name: str, extra_name: str) -> dict[str, bytes]:
    entries[extra_name] = b"unexpected\n"
    manifest = json.loads(entries[manifest_name].decode("utf-8"))
    files = [row for row in manifest.get("files", []) if isinstance(row, dict)]
    files.append({"path": extra_name, "size_bytes": len(entries[extra_name]), "sha256": _sha256_bytes(entries[extra_name])})
    manifest["files"] = sorted(files, key=lambda row: row.get("path", ""))
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries[manifest_name] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _forge_archive_signer(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged signer"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    history_rows = []
    previous = ""
    for line in entries["signoff-history.jsonl"].decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "ucc_signoff_created":
            event["signed_by"] = "forged signer"
            event["signoff_hash"] = signoff["integrity_hash"]
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        history_rows.append(event)
    entries["signoff-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in history_rows) + "\n").encode("utf-8")

    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest.setdefault("source", {})["signoff_hash"] = signoff["integrity_hash"]
    _sync_manifest_file(manifest, "signoff.json", entries["signoff.json"])
    _sync_manifest_file(manifest, "signoff-history.jsonl", entries["signoff-history.jsonl"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    for row in manifest.get("files", []):
        if isinstance(row, dict) and row.get("path") == rel:
            row["size_bytes"] = len(data)
            row["sha256"] = _sha256_bytes(data)
            return
    raise AssertionError(f"manifest row missing: {rel}")


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
