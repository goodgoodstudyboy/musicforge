from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import _declared_primary_marker
from song_agent.release_check.matrix import ReleaseCheckDefinition, ReleaseCheckMatrixError, select_check_definitions
from song_agent.release_check.reviewer_package import verify_reviewer_package, write_reviewer_manifest
from song_agent.release_check_governance_v137 import _valid_runtime, _write_synthetic_package, run_release_check_ci_docs_governance_smoke


ROOT = Path(__file__).resolve().parents[1]


def test_current_profile_rejects_legacy_callable() -> None:
    legacy = ReleaseCheckDefinition(
        check_id="bad.legacy",
        name="legacy",
        group="release-check",
        version="13.7",
        kind="smoke",
        risk="critical",
        timeout_seconds=10,
        callable_name="_v12_workflow_smoke",
        profiles=("v13",),
        duration_budget_seconds=10,
        budget_enforced_profiles=("v13",),
        budget_warning_only=False,
    )
    with pytest.raises(ReleaseCheckMatrixError, match="non-active callables"):
        select_check_definitions(profile="v13", definitions=(legacy,), run_tests=False)


def test_missing_explicit_marker_fails() -> None:
    with pytest.raises(pytest.UsageError, match="no explicit primary marker"):
        _declared_primary_marker("test_new_unregistered_module.py", {})


def test_marker_and_document_indexes_are_current() -> None:
    marker = json.loads((ROOT / "tests" / "marker-manifest.json").read_text(encoding="utf-8"))
    assert set(marker["files"]) == {path.relative_to(ROOT).as_posix() for path in (ROOT / "tests").glob("test_*.py")}
    material = json.loads((ROOT / "material" / "index.json").read_text(encoding="utf-8"))
    assert {row["path"] for row in material["documents"]} == {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "material").glob("*.md")
    }
    assert len((ROOT / "README.md").read_text(encoding="utf-8").splitlines()) <= 300


def test_reviewer_package_requires_nightly_and_full(tmp_path: Path) -> None:
    sha = "a" * 40
    runtime = _valid_runtime(sha)
    _write_synthetic_package(tmp_path, runtime)
    assert verify_reviewer_package(tmp_path, expected_sha=sha)["status"] == "passed"

    ci_path = tmp_path / "ci-matrix.json"
    ci = json.loads(ci_path.read_text(encoding="utf-8"))
    ci.pop("nightly")
    ci_path.write_text(json.dumps(ci, sort_keys=True), encoding="utf-8")
    write_reviewer_manifest(tmp_path, final_sha=sha)
    assert "reviewer_package_ci_nightly" in verify_reviewer_package(tmp_path, expected_sha=sha)["blockers"]

    _write_synthetic_package(tmp_path, runtime)
    reports_path = tmp_path / "release-check-reports.json"
    reports = json.loads(reports_path.read_text(encoding="utf-8"))
    reports["profiles"].pop("full")
    reports_path.write_text(json.dumps(reports, sort_keys=True), encoding="utf-8")
    write_reviewer_manifest(tmp_path, final_sha=sha)
    assert "reviewer_package_release_check_full" in verify_reviewer_package(tmp_path, expected_sha=sha)["blockers"]


def test_v137_governance_smoke() -> None:
    ok, detail = run_release_check_ci_docs_governance_smoke(ROOT)
    assert ok, detail
