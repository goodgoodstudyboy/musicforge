from __future__ import annotations

import ast
from collections import Counter
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import Any, Iterable

from song_agent.platform.verification.hashing import canonical_text_bytes, sha256_text_file, stable_hash


QUALITY_POLICY_PATH = "architecture-v14-quality.json"
QUALITY_POLICY_VERSION = "14.2.8"
EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION = 11
MYPY_ROOTS = (
    "song_agent/platform",
    "song_agent/application",
    "song_agent/domains",
    "song_agent/capabilities",
    "song_agent/interfaces",
)
COVERAGE_ROOTS = (*MYPY_ROOTS, "song_agent/release_check")
MYPY_ERROR = re.compile(r"^(.*?):\d+: error: .*\[([^\]]+)\]\s*$")
FUNCTION_LIMITS = {"interface_api": 100, "interface_cli": 120, "application": 150, "domain": 200}
V1421_STABILIZATION_ADR = "docs/architecture/ADR-016-v1421-stabilization-rollback.md"
V1422_COLLECTOR_ADR = "docs/architecture/ADR-017-v1422-explicit-any-scope-collector.md"
V1423_LAMBDA_COLLECTOR_ADR = "docs/architecture/ADR-018-v1423-explicit-any-lambda-scope.md"
V1424_DEFINITION_TIME_COLLECTOR_ADR = "docs/architecture/ADR-019-v1424-explicit-any-definition-time-scope.md"
V1425_CLASS_GLOBAL_COLLECTOR_ADR = "docs/architecture/ADR-020-v1425-explicit-any-class-global-scope.md"
V1426_INDIRECT_TARGET_COLLECTOR_ADR = "docs/architecture/ADR-021-v1426-explicit-any-indirect-target-scope.md"
V1427_DERIVED_UNCERTAIN_COLLECTOR_ADR = "docs/architecture/ADR-022-v1427-explicit-any-derived-uncertain-flow.md"
V1428_OBJECT_ALIAS_COLLECTOR_ADR = "docs/architecture/ADR-023-v1428-explicit-any-object-alias-flow.md"
V1421_EXPLICIT_ANY_FILE_BUDGETS_HASH = "950a9252b03d600d36776ef8aebe51b1392fe917b70b0f9d976a94589f24476d"
V1421_MODULE_DEBT_CEILINGS_HASH = "9e3bae0ce93f17d5d8f801cd2851d9fc1e5322d49eba25e0beca264ab8ea331b"
V1421_RECOVERY_LIMITS: dict[str, Any] = {
    "active_python_file_max_count": 700,
    "explicit_any_max_count": 12040,
    "explicit_any_affected_file_max_count": 470,
    "raw_dict_str_any_max_count": 5605,
    "implementation_document_max_count": 7118,
    "explicit_any_layer_max_counts": {
        "application": 72,
        "capabilities": 13,
        "domains": 6545,
        "interfaces": 5214,
        "platform": 196,
    },
    "oversized_module_max_count": 137,
    "modules_over_1000_max_count": 37,
    "largest_module_max_lines": 2226,
    "total_oversized_module_max_lines": 124043,
}


def evaluate_v14_quality(
    repo_root: Path | str = ".",
    *,
    policy_path: Path | str = QUALITY_POLICY_PATH,
    run_mypy: bool = True,
    require_coverage: bool = True,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = json.loads(_rooted(root, policy_path).read_text(encoding="utf-8"))
    blockers = _policy_blockers(policy)
    typing = collect_typing_metrics(root)
    complexity = collect_complexity_metrics(root, policy)
    blockers.extend(_typing_blockers(typing, policy))
    blockers.extend(complexity["blockers"])
    mypy = {"status": "skipped", "total_errors": 0, "new_error_budgets": {}, "grown_error_budgets": {}}
    if run_mypy:
        mypy = collect_mypy_metrics(root)
        blockers.extend(_mypy_blockers(mypy, policy))
    coverage = collect_coverage_metrics(root, policy)
    if require_coverage:
        blockers.extend(coverage["blockers"])
    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_quality_report",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "typing": typing,
        "mypy": mypy,
        "complexity": complexity,
        "coverage": coverage,
    }


def collect_typing_metrics(root: Path) -> dict[str, Any]:
    resolved = root.resolve()
    source_hash = active_source_tree_hash(resolved)
    return deepcopy(_collect_typing_metrics_cached(str(resolved), source_hash))


@lru_cache(maxsize=8)
def _collect_typing_metrics_cached(root: str, source_hash: str) -> dict[str, Any]:
    path = Path(root)
    metrics = _collect_typing_metrics_uncached(path)
    if active_source_tree_hash(path) != source_hash:
        raise RuntimeError("Active source changed while collecting typing metrics.")
    return metrics


def _collect_typing_metrics_uncached(root: Path) -> dict[str, Any]:
    raw_count = 0
    implementation_count = 0
    explicit_any_by_file: Counter[str] = Counter()
    explicit_any_by_layer: Counter[str] = Counter()
    explicit_any_scope_blockers: list[dict[str, Any]] = []
    public_dynamic: list[dict[str, Any]] = []
    untyped_public: list[dict[str, Any]] = []
    for path in _active_python_files(root):
        source = path.read_text(encoding="utf-8")
        raw_count += source.count("dict[str, Any]")
        implementation_count += source.count("ImplementationDocument")
        tree = ast.parse(source, filename=str(path))
        relative = path.relative_to(root).as_posix()
        explicit_any, scope_blockers = _explicit_any_annotation_analysis(tree)
        if explicit_any:
            explicit_any_by_file[relative] = explicit_any
            explicit_any_by_layer[_typing_layer(relative)] += explicit_any
        explicit_any_scope_blockers.extend(
            {"path": relative, "detail": detail} for detail in scope_blockers
        )
        for function, owner in _public_functions(tree):
            annotations = _function_annotations(function, skip_receiver=owner is not None)
            if function.returns is None or any(annotation is None for annotation in annotations):
                untyped_public.append(
                    {"path": relative, "owner": owner or "", "name": function.name, "line": function.lineno}
                )
            annotated_nodes = [function.returns, *annotations]
            if any(
                "ImplementationDocument" in (ast.get_source_segment(source, node) or "")
                for node in annotated_nodes
                if node is not None
            ):
                public_dynamic.append(
                    {"path": relative, "owner": owner or "", "name": function.name, "line": function.lineno}
                )
    return {
        "collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "active_python_file_count": len(_active_python_files(root)),
        "raw_dict_str_any_count": raw_count,
        "implementation_document_count": implementation_count,
        "explicit_any_count": sum(explicit_any_by_file.values()),
        "explicit_any_affected_file_count": len(explicit_any_by_file),
        "explicit_any_by_layer": dict(sorted(explicit_any_by_layer.items())),
        "explicit_any_by_file": dict(sorted(explicit_any_by_file.items())),
        "explicit_any_scope_blocker_count": len(explicit_any_scope_blockers),
        "explicit_any_scope_blockers": explicit_any_scope_blockers,
        "public_implementation_document_count": len(public_dynamic),
        "public_implementation_documents": public_dynamic,
        "untyped_public_function_count": len(untyped_public),
        "untyped_public_functions": untyped_public,
    }


def collect_mypy_metrics(root: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "mypy",
        *MYPY_ROOTS,
        "--follow-imports=skip",
        "--no-incremental",
        "--show-error-codes",
        "--no-error-summary",
        "--no-pretty",
        "--no-color-output",
    ]
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    output = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
    budgets: Counter[str] = Counter()
    for line in output.splitlines():
        match = MYPY_ERROR.match(line.strip())
        if not match:
            continue
        path = str(match.group(1)).replace("\\", "/")
        try:
            path = Path(path).resolve().relative_to(root).as_posix()
        except ValueError:
            pass
        budgets[f"{path}|{match.group(2)}"] += 1
    strict = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", "--no-pretty", "--no-color-output"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "status": "measured" if completed.returncode in {0, 1} else "tool_failed",
        "command_returncode": completed.returncode,
        "total_errors": sum(budgets.values()),
        "error_budgets": dict(sorted(budgets.items())),
        "strict_status": "passed" if strict.returncode == 0 else "failed",
        "strict_returncode": strict.returncode,
    }


