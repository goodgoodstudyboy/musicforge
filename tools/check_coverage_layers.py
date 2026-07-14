from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply MusicForge active/compatibility coverage policy.")
    parser.add_argument("coverage_json")
    parser.add_argument("--layer", choices=("active", "compatibility"), required=True)
    args = parser.parse_args()
    policy = json.loads((ROOT / "coverage-governance.json").read_text(encoding="utf-8"))[args.layer]
    report = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))
    roots = tuple(str(value).replace("\\", "/") for value in policy["roots"])
    totals = _totals(report, roots, active_only=args.layer == "active")
    percent = 100.0 if totals["statements"] == 0 else 100.0 * totals["covered"] / totals["statements"]
    passed = percent >= float(policy["minimum_percent"])
    print(json.dumps({"layer": args.layer, "percent": round(percent, 2), "policy": policy, **totals, "status": "passed" if passed else "failed"}, sort_keys=True))
    return 0 if passed or policy["enforcement"] == "soft" else 1


def _totals(report: dict[str, object], roots: tuple[str, ...], *, active_only: bool) -> dict[str, int]:
    statements = 0
    covered = 0
    for raw_path, row in dict(report.get("files") or {}).items():
        path = str(raw_path).replace("\\", "/")
        selected = any(path.startswith(root) for root in roots)
        if active_only and not selected:
            continue
        if not active_only and any(
            path.startswith(root)
            for root in (
                "song_agent/platform/",
                "song_agent/application/",
                "song_agent/domains/",
                "song_agent/capabilities/",
                "song_agent/release_check/",
            )
        ):
            continue
        summary = dict(row).get("summary") if isinstance(row, dict) else {}
        if not isinstance(summary, dict):
            continue
        statements += int(summary.get("num_statements") or 0)
        covered += int(summary.get("covered_lines") or 0)
    return {"statements": statements, "covered": covered}


if __name__ == "__main__":
    raise SystemExit(main())
