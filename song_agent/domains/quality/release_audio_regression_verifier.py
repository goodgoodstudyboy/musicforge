# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
import re as re
import zipfile as zipfile
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package as verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package as verify_release_audio_timeline_package
from song_agent.domains.delivery.releases import stable_hash as stable_hash


RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE = "release_audio_regression"
RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE = "release_audio_regression_verification"
RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION = 1

REQUIRED_ENTRIES = {
    "manifest.json",
    "regression-report.json",
    "track-regression-matrix.json",
    "issue-regression-index.json",
    "quality-delta-summary.json",
    "blocker-register.json",
    "baseline-binding.json",
    "current-binding.json",
    "README.txt",
}
OPTIONAL_ENTRIES = {"regression-signoff.json", "regression-signoff-history.jsonl"}

SENSITIVE_PATTERNS = [
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
    re.compile(rb"api[_-]?key\s*[:=]\s*[^,\s\"']+", re.IGNORECASE),
    re.compile(rb"[A-Za-z]:\\Users\\[^\\\r\n]+", re.IGNORECASE),
    re.compile(rb"\.musicforge[\\/]", re.IGNORECASE),
]


def verify_release_audio_regression_package(
    zip_path: Path | str,
    *,
    strict: bool = False,
    require_passed: bool = False,
    require_signed: bool = False,
    require_current: bool = False,
    require_baseline_current: bool = False,
    baseline_timeline_path: Path | str | None = None,
    baseline_timeline_verification_report_path: Path | str | None = None,
    baseline_certification_path: Path | str | None = None,
    baseline_certification_verification_report_path: Path | str | None = None,
    current_timeline_path: Path | str | None = None,
    current_timeline_verification_report_path: Path | str | None = None,
    current_certification_path: Path | str | None = None,
    current_certification_verification_report_path: Path | str | None = None,
    max_zip_size_mb: int = 128,
    max_uncompressed_size_mb: int = 512,
    max_entry_count: int = 1000,
) -> DomainDocument:
    zip_path = Path(zip_path)
    checks: list[ImplementationDocument] = []
    summary: ImplementationDocument = {
        "zip_path": str(zip_path),
        "zip_sha256": None,
        "zip_size_bytes": 0,
        "manifest_hash": None,
        "release_id": None,
        "baseline_release_id": None,
    }
    if not zip_path.exists():
        return _finish(checks, summary, _check("release_audio_regression_zip_exists", False, "Release Audio Regression ZIP exists."))

    summary["zip_sha256"] = _sha256_path(zip_path)
    summary["zip_size_bytes"] = zip_path.stat().st_size
    checks.append(_check("release_audio_regression_zip_size", zip_path.stat().st_size <= max_zip_size_mb * 1024 * 1024, "ZIP size is within limit."))
    if checks[-1]["status"] == "failed":
        return _finish(checks, summary)

    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            duplicate_names = sorted({name for name in names if names.count(name) > 1})
            checks.append(_check("release_audio_regression_no_duplicate_entries", not duplicate_names, "ZIP contains no duplicate entries.", {"duplicates": duplicate_names}))
            checks.append(_check("release_audio_regression_entry_count", len(infos) <= max_entry_count, "ZIP entry count is within limit.", {"entry_count": len(infos)}))
            checks.append(_check("release_audio_regression_uncompressed_size", sum(info.file_size for info in infos) <= max_uncompressed_size_mb * 1024 * 1024, "ZIP uncompressed size is within limit."))
            unsafe = [name for name in names if not _is_safe_entry(name)]
            checks.append(_check("release_audio_regression_zip_entry_paths_safe", not unsafe, "ZIP entries are safe POSIX relative paths.", {"unsafe": unsafe}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            expected_entries = set(REQUIRED_ENTRIES)
            if "regression-signoff.json" in names:
                expected_entries.add("regression-signoff.json")
            if "regression-signoff-history.jsonl" in names:
                expected_entries.add("regression-signoff-history.jsonl")
            extra_entries = sorted(set(names) - expected_entries)
            missing_entries = sorted(expected_entries - set(names))
            checks.append(_check("release_audio_regression_zip_allowed_entries", not extra_entries, "ZIP contains only fixed Release Audio Regression entries.", {"extra": extra_entries}))
            checks.append(_check("release_audio_regression_zip_expected_entries", not missing_entries, "ZIP contains all expected Release Audio Regression entries.", {"missing": missing_entries}))
            if any(check["status"] == "failed" for check in checks):
                return _finish(checks, summary)

            manifest = _read_json_entry(archive, "manifest.json")
            report = _read_json_entry(archive, "regression-report.json")
            matrix = _read_json_entry(archive, "track-regression-matrix.json")
            issue_index = _read_json_entry(archive, "issue-regression-index.json")
            quality = _read_json_entry(archive, "quality-delta-summary.json")
            blockers = _read_json_entry(archive, "blocker-register.json")
            baseline_binding = _read_json_entry(archive, "baseline-binding.json")
            current_binding = _read_json_entry(archive, "current-binding.json")
            signoff = _read_json_entry(archive, "regression-signoff.json") if "regression-signoff.json" in names else None
            history = _read_jsonl_entry(archive, "regression-signoff-history.jsonl") if "regression-signoff-history.jsonl" in names else []

            summary["manifest_hash"] = manifest.get("integrity_hash")
            summary["release_id"] = manifest.get("release_id") or report.get("release_id")
            summary["baseline_release_id"] = manifest.get("baseline_release_id") or report.get("baseline_release_id")

            checks.extend(_manifest_checks(archive, manifest, set(names), expected_entries=expected_entries, strict=strict))
            checks.append(_check("release_audio_regression_manifest_package_type", manifest.get("package_type") == RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE, "Manifest package_type is release_audio_regression."))
            checks.append(_check("release_audio_regression_manifest_schema_version", int(manifest.get("schema_version") or 0) == RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION, "Manifest schema version is supported."))
            for check_id, document in (
                ("release_audio_regression_manifest_integrity", manifest),
                ("release_audio_regression_report_integrity", report),
                ("release_audio_regression_matrix_integrity", matrix),
                ("release_audio_regression_issue_index_integrity", issue_index),
                ("release_audio_regression_quality_delta_integrity", quality),
                ("release_audio_regression_blocker_register_integrity", blockers),
                ("release_audio_regression_baseline_binding_integrity", baseline_binding),
                ("release_audio_regression_current_binding_integrity", current_binding),
            ):
                checks.append(_check(check_id, _integrity_ok(document), f"{check_id} hash is valid."))
            checks.extend(_document_binding_checks(manifest, report, matrix, issue_index, quality, blockers, baseline_binding, current_binding))

            baseline_facts = _external_facts(
                "baseline",
                timeline_path=baseline_timeline_path,
                timeline_report_path=baseline_timeline_verification_report_path,
                certification_path=baseline_certification_path,
                certification_report_path=baseline_certification_verification_report_path,
                required=require_baseline_current,
            )
            current_facts = _external_facts(
                "current",
                timeline_path=current_timeline_path,
                timeline_report_path=current_timeline_verification_report_path,
                certification_path=current_certification_path,
                certification_report_path=current_certification_verification_report_path,
                required=require_current,
            )
            checks.extend(baseline_facts["checks"])
            checks.extend(current_facts["checks"])
            if baseline_facts["binding"] and current_facts["binding"]:
                expected = _expected_documents(baseline_facts["binding"], current_facts["binding"], policy=_as_document(report.get("policy")))
                checks.extend(_external_binding_checks("baseline", baseline_binding, baseline_facts["binding"]))
                checks.extend(_external_binding_checks("current", current_binding, current_facts["binding"]))
                checks.extend(_recomputed_document_checks(report, matrix, issue_index, quality, blockers, expected))

            if require_passed:
                checks.append(_check("release_audio_regression_require_passed", report.get("status") == "passed", "Regression report is passed."))
            checks.extend(_signoff_checks(signoff, history, manifest, report, matrix, issue_index, quality, blockers, baseline_binding, current_binding, require_signed=require_signed))
            checks.append(_redaction_check(archive, names))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, ValueError) as exc:
        checks.append(_check("release_audio_regression_zip_readable", False, "Release Audio Regression ZIP can be read.", {"error": str(exc)}))
    return _finish(checks, summary)


def write_release_audio_regression_verification_report(report: DomainDocument, path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_regression_verification_exit_code(report: DomainDocument) -> int:
    return 0 if report.get("status") == "passed" else 1


def build_regression_documents_from_bindings(baseline_binding: DomainDocument, current_binding: DomainDocument, *, policy: DomainDocument | None = None) -> dict[str, DomainDocument]:
    return _expected_documents(baseline_binding, current_binding, policy=policy or {})


def _external_facts(
    prefix: str,
    *,
    timeline_path: Path | str | None,
    timeline_report_path: Path | str | None,
    certification_path: Path | str | None,
    certification_report_path: Path | str | None,
    required: bool,
) -> ImplementationDocument:
    checks: list[ImplementationDocument] = []
    if not timeline_path or not timeline_report_path or not certification_path or not certification_report_path:
        if required:
            checks.append(_check(f"release_audio_regression_{prefix}_external_evidence_required", False, f"{prefix} Timeline and Certification external evidence are required."))
        return {"checks": checks, "binding": None}
    timeline_zip = Path(timeline_path)
    timeline_report_file = Path(timeline_report_path)
    cert_zip = Path(certification_path)
    cert_report_file = Path(certification_report_path)
    try:
        timeline_report = read_json(timeline_report_file)
        cert_report = read_json(cert_report_file)
    except Exception as exc:
        checks.append(_check(f"release_audio_regression_{prefix}_external_report_readable", False, f"{prefix} external verification report could not be read: {exc}"))
        return {"checks": checks, "binding": None}
    cert_runtime = verify_release_audio_certification_package(
        cert_zip,
        strict=True,
        require_passed=True,
        require_signed=True,
        require_real_audio=True,
        require_manual_review=True,
        require_remediation_when_needed=True,
    )
    timeline_runtime = verify_release_audio_timeline_package(
        timeline_zip,
        strict=True,
        require_passed=True,
        require_signed=True,
        require_real_audio=True,
        require_manual_review=True,
        require_current_certification=True,
        release_audio_certification_path=cert_zip,
        release_audio_certification_verification_report_path=cert_report_file,
    )
    timeline_ok = (
        timeline_report.get("status") == "passed"
        and _integrity_ok(timeline_report)
        and timeline_report.get("zip_sha256") == _sha256_path(timeline_zip)
        and timeline_report.get("zip_size_bytes") == timeline_zip.stat().st_size
        and timeline_report.get("manifest_hash") == timeline_runtime.get("manifest_hash")
        and timeline_runtime.get("status") == "passed"
    )
    cert_ok = (
        cert_report.get("status") == "passed"
        and _integrity_ok(cert_report)
        and cert_report.get("zip_sha256") == _sha256_path(cert_zip)
        and cert_report.get("zip_size_bytes") == cert_zip.stat().st_size
        and cert_report.get("manifest_hash") == cert_runtime.get("manifest_hash")
        and cert_runtime.get("status") == "passed"
    )
    checks.append(_check(f"release_audio_regression_{prefix}_timeline_current", timeline_ok, f"{prefix} Timeline verification report matches current ZIP and Certification binding."))
    checks.append(_check(f"release_audio_regression_{prefix}_certification_current", cert_ok, f"{prefix} Certification verification report matches current ZIP."))
    facts = _timeline_facts(timeline_zip)
    binding = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "binding_kind": prefix,
        "release_id": timeline_runtime.get("summary", {}).get("release_id") or facts.get("release_id"),
        "timeline": {
            "zip_sha256": _sha256_path(timeline_zip),
            "zip_size_bytes": timeline_zip.stat().st_size,
            "manifest_hash": timeline_runtime.get("manifest_hash"),
            "verification_report_hash": timeline_report.get("integrity_hash"),
            "verification_status": timeline_report.get("status"),
            "source_hash": facts.get("timeline_source_hash"),
            "signoff_hash": facts.get("timeline_signoff_hash"),
        },
        "certification": {
            "zip_sha256": _sha256_path(cert_zip),
            "zip_size_bytes": cert_zip.stat().st_size,
            "manifest_hash": cert_runtime.get("manifest_hash"),
            "verification_report_hash": cert_report.get("integrity_hash"),
            "verification_status": cert_report.get("status"),
            "source_hash": cert_runtime.get("summary", {}).get("source_hash"),
            "signoff_hash": _certification_signoff_hash(cert_zip),
        },
        "track_identities": facts.get("track_identities", []),
        "facts": facts.get("tracks", []),
    }
    binding["payload_hash"] = stable_hash({key: value for key, value in binding.items() if key not in {"payload_hash", "integrity_hash"}})
    binding["integrity_hash"] = _integrity_hash(binding)
    return {"checks": checks, "binding": binding if timeline_ok and cert_ok else None}


def _timeline_facts(timeline_zip: Path) -> ImplementationDocument:
    with zipfile.ZipFile(timeline_zip) as archive:
        report = _read_json_entry(archive, "audio-timeline-report.json")
        track_index = _read_json_entry(archive, "track-timeline-index.json")
        trend = _read_json_entry(archive, "quality-trend.json")
        taxonomy = _read_json_entry(archive, "issue-taxonomy.json")
        risks = _read_json_entry(archive, "risk-register.json")
        signoff = _read_json_entry(archive, "timeline-signoff.json") if "timeline-signoff.json" in [item.filename for item in archive.infolist()] else {}
    tracks: list[ImplementationDocument] = []
    identities: list[ImplementationDocument] = []
    issue_by_track: dict[str, dict[str, int]] = {}
    for issue in taxonomy.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        for track_id in issue.get("track_ids") or []:
            key = str(track_id or "")
            item = issue_by_track.setdefault(key, {"high": 0, "critical": 0, "open": 0})
            severity = str(issue.get("severity_max") or "info")
            count = int(issue.get("open_count") or 0)
            item["open"] += count
            if severity == "high":
                item["high"] += count
            if severity in {"critical", "blocking"}:
                item["critical"] += count
    for row in track_index.get("tracks") or []:
        if not isinstance(row, dict):
            continue
        track_id = str(row.get("track_id") or "")
        issues = issue_by_track.get(track_id, {"high": 0, "critical": 0, "open": int(row.get("open_issue_count") or 0)})
        identity = {
            "track_id": row.get("track_id"),
            "project_id": row.get("project_id"),
            "version_id": row.get("version_id"),
            "title": row.get("title"),
            "normalized_title": _normalize_title(row.get("title")),
            "final_export_hash": row.get("final_export_hash"),
            "current_final_export_hash": row.get("current_final_export_hash"),
        }
        identities.append(identity)
        tracks.append(
            {
                **identity,
                "manual_rating": _manual_rating(row),
                "accepted_review_count": 1 if row.get("review_status") == "accepted" else 0,
                "needs_fix_count": 1 if row.get("review_status") == "needs_fix" else 0,
                "rejected_count": 1 if row.get("review_status") == "rejected" else 0,
                "high_issue_count": issues.get("high", 0),
                "critical_issue_count": issues.get("critical", 0),
                "open_issue_count": int(row.get("open_issue_count") or issues.get("open", 0)),
                "remediation_count": int(row.get("fix_sprint_count") or 0),
                "manual_review_count": int(row.get("manual_review_count") or 0),
                "real_audio_review_count": int(row.get("real_audio_review_count") or 0),
                "test_fake_count": int(row.get("test_fake_count") or 0),
                "audio_health_status": "passed" if row.get("status") == "certified" else "failed",
                "certification_status": row.get("certification_status") or row.get("status"),
            }
        )
    return {
        "release_id": report.get("release_id"),
        "timeline_id": report.get("timeline_id"),
        "timeline_source_hash": report.get("source_hash"),
        "timeline_signoff_hash": signoff.get("integrity_hash"),
        "track_identities": identities,
        "tracks": tracks,
        "trend_summary": trend.get("summary") or {},
        "risk_summary": risks.get("summary") or {},
    }


from song_agent.domains.quality import v142_rarv_readiness as _v142_rarv_readiness
from song_agent.domains.quality.v142_rarv_readiness import (
    _expected_documents,
    _external_binding_checks,
    _recomputed_document_checks,
    _document_binding_checks,
    _signoff_checks,
    _history_chain_ok,
    _manifest_checks,
    _finish,
    _check,
    _read_json_entry,
    _read_jsonl_entry,
    _is_safe_entry,
    _redaction_check,
    _certification_signoff_hash,
    _manual_rating,
    _identity_key,
    _normalize_title,
    _num,
    _blocker,
    _strip_binding,
    _semantic_hash,
    _strip_volatile,
    _integrity_hash,
    _integrity_ok,
    _sha256_path,
    _sha256_bytes,
)

_v142_rarv_readiness.bind_globals(globals())