def collect_complexity_metrics(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    resolved = root.resolve()
    source_hash = active_source_tree_hash(resolved)
    policy_json = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return deepcopy(_collect_complexity_metrics_cached(str(resolved), source_hash, policy_json))


@lru_cache(maxsize=8)
def _collect_complexity_metrics_cached(root: str, source_hash: str, policy_json: str) -> dict[str, Any]:
    path = Path(root)
    metrics = _collect_complexity_metrics_uncached(path, json.loads(policy_json))
    if active_source_tree_hash(path) != source_hash:
        raise RuntimeError("Active source changed while collecting complexity metrics.")
    return metrics


def _collect_complexity_metrics_uncached(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    oversized_functions: list[dict[str, Any]] = []
    oversized_modules: list[dict[str, Any]] = []
    blockers: list[str] = []
    debt = {str(row["path"]): row for row in policy.get("module_size_debt") or []}
    for path in _active_python_files(root):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        line_count = len(source.splitlines())
        layer, limit = _function_layer_limit(relative)
        if line_count > int(policy["complexity"]["module_default_max_lines"]):
            row = {"path": relative, "lines": line_count}
            oversized_modules.append(row)
            allowance = debt.get(relative)
            if allowance is None:
                blockers.append(f"v14_quality_module_size_unregistered:{relative}:{line_count}")
            elif line_count > int(allowance["max_lines"]):
                blockers.append(f"v14_quality_module_size_grew:{relative}:{line_count}>{allowance['max_lines']}")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            lines = int(node.end_lineno or node.lineno) - int(node.lineno) + 1
            if lines > limit:
                oversized_functions.append(
                    {"path": relative, "name": node.name, "line": node.lineno, "lines": lines, "limit": limit, "layer": layer}
                )
                blockers.append(f"v14_quality_function_size:{relative}:{node.name}:{lines}>{limit}")
    aggregate = {
        "oversized_module_count": len(oversized_modules),
        "modules_over_1000_lines": sum(1 for row in oversized_modules if int(row["lines"]) > 1000),
        "largest_module_lines": max((int(row["lines"]) for row in oversized_modules), default=0),
        "total_oversized_module_lines": sum(int(row["lines"]) for row in oversized_modules),
    }
    aggregate_policy = policy.get("complexity", {}).get("aggregate_debt") or {}
    aggregate_limits = (
        ("oversized_module_count", "max_oversized_module_count"),
        ("modules_over_1000_lines", "max_modules_over_1000_lines"),
        ("largest_module_lines", "max_largest_module_lines"),
        ("total_oversized_module_lines", "max_total_oversized_module_lines"),
    )
    for metric, maximum in aggregate_limits:
        if maximum in aggregate_policy and int(aggregate[metric]) > int(aggregate_policy[maximum]):
            blockers.append(
                f"v14_quality_complexity_{metric}:{aggregate[metric]}>{aggregate_policy[maximum]}"
            )
    decision = str(aggregate_policy.get("architecture_decision") or "")
    if aggregate_policy and (not decision or not (root / decision).is_file()):
        blockers.append("v14_quality_complexity_architecture_decision_missing")
    return {
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "oversized_function_count": len(oversized_functions),
        "oversized_functions": oversized_functions,
        "registered_oversized_module_count": len(oversized_modules),
        "oversized_modules": oversized_modules,
        "aggregate": aggregate,
    }


def collect_coverage_metrics(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    coverage_policy = policy.get("coverage") or {}
    report_path = _rooted(root, str(coverage_policy.get("report_path") or "runs/v14-quality/coverage.json"))
    blockers: list[str] = []
    if not report_path.is_file():
        return {"status": "missing", "blockers": ["v14_quality_coverage_report_missing"], "layers": {}}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    files = report.get("files") or {}
    if report.get("schema_version") != 2:
        blockers.append("v14_quality_coverage_schema")
    if report.get("package_type") != "musicforge_v14_coverage_evidence":
        blockers.append("v14_quality_coverage_package_type")
    if int(report.get("file_count") or -1) != len(files):
        blockers.append("v14_quality_coverage_file_count")
    if report.get("source_report_semantic_hash") != coverage_semantic_hash(files):
        blockers.append("v14_quality_coverage_semantic_hash")
    expected_hash = str(coverage_policy.get("report_sha256") or "")
    if expected_hash and _file_hash(report_path) != expected_hash:
        blockers.append("v14_quality_coverage_report_hash")
    expected_source = str(coverage_policy.get("source_tree_hash") or "")
    if expected_source and active_source_tree_hash(root) != expected_source:
        blockers.append("v14_quality_coverage_source_stale")
    roots = {
        "active": COVERAGE_ROOTS,
        "verification_kernel": ("song_agent/platform/verification",),
        "lifecycle_kernel": ("song_agent/platform/lifecycle",),
        "persistence_kernel": ("song_agent/platform/persistence",),
        "policy_kernel": ("song_agent/platform/policy",),
    }
    layers = {name: _coverage_totals(report, values) for name, values in roots.items()}
    migration = json.loads((root / "architecture-v14-domain-migration.json").read_text(encoding="utf-8"))
    migrated_paths = tuple(
        str(row["target"]).replace(".", "/")
        for wave in migration.get("waves") or []
        for row in wave.get("modules") or []
        if row.get("target")
    )
    layers["migrated"] = _coverage_totals(report, migrated_paths, exact=True)
    minimums = coverage_policy.get("minimum_percent") or {}
    for name, minimum in minimums.items():
        if float(layers.get(name, {}).get("percent") or 0.0) < float(minimum):
            blockers.append(f"v14_quality_coverage_{name}:{layers.get(name, {}).get('percent', 0.0)}<{minimum}")
    return {"status": "passed" if not blockers else "failed", "blockers": blockers, "layers": layers}


def active_source_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    paths = sorted(
        path
        for relative in COVERAGE_ROOTS
        for path in (root / relative).rglob("*.py")
        if path.is_file()
    )
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(canonical_text_bytes(path.read_bytes()))
        digest.update(b"\0")
    return digest.hexdigest()


def coverage_semantic_hash(files: dict[str, Any]) -> str:
    return stable_hash({"files": files})


def build_v14_quality_policy(root: Path, *, coverage_report: Path | None = None) -> dict[str, Any]:
    typing = collect_typing_metrics(root)
    mypy = collect_mypy_metrics(root)
    module_debt: list[dict[str, Any]] = []
    maximum = 600
    for path in _active_python_files(root):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > maximum:
            module_debt.append(
                {"path": path.relative_to(root).as_posix(), "max_lines": lines, "expires_version": "14.3.0"}
            )
    report = coverage_report or root / "runs/v14-quality/coverage.json"
    coverage_bound = coverage_report is not None and report.is_file()
    document: dict[str, Any] = {
        "schema_version": 1,
        "package_type": "musicforge_v14_quality_policy",
        "release_version": QUALITY_POLICY_VERSION,
        "typing": {
            "activation_baseline_dict_str_any_count": 12535,
            "raw_dict_str_any_max_count": 8774,
            "implementation_document_max_count": typing["implementation_document_count"],
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": typing["explicit_any_count"],
            "explicit_any_affected_file_max_count": typing["explicit_any_affected_file_count"],
            "explicit_any_layer_budgets": typing["explicit_any_by_layer"],
            "explicit_any_file_budgets": typing["explicit_any_by_file"],
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        },
        "mypy": {
            "active_roots": list(MYPY_ROOTS),
            "max_total_errors": mypy["total_errors"],
            "error_budgets": mypy["error_budgets"],
            "strict_required": True,
        },
        "complexity": {
            "interface_api_max_lines": 100,
            "interface_cli_max_lines": 120,
            "application_max_lines": 150,
            "domain_max_lines": 200,
            "module_default_max_lines": 600,
            "new_module_max_lines": 400,
            "aggregate_debt": {
                "architecture_decision": V1421_STABILIZATION_ADR,
                "expires_version": "14.3.0",
                "max_oversized_module_count": V1421_RECOVERY_LIMITS["oversized_module_max_count"],
                "max_modules_over_1000_lines": V1421_RECOVERY_LIMITS["modules_over_1000_max_count"],
                "max_largest_module_lines": V1421_RECOVERY_LIMITS["largest_module_max_lines"],
                "max_total_oversized_module_lines": V1421_RECOVERY_LIMITS["total_oversized_module_max_lines"],
            },
        },
        "module_size_debt": module_debt,
        "stabilization": {
            "architecture_decision": V1421_STABILIZATION_ADR,
            "strategy": "rollback_generated_v142_split_to_v14.1.2_structure",
            "collector_migration": {
                "from_schema_version": 2,
                "to_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
                "previous_explicit_any_count": 11744,
                "recovered_explicit_any_count": typing["explicit_any_count"],
            },
            "hard_limits": V1421_RECOVERY_LIMITS,
            "explicit_any_file_budgets_hash": V1421_EXPLICIT_ANY_FILE_BUDGETS_HASH,
            "module_debt_ceilings_hash": V1421_MODULE_DEBT_CEILINGS_HASH,
        },
        "coverage": {
            "report_path": report.relative_to(root).as_posix() if report.is_absolute() else report.as_posix(),
            "report_sha256": _file_hash(report) if coverage_bound else "",
            "source_tree_hash": active_source_tree_hash(root) if coverage_bound else "",
            "minimum_percent": {
                "active": 60.0,
                "verification_kernel": 85.0,
                "lifecycle_kernel": 85.0,
                "persistence_kernel": 85.0,
                "policy_kernel": 85.0,
                "migrated": 80.0,
            },
        },
        "integrity_hash": "",
    }
    document["integrity_hash"] = stable_hash({key: value for key, value in document.items() if key != "integrity_hash"})
    return document


def run_v14_interface_application_boundary_smoke(root: Path) -> tuple[bool, str]:
    report = evaluate_v14_quality(root, run_mypy=False, require_coverage=False)
    blockers = [
        value
        for value in report["blockers"]
        if "coverage" not in value and "mypy" not in value and "typing_raw" not in value
    ]
    detail = {
        "status": "passed" if not blockers else "failed",
        "oversized_functions": report["complexity"]["oversized_function_count"],
        "untyped_public": report["typing"]["untyped_public_function_count"],
        "public_dynamic_documents": report["typing"]["public_implementation_document_count"],
        "blockers": blockers,
    }
    return not blockers, json.dumps(detail, sort_keys=True)


def run_v14_typing_coverage_ratchet_smoke(root: Path) -> tuple[bool, str]:
    report = evaluate_v14_quality(root)
    detail = {
        "status": report["status"],
        "raw_dict_str_any": report["typing"]["raw_dict_str_any_count"],
        "explicit_any": report["typing"]["explicit_any_count"],
        "mypy_errors": report["mypy"]["total_errors"],
        "strict_mypy": report["mypy"]["strict_status"],
        "coverage": report["coverage"]["layers"],
        "blockers": report["blockers"],
    }
    return report["status"] == "passed", json.dumps(detail, sort_keys=True)


def run_v141_quality_debt_closure_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "song_agent", "tests", "tools"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    from song_agent.release_check.performance import (
        CI_PROFILE_DURATION_BUDGET_SECONDS,
        CI_PROFILE_DURATION_PREVIOUS_BUDGET_SECONDS,
    )

    aggregate = dict((policy.get("complexity") or {}).get("aggregate_debt") or {})
    policy_integrity = policy.get("integrity_hash") == stable_hash(
        {key: value for key, value in policy.items() if key != "integrity_hash"}
    )
    details = {
        "policy_integrity": policy_integrity,
        "mypy_budget": int((policy.get("mypy") or {}).get("max_total_errors") or 0),
        "mypy_roots": list((policy.get("mypy") or {}).get("active_roots") or []),
        "ruff_status": "passed" if ruff.returncode == 0 else "failed",
        "explicit_any_alias_probe": _explicit_any_alias_probe(),
        "explicit_any_scope_probe": _explicit_any_scope_probe(),
        "explicit_any_lambda_scope_probe": _explicit_any_lambda_scope_probe(),
        "explicit_any_definition_time_scope_probe": _explicit_any_definition_time_probe(),
        "explicit_any_class_global_scope_probe": _explicit_any_class_global_scope_probe(),
        "explicit_any_indirect_target_scope_probe": _explicit_any_indirect_target_scope_probe(),
        "explicit_any_derived_uncertain_scope_probe": _explicit_any_derived_uncertain_scope_probe(),
        "explicit_any_object_alias_scope_probe": _explicit_any_object_alias_scope_probe(),
        "explicit_any_collector_schema_version": int(
            (policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0
        ),
        "explicit_any_max": int((policy.get("typing") or {}).get("explicit_any_max_count") or 0),
        "explicit_any_layer_budgets": dict((policy.get("typing") or {}).get("explicit_any_layer_budgets") or {}),
        "complexity": aggregate,
        "complexity_decision_present": bool(aggregate.get("architecture_decision"))
        and (root / str(aggregate["architecture_decision"])).is_file(),
        "ci_budget_ratchet": all(
            CI_PROFILE_DURATION_BUDGET_SECONDS[profile] < previous
            for profile, previous in CI_PROFILE_DURATION_PREVIOUS_BUDGET_SECONDS.items()
        ),
    }
    passed = (
        policy_integrity
        and policy.get("release_version") == QUALITY_POLICY_VERSION
        and details["mypy_budget"] == 0
        and details["mypy_roots"] == list(MYPY_ROOTS)
        and ruff.returncode == 0
        and details["explicit_any_alias_probe"]
        and details["explicit_any_scope_probe"]
        and details["explicit_any_lambda_scope_probe"]
        and details["explicit_any_definition_time_scope_probe"]
        and details["explicit_any_class_global_scope_probe"]
        and details["explicit_any_indirect_target_scope_probe"]
        and details["explicit_any_derived_uncertain_scope_probe"]
        and details["explicit_any_object_alias_scope_probe"]
        and details["explicit_any_collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
        and details["complexity_decision_present"]
        and details["ci_budget_ratchet"]
    )
    return passed, json.dumps(details, sort_keys=True)


def collect_v1421_static_violations(root: Path) -> dict[str, Any]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    mypy_config = dict((pyproject.get("tool") or {}).get("mypy") or {})
    active_files = _active_python_files(root)
    generated_modules: list[str] = []
    suppressions: list[str] = []
    runtime_global_binders: list[str] = []
    for path in active_files:
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        if path.name.startswith("v142_"):
            generated_modules.append(relative)
        if "# mypy: ignore-errors" in source or "# ruff: noqa" in source:
            suppressions.append(relative)
        if "bind_globals(globals())" in source:
            runtime_global_binders.append(relative)
    return {
        "generated_modules": sorted(generated_modules),
        "splitter_present": (root / "tools" / "split_v142_oversized_modules.py").exists(),
        "suppressions": sorted(suppressions),
        "runtime_global_binders": sorted(runtime_global_binders),
        "mypy_roots_complete": list(mypy_config.get("files") or []) == list(MYPY_ROOTS),
        "mypy_exclude": mypy_config.get("exclude"),
    }


def run_v1421_stabilization_rollback_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    complexity = collect_complexity_metrics(root, policy)
    violations = collect_v1421_static_violations(root)
    stabilization = dict(policy.get("stabilization") or {})
    hard_limits = V1421_RECOVERY_LIMITS
    actual_limits = {
        "active_python_file_max_count": int(typing["active_python_file_count"]),
        "explicit_any_max_count": int(typing["explicit_any_count"]),
        "explicit_any_affected_file_max_count": int(typing["explicit_any_affected_file_count"]),
        "raw_dict_str_any_max_count": int(typing["raw_dict_str_any_count"]),
        "implementation_document_max_count": int(typing["implementation_document_count"]),
        "explicit_any_layer_max_counts": dict(typing["explicit_any_by_layer"]),
        "oversized_module_max_count": int(complexity["aggregate"]["oversized_module_count"]),
        "modules_over_1000_max_count": int(complexity["aggregate"]["modules_over_1000_lines"]),
        "largest_module_max_lines": int(complexity["aggregate"]["largest_module_lines"]),
        "total_oversized_module_max_lines": int(complexity["aggregate"]["total_oversized_module_lines"]),
    }
    hard_limits_passed = all(
        actual_limits[key] <= maximum
        for key, maximum in hard_limits.items()
        if key != "explicit_any_layer_max_counts"
    ) and all(
        int(actual_limits["explicit_any_layer_max_counts"].get(layer, 0)) <= int(maximum)
        for layer, maximum in hard_limits["explicit_any_layer_max_counts"].items()
    )
    policy_blockers = [*_policy_blockers(policy), *_typing_blockers(typing, policy), *complexity["blockers"]]
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "collector_nested_scope_probe": _explicit_any_alias_probe(),
        "collector_control_flow_scope_probe": _explicit_any_scope_probe(),
        "collector_lambda_scope_probe": _explicit_any_lambda_scope_probe(),
        "collector_definition_time_scope_probe": _explicit_any_definition_time_probe(),
        "collector_class_global_scope_probe": _explicit_any_class_global_scope_probe(),
        "collector_indirect_target_scope_probe": _explicit_any_indirect_target_scope_probe(),
        "collector_derived_uncertain_scope_probe": _explicit_any_derived_uncertain_scope_probe(),
        "collector_object_alias_scope_probe": _explicit_any_object_alias_scope_probe(),
        "generated_v142_modules_absent": not violations["generated_modules"],
        "splitter_absent": not violations["splitter_present"],
        "active_suppressions_absent": not violations["suppressions"],
        "runtime_global_binders_absent": not violations["runtime_global_binders"],
        "mypy_roots_complete": bool(violations["mypy_roots_complete"]),
        "mypy_exclude_absent": not violations["mypy_exclude"],
        "policy_hard_limits_immutable": stabilization.get("hard_limits") == hard_limits,
        "policy_typing_file_budgets_immutable": _explicit_any_file_budgets_hash(policy)
        == V1421_EXPLICIT_ANY_FILE_BUDGETS_HASH,
        "policy_module_debt_ceilings_immutable": _module_debt_ceilings_hash(policy)
        == V1421_MODULE_DEBT_CEILINGS_HASH,
        "policy_strategy": stabilization.get("strategy") == "rollback_generated_v142_split_to_v14.1.2_structure",
        "architecture_decision_present": (root / V1421_STABILIZATION_ADR).is_file(),
        "hard_recovery_limits_passed": hard_limits_passed,
        "quality_policy_passed": not policy_blockers,
    }
    details = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "actual_limits": actual_limits,
        "hard_limits": hard_limits,
        "static_violations": violations,
        "policy_blockers": policy_blockers,
    }
    return all(checks.values()), json.dumps(details, sort_keys=True)


def run_v1422_explicit_any_scope_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    stabilization = dict(policy.get("stabilization") or {})
    collector_hotfix = dict(stabilization.get("collector_hotfix") or {})
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_schema_current": int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "scope_collector_migration_recorded": int(collector_hotfix.get("to_schema_version") or 0) == 5,
        "conditional_scope_probe": _explicit_any_scope_probe(),
        "existing_alias_probe": _explicit_any_alias_probe(),
        "collector_decision_present": stabilization.get("collector_decision") == V1422_COLLECTOR_ADR
        and (root / V1422_COLLECTOR_ADR).is_file(),
        "recovery_ceilings_unchanged": stabilization.get("hard_limits") == V1421_RECOVERY_LIMITS,
        "quality_policy_passed": not _policy_blockers(policy) and not _typing_blockers(typing, policy),
    }
    detail = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "explicit_any_count": typing["explicit_any_count"],
        "affected_file_count": typing["explicit_any_affected_file_count"],
    }
    return all(checks.values()), json.dumps(detail, sort_keys=True)


def run_v1423_explicit_any_lambda_scope_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    stabilization = dict(policy.get("stabilization") or {})
    lambda_hotfix = dict(stabilization.get("lambda_collector_hotfix") or {})
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_schema_current": int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "lambda_scope_probe": _explicit_any_lambda_scope_probe(),
        "lambda_collector_decision_present": stabilization.get("lambda_collector_decision")
        == V1423_LAMBDA_COLLECTOR_ADR
        and (root / V1423_LAMBDA_COLLECTOR_ADR).is_file(),
        "lambda_collector_migration_recorded": int(lambda_hotfix.get("from_schema_version") or 0) == 5
        and int(lambda_hotfix.get("to_schema_version") or 0) == 6,
        "recovery_ceilings_unchanged": stabilization.get("hard_limits") == V1421_RECOVERY_LIMITS,
        "quality_policy_passed": not _policy_blockers(policy) and not _typing_blockers(typing, policy),
    }
    detail = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "explicit_any_count": typing["explicit_any_count"],
        "affected_file_count": typing["explicit_any_affected_file_count"],
    }
    return all(checks.values()), json.dumps(detail, sort_keys=True)


