from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import re
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json
from song_agent.platform.verification.hashing import stable_hash


FIX_PLAN_ROOT = Path(".musicforge") / "fix-plans"
ACCEPTANCE_KB_ROOT = Path(".musicforge") / "acceptance-kb"
PLAN_ID_PATTERN = re.compile(r"^afp-[0-9]{6}$")
ENTRY_ID_PATTERN = re.compile(r"^akb-[0-9]{6}$")


def current_fix_plan_state(plan_id: str, *, analytics_store: Any) -> DomainDocument:
    if not PLAN_ID_PATTERN.fullmatch(plan_id):
        return {"plan": {}, "stale": True, "reasons": ["invalid_plan_id"]}
    plan = _read_optional(FIX_PLAN_ROOT / plan_id / "fix-plan.json")
    if not plan:
        return {"plan": {}, "stale": True, "reasons": ["missing_plan"]}
    reasons: list[str] = []
    if plan.get("status") in {"archived", "stale"}:
        reasons.append("plan_status")
    source = _as_document(plan.get("source"))
    try:
        analytics = analytics_store.get_report(str(source.get("analytics_report_id") or ""))
    except Exception:
        analytics = {}
    if not analytics or analytics.get("stale") is True:
        reasons.append("analytics_stale")
    elif str(analytics.get("source_hash") or "") != str(source.get("analytics_source_hash") or ""):
        reasons.append("analytics_source_hash")
    recommendations = {
        str(item.get("recommendation_id") or ""): item
        for item in analytics.get("recommendations", [])
        if isinstance(item, dict)
    }
    expected_recommendations = _as_document(source.get("recommendation_hashes"))
    for recommendation_id, expected_hash in expected_recommendations.items():
        if recommendation_id not in recommendations or stable_hash(recommendations[recommendation_id]) != expected_hash:
            reasons.append(f"recommendation:{recommendation_id}")
    expected_entries = _as_document(source.get("kb_entry_hashes"))
    for entry_id, expected_hash in expected_entries.items():
        if not ENTRY_ID_PATTERN.fullmatch(str(entry_id)):
            reasons.append(f"kb_entry:{entry_id}")
            continue
        entry = _read_optional(ACCEPTANCE_KB_ROOT / "entries" / f"{entry_id}.json")
        if not entry or stable_hash(_entry_plan_summary(entry)) != expected_hash:
            reasons.append(f"kb_entry:{entry_id}")
    return {"plan": plan, "stale": bool(reasons), "reasons": sorted(set(reasons))}


def _entry_plan_summary(entry: ImplementationDocument) -> ImplementationDocument:
    target = _as_document(entry.get("target"))
    outcome = _as_document(entry.get("outcome"))
    fix = _as_document(entry.get("fix"))
    source = _as_document(entry.get("source"))
    return {
        "entry_id": entry.get("entry_id"),
        "status": entry.get("status"),
        "fix_sprint_id": source.get("fix_sprint_id"),
        "project_id": target.get("project_id"),
        "release_id": target.get("release_id"),
        "song_id": target.get("song_id"),
        "style": target.get("style"),
        "issue_types": _as_list(target.get("issue_types")),
        "outcome_status": outcome.get("outcome_status"),
        "effectiveness_score": outcome.get("effectiveness_score"),
        "waived_count": fix.get("waived_count", 0),
        "warnings": _as_list(entry.get("warnings")),
        "source_fingerprint": source.get("source_fingerprint"),
    }


def _read_optional(path: Path) -> ImplementationDocument:
    try:
        value = read_json(path)
    except (OSError, TypeError, ValueError):
        return {}
    return _as_document(value)
