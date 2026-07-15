from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path


COMMANDS = Path("song_agent/interfaces/cli/commands")


def staticize(root: Path, *, check: bool = False) -> int:
    command_root = root / COMMANDS
    trees = {
        path: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in command_root.rglob("*.py")
    }
    definitions: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for path, tree in trees.items():
        group = _group(command_root, path)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not _proxy(node):
                definitions[(group, node.name)].append(path)

    changed = 0
    proxy_count = 0
    for path, tree in trees.items():
        replacements: list[tuple[int, int, list[str]]] = []
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not _proxy(node):
                continue
            call = next(
                child
                for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "_resolve_symbol"
            )
            if len(call.args) < 2 or not all(isinstance(arg, ast.Constant) for arg in call.args[:2]):
                raise ValueError(f"Non-static CLI adapter at {path}:{node.lineno}")
            group = str(call.args[0].value)
            symbol = str(call.args[1].value)
            targets = definitions[(group, symbol)]
            if len(targets) != 1:
                raise ValueError(f"CLI adapter target is not unique: {group}.{symbol} -> {targets}")
            target_module = _module_name(root, targets[0])
            indent = " " * (node.body[0].col_offset if node.body else node.col_offset + 4)
            body_start = node.body[0].lineno - 1
            body_end = int(node.end_lineno or node.lineno)
            replacement = [
                f"{indent}from {target_module} import {symbol} as implementation\n",
                f"{indent}return implementation(*args, **kwargs)\n",
            ]
            replacements.append((body_start, body_end, replacement))
            proxy_count += 1
        if not replacements:
            continue
        if check:
            continue
        for start, end, replacement in reversed(replacements):
            lines[start:end] = replacement
        updated = "".join(lines)
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
        changed += 1
    if check and proxy_count:
        print(f"dynamic CLI adapters remaining: {proxy_count}")
        return 1
    print(f"staticized CLI adapters: {proxy_count} across {changed} files")
    return 0


def _group(command_root: Path, path: Path) -> str:
    relative = path.relative_to(command_root)
    if len(relative.parts) == 1:
        return path.stem
    return relative.parts[0].removesuffix("_parts")


def _proxy(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "_resolve_symbol"
        for child in ast.walk(node)
    )


def _module_name(root: Path, path: Path) -> str:
    return ".".join(path.relative_to(root).with_suffix("").parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Replace dynamic CLI symbol lookup with static adapters.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return staticize(args.root.resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