def run_v1424_explicit_any_definition_time_scope_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    stabilization = dict(policy.get("stabilization") or {})
    definition_hotfix = dict(stabilization.get("definition_time_collector_hotfix") or {})
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_schema_current": int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_version_current": policy.get("release_version") == QUALITY_POLICY_VERSION,
        "definition_time_scope_probe": _explicit_any_definition_time_probe(),
        "definition_time_collector_decision_present": stabilization.get("definition_time_collector_decision")
        == V1424_DEFINITION_TIME_COLLECTOR_ADR
        and (root / V1424_DEFINITION_TIME_COLLECTOR_ADR).is_file(),
        "definition_time_collector_migration_recorded": int(definition_hotfix.get("from_schema_version") or 0) == 6
        and int(definition_hotfix.get("to_schema_version") or 0) == 7,
        "recovery_ceilings_unchanged": stabilization.get("hard_limits") == V1421_RECOVERY_LIMITS,
        "quality_policy_passed": not _policy_blockers(policy) and not _typing_blockers(typing, policy),
    }
    detail = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "explicit_any_count": typing["explicit_any_count"],
        "affected_file_count": typing["explicit_any_affected_file_count"],
    }
    return all(checks.values()), json.dumps(detail, sort_keys=True)


def run_v1425_explicit_any_class_global_scope_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    stabilization = dict(policy.get("stabilization") or {})
    class_global_hotfix = dict(stabilization.get("class_global_collector_hotfix") or {})
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_schema_current": int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_version_current": policy.get("release_version") == QUALITY_POLICY_VERSION,
        "class_global_scope_probe": _explicit_any_class_global_scope_probe(),
        "active_scope_flow_clear": int(typing.get("explicit_any_scope_blocker_count") or 0) == 0,
        "class_global_collector_decision_present": stabilization.get("class_global_collector_decision")
        == V1425_CLASS_GLOBAL_COLLECTOR_ADR
        and (root / V1425_CLASS_GLOBAL_COLLECTOR_ADR).is_file(),
        "class_global_collector_migration_recorded": int(class_global_hotfix.get("from_schema_version") or 0) == 7
        and int(class_global_hotfix.get("to_schema_version") or 0) == 8,
        "recovery_ceilings_unchanged": stabilization.get("hard_limits") == V1421_RECOVERY_LIMITS,
        "quality_policy_passed": not _policy_blockers(policy) and not _typing_blockers(typing, policy),
    }
    detail = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "explicit_any_count": typing["explicit_any_count"],
        "affected_file_count": typing["explicit_any_affected_file_count"],
        "scope_flow_blockers": typing.get("explicit_any_scope_blockers") or [],
    }
    return all(checks.values()), json.dumps(detail, sort_keys=True)


def run_v1426_explicit_any_indirect_target_scope_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    stabilization = dict(policy.get("stabilization") or {})
    indirect_hotfix = dict(stabilization.get("indirect_target_collector_hotfix") or {})
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_schema_current": int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_version_current": policy.get("release_version") == QUALITY_POLICY_VERSION,
        "indirect_target_scope_probe": _explicit_any_indirect_target_scope_probe(),
        "active_scope_flow_clear": int(typing.get("explicit_any_scope_blocker_count") or 0) == 0,
        "indirect_target_collector_decision_present": stabilization.get("indirect_target_collector_decision")
        == V1426_INDIRECT_TARGET_COLLECTOR_ADR
        and (root / V1426_INDIRECT_TARGET_COLLECTOR_ADR).is_file(),
        "indirect_target_collector_migration_recorded": int(indirect_hotfix.get("from_schema_version") or 0) == 8
        and int(indirect_hotfix.get("to_schema_version") or 0) == 9,
        "recovery_ceilings_unchanged": stabilization.get("hard_limits") == V1421_RECOVERY_LIMITS,
        "quality_policy_passed": not _policy_blockers(policy) and not _typing_blockers(typing, policy),
    }
    detail = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "explicit_any_count": typing["explicit_any_count"],
        "affected_file_count": typing["explicit_any_affected_file_count"],
        "scope_flow_blockers": typing.get("explicit_any_scope_blockers") or [],
    }
    return all(checks.values()), json.dumps(detail, sort_keys=True)


def run_v1427_explicit_any_derived_uncertain_scope_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    stabilization = dict(policy.get("stabilization") or {})
    derived_hotfix = dict(stabilization.get("derived_uncertain_collector_hotfix") or {})
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_schema_current": int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_version_current": policy.get("release_version") == QUALITY_POLICY_VERSION,
        "derived_uncertain_scope_probe": _explicit_any_derived_uncertain_scope_probe(),
        "active_scope_flow_clear": int(typing.get("explicit_any_scope_blocker_count") or 0) == 0,
        "derived_uncertain_collector_decision_present": stabilization.get("derived_uncertain_collector_decision")
        == V1427_DERIVED_UNCERTAIN_COLLECTOR_ADR
        and (root / V1427_DERIVED_UNCERTAIN_COLLECTOR_ADR).is_file(),
        "derived_uncertain_collector_migration_recorded": int(derived_hotfix.get("from_schema_version") or 0) == 9
        and int(derived_hotfix.get("to_schema_version") or 0) == 10,
        "recovery_ceilings_unchanged": stabilization.get("hard_limits") == V1421_RECOVERY_LIMITS,
        "quality_policy_passed": not _policy_blockers(policy) and not _typing_blockers(typing, policy),
    }
    detail = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "explicit_any_count": typing["explicit_any_count"],
        "affected_file_count": typing["explicit_any_affected_file_count"],
        "scope_flow_blockers": typing.get("explicit_any_scope_blockers") or [],
    }
    return all(checks.values()), json.dumps(detail, sort_keys=True)


