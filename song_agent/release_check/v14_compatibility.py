from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.platform.verification.hashing import sha256_text_file, stable_hash


RETIREMENT_PATH = "architecture-v14-compatibility-retirement.json"
FROZEN_PATH = "architecture-v14-migration.json"
DOMAIN_MIGRATION_PATH = "architecture-v14-domain-migration.json"


def evaluate_v14_compatibility_retirement(
    repo_root: Path | str = ".",
    *,
    retirement_path: Path | str = RETIREMENT_PATH,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    target = _rooted(root, retirement_path)
    document = _read_json(target)
    frozen = _read_json(root / FROZEN_PATH)
    migration = _read_json(root / DOMAIN_MIGRATION_PATH)
    architecture_snapshot = snapshot or build_architecture_snapshot(root)
    blockers: list[str] = []

    if document.get("schema_version") != 1:
        blockers.append("v14_compatibility_schema")
    if document.get("package_type") != "musicforge_v14_compatibility_retirement":
        blockers.append("v14_compatibility_package_type")
    if document.get("release_version") != "14.0.0" or document.get("baseline_tag") != "v13.8.0":
        blockers.append("v14_compatibility_release_binding")
    expected_integrity = stable_hash({key: value for key, value in document.items() if key != "integrity_hash"})
    if document.get("integrity_hash") != expected_integrity:
        blockers.append("v14_compatibility_integrity")
    source = document.get("source") or {}
    if source.get("frozen_migration_hash") != stable_hash(frozen):
        blockers.append("v14_compatibility_frozen_source")
    if source.get("domain_migration_hash") != stable_hash(migration):
        blockers.append("v14_compatibility_domain_source")

    baseline_entries = {
        str(row["module"]): row
        for row in ((frozen.get("retirement") or {}).get("entries") or [])
    }
    migration_entries = {
        str(row["source"]): row
        for wave in migration.get("waves") or []
        for row in wave.get("modules") or []
    }
    entries = {str(row.get("module")): row for row in document.get("entries") or []}
    analyses: dict[str, dict[str, Any]] = {}
    if set(entries) != set(baseline_entries):
        blockers.append("v14_compatibility_module_inventory")
    if len(migration_entries) != 270:
        blockers.append("v14_compatibility_domain_migration_count")

    implementation_lines = 0
    for module, baseline in baseline_entries.items():
        row = entries.get(module)
        if not row:
            continue
        prefix = f"v14_compatibility_entry:{module}"
        if row.get("retirement_status") != "retired":
            blockers.append(f"{prefix}:status")
        facade_path = root / str(row.get("facade_path") or "")
        target_path = root / str(row.get("target_path") or "")
        if not facade_path.is_file():
            blockers.append(f"{prefix}:facade_missing")
            continue
        if not target_path.is_file():
            blockers.append(f"{prefix}:target_missing")
        if row.get("facade_hash") != _file_hash(facade_path):
            blockers.append(f"{prefix}:facade_hash")
        analysis = _facade_analysis(facade_path)
        analyses[module] = analysis
        implementation_lines += int(analysis["implementation_lines"])
        if not analysis["static"]:
            blockers.append(f"{prefix}:not_static")
        expected_contract_hash = stable_hash(
            sorted(str(item) for item in baseline.get("public_contracts") or [])
        )
        if row.get("public_contract_hash") != expected_contract_hash:
            blockers.append(f"{prefix}:public_contract")
        migration_row = migration_entries.get(module)
        expected_target = str(migration_row.get("target")) if migration_row else "song_agent.platform.version" if module == "song_agent" else ""
        if row.get("target_module") != expected_target:
            blockers.append(f"{prefix}:target_binding")
        expected_target_path = _module_path(root, expected_target)
        if expected_target_path is None or row.get("target_path") != expected_target_path.relative_to(root).as_posix():
            blockers.append(f"{prefix}:target_path")

    active_compatibility = list(architecture_snapshot.get("active_to_compatibility_imports") or [])
    active_legacy = _active_legacy_imports(architecture_snapshot)
    blockers.extend(
        f"v14_compatibility_active_edge:{row['importer']}->{row['imported']}"
        for row in active_compatibility
    )
    blockers.extend(
        f"v14_compatibility_legacy_dependency:{row['importer']}->{row['imported']}"
        for row in active_legacy
    )
    legacy_profiles = _current_profile_legacy_callables()
    blockers.extend(
        f"v14_compatibility_current_profile_legacy:{profile}:{callable_name}"
        for profile, callable_name in legacy_profiles
    )

    summary = document.get("summary") or {}
    expected_summary = {
        "baseline_module_count": len(baseline_entries),
        "domain_migration_count": len(migration_entries),
        "retired_module_count": sum(row.get("retirement_status") == "retired" for row in entries.values()),
        "unresolved_module_count": sum(row.get("retirement_status") != "retired" for row in entries.values()),
        "active_to_compatibility_import_count": len(active_compatibility),
        "active_legacy_dependency_import_count": len(active_legacy),
        "active_compatibility_implementation_line_count": implementation_lines,
        "dynamic_facade_count": sum(bool(row["dynamic"]) for row in analyses.values()),
        "wildcard_facade_count": sum(bool(row["wildcard"]) for row in analyses.values()),
    }
    for key, expected in expected_summary.items():
        if int(summary.get(key, -1)) != int(expected):
            blockers.append(f"v14_compatibility_summary:{key}")
    for key in (
        "unresolved_module_count",
        "active_to_compatibility_import_count",
        "active_legacy_dependency_import_count",
        "active_compatibility_implementation_line_count",
        "dynamic_facade_count",
        "wildcard_facade_count",
    ):
        if int(expected_summary[key]) != 0:
            blockers.append(f"v14_compatibility_not_retired:{key}:{expected_summary[key]}")

    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_compatibility_retirement_verification",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "summary": expected_summary,
        "current_profile_legacy_callables": [
            {"profile": profile, "callable_name": callable_name}
            for profile, callable_name in legacy_profiles
        ],
        "retirement_integrity_hash": document.get("integrity_hash"),
    }


