from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import ast
from collections import Counter
from contextlib import contextmanager
import hashlib
import io
import json
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Iterable

from song_agent.architecture_guardrails import build_architecture_snapshot


BASELINE_TAG = "v13.8.0"
BASELINE_VERSION = "13.8.0"
V14_CONTEXTS = ("creation", "studio", "quality", "delivery", "trust", "program")
INTERFACE_LIMITS = {"api": 100, "cli": 120, "web": 100}
_EVIDENCE_LITERAL = re.compile(r"^musicforge_[a-z0-9_]+$")
_PART_FILE = re.compile(r"part_\d+\.py$")


def build_v14_baseline(
    repo_root: Path | str = ".",
    *,
    coverage_report: Path | str | None = None,
    performance_report: Path | str | None = None,
) -> dict[str, DomainDocument]:
    root = Path(repo_root).resolve()
    final_sha = _git(root, "rev-parse", f"{BASELINE_TAG}^{{}}")
    head_sha = _git(root, "rev-parse", "HEAD")
    with _baseline_source(root) as source_root:
        snapshot = build_architecture_snapshot(source_root)
        modules = {str(row["module"]): row for row in snapshot["modules"]}
        imports = _imports_by_target(snapshot)
        retirement = _compatibility_retirement(source_root, snapshot, modules, imports, final_sha)
        architecture = {
            "schema_version": 1,
            "package_type": "musicforge_v14_architecture_baseline",
            "baseline_tag": BASELINE_TAG,
            "baseline_version": BASELINE_VERSION,
            "baseline_sha": final_sha,
            "generation_head_sha": head_sha,
            "source_tree_sha": final_sha,
            "source_matches_baseline": True,
            "module_count": snapshot["module_count"],
            "total_source_lines": snapshot["total_source_lines"],
            "production_cycle_count": len(snapshot["cycles"]),
            "all_cycle_count": len(snapshot["all_import_cycles"]),
            "boundary_violation_count": len(snapshot["boundary_violations"]),
            "dependency_exception_count": len(snapshot["dependency_exceptions"]),
            "active_to_compatibility_import_count": len(snapshot["active_to_compatibility_imports"]),
            "active_to_compatibility_imports": snapshot["active_to_compatibility_imports"],
            "compatibility_module_count": len(retirement["entries"]),
            "compatibility_source_lines": sum(int(row["source_lines"]) for row in retirement["entries"]),
            "compatibility_nonblank_source_lines": sum(
                int(row["nonblank_source_lines"]) for row in retirement["entries"]
            ),
            "active_source_lines": snapshot["total_source_lines"]
            - sum(int(row["source_lines"]) for row in retirement["entries"]),
            "code_metrics": snapshot["code_metrics"],
            "integrity_hash": "",
        }
        architecture["integrity_hash"] = _stable_hash(architecture)
        return {
            "architecture.json": architecture,
            "compatibility-retirement.json": retirement,
            "interface-debt.json": _interface_debt(source_root, snapshot, modules, final_sha),
            "coverage.json": _coverage_baseline(root, coverage_report, final_sha),
            "type-debt.json": _type_debt(source_root, modules, final_sha),
            "performance.json": _performance_baseline(root, performance_report, final_sha),
        }


def write_v14_baseline(
    repo_root: Path | str = ".",
    *,
    output_dir: Path | str = "runs/v14-baseline",
    tracked_manifest: Path | str | None = "architecture-v14-migration.json",
    coverage_report: Path | str | None = None,
    performance_report: Path | str | None = None,
) -> dict[str, DomainDocument]:
    root = Path(repo_root).resolve()
    output = _rooted(root, output_dir)
    output.mkdir(parents=True, exist_ok=True)
    documents = build_v14_baseline(
        root,
        coverage_report=coverage_report,
        performance_report=performance_report,
    )
    for name, document in documents.items():
        _write_json(output / name, document)
    if tracked_manifest is not None:
        tracked = _rooted(root, tracked_manifest)
        _write_json(
            tracked,
            {
                "schema_version": 1,
                "package_type": "musicforge_v14_migration_baseline",
                "baseline_tag": BASELINE_TAG,
                "baseline_sha": documents["architecture.json"]["baseline_sha"],
                "architecture": {
                    key: value
                    for key, value in documents["architecture.json"].items()
                    if key not in {"active_to_compatibility_imports", "code_metrics"}
                },
                "retirement": documents["compatibility-retirement.json"],
                "interface_debt": documents["interface-debt.json"],
                "type_debt": documents["type-debt.json"],
                "coverage": documents["coverage.json"],
                "performance": documents["performance.json"],
            },
        )
    return documents


