from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


ACCEPTED_EVIDENCE_PACKAGE_TYPE = "release_portfolio_governance_attestation_accepted_evidence"


ACCEPTED_EVIDENCE_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


ACCEPTED_EVIDENCE_STATUSES = {"current", "stale", "failed", "archived"}


def accepted_evidence_hash(evidence: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (evidence or {}).items() if key not in ACCEPTED_EVIDENCE_HASH_EXCLUDE_KEYS})


def accepted_evidence_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ACCEPTED_EVIDENCE_MANIFEST_HASH_EXCLUDE_KEYS})


def accepted_evidence_summary(evidence: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(evidence)
    public = _as_document(data.get("public_summary"))
    source = _as_document(data.get("source"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "external_review_status": public.get("external_review_status") or data.get("status") or "missing",
            "accepted_evidence_id": data.get("accepted_evidence_id"),
            "response_id": source.get("response_id") or public.get("response_id"),
            "reviewer_label": public.get("reviewer_label"),
            "reviewed_at": public.get("accepted_at") or public.get("reviewed_at"),
            "verification_status": source.get("response_verification_status"),
            "source_hash": data.get("source_hash"),
            "current_entry_id": source.get("registry_current_entry_id"),
            "current_certificate_id": source.get("current_certificate_id"),
            "stale": data.get("status") == "stale",
        },
        blocked_keys=ACCEPTED_EVIDENCE_BLOCKED_KEYS,
    )
