from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "tests" / "marker-manifest.json"


def build_manifest(root: Path = ROOT) -> dict[str, object]:
    files = {
        path.relative_to(root).as_posix(): _primary_marker(path)
        for path in sorted((root / "tests").glob("test_*.py"))
    }
    return {
        "schema_version": 1,
        "description": "Explicit primary pytest ownership; generated changes require review.",
        "files": files,
    }


def _primary_marker(path: Path) -> str:
    name = path.name.lower()
    text = path.read_text(encoding="utf-8")
    if name == "test_release_check.py":
        return "legacy"
    if name.startswith(("test_cli", "test_server", "test_webui")) or "start_test_server" in text:
        return "integration"
    if any(token in name for token in ("architecture", "contract", "registry", "matrix")):
        return "contract"
    return "unit"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update or validate the explicit pytest marker manifest.")
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in manifest is stale.")
    args = parser.parse_args(argv)
    expected = build_manifest()
    if args.check:
        actual = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.is_file() else None
        if actual != expected:
            print("tests/marker-manifest.json is stale; run tools/update_test_marker_manifest.py", file=sys.stderr)
            return 1
        return 0
    MANIFEST_PATH.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
