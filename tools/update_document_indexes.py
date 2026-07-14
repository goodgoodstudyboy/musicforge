from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "material" / "index.json"


def build_material_index() -> dict[str, object]:
    rows = []
    for path in sorted((ROOT / "material").glob("*.md")):
        relative = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        heading = next((line.removeprefix("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        version = _version(path.name)
        rows.append(
            {
                "path": relative,
                "title": heading,
                "version": version,
                "status": "active" if "v13.0.1-v13.8" in path.name else "historical",
            }
        )
    return {"schema_version": 1, "archive_policy": "original_paths_preserved", "documents": rows}


def _version(name: str) -> str:
    match = re.search(r"v(\d+(?:\.\d+){0,2}(?:-v?\d+(?:\.\d+){0,2})?)", name, re.IGNORECASE)
    return match.group(1) if match else "unversioned"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update or validate documentation catalogs.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    expected = build_material_index()
    if args.check:
        actual = json.loads(INDEX_PATH.read_text(encoding="utf-8")) if INDEX_PATH.is_file() else None
        if actual != expected:
            print("material/index.json is stale; run tools/update_document_indexes.py", file=sys.stderr)
            return 1
        return 0
    INDEX_PATH.write_text(json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
