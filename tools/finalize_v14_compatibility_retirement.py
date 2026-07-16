from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any

from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.platform.verification.hashing import sha256_text_file, stable_hash


OUTPUT_PATH = Path("architecture-v14-compatibility-retirement.json")
FROZEN_PATH = Path("architecture-v14-migration.json")
DOMAIN_MIGRATION_PATH = Path("architecture-v14-domain-migration.json")
ROOT_TARGET = "song_agent.platform.version"


def build_retirement_document(root: Path) -> dict[str, Any]:
    frozen = _read_json(root / FROZEN_PATH)
    migration = _read_json(root / DOMAIN_MIGRATION_PATH)
    snapshot = build_architecture_snapshot(root)
    migrated = {
        str(row["source"]): row
        for wave in migration.get("waves") or []
        for row in wave.get("modules") or []
    }
    frozen_entries = list((frozen.get("retirement") or {}).get("entries") or [])
    entries: list[dict[str, Any]] = []
    unresolved: list[str] = []
    dynamic_facades: list[str] = []
    wildcard_facades: list[str] = []
    implementation_lines = 0
    for baseline in frozen_entries:
        module = str(baseline["module"])
        migration_row = migrated.get(module)
        target = str(migration_row["target"]) if migration_row else ROOT_TARGET if module == "song_agent" else ""
        source_path = root / str(baseline["path"])
        target_path = _module_path(root, target)
        facade = _facade_analysis(source_path)
        if facade["dynamic"]:
            dynamic_facades.append(module)
        if facade["wildcard"]:
            wildcard_facades.append(module)
        implementation_lines += int(facade["implementation_lines"])
        status = "retired" if target and target_path is not None and facade["static"] else "unresolved"
        if status != "retired":
            unresolved.append(module)
        entries.append(
            {
                "module": module,
                "context": str(baseline.get("context") or "unknown"),
                "owner": str(baseline.get("owner") or ""),
                "legacy_decision": str(baseline.get("removal_decision") or ""),
                "retirement_status": status,
                "facade_kind": "static_package_facade" if source_path.name == "__init__.py" else "static_module_facade",
                "facade_path": source_path.relative_to(root).as_posix(),
                "facade_hash": _file_hash(source_path),
                "target_module": target,
                "target_path": target_path.relative_to(root).as_posix() if target_path else "",
                "active_callers": [],
                "public_contract_count": len(baseline.get("public_contracts") or []),
                "public_contract_hash": stable_hash(sorted(str(item) for item in baseline.get("public_contracts") or [])),
            }
        )

    active_legacy = _active_legacy_imports(snapshot)
    active_compatibility = list(snapshot.get("active_to_compatibility_imports") or [])
    summary = {
        "baseline_module_count": len(frozen_entries),
        "domain_migration_count": len(migrated),
        "retired_module_count": sum(row["retirement_status"] == "retired" for row in entries),
        "unresolved_module_count": len(unresolved),
        "active_to_compatibility_import_count": len(active_compatibility),
        "active_legacy_dependency_import_count": len(active_legacy),
        "active_compatibility_implementation_line_count": implementation_lines,
        "dynamic_facade_count": len(dynamic_facades),
        "wildcard_facade_count": len(wildcard_facades),
    }
    document: dict[str, Any] = {
        "schema_version": 1,
        "package_type": "musicforge_v14_compatibility_retirement",
        "release_version": "14.0.0",
        "baseline_tag": "v13.8.0",
        "source": {
            "frozen_migration_hash": stable_hash(frozen),
            "domain_migration_hash": stable_hash(migration),
        },
        "summary": summary,
        "unresolved_modules": unresolved,
        "dynamic_facades": dynamic_facades,
        "wildcard_facades": wildcard_facades,
        "active_to_compatibility_imports": active_compatibility,
        "active_legacy_dependency_imports": active_legacy,
        "entries": entries,
    }
    document["integrity_hash"] = stable_hash(document)
    return document


def write_retirement_document(root: Path, output: Path = OUTPUT_PATH) -> Path:
    target = output if output.is_absolute() else root / output
    document = build_retirement_document(root)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


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
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in {"globals.update", "importlib.import_module", "import_module", "__getattr__"}:
                dynamic = True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"__getattr__", "_resolve_symbol"}:
            dynamic = True
    return {
        "static": implementation_lines == 0 and not dynamic and not wildcard,
        "dynamic": dynamic,
        "wildcard": wildcard,
        "implementation_lines": implementation_lines,
    }


def _simple_assignment(node: ast.Assign | ast.AnnAssign) -> bool:
    value = node.value
    if value is None:
        return True
    return isinstance(value, (ast.Constant, ast.Name, ast.Tuple, ast.List, ast.Set, ast.Dict))


def _call_name(node: ast.Call) -> str:
    parts: list[str] = []
    value: ast.AST = node.func
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _active_legacy_imports(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    ownership = {str(row["module"]): row for row in snapshot.get("modules") or []}
    rows: list[dict[str, str]] = []
    for pair in snapshot.get("import_pairs") or []:
        importer = str(pair["importer"])
        imported = str(pair["imported"])
        layer = str((ownership.get(importer) or {}).get("layer") or "")
        if layer not in {"compatibility", "release_check"} and imported.startswith("song_agent.application.legacy_dependencies"):
            rows.append({"importer": importer, "imported": imported})
    return rows


def _module_path(root: Path, module: str) -> Path | None:
    if not module:
        return None
    relative = Path(*module.split("."))
    module_path = root / relative.with_suffix(".py")
    if module_path.is_file():
        return module_path
    package_path = root / relative / "__init__.py"
    return package_path if package_path.is_file() else None


def _file_hash(path: Path) -> str:
    value = sha256_text_file(path)
    if value is None:
        raise FileNotFoundError(path)
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize the v14 compatibility retirement manifest.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    expected = build_retirement_document(root)
    target = Path(args.output)
    target = target if target.is_absolute() else root / target
    if args.check:
        actual = _read_json(target)
        if actual != expected:
            raise SystemExit("v14 compatibility retirement manifest is stale")
    else:
        write_retirement_document(root, target)
    print(json.dumps(expected["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
