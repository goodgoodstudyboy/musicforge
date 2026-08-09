from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document

import json
import re
from pathlib import Path
from typing import Any

from song_agent.domains.creation.planning_rule_projections import governance_projection, planning_rule_impact_projection, planning_simulation_projection
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.studio.projectio import read_json


PLANNING_RULE_SIMULATION_ROOT = Path(".musicforge") / "planning-rule-simulations"
PLANNING_RULE_GOVERNANCE_ROOT = Path(".musicforge") / "planning-rule-governance"
PLANNING_RULE_IMPACT_ROOT = Path(".musicforge") / "planning-rule-impact"
FIX_PLAN_ROOT = Path(".musicforge") / "fix-plans"


def collect_planning_rule_simulation_summary(project_id: str) -> dict[str, Any]:
    rows = _read_rows(PLANNING_RULE_SIMULATION_ROOT / "simulations", "afpsim-*/simulation-report.json")
    matches = [row for row in rows if _simulation_matches_project(row, project_id) and row.get("status") != "archived"]
    if not matches:
        return {"status": "missing"}
    return planning_simulation_projection(_latest(matches))


def collect_planning_rule_governance_summary(project_id: str) -> dict[str, Any]:
    active = _read_optional(PLANNING_RULE_GOVERNANCE_ROOT / "active.json")
    version_id = str(active.get("active_version_id") or "")
    if not version_id:
        return {"status": "missing", "governance_status": "legacy_default", "active_version_id": None}
    version = _read_optional(PLANNING_RULE_GOVERNANCE_ROOT / "versions" / version_id / "version.json")
    summary = governance_projection(version, active=active, evidence_stale=_governance_evidence_stale(version))
    used: dict[str, int] = {}
    for plan in _read_rows(FIX_PLAN_ROOT, "afp-*/fix-plan.json"):
        if plan.get("status") == "archived" or not _plan_matches_project(plan, project_id):
            continue
        source = _as_document(plan.get("source"))
        governance = _as_document(source.get("planning_rule_governance"))
        used_id = str(governance.get("planning_rule_version_id") or governance.get("version_id") or "legacy_default")
        used[used_id] = used.get(used_id, 0) + 1
    summary["used_rule_versions"] = [
        {"version_id": key, "plan_count": value}
        for key, value in sorted(used.items())
    ]
    return sanitize_metadata(summary)


def collect_planning_rule_impact_summary(project_id: str) -> dict[str, Any]:
    safe_project_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", project_id)
    direct = _read_optional(PLANNING_RULE_IMPACT_ROOT / f"latest-project-{safe_project_id}.json")
    if direct and _impact_matches_project(direct, project_id):
        return planning_rule_impact_projection(direct)
    rows = _read_rows(PLANNING_RULE_IMPACT_ROOT / "reports", "prgir-*/report.json")
    matches = [row for row in rows if row.get("status") != "archived" and _impact_matches_project(row, project_id)]
    if not matches:
        return {"status": "missing"}
    return planning_rule_impact_projection(_latest(matches))


def _read_rows(root: Path, pattern: str) -> list[ImplementationDocument]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for path in root.glob(pattern):
        try:
            row = read_json(path)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _read_optional(path: Path) -> ImplementationDocument:
    try:
        value = read_json(path)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return _as_document(value)


def _latest(rows: list[ImplementationDocument]) -> ImplementationDocument:
    return max(rows, key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""))


def _simulation_matches_project(report: ImplementationDocument, project_id: str) -> bool:
    scope = _as_document(report.get("scope"))
    if scope.get("project_id") == project_id:
        return True
    for review in report.get("review_results", []) if isinstance(report.get("review_results"), list) else []:
        for item in review.get("item_results", []) if isinstance(review, dict) and isinstance(review.get("item_results"), list) else []:
            target = item.get("target") if isinstance(item, dict) and isinstance(item.get("target"), dict) else {}
            if _as_document(target).get("project_id") == project_id:
                return True
    return False


def _plan_matches_project(plan: ImplementationDocument, project_id: str) -> bool:
    scope = _as_document(plan.get("scope"))
    if scope.get("project_id") == project_id:
        return True
    for item in plan.get("planned_items", []) if isinstance(plan.get("planned_items"), list) else []:
        target = item.get("target") if isinstance(item, dict) and isinstance(item.get("target"), dict) else {}
        if _as_document(target).get("project_id") == project_id:
            return True
    return False


def _impact_matches_project(report: ImplementationDocument, project_id: str) -> bool:
    scope = _as_document(report.get("scope"))
    if scope.get("project_id") == project_id:
        return True
    for sample in report.get("plan_samples", []) if isinstance(report.get("plan_samples"), list) else []:
        ids = sample.get("project_ids", []) if isinstance(sample, dict) and isinstance(sample.get("project_ids"), list) else []
        if project_id in {str(value) for value in ids}:
            return True
    return False


def _governance_evidence_stale(version: ImplementationDocument) -> bool:
    promoted = _as_document(version.get("promoted_from"))
    simulation_id = str(promoted.get("simulation_id") or "")
    if not simulation_id:
        return True
    simulation = _read_optional(
        PLANNING_RULE_SIMULATION_ROOT / "simulations" / simulation_id / "simulation-report.json"
    )
    if not simulation:
        return True
    source = _as_document(simulation.get("source"))
    return (
        simulation.get("status") not in {"ready", "warning"}
        or str(source.get("source_hash") or "") != str(promoted.get("simulation_source_hash") or "")
    )
