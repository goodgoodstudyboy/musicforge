from __future__ import annotations

import json
import stat
import tempfile
import warnings
import zipfile
from pathlib import Path
from typing import Any

from song_agent.capabilities import CapabilityRegistry, CapabilitySpec, RuntimeVerificationSpec
from song_agent.platform.contracts.lifecycle import ResetAuthorization
from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.evidence_graph import build_evidence_graph
from song_agent.platform.evidence_graph.builder import write_evidence_graph_manifest
from song_agent.platform.lifecycle import ArchiveBuilder, ChangeRequestService
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import integrity_hash, sha256_bytes, sha256_file
from song_agent.projectio import write_json


ACTIVE_V12_VERIFIERS = (
    "unified_release_program_verifier.py",
    "unified_release_program_operations_verifier.py",
    "unified_release_program_handoff_verifier.py",
    "unified_release_program_vault_verifier.py",
    "unified_release_program_vault_operations_verifier.py",
    "unified_release_program_continuity_verifier.py",
    "unified_release_program_continuity_distribution_verifier.py",
    "unified_release_program_continuity_acceptance_verifier.py",
    "unified_release_program_continuity_acceptance_change_verifier.py",
    "unified_release_program_continuity_command_center_verifier.py",
    "unified_release_program_continuity_command_center_signoff_verifier.py",
    "unified_release_program_continuity_command_center_acceptance_verifier.py",
    "unified_release_program_continuity_command_center_acceptance_change_verifier.py",
)


def run_verification_kernel_smoke(root: Path) -> tuple[bool, str]:
    del root
    try:
        spec = PackageSpec(
            package_type="musicforge_release_check_verification_kernel",
            verification_package_type="musicforge_release_check_verification_kernel_report",
            check_prefix="v1215_kernel",
            required_entries=frozenset({"manifest.json", "data.json", "README.txt"}),
        )
        with tempfile.TemporaryDirectory(prefix="mf-v1215-verification-kernel-") as temp:
            base = Path(temp)
            valid = {"data.json": b'{"ok":true}', "README.txt": b"verification kernel\n"}
            happy_path = _write_package(base / "happy.zip", valid, spec.package_type)
            reports = {
                "happy": _verify(happy_path, spec),
                "missing_file_index": _verify(
                    _write_package_without_file_index(base / "missing-file-index.zip", valid, spec.package_type),
                    spec,
                ),
                "missing": _verify(_write_package(base / "missing.zip", {"README.txt": b"missing data"}, spec.package_type), spec),
                "declared_extra": _verify(_write_package(base / "extra.zip", {**valid, "UNTRUSTED.txt": b"extra"}, spec.package_type), spec),
                "dangerous_path": _verify(_write_package(base / "dangerous.zip", {**valid, "../escape.txt": b"escape"}, spec.package_type), spec),
                "musicforge": _verify(_write_package(base / "musicforge.zip", {**valid, ".MusicForge/private.json": b"{}"}, spec.package_type), spec),
                "nested_zip": _verify(_write_package(base / "nested.zip", {**valid, "unexpected.zip": b"PK"}, spec.package_type), spec),
                "redaction": _verify(_write_package(base / "redaction.zip", {"data.json": b"{}", "README.txt": b"api_key=secret-value"}, spec.package_type), spec),
                "wrong_package_type": _verify(_write_package(base / "wrong-type.zip", valid, "wrong_package"), spec),
            }
            duplicate_path = _write_package(base / "duplicate.zip", valid, spec.package_type)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate_path, "a") as archive:
                    archive.writestr("data.json", b"{}")
            reports["duplicate"] = _verify(duplicate_path, spec)

            raw_backslash_path = _write_package(base / "raw-backslash.zip", valid, spec.package_type)
            raw_backslash_path.write_bytes(raw_backslash_path.read_bytes().replace(b"README.txt", b"README\\txt"))
            reports["raw_backslash"] = _verify(raw_backslash_path, spec)

            trailing_path = _write_package(base / "trailing.zip", valid, spec.package_type)
            trailing_path.write_bytes(trailing_path.read_bytes() + b"tamper")
            reports["trailing_data"] = _verify(trailing_path, spec)

            manifest_spoof_path = _write_package(base / "manifest-spoof.zip", valid, spec.package_type)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(manifest_spoof_path, "a") as archive:
                    archive.writestr("data.json", b'{"forged":true}')
            reports["manifest_spoof"] = _verify(manifest_spoof_path, spec)

        source_root = Path(__file__).resolve().parent
        migrated = all(
            "PackageSpec" in (source_root / filename).read_text(encoding="utf-8")
            and "verify_package_envelope" in (source_root / filename).read_text(encoding="utf-8")
            for filename in ACTIVE_V12_VERIFIERS
        )
        statuses = {name: str(report.get("status")) for name, report in reports.items()}
        ok = statuses["happy"] == "passed" and all(
            status == "failed" for name, status in statuses.items() if name != "happy"
        ) and migrated
        return ok, "v12.15 verification kernel: " + ", ".join(
            [*(f"{name}={status}" for name, status in statuses.items()), f"active_verifiers_migrated={migrated}"]
        )
    except Exception as exc:
        return False, f"v12.15 Verification Kernel smoke failed: {exc}"


