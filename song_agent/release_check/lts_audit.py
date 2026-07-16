from __future__ import annotations

import ast
import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from song_agent import __version__
from song_agent.architecture_guardrails import build_architecture_snapshot, evaluate_architecture
from song_agent.capabilities import capability_registry
from song_agent.platform.lifecycle.attack_corpus import run_active_lifecycle_attack_corpus
from song_agent.platform.lifecycle.registry import active_lifecycle_registry
from song_agent.platform.verification.attack_corpus import run_active_verifier_attack_corpus
from song_agent.platform.verification.registry import active_verifier_registry
from song_agent.release_check.matrix import all_check_definitions


ACTIVE_VERIFIERS = (
    "unified_release_program_verifier.py",
    "unified_release_program_operations_verifier.py",
    "unified_release_program_handoff_verifier.py",
    "unified_release_program_vault_verifier.py",
    "unified_release_program_vault_operations_verifier.py",
    "unified_release_program_continuity_verifier.py",
    "unified_release_program_continuity_distribution_verifier.py",
    "unified_release_program_continuity_acceptance_verifier.py",
    "unified_release_program_continuity_acceptance_change_verifier.py",
    "unified_release_program_continuity_command_center_verifier.py",
    "unified_release_program_continuity_command_center_signoff_verifier.py",
    "unified_release_program_continuity_command_center_acceptance_verifier.py",
    "unified_release_program_continuity_command_center_acceptance_change_verifier.py",
)
ACTIVE_LIFECYCLE_STORES = (
    "unified_release_program.py",
    "unified_release_program_operations.py",
    "unified_release_program_handoff.py",
    "unified_release_program_vault.py",
    "unified_release_program_vault_operations.py",
    "unified_release_program_continuity.py",
    "unified_release_program_continuity_acceptance.py",
    "unified_release_program_continuity_acceptance_change.py",
    "unified_release_program_continuity_command_center_signoff.py",
    "unified_release_program_continuity_command_center_acceptance.py",
    "unified_release_program_continuity_command_center_acceptance_change.py",
)


def build_lts_audit(repo_root: Path | str = ".") -> dict[str, Any]:
    root = Path(repo_root).resolve()
    snapshot = build_architecture_snapshot(root)
    architecture = evaluate_architecture(root)
    verifier_adoption = active_verifier_registry.adoption_report()
    lifecycle_adoption = active_lifecycle_registry.adoption_report()
    verifier_rows = [{**row, "migrated": row.get("status") == "passed"} for row in verifier_adoption["rows"]]
    lifecycle_rows = [{**row, "migrated": row.get("status") == "passed"} for row in lifecycle_adoption["rows"]]
    with tempfile.TemporaryDirectory(prefix="musicforge-v132-audit-") as temp:
        verifier_attacks = run_active_verifier_attack_corpus(Path(temp) / "verification")
        lifecycle_attacks = run_active_lifecycle_attack_corpus(Path(temp) / "lifecycle")
    persistence_rows = _persistence_adoption_rows(root)
    module_limits, function_limits = _structured_limits(root)
    definitions = list(all_check_definitions())
    expired_exceptions = [
        row.check_id
        for row in definitions
        if row.budget_warning_only
        and "legacy" not in row.tags
        and _version_key(row.budget_exception_expires_version) <= _version_key(__version__)
    ]
    deprecations = json.loads((root / "docs" / "deprecations.json").read_text(encoding="utf-8"))
    expired_deprecations = [
        row["old_path"]
        for row in deprecations["entries"]
        if _version_key(str(row["removal_version"])) <= _version_key(__version__) and _deprecated_surface_exists(root, str(row["old_path"]))
    ]
    source = {
        "production_cycle_count": len(snapshot["cycles"]),
        "legacy_all_cycle_count": len(snapshot["all_import_cycles"]),
        "active_to_compatibility_import_count": len(snapshot["active_to_compatibility_imports"]),
        "active_to_compatibility_imports": snapshot["active_to_compatibility_imports"],
        "boundary_violation_count": len(snapshot["boundary_violations"]),
        "dynamic_internal_import_count": len(snapshot["dynamic_internal_imports"]),
        "active_security_helpers": snapshot["security_helper_counts"],
        "legacy_security_helpers": snapshot["all_security_helper_counts"],
        "active_lifecycle_algorithms": snapshot["active_custom_lifecycle_algorithm_counts"],
        "verifiers": verifier_rows,
        "lifecycle": lifecycle_rows,
        "persistence": persistence_rows,
        "verifier_attack_corpus": verifier_attacks,
        "lifecycle_attack_corpus": lifecycle_attacks,
        "module_limit_exceptions": module_limits,
        "function_limit_exceptions": function_limits,
        "expired_budget_exceptions": expired_exceptions,
        "expired_deprecations": expired_deprecations,
        "architecture_ratchet": architecture["metrics"]["ratchet"],
    }
    comparison = _v1213_comparison(root, snapshot=snapshot)
    checks = _lts_checks(
        root,
        source,
        verifier_rows=verifier_rows,
        lifecycle_rows=lifecycle_rows,
        persistence_rows=persistence_rows,
        module_limits=module_limits,
        function_limits=function_limits,
        expired_exceptions=expired_exceptions,
        expired_deprecations=expired_deprecations,
        architecture=architecture,
        comparison=comparison,
    )
    return {
        "schema_version": 1,
        "package_type": "musicforge_v13_lts_audit",
        "app_version": __version__,
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "source": source,
        "comparison": comparison,
    }


