from __future__ import annotations

import argparse
import ast
import subprocess
import textwrap
from pathlib import Path


DEFAULT_CONTEXTS = (
    "creation",
    "quality",
    "delivery",
    "trust",
    "program",
    "maintenance",
    "release_check",
)


def split_module(path: Path, *, target_lines: int = 420, source: str | None = None) -> list[Path]:
    source = path.read_text(encoding="utf-8") if source is None else source
    lines = source.splitlines()
    tree = ast.parse(source, filename=str(path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if not functions:
        raise ValueError(f"Refusing to split an already aggregated command module: {path}")
    dependencies = {
        name: {
            item.id
            for item in ast.walk(node)
            if isinstance(item, ast.Name) and item.id in functions and item.id != name
        }
        for name, node in functions.items()
    }
    ordered = _dependency_order(functions, dependencies)
    groups = _pack(ordered, functions, target_lines)
    owner = {name: index for index, group in enumerate(groups, start=1) for name in group}
    import_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]
    owners: dict[str, set[tuple[str, str]]] = {}
    for node in import_nodes:
        module = str(node.module or "") if isinstance(node, ast.ImportFrom) else ""
        for alias in node.names:
            name = alias.asname or (alias.name.split(".", 1)[0] if isinstance(node, ast.Import) else alias.name)
            owners.setdefault(name, set()).add((module, alias.name))
    conflicts = {name for name, rows in owners.items() if len(rows) > 1}
    promoted = [
        node
        for node in import_nodes
        if all(
            (alias.asname or (alias.name.split(".", 1)[0] if isinstance(node, ast.Import) else alias.name)) not in conflicts
            for alias in node.names
        )
    ]
    imports = list(
        dict.fromkeys(
            textwrap.dedent("\n".join(lines[node.lineno - 1 : node.end_lineno])) for node in promoted
        )
    )
    promoted_lines = {
        line
        for node in promoted
        if node not in tree.body
        for line in range(node.lineno, int(node.end_lineno or node.lineno) + 1)
    }
    promoted_first_lines = {node.lineno for node in promoted if node not in tree.body}
    assignments = [
        "\n".join(lines[node.lineno - 1 : node.end_lineno])
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
    ]

    parts_dir = path.with_name(f"{path.stem}_parts")
    parts_dir.mkdir(exist_ok=True)
    for old in parts_dir.glob("part_*.py"):
        old.unlink()
    if (parts_dir / "dependency_parts").exists():
        for old in (parts_dir / "dependency_parts").glob("*.py"):
            old.unlink()
    (parts_dir / "__init__.py").write_text('"""Generated command implementation parts."""\n', encoding="utf-8")
    dependency_names = sorted(
        {
            alias.asname or (alias.name.split(".", 1)[0] if isinstance(node, ast.Import) else alias.name)
            for node in promoted
            for alias in node.names
            if alias.name != "*"
        }
    )
    dependency_dir = parts_dir / "dependency_parts"
    dependency_dir.mkdir(exist_ok=True)
    (dependency_dir / "__init__.py").write_text('"""Bounded command dependency modules."""\n', encoding="utf-8")
    dependency_imports: list[str] = []
    for index, group in enumerate(_pack_imports(imports, 320), start=1):
        names = sorted(name for name in dependency_names if any(_import_binds(item, name) for item in group))
        document = "\n\n".join(
            ["from __future__ import annotations", *group, f"__all__ = {names!r}"]
        ) + "\n"
        (dependency_dir / f"part_{index:03d}.py").write_text(document, encoding="utf-8")
        dependency_imports.append(f"from .dependency_parts.part_{index:03d} import *")
    dependency_source = "\n\n".join(
        [
            "from __future__ import annotations",
            *dependency_imports,
            f"__all__ = {dependency_names!r}",
        ]
    ) + "\n"
    (parts_dir / "dependencies.py").write_text(dependency_source, encoding="utf-8")

    outputs: list[Path] = []
    for index, group in enumerate(groups, start=1):
        cross = sorted({dependency for name in group for dependency in dependencies[name] if owner[dependency] != index})
        cross_imports = []
        for dependency_index in sorted({owner[name] for name in cross}):
            names = sorted(name for name in cross if owner[name] == dependency_index)
            cross_imports.append(
                f"from .part_{dependency_index:03d} import " + ", ".join(names)
            )
        bodies = [
            _function_source(functions[name], lines, promoted_lines, promoted_first_lines)
            for name in group
        ]
        document = "\n\n".join(
            [
                "from __future__ import annotations",
                f"from .dependencies import *",
                *cross_imports,
                *bodies,
                "__all__ = " + repr(tuple(group)),
            ]
        ) + "\n"
        output = parts_dir / f"part_{index:03d}.py"
        output.write_text(document, encoding="utf-8")
        outputs.append(output)

    part_imports = [f"from .{path.stem}_parts.part_{index:03d} import *" for index in range(1, len(groups) + 1)]
    aggregator = "\n\n".join(
        [
            "from __future__ import annotations",
            f"from .{path.stem}_parts.dependencies import *",
            *part_imports,
            *assignments,
            "for _spec in SPECS:\n    _spec.parser.__module__ = __name__\n    _spec.handler.__module__ = __name__",
        ]
    ) + "\n"
    path.write_text(aggregator, encoding="utf-8")
    return outputs


def _dependency_order(
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    dependencies: dict[str, set[str]],
) -> list[str]:
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"CLI command dependency cycle: {name}")
        visiting.add(name)
        for dependency in sorted(dependencies[name]):
            visit(dependency)
        visiting.remove(name)
        visited.add(name)
        ordered.append(name)

    for name in functions:
        visit(name)
    return ordered


