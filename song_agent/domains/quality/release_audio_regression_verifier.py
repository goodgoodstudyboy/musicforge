from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.quality.release_audio_certification_verifier import verify_release_audio_certification_package
from song_agent.domains.quality.release_audio_timeline_verifier import verify_release_audio_timeline_package
from song_agent.application.legacy_dependencies.releases import stable_hash


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
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    checks: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
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
                expected = _expected_documents(baseline_facts["binding"], current_facts["binding"], policy=report.get("policy") if isinstance(report.get("policy"), dict) else {})
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


def write_release_audio_regression_verification_report(report: dict[str, Any], path: Path | str) -> None:
    write_json(Path(path), report)


def release_audio_regression_verification_exit_code(report: dict[str, Any]) -> int:
    return 0 if report.get("status") == "passed" else 1


def build_regression_documents_from_bindings(baseline_binding: dict[str, Any], current_binding: dict[str, Any], *, policy: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    return _expected_documents(baseline_binding, current_binding, policy=policy or {})


def _external_facts(
    prefix: str,
    *,
    timeline_path: Path | str | None,
    timeline_report_path: Path | str | None,
    certification_path: Path | str | None,
    certification_report_path: Path | str | None,
    required: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
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


def _timeline_facts(timeline_zip: Path) -> dict[str, Any]:
    with zipfile.ZipFile(timeline_zip) as archive:
        report = _read_json_entry(archive, "audio-timeline-report.json")
        track_index = _read_json_entry(archive, "track-timeline-index.json")
        trend = _read_json_entry(archive, "quality-trend.json")
        taxonomy = _read_json_entry(archive, "issue-taxonomy.json")
        risks = _read_json_entry(archive, "risk-register.json")
        signoff = _read_json_entry(archive, "timeline-signoff.json") if "timeline-signoff.json" in [item.filename for item in archive.infolist()] else {}
    tracks: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
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


def _expected_documents(baseline_binding: dict[str, Any], current_binding: dict[str, Any], *, policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    baseline_tracks = baseline_binding.get("facts") if isinstance(baseline_binding.get("facts"), list) else []
    current_tracks = current_binding.get("facts") if isinstance(current_binding.get("facts"), list) else []
    baseline_by_key = {_identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage")): row for row in baseline_tracks if _identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage"))}
    current_by_key = {_identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage")): row for row in current_tracks if _identity_key(row, mode=str(policy.get("identity_mode") or "release_track_lineage"))}
    keys = sorted(set(baseline_by_key) | set(current_by_key))
    rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    max_rating_drop = float(policy.get("max_rating_drop", 0.5) or 0.5)
    max_average_rating_drop = float(policy.get("max_average_rating_drop", 0.25) or 0.25)
    for key in keys:
        baseline = baseline_by_key.get(key, {})
        current = current_by_key.get(key, {})
        title = current.get("title") or baseline.get("title")
        identity_status = "matched" if baseline and current else "missing_current" if baseline else "missing_baseline"
        rating_delta = _num(current.get("manual_rating")) - _num(baseline.get("manual_rating")) if baseline and current else None
        new_high = max(0, int(current.get("high_issue_count") or 0) - int(baseline.get("high_issue_count") or 0))
        new_critical = max(0, int(current.get("critical_issue_count") or 0) - int(baseline.get("critical_issue_count") or 0))
        remediation_delta = int(current.get("remediation_count") or 0) - int(baseline.get("remediation_count") or 0)
        row_blockers: list[str] = []
        if identity_status != "matched":
            row_blockers.append(identity_status)
        if new_critical > 0:
            row_blockers.append("new_critical_issue")
        if new_high > 0:
            row_blockers.append("new_high_issue")
        if rating_delta is not None and rating_delta < -max_rating_drop:
            row_blockers.append("rating_drop")
        if current.get("test_fake_count"):
            row_blockers.append("test_fake_audio")
        if current.get("audio_health_status") == "failed":
            row_blockers.append("audio_health_failed")
        status = "failed" if row_blockers else "passed"
        if remediation_delta > int(policy.get("max_remediation_count_increase", 0) or 0) and not row_blockers:
            status = "warning"
            warnings.append(_blocker("remediation_count_increase", "Remediation count increased.", track_id=current.get("track_id") or baseline.get("track_id")))
        for blocker in row_blockers:
            blockers.append(_blocker(blocker, blocker.replace("_", " "), track_id=current.get("track_id") or baseline.get("track_id"), title=title))
        rows.append(
            {
                "track_key": key,
                "track_id": current.get("track_id") or baseline.get("track_id"),
                "title": title,
                "identity_status": identity_status,
                "baseline": baseline,
                "current": current,
                "delta": {
                    "manual_rating_delta": rating_delta,
                    "new_high_issue_count": new_high,
                    "new_critical_issue_count": new_critical,
                    "remediation_count_delta": remediation_delta,
                },
                "status": status,
                "blockers": row_blockers,
            }
        )
        if new_high or new_critical:
            issue_rows.append(
                {
                    "track_id": current.get("track_id") or baseline.get("track_id"),
                    "title": title,
                    "new_high_issue_count": new_high,
                    "new_critical_issue_count": new_critical,
                    "status": "failed",
                }
            )
    rating_deltas = [row.get("delta", {}).get("manual_rating_delta") for row in rows if isinstance(row.get("delta", {}).get("manual_rating_delta"), (int, float))]
    average_rating_delta = round(sum(rating_deltas) / len(rating_deltas), 4) if rating_deltas else 0.0
    if average_rating_delta < -max_average_rating_drop:
        blockers.append(_blocker("average_rating_drop", "Average manual rating dropped beyond policy threshold.", delta=average_rating_delta))
    matrix = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "baseline_release_id": baseline_binding.get("release_id"),
        "rows": rows,
        "summary": {
            "track_count": len(rows),
            "matched_track_count": sum(1 for row in rows if row.get("identity_status") == "matched"),
            "failed_track_count": sum(1 for row in rows if row.get("status") == "failed"),
            "warning_track_count": sum(1 for row in rows if row.get("status") == "warning"),
            "passed_track_count": sum(1 for row in rows if row.get("status") == "passed"),
        },
    }
    issue_index = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "issue_taxonomy": issue_rows,
        "new_issues": issue_rows,
        "resolved_issues": [],
    }
    quality = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "baseline_release_id": baseline_binding.get("release_id"),
        "metrics": {
            "average_manual_rating_delta": average_rating_delta,
            "min_manual_rating_delta": min(rating_deltas) if rating_deltas else 0,
            "high_issue_delta": sum(int(row.get("delta", {}).get("new_high_issue_count") or 0) for row in rows),
            "critical_issue_delta": sum(int(row.get("delta", {}).get("new_critical_issue_count") or 0) for row in rows),
            "remediation_count_delta": sum(int(row.get("delta", {}).get("remediation_count_delta") or 0) for row in rows),
        },
    }
    blocker_register = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "release_id": current_binding.get("release_id"),
        "status": "failed" if blockers else "passed",
        "summary": {"blocker_count": len(blockers), "warning_count": len(warnings)},
        "blockers": blockers,
        "warnings": warnings,
    }
    status = "failed" if blockers else "warning" if warnings else "passed"
    quality["decision"] = {
        "status": status,
        "recommendation": "block_release_until_audio_regression_is_resolved" if blockers else "audio_regression_review_recommended" if warnings else "audio_regression_guard_passed",
        "blockers": [row.get("check_id") for row in blockers],
        "warnings": [row.get("check_id") for row in warnings],
    }
    source = {
        "baseline_binding_hash": baseline_binding.get("integrity_hash"),
        "current_binding_hash": current_binding.get("integrity_hash"),
        "policy_hash": stable_hash(policy or {}),
    }
    source["source_hash"] = stable_hash(source)
    for doc in (matrix, issue_index, quality, blocker_register):
        doc["source_hash"] = source["source_hash"]
        doc["integrity_hash"] = _integrity_hash(doc)
    report = {
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
        "package_type": RELEASE_AUDIO_REGRESSION_PACKAGE_TYPE,
        "release_id": current_binding.get("release_id"),
        "baseline_release_id": baseline_binding.get("release_id"),
        "status": status,
        "readiness": "blocked" if blockers else "warning_requires_audio_lead_review" if warnings else "ready",
        "summary": {
            **matrix["summary"],
            "new_high_issue_count": quality["metrics"]["high_issue_delta"],
            "new_critical_issue_count": quality["metrics"]["critical_issue_delta"],
            "average_manual_rating_delta": average_rating_delta,
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "policy": policy or {},
        "blockers": blockers,
        "warnings": warnings,
        "source": {**source, "track_matrix_hash": matrix.get("integrity_hash"), "issue_index_hash": issue_index.get("integrity_hash"), "quality_delta_hash": quality.get("integrity_hash"), "blocker_register_hash": blocker_register.get("integrity_hash")},
        "source_hash": source["source_hash"],
    }
    report["integrity_hash"] = _integrity_hash(report)
    return {"report": report, "matrix": matrix, "issue_index": issue_index, "quality": quality, "blockers": blocker_register}


def _external_binding_checks(prefix: str, actual: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        _check(f"release_audio_regression_{prefix}_binding_integrity", _integrity_ok(actual), f"{prefix} binding integrity is valid."),
        _check(f"release_audio_regression_{prefix}_binding_matches_external", _semantic_hash(_strip_binding(actual)) == _semantic_hash(_strip_binding(expected)), f"{prefix} binding matches external Timeline/Certification evidence."),
    ]


def _recomputed_document_checks(report: dict[str, Any], matrix: dict[str, Any], issue_index: dict[str, Any], quality: dict[str, Any], blockers: dict[str, Any], expected: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _check("release_audio_regression_facts_recomputed", True, "Regression facts were recomputed from external Timeline/Certification packages."),
        _check("release_audio_regression_track_matrix_binding", _semantic_hash(matrix) == _semantic_hash(expected["matrix"]), "Track regression matrix matches recomputed external facts."),
        _check("release_audio_regression_issue_index_binding", _semantic_hash(issue_index) == _semantic_hash(expected["issue_index"]), "Issue regression index matches recomputed external facts."),
        _check("release_audio_regression_quality_delta_binding", _semantic_hash(quality) == _semantic_hash(expected["quality"]), "Quality delta summary matches recomputed external facts."),
        _check("release_audio_regression_blocker_register_binding", _semantic_hash(blockers) == _semantic_hash(expected["blockers"]), "Blocker register matches recomputed external facts."),
        _check("release_audio_regression_policy_decision_match", _semantic_hash(report.get("summary")) == _semantic_hash(expected["report"].get("summary")) and report.get("status") == expected["report"].get("status") and report.get("readiness") == expected["report"].get("readiness"), "Regression report decision matches recomputed external facts."),
        _check("release_audio_regression_internal_full_resign_guard", _semantic_hash(report) == _semantic_hash(expected["report"]), "Regression report is not an internally re-signed forgery."),
    ]


def _document_binding_checks(manifest: dict[str, Any], report: dict[str, Any], matrix: dict[str, Any], issue_index: dict[str, Any], quality: dict[str, Any], blockers: dict[str, Any], baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    same_source = report.get("source_hash") == matrix.get("source_hash") == issue_index.get("source_hash") == quality.get("source_hash") == blockers.get("source_hash")
    return [
        _check("release_audio_regression_manifest_report_binding", manifest.get("report_hash") == report.get("integrity_hash"), "Manifest binds regression report."),
        _check("release_audio_regression_manifest_matrix_binding", manifest.get("track_matrix_hash") == matrix.get("integrity_hash"), "Manifest binds track matrix."),
        _check("release_audio_regression_manifest_issue_binding", manifest.get("issue_index_hash") == issue_index.get("integrity_hash"), "Manifest binds issue index."),
        _check("release_audio_regression_manifest_quality_binding", manifest.get("quality_delta_hash") == quality.get("integrity_hash"), "Manifest binds quality delta."),
        _check("release_audio_regression_manifest_blocker_binding", manifest.get("blocker_register_hash") == blockers.get("integrity_hash"), "Manifest binds blocker register."),
        _check("release_audio_regression_manifest_baseline_binding", manifest.get("baseline_binding_hash") == baseline.get("integrity_hash"), "Manifest binds baseline binding."),
        _check("release_audio_regression_manifest_current_binding", manifest.get("current_binding_hash") == current.get("integrity_hash"), "Manifest binds current binding."),
        _check("release_audio_regression_source_binding", same_source and manifest.get("source_hash") == report.get("source_hash"), "Regression documents bind same source hash."),
    ]


def _signoff_checks(signoff: dict[str, Any] | None, history: list[dict[str, Any]], manifest: dict[str, Any], report: dict[str, Any], matrix: dict[str, Any], issue_index: dict[str, Any], quality: dict[str, Any], blockers: dict[str, Any], baseline: dict[str, Any], current: dict[str, Any], *, require_signed: bool) -> list[dict[str, Any]]:
    if signoff is None:
        return [_check("release_audio_regression_signoff_present", not require_signed, "Regression signoff is present when required.")]
    latest = history[-1] if history else {}
    return [
        _check("release_audio_regression_signoff_integrity", _integrity_ok(signoff), "Regression signoff integrity is valid."),
        _check("release_audio_regression_signoff_status", signoff.get("status") == "signed", "Regression signoff status is signed."),
        _check("release_audio_regression_signoff_report_binding", signoff.get("regression_report_hash") == report.get("integrity_hash") == manifest.get("report_hash"), "Regression signoff binds report."),
        _check("release_audio_regression_signoff_matrix_binding", signoff.get("track_matrix_hash") == matrix.get("integrity_hash"), "Regression signoff binds matrix."),
        _check("release_audio_regression_signoff_issue_binding", signoff.get("issue_index_hash") == issue_index.get("integrity_hash"), "Regression signoff binds issue index."),
        _check("release_audio_regression_signoff_quality_binding", signoff.get("quality_delta_hash") == quality.get("integrity_hash"), "Regression signoff binds quality delta."),
        _check("release_audio_regression_signoff_blocker_binding", signoff.get("blocker_register_hash") == blockers.get("integrity_hash"), "Regression signoff binds blockers."),
        _check("release_audio_regression_signoff_baseline_binding", signoff.get("baseline_binding_hash") == baseline.get("integrity_hash"), "Regression signoff binds baseline."),
        _check("release_audio_regression_signoff_current_binding", signoff.get("current_binding_hash") == current.get("integrity_hash"), "Regression signoff binds current evidence."),
        _check("release_audio_regression_manifest_signoff_binding", manifest.get("signoff_hash") == signoff.get("integrity_hash"), "Manifest binds signoff."),
        _check("release_audio_regression_signoff_history_chain", _history_chain_ok(history), "Regression signoff history hash chain is valid."),
        _check("release_audio_regression_signoff_history_latest", (latest.get("payload") or {}).get("signoff_hash") == signoff.get("integrity_hash"), "Latest signoff history event binds current signoff."),
    ]


def _history_chain_ok(history: list[dict[str, Any]]) -> bool:
    previous: str | None = None
    for event in history:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("previous_event_hash") != previous:
            return False
        if event.get("payload_hash") != stable_hash(payload):
            return False
        if event.get("event_hash") != stable_hash({key: value for key, value in event.items() if key != "event_hash"}):
            return False
        previous = str(event.get("event_hash") or "")
    return bool(history)


def _manifest_checks(archive: zipfile.ZipFile, manifest: dict[str, Any], names: set[str], *, expected_entries: set[str], strict: bool) -> list[dict[str, Any]]:
    files = manifest.get("files") if isinstance(manifest.get("files"), list) else []
    declared = {str(row.get("path") or "") for row in files if isinstance(row, dict)}
    effective_names = names - {"manifest.json"}
    expected_files = expected_entries - {"manifest.json"}
    undeclared = sorted(effective_names - declared)
    extra_declared = sorted(declared - effective_names)
    fixed_extra_declared = sorted(declared - expected_files)
    fixed_missing_declared = sorted(expected_files - declared)
    mismatches: list[str] = []
    for row in files:
        if not isinstance(row, dict):
            continue
        path = str(row.get("path") or "")
        if not path or path not in names:
            continue
        info = archive.getinfo(path)
        data = archive.read(path)
        if row.get("sha256") != _sha256_bytes(data) or int(row.get("size_bytes") or -1) != info.file_size:
            mismatches.append(path)
    return [
        _check("release_audio_regression_manifest_files_present", bool(files), "Manifest declares package files."),
        _check("release_audio_regression_no_undeclared_entries", not undeclared, "ZIP has no undeclared entries.", {"undeclared": undeclared}, blocking=strict or bool(undeclared)),
        _check("release_audio_regression_declared_entries_exist", not extra_declared, "All manifest file entries exist.", {"missing": extra_declared}),
        _check("release_audio_regression_manifest_fixed_files", not fixed_extra_declared and not fixed_missing_declared, "Manifest files match fixed Regression layout.", {"extra": fixed_extra_declared, "missing": fixed_missing_declared}),
        _check("release_audio_regression_manifest_file_hashes", not mismatches, "Manifest file hashes and sizes match ZIP entries.", {"mismatches": mismatches}),
    ]


def _finish(checks: list[dict[str, Any]], summary: dict[str, Any], *extra: dict[str, Any]) -> dict[str, Any]:
    checks.extend(extra)
    blockers = [check for check in checks if check.get("status") == "failed" and check.get("blocking", True)]
    warnings = [check for check in checks if check.get("status") == "warning"]
    report = {
        "package_type": RELEASE_AUDIO_REGRESSION_VERIFICATION_PACKAGE_TYPE,
        "schema_version": RELEASE_AUDIO_REGRESSION_SCHEMA_VERSION,
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


def _check(check_id: str, passed: bool, message: str, details: dict[str, Any] | None = None, *, blocking: bool = True) -> dict[str, Any]:
    return {"check_id": check_id, "status": "passed" if passed else "failed", "message": message, "details": details or {}, "blocking": blocking}


def _read_json_entry(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    with archive.open(name) as handle:
        data = json.loads(handle.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object.")
    return data


def _read_jsonl_entry(archive: zipfile.ZipFile, name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with archive.open(name) as handle:
        for raw in handle.read().decode("utf-8").splitlines():
            if not raw.strip():
                continue
            item = json.loads(raw)
            if not isinstance(item, dict):
                raise ValueError(f"{name} must contain JSON objects.")
            rows.append(item)
    return rows


def _is_safe_entry(name: str) -> bool:
    if "\\" in name:
        return False
    if not name or name.startswith("/") or name.startswith("../") or "/../" in name or name.endswith("/.."):
        return False
    lowered = name.lower()
    if lowered.startswith(".musicforge/") or "/.musicforge/" in lowered or lowered.endswith(".zip"):
        return False
    return True


def _redaction_check(archive: zipfile.ZipFile, names: list[str]) -> dict[str, Any]:
    leaks: list[str] = []
    for name in names:
        if not name.lower().endswith((".json", ".md", ".txt", ".jsonl")):
            continue
        data = archive.read(name)
        if any(pattern.search(data) for pattern in SENSITIVE_PATTERNS):
            leaks.append(name)
    return _check("release_audio_regression_redaction_scan", not leaks, "Package text files do not contain obvious secrets or local paths.", {"leaks": leaks})


def _certification_signoff_hash(cert_zip: Path) -> str | None:
    try:
        with zipfile.ZipFile(cert_zip) as archive:
            if "certification-signoff.json" not in [item.filename for item in archive.infolist()]:
                return None
            return _read_json_entry(archive, "certification-signoff.json").get("integrity_hash")
    except Exception:
        return None


def _manual_rating(row: dict[str, Any]) -> float:
    value = row.get("manual_rating") or row.get("rating")
    if isinstance(value, (int, float)):
        return float(value)
    if row.get("review_status") == "accepted":
        return 5.0
    if row.get("review_status") == "needs_fix":
        return 3.0
    if row.get("review_status") == "rejected":
        return 1.0
    return 0.0


def _identity_key(row: dict[str, Any], *, mode: str) -> str:
    if mode == "same_artifact_repeat_check":
        value = stable_hash({"project_id": row.get("project_id"), "title": _normalize_title(row.get("title")), "final_export_hash": row.get("final_export_hash")})
    else:
        value = stable_hash({"title": _normalize_title(row.get("title"))})
    return value if row.get("project_id") or row.get("title") else ""


def _normalize_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _num(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _blocker(check_id: str, message: str, **details: Any) -> dict[str, Any]:
    return {"check_id": check_id, "message": message, **details}


def _strip_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in binding.items() if key not in {"payload_hash", "integrity_hash"}}


def _semantic_hash(value: Any) -> str:
    return stable_hash(_strip_volatile(value))


def _strip_volatile(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_volatile(item) for key, item in value.items() if key not in {"generated_at", "created_at", "updated_at", "integrity_hash", "payload_hash"}}
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    return value


def _integrity_hash(payload: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _integrity_ok(payload: dict[str, Any]) -> bool:
    return bool(payload.get("integrity_hash")) and payload.get("integrity_hash") == _integrity_hash(payload)


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()
