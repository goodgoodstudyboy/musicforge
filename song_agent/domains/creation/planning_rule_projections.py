from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document

from typing import Any

from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.platform.verification.hashing import stable_hash


IMPACT_REPORT_INTEGRITY_FIELDS = (
    "status",
    "scope",
    "active_version",
    "source",
    "summary",
    "adoption",
    "before_after",
    "risk_drift",
    "version_metrics",
    "plan_samples",
    "review_samples",
    "warnings",
)


def planning_simulation_projection(report: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    source = _as_document(data.get("source"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "simulation_id": data.get("simulation_id"),
            "ruleset_id": data.get("ruleset_id"),
            "scope": _as_document(data.get("scope")),
            "review_count": summary.get("review_count", 0),
            "item_count": summary.get("item_count", 0),
            "baseline_alignment_score": summary.get("baseline_alignment_score"),
            "simulated_alignment_score": summary.get("simulated_alignment_score"),
            "alignment_delta": summary.get("alignment_delta"),
            "recommendation": summary.get("recommendation") or "missing",
            "synthetic_penalty_applied_count": summary.get("synthetic_penalty_applied_count", 0),
            "waiver_penalty_applied_count": summary.get("waiver_penalty_applied_count", 0),
            "stale": data.get("status") == "stale" or bool(summary.get("stale", False)),
            "source_hash": source.get("source_hash"),
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
        }
    )


def governance_projection(
    version: dict[str, Any] | None,
    *,
    active: dict[str, Any] | None = None,
    evidence_stale: bool = False,
) -> dict[str, Any]:
    data = _as_document(version)
    if not data:
        return {"status": "missing", "governance_status": "legacy_default", "active_version_id": None}
    promoted = _as_document(data.get("promoted_from"))
    active = _as_document(active)
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "governance_status": data.get("status") or "missing",
            "active_version_id": data.get("version_id") if data.get("status") == "active" else active.get("active_version_id") or data.get("version_id"),
            "version_id": data.get("version_id"),
            "ruleset_id": data.get("ruleset_id"),
            "ruleset_hash": data.get("ruleset_hash"),
            "ruleset_name": data.get("ruleset_name"),
            "promotion_id": promoted.get("promotion_id"),
            "promoted_from_simulation_id": promoted.get("simulation_id"),
            "simulation_id": promoted.get("simulation_id"),
            "recommendation": promoted.get("recommendation"),
            "alignment_delta": promoted.get("alignment_delta"),
            "review_count": promoted.get("review_count", 0),
            "item_count": promoted.get("item_count", 0),
            "activated_at": active.get("activated_at") or data.get("created_at"),
            "activated_by": active.get("activated_by") or data.get("created_by"),
            "evidence_stale": bool(evidence_stale),
            "stale": bool(evidence_stale),
            "source_hash": data.get("source_hash"),
        }
    )


def planning_rule_impact_hash(report: dict[str, Any] | None) -> str:
    data = _as_document(report)
    return stable_hash({key: data.get(key) for key in IMPACT_REPORT_INTEGRITY_FIELDS})


def planning_rule_impact_projection(report: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    risk = _as_document(data.get("risk_drift"))
    integrity_hash = str(data.get("integrity_hash") or data.get("report_hash") or "")
    return sanitize_metadata(
        {
            "status": data.get("status") or summary.get("status") or "missing",
            "report_id": data.get("report_id") or summary.get("report_id"),
            "active_version_id": summary.get("active_version_id"),
            "observed_plan_count": summary.get("observed_plan_count", 0),
            "observed_review_count": summary.get("observed_review_count", 0),
            "manual_review_count": summary.get("manual_review_count", 0),
            "synthetic_review_count": summary.get("synthetic_review_count", 0),
            "adoption_status": summary.get("adoption_status"),
            "effectiveness_delta": summary.get("effectiveness_delta"),
            "ranking_alignment_delta": summary.get("ranking_alignment_delta"),
            "recommendation": summary.get("recommendation") or "missing",
            "rollback_recommended": bool(summary.get("rollback_recommended", False)),
            "readiness_status": summary.get("readiness_status"),
            "synthetic_only_rate": risk.get("synthetic_only_rate"),
            "waiver_rate": risk.get("waiver_rate"),
            "force_close_rate": risk.get("force_close_rate"),
            "stale": data.get("status") == "stale" or bool(summary.get("stale", False)),
            "warnings": data.get("warnings", []) if isinstance(data.get("warnings"), list) else [],
            "source_hash": (_as_document(data.get("source"))).get("source_hash"),
            "integrity_hash": integrity_hash,
            "integrity_ok": bool(integrity_hash and integrity_hash == planning_rule_impact_hash(data)),
        }
    )
