from __future__ import annotations

import argparse
import ast
import importlib
from pathlib import Path
from typing import Any


INTERFACES = Path("song_agent/interfaces")
RUNTIME_IMPORT = "song_agent.interfaces.api.runtime"
RUNTIME_ALIAS = "_interfaces_api_runtime"
SERVER_DIRECT_TYPES = frozenset({"Any", "AuthConfig", "BaseHTTPRequestHandler", "ThreadingHTTPServer"})


def normalize(root: Path, *, check: bool = False) -> int:
    server_types = _normalize_server_type_bindings(root, check=check)
    typing_any = _normalize_typing_any(root, check=check)
    compact = _normalize_compact_bindings(root, check=check)
    references = _repair_runtime_references(root, check=check)
    if check and (server_types or typing_any or compact or references):
        print(
            "interface bindings stale: "
            f"server_types={server_types}, typing_any={typing_any}, "
            f"compact={compact}, runtime_references={references}"
        )
        return 1
    print(
        "interface bindings normalized: "
        f"server_types={server_types}, typing_any={typing_any}, "
        f"compact={compact}, runtime_references={references}"
    )
    return 0


def _normalize_server_type_bindings(root: Path, *, check: bool) -> int:
    path = root / INTERFACES / "api" / "server.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    assignment = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and SERVER_DIRECT_TYPES.intersection(_assignment_names(node.targets[0]))
        ),
        None,
    )
    imports = {
        (node.module or "", alias.name)
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    required = {
        ("http.server", "BaseHTTPRequestHandler"),
        ("http.server", "ThreadingHTTPServer"),
        ("typing", "Any"),
        ("song_agent.domains.creation.auth", "AuthConfig"),
    }
    if assignment is None and required.issubset(imports):
        return 0
    if check:
        return 1
    if assignment is None:
        raise ValueError("Interface server runtime binding assignment is missing.")

    names = _assignment_names(assignment.targets[0])
    values = _assignment_values(assignment.value)
    retained = [(name, value) for name, value in zip(names, values, strict=True) if name not in SERVER_DIRECT_TYPES]
    lines = source.splitlines(keepends=True)
    left = ", ".join(name for name, _value in retained)
    right = ", ".join(ast.unparse(value) for _name, value in retained)
    lines[assignment.lineno - 1 : int(assignment.end_lineno or assignment.lineno)] = [f"{left} = {right}\n"]

    future = next(
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "__future__"
    )
    insertion = [
        "\n",
        "from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\n",
        "from typing import Any\n",
        "\n",
        "from song_agent.domains.creation.auth import AuthConfig\n",
    ]
    lines[int(future.end_lineno or future.lineno) : int(future.end_lineno or future.lineno)] = insertion
    updated = "".join(lines)
    ast.parse(updated, filename=str(path))
    path.write_text(updated, encoding="utf-8")
    return 1


def _normalize_typing_any(root: Path, *, check: bool) -> int:
    changed = 0
    for path in sorted((root / INTERFACES / "api").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if f"{RUNTIME_ALIAS}.Any" not in source:
            continue
        changed += 1
        if check:
            continue
        updated = source.replace(f"{RUNTIME_ALIAS}.Any", "Any")
        tree = ast.parse(updated, filename=str(path))
        typing_import = next(
            (node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "typing"),
            None,
        )
        lines = updated.splitlines(keepends=True)
        if typing_import is not None:
            names = {alias.name for alias in typing_import.names}
            if "Any" not in names:
                names.add("Any")
                lines[typing_import.lineno - 1 : int(typing_import.end_lineno or typing_import.lineno)] = [
                    f"from typing import {', '.join(sorted(names))}\n"
                ]
        else:
            future = next(
                node
                for node in tree.body
                if isinstance(node, ast.ImportFrom) and node.module == "__future__"
            )
            lines[int(future.end_lineno or future.lineno) : int(future.end_lineno or future.lineno)] = [
                "\n",
                "from typing import Any\n",
            ]
        result = "".join(lines)
        ast.parse(result, filename=str(path))
        path.write_text(result, encoding="utf-8")
    return changed


def _normalize_compact_bindings(root: Path, *, check: bool) -> int:
    changed = 0
    for path in sorted((root / INTERFACES).rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        pairs: list[tuple[ast.Import | ast.ImportFrom, ast.Assign, str]] = []
        for first, second in zip(tree.body, tree.body[1:]):
            if not isinstance(first, (ast.Import, ast.ImportFrom)) or not isinstance(second, ast.Assign):
                continue
            if first.lineno != second.lineno or len(second.targets) != 1:
                continue
            alias = _single_import_alias(first)
            if alias and _binding_assignment(second, alias):
                pairs.append((first, second, alias))
        if not pairs:
            continue
        changed += 1
        if check:
            continue
        lines = source.splitlines(keepends=True)
        latest: dict[str, int] = {}
        for pair_index, (_imported, assigned, _alias) in enumerate(pairs):
            for name in _assignment_names(assigned.targets[0]):
                latest[name] = pair_index
        assignment_rows: list[str] = []
        for pair_index, (imported, assigned, alias) in enumerate(pairs):
            names = _assignment_names(assigned.targets[0])
            values = _assignment_values(assigned.value)
            selected: list[str] = []
            for name, value in zip(names, values, strict=True):
                if not isinstance(value, ast.Attribute) or not isinstance(value.value, ast.Name) or value.value.id != alias:
                    raise ValueError(f"Invalid compact interface binding at {path}:{assigned.lineno}")
                if latest[name] == pair_index:
                    selected.append(name)
            lines[imported.lineno - 1] = ast.unparse(imported) + "\n"
            if selected:
                left = ", ".join(selected)
                right = ", ".join(f"{alias}.{name}" for name in selected)
                assignment_rows.append(f"{left} = {right}\n")
        last_import_line = max(int(node.end_lineno or node.lineno) for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom)))
        compact_assignments = {id(assigned) for _imported, assigned, _alias in pairs}
        first_code_line = min(
            (node.lineno for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom)) and id(node) not in compact_assignments),
            default=last_import_line + 1,
        )
        blank_indexes = [index for index in range(first_code_line - 1) if not lines[index].strip()]
        if len(blank_indexes) < len(assignment_rows):
            raise ValueError(f"Interface import block lacks binding capacity: {path}")
        removed = set(blank_indexes[-len(assignment_rows) :]) if assignment_rows else set()
        output: list[str] = []
        for index, line in enumerate(lines):
            if index not in removed:
                output.append(line)
            if index == last_import_line - 1:
                output.extend(assignment_rows)
        updated = "".join(output)
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
    return changed


