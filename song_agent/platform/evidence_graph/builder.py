from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.evidence import EvidenceRef
from song_agent.platform.evidence_graph.model import EvidenceEdge, EvidenceGraph, EvidenceNode
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok, sha256_file, stable_hash


EVIDENCE_GRAPH_MANIFEST_PACKAGE_TYPE = "musicforge_evidence_graph_manifest"
ALLOWED_EDGE_RELATIONS = {
    "depends_on",
    "supersedes",
    "verifies",
    "signed_by",
    "reset_by",
    "derived_from",
    "delivers_to",
}


class EvidenceGraphBuildError(RuntimeError):
    pass


def write_evidence_graph_manifest(
    path: Path | str,
    *,
    items: list[dict[str, Any]],
    edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    document = json.loads(json.dumps({
        "schema_version": 1,
        "package_type": EVIDENCE_GRAPH_MANIFEST_PACKAGE_TYPE,
        "items": items,
        "edges": edges or [],
    }, ensure_ascii=False, default=str))
    document["integrity_hash"] = integrity_hash(document)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return document


def build_evidence_graph(
    manifest_path: Path | str,
    *,
    registry: Any | None = None,
    allowed_root: Path | str | None = None,
) -> EvidenceGraph:
    target = Path(manifest_path)
    manifest = _read_evidence_manifest(target)
    if registry is None:
        raise EvidenceGraphBuildError("Evidence graph construction requires an explicit capability registry.")
    graph_blockers = _manifest_blockers(manifest)
    raw_items = manifest.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        graph_blockers.append("evidence_manifest_items_required")
        raw_items = []
    nodes = _build_nodes(
        raw_items,
        root=target.parent,
        allowed_root=Path(allowed_root).resolve() if allowed_root is not None else None,
        registry=registry,
        blockers=graph_blockers,
    )
    return _finalize_graph(manifest, nodes, graph_blockers)


def _read_evidence_manifest(target: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceGraphBuildError(f"Evidence manifest could not be read: {exc}") from exc
    if not isinstance(manifest, dict):
        raise EvidenceGraphBuildError("Evidence manifest must be a JSON object.")
    return manifest


def _manifest_blockers(manifest: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if manifest.get("package_type") != EVIDENCE_GRAPH_MANIFEST_PACKAGE_TYPE:
        blockers.append("evidence_manifest_package_type")
    if not integrity_ok(manifest):
        blockers.append("evidence_manifest_integrity")
    return blockers


def _build_nodes(
    raw_items: list[Any],
    *,
    root: Path,
    allowed_root: Path | None,
    registry: Any,
    blockers: list[str],
) -> list[EvidenceNode]:
    nodes: list[EvidenceNode] = []
    seen_identities: set[tuple[str, str, str, int]] = set()
    seen_node_ids: set[str] = set()
    report_owners: dict[str, tuple[str, str, str, int]] = {}
    report_hash_owners: dict[str, tuple[str, str, str, int]] = {}
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            blockers.append(f"evidence_manifest_item_{index}_object")
            continue
        node = _build_node(raw, root=root, allowed_root=allowed_root, registry=registry)
        identity = node.ref.identity
        claimed_identity = _claimed_identity(raw)
        if identity in seen_identities:
            blockers.append(f"evidence_identity_duplicate:{node.node_id}")
        seen_identities.add(identity)
        if node.node_id in seen_node_ids:
            blockers.append(f"evidence_node_id_duplicate:{node.node_id}")
        seen_node_ids.add(node.node_id)
        report_locator = str(raw.get("verification_report_path") or raw.get("verification_report") or "")
        if report_locator:
            resolved_locator = str(_resolve_path(root, report_locator)).casefold()
            owner = report_owners.setdefault(resolved_locator, claimed_identity)
            if owner != claimed_identity:
                blockers.append(f"evidence_report_reused:{node.node_id}")
        if node.ref.verification_report_hash:
            owner = report_hash_owners.setdefault(node.ref.verification_report_hash, claimed_identity)
            if owner != claimed_identity:
                blockers.append(f"evidence_report_hash_reused:{node.node_id}")
        nodes.append(node)
    return nodes


def _finalize_graph(manifest: dict[str, Any], nodes: list[EvidenceNode], blockers: list[str]) -> EvidenceGraph:
    edges = _build_edges(manifest, nodes, blockers)
    node_ids = {node.node_id for node in nodes}
    for node in nodes:
        for dependency in node.dependencies:
            if dependency not in node_ids:
                blockers.append(f"evidence_dependency_missing:{node.node_id}:{dependency}")
            else:
                edges.append(EvidenceEdge(source=node.node_id, target=dependency, relation="depends_on"))
    unique_edges = {(edge.source, edge.target, edge.relation): edge for edge in edges}
    if _dependency_cycle(tuple(unique_edges.values())):
        blockers.append("evidence_dependency_cycle")
    return EvidenceGraph(
        nodes=tuple(nodes),
        edges=tuple(unique_edges[key] for key in sorted(unique_edges)),
        blockers=tuple(sorted(set(blockers))),
    )


def _build_node(
    row: dict[str, Any],
    *,
    root: Path,
    allowed_root: Path | None,
    registry: Any,
) -> EvidenceNode:
    component_type, component_id, evidence_type, generation, node_id, blockers = _node_identity(row)
    warnings: list[str] = []
    capability = registry.resolve_component(component_type)
    package_path = _path_from_row(root, row, "package_path", "package", "zip_path", "zip", allowed_root=allowed_root)
    report_path = _path_from_row(root, row, "verification_report_path", "verification_report", allowed_root=allowed_root)
    if capability is None:
        blockers.append("evidence_capability_unknown")
        return _failed_node(
            node_id, component_type, component_id, evidence_type, generation, blockers,
            dependencies=_dependencies(row),
        )
    _check_capability_metadata(capability, blockers)
    if package_path is None or not package_path.is_file():
        blockers.append("evidence_package_missing")
    if report_path is None or not report_path.is_file():
        blockers.append("evidence_verification_report_missing")
    spec = capability.runtime
    external_report = _read_external_report(report_path, spec.verification_package_type, blockers)
    resolved_proofs = _resolve_proofs(row, root, allowed_root, spec, blockers)
    runtime = _run_runtime(package_path, resolved_proofs, spec, blockers)
    runtime_status = _text(runtime.get("status")) or "failed"
    runtime_identity = spec.extract_identity(runtime, component_type=capability.component_type)
    report_identity = spec.extract_identity(external_report, component_type=capability.component_type)
    manifest_identity = _manifest_identity(
        row, canonical_component_type=capability.component_type, package_type=spec.package_type
    )
    blockers.extend(_identity_blockers(manifest_identity, runtime_identity, report_identity))
    canonical_component_id = _text(runtime_identity.get("component_id")) or component_id
    canonical_generation = _positive_int(runtime_identity.get("generation"), default=generation)
    canonical_node_id = _node_id(capability.component_type, canonical_component_id, evidence_type, canonical_generation)
    if canonical_node_id != node_id:
        blockers.append("evidence_node_identity_runtime")
    node_id = canonical_node_id
    actual_zip_hash, actual_zip_size, runtime_fp, report_fp = _validate_bindings(
        row, package_path, runtime, external_report, blockers
    )
    _append_runtime_diagnostics(runtime, blockers, warnings)
    current = runtime_status == "passed" and runtime_identity.get("current") is True and not blockers
    ref = EvidenceRef(
        component_type=capability.component_type,
        component_id=canonical_component_id,
        evidence_type=evidence_type,
        generation=canonical_generation,
        package_type=spec.package_type,
        zip_sha256=str(actual_zip_hash or ""),
        zip_size_bytes=actual_zip_size,
        manifest_hash=str(runtime_fp["manifest_hash"] or ""),
        verification_report_hash=str(external_report.get("integrity_hash") or ""),
        source_hash=str(runtime_fp["source_hash"] or report_fp["source_hash"] or ""),
        signoff_hash=_proof_hash(resolved_proofs.get("signoff_binding")),
    )
    return EvidenceNode(
        node_id=node_id,
        ref=ref,
        capability_id=capability.capability_id,
        report_status=_text(external_report.get("status")) or "missing",
        runtime_status=runtime_status,
        current=current,
        lifecycle_status=_lifecycle_status(runtime),
        blockers=tuple(sorted(set(blockers))),
        warnings=tuple(sorted(set(warnings))),
        dependencies=_dependencies(row),
        runtime_summary={**_public_runtime_summary(runtime), "identity": runtime_identity},
    )


def _check_capability_metadata(capability: Any, blockers: list[str]) -> None:
    metadata = (
        capability.cli_commands,
        capability.api_routes,
        capability.web_panel,
        capability.release_checks,
        capability.gate_policies,
    )
    if not all(metadata):
        blockers.append("evidence_capability_metadata_incomplete")


def _node_identity(row: dict[str, Any]) -> tuple[str, str, str, int, str, list[str]]:
    component_type = _text(row.get("component_type"))
    component_id = _text(row.get("component_id"))
    evidence_type = _text(row.get("evidence_type")) or "package"
    try:
        generation = max(1, int(row.get("generation") or 1))
    except (TypeError, ValueError):
        generation = 1
    node_id = _node_id(component_type, component_id, evidence_type, generation)
    blockers = [] if component_type and component_id else ["evidence_identity_required"]
    provided = _text(row.get("node_id"))
    if provided and provided != node_id:
        blockers.append("evidence_node_id_identity")
    return component_type, component_id, evidence_type, generation, node_id, blockers


def _claimed_identity(row: dict[str, Any]) -> tuple[str, str, str, int]:
    component_type, component_id, evidence_type, generation, _node, _blockers = _node_identity(row)
    return component_type, component_id, evidence_type, generation


def _manifest_identity(
    row: dict[str, Any],
    *,
    canonical_component_type: str,
    package_type: str,
) -> dict[str, Any]:
    generation = _positive_int(row.get("generation"), default=1)
    current_generation = _positive_int(row.get("current_generation"), default=generation)
    return {
        "component_type": canonical_component_type,
        "component_id": _text(row.get("component_id")),
        "generation": generation,
        "current_generation": current_generation,
        "current": row.get("current", True) is True,
        "package_type": _text(row.get("package_type")) or package_type,
        "source_hash": _text(row.get("source_hash")),
    }


def _identity_blockers(
    manifest: dict[str, Any],
    runtime: dict[str, Any],
    external: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    required_fields = ("component_type", "component_id", "generation", "current_generation", "package_type", "source_hash")
    for owner, identity in (("runtime", runtime), ("external", external)):
        for field in required_fields:
            if identity.get(field) in (None, "", 0):
                blockers.append(f"evidence_{owner}_identity_{field}_required")
    for field in ("component_type", "component_id", "generation", "current_generation", "current", "package_type"):
        if manifest.get(field) != runtime.get(field):
            blockers.append(f"evidence_manifest_identity_{field}")
        if external.get(field) != runtime.get(field):
            blockers.append(f"evidence_external_identity_{field}")
    if manifest.get("source_hash") and manifest.get("source_hash") != runtime.get("source_hash"):
        blockers.append("evidence_manifest_identity_source_hash")
    if external.get("source_hash") != runtime.get("source_hash"):
        blockers.append("evidence_external_identity_source_hash")
    return blockers


def _read_external_report(path: Path | None, package_type: str, blockers: list[str]) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        report = value if isinstance(value, dict) else {}
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        blockers.append("evidence_verification_report_readable")
        return {}
    if report.get("package_type") != package_type:
        blockers.append("evidence_verification_package_type")
    if not integrity_ok(report):
        blockers.append("evidence_verification_report_integrity")
    if report.get("status") != "passed":
        blockers.append("evidence_verification_report_status")
    return report


def _resolve_proofs(row: dict[str, Any], root: Path, allowed_root: Path | None, spec: Any, blockers: list[str]) -> dict[str, Path]:
    proof_value = row.get("proofs")
    proofs: dict[str, Any] = proof_value if isinstance(proof_value, dict) else {}
    resolved: dict[str, Path] = {}
    for key, _argument in spec.proof_arguments:
        raw_path = proofs.get(key) or row.get(key)
        if raw_path:
            resolved[key] = _resolve_path(root, str(raw_path), allowed_root=allowed_root)
    for key in spec.required_proofs:
        if key not in resolved or not resolved[key].exists():
            blockers.append(f"evidence_proof_missing:{key}")
    return resolved


def _run_runtime(package_path: Path | None, proofs: dict[str, Path], spec: Any, blockers: list[str]) -> dict[str, Any]:
    runtime: dict[str, Any] = {}
    if package_path is not None and package_path.is_file() and not any(item.startswith("evidence_proof_missing:") for item in blockers):
        kwargs = dict(spec.defaults)
        kwargs.update({argument: proofs[key] for key, argument in spec.proof_arguments if key in proofs})
        try:
            runtime = spec.verifier()(package_path, **kwargs)
        except Exception as exc:
            runtime = {"status": "failed", "blockers": ["runtime_verifier_exception"], "error": type(exc).__name__}
    if runtime.get("status") != "passed":
        blockers.append("evidence_runtime_verification")
    if runtime and runtime.get("package_type") != spec.verification_package_type:
        blockers.append("evidence_runtime_package_type")
    return runtime


def _validate_bindings(
    row: dict[str, Any],
    package_path: Path | None,
    runtime: dict[str, Any],
    report: dict[str, Any],
    blockers: list[str],
) -> tuple[str | None, int, dict[str, Any], dict[str, Any]]:
    actual_hash = sha256_file(package_path) if package_path is not None and package_path.is_file() else None
    actual_size = package_path.stat().st_size if package_path is not None and package_path.is_file() else 0
    runtime_fp = _verification_fingerprint(runtime)
    report_fp = _verification_fingerprint(report)
    comparisons = {
        "evidence_verification_zip_sha256": report_fp["zip_sha256"] == actual_hash and bool(report_fp["zip_sha256"]),
        "evidence_verification_zip_size": report_fp["zip_size_bytes"] == actual_size and bool(report_fp["zip_size_bytes"]),
        "evidence_runtime_zip_sha256": runtime_fp["zip_sha256"] == actual_hash and bool(runtime_fp["zip_sha256"]),
        "evidence_verification_manifest_hash": report_fp["manifest_hash"] == runtime_fp["manifest_hash"] and bool(runtime_fp["manifest_hash"]),
    }
    blockers.extend(check_id for check_id, valid in comparisons.items() if not valid)
    expected_fields = {
        "zip_sha256": actual_hash,
        "zip_size_bytes": actual_size,
        "manifest_hash": runtime_fp["manifest_hash"],
        "verification_report_hash": report.get("integrity_hash"),
    }
    blockers.extend(
        f"evidence_manifest_{key}"
        for key, actual in expected_fields.items()
        if row.get(key) not in (None, "") and row.get(key) != actual
    )
    return actual_hash, actual_size, runtime_fp, report_fp


def _append_runtime_diagnostics(runtime: dict[str, Any], blockers: list[str], warnings: list[str]) -> None:
    blocker_value = runtime.get("blockers")
    runtime_blockers: list[Any] = blocker_value if isinstance(blocker_value, list) else []
    blockers.extend(f"runtime:{item}" for item in runtime_blockers if item)
    warning_value = runtime.get("warnings")
    runtime_warnings: list[Any] = warning_value if isinstance(warning_value, list) else []
    warnings.extend(f"runtime:{item}" for item in runtime_warnings if item)


def _failed_node(
    node_id: str,
    component_type: str,
    component_id: str,
    evidence_type: str,
    generation: int,
    blockers: list[str],
    *,
    dependencies: tuple[str, ...],
) -> EvidenceNode:
    return EvidenceNode(
        node_id=node_id,
        ref=EvidenceRef(component_type=component_type, component_id=component_id, evidence_type=evidence_type, generation=generation),
        capability_id="unknown",
        report_status="missing",
        runtime_status="failed",
        current=False,
        blockers=tuple(sorted(set(blockers))),
        dependencies=dependencies,
    )


def _build_edges(manifest: dict[str, Any], nodes: list[EvidenceNode], blockers: list[str]) -> list[EvidenceEdge]:
    node_ids = {node.node_id for node in nodes}
    result: list[EvidenceEdge] = []
    edge_value = manifest.get("edges")
    raw_edges: list[Any] = edge_value if isinstance(edge_value, list) else []
    for index, raw in enumerate(raw_edges):
        if not isinstance(raw, dict):
            blockers.append(f"evidence_edge_{index}_object")
            continue
        source = _text(raw.get("source"))
        target = _text(raw.get("target"))
        relation = _text(raw.get("relation"))
        if source not in node_ids or target not in node_ids:
            blockers.append(f"evidence_edge_{index}_identity")
        elif relation not in ALLOWED_EDGE_RELATIONS:
            blockers.append(f"evidence_edge_{index}_relation")
        else:
            result.append(EvidenceEdge(source=source, target=target, relation=relation))
    return result


def _dependency_cycle(edges: tuple[EvidenceEdge, ...]) -> bool:
    graph: dict[str, set[str]] = {}
    for edge in edges:
        if edge.relation == "depends_on":
            graph.setdefault(edge.source, set()).add(edge.target)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(target) for target in graph.get(node, ())):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _verification_fingerprint(report: dict[str, Any]) -> dict[str, Any]:
    summary_value = report.get("summary")
    summary: dict[str, Any] = summary_value if isinstance(summary_value, dict) else {}
    verification_value = summary.get("verification")
    verification: dict[str, Any] = verification_value if isinstance(verification_value, dict) else {}
    return {
        "zip_sha256": report.get("zip_sha256") or summary.get("zip_sha256") or verification.get("zip_sha256"),
        "zip_size_bytes": report.get("zip_size_bytes") or summary.get("zip_size_bytes") or verification.get("zip_size_bytes"),
        "manifest_hash": report.get("manifest_hash") or summary.get("manifest_hash") or verification.get("manifest_hash"),
        "source_hash": report.get("source_hash") or summary.get("source_hash") or verification.get("source_hash"),
    }


def _public_runtime_summary(report: dict[str, Any]) -> dict[str, Any]:
    summary_value = report.get("summary")
    summary: dict[str, Any] = summary_value if isinstance(summary_value, dict) else {}
    allowed = {
        "status",
        "readiness",
        "component_id",
        "release_id",
        "program_id",
        "generation",
        "current_generation",
        "signoff_status",
        "blocker_count",
        "warning_count",
        "track_count",
        "item_count",
    }
    return {key: value for key, value in summary.items() if key in allowed and isinstance(value, (str, int, float, bool, type(None)))}


def _lifecycle_status(report: dict[str, Any]) -> str:
    summary_value = report.get("summary")
    summary: dict[str, Any] = summary_value if isinstance(summary_value, dict) else {}
    for key in ("signoff_status", "lifecycle_status", "readiness", "status"):
        value = summary.get(key)
        if isinstance(value, str) and value:
            return value
    return "verified" if report.get("status") == "passed" else "failed"


def _dependencies(row: dict[str, Any]) -> tuple[str, ...]:
    dependency_value = row.get("dependencies")
    values: list[Any] = dependency_value if isinstance(dependency_value, list) else []
    return tuple(sorted({_text(value) for value in values if _text(value)}))


def _node_id(component_type: str, component_id: str, evidence_type: str, generation: int) -> str:
    return f"{component_type}:{component_id}:{evidence_type}:{generation}"


def _path_from_row(root: Path, row: dict[str, Any], *keys: str, allowed_root: Path | None = None) -> Path | None:
    for key in keys:
        value = row.get(key)
        if value:
            return _resolve_path(root, str(value), allowed_root=allowed_root)
    return None


def _resolve_path(root: Path, value: str, *, allowed_root: Path | None = None) -> Path:
    target = Path(value)
    resolved = (target if target.is_absolute() else root / target).resolve()
    if allowed_root is not None:
        try:
            resolved.relative_to(allowed_root)
        except ValueError as exc:
            raise EvidenceGraphBuildError("Evidence manifest references a path outside the allowed workspace.") from exc
    return resolved


def _proof_hash(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return str(sha256_file(path) or "")
    if isinstance(value, dict) and value.get("integrity_hash"):
        return str(value["integrity_hash"])
    return stable_hash(value)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default
