from __future__ import annotations

import argparse
from pathlib import Path
import re

from song_agent.release_check.v14_quality import MYPY_ROOTS


PAIR = re.compile(
    r"^from song_agent\.platform\.contracts\.coercion import (?P<coercions>[^\n]+)\n\n"
    r"from song_agent\.platform\.contracts\.documents import ImplementationDocument$",
    re.MULTILINE,
)


def consolidate_contract_imports(root: Path, *, write: bool) -> dict[str, object]:
    changed: list[str] = []
    replacement_count = 0
    for relative in MYPY_ROOTS:
        for path in sorted((root / relative).rglob("*.py")):
            source = path.read_text(encoding="utf-8")
            updated, count = PAIR.subn(
                lambda match: "from song_agent.platform.contracts import ImplementationDocument, " + match.group("coercions"),
                source,
            )
            if not count:
                continue
            compile(updated, str(path), "exec")
            changed.append(path.relative_to(root).as_posix())
            replacement_count += count
            if write:
                path.write_text(updated, encoding="utf-8")
    return {"changed_files": changed, "replacement_count": replacement_count}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = consolidate_contract_imports(Path.cwd(), write=not args.check)
    print(result)
    return 1 if args.check and result["changed_files"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
