from __future__ import annotations

import os
from pathlib import Path
import subprocess


def main() -> int:
    expected = os.environ.get("GITHUB_SHA", "").strip().lower()
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    actual = completed.stdout.strip().lower()
    if completed.returncode != 0 or not expected or actual != expected:
        print(f"final SHA mismatch: expected={expected or '<missing>'}, actual={actual or '<unavailable>'}")
        return 1
    print(f"final SHA verified: {actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
