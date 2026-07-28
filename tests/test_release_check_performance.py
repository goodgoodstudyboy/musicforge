from __future__ import annotations

import sys
from pathlib import Path

from song_agent.release_check.matrix import ReleaseCheckDefinition, get_check_definition
from song_agent.release_check.runner import run_release_check_matrix
from song_agent.release_check.performance import (
    CI_PROFILE_DURATION_BUDGET_SECONDS,
    CI_PROFILE_DURATION_PREVIOUS_BUDGET_SECONDS,
    PROFILE_DURATION_BUDGET_SECONDS,
    performance_summary,
)
from tests.conftest import pytest_xdist_auto_num_workers


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


def test_release_check_profile_budget_is_blocking(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setitem(PROFILE_DURATION_BUDGET_SECONDS, "latest", 0.001)
    definition = ReleaseCheckDefinition(
        check_id="performance.profile",
        name="performance profile",
        group="release-check",
        version="12.20",
        kind="command",
        risk="normal",
        timeout_seconds=10,
        command=(sys.executable, "-c", "import time; time.sleep(0.03)"),
        profiles=("latest",),
        duration_budget_seconds=5,
        budget_enforced_profiles=("latest",),
        budget_warning_only=False,
    )

    report = run_release_check_matrix(repo_root=tmp_path, profile="latest", definitions=[definition])

    assert report.ok is False
    assert report.results[-1].check_id == "release_check.profile_duration_budget"
    assert report.results[-1].status == "failed"


def test_github_actions_uses_shared_runner_profile_budget(monkeypatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    summary = performance_summary([], profile="latest", duration_ms=800_000)

    assert summary["profile_duration_budget_seconds"] == 810.0
    assert summary["duration_budget_status"] == "passed"
    assert summary["profile_over_budget"] is False


def test_ci_profile_budgets_are_hard_downward_ratchets() -> None:
    assert set(CI_PROFILE_DURATION_BUDGET_SECONDS) == set(CI_PROFILE_DURATION_PREVIOUS_BUDGET_SECONDS)
    assert all(
        CI_PROFILE_DURATION_BUDGET_SECONDS[profile] < previous
        for profile, previous in CI_PROFILE_DURATION_PREVIOUS_BUDGET_SECONDS.items()
    )


def test_full_pytest_uses_aggregate_budget_and_only_suppresses_duplicate_zip_warning() -> None:
    definition = get_check_definition("pytest.full")

    assert definition.duration_budget_seconds == 3600
    assert definition.budget_warning_only is False
    assert definition.command[-2:] == ("-W", "ignore:Duplicate name:UserWarning")


def test_default_xdist_workers_are_adaptive_without_changing_ci_parallelism(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("tests.conftest.os.cpu_count", lambda: 32)
    assert pytest_xdist_auto_num_workers(None) == 8

    monkeypatch.setattr("tests.conftest.os.cpu_count", lambda: 8)
    assert pytest_xdist_auto_num_workers(None) == 4

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr("tests.conftest.os.cpu_count", lambda: 32)
    assert pytest_xdist_auto_num_workers(None) == 4
