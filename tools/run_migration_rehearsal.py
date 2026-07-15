from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from song_agent.platform.persistence import V13MigrationOrchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a representative v13 migration rollback rehearsal.")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="musicforge-final-migration-") as temp:
        workspace = Path(temp) / ".musicforge"
        source = workspace / "unified-release-programs" / "reviewer-sample" / "program.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('{"project_id":"reviewer-sample","status":"ready"}\n', encoding="utf-8")
        orchestrator = V13MigrationOrchestrator(workspace)
        plan = orchestrator.dry_run()
        rehearsal = orchestrator.rollback_rehearsal()
        result = {
            "schema_version": 1,
            "sha": _git_head(),
            "status": "passed"
            if int(plan.get("file_count") or 0) > 0
            and rehearsal.get("status") == "passed"
            and rehearsal.get("source_restored") is True
            else "failed",
            "file_count": int(plan.get("file_count") or 0),
            "rollback_identical": rehearsal.get("source_restored") is True,
            "backup_verified": rehearsal.get("backup_verified") is True,
        }
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0 if result["status"] == "passed" else 1


def _git_head() -> str:
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip().lower()


if __name__ == "__main__":
    raise SystemExit(main())
