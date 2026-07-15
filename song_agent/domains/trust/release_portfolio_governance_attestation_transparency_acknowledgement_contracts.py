from __future__ import annotations

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS
from song_agent.domains.delivery.releases import stable_hash


ACK_SCHEMA_VERSION = 1


ACK_PACK_PACKAGE_TYPE = "release_portfolio_governance_attestation_transparency_acknowledgement_pack"


ACK_RESPONSE_PACKAGE_TYPE = "release_portfolio_governance_attestation_transparency_acknowledgement_response"


ACK_EVIDENCE_PACKAGE_TYPE = "release_portfolio_governance_attestation_transparency_acknowledgement_evidence"


ACK_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


ACK_PACK_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


ACK_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


ACK_EVIDENCE_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


def ack_pack_hash(pack: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (pack or {}).items() if key not in ACK_PACK_HASH_EXCLUDE_KEYS})


def ack_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ACK_MANIFEST_HASH_EXCLUDE_KEYS})


def ack_evidence_hash(evidence: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (evidence or {}).items() if key not in ACK_EVIDENCE_HASH_EXCLUDE_KEYS})


def acknowledgement_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    data = evidence if isinstance(evidence, dict) else {}
    public = data.get("public_summary") if isinstance(data.get("public_summary"), dict) else {}
    return {
        "status": data.get("status") or "missing",
        "external_review_status": data.get("external_review_status") or "missing",
        "acknowledgement_id": data.get("acknowledgement_id"),
        "response_id": (data.get("source") if isinstance(data.get("source"), dict) else {}).get("response_id"),
        "reviewer_name": public.get("reviewer_name"),
        "reviewed_notice_count": public.get("reviewed_notice_count", 0),
    }


def response_template(pack: dict[str, Any]) -> dict[str, Any]:
    source = pack.get("source") if isinstance(pack.get("source"), dict) else {}
    return {
        "schema_version": ACK_SCHEMA_VERSION,
        "package_type": ACK_RESPONSE_PACKAGE_TYPE,
        "response_id": "",
        "review_pack_id": pack.get("pack_id"),
        "review_pack_source_hash": pack.get("source_hash"),
        "portfolio_id": pack.get("portfolio_id"),
        "profile": pack.get("profile") or "public_summary",
        "transparency_zip_sha256": source.get("transparency_zip_sha256"),
        "transparency_manifest_hash": source.get("transparency_manifest_hash"),
        "transparency_feed_source_hash": source.get("transparency_feed_source_hash"),
        "reviewer": {"name": "", "organization": "", "role": ""},
        "review_status": "accepted",
        "reviewed_notice_ids": list(source.get("notice_ids") or []),
        "reviewed_event_ids": list(source.get("event_ids") or []),
        "comments": "",
        "concerns": [],
        "submitted_at": "",
    }
