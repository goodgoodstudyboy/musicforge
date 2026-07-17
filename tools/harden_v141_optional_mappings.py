from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

from song_agent.release_check.v14_quality import MYPY_ROOTS


GET_ERROR = re.compile(
    r'^(.+?):(\d+):(\d+): error: .* has no attribute "get"  \[union-attr\]$'
)
IMPORT_ROW = "from song_agent.platform.contracts.coercion import as_document as _as_document"


def harden_optional_mappings(root: Path, *, write: bool) -> dict[str, object]:
    completed = subprocess.run(_mypy_command(), cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Mypy failed before optional mapping hardening.")
    requested: dict[Path, set[tuple[int, int]]] = {}
    for raw_line in completed.stdout.splitlines():
        match = GET_ERROR.match(raw_line.strip())
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
            attribute = _get_attribute(tree, line, column)
            if attribute is None:
                raise RuntimeError(f"Optional mapping receiver was not found at {path}:{line}:{column}")
            receiver = ast.get_source_segment(source, attribute.value)
            if not receiver:
                raise RuntimeError(f"Optional mapping source was not found at {path}:{line}:{column}")
            start = _offset(source, attribute.value.lineno, attribute.value.col_offset)
            end = _offset(
                source,
                int(attribute.value.end_lineno or attribute.value.lineno),
                int(attribute.value.end_col_offset or attribute.value.col_offset),
            )
            replacements.append((start, end, f"_as_document({receiver})"))
        updated = source
        for start, end, value in sorted(set(replacements), reverse=True):
            updated = updated[:start] + value + updated[end:]
        updated = _insert_import(updated)
        ast.parse(updated, filename=str(path))
        changed.append(path.relative_to(root).as_posix())
        wrapped += len(set(replacements))
        if write:
            path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "wrapped_receiver_count": wrapped}


def _get_attribute(tree: ast.Module, line: int, column: int) -> ast.Attribute | None:
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == "get" and node.lineno == line
    ]
    exact = [node for node in candidates if node.col_offset + 1 == column]
    if exact:
        return max(exact, key=lambda node: (int(node.end_lineno or node.lineno), int(node.end_col_offset or 0)))
    return candidates[0] if len(candidates) == 1 else None


def _insert_import(source: str) -> str:
    if IMPORT_ROW in source:
        return source
    tree = ast.parse(source)
    existing = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "song_agent.platform.contracts.coercion"
        ),
        None,
    )
    if existing is not None:
        names = {(alias.name, alias.asname) for alias in existing.names}
        names.add(("as_document", "_as_document"))
        replacement = "from song_agent.platform.contracts.coercion import " + ", ".join(
            f"{name} as {alias}" if alias else name for name, alias in sorted(names)
        )
        start = _offset(source, existing.lineno, existing.col_offset)
        end = _offset(source, int(existing.end_lineno or existing.lineno), int(existing.end_col_offset or existing.col_offset))
        return source[:start] + replacement + source[end:]
    future = next((node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"), None)
    position = _offset(source, int(future.end_lineno), int(future.end_col_offset)) if future else 0
    return source[:position] + "\n\n" + IMPORT_ROW + source[position:]


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
    result = harden_optional_mappings(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["wrapped_receiver_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
