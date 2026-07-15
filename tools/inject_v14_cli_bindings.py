from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path


COMMANDS = Path("song_agent/interfaces/cli/commands")
BINDINGS = Path("song_agent/interfaces/cli/bindings.py")
COMPOSITION = Path("song_agent/interfaces/cli/composition.py")
COMPOSITION_PARTS = Path("song_agent/interfaces/cli/composition_parts")


def migrate(root: Path, *, check: bool = False) -> int:
    wrappers = _wrappers(root)
    if check:
        if wrappers:
            print(f"local-import CLI adapters remaining: {len(wrappers)}")
            return 1
        print("local-import CLI adapters remaining: 0")
        return 0
    if not wrappers:
        print("injected CLI adapters: 0")
        return 0

    targets: dict[str, dict[str, str]] = defaultdict(dict)
    for _, node, module in wrappers:
        group = _target_group(module)
        existing = targets[group].get(node.name)
        if existing is not None and existing != module:
            raise ValueError(f"Ambiguous binding target: {group}.{node.name}")
        targets[group][node.name] = module

    (root / BINDINGS).write_text(_bindings_source(targets), encoding="utf-8")
    (root / COMPOSITION).write_text(_composition_source(targets), encoding="utf-8")

    by_path: dict[Path, list[ast.FunctionDef | ast.AsyncFunctionDef]] = defaultdict(list)
    for path, node, _ in wrappers:
        by_path[path].append(node)
    for path, nodes in by_path.items():
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        group_by_name = {
            node.name: _target_group(str(cast_import(node).module))
            for node in nodes
        }
        for node in sorted(nodes, key=lambda row: row.lineno, reverse=True):
            indent = " " * node.body[0].col_offset
            start = node.body[0].lineno - 1
            end = int(node.end_lineno or node.lineno)
            group = group_by_name[node.name]
            lines[start:end] = [f"{indent}return CLI_BINDINGS.{group}.{node.name}(*args, **kwargs)\n"]
        updated = "".join(lines)
        future_end = next(
            int(node.end_lineno or node.lineno)
            for node in ast.parse(updated).body
            if isinstance(node, ast.ImportFrom) and node.module == "__future__"
        )
        updated_lines = updated.splitlines(keepends=True)
        updated_lines.insert(future_end, "\nfrom song_agent.interfaces.cli.bindings import BINDINGS as CLI_BINDINGS\n")
        updated = "".join(updated_lines)
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
    print(f"injected CLI adapters: {len(wrappers)} across {len(by_path)} files")
    return 0


def flatten_composition(root: Path) -> int:
    path = root / COMPOSITION
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "configure_bindings"
    )
    lines = source.splitlines(keepends=True)
    body = [line[4:] if line.startswith("    ") else line for line in lines[function.body[0].lineno - 1 : int(function.end_lineno or function.lineno)]]
    lines[function.lineno - 1 : int(function.end_lineno or function.lineno)] = body
    updated = "".join(lines)
    ast.parse(updated, filename=str(path))
    path.write_text(updated, encoding="utf-8")
    print("flattened CLI composition")
    return 0


def split_composition(root: Path) -> int:
    path = root / COMPOSITION
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: dict[str, tuple[str, str]] = {}
    assignments: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname and node.module and node.module != "__future__" and alias.name != "BINDINGS":
                    imports[alias.asname] = (node.module, alias.name)
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "BINDINGS"
            and isinstance(node.value, ast.Name)
        ):
            continue
        group = target.value.attr
        assignments[group].append((target.attr, node.value.id))

    directory = root / COMPOSITION_PARTS
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "__init__.py").write_text('"""Static CLI composition grouped by bounded context."""\n', encoding="utf-8")
    root_rows = ["from __future__ import annotations\n", "\n"]
    for group, rows in sorted(assignments.items()):
        part_rows = [
            "from __future__ import annotations\n",
            "\n",
            "from song_agent.interfaces.cli.bindings import BINDINGS\n",
            "\n",
        ]
        for _, alias in rows:
            module, name = imports[alias]
            part_rows.append(f"from {module} import {name} as {alias}\n")
        part_rows.append("\n")
        for name, alias in rows:
            part_rows.append(f"BINDINGS.{group}.{name} = {alias}\n")
        part_path = directory / f"{group}.py"
        source = "".join(part_rows)
        ast.parse(source, filename=str(part_path))
        part_path.write_text(source, encoding="utf-8")
        root_rows.append(
            f"import song_agent.interfaces.cli.composition_parts.{group} as _{group}_composition\n"
        )
    source = "".join(root_rows)
    ast.parse(source, filename=str(path))
    path.write_text(source, encoding="utf-8")
    print(f"split CLI composition groups: {len(assignments)}")
    return 0


