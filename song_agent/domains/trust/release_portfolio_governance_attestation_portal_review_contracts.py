from __future__ import annotations
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


PORTAL_REVIEW_PACK_PACKAGE_TYPE = "release_portfolio_governance_attestation_portal_review_pack"


PORTAL_REVIEW_RESPONSE_PACKAGE_TYPE = "release_portfolio_governance_attestation_portal_response"


PORTAL_REVIEW_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


PORTAL_REVIEW_PACK_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


PORTAL_REVIEW_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


PORTAL_REVIEW_RESPONSE_HASH_FIELDS = (
    "response_id",
    "review_pack_id",
    "review_pack_source_hash",
    "reviewer",
    "decision",
    "reviewed_at",
    "rating",
    "notes",
    "findings",
    "attachment_summaries",
)


def review_pack_hash(pack: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (pack or {}).items() if key not in PORTAL_REVIEW_PACK_HASH_EXCLUDE_KEYS})


def review_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in PORTAL_REVIEW_MANIFEST_HASH_EXCLUDE_KEYS})


def response_payload_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: response.get(key) for key in PORTAL_REVIEW_RESPONSE_HASH_FIELDS})


def response_integrity_hash(response: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (response or {}).items() if key != "integrity_hash"})


def review_pack_summary(pack: dict[str, Any]) -> dict[str, Any]:
    source = pack.get("source") if isinstance(pack.get("source"), dict) else {}
    return {
        "status": pack.get("status") or "missing",
        "portfolio_id": pack.get("portfolio_id"),
        "review_pack_id": pack.get("review_pack_id"),
        "source_hash": pack.get("source_hash"),
        "portal_verification_status": source.get("portal_verification_status"),
        "current_entry_id": source.get("registry_current_entry_id"),
        "current_certificate_id": source.get("current_certificate_id"),
        "blocker_count": len(pack.get("blockers") if isinstance(pack.get("blockers"), list) else []),
        "warning_count": len(pack.get("warnings") if isinstance(pack.get("warnings"), list) else []),
    }


def response_summary(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "response_id": response.get("response_id"),
        "review_pack_id": response.get("review_pack_id"),
        "review_pack_source_hash": response.get("review_pack_source_hash"),
        "decision": response.get("decision"),
        "status": response.get("status"),
        "reviewer": response.get("reviewer"),
        "reviewed_at": response.get("reviewed_at"),
        "payload_hash": response.get("payload_hash"),
        "integrity_hash": response.get("integrity_hash"),
    }


def verification_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key != "generated_at"})
