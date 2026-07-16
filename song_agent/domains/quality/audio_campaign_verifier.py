from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.delivery.releases import stable_hash as stable_hash


AUDIO_CAMPAIGN_PACKAGE_TYPE = "audio_campaign"
AUDIO_CAMPAIGN_SCHEMA_VERSION = 1
REQUIRED_ENTRIES = {"manifest.json", "campaign-report.json", "case-index.json", "README.md"}
SENSITIVE_PATTERNS = [
    re.compile(rb"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_audio_campaign_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_real_audio: bool = False,
    require_manual_review: bool = False,
    require_fix_sprints_closed: bool = False,
    require_signed: bool = False,
    require_no_open_high: bool = False,
    require_no_open_critical: bool = False,
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
        "case_count": 0,
    }
    manifest: dict[str, Any] = {}
    report: dict[str, Any] = {}
    signoff: dict[str, Any] | None = None

    if not zip_path.exists():
        return _finish(checks, summary, _check("audio_campaign_zip_exists", False, "Audio Campaign ZIP does not exist."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("audio_campaign_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("audio_campaign_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("audio_campaign_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("audio_campaign_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("audio_campaign_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            for required in REQUIRED_ENTRIES:
                checks.append(_check(f"audio_campaign_required_{required.replace('/', '_').replace('.', '_')}", required in names, f"{required} exists."))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(zf, "manifest.json")
            report = _read_json_entry(zf, "campaign-report.json")
            case_index = _read_json_entry(zf, "case-index.json")
            if "campaign-signoff.json" in names:
                signoff = _read_json_entry(zf, "campaign-signoff.json")

            summary["manifest_hash"] = _payload_hash(manifest)
            summary["campaign_id"] = manifest.get("campaign_id") or report.get("campaign_id")
            summary["case_count"] = int((report.get("summary") or {}).get("case_count") or len(case_index.get("cases") or []))

            checks.extend(_manifest_checks(zf, manifest, set(names), strict=strict))
            checks.append(_check("audio_campaign_manifest_package_type", manifest.get("package_type") == AUDIO_CAMPAIGN_PACKAGE_TYPE, "Manifest package_type is audio_campaign."))
            checks.append(_check("audio_campaign_manifest_schema_version", int(manifest.get("schema_version") or 0) == AUDIO_CAMPAIGN_SCHEMA_VERSION, "Manifest schema version is supported."))
            checks.append(_check("audio_campaign_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            checks.append(_check("audio_campaign_report_integrity", _integrity_ok(report), "Campaign report integrity hash is valid."))
            checks.append(
                _check(
                    "audio_campaign_case_index_binding",
                    manifest.get("case_index_hash") == case_index.get("integrity_hash"),
                    "Manifest binds case-index integrity hash.",
                    {"manifest_case_index_hash": manifest.get("case_index_hash"), "case_index_hash": case_index.get("integrity_hash")},
                )
            )
            checks.append(
                _check(
                    "audio_campaign_report_binding",
                    manifest.get("campaign_report_hash") == report.get("integrity_hash"),
                    "Manifest binds campaign report integrity hash.",
                    {"manifest_report_hash": manifest.get("campaign_report_hash"), "report_hash": report.get("integrity_hash")},
                )
            )

            checks.extend(_signoff_checks(signoff, report, require_signed=require_signed))
            checks.extend(_requirement_checks(report, require_real_audio=require_real_audio, require_manual_review=require_manual_review, require_fix_sprints_closed=require_fix_sprints_closed, require_no_open_high=require_no_open_high, require_no_open_critical=require_no_open_critical))
            checks.append(_redaction_check(zf, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("audio_campaign_zip_readable", False, "Audio Campaign ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_audio_campaign_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def audio_campaign_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _manifest_checks(zf: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str], *, strict: bool) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    checks.append(_check("audio_campaign_manifest_files_present", bool(files), "Manifest declares package files."))
    effective_names = names - {"manifest.json"}
    undeclared = sorted(effective_names - declared)
    extra_declared = sorted(declared - effective_names)
    checks.append(_check("audio_campaign_no_undeclared_entries", not undeclared, "ZIP has no undeclared entries.", {"undeclared": undeclared}, blocking=strict or bool(undeclared)))
    checks.append(_check("audio_campaign_declared_entries_exist", not extra_declared, "All manifest file entries exist.", {"missing": extra_declared}))
    mismatches = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = zf.getinfo(path)
        data = zf.read(path)
        sha = _sha256_bytes(data)
        if row.get("sha256") != sha or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    checks.append(_check("audio_campaign_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _signoff_checks(signoff: ImplementationDocument | None, report: ImplementationDocument, *, require_signed: bool) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    if signoff is None:
        checks.append(_check("audio_campaign_signoff_present", not require_signed, "Campaign signoff is present when required."))
        return checks
    checks.append(_check("audio_campaign_signoff_integrity", _integrity_ok(signoff), "Campaign signoff integrity hash is valid."))
    checks.append(_check("audio_campaign_signoff_status", signoff.get("status") == "signed", "Campaign signoff status is signed."))
    checks.append(
        _check(
            "audio_campaign_signoff_report_binding",
            signoff.get("campaign_report_hash") == report.get("integrity_hash"),
            "Campaign signoff binds current report hash.",
            {"signoff_report_hash": signoff.get("campaign_report_hash"), "report_hash": report.get("integrity_hash")},
        )
    )
    return checks


def _requirement_checks(
    report: ImplementationDocument,
    *,
    require_real_audio: bool,
    require_manual_review: bool,
    require_fix_sprints_closed: bool,
    require_no_open_high: bool,
    require_no_open_critical: bool,
) -> list[ImplementationDocument]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    case_count = int(summary.get("case_count") or 0)
    checks: list[dict[str, Any]] = []
    checks.append(_check("audio_campaign_report_status", report.get("status") == "passed", "Campaign report status is passed."))
    if require_real_audio:
        checks.append(
            _check(
                "audio_campaign_require_real_audio",
                case_count > 0 and int(summary.get("real_audio_count") or 0) == case_count and int(summary.get("test_fake_count") or 0) == 0,
                "All campaign cases use release-ready real WAV audio.",
                {"case_count": case_count, "real_audio_count": summary.get("real_audio_count"), "test_fake_count": summary.get("test_fake_count")},
            )
        )
    if require_manual_review:
        checks.append(
            _check(
                "audio_campaign_require_manual_review",
                case_count > 0 and int(summary.get("manual_review_count") or 0) == case_count and int(summary.get("synthetic_review_count") or 0) == 0,
                "All campaign cases have manual playback-confirmed review.",
                {"case_count": case_count, "manual_review_count": summary.get("manual_review_count"), "synthetic_review_count": summary.get("synthetic_review_count")},
            )
        )
    if require_fix_sprints_closed:
        checks.append(
            _check(
                "audio_campaign_require_fix_sprints_closed",
                int(summary.get("open_fix_sprint_count") or 0) == 0 and int(summary.get("failed_fix_sprint_count") or 0) == 0,
                "All required Audio Fix Sprints are closed with passed closeout.",
                {"open_fix_sprint_count": summary.get("open_fix_sprint_count"), "failed_fix_sprint_count": summary.get("failed_fix_sprint_count")},
            )
        )
    if require_no_open_high:
        checks.append(_check("audio_campaign_no_open_high_markers", int(summary.get("open_high_marker_count") or 0) == 0, "No open high markers remain."))
    if require_no_open_critical:
        checks.append(_check("audio_campaign_no_open_critical_markers", int(summary.get("open_critical_marker_count") or 0) == 0, "No open critical markers remain."))
    return checks


def _redaction_check(zf: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt")):
            continue
        data = zf.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("audio_campaign_redaction_scan", not leaks, "Package text files do not contain obvious secrets or local paths.", {"leaks": leaks})


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": "audio_campaign_verification",
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "ok": not blockers,
        "summary": {**summary, "check_count": len(checks), "blocker_count": len(blockers), "warning_count": len(warnings)},
        "checks": checks,
        "blockers": [check.get("check_id") for check in blockers],
        "warnings": [check.get("check_id") for check in warnings],
    }
    report["integrity_hash"] = _integrity_hash(report)
    return report


def _check(check_id: str, passed: bool, message: str, details: ImplementationDocument | None = None, *, blocking: bool = True) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(zf: zipfile.ZipFile, name: str) -> ImplementationDocument:
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


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _payload_hash(payload: ImplementationDocument) -> str:
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
