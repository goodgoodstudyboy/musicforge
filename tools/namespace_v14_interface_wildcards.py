from __future__ import annotations

import argparse
import ast
import builtins
from collections import defaultdict
import importlib
import re
from pathlib import Path
from typing import Any


INTERFACES = Path("song_agent/interfaces")


def migrate(root: Path, *, check: bool = False) -> int:
    files = sorted((root / INTERFACES).rglob("*.py"))
    documents = {path: path.read_text(encoding="utf-8") for path in files}
    trees = {path: ast.parse(source, filename=str(path)) for path, source in documents.items()}
    stars: dict[Path, list[ast.ImportFrom]] = {
        path: [
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names)
        ]
        for path, tree in trees.items()
    }
    stars = {path: nodes for path, nodes in stars.items() if nodes}
    if check:
        count = sum(len(nodes) for nodes in stars.values())
        if count:
            print(f"interface wildcard imports remaining: {count}")
            return 1
        print("interface wildcard imports remaining: 0")
        return 0

    importlib.import_module("song_agent.interfaces.api.server")
    importlib.import_module("song_agent.interfaces.cli.app")
    exports: dict[str, tuple[str, ...]] = {}
    for path, nodes in stars.items():
        source_module = _module_name(root, path)
        for node in nodes:
            target = _absolute_import(source_module, node)
            module = importlib.import_module(target)
            names = getattr(module, "__all__", None)
            if names is None:
                names = [name for name in vars(module) if not name.startswith("_")]
            exports[target] = tuple(dict.fromkeys(str(name) for name in names if str(name).isidentifier()))

    star_targets = {
        _absolute_import(_module_name(root, path), node)
        for path, nodes in stars.items()
        for node in nodes
    }
    changed = 0
    for path, nodes in stars.items():
        source = documents[path]
        tree = trees[path]
        source_module = _module_name(root, path)
        preserve = (
            source_module in star_targets
            or _has_explicit_all(tree)
            or _has_specs(tree)
            or path.name in {"runtime.py", "server.py"}
            or path.name == "dependencies.py"
        )
        aliases: dict[int, str] = {}
        used_aliases: set[str] = set()
        symbol_sources: dict[str, str] = {}
        for position, node in enumerate(nodes):
            target = _absolute_import(source_module, node)
            alias = _alias_for(target, position, used_aliases)
            aliases[id(node)] = alias
            for name in exports[target]:
                symbol_sources[name] = alias

        explicit = _module_bindings(tree)
        symbol_sources = {name: alias for name, alias in symbol_sources.items() if name not in explicit}
        inserts: list[tuple[int, str]] = []
        replacements: list[tuple[int, int, str]] = []
        offsets = _line_offsets(source)
        for node in nodes:
            target = _absolute_import(source_module, node)
            alias = aliases[id(node)]
            replacement = _namespace_import(node, alias)
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[int(node.end_lineno or node.lineno) - 1] + int(node.end_col_offset or 0)
            if preserve:
                assignments = "".join(f"\n{name} = {alias}.{name}" for name in exports[target])
                replacement += assignments
            replacements.append((start, end, replacement))
        if not preserve:
            for node in _module_name_loads(tree, set(symbol_sources)):
                inserts.append((offsets[node.lineno - 1] + node.col_offset, f"{symbol_sources[node.id]}."))
        updated = source
        for start, end, replacement in sorted(replacements, reverse=True):
            updated = f"{updated[:start]}{replacement}{updated[end:]}"
        for position, value in sorted(inserts, reverse=True):
            shift = sum(
                len(replacement) - (end - start)
                for start, end, replacement in replacements
                if start < position
            )
            adjusted = position + shift
            updated = f"{updated[:adjusted]}{value}{updated[adjusted:]}"
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
        changed += 1
    print(f"namespaced interface wildcard imports: {sum(map(len, stars.values()))} across {changed} files")
    return 0