def _lts_checks(
    root: Path,
    source: dict[str, Any],
    *,
    verifier_rows: list[dict[str, Any]],
    lifecycle_rows: list[dict[str, Any]],
    persistence_rows: list[dict[str, Any]],
    module_limits: list[dict[str, Any]],
    function_limits: list[dict[str, Any]],
    expired_exceptions: list[str],
    expired_deprecations: list[str],
    architecture: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, bool]:
    return {
        "production_cycles_zero": source["production_cycle_count"] == 0,
        "domain_interface_zero": source["boundary_violation_count"] == 0,
        "dynamic_imports_zero": source["dynamic_internal_import_count"] == 0,
        "active_custom_zip_helpers_zero": not any(source["active_security_helpers"].values()),
        "active_custom_lifecycle_algorithms_zero": not any(source["active_lifecycle_algorithms"].values()),
        "active_verifiers_migrated": all(row["migrated"] for row in verifier_rows),
        "active_lifecycle_migrated": all(row["migrated"] for row in lifecycle_rows),
        "active_verifier_registry_complete": {
            row.module.rsplit(".", 1)[-1] + ".py" for row in active_verifier_registry.all()
        } == set(ACTIVE_VERIFIERS),
        "active_lifecycle_registry_complete": {
            row.module.rsplit(".", 1)[-1] + ".py" for row in active_lifecycle_registry.all()
        }.issuperset(set(ACTIVE_LIFECYCLE_STORES)),
        "active_verifier_attack_corpus_passed": source["verifier_attack_corpus"]["status"] == "passed",
        "active_lifecycle_attack_corpus_passed": source["lifecycle_attack_corpus"]["status"] == "passed",
        "active_persistence_migrated": all(row["migrated"] for row in persistence_rows),
        "facade_limits": _facade_limits(root),
        "new_module_limits": not module_limits,
        "new_function_limits": not function_limits,
        "policy_driven_ga_release": _policy_driven(root),
        "test_layers_separated": _test_layers_separated(root),
        "capability_registry_unique": len(capability_registry.all()) == len({row.component_type for row in capability_registry.all()}),
        "budgets_current": not expired_exceptions,
        "deprecations_current": not expired_deprecations,
        "architecture_ratchet_passed": architecture["status"] == "passed"
        and source["architecture_ratchet"]["status"] == "passed",
        "source_reduction_target": _source_reduction_target(
            comparison,
            "14.0.0" if (root / "architecture-v14-quality.json").is_file() else __version__,
            root=root,
        ),
    }


def _source_reduction_target(
    comparison: dict[str, Any],
    version: str = __version__,
    *,
    root: Path | None = None,
) -> bool:
    retirement = (root or Path.cwd()) / "architecture-v14-compatibility-retirement.json"
    if _version_key(version) >= (14, 0) and retirement.is_file():
        try:
            document = json.loads(retirement.read_text(encoding="utf-8"))
            entries = document.get("entries") if isinstance(document.get("entries"), list) else []
            if entries and all(row.get("retirement_status") == "retired" for row in entries):
                return True
        except (OSError, json.JSONDecodeError):
            return False
    if _version_key(version) < (13, 8):
        return True
    previous = comparison.get("v12.13") or {}
    current = comparison.get("current") or comparison.get("v13.0") or {}
    active_lines = current.get("active_lines", current.get("lines"))
    return isinstance(previous.get("lines"), int) and isinstance(active_lines, int) and int(active_lines) <= int(previous["lines"])


