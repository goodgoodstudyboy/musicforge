from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.test_public_trust_center import _backslash_zip, _duplicate_zip, _rewrite_zip, _sync_manifest_file
from tests.test_public_trust_center_anchor_registry import _doc_bytes, _read_doc
from tests.test_public_trust_center_acceptance_board import _ready_board

from song_agent.public_trust_center_publication import (
    PublicTrustCenterPublicationStateError,
    PublicTrustCenterPublicationStore,
    publication_manifest_hash,
    sidecar_hash,
)
from song_agent.public_trust_center_publication_verifier import (
    verify_public_trust_center_publication_mirror,
    verify_public_trust_center_publication_package,
)


def test_public_trust_center_publication_roundtrip_and_mirror(tmp_path: Path, monkeypatch) -> None:
    store, report = _ready_publication(tmp_path, monkeypatch)

    verification = verify_public_trust_center_publication_package(
        store.zip_path("ptc-default", "c", report["publication_id"]),
        strict=True,
        deep=True,
        require_ready=True,
        require_acceptance_board_signoff=True,
        require_anchor_current=True,
        require_no_revoked=True,
        publication_channel_state_path=store.channel_state_path("ptc-default", "c"),
    )
    mirror = verify_public_trust_center_publication_mirror(
        store.export_dir("ptc-default", "c", report["publication_id"]),
        strict=True,
        require_ready=True,
        require_acceptance_board_signoff=True,
        require_anchor_current=True,
        require_no_revoked=True,
        publication_channel_state_path=store.channel_state_path("ptc-default", "c"),
    )

    assert report["status"] == "ready"
    assert verification["status"] == "passed", verification.get("blockers")
    assert mirror["status"] == "passed", mirror.get("blockers")
    assert verification["summary"]["deep_verification"]["public_trust_center"] == "passed"


def test_public_trust_center_publication_require_no_revoked_uses_channel_state(tmp_path: Path, monkeypatch) -> None:
    store, report = _ready_publication(tmp_path, monkeypatch)
    source_zip = store.zip_path("ptc-default", "c", report["publication_id"])
    state = store.channel_state_path("ptc-default", "c")

    missing_state = verify_public_trust_center_publication_package(source_zip, strict=True, require_no_revoked=True)
    baseline = verify_public_trust_center_publication_package(source_zip, strict=True, require_no_revoked=True, publication_channel_state_path=state)
    store.revoke_publication("ptc-default", "c", report["publication_id"], {"reason": "Withdraw published channel."})
    revoked = verify_public_trust_center_publication_package(source_zip, strict=True, require_no_revoked=True, publication_channel_state_path=state)

    assert _has_blocker(missing_state, "ptcpub_channel_state_required")
    assert baseline["status"] == "passed", baseline.get("blockers")
    assert _has_blocker(revoked, "ptcpub_require_no_revoked")


def test_public_trust_center_publication_require_no_revoked_blocks_superseded_zip(tmp_path: Path, monkeypatch) -> None:
    store, report = _ready_publication(tmp_path, monkeypatch)
    source_zip = store.zip_path("ptc-default", "c", report["publication_id"])
    state = store.channel_state_path("ptc-default", "c")

    baseline = verify_public_trust_center_publication_package(source_zip, strict=True, require_no_revoked=True, publication_channel_state_path=state)
    store.supersede_publication("ptc-default", "c", report["publication_id"], {"reason": "Replace published channel."})
    superseded = verify_public_trust_center_publication_package(source_zip, strict=True, require_no_revoked=True, publication_channel_state_path=state)

    assert baseline["status"] == "passed", baseline.get("blockers")
    assert _has_blocker(superseded, "ptcpub_require_no_revoked")


