from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

from song_agent.platform.verification.hashing import stable_hash


QUALITY_POLICY_PATH = "architecture-v14-quality.json"
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
    raw_count = 0
    implementation_count = 0
    public_dynamic: list[dict[str, Any]] = []
    untyped_public: list[dict[str, Any]] = []
    for path in _active_python_files(root):
        source = path.read_text(encoding="utf-8")
        raw_count += source.count("dict[str, Any]")
        implementation_count += source.count("ImplementationDocument")
        tree = ast.parse(source, filename=str(path))
        relative = path.relative_to(root).as_posix()
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
        "raw_dict_str_any_count": raw_count,
        "implementation_document_count": implementation_count,
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
        [sys.executable, "-m", "mypy", "--no-pretty", "--no-color-output"],
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
    return {
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "oversized_function_count": len(oversized_functions),
        "oversized_functions": oversized_functions,
        "registered_oversized_module_count": len(oversized_modules),
        "oversized_modules": oversized_modules,
    }


def collect_coverage_metrics(root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    coverage_policy = policy.get("coverage") or {}
    report_path = _rooted(root, str(coverage_policy.get("report_path") or "runs/v14-quality/coverage.json"))
    blockers: list[str] = []
    if not report_path.is_file():
        return {"status": "missing", "blockers": ["v14_quality_coverage_report_missing"], "layers": {}}
    report = json.loads(report_path.read_text(encoding="utf-8"))
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
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_v14_quality_policy(root: Path, *, coverage_report: Path | None = None) -> dict[str, Any]:
    typing = collect_typing_metrics(root)
    mypy = collect_mypy_metrics(root)
    module_debt: list[dict[str, Any]] = []
    maximum = 600
    for path in _active_python_files(root):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > maximum:
            module_debt.append(
                {"path": path.relative_to(root).as_posix(), "max_lines": lines, "expires_version": "14.1.0"}
            )
    report = coverage_report or root / "runs/v14-quality/coverage.json"
    coverage_bound = coverage_report is not None and report.is_file()
    document: dict[str, Any] = {
        "schema_version": 1,
        "package_type": "musicforge_v14_quality_policy",
        "release_version": "14.0.0",
        "typing": {
            "activation_baseline_dict_str_any_count": 12535,
            "raw_dict_str_any_max_count": 8774,
            "implementation_document_max_count": typing["implementation_document_count"],
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
        "mypy_errors": report["mypy"]["total_errors"],
        "strict_mypy": report["mypy"]["strict_status"],
        "coverage": report["coverage"]["layers"],
        "blockers": report["blockers"],
    }
    return report["status"] == "passed", json.dumps(detail, sort_keys=True)


def _typing_blockers(metrics: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    limits = policy.get("typing") or {}
    fields = (
        ("raw_dict_str_any_count", "raw_dict_str_any_max_count", "typing_raw_dict_str_any"),
        ("implementation_document_count", "implementation_document_max_count", "typing_implementation_document"),
        ("public_implementation_document_count", "public_implementation_document_max_count", "typing_public_dynamic"),
        ("untyped_public_function_count", "untyped_public_function_max_count", "typing_untyped_public"),
    )
    return [
        f"v14_quality_{label}:{metrics[current]}>{limits[maximum]}"
        for current, maximum, label in fields
        if int(metrics[current]) > int(limits[maximum])
    ]


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
    if policy.get("release_version") != "14.0.0":
        blockers.append("v14_quality_policy_version")
    if int((policy.get("typing") or {}).get("raw_dict_str_any_max_count") or 0) > 8774:
        blockers.append("v14_quality_policy_typing_loosened")
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
    return hashlib.sha256(path.read_bytes()).hexdigest()
