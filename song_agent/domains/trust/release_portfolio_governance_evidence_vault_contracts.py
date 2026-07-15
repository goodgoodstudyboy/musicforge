from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


EVIDENCE_VAULT_PACKAGE_TYPE = "release_portfolio_governance_evidence_vault"


EVIDENCE_VAULT_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


EVIDENCE_VAULT_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


EVIDENCE_VAULT_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


def evidence_vault_report_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in EVIDENCE_VAULT_REPORT_HASH_EXCLUDE_KEYS})


def evidence_vault_package_index_hash(index: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (index or {}).items() if key not in EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS})


def evidence_vault_verification_index_hash(index: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (index or {}).items() if key not in EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS})


def evidence_vault_chain_hash(chain: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (chain or {}).items() if key not in EVIDENCE_VAULT_INDEX_HASH_EXCLUDE_KEYS})


def evidence_vault_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in EVIDENCE_VAULT_MANIFEST_HASH_EXCLUDE_KEYS})


def evidence_vault_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": report.get("status"),
            "zip_sha256": report.get("zip_sha256"),
            "zip_size_bytes": report.get("zip_size_bytes"),
            "manifest_hash": report.get("manifest_hash"),
            "portfolio_id": summary.get("portfolio_id"),
            "deep_verification_status": summary.get("deep_verification_status"),
            "checked_package_count": summary.get("checked_package_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=EVIDENCE_VAULT_BLOCKED_KEYS,
    )
