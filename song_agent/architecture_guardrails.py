from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any, Iterable

from song_agent import __version__


ARCHITECTURE_BASELINE_SCHEMA_VERSION = 1
INTERFACE_MODULES = {
    "song_agent.cli": "cli",
    "song_agent.server": "api",
    "song_agent.webui": "web",
}
INTERFACE_CONTEXTS = {"cli", "api", "web"}
MEGA_FILE_PATHS = (
    "song_agent/release_checks.py",
    "song_agent/server.py",
    "song_agent/cli.py",
    "song_agent/webui.py",
    "song_agent/interfaces/api/runtime.py",
    "song_agent/interfaces/api/routes/creation.py",
    "song_agent/interfaces/api/routes/studio.py",
    "song_agent/interfaces/api/routes/quality.py",
    "song_agent/interfaces/api/routes/delivery.py",
    "song_agent/interfaces/api/routes/trust.py",
    "song_agent/interfaces/api/routes/program.py",
    "song_agent/interfaces/api/routes/maintenance.py",
    "song_agent/interfaces/cli/commands/creation.py",
    "song_agent/interfaces/cli/commands/studio.py",
    "song_agent/interfaces/cli/commands/quality.py",
    "song_agent/interfaces/cli/commands/delivery.py",
    "song_agent/interfaces/cli/commands/trust.py",
    "song_agent/interfaces/cli/commands/program.py",
    "song_agent/interfaces/cli/commands/maintenance.py",
    "song_agent/interfaces/cli/commands/release_check.py",
)
SECURITY_HELPER_NAMES = (
    "_raw_zip_entry_names",
    "_is_safe_zip_entry",
    "_zip_has_no_trailing_data",
)
CUSTOM_LIFECYCLE_ALGORITHM_NAMES = (
    "_append_history_event",
    "_build_history_event",
    "_hash_history_event",
)
DEPENDENCY_EXCEPTIONS: dict[tuple[str, str], str] = {}


