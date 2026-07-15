from __future__ import annotations

import ast
from pathlib import Path


def remove_resolver(root: Path) -> int:
    changed = 0
    for path in sorted((root / "song_agent" / "interfaces" / "cli").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        offsets = _line_offsets(source)
        replacements: list[tuple[int, int, str]] = []
        for node in tree.body:
            replacement = _without_resolver(node)
            if replacement is None:
                continue
            start = offsets[node.lineno - 1] + node.col_offset
            end = offsets[int(node.end_lineno or node.lineno) - 1] + int(node.end_col_offset or 0)
            if replacement == "" and end < len(source) and source[end : end + 1] == "\n":
                end += 1
            replacements.append((start, end, replacement))
        if not replacements:
            continue
        updated = source
        for start, end, replacement in sorted(replacements, reverse=True):
            updated = f"{updated[:start]}{replacement}{updated[end:]}"
        ast.parse(updated, filename=str(path))
        path.write_text(updated, encoding="utf-8")
        changed += 1
    print(f"removed CLI resolver exports: {changed}")
    return 0


def _without_resolver(node: ast.stmt) -> str | None:
    if isinstance(node, ast.ImportFrom):
        aliases = [alias for alias in node.names if (alias.asname or alias.name) != "_resolve_symbol"]
        if len(aliases) == len(node.names):
            return None
        if not aliases:
            return ""
        node.names = aliases
        return ast.unparse(node)
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
    ):
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            return None
        node.value.elts = [
            value
            for value in node.value.elts
            if not (isinstance(value, ast.Constant) and value.value == "_resolve_symbol")
        ]
        return ast.unparse(node)
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "_resolve_symbol":
            return ""
        if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
            indexes = [
                index
                for index, element in enumerate(target.elts)
                if isinstance(element, ast.Name) and element.id == "_resolve_symbol"
            ]
            if not indexes:
                return None
            target.elts = [element for index, element in enumerate(target.elts) if index not in indexes]
            node.value.elts = [element for index, element in enumerate(node.value.elts) if index not in indexes]
            return ast.unparse(node) if target.elts else ""
    return None


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    for index, value in enumerate(source):
        if value == "\n":
            offsets.append(index + 1)
    return offsets


if __name__ == "__main__":
    raise SystemExit(remove_resolver(Path.cwd().resolve()))
