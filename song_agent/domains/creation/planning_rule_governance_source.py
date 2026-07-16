from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from pathlib import Path
from typing import Any

from song_agent.domains.creation.planning_rule_projections import governance_projection
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.studio.projectio import read_json
from song_agent.platform.verification.hashing import stable_hash


PLANNING_RULE_GOVERNANCE_ROOT = Path(".musicforge") / "planning-rule-governance"
PLANNING_RULE_SIMULATION_ROOT = Path(".musicforge") / "planning-rule-simulations"


def current_fix_plan_governance_source(
    root: Path | str = PLANNING_RULE_GOVERNANCE_ROOT,
) -> dict[str, Any]:
    root = Path(root)
    active = _read_optional(root / "active.json")
    version_id = str(active.get("active_version_id") or "")
    if not version_id:
        return legacy_fix_plan_governance_source()
    version = _read_optional(root / "versions" / version_id / "version.json")
    if not version:
        return legacy_fix_plan_governance_source()
    summary = governance_projection(
        version,
        active=active,
        evidence_stale=_version_evidence_stale(version, root=root),
    )
    return fix_plan_governance_projection(summary)


def fix_plan_governance_projection(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("status") == "missing" or summary.get("stale"):
        return legacy_fix_plan_governance_source()
    return sanitize_metadata(
        {
            "status": "active",
            "governance_status": "active",
            "generated_with_active_rules": True,
            "planning_rule_version_id": summary.get("active_version_id") or summary.get("version_id"),
            "version_id": summary.get("active_version_id") or summary.get("version_id"),
            "ruleset_id": summary.get("ruleset_id"),
            "ruleset_hash": summary.get("ruleset_hash"),
            "active_at": summary.get("activated_at"),
            "source": "planning_rule_governance",
        }
    )


def legacy_fix_plan_governance_source() -> dict[str, Any]:
    return {
        "status": "legacy_default",
        "governance_status": "legacy_default",
        "generated_with_active_rules": False,
        "planning_rule_version_id": None,
    }


def _version_evidence_stale(version: ImplementationDocument, *, root: Path) -> bool:
    promoted = version.get("promoted_from") if isinstance(version.get("promoted_from"), dict) else {}
    simulation_id = str(promoted.get("simulation_id") or "")
    if not simulation_id:
        return True
    simulation = _read_optional(
        PLANNING_RULE_SIMULATION_ROOT / "simulations" / simulation_id / "simulation-report.json"
    )
    if simulation.get("status") not in {"ready", "warning"}:
        return True
    source = simulation.get("source") if isinstance(simulation.get("source"), dict) else {}
    if str(source.get("source_hash") or "") != str(promoted.get("simulation_source_hash") or ""):
        return True
    frozen = _read_optional(
        root / "versions" / str(version.get("version_id") or "") / "ruleset-frozen.json"
    )
    return not frozen or stable_hash(frozen) != str(version.get("ruleset_hash") or "")


def _read_optional(path: Path) -> ImplementationDocument:
    try:
        value = read_json(path)
    except (OSError, TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}
