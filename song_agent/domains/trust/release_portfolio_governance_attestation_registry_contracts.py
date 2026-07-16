from __future__ import annotations
from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


REGISTRY_PACKAGE_TYPE = "release_portfolio_governance_attestation_registry"


REGISTRY_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


REGISTRY_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at"}


REGISTRY_ENTRY_HASH_EXCLUDE_KEYS = {"integrity_hash"}


REGISTRY_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


REGISTRY_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


ENTRY_STATUSES = {"draft", "published", "revoked", "superseded", "archived", "failed"}


def registry_hash(registry: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (registry or {}).items() if key not in REGISTRY_HASH_EXCLUDE_KEYS})


def registry_entry_hash(entry: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (entry or {}).items() if key not in REGISTRY_ENTRY_HASH_EXCLUDE_KEYS})


def registry_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in REGISTRY_REPORT_HASH_EXCLUDE_KEYS})


def registry_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in REGISTRY_MANIFEST_HASH_EXCLUDE_KEYS})


def registry_summary(registry: dict[str, Any] | None) -> dict[str, Any]:
    data = registry if isinstance(registry, dict) else {}
    entries = data.get("entries") if isinstance(data.get("entries"), list) else []
    current = _find_entry(data, str(data.get("current_entry_id") or "")) if data.get("current_entry_id") else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "current_entry_id": data.get("current_entry_id"),
            "current_certificate_id": current.get("certificate_id") if current else None,
            "entry_count": len(entries),
            "published_count": sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "published"),
            "revoked_count": sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "revoked"),
            "superseded_count": sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "superseded"),
            "has_current_published_attestation": bool(current and current.get("status") == "published"),
            "latest_attestation_verification_status": (current.get("verification") if isinstance(current.get("verification"), dict) else {}).get("status") if current else None,
        },
        blocked_keys=REGISTRY_BLOCKED_KEYS,
    )


def registry_verification_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return sanitize_metadata({"status": report.get("status"), "portfolio_id": summary.get("portfolio_id"), "current_entry_id": summary.get("current_entry_id"), "blocker_count": summary.get("blocker_count", 0), "warning_count": summary.get("warning_count", 0), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash")}, blocked_keys=REGISTRY_BLOCKED_KEYS)


def _find_entry(registry: ImplementationDocument, entry_id: str) -> ImplementationDocument:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}