def verify_v14_baseline(repo_root: Path | str = ".") -> DomainDocument:
    root = Path(repo_root).resolve()
    tracked_path = root / "architecture-v14-migration.json"
    blockers: list[str] = []
    if not tracked_path.is_file():
        return {"status": "failed", "blockers": ["v14_baseline_manifest_missing"]}
    tracked = json.loads(tracked_path.read_text(encoding="utf-8"))
    current = build_v14_baseline(root)
    retirement = tracked.get("retirement") if isinstance(tracked.get("retirement"), dict) else {}
    entries = retirement.get("entries") if isinstance(retirement.get("entries"), list) else []
    baseline_sha = _git(root, "rev-parse", f"{BASELINE_TAG}^{{}}")
    if tracked.get("baseline_sha") != baseline_sha:
        blockers.append("v14_baseline_sha")
    if len(entries) != int(current["architecture.json"]["compatibility_module_count"]):
        blockers.append("v14_baseline_compatibility_inventory_count")
    if int((retirement.get("summary") or {}).get("active_edge_count") or -1) != 224:
        blockers.append("v14_baseline_active_edge_count")
    required = {
        "module",
        "context",
        "owner",
        "active_callers",
        "public_contracts",
        "state_paths",
        "evidence_types",
        "target_module",
        "migration_status",
        "differential_tests",
        "removal_decision",
    }
    for row in entries:
        module = str(row.get("module") or "unknown")
        if not required.issubset(row):
            blockers.append(f"v14_baseline_entry_fields:{module}")
        if row.get("context") not in V14_CONTEXTS:
            blockers.append(f"v14_baseline_entry_context:{module}")
        if not row.get("owner") or not row.get("target_module"):
            blockers.append(f"v14_baseline_entry_ownership:{module}")
    return {
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "summary": {
            "compatibility_module_count": len(entries),
            "active_edge_count": int((retirement.get("summary") or {}).get("active_edge_count") or 0),
            "baseline_sha": baseline_sha,
        },
    }


