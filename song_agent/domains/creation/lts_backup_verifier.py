from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.domains.quality.music_acceptance import stable_hash
from song_agent.domains.studio.projectio import write_json


MAINTENANCE_BACKUP_PACKAGE_TYPE = "musicforge_lts_maintenance_backup"
MAINTENANCE_BACKUP_VERIFICATION_PACKAGE_TYPE = "musicforge_lts_maintenance_backup_verification_report"
MAINTENANCE_BACKUP_SCHEMA_VERSION = 1
LEGAL_SIDECAR_ENTRIES = {
    "manifest.json",
    "README.txt",
    "workspace-index.json",
    "redaction-report.json",
    "git-summary.json",
    "ga-summary.json",
    "maintenance-summary.json",
}

_SENSITIVE_BYTES_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(rb"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(rb"Bearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE),
    re.compile(rb"githubkey\.txt", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\\\\[A-Za-z0-9_.-]+\\[^\r\n]+", re.IGNORECASE),
)


def maintenance_backup_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in manifest.items() if key != "integrity_hash"})


def maintenance_backup_manifest_integrity_ok(manifest: dict[str, Any]) -> bool:
    expected = str(manifest.get("integrity_hash") or "")
    return bool(expected) and expected == maintenance_backup_manifest_hash(manifest)


def verify_maintenance_backup_zip(
    zip_path: Path | str,
    *,
    strict: bool = False,
    max_zip_size_mb: int = 512,
    max_uncompressed_size_mb: int = 2048,
    max_entry_count: int = 20000,
) -> dict[str, Any]:
    target = Path(zip_path)
    checks: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    entries: list[zipfile.ZipInfo] = []
    entry_names: list[str] = []

    if not target.exists() or not target.is_file():
        _add_check(checks, "lts_backup_zip_readable", "failed", "blocking", "Maintenance backup ZIP is missing.")
        return _report(target, checks, manifest)

    zip_size = target.stat().st_size
    _add_check(
        checks,
        "lts_backup_zip_size",
        "passed" if zip_size <= max_zip_size_mb * 1024 * 1024 else "failed",
        "blocking",
        "Maintenance backup ZIP size is within limit." if zip_size <= max_zip_size_mb * 1024 * 1024 else "Maintenance backup ZIP is too large.",
        {"zip_size_bytes": zip_size, "max_zip_size_mb": max_zip_size_mb},
    )

    try:
        with zipfile.ZipFile(target) as archive:
            entries = archive.infolist()
            entry_names = [info.filename for info in entries]
            manifest = _read_json_entry(archive, "manifest.json")
            _verify_entries(checks, entries, max_uncompressed_size_mb=max_uncompressed_size_mb, max_entry_count=max_entry_count)
            _verify_manifest(checks, manifest)
            _verify_manifest_entries(checks, archive, manifest, entry_names, strict=strict)
            _verify_redaction(checks, archive, entries)
    except zipfile.BadZipFile as exc:
        _add_check(checks, "lts_backup_zip_readable", "failed", "blocking", f"Maintenance backup ZIP is not readable: {exc}")
    except KeyError as exc:
        _add_check(checks, "lts_backup_manifest_present", "failed", "blocking", f"Required ZIP entry is missing: {exc}")
    except Exception as exc:
        _add_check(checks, "lts_backup_verifier_exception", "failed", "blocking", str(exc))

    return _report(target, checks, manifest)


def write_maintenance_backup_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    return write_json(Path(path), report)


def maintenance_backup_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") != "failed" else 1


def print_maintenance_backup_verification_report(report: dict[str, Any]) -> None:
    print(f"MusicForge maintenance backup verification: {report.get('status')}")
    for check in report.get("checks", []):
        marker = "ok" if check.get("status") == "passed" else check.get("status")
        print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")