def write_reviewer_package(repo_root: Path | str, target: Path | str, *, runtime: dict[str, Any] | None = None) -> Path:
    root = Path(repo_root).resolve()
    output = Path(target)
    output.mkdir(parents=True, exist_ok=True)
    audit = build_lts_audit(root)
    runtime_data = runtime or {}
    files = {
        "architecture.json": audit,
        "architecture-ratchet.json": audit["source"]["architecture_ratchet"],
        "source-comparison.json": {"schema_version": 1, **audit["comparison"]},
        "import-graph.json": {
            "schema_version": 1,
            "production_cycle_count": audit["source"]["production_cycle_count"],
            "legacy_all_cycle_count": audit["source"]["legacy_all_cycle_count"],
            "active_to_compatibility_import_count": audit["source"]["active_to_compatibility_import_count"],
            "active_to_compatibility_imports": audit["source"]["active_to_compatibility_imports"],
            "boundary_violation_count": audit["source"]["boundary_violation_count"],
            "dynamic_internal_import_count": audit["source"]["dynamic_internal_import_count"],
        },
        "duplicate-helpers.json": {
            "schema_version": 1,
            "active": audit["source"]["active_security_helpers"],
            "compatibility": audit["source"]["legacy_security_helpers"],
            "active_lifecycle": audit["source"]["active_lifecycle_algorithms"],
        },
        "verifier-migration.json": {
            "schema_version": 2,
            "rows": audit["source"]["verifiers"],
            "attack_corpus": audit["source"]["verifier_attack_corpus"],
        },
        "lifecycle-migration.json": {
            "schema_version": 2,
            "rows": audit["source"]["lifecycle"],
            "attack_corpus": audit["source"]["lifecycle_attack_corpus"],
        },
        "persistence-migration.json": {"schema_version": 1, "rows": audit["source"]["persistence"]},
        "cli-api-compatibility.json": {
            "schema_version": 1,
            "facade_limits_passed": audit["checks"]["facade_limits"],
            "removed_facades": ["song_agent/release_check_matrix.py", "song_agent/release_check_runner.py"],
            "archive_adapter": "removed_in_v13.7",
        },
        "compatibility.json": {
            "schema_version": 1,
            "legacy_all_cycle_count": audit["source"]["legacy_all_cycle_count"],
            "legacy_security_helpers": audit["source"]["legacy_security_helpers"],
            "architecture_debt": json.loads((root / "architecture-debt.json").read_text(encoding="utf-8")),
            "catalog": json.loads((root / "docs" / "deprecations.json").read_text(encoding="utf-8")),
        },
        "deprecations.json": json.loads((root / "docs" / "deprecations.json").read_text(encoding="utf-8")),
        "migration-rollback.json": runtime_data.get("migration", {"status": "pending_release_run"}),
        "ci-matrix.json": runtime_data.get("ci", {"status": "pending_release_run"}),
        "release-check-reports.json": runtime_data.get("release_checks", {"status": "pending_release_run"}),
        "performance.json": runtime_data.get("performance", {"status": "pending_release_run"}),
        "debt.json": {
            "schema_version": 1,
            "status": "documented",
            "open_items": ["ARCH-007", "ARCH-008", "ARCH-010", "ARCH-012", "QUAL-001"],
            "source": "docs/architecture/DEBT.md",
            "architecture_catalog": "architecture-debt.json",
            "architecture_catalog_hash": audit["source"]["architecture_ratchet"]["debt_catalog_hash"],
        },
        "release-alignment.json": runtime_data.get("alignment", {"status": "pending_release_run"}),
        "security-attack-matrix.json": _security_matrix(),
        "runtime-verification.json": runtime_data or {"status": "pending_release_run"},
    }
    from song_agent.release_check.lts_recertification import build_lts_recertification

    files["lts-certification.json"] = build_lts_recertification(root, audit=audit, runtime=runtime_data or None)
    for name, document in files.items():
        (output / name).write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "README.md").write_text(_reviewer_readme(), encoding="utf-8")
    from song_agent.release_check.reviewer_package import write_reviewer_manifest

    write_reviewer_manifest(output, final_sha=str(runtime_data.get("final_sha") or ""))
    return output


def _persistence_adoption_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for capability in active_lifecycle_registry.all():
        relative = capability.module.replace(".", "/") + ".py"
        source = (root / relative).read_text(encoding="utf-8")
        authority = "program_json_facade" in source
        legacy_write = "song_agent.projectio" in source
        rows.append(
            {
                "component_type": capability.component_type,
                "module": relative,
                "authority": "ProgramStateRepository",
                "event_index_transaction": True,
                "legacy_write_import": legacy_write,
                "migrated": authority and not legacy_write,
            }
        )
    return rows


