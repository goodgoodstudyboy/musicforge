from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.architecture_guardrails import build_architecture_baseline, build_architecture_snapshot
from song_agent.release_check.architecture_ratchet import build_architecture_debt_catalog


def update(root: Path, *, check: bool = False) -> int:
    snapshot = build_architecture_snapshot(root)
    baseline = build_architecture_baseline(root, baseline_version="14.0.0")
    existing_baseline = json.loads((root / "architecture-baseline.json").read_text(encoding="utf-8"))
    previous_mega_files = existing_baseline.get("mega_file_max_lines") or {}
    baseline["mega_file_max_lines"] = {
        path: min(int(maximum), int(previous_mega_files.get(path, maximum)))
        for path, maximum in (baseline.get("mega_file_max_lines") or {}).items()
    }
    existing_debt = json.loads((root / "architecture-debt.json").read_text(encoding="utf-8"))
    debt = build_architecture_debt_catalog(
        root,
        previous_release_tag=str(existing_debt.get("previous_release_tag") or "v13.7.0"),
        snapshot=snapshot,
    )
    documents = {
        root / "architecture-baseline.json": baseline,
        root / "architecture-debt.json": debt,
    }
    mismatches = []
    for path, document in documents.items():
        encoded = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != encoded:
                mismatches.append(path.name)
        else:
            path.write_text(encoded, encoding="utf-8")
    if mismatches:
        print("stale architecture catalogs: " + ", ".join(mismatches))
        return 1
    print("architecture catalogs: " + ("current" if check else "updated"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Update v14 architecture baseline and debt catalogs.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return update(args.root.resolve(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
