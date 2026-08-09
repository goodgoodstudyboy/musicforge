from __future__ import annotations

from song_agent.platform.contracts.policy import GateResult, PolicyProfile
from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document
from song_agent.platform.evidence_graph.model import EvidenceGraph, EvidenceNode


class PolicyEvaluationError(RuntimeError):
    pass


def evaluate_policy(profile: PolicyProfile, graph: EvidenceGraph) -> GateResult:
    checks: list[JsonDocument] = []
    blockers: list[str] = list(graph.blockers)
    warnings: list[str] = list(graph.warnings)

    _add_check(
        checks,
        "policy.graph.integrity",
        not graph.blockers,
        "Evidence graph manifest and identities are valid.",
        {"blockers": list(graph.blockers)},
    )
    _add_check(
        checks,
        "policy.graph.non_empty",
        bool(graph.nodes),
        "Evidence graph contains at least one runtime-verified node.",
        {"node_count": len(graph.nodes)},
    )
    if not graph.nodes:
        blockers.append("policy.graph.non_empty")

    # These requirements are platform invariants. Profiles cannot disable them.
    for node in graph.nodes:
        _hard_node_checks(node, checks, blockers)
        warnings.extend(f"{node.node_id}:{warning}" for warning in node.warnings)

    for requirement in profile.evidence_requirements:
        matches = [node for node in graph.nodes if _matches(node, requirement.component_types, requirement.evidence_types)]
        ready_matches = [node for node in matches if node.ready]
        passed = len(ready_matches) >= requirement.minimum_count
        check_id = f"policy.evidence.{requirement.requirement_id}"
        _add_check(
            checks,
            check_id,
            passed,
            requirement.description or f"Evidence requirement {requirement.requirement_id} is satisfied.",
            {
                "minimum_count": requirement.minimum_count,
                "matched_count": len(matches),
                "ready_count": len(ready_matches),
                "node_ids": [node.node_id for node in ready_matches],
            },
        )
        if not passed:
            blockers.append(check_id)

    for quorum in profile.quorum_requirements:
        candidates = [node for node in graph.nodes if not quorum.component_types or node.ref.component_type in quorum.component_types]
        ready_count = sum(1 for node in candidates if node.ready)
        passed = ready_count >= quorum.minimum_count
        check_id = f"policy.quorum.{quorum.requirement_id}"
        _add_check(
            checks,
            check_id,
            passed,
            quorum.description or f"Quorum requirement {quorum.requirement_id} is satisfied.",
            {"minimum_count": quorum.minimum_count, "ready_count": ready_count},
        )
        if not passed:
            blockers.append(check_id)

    dependencies_ready = all(
        graph.by_node_id().get(edge.target) is not None and graph.by_node_id()[edge.target].ready
        for edge in graph.edges
        if edge.relation == "depends_on"
    )
    _add_check(checks, "policy.dependencies.ready", dependencies_ready, "All declared dependencies are present and ready.")
    if not dependencies_ready:
        blockers.append("policy.dependencies.ready")

    blocker_tuple = tuple(sorted(set(blockers)))
    return GateResult(
        policy_id=profile.policy_id,
        status="failed" if blocker_tuple else "warning" if warnings else "passed",
        checks=tuple(checks),
        blockers=blocker_tuple,
        warnings=tuple(sorted(set(warnings))),
        graph_hash=graph.graph_hash,
    )


def _hard_node_checks(node: EvidenceNode, checks: list[JsonDocument], blockers: list[str]) -> None:
    values = (
        ("report", node.report_status == "passed", "External verification report is passed."),
        ("runtime", node.runtime_status == "passed", "Current package runtime verification is passed."),
        ("current", node.current, "Evidence is bound to the current verified generation."),
        ("blockers", not node.blockers, "Evidence node has no blockers."),
    )
    for suffix, passed, message in values:
        check_id = f"policy.node.{node.node_id}.{suffix}"
        _add_check(checks, check_id, passed, message, {"node_id": node.node_id, "blockers": list(node.blockers)})
        if not passed:
            blockers.append(check_id)


def _matches(node: EvidenceNode, component_types: tuple[str, ...], evidence_types: tuple[str, ...]) -> bool:
    return (
        (not component_types or node.ref.component_type in component_types)
        and (not evidence_types or node.ref.evidence_type in evidence_types)
    )


def _add_check(
    checks: list[JsonDocument],
    check_id: str,
    passed: bool,
    message: str,
    detail: JsonDocument | None = None,
) -> None:
    checks.append(normalize_json_document(
        {
            "check_id": check_id,
            "status": "passed" if passed else "failed",
            "severity": "blocking",
            "message": message,
            "detail": detail or {},
        }
    ))
