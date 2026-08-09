from __future__ import annotations

import argparse
from pathlib import Path

from tools.v14_baseline import write_v14_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the reproducible MusicForge v14 migration baseline.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("runs/v14-baseline"))
    parser.add_argument("--tracked-manifest", type=Path, default=Path("architecture-v14-migration.json"))
    parser.add_argument("--coverage-json", type=Path)
    parser.add_argument("--performance-json", type=Path)
    args = parser.parse_args()
    documents = write_v14_baseline(
        args.root.resolve(),
        output_dir=args.output,
        tracked_manifest=args.tracked_manifest,
        coverage_report=args.coverage_json,
        performance_report=args.performance_json,
    )
    architecture = documents["architecture.json"]
    retirement = documents["compatibility-retirement.json"]
    print(
        "v14 baseline: "
        f"modules={architecture['module_count']} "
        f"compatibility={retirement['summary']['module_count']} "
        f"active_edges={retirement['summary']['active_edge_count']}"
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
