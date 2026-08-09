from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from song_agent.platform.contracts.documents import (
    JsonDocument,
    JsonValue,
    normalize_json_document,
    normalize_json_value,
)

from song_agent.platform.contracts.packages import require_registered_package_type as _require_registered_package_type
from song_agent.platform.verification.hashing import integrity_hash


def build_check(
    check_id: str,
    passed: bool,
    message: str,
    details: Mapping[str, object] | None = None,
    *,
    severity: str = "blocking",
) -> JsonDocument:
    row: JsonDocument = {
        "check_id": str(check_id),
        "status": "passed" if passed else "failed",
        "severity": str(severity),
        "message": str(message),
        "details": normalize_json_document(details) if details else {},
    }
    return row


def has_blocking_failures(checks: Iterable[Mapping[str, object]]) -> bool:
    return any(
        row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"
        for row in checks
    )


def build_verification_report(
    *,
    package_type: str,
    checks: Sequence[Mapping[str, object]],
    summary: Mapping[str, object],
    schema_version: int = 1,
    extra: Mapping[str, object] | None = None,
    warning_status: bool = False,
) -> JsonDocument:
    normalized_checks = [normalize_json_document(row) for row in checks]
    failed = [
        row for row in normalized_checks
        if row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"
    ]
    warnings = [
        row for row in normalized_checks
        if row.get("status") == "failed" and row.get("severity", "blocking") != "blocking"
    ]
    normalized_summary = normalize_json_document(summary)
    checks_value: JsonValue = normalize_json_value(normalized_checks)
    report: JsonDocument = {
        "schema_version": int(schema_version),
        "package_type": _require_registered_package_type(str(package_type), writer_id="song_agent.platform.verification.model.build_verification_report"),
        "status": "failed" if failed else "warning" if warning_status and warnings else "passed",
        "zip_sha256": normalized_summary.get("zip_sha256"),
        "zip_size_bytes": normalized_summary.get("zip_size_bytes", 0),
        "manifest_hash": normalized_summary.get("manifest_hash"),
        "source_hash": normalized_summary.get("source_hash"),
        "summary": normalized_summary,
        "checks": checks_value,
        "blockers": [str(row.get("check_id")) for row in failed],
        "warnings": [str(row.get("check_id")) for row in warnings],
    }
    if extra:
        report.update(normalize_json_document(extra))
    report["integrity_hash"] = integrity_hash(report)
    return report
