from __future__ import annotations

import json
from pathlib import Path

from song_agent.release_check.lts_recertification import _runtime_checks, build_lts_recertification, run_lts_recertification_smoke
from song_agent.release_check.reviewer_package import verify_reviewer_package, write_reviewer_manifest
from song_agent.release_check_governance_v137 import _valid_runtime, _write_synthetic_package
from song_agent.platform.contracts.run_state import RunState as CanonicalRunState
from song_agent.state import RunState as CompatibilityRunState
from tools.build_v13_final_reviewer_package import PROFILES, _runtime


ROOT = Path(__file__).resolve().parents[1]


def test_run_state_compatibility_exports_canonical_contract() -> None:
    assert CompatibilityRunState is CanonicalRunState


def test_v138_structural_recertification_hard_gates() -> None:
    report = build_lts_recertification(ROOT)

    assert report["status"] == "passed", report
    assert report["structural_status"] == "passed"
    assert report["runtime_status"] == "pending"
    assert report["p1_blockers"] == []
    assert report["summary"]["program_active_to_compatibility_import_count"] == 0
    assert report["summary"]["current_profile_legacy_callable_count"] == 0
    assert report["summary"]["migration_file_count"] > 0
    comparison = report["source"]["source_comparison"]
    if (ROOT / "architecture-v14-quality.json").is_file():
        assert report["checks"]["active_source_reduced"] is True
    else:
        assert comparison["current"]["active_lines"] <= comparison["v12.13"]["lines"]
    assert comparison["current"]["lines"] >= comparison["current"]["active_lines"]


def test_final_reviewer_package_binds_manifest_and_runtime_sha(tmp_path: Path) -> None:
    runtime_sha = "a" * 40
    package = tmp_path / "reviewer"
    _write_synthetic_package(package, _valid_runtime(runtime_sha))
    write_reviewer_manifest(package, final_sha="b" * 40)

    report = verify_reviewer_package(package, expected_sha=runtime_sha)

    assert report["status"] == "failed"
    assert "reviewer_package_manifest_final_sha" in report["blockers"]


def test_final_runtime_evidence_all_binds_the_same_sha() -> None:
    final_sha = "a" * 40
    runtime = _valid_runtime(final_sha)

    assert all(_runtime_checks(runtime).values())
    for key, check_id in (
        ("migration", "runtime_migration"),
        ("performance", "runtime_performance"),
        ("alignment", "release_alignment"),
    ):
        stale = _valid_runtime(final_sha)
        stale[key]["sha"] = "b" * 40
        assert _runtime_checks(stale)[check_id] is False


def test_reviewer_package_rejects_stale_performance_evidence(tmp_path: Path) -> None:
    final_sha = "a" * 40
    package = tmp_path / "reviewer"
    _write_synthetic_package(package, _valid_runtime(final_sha))
    performance_path = package / "performance.json"
    performance = json.loads(performance_path.read_text(encoding="utf-8"))
    performance["sha"] = "b" * 40
    performance_path.write_text(json.dumps(performance), encoding="utf-8")
    write_reviewer_manifest(package, final_sha=final_sha)

    report = verify_reviewer_package(package, expected_sha=final_sha)

    assert report["status"] == "failed"
    assert "reviewer_package_performance" in report["blockers"]


def test_reviewer_builder_rejects_stale_release_evidence(tmp_path: Path) -> None:
    final_sha = "a" * 40
    attestations = {
        "quality.json": {"status": "passed", "sha": final_sha, "evidence_kind": "local_equivalent"},
        "nightly.json": {"status": "passed", "sha": final_sha, "evidence_kind": "local_equivalent"},
        "active-tests.json": {"status": "passed", "sha": final_sha},
        "legacy-tests.json": {"status": "passed", "sha": final_sha},
        "migration.json": {"status": "passed", "sha": final_sha, "file_count": 1, "rollback_identical": True},
        "performance.json": {"status": "passed", "sha": final_sha},
        "release-alignment.json": {"status": "passed", "sha": final_sha},
    }
    for name, document in attestations.items():
        (tmp_path / name).write_text(json.dumps(document), encoding="utf-8")
    for profile in PROFILES:
        report = {
            "ok": True,
            "profile": profile,
            "duration_ms": 1,
            "summary": {"failed": 0},
            "environment": {"git_head": final_sha},
        }
        (tmp_path / f"release-check-{profile}.json").write_text(json.dumps(report), encoding="utf-8")

    assert _runtime(tmp_path, final_sha)["status"] == "passed"
    for name in ("migration.json", "performance.json", "release-alignment.json"):
        path = tmp_path / name
        document = json.loads(path.read_text(encoding="utf-8"))
        document["sha"] = "b" * 40
        path.write_text(json.dumps(document), encoding="utf-8")
        assert _runtime(tmp_path, final_sha)["status"] == "failed"
        document["sha"] = final_sha
        path.write_text(json.dumps(document), encoding="utf-8")


def test_v138_lts_recertification_smoke() -> None:
    ok, detail = run_lts_recertification_smoke(ROOT)

    assert ok is True, detail
