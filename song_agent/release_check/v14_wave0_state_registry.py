from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import cast

from song_agent.platform.persistence.repository import (
    check_state_path_overlaps,
    namespace_identity_hash,
    relative_state_path,
    resolve_runtime_state_roots,
    validate_runtime_state_composition,
    validate_runtime_state_namespaces,
    validated_overlap_exceptions,
)
from song_agent.release_check.v14_wave0_source import (
    SOURCE_EVIDENCE_SCHEMA_VERSION,
    source_fragment,
    source_fragment_hash,
    source_span,
)

__all__ = [
    "namespace_identity_hash",
    "namespace_path_evidence",
    "resolve_runtime_state_roots",
    "validate_runtime_state_composition",
    "validate_runtime_state_namespaces",
    "validate_state_registry",
]


ROOT_KINDS = {"filesystem", "database", "object_store"}
DISJOINTNESS_POLICIES = {"static", "runtime_required"}


def validate_state_registry(
    registry: dict[str, object],
    capability_ids: set[str],
    store_owners: dict[str, str],
    blockers: list[str],
    *,
    root: Path | None,
    baseline_integrity_hash: str | None = None,
) -> None:
    roots = cast(list[dict[str, object]], registry.get("roots") or [])
    root_rows = _unique_rows(roots, "root_authority_id", "root", blockers)
    for root_id, row in root_rows.items():
        if row.get("kind") not in ROOT_KINDS:
            blockers.append(f"v144_wave0_state_root_kind:{root_id}")
        for field in ("path_template", "composition_binding", "disjointness"):
            if not str(row.get(field) or "").strip():
                blockers.append(f"v144_wave0_state_root_field:{root_id}:{field}")
        if row.get("disjointness") not in DISJOINTNESS_POLICIES:
            blockers.append(f"v144_wave0_state_root_disjointness:{root_id}")
        if not isinstance(row.get("runtime_configurable"), bool):
            blockers.append(f"v144_wave0_state_root_runtime:{root_id}")
        if "Store" in root_id:
            blockers.append(f"v144_wave0_state_root_class_scoped:{root_id}")

    entries = cast(list[dict[str, object]], registry.get("entries") or [])
    _unique_rows(entries, "store_id", "state", blockers)
    writers: dict[str, list[tuple[str, PurePosixPath, str]]] = {}
    for row in entries:
        store_id = str(row.get("store_id") or "")
        capability_id = str(row.get("capability_id") or "")
        if capability_id not in capability_ids or store_owners.get(store_id) != capability_id:
            blockers.append(f"v144_wave0_state_capability:{store_id}")
        if row.get("role") not in {"authority", "projection", "workflow", "evidence", "adapter", "read_only"}:
            blockers.append(f"v144_wave0_state_role:{store_id}")
        for field in ("entity", "source", "generation_semantics"):
            if not str(row.get(field) or "").strip():
                blockers.append(f"v144_wave0_state_field:{store_id}:{field}")
        access = row.get("access")
        namespaces = row.get("physical_namespaces")
        if not isinstance(access, dict) or not isinstance(access.get("write"), bool):
            blockers.append(f"v144_wave0_state_access:{store_id}")
            continue
        if not isinstance(namespaces, list) or (access["write"] and not namespaces):
            blockers.append(f"v144_wave0_state_namespace:{store_id}")
            continue
        if not access["write"] and namespaces:
            blockers.append(f"v144_wave0_read_only_namespace:{store_id}")
        for namespace in namespaces:
            if not isinstance(namespace, dict):
                blockers.append(f"v144_wave0_state_namespace_shape:{store_id}")
                continue
            root_id = str(namespace.get("root_authority_id") or "")
            relative = relative_state_path(namespace.get("relative_path_template"))
            if root_id not in root_rows or relative is None:
                blockers.append(f"v144_wave0_state_namespace_value:{store_id}")
                continue
            _validate_path_evidence(
                store_id,
                str(row.get("source") or ""),
                namespace,
                blockers,
                root=root,
            )
            if access["write"]:
                writers.setdefault(root_id, []).append((store_id, relative, namespace_identity_hash(store_id, namespace)))
    exceptions = validated_overlap_exceptions(
        registry,
        root_rows,
        blockers,
        repo_root=root,
        baseline_integrity_hash=baseline_integrity_hash,
    )
    check_state_path_overlaps(writers, blockers, prefix="v144_wave0_state_writer", exceptions=exceptions)


