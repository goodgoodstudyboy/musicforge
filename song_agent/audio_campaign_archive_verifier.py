from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.projectio import write_json
from song_agent.releases import stable_hash


AUDIO_CAMPAIGN_ARCHIVE_PACKAGE_TYPE = "audio_campaign_archive"
AUDIO_CAMPAIGN_ARCHIVE_SCHEMA_VERSION = 1
REQUIRED_ENTRIES = {
    "manifest.json",
    "campaign.json",
    "campaign-report.json",
    "case-index.json",
    "campaign-signoff.json",
    "audio-campaign-verification-report.json",
    "governance-report.json",
    "analytics-summary.json",
    "reset-history.jsonl",
    "README.md",
}
SENSITIVE_PATTERNS = [
    re.compile(rb"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_audio_campaign_archive_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_signed: bool = False,
    require_verification_passed: bool = False,
    max_zip_size_mb: int = 256,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 5000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
        "campaign_id": None,
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("audio_campaign_archive_zip_exists", False, "Audio Campaign Archive ZIP does not exist."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("audio_campaign_archive_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("audio_campaign_archive_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("audio_campaign_archive_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("audio_campaign_archive_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("audio_campaign_archive_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            for required in REQUIRED_ENTRIES:
                checks.append(_check(f"audio_campaign_archive_required_{required.replace('/', '_').replace('.', '_')}", required in names, f"{required} exists."))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(zf, "manifest.json")
            campaign = _read_json_entry(zf, "campaign.json")
            report = _read_json_entry(zf, "campaign-report.json")
            case_index = _read_json_entry(zf, "case-index.json")
            signoff = _read_json_entry(zf, "campaign-signoff.json")
            verification = _read_json_entry(zf, "audio-campaign-verification-report.json")
            governance = _read_json_entry(zf, "governance-report.json")
            analytics = _read_json_entry(zf, "analytics-summary.json")

            summary["manifest_hash"] = _payload_hash(manifest)
            summary["campaign_id"] = manifest.get("campaign_id") or campaign.get("campaign_id")

            checks.extend(_manifest_checks(zf, manifest, set(names), strict=strict))
            checks.append(_check("audio_campaign_archive_manifest_package_type", manifest.get("package_type") == AUDIO_CAMPAIGN_ARCHIVE_PACKAGE_TYPE, "Manifest package_type is audio_campaign_archive."))
            checks.append(_check("audio_campaign_archive_manifest_schema_version", int(manifest.get("schema_version") or 0) == AUDIO_CAMPAIGN_ARCHIVE_SCHEMA_VERSION, "Manifest schema version is supported."))
            checks.append(_check("audio_campaign_archive_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            checks.append(_check("audio_campaign_archive_campaign_integrity", _integrity_ok(campaign), "Campaign integrity hash is valid."))
            checks.append(_check("audio_campaign_archive_report_integrity", _integrity_ok(report), "Campaign report integrity hash is valid."))
            checks.append(_check("audio_campaign_archive_case_index_integrity", _integrity_ok(case_index), "Case index integrity hash is valid."))
            checks.append(_check("audio_campaign_archive_signoff_integrity", _integrity_ok(signoff), "Campaign signoff integrity hash is valid."))
            checks.append(_check("audio_campaign_archive_governance_integrity", _integrity_ok(governance), "Governance report integrity hash is valid."))
            checks.append(_check("audio_campaign_archive_analytics_integrity", _integrity_ok(analytics), "Analytics summary integrity hash is valid."))

            source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
            checks.append(_check("audio_campaign_archive_report_binding", source.get("campaign_report_hash") == report.get("integrity_hash") == signoff.get("campaign_report_hash"), "Archive binds signed campaign report hash."))
            checks.append(_check("audio_campaign_archive_case_index_binding", source.get("case_index_hash") == case_index.get("integrity_hash") == signoff.get("case_index_hash"), "Archive binds signed case-index hash."))
            checks.append(_check("audio_campaign_archive_signoff_binding", source.get("campaign_signoff_hash") == signoff.get("integrity_hash"), "Archive binds campaign signoff hash."))
            checks.append(_check("audio_campaign_archive_source_binding", source.get("campaign_source_hash") == campaign.get("source_hash") == signoff.get("source_hash"), "Archive binds campaign source hash."))
            checks.append(_check("audio_campaign_archive_governance_binding", source.get("governance_report_hash") == governance.get("integrity_hash"), "Archive binds governance report hash."))
            checks.append(_check("audio_campaign_archive_analytics_binding", source.get("analytics_summary_hash") == analytics.get("integrity_hash"), "Archive binds analytics summary hash."))
            checks.append(_check("audio_campaign_archive_verification_binding", source.get("campaign_verification_hash") == verification.get("integrity_hash"), "Archive binds campaign verification report hash."))
            checks.append(_check("audio_campaign_archive_verification_status", verification.get("status") == "passed" or not require_verification_passed, "Campaign ZIP verification is passed when required.", {"status": verification.get("status")}))
            checks.append(_check("audio_campaign_archive_verification_zip_binding", source.get("campaign_zip_sha256") == verification.get("summary", {}).get("zip_sha256"), "Archive binds the verified campaign ZIP sha256."))
            checks.append(_check("audio_campaign_archive_signoff_status", signoff.get("status") == "signed" or not require_signed, "Campaign signoff status is signed when required."))
            checks.append(_redaction_check(zf, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("audio_campaign_archive_zip_readable", False, "Audio Campaign Archive ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_audio_campaign_archive_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def audio_campaign_archive_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _manifest_checks(zf: zipfile.ZipFile, manifest: dict[str, Any], names: set[str], *, strict: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    expected = names - {"manifest.json"}
    undeclared = sorted(expected - declared)
    extra_declared = sorted(declared - expected)
    checks.append(_check("audio_campaign_archive_manifest_files_present", bool(files), "Manifest declares package files."))
    checks.append(_check("audio_campaign_archive_no_undeclared_entries", not undeclared, "ZIP has no undeclared entries.", {"undeclared": undeclared}, blocking=strict or bool(undeclared)))
    checks.append(_check("audio_campaign_archive_declared_entries_exist", not extra_declared, "All manifest file entries exist.", {"missing": extra_declared}))
    unexpected = sorted(names - REQUIRED_ENTRIES)
    checks.append(_check("audio_campaign_archive_fixed_entry_allowlist", not unexpected, "Archive ZIP contains only fixed allow-list entries.", {"unexpected": unexpected}))
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = zf.getinfo(path)
        data = zf.read(path)
        expected_size = row.get("size_bytes")
        if row.get("sha256") != _sha256_bytes(data) or int(expected_size if expected_size is not None else -1) != info.file_size:
            mismatches.append(path)
    checks.append(_check("audio_campaign_archive_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _redaction_check(zf: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt", ".jsonl")):
            continue
        data = zf.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("audio_campaign_archive_redaction_scan", not leaks, "Archive text files do not contain obvious secrets or local paths.", {"leaks": leaks})


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": "audio_campaign_archive_verification",
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "ok": not blockers,
        "summary": {**summary, "check_count": len(checks), "blocker_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": [check.get("check_id") for check in blockers],
        "warnings": [check.get("check_id") for check in warnings],
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, blocking: bool = True) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(zf: zipfile.ZipFile, name: str) -> dict[str, Any]:
    with zf.open(name) as fp:
        data = json.loads(fp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    if not name or name.startswith("/") or name.startswith("../") or "/../" in name or name.endswith("/.."):
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or lowered.endswith(".zip") or "/.musicforge/" in lowered:
        return False
    return True


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _payload_hash(payload: dict[str, Any]) -> str:
    return stable_hash(payload)


def _sha256_path(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
