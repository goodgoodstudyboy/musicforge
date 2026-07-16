from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


ATTESTATION_PACKAGE_TYPE = "release_portfolio_governance_public_attestation"


ATTESTATION_CERTIFICATE_TYPE = "musicforge_portfolio_governance_public_attestation"


ATTESTATION_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


ATTESTATION_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


ATTESTATION_CERTIFICATE_HASH_EXCLUDE_KEYS = {"payload_hash", "issued_at", "updated_at"}


ATTESTATION_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


def attestation_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in ATTESTATION_REPORT_HASH_EXCLUDE_KEYS})


def attestation_certificate_hash(certificate: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (certificate or {}).items() if key not in ATTESTATION_CERTIFICATE_HASH_EXCLUDE_KEYS})


def attestation_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ATTESTATION_MANIFEST_HASH_EXCLUDE_KEYS})


def attestation_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata({"status": report.get("status"), "zip_sha256": report.get("zip_sha256"), "zip_size_bytes": report.get("zip_size_bytes"), "manifest_hash": report.get("manifest_hash"), "portfolio_id": summary.get("portfolio_id"), "certificate_id": summary.get("certificate_id"), "blocker_count": summary.get("blocker_count", 0), "warning_count": summary.get("warning_count", 0)}, blocked_keys=ATTESTATION_BLOCKED_KEYS)
