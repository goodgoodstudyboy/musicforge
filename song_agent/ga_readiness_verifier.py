from __future__ import annotations

import json
import re
import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from song_agent.ga_readiness import GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok
from song_agent.audio_campaign_archive_verifier import (
    AUDIO_CAMPAIGN_ARCHIVE_PACKAGE_TYPE,
    verify_audio_campaign_archive_package,
)
from song_agent.music_acceptance import AcceptanceStore
from song_agent.music_acceptance import stable_hash
from song_agent.projectio import read_json, write_json
from song_agent.trust_operations_final_readiness_verifier import (
    TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE,
    verify_trust_operations_final_handoff_package,
)


GA_READINESS_VERIFICATION_PACKAGE_TYPE = "musicforge_ga_readiness_verification_report"

_SENSITIVE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|githubkey\.txt)", re.IGNORECASE)


def verify_ga_readiness_report(
    report_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_manual_acceptance: bool = False,
    require_audio_campaign: bool = False,
    require_final_readiness: bool = False,
    manual_acceptance_report_path: Path | str | None = None,
    audio_campaign_archive_path: Path | str | None = None,
    audio_campaign_archive_verification_report_path: Path | str | None = None,
    final_handoff_package_path: Path | str | None = None,
    final_handoff_verification_report_path: Path | str | None = None,
) -> dict[str, Any]:
    target = Path(report_path)
    checks: list[dict[str, Any]] = []
    try:
        report = read_json(target)
    except Exception as exc:
        report = {}
        _add_check(checks, "ga_readiness_report_readable", "failed", "blocking", f"GA readiness report could not be read: {exc}")

    if report:
        _add_check(
            checks,
            "ga_readiness_package_type",
            "passed" if report.get("package_type") == GA_READINESS_PACKAGE_TYPE else "failed",
            "blocking",
            "GA readiness report package type is valid." if report.get("package_type") == GA_READINESS_PACKAGE_TYPE else "GA readiness report package type is invalid.",
        )
        _add_check(
            checks,
            "ga_readiness_schema_version",
            "passed" if report.get("schema_version") == GA_READINESS_SCHEMA_VERSION else "failed",
            "blocking",
            "GA readiness report schema version is supported." if report.get("schema_version") == GA_READINESS_SCHEMA_VERSION else "GA readiness report schema version is unsupported.",
        )
        _add_check(
            checks,
            "ga_readiness_integrity",
            "passed" if ga_readiness_integrity_ok(report) else "failed",
            "blocking",
            "GA readiness report integrity hash matches." if ga_readiness_integrity_ok(report) else "GA readiness report integrity hash mismatch.",
        )
        status = str(report.get("status") or "unknown")
        allowed_statuses = {"ready", "warning"} if not strict else {"ready"}
        status_severity = "blocking" if strict or require_ready else "warning"
        _add_check(
            checks,
            "ga_readiness_status_allowed",
            "passed" if status in allowed_statuses else "failed",
            status_severity,
            f"GA readiness status is {status}.",
            {"status": status, "allowed": sorted(allowed_statuses)},
        )
        if require_ready:
            _add_check(
                checks,
                "ga_readiness_require_ready",
                "passed" if status == "ready" else "failed",
                "blocking",
                "GA readiness is ready." if status == "ready" else "GA readiness is not ready.",
            )
        _add_check(
            checks,
            "ga_readiness_redaction",
            "passed" if not _SENSITIVE_RE.search(json.dumps(report, ensure_ascii=False)) else "failed",
            "blocking",
            "GA readiness report contains no obvious token strings." if not _SENSITIVE_RE.search(json.dumps(report, ensure_ascii=False)) else "GA readiness report contains a token-like string.",
        )
        checks_by_id = {str(item.get("check_id")): item for item in report.get("checks", []) if isinstance(item, dict)}
        if require_manual_acceptance:
            _verify_manual_acceptance_evidence(checks, checks_by_id.get("ga.acceptance_manual", {}), manual_acceptance_report_path)
        if require_audio_campaign:
            _verify_audio_campaign_evidence(
                checks,
                checks_by_id.get("ga.audio_campaign", {}),
                audio_campaign_archive_path,
                audio_campaign_archive_verification_report_path,
            )
        if require_final_readiness:
            _verify_final_readiness_evidence(
                checks,
                checks_by_id.get("ga.trust_final_readiness", {}),
                final_handoff_package_path,
                final_handoff_verification_report_path,
            )

    blockers = [check for check in checks if check.get("status") == "failed" and check.get("severity") == "blocking"]
    warnings = [check for check in checks if check.get("status") == "warning" or check.get("severity") == "warning"]
    verification = {
        "package_type": GA_READINESS_VERIFICATION_PACKAGE_TYPE,
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "failed" if blockers else "warning" if warnings else "passed",
        "summary": {
            "source_path": str(target.name),
            "ga_status": report.get("status") if isinstance(report, dict) else "missing",
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "checks": checks,
    }
    verification["integrity_hash"] = stable_hash({key: value for key, value in verification.items() if key != "integrity_hash"})
    return verification


def write_ga_readiness_verification_report(report: dict[str, Any], path: Path | str) -> Path:
    target = Path(path)
    write_json(target, report)
    return target


def _verify_manual_acceptance_evidence(checks: list[dict[str, Any]], ga_check: dict[str, Any], report_path: Path | str | None) -> None:
    if not report_path:
        _add_check(
            checks,
            "ga_readiness_manual_acceptance_report_required",
            "failed",
            "blocking",
            "Manual acceptance requirement needs an external music acceptance report.",
        )
        return
    target = Path(report_path)
    try:
        report = read_json(target)
    except Exception as exc:
        _add_check(
            checks,
            "ga_readiness_manual_acceptance_report_readable",
            "failed",
            "blocking",
            f"Manual acceptance report could not be read: {exc}",
        )
        return
    _add_check(checks, "ga_readiness_manual_acceptance_report_readable", "passed", "info", "Manual acceptance report is readable.", {"source_path": target.name})
    suite_id = str(report.get("suite_id") or "")
    verified_report = _verify_acceptance_report_from_store(target, suite_id, report)
    if verified_report:
        report = verified_report
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    report_passed = report.get("status") == "passed"
    verification_passed = verification.get("status") == "passed" and verification.get("source_status") == "passed" and verification.get("content_status") == "passed"
    manual_count = _safe_int(summary.get("manual_accepted_count"))
    synthetic_count = _safe_int(summary.get("synthetic_accepted_count"))
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_status",
        "passed" if report_passed else "failed",
        "blocking",
        "Manual acceptance report is passed." if report_passed else "Manual acceptance report is not passed.",
        {"status": report.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_verification",
        "passed" if verification_passed else "failed",
        "blocking",
        "Manual acceptance report source/content verification is passed." if verification_passed else "Manual acceptance report source/content verification is not passed.",
        {
            "status": verification.get("status"),
            "source_status": verification.get("source_status"),
            "content_status": verification.get("content_status"),
        },
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_store_binding",
        "passed" if verified_report and verification_passed else "failed",
        "blocking",
        "Manual acceptance report matches the current AcceptanceStore source." if verified_report and verification_passed else "Manual acceptance report is not bound to current AcceptanceStore source.",
        {"suite_id": suite_id},
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_manual_review",
        "passed" if manual_count > 0 else "failed",
        "blocking",
        "Manual human listening acceptance is present." if manual_count > 0 else "Manual human listening acceptance is missing.",
        {"manual_accepted_count": manual_count, "synthetic_accepted_count": synthetic_count},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
    latest = detail.get("latest") if isinstance(detail.get("latest"), dict) else {}
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and _safe_int(detail.get("manual_ready_count")) > 0
        and (not latest or latest.get("suite_id") == report.get("suite_id"))
        and (not latest or latest.get("status") == report.get("status"))
        and (not latest or _safe_int(latest.get("manual_accepted_count")) == manual_count)
    )
    _add_check(
        checks,
        "ga_readiness_manual_acceptance_report_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness manual acceptance check matches the external report." if ga_binding_ok else "GA readiness manual acceptance check does not match the external report.",
        {"ga_check_status": ga_check.get("status"), "suite_id": report.get("suite_id"), "ga_latest_suite_id": latest.get("suite_id")},
    )


def _verify_final_readiness_evidence(
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
    package_path: Path | str | None,
    verification_report_path: Path | str | None,
) -> None:
    if not package_path:
        _add_check(checks, "ga_readiness_final_handoff_package_required", "failed", "blocking", "Final readiness requirement needs an external Final Handoff ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_final_handoff_verification_required", "failed", "blocking", "Final readiness requirement needs an external Final Handoff verification report.")
        return
    zip_path = Path(package_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_final_handoff_verification_readable", "failed", "blocking", f"Final Handoff verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_final_handoff_verification_readable", "passed", "info", "Final Handoff verification report is readable.", {"source_path": report_path.name})
    try:
        package_verification = verify_trust_operations_final_handoff_package(zip_path, strict=True, require_signed=True)
    except Exception as exc:
        package_verification = {"status": "failed", "error": str(exc)}
    manifest = _read_final_handoff_manifest(zip_path)
    zip_sha = _sha256_file(zip_path) if zip_path.exists() else None
    zip_size = zip_path.stat().st_size if zip_path.exists() else None
    _add_check(
        checks,
        "ga_readiness_final_handoff_verification_package_type",
        "passed" if verification_report.get("package_type") == TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE else "failed",
        "blocking",
        "Final Handoff verification package type is valid." if verification_report.get("package_type") == TRUST_OPERATIONS_FINAL_HANDOFF_VERIFICATION_PACKAGE_TYPE else "Final Handoff verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_verification_status",
        "passed" if verification_report.get("status") == "passed" else "failed",
        "blocking",
        "Final Handoff verification report is passed." if verification_report.get("status") == "passed" else "Final Handoff verification report is not passed.",
        {"status": verification_report.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_package_self_verification",
        "passed" if package_verification.get("status") == "passed" else "failed",
        "blocking",
        "Final Handoff ZIP self-verification is passed." if package_verification.get("status") == "passed" else "Final Handoff ZIP self-verification failed.",
        {"status": package_verification.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_zip_binding",
        "passed"
        if verification_report.get("zip_sha256") == zip_sha and verification_report.get("zip_size_bytes") == zip_size and verification_report.get("manifest_hash") == manifest.get("integrity_hash")
        else "failed",
        "blocking",
        "Final Handoff verification report matches the ZIP and manifest." if verification_report.get("zip_sha256") == zip_sha and verification_report.get("zip_size_bytes") == zip_size and verification_report.get("manifest_hash") == manifest.get("integrity_hash") else "Final Handoff verification report does not match the ZIP and manifest.",
        {"zip_sha256": zip_sha, "zip_size_bytes": zip_size, "manifest_hash": manifest.get("integrity_hash")},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and detail.get("package_type") == verification_report.get("package_type")
        and detail.get("zip_sha256") == verification_report.get("zip_sha256")
        and detail.get("manifest_hash") == verification_report.get("manifest_hash")
    )
    _add_check(
        checks,
        "ga_readiness_final_handoff_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness final readiness check matches the external Final Handoff verification report." if ga_binding_ok else "GA readiness final readiness check does not match the external Final Handoff verification report.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": verification_report.get("zip_sha256"), "ga_zip_sha256": detail.get("zip_sha256")},
    )


def _verify_audio_campaign_evidence(
    checks: list[dict[str, Any]],
    ga_check: dict[str, Any],
    archive_path: Path | str | None,
    verification_report_path: Path | str | None,
) -> None:
    if not archive_path:
        _add_check(checks, "ga_readiness_audio_campaign_archive_required", "failed", "blocking", "Audio Campaign requirement needs an external Audio Campaign Archive ZIP.")
        return
    if not verification_report_path:
        _add_check(checks, "ga_readiness_audio_campaign_verification_required", "failed", "blocking", "Audio Campaign requirement needs an external Audio Campaign Archive verification report.")
        return
    zip_path = Path(archive_path)
    report_path = Path(verification_report_path)
    try:
        verification_report = read_json(report_path)
    except Exception as exc:
        _add_check(checks, "ga_readiness_audio_campaign_verification_readable", "failed", "blocking", f"Audio Campaign Archive verification report could not be read: {exc}")
        return
    _add_check(checks, "ga_readiness_audio_campaign_verification_readable", "passed", "info", "Audio Campaign Archive verification report is readable.", {"source_path": report_path.name})
    try:
        current_verification = verify_audio_campaign_archive_package(zip_path, strict=True, require_signed=True, require_verification_passed=True)
    except Exception as exc:
        current_verification = {"status": "failed", "error": str(exc), "summary": {}}
    report_integrity_ok = verification_report.get("integrity_hash") == stable_hash({key: value for key, value in verification_report.items() if key != "integrity_hash"})
    current_summary = current_verification.get("summary") if isinstance(current_verification.get("summary"), dict) else {}
    report_summary = verification_report.get("summary") if isinstance(verification_report.get("summary"), dict) else {}
    _add_check(
        checks,
        "ga_readiness_audio_campaign_verification_package_type",
        "passed" if verification_report.get("package_type") == "audio_campaign_archive_verification" else "failed",
        "blocking",
        "Audio Campaign Archive verification package type is valid." if verification_report.get("package_type") == "audio_campaign_archive_verification" else "Audio Campaign Archive verification package type is invalid.",
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_verification_integrity",
        "passed" if report_integrity_ok else "failed",
        "blocking",
        "Audio Campaign Archive verification report integrity hash matches." if report_integrity_ok else "Audio Campaign Archive verification report integrity hash mismatch.",
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_verification_status",
        "passed" if verification_report.get("status") == "passed" else "failed",
        "blocking",
        "Audio Campaign Archive verification report is passed." if verification_report.get("status") == "passed" else "Audio Campaign Archive verification report is not passed.",
        {"status": verification_report.get("status")},
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_archive_self_verification",
        "passed" if current_verification.get("status") == "passed" else "failed",
        "blocking",
        "Audio Campaign Archive ZIP self-verification is passed." if current_verification.get("status") == "passed" else "Audio Campaign Archive ZIP self-verification failed.",
        {"status": current_verification.get("status"), "blockers": current_verification.get("blockers", [])},
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_zip_binding",
        "passed" if report_summary.get("zip_sha256") == current_summary.get("zip_sha256") and report_summary.get("manifest_hash") == current_summary.get("manifest_hash") else "failed",
        "blocking",
        "Audio Campaign Archive verification report matches the ZIP and manifest." if report_summary.get("zip_sha256") == current_summary.get("zip_sha256") and report_summary.get("manifest_hash") == current_summary.get("manifest_hash") else "Audio Campaign Archive verification report does not match the ZIP and manifest.",
        {"zip_sha256": current_summary.get("zip_sha256"), "manifest_hash": current_summary.get("manifest_hash")},
    )
    detail = ga_check.get("detail") if isinstance(ga_check.get("detail"), dict) else {}
    gate = detail.get("gate") if isinstance(detail.get("gate"), dict) else {}
    ga_binding_ok = (
        ga_check.get("status") == "passed"
        and detail.get("status") == "passed"
        and gate.get("archive_zip_sha256") == current_summary.get("zip_sha256")
        and gate.get("archive_verification_hash") == verification_report.get("integrity_hash")
    )
    _add_check(
        checks,
        "ga_readiness_audio_campaign_ga_binding",
        "passed" if ga_binding_ok else "failed",
        "blocking",
        "GA readiness Audio Campaign check matches the external archive verification." if ga_binding_ok else "GA readiness Audio Campaign check does not match the external archive verification.",
        {"ga_check_status": ga_check.get("status"), "zip_sha256": current_summary.get("zip_sha256"), "ga_zip_sha256": gate.get("archive_zip_sha256")},
    )


def _read_final_handoff_manifest(zip_path: Path) -> dict[str, Any]:
    if not zip_path.exists():
        return {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open("trust-operations-final-readiness-manifest.json") as file:
                return json.loads(file.read().decode("utf-8"))
    except Exception:
        return {}


def _verify_acceptance_report_from_store(report_path: Path, suite_id: str, report: dict[str, Any]) -> dict[str, Any] | None:
    if not suite_id:
        return None
    try:
        store_root = report_path.resolve().parents[1]
        if report_path.resolve().parent.name != suite_id:
            return None
        store = AcceptanceStore(store_root)
        return store.verify_report(suite_id, report)
    except Exception:
        return None


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _add_check(checks: list[dict[str, Any]], check_id: str, status: str, severity: str, message: str, detail: dict[str, Any] | None = None) -> None:
    checks.append({"check_id": check_id, "status": status, "severity": severity, "message": message, "detail": detail or {}})
