from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument
import json
from pathlib import Path
import tempfile

from song_agent.release_check.reviewer_package import REQUIRED_DOCUMENTS, verify_reviewer_package, write_reviewer_manifest


CURRENT_PROFILES = ("latest", "ga", "v14", "security")


def run_release_check_ci_docs_governance_smoke(root: Path) -> tuple[bool, str]:
    try:
        from song_agent.release_check.checks.registry import callable_provenance
        from song_agent.release_check.matrix import select_check_definitions

        profiles = {
            profile: [
                row.check_id
                for row in select_check_definitions(profile=profile, run_tests=False)
                if row.callable_name and callable_provenance(row.callable_name) != "active"
            ]
            for profile in CURRENT_PROFILES
        }
        full = select_check_definitions(profile="full", run_tests=False)
        unlabelled_full = [
            row.check_id
            for row in full
            if row.callable_name and callable_provenance(row.callable_name) == "legacy" and "legacy" not in row.tags
        ]
        marker_payload = json.loads((root / "tests" / "marker-manifest.json").read_text(encoding="utf-8"))
        marker_files = set(marker_payload.get("files") or {})
        test_files = {path.relative_to(root).as_posix() for path in (root / "tests").glob("test_*.py")}
        quality = (root / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
        nightly = (root / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")
        coverage = json.loads((root / "coverage-governance.json").read_text(encoding="utf-8"))
        material = json.loads((root / "material" / "index.json").read_text(encoding="utf-8"))
        reviewer = _reviewer_package_checks()
        details: ImplementationDocument = {
            "current_profile_legacy_callables": profiles,
            "current_profiles_active": all(not rows for rows in profiles.values()),
            "full_legacy_labelled": not unlabelled_full,
            "marker_manifest_complete": marker_payload.get("schema_version") == 1 and marker_files == test_files,
            "readme_under_300": _line_count(root / "README.md") <= 300,
            "changelog_current_major_only": _changelog_current_major(root / "CHANGELOG.md"),
            "material_index_complete": material.get("schema_version") == 1
            and {str(row.get("path")) for row in material.get("documents") or []}
            == {path.relative_to(root).as_posix() for path in (root / "material").glob("*.md")},
            "quality_full_lts": "full-lts:" in quality and "workflow_dispatch:" in quality,
            "nightly_final_sha": "tools/assert_ci_final_sha.py" in nightly and "github.sha" in nightly,
            "nightly_active_suite": "active-fast:" in nightly and "active-slow:" in nightly,
            "nightly_legacy_suite": "legacy:" in nightly,
            "nightly_full_release_check": "--profile full --skip-tests --json" in nightly,
            "nightly_migration_rehearsal": "v13-rollback-rehearsal" in nightly,
            "coverage_active_hard": (coverage.get("active") or {}).get("enforcement") == "hard",
            "coverage_compatibility_soft": (coverage.get("compatibility") or {}).get("enforcement") == "soft",
            **reviewer,
        }
        return all(value is True or isinstance(value, dict) for key, value in details.items() if key == "current_profile_legacy_callables" or isinstance(value, bool)), json.dumps(details, sort_keys=True)
    except Exception as exc:
        return False, str(exc)


def _reviewer_package_checks() -> dict[str, bool]:
    with tempfile.TemporaryDirectory(prefix="mf-v137-reviewer-") as temp:
        root = Path(temp)
        sha = "a" * 40
        runtime = _valid_runtime(sha)
        _write_synthetic_package(root, runtime)
        valid = verify_reviewer_package(root, expected_sha=sha)
        ci_path = root / "ci-matrix.json"
        ci = json.loads(ci_path.read_text(encoding="utf-8"))
        ci.pop("nightly")
        ci_path.write_text(json.dumps(ci, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_reviewer_manifest(root, final_sha=sha)
        missing_nightly = verify_reviewer_package(root, expected_sha=sha)
        _write_synthetic_package(root, runtime)
        release_path = root / "release-check-reports.json"
        release = json.loads(release_path.read_text(encoding="utf-8"))
        release["profiles"].pop("full")
        release_path.write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_reviewer_manifest(root, final_sha=sha)
        missing_full = verify_reviewer_package(root, expected_sha=sha)
        return {
            "reviewer_package_valid": valid.get("status") == "passed",
            "reviewer_missing_nightly_failed": "reviewer_package_ci_nightly" in missing_nightly.get("blockers", []),
            "reviewer_missing_full_failed": "reviewer_package_release_check_full" in missing_full.get("blockers", []),
        }


def _write_synthetic_package(root: Path, runtime: ImplementationDocument) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for path in root.iterdir():
        if path.is_file():
            path.unlink()
    for name in REQUIRED_DOCUMENTS:
        path = root / name
        if name == "README.md":
            path.write_text("# Reviewer package\n", encoding="utf-8")
        else:
            document = _document_for(name, runtime)
            path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_reviewer_manifest(root, final_sha=str(runtime["final_sha"]))


def _document_for(name: str, runtime: ImplementationDocument) -> ImplementationDocument:
    mapping = {
        "runtime-verification.json": runtime,
        "ci-matrix.json": runtime["ci"],
        "release-check-reports.json": runtime["release_checks"],
        "migration-rollback.json": runtime["migration"],
        "performance.json": runtime["performance"],
        "release-alignment.json": runtime["alignment"],
        "architecture.json": {"schema_version": 1, "status": "passed"},
        "source-comparison.json": {
            "schema_version": 2,
            "v12.13": {"modules": 100, "lines": 1000},
            "current": {"modules": 50, "lines": 900, "active_modules": 40, "active_lines": 800},
        },
        "import-graph.json": {"schema_version": 1, "active_to_compatibility_imports": []},
        "lts-certification.json": {
            "schema_version": 1,
            "status": "passed",
            "runtime_status": "passed",
            "summary": {"open_p1_count": 0},
        },
    }
    return mapping.get(name, {"schema_version": 1, "status": "passed"})


def _valid_runtime(sha: str) -> ImplementationDocument:
    passed = {"status": "passed", "sha": sha}
    ci_passed = {**passed, "evidence_kind": "local_equivalent"}
    return {
        "schema_version": 1,
        "status": "passed",
        "final_sha": sha,
        "ci": {"quality": dict(ci_passed), "nightly": dict(ci_passed)},
        "release_checks": {
            "status": "passed",
            "profiles": {profile: dict(passed) for profile in ("full", "v13", "latest", "ga", "security")},
        },
        "migration": {**passed, "file_count": 1, "rollback_identical": True},
        "tests": {"active": dict(passed), "legacy": dict(passed)},
        "performance": dict(passed),
        "alignment": dict(passed),
        "p1_blockers": [],
    }


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _changelog_current_major(path: Path) -> bool:
    headings = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("## v")]
    majors = {line.split(".", 1)[0] for line in headings}
    return bool(headings) and len(majors) == 1
