from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent import __version__
from song_agent.release_check.v14_reviewer import (
    build_v14_reviewer_package,
    verify_v14_reviewer_package,
    write_v14_reviewer_manifest,
)
from song_agent.release_check.v14_quality import active_source_tree_hash


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.integration


def test_v14_reviewer_package_recomputes_source_evidence(tmp_path: Path) -> None:
    package = build_v14_reviewer_package(ROOT, tmp_path / "reviewer")

    report = verify_v14_reviewer_package(package, ROOT)
    manifest = json.loads((package / "reviewer-package-manifest.json").read_text(encoding="utf-8"))

    assert report["status"] == "passed", report["blockers"]
    assert manifest["release_version"] == __version__


def test_v14_reviewer_package_rejects_resigned_source_report(tmp_path: Path) -> None:
    package = build_v14_reviewer_package(ROOT, tmp_path / "reviewer")
    path = package / "compatibility-retirement.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["summary"]["active_to_compatibility_import_count"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")
    manifest = json.loads((package / "reviewer-package-manifest.json").read_text(encoding="utf-8"))
    write_v14_reviewer_manifest(
        package,
        final_sha=str(manifest["final_sha"]),
        source_tree_hash=active_source_tree_hash(ROOT),
    )

    report = verify_v14_reviewer_package(package, ROOT)

    assert report["status"] == "failed"
    assert "v14_reviewer_runtime_binding:compatibility-retirement.json" in report["blockers"]


def test_v14_reviewer_package_binds_expected_sha(tmp_path: Path) -> None:
    package = build_v14_reviewer_package(ROOT, tmp_path / "reviewer")

    report = verify_v14_reviewer_package(package, ROOT, expected_sha="f" * 40)

    assert "v14_reviewer_expected_sha" in report["blockers"]
