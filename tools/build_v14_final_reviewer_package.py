from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from song_agent.release_check.v14_reviewer import (
    build_v14_reviewer_package,
    verify_v14_reviewer_package,
)


PROFILES = ("v14", "latest", "ga", "security", "full")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the final MusicForge v14 reviewer package.")
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-sha", default="")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sha = args.expected_sha or _git_head(root)
    runtime = load_runtime_evidence(Path(args.evidence_dir), sha)
    package = build_v14_reviewer_package(root, Path(args.output), runtime=runtime, final_sha=sha)
    report = verify_v14_reviewer_package(package, root, expected_sha=sha, require_final=True)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


def load_runtime_evidence(evidence_dir: Path, sha: str) -> dict[str, Any]:
    tests = {name: _read(evidence_dir / f"{name}-tests.json") for name in ("active", "legacy")}
    release_checks = {
        profile: _release_check_row(_read(evidence_dir / f"release-check-{profile}.json"), sha)
        for profile in PROFILES
    }
    quality = _read(evidence_dir / "quality.json")
    nightly = _read(evidence_dir / "nightly.json")
    ci = {
        "windows_quality": _ci_row(quality, sha, "windows"),
        "linux_quality": _ci_row(quality, sha, "linux"),
        "windows_nightly": _ci_row(nightly, sha, "windows"),
        "linux_nightly": _ci_row(nightly, sha, "linux"),
    }
    performance = _read(evidence_dir / "performance.json")
    alignment = _read(evidence_dir / "release-alignment.json")
    rows = [*tests.values(), *release_checks.values(), *ci.values(), performance, alignment]
    return {
        "schema_version": 1,
        "status": "passed" if all(row.get("status") == "passed" and row.get("sha") == sha for row in rows) else "failed",
        "final_sha": sha,
        "p1_blockers": [],
        "tests": tests,
        "release_checks": release_checks,
        "ci": ci,
        "performance": performance,
        "alignment": alignment,
    }


def _release_check_row(report: dict[str, Any], sha: str) -> dict[str, Any]:
    environment = report.get("environment") or {}
    return {
        "status": "passed" if report.get("ok") is True and environment.get("git_head") == sha else "failed",
        "sha": environment.get("git_head") or "",
        "duration_ms": report.get("duration_ms") or 0,
    }


def _ci_row(report: dict[str, Any], sha: str, platform: str) -> dict[str, Any]:
    return {
        "status": "passed" if report.get("status") == "passed" and report.get("sha") == sha else "failed",
        "sha": report.get("sha") or "",
        "evidence_kind": report.get("evidence_kind") or "",
        "workflow": report.get("workflow") or "",
        "platform": platform,
    }


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip().lower()


if __name__ == "__main__":
    raise SystemExit(main())
