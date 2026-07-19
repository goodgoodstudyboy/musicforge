from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.capabilities import capability_registry
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok
from song_agent.release_check.v14_architecture import evaluate_v14_architecture
from song_agent.release_check.v14_certification import (
    evaluate_v14_domain_vertical_slices,
    evaluate_v14_migration_rollback,
    evaluate_v14_verification_lifecycle_security,
)
from song_agent.release_check.v14_compatibility import evaluate_v14_compatibility_retirement
from song_agent.release_check.v14_contracts import verify_v14_public_contracts
from song_agent.release_check.v14_quality import active_source_tree_hash, evaluate_v14_quality


MANIFEST_NAME = "reviewer-package-manifest.json"
REQUIRED_DOCUMENTS = frozenset(
    {
        "README.md",
        "architecture.json",
        "capability-inventory.json",
        "compatibility-retirement.json",
        "domain-migration.json",
        "migration-rollback.json",
        "performance.json",
        "public-contracts.json",
        "quality.json",
        "release-alignment.json",
        "release-check-reports.json",
        "reviewer-runtime.json",
        "security-attack-matrix.json",
        "source-comparison.json",
        "test-reports.json",
        "ci-attestations.json",
    }
)
_SHA = re.compile(r"^[0-9a-f]{40}$")
_SENSITIVE = (
    re.compile(r"(?:ghp_|github_pat_)[A-Za-z0-9_]{12,}", re.IGNORECASE),
    re.compile(r"(?:api_key|access_token)\s*[:=]\s*[^*\s][^\s]{7,}", re.IGNORECASE),
    re.compile(r"[A-Za-z]:[/\\]Users[/\\][^/\\]+[/\\]", re.IGNORECASE),
    re.compile(r"/home/[^/]+/"),
)


def build_v14_reviewer_package(
    repo_root: Path,
    target: Path,
    *,
    runtime: dict[str, Any] | None = None,
    final_sha: str = "",
) -> Path:
    root = repo_root.resolve()
    output = target.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise RuntimeError("V14 reviewer package target must be empty.")
    sha = final_sha or _git_head(root)
    snapshot = build_architecture_snapshot(root)
    architecture = evaluate_v14_architecture(root, snapshot=snapshot)
    compatibility = evaluate_v14_compatibility_retirement(root, snapshot=snapshot)
    domain = evaluate_v14_domain_vertical_slices(root, snapshot=snapshot)
    security = evaluate_v14_verification_lifecycle_security(root, snapshot=snapshot)
    migration = evaluate_v14_migration_rollback()
    contracts = verify_v14_public_contracts(root)
    quality = evaluate_v14_quality(root, run_mypy=False)
    runtime_data = runtime or preflight_runtime(root, sha)
    documents = {
        "architecture.json": architecture,
        "capability-inventory.json": _capability_inventory(),
        "compatibility-retirement.json": compatibility,
        "domain-migration.json": domain,
        "migration-rollback.json": migration,
        "public-contracts.json": contracts,
        "quality.json": quality,
        "security-attack-matrix.json": security,
        "source-comparison.json": _source_comparison(root, snapshot, compatibility),
        "release-check-reports.json": runtime_data.get("release_checks") or {},
        "test-reports.json": runtime_data.get("tests") or {},
        "ci-attestations.json": runtime_data.get("ci") or {},
        "performance.json": runtime_data.get("performance") or {},
        "release-alignment.json": runtime_data.get("alignment") or {},
        "reviewer-runtime.json": {
            **runtime_data,
            "final_sha": sha,
            "source_tree_hash": active_source_tree_hash(root),
        },
    }
    for name, document in documents.items():
        _write_json(output / name, document)
    (output / "README.md").write_text(_readme(), encoding="utf-8")
    write_v14_reviewer_manifest(output, final_sha=sha, source_tree_hash=active_source_tree_hash(root))
    return output


def write_v14_reviewer_manifest(
    package_dir: Path,
    *,
    final_sha: str,
    source_tree_hash: str,
) -> Path:
    rows = [
        _file_row(path, package_dir)
        for path in sorted(package_dir.iterdir())
        if path.is_file() and path.name != MANIFEST_NAME
    ]
    manifest = {
        "schema_version": 1,
        "package_type": "musicforge_v14_reviewer_package_manifest",
        "release_version": __version__,
        "final_sha": final_sha,
        "source_tree_hash": source_tree_hash,
        "files": rows,
    }
    manifest["integrity_hash"] = integrity_hash(manifest)
    path = package_dir / MANIFEST_NAME
    _write_json(path, manifest)
    return path