def _verify_entries(checks: list[ImplementationDocument], entries: list[zipfile.ZipInfo], *, max_uncompressed_size_mb: int, max_entry_count: int) -> None:
    names = [info.filename for info in entries]
    raw_names = [str(getattr(info, "orig_filename", info.filename)) for info in entries]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    _add_check(
        checks,
        "lts_backup_zip_no_duplicate_entries",
        "passed" if not duplicates else "failed",
        "blocking",
        "ZIP has no duplicate entries." if not duplicates else "ZIP contains duplicate entries.",
        {"duplicates": duplicates[:20]},
    )
    unsafe = [name for name in raw_names if not _is_safe_entry_name(name)]
    _add_check(
        checks,
        "lts_backup_zip_path_safe",
        "passed" if not unsafe else "failed",
        "blocking",
        "ZIP entry names are POSIX relative paths." if not unsafe else "ZIP contains unsafe entry names.",
        {"unsafe": unsafe[:20]},
    )
    backslash = [name for name in raw_names if "\\" in name]
    _add_check(
        checks,
        "lts_backup_zip_no_backslash_entries",
        "passed" if not backslash else "failed",
        "blocking",
        "ZIP entry names do not contain backslashes." if not backslash else "ZIP entry names contain backslashes.",
        {"entries": backslash[:20]},
    )
    forbidden = [name for name in raw_names if _is_forbidden_entry(name)]
    _add_check(
        checks,
        "lts_backup_zip_forbidden_entries",
        "passed" if not forbidden else "failed",
        "blocking",
        "ZIP does not include forbidden local config or repository entries." if not forbidden else "ZIP includes forbidden local config or repository entries.",
        {"entries": forbidden[:20]},
    )
    total_uncompressed = sum(max(0, int(info.file_size or 0)) for info in entries)
    _add_check(
        checks,
        "lts_backup_zip_uncompressed_size",
        "passed" if total_uncompressed <= max_uncompressed_size_mb * 1024 * 1024 else "failed",
        "blocking",
        "ZIP uncompressed size is within limit." if total_uncompressed <= max_uncompressed_size_mb * 1024 * 1024 else "ZIP uncompressed size is too large.",
        {"total_uncompressed_size_bytes": total_uncompressed, "max_uncompressed_size_mb": max_uncompressed_size_mb},
    )
    _add_check(
        checks,
        "lts_backup_zip_entry_count",
        "passed" if len(entries) <= max_entry_count else "failed",
        "blocking",
        "ZIP entry count is within limit." if len(entries) <= max_entry_count else "ZIP has too many entries.",
        {"entry_count": len(entries), "max_entry_count": max_entry_count},
    )


def _verify_manifest(checks: list[ImplementationDocument], manifest: ImplementationDocument) -> None:
    _add_check(
        checks,
        "lts_backup_manifest_package_type",
        "passed" if manifest.get("package_type") == MAINTENANCE_BACKUP_PACKAGE_TYPE else "failed",
        "blocking",
        "Backup manifest package type is valid." if manifest.get("package_type") == MAINTENANCE_BACKUP_PACKAGE_TYPE else "Backup manifest package type is invalid.",
    )
    _add_check(
        checks,
        "lts_backup_manifest_schema_version",
        "passed" if manifest.get("schema_version") == MAINTENANCE_BACKUP_SCHEMA_VERSION else "failed",
        "blocking",
        "Backup manifest schema version is supported." if manifest.get("schema_version") == MAINTENANCE_BACKUP_SCHEMA_VERSION else "Backup manifest schema version is unsupported.",
    )
    _add_check(
        checks,
        "lts_backup_manifest_integrity",
        "passed" if maintenance_backup_manifest_integrity_ok(manifest) else "failed",
        "blocking",
        "Backup manifest integrity hash matches." if maintenance_backup_manifest_integrity_ok(manifest) else "Backup manifest integrity hash mismatch.",
    )


