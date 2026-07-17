from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

from song_agent.release_check.v14_quality import MYPY_ROOTS


ERROR = re.compile(
    r'^(.+?):(\d+):(\d+): error: Argument 1 to "(Path|int|float)" has incompatible type .+  \[arg-type\]$'
)
HELPERS = {
    "Path": ("as_path", "_as_path"),
    "int": ("as_int", "_as_int"),
    "float": ("as_float", "_as_float"),
}
IMPORT_MODULE = "song_agent.platform.contracts.coercion"


def harden_scalar_coercions(root: Path, *, write: bool) -> dict[str, object]:
    completed = subprocess.run(_mypy_command(), cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Mypy failed before scalar coercion hardening.")
    requested: dict[Path, set[tuple[int, int, str]]] = {}
    for raw_line in completed.stdout.splitlines():
        match = ERROR.match(raw_line.strip())
        if not match:
            continue
        path = Path(match.group(1))
        path = path if path.is_absolute() else root / path
        requested.setdefault(path.resolve(), set()).add((int(match.group(2)), int(match.group(3)), match.group(4)))

    changed: list[str] = []
    replacement_count = 0
    for path, locations in sorted(requested.items(), key=lambda item: str(item[0])):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        replacements: list[tuple[int, int, str, str]] = []
        for line, column, name in sorted(locations):
            call = _call_at(tree, line, column, name)
            if call is None or len(call.args) != 1 or call.keywords:
                raise RuntimeError(f"Scalar conversion call was not found at {path}:{line}:{column}:{name}")
            argument = ast.get_source_segment(source, call.args[0])
            if not argument:
                raise RuntimeError(f"Scalar conversion argument was not found at {path}:{line}:{column}:{name}")
            start = _offset(source, call.lineno, call.col_offset)
            end = _offset(source, int(call.end_lineno or call.lineno), int(call.end_col_offset or call.col_offset))
            replacements.append((start, end, f"{HELPERS[name][1]}({argument})", name))
        updated = source
        for start, end, value, _ in sorted(replacements, reverse=True):
            updated = updated[:start] + value + updated[end:]
        requested_imports = {HELPERS[name] for _, _, _, name in replacements}
        updated = _insert_import(updated, requested_imports)
        ast.parse(updated, filename=str(path))
        changed.append(path.relative_to(root).as_posix())
        replacement_count += len(replacements)
        if write:
            path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "replacement_count": replacement_count}


def _call_at(tree: ast.Module, line: int, column: int, name: str) -> ast.Call | None:
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == name
        and node.lineno == line
    ]
    exact = [node for node in candidates if node.col_offset + 1 == column]
    if exact:
        return exact[0]
    return candidates[0] if len(candidates) == 1 else None


def _insert_import(source: str, requested: set[tuple[str, str]]) -> str:
    tree = ast.parse(source)
    existing = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == IMPORT_MODULE
        ),
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
    result = harden_scalar_coercions(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["changed_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