def _compatibility_retirement(
    root: Path,
    snapshot: ImplementationDocument,
    modules: dict[str, ImplementationDocument],
    imports: dict[str, list[str]],
    final_sha: str,
) -> ImplementationDocument:
    debt = json.loads((root / "architecture-debt.json").read_text(encoding="utf-8"))
    debt_rows = {str(row["module"]): row for row in debt.get("compatibility_entries", [])}
    test_imports = _test_imports(root)
    entries: list[ImplementationDocument] = []
    for module, ownership in sorted(modules.items()):
        if ownership.get("layer") != "compatibility":
            continue
        path = root / str(ownership["path"])
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        context = str(ownership.get("context") or "creation")
        wrapper_target = _legacy_wrapper_target(root, module)
        target_module = wrapper_target if wrapper_target.startswith("song_agent.domains.") else _domain_target(module, context)
        active_callers = sorted(
            importer
            for importer in imports.get(module, [])
            if modules.get(importer, {}).get("layer") not in {"compatibility", "release_check"}
        )
        public_contracts = sorted(f"{module}.{name}" for name in _public_names(tree))
        wrapper_module = "song_agent.application.legacy_dependencies." + module.removeprefix("song_agent.").replace(".", "__")
        differential_tests = sorted(
            relative
            for relative, imported_modules in test_imports.items()
            if module in imported_modules or wrapper_module in imported_modules
        )
        already_migrated = wrapper_target.startswith("song_agent.domains.")
        if active_callers:
            decision = "move"
            status = "pending"
        elif already_migrated:
            decision = "facade"
            status = "migrated"
        elif differential_tests or public_contracts:
            decision = "facade"
            status = "pending"
        else:
            decision = "archive"
            status = "pending"
        debt_row = debt_rows.get(module) or {}
        entries.append(
            {
                "module": module,
                "path": str(ownership["path"]),
                "context": context,
                "owner": str(debt_row.get("owner") or f"musicforge-{context}"),
                "source_lines": len(source.splitlines()),
                "nonblank_source_lines": sum(1 for line in source.splitlines() if line.strip()),
                "active_callers": active_callers,
                "public_contracts": public_contracts,
                "state_paths": _state_paths(tree),
                "evidence_types": _evidence_types(tree),
                "target_module": target_module,
                "migration_status": status,
                "differential_tests": differential_tests,
                "removal_decision": decision,
            }
        )
    counts = Counter(str(row["context"]) for row in entries)
    active_edges = sum(len(row["active_callers"]) for row in entries)
    document: ImplementationDocument = {
        "schema_version": 1,
        "package_type": "musicforge_v14_compatibility_retirement",
        "baseline_tag": BASELINE_TAG,
        "baseline_sha": final_sha,
        "summary": {
            "module_count": len(entries),
            "source_lines": sum(int(row["source_lines"]) for row in entries),
            "nonblank_source_lines": sum(int(row["nonblank_source_lines"]) for row in entries),
            "active_edge_count": active_edges,
            "context_module_counts": dict(sorted(counts.items())),
            "migration_status_counts": dict(sorted(Counter(str(row["migration_status"]) for row in entries).items())),
            "decision_counts": dict(sorted(Counter(str(row["removal_decision"]) for row in entries).items())),
        },
        "entries": entries,
        "integrity_hash": "",
    }
    document["integrity_hash"] = _stable_hash(document)
    return document


def _interface_debt(
    root: Path,
    snapshot: ImplementationDocument,
    modules: dict[str, ImplementationDocument],
    final_sha: str,
) -> ImplementationDocument:
    part_files: list[str] = []
    wildcard_imports: list[ImplementationDocument] = []
    dynamic_forwarding: list[ImplementationDocument] = []
    store_references: list[ImplementationDocument] = []
    oversized_functions: list[ImplementationDocument] = []
    for module, row in sorted(modules.items()):
        layer = str(row.get("layer"))
        if layer in {"compatibility", "release_check"}:
            continue
        relative = str(row["path"])
        path = root / relative
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if layer == "interface" and _PART_FILE.search(path.name):
            part_files.append(relative)
        context = str(row.get("context") or "api")
        limit = INTERFACE_LIMITS.get(context, 100)
        for node in ast.walk(tree):
            if layer == "interface" and isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
                wildcard_imports.append({"module": module, "line": node.lineno, "target": node.module or ""})
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines = int(node.end_lineno or node.lineno) - int(node.lineno) + 1
                if node.name == "_resolve_symbol" or _uses_globals_update(node) or _uses_resolve_symbol(node):
                    dynamic_forwarding.append({"module": module, "line": node.lineno, "name": node.name})
                if layer == "interface" and lines > limit:
                    oversized_functions.append(
                        {"module": module, "path": relative, "name": node.name, "line": node.lineno, "lines": lines, "limit": limit}
                    )
            if layer == "interface" and isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name.endswith("Store"):
                        store_references.append(
                            {"module": module, "line": node.lineno, "name": alias.name, "target": node.module or ""}
                        )
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and _is_globals_update(node.value):
                dynamic_forwarding.append({"module": module, "line": node.lineno, "name": "globals.update"})
    document: ImplementationDocument = {
        "schema_version": 1,
        "package_type": "musicforge_v14_interface_debt",
        "baseline_sha": final_sha,
        "summary": {
            "anonymous_part_file_count": len(part_files),
            "wildcard_import_count": len(wildcard_imports),
            "dynamic_forwarding_count": len(dynamic_forwarding),
            "direct_store_reference_count": len(store_references),
            "oversized_function_count": len(oversized_functions),
            "cli_argument_count": int(snapshot["code_metrics"]["cli_argument_count"]),
            "api_route_count": int(snapshot["code_metrics"]["api_route_count"]),
        },
        "anonymous_part_files": part_files,
        "wildcard_imports": wildcard_imports,
        "dynamic_forwarding": dynamic_forwarding,
        "direct_store_references": store_references,
        "oversized_functions": oversized_functions,
        "integrity_hash": "",
    }
    document["integrity_hash"] = _stable_hash(document)
    return document


