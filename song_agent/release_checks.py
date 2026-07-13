"""Compatibility facade for release checks.

New code imports :mod:`song_agent.release_check`. Historical private smoke
names remain lazily available through the domain provider registry until the
v13 compatibility cutover.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.release_check.checks.registry import resolve_callable
from song_agent.release_check.runner import (
    CheckResult,
    ReleaseCheckReport,
    print_release_check_report,
    run_release_check_matrix,
)


def run_release_checks(*, run_tests: bool = True, repo_root: Path | None = None) -> ReleaseCheckReport:
    return run_release_check_matrix(profile="full", run_tests=run_tests, repo_root=repo_root)


def _version_consistency(root: Path) -> tuple[bool, str]:
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    pyproject_version = match.group(1) if match else ""
    ok = pyproject_version == __version__ and f"## v{__version__}" in changelog
    return ok, f"package={__version__}, pyproject={pyproject_version}"


def __getattr__(name: str) -> Any:
    return resolve_callable(name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | {"run_release_checks", "_version_consistency"})


__all__ = [
    "CheckResult",
    "ReleaseCheckReport",
    "print_release_check_report",
    "run_release_check_matrix",
    "run_release_checks",
]
