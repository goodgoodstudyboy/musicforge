from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from song_agent.ga_readiness import GA_READINESS_PACKAGE_TYPE, GA_READINESS_SCHEMA_VERSION, ga_readiness_integrity_ok
from song_agent.music_acceptance import stable_hash
from song_agent.projectio import read_json, write_json


GA_READINESS_VERIFICATION_PACKAGE_TYPE = "musicforge_ga_readiness_verification_report"

_SENSITIVE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{12,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9_]{20,}|githubkey\.txt)", re.IGNORECASE)


def verify_ga_readiness_report(
    report_path: Path | str,
    *,
    strict: bool = False,
    require_ready: bool = False,
    require_manual_acceptance: bool = False,
    require_final_readiness: bool = False,
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
        status_severity = "blocking" if status == "blocked" or strict or require_ready else "warning"
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
        check_statuses = {str(item.get("check_id")): str(item.get("status")) for item in report.get("checks", []) if isinstance(item, dict)}
        if require_manual_acceptance:
            _add_check(
                checks,
                "ga_readiness_require_manual_acceptance",
                "passed" if check_statuses.get("ga.acceptance_manual") == "passed" else "failed",
                "blocking",
                "Manual acceptance readiness is present." if check_statuses.get("ga.acceptance_manual") == "passed" else "Manual acceptance readiness is missing or not passed.",
            )
        if require_final_readiness:
            _add_check(
                checks,
                "ga_readiness_require_final_readiness",
                "passed" if check_statuses.get("ga.trust_final_readiness") == "passed" else "failed",
                "blocking",
                "Final readiness evidence is present." if check_statuses.get("ga.trust_final_readiness") == "passed" else "Final readiness evidence is missing or not passed.",
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


def _add_check(checks: list[dict[str, Any]], check_id: str, status: str, severity: str, message: str, detail: dict[str, Any] | None = None) -> None:
    checks.append({"check_id": check_id, "status": status, "severity": severity, "message": message, "detail": detail or {}})