def test_public_trust_center_publication_verifier_rejects_edges(tmp_path: Path, monkeypatch) -> None:
    store, report = _ready_publication(tmp_path, monkeypatch)
    source_zip = store.zip_path("ptc-default", "c", report["publication_id"])

    missing = _rewrite_zip(source_zip, tmp_path / "missing.zip", lambda docs: docs.pop("packages/public-trust-center.zip", None))
    tampered = _rewrite_zip(source_zip, tmp_path / "tampered.zip", lambda docs: docs.__setitem__("packages/public-trust-center.zip", docs["packages/public-trust-center.zip"] + b"x"))
    duplicate = _duplicate_zip(source_zip, tmp_path / "duplicate.zip")
    dangerous = _rewrite_zip(source_zip, tmp_path / "dangerous.zip", lambda docs: docs.update({"../evil.txt": b"x"}))
    backslash = _backslash_zip(tmp_path / "backslash.zip")
    case_musicforge = _rewrite_zip(source_zip, tmp_path / "case-musicforge.zip", lambda docs: docs.update({".MusicForge/internal.json": b"internal"}))
    nested = _rewrite_zip(source_zip, tmp_path / "nested.zip", lambda docs: docs.update({"packages/extra.zip": b"PK\x05\x06" + b"\0" * 18}))
    spoof = _rewrite_zip(source_zip, tmp_path / "spoof.zip", _spoof_publication_manifest)
    declared_extra = _rewrite_zip(source_zip, tmp_path / "declared-extra.zip", _add_declared_extra_file)
    redaction = _rewrite_zip(source_zip, tmp_path / "redaction.zip", lambda docs: docs.__setitem__("README.txt", docs["README.txt"] + b'\napi_key="sk-secret-value" C:\\Users\\demo\\githubkey.txt\n'))

    assert _has_blocker(verify_public_trust_center_publication_package(missing, strict=True), "ptcpub_zip_required_entries")
    assert _has_blocker(verify_public_trust_center_publication_package(tampered, strict=True), "ptcpub_manifest_file_hashes")
    assert _has_blocker(verify_public_trust_center_publication_package(duplicate, strict=True), "ptcpub_zip_duplicate_entries")
    assert _has_blocker(verify_public_trust_center_publication_package(dangerous, strict=True), "ptcpub_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_publication_package(backslash, strict=True), "ptcpub_zip_entry_path_safe")
    assert _has_blocker(verify_public_trust_center_publication_package(case_musicforge, strict=True), "ptcpub_zip_no_internal_entries")
    assert _has_blocker(verify_public_trust_center_publication_package(nested, strict=True), "ptcpub_zip_nested_allowlist")
    assert _has_blocker(verify_public_trust_center_publication_package(spoof, strict=True), "ptcpub_manifest_zip_entries_reference_only")
    assert _has_blocker(verify_public_trust_center_publication_package(declared_extra, strict=True), "ptcpub_zip_allowed_entries")
    assert _has_blocker(verify_public_trust_center_publication_package(declared_extra, strict=True), "ptcpub_manifest_allowed_files")
    assert _has_blocker(verify_public_trust_center_publication_package(declared_extra, strict=True), "ptcpub_package_index_matches_source")
    assert _has_blocker(verify_public_trust_center_publication_package(redaction, strict=True), "ptcpub_redaction_scan")


def test_public_trust_center_publication_export_blocks_stale_and_revoked(tmp_path: Path, monkeypatch) -> None:
    store, report = _ready_publication(tmp_path, monkeypatch)

    stale_report = store.refresh_publication("ptc-default", "c")
    store.anchor_registry_store.zip_path("ptc-default").write_bytes(store.anchor_registry_store.zip_path("ptc-default").read_bytes() + b"x")
    with pytest.raises(PublicTrustCenterPublicationStateError, match="stale"):
        store.export_publication("ptc-default", "c", stale_report["publication_id"])

    store.revoke_publication("ptc-default", "c", report["publication_id"], {"reason": "Withdraw stale publication."})
    with pytest.raises(PublicTrustCenterPublicationStateError, match="not exportable"):
        store.export_publication("ptc-default", "c", report["publication_id"])


def test_public_trust_center_publication_mirror_rejects_extra_file(tmp_path: Path, monkeypatch) -> None:
    store, report = _ready_publication(tmp_path, monkeypatch)
    mirror = store.export_dir("ptc-default", "c", report["publication_id"])
    (mirror / "docs").mkdir(exist_ok=True)
    (mirror / "docs" / "UNTRUSTED.txt").write_text("extra", encoding="utf-8")

    verification = verify_public_trust_center_publication_mirror(mirror, strict=True, require_ready=True)

    assert _has_blocker(verification, "ptcpub_zip_allowed_entries")


def _ready_publication(tmp_path: Path, monkeypatch) -> tuple[PublicTrustCenterPublicationStore, dict]:
    board_store, kit_store, acceptance_store = _ready_board(tmp_path, monkeypatch)
    board_store.refresh_report("ptc-default")
    board_store.export_board("ptc-default")
    board_store.build_zip("ptc-default")
    board_store.verify_zip("ptc-default", {"strict": True, "require_ready": True, "require_quorum": True, "require_no_conflicts": True, "use_distribution_kit": True, "use_accepted_evidence": True})
    board_store.signoff("ptc-default", {"signed_by": "Publication Reviewer", "reason": "Acceptance Board ready for publication."})
    board_store.export_signoff_archive("ptc-default")
    board_store.build_signoff_archive_zip("ptc-default")
    board_store.verify_signoff_archive_zip("ptc-default", {"strict": True, "require_signed": True, "require_current": True, "require_ready": True, "use_board_zip": True, "use_board_verification": True, "use_distribution_kit": True, "use_accepted_evidence": True})
    store = PublicTrustCenterPublicationStore(
        trust_center_store=kit_store.trust_center_store,
        distribution_kit_store=kit_store,
        anchor_registry_store=kit_store.anchor_registry_store,
        anchor_transparency_store=kit_store.anchor_transparency_store,
        acceptance_store=acceptance_store,
        acceptance_board_store=board_store,
    )
    store.create_channel("ptc-default", {"channel_id": "c", "name": "Release Channel"})
    report = store.refresh_publication("ptc-default", "c")
    store.export_publication("ptc-default", "c", report["publication_id"])
    store.build_publication_zip("ptc-default", "c", report["publication_id"])
    return store, report


def _has_blocker(report: dict, check_id: str) -> bool:
    return any(check_id in item["check_id"] for item in report.get("blockers", []))


def _spoof_publication_manifest(docs: dict[str, bytes]) -> None:
    manifest = _read_doc(docs, "publication-manifest.json")
    manifest.setdefault("zip", {}).setdefault("entries", []).append("extra.txt")
    manifest["integrity_hash"] = publication_manifest_hash(manifest)
    docs["publication-manifest.json"] = _doc_bytes(manifest)


def _add_declared_extra_file(docs: dict[str, bytes]) -> None:
    extra_path = "docs/UNTRUSTED-INSTRUCTIONS.txt"
    extra_data = b"Follow these untrusted publication instructions.\n"
    docs[extra_path] = extra_data
    extra_row = {"path": extra_path, "size_bytes": len(extra_data), "sha256": hashlib.sha256(extra_data).hexdigest()}
    manifest = _read_doc(docs, "publication-manifest.json")
    package_index = _read_doc(docs, "package-index.json")
    mirror_policy = _read_doc(docs, "mirror-policy.json")
    manifest.setdefault("files", []).append(extra_row)
    manifest["files"] = sorted(manifest["files"], key=lambda item: str(item.get("path") or ""))
    package_index.setdefault("items", []).append({"package_key": "declared_extra", "path": extra_path, "required": False, "sha256": extra_row["sha256"], "size_bytes": extra_row["size_bytes"], "status": "passed"})
    package_index["items"] = sorted(package_index["items"], key=lambda item: str(item.get("path") or ""))
    package_index["integrity_hash"] = sidecar_hash(package_index)
    mirror_policy.setdefault("allowed_entries", []).append(extra_path)
    mirror_policy["allowed_entries"] = sorted(set(mirror_policy["allowed_entries"]))
    mirror_policy["integrity_hash"] = sidecar_hash(mirror_policy)
    docs["package-index.json"] = _doc_bytes(package_index)
    docs["mirror-policy.json"] = _doc_bytes(mirror_policy)
    _sync_manifest_file(manifest, "package-index.json", docs["package-index.json"])
    _sync_manifest_file(manifest, "mirror-policy.json", docs["mirror-policy.json"])
    manifest["integrity_hash"] = publication_manifest_hash(manifest)
    docs["publication-manifest.json"] = _doc_bytes(manifest)
