from __future__ import annotations

import re
from pathlib import Path

from song_agent.capabilities import capability_registry
from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.evidence_graph import build_evidence_graph
from song_agent.platform.policy import evaluate_policy, get_policy_profile


class EvidencePolicyGateError(RuntimeError):
    pass


def resolve_workspace_evidence_manifest(
    workspace: Path | str,
    *,
    manifest_id: str | None = None,
    manifest: str | Path | None = None,
) -> Path:
    root = Path(workspace).resolve()
    identifier = str(manifest_id or "").strip()
    if identifier:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", identifier):
            raise EvidencePolicyGateError("Invalid evidence_manifest_id.")
        target = root / "evidence-manifests" / f"{identifier}.json"
    elif manifest is not None and str(manifest).strip():
        candidate = Path(str(manifest))
        target = candidate if candidate.is_absolute() else root / candidate
    else:
        raise EvidencePolicyGateError("An evidence manifest reference is required.")
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise EvidencePolicyGateError("Evidence manifest must be stored inside the MusicForge workspace.") from exc
    return target


def evaluate_evidence_policy_gate(
    policy_id: str,
    manifest_path: Path | str,
    *,
    allowed_root: Path | str | None = None,
) -> JsonDocument:
    graph = build_evidence_graph(manifest_path, registry=capability_registry, allowed_root=allowed_root)
    gate = evaluate_policy(get_policy_profile(policy_id), graph)
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
