from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable

from song_agent.platform.verification.hashing import canonical_text_bytes, sha256_text_file, stable_hash


QUALITY_POLICY_PATH = "architecture-v14-quality.json"
QUALITY_POLICY_VERSION = "14.2.0"
EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION = 3
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


def evaluate_v14_quality(
    repo_root: Path | str = ".",
    *,
    policy_path: Path | str = QUALITY_POLICY_PATH,
    run_mypy: bool = True,
    require_coverage: bool = True,
) -> DomainDocument:
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


def collect_typing_metrics(root: Path) -> DomainDocument:
    raw_count = 0
    implementation_count = 0
    explicit_any_by_file: Counter[str] = Counter()
    explicit_any_by_layer: Counter[str] = Counter()
    public_dynamic: list[ImplementationDocument] = []
    untyped_public: list[ImplementationDocument] = []
    for path in _active_python_files(root):
        source = path.read_text(encoding="utf-8")
        raw_count += source.count("dict[str, Any]")
        implementation_count += source.count("ImplementationDocument")
        tree = ast.parse(source, filename=str(path))
        relative = path.relative_to(root).as_posix()
        explicit_any = _explicit_any_annotation_count(tree)
        if explicit_any:
            explicit_any_by_file[relative] = explicit_any
            explicit_any_by_layer[_typing_layer(relative)] += explicit_any
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
    for root_name in MYPY_ROOTS:
        explicit_any_by_layer.setdefault(_typing_layer(root_name), 0)
    return {
        "collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "raw_dict_str_any_count": raw_count,
        "implementation_document_count": implementation_count,
        "explicit_any_count": sum(explicit_any_by_file.values()),
        "explicit_any_by_layer": dict(sorted(explicit_any_by_layer.items())),
        "explicit_any_by_file": dict(sorted(explicit_any_by_file.items())),
        "public_implementation_document_count": len(public_dynamic),
        "public_implementation_documents": public_dynamic,
        "untyped_public_function_count": len(untyped_public),
        "untyped_public_functions": untyped_public,
    }


def collect_mypy_metrics(root: Path) -> DomainDocument:
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


def collect_complexity_metrics(root: Path, policy: DomainDocument) -> DomainDocument:
    oversized_functions: list[ImplementationDocument] = []
    oversized_modules: list[ImplementationDocument] = []
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


def collect_coverage_metrics(root: Path, policy: DomainDocument) -> DomainDocument:
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


def coverage_semantic_hash(files: DomainDocument) -> str:
    return stable_hash({"files": files})


def build_v14_quality_policy(root: Path, *, coverage_report: Path | None = None) -> DomainDocument:
    typing = collect_typing_metrics(root)
    mypy = collect_mypy_metrics(root)
    module_debt: list[ImplementationDocument] = []
    maximum = 600
    for path in _active_python_files(root):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > maximum:
            module_debt.append(
                {"path": path.relative_to(root).as_posix(), "max_lines": lines, "expires_version": "14.3.0"}
            )
    total_oversized_lines = sum(int(row["max_lines"]) for row in module_debt)
    largest_module_lines = max((int(row["max_lines"]) for row in module_debt), default=0)
    report = coverage_report or root / "runs/v14-quality/coverage.json"
    coverage_bound = coverage_report is not None and report.is_file()
    document: ImplementationDocument = {
        "schema_version": 1,
        "package_type": "musicforge_v14_quality_policy",
        "release_version": QUALITY_POLICY_VERSION,
        "typing": {
            "activation_baseline_dict_str_any_count": 12535,
            "raw_dict_str_any_max_count": 8774,
            "implementation_document_max_count": typing["implementation_document_count"],
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": typing["explicit_any_count"],
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
                "architecture_decision": "docs/architecture/ADR-015-v141-complexity-ratchet.md",
                "expires_version": "14.3.0",
                "previous_oversized_module_count": 137,
                "previous_total_oversized_module_lines": 124039,
                "required_total_line_reduction": max(0, 124039 - total_oversized_lines),
                "max_oversized_module_count": len(module_debt),
                "max_modules_over_1000_lines": sum(1 for row in module_debt if int(row["max_lines"]) > 1000),
                "max_largest_module_lines": largest_module_lines,
                "max_total_oversized_module_lines": total_oversized_lines,
            },
        },
        "module_size_debt": module_debt,
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
        and details["explicit_any_collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
        and details["complexity_decision_present"]
        and details["ci_budget_ratchet"]
    )
    return passed, json.dumps(details, sort_keys=True)


