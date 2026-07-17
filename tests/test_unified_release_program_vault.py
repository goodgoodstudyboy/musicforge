from __future__ import annotations

import json
from pathlib import Path

from song_agent.projectio import read_json, write_json
from tests.zip_helpers import _v76_rewrite_zip
from song_agent.releases import stable_hash
from song_agent.unified_release_program_vault import UnifiedReleaseProgramVaultStore
from song_agent.unified_release_program_vault_verifier import verify_unified_release_program_vault_package
from tests.test_unified_release_program_handoff import _accepted_manifest_row, _program_ops_handoff, _review_response, _write_handoff_manifest


def _signed_handoff_with_accepted_evidence(tmp_path: Path):
    handoff_store, program_store, ops_store, program_id, program_manifest_path, handoff_manifest = _program_ops_handoff(tmp_path)
    handoff_store.refresh_handoff(program_id, {"external_evidence_manifest": handoff_manifest})
    pack = handoff_store.export_review_pack(program_id, {"audience": "release_owner"})
    handoff_store.build_review_pack_zip(program_id, pack["review_pack_id"])
    response = handoff_store.import_response(program_id, _review_response(handoff_store, program_id, pack["review_pack_id"]))
    accepted = handoff_store.create_accepted_evidence(program_id, response["response"]["response_id"])
    evidence_id = accepted["evidence"]["evidence_id"]
    _write_handoff_manifest(handoff_store, program_store, ops_store, program_id, program_manifest_path, handoff_manifest, [_accepted_manifest_row(handoff_store, program_id, evidence_id, response["response"]["response_id"])])
    handoff_store.refresh_handoff(program_id, {"external_evidence_manifest": handoff_manifest})
    handoff_store.refresh_decision_board(program_id, {})
    handoff_store.signoff_handoff(program_id, {"signed_by": "handoff chair", "role": "release_owner"})
    handoff_store.build_handoff_archive_zip(program_id)
    handoff_verify = handoff_store.verify_handoff_archive_zip(program_id, {"external_evidence_manifest": handoff_manifest, "handoff_signoff_binding": handoff_store.signoff_binding_path(program_id)})
    assert handoff_verify["status"] == "passed", handoff_verify.get("blockers")
    return program_store, UnifiedReleaseProgramVaultStore(program_store), program_id


def test_unified_release_program_vault_happy_path_and_anchor(tmp_path: Path) -> None:
    _program_store, vault_store, program_id = _signed_handoff_with_accepted_evidence(tmp_path)

    report = vault_store.refresh_vault(program_id)
    zipped = vault_store.build_vault_zip(program_id)
    verified = vault_store.verify_vault_zip(program_id, {"deep": True, "require_anchor": True})
    standalone = verify_unified_release_program_vault_package(
        zipped["zip_path"],
        strict=True,
        deep=True,
        require_anchor=True,
        vault_anchor_path=vault_store.anchor_path(program_id),
    )
    missing_anchor = verify_unified_release_program_vault_package(zipped["zip_path"], strict=True, deep=True, require_anchor=True)

    assert report["status"] == "passed", report.get("blockers")
    assert Path(zipped["zip_path"]).exists()
    assert Path(zipped["anchor_path"]).exists()
    assert verified["status"] == "passed", verified.get("blockers")
    assert standalone["status"] == "passed", standalone.get("blockers")
    assert missing_anchor["status"] == "failed"
    assert "urpv_anchor_required" in missing_anchor["blockers"]


def test_unified_release_program_vault_rejects_declared_extra_and_nested_tamper(tmp_path: Path) -> None:
    _program_store, vault_store, program_id = _signed_handoff_with_accepted_evidence(tmp_path)
    zipped = vault_store.build_vault_zip(program_id)

    extra_zip = tmp_path / "vault-extra.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), extra_zip, _add_declared_extra)
    extra = verify_unified_release_program_vault_package(extra_zip, strict=True, deep=True, require_anchor=True, vault_anchor_path=vault_store.anchor_path(program_id))

    tampered_zip = tmp_path / "vault-tampered-nested.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), tampered_zip, _tamper_nested_handoff)
    tampered = verify_unified_release_program_vault_package(tampered_zip, strict=True, deep=True, require_anchor=True, vault_anchor_path=vault_store.anchor_path(program_id))

    assert extra["status"] == "failed"
    assert "urpv_allowed_entries" in extra["blockers"]
    assert tampered["status"] == "failed"
    assert "urpv_anchor_zip_sha256" in tampered["blockers"]


