from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document
from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


TRANSPARENCY_FEED_PACKAGE_TYPE = "release_portfolio_governance_attestation_transparency_feed"


TRANSPARENCY_REPORT_PACKAGE_TYPE = "release_portfolio_governance_attestation_transparency_report"


TRANSPARENCY_PACKAGE_TYPE = "release_portfolio_governance_attestation_transparency"


TRANSPARENCY_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


TRANSPARENCY_FEED_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


TRANSPARENCY_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


TRANSPARENCY_NOTICE_HASH_EXCLUDE_KEYS = {"integrity_hash"}


TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS = {"event_hash"}


def transparency_feed_hash(feed: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (feed or {}).items() if key not in TRANSPARENCY_FEED_HASH_EXCLUDE_KEYS})


def transparency_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in TRANSPARENCY_MANIFEST_HASH_EXCLUDE_KEYS})


def transparency_event_hash(event: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (event or {}).items() if key not in TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS})


def transparency_notice_hash(notice: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (notice or {}).items() if key not in TRANSPARENCY_NOTICE_HASH_EXCLUDE_KEYS})


def transparency_summary(feed: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(feed)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "readiness": data.get("readiness") or "missing",
            "portfolio_id": data.get("portfolio_id"),
            "profile": data.get("attestation_profile") or "public_summary",
            "event_count": summary.get("event_count", 0),
            "notice_count": summary.get("notice_count", 0),
            "current_entry_id": summary.get("current_entry_id"),
            "current_certificate_id": summary.get("current_certificate_id"),
            "external_review_status": summary.get("external_review_status") or "missing",
            "latest_notice_type": summary.get("latest_notice_type"),
        },
        blocked_keys=TRANSPARENCY_BLOCKED_KEYS,
    )


def _build_events(portfolio_id: str, profile: str, public_state: ImplementationDocument, source: ImplementationDocument, *, now: str) -> list[ImplementationDocument]:
    registry = _as_document(public_state.get("registry"))
    attestation = _as_document(public_state.get("public_attestation"))
    portal = _as_document(public_state.get("portal"))
    accepted = _as_document(public_state.get("accepted_evidence"))
    definitions: list[tuple[str, str, str, str, dict[str, Any]]] = []
    current_id = registry.get("current_entry_id")
    current_status = registry.get("current_entry_status")
    if current_id and current_status == "published":
        definitions.append(("registry_current_published", "info", "Current public attestation entry is published", f"Registry current entry {current_id} is published.", {"current_entry_id": current_id, "current_certificate_id": registry.get("current_certificate_id")}))
    elif current_status == "revoked":
        definitions.append(("registry_current_revoked", "warning", "Current public attestation entry is revoked", f"Registry current entry {current_id} is revoked.", {"current_entry_id": current_id}))
    else:
        definitions.append(("registry_current_missing", "warning", "Current public attestation entry is missing", "No current published Registry entry is available.", {"current_entry_id": current_id}))
    definitions.append(("public_attestation_verified" if attestation.get("attestation_verification_status") == "passed" else "public_attestation_verification_failed", "info" if attestation.get("attestation_verification_status") == "passed" else "warning", "Public Attestation verification", f"Public Attestation verification status is {attestation.get('attestation_verification_status') or 'missing'}.", {"attestation_manifest_hash": attestation.get("attestation_manifest_hash")}))
    definitions.append(("portal_snapshot_verified" if portal.get("portal_verification_status") == "passed" else "portal_snapshot_stale", "info" if portal.get("portal_verification_status") == "passed" else "warning", "Portal snapshot verification", f"Portal verification status is {portal.get('portal_verification_status') or 'missing'}.", {"portal_manifest_hash": portal.get("portal_manifest_hash")}))
    if _accepted_evidence_current(source):
        definitions.append(("accepted_evidence_current", "info", "Accepted external review evidence is current", f"Accepted Evidence {accepted.get('accepted_evidence_id')} is current and verified.", {"accepted_evidence_id": accepted.get("accepted_evidence_id"), "accepted_evidence_manifest_hash": accepted.get("accepted_evidence_manifest_hash")}))
        definitions.append(("external_review_accepted", "info", "External review accepted", f"External review response {accepted.get('response_id')} is accepted.", {"response_id": accepted.get("response_id")}))
    elif accepted.get("status") == "archived":
        definitions.append(("accepted_evidence_archived", "warning", "Accepted Evidence is archived", "Accepted Evidence has been archived.", {"accepted_evidence_id": accepted.get("accepted_evidence_id")}))
    elif accepted.get("status") == "stale":
        definitions.append(("accepted_evidence_stale", "warning", "Accepted Evidence is stale", "Accepted Evidence is stale and must not be treated as current.", {"accepted_evidence_id": accepted.get("accepted_evidence_id")}))
    else:
        definitions.append(("accepted_evidence_missing", "warning", "Accepted Evidence is missing", "No current accepted external review evidence is available.", {"accepted_evidence_id": accepted.get("accepted_evidence_id")}))
    events: list[dict[str, Any]] = []
    previous_hash = ""
    for index, (event_type, severity, title, message, refs) in enumerate(definitions, start=1):
        event: ImplementationDocument = {
            "event_id": f"att-trans-event-{index:06d}",
            "event_type": event_type,
            "severity": severity,
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "source": {
                "public_state_hash": source.get("public_state_hash"),
                "registry_current_entry_id": registry.get("current_entry_id"),
                "current_certificate_id": registry.get("current_certificate_id"),
                "portal_manifest_hash": portal.get("portal_manifest_hash"),
                "accepted_evidence_id": accepted.get("accepted_evidence_id"),
            },
            "summary": {"title": title, "message": message, "public_references": refs},
            "created_at": now,
            "previous_event_hash": previous_hash,
        }
        event["event_hash"] = transparency_event_hash(event)
        previous_hash = str(event["event_hash"])
        events.append(sanitize_metadata(event, blocked_keys=TRANSPARENCY_BLOCKED_KEYS))
    return events


