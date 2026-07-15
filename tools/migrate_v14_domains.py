from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from song_agent.architecture_guardrails import build_architecture_snapshot


MANIFEST = Path("architecture-v14-domain-migration.json")


def migrate(root: Path, contexts: set[str], *, plan: bool = False) -> int:
    snapshot = build_architecture_snapshot(root)
    ownership = {str(row["module"]): row for row in snapshot["modules"]}
    selected = {
        module: _domain_module(str(row["context"]), module)
        for module, row in ownership.items()
        if row.get("layer") == "compatibility" and row.get("context") in contexts
    }
    if not selected:
        print("domain modules selected: 0")
        return 0
    wrapper_targets = _wrapper_targets(root)
    target_wrappers = _target_wrappers(root, wrapper_targets)
    missing_cross = _missing_cross_boundaries(root, selected, ownership, target_wrappers)
    if missing_cross:
        raise ValueError("Cross-domain compatibility imports lack wrappers: " + ", ".join(sorted(missing_cross)))
    adopted = {
        source: target
        for source, target in selected.items()
        if _existing_module_path_or_none(root, target) is not None
    }
    collisions = [
        target
        for source, target in adopted.items()
        if not _facade_points_to(root / str(ownership[source]["path"]), target)
    ]
    if collisions:
        raise ValueError("Domain migration targets already exist: " + ", ".join(sorted(collisions)))
    dynamic = _dynamic_imports(root, selected, ownership)
    if dynamic:
        raise ValueError("Selected modules use dynamic internal imports: " + ", ".join(dynamic))

    active_rewrites = _active_rewrite_count(root, wrapper_targets, selected)
    detail = {
        "contexts": sorted(contexts),
        "module_count": len(selected),
        "active_caller_rewrite_count": active_rewrites,
        "adopted_module_count": len(adopted),
        "selected_modules": dict(sorted(selected.items())),
    }
    if plan:
        print(json.dumps(detail, ensure_ascii=False, indent=2))
        return 0

    exports: dict[str, list[str]] = {}
    for source_module, target_module in sorted(selected.items()):
        source_path = root / str(ownership[source_module]["path"])
        target_existing = _existing_module_path_or_none(root, target_module)
        source = (
            target_existing.read_text(encoding="utf-8")
            if source_module in adopted and target_existing is not None
            else source_path.read_text(encoding="utf-8")
        )
        exports[source_module] = _module_exports(source)
        if source_module in adopted:
            continue
        rewritten = _rewrite_domain_source(
            source,
            source_module=source_module,
            source_is_package=source_path.name == "__init__.py",
            selected=selected,
            ownership=ownership,
            target_wrappers=target_wrappers,
        )
        target_path = _module_path(root, target_module, source_path.name == "__init__.py")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_packages(root, target_path.parent)
        target_path.write_text(rewritten, encoding="utf-8")

    _rewrite_active_callers(root, wrapper_targets, selected)
    _canonicalize_domain_imports(root)

    for source_module, target_module in sorted(selected.items()):
        source_path = root / str(ownership[source_module]["path"])
        source_path.write_text(_facade_source(source_module, target_module, exports[source_module]), encoding="utf-8")
        wrapper_module = target_wrappers.get(source_module)
        if wrapper_module:
            wrapper_path = _module_path(root, wrapper_module)
            wrapper_path.write_text(
                _facade_source(wrapper_module, target_module, exports[source_module], application_boundary=True),
                encoding="utf-8",
            )
    _canonicalize_domain_imports(root)

    manifest = _read_manifest(root)
    manifest.setdefault("schema_version", 1)
    manifest.setdefault("baseline_tag", "v13.8.0")
    manifest.setdefault("waves", [])
    manifest["waves"].append(
        {
            "contexts": sorted(contexts),
            "module_count": len(selected),
            "active_caller_rewrite_count": active_rewrites,
            "modules": [
                {
                    "source": source,
                    "target": target,
                    "exports_hash": _stable_hash(exports[source]),
                    "export_count": len(exports[source]),
                }
                for source, target in sorted(selected.items())
            ],
        }
    )
    (root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(detail, ensure_ascii=False, sort_keys=True))
    return 0


