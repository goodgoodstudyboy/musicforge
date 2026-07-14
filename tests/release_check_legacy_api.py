"""Test-only resolver for the archived monolithic release-check suite."""

from __future__ import annotations

from typing import Any

from song_agent.release_check.checks.registry import resolve_callable
from song_agent.release_check.runner import CheckResult, ReleaseCheckReport, print_release_check_report


def __getattr__(name: str) -> Any:
    return resolve_callable(name)


__all__ = ["CheckResult", "ReleaseCheckReport", "print_release_check_report"]