def _type_debt(root: Path, modules: dict[str, ImplementationDocument], final_sha: str) -> ImplementationDocument:
    by_layer: Counter[str] = Counter()
    by_context: Counter[str] = Counter()
    untyped_public: list[ImplementationDocument] = []
    for module, row in sorted(modules.items()):
        if row.get("layer") in {"compatibility", "release_check"}:
            continue
        path = root / str(row["path"])
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        count = source.count("dict[str, Any]")
        by_layer[str(row.get("layer"))] += count
        by_context[str(row.get("context") or "shared")] += count
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                if node.returns is None or any(arg.annotation is None for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)):
                    untyped_public.append({"module": module, "name": node.name, "line": node.lineno})
    document: ImplementationDocument = {
        "schema_version": 1,
        "package_type": "musicforge_v14_type_debt",
        "baseline_sha": final_sha,
        "dict_str_any_count": sum(by_layer.values()),
        "dict_str_any_by_layer": dict(sorted(by_layer.items())),
        "dict_str_any_by_context": dict(sorted(by_context.items())),
        "untyped_public_function_count": len(untyped_public),
        "untyped_public_functions": untyped_public,
        "integrity_hash": "",
    }
    document["integrity_hash"] = _stable_hash(document)
    return document


def _coverage_baseline(root: Path, report_path: Path | str | None, final_sha: str) -> ImplementationDocument:
    policy = json.loads((root / "coverage-governance.json").read_text(encoding="utf-8"))
    report = _optional_json(root, report_path)
    totals = dict(report.get("totals") or {}) if report else {}
    active_roots = tuple(str(value).replace("\\", "/") for value in policy["active"]["roots"])
    layers = {
        "active": _coverage_totals(report, include_roots=active_roots),
        "compatibility": _coverage_totals(report, exclude_roots=active_roots),
        "verification_kernel": _coverage_totals(report, include_roots=("song_agent/platform/verification/",)),
        "lifecycle_kernel": _coverage_totals(report, include_roots=("song_agent/platform/lifecycle/",)),
        "persistence_kernel": _coverage_totals(report, include_roots=("song_agent/platform/persistence/",)),
        "policy_kernel": _coverage_totals(report, include_roots=("song_agent/platform/policy/",)),
    } if report else {}
    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_coverage_baseline",
        "baseline_sha": final_sha,
        "status": "measured" if report else "pending_measurement",
        "policy": policy,
        "totals": totals,
        "layers": layers,
        "source_report_sha256": _file_hash(_rooted(root, report_path)) if report_path else "",
    }


def _performance_baseline(root: Path, report_path: Path | str | None, final_sha: str) -> ImplementationDocument:
    report = _optional_json(root, report_path)
    return {
        "schema_version": 1,
        "package_type": "musicforge_v14_performance_baseline",
        "baseline_sha": final_sha,
        "status": "measured" if report else "pending_measurement",
        "report": report,
        "source_report_sha256": _file_hash(_rooted(root, report_path)) if report_path else "",
    }


def _imports_by_target(snapshot: ImplementationDocument) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in snapshot["import_pairs"]:
        result.setdefault(str(row["imported"]), []).append(str(row["importer"]))
    return result