def test_unified_release_program_vault_rejects_forged_indexed_nested_package(tmp_path: Path) -> None:
    _program_store, vault_store, program_id = _signed_handoff_with_accepted_evidence(tmp_path)
    zipped = vault_store.build_vault_zip(program_id)

    forged_zip = tmp_path / "vault-forged-index.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), forged_zip, _add_indexed_evil_package)
    forged_anchor = tmp_path / "vault-forged-index-anchor.json"
    _write_forged_anchor(vault_store.anchor_path(program_id), forged_zip, forged_anchor)

    forged = verify_unified_release_program_vault_package(
        forged_zip,
        strict=True,
        deep=True,
        require_anchor=True,
        vault_anchor_path=forged_anchor,
    )

    assert forged["status"] == "failed"
    assert "urpv_allowed_entries" in forged["blockers"]
    assert "urpv_manifest_files_exact" in forged["blockers"]
    assert "urpv_package_packages_evil_zip_allowed_component" in forged["blockers"]


def test_unified_release_program_vault_deep_rejects_nested_tamper_after_anchor_resign(tmp_path: Path) -> None:
    _program_store, vault_store, program_id = _signed_handoff_with_accepted_evidence(tmp_path)
    zipped = vault_store.build_vault_zip(program_id)

    tampered_zip = tmp_path / "vault-tampered-nested-resigned.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), tampered_zip, _tamper_nested_handoff_and_indexes)
    forged_anchor = tmp_path / "vault-tampered-nested-anchor.json"
    _write_forged_anchor(vault_store.anchor_path(program_id), tampered_zip, forged_anchor)

    tampered = verify_unified_release_program_vault_package(
        tampered_zip,
        strict=True,
        deep=True,
        require_anchor=True,
        vault_anchor_path=forged_anchor,
    )

    assert tampered["status"] == "failed"
    assert "urpv_deep_handoff_zip_sha256" in tampered["blockers"]


def test_unified_release_program_vault_deep_skips_extraction_for_unsafe_entries(tmp_path: Path) -> None:
    _program_store, vault_store, program_id = _signed_handoff_with_accepted_evidence(tmp_path)
    zipped = vault_store.build_vault_zip(program_id)

    for name in ("../outside.txt", ".MusicForge/internal.json"):
        unsafe_zip = tmp_path / f"vault-unsafe-{len(name)}.zip"
        _v76_rewrite_zip(Path(zipped["zip_path"]), unsafe_zip, lambda entries, entry_name=name: _add_unsafe_entry(entries, entry_name))
        report = verify_unified_release_program_vault_package(unsafe_zip, strict=True, deep=True)

        assert report["status"] == "failed"
        assert "urpv_entry_paths_safe" in report["blockers"]
        assert "urpv_deep_preflight" in report["blockers"]
    backslash_zip = tmp_path / "vault-unsafe-backslash.zip"
    _v76_rewrite_zip(Path(zipped["zip_path"]), backslash_zip, lambda entries: _add_unsafe_entry(entries, "packages/evil.zip"))
    backslash_zip.write_bytes(backslash_zip.read_bytes().replace(b"packages/evil.zip", b"packages\\evil.zip"))
    backslash = verify_unified_release_program_vault_package(backslash_zip, strict=True, deep=True)

    assert backslash["status"] == "failed"
    assert "urpv_entry_paths_safe" in backslash["blockers"]
    assert "urpv_deep_preflight" in backslash["blockers"]


