from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

from song_agent.release_check.v14_quality import MYPY_ROOTS


ITER_ERROR = re.compile(
    r'^(.+?):(\d+):(\d+): error: .* has no attribute "__iter__" \(not iterable\)  \[union-attr\]$'
)
IMPORT_MODULE = "song_agent.platform.contracts.coercion"


def harden_optional_lists(root: Path, *, write: bool) -> dict[str, object]:
    completed = subprocess.run(_mypy_command(), cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Mypy failed before optional list hardening.")
    requested: dict[Path, set[tuple[int, int]]] = {}
    for raw_line in completed.stdout.splitlines():
        match = ITER_ERROR.match(raw_line.strip())
        if not match:
            continue
        path = Path(match.group(1))
        path = path if path.is_absolute() else root / path
        requested.setdefault(path.resolve(), set()).add((int(match.group(2)), int(match.group(3))))

    changed: list[str] = []
    wrapped = 0
    for path, locations in sorted(requested.items(), key=lambda item: str(item[0])):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        replacements: list[tuple[int, int, str]] = []
        for line, column in sorted(locations):
            expression = _expression_at(tree, line, column)
            if expression is None:
                raise RuntimeError(f"Optional list expression was not found at {path}:{line}:{column}")
            value = ast.get_source_segment(source, expression)
            if not value:
                raise RuntimeError(f"Optional list source was not found at {path}:{line}:{column}")
            start = _offset(source, expression.lineno, expression.col_offset)
            end = _offset(source, int(expression.end_lineno or expression.lineno), int(expression.end_col_offset or expression.col_offset))
            replacements.append((start, end, f"_as_list({value})"))
        updated = source
        for start, end, value in sorted(set(replacements), reverse=True):
            updated = updated[:start] + value + updated[end:]
        updated = _insert_import(updated)
        ast.parse(updated, filename=str(path))
        changed.append(path.relative_to(root).as_posix())
        wrapped += len(set(replacements))
        if write:
            path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "wrapped_iterable_count": wrapped}


def _expression_at(tree: ast.Module, line: int, column: int) -> ast.expr | None:
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.expr) and node.lineno == line and node.col_offset + 1 == column
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda node: (int(node.end_lineno or node.lineno), int(node.end_col_offset or 0)))


def _insert_import(source: str) -> str:
    tree = ast.parse(source)
    existing = next(
        (node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == IMPORT_MODULE),
        None,
    )
    if existing is not None:
        names = {(alias.name, alias.asname) for alias in existing.names}
        names.add(("as_list", "_as_list"))
        replacement = f"from {IMPORT_MODULE} import " + ", ".join(
            f"{name} as {alias}" if alias else name for name, alias in sorted(names)
        )
        start = _offset(source, existing.lineno, existing.col_offset)
        end = _offset(source, int(existing.end_lineno or existing.lineno), int(existing.end_col_offset or existing.col_offset))
        return source[:start] + replacement + source[end:]
    future = next((node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"), None)
    position = _offset(source, int(future.end_lineno), int(future.end_col_offset)) if future else 0
    return source[:position] + f"\n\nfrom {IMPORT_MODULE} import as_list as _as_list" + source[position:]


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


def _offset(source: str, line: int, column: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[: line - 1]) + column


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = harden_optional_lists(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["wrapped_iterable_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