def _typing_blockers(metrics: ImplementationDocument, policy: ImplementationDocument) -> list[str]:
    limits = policy.get("typing") or {}
    blockers: list[str] = []
    if int(limits.get("explicit_any_collector_schema_version") or 0) != EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION:
        blockers.append("v14_quality_typing_explicit_any_collector_schema")
    if int(metrics.get("collector_schema_version") or 0) != EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION:
        blockers.append("v14_quality_typing_metrics_collector_schema")
    fields = (
        ("raw_dict_str_any_count", "raw_dict_str_any_max_count", "typing_raw_dict_str_any"),
        ("implementation_document_count", "implementation_document_max_count", "typing_implementation_document"),
        ("explicit_any_count", "explicit_any_max_count", "typing_explicit_any"),
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


def _mypy_blockers(metrics: ImplementationDocument, policy: ImplementationDocument) -> list[str]:
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


def _policy_blockers(policy: ImplementationDocument) -> list[str]:
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
    return blockers


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
    def __init__(self) -> None:
        self.count = 0
        self._scopes: list[dict[str, str]] = [{}]

    def visit_Module(self, node: ast.Module) -> None:
        self._scan_aliases_until_stable(node.body)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scopes.append({})
        self._scan_aliases_until_stable(node.body)
        self.generic_visit(node)
        self._scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._count_function_annotations(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._count_function_annotations(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._is_type_alias_annotation(node.annotation):
            return
        self.count += self._annotation_any_count(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_arg(self, node: ast.arg) -> None:
        if node.annotation is not None:
            self.count += self._annotation_any_count(node.annotation)

    def _count_function_annotations(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for annotation in _function_annotations(node, skip_receiver=False):
            if annotation is not None:
                self.count += self._annotation_any_count(annotation)
        if node.returns is not None:
            self.count += self._annotation_any_count(node.returns)

    def _scan_aliases_until_stable(self, body: list[ast.stmt]) -> None:
        changed = True
        while changed:
            changed = False
            for statement in body:
                changed = self._record_alias(statement) or changed

    def _record_alias(self, statement: ast.stmt) -> bool:
        before = dict(self._scopes[-1])
        self._record_alias_once(statement)
        return before != self._scopes[-1]

    def _record_alias_once(self, statement: ast.stmt) -> None:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                if alias.name in {"typing", "typing_extensions"}:
                    self._scopes[-1][alias.asname or alias.name] = "typing-module"
            return
        if isinstance(statement, ast.ImportFrom) and statement.module in {"typing", "typing_extensions"}:
            for alias in statement.names:
                name = alias.asname or alias.name
                if alias.name == "Any":
                    self._scopes[-1][name] = "any"
                elif alias.name == "TypeAlias":
                    self._scopes[-1][name] = "type-alias-marker"
            return
        if isinstance(statement, ast.If) and self._is_type_checking_guard(statement.test):
            self._scan_aliases_until_stable(statement.body)
            return
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
            if self._annotation_any_count(statement.value) > 0:
                self._scopes[-1][statement.targets[0].id] = "any"
            return
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if self._is_type_alias_annotation(statement.annotation) and statement.value is not None:
                if self._annotation_any_count(statement.value) > 0:
                    self._scopes[-1][statement.target.id] = "any"
            return
        if hasattr(ast, "TypeAlias") and isinstance(statement, ast.TypeAlias):
            name = getattr(statement, "name", None)
            value = getattr(statement, "value", None)
            if isinstance(name, ast.Name) and isinstance(value, ast.expr) and self._annotation_any_count(value) > 0:
                self._scopes[-1][name.id] = "any"

    def _annotation_any_count(self, annotation: ast.expr) -> int:
        count = 0
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name) and self._resolve_name(node.id) == "any":
                count += 1
            elif isinstance(node, ast.Attribute) and node.attr == "Any" and isinstance(node.value, ast.Name):
                if self._resolve_name(node.value.id) == "typing-module":
                    count += 1
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                count += _quoted_annotation_any_count(
                    node.value,
                    {
                        name
                        for scope in self._scopes
                        for name, kind in scope.items()
                        if kind == "any"
                    }
                    | {"Any"},
                    {
                        name
                        for scope in self._scopes
                        for name, kind in scope.items()
                        if kind == "typing-module"
                    }
                    | {"typing", "typing_extensions"},
                )
        return count

    def _is_type_alias_annotation(self, annotation: ast.expr) -> bool:
        return isinstance(annotation, ast.Name) and self._resolve_name(annotation.id) == "type-alias-marker"

    def _is_type_checking_guard(self, test: ast.expr) -> bool:
        if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
            return True
        return (
            isinstance(test, ast.Attribute)
            and test.attr == "TYPE_CHECKING"
            and isinstance(test.value, ast.Name)
            and self._resolve_name(test.value.id) == "typing-module"
        )

    def _resolve_name(self, name: str) -> str:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        if name == "Any":
            return "any"
        if name in {"typing", "typing_extensions"}:
            return "typing-module"
        if name == "TypeAlias":
            return "type-alias-marker"
        return ""


def _explicit_any_annotation_count(tree: ast.Module) -> int:
    collector = _ExplicitAnyCollector()
    collector.visit(tree)
    return collector.count


def _quoted_annotation_any_count(value: str, any_names: set[str], module_names: set[str]) -> int:
    try:
        expression = ast.parse(value, mode="eval")
    except SyntaxError:
        return 0
    return _legacy_annotation_any_count(expression.body, any_names, module_names)


def _legacy_annotation_any_count(annotation: ast.expr, any_names: set[str], module_names: set[str]) -> int:
    count = 0
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and node.id in any_names:
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
class Scoped:
    from typing import Any as ScopedAny
    value: ScopedAny
"""
    )
    return _explicit_any_annotation_count(tree) == 13


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


def _coverage_totals(report: ImplementationDocument, roots: tuple[str, ...], *, exact: bool = False) -> ImplementationDocument:
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