def run_v1428_explicit_any_object_alias_scope_smoke(root: Path) -> tuple[bool, str]:
    policy = json.loads((root / QUALITY_POLICY_PATH).read_text(encoding="utf-8"))
    typing = collect_typing_metrics(root)
    stabilization = dict(policy.get("stabilization") or {})
    alias_hotfix = dict(stabilization.get("object_alias_collector_hotfix") or {})
    checks = {
        "collector_schema_current": typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_schema_current": int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "policy_version_current": policy.get("release_version") == QUALITY_POLICY_VERSION,
        "object_alias_scope_probe": _explicit_any_object_alias_scope_probe(),
        "active_scope_flow_clear": int(typing.get("explicit_any_scope_blocker_count") or 0) == 0,
        "object_alias_collector_decision_present": stabilization.get("object_alias_collector_decision")
        == V1428_OBJECT_ALIAS_COLLECTOR_ADR
        and (root / V1428_OBJECT_ALIAS_COLLECTOR_ADR).is_file(),
        "object_alias_collector_migration_recorded": int(alias_hotfix.get("from_schema_version") or 0) == 10
        and int(alias_hotfix.get("to_schema_version") or 0) == 11,
        "recovery_ceilings_unchanged": stabilization.get("hard_limits") == V1421_RECOVERY_LIMITS,
        "quality_policy_passed": not _policy_blockers(policy) and not _typing_blockers(typing, policy),
    }
    detail = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "explicit_any_count": typing["explicit_any_count"],
        "affected_file_count": typing["explicit_any_affected_file_count"],
        "scope_flow_blockers": typing.get("explicit_any_scope_blockers") or [],
    }
    return all(checks.values()), json.dumps(detail, sort_keys=True)