def _repair_runtime_references(root: Path, *, check: bool) -> int:
    runtime = importlib.import_module(RUNTIME_IMPORT)
    runtime_names = {name for name in vars(runtime) if name.isidentifier()}
    changed = 0
    for path in sorted((root / INTERFACES / "api").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        if not _imports_runtime_alias(tree):
            continue
        candidates = runtime_names - _module_bindings(tree)
        visitor = _GlobalLoadVisitor(candidates)
        visitor.visit(tree)
        if not visitor.loads:
            continue
        changed += 1
        if check:
            continue
        offsets = _line_offsets(source)
        positions = sorted({offsets[node.lineno - 1] + node.col_offset for node in visitor.loads}, reverse=True)
        updated = source
        for position in positions:
            updated = f"{updated[:position]}{RUNTIME_ALIAS}.{updated[position:]}"
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
    return changed


def _single_import_alias(node: ast.Import | ast.ImportFrom) -> str | None:
    if len(node.names) != 1:
        return None
    return node.names[0].asname


def _binding_assignment(node: ast.Assign, alias: str) -> bool:
    names = _assignment_names(node.targets[0])
    values = _assignment_values(node.value)
    return bool(names) and len(names) == len(values) and all(
        isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name) and value.value.id == alias and value.attr == name
        for name, value in zip(names, values, strict=True)
    )


def _assignment_names(node: ast.expr) -> list[str]:
    rows = node.elts if isinstance(node, (ast.Tuple, ast.List)) else [node]
    return [row.id for row in rows if isinstance(row, ast.Name)]


def _assignment_values(node: ast.expr) -> list[ast.expr]:
    return list(node.elts) if isinstance(node, (ast.Tuple, ast.List)) else [node]


def _imports_runtime_alias(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.Import)
        and any(alias.name == RUNTIME_IMPORT and alias.asname == RUNTIME_ALIAS for alias in node.names)
        for node in tree.body
    )


def _module_bindings(tree: ast.Module) -> set[str]:
    collector = _BindingCollector()
    for statement in tree.body:
        collector.visit(statement)
    return collector.names


class _GlobalLoadVisitor(ast.NodeVisitor):
    def __init__(self, candidates: set[str]) -> None:
        self.candidates = candidates
        self.loads: list[ast.Name] = []
        self.local_scopes: list[set[str]] = []

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Load) and node.id in self.candidates and not any(node.id in scope for scope in self.local_scopes):
            self.loads.append(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            if argument.annotation is not None:
                self.visit(argument.annotation)
        if node.args.vararg and node.args.vararg.annotation is not None:
            self.visit(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation is not None:
            self.visit(node.args.kwarg.annotation)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        if node.returns is not None:
            self.visit(node.returns)
        collector = _BindingCollector()
        for statement in node.body:
            collector.visit(statement)
        collector.names.update(argument.arg for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs])
        if node.args.vararg:
            collector.names.add(node.args.vararg.arg)
        if node.args.kwarg:
            collector.names.add(node.args.kwarg.arg)
        self.local_scopes.append(collector.names - collector.globals)
        for statement in node.body:
            self.visit(statement)
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


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for index, character in enumerate(source):
        if character == "\n":
            offsets.append(index + 1)
    return offsets


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize v14 static interface bindings and runtime references.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return normalize(args.root.resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