def run_shared_kernel_security_smoke(root: Path) -> tuple[bool, str]:
    del root
    try:
        with tempfile.TemporaryDirectory(prefix="mf-v1301-shared-kernel-") as raw:
            base = Path(raw)
            signals = {
                "directory_entry": _non_regular_entry_rejected(base, stat.S_IFDIR),
                "symlink_entry": _non_regular_entry_rejected(base, stat.S_IFLNK),
                "manifest_size": _wrong_manifest_size_rejected(base),
                "archive_duplicate": _archive_duplicate_rejected(base),
                "change_request_fail_closed": _change_request_missing_fields_rejected(),
                "evidence_identity": _forged_evidence_identity_rejected(base),
            }
        return all(signals.values()), "v13.0.1 shared kernel security: " + ", ".join(
            f"{key}={value}" for key, value in signals.items()
        )
    except Exception as exc:
        return False, f"v13.0.1 shared kernel security failed: {exc}"


def _non_regular_entry_rejected(base: Path, file_type: int) -> bool:
    spec = PackageSpec(
        package_type="musicforge_v1301_kernel_package",
        verification_package_type="musicforge_v1301_kernel_verification",
        check_prefix="v1301_kernel",
        required_entries=frozenset({"manifest.json", "data.json", "README.txt"}),
    )
    target = base / f"non-regular-{file_type}.zip"
    payloads = {"data.json": b"{}", "README.txt": b"security\n"}
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("manifest.json", json.dumps(_kernel_manifest(payloads), sort_keys=True))
        info = zipfile.ZipInfo("data.json")
        info.create_system = 3
        info.external_attr = (file_type | 0o644) << 16
        archive.writestr(info, payloads["data.json"])
        archive.writestr("README.txt", payloads["README.txt"])
    strict = verify_package_envelope(target, spec, strict=True)
    relaxed = verify_package_envelope(target, spec, strict=False)
    return strict["status"] == relaxed["status"] == "failed" and "v1301_kernel_entry_types_regular" in strict["blockers"]


def _wrong_manifest_size_rejected(base: Path) -> bool:
    spec = PackageSpec(
        package_type="musicforge_v1301_kernel_package",
        verification_package_type="musicforge_v1301_kernel_verification",
        check_prefix="v1301_kernel",
        required_entries=frozenset({"manifest.json", "data.json", "README.txt"}),
    )
    target = base / "wrong-size.zip"
    payloads = {"data.json": b"{}", "README.txt": b"security\n"}
    manifest = _kernel_manifest(payloads)
    next(row for row in manifest["files"] if row["path"] == "data.json")["size_bytes"] += 1
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, data in payloads.items():
            archive.writestr(name, data)
    report = verify_package_envelope(target, spec, strict=True)
    return report["status"] == "failed" and "v1301_kernel_manifest_file_data_json_size" in report["blockers"]