def _typing_blockers(metrics: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    limits = policy.get("typing") or {}
    blockers: list[str] = []
    if int(limits.get("explicit_any_collector_schema_version") or 0) != EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION:
        blockers.append("v14_quality_typing_explicit_any_collector_schema")
    if int(metrics.get("collector_schema_version") or 0) != EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION:
        blockers.append("v14_quality_typing_metrics_collector_schema")
    blockers.extend(
        "v14_quality_typing_explicit_any_scope_flow:"
        f"{row.get('path', '<unknown>')}:{row.get('detail', 'unsupported')}"
        for row in metrics.get("explicit_any_scope_blockers") or []
        if isinstance(row, dict)
    )
    fields = (
        ("raw_dict_str_any_count", "raw_dict_str_any_max_count", "typing_raw_dict_str_any"),
        ("implementation_document_count", "implementation_document_max_count", "typing_implementation_document"),
        ("explicit_any_count", "explicit_any_max_count", "typing_explicit_any"),
        (
            "explicit_any_affected_file_count",
            "explicit_any_affected_file_max_count",
            "typing_explicit_any_affected_files",
        ),
        ("public_implementation_document_count", "public_implementation_document_max_count", "typing_public_dynamic"),
        ("untyped_public_function_count", "untyped_public_function_max_count", "typing_untyped_public"),
    )
    blockers.extend(
        f"v14_quality_{label}:{metrics[current]}>{limits[maximum]}"
        for current, maximum, label in fields
        if maximum in limits
        if int(metrics[current]) > int(limits[maximum])
    )
    layer_limits = {str(key): int(value) for key, value in (limits.get("explicit_any_layer_budgets") or {}).items()}
    layer_actual = {str(key): int(value) for key, value in (metrics.get("explicit_any_by_layer") or {}).items()}
    for layer, count in sorted(layer_actual.items()):
        maximum = layer_limits.get(layer, 0)
        if count > maximum:
            blockers.append(f"v14_quality_typing_explicit_any_layer:{layer}:{count}>{maximum}")
    file_limits = {str(key): int(value) for key, value in (limits.get("explicit_any_file_budgets") or {}).items()}
    file_actual = {str(key): int(value) for key, value in (metrics.get("explicit_any_by_file") or {}).items()}
    for path, count in sorted(file_actual.items()):
        maximum = file_limits.get(path, 0)
        if count > maximum:
            blockers.append(f"v14_quality_typing_explicit_any_file:{path}:{count}>{maximum}")
    return blockers


def _mypy_blockers(metrics: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    expected = policy.get("mypy") or {}
    blockers: list[str] = []
    if metrics["status"] != "measured":
        blockers.append("v14_quality_mypy_tool_failed")
        return blockers
    if int(metrics["total_errors"]) > int(expected.get("max_total_errors") or 0):
        blockers.append(f"v14_quality_mypy_total:{metrics['total_errors']}>{expected.get('max_total_errors')}")
    allowed = {str(key): int(value) for key, value in (expected.get("error_budgets") or {}).items()}
    actual = {str(key): int(value) for key, value in metrics["error_budgets"].items()}
    new = {key: value for key, value in actual.items() if key not in allowed}
    grown = {key: value for key, value in actual.items() if key in allowed and value > allowed[key]}
    metrics["new_error_budgets"] = new
    metrics["grown_error_budgets"] = grown
    if new:
        blockers.append(f"v14_quality_mypy_new_error_budget:{len(new)}")
    if grown:
        blockers.append(f"v14_quality_mypy_grown_error_budget:{len(grown)}")
    if expected.get("strict_required") and metrics["strict_status"] != "passed":
        blockers.append("v14_quality_mypy_strict")
    return blockers


def _policy_blockers(policy: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = stable_hash({key: value for key, value in policy.items() if key != "integrity_hash"})
    if policy.get("integrity_hash") != expected:
        blockers.append("v14_quality_policy_integrity")
    if policy.get("package_type") != "musicforge_v14_quality_policy":
        blockers.append("v14_quality_policy_type")
    if policy.get("release_version") != QUALITY_POLICY_VERSION:
        blockers.append("v14_quality_policy_version")
    if int((policy.get("typing") or {}).get("raw_dict_str_any_max_count") or 0) > 8774:
        blockers.append("v14_quality_policy_typing_loosened")
    if "explicit_any_max_count" not in (policy.get("typing") or {}):
        blockers.append("v14_quality_policy_explicit_any_missing")
    if (
        int((policy.get("typing") or {}).get("explicit_any_collector_schema_version") or 0)
        != EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    ):
        blockers.append("v14_quality_policy_explicit_any_collector_schema")
    if int((policy.get("mypy") or {}).get("max_total_errors") or 0) != 0:
        blockers.append("v14_quality_policy_mypy_debt_not_closed")
    stabilization = policy.get("stabilization") or {}
    if stabilization.get("architecture_decision") != V1421_STABILIZATION_ADR:
        blockers.append("v14_quality_policy_stabilization_decision")
    if stabilization.get("collector_decision") != V1422_COLLECTOR_ADR:
        blockers.append("v14_quality_policy_collector_decision")
    if stabilization.get("lambda_collector_decision") != V1423_LAMBDA_COLLECTOR_ADR:
        blockers.append("v14_quality_policy_lambda_collector_decision")
    lambda_hotfix = stabilization.get("lambda_collector_hotfix") or {}
    if (
        int(lambda_hotfix.get("from_schema_version") or 0) != 5
        or int(lambda_hotfix.get("to_schema_version") or 0) != 6
    ):
        blockers.append("v14_quality_policy_lambda_collector_migration")
    if stabilization.get("definition_time_collector_decision") != V1424_DEFINITION_TIME_COLLECTOR_ADR:
        blockers.append("v14_quality_policy_definition_time_collector_decision")
    definition_hotfix = stabilization.get("definition_time_collector_hotfix") or {}
    if (
        int(definition_hotfix.get("from_schema_version") or 0) != 6
        or int(definition_hotfix.get("to_schema_version") or 0) != 7
    ):
        blockers.append("v14_quality_policy_definition_time_collector_migration")
    if stabilization.get("class_global_collector_decision") != V1425_CLASS_GLOBAL_COLLECTOR_ADR:
        blockers.append("v14_quality_policy_class_global_collector_decision")
    class_global_hotfix = stabilization.get("class_global_collector_hotfix") or {}
    if (
        int(class_global_hotfix.get("from_schema_version") or 0) != 7
        or int(class_global_hotfix.get("to_schema_version") or 0) != 8
    ):
        blockers.append("v14_quality_policy_class_global_collector_migration")
    if stabilization.get("indirect_target_collector_decision") != V1426_INDIRECT_TARGET_COLLECTOR_ADR:
        blockers.append("v14_quality_policy_indirect_target_collector_decision")
    indirect_hotfix = stabilization.get("indirect_target_collector_hotfix") or {}
    if (
        int(indirect_hotfix.get("from_schema_version") or 0) != 8
        or int(indirect_hotfix.get("to_schema_version") or 0) != 9
    ):
        blockers.append("v14_quality_policy_indirect_target_collector_migration")
    if stabilization.get("derived_uncertain_collector_decision") != V1427_DERIVED_UNCERTAIN_COLLECTOR_ADR:
        blockers.append("v14_quality_policy_derived_uncertain_collector_decision")
    derived_hotfix = stabilization.get("derived_uncertain_collector_hotfix") or {}
    if (
        int(derived_hotfix.get("from_schema_version") or 0) != 9
        or int(derived_hotfix.get("to_schema_version") or 0) != 10
    ):
        blockers.append("v14_quality_policy_derived_uncertain_collector_migration")
    if stabilization.get("object_alias_collector_decision") != V1428_OBJECT_ALIAS_COLLECTOR_ADR:
        blockers.append("v14_quality_policy_object_alias_collector_decision")
    alias_hotfix = stabilization.get("object_alias_collector_hotfix") or {}
    if (
        int(alias_hotfix.get("from_schema_version") or 0) != 10
        or int(alias_hotfix.get("to_schema_version") or 0) != 11
    ):
        blockers.append("v14_quality_policy_object_alias_collector_migration")
    if stabilization.get("hard_limits") != V1421_RECOVERY_LIMITS:
        blockers.append("v14_quality_policy_stabilization_limits")
    if _explicit_any_file_budgets_hash(policy) != V1421_EXPLICIT_ANY_FILE_BUDGETS_HASH:
        blockers.append("v14_quality_policy_stabilization_typing_file_budgets")
    if _module_debt_ceilings_hash(policy) != V1421_MODULE_DEBT_CEILINGS_HASH:
        blockers.append("v14_quality_policy_stabilization_module_debt")
    return blockers


def _explicit_any_file_budgets_hash(policy: dict[str, Any]) -> str:
    return stable_hash(dict((policy.get("typing") or {}).get("explicit_any_file_budgets") or {}))


def _module_debt_ceilings_hash(policy: dict[str, Any]) -> str:
    rows = [
        {"path": str(row.get("path") or ""), "max_lines": int(row.get("max_lines") or 0)}
        for row in policy.get("module_size_debt") or []
        if isinstance(row, dict)
    ]
    return stable_hash(rows)


def _public_functions(tree: ast.Module) -> Iterable[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str | None]]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            yield node, None
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_"):
                    yield child, node.name


def _function_annotations(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    skip_receiver: bool,
) -> list[ast.expr | None]:
    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if skip_receiver and arguments and arguments[0].arg in {"self", "cls"}:
        arguments = arguments[1:]
    annotations: list[ast.expr | None] = [argument.annotation for argument in arguments]
    if node.args.vararg:
        annotations.append(node.args.vararg.annotation)
    if node.args.kwarg:
        annotations.append(node.args.kwarg.annotation)
    return annotations


class _ExplicitAnyCollector(ast.NodeVisitor):
    """Count effective Any annotations without losing nested lexical scopes."""

    def __init__(self) -> None:
        self.count = 0
        self.blockers: list[str] = []
        self._scopes: list[dict[str, str]] = [{}]
        self._aliases: list[dict[str, frozenset[int]]] = [{}]
        self._next_alias_identity = 0
        self._potential_scopes: list[dict[str, str]] = []
        self._scope_kinds: list[str] = ["module"]
        self._global_names: list[set[str]] = [set()]
        self._nonlocal_names: list[set[str]] = [set()]
        self._control_flow_scopes: list[int] = []

    def visit_Module(self, node: ast.Module) -> None:
        self._visit_scope_body(node.body, push_scope=False, scope_kind="module")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_expressions(node.decorator_list)
        self._visit_expressions(node.bases)
        self._visit_expressions(keyword.value for keyword in node.keywords)
        self._visit_scope_body(node.body, push_scope=True, scope_kind="class")
        self._bind(node.name, "other")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # Defaults run in the enclosing scope when the lambda is created.
        # The body owns no annotations and runs in the lambda scope.
        self._visit_argument_defaults(node.args)

    def visit_Global(self, node: ast.Global) -> None:
        # Declarations are collected before the lexical scope is visited.
        return None

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        # Declarations are collected before the lexical scope is visited.
        return None

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name.split(".", 1)[0]
            kind = "typing-module" if alias.name in {"typing", "typing_extensions"} else "other"
            self._bind(name, kind)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*" and node.module in {"typing", "typing_extensions"}:
                self._bind("Any", "any")
                self._bind("TypeAlias", "type-alias-marker")
                self._bind("TYPE_CHECKING", "type-checking-marker")
                continue
            name = alias.asname or alias.name
            kind = "other"
            if node.module in {"typing", "typing_extensions"}:
                kind = {
                    "Any": "any",
                    "TypeAlias": "type-alias-marker",
                    "TYPE_CHECKING": "type-checking-marker",
                }.get(alias.name, "other")
            self._bind(name, kind)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if not self._is_type_alias_annotation(node.annotation):
            self.count += self._annotation_any_count(node.annotation)
        kind = self._expression_binding_kind(node.value) if node.value is not None else "other"
        aliases = self._expression_aliases(node.value) if node.value is not None else self._new_alias_identity()
        if node.value is not None:
            self.visit(node.value)
        self._bind_target(node.target, kind, aliases=aliases)

    def visit_Assign(self, node: ast.Assign) -> None:
        kind = self._expression_binding_kind(node.value)
        aliases = self._expression_aliases(node.value)
        self.visit(node.value)
        for target in node.targets:
            self._bind_target(target, kind, aliases=aliases)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        target_kind = self._expression_binding_kind(node.target)
        value_kind = self._expression_binding_kind(node.value)
        aliases = self._target_aliases(node.target)
        self.visit(node.value)
        kinds = {target_kind, value_kind}
        any_capable = {"any", "typing-module", "any-or-typing-module", "uncertain"}
        kind = "uncertain" if kinds & any_capable else "unknown" if "unknown" in kinds else "other"
        if isinstance(node.target, ast.Name) and kind in {"uncertain", "unknown"}:
            # Augmented assignment can mutate an object in place. A write
            # through one name must therefore taint every possible alias.
            self._taint_alias_group(node.target.id, kind=kind)
        self._bind_target(node.target, kind, aliases=aliases)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        kind = self._expression_binding_kind(node.value)
        aliases = self._expression_aliases(node.value)
        self.visit(node.value)
        self._bind_target(node.target, kind, aliases=aliases)

    def visit_Call(self, node: ast.Call) -> None:
        uncertain_arguments = [
            value
            for value in (*node.args, *(keyword.value for keyword in node.keywords))
            if self._expression_binding_kind(value) in {"any", "typing-module", "any-or-typing-module", "uncertain"}
        ]
        if uncertain_arguments:
            candidates: list[ast.expr] = [
                value
                for value in (*node.args, *(keyword.value for keyword in node.keywords))
                if value not in uncertain_arguments
            ]
            if isinstance(node.func, ast.Attribute):
                candidates.append(node.func.value)
            for candidate in candidates:
                for name in self._expression_alias_names(candidate):
                    self._taint_alias_group(name)
        self.generic_visit(node)

    def visit_TypeAlias(self, node: ast.AST) -> None:
        name = getattr(node, "name", None)
        value = getattr(node, "value", None)
        if isinstance(name, ast.Name) and isinstance(value, ast.expr):
            self._bind(name.id, self._expression_binding_kind(value))

    def visit_If(self, node: ast.If) -> None:
        self.visit(node.test)
        base = dict(self._scopes[-1])
        base_aliases = dict(self._aliases[-1])
        states = [self._visit_branch(node.body, base, base_aliases)]
        states.append(self._visit_branch(node.orelse, base, base_aliases) if node.orelse else (base, base_aliases))
        self._scopes[-1] = self._merge_branch_states([state[0] for state in states])
        self._aliases[-1] = self._merge_branch_aliases([state[1] for state in states])

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_try(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self._visit_try(node)

    def visit_With(self, node: ast.With) -> None:
        self._visit_with(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._visit_with(node)

    def visit_For(self, node: ast.For) -> None:
        self._visit_for(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._visit_for(node)

    def visit_While(self, node: ast.While) -> None:
        self.visit(node.test)
        base = dict(self._scopes[-1])
        base_aliases = dict(self._aliases[-1])
        body_state, body_aliases = self._visit_branch(node.body, base, base_aliases)
        merged = self._merge_branch_states([base, body_state])
        merged_aliases = self._merge_branch_aliases([base_aliases, body_aliases])
        if node.orelse:
            orelse_state, orelse_aliases = self._visit_branch(node.orelse, merged, merged_aliases)
            merged = self._merge_branch_states([merged, orelse_state])
            merged_aliases = self._merge_branch_aliases([merged_aliases, orelse_aliases])
        self._scopes[-1] = merged
        self._aliases[-1] = merged_aliases

    def visit_Match(self, node: ast.Match) -> None:
        target_kind = self._indirect_target_kind(node.subject)
        self.visit(node.subject)
        base = dict(self._scopes[-1])
        base_aliases = dict(self._aliases[-1])
        states = [base]
        alias_states = [base_aliases]
        for case in node.cases:
            self._scopes[-1] = dict(base)
            self._aliases[-1] = dict(base_aliases)
            self._control_flow_scopes.append(len(self._scopes) - 1)
            try:
                for name in _match_pattern_names(case.pattern):
                    self._bind(name, target_kind)
                if case.guard is not None:
                    self.visit(case.guard)
                self._visit_statements(case.body)
            finally:
                self._control_flow_scopes.pop()
            states.append(dict(self._scopes[-1]))
            alias_states.append(dict(self._aliases[-1]))
        self._scopes[-1] = self._merge_branch_states(states)
        self._aliases[-1] = self._merge_branch_aliases(alias_states)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._visit_expressions(node.decorator_list)
        self._visit_argument_defaults(node.args)
        for annotation in _function_annotations(node, skip_receiver=False):
            if annotation is not None:
                self.count += self._annotation_any_count(annotation)
        if node.returns is not None:
            self.count += self._annotation_any_count(node.returns)
        parameter_scope = {
            argument.arg: "other"
            for argument in (
                *node.args.posonlyargs,
                *node.args.args,
                *node.args.kwonlyargs,
            )
        }
        if node.args.vararg is not None:
            parameter_scope[node.args.vararg.arg] = "other"
        if node.args.kwarg is not None:
            parameter_scope[node.args.kwarg.arg] = "other"
        self._visit_scope_body(node.body, push_scope=True, initial=parameter_scope, scope_kind="function")
        self._bind(node.name, "other")

    def _visit_argument_defaults(self, arguments: ast.arguments) -> None:
        self._visit_expressions(arguments.defaults)
        self._visit_expressions(default for default in arguments.kw_defaults if default is not None)

    def _visit_expressions(self, expressions: Iterable[ast.expr]) -> None:
        for expression in expressions:
            self.visit(expression)

    def _visit_scope_body(
        self,
        body: list[ast.stmt],
        *,
        push_scope: bool,
        initial: dict[str, str] | None = None,
        scope_kind: str,
    ) -> None:
        global_names, nonlocal_names = _scope_declarations(body)
        if push_scope:
            self._scopes.append(dict(initial or {}))
            self._aliases.append({name: self._new_alias_identity() for name in (initial or {})})
            self._scope_kinds.append(scope_kind)
            self._global_names.append(global_names)
            self._nonlocal_names.append(nonlocal_names)
        else:
            self._scope_kinds[0] = scope_kind
            self._global_names[0] = global_names
            self._nonlocal_names[0] = nonlocal_names
        excluded = global_names | nonlocal_names
        self._potential_scopes.append(self._potential_scope_bindings(body, excluded=excluded))
        try:
            if global_names & nonlocal_names:
                self._add_blocker("conflicting_global_nonlocal:" + ",".join(sorted(global_names & nonlocal_names)))
            self._visit_statements(body)
        finally:
            self._potential_scopes.pop()
            if push_scope:
                self._scopes.pop()
                self._aliases.pop()
                self._scope_kinds.pop()
                self._global_names.pop()
                self._nonlocal_names.pop()

    def _visit_statements(self, body: list[ast.stmt]) -> None:
        for statement in body:
            self.visit(statement)

    def _visit_branch(
        self,
        body: list[ast.stmt],
        state: dict[str, str],
        aliases: dict[str, frozenset[int]],
    ) -> tuple[dict[str, str], dict[str, frozenset[int]]]:
        self._scopes[-1] = dict(state)
        self._aliases[-1] = dict(aliases)
        self._control_flow_scopes.append(len(self._scopes) - 1)
        try:
            self._visit_statements(body)
        finally:
            self._control_flow_scopes.pop()
        return dict(self._scopes[-1]), dict(self._aliases[-1])

    def _visit_try(self, node: ast.Try | ast.TryStar) -> None:
        base = dict(self._scopes[-1])
        base_aliases = dict(self._aliases[-1])
        normal_state, normal_aliases = self._visit_branch([*node.body, *node.orelse], base, base_aliases)
        states = [normal_state]
        alias_states = [normal_aliases]
        for handler in node.handlers:
            self._scopes[-1] = dict(base)
            self._aliases[-1] = dict(base_aliases)
            self._control_flow_scopes.append(len(self._scopes) - 1)
            try:
                if handler.type is not None:
                    self.visit(handler.type)
                if handler.name:
                    self._bind(handler.name, "other")
                self._visit_statements(handler.body)
            finally:
                self._control_flow_scopes.pop()
            states.append(dict(self._scopes[-1]))
            alias_states.append(dict(self._aliases[-1]))
        self._scopes[-1] = self._merge_branch_states(states)
        self._aliases[-1] = self._merge_branch_aliases(alias_states)
        self._visit_statements(node.finalbody)

    def _visit_with(self, node: ast.With | ast.AsyncWith) -> None:
        for item in node.items:
            target_kind = self._indirect_target_kind(item.context_expr)
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._bind_target(item.optional_vars, target_kind)
        self._control_flow_scopes.append(len(self._scopes) - 1)
        try:
            self._visit_statements(node.body)
        finally:
            self._control_flow_scopes.pop()

    def _visit_for(self, node: ast.For | ast.AsyncFor) -> None:
        target_kind = self._indirect_target_kind(node.iter)
        self.visit(node.iter)
        base = dict(self._scopes[-1])
        base_aliases = dict(self._aliases[-1])
        self._scopes[-1] = dict(base)
        self._aliases[-1] = dict(base_aliases)
        self._control_flow_scopes.append(len(self._scopes) - 1)
        try:
            self._bind_target(node.target, target_kind)
            self._visit_statements(node.body)
        finally:
            self._control_flow_scopes.pop()
        merged = self._merge_branch_states([base, dict(self._scopes[-1])])
        merged_aliases = self._merge_branch_aliases([base_aliases, dict(self._aliases[-1])])
        if node.orelse:
            orelse_state, orelse_aliases = self._visit_branch(node.orelse, merged, merged_aliases)
            merged = self._merge_branch_states([merged, orelse_state])
            merged_aliases = self._merge_branch_aliases([merged_aliases, orelse_aliases])
        self._scopes[-1] = merged
        self._aliases[-1] = merged_aliases

    def _potential_scope_bindings(self, body: list[ast.stmt], *, excluded: set[str]) -> dict[str, str]:
        statements = list(_lexical_scope_statements(body))
        potential: dict[str, str] = {}
        for statement in statements:
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    if alias.name in {"typing", "typing_extensions"}:
                        name = alias.asname or alias.name
                        if name not in excluded:
                            _merge_potential_binding(potential, name, "typing-module")
            elif isinstance(statement, ast.ImportFrom) and statement.module in {"typing", "typing_extensions"}:
                for alias in statement.names:
                    if alias.name == "*":
                        if "Any" not in excluded:
                            _merge_potential_binding(potential, "Any", "any")
                        if "TypeAlias" not in excluded:
                            _merge_potential_binding(potential, "TypeAlias", "type-alias-marker")
                        if "TYPE_CHECKING" not in excluded:
                            _merge_potential_binding(potential, "TYPE_CHECKING", "type-checking-marker")
                        continue
                    kind = {
                        "Any": "any",
                        "TypeAlias": "type-alias-marker",
                        "TYPE_CHECKING": "type-checking-marker",
                    }.get(alias.name)
                    name = alias.asname or alias.name
                    if kind and name not in excluded:
                        _merge_potential_binding(potential, name, kind)

        changed = True
        while changed:
            changed = False
            any_names = self._names_for("any") | {name for name, kind in potential.items() if kind == "any"}
            module_names = self._names_for("typing-module") | {
                name for name, kind in potential.items() if kind == "typing-module"
            }
            for statement in statements:
                targets: list[ast.expr] = []
                value: ast.expr | None = None
                if isinstance(statement, ast.Assign):
                    targets = list(statement.targets)
                    value = statement.value
                elif isinstance(statement, ast.AnnAssign):
                    targets = [statement.target]
                    value = statement.value
                elif isinstance(statement, ast.NamedExpr):
                    targets = [statement.target]
                    value = statement.value
                else:
                    type_alias_node = getattr(ast, "TypeAlias", None)
                    if type_alias_node is not None and isinstance(statement, type_alias_node):
                        alias_name = getattr(statement, "name", None)
                        if isinstance(alias_name, ast.expr):
                            targets = [alias_name]
                        candidate = getattr(statement, "value", None)
                        value = candidate if isinstance(candidate, ast.expr) else None
                if value is None:
                    continue
                kind = _potential_expression_binding_kind(value, any_names, module_names)
                if not kind:
                    continue
                for target in targets:
                    for name in _assignment_target_names(target):
                        if name not in excluded:
                            changed = _merge_potential_binding(potential, name, kind) or changed
        return potential

    def _bind(self, name: str, kind: str, *, aliases: frozenset[int] | None = None) -> None:
        target_index = self._binding_scope_index(name)
        if target_index is None:
            if self._binding_is_relevant(kind) or self._binding_is_relevant(self._resolve_outer_name(name)):
                self._add_blocker(f"unresolved_nonlocal:{name}")
            return
        current_index = len(self._scopes) - 1
        if target_index != current_index:
            previous = self._scopes[target_index].get(name, "")
            relevant = self._binding_is_relevant(kind) or self._binding_is_relevant(previous)
            if relevant and "function" in self._scope_kinds[1 : current_index + 1]:
                self._add_blocker(f"runtime_redirect:{self._scope_kinds[current_index]}:{name}")
            if relevant and self._control_flow_scopes and self._control_flow_scopes[-1] != target_index:
                self._add_blocker(f"cross_scope_control_flow:{name}")
        self._scopes[target_index][name] = kind
        self._aliases[target_index][name] = aliases or self._new_alias_identity()

    def _binding_scope_index(self, name: str) -> int | None:
        current_index = len(self._scopes) - 1
        if name in self._global_names[current_index]:
            return 0
        if name in self._nonlocal_names[current_index]:
            for index in range(current_index - 1, 0, -1):
                if self._scope_kinds[index] != "function":
                    continue
                if name in self._scopes[index] or (
                    index < len(self._potential_scopes) and name in self._potential_scopes[index]
                ):
                    return index
            return None
        return current_index

    @staticmethod
    def _binding_is_relevant(kind: str) -> bool:
        return kind in {"any", "typing-module", "any-or-typing-module", "type-alias-marker"}

    def _add_blocker(self, detail: str) -> None:
        if detail not in self.blockers:
            self.blockers.append(detail)

    def _merge_branch_states(self, states: list[dict[str, str]]) -> dict[str, str]:
        merged: dict[str, str] = {}
        for name in set().union(*(state.keys() for state in states)):
            kinds = [state[name] for state in states if name in state]
            if len(kinds) != len(states):
                inherited = self._resolve_outer_name(name)
                if inherited:
                    kinds.append(inherited)
            if kinds:
                # Any-capable branch bindings dominate ordinary or absent
                # bindings. Sequential statements still overwrite normally.
                merged[name] = _merge_binding_kinds(kinds)
        return merged

    @staticmethod
    def _merge_branch_aliases(states: list[dict[str, frozenset[int]]]) -> dict[str, frozenset[int]]:
        merged: dict[str, frozenset[int]] = {}
        for name in set().union(*(state.keys() for state in states)):
            identities = frozenset().union(*(state.get(name, frozenset()) for state in states))
            if identities:
                merged[name] = identities
        return merged

    def _resolve_outer_name(self, name: str) -> str:
        for index in range(len(self._scopes) - 2, -1, -1):
            if name in self._scopes[index]:
                return self._scopes[index][name]
            if index < len(self._potential_scopes) and name in self._potential_scopes[index]:
                return self._potential_scopes[index][name]
        return ""

    def _bind_target(
        self,
        target: ast.expr,
        kind: str,
        *,
        aliases: frozenset[int] | None = None,
    ) -> None:
        if isinstance(target, ast.Name):
            self._bind(target.id, kind, aliases=aliases)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for item in target.elts:
                self._bind_target(item, kind, aliases=aliases)
            return
        if isinstance(target, (ast.Attribute, ast.Subscript)) and kind in {
            "any",
            "typing-module",
            "any-or-typing-module",
            "uncertain",
            "unknown",
        }:
            root_name = self._mutation_root_name(target)
            if root_name:
                self._taint_alias_group(root_name, kind="uncertain" if kind != "unknown" else "unknown")

    def _taint_alias_group(self, root_name: str, *, kind: str = "uncertain") -> None:
        identities = self._resolve_aliases(root_name)
        if not identities:
            self._bind(root_name, kind)
            return
        matched = False
        for index, scope_aliases in enumerate(self._aliases):
            for name, candidate in scope_aliases.items():
                if identities & candidate:
                    self._scopes[index][name] = kind
                    matched = True
        if not matched:
            self._bind(root_name, kind)

    def _new_alias_identity(self) -> frozenset[int]:
        self._next_alias_identity += 1
        return frozenset({self._next_alias_identity})

    def _expression_aliases(self, value: ast.expr) -> frozenset[int]:
        if isinstance(value, ast.Name):
            return self._resolve_aliases(value.id) or self._new_alias_identity()
        if isinstance(value, ast.NamedExpr):
            return self._expression_aliases(value.value)
        if isinstance(value, ast.IfExp):
            return self._expression_aliases(value.body) | self._expression_aliases(value.orelse)
        if isinstance(value, ast.BoolOp):
            return frozenset().union(*(self._expression_aliases(item) for item in value.values))
        return self._new_alias_identity()

    def _target_aliases(self, target: ast.expr) -> frozenset[int]:
        if isinstance(target, ast.Name):
            return self._resolve_aliases(target.id) or self._new_alias_identity()
        root_name = self._mutation_root_name(target) if isinstance(target, (ast.Attribute, ast.Subscript)) else ""
        return self._resolve_aliases(root_name) if root_name else self._new_alias_identity()

    def _expression_alias_names(self, value: ast.expr) -> set[str]:
        return {
            node.id
            for node in ast.walk(value)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and self._resolve_aliases(node.id)
        }

    @staticmethod
    def _mutation_root_name(target: ast.Attribute | ast.Subscript) -> str:
        value: ast.expr = target.value
        while isinstance(value, (ast.Attribute, ast.Subscript)):
            value = value.value
        return value.id if isinstance(value, ast.Name) else ""

    def _expression_binding_kind(self, value: ast.expr) -> str:
        if isinstance(value, ast.Name):
            binding = self._resolve_name(value.id)
            if binding in {"any", "typing-module", "any-or-typing-module", "uncertain", "unknown"}:
                return binding
        if self._expression_depends_on_uncertain(value):
            return "uncertain"
        if self._expression_depends_on_kind(value, "unknown"):
            return "unknown"
        return "any" if self._annotation_any_count(value, fail_on_uncertain=False) > 0 else "other"

    def _expression_depends_on_uncertain(self, value: ast.expr) -> bool:
        return self._expression_depends_on_kind(value, "uncertain")

    def _expression_depends_on_kind(self, value: ast.expr, kind: str) -> bool:
        return any(
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and self._resolve_name(node.id) == kind
            for node in ast.walk(value)
        )

    def _indirect_target_kind(self, source: ast.expr) -> str:
        source_kind = self._expression_binding_kind(source)
        return (
            "uncertain"
            if source_kind in {"any", "typing-module", "any-or-typing-module", "uncertain"}
            else "unknown"
        )

    def _annotation_any_count(self, annotation: ast.expr, *, fail_on_uncertain: bool = True) -> int:
        count = 0
        qualified_names = {
            id(node.value)
            for node in ast.walk(annotation)
            if isinstance(node, ast.Attribute)
            and node.attr == "Any"
            and isinstance(node.value, ast.Name)
            and _binding_matches(self._resolve_name(node.value.id), "typing-module")
        }
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name) and id(node) not in qualified_names:
                binding = self._resolve_name(node.id)
                if binding in {"uncertain", "unknown"} and fail_on_uncertain:
                    self._add_blocker(f"{binding}_annotation_binding:{node.id}")
                    count += 1
                elif _binding_matches(binding, "any"):
                    count += 1
            elif isinstance(node, ast.Attribute) and node.attr == "Any" and isinstance(node.value, ast.Name):
                if _binding_matches(self._resolve_name(node.value.id), "typing-module"):
                    count += 1
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                count += self._quoted_annotation_any_count(node.value, fail_on_uncertain=fail_on_uncertain)
        return count

    def _quoted_annotation_any_count(self, value: str, *, fail_on_uncertain: bool) -> int:
        try:
            expression = ast.parse(value, mode="eval")
        except SyntaxError:
            return 0
        return self._annotation_any_count(expression.body, fail_on_uncertain=fail_on_uncertain)

    def _names_for(self, kind: str) -> set[str]:
        candidates = {name for scope in self._scopes for name in scope}
        candidates.update(name for scope in self._potential_scopes for name in scope)
        return {name for name in candidates if _binding_matches(self._resolve_name(name), kind)}

    def _is_type_alias_annotation(self, annotation: ast.expr) -> bool:
        if isinstance(annotation, ast.Name):
            return self._resolve_name(annotation.id) == "type-alias-marker"
        if isinstance(annotation, ast.Attribute) and annotation.attr == "TypeAlias" and isinstance(annotation.value, ast.Name):
            return self._resolve_name(annotation.value.id) == "typing-module"
        return False

    def _resolve_name(self, name: str) -> str:
        target_index = self._binding_scope_index(name)
        if target_index is None:
            return ""
        if target_index != len(self._scopes) - 1:
            if name in self._scopes[target_index]:
                return self._scopes[target_index][name]
            if target_index < len(self._potential_scopes):
                return self._potential_scopes[target_index].get(name, "")
            return ""
        for index in range(len(self._scopes) - 1, -1, -1):
            scope = self._scopes[index]
            if name in scope:
                return scope[name]
            if index < len(self._potential_scopes) and name in self._potential_scopes[index]:
                return self._potential_scopes[index][name]
        return ""

    def _resolve_aliases(self, name: str) -> frozenset[int]:
        target_index = self._binding_scope_index(name)
        if target_index is None:
            return frozenset()
        if target_index != len(self._aliases) - 1:
            return self._aliases[target_index].get(name, frozenset())
        for index in range(len(self._aliases) - 1, -1, -1):
            aliases = self._aliases[index]
            if name in aliases:
                return aliases[name]
        return frozenset()


def _match_pattern_names(pattern: ast.pattern) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(pattern):
        if isinstance(node, ast.MatchAs) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchStar) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


def _lexical_scope_statements(body: list[ast.stmt]) -> Iterable[ast.stmt]:
    for statement in body:
        yield statement
        nested: list[list[ast.stmt]] = []
        if isinstance(statement, ast.If):
            nested.extend((statement.body, statement.orelse))
        elif isinstance(statement, (ast.Try, ast.TryStar)):
            nested.extend((statement.body, statement.orelse, statement.finalbody))
            nested.extend(handler.body for handler in statement.handlers)
        elif isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)):
            nested.append(statement.body)
            if hasattr(statement, "orelse"):
                nested.append(statement.orelse)
        elif isinstance(statement, ast.Match):
            nested.extend(case.body for case in statement.cases)
        for branch in nested:
            yield from _lexical_scope_statements(branch)


def _scope_declarations(body: list[ast.stmt]) -> tuple[set[str], set[str]]:
    global_names: set[str] = set()
    nonlocal_names: set[str] = set()
    for statement in _lexical_scope_statements(body):
        if isinstance(statement, ast.Global):
            global_names.update(statement.names)
        elif isinstance(statement, ast.Nonlocal):
            nonlocal_names.update(statement.names)
    return global_names, nonlocal_names


def _assignment_target_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_assignment_target_names(item) for item in target.elts)) if target.elts else set()
    return set()