def run_v14_compatibility_zero_smoke(root: Path) -> tuple[bool, str]:
    try:
        report = evaluate_v14_compatibility_retirement(root)
        detail = {
            "status": report["status"],
            "retired": report["summary"]["retired_module_count"],
            "active_edges": report["summary"]["active_to_compatibility_import_count"],
            "legacy_dependencies": report["summary"]["active_legacy_dependency_import_count"],
            "implementation_lines": report["summary"]["active_compatibility_implementation_line_count"],
        }
        return report["status"] == "passed", json.dumps(detail, sort_keys=True)
    except Exception as exc:
        return False, f"v14 compatibility retirement smoke failed: {exc}"


def _current_profile_legacy_callables() -> list[tuple[str, str]]:
    from song_agent.release_check.matrix import (
        LEGACY_COMPATIBILITY_CALLABLES,
        select_check_definitions,
    )

    rows: list[tuple[str, str]] = []
    for profile in ("latest", "ga", "security", "v14"):
        for definition in select_check_definitions(profile=profile, run_tests=False):
            name = str(definition.callable_name or "")
            if name in LEGACY_COMPATIBILITY_CALLABLES:
                rows.append((profile, name))
    return rows


def _active_legacy_imports(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    ownership = {str(row["module"]): row for row in snapshot.get("modules") or []}
    return [
        {"importer": str(row["importer"]), "imported": str(row["imported"])}
        for row in snapshot.get("import_pairs") or []
        if str((ownership.get(str(row["importer"])) or {}).get("layer") or "")
        not in {"compatibility", "release_check"}
        and str(row["imported"]).startswith("song_agent.application.legacy_dependencies")
    ]


def _facade_analysis(path: Path) -> dict[str, Any]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dynamic = False
    wildcard = False
    implementation_lines = 0
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.ImportFrom):
            wildcard = wildcard or any(alias.name == "*" for alias in node.names)
            continue
        if isinstance(node, ast.Import):
            continue
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and _simple_assignment(node):
            continue
        start = int(getattr(node, "lineno", 1))
        end = int(getattr(node, "end_lineno", start))
        implementation_lines += end - start + 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"__getattr__", "_resolve_symbol"}:
            dynamic = True
        if isinstance(node, ast.Call) and _call_name(node) in {
            "globals.update",
            "importlib.import_module",
            "import_module",
        }:
            dynamic = True
    return {
        "static": implementation_lines == 0 and not dynamic and not wildcard,
        "dynamic": dynamic,
        "wildcard": wildcard,
        "implementation_lines": implementation_lines,
    }


def _simple_assignment(node: ast.Assign | ast.AnnAssign) -> bool:
    value = node.value
    return value is None or isinstance(value, (ast.Constant, ast.Name, ast.Tuple, ast.List, ast.Set, ast.Dict))


def _call_name(node: ast.Call) -> str:
    parts: list[str] = []
    value: ast.AST = node.func
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _file_hash(path: Path) -> str:
    value = sha256_text_file(path)
    if value is None:
        raise FileNotFoundError(path)
    return value


def _module_path(root: Path, module: str) -> Path | None:
    if not module:
        return None
    relative = Path(*module.split("."))
    module_path = root / relative.with_suffix(".py")
    if module_path.is_file():
        return module_path
    package_path = root / relative / "__init__.py"
    return package_path if package_path.is_file() else None


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _rooted(root: Path, path: Path | str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target