def _build_notices(
    portfolio_id: str,
    profile: str,
    public_state: ImplementationDocument,
    source: ImplementationDocument,
    events: list[ImplementationDocument],
    previous_feed: ImplementationDocument,
    *,
    now: str,
) -> list[ImplementationDocument]:
    registry = _as_document(public_state.get("registry"))
    portal = _as_document(public_state.get("portal"))
    accepted = _as_document(public_state.get("accepted_evidence"))
    previous_source = _as_document(previous_feed.get("source"))
    previous_state_hash = (previous_source.get("public_state_hash") or previous_feed.get("source_hash")) if isinstance(previous_feed, dict) else None
    event_by_type = {str(event.get("event_type")): str(event.get("event_id")) for event in events if isinstance(event, dict)}
    rows: list[tuple[str, str, str, str, list[str], dict[str, Any]]] = []
    if registry.get("current_entry_status") == "published":
        rows.append(("initial_publish", "info", "Current public attestation is published", f"Registry current entry {registry.get('current_entry_id')} is published.", [event_by_type.get("registry_current_published", "")], {"current_entry_id": registry.get("current_entry_id"), "current_certificate_id": registry.get("current_certificate_id")}))
    if previous_state_hash and previous_state_hash != source.get("public_state_hash"):
        rows.append(("public_state_refreshed", "info", "Public attestation state changed", "Transparency Feed source changed since the previous refresh.", [events[-1]["event_id"] if events else ""], {"previous_state_hash": previous_state_hash, "current_state_hash": source.get("public_state_hash")}))
    else:
        rows.append(("public_state_refreshed", "info", "Public attestation state refreshed", "Transparency Feed source was refreshed.", [events[-1]["event_id"] if events else ""], {"current_state_hash": source.get("public_state_hash")}))
    if _accepted_evidence_current(source):
        rows.append(("accepted_evidence_added", "info", "Accepted external review evidence available", f"Accepted Evidence {accepted.get('accepted_evidence_id')} is current.", [event_by_type.get("accepted_evidence_current", "")], {"accepted_evidence_id": accepted.get("accepted_evidence_id"), "accepted_evidence_manifest_hash": accepted.get("accepted_evidence_manifest_hash")}))
    else:
        rows.append(("accepted_evidence_missing", "warning", "Accepted external review evidence missing", "No current accepted external review evidence is available.", [event_by_type.get("accepted_evidence_missing", "")], {"accepted_evidence_status": accepted.get("status"), "accepted_evidence_verification_status": accepted.get("accepted_evidence_verification_status")}))
    if portal.get("portal_verification_status") == "passed":
        rows.append(("portal_snapshot_changed", "info", "Portal snapshot fingerprint", "Current Portal snapshot fingerprint is recorded.", [event_by_type.get("portal_snapshot_verified", "")], {"portal_manifest_hash": portal.get("portal_manifest_hash"), "portal_zip_sha256": portal.get("portal_zip_sha256")}))
    notices: list[dict[str, Any]] = []
    from_hash = str(previous_state_hash or "")
    to_hash = str(source.get("public_state_hash") or "")
    for index, (notice_type, severity, title, message, event_ids, refs) in enumerate(rows, start=1):
        notice = {
            "notice_id": f"att-trans-notice-{index:06d}",
            "notice_type": notice_type,
            "severity": severity,
            "portfolio_id": portfolio_id,
            "attestation_profile": profile,
            "from_state_hash": from_hash,
            "to_state_hash": to_hash,
            "source_event_ids": [item for item in event_ids if item],
            "title": title,
            "message": message,
            "public_references": refs,
            "created_at": now,
        }
        notice["integrity_hash"] = transparency_notice_hash(notice)
        notices.append(sanitize_metadata(notice, blocked_keys=TRANSPARENCY_BLOCKED_KEYS))
    return notices


def _accepted_evidence_current(source: ImplementationDocument) -> bool:
    return (
        source.get("accepted_evidence_status") == "current"
        and source.get("accepted_evidence_external_review_status") == "accepted"
        and source.get("accepted_evidence_verification_status") == "passed"
        and bool(source.get("accepted_evidence_zip_sha256"))
        and bool(source.get("accepted_evidence_manifest_hash"))
        and bool(source.get("accepted_evidence_verification_report_hash"))
    )
