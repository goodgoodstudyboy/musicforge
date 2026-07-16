from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from song_agent.platform.persistence import V14MigrationOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the v14 non-empty byte-identical migration rollback rehearsal.")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="musicforge-v14-final-migration-") as temp:
        workspace = Path(temp) / ".musicforge"
        source = workspace / "unified-release-programs" / "reviewer-sample" / "program.json"
        source.parent.mkdir(parents=True)
        source.write_text(
            '{"component_type":"unified_release_program","generation":1,"program_id":"reviewer-sample","status":"ready"}\n',
            encoding="utf-8",
        )
        report = V14MigrationOrchestrator(workspace).rollback_rehearsal()
    result = {
        **report,
        "sha": _git_head(),
        "rollback_identical": report.get("byte_identical") is True
        and report.get("logical_state_identical") is True,
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.get("status") == "passed" else 1


def _git_head() -> str:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip().lower()


if __name__ == "__main__":
    raise SystemExit(main())
