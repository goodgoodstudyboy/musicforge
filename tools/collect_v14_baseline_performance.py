from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from typing import Any


PROFILES = ("v13", "latest", "ga", "security")


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure v13.8 performance budgets for the v14 migration ratchet.")
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    final_sha = _git(source, "rev-parse", "HEAD")
    architecture_start = perf_counter()
    architecture = _run_json(
        source,
        [sys.executable, "-c", "from song_agent.architecture_guardrails import evaluate_architecture; import json; print(json.dumps(evaluate_architecture('.')))"],
    )
    architecture_seconds = perf_counter() - architecture_start
    profiles: dict[str, Any] = {}
    for profile in PROFILES:
        started = perf_counter()
        report = _run_json(
            source,
            [sys.executable, "-m", "song_agent.cli", "release-check", "--profile", profile, "--skip-tests", "--json"],
        )
        profiles[profile] = {
            "status": "passed" if report.get("ok") is True else "failed",
            "duration_seconds": round(perf_counter() - started, 3),
            "check_count": int((report.get("summary") or {}).get("total") or len(report.get("checks") or [])),
            "duration_budget_status": (report.get("performance") or {}).get("duration_budget_status"),
        }
    document = {
        "schema_version": 1,
        "package_type": "musicforge_v14_performance_measurement",
        "baseline_tag": "v13.8.0",
        "baseline_sha": final_sha,
        "status": "passed"
        if architecture.get("status") == "passed" and all(row["status"] == "passed" for row in profiles.values())
        else "failed",
        "architecture": {"status": architecture.get("status"), "duration_seconds": round(architecture_seconds, 3)},
        "profiles": profiles,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(document, sort_keys=True))
    return 0 if document["status"] == "passed" else 1


def _run_json(cwd: Path, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr}\n{completed.stdout}")
    output = completed.stdout.strip()
    if not output:
        raise RuntimeError(f"Command produced no JSON: {' '.join(command)}")
    start = output.find("{")
    if start < 0:
        raise RuntimeError(f"Command produced no JSON object: {' '.join(command)}")
    value, _end = json.JSONDecoder().raw_decode(output[start:])
    if not isinstance(value, dict):
        raise RuntimeError(f"Command produced non-object JSON: {' '.join(command)}")
    return value


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
