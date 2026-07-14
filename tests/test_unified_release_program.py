from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from song_agent.platform.persistence.program import write_program_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program import UnifiedReleaseProgramStateError, UnifiedReleaseProgramStore, write_external_evidence_manifest
from song_agent.unified_release_program_verifier import verify_unified_release_program_package
from tests.test_unified_command_center_release_train_handoff import _handoff_fixture, _verify_payload


def _signed_handoff_fixture(tmp_path: Path) -> dict:
    handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload = _handoff_fixture(tmp_path)
    handoff_store.refresh_report(train_id, handoff_id, payload)
    handoff_store.signoff(train_id, handoff_id, {**payload, "signed_by": "handoff chair"})
    zipped = handoff_store.build_zip(train_id, handoff_id)
    verify_payload = _verify_payload(handoff_store, handoff_id, train_store, change_store, lifecycle_store, train_id, manifest_path, payload)
    verification = handoff_store.verify_package(train_id, handoff_id, verify_payload)
    assert verification["status"] == "passed", verification.get("blockers")
    return {
        "train_id": train_id,
        "handoff_id": handoff_id,
        "handoff_zip": Path(zipped["zip_path"]),
        "handoff_verification_report": handoff_store.verification_report_path(train_id, handoff_id),
        "handoff_signoff_binding": handoff_store.signoff_binding_path(train_id, handoff_id),
    }


def _program_with_handoff(tmp_path: Path) -> tuple[UnifiedReleaseProgramStore, str, Path, dict]:
    handoff = _signed_handoff_fixture(tmp_path)
    store = UnifiedReleaseProgramStore(root=tmp_path / ".musicforge" / "unified-release-programs")
    program = store.create_program({"program_id": "urp-test", "name": "Test Program"})
    item = store.add_train_item(
        program["program_id"],
        {
            "item_id": "train-a",
            "train_id": handoff["train_id"],
            "handoff_id": handoff["handoff_id"],
            "type": "required",
            "lane": "audio",
            "handoff_zip": handoff["handoff_zip"],
            "handoff_verification_report": handoff["handoff_verification_report"],
            "handoff_signoff_binding": handoff["handoff_signoff_binding"],
        },
    )
    manifest_path = tmp_path / "program-external-evidence.json"
    write_external_evidence_manifest(
        manifest_path,
        program_id=program["program_id"],
        items=[
            {
                "item_id": item["item_id"],
                "train_id": handoff["train_id"],
                "handoff_id": handoff["handoff_id"],
                "handoff_zip": str(handoff["handoff_zip"]),
                "handoff_verification_report": str(handoff["handoff_verification_report"]),
                "handoff_signoff_binding": str(handoff["handoff_signoff_binding"]),
            }
        ],
    )
    return store, program["program_id"], manifest_path, handoff


def test_unified_release_program_signoff_and_verify(tmp_path: Path) -> None:
    store, program_id, manifest_path, _handoff = _program_with_handoff(tmp_path)

    report = store.refresh_report(program_id, {"external_evidence_manifest": manifest_path})
    signoff = store.signoff(program_id, {"external_evidence_manifest": manifest_path, "signed_by": "program owner", "role": "release_owner"})
    zipped = store.build_zip(program_id)
    verified = verify_unified_release_program_package(
        zipped["zip_path"],
        strict=True,
        require_current=True,
        require_signed=True,
        external_evidence_manifest_path=manifest_path,
        program_signoff_binding_path=store.signoff_binding_path(program_id),
    )

    assert report["status"] == "ready", report.get("summary")
    assert signoff["status"] == "signed"
    assert verified["status"] == "passed", verified.get("blockers")
    with pytest.raises(UnifiedReleaseProgramStateError):
        store.refresh_report(program_id, {"external_evidence_manifest": manifest_path})
    store.signoff_path(program_id).unlink()
    with pytest.raises(UnifiedReleaseProgramStateError):
        store.add_train_item(program_id, {"item_id": "other", "train_id": "uct-other", "handoff_id": "rth-other"})


def test_unified_release_program_blocks_dependency_cycle(tmp_path: Path) -> None:
    store, program_id, manifest_path, handoff = _program_with_handoff(tmp_path)
    second = store.add_train_item(
        program_id,
        {
            "item_id": "train-b",
            "train_id": f"{handoff['train_id']}-b",
            "handoff_id": f"{handoff['handoff_id']}-b",
            "type": "required",
            "depends_on": ["train-a"],
            "handoff_zip": handoff["handoff_zip"],
            "handoff_verification_report": handoff["handoff_verification_report"],
            "handoff_signoff_binding": handoff["handoff_signoff_binding"],
            "allow_duplicate_train": True,
        },
    )
    items = read_json(store.items_path(program_id))
    for row in items["items"]:
        if row["item_id"] == "train-a":
            row["depends_on"] = [second["item_id"]]
    items["integrity_hash"] = stable_hash({key: value for key, value in items.items() if key != "integrity_hash"})
    write_program_json(store.items_path(program_id), items)
    manifest = read_json(manifest_path)
    manifest["items"].append(
        {
            "item_id": second["item_id"],
            "train_id": second["train_id"],
            "handoff_id": second["handoff_id"],
            "evidence_type": "release_train_handoff",
            "handoff_zip": str(handoff["handoff_zip"]),
            "handoff_verification_report": str(handoff["handoff_verification_report"]),
            "handoff_signoff_binding": str(handoff["handoff_signoff_binding"]),
        }
    )
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    report = store.refresh_report(program_id, {"external_evidence_manifest": manifest_path})

    assert report["status"] == "blocked"
    with pytest.raises(UnifiedReleaseProgramStateError):
        store.signoff(program_id, {"external_evidence_manifest": manifest_path})