def _pack(
    ordered: list[str],
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    target_lines: int,
) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    current_lines = 0
    for name in ordered:
        node = functions[name]
        size = int(node.end_lineno or node.lineno) - _source_start(node) + 2
        if current and current_lines + size > target_lines:
            groups.append(current)
            current = []
            current_lines = 0
        current.append(name)
        current_lines += size
    if current:
        groups.append(current)
    return groups


def _source_start(node: ast.AST) -> int:
    decorators = getattr(node, "decorator_list", ())
    return min([node.lineno, *(item.lineno for item in decorators)])


def _function_source(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    lines: list[str],
    promoted_lines: set[int],
    promoted_first_lines: set[int],
) -> str:
    start = _source_start(node)
    end = int(node.end_lineno or node.lineno)
    selected = list(lines[start - 1 : end])
    for offset, line_number in enumerate(range(start, end + 1)):
        if line_number in promoted_first_lines:
            original = selected[offset]
            selected[offset] = original[: len(original) - len(original.lstrip())] + "pass"
        elif line_number in promoted_lines:
            selected[offset] = ""
    return "\n".join(selected)


def _pack_imports(imports: list[str], target_lines: int) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] = []
    count = 0
    for source in imports:
        size = len(source.splitlines()) + 2
        if current and count + size > target_lines:
            groups.append(current)
            current, count = [], 0
        current.append(source)
        count += size
    if current:
        groups.append(current)
    return groups


def _import_binds(source: str, name: str) -> bool:
    node = ast.parse(textwrap.dedent(source)).body[0]
    if isinstance(node, ast.Import):
        return any((alias.asname or alias.name.split(".", 1)[0]) == name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return any((alias.asname or alias.name) == name for alias in node.names)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Split generated CLI command modules at function boundaries.")
    parser.add_argument("contexts", nargs="*", default=DEFAULT_CONTEXTS)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--target-lines", type=int, default=330)
    parser.add_argument("--git-ref")
    args = parser.parse_args()
    commands = args.root.resolve() / "song_agent" / "interfaces" / "cli" / "commands"
    for context in args.contexts:
        path = commands / f"{context}.py"
        source = None
        if args.git_ref:
            relative = path.relative_to(args.root.resolve()).as_posix()
            source = subprocess.run(
                ["git", "show", f"{args.git_ref}:{relative}"],
                cwd=args.root.resolve(),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            ).stdout
        outputs = split_module(path, target_lines=args.target_lines, source=source)
        print(f"{context}: {len(outputs)} parts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
