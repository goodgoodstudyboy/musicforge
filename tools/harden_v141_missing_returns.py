from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

from song_agent.release_check.v14_quality import MYPY_ROOTS


ERROR = re.compile(r"^(.+?):(\d+): error: Missing return statement  \[return\]$")


def harden_missing_returns(root: Path, *, write: bool) -> dict[str, object]:
    completed = subprocess.run(_mypy_command(), cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Mypy failed before missing-return hardening.")
    requested: dict[Path, set[int]] = {}
    for raw_line in completed.stdout.splitlines():
        match = ERROR.match(raw_line.strip())
        if not match:
            continue
        path = Path(match.group(1))
        path = path if path.is_absolute() else root / path
        requested.setdefault(path.resolve(), set()).add(int(match.group(2)))

    changed: list[str] = []
    function_count = 0
    for path, lines in sorted(requested.items(), key=lambda item: str(item[0])):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        insertions: list[tuple[int, str]] = []
        for line in sorted(lines):
            function = next(
                (
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == line
                ),
                None,
            )
            if function is None:
                raise RuntimeError(f"Missing-return function was not found at {path}:{line}")
            offset = _line_end_offset(source, int(function.end_lineno or function.lineno))
            indent = " " * (function.col_offset + 4)
            insertions.append((offset, f'{indent}raise RuntimeError("{function.name} did not produce a result.")\n'))
        updated = source
        for offset, value in sorted(insertions, reverse=True):
            updated = updated[:offset] + value + updated[offset:]
        ast.parse(updated, filename=str(path))
        changed.append(path.relative_to(root).as_posix())
        function_count += len(insertions)
        if write:
            path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "function_count": function_count}


def _line_end_offset(source: str, line: int) -> int:
    lines = source.splitlines(keepends=True)
    return sum(len(value) for value in lines[:line])


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = harden_missing_returns(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["changed_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