def _wrappers(root: Path) -> list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef, str]]:
    result: list[tuple[Path, ast.FunctionDef | ast.AsyncFunctionDef, str]] = []
    for path in sorted((root / COMMANDS).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or len(node.body) != 2:
                continue
            imported = node.body[0]
            returned = node.body[1]
            if not isinstance(imported, ast.ImportFrom) or len(imported.names) != 1:
                continue
            alias = imported.names[0]
            if alias.name != node.name or alias.asname != "implementation":
                continue
            if not isinstance(returned, ast.Return):
                continue
            result.append((path, node, str(imported.module)))
    return result


def cast_import(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.ImportFrom:
    imported = node.body[0]
    if not isinstance(imported, ast.ImportFrom):
        raise TypeError(node.name)
    return imported


def _target_group(module: str) -> str:
    marker = ".commands."
    relative = module.split(marker, 1)[1]
    first = relative.split(".", 1)[0]
    return first.removesuffix("_parts")


def _class_name(group: str) -> str:
    return "".join(part.capitalize() for part in group.split("_")) + "Bindings"


def _bindings_source(targets: dict[str, dict[str, str]]) -> str:
    rows = [
        "from __future__ import annotations\n",
        "\n",
        "from collections.abc import Callable\n",
        "from typing import Any\n",
        "\n",
        "\n",
        "CommandCallable = Callable[..., Any]\n",
        "\n",
        "\n",
        "def _unconfigured(*args: Any, **kwargs: Any) -> Any:\n",
        "    raise RuntimeError(\"CLI command bindings have not been configured.\")\n",
    ]
    for group, symbols in sorted(targets.items()):
        rows.extend(["\n\n", f"class {_class_name(group)}:\n", "    def __init__(self) -> None:\n"])
        for name in sorted(symbols):
            rows.append(f"        self.{name}: CommandCallable = _unconfigured\n")
    rows.extend(["\n\n", "class CommandBindings:\n", "    def __init__(self) -> None:\n"])
    for group in sorted(targets):
        rows.append(f"        self.{group} = {_class_name(group)}()\n")
    rows.extend(["\n\n", "BINDINGS = CommandBindings()\n"])
    return "".join(rows)


def _composition_source(targets: dict[str, dict[str, str]]) -> str:
    rows = [
        "from __future__ import annotations\n",
        "\n",
        "from .bindings import BINDINGS\n",
        "\n",
    ]
    imports: list[tuple[str, str, str, str]] = []
    for group, symbols in sorted(targets.items()):
        for name, module in sorted(symbols.items()):
            alias = f"_{group}_{name}".replace("__", "_private_")
            imports.append((module, name, alias, group))
            rows.append(f"from {module} import {name} as {alias}\n")
    rows.extend(["\n"])
    for _, name, alias, group in imports:
        rows.append(f"BINDINGS.{group}.{name} = {alias}\n")
    return "".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject statically composed CLI cross-domain bindings.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--flatten-composition", action="store_true")
    parser.add_argument("--split-composition", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.flatten_composition:
        return flatten_composition(root)
    if args.split_composition:
        return split_composition(root)
    return migrate(root, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