def normalize_api_runtime(root: Path) -> int:
    changed = 0
    pattern = re.compile(
        r"^from song_agent\.interfaces\.api import runtime as (?P<alias>[A-Za-z_]\w*)$",
        re.MULTILINE,
    )
    for path in sorted((root / INTERFACES).rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        updated = pattern.sub(
            lambda match: f"import song_agent.interfaces.api.runtime as {match.group('alias')}",
            source,
        )
        if updated != source:
            ast.parse(updated, filename=str(path))
            path.write_text(updated, encoding="utf-8")
            changed += 1

    server_path = root / "song_agent" / "server.py"
    source = server_path.read_text(encoding="utf-8")
    source = source.replace(
        "from song_agent.interfaces.api import runtime as _runtime",
        "import song_agent.interfaces.api.runtime as _runtime",
    )
    wildcard = "from song_agent.interfaces.api.runtime import *"
    runtime = importlib.import_module("song_agent.interfaces.api.runtime")
    names = tuple(dict.fromkeys(str(name) for name in runtime.__all__ if str(name).isidentifier()))
    exports = _compact_runtime_exports(names)
    if wildcard in source:
        source = source.replace(wildcard, exports, 1)
    else:
        marker = "from song_agent.interfaces.api.server import "
        marker_index = source.index(marker)
        prefix_end = source.index("\n", source.index("import song_agent.interfaces.api.runtime as _runtime")) + 1
        source = f"{source[:prefix_end]}{exports}\n{source[marker_index:]}"
    ast.parse(source, filename=str(server_path))
    server_path.write_text(source, encoding="utf-8")
    changed += 1
    print(f"normalized API runtime imports: {changed}")
    return 0


def compact_static_reexports(root: Path) -> int:
    assignment = re.compile(
        r"^(?P<name>[A-Za-z_]\w*) = (?P<alias>_[A-Za-z_]\w*)\.(?P=name)\r?\n?$"
    )
    import_alias = re.compile(r"^(?P<import>.*\s+as\s+(?P<alias>_[A-Za-z_]\w*))\r?\n?$")
    changed = 0
    for path in sorted((root / INTERFACES).rglob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        output: list[str] = []
        index = 0
        modified = False
        while index < len(lines):
            match = import_alias.match(lines[index])
            if match is None:
                output.append(lines[index])
                index += 1
                continue
            alias = match.group("alias")
            names: list[str] = []
            cursor = index + 1
            while cursor < len(lines):
                row = assignment.match(lines[cursor])
                if row is None or row.group("alias") != alias:
                    break
                names.append(row.group("name"))
                cursor += 1
            if not names:
                output.append(lines[index])
                index += 1
                continue
            left = ", ".join(names)
            right = ", ".join(f"{alias}.{name}" for name in names)
            output.append(f"{match.group('import')}; {left} = {right}\n")
            index = cursor
            modified = True
        if not modified:
            continue
        updated = "".join(output)
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
        changed += 1
    print(f"compacted static interface reexports: {changed}")
    return 0


def _compact_runtime_exports(names: tuple[str, ...], size: int = 100_000) -> str:
    rows: list[str] = []
    for index in range(0, len(names), size):
        chunk = names[index : index + size]
        left = ", ".join(chunk)
        right = ", ".join(f"_runtime.{name}" for name in chunk)
        rows.append(f"{left} = {right}")
    return "\n".join(rows)


def _module_name(root: Path, path: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def _absolute_import(source_module: str, node: ast.ImportFrom) -> str:
    if not node.level:
        return str(node.module)
    package = source_module.split(".")[:-1]
    anchor = package[: len(package) - node.level + 1]
    return ".".join([*anchor, *((node.module or "").split("."))])


def _alias_for(target: str, position: int, used: set[str]) -> str:
    parts = target.split(".")
    base = "_" + "_".join(parts[-3:])
    base = re.sub(r"\W+", "_", base)
    alias = base
    suffix = position + 1
    while alias in used:
        alias = f"{base}_{suffix}"
        suffix += 1
    used.add(alias)
    return alias


def _namespace_import(node: ast.ImportFrom, alias: str) -> str:
    module = str(node.module)
    parts = module.split(".")
    leaf = parts[-1]
    parent = ".".join(parts[:-1])
    dots = "." * node.level
    owner = f"{dots}{parent}" if parent else dots
    return f"from {owner} import {leaf} as {alias}"


def _has_explicit_all(tree: ast.Module) -> bool:
    return any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(name.id == "__all__" for name in ast.walk(node) if isinstance(name, ast.Name))
        for node in tree.body
    )


def _has_specs(tree: ast.Module) -> bool:
    return any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(name.id == "SPECS" for name in ast.walk(node) if isinstance(name, ast.Name))
        for node in tree.body
    )


def _module_bindings(tree: ast.Module) -> set[str]:
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                continue
            result.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            result.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result.add(node.name)
        else:
            result.update(name.id for name in ast.walk(node) if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store))
    return result


def _module_name_loads(tree: ast.Module, candidates: set[str]) -> list[ast.Name]:
    visitor = _GlobalLoadVisitor(candidates)
    visitor.visit(tree)
    return visitor.loads


class _GlobalLoadVisitor(ast.NodeVisitor):
    def __init__(self, candidates: set[str]) -> None:
        self.candidates = candidates
        self.loads: list[ast.Name] = []
        self.local_scopes: list[set[str]] = []

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load) and node.id in self.candidates:
            if not any(node.id in scope for scope in self.local_scopes):
                self.loads.append(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        if node.returns is not None:
            self.visit(node.returns)
        local = _function_bindings(node)
        self.local_scopes.append(local)
        for statement in node.body:
            self.visit(statement)
        self.local_scopes.pop()

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        local = {arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
        if node.args.vararg:
            local.add(node.args.vararg.arg)
        if node.args.kwarg:
            local.add(node.args.kwarg.arg)
        self.local_scopes.append(local)
        self.visit(node.body)
        self.local_scopes.pop()


class _BindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()
        self.globals: set[str] = set()

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Store):
            self.names.add(node.id)

    def visit_Global(self, node: ast.Global) -> Any:
        self.globals.update(node.names)

    def visit_Import(self, node: ast.Import) -> Any:
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        self.names.update(alias.asname or alias.name for alias in node.names if alias.name != "*")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        return None


def _function_bindings(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    collector = _BindingCollector()
    for statement in node.body:
        collector.visit(statement)
    result = collector.names - collector.globals
    result.update(arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])
    if node.args.vararg:
        result.add(node.args.vararg.arg)
    if node.args.kwarg:
        result.add(node.args.kwarg.arg)
    return result


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for match in re.finditer("\n", source):
        offsets.append(match.end())
    return offsets


def main() -> int:
    parser = argparse.ArgumentParser(description="Replace interface wildcard imports with static namespaces.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--normalize-api-runtime", action="store_true")
    parser.add_argument("--compact-reexports", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.normalize_api_runtime:
        return normalize_api_runtime(root)
    if args.compact_reexports:
        return compact_static_reexports(root)
    return migrate(root, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