def repair_facades(root: Path) -> int:
    manifest = _read_manifest(root)
    modules = [row for wave in manifest.get("waves") or [] for row in wave.get("modules") or []]
    wrapper_targets = _wrapper_targets(root)
    target_wrappers = {target: wrapper for wrapper, target in wrapper_targets.items()}
    changed = 0
    for row in modules:
        source_module = str(row["source"])
        target_module = str(row["target"])
        target_path = _existing_module_path(root, target_module)
        exports = _module_exports(target_path.read_text(encoding="utf-8"))
        source_path = _existing_module_path(root, source_module)
        source_path.write_text(_facade_source(source_module, target_module, exports), encoding="utf-8")
        wrapper_module = target_wrappers.get(target_module)
        if wrapper_module:
            _module_path(root, wrapper_module).write_text(
                _facade_source(wrapper_module, target_module, exports, application_boundary=True),
                encoding="utf-8",
            )
        row["exports_hash"] = _stable_hash(exports)
        row["export_count"] = len(exports)
        changed += 1
    (root / MANIFEST).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _canonicalize_domain_imports(root)
    print(f"repaired domain facades: {changed}")
    return 0


def _wrapper_targets(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    directory = root / "song_agent" / "application" / "legacy_dependencies"
    for path in sorted(directory.glob("*.py")):
        module = ".".join(path.relative_to(root).with_suffix("").parts)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname == "_implementation" and alias.name.startswith("song_agent."):
                        result[module] = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("song_agent.domains."):
                result[module] = node.module
    return result


def _target_wrappers(root: Path, wrapper_targets: dict[str, str]) -> dict[str, str]:
    result = {target: wrapper for wrapper, target in wrapper_targets.items()}
    manifest = _read_manifest(root)
    for wave in manifest.get("waves") or []:
        for row in wave.get("modules") or []:
            source = str(row.get("source") or "")
            target = str(row.get("target") or "")
            if source and target:
                result[source] = target
    return result


def _canonicalize_domain_imports(root: Path) -> int:
    replacements = {
        wrapper: target
        for wrapper, target in _wrapper_targets(root).items()
        if target.startswith("song_agent.domains.")
    }
    changed = 0
    for path in sorted((root / "song_agent" / "domains").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        updated = _rewrite_imports(source, replacements)
        if updated != source:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def _missing_cross_boundaries(
    root: Path,
    selected: dict[str, str],
    ownership: dict[str, dict[str, Any]],
    target_wrappers: dict[str, str],
) -> set[str]:
    known = set(ownership)
    missing: set[str] = set()
    for module in selected:
        path = root / str(ownership[module]["path"])
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for target in _import_targets(tree):
            known_target = _known_module(target, known)
            if not known_target or known_target in selected:
                continue
            row = ownership[known_target]
            if row.get("layer") != "compatibility":
                continue
            if known_target == "song_agent" and target == "song_agent":
                continue
            if known_target not in target_wrappers:
                missing.add(f"{module}->{known_target}")
    return missing


def _dynamic_imports(
    root: Path,
    selected: dict[str, str],
    ownership: dict[str, dict[str, Any]],
) -> list[str]:
    result: list[str] = []
    for module in selected:
        path = root / str(ownership[module]["path"])
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args or not isinstance(node.args[0], ast.Constant):
                continue
            function = node.func
            if (
                isinstance(function, ast.Name) and function.id == "__import__"
            ) or (
                isinstance(function, ast.Attribute) and function.attr == "import_module"
            ):
                value = str(node.args[0].value)
                if value == "song_agent" or value.startswith("song_agent."):
                    result.append(f"{module}:{node.lineno}:{value}")
    return result


def _active_rewrite_count(root: Path, wrappers: dict[str, str], selected: dict[str, str]) -> int:
    selected_targets = set(selected.values())
    selected_wrappers = {
        wrapper
        for wrapper, target in wrappers.items()
        if target in selected or target in selected_targets
    }
    count = 0
    for path in (root / "song_agent").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        count += sum(source.count(wrapper) for wrapper in selected_wrappers)
    return count


def _rewrite_active_callers(root: Path, wrappers: dict[str, str], selected: dict[str, str]) -> None:
    selected_targets = set(selected.values())
    replacements = {
        wrapper: selected[target] if target in selected else target
        for wrapper, target in wrappers.items()
        if target in selected or target in selected_targets
    }
    if not replacements:
        return
    for path in sorted((root / "song_agent").rglob("*.py")):
        if "domains" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        updated = _rewrite_imports(source, replacements)
        if updated != source:
            path.write_text(updated, encoding="utf-8")


def _rewrite_domain_source(
    source: str,
    *,
    source_module: str,
    source_is_package: bool,
    selected: dict[str, str],
    ownership: dict[str, dict[str, Any]],
    target_wrappers: dict[str, str],
) -> str:
    replacements = dict(selected)
    for module, row in ownership.items():
        if row.get("layer") == "compatibility" and module not in selected and module in target_wrappers:
            replacements[module] = target_wrappers[module]
    relative_replacements = dict(replacements)
    source_context = str(ownership[source_module]["context"])
    for module, target in selected.items():
        if str(ownership[module]["context"]) != source_context:
            relative_replacements[module] = target_wrappers[module]
    updated = _rewrite_relative_imports(
        source,
        source_module=source_module,
        source_is_package=source_is_package,
        replacements=relative_replacements,
    )
    updated = _rewrite_imports(updated, replacements)
    updated = updated.replace(
        "from song_agent import __version__",
        "from song_agent.platform.version import VERSION as __version__",
    )
    ast.parse(updated, filename=source_module)
    return updated


def _rewrite_relative_imports(
    source: str,
    *,
    source_module: str,
    source_is_package: bool,
    replacements: dict[str, str],
) -> str:
    tree = ast.parse(source)
    offsets = _line_offsets(source)
    package = source_module if source_is_package else source_module.rpartition(".")[0]
    edits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.level:
            continue
        package_parts = package.split(".")
        parent_count = node.level - 1
        if parent_count >= len(package_parts):
            raise ValueError(f"Relative import escapes package in {source_module}:{node.lineno}")
        base = package_parts[: len(package_parts) - parent_count]
        resolved = ".".join([*base, *([node.module] if node.module else [])])
        updated = copy.deepcopy(node)
        updated.level = 0
        updated.module = _replace_module(resolved, replacements)
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[int(node.end_lineno or node.lineno) - 1] + int(node.end_col_offset or 0)
        edits.append((start, end, ast.unparse(updated)))
    result = source
    for start, end, replacement in sorted(edits, reverse=True):
        result = f"{result[:start]}{replacement}{result[end:]}"
    return result


def _rewrite_imports(source: str, replacements: dict[str, str]) -> str:
    tree = ast.parse(source)
    offsets = _line_offsets(source)
    edits: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        changed = False
        updated = copy.deepcopy(node)
        if isinstance(node, ast.ImportFrom) and not node.level and node.module:
            target = _replace_module(node.module, replacements)
            if target != node.module:
                updated.module = target
                changed = True
        elif isinstance(node, ast.Import):
            for alias in updated.names:
                target = _replace_module(alias.name, replacements)
                if target != alias.name:
                    alias.name = target
                    changed = True
        if not changed or not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        start = offsets[node.lineno - 1] + node.col_offset
        end = offsets[int(node.end_lineno or node.lineno) - 1] + int(node.end_col_offset or 0)
        edits.append((start, end, ast.unparse(updated)))
    result = source
    for start, end, replacement in sorted(edits, reverse=True):
        result = f"{result[:start]}{replacement}{result[end:]}"
    return result


def _replace_module(module: str, replacements: dict[str, str]) -> str:
    for source in sorted(replacements, key=len, reverse=True):
        if module == source:
            return replacements[source]
        if module.startswith(source + "."):
            return replacements[source] + module[len(source) :]
    return module


def _module_exports(source: str) -> list[str]:
    tree = ast.parse(source)
    result = _statement_bindings(tree.body)
    return sorted(name for name in result if not name.startswith("__"))


def _statement_bindings(statements: list[ast.stmt]) -> set[str]:
    result: set[str] = set()
    for node in statements:
        if isinstance(node, ast.Import):
            result.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                result.update(_target_bindings(target))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            result.update(_target_bindings(node.target))
            result.update(_statement_bindings([*node.body, *node.orelse]))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    result.update(_target_bindings(item.optional_vars))
            result.update(_statement_bindings(node.body))
        elif isinstance(node, ast.If):
            result.update(_statement_bindings([*node.body, *node.orelse]))
        elif isinstance(node, (ast.While, ast.Try, ast.TryStar)):
            bodies = [*node.body, *node.orelse]
            if isinstance(node, (ast.Try, ast.TryStar)):
                bodies.extend(node.finalbody)
                for handler in node.handlers:
                    if handler.name:
                        result.add(handler.name)
                    bodies.extend(handler.body)
            result.update(_statement_bindings(bodies))
    return result


def _target_bindings(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {name for element in target.elts for name in _target_bindings(element)}
    return set()


def _facade_source(
    facade_module: str,
    target_module: str,
    exports: list[str],
    *,
    application_boundary: bool = False,
) -> str:
    role = "Application boundary" if application_boundary else "Compatibility facade"
    rows = [f'"""{role} for {target_module}."""\n', "\n"]
    if exports:
        rows.append(f"from {target_module} import {', '.join(exports)}\n")
    rows.extend(["\n", f"__all__ = {tuple(exports)!r}\n"])
    source = "".join(rows)
    ast.parse(source, filename=facade_module)
    return source


def _domain_module(context: str, module: str) -> str:
    suffix = module.removeprefix("song_agent.")
    return f"song_agent.domains.{context}.{suffix}"


def _module_path(root: Path, module: str, package: bool = False) -> Path:
    base = root.joinpath(*module.split("."))
    return base / "__init__.py" if package else base.with_suffix(".py")


def _existing_module_path(root: Path, module: str) -> Path:
    base = root.joinpath(*module.split("."))
    module_path = base.with_suffix(".py")
    return module_path if module_path.is_file() else base / "__init__.py"


def _existing_module_path_or_none(root: Path, module: str) -> Path | None:
    path = _existing_module_path(root, module)
    return path if path.is_file() else None


def _facade_points_to(path: Path, target_module: str) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parent, _, leaf = target_module.rpartition(".")
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == target_module:
                return True
            if node.module == parent and any(alias.name == leaf for alias in node.names):
                return True
        if isinstance(node, ast.Import) and any(alias.name == target_module for alias in node.names):
            return True
    return False


def _ensure_packages(root: Path, directory: Path) -> None:
    package_root = root / "song_agent"
    current = directory
    while current != package_root and package_root in current.parents:
        init = current / "__init__.py"
        if not init.exists():
            init.write_text('"""MusicForge domain package."""\n', encoding="utf-8")
        current = current.parent


def _import_targets(tree: ast.AST) -> list[str]:
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            result.append(node.module)
    return result


def _known_module(value: str, known: set[str]) -> str | None:
    candidate = value
    while candidate:
        if candidate in known:
            return candidate
        candidate = candidate.rpartition(".")[0]
    return None


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for index, value in enumerate(source):
        if value == "\n":
            offsets.append(index + 1)
    return offsets


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _read_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate v14 compatibility implementations into domain packages.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--contexts", nargs="+", default=[])
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--repair-facades", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.repair_facades:
        return repair_facades(root)
    if not args.contexts:
        parser.error("--contexts is required unless --repair-facades is used")
    return migrate(root, set(args.contexts), plan=args.plan)


if __name__ == "__main__":
    raise SystemExit(main())
