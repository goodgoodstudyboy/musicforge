from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys

from song_agent.release_check.v14_quality import MYPY_ROOTS


UNUSED_IGNORE = re.compile(r'^(.*?):(\d+): error: Unused "type: ignore" comment  \[unused-ignore\]$')
IGNORE_COMMENT = re.compile(r"\s*#\s*type:\s*ignore(?:\[[^\]]*\])?")


def remove_unused_ignores(root: Path, *, write: bool) -> dict[str, object]:
    command = [
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
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError("Mypy failed before unused-ignore cleanup.")
    locations: dict[Path, set[int]] = {}
    for raw_line in completed.stdout.splitlines():
        match = UNUSED_IGNORE.match(raw_line.strip())
        if not match:
            continue
        path = Path(match.group(1))
        path = path if path.is_absolute() else root / path
        locations.setdefault(path.resolve(), set()).add(int(match.group(2)))

    changed: list[str] = []
    removed = 0
    for path, line_numbers in sorted(locations.items(), key=lambda item: str(item[0])):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        for line_number in sorted(line_numbers):
            index = line_number - 1
            original = lines[index]
            newline = "\r\n" if original.endswith("\r\n") else "\n" if original.endswith("\n") else ""
            body = original[: -len(newline)] if newline else original
            updated = IGNORE_COMMENT.sub("", body).rstrip() + newline
            if updated == original:
                raise RuntimeError(f"Unused ignore was not found at {path}:{line_number}")
            lines[index] = updated
            removed += 1
        updated_source = "".join(lines)
        ast.parse(updated_source, filename=str(path))
        changed.append(path.relative_to(root).as_posix())
        if write:
            path.write_text(updated_source, encoding="utf-8", newline="")
    return {"changed_files": changed, "removed_ignore_count": removed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = remove_unused_ignores(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["removed_ignore_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