def _potential_expression_binding_kind(
    value: ast.expr,
    any_names: set[str],
    module_names: set[str],
) -> str:
    if isinstance(value, ast.Name):
        is_any = value.id in any_names
        is_module = value.id in module_names
        if is_any and is_module:
            return "any-or-typing-module"
        if is_any:
            return "any"
        if is_module:
            return "typing-module"
    if _annotation_any_count(value, any_names, module_names) > 0:
        return "any"
    return ""


def _merge_potential_binding(bindings: dict[str, str], name: str, kind: str) -> bool:
    current = bindings.get(name)
    merged = kind if current is None else _merge_binding_kinds([current, kind])
    if current == merged:
        return False
    bindings[name] = merged
    return True


def _merge_binding_kinds(kinds: Iterable[str]) -> str:
    values = set(kinds)
    if "uncertain" in values:
        return "uncertain"
    if "unknown" in values:
        return "unknown"
    if "any-or-typing-module" in values or {"any", "typing-module"}.issubset(values):
        return "any-or-typing-module"
    priority = {
        "other": 0,
        "type-checking-marker": 1,
        "type-alias-marker": 2,
        "typing-module": 3,
        "any": 4,
    }
    return max(values, key=lambda value: priority[value])


def _binding_matches(binding: str, expected: str) -> bool:
    return binding == expected or (
        binding == "any-or-typing-module" and expected in {"any", "typing-module"}
    )


