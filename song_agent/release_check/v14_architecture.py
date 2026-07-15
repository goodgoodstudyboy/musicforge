from __future__ import annotations

import ast
from collections import Counter
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.architecture_guardrails import build_architecture_snapshot


V14_POLICY_PATH = "architecture-v14-policy.json"
_PART_FILE = re.compile(r"part_\d+\.py$")


def evaluate_v14_architecture(
    repo_root: Path | str = ".",
    *,
    policy_path: Path | str = V14_POLICY_PATH,
    require_final: bool | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy_file = _rooted(root, policy_path)
    policy = json.loads(policy_file.read_text(encoding="utf-8"))
    snapshot = build_architecture_snapshot(root)
    metrics = _v14_metrics(root, snapshot, policy)
    frozen = json.loads((root / "architecture-v14-migration.json").read_text(encoding="utf-8"))
    blockers = _policy_declaration_blockers(policy, frozen)
    final = bool(policy.get("enforce_final_targets")) if require_final is None else require_final
    limits = policy.get("final_targets") if final else policy.get("limits")
    blockers.extend(_limit_blockers(metrics, limits or {}, final=final))
    blockers.extend(_context_limit_blockers(metrics, policy, final=final))
    if str(policy.get("release_version")) != "14.0.0":
        blockers.append("v14_architecture_release_version")
    if not _current_docs_match_package(root):
        blockers.append("v14_architecture_current_docs_version")
    report: dict[str, Any] = {
        "schema_version": 1,
        "package_type": "musicforge_v14_architecture_report",
        "app_version": __version__,
        "phase": int(policy.get("current_phase") or 0),
        "final_targets_enforced": final,
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "metrics": metrics,
        "limits": limits,
    }
    return report


def run_v14_architecture_cutover_smoke(root: Path) -> tuple[bool, str]:
    try:
        report = evaluate_v14_architecture(root)
        detail = {
            "status": report["status"],
            "phase": report["phase"],
            "active_edges": report["metrics"]["active_to_compatibility_import_count"],
            "anonymous_parts": report["metrics"]["anonymous_part_file_count"],
            "wildcards": report["metrics"]["interface_wildcard_import_count"],
            "dynamic_forwarding": report["metrics"]["active_dynamic_forwarding_count"],
        }
        return report["status"] == "passed", json.dumps(detail, sort_keys=True)
    except Exception as exc:
        return False, f"v14 architecture cutover smoke failed: {exc}"


def _v14_metrics(root: Path, snapshot: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    ownership = {str(row["module"]): row for row in snapshot["modules"]}
    edge_contexts = Counter(
        str(ownership.get(str(row["imported"]), {}).get("context") or "unknown")
        for row in snapshot["active_to_compatibility_imports"]
    )
    anonymous_parts: list[str] = []
    wildcard_imports: list[dict[str, Any]] = []
    dynamic_forwarding: list[dict[str, Any]] = []
    store_references: list[dict[str, Any]] = []
    oversized_functions: list[dict[str, Any]] = []
    for module, row in sorted(ownership.items()):
        layer = str(row.get("layer"))
        if layer in {"compatibility", "release_check"}:
            continue
        relative = str(row["path"])
        path = root / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if layer == "interface" and _PART_FILE.search(path.name):
            anonymous_parts.append(relative)
        for node in ast.walk(tree):
            if layer == "interface" and isinstance(node, ast.ImportFrom):
                if any(alias.name == "*" for alias in node.names):
                    wildcard_imports.append({"module": module, "line": node.lineno, "target": node.module or ""})
                for alias in node.names:
                    if alias.name.endswith("Store"):
                        store_references.append(
                            {"module": module, "path": relative, "line": node.lineno, "name": alias.name}
                        )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "_resolve_symbol" or _uses_globals_update(node) or _uses_resolve_symbol(node):
                    dynamic_forwarding.append({"module": module, "path": relative, "line": node.lineno, "name": node.name})
                if layer == "interface":
                    limit = 120 if row.get("context") == "cli" else 100
                    lines = int(node.end_lineno or node.lineno) - int(node.lineno) + 1
                    if lines > limit:
                        oversized_functions.append(
                            {"module": module, "path": relative, "line": node.lineno, "name": node.name, "lines": lines, "limit": limit}
                        )
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and _is_globals_update(node.value):
                dynamic_forwarding.append({"module": module, "path": relative, "line": node.lineno, "name": "globals.update"})
    baseline_flat = _git_paths(root, str(policy.get("baseline_tag") or "v13.8.0"), "song_agent")
    current_flat = {
        path.relative_to(root).as_posix()
        for path in (root / "song_agent").glob("*.py")
        if path.is_file()
    }
    new_flat = sorted(current_flat - {path for path in baseline_flat if path.count("/") == 1})
    return {
        "production_cycle_count": len(snapshot["cycles"]),
        "boundary_violation_count": len(snapshot["boundary_violations"]),
        "dependency_exception_count": len(snapshot["dependency_exceptions"]),
        "active_to_compatibility_import_count": len(snapshot["active_to_compatibility_imports"]),
        "active_to_compatibility_by_context": dict(sorted(edge_contexts.items())),
        "anonymous_part_file_count": len(anonymous_parts),
        "anonymous_part_files": anonymous_parts,
        "interface_wildcard_import_count": len(wildcard_imports),
        "interface_wildcard_imports": wildcard_imports,
        "active_dynamic_forwarding_count": len(dynamic_forwarding),
        "active_dynamic_forwarding": dynamic_forwarding,
        "interface_store_reference_count": len(store_references),
        "interface_store_references": store_references,
        "interface_oversized_function_count": len(oversized_functions),
        "interface_oversized_functions": oversized_functions,
        "new_flat_module_count": len(new_flat),
        "new_flat_modules": new_flat,
    }


def _policy_declaration_blockers(policy: dict[str, Any], frozen: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if policy.get("schema_version") != 1:
        blockers.append("v14_architecture_policy_schema")
    if policy.get("baseline_tag") != "v13.8.0":
        blockers.append("v14_architecture_policy_baseline_tag")
    frozen_interface = ((frozen.get("interface_debt") or {}).get("summary") or {})
    frozen_limits = {
        "active_to_compatibility_import_count": int(((frozen.get("retirement") or {}).get("summary") or {}).get("active_edge_count") or 0),
        "anonymous_part_file_count": int(frozen_interface.get("anonymous_part_file_count") or 0),
        "interface_wildcard_import_count": int(frozen_interface.get("wildcard_import_count") or 0),
        "interface_store_reference_count": int(frozen_interface.get("direct_store_reference_count") or 0),
        "interface_oversized_function_count": int(frozen_interface.get("oversized_function_count") or 0),
        "active_dynamic_forwarding_count": int(frozen_interface.get("dynamic_forwarding_count") or 0),
        "new_flat_module_count": 0,
    }
    limits = policy.get("limits") or {}
    for key, maximum in frozen_limits.items():
        if int(limits.get(key, maximum)) > maximum:
            blockers.append(f"v14_architecture_policy_loosened:{key}")
    return blockers


def _limit_blockers(metrics: dict[str, Any], limits: dict[str, Any], *, final: bool) -> list[str]:
    prefix = "v14_final" if final else "v14_ratchet"
    blockers: list[str] = []
    for key, maximum in limits.items():
        if isinstance(maximum, dict) or key not in metrics:
            continue
        if int(metrics[key]) > int(maximum):
            blockers.append(f"{prefix}:{key}:{metrics[key]}>{maximum}")
    return blockers


def _context_limit_blockers(metrics: dict[str, Any], policy: dict[str, Any], *, final: bool) -> list[str]:
    counts = metrics["active_to_compatibility_by_context"]
    if final:
        return [f"v14_final:active_to_compatibility_context:{context}:{count}>0" for context, count in counts.items() if count]
    maxima = (policy.get("limits") or {}).get("active_to_compatibility_by_context") or {}
    return [
        f"v14_ratchet:active_to_compatibility_context:{context}:{count}>{maxima.get(context, 0)}"
        for context, count in counts.items()
        if int(count) > int(maxima.get(context, 0))
    ]


def _current_docs_match_package(root: Path) -> bool:
    current = (root / "docs" / "architecture" / "CURRENT.md").read_text(encoding="utf-8")
    return __version__ in current


def _is_globals_update(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "update":
        return False
    owner = call.func.value
    return isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) and owner.func.id == "globals"


def _uses_globals_update(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Call) and _is_globals_update(child) for child in ast.walk(node))


def _uses_resolve_symbol(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "_resolve_symbol"
        for child in ast.walk(node)
    )


def _git_paths(root: Path, ref: str, prefix: str) -> set[str]:
    completed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, prefix],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in completed.stdout.splitlines() if line.strip()}


def _rooted(root: Path, path: Path | str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