def _kernel_manifest(payloads: dict[str, bytes]) -> dict[str, Any]:
    document = {
        "schema_version": 1,
        "package_type": "musicforge_v1301_kernel_package",
        "files": [
            {"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)}
            for name, data in sorted(payloads.items())
        ],
    }
    document["integrity_hash"] = integrity_hash(document)
    return document


def _archive_duplicate_rejected(base: Path) -> bool:
    export_dir = base / "archive-export"
    zip_path = base / "archive.zip"
    expected = ArchiveBuilder.export_documents(export_dir, {"manifest.json": {"status": "passed"}, "README.txt": "frozen\n"})
    ArchiveBuilder.build_zip(export_dir, zip_path, expected)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(zip_path, "a") as archive:
            archive.writestr("README.txt", expected["README.txt"])
    try:
        ArchiveBuilder.build_zip(export_dir, zip_path, expected)
    except ValueError:
        return True
    return False


def _change_request_missing_fields_rejected() -> bool:
    target = {"signoff_hash": "signoff-1"}
    source = {"source_hash": "source-1"}
    request = _with_integrity({
        "program_id": "program-1",
        "change_request_id": "cr-1",
        "change_type": "reset_signoff",
        "allowed_actions": ["reset_signoff"],
        "status": "approved",
        "target": target,
        "source": source,
        "submitted_request_hash": "submitted-1",
    })
    approval = _with_integrity({
        "program_id": "program-1",
        "change_request_id": "cr-1",
        "status": "approved",
        "target": target,
        "source": source,
    })
    request["approval_hash"] = approval["integrity_hash"]
    request["integrity_hash"] = integrity_hash(request)
    try:
        ChangeRequestService.validate_reset_authorization(
            request,
            approval,
            ResetAuthorization("program-1", "cr-1", "reset_signoff", "reset_signoff", target, source),
        )
    except ValueError:
        return True
    return False


def _forged_evidence_identity_rejected(base: Path) -> bool:
    package = base / "identity-package.zip"
    package.write_bytes(b"identity")
    report_path = base / "identity-verification.json"
    write_json(report_path, _identity_runtime_verifier(package))
    manifest_path = base / "identity-manifest.json"
    write_evidence_graph_manifest(manifest_path, items=[{
        "component_type": "test_component",
        "component_id": "forged-component",
        "evidence_type": "archive",
        "generation": 2,
        "current": False,
        "package_path": package.name,
        "verification_report_path": report_path.name,
    }])
    registry = CapabilityRegistry()
    registry.register(CapabilitySpec(
        "test.identity",
        "test_component",
        "test",
        "test.verify",
        RuntimeVerificationSpec(
            __name__,
            "_identity_runtime_verifier",
            "musicforge_v1301_identity_package",
            "musicforge_v1301_identity_verification",
            defaults=(("strict", True),),
        ),
    ))
    graph = build_evidence_graph(manifest_path, registry=registry)
    blockers = set(graph.nodes[0].blockers)
    return graph.status == "failed" and {
        "evidence_manifest_identity_component_id",
        "evidence_manifest_identity_generation",
        "evidence_manifest_identity_current",
    }.issubset(blockers)


def _identity_runtime_verifier(package_path: Path | str, *, strict: bool = True) -> dict[str, Any]:
    del strict
    target = Path(package_path)
    fingerprint = sha256_file(target)
    report = {
        "package_type": "musicforge_v1301_identity_verification",
        "status": "passed" if target.is_file() else "failed",
        "zip_sha256": fingerprint,
        "zip_size_bytes": target.stat().st_size if target.is_file() else 0,
        "manifest_hash": fingerprint,
        "summary": {
            "component_id": "component-001",
            "generation": 1,
            "current_generation": 1,
            "current": True,
            "source_hash": fingerprint,
        },
        "blockers": [],
    }
    report["integrity_hash"] = integrity_hash(report)
    return report


def _with_integrity(document: dict[str, Any]) -> dict[str, Any]:
    result = dict(document)
    result["integrity_hash"] = integrity_hash(result)
    return result


def _write_package(path: Path, entries: dict[str, bytes], package_type: str) -> Path:
    manifest = {
        "schema_version": 1,
        "package_type": package_type,
        "files": [
            {"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)}
            for name, data in sorted(entries.items())
        ],
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _write_package_without_file_index(path: Path, entries: dict[str, bytes], package_type: str) -> Path:
    manifest = {"schema_version": 1, "package_type": package_type}
    manifest["integrity_hash"] = integrity_hash(manifest)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _verify(path: Path, spec: PackageSpec) -> dict[str, Any]:
    return verify_package_envelope(path, spec, strict=True)
