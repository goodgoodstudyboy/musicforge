from __future__ import annotations

from datetime import datetime
from typing import Any

from song_agent.domains.creation.redaction import DEFAULT_BLOCKED_METADATA_KEYS, sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.trust.release_operations_retrospective_contracts import RETROSPECTIVE_HASH_EXCLUDE_KEYS, operations_retrospective_integrity_hash


OPERATIONS_RETROSPECTIVE_SCHEMA_VERSION = 1

RETROSPECTIVE_BLOCKED_KEYS = DEFAULT_BLOCKED_METADATA_KEYS - {"path"}


def build_operations_retrospective_report(
    *,
    release_id: str,
    audit_report: dict[str, Any],
    ledger_entries: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    timeline = _timeline(ledger_entries)
    stage_durations = _stage_durations(timeline)
    risk_hotspots = _risk_hotspots(audit_report, ledger_entries)
    manual_summary = _manual_action_summary(ledger_entries)
    verifier_outcomes = _verifier_outcomes(audit_report, ledger_entries)
    change_summary = _change_request_summary(ledger_entries)
    warnings = []
    if any(item.get("duration_status") == "unknown" for item in stage_durations):
        warnings.append({"check_id": "retrospective_duration_unknown", "severity": "warning", "message": "Some stage durations could not be calculated because timestamps are missing."})
    recommendations = _recommendations(stage_durations, risk_hotspots, manual_summary, change_summary, verifier_outcomes)
    source = {
        "audit_report_integrity_hash": audit_report.get("integrity_hash"),
        "audit_source_hash": audit_report.get("source_hash"),
        "ledger_hash": audit_report.get("ledger_hash"),
        "entry_count": len(ledger_entries),
    }
    report = {
        "schema_version": OPERATIONS_RETROSPECTIVE_SCHEMA_VERSION,
        "release_id": release_id,
        "generated_at": generated_at,
        "status": "warning" if warnings else "passed",
        "source_hash": stable_hash(source),
        "source": source,
        "timeline": timeline,
        "stage_durations": stage_durations,
        "risk_hotspots": risk_hotspots,
        "manual_action_summary": manual_summary,
        "verifier_outcomes": verifier_outcomes,
        "change_request_summary": change_summary,
        "recommendations": recommendations,
        "warnings": warnings,
    }
    report["integrity_hash"] = operations_retrospective_integrity_hash(report)
    return sanitize_metadata(report, blocked_keys=RETROSPECTIVE_BLOCKED_KEYS)





def operations_retrospective_integrity_ok(report: dict[str, Any] | None) -> bool:
    data = report if isinstance(report, dict) else {}
    return bool(data.get("integrity_hash")) and str(data.get("integrity_hash")) == operations_retrospective_integrity_hash(data)


def retrospective_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "source_hash": data.get("source_hash"),
            "integrity_ok": operations_retrospective_integrity_ok(data),
            "timeline_count": len(data.get("timeline") if isinstance(data.get("timeline"), list) else []),
            "recommendation_count": len(data.get("recommendations") if isinstance(data.get("recommendations"), list) else []),
            "risk_hotspot_count": len(data.get("risk_hotspots") if isinstance(data.get("risk_hotspots"), list) else []),
        },
        blocked_keys=RETROSPECTIVE_BLOCKED_KEYS,
    )


