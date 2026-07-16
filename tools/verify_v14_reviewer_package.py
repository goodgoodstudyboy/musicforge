from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.release_check.v14_reviewer import verify_v14_reviewer_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a MusicForge v14 reviewer package.")
    parser.add_argument("package")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--require-final", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = verify_v14_reviewer_package(
        Path(args.package), root, expected_sha=args.expected_sha, require_final=args.require_final
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
