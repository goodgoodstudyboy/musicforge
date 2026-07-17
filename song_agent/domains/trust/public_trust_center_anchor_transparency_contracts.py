from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document
from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.domains.trust.public_trust_center_anchor_registry_contracts import ANCHOR_REGISTRY_BLOCKED_KEYS
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash


ANCHOR_TRANSPARENCY_PACKAGE_TYPE = "musicforge_public_trust_center_anchor_transparency"


ANCHOR_CHECKPOINT_PACKAGE_TYPE = "musicforge_public_trust_center_anchor_checkpoint"


ANCHOR_TRANSPARENCY_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at", "zip"}


ANCHOR_TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS = {"integrity_hash", "created_at", "updated_at"}


ANCHOR_TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS = {"event_hash"}


ANCHOR_CHECKPOINT_HASH_EXCLUDE_KEYS = {"integrity_hash"}


ANCHOR_TRANSPARENCY_BLOCKED_KEYS = ANCHOR_REGISTRY_BLOCKED_KEYS


def anchor_transparency_event_hash(event: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (event or {}).items() if key not in ANCHOR_TRANSPARENCY_EVENT_HASH_EXCLUDE_KEYS})


def anchor_transparency_ledger_hash(events: list[dict[str, Any]]) -> str:
    return stable_hash([event for event in events if isinstance(event, dict)])


def anchor_checkpoint_hash(checkpoint: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (checkpoint or {}).items() if key not in ANCHOR_CHECKPOINT_HASH_EXCLUDE_KEYS})


def anchor_checkpoint_integrity_ok(checkpoint: dict[str, Any] | None) -> bool:
    data = _as_document(checkpoint)
    return bool(data.get("integrity_hash")) and data.get("integrity_hash") == anchor_checkpoint_hash(data)


def anchor_checkpoint_signature_ok(checkpoint: dict[str, Any] | None) -> bool:
    data = _as_document(checkpoint)
    signature = _as_document(data.get("signature"))
    payload_hash = _checkpoint_payload_hash(data)
    expected_key = stable_hash({"key_id": signature.get("key_id"), "mode": signature.get("mode")})
    expected_signature = stable_hash({key: value for key, value in signature.items() if key != "signature_hash"})
    return (
        signature.get("mode") == "local_deterministic_checkpoint"
        and signature.get("payload_hash") == payload_hash
        and signature.get("key_fingerprint") == expected_key
        and signature.get("signature_hash") == expected_signature
    )


def anchor_transparency_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (report or {}).items() if key not in ANCHOR_TRANSPARENCY_REPORT_HASH_EXCLUDE_KEYS})


def anchor_transparency_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in (manifest or {}).items() if key not in ANCHOR_TRANSPARENCY_HASH_EXCLUDE_KEYS})


def anchor_transparency_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "center_id": data.get("center_id") or summary.get("center_id"),
            "event_count": summary.get("event_count", 0),
            "checkpoint_id": summary.get("checkpoint_id"),
            "current_entry_id": summary.get("current_entry_id"),
            "current_entry_status": summary.get("current_entry_status"),
            "registry_verification_status": summary.get("registry_verification_status"),
        },
        blocked_keys=ANCHOR_TRANSPARENCY_BLOCKED_KEYS,
    )


def _checkpoint_payload_hash(checkpoint: ImplementationDocument) -> str:
    payload = {key: value for key, value in (checkpoint or {}).items() if key not in {"signature", "integrity_hash"}}
    return stable_hash(payload)