def test_unified_release_program_blocks_deferred_only_signoff(tmp_path: Path) -> None:
    store = UnifiedReleaseProgramStore(root=tmp_path / ".musicforge" / "unified-release-programs")
    program = store.create_program({"program_id": "urp-deferred", "name": "Deferred only Program"})
    store.add_train_item(
        program["program_id"],
        {
            "item_id": "train-deferred",
            "train_id": "uct-deferred",
            "handoff_id": "rth-deferred",
            "type": "deferred",
            "defer_reason": "not part of this wave",
        },
    )

    report = store.refresh_report(program["program_id"], {})

    assert report["status"] == "blocked"
    assert report["summary"]["ready_count"] == 0
    assert report["summary"]["readiness"] == "blocked"
    rows = read_json(store.readiness_path(program["program_id"]))["rows"]
    assert any(row["check_id"] == "program_has_verified_required_handoff" and row["status"] == "failed" for row in rows)
    with pytest.raises(UnifiedReleaseProgramStateError):
        store.signoff(program["program_id"], {"signed_by": "program owner"})


def test_unified_release_program_rejects_declared_extra_and_full_resign(tmp_path: Path) -> None:
    store, program_id, manifest_path, _handoff = _program_with_handoff(tmp_path)
    store.signoff(program_id, {"external_evidence_manifest": manifest_path, "signed_by": "original program signer", "role": "release_owner"})
    zipped = store.build_zip(program_id)

    extra_zip = tmp_path / "program-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_package(extra_zip, strict=True)

    forged_zip = tmp_path / "program-forged-signer.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _full_resign_program_signer)
    forged = verify_unified_release_program_package(
        forged_zip,
        strict=True,
        require_current=True,
        require_signed=True,
        external_evidence_manifest_path=manifest_path,
        program_signoff_binding_path=store.signoff_binding_path(program_id),
    )
    missing_binding = verify_unified_release_program_package(
        Path(zipped["zip_path"]),
        strict=True,
        require_current=True,
        require_signed=True,
        external_evidence_manifest_path=manifest_path,
    )

    assert extra["status"] == "failed"
    assert "urp_allowed_entries" in extra["blockers"]
    assert forged["status"] == "failed"
    assert "urp_external_signoff_binding_hash" in forged["blockers"]
    assert missing_binding["status"] == "failed"
    assert "urp_external_signoff_binding_required" in missing_binding["blockers"]


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra] = b"unexpected program file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": extra, "size_bytes": len(entries[extra]), "sha256": _sha256_bytes(entries[extra])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _full_resign_program_signer(entries: dict[str, bytes]) -> dict[str, bytes]:
    signoff = json.loads(entries["program-signoff.json"].decode("utf-8"))
    signoff["signed_by"] = "forged program signer"
    signoff["role"] = "forged_role"
    signoff["reason"] = "forged program reason"
    signoff["payload_hash"] = stable_hash({key: value for key, value in signoff.items() if key not in {"payload_hash", "integrity_hash"}})
    signoff["integrity_hash"] = stable_hash({key: value for key, value in signoff.items() if key != "integrity_hash"})
    entries["program-signoff.json"] = json.dumps(signoff, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    history_rows = []
    previous = ""
    event_hash = ""
    for line in entries["program-history.jsonl"].decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "unified_release_program_signoff_created":
            event["signed_by"] = signoff["signed_by"]
            event["role"] = signoff["role"]
            event["reason"] = signoff["reason"]
            event["signoff_hash"] = signoff["integrity_hash"]
            event["signoff_payload_hash"] = signoff["payload_hash"]
            event["program_report_hash"] = signoff["program_report_hash"]
        event["previous_event_hash"] = previous
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        previous = event["event_hash"]
        event_hash = event["event_hash"]
        history_rows.append(event)
    entries["program-history.jsonl"] = ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in history_rows) + "\n").encode("utf-8")
    binding = json.loads(entries["program-signoff-binding-summary.json"].decode("utf-8"))
    binding["signed_by"] = signoff["signed_by"]
    binding["role"] = signoff["role"]
    binding["reason"] = signoff["reason"]
    binding["signoff_hash"] = signoff["integrity_hash"]
    binding["signoff_payload_hash"] = signoff["payload_hash"]
    binding["latest_history_event_hash"] = event_hash
    binding["integrity_hash"] = stable_hash({key: value for key, value in binding.items() if key != "integrity_hash"})
    entries["program-signoff-binding-summary.json"] = json.dumps(binding, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["source"]["program_signoff_hash"] = signoff["integrity_hash"]
    manifest["source"]["program_signoff_binding_hash"] = binding["integrity_hash"]
    _sync_manifest_file(manifest, "program-signoff.json", entries["program-signoff.json"])
    _sync_manifest_file(manifest, "program-history.jsonl", entries["program-history.jsonl"])
    _sync_manifest_file(manifest, "program-signoff-binding-summary.json", entries["program-signoff-binding-summary.json"])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _sync_manifest_file(manifest: dict, rel: str, data: bytes) -> None:
    files = [row for row in manifest.get("files", []) if row.get("path") != rel]
    files.append({"path": rel, "size_bytes": len(data), "sha256": _sha256_bytes(data)})
    manifest["files"] = sorted(files, key=lambda row: row.get("path") or "")


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
