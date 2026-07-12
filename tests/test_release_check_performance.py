from __future__ import annotations

import sys
from pathlib import Path

from song_agent.release_check_matrix import ReleaseCheckDefinition
from song_agent.release_check_runner import run_release_check_matrix


def _slow_definition(*, warning_only: bool) -> ReleaseCheckDefinition:
    return ReleaseCheckDefinition(
        check_id="performance.slow",
        name="performance slow",
        group="release-check",
        version="12.13",
        kind="command",
        risk="normal",
        timeout_seconds=10,
        command=(sys.executable, "-c", "import time; time.sleep(0.03)"),
        profiles=("latest",),
        duration_budget_seconds=0.001,
        budget_enforced_profiles=("latest",),
        budget_warning_only=warning_only,
    )


def test_release_check_budget_warning_is_reported_without_masking_success(tmp_path: Path) -> None:
    report = run_release_check_matrix(
        repo_root=tmp_path,
        profile="latest",
        definitions=[_slow_definition(warning_only=True)],
    )
    payload = report.to_json_report()
    timing = report.to_timing_report()

    assert report.ok is True
    assert payload["results"][0]["duration_budget_status"] == "warning"
    assert payload["summary"]["checks_over_budget"][0]["check_id"] == "performance.slow"
    assert payload["summary"]["duration_budget_status"] == "warning"
    assert timing["checks_over_budget"][0]["check_id"] == "performance.slow"


def test_release_check_hard_budget_failure_is_blocking(tmp_path: Path) -> None:
    report = run_release_check_matrix(
        repo_root=tmp_path,
        profile="latest",
        definitions=[_slow_definition(warning_only=False)],
    )
    payload = report.to_json_report()

    assert report.ok is False
    assert payload["results"][0]["status"] == "failed"
    assert payload["results"][0]["duration_budget_status"] == "failed"
    assert "duration budget exceeded" in payload["results"][0]["detail"]
