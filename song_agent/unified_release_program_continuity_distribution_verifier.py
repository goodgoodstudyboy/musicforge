from __future__ import annotations

import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import read_json, write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_release_program_continuity_verifier import (
    UNIFIED_RELEASE_PROGRAM_CONTINUITY_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_continuity_package,
)
from song_agent.unified_release_program_vault_operations_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_OPERATIONS_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_operations_package,
)
from song_agent.unified_release_program_vault_verifier import (
    UNIFIED_RELEASE_PROGRAM_VAULT_VERIFICATION_PACKAGE_TYPE,
    verify_unified_release_program_vault_package,
)


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

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[^\\\r\n]+\\[^\\\r\n]+"),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


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


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], name_set: set[str]) -> list[dict[str, Any]]:
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


def _package_index_checks(archive: zipfile.ZipFile, package_index: dict[str, Any]) -> list[dict[str, Any]]:
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


def _verification_index_checks(verification_index: dict[str, Any], verification_docs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
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
    source_binding: dict[str, Any],
    package_index: dict[str, Any],
    verification_index: dict[str, Any],
    verification_docs: dict[str, dict[str, Any]],
    binding_docs: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
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


def _deep_checks(archive: zipfile.ZipFile, verification_docs: dict[str, dict[str, Any]], binding_docs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
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


def _receiver_receipt_checks(receiver_receipt_path: Path | str | None, kit_path: Path, manifest: dict[str, Any], kit_verification_report_path: Path | str | None) -> list[dict[str, Any]]:
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


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], first_check: dict[str, Any] | None = None) -> dict[str, Any]:
    if first_check is not None:
        checks.insert(0, first_check)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("severity") == "warning"]
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "schema_version": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_SCHEMA_VERSION,
        "package_type": UNIFIED_RELEASE_PROGRAM_CONTINUITY_DISTRIBUTION_VERIFICATION_PACKAGE_TYPE,
        "status": status,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    return report


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, severity: str = "blocking") -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "severity": severity, "message": message, "details": details or {}}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _integrity_hash(doc: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in doc.items() if key != "integrity_hash"})


def _integrity_ok(doc: dict[str, Any]) -> bool:
    return bool(doc) and doc.get("integrity_hash") == _integrity_hash(doc)


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    path = Path(name)
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    return bool(name and not path.is_absolute() and ".." not in path.parts)


def _raw_unsafe_entry_names(zip_path: Path) -> list[str]:
    data = zip_path.read_bytes()
    unsafe: list[str] = []
    offset = 0
    while True:
        offset = data.find(b"PK\x01\x02", offset)
        if offset < 0:
            break
        if offset + 46 > len(data):
            break
        name_len = int.from_bytes(data[offset + 28 : offset + 30], "little")
        extra_len = int.from_bytes(data[offset + 30 : offset + 32], "little")
        comment_len = int.from_bytes(data[offset + 32 : offset + 34], "little")
        name = data[offset + 46 : offset + 46 + name_len]
        if b"\\" in name:
            unsafe.append(name.decode("utf-8", errors="replace"))
        offset += 46 + name_len + extra_len + comment_len
    return unsafe


def _zip_has_no_trailing_data(zip_path: Path) -> bool:
    data = zip_path.read_bytes()
    eocd_signature = b"PK\x05\x06"
    search_start = max(0, len(data) - (65535 + 22))
    offset = data.rfind(eocd_signature, search_start)
    if offset < 0 or offset + 22 > len(data):
        return False
    comment_len = int.from_bytes(data[offset + 20 : offset + 22], "little")
    return offset + 22 + comment_len == len(data)


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    offenders = []
    for name in names:
        if not name.lower().endswith((".json", ".jsonl", ".txt", ".md", ".html")):
            continue
        data = archive.read(name)
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(data):
                offenders.append(name)
                break
    return _check("urpcdk_redaction_scan", not offenders, "Continuity Distribution Kit contains no obvious secrets or local paths.", {"offenders": sorted(set(offenders))})


def _has_blocking_failures(checks: list[dict[str, Any]]) -> bool:
    return any(check.get("status") == "failed" and check.get("severity") == "blocking" for check in checks)


def _safe_check_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value.strip("/").replace("/", "_"))[:120] or "root"


def _is_within(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
