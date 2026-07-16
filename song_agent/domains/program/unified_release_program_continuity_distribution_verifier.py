from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import re as re
import tempfile as tempfile
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.platform.contracts.packages import PackageSpec as PackageSpec
from song_agent.platform.verification.engine import verify_package_envelope as verify_package_envelope
from song_agent.platform.verification.hashing import (
    integrity_ok as _integrity_ok,
    sha256_bytes as _sha256_bytes,
    sha256_file as _sha256_path,
)
from song_agent.platform.verification.model import build_check as _check, build_verification_report as build_verification_report
from song_agent.platform.verification.redaction import archive_redaction_check as archive_redaction_check
from song_agent.platform.verification.zip_security import (
    is_safe_zip_entry as _is_safe_entry,
    raw_unsafe_entry_names as _raw_unsafe_entry_names,
    zip_has_no_trailing_data as _zip_has_no_trailing_data,
)

from song_agent.platform.persistence.program import read_program_json as read_json, write_program_json as write_json
from song_agent.platform.verification.sanitization import sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.program.unified_release_program_continuity_verifier import UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_continuity_package as verify_unified_release_program_continuity_package
from song_agent.domains.program.unified_release_program_vault_operations_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_operations_package as verify_unified_release_program_vault_operations_package
from song_agent.domains.program.unified_release_program_vault_verifier import UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE as UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE, verify_unified_release_program_vault_package as verify_unified_release_program_vault_package


UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_distribution_kit"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_distribution_verification"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_RECEIPT_PACKAGE_TYPE = "musicforge_unified_release_program_continuity_distribution_receiver_receipt"
UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "README.txt",
    "package-index.json",
    "verification-index.json",
    "source-binding-summary.json",
    "restore-command-guide.md",
    "receiver-guide.md",
    "custody-checklist.json",
    "redaction-report.json",
    "packages/continuity-archive.zip",
    "packages/vault-operations-archive.zip",
    "packages/evidence-vault.zip",
    "verification/continuity-verification-report.json",
    "verification/vault-operations-verification-report.json",
    "verification/vault-verification-report.json",
    "bindings/continuity-signoff-binding-summary.json",
    "bindings/vault-operations-signoff-binding-summary.json",
    "bindings/vault-anchor.json",
    "receipts/receiver-receipt-template.json",
}

NESTED_ZIP_ENTRIES = {
    "packages/continuity-archive.zip",
    "packages/vault-operations-archive.zip",
    "packages/evidence-vault.zip",
}

PACKAGE_COMPONENTS = {
    "continuity": {
        "path": "packages/continuity-archive.zip",
        "verification_path": "verification/continuity-verification-report.json",
        "binding_path": "bindings/continuity-signoff-binding-summary.json",
        "verification_package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
    },
    "vault_operations": {
        "path": "packages/vault-operations-archive.zip",
        "verification_path": "verification/vault-operations-verification-report.json",
        "binding_path": "bindings/vault-operations-signoff-binding-summary.json",
        "verification_package_type": UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    },
    "evidence_vault": {
        "path": "packages/evidence-vault.zip",
        "verification_path": "verification/vault-verification-report.json",
        "binding_path": "bindings/vault-anchor.json",
        "verification_package_type": UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
    },
}

