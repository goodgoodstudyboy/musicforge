from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from song_agent.projectio import read_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_distribution import (
    UnifiedReleaseProgramContinuityDistributionStateError,
    UnifiedReleaseProgramContinuityDistributionStore,
)
from song_agent.unified_release_program_continuity_distribution_verifier import verify_unified_release_program_continuity_distribution_package
from tests.test_unified_release_program_continuity import _prepared_continuity
from tests.test_unified_release_program_vault import _sha256_bytes


def _prepared_kit(tmp_path: Path):
    program_store, ops, continuity, program_id = _prepared_continuity(tmp_path)
    continuity.signoff_continuity(program_id, {"signed_by": "continuity lead"})
    continuity.build_archive_zip(program_id)
    continuity.verify_archive_zip(program_id, {"deep_restore": True, "require_signed": True, "require_current_vault_operations": True})
    distribution = UnifiedReleaseProgramContinuityDistributionStore(program_store)
    distribution.prepare_kit(program_id)
    zipped = distribution.build_kit_zip(program_id)
    report = distribution.verify_kit(program_id, {"deep": True})
    assert report["status"] == "passed", report.get("blockers")
    return program_store, ops, continuity, distribution, program_id, zipped


def test_unified_release_program_continuity_distribution_happy_path(tmp_path: Path) -> None:
    _program_store, _ops, _continuity, distribution, program_id, zipped = _prepared_kit(tmp_path)

    report = verify_unified_release_program_continuity_distribution_package(zipped["zip_path"], strict=True, deep=True)
    gate = distribution.gate(program_id, required=True)

    assert report["status"] == "passed", report.get("blockers")
    assert gate["status"] == "passed", gate


def test_unified_release_program_continuity_distribution_rejects_declared_extra_and_extra_nested_zip(tmp_path: Path) -> None:
    _program_store, _ops, _continuity, _distribution, _program_id, zipped = _prepared_kit(tmp_path)

    declared_extra_zip = tmp_path / "kit-declared-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), declared_extra_zip, _add_declared_extra)
    declared_extra = verify_unified_release_program_continuity_distribution_package(declared_extra_zip, strict=True, deep=True)
    assert declared_extra["status"] == "failed"
    assert "urpcdk_allowed_entries" in declared_extra["blockers"]
    assert "urpcdk_deep_preflight" in declared_extra["blockers"]

    extra_nested_zip = tmp_path / "kit-extra-nested.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_nested_zip, _add_extra_nested_zip)
    nested = verify_unified_release_program_continuity_distribution_package(extra_nested_zip, strict=True, deep=True)
    assert nested["status"] == "failed"
    assert "urpcdk_nested_zip_allowlist" in nested["blockers"]


def test_unified_release_program_continuity_distribution_rejects_backslash_musicforge_and_nested_tamper(tmp_path: Path) -> None:
    _program_store, _ops, _continuity, _distribution, _program_id, zipped = _prepared_kit(tmp_path)

    backslash_zip = tmp_path / "kit-backslash.zip"
    _replace_zip_name_bytes(Path(zipped["zip_path"]), backslash_zip, b"README.txt", b"README\\txt")
    backslash = verify_unified_release_program_continuity_distribution_package(backslash_zip, strict=True, deep=True)
    assert backslash["status"] == "failed"
    assert "urpcdk_entry_paths_safe" in backslash["blockers"]

    musicforge_zip = tmp_path / "kit-musicforge.zip"
    _write_with_extra_entry(Path(zipped["zip_path"]), musicforge_zip, ".MusicForge/internal.json", b"{}")
    musicforge = verify_unified_release_program_continuity_distribution_package(musicforge_zip, strict=True, deep=True)
    assert musicforge["status"] == "failed"
    assert "urpcdk_entry_paths_safe" in musicforge["blockers"]

    nested_tamper_zip = tmp_path / "kit-nested-tamper.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), nested_tamper_zip, _tamper_nested_continuity)
    nested_tamper = verify_unified_release_program_continuity_distribution_package(nested_tamper_zip, strict=True, deep=True)
    assert nested_tamper["status"] == "failed"
    assert "urpcdk_source_continuity_zip_sha256" in nested_tamper["blockers"] or "urpcdk_continuity_runtime_zip_hash" in nested_tamper["blockers"]


def test_unified_release_program_continuity_distribution_rejects_receipt_wrong_hash(tmp_path: Path) -> None:
    _program_store, _ops, _continuity, distribution, program_id, zipped = _prepared_kit(tmp_path)
    verification = read_json(distribution.verification_report_path(program_id))
    receipt = distribution.import_receiver_receipt(
        program_id,
        {
            "receiver_name": "Receiver",
            "organization": "QA",
            "decision": "accepted",
            "verification_status": "passed",
            "kit_sha256": "0" * 64,
            "kit_manifest_hash": zipped["manifest_hash"],
            "verification_report_hash": verification.get("integrity_hash"),
        },
    )

    report = verify_unified_release_program_continuity_distribution_package(
        zipped["zip_path"],
        strict=True,
        deep=True,
        require_receiver_receipt=True,
        receiver_receipt_path=distribution.receiver_receipt_path(program_id, str(receipt["receipt_id"])),
        kit_verification_report_path=distribution.verification_report_path(program_id),
    )

    assert report["status"] == "failed"
    assert "urpcdk_receiver_receipt_kit_sha256" in report["blockers"]