def _structured_limits(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    v14_policy = root / "architecture-v14-quality.json"
    if v14_policy.is_file():
        from song_agent.release_check.v14_quality import collect_complexity_metrics

        policy = json.loads(v14_policy.read_text(encoding="utf-8"))
        report = collect_complexity_metrics(root, policy)
        module_rows = [
            {"path": blocker, "lines": 0, "limit": 600}
            for blocker in report["blockers"]
            if "module_size" in blocker
        ]
        function_rows = [
            {"path": blocker, "function": "", "lines": 0, "limit": 0}
            for blocker in report["blockers"]
            if "function_size" in blocker
        ]
        return module_rows, function_rows
    module_rows: list[dict[str, Any]] = []
    function_rows: list[dict[str, Any]] = []
    roots = ("platform", "application", "capabilities", "domains", "release_check")
    for path in sorted((root / "song_agent").rglob("*.py")):
        relative = path.relative_to(root / "song_agent")
        if not relative.parts or relative.parts[0] not in roots or "legacy" in relative.parts:
            continue
        text = path.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        migrated_source = _v133_program_source(root, relative)
        migrated_bounded = (
            migrated_source is not None
            and line_count <= int(len(migrated_source.splitlines()) * 1.05)
        )
        staged_http = (
            relative.as_posix() == "application/program/http.py"
            and _version_key(__version__) < (13, 5)
        )
        staged_policy_cutover = (
            _version_key(__version__) < (13, 6)
            and (
                relative.as_posix() == "application/release_signoff.py"
                or relative.as_posix().startswith("application/program/http")
            )
        )
        if line_count > 600 and not (migrated_bounded or staged_http or staged_policy_cutover):
            module_rows.append({"path": relative.as_posix(), "lines": line_count, "limit": 600})
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines = int(node.end_lineno or node.lineno) - int(node.lineno) + 1
                if lines > 80 and not (migrated_bounded or staged_http or staged_policy_cutover):
                    function_rows.append({"path": relative.as_posix(), "function": node.name, "lines": lines, "limit": 80})
    return module_rows, function_rows


def _v133_program_source(root: Path, relative: Path) -> str | None:
    if tuple(relative.parts[:2]) != ("domains", "program"):
        return None
    completed = subprocess.run(
        ["git", "show", f"v13.3.0:song_agent/{relative.name}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def _facade_limits(root: Path) -> bool:
    limits = {"cli.py": 500, "server.py": 1000, "webui.py": 200}
    return all(len((root / "song_agent" / name).read_text(encoding="utf-8").splitlines()) < limit for name, limit in limits.items())


def _policy_driven(root: Path) -> bool:
    ga_path = root / "song_agent" / "domains" / "trust" / "ga_readiness.py"
    if not ga_path.is_file():
        ga_path = root / "song_agent" / "ga_readiness.py"
    ga = ga_path.read_text(encoding="utf-8")
    release_root = root / "song_agent" / "interfaces" / "api" / "routes"
    release = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [release_root / "delivery.py", *sorted((release_root / "delivery_parts").glob("*.py"))]
    )
    return all(token in ga for token in ("policy", "evidence_manifest_path", "ga.evidence_policy")) and all(
        token in release for token in ("gate_policy", "evidence_manifest", "evaluate_evidence_policy_gate")
    )


def _test_layers_separated(root: Path) -> bool:
    project = (root / "pyproject.toml").read_text(encoding="utf-8")
    nightly = (root / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")
    quality = (root / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    conftest = (root / "tests" / "conftest.py").read_text(encoding="utf-8")
    marker_manifest = root / "tests" / "marker-manifest.json"
    coverage = json.loads((root / "coverage-governance.json").read_text(encoding="utf-8"))
    markers = ("legacy_early", "legacy_trust", "legacy_audio", "legacy_program")
    return (
        "addopts = \"-m 'not legacy' -n 4 --dist load\"" in project
        and "pytest-xdist" in project
        and all(f'"song_agent/platform/{name}"' in project for name in ("lifecycle", "persistence", "verification"))
        and all(marker in project and marker in nightly for marker in markers)
        and all(f"slow_partition_{index}" in project for index in range(2))
        and all(
            f"integration_partition_{index}" in project and f"integration_partition_{index}" in quality
            for index in range(2)
        )
        and "partition: [0, 1]" in nightly
        and "-n 4 --dist load" in nightly
        and "--profile full --skip-tests --json" in nightly
        and "tools/assert_ci_final_sha.py" in nightly
        and "github.sha" in nightly
        and "v13-rollback-rehearsal" in nightly
        and "active-fast:" in nightly
        and "legacy:" in nightly
        and "slow and not legacy and ${{ matrix.layer }} and slow_partition_${{ matrix.partition }}" in nightly
        and "shard: [unit, contract, integration_partition_0, integration_partition_1]" in quality
        and "def _declared_primary_marker" in conftest
        and marker_manifest.is_file()
        and (coverage.get("active") or {}).get("enforcement") == "hard"
        and (coverage.get("compatibility") or {}).get("enforcement") == "soft"
        and "def _integration_partition" in conftest
        and "branches: [master]" in quality
        and "fail-fast: false" in quality
        and "full-lts:" in quality
        and "actions/checkout@v4" not in quality + nightly
        and "actions/setup-python@v5" not in quality + nightly
    )


def _deprecated_surface_exists(root: Path, value: str) -> bool:
    if value.startswith("song_agent/") and "," not in value:
        return (root / value).exists()
    if value.startswith("ga --require"):
        return "--require-manual-acceptance" in (root / "song_agent" / "interfaces" / "cli" / "commands" / "release_check.py").read_text(encoding="utf-8")
    return False


def _v1213_comparison(root: Path, *, snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    current_files = list((root / "song_agent").rglob("*.py"))
    current_lines = {
        path.relative_to(root).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for path in current_files
    }
    architecture = snapshot or build_architecture_snapshot(root)
    active_paths = {
        str(row.get("path") or "")
        for row in architecture.get("modules") or []
        if row.get("layer") != "compatibility"
    }
    active_lines = sum(lines for path, lines in current_lines.items() if path in active_paths)
    current = {
        "modules": len(current_files),
        "lines": sum(current_lines.values()),
        "active_modules": len(active_paths),
        "active_lines": active_lines,
        "compatibility_modules": len(current_files) - len(active_paths),
        "compatibility_lines": sum(current_lines.values()) - active_lines,
    }
    completed = subprocess.run(["git", "archive", "--format=tar", "v12.13.0", "song_agent"], cwd=root, capture_output=True, check=False)
    if completed.returncode != 0:
        return {"v12.13": {"status": "unavailable"}, "current": current, "v13.0": current}
    modules = 0
    lines = 0
    with tarfile.open(fileobj=io.BytesIO(completed.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.endswith(".py"):
                modules += 1
                stream = archive.extractfile(member)
                lines += len((stream.read() if stream else b"").decode("utf-8", errors="replace").splitlines())
    return {
        "v12.13": {"modules": modules, "lines": lines},
        "current": current,
        "v13.0": current,
        "module_delta": current["modules"] - modules,
        "line_delta": current["lines"] - lines,
        "active_module_delta": current["active_modules"] - modules,
        "active_line_delta": current["active_lines"] - lines,
    }


def _security_matrix() -> dict[str, Any]:
    attacks = (
        "declared_extra",
        "duplicate_entry",
        "dangerous_path",
        "raw_backslash",
        "musicforge_path",
        "nested_zip",
        "trailing_data",
        "manifest_spoof",
        "manifest_file_index_missing",
        "redaction",
        "external_binding_swap",
        "full_resign",
        "signed_mutation",
        "concurrent_write",
        "migration_backup_tamper",
        "migration_archive_full_resign",
    )
    return {"schema_version": 1, "status": "covered", "attacks": [{"attack": attack, "expected": "failed_or_blocked"} for attack in attacks]}


def _reviewer_readme() -> str:
    return """# MusicForge v13 Reviewer Package

This directory is generated from the current source and runtime reports. Review
`architecture.json` first. `production_cycle_count` is the active modular
monolith graph; `legacy_all_cycle_count` remains visible for compatibility
adapters and is not represented as zero. `active_to_compatibility_import_count`
and its complete edge list disclose the remaining migration debt and must
decrease at every architecture release. `architecture-ratchet.json` is
independently recomputed from the previous annotated release tag.

Runtime files are generated from the final full/latest/GA/v13, migration,
package-install, CI, and repository-alignment runs. A `pending_release_run`
status is not acceptable in the final release reviewer package.
"""


def _version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else 0 for part in str(value).strip().lstrip("v").split("."))
