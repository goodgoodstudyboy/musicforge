from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.release_check.v14_quality import build_v14_quality_policy


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the v14 typing, coverage, and complexity ratchet.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--coverage-report")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report = Path(args.coverage_report).resolve() if args.coverage_report else None
    document = build_v14_quality_policy(root, coverage_report=report)
    path = root / "architecture-v14-quality.json"
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "path": path.relative_to(root).as_posix(),
                "raw_dict_str_any_max": document["typing"]["raw_dict_str_any_max_count"],
                "mypy_error_budget": document["mypy"]["max_total_errors"],
                "module_debt_count": len(document["module_size_debt"]),
                "coverage_bound": bool(document["coverage"]["report_sha256"]),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