def _explicit_any_annotation_count(tree: ast.Module) -> int:
    return _explicit_any_annotation_analysis(tree)[0]


def _explicit_any_annotation_analysis(tree: ast.Module) -> tuple[int, list[str]]:
    collector = _ExplicitAnyCollector()
    collector.visit(tree)
    return collector.count, list(collector.blockers)


def _annotation_any_count(annotation: ast.expr, any_names: set[str], module_names: set[str]) -> int:
    count = 0
    qualified_names = {
        id(node.value)
        for node in ast.walk(annotation)
        if isinstance(node, ast.Attribute)
        and node.attr == "Any"
        and isinstance(node.value, ast.Name)
        and node.value.id in module_names
    }
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and id(node) not in qualified_names and node.id in any_names:
            count += 1
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "Any"
            and isinstance(node.value, ast.Name)
            and node.value.id in module_names
        ):
            count += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            count += _quoted_annotation_any_count(node.value, any_names, module_names)
    return count


def _quoted_annotation_any_count(value: str, any_names: set[str], module_names: set[str]) -> int:
    try:
        expression = ast.parse(value, mode="eval")
    except SyntaxError:
        return 0
    return _annotation_any_count(expression.body, any_names, module_names)


def _explicit_any_alias_probe() -> bool:
    tree = ast.parse(
        """
from typing import Any, Any as _InterfaceType
from typing_extensions import Any as _InferenceType
from typing import TYPE_CHECKING, TypeAlias
import typing as t
import typing_extensions as tx

direct: Any
alias: _InterfaceType
module_alias: t.Any
extension_alias: _InferenceType
extension_module_alias: tx.Any
nested: dict[str, list[_InterfaceType | t.Any]]
quoted: "_InterfaceType"
quoted_nested: "dict[str, tx.Any]"
if TYPE_CHECKING:
    from typing import Any as _CheckedAny
checked: _CheckedAny
TypeAliasAny: TypeAlias = _InterfaceType
type_alias_value: TypeAliasAny
AliasChain = TypeAliasAny
alias_chain_value: AliasChain
class Handler:
    from typing import Any as ScopedAny
    value: ScopedAny

    def route(self, value: "_InferenceType") -> list["t.Any"]:
        local: _InterfaceType

        def nested(item: tx.Any) -> _CheckedAny:
            nested_local: ScopedAny
            return item

        return []
"""
    )
    return _explicit_any_annotation_count(tree) == 19


def _explicit_any_scope_probe() -> bool:
    positive = ast.parse(
        """
if True:
    from typing import Any as ConditionalAlias
conditional_values: tuple[ConditionalAlias, ConditionalAlias]

future_value: FutureAlias
if enabled:
    from typing import Any as FutureAlias

try:
    from typing_extensions import Any as TryAlias
except ImportError:
    TryAlias = object
try_value: TryAlias

with context():
    import typing as scoped_typing
with_value: scoped_typing.Any

for _item in items:
    from typing import Any as LoopAlias
loop_value: LoopAlias

match subject:
    case "typed":
        from typing import Any as MatchAlias
match_value: MatchAlias

if enabled:
    from typing import Any as MixedAlias
else:
    import typing as MixedAlias
mixed_direct: MixedAlias
mixed_qualified: MixedAlias.Any
AssignedMixedAlias = MixedAlias
assigned_mixed_direct: AssignedMixedAlias
assigned_mixed_qualified: AssignedMixedAlias.Any

AssignedModuleAlias = scoped_typing
assigned_module_qualified: AssignedModuleAlias.Any

def route() -> None:
    if enabled:
        from typing import Any as FunctionAlias
    local: FunctionAlias
"""
    )
    shadowed = ast.parse(
        """
from typing import Any as ClassAny
class ClassAny:
    pass
class_value: ClassAny

from typing import Any as FunctionAny
def FunctionAny() -> None:
    pass
function_value: FunctionAny

from typing import Any as AssignmentAny
AssignmentAny = int
assignment_value: AssignmentAny

class Any:
    pass
plain_shadow: Any
"""
    )
    growth = ast.parse(
        "if enabled:\n    from typing import Any as Alias\n"
        + "\n".join(f"value_{index}: Alias" for index in range(100))
        + "\n"
    )
    return (
        _explicit_any_annotation_count(positive) == 13
        and _explicit_any_annotation_count(shadowed) == 0
        and _explicit_any_annotation_count(growth) == 100
    )


def _explicit_any_lambda_scope_probe() -> bool:
    tree = ast.parse(
        "from typing import Any as Alias\n"
        "parameter_shadow = lambda Alias: Alias\n"
        "walrus_shadow = lambda: (Alias := int)\n"
        "nested_shadow = lambda: (lambda: (Alias := int))\n"
        + "\n".join(f"field_{index}: Alias" for index in range(100))
        + "\n"
    )
    return _explicit_any_annotation_count(tree) == 100


def _explicit_any_definition_time_probe() -> bool:
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    prefix = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
    )
    lambda_tree = ast.parse(prefix + '    registry = {"fn": lambda value=(Alias := t.Any): value}\n' + annotations)
    function_tree = ast.parse(prefix + "    def factory(value=(Alias := t.Any)):\n        return value\n" + annotations)
    definition_tree = ast.parse(
        "import typing as t\n"
        "decorators = {t.Any: lambda value: value}\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "def decorated():\n    pass\n"
        "decorated_value: Alias\n"
        "Alias = int\n"
        "async def async_default(*, value=(Alias := t.Any)):\n    pass\n"
        "async_value: Alias\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "class Decorated:\n    pass\n"
        "decorated_class_value: Alias\n"
        "Alias = int\n"
        "class Based((Alias := t.Any, object)[1]):\n    pass\n"
        "base_value: Alias\n"
        "Alias = int\n"
        "class Meta(object, metaclass=(Alias := t.Any, type)[1]):\n    pass\n"
        "metaclass_value: Alias\n"
    )
    ordered_tree = ast.parse(
        "import typing as t\n"
        "decorators = {t.Any: lambda value: value}\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "def ordered(value=(Alias := int)):\n    pass\n"
        "function_value: Alias\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "class Ordered((Alias := int, object)[1]):\n    pass\n"
        "class_value: Alias\n"
    )
    return (
        _explicit_any_annotation_count(lambda_tree) == 100
        and _explicit_any_annotation_count(function_tree) == 100
        and _explicit_any_annotation_count(definition_tree) == 5
        and _explicit_any_annotation_count(ordered_tree) == 0
    )


