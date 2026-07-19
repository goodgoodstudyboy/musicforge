from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document, as_list as _as_list

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


ANCHOR_REGISTRY_PACKAGE_TYPE = "musicforge_public_trust_center_anchor_registry"


ANCHOR_REGISTRY_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path", "file"}


ANCHOR_REGISTRY_HASH_EXCLUDE_KEYS = {"integrity_hash", "updated_at", "events"}


ANCHOR_ENTRY_HASH_EXCLUDE_KEYS = {"integrity_hash"}


ANCHOR_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "generated_at", "updated_at"}


ANCHOR_MANIFEST_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


ANCHOR_EVENT_HASH_EXCLUDE_KEYS = {"event_hash"}


ANCHOR_ENTRY_STATUSES = {"draft", "published", "superseded", "revoked"}


def anchor_registry_hash(registry: DomainDocument) -> str:
    payload = {key: value for key, value in (registry or {}).items() if key not in ANCHOR_REGISTRY_HASH_EXCLUDE_KEYS}
    payload["state_events"] = [
        event
        for event in registry.get("events", []) if isinstance(event, dict) and event.get("event_type") not in {"exported", "zip_built"}
    ] if isinstance(registry.get("events"), list) else []
    return stable_hash(payload)


def anchor_entry_hash(entry: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (entry or {}).items() if key not in ANCHOR_ENTRY_HASH_EXCLUDE_KEYS})


def anchor_registry_report_hash(report: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in ANCHOR_REPORT_HASH_EXCLUDE_KEYS})


def anchor_registry_manifest_hash(manifest: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ANCHOR_MANIFEST_HASH_EXCLUDE_KEYS})


def anchor_event_hash(event: DomainDocument) -> str:
    return stable_hash({key: value for key, value in (event or {}).items() if key not in ANCHOR_EVENT_HASH_EXCLUDE_KEYS})


def anchor_entry_signature_ok(entry: DomainDocument | None) -> bool:
    data = _as_document(entry)
    signature = _as_document(data.get("signature"))
    payload = {
        "anchor_hash": data.get("anchor_hash"),
        "zip_fingerprint": _as_document(data.get("zip_fingerprint")),
        "delivery_fingerprint_summary": _as_document(data.get("delivery_fingerprint_summary")),
    }
    expected_payload_hash = stable_hash(payload)
    expected_key = stable_hash({"key_id": signature.get("key_id"), "mode": signature.get("mode")})
    expected_signature = stable_hash({key: value for key, value in signature.items() if key != "signature_hash"})
    return (
        signature.get("mode") == "local_deterministic"
        and bool(signature.get("key_id"))
        and signature.get("signed_payload_hash") == expected_payload_hash
        and signature.get("key_fingerprint") == expected_key
        and signature.get("signature_hash") == expected_signature
    )


def anchor_registry_summary(registry: DomainDocument | None) -> DomainDocument:
    data = _as_document(registry)
    entries = _as_list(data.get("entries"))
    current = _current_entry(data)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "center_id": data.get("center_id"),
            "current_entry_id": data.get("current_entry_id"),
            "current_anchor_hash": current.get("anchor_hash") if current else None,
            "current_entry_status": current.get("status") if current else None,
            "entry_count": len(entries),
            "published_count": sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "published"),
            "revoked_count": sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "revoked"),
            "superseded_count": sum(1 for item in entries if isinstance(item, dict) and item.get("status") == "superseded"),
        },
        blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS,
    )


def anchor_registry_verification_summary(report: DomainDocument) -> DomainDocument:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata({"status": report.get("status"), "center_id": summary.get("center_id"), "current_entry_id": summary.get("current_entry_id"), "current_anchor_hash": summary.get("current_anchor_hash"), "blocker_count": summary.get("blocker_count", 0), "warning_count": summary.get("warning_count", 0), "zip_sha256": report.get("zip_sha256"), "manifest_hash": report.get("manifest_hash")}, blocked_keys=ANCHOR_REGISTRY_BLOCKED_KEYS)


def _current_entry(registry: ImplementationDocument) -> ImplementationDocument:
    return _find_entry(registry, str(registry.get("current_entry_id") or "")) if registry.get("current_entry_id") else {}


def _find_entry(registry: ImplementationDocument, entry_id: str) -> ImplementationDocument:
    for entry in registry.get("entries", []) if isinstance(registry.get("entries"), list) else []:
        if isinstance(entry, dict) and entry.get("entry_id") == entry_id:
            return entry
    return {}
