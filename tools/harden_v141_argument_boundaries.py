from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

from song_agent.release_check.v14_quality import MYPY_ROOTS


ERROR = re.compile(
    r'^(.+?):(\d+):(\d+): error: Argument (?:(\d+)|"([^"]+)") to "([^"]+)"[^;]*; expected "([^"]+)"  \[arg-type\]$'
)
IMPORT_MODULE = "song_agent.platform.contracts.coercion"
HELPERS = {
    "document": ("as_document", "_as_document"),
    "list": ("as_list", "_as_list"),
    "path": ("as_path", "_as_path"),
    "text": ("as_text", "_as_text"),
}


def harden_argument_boundaries(root: Path, *, write: bool) -> dict[str, object]:
    completed = subprocess.run(_mypy_command(), cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Mypy failed before argument boundary hardening.")
    requested: dict[Path, list[tuple[int, int, int | str, str, str]]] = {}
    for raw_line in completed.stdout.splitlines():
        match = ERROR.match(raw_line.strip())
        if not match:
            continue
        kind = _expected_kind(match.group(7))
        if kind is None:
            continue
        path = Path(match.group(1))
        path = path if path.is_absolute() else root / path
        argument: int | str = int(match.group(4)) if match.group(4) else str(match.group(5))
        requested.setdefault(path.resolve(), []).append((int(match.group(2)), int(match.group(3)), argument, kind, match.group(6)))

    changed: list[str] = []
    replacement_count = 0
    for path, rows in sorted(requested.items(), key=lambda item: str(item[0])):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        replacements: list[tuple[int, int, str, str]] = []
        for line, column, argument, kind, callee in rows:
            call = _call_at(tree, line, column, argument, callee)
            if call is None:
                raise RuntimeError(f"Argument call was not found at {path}:{line}:{column}")
            node = _argument_node(call, argument)
            if node is None:
                raise RuntimeError(f"Argument was not found at {path}:{line}:{column}:{argument}")
            expression = ast.get_source_segment(source, node)
            if not expression:
                raise RuntimeError(f"Argument source was not found at {path}:{line}:{column}:{argument}")
            helper = HELPERS[kind][1]
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper:
                continue
            start = _offset(source, node.lineno, node.col_offset)
            end = _offset(source, int(node.end_lineno or node.lineno), int(node.end_col_offset or node.col_offset))
            replacements.append((start, end, f"{helper}({expression})", kind))
        if not replacements:
            continue
        updated = source
        for start, end, value, _ in sorted(set(replacements), reverse=True):
            updated = updated[:start] + value + updated[end:]
        updated = _insert_import(updated, {HELPERS[kind] for _, _, _, kind in replacements})
        ast.parse(updated, filename=str(path))
        changed.append(path.relative_to(root).as_posix())
        replacement_count += len(set(replacements))
        if write:
            path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "replacement_count": replacement_count}


def _expected_kind(expected: str) -> str | None:
    normalized = expected.replace(" ", "")
    if normalized == "dict[str,Any]":
        return "document"
    if normalized.startswith("list["):
        return "list"
    if expected in {"Path | str", "str | Path"}:
        return "path"
    if expected == "str":
        return "text"
    return None


def _call_at(tree: ast.Module, line: int, column: int, argument: int | str, callee: str) -> ast.Call | None:
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _call_name(node) == callee
        and node.lineno <= line <= int(node.end_lineno or node.lineno)
        and _argument_node(node, argument) is not None
    ]
    exact = [node for node in candidates if node.col_offset + 1 == column]
    if exact:
        return min(exact, key=lambda node: int(node.end_col_offset or 0) - node.col_offset)
    containing = [
        node
        for node in candidates
        if _contains(_argument_node(node, argument), line, column)
    ]
    return min(containing, key=_span) if containing else None


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _contains(node: ast.expr | None, line: int, column: int) -> bool:
    if node is None or not (node.lineno <= line <= int(node.end_lineno or node.lineno)):
        return False
    if line == node.lineno and column < node.col_offset + 1:
        return False
    return not (line == int(node.end_lineno or node.lineno) and column > int(node.end_col_offset or node.col_offset) + 1)


def _span(node: ast.AST) -> tuple[int, int]:
    return (int(node.end_lineno or node.lineno) - node.lineno, int(node.end_col_offset or 0) - node.col_offset)


def _argument_node(call: ast.Call, argument: int | str) -> ast.expr | None:
    if isinstance(argument, int):
        return call.args[argument - 1] if 0 < argument <= len(call.args) else None
    return next((keyword.value for keyword in call.keywords if keyword.arg == argument), None)


def _insert_import(source: str, requested: set[tuple[str, str]]) -> str:
    tree = ast.parse(source)
    existing = next(
        (node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == IMPORT_MODULE),
        None,
    )
    if existing is not None:
        names = {(alias.name, alias.asname) for alias in existing.names}
        names.update(requested)
        replacement = f"from {IMPORT_MODULE} import " + ", ".join(
            f"{name} as {alias}" if alias else name for name, alias in sorted(names)
        )
        start = _offset(source, existing.lineno, existing.col_offset)
        end = _offset(source, int(existing.end_lineno or existing.lineno), int(existing.end_col_offset or existing.col_offset))
        return source[:start] + replacement + source[end:]
    row = f"from {IMPORT_MODULE} import " + ", ".join(f"{name} as {alias}" for name, alias in sorted(requested))
    future = next((node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"), None)
    position = _offset(source, int(future.end_lineno), int(future.end_col_offset)) if future else 0
    return source[:position] + "\n\n" + row + source[position:]


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


def _mypy_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "mypy",
        *MYPY_ROOTS,
        "--follow-imports=skip",
        "--no-incremental",
        "--show-error-codes",
        "--show-column-numbers",
        "--no-error-summary",
        "--no-pretty",
        "--no-color-output",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = harden_argument_boundaries(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["changed_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
