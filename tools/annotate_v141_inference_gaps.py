from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

from song_agent.release_check.v14_quality import MYPY_ROOTS


VAR_ERROR = re.compile(
    r'^(.+?):(\d+): error: Need type annotation for "([^"]+)"(?: \(hint: "[^:]+: (list|dict)\[<type>[^\"]*"\))?  \[var-annotated\]$'
)
TYPE_IMPORT = "from typing import Any as _InferenceType"


def annotate_inference_gaps(root: Path, *, write: bool) -> dict[str, object]:
    completed = subprocess.run(_mypy_command(), cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Mypy failed before inference annotation cleanup.")
    requested: dict[Path, list[tuple[int, str, str | None]]] = {}
    for raw_line in completed.stdout.splitlines():
        match = VAR_ERROR.match(raw_line.strip())
        if not match:
            continue
        path = Path(match.group(1))
        path = path if path.is_absolute() else root / path
        requested.setdefault(path.resolve(), []).append((int(match.group(2)), match.group(3), match.group(4)))

    changed: list[str] = []
    annotation_count = 0
    for path, rows in sorted(requested.items(), key=lambda item: str(item[0])):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        replacements: list[tuple[int, int, str]] = []
        for line, name, hint in rows:
            target = _assignment_target(tree, line, name)
            if target is None:
                raise RuntimeError(f"Inference assignment was not found at {path}:{line}:{name}")
            annotation = "list[_InferenceType]" if hint == "list" else "dict[str, _InferenceType]" if hint == "dict" else "_InferenceType"
            end = _offset(source, int(target.end_lineno or target.lineno), int(target.end_col_offset or target.col_offset))
            replacements.append((end, end, f": {annotation}"))
        updated = source
        for start, end, value in sorted(replacements, reverse=True):
            updated = updated[:start] + value + updated[end:]
        updated = _insert_import(updated, TYPE_IMPORT)
        ast.parse(updated, filename=str(path))
        changed.append(path.relative_to(root).as_posix())
        annotation_count += len(rows)
        if write:
            path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "annotation_count": annotation_count}


def _assignment_target(tree: ast.Module, line: int, name: str) -> ast.Name | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or node.lineno != line:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return target
    return None


def _insert_import(source: str, row: str) -> str:
    if row in source:
        return source
    tree = ast.parse(source)
    future = next((node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "__future__"), None)
    position = _offset(source, int(future.end_lineno), int(future.end_col_offset)) if future else 0
    return source[:position] + "\n\n" + row + source[position:]


def _mypy_command() -> list[str]:
    return [
        sys.executable,
        "-m",
        "mypy",
        *MYPY_ROOTS,
        "--follow-imports=skip",
        "--no-incremental",
        "--show-error-codes",
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
    result = annotate_inference_gaps(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["annotation_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
