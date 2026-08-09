from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_campaign_remediation_contracts import AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE as AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE, AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION as AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION
from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.delivery.releases import stable_hash as stable_hash


REQUIRED_ENTRIES = {"manifest.json", "remediation-plan.json", "action-queue.json", "closeout-report.json", "linked-fix-sprints.json", "README.txt"}
OPTIONAL_ENTRIES = {"remediation-signoff.json"}
SENSITIVE_PATTERNS = [
    re.compile(rb"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_audio_campaign_remediation_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_passed: bool = False,
    require_signed: bool = False,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary = {"zip_path": zip_path.name, "zip_sha256": None, "zip_size_bytes": 0, "manifest_hash": None, "release_id": None, "campaign_id": None, "issue_count": 0}
    if not zip_path.exists():
        return _finish(checks, summary, _check("audio_campaign_remediation_zip_exists", False, "Audio Campaign remediation ZIP exists."))
    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("audio_campaign_remediation_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("audio_campaign_remediation_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("audio_campaign_remediation_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("audio_campaign_remediation_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("audio_campaign_remediation_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)
            expected_entries = set(REQUIRED_ENTRIES)
            if "remediation-signoff.json" in names:
                expected_entries.add("remediation-signoff.json")
            extra_entries = sorted(set(names) - expected_entries)
            missing_entries = sorted(expected_entries - set(names))
            checks.append(_check("audio_campaign_remediation_zip_allowed_entries", not extra_entries, "ZIP contains only fixed Audio Campaign remediation entries.", {"extra": extra_entries}))
            checks.append(_check("audio_campaign_remediation_zip_expected_entries", not missing_entries, "ZIP contains all expected Audio Campaign remediation entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)
            for required in REQUIRED_ENTRIES:
                checks.append(_check(f"audio_campaign_remediation_required_{required.replace('/', '_').replace('.', '_')}", required in names, f"{required} exists."))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(zf, "manifest.json")
            plan = _read_json_entry(zf, "remediation-plan.json")
            queue = _read_json_entry(zf, "action-queue.json")
            closeout = _read_json_entry(zf, "closeout-report.json")
            linked = _read_json_entry(zf, "linked-fix-sprints.json")
            signoff = _read_json_entry(zf, "remediation-signoff.json") if "remediation-signoff.json" in names else None
            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["release_id"] = manifest.get("release_id") or closeout.get("release_id")
            summary["campaign_id"] = manifest.get("campaign_id") or closeout.get("campaign_id")
            summary["issue_count"] = int((closeout.get("summary") or {}).get("issue_count") or 0)

            checks.extend(_manifest_checks(zf, manifest, set(names), expected_entries=expected_entries, strict=strict))
            checks.append(_check("audio_campaign_remediation_manifest_package_type", manifest.get("package_type") == AUDIO_CAMPAIGN_REMEDIATION_PACKAGE_TYPE, "Manifest package_type is audio_campaign_remediation."))
            checks.append(_check("audio_campaign_remediation_manifest_schema_version", int(manifest.get("schema_version") or 0) == AUDIO_CAMPAIGN_REMEDIATION_SCHEMA_VERSION, "Manifest schema version is supported."))
            checks.append(_check("audio_campaign_remediation_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            checks.append(_check("audio_campaign_remediation_plan_integrity", _integrity_ok(plan), "Remediation plan integrity hash is valid."))
            checks.append(_check("audio_campaign_remediation_queue_integrity", _integrity_ok(queue), "Action queue integrity hash is valid."))
            checks.append(_check("audio_campaign_remediation_closeout_integrity", _integrity_ok(closeout), "Closeout report integrity hash is valid."))
            checks.append(_check("audio_campaign_remediation_manifest_plan_binding", manifest.get("plan_hash") == plan.get("integrity_hash"), "Manifest binds plan hash."))
            checks.append(_check("audio_campaign_remediation_manifest_queue_binding", manifest.get("queue_hash") == queue.get("integrity_hash"), "Manifest binds queue hash."))
            checks.append(_check("audio_campaign_remediation_manifest_closeout_binding", manifest.get("closeout_hash") == closeout.get("integrity_hash"), "Manifest binds closeout hash."))
            checks.append(_check("audio_campaign_remediation_closeout_source_binding", closeout.get("source", {}).get("plan_source_hash") == plan.get("source_hash") and closeout.get("source", {}).get("queue_integrity_hash") == queue.get("integrity_hash"), "Closeout binds plan and queue source."))
            linked_ids = {str(row.get("fix_sprint_id") or "") for row in linked.get("fix_sprints", []) if isinstance(row, dict)}
            closeout_ids = {str(row.get("fix_sprint_id") or "") for row in closeout.get("issues", []) if isinstance(row, dict) and row.get("fix_sprint_id")}
            checks.append(_check("audio_campaign_remediation_linked_fix_sprints_match", closeout_ids <= linked_ids, "Linked Fix Sprint summary covers closeout issues.", {"missing": sorted(closeout_ids - linked_ids)}))
            if require_passed:
                checks.append(_check("audio_campaign_remediation_closeout_passed", closeout.get("status") == "passed", "Closeout report is passed."))
            checks.extend(_signoff_checks(signoff, manifest, closeout, require_signed=require_signed))
            checks.append(_redaction_check(zf, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("audio_campaign_remediation_zip_readable", False, "Audio Campaign remediation ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_audio_campaign_remediation_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def audio_campaign_remediation_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _manifest_checks(zf: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str], *, expected_entries: set[str], strict: bool) -> list[ImplementationDocument]:
    checks = []
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = expected_entries - {"manifest.json"}
    undeclared = sorted(effective_names - declared)
    extra_declared = sorted(declared - effective_names)
    fixed_extra_declared = sorted(declared - expected_files)
    fixed_missing_declared = sorted(expected_files - declared)
    checks.append(_check("audio_campaign_remediation_manifest_files_present", bool(files), "Manifest declares package files."))
    checks.append(_check("audio_campaign_remediation_no_undeclared_entries", not undeclared, "ZIP has no undeclared entries.", {"undeclared": undeclared}, blocking=strict or bool(undeclared)))
    checks.append(_check("audio_campaign_remediation_declared_entries_exist", not extra_declared, "All manifest file entries exist.", {"missing": extra_declared}))
    checks.append(
        _check(
            "audio_campaign_remediation_manifest_fixed_files",
            not fixed_extra_declared and not fixed_missing_declared,
            "Manifest files match the fixed Audio Campaign remediation package layout.",
            {"extra": fixed_extra_declared, "missing": fixed_missing_declared},
        )
    )
    mismatches = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = zf.getinfo(path)
        data = zf.read(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    checks.append(_check("audio_campaign_remediation_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _signoff_checks(signoff: ImplementationDocument | None, manifest: ImplementationDocument, closeout: ImplementationDocument, *, require_signed: bool) -> list[ImplementationDocument]:
    if signoff is None:
        return [_check("audio_campaign_remediation_signoff_present", not require_signed, "Remediation signoff is present when required.")]
    return [
        _check("audio_campaign_remediation_signoff_integrity", _integrity_ok(signoff), "Remediation signoff integrity hash is valid."),
        _check("audio_campaign_remediation_signoff_status", signoff.get("status") == "signed", "Remediation signoff status is signed."),
        _check("audio_campaign_remediation_signoff_closeout_binding", signoff.get("closeout_hash") == closeout.get("integrity_hash") == manifest.get("closeout_hash"), "Remediation signoff binds current closeout."),
        _check("audio_campaign_remediation_manifest_signoff_binding", manifest.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds remediation signoff."),
    ]


def _redaction_check(zf: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    leaks = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt")):
            continue
        data = zf.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("audio_campaign_remediation_redaction_scan", not leaks, "Package text files do not contain obvious secrets or local paths.", {"leaks": leaks})


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": "audio_campaign_remediation_verification",
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "ok": not blockers,
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes"),
        "manifest_hash": summary.get("manifest_hash"),
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
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered or lowered.endswith(".zip"):
        return False
    return True


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: ImplementationDocument) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


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
