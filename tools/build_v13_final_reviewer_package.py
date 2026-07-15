from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from song_agent.release_check.lts_audit import write_reviewer_package
from song_agent.release_check.reviewer_package import verify_reviewer_package


PROFILES = ("v13", "latest", "ga", "security", "full")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and verify the final MusicForge v13 LTS reviewer package.")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--final-sha", default="")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence = Path(args.evidence_dir)
    output = Path(args.output)
    final_sha = args.final_sha.strip().lower() or _git_head(root)
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Reviewer output must be empty: {output}")
    runtime = _runtime(evidence, final_sha)
    write_reviewer_package(root, output, runtime=runtime)
    report = verify_reviewer_package(output, expected_sha=final_sha)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


def _runtime(evidence: Path, final_sha: str) -> dict[str, Any]:
    quality = _attestation(evidence / "quality.json", final_sha, require_kind=True)
    nightly = _attestation(evidence / "nightly.json", final_sha, require_kind=True)
    active = _attestation(evidence / "active-tests.json", final_sha)
    legacy = _attestation(evidence / "legacy-tests.json", final_sha)
    profiles = {
        profile: _release_report(evidence / f"release-check-{profile}.json", final_sha, profile)
        for profile in PROFILES
    }
    migration = _attestation(evidence / "migration.json", final_sha)
    performance = _attestation(evidence / "performance.json", final_sha)
    alignment = _attestation(evidence / "release-alignment.json", final_sha)
    runtime = {
        "schema_version": 1,
        "status": "passed",
        "final_sha": final_sha,
        "p1_blockers": [],
        "ci": {"quality": quality, "nightly": nightly},
        "release_checks": {"status": "passed", "profiles": profiles},
        "tests": {"active": active, "legacy": legacy},
        "migration": migration,
        "performance": performance,
        "alignment": alignment,
    }
    if not all(
        row.get("status") == "passed"
        for row in (quality, nightly, active, legacy, migration, performance, alignment, *profiles.values())
    ):
        runtime["status"] = "failed"
    if not (
        migration.get("status") == "passed"
        and int(migration.get("file_count") or 0) > 0
        and migration.get("rollback_identical") is True
    ):
        runtime["status"] = "failed"
    return runtime


def _attestation(path: Path, final_sha: str, *, require_kind: bool = False) -> dict[str, Any]:
    row = _read_json(path)
    passed = row.get("status") == "passed" and row.get("sha") == final_sha
    if require_kind:
        passed = passed and row.get("evidence_kind") in {"github_workflow", "local_equivalent"}
    return {**row, "status": "passed" if passed else "failed"}


def _release_report(path: Path, final_sha: str, profile: str) -> dict[str, Any]:
    report = _read_json(path)
    environment = report.get("environment") if isinstance(report.get("environment"), dict) else {}
    return {
        "status": "passed" if report.get("ok") is True and environment.get("git_head") == final_sha and report.get("profile") == profile else "failed",
        "sha": str(environment.get("git_head") or ""),
        "duration_ms": int(report.get("duration_ms") or 0),
        "failed": int((report.get("summary") or {}).get("failed") or 0),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _git_head(root: Path) -> str:
    completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True)
    return completed.stdout.strip().lower()


if __name__ == "__main__":
    raise SystemExit(main())