def test_unified_release_program_continuity_distribution_rejects_receipt_wrong_verification_hash(tmp_path: Path) -> None:
    _program_store, _ops, _continuity, distribution, program_id, zipped = _prepared_kit(tmp_path)
    manifest = read_json(distribution.manifest_path(program_id))
    receipt = distribution.import_receiver_receipt(
        program_id,
        {
            "receiver_name": "Receiver",
            "organization": "QA",
            "decision": "accepted",
            "verification_status": "passed",
            "kit_sha256": zipped["zip_sha256"],
            "kit_manifest_hash": manifest.get("integrity_hash"),
            "verification_report_hash": "f" * 64,
        },
    )

    report = verify_unified_release_program_continuity_distribution_package(
        zipped["zip_path"],
        strict=True,
        deep=True,
        require_receiver_receipt=True,
        receiver_receipt_path=distribution.receiver_receipt_path(program_id, str(receipt["receipt_id"])),
        kit_verification_report_path=distribution.verification_report_path(program_id),
    )

    assert report["status"] == "failed"
    assert "urpcdk_receiver_receipt_verification_hash" in report["blockers"]


def test_unified_release_program_continuity_distribution_receipt_verify_does_not_overwrite_canonical_report(tmp_path: Path) -> None:
    _program_store, _ops, _continuity, distribution, program_id, zipped = _prepared_kit(tmp_path)
    canonical_before = read_json(distribution.verification_report_path(program_id))
    receipt = distribution.import_receiver_receipt(
        program_id,
        {
            "receiver_name": "Receiver",
            "organization": "QA",
            "decision": "accepted",
            "verification_status": "passed",
            "kit_sha256": zipped["zip_sha256"],
            "kit_manifest_hash": zipped["manifest_hash"],
            "verification_report_hash": canonical_before.get("integrity_hash"),
        },
    )
    receipt_path = distribution.receiver_receipt_path(program_id, str(receipt["receipt_id"]))

    receipt_report = distribution.verify_kit(
        program_id,
        {
            "deep": True,
            "require_receiver_receipt": True,
            "receiver_receipt": receipt_path,
        },
    )
    canonical_after = read_json(distribution.verification_report_path(program_id))
    gate = distribution.gate(program_id, required=True, require_receiver_receipt=True, receiver_receipt_path=receipt_path)

    assert receipt_report["status"] == "passed", receipt_report.get("blockers")
    assert canonical_after.get("integrity_hash") == canonical_before.get("integrity_hash")
    assert gate["status"] == "passed", gate


def test_unified_release_program_continuity_distribution_store_rejects_source_tamper(tmp_path: Path) -> None:
    _program_store, _ops, _continuity, distribution, program_id, _zipped = _prepared_kit(tmp_path)
    with distribution.continuity_store.archive_zip_path(program_id).open("ab") as fh:
        fh.write(b"tamper")

    with pytest.raises(UnifiedReleaseProgramContinuityDistributionStateError):
        distribution.build_kit_zip(program_id)


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[rel] = b"unexpected kit instructions\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _add_extra_nested_zip(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "packages/evil.zip"
    entries[rel] = b"PK\x05\x06" + (b"\x00" * 18)
    return _add_manifest_file(entries, rel)


def _tamper_nested_continuity(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "packages/continuity-archive.zip"
    entries[rel] = entries[rel] + b"tamper"
    return _resign_indexes(entries, rel)


def _add_manifest_file(entries: dict[str, bytes], rel: str) -> dict[str, bytes]:
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": rel, "size_bytes": len(entries[rel]), "sha256": _sha256_bytes(entries[rel])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _resign_indexes(entries: dict[str, bytes], rel: str) -> dict[str, bytes]:
    package_index = json.loads(entries["package-index.json"].decode("utf-8"))
    for row in package_index.get("packages", []):
        if row.get("path") == rel:
            row["sha256"] = _sha256_bytes(entries[rel])
            row["size_bytes"] = len(entries[rel])
    package_index["integrity_hash"] = stable_hash({key: value for key, value in package_index.items() if key != "integrity_hash"})
    entries["package-index.json"] = json.dumps(package_index, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    source = json.loads(entries["source-binding-summary.json"].decode("utf-8"))
    source["package_index_hash"] = package_index["integrity_hash"]
    source["continuity_zip_sha256"] = _sha256_bytes(entries[rel])
    source["integrity_hash"] = stable_hash({key: value for key, value in source.items() if key != "integrity_hash"})
    entries["source-binding-summary.json"] = json.dumps(source, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    for row in manifest.get("files", []):
        if row.get("path") in {rel, "package-index.json", "source-binding-summary.json"}:
            data = entries[row["path"]]
            row["sha256"] = _sha256_bytes(data)
            row["size_bytes"] = len(data)
    manifest["source"]["package_index_hash"] = package_index["integrity_hash"]
    manifest["source"]["source_binding_hash"] = source["integrity_hash"]
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _write_with_extra_entry(source: Path, dest: Path, name: str, data: bytes) -> None:
    with zipfile.ZipFile(source, "r") as zin, zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr(name, data)


def _replace_zip_name_bytes(source: Path, dest: Path, old: bytes, new: bytes) -> None:
    assert len(old) == len(new)
    dest.write_bytes(source.read_bytes().replace(old, new))
