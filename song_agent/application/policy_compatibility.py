from __future__ import annotations

from typing import Any, Iterable

from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.contracts.policy import PolicyProfile
from song_agent.platform.evidence_graph.model import EvidenceGraph, EvidenceNode
from song_agent.platform.policy import evaluate_policy


_PASSING_STATES = {"passed", "ready", "signed", "closed", "current", "accepted", "not_required"}


def normalized_legacy_require_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        key: value for key, value in payload.items() if key.startswith("require_")
    }
    if not bool(normalized.get("require_unified_command_center_reviewer_decision_board")):
        normalized["require_unified_command_center_reviewer_decision_board_signed"] = False
        normalized["require_unified_command_center_reviewer_decision_board_quorum"] = False
    return normalized


def legacy_require_summary(payload: dict[str, Any], policy_id: str) -> dict[str, Any]:
    payload = normalized_legacy_require_payload(payload)
    enabled = sorted(
        key
        for key, value in payload.items()
        if key.startswith("require_") and bool(value)
    )
    return {
        "status": "converted" if enabled else "not_requested",
        "policy_id": policy_id,
        "enabled": enabled,
        "count": len(enabled),
        "authoritative": False,
    }


def canonical_release_policy_id(payload: dict[str, Any]) -> str:
    requested = str(payload.get("gate_policy") or payload.get("policy") or "").strip()
    if requested == "release.audio_strict":
        return "release.audio"
    if requested:
        return requested
    return "release.audio" if any(
        key.startswith("require_") and "audio" in key and bool(value)
        for key, value in payload.items()
    ) else "release.standard"


def canonical_ga_policy_id(requested: str | None, payload: dict[str, Any]) -> str:
    if requested:
        return str(requested)
    lts_terms = ("continuity", "receiver", "final_readiness", "trust_control", "assurance")
    return "ga.lts" if any(
        key.startswith("require_")
        and bool(value)
        and any(term in key for term in lts_terms)
        for key, value in payload.items()
    ) else "ga.standard"


def evaluate_legacy_release_policy(
    payload: dict[str, Any],
    acceptance_gate: dict[str, Any],
    *,
    release_id: str,
    qa_passed: bool,
) -> dict[str, Any]:
    policy_id = canonical_release_policy_id(payload)
    external = acceptance_gate.get("evidence_policy")
    if isinstance(external, dict):
        result = dict(external)
        result["policy_id"] = policy_id
        result["legacy_require_summary"] = legacy_require_summary(payload, policy_id)
        return result
    rows: list[tuple[str, dict[str, Any]]] = [
        ("release_qa", {"status": "passed" if qa_passed else "failed"})
    ]
    if acceptance_gate.get("status"):
        rows.append(
            (
                "legacy_required_gates",
                {
                    "status": acceptance_gate.get("status"),
                    "blockers": acceptance_gate.get("blockers") or ("release.legacy_required_gates",),
                },
            )
        )
    result = evaluate_gate_rows(policy_id, release_id, rows)
    result["legacy_require_summary"] = legacy_require_summary(payload, policy_id)
    return result


def evaluate_check_policy(
    policy_id: str,
    component_id: str,
    checks: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    rows = [
        (str(check.get("check_id") or "check"), check)
        for check in checks
        if check.get("severity") == "blocking"
    ]
    return evaluate_gate_rows(policy_id, component_id, rows or [("readiness", {"status": "passed"})])


def evaluate_gate_rows(
    policy_id: str,
    component_id: str,
    rows: Iterable[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    nodes = tuple(_gate_node(component_id, key, value) for key, value in rows)
    graph = EvidenceGraph(nodes=nodes, edges=())
    gate = evaluate_policy(PolicyProfile(policy_id=policy_id, description="Legacy gate facts projected into Policy Engine."), graph)
    return {
        "status": gate.status,
        "hard_block": gate.status != "passed",
        "policy_id": gate.policy_id,
        "graph_hash": gate.graph_hash,
        "blockers": list(gate.blockers),
        "warnings": list(gate.warnings),
        "checks": list(gate.checks),
        "graph": graph.to_dict(),
    }


def _gate_node(component_id: str, key: str, value: dict[str, Any]) -> EvidenceNode:
    status = str(value.get("status") or "failed").lower()
    passed = status in _PASSING_STATES
    blockers = () if passed else tuple(str(row) for row in value.get("blockers") or (f"legacy_gate.{key}",))
    return EvidenceNode(
        node_id=f"legacy:{component_id}:{key}",
        ref=EvidenceRef(
            component_type="legacy_gate_fact",
            component_id=component_id,
            evidence_type=key,
        ),
        capability_id="policy.compatibility",
        report_status="passed" if passed else "failed",
        runtime_status="passed" if passed else "failed",
        current=passed,
        blockers=blockers,
        runtime_summary={"legacy_status": status},
    )