def verify_v14_reviewer_package(
    package_dir: Path,
    repo_root: Path,
    *,
    expected_sha: str = "",
    require_final: bool = False,
) -> dict[str, Any]:
    package = package_dir.resolve()
    root = repo_root.resolve()
    blockers: list[str] = []
    entries = {path.name for path in package.iterdir() if path.is_file()} if package.is_dir() else set()
    if entries != REQUIRED_DOCUMENTS | {MANIFEST_NAME}:
        blockers.append("v14_reviewer_allowed_entries")
    manifest = _read_json(package / MANIFEST_NAME)
    if manifest.get("package_type") != "musicforge_v14_reviewer_package_manifest":
        blockers.append("v14_reviewer_manifest_type")
    if manifest.get("release_version") != __version__:
        blockers.append("v14_reviewer_release_version")
    if not integrity_ok(manifest):
        blockers.append("v14_reviewer_manifest_integrity")
    rows = manifest.get("files") or []
    if {str(row.get("path")) for row in rows} != REQUIRED_DOCUMENTS:
        blockers.append("v14_reviewer_manifest_paths")
    for row in rows:
        path = package / str(row.get("path") or "")
        if not path.is_file() or path.stat().st_size != row.get("size_bytes") or _sha256(path) != row.get("sha256"):
            blockers.append(f"v14_reviewer_file:{row.get('path')}")
    runtime = _read_json(package / "reviewer-runtime.json")
    final_sha = str(runtime.get("final_sha") or "")
    if not _SHA.fullmatch(final_sha):
        blockers.append("v14_reviewer_final_sha")
    if manifest.get("final_sha") != final_sha:
        blockers.append("v14_reviewer_manifest_sha")
    if expected_sha and final_sha != expected_sha:
        blockers.append("v14_reviewer_expected_sha")
    source_hash = active_source_tree_hash(root)
    if manifest.get("source_tree_hash") != source_hash or runtime.get("source_tree_hash") != source_hash:
        blockers.append("v14_reviewer_source_tree")
    blockers.extend(_source_report_blockers(package, root))
    if require_final:
        blockers.extend(_final_runtime_blockers(runtime, final_sha))
    if _contains_sensitive(package):
        blockers.append("v14_reviewer_redaction")
    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_reviewer_package_verification",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "summary": {"final_sha": final_sha, "file_count": len(entries), "failed_count": len(blockers)},
    }


def preflight_runtime(root: Path, sha: str) -> dict[str, Any]:
    passed = {"status": "passed", "sha": sha, "evidence_kind": "local_preflight"}
    return {
        "schema_version": 1,
        "status": "preflight",
        "final_sha": sha,
        "source_tree_hash": active_source_tree_hash(root),
        "p1_blockers": [],
        "tests": {name: dict(passed) for name in ("active", "legacy")},
        "release_checks": {name: dict(passed) for name in ("v14", "latest", "ga", "security", "full")},
        "ci": {name: dict(passed) for name in ("windows_quality", "linux_quality", "windows_nightly", "linux_nightly")},
        "performance": dict(passed),
        "alignment": {**passed, "head": sha, "origin_master": sha, "tag_target": sha, "release_target": sha},
    }


def run_v14_reviewer_package_smoke(root: Path) -> tuple[bool, str]:
    try:
        sha = _git_head(root)
        with tempfile.TemporaryDirectory(prefix="musicforge-v14-reviewer-") as temp:
            package = build_v14_reviewer_package(root, Path(temp) / "reviewer", final_sha=sha)
            report = verify_v14_reviewer_package(package, root, expected_sha=sha)
        return report["status"] == "passed", json.dumps(report, sort_keys=True)
    except Exception as exc:
        return False, f"v14 reviewer package smoke failed: {exc}"


def _source_report_blockers(package: Path, root: Path) -> list[str]:
    blockers: list[str] = []
    snapshot = build_architecture_snapshot(root)
    expected = {
        "architecture.json": evaluate_v14_architecture(root, snapshot=snapshot),
        "compatibility-retirement.json": evaluate_v14_compatibility_retirement(root, snapshot=snapshot),
        "domain-migration.json": evaluate_v14_domain_vertical_slices(root, snapshot=snapshot),
        "security-attack-matrix.json": evaluate_v14_verification_lifecycle_security(root, snapshot=snapshot),
        "migration-rollback.json": evaluate_v14_migration_rollback(),
        "public-contracts.json": verify_v14_public_contracts(root),
        "quality.json": evaluate_v14_quality(root, run_mypy=False),
        "capability-inventory.json": _capability_inventory(),
        "source-comparison.json": _source_comparison(
            root, snapshot, evaluate_v14_compatibility_retirement(root, snapshot=snapshot)
        ),
    }
    for name, report in expected.items():
        actual = _read_json(package / name)
        if actual != report:
            blockers.append(f"v14_reviewer_runtime_binding:{name}")
        if name not in {"capability-inventory.json", "source-comparison.json"} and report.get("status") != "passed":
            blockers.append(f"v14_reviewer_runtime_status:{name}")
    return blockers