def namespace_path_evidence(
    source_path: Path,
    source: str,
    class_name: str,
    root_authority_id: str,
    relative_path_template: str,
) -> dict[str, object] | None:
    try:
        source_text = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source_text, filename=str(source_path))
    except (OSError, SyntaxError, UnicodeError):
        return None
    expression = _path_expression(tree, source_text, class_name, relative_path_template)
    if expression is None:
        return None
    span = source_span(expression)
    return {
        "source_evidence_schema_version": SOURCE_EVIDENCE_SCHEMA_VERSION,
        "source": source,
        **span.document(),
        "expression_source_hash": source_fragment_hash(source_text, expression),
        "root_authority_id": root_authority_id,
        "relative_path_template_hash": hashlib.sha256(relative_path_template.encode("utf-8")).hexdigest(),
    }


def _validate_path_evidence(
    store_id: str,
    source: str,
    namespace: dict[str, object],
    blockers: list[str],
    *,
    root: Path | None,
) -> None:
    evidence = namespace.get("path_evidence")
    if not isinstance(evidence, dict):
        blockers.append(f"v144_wave0_state_path_evidence:{store_id}")
        return
    evidence_source = str(evidence.get("source") or "")
    line = evidence.get("line")
    column = evidence.get("column")
    end_line = evidence.get("end_line")
    end_column = evidence.get("end_column")
    expression_source_hash = str(evidence.get("expression_source_hash") or "")
    root_id = str(namespace.get("root_authority_id") or "")
    relative = str(namespace.get("relative_path_template") or "")
    relative_hash = hashlib.sha256(relative.encode("utf-8")).hexdigest()
    if (
        evidence.get("source_evidence_schema_version") != SOURCE_EVIDENCE_SCHEMA_VERSION
        or not evidence_source
        or not isinstance(line, int)
        or not isinstance(column, int)
        or not isinstance(end_line, int)
        or not isinstance(end_column, int)
        or line < 1
        or column < 0
        or end_line < line
        or end_column < 0
        or len(expression_source_hash) != 64
        or evidence.get("root_authority_id") != root_id
        or evidence.get("relative_path_template_hash") != relative_hash
    ):
        blockers.append(f"v144_wave0_state_path_evidence:{store_id}")
        return
    if not evidence_source.startswith(source.rsplit("/", 1)[0] + "/"):
        blockers.append(f"v144_wave0_state_path_evidence_identity:{store_id}")
    if root is not None:
        expected = namespace_path_evidence(
            root / evidence_source,
            evidence_source,
            store_id.rsplit(".", 1)[-1],
            root_id,
            relative,
        )
        if expected != evidence:
            blockers.append(f"v144_wave0_state_path_evidence_current:{store_id}")


def _path_expression(tree: ast.AST, source_text: str, class_name: str, relative: str) -> ast.expr | None:
    class_node = next((node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == class_name), None)
    search_root: ast.AST = class_node if class_node is not None else tree
    candidates = [node for node in ast.walk(search_root) if isinstance(node, ast.expr)]
    module_assignments = [
        value
        for statement in ast.iter_child_nodes(tree)
        if (assignment := _assignment_value(statement)) is not None
        for value in [assignment]
    ]
    candidates.extend(module_assignments)
    rendered_candidates = [source_fragment(source_text, expression).lower() for expression in candidates]
    required_static = _static_path_tokens(relative)
    if any(not any(token in rendered for rendered in rendered_candidates) for token in required_static):
        return None
    tokens = _path_tokens(relative)
    scored: list[tuple[int, int, int, ast.expr]] = []
    for expression, rendered in zip(candidates, rendered_candidates):
        score = sum(token in rendered for token in tokens)
        if relative == "." and any(marker in rendered for marker in ("root", "dir", "path", "store")):
            score = max(score, 1)
        if score:
            scored.append((-score, len(rendered), int(getattr(expression, "lineno", 0)), expression))
    if not scored:
        return None
    scored.sort(key=lambda item: item[:3])
    return scored[0][3]


def _assignment_value(node: ast.AST) -> ast.expr | None:
    if isinstance(node, ast.Assign):
        return node.value
    if isinstance(node, ast.AnnAssign):
        return node.value
    return None


def _path_tokens(template: str) -> list[str]:
    fields = re.findall(r"\{([^}]+)\}", template.lower())
    return [*_static_path_tokens(template), *fields]


def _static_path_tokens(template: str) -> list[str]:
    without_fields = re.sub(r"\{[^}]+\}", "", template.lower())
    return [part for part in re.split(r"[^a-z0-9_-]+", without_fields) if part]


def _unique_rows(rows: list[dict[str, object]], key: str, label: str, blockers: list[str]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        identity = str(row.get(key) or "")
        if not identity or identity in result:
            blockers.append(f"v144_wave0_registry_ids:{label}")
        result[identity] = row
    return result