def _timeline(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in entries:
        event_type = str(item.get("event_type") or "")
        domain = str(item.get("domain") or "")
        if domain not in {"release", "operations_report", "operations_runbook", "operations_signoff", "operations_change_request", "operations_archive", "operations_audit"}:
            continue
        rows.append(
            {
                "entry_id": item.get("entry_id"),
                "occurred_at": item.get("occurred_at"),
                "domain": domain,
                "event_type": event_type,
                "risk": item.get("risk"),
                "mutation_kind": item.get("mutation_kind"),
                "payload_hash": (item.get("evidence_ref") or {}).get("payload_hash") if isinstance(item.get("evidence_ref"), dict) else None,
            }
        )
    return rows[:500]


def _stage_durations(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checkpoints = {
        "release_created": _first_time(timeline, {"release_document_current"}),
        "operations_report": _first_time(timeline, {"operations_report_refreshed"}),
        "runbook": _first_time(timeline, {"operations_runbook_current"}),
        "signoff": _first_time(timeline, {"operations_signoff_signed"}),
        "archive": _first_time(timeline, {"operations_archive_exported"}),
        "audit": _first_time(timeline, {"operations_audit_refreshed"}),
    }
    pairs = [
        ("release_to_operations_report", "release_created", "operations_report"),
        ("operations_report_to_runbook", "operations_report", "runbook"),
        ("runbook_to_signoff", "runbook", "signoff"),
        ("signoff_to_archive", "signoff", "archive"),
        ("archive_to_audit", "archive", "audit"),
        ("total_release_operations_duration", "release_created", "audit"),
    ]
    rows = []
    for name, start_key, end_key in pairs:
        start = checkpoints.get(start_key)
        end = checkpoints.get(end_key)
        duration = _duration_seconds(start, end)
        rows.append(
            {
                "stage": name,
                "start_at": start,
                "end_at": end,
                "duration_seconds": duration,
                "duration_status": "known" if duration is not None else "unknown",
            }
        )
    return rows


def _risk_hotspots(audit_report: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hotspots: list[dict[str, Any]] = []
    if any(item.get("event_type") == "operations_change_request_applied" for item in entries):
        hotspots.append({"risk": "applied_change_request", "count": sum(1 for item in entries if item.get("event_type") == "operations_change_request_applied"), "severity": "warning"})
    if any(item.get("event_type") == "operations_signoff_signed" and "force" in str((item.get("source_ref") or {}).get("source_id") or "") for item in entries):
        hotspots.append({"risk": "force_signoff", "count": 1, "severity": "warning"})
    verifier_summary = audit_report.get("package_verifiers") if isinstance(audit_report.get("package_verifiers"), dict) else {}
    failed_count = int(verifier_summary.get("failed_count") or 0)
    if failed_count:
        hotspots.append({"risk": "failed_package_verifier", "count": failed_count, "severity": "blocking"})
    warning_count = len(audit_report.get("warnings") if isinstance(audit_report.get("warnings"), list) else [])
    if warning_count:
        hotspots.append({"risk": "audit_warnings", "count": warning_count, "severity": "warning"})
    manual_count = sum(1 for item in entries if item.get("risk") == "manual_required")
    if manual_count:
        hotspots.append({"risk": "manual_required_actions", "count": manual_count, "severity": "info"})
    return hotspots


def _manual_action_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    manual = [item for item in entries if item.get("risk") == "manual_required"]
    return {"count": len(manual), "event_types": sorted({str(item.get("event_type") or "") for item in manual})}


def _verifier_outcomes(audit_report: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    verifier_entries = [item for item in entries if str(item.get("event_type") or "").endswith("_verified") or str(item.get("event_type") or "").startswith("package_verifier_")]
    failed = [item for item in verifier_entries if (item.get("evidence_ref") or {}).get("integrity_ok") is False]
    return {"count": len(verifier_entries), "failed_count": len(failed), "audit_package_verifier_summary": audit_report.get("package_verifiers") if isinstance(audit_report.get("package_verifiers"), dict) else {}}


def _change_request_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    change_entries = [item for item in entries if item.get("domain") == "operations_change_request"]
    applied = [item for item in change_entries if item.get("event_type") == "operations_change_request_applied"]
    return {"count": len(change_entries), "applied_count": len(applied), "event_types": sorted({str(item.get("event_type") or "") for item in change_entries})}


def _recommendations(stage_durations: list[dict[str, Any]], hotspots: list[dict[str, Any]], manual_summary: dict[str, Any], change_summary: dict[str, Any], verifier_outcomes: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if any(item.get("duration_status") == "unknown" for item in stage_durations):
        rows.append({"recommendation": "Add or preserve event timestamps so Operations retrospective durations can be computed.", "category": "observability"})
    if int(manual_summary.get("count") or 0) > 3:
        rows.append({"recommendation": "Review manual-required Operations steps and document why they cannot be automated safely.", "category": "process"})
    if int(change_summary.get("applied_count") or 0) > 0:
        rows.append({"recommendation": "Review applied Change Requests to identify checks that should happen before Operations Signoff.", "category": "change_control"})
    if int(verifier_outcomes.get("failed_count") or 0) > 0:
        rows.append({"recommendation": "Fix failed verifier evidence before using the Reviewer Pack externally.", "category": "verification"})
    if any(item.get("risk") == "audit_warnings" for item in hotspots):
        rows.append({"recommendation": "Review audit warnings with the external reviewer instead of treating the pack as warning-free.", "category": "review"})
    return rows


def _first_time(timeline: list[dict[str, Any]], event_types: set[str]) -> str | None:
    for item in timeline:
        if item.get("event_type") in event_types:
            return str(item.get("occurred_at") or "") or None
    return None


def _duration_seconds(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        left = datetime.fromisoformat(start.replace("Z", "+00:00"))
        right = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((right - left).total_seconds()))