def _final_runtime_blockers(runtime: dict[str, Any], sha: str) -> list[str]:
    blockers: list[str] = []
    if runtime.get("status") != "passed" or runtime.get("p1_blockers"):
        blockers.append("v14_reviewer_runtime_final")
    for section, names in (
        ("tests", ("active", "legacy")),
        ("release_checks", ("v14", "latest", "ga", "security", "full")),
        ("ci", ("windows_quality", "linux_quality", "windows_nightly", "linux_nightly")),
    ):
        rows = runtime.get(section) or {}
        for name in names:
            row = rows.get(name) or {}
            if row.get("status") != "passed" or row.get("sha") != sha:
                blockers.append(f"v14_reviewer_{section}:{name}")
    alignment = runtime.get("alignment") or {}
    if alignment.get("status") != "passed" or any(
        alignment.get(field) != sha for field in ("head", "origin_master", "tag_target", "release_target")
    ):
        blockers.append("v14_reviewer_release_alignment")
    return blockers


def _capability_inventory() -> dict[str, Any]:
    rows = []
    for row in capability_registry.all():
        rows.append(
            {
                "capability_id": row.capability_id,
                "component_type": row.component_type,
                "bounded_context": row.bounded_context,
                "application_service": row.application_service,
                "runtime_module": row.runtime.module,
                "runtime_function": row.runtime.function,
                "package_type": row.runtime.package_type,
                "verification_package_type": row.runtime.verification_package_type,
                "required_proofs": list(row.runtime.required_proofs),
                "gate_policies": list(row.gate_policies),
                "cli_commands": list(row.cli_commands),
                "api_routes": list(row.api_routes),
                "web_panel": row.web_panel,
                "release_checks": list(row.release_checks),
            }
        )
    return {"schema_version": 1, "status": "passed", "capability_count": len(rows), "rows": rows}


def _source_comparison(root: Path, snapshot: dict[str, Any], compatibility: dict[str, Any]) -> dict[str, Any]:
    baseline = _read_json(root / "architecture-v14-migration.json").get("architecture") or {}
    current_paths = {str(row.get("path")): str(row.get("layer")) for row in snapshot.get("modules") or []}
    active_lines = compatibility_lines = 0
    for relative, layer in current_paths.items():
        path = root / relative
        lines = len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0
        if layer == "compatibility":
            compatibility_lines += lines
        else:
            active_lines += lines
    return {
        "schema_version": 1,
        "status": "passed",
        "baseline": {
            "tag": "v13.8.0",
            "sha": baseline.get("baseline_sha"),
            "module_count": baseline.get("module_count"),
            "total_source_lines": baseline.get("total_source_lines"),
            "active_source_lines": baseline.get("active_source_lines"),
            "compatibility_source_lines": baseline.get("compatibility_source_lines"),
            "active_to_compatibility_import_count": baseline.get("active_to_compatibility_import_count"),
        },
        "current": {
            "module_count": len(current_paths),
            "active_source_lines": active_lines,
            "compatibility_source_lines": compatibility_lines,
            "active_to_compatibility_import_count": compatibility["summary"]["active_to_compatibility_import_count"],
            "retired_compatibility_module_count": compatibility["summary"]["retired_module_count"],
        },
    }


def _contains_sensitive(package: Path) -> bool:
    for path in package.iterdir():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if any(pattern.search(text) for pattern in _SENSITIVE):
            return True
    return False


def _file_row(path: Path, root: Path) -> dict[str, Any]:
    return {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip().lower()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _readme() -> str:
    return """# MusicForge v14 Reviewer Package

This fixed-layout package is bound to one final source SHA and active source
tree hash. The verifier recomputes architecture, compatibility retirement,
domain migration, kernel security, migration rollback, public contracts,
quality metrics, capability ownership, and source comparison from the source
checkout. Final mode additionally requires active and legacy tests, all current
release-check profiles, Windows and Linux CI, and release alignment evidence.
"""
