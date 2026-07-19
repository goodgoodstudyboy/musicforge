from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import write_json as write_json
from song_agent.domains.delivery.releases import stable_hash as stable_hash


RELEASE_AUDIO_CERTIFICATION_PACKAGE_TYPE = "release_audio_certification"
RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE = "release_audio_certification_verification"
RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "certification-report.json",
    "track-audio-matrix.json",
    "evidence-index.json",
    "blocker-register.json",
    "README.txt",
}
OPTIONAL_ENTRIES = {"certification-signoff.json"}
SENSITIVE_PATTERNS = [
    re.compile(rb"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_release_audio_certification_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_passed: bool = False,
    require_signed: bool = False,
    require_real_audio: bool = False,
    require_manual_review: bool = False,
    require_remediation_when_needed: bool = False,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "zip_path": zip_path.name,
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
        "release_id": None,
        "campaign_id": None,
        "track_count": 0,
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_certification_zip_exists", False, "Release Audio Certification ZIP exists."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_certification_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_certification_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("release_audio_certification_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_certification_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("release_audio_certification_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            expected_entries = set(REQUIRED_ENTRIES)
            if "certification-signoff.json" in names:
                expected_entries.add("certification-signoff.json")
            extra_entries = sorted(set(names) - expected_entries)
            missing_entries = sorted(expected_entries - set(names))
            checks.append(_check("release_audio_certification_zip_allowed_entries", not extra_entries, "ZIP contains only fixed Release Audio Certification entries.", {"extra": extra_entries}))
            checks.append(_check("release_audio_certification_zip_expected_entries", not missing_entries, "ZIP contains all expected Release Audio Certification entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(zf, "manifest.json")
            report = _read_json_entry(zf, "certification-report.json")
            matrix = _read_json_entry(zf, "track-audio-matrix.json")
            evidence = _read_json_entry(zf, "evidence-index.json")
            blocker_register = _read_json_entry(zf, "blocker-register.json")
            signoff = _read_json_entry(zf, "certification-signoff.json") if "certification-signoff.json" in names else None

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["release_id"] = manifest.get("release_id") or report.get("release_id")
            summary["campaign_id"] = report.get("campaign_id")
            summary["track_count"] = int((matrix.get("summary") or {}).get("track_count") or 0)

            checks.extend(_manifest_checks(zf, manifest, set(names), expected_entries=expected_entries, strict=strict))
            checks.append(_check("release_audio_certification_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_CERTIFICATION_PACKAGE_TYPE, "Manifest package_type is release_audio_certification."))
            checks.append(_check("release_audio_certification_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_CERTIFICATION_SCHEMA_VERSION, "Manifest schema version is supported."))
            checks.append(_check("release_audio_certification_manifest_integrity", _integrity_ok(manifest), "Manifest integrity hash is valid."))
            checks.append(_check("release_audio_certification_report_integrity", _integrity_ok(report), "Certification report integrity hash is valid."))
            checks.append(_check("release_audio_certification_matrix_integrity", _integrity_ok(matrix), "Track audio matrix integrity hash is valid."))
            checks.append(_check("release_audio_certification_evidence_index_integrity", _integrity_ok(evidence), "Evidence index integrity hash is valid."))
            checks.append(_check("release_audio_certification_blocker_register_integrity", _integrity_ok(blocker_register), "Blocker register integrity hash is valid."))
            checks.append(_check("release_audio_certification_manifest_report_binding", manifest.get("report_hash") == report.get("integrity_hash"), "Manifest binds certification report."))
            checks.append(_check("release_audio_certification_manifest_matrix_binding", manifest.get("matrix_hash") == matrix.get("integrity_hash"), "Manifest binds track matrix."))
            checks.append(_check("release_audio_certification_manifest_evidence_binding", manifest.get("evidence_index_hash") == evidence.get("integrity_hash"), "Manifest binds evidence index."))
            checks.append(_check("release_audio_certification_manifest_blocker_binding", manifest.get("blocker_register_hash") == blocker_register.get("integrity_hash"), "Manifest binds blocker register."))
            checks.append(_check("release_audio_certification_report_source_binding", manifest.get("source_hash") == report.get("source_hash") == matrix.get("source_hash") == evidence.get("source_hash") == blocker_register.get("source_hash"), "Certification documents bind the same source hash."))

            matrix_summary = _as_document(matrix.get("summary"))
            evidence_summary = _as_document(evidence.get("summary"))
            blockers = _as_list(blocker_register.get("blockers"))
            if require_passed:
                checks.append(_check("release_audio_certification_report_passed", report.get("status") == "passed", "Certification report is passed."))
            if require_real_audio:
                real_count = int(matrix_summary.get("real_audio_track_count") or 0)
                track_count = int(matrix_summary.get("track_count") or 0)
                checks.append(_check("release_audio_certification_real_audio_complete", track_count > 0 and real_count == track_count, "All certified tracks use release-ready real audio.", {"real_audio_track_count": real_count, "track_count": track_count}))
                checks.append(_check("release_audio_certification_no_test_fake", int(matrix_summary.get("test_fake_track_count") or 0) == 0, "No test fake WAV is counted as release-ready audio."))
            if require_manual_review:
                manual_count = int(matrix_summary.get("manual_accepted_track_count") or 0)
                track_count = int(matrix_summary.get("track_count") or 0)
                checks.append(_check("release_audio_certification_manual_review_complete", track_count > 0 and manual_count == track_count, "All certified tracks have manual accepted listening review.", {"manual_accepted_track_count": manual_count, "track_count": track_count}))
            if require_remediation_when_needed:
                remediation = _as_document(evidence_summary.get("remediation"))
                needed = bool(remediation.get("needed"))
                ok = (not needed) or remediation.get("status") == "passed"
                checks.append(_check("release_audio_certification_remediation_when_needed", ok, "Remediation evidence is passed when campaign issues require it.", remediation))
            checks.append(_check("release_audio_certification_no_blockers", not blockers and int(blocker_register.get("summary", {}).get("blocker_count") or 0) == 0, "Certification blocker register is empty.", {"blocker_count": len(blockers)}))
            checks.extend(_signoff_checks(signoff, manifest, report, require_signed=require_signed))
            checks.append(_redaction_check(zf, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_certification_zip_readable", False, "Release Audio Certification ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_certification_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_certification_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def _manifest_checks(zf: zipfile.ZipFile, manifest: ImplementationDocument, names: set[str], *, expected_entries: set[str], strict: bool) -> list[ImplementationDocument]:
    checks: list[dict[str, Any]] = []
    files = _as_list(manifest.get("files"))
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = expected_entries - {"manifest.json"}
    undeclared = sorted(effective_names - declared)
    extra_declared = sorted(declared - effective_names)
    fixed_extra_declared = sorted(declared - expected_files)
    fixed_missing_declared = sorted(expected_files - declared)
    checks.append(_check("release_audio_certification_manifest_files_present", bool(files), "Manifest declares package files."))
    checks.append(_check("release_audio_certification_no_undeclared_entries", not undeclared, "ZIP has no undeclared entries.", {"undeclared": undeclared}, blocking=strict or bool(undeclared)))
    checks.append(_check("release_audio_certification_declared_entries_exist", not extra_declared, "All manifest file entries exist.", {"missing": extra_declared}))
    checks.append(_check("release_audio_certification_manifest_fixed_files", not fixed_extra_declared and not fixed_missing_declared, "Manifest files match the fixed Release Audio Certification layout.", {"extra": fixed_extra_declared, "missing": fixed_missing_declared}))
    mismatches: list[str] = []
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
    checks.append(_check("release_audio_certification_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}))
    return checks


def _signoff_checks(signoff: ImplementationDocument | None, manifest: ImplementationDocument, report: ImplementationDocument, *, require_signed: bool) -> list[ImplementationDocument]:
    if signoff is None:
        return [_check("release_audio_certification_signoff_present", not require_signed, "Certification signoff is present when required.")]
    return [
        _check("release_audio_certification_signoff_integrity", _integrity_ok(signoff), "Certification signoff integrity hash is valid."),
        _check("release_audio_certification_signoff_status", signoff.get("status") == "signed", "Certification signoff status is signed."),
        _check("release_audio_certification_signoff_report_binding", signoff.get("certification_report_hash") == report.get("integrity_hash") == manifest.get("report_hash"), "Certification signoff binds current report."),
        _check("release_audio_certification_signoff_source_binding", signoff.get("source_hash") == report.get("source_hash") == manifest.get("source_hash"), "Certification signoff binds current source."),
        _check("release_audio_certification_manifest_signoff_binding", manifest.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds certification signoff."),
    ]


def _redaction_check(zf: zipfile.ZipFile, names: list[str]) -> ImplementationDocument:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt", ".jsonl")):
            continue
        data = zf.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("release_audio_certification_redaction_scan", not leaks, "Package text files do not contain obvious secrets or local paths.", {"leaks": leaks})


def _finish(checks: list[ImplementationDocument], summary: ImplementationDocument, *extra: ImplementationDocument) -> ImplementationDocument:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": RELEASE_AUDIO_CERTIFICATION_VERIFICATION_PACKAGE_TYPE,
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