def verify_unified_release_program_continuity_distribution_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    deep: bool = False,
    require_receiver_receipt: bool = False,
    receiver_receipt_path: Path | str | None = None,
    kit_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = 4096,
    max_uncompressed_size_mb: int = 8192,
    max_entry_count: int = 2000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    checks.extend(
        verify_package_envelope(
            zip_path,
            PackageSpec(
                package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_PACKAGE_TYPE,
                verification_package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
                check_prefix="urpcdk_kernel",
                required_entries=frozenset(REQUIRED_ENTRIES),
                optional_entries=frozenset(),
                nested_zip_policy="allowlisted",
                allowed_nested_entries=frozenset(NESTED_ZIP_ENTRIES),
                manifest_entry="manifest.json",
                max_zip_size_mb=max_zip_size_mb,
                max_uncompressed_size_mb=max_uncompressed_size_mb,
                max_entry_count=max_entry_count,
            ),
            strict=strict,
        ).get("checks", [])
    )
    if not zip_path.exists():
        return _finish(checks, summary, _check("urpcdk_zip_exists", False, "Continuity Distribution Kit ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("urpcdk_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    checks.append(_check("urpcdk_no_trailing_data", _zip_has_no_trailing_data(zip_path), "ZIP has no trailing data after the end of central directory."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            unsafe = sorted({*[name for name in names if not _is_safe_entry(name)], *_raw_unsafe_entry_names(zip_path)})
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            nested = sorted(name for name in names if name.lower().endswith(".zip"))
            checks.extend(
                [
                    _check("urpcdk_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}),
                    _check("urpcdk_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}),
                    _check("urpcdk_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."),
                    _check("urpcdk_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}),
                    _check("urpcdk_allowed_entries", not extra, "Kit contains only fixed entries.", {"extra": extra}),
                    _check("urpcdk_required_entries", not missing, "Kit contains required entries.", {"missing": missing}),
                    _check("urpcdk_nested_zip_allowlist", set(nested) == NESTED_ZIP_ENTRIES, "Kit contains only the fixed nested ZIP entries.", {"nested": nested}),
                ]
            )
            if _has_blocking_failures(checks):
                if deep:
                    checks.append(_check("urpcdk_deep_preflight", False, "Deep verification is skipped when ZIP structure checks fail."))
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            package_index = _read_json_entry(archive, "package-index.json")
            verification_index = _read_json_entry(archive, "verification-index.json")
            source_binding = _read_json_entry(archive, "source-binding-summary.json")
            checklist = _read_json_entry(archive, "custody-checklist.json")
            redaction = _read_json_entry(archive, "redaction-report.json")
            receipt_template = _read_json_entry(archive, "receipts/receiver-receipt-template.json")
            verification_docs = {
                key: _read_json_entry(archive, str(component["verification_path"]))
                for key, component in PACKAGE_COMPONENTS.items()
            }
            binding_docs = {
                key: _read_json_entry(archive, str(component["binding_path"]))
                for key, component in PACKAGE_COMPONENTS.items()
            }
            summary.update(
                {
                    "program_id": manifest.get("program_id") or source_binding.get("program_id"),
                    "manifest_hash": manifest.get("integrity_hash"),
                    "kit_status": source_binding.get("status"),
                    "package_count": len(package_index.get("packages") or []),
                    "verification_count": len(verification_index.get("verifications") or []),
                }
            )
            checks.extend(
                [
                    _check("urpcdk_manifest_package_type", manifest.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_PACKAGE_TYPE, "Manifest package type is valid."),
                    _check("urpcdk_schema_version", int(manifest.get("schema_version") or 0) == UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION, "Manifest schema version is supported."),
                    _check("urpcdk_package_index_package_type", package_index.get("package_type") == "musicforge_unified_release_program_continuity_distribution_package_index", "Package index package type is valid."),
                    _check("urpcdk_verification_index_package_type", verification_index.get("package_type") == "musicforge_unified_release_program_continuity_distribution_verification_index", "Verification index package type is valid."),
                    _check("urpcdk_source_binding_package_type", source_binding.get("package_type") == "musicforge_unified_release_program_continuity_distribution_source_binding", "Source binding package type is valid."),
                    _check("urpcdk_checklist_package_type", checklist.get("package_type") == "musicforge_unified_release_program_continuity_distribution_custody_checklist", "Custody checklist package type is valid."),
                    _check("urpcdk_redaction_package_type", redaction.get("package_type") == "musicforge_unified_release_program_continuity_distribution_redaction_report", "Redaction report package type is valid."),
                    _check("urpcdk_receipt_template_package_type", receipt_template.get("package_type") == "musicforge_unified_release_program_continuity_distribution_receiver_receipt_template", "Receiver receipt template package type is valid."),
                ]
            )
            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.extend(_package_index_checks(archive, package_index))
            checks.extend(_verification_index_checks(verification_index, verification_docs))
            for check_id, doc in (
                ("urpcdk_manifest_integrity", manifest),
                ("urpcdk_package_index_integrity", package_index),
                ("urpcdk_verification_index_integrity", verification_index),
                ("urpcdk_source_binding_integrity", source_binding),
                ("urpcdk_checklist_integrity", checklist),
                ("urpcdk_redaction_integrity", redaction),
                ("urpcdk_receipt_template_integrity", receipt_template),
            ):
                checks.append(_check(check_id, _integrity_ok(doc), f"{check_id} hash is valid."))
            for key, doc in verification_docs.items():
                checks.append(_check(f"urpcdk_{key}_verification_package_type", doc.get("package_type") == PACKAGE_COMPONENTS[key]["verification_package_type"], f"{key} verification package type is valid."))
                checks.append(_check(f"urpcdk_{key}_verification_integrity", _integrity_ok(doc), f"{key} verification report integrity is valid."))
                checks.append(_check(f"urpcdk_{key}_verification_passed", doc.get("status") == "passed", f"{key} external verification passed."))
            for key, doc in binding_docs.items():
                checks.append(_check(f"urpcdk_{key}_binding_integrity", _integrity_ok(doc), f"{key} binding integrity is valid."))
            checks.extend(_source_binding_checks(source_binding, package_index, verification_index, verification_docs, binding_docs))
            if deep:
                if _has_blocking_failures(checks):
                    checks.append(_check("urpcdk_deep_preflight", False, "Deep verification is skipped when kit document checks fail."))
                else:
                    checks.extend(_deep_checks(archive, verification_docs, binding_docs))
            elif strict:
                checks.append(_check("urpcdk_deep_verification_requested", True, "Deep verification was not requested.", severity="warning"))
            if require_receiver_receipt:
                checks.extend(_receiver_receipt_checks(receiver_receipt_path, zip_path, manifest, kit_verification_report_path))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("urpcdk_zip_readable", False, "Continuity Distribution Kit ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_release_program_continuity_distribution_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_release_program_continuity_distribution_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _manifest_checks(archive: zipfile.ZipFile, manifest: ImplementationDocument, name_set: set[str]) -> list[ImplementationDocument]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    file_paths = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected_files = REQUIRED_ENTRIES - {"manifest.json"}
    zip_meta = manifest.get("zip") if isinstance(manifest.get("zip"), dict) else {}
    checks = [
        _check("urpcdk_manifest_files_exact", file_paths == expected_files, "Manifest files match fixed kit entries.", {"missing": sorted(expected_files - file_paths), "extra": sorted(file_paths - expected_files)}),
        _check("urpcdk_manifest_entries_exact", name_set == REQUIRED_ENTRIES, "ZIP entries match fixed kit entries.", {"missing": sorted(REQUIRED_ENTRIES - name_set), "extra": sorted(name_set - REQUIRED_ENTRIES)}),
        _check("urpcdk_manifest_zip_filename", zip_meta.get("filename") == "unified-release-program-continuity-distribution-kit.zip", "Manifest ZIP filename is canonical."),
        _check("urpcdk_manifest_zip_entries", sorted(zip_meta.get("entries") or []) == sorted(name_set), "Manifest ZIP entries match central directory entries."),
        _check("urpcdk_manifest_zip_entry_count", int(zip_meta.get("entry_count") or -1) == len(name_set), "Manifest ZIP entry count matches central directory."),
        _check("urpcdk_manifest_zip_no_self_hash", "sha256" not in zip_meta and "size_bytes" not in zip_meta, "Manifest ZIP metadata does not contain an impossible self-hash or self-size."),
    ]
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if rel not in archive.namelist():
            checks.append(_check(f"urpcdk_manifest_file_{_safe_check_key(rel)}_exists", False, "Manifest file exists in ZIP."))
            continue
        data = archive.read(rel)
        checks.append(_check(f"urpcdk_manifest_file_{_safe_check_key(rel)}_sha256", row.get("sha256") == _sha256_bytes(data), "Manifest file hash matches ZIP entry."))
        checks.append(_check(f"urpcdk_manifest_file_{_safe_check_key(rel)}_size", int(row.get("size_bytes") or -1) == len(data), "Manifest file size matches ZIP entry."))
    return checks


def _package_index_checks(archive: zipfile.ZipFile, package_index: ImplementationDocument) -> list[ImplementationDocument]:
    rows = package_index.get("packages") if isinstance(package_index.get("packages"), list) else []
    expected = {
        key: {
            "component_type": key,
            "path": component["path"],
            "sha256": _sha256_bytes(archive.read(str(component["path"]))),
            "size_bytes": len(archive.read(str(component["path"]))),
        }
        for key, component in PACKAGE_COMPONENTS.items()
    }
    row_by_type = {str(row.get("component_type") or ""): row for row in rows if isinstance(row, dict)}
    checks = [
        _check("urpcdk_package_index_components", set(row_by_type) == set(PACKAGE_COMPONENTS), "Package index lists exactly the fixed package components.", {"components": sorted(row_by_type)}),
    ]
    for key, expected_row in expected.items():
        row = row_by_type.get(key) or {}
        checks.extend(
            [
                _check(f"urpcdk_package_index_{key}_path", row.get("path") == expected_row["path"], f"{key} package path is fixed."),
                _check(f"urpcdk_package_index_{key}_sha256", row.get("sha256") == expected_row["sha256"], f"{key} package hash matches nested ZIP."),
                _check(f"urpcdk_package_index_{key}_size", int(row.get("size_bytes") or -1) == expected_row["size_bytes"], f"{key} package size matches nested ZIP."),
            ]
        )
    return checks


def _verification_index_checks(verification_index: ImplementationDocument, verification_docs: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    rows = verification_index.get("verifications") if isinstance(verification_index.get("verifications"), list) else []
    row_by_type = {str(row.get("component_type") or ""): row for row in rows if isinstance(row, dict)}
    checks = [_check("urpcdk_verification_index_components", set(row_by_type) == set(PACKAGE_COMPONENTS), "Verification index lists exactly the fixed verification components.", {"components": sorted(row_by_type)})]
    for key, doc in verification_docs.items():
        row = row_by_type.get(key) or {}
        checks.extend(
            [
                _check(f"urpcdk_verification_index_{key}_path", row.get("path") == PACKAGE_COMPONENTS[key]["verification_path"], f"{key} verification path is fixed."),
                _check(f"urpcdk_verification_index_{key}_hash", row.get("verification_report_hash") == doc.get("integrity_hash"), f"{key} verification hash matches report."),
                _check(f"urpcdk_verification_index_{key}_status", row.get("status") == doc.get("status") == "passed", f"{key} verification status passed."),
            ]
        )
    return checks


def _source_binding_checks(
    source_binding: ImplementationDocument,
    package_index: ImplementationDocument,
    verification_index: ImplementationDocument,
    verification_docs: dict[str, ImplementationDocument],
    binding_docs: dict[str, ImplementationDocument],
) -> list[ImplementationDocument]:
    checks = [
        _check("urpcdk_source_binding_status", source_binding.get("status") == "passed", "Source binding status passed."),
        _check("urpcdk_source_package_index_hash", source_binding.get("package_index_hash") == package_index.get("integrity_hash"), "Source binding matches package index."),
        _check("urpcdk_source_verification_index_hash", source_binding.get("verification_index_hash") == verification_index.get("integrity_hash"), "Source binding matches verification index."),
    ]
    for key, doc in verification_docs.items():
        checks.append(_check(f"urpcdk_source_{key}_verification_hash", source_binding.get(f"{key}_verification_report_hash") == doc.get("integrity_hash"), f"Source binding matches {key} verification report."))
        checks.append(_check(f"urpcdk_source_{key}_zip_sha256", source_binding.get(f"{key}_zip_sha256") == doc.get("zip_sha256"), f"Source binding matches {key} ZIP hash."))
        checks.append(_check(f"urpcdk_source_{key}_manifest_hash", source_binding.get(f"{key}_manifest_hash") == doc.get("manifest_hash"), f"Source binding matches {key} manifest hash."))
    for key, doc in binding_docs.items():
        binding_key = f"{key}_binding_hash" if key != "evidence_vault" else "evidence_vault_anchor_hash"
        checks.append(_check(f"urpcdk_source_{key}_binding_hash", source_binding.get(binding_key) == doc.get("integrity_hash"), f"Source binding matches {key} binding/anchor."))
    return checks


def _deep_checks(archive: zipfile.ZipFile, verification_docs: dict[str, ImplementationDocument], binding_docs: dict[str, ImplementationDocument]) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mf-urpcdk-") as temp:
        root = Path(temp).resolve()
        extracted: dict[str, Path] = {}
        for rel in REQUIRED_ENTRIES:
            dest = (root / rel).resolve()
            if not _is_within(root, dest):
                checks.append(_check("urpcdk_deep_extract_containment", False, "Deep extraction target is inside temp root.", {"entry": rel}))
                return checks
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(archive.read(rel))
            extracted[rel] = dest
        continuity = verify_unified_release_program_continuity_package(
            extracted["packages/continuity-archive.zip"],
            strict=True,
            deep_restore=True,
            require_signed=True,
            require_current_vault_operations=True,
            signoff_binding_path=extracted["bindings/continuity-signoff-binding-summary.json"],
            vault_operations_archive_path=extracted["packages/vault-operations-archive.zip"],
            vault_operations_verification_report_path=extracted["verification/vault-operations-verification-report.json"],
            vault_operations_signoff_binding_path=extracted["bindings/vault-operations-signoff-binding-summary.json"],
        )
        vault_operations = verify_unified_release_program_vault_operations_package(
            extracted["packages/vault-operations-archive.zip"],
            strict=True,
            deep=True,
            require_signed=True,
            require_current_vault=True,
            signoff_binding_path=extracted["bindings/vault-operations-signoff-binding-summary.json"],
        )
        vault = verify_unified_release_program_vault_package(
            extracted["packages/evidence-vault.zip"],
            strict=True,
            deep=True,
            require_anchor=True,
            vault_anchor_path=extracted["bindings/vault-anchor.json"],
        )
    runtime = {"continuity": continuity, "vault_operations": vault_operations, "evidence_vault": vault}
    for key, report in runtime.items():
        external = verification_docs[key]
        checks.extend(
            [
                _check(f"urpcdk_{key}_runtime_passed", report.get("status") == "passed", f"{key} runtime verifier passed.", {"blockers": report.get("blockers", [])}),
                _check(f"urpcdk_{key}_runtime_zip_hash", report.get("zip_sha256") == external.get("zip_sha256"), f"{key} runtime ZIP hash matches external report."),
                _check(f"urpcdk_{key}_runtime_manifest_hash", report.get("manifest_hash") == external.get("manifest_hash"), f"{key} runtime manifest hash matches external report."),
            ]
        )
    return checks


def _receiver_receipt_checks(receiver_receipt_path: Path | str | None, kit_path: Path, manifest: ImplementationDocument, kit_verification_report_path: Path | str | None) -> list[ImplementationDocument]:
    if receiver_receipt_path is None:
        return [_check("urpcdk_receiver_receipt_required", False, "Receiver receipt is required.")]
    if kit_verification_report_path is None:
        return [_check("urpcdk_receiver_receipt_verification_report_required", False, "Receiver receipt verification requires the current Kit verification report.")]
    path = Path(receiver_receipt_path)
    if not path.exists():
        return [_check("urpcdk_receiver_receipt_exists", False, "Receiver receipt exists.")]
    report_path = Path(kit_verification_report_path)
    if not report_path.exists():
        return [_check("urpcdk_receiver_receipt_verification_report_exists", False, "Current Kit verification report exists.")]
    try:
        receipt = read_json(path)
        verification_report = read_json(report_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [_check("urpcdk_receiver_receipt_readable", False, "Receiver receipt and Kit verification report are readable.", {"error": sanitize_sensitive_text(str(exc))})]
    checks = [
        _check("urpcdk_receiver_receipt_package_type", receipt.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_RECEIPT_PACKAGE_TYPE, "Receiver receipt package type is valid."),
        _check("urpcdk_receiver_receipt_integrity", _integrity_ok(receipt), "Receiver receipt integrity is valid."),
        _check("urpcdk_receiver_receipt_decision", receipt.get("decision") == "accepted", "Receiver receipt decision is accepted."),
        _check("urpcdk_receiver_receipt_verification_status", receipt.get("verification_status") == "passed", "Receiver receipt verification status passed."),
        _check("urpcdk_receiver_receipt_kit_sha256", receipt.get("kit_sha256") == _sha256_path(kit_path), "Receiver receipt matches current kit ZIP hash."),
        _check("urpcdk_receiver_receipt_manifest_hash", receipt.get("kit_manifest_hash") == manifest.get("integrity_hash"), "Receiver receipt matches current kit manifest hash."),
        _check("urpcdk_receiver_receipt_verification_report_type", verification_report.get("package_type") == UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE, "Kit verification report package type is valid."),
        _check("urpcdk_receiver_receipt_verification_report_integrity", _integrity_ok(verification_report), "Kit verification report integrity is valid."),
        _check("urpcdk_receiver_receipt_verification_report_status", verification_report.get("status") == "passed", "Kit verification report status is passed."),
        _check("urpcdk_receiver_receipt_verification_report_zip_sha256", verification_report.get("zip_sha256") == _sha256_path(kit_path), "Kit verification report matches current kit ZIP hash."),
        _check("urpcdk_receiver_receipt_verification_report_manifest_hash", verification_report.get("manifest_hash") == manifest.get("integrity_hash"), "Kit verification report matches current kit manifest hash."),
        _check("urpcdk_receiver_receipt_verification_hash", receipt.get("verification_report_hash") == verification_report.get("integrity_hash"), "Receiver receipt matches current Kit verification report hash."),
    ]
    return checks


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, first_check: ImplementationDocument | None = None) -> ImplementationDocument:
    if first_check is not None:
        checks.insert(0, first_check)
    return build_verification_report(
        package_type=UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
        checks=checks,
        summary=summary,
        schema_version=UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    return json.loads(archive.read(name).decode("utf-8"))


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    return archive_redaction_check(archive, names, check_id="urpcdk_redaction_scan")


def _has_blocking_failures(checks: list[ImplementationDocument]) -> bool:
    return any(check.get("status") == "failed" and check.get("severity") == "blocking" for check in checks)


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"


def _is_within(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