def _verify_manifest_entries(checks: list[ImplementationDocument], archive: zipfile.ZipFile, manifest: ImplementationDocument, entry_names: list[str], *, strict: bool) -> None:
    manifest_files = [item for item in manifest.get("files", []) if isinstance(item, dict)]
    declared_paths = [str(item.get("path") or "") for item in manifest_files]
    invalid_declared = [path for path in declared_paths if not path.startswith("data/musicforge/") or not _is_safe_entry_name(path)]
    _add_check(
        checks,
        "lts_backup_manifest_file_paths_allowed",
        "passed" if not invalid_declared else "failed",
        "blocking",
        "Manifest file paths are under data/musicforge/." if not invalid_declared else "Manifest declares unsupported file paths.",
        {"paths": invalid_declared[:20]},
    )
    expected = set(LEGAL_SIDECAR_ENTRIES) | set(declared_paths)
    actual = set(entry_names)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    _add_check(
        checks,
        "lts_backup_manifest_entries_match_zip",
        "passed" if not missing and not extra else "failed",
        "blocking" if missing or extra else "info",
        "Manifest files match ZIP entries." if not missing and not extra else "Manifest files do not match ZIP entries.",
        {"missing": missing[:20], "extra": extra[:20]},
    )
    hash_mismatches: list[dict[str, Any]] = []
    size_mismatches: list[dict[str, Any]] = []
    for item in manifest_files:
        path = str(item.get("path") or "")
        if path not in actual:
            continue
        data = archive.read(path)
        sha = hashlib.sha256(data).hexdigest()
        size = len(data)
        if sha != item.get("sha256"):
            hash_mismatches.append({"path": path, "expected": item.get("sha256"), "actual": sha})
        if int(item.get("size_bytes") or -1) != size:
            size_mismatches.append({"path": path, "expected": item.get("size_bytes"), "actual": size})
    _add_check(
        checks,
        "lts_backup_file_hashes_match",
        "passed" if not hash_mismatches else "failed",
        "blocking",
        "Manifest file hashes match ZIP content." if not hash_mismatches else "Manifest file hash mismatch.",
        {"mismatches": hash_mismatches[:20]},
    )
    _add_check(
        checks,
        "lts_backup_file_sizes_match",
        "passed" if not size_mismatches else "failed",
        "blocking",
        "Manifest file sizes match ZIP content." if not size_mismatches else "Manifest file size mismatch.",
        {"mismatches": size_mismatches[:20]},
    )


def _verify_redaction(checks: list[ImplementationDocument], archive: zipfile.ZipFile, entries: list[zipfile.ZipInfo]) -> None:
    findings: list[dict[str, Any]] = []
    for info in entries:
        if info.is_dir() or info.file_size > 10 * 1024 * 1024:
            continue
        try:
            data = archive.read(info.filename)
        except Exception:
            continue
        for pattern in _SENSITIVE_BYTES_PATTERNS:
            if pattern.search(data):
                findings.append({"path": info.filename, "pattern": pattern.pattern.decode("utf-8", errors="replace")})
                break
    _add_check(
        checks,
        "lts_backup_redaction_scan",
        "passed" if not findings else "failed",
        "blocking",
        "Backup ZIP contains no obvious token or local path strings." if not findings else "Backup ZIP contains token-like or local path strings.",
        {"findings": findings[:20]},
    )


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> ImplementationDocument:
    with archive.open(name) as file:
        data = json.loads(file.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must be a JSON object.")
    return data


def _report(target: Path, checks: list[ImplementationDocument], manifest: ImplementationDocument) -> ImplementationDocument:
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check.get("status") == "warning" or check.get("severity") == "warning"]
    report = {
        "package_type": MAINTENANCE_BACKUP_VERIFICATION_PACKAGE_TYPE,
        "schema_version": 1,
        "generated_at": _now(),
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "zip_sha256": _sha256_file(target) if target.exists() else None,
        "zip_size_bytes": target.stat().st_size if target.exists() else None,
        "manifest_hash": manifest.get("integrity_hash") if isinstance(manifest, dict) else None,
        "summary": {
            "backup_id": manifest.get("backup_id") if isinstance(manifest, dict) else None,
            "mode": manifest.get("mode") if isinstance(manifest, dict) else None,
            "file_count": len(manifest.get("files", [])) if isinstance(manifest, dict) and isinstance(manifest.get("files"), list) else 0,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "checks": checks,
    }
    report["integrity_hash"] = stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})
    return report


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_safe_entry_name(name: str) -> bool:
    if not name or "\\" in name:
        return False
    if name.startswith("/") or name.startswith("~"):
        return False
    if re.match(r"^[A-Za-z]:", name):
        return False
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        return False
    return True


def _is_forbidden_entry(name: str) -> bool:
    lowered = name.replace("\\", "/").lower()
    if lowered.startswith(".git/") or lowered.startswith(".musicforge/"):
        return True
    if lowered in {"data/musicforge/provider.json", "data/musicforge/renderer.json"}:
        return True
    if lowered.endswith("/provider.json") and "provider" in lowered:
        return True
    if lowered.endswith("/renderer.json") and "renderer" in lowered:
        return True
    if "token" in lowered or "githubkey" in lowered:
        return True
    return False


def _add_check(checks: list[ImplementationDocument], check_id: str, status: str, severity: str, message: str, detail: ImplementationDocument | None = None) -> None:
    checks.append({"check_id": check_id, "status": status, "severity": severity, "message": message, "detail": detail or {}})


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
