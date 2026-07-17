from __future__ import annotations

import ast
from pathlib import Path

from song_agent.release_check.v14_quality import MYPY_ROOTS


IMPORT_MODULE = "song_agent.platform.contracts.coercion"
HELPERS = {"dict": ("as_document", "_as_document"), "list": ("as_list", "_as_list")}
FALLBACK_HELPERS = {"dict": ("document_or", "_document_or"), "list": ("list_or", "_list_or")}


def adopt_document_coercions(root: Path, *, write: bool) -> dict[str, object]:
    changed: list[str] = []
    replacement_count = 0
    for relative_root in MYPY_ROOTS:
        for path in sorted((root / relative_root).rglob("*.py")):
            if path.as_posix().endswith("/platform/contracts/coercion.py"):
                continue
            source = path.read_text(encoding="utf-8")
            updated, count = _rewrite_source(source)
            if updated == source:
                continue
            ast.parse(updated, filename=str(path))
            changed.append(path.relative_to(root).as_posix())
            replacement_count += count
            if write:
                path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "replacement_count": replacement_count}


def _rewrite_source(source: str) -> tuple[str, int]:
    tree = ast.parse(source)
    candidates: list[tuple[int, int, str, str, str | None]] = []
    for node in ast.walk(tree):
        kind = _coercion_kind(node)
        if kind is None:
            continue
        expression = ast.get_source_segment(source, node.test.args[0])
        if not expression:
            continue
        start = _offset(source, node.lineno, node.col_offset)
        end = _offset(source, int(node.end_lineno or node.lineno), int(node.end_col_offset or node.col_offset))
        fallback = None if _is_empty_fallback(node, kind) else ast.get_source_segment(source, node.orelse)
        if fallback is None and not _is_empty_fallback(node, kind):
            continue
        candidates.append((start, end, kind, expression, fallback))
    selected = [
        row
        for row in candidates
        if not any(other[0] <= row[0] and row[1] <= other[1] and other[:2] != row[:2] for other in candidates)
    ]
    if not selected:
        return source, 0
    replacements = [
        (
            start,
            end,
            f"{HELPERS[kind][1]}({expression})" if fallback is None else f"{FALLBACK_HELPERS[kind][1]}({expression}, {fallback})",
        )
        for start, end, kind, expression, fallback in selected
    ]
    updated = source
    for start, end, value in sorted(replacements, reverse=True):
        updated = updated[:start] + value + updated[end:]
    requested = {
        (HELPERS[kind] if fallback is None else FALLBACK_HELPERS[kind])
        for _, _, kind, _, fallback in selected
    }
    imports = ", ".join(f"{name} as {alias}" for name, alias in sorted(requested))
    updated = _insert_import(updated, f"from {IMPORT_MODULE} import {imports}")
    return updated, len(selected)


def _coercion_kind(node: ast.AST) -> str | None:
    if not isinstance(node, ast.IfExp):
        return None
    test = node.test
    if not isinstance(test, ast.Call) or not isinstance(test.func, ast.Name) or test.func.id != "isinstance":
        return None
    if len(test.args) != 2 or ast.dump(node.body, include_attributes=False) != ast.dump(test.args[0], include_attributes=False):
        return None
    type_node = test.args[1]
    if not isinstance(type_node, ast.Name) or type_node.id not in HELPERS:
        return None
    if isinstance(node.orelse, ast.Constant) and node.orelse.value is None:
        return None
    return type_node.id


def _is_empty_fallback(node: ast.IfExp, kind: str) -> bool:
    if kind == "dict":
        return isinstance(node.orelse, ast.Dict) and not node.orelse.keys
    return isinstance(node.orelse, ast.List) and not node.orelse.elts


def _insert_import(source: str, row: str) -> str:
    tree = ast.parse(source)
    existing = next(
        (node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == IMPORT_MODULE),
        None,
    )
    if existing is not None:
        names = {(alias.name, alias.asname) for alias in existing.names}
        requested = []
        for helper, alias in (*HELPERS.values(), *FALLBACK_HELPERS.values()):
            if f"{alias}(" in source and (helper, alias) not in names:
                requested.append((helper, alias))
        if not requested:
            return source
        start = _offset(source, existing.lineno, existing.col_offset)
        end = _offset(source, int(existing.end_lineno or existing.lineno), int(existing.end_col_offset or existing.col_offset))
        all_names = sorted([*names, *requested])
        replacement = f"from {IMPORT_MODULE} import " + ", ".join(
            f"{name} as {alias}" if alias else name for name, alias in all_names
        )
        return source[:start] + replacement + source[end:]
    future = next(
        (node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"),
        None,
    )
    position = _offset(source, int(future.end_lineno), int(future.end_col_offset)) if future else 0
    return source[:position] + "\n\n" + row + source[position:]


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


if __name__ == "__main__":
    result = adopt_document_coercions(Path.cwd(), write=True)
    print(f"document coercions: changed={len(result['changed_files'])} replacements={result['replacement_count']}")