def build_architecture_snapshot(repo_root: Path | str = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    paths = sorted((root / "song_agent").rglob("*.py"))
    modules = {_module_name(root, path): path for path in paths}
    sources = {module: path.read_text(encoding="utf-8") for module, path in modules.items()}
    trees: dict[str, ast.AST] = {
        module: ast.parse(sources[module], filename=str(path))
        for module, path in modules.items()
    }
    ownership = {
        module: _module_ownership(module, path.relative_to(root).as_posix())
        for module, path in modules.items()
    }
    imports, imported_names, dynamic_internal_imports = _import_graph(modules, trees)
    all_cycles = _import_cycles(imports)
    active_to_compatibility_imports = [
        {"importer": importer, "imported": imported}
        for importer in sorted(imports)
        if ownership[importer]["layer"] not in {"compatibility", "release_check"}
        for imported in sorted(imports[importer])
        if ownership[imported]["layer"] == "compatibility"
    ]
    production_modules = {
        module
        for module, row in ownership.items()
        if row.get("layer") not in {"compatibility", "release_check"}
    }
    production_imports = {
        module: {target for target in imports[module] if target in production_modules}
        for module in production_modules
    }
    cycles = _import_cycles(production_imports)
    line_counts = {
        modules[module].relative_to(root).as_posix(): len(source.splitlines())
        for module, source in sources.items()
    }
    helper_counts = _security_helper_counts(trees, ownership, active_only=True)
    all_helper_counts = _security_helper_counts(trees, ownership, active_only=False)
    lifecycle_algorithm_counts = _lifecycle_algorithm_counts(trees, ownership)
    code_metrics = _code_metrics(root, modules, trees, line_counts, imports, ownership)
    boundary_violations = _boundary_violations(
        ownership,
        imports,
        imported_names,
        dynamic_internal_imports,
    )
    dependency_exceptions = _active_dependency_exceptions(imports)
    module_rows = [ownership[module] for module in sorted(ownership)]
    return {
        "schema_version": ARCHITECTURE_BASELINE_SCHEMA_VERSION,
        "app_version": __version__,
        "module_count": len(module_rows),
        "total_source_lines": sum(line_counts.values()),
        "modules": module_rows,
        "import_pairs": [
            {"importer": importer, "imported": imported}
            for importer in sorted(imports)
            for imported in sorted(imports[importer])
        ],
        "cycles": cycles,
        "all_import_cycles": all_cycles,
        "active_to_compatibility_imports": active_to_compatibility_imports,
        "dynamic_internal_imports": dynamic_internal_imports,
        "boundary_violations": boundary_violations,
        "dependency_exceptions": dependency_exceptions,
        "mega_files": {path: line_counts.get(path, 0) for path in MEGA_FILE_PATHS},
        "security_helper_counts": helper_counts,
        "all_security_helper_counts": all_helper_counts,
        "active_custom_lifecycle_algorithm_counts": lifecycle_algorithm_counts,
        "code_metrics": code_metrics,
    }


def build_architecture_baseline(
    repo_root: Path | str = ".",
    *,
    baseline_version: str = "13.0.0",
) -> dict[str, Any]:
    snapshot = build_architecture_snapshot(repo_root)
    return {
        "schema_version": ARCHITECTURE_BASELINE_SCHEMA_VERSION,
        "baseline_version": baseline_version,
        "module_count": snapshot["module_count"],
        "modules": snapshot["modules"],
        "allowed_cycles": snapshot["cycles"],
        "mega_file_max_lines": snapshot["mega_files"],
        "security_helper_max_counts": snapshot["security_helper_counts"],
        "active_to_compatibility_import_max_count": len(snapshot["active_to_compatibility_imports"]),
        "allowed_active_to_compatibility_imports": snapshot["active_to_compatibility_imports"],
        "dependency_exceptions": snapshot["dependency_exceptions"],
        "required_absent_dependencies": [
            {"importer": "song_agent.server", "imported": "song_agent.cli"},
            {"importer": "song_agent.mix_render", "imported": "song_agent.server"},
        ],
        "notes": {
            "allowed_cycles": "The active production graph is acyclic. Historical compatibility cycles remain visible only in all_import_cycles metrics.",
            "mega_files": "Interface and release-check facades must remain below v13 hard limits.",
            "security_helpers": "Active verifier ZIP safety is owned exclusively by platform.verification.",
            "compatibility_imports": "Active-to-compatibility imports are visible debt and may only decrease after the v13 cutover.",
        },
    }


def evaluate_architecture(
    repo_root: Path | str = ".",
    *,
    baseline_path: Path | str = "architecture-baseline.json",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    baseline_file = Path(baseline_path)
    if not baseline_file.is_absolute():
        baseline_file = root / baseline_file
    baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
    snapshot = build_architecture_snapshot(root)
    blockers: list[str] = []

    baseline_modules = {str(row.get("module")): row for row in baseline.get("modules", [])}
    current_modules = {str(row.get("module")): row for row in snapshot.get("modules", [])}
    missing_modules = sorted(set(baseline_modules) - set(current_modules))
    unclassified_modules = sorted(set(current_modules) - set(baseline_modules))
    changed_ownership = sorted(
        module
        for module in set(current_modules) & set(baseline_modules)
        if _ownership_key(current_modules[module]) != _ownership_key(baseline_modules[module])
    )
    blockers.extend(f"architecture_module_missing:{module}" for module in missing_modules)
    blockers.extend(f"architecture_module_unclassified:{module}" for module in unclassified_modules)
    blockers.extend(f"architecture_module_ownership_changed:{module}" for module in changed_ownership)

    baseline_exceptions = {
        (str(row.get("importer")), str(row.get("imported")))
        for row in baseline.get("dependency_exceptions", [])
    }
    current_exceptions = {
        (str(row.get("importer")), str(row.get("imported")))
        for row in snapshot.get("dependency_exceptions", [])
    }
    blockers.extend(
        f"architecture_dependency_exception_unapproved:{importer}->{imported}"
        for importer, imported in sorted(current_exceptions - baseline_exceptions)
    )

    new_cycles = _new_cycles(
        baseline.get("allowed_cycles", []),
        snapshot.get("cycles", []),
    )
    blockers.extend(f"architecture_import_cycle:{_cycle_key(cycle)}" for cycle in new_cycles)
    blockers.extend(
        f"architecture_boundary:{row['importer']}->{row['imported']}:{row['reason']}"
        for row in snapshot.get("boundary_violations", [])
    )

    imports = {
        (str(row.get("importer")), str(row.get("imported")))
        for row in snapshot.get("import_pairs", [])
    }
    for row in baseline.get("required_absent_dependencies", []):
        pair = (str(row.get("importer")), str(row.get("imported")))
        if pair in imports:
            blockers.append(f"architecture_forbidden_dependency:{pair[0]}->{pair[1]}")

    for path, maximum in (baseline.get("mega_file_max_lines") or {}).items():
        current = int((snapshot.get("mega_files") or {}).get(path, 0))
        if current > int(maximum):
            blockers.append(f"architecture_mega_file_growth:{path}:{current}>{maximum}")
    for name, maximum in (baseline.get("security_helper_max_counts") or {}).items():
        current = int((snapshot.get("security_helper_counts") or {}).get(name, 0))
        if current > int(maximum):
            blockers.append(f"architecture_security_helper_growth:{name}:{current}>{maximum}")
    compatibility_import_count = len(snapshot.get("active_to_compatibility_imports", []))
    compatibility_import_maximum = int(baseline.get("active_to_compatibility_import_max_count", compatibility_import_count))
    baseline_compatibility_imports = {
        (str(row.get("importer")), str(row.get("imported")))
        for row in baseline.get("allowed_active_to_compatibility_imports", [])
    }
    current_compatibility_imports = {
        (str(row.get("importer")), str(row.get("imported")))
        for row in snapshot.get("active_to_compatibility_imports", [])
    }
    blockers.extend(
        f"architecture_compatibility_import_unapproved:{importer}->{imported}"
        for importer, imported in sorted(current_compatibility_imports - baseline_compatibility_imports)
    )
    if compatibility_import_count > compatibility_import_maximum:
        blockers.append(
            f"architecture_compatibility_import_growth:{compatibility_import_count}>{compatibility_import_maximum}"
        )

    from song_agent.release_check.architecture_ratchet import evaluate_architecture_ratchet

    ratchet = evaluate_architecture_ratchet(
        root,
        current_baseline=baseline,
        snapshot=snapshot,
    )
    blockers.extend(str(blocker) for blocker in ratchet.get("blockers") or [])

    metrics = {
        "schema_version": ARCHITECTURE_BASELINE_SCHEMA_VERSION,
        "app_version": __version__,
        "status": "passed" if not blockers else "failed",
        "module_count": snapshot["module_count"],
        "total_source_lines": snapshot["total_source_lines"],
        "mega_files": snapshot["mega_files"],
        "security_helper_counts": snapshot["security_helper_counts"],
        "all_security_helper_counts": snapshot["all_security_helper_counts"],
        "active_custom_lifecycle_algorithm_counts": snapshot["active_custom_lifecycle_algorithm_counts"],
        "cycle_count": len(snapshot["cycles"]),
        "cycles": snapshot["cycles"],
        "all_import_cycle_count": len(snapshot["all_import_cycles"]),
        "active_to_compatibility_import_count": compatibility_import_count,
        "active_to_compatibility_imports": snapshot["active_to_compatibility_imports"],
        "boundary_violation_count": len(snapshot["boundary_violations"]),
        "dependency_exceptions": snapshot["dependency_exceptions"],
        "source_file_count": snapshot["code_metrics"]["source_file_count"],
        "top_largest_files": snapshot["code_metrics"]["top_largest_files"],
        "top_largest_functions": snapshot["code_metrics"]["top_largest_functions"],
        "top_largest_classes": snapshot["code_metrics"]["top_largest_classes"],
        "internal_import_edge_count": snapshot["code_metrics"]["internal_import_edge_count"],
        "internal_import_edges": snapshot["import_pairs"],
        "domain_interface_violation_count": snapshot["code_metrics"]["domain_interface_violation_count"],
        "store_class_count": snapshot["code_metrics"]["store_class_count"],
        "verifier_module_count": snapshot["code_metrics"]["verifier_module_count"],
        "verifier_function_count": snapshot["code_metrics"]["verifier_function_count"],
        "dict_str_any_count": snapshot["code_metrics"]["dict_str_any_count"],
        "cli_argument_count": snapshot["code_metrics"]["cli_argument_count"],
        "api_route_count": snapshot["code_metrics"]["api_route_count"],
        "web_function_count": snapshot["code_metrics"]["web_function_count"],
        "pytest_test_function_count": snapshot["code_metrics"]["pytest_test_function_count"],
        "ratchet": ratchet,
        "blockers": blockers,
        "baseline_hash": _stable_hash(baseline),
    }
    return {
        "status": metrics["status"],
        "blockers": blockers,
        "metrics": metrics,
        "snapshot": snapshot,
    }


def write_architecture_metrics(report: dict[str, Any], path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.get("metrics") or {}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def write_architecture_baseline(document: dict[str, Any], path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def update_architecture_release_metrics(
    path: Path | str,
    *,
    profile: str,
    duration_ms: int,
    status: str,
    check_count: int,
) -> Path | None:
    target = Path(path)
    if not target.exists():
        return None
    metrics = json.loads(target.read_text(encoding="utf-8"))
    metrics["release_check"] = {
        "profile": str(profile),
        "duration_ms": int(duration_ms),
        "status": str(status),
        "check_count": int(check_count),
    }
    target.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _module_name(root: Path, path: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_ownership(module: str, path: str) -> dict[str, Any]:
    if module == "song_agent":
        return _ownership_row(module, path, "compatibility", None)
    if module.startswith("song_agent.platform"):
        return _ownership_row(module, path, "platform", None)
    if module.startswith("song_agent.application"):
        return _ownership_row(module, path, "application", None)
    if module.startswith("song_agent.capabilities"):
        return _ownership_row(module, path, "application", None)
    if module.startswith("song_agent.interfaces."):
        parts = module.split(".")
        context = parts[2] if len(parts) > 2 and parts[2] in INTERFACE_CONTEXTS else None
        return _ownership_row(module, path, "interface", context)
    if module in INTERFACE_MODULES:
        return _ownership_row(module, path, "interface", INTERFACE_MODULES[module])
    if module in {"song_agent.release_check", "song_agent.release_checks"} or module.startswith("song_agent.release_check_") or module.startswith("song_agent.release_check.") or module == "song_agent.architecture_guardrails":
        return _ownership_row(module, path, "release_check", None)
    if module.startswith("song_agent.domains."):
        parts = module.split(".")
        return _ownership_row(module, path, "domain", parts[2] if len(parts) > 2 else "creation")
    if module == "song_agent.domains":
        return _ownership_row(module, path, "domain", None)
    if module.startswith("song_agent.unified_release_program"):
        return _ownership_row(module, path, "domain", "program")
    return _ownership_row(module, path, "compatibility", _legacy_domain_context(module))


def _ownership_row(module: str, path: str, layer: str, context: str | None) -> dict[str, Any]:
    return {"module": module, "path": path, "layer": layer, "context": context}


def _legacy_domain_context(module: str) -> str:
    leaf = module.rsplit(".", 1)[-1]
    if leaf.startswith("unified_"):
        return "program"
    if leaf.startswith(("public_trust", "trust_operations", "release_portfolio", "release_operations", "ga_readiness")):
        return "trust"
    if leaf.startswith(
        (
            "audio_",
            "acceptance_",
            "review_",
            "candidate_",
            "human_review",
            "mix_",
            "mastering_",
            "music_acceptance",
            "release_audio",
            "quality",
        )
    ):
        return "quality"
    if leaf.startswith(("release", "distribution", "submission", "rights_", "delivery_", "format_")):
        return "delivery"
    if leaf.startswith(
        (
            "project",
            "editor_",
            "asset",
            "reference",
            "context_",
            "library_",
            "prompt_",
            "song_editor",
            "version",
        )
    ):
        return "studio"
    return "creation"


def _import_graph(
    modules: dict[str, Path],
    trees: dict[str, ast.AST],
) -> tuple[
    dict[str, set[str]],
    dict[str, list[tuple[str, tuple[str, ...]]]],
    list[dict[str, Any]],
]:
    known = set(modules)
    graph: dict[str, set[str]] = {module: set() for module in known}
    imported_names: dict[str, list[tuple[str, tuple[str, ...]]]] = {module: [] for module in known}
    dynamic_internal_imports: list[dict[str, Any]] = []
    for module in modules:
        path = modules[module]
        tree = trees[module]
        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _known_module(alias.name, known)
                    if target:
                        graph[module].add(target)
                        imported_names[module].append((target, ()))
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import_from(node, package)
                targets: set[str] = set()
                base_target = _known_module(base, known)
                if base_target:
                    targets.add(base_target)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{base}.{alias.name}" if base else alias.name
                    target = _known_module(candidate, known)
                    if target:
                        targets.add(target)
                names = tuple(alias.name for alias in node.names)
                for target in targets:
                    graph[module].add(target)
                    imported_names[module].append((target, names if target == base_target else ()))
            elif isinstance(node, ast.Call):
                target = _dynamic_internal_import_target(node)
                if target:
                    dynamic_internal_imports.append(
                        {"importer": module, "imported": target, "line": int(node.lineno)}
                    )
    return graph, imported_names, sorted(
        dynamic_internal_imports,
        key=lambda row: (str(row["importer"]), int(row["line"]), str(row["imported"])),
    )


def _dynamic_internal_import_target(node: ast.Call) -> str | None:
    if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
        return None
    function = node.func
    is_dynamic_import = (
        isinstance(function, ast.Name)
        and function.id == "__import__"
    ) or (
        isinstance(function, ast.Attribute)
        and function.attr == "import_module"
    )
    target = str(node.args[0].value)
    if is_dynamic_import and (target == "song_agent" or target.startswith("song_agent.")):
        return target
    return None


def _resolve_import_from(node: ast.ImportFrom, package: str) -> str:
    if not node.level:
        return str(node.module or "")
    relative = "." * node.level + str(node.module or "")
    try:
        return importlib.util.resolve_name(relative, package)
    except (ImportError, ValueError):
        return ""


def _known_module(value: str, known: set[str]) -> str | None:
    candidate = value
    while candidate:
        if candidate in known:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return None


def _import_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(module: str) -> None:
        nonlocal index
        indexes[module] = index
        lowlinks[module] = index
        index += 1
        stack.append(module)
        on_stack.add(module)
        for target in graph.get(module, set()):
            if target not in indexes:
                visit(target)
                lowlinks[module] = min(lowlinks[module], lowlinks[target])
            elif target in on_stack:
                lowlinks[module] = min(lowlinks[module], indexes[target])
        if lowlinks[module] != indexes[module]:
            return
        component: list[str] = []
        while stack:
            target = stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target == module:
                break
        if len(component) > 1 or module in graph.get(module, set()):
            components.append(sorted(component))

    for module in sorted(graph):
        if module not in indexes:
            visit(module)
    return sorted(components, key=_cycle_key)


def _boundary_violations(
    ownership: dict[str, dict[str, Any]],
    imports: dict[str, set[str]],
    imported_names: dict[str, list[tuple[str, tuple[str, ...]]]],
    dynamic_internal_imports: list[dict[str, Any]],
) -> list[dict[str, str]]:
    violations: set[tuple[str, str, str]] = set()
    for importer, targets in imports.items():
        importer_layer = str(ownership[importer]["layer"])
        for imported in targets:
            imported_layer = str(ownership[imported]["layer"])
            reason = ""
            if importer_layer == "platform" and imported_layer != "platform":
                reason = "platform_must_not_depend_outward"
            elif importer_layer == "application" and imported_layer in {"interface", "release_check"}:
                reason = "application_must_not_depend_on_interface_or_release_check"
            elif importer_layer == "domain" and imported_layer in {"interface", "release_check"}:
                reason = "domain_must_not_depend_on_interface_or_release_check"
            elif importer_layer in {"platform", "application", "domain"} and imported_layer == "release_check":
                reason = "production_must_not_depend_on_release_check"
            if reason:
                if (importer, imported) not in DEPENDENCY_EXCEPTIONS:
                    violations.add((importer, imported, reason))
    for imported, names in imported_names.get("song_agent.release_checks", []):
        if imported == "song_agent.server" and any(name.startswith("_") for name in names):
            violations.add(
                (
                    "song_agent.release_checks",
                    "song_agent.server",
                    "release_check_must_not_import_private_interface_symbol",
                )
            )
    for row in dynamic_internal_imports:
        violations.add(
            (
                str(row["importer"]),
                str(row["imported"]),
                f"dynamic_internal_import_at_line_{int(row['line'])}",
            )
        )
    return [
        {"importer": importer, "imported": imported, "reason": reason}
        for importer, imported, reason in sorted(violations)
    ]


def _active_dependency_exceptions(imports: dict[str, set[str]]) -> list[dict[str, str]]:
    return [
        {"importer": importer, "imported": imported, "reason": reason}
        for (importer, imported), reason in sorted(DEPENDENCY_EXCEPTIONS.items())
        if imported in imports.get(importer, set())
    ]


def _security_helper_counts(
    trees: dict[str, ast.AST],
    ownership: dict[str, dict[str, Any]],
    *,
    active_only: bool,
) -> dict[str, int]:
    counts = {name: 0 for name in SECURITY_HELPER_NAMES}
    for module, tree in trees.items():
        layer = str(ownership[module]["layer"])
        if active_only and layer in {"compatibility", "release_check"}:
            continue
        if module == "song_agent.platform.verification.zip_security":
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in counts:
                counts[node.name] += 1
    return counts


def _lifecycle_algorithm_counts(
    trees: dict[str, ast.AST],
    ownership: dict[str, dict[str, Any]],
) -> dict[str, int]:
    counts = {name: 0 for name in CUSTOM_LIFECYCLE_ALGORITHM_NAMES}
    for module, tree in trees.items():
        if ownership[module]["layer"] in {"compatibility", "release_check"}:
            continue
        if module.startswith("song_agent.platform.lifecycle"):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in counts:
                counts[node.name] += 1
    return counts


def _code_metrics(
    root: Path,
    modules: dict[str, Path],
    trees: dict[str, ast.AST],
    line_counts: dict[str, int],
    imports: dict[str, set[str]],
    ownership: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    store_class_count = 0
    verifier_function_count = 0
    dict_str_any_count = 0
    cli_argument_count = 0
    api_routes: set[str] = set()
    web_function_count = 0
    for module, tree in trees.items():
        path = modules[module].relative_to(root).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                row = _definition_metric(module, path, node, "function")
                functions.append(row)
                if node.name.startswith("verify_"):
                    verifier_function_count += 1
                if module == "song_agent.webui" or module.startswith("song_agent.interfaces.web"):
                    web_function_count += 1
            elif isinstance(node, ast.ClassDef):
                classes.append(_definition_metric(module, path, node, "class"))
                if node.name.endswith("Store"):
                    store_class_count += 1
            elif _is_dict_str_any(node):
                dict_str_any_count += 1
            elif (module == "song_agent.cli" or module.startswith("song_agent.interfaces.cli")) and isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
                    cli_argument_count += 1
            elif (module == "song_agent.server" or module.startswith("song_agent.interfaces.api")) and isinstance(node, ast.Constant):
                if isinstance(node.value, str) and node.value.startswith("/api/"):
                    api_routes.add(node.value)
    test_pattern = re.compile(r"^\s*(?:async\s+)?def\s+test_[A-Za-z0-9_]+\s*\(")
    pytest_test_function_count = 0
    for test_path in sorted((root / "tests").rglob("*.py")):
        pytest_test_function_count += sum(
            1 for line in test_path.read_text(encoding="utf-8").splitlines() if test_pattern.match(line)
        )
    return {
        "source_file_count": len(modules),
        "top_largest_files": [
            {"path": path, "lines": lines}
            for path, lines in sorted(line_counts.items(), key=lambda row: (-row[1], row[0]))[:20]
        ],
        "top_largest_functions": _largest_definitions(functions),
        "top_largest_classes": _largest_definitions(classes),
        "internal_import_edge_count": sum(len(targets) for targets in imports.values()),
        "domain_interface_violation_count": sum(
            1
            for importer, targets in imports.items()
            for imported in targets
            if ownership[importer]["layer"] == "domain"
            and ownership[imported]["layer"] == "interface"
        ),
        "store_class_count": store_class_count,
        "verifier_module_count": sum(1 for module in modules if module.endswith("_verifier")),
        "verifier_function_count": verifier_function_count,
        "dict_str_any_count": dict_str_any_count,
        "cli_argument_count": cli_argument_count,
        "api_route_count": len(api_routes),
        "web_function_count": web_function_count,
        "pytest_test_function_count": pytest_test_function_count,
    }


def _definition_metric(
    module: str,
    path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    kind: str,
) -> dict[str, Any]:
    end_line = int(node.end_lineno or node.lineno)
    return {
        "module": module,
        "path": path,
        "name": node.name,
        "kind": kind,
        "line": int(node.lineno),
        "lines": end_line - int(node.lineno) + 1,
    }


def _largest_definitions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (-int(row["lines"]), str(row["module"]), int(row["line"]), str(row["name"])),
    )[:20]


def _is_dict_str_any(node: ast.AST) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    if not isinstance(node.value, ast.Name) or node.value.id != "dict":
        return False
    if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2:
        return False
    key_type, value_type = node.slice.elts
    return (
        isinstance(key_type, ast.Name)
        and key_type.id == "str"
        and isinstance(value_type, ast.Name)
        and value_type.id == "Any"
    )


def _new_cycles(
    allowed_cycles: Iterable[Iterable[str]],
    current_cycles: Iterable[Iterable[str]],
) -> list[list[str]]:
    allowed_sets = [set(str(module) for module in cycle) for cycle in allowed_cycles]
    return [
        sorted(str(module) for module in cycle)
        for cycle in current_cycles
        if not any(set(str(module) for module in cycle).issubset(allowed) for allowed in allowed_sets)
    ]


def _ownership_key(row: dict[str, Any]) -> tuple[str, str | None, str]:
    return str(row.get("layer")), row.get("context"), str(row.get("path"))


def _cycle_key(cycle: Iterable[str]) -> str:
    return "|".join(sorted(str(module) for module in cycle))


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