def _legacy_wrapper_target(root: Path, module: str) -> str:
    if module == "song_agent":
        return ""
    name = module.removeprefix("song_agent.").replace(".", "__") + ".py"
    wrapper = root / "song_agent" / "application" / "legacy_dependencies" / name
    if not wrapper.is_file():
        return ""
    tree = ast.parse(wrapper.read_text(encoding="utf-8"), filename=str(wrapper))
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname == "_implementation":
                    return alias.name
    return ""


def _domain_target(module: str, context: str) -> str:
    if module == "song_agent":
        return "song_agent.compat.v13"
    return f"song_agent.domains.{context}.{module.removeprefix('song_agent.')}"


def _public_names(tree: ast.AST) -> set[str]:
    explicit: set[str] = set()
    discovered: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            discovered.add(node.name)
        elif isinstance(node, ast.Import):
            discovered.update((alias.asname or alias.name.split(".", 1)[0]) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            discovered.update((alias.asname or alias.name) for alias in node.names if alias.name != "*")
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            discovered.update(name for target in targets for name in _assigned_names(target) if not name.startswith("_"))
            if any(name == "__all__" for target in targets for name in _assigned_names(target)):
                value = node.value
                if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                    explicit.update(
                        str(element.value)
                        for element in value.elts
                        if isinstance(element, ast.Constant) and isinstance(element.value, str)
                    )
    return explicit or {name for name in discovered if not name.startswith("_")}


def _assigned_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return {name for element in node.elts for name in _assigned_names(element)}
    return set()


def _state_paths(tree: ast.AST) -> list[str]:
    return sorted(
        {
            str(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and (".musicforge" in node.value.lower() or node.value.startswith(("runs/", "outputs/")))
        }
    )


def _evidence_types(tree: ast.AST) -> list[str]:
    return sorted(
        {
            str(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _EVIDENCE_LITERAL.fullmatch(node.value)
        }
    )


def _test_imports(root: Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in sorted((root / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        result[path.relative_to(root).as_posix()] = imported
    return result


def _uses_globals_update(node: ast.AST) -> bool:
    return any(isinstance(child, ast.Call) and _is_globals_update(child) for child in ast.walk(node))


def _is_globals_update(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "update":
        return False
    owner = call.func.value
    return isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) and owner.func.id == "globals"


def _uses_resolve_symbol(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "_resolve_symbol"
        for child in ast.walk(node)
    )


def _optional_json(root: Path, path: Path | str | None) -> ImplementationDocument:
    if path is None:
        return {}
    target = _rooted(root, path)
    if not target.is_file():
        return {}
    value = json.loads(target.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _coverage_totals(
    report: ImplementationDocument,
    *,
    include_roots: tuple[str, ...] = (),
    exclude_roots: tuple[str, ...] = (),
) -> ImplementationDocument:
    statements = 0
    covered = 0
    for raw_path, raw_row in dict(report.get("files") or {}).items():
        path = str(raw_path).replace("\\", "/")
        marker = path.find("song_agent/")
        normalized = path[marker:] if marker >= 0 else path
        if include_roots and not any(normalized.startswith(root) for root in include_roots):
            continue
        if exclude_roots and any(normalized.startswith(root) for root in exclude_roots):
            continue
        row = raw_row if isinstance(raw_row, dict) else {}
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        statements += int(summary.get("num_statements") or 0)
        covered += int(summary.get("covered_lines") or 0)
    return {
        "statements": statements,
        "covered": covered,
        "missing": statements - covered,
        "percent": round(100.0 if statements == 0 else 100.0 * covered / statements, 2),
    }


def _rooted(root: Path, path: Path | str) -> Path:
    target = Path(path)
    return target if target.is_absolute() else root / target


def _write_json(path: Path, value: ImplementationDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stable_hash(value: ImplementationDocument) -> str:
    payload = {key: item for key, item in value.items() if key != "integrity_hash"}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@contextmanager
def _baseline_source(root: Path) -> Iterable[Path]:
    archive = subprocess.run(
        ["git", "archive", "--format=tar", BASELINE_TAG],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    with tempfile.TemporaryDirectory(prefix="musicforge-v14-baseline-") as temp:
        target = Path(temp)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            bundle.extractall(target, filter="data")
        yield target
