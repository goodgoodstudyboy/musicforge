from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document, as_list as _as_list

import json as json
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.delivery.distribution import DistributionStateError as DistributionStateError, DistributionStore as DistributionStore
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.delivery.distribution_templates import template_summary as template_summary
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash


DISTRIBUTION_CHECKLIST_SCHEMA_VERSION = 1
CHECKLIST_STATUSES = {"pending", "done", "waived", "blocked"}


class DistributionChecklistError(ValueError):
    pass


def checklist_dir(store: DistributionStore, release_id: str) -> Path:
    return store.distribution_dir(release_id) / "checklist"


def checklist_path(store: DistributionStore, release_id: str, target_id: str) -> Path:
    return checklist_dir(store, release_id) / f"{target_id}-checklist.json"


def read_distribution_checklist(store: DistributionStore, release_id: str, target_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    path = checklist_path(store, release_id, target_id)
    if not path.exists():
        return default if default is not None else {}
    value = read_json(path)
    return sanitize_metadata(_as_document(value), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def initialize_distribution_checklist(
    store: DistributionStore,
    release_id: str,
    target: Any,
    template: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    store.ensure_target_mutable(release_id, target)
    return reconcile_distribution_checklist(store, release_id, target, template, now=now, write=True)


def reconcile_distribution_checklist(
    store: DistributionStore,
    release_id: str,
    target: Any,
    template: dict[str, Any],
    *,
    now: str | None = None,
    write: bool = False,
) -> dict[str, Any]:
    now = now or now_iso()
    existing = read_distribution_checklist(store, release_id, target.target_id, default={})
    existing_items = {str(item.get("item_id")): item for item in existing.get("items", []) if isinstance(item, dict)}
    template_items = _as_list(template.get("checklist"))
    items: list[dict[str, Any]] = []
    for item in template_items:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id") or "").strip()
        if not item_id:
            continue
        previous = existing_items.get(item_id, {})
        status = str(previous.get("status") or item.get("default_status") or "pending")
        if status not in CHECKLIST_STATUSES:
            status = "pending"
        items.append(
            {
                "item_id": item_id,
                "label": str(item.get("label") or item_id)[:160],
                "description": str(item.get("description") or "")[:500],
                "required": bool(item.get("required", False)),
                "scope": str(item.get("scope") or "release")[:40],
                "status": status,
                "note": _safe_note(previous.get("note")),
                "waiver_reason": _safe_note(previous.get("waiver_reason")),
                "updated_at": str(previous.get("updated_at") or now),
                "updated_by": str(previous.get("updated_by") or "local-user")[:120],
            }
        )
    document = {
        "schema_version": DISTRIBUTION_CHECKLIST_SCHEMA_VERSION,
        "release_id": release_id,
        "target_id": target.target_id,
        "template_pack_id": template.get("template_pack_id"),
        "template_hash": template.get("template_hash"),
        "updated_at": now,
        "items": items,
    }
    document["summary"] = checklist_summary(document)
    document["payload_hash"] = checklist_payload_hash(document)
    document = sanitize_metadata(document, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
    if write:
        write_json(checklist_path(store, release_id, target.target_id), document)
        store.append_event(release_id, "distribution_checklist_initialized", {"target_id": target.target_id, "template_pack_id": template.get("template_pack_id")})
    return document


def update_distribution_checklist_item(
    store: DistributionStore,
    release_id: str,
    target: Any,
    template: dict[str, Any],
    item_id: str,
    payload: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    store.ensure_target_mutable(release_id, target)
    now = now or now_iso()
    document = reconcile_distribution_checklist(store, release_id, target, template, now=now, write=False)
    status = str(payload.get("status") or "").strip()
    if status not in CHECKLIST_STATUSES:
        raise DistributionChecklistError("Unsupported checklist status.")
    found = False
    for item in document.get("items", []):
        if not isinstance(item, dict) or item.get("item_id") != item_id:
            continue
        found = True
        item["status"] = status
        item["note"] = _safe_note(payload.get("note"))
        item["waiver_reason"] = _safe_note(payload.get("waiver_reason"))
        item["updated_at"] = now
        item["updated_by"] = str(payload.get("updated_by") or "local-user")[:120]
        break
    if not found:
        raise DistributionChecklistError(f"Checklist item does not exist: {item_id}.")
    document["updated_at"] = now
    document["summary"] = checklist_summary(document)
    document["payload_hash"] = checklist_payload_hash(document)
    document = sanitize_metadata(document, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
    write_json(checklist_path(store, release_id, target.target_id), document)
    target.latest_qa_summary = _stale_summary(target.latest_qa_summary, "checklist_updated")
    target.latest_export_summary = _stale_summary(target.latest_export_summary, "checklist_updated")
    store.save_target(target)
    store.append_event(release_id, "distribution_checklist_item_updated", {"target_id": target.target_id, "item_id": item_id, "status": status})
    return document


def checklist_summary(document: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(document)
    items = _as_list(data.get("items"))
    counts = {status: 0 for status in CHECKLIST_STATUSES}
    required_pending = 0
    required_blocked = 0
    required_waived_missing_reason = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "pending")
        counts[status] = counts.get(status, 0) + 1
        required = bool(item.get("required", False))
        if required and status == "pending":
            required_pending += 1
        if required and status == "blocked":
            required_blocked += 1
        if required and status == "waived" and not str(item.get("waiver_reason") or "").strip():
            required_waived_missing_reason += 1
    status = "failed" if required_pending or required_blocked else "warning" if counts.get("pending", 0) or required_waived_missing_reason else "passed"
    return sanitize_metadata(
        {
            "status": status,
            "item_count": len([item for item in items if isinstance(item, dict)]),
            "done_count": counts.get("done", 0),
            "pending_count": counts.get("pending", 0),
            "waived_count": counts.get("waived", 0),
            "blocked_count": counts.get("blocked", 0),
            "required_pending_count": required_pending,
            "required_blocked_count": required_blocked,
            "required_waived_missing_reason_count": required_waived_missing_reason,
            "payload_hash": checklist_payload_hash(data) if data else None,
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def checklist_checks(document: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = _as_document(document)
    summary = checklist_summary(data)
    checks: list[dict[str, Any]] = [
        _check("checklist_exists", not bool(data), "blocking", "Submission checklist exists."),
        _check("checklist_required_pending", int(summary.get("required_pending_count") or 0) > 0, "blocking", "Required checklist items are still pending.", count=int(summary.get("required_pending_count") or 0)),
        _check("checklist_required_blocked", int(summary.get("required_blocked_count") or 0) > 0, "blocking", "Required checklist items are blocked.", count=int(summary.get("required_blocked_count") or 0)),
        _check("checklist_required_waiver_reason", int(summary.get("required_waived_missing_reason_count") or 0) > 0, "warning", "Required checklist waivers need a reason.", count=int(summary.get("required_waived_missing_reason_count") or 0)),
        _check("checklist_optional_pending", int(summary.get("pending_count") or 0) > int(summary.get("required_pending_count") or 0), "warning", "Optional checklist items are still pending.", count=max(0, int(summary.get("pending_count") or 0) - int(summary.get("required_pending_count") or 0))),
    ]
    return checks


def checklist_payload_hash(document: dict[str, Any] | None) -> str:
    data = _as_document(document)
    return stable_hash(
        {
            "release_id": data.get("release_id"),
            "target_id": data.get("target_id"),
            "template_pack_id": data.get("template_pack_id"),
            "template_hash": data.get("template_hash"),
            "items": [
                {
                    "item_id": item.get("item_id"),
                    "required": item.get("required"),
                    "status": item.get("status"),
                    "note": item.get("note"),
                    "waiver_reason": item.get("waiver_reason"),
                }
                for item in data.get("items", [])
                if isinstance(item, dict)
            ],
        }
    )


def checklist_export_payload(document: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            **document,
            "template_summary": template_summary(template),
            "summary": checklist_summary(document),
            "payload_hash": checklist_payload_hash(document),
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def checklist_markdown(document: dict[str, Any], template: dict[str, Any]) -> str:
    summary = checklist_summary(document)
    lines = [
        f"# Distribution Checklist - {template.get('name') or template.get('slug') or 'Template'}",
        "",
        f"Status: {summary.get('status')}",
        "",
    ]
    for item in document.get("items", []):
        if not isinstance(item, dict):
            continue
        mark = "x" if item.get("status") == "done" else "!"
        required = "required" if item.get("required") else "optional"
        lines.append(f"- [{mark}] {item.get('label') or item.get('item_id')} ({required}, {item.get('status')})")
        if item.get("note"):
            lines.append(f"  Note: {sanitize_sensitive_text(str(item.get('note')))}")
        if item.get("waiver_reason"):
            lines.append(f"  Waiver: {sanitize_sensitive_text(str(item.get('waiver_reason')))}")
    return "\n".join(lines).rstrip() + "\n"


def _safe_note(value: Any) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:500]


def _stale_summary(summary: ImplementationDocument | None, reason: str) -> ImplementationDocument:
    data = dict(summary or {})
    if data:
        data["stale"] = True
        data["status"] = "stale"
        data["stale_reason"] = reason
    return sanitize_metadata(data, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def _check(check_id: str, failed: bool, severity: str, message: str, count: int | None = None) -> ImplementationDocument:
    item: ImplementationDocument = {
        "scope": "distribution_checklist",
        "check_id": check_id,
        "status": "failed" if failed and severity == "blocking" else "warning" if failed else "passed",
        "severity": severity,
        "message": message,
    }
    if count is not None:
        item["count"] = count
    return sanitize_metadata(item, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
