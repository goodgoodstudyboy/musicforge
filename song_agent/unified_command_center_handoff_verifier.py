from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import write_json
from song_agent.redaction import sanitize_sensitive_text
from song_agent.releases import stable_hash
from song_agent.unified_command_center_archive_verifier import (
    UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE,
    verify_unified_command_center_archive_package,
)


UNIFIED_COMMAND_CENTER_HANDOFF_PACKAGE_TYPE = "musicforge_final_handoff_pack"
UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE = "musicforge_final_handoff_pack_verification"
UNIFIED_COMMAND_CENTER_HANDOFF_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "README.txt",
    "manifest.json",
    "handoff-report.json",
    "package-index.json",
    "verification-instructions.txt",
    "archive-verification-report.json",
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


def verify_unified_command_center_handoff_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_archive: bool = False,
    archive_zip_path: Path | str | None = None,
    archive_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = 32,
    max_uncompressed_size_mb: int = 128,
    max_entry_count: int = 200,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {"zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None}
    if not zip_path.exists():
        return _finish(checks, summary, _check("ucc_handoff_zip_exists", False, "Unified Command Center Handoff ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("ucc_handoff_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            name_set = set(names)
            duplicates = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("ucc_handoff_no_duplicate_entries", not duplicates, "ZIP contains no duplicate entries.", {"duplicates": duplicates}))
            checks.append(_check("ucc_handoff_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("ucc_handoff_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("ucc_handoff_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            extra = sorted(name_set - REQUIRED_ENTRIES)
            missing = sorted(REQUIRED_ENTRIES - name_set)
            checks.append(_check("ucc_handoff_allowed_entries", not extra, "Handoff ZIP contains only fixed entries.", {"extra": extra}))
            checks.append(_check("ucc_handoff_required_entries", not missing, "Handoff ZIP contains all required entries.", {"missing": missing}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "handoff-report.json")
            package_index = _read_json_entry(archive, "package-index.json")
            archive_verification = _read_json_entry(archive, "archive-verification-report.json")
            summary.update({"center_id": manifest.get("center_id"), "manifest_hash": manifest.get("integrity_hash"), "archive_zip_sha256": (manifest.get("source") or {}).get("archive_zip_sha256")})
            checks.extend(_manifest_checks(archive, manifest, name_set))
            checks.append(_check("ucc_handoff_manifest_package_type", manifest.get("package_type") == UNIFIED_COMMAND_CENTER_HANDOFF_PACKAGE_TYPE, "Manifest package type is valid."))
            checks.append(_check("ucc_handoff_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            checks.append(_check("ucc_handoff_report_integrity", _integrity_ok(report), "Handoff report integrity hash is valid."))
            checks.append(_check("ucc_handoff_package_index_integrity", _integrity_ok(package_index), "Package index integrity hash is valid."))
            checks.append(_check("ucc_handoff_archive_verification_integrity", _integrity_ok(archive_verification), "Archive verification report integrity hash is valid."))
            source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
            report_source = report.get("source") if isinstance(report.get("source"), dict) else {}
            checks.extend(
                [
                    _check("ucc_handoff_source_hash_binding", source.get("source_hash") == report.get("source_hash") == package_index.get("source_hash"), "Handoff docs bind the same source hash."),
                    _check("ucc_handoff_report_binding", source.get("handoff_report_hash") == report.get("integrity_hash"), "Manifest binds handoff report."),
                    _check("ucc_handoff_package_index_binding", source.get("package_index_hash") == package_index.get("integrity_hash"), "Manifest binds package index."),
                    _check("ucc_handoff_archive_verification_binding", source.get("archive_verification_hash") == archive_verification.get("integrity_hash") == report_source.get("archive_verification_hash"), "Handoff binds archive verification report."),
                    _check("ucc_handoff_archive_verification_package_type", archive_verification.get("package_type") == UNIFIED_COMMAND_CENTER_ARCHIVE_VERIFICATION_PACKAGE_TYPE, "Archive verification package type is valid."),
                    _check("ucc_handoff_archive_verification_status", archive_verification.get("status") == "passed", "Archive verification report is passed."),
                    _check("ucc_handoff_archive_zip_binding", source.get("archive_zip_sha256") == archive_verification.get("zip_sha256") == report_source.get("archive_zip_sha256"), "Handoff binds archive ZIP sha256."),
                    _check("ucc_handoff_archive_manifest_binding", source.get("archive_manifest_hash") == archive_verification.get("manifest_hash") == report_source.get("archive_manifest_hash"), "Handoff binds archive manifest hash."),
                ]
            )
            if require_archive:
                checks.extend(_current_archive_checks(archive_zip_path, archive_verification_report_path, source))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("ucc_handoff_zip_readable", False, "Unified Command Center Handoff ZIP can be read.", {"error": sanitize_sensitive_text(str(exc))}))
    return _finish(checks, summary)


def write_unified_command_center_handoff_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def unified_command_center_handoff_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _current_archive_checks(archive_zip_path: Path | str | None, archive_verification_report_path: Path | str | None, source: dict[str, Any]) -> list[dict[str, Any]]:
    if not archive_zip_path:
        return [_check("ucc_handoff_archive_zip_required", False, "Current archive ZIP is required.")]
    if not archive_verification_report_path:
        return [_check("ucc_handoff_archive_verification_required", False, "Current archive verification report is required.")]
    archive_zip_path = Path(archive_zip_path)
    archive_verification_report_path = Path(archive_verification_report_path)
    checks = [
        _check("ucc_handoff_archive_zip_exists", archive_zip_path.exists(), "Current archive ZIP exists."),
        _check("ucc_handoff_archive_verification_exists", archive_verification_report_path.exists(), "Current archive verification report exists."),
    ]
    if any(check["status"] == "failed" for check in checks):
        return checks
    external = _read_json_file(archive_verification_report_path)
    runtime = verify_unified_command_center_archive_package(archive_zip_path, strict=True, require_signed=True)
    checks.extend(
        [
            _check("ucc_handoff_current_archive_verification_integrity", _integrity_ok(external), "Current archive verification report integrity is valid."),
            _check("ucc_handoff_current_archive_status", external.get("status") == "passed" and runtime.get("status") == "passed", "Current archive verification is passed.", {"external_status": external.get("status"), "runtime_status": runtime.get("status")}),
            _check("ucc_handoff_current_archive_zip_binding", source.get("archive_zip_sha256") == _sha256_path(archive_zip_path) == external.get("zip_sha256") == runtime.get("zip_sha256"), "Current archive ZIP matches handoff."),
            _check("ucc_handoff_current_archive_manifest_binding", source.get("archive_manifest_hash") == external.get("manifest_hash") == runtime.get("manifest_hash"), "Current archive manifest matches handoff."),
            _check("ucc_handoff_current_archive_verification_binding", source.get("archive_verification_hash") == external.get("integrity_hash"), "Current archive verification report matches handoff."),
        ]
    )
    return checks


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], names: set[str]) -> list[dict[str, Any]]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = REQUIRED_ENTRIES - {"manifest.json"}
    effective = names - {"manifest.json"}
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("path") or "")
        if not rel or rel not in names:
            continue
        data = archive.read(rel)
        info = archive.getinfo(rel)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(rel)
    return [
        _check("ucc_handoff_manifest_declares_files", declared == effective, "Manifest files exactly match ZIP entries.", {"declared_extra": sorted(declared - effective), "undeclared": sorted(effective - declared)}),
        _check("ucc_handoff_manifest_fixed_files", declared == expected, "Manifest files match fixed handoff structure.", {"extra": sorted(declared - expected), "missing": sorted(expected - declared)}),
        _check("ucc_handoff_manifest_file_hashes", not mismatches, "Manifest file hashes match ZIP contents.", {"mismatches": mismatches}),
    ]


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    blockers = [check["check_id"] for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check["check_id"] for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": UNIFIED_COMMAND_CENTER_HANDOFF_VERIFICATION_PACKAGE_TYPE,
        "schema_version": UNIFIED_COMMAND_CENTER_HANDOFF_SCHEMA_VERSION,
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {**summary, "check_count": len(checks), "failed_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, blocking: bool = True) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    return json.loads(archive.read(name).decode("utf-8"))


def _read_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload) and payload.get("integrity_hash") == _integrity_hash(payload)


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered:
        return False
    path = Path(name)
    if path.is_absolute():
        return False
    return all(part and part not in {".", ".."} and ":" not in part for part in name.split("/"))


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    offenders: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            offenders.append(name)
    return _check("ucc_handoff_redaction_scan", not offenders, "Handoff text files contain no obvious secrets or local workspace paths.", {"offenders": offenders})


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path | str | None) -> str | None:
    if not path or not Path(path).exists() or not Path(path).is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