def _explicit_any_class_global_scope_probe() -> bool:
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    prefix = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
    )
    assignment = ast.parse(
        prefix
        + "    class Probe:\n"
        "        global Alias\n"
        "        Alias = t.Any\n"
        + annotations
        + "\n"
    )
    imported = ast.parse(
        prefix
        + "    class Probe:\n"
        "        global Alias\n"
        "        from typing import Any as Alias\n"
        + annotations
        + "\n"
    )
    assignment_count, assignment_blockers = _explicit_any_annotation_analysis(assignment)
    import_count, import_blockers = _explicit_any_annotation_analysis(imported)
    growth_metrics = {
        "collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "raw_dict_str_any_count": 0,
        "implementation_document_count": 0,
        "explicit_any_count": assignment_count,
        "explicit_any_affected_file_count": 1,
        "explicit_any_by_layer": {"interfaces": assignment_count},
        "explicit_any_by_file": {"song_agent/interfaces/api/class_global_probe.py": assignment_count},
        "explicit_any_scope_blockers": [],
        "public_implementation_document_count": 0,
        "untyped_public_function_count": 0,
    }
    growth_policy = {
        "typing": {
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/class_global_probe.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }
    growth_blockers = _typing_blockers(growth_metrics, growth_policy)
    return (
        assignment_count == 100
        and not assignment_blockers
        and import_count == 100
        and not import_blockers
        and any("typing_explicit_any:" in blocker for blocker in growth_blockers)
        and any("typing_explicit_any_layer" in blocker for blocker in growth_blockers)
        and any("typing_explicit_any_file" in blocker for blocker in growth_blockers)
    )


def _explicit_any_indirect_target_scope_probe() -> bool:
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    variants = (
        "        for Alias in (t.Any,):\n            pass\n",
        "        with contextlib.nullcontext(t.Any) as Alias:\n            pass\n",
        "        match t.Any:\n            case Alias:\n                pass\n",
    )
    for body in variants:
        source = (
            "from __future__ import annotations\n"
            "import contextlib\n"
            "import typing as t\n"
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    Alias = int\n"
            "else:\n"
            "    class Probe:\n"
            "        global Alias\n"
            + body
            + annotations
            + "\n"
        )
        count, scope_blockers = _explicit_any_annotation_analysis(ast.parse(source))
        metrics = {
            "collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "raw_dict_str_any_count": 0,
            "implementation_document_count": 0,
            "explicit_any_count": count,
            "explicit_any_affected_file_count": 1,
            "explicit_any_by_layer": {"interfaces": count},
            "explicit_any_by_file": {"song_agent/interfaces/api/indirect_target_probe.py": count},
            "explicit_any_scope_blockers": [
                {"path": "song_agent/interfaces/api/indirect_target_probe.py", "detail": detail}
                for detail in scope_blockers
            ],
            "public_implementation_document_count": 0,
            "untyped_public_function_count": 0,
        }
        policy = {
            "typing": {
                "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
                "raw_dict_str_any_max_count": 0,
                "implementation_document_max_count": 0,
                "explicit_any_max_count": 99,
                "explicit_any_affected_file_max_count": 1,
                "explicit_any_layer_budgets": {"interfaces": 99},
                "explicit_any_file_budgets": {"song_agent/interfaces/api/indirect_target_probe.py": 99},
                "public_implementation_document_max_count": 0,
                "untyped_public_function_max_count": 0,
            }
        }
        blockers = _typing_blockers(metrics, policy)
        if not (
            count == 100
            and "uncertain_annotation_binding:Alias" in scope_blockers
            and any("typing_explicit_any_scope_flow" in blocker for blocker in blockers)
            and any("typing_explicit_any:" in blocker for blocker in blockers)
            and any("typing_explicit_any_layer" in blocker for blocker in blockers)
            and any("typing_explicit_any_file" in blocker for blocker in blockers)
        ):
            return False
    return True


def _explicit_any_derived_uncertain_scope_probe() -> bool:
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    variants = (
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = Alias[0]\n",
        "        with contextlib.nullcontext((t.Any,)) as Alias:\n            Alias = Alias[0]\n",
        "        match (t.Any,):\n            case (Alias,):\n                Alias = (Alias,)[0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = (Alias,)[0][0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = (lambda value: value)(Alias[0])\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = Alias[0] if True else int\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = Alias[0] or int\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Derived = Alias\n        Alias = Derived[0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = (Alias[0], (Alias := int))[0]\n",
        "        for Alias in ([t.Any],):\n            pass\n        Alias += []\n        Alias = Alias[0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        class Holder:\n            pass\n        Holder.value = Alias\n        Alias = Holder.value[0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Holder = [None]\n        Holder[0] = Alias\n        Alias = Holder[0][0]\n",
    )
    for body in variants:
        source = (
            "from __future__ import annotations\n"
            "import contextlib\n"
            "import typing as t\n"
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    Alias = int\n"
            "else:\n"
            "    class Probe:\n"
            "        global Alias\n"
            + body
            + annotations
            + "\n"
        )
        count, scope_blockers = _explicit_any_annotation_analysis(ast.parse(source))
        metrics = {
            "collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "raw_dict_str_any_count": 0,
            "implementation_document_count": 0,
            "explicit_any_count": count,
            "explicit_any_affected_file_count": 1,
            "explicit_any_by_layer": {"interfaces": count},
            "explicit_any_by_file": {"song_agent/interfaces/api/derived_uncertain_probe.py": count},
            "explicit_any_scope_blockers": [
                {"path": "song_agent/interfaces/api/derived_uncertain_probe.py", "detail": detail}
                for detail in scope_blockers
            ],
            "public_implementation_document_count": 0,
            "untyped_public_function_count": 0,
        }
        policy = {
            "typing": {
                "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
                "raw_dict_str_any_max_count": 0,
                "implementation_document_max_count": 0,
                "explicit_any_max_count": 99,
                "explicit_any_affected_file_max_count": 1,
                "explicit_any_layer_budgets": {"interfaces": 99},
                "explicit_any_file_budgets": {"song_agent/interfaces/api/derived_uncertain_probe.py": 99},
                "public_implementation_document_max_count": 0,
                "untyped_public_function_max_count": 0,
            }
        }
        blockers = _typing_blockers(metrics, policy)
        if not (
            count == 100
            and bool(
                {"uncertain_annotation_binding:Alias", "unknown_annotation_binding:Alias"}.intersection(scope_blockers)
            )
            and any("typing_explicit_any_scope_flow" in blocker for blocker in blockers)
            and any("typing_explicit_any:" in blocker for blocker in blockers)
            and any("typing_explicit_any_layer" in blocker for blocker in blockers)
            and any("typing_explicit_any_file" in blocker for blocker in blockers)
        ):
            return False
    return True


def _explicit_any_object_alias_scope_probe() -> bool:
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    variants = (
        "        Holder = [None]\n        Ref = Holder\n        Ref[0] = Alias\n        Alias = Holder[0][0]\n",
        "        class Holder:\n            value = [None]\n        Ref = Holder\n        Ref.value = Alias\n        Alias = Holder.value[0]\n",
        "        Holder = [None]\n        Ref = Holder\n        Ref2 = Ref\n        Ref2[0] = Alias\n        Alias = Holder[0][0]\n",
        "        Holder = [None]\n        if enabled:\n            Ref = Holder\n        else:\n            Ref = [None]\n        Ref[0] = Alias\n        Alias = Holder[0][0]\n",
        "        Holder = [None]\n        def store(target, value):\n            target[0] = value\n        store(Holder, Alias)\n        Alias = Holder[0][0]\n",
        "        Holder = [None]\n        def store(target, value):\n            target[0] = value\n        store(Holder, t.Any)\n        Alias = Holder[0]\n",
        "        Holder = []\n        Ref = Holder\n        Ref += [Alias]\n        Alias = Holder[0][0]\n",
        "        Holder = []\n        Ref = Holder\n        Ref += [t.Any]\n        Alias = Holder[0]\n",
    )
    for body in variants:
        source = (
            "from __future__ import annotations\n"
            "import typing as t\n"
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    Alias = int\n"
            "else:\n"
            "    class Probe:\n"
            "        global Alias\n"
            "        for Alias in ((t.Any,),):\n"
            "            pass\n"
            + body
            + annotations
            + "\n"
        )
        count, scope_blockers = _explicit_any_annotation_analysis(ast.parse(source))
        metrics = {
            "collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "raw_dict_str_any_count": 0,
            "implementation_document_count": 0,
            "explicit_any_count": count,
            "explicit_any_affected_file_count": 1,
            "explicit_any_by_layer": {"interfaces": count},
            "explicit_any_by_file": {"song_agent/interfaces/api/object_alias_probe.py": count},
            "explicit_any_scope_blockers": [
                {"path": "song_agent/interfaces/api/object_alias_probe.py", "detail": detail}
                for detail in scope_blockers
            ],
            "public_implementation_document_count": 0,
            "untyped_public_function_count": 0,
        }
        policy = {
            "typing": {
                "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
                "raw_dict_str_any_max_count": 0,
                "implementation_document_max_count": 0,
                "explicit_any_max_count": 99,
                "explicit_any_affected_file_max_count": 1,
                "explicit_any_layer_budgets": {"interfaces": 99},
                "explicit_any_file_budgets": {"song_agent/interfaces/api/object_alias_probe.py": 99},
                "public_implementation_document_max_count": 0,
                "untyped_public_function_max_count": 0,
            }
        }
        blockers = _typing_blockers(metrics, policy)
        if not (
            count == 100
            and "uncertain_annotation_binding:Alias" in scope_blockers
            and any("typing_explicit_any_scope_flow" in blocker for blocker in blockers)
            and any("typing_explicit_any:" in blocker for blocker in blockers)
            and any("typing_explicit_any_layer" in blocker for blocker in blockers)
            and any("typing_explicit_any_file" in blocker for blocker in blockers)
        ):
            return False
    rebind = ast.parse(
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        "        for Alias in ((t.Any,),):\n"
        "            pass\n"
        "        Holder = [int]\n"
        "        Ref = Holder\n"
        "        Ref = [None]\n"
        "        Ref[0] = Alias\n"
        "        Alias = Holder[0]\n"
        "field: Alias\n"
    )
    rebind_count, rebind_blockers = _explicit_any_annotation_analysis(rebind)
    return rebind_count == 0 and not rebind_blockers


def _typing_layer(relative: str) -> str:
    parts = relative.split("/")
    return parts[1] if len(parts) > 1 and parts[0] == "song_agent" else "unknown"


def _function_layer_limit(relative: str) -> tuple[str, int]:
    if relative.startswith("song_agent/interfaces/cli/"):
        return "interface_cli", FUNCTION_LIMITS["interface_cli"]
    if relative.startswith("song_agent/interfaces/"):
        return "interface_api", FUNCTION_LIMITS["interface_api"]
    if relative.startswith("song_agent/application/"):
        return "application", FUNCTION_LIMITS["application"]
    return "domain", FUNCTION_LIMITS["domain"]


def _active_python_files(root: Path) -> list[Path]:
    return sorted(path for relative in MYPY_ROOTS for path in (root / relative).rglob("*.py") if path.is_file())


def _coverage_totals(report: dict[str, Any], roots: tuple[str, ...], *, exact: bool = False) -> dict[str, Any]:
    statements = covered = 0
    normalized = tuple(value.replace("\\", "/") for value in roots)
    for raw_path, row in (report.get("files") or {}).items():
        path = str(raw_path).replace("\\", "/").removesuffix(".py")
        selected = path in normalized if exact else any(path.startswith(root) for root in normalized)
        if not selected or not isinstance(row, dict):
            continue
        summary = row.get("summary") or {}
        statements += int(summary.get("num_statements") or 0)
        covered += int(summary.get("covered_lines") or 0)
    percent = 100.0 if statements == 0 else round(100.0 * covered / statements, 2)
    return {"statements": statements, "covered": covered, "percent": percent}


def _rooted(root: Path, path: Path | str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value


def _file_hash(path: Path) -> str:
    value = sha256_text_file(path)
    if value is None:
        raise FileNotFoundError(path)
    return value