def _add_declared_extra(entries: dict[str, bytes]) -> dict[str, bytes]:
    extra = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    entries[extra] = b"unexpected vault file\n"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    manifest["files"].append({"path": extra, "size_bytes": len(entries[extra]), "sha256": _sha256_bytes(entries[extra])})
    manifest["files"] = sorted(manifest["files"], key=lambda row: row.get("path") or "")
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _tamper_nested_handoff(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "packages/unified-release-program-handoff.zip"
    entries[rel] = entries[rel] + b"tamper"
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    for row in manifest.get("files", []):
        if row.get("path") == rel:
            row["size_bytes"] = len(entries[rel])
            row["sha256"] = _sha256_bytes(entries[rel])
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    return entries


def _add_indexed_evil_package(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "packages/evil.zip"
    entries[rel] = b"not a trusted nested package\n"
    package_index = json.loads(entries["package-index.json"].decode("utf-8"))
    package_index.setdefault("packages", []).append(
        {
            "component_type": "evil",
            "component_id": "evil",
            "path": rel,
            "zip_sha256": _sha256_bytes(entries[rel]),
            "zip_size_bytes": len(entries[rel]),
            "exists": True,
        }
    )
    package_index["summary"] = {"package_count": len(package_index.get("packages", []))}
    package_index["integrity_hash"] = stable_hash({key: value for key, value in package_index.items() if key != "integrity_hash"})
    entries["package-index.json"] = json.dumps(package_index, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    _sync_manifest(entries, "package-index.json", entries["package-index.json"], package_index_hash=package_index["integrity_hash"])
    _sync_manifest(entries, rel, entries[rel])
    return entries


def _tamper_nested_handoff_and_indexes(entries: dict[str, bytes]) -> dict[str, bytes]:
    rel = "packages/unified-release-program-handoff.zip"
    entries[rel] = entries[rel] + b"tamper"
    package_index = json.loads(entries["package-index.json"].decode("utf-8"))
    for row in package_index.get("packages", []):
        if row.get("path") == rel:
            row["zip_sha256"] = _sha256_bytes(entries[rel])
            row["zip_size_bytes"] = len(entries[rel])
    package_index["integrity_hash"] = stable_hash({key: value for key, value in package_index.items() if key != "integrity_hash"})
    entries["package-index.json"] = json.dumps(package_index, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    _sync_manifest(entries, rel, entries[rel])
    _sync_manifest(entries, "package-index.json", entries["package-index.json"], package_index_hash=package_index["integrity_hash"])
    return entries


def _add_unsafe_entry(entries: dict[str, bytes], name: str) -> dict[str, bytes]:
    entries[name] = b"unsafe vault entry\n"
    return entries


def _sync_manifest(entries: dict[str, bytes], rel: str, data: bytes, *, package_index_hash: str | None = None) -> None:
    manifest = json.loads(entries["manifest.json"].decode("utf-8"))
    if package_index_hash:
        manifest.setdefault("source", {})["package_index_hash"] = package_index_hash
    files = [row for row in manifest.get("files", []) if isinstance(row, dict) and row.get("path") != rel]
    files.append({"path": rel, "size_bytes": len(data), "sha256": _sha256_bytes(data)})
    manifest["files"] = sorted(files, key=lambda row: row.get("path") or "")
    manifest.setdefault("zip", {})["entries"] = sorted({*manifest.get("zip", {}).get("entries", []), *entries.keys()})
    manifest["integrity_hash"] = stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})
    entries["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def _write_forged_anchor(original_anchor_path: Path, zip_path: Path, target_anchor_path: Path) -> None:
    import zipfile

    anchor = read_json(original_anchor_path)
    with zipfile.ZipFile(zip_path) as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        source = json.loads(archive.read("source-summary.json").decode("utf-8"))
        report = json.loads(archive.read("vault-report.json").decode("utf-8"))
        package_index = json.loads(archive.read("package-index.json").decode("utf-8"))
        verification_index = json.loads(archive.read("verification-index.json").decode("utf-8"))
        proof_index = json.loads(archive.read("proof-index.json").decode("utf-8"))
        chain = json.loads(archive.read("chain-of-custody.json").decode("utf-8"))
    anchor.update(
        {
            "vault_zip_sha256": _sha256_path(zip_path),
            "vault_zip_size_bytes": zip_path.stat().st_size,
            "vault_manifest_hash": manifest.get("integrity_hash"),
            "vault_source_hash": source.get("source_hash"),
            "vault_report_hash": report.get("integrity_hash"),
            "package_index_hash": package_index.get("integrity_hash"),
            "verification_index_hash": verification_index.get("integrity_hash"),
            "proof_index_hash": proof_index.get("integrity_hash"),
            "chain_of_custody_hash": chain.get("integrity_hash"),
        }
    )
    anchor["integrity_hash"] = stable_hash({key: value for key, value in anchor.items() if key != "integrity_hash"})
    write_json(target_anchor_path, anchor)


def _sha256_path(path: Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
