from __future__ import annotations

from typing import Any

from song_agent.platform.contracts.packages import require_registered_package_type as _require_registered_package_type
from song_agent.platform.verification.hashing import integrity_hash


def build_check(
    check_id: str,
    passed: bool,
    message: str,
    details: dict[str, Any] | None = None,
    *,
    severity: str = "blocking",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "check_id": str(check_id),
        "status": "passed" if passed else "failed",
        "severity": str(severity),
        "message": str(message),
        "details": details or {},
    }
    return row


def has_blocking_failures(checks: list[dict[str, Any]]) -> bool:
    return any(
        row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"
        for row in checks
    )


def build_verification_report(
    *,
    package_type: str,
    checks: list[dict[str, Any]],
    summary: dict[str, Any],
    schema_version: int = 1,
    extra: dict[str, Any] | None = None,
    warning_status: bool = False,
) -> dict[str, Any]:
    failed = [
        row for row in checks
        if row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"
    ]
    warnings = [
        row for row in checks
        if row.get("status") == "failed" and row.get("severity", "blocking") != "blocking"
    ]
    report: dict[str, Any] = {
        "schema_version": int(schema_version),
        "package_type": _require_registered_package_type(str(package_type), writer_id="song_agent.platform.verification.model.build_verification_report"),
        "status": "failed" if failed else "warning" if warning_status and warnings else "passed",
        "zip_sha256": summary.get("zip_sha256"),
        "zip_size_bytes": summary.get("zip_size_bytes", 0),
        "manifest_hash": summary.get("manifest_hash"),
        "source_hash": summary.get("source_hash"),
        "summary": summary,
        "checks": checks,
        "blockers": [str(row.get("check_id")) for row in failed],
        "warnings": [str(row.get("check_id")) for row in warnings],
    }
    if extra:
        report.update(extra)
    report["integrity_hash"] = integrity_hash(report)
    return report
