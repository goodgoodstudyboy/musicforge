from __future__ import annotations

from song_agent.platform.contracts import DomainDocument
from song_agent.platform.contracts.coercion import as_document as _as_document

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


PORTAL_PACKAGE_TYPE = "release_portfolio_governance_attestation_portal"


PORTAL_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


PORTAL_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


PORTAL_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


PORTAL_PAGES = ("index.html", "current.html", "registry.html", "revocations.html", "verify.html")


def portal_report_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in PORTAL_REPORT_HASH_EXCLUDE_KEYS})


def portal_manifest_hash(manifest: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in PORTAL_MANIFEST_HASH_EXCLUDE_KEYS})


def portal_verification_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata({"status": report.get("status"), "portfolio_id": summary.get("portfolio_id"), "current_entry_id": summary.get("current_entry_id"), "blocker_count": summary.get("blocker_count", 0), "warning_count": summary.get("warning_count", 0), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash")}, blocked_keys=PORTAL_BLOCKED_KEYS)


def portal_summary(report: DomainDocument) -> DomainDocument:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness") or "missing",
            "portfolio_id": data.get("portfolio_id"),
            "current_entry_id": summary.get("current_entry_id"),
            "current_certificate_id": summary.get("current_certificate_id"),
            "registry_status": summary.get("registry_status"),
            "attestation_status": summary.get("attestation_status"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=PORTAL_BLOCKED_KEYS,
    )
