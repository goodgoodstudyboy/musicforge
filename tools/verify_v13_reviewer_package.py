from __future__ import annotations

import argparse
import json

from song_agent.release_check.reviewer_package import verify_reviewer_package


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a MusicForge v13 final reviewer package.")
    parser.add_argument("package_dir")
    parser.add_argument("--expected-sha", default="")
    parser.add_argument("--allow-pending", action="store_true")
    args = parser.parse_args()
    report = verify_reviewer_package(
        args.package_dir,
        expected_sha=args.expected_sha,
        require_final=not args.allow_pending,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
