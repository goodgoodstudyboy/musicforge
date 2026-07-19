from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

from song_agent.platform.verification.hashing import integrity_hash


def build_check(
    check_id: str,
    passed: bool,
    message: str,
    details: DomainDocument | None = None,
    *,
    severity: str = "blocking",
) -> DomainDocument:
    row: ImplementationDocument = {
        "check_id": str(check_id),
        "status": "passed" if passed else "failed",
        "severity": str(severity),
        "message": str(message),
        "details": details or {},
    }
    return row


def has_blocking_failures(checks: list[DomainDocument]) -> bool:
    return any(
        row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"
        for row in checks
    )


def build_verification_report(
    *,
    package_type: str,
    checks: list[DomainDocument],
    summary: DomainDocument,
    schema_version: int = 1,
    extra: DomainDocument | None = None,
    warning_status: bool = False,
) -> DomainDocument:
    failed = [
        row for row in checks
        if row.get("status") == "failed" and row.get("severity", "blocking") == "blocking"
    ]
    warnings = [
        row for row in checks
        if row.get("status") == "failed" and row.get("severity", "blocking") != "blocking"
    ]
    report: ImplementationDocument = {
        "schema_version": int(schema_version),
        "package_type": str(package_type),
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
