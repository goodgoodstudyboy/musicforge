from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


RATCHET_SCHEMA_VERSION = 1
DEFAULT_DECLARATION_PATH = "architecture-ratchet.json"
DEFAULT_DEBT_PATH = "architecture-debt.json"


def evaluate_architecture_ratchet(
    repo_root: Path | str,
    *,
    current_baseline: dict[str, Any],
    snapshot: dict[str, Any],
    declaration_path: Path | str = DEFAULT_DECLARATION_PATH,
    debt_path: Path | str = DEFAULT_DEBT_PATH,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    declaration = _read_json(_resolve(root, declaration_path))
    debt = _read_json(_resolve(root, debt_path))
    previous_tag = str(declaration.get("previous_release_tag") or "")
    previous_baseline = _git_json(root, previous_tag, "architecture-baseline.json")
    blockers: list[str] = []
    if not previous_tag or not previous_baseline:
        blockers.append("architecture_ratchet_previous_baseline_missing")
    blockers.extend(_declaration_checks(declaration))
    blockers.extend(_baseline_checks(previous_baseline, current_baseline))
    blockers.extend(_compatibility_checks(previous_baseline, snapshot, debt))
    interface = evaluate_interface_limits(root, previous_tag=previous_tag, debt=debt)
    blockers.extend(interface["blockers"])
    previous_count = int(previous_baseline.get("active_to_compatibility_import_max_count", 0))
    current_count = len(snapshot.get("active_to_compatibility_imports") or [])
    if declaration.get("require_active_import_decrease", True) and current_count >= previous_count:
        blockers.append(f"architecture_compatibility_import_not_reduced:{current_count}>={previous_count}")
    report = {
        "schema_version": RATCHET_SCHEMA_VERSION,
        "package_type": "musicforge_architecture_ratchet_report",
        "status": "passed" if not blockers else "failed",
        "release_version": declaration.get("release_version"),
        "current_commit": _git_text(root, "rev-parse", "--verify", "HEAD"),
        "previous_release_tag": previous_tag,
        "previous_release_commit": _git_text(root, "rev-parse", f"{previous_tag}^{{}}"),
        "previous_baseline_hash": _stable_hash(previous_baseline),
        "current_baseline_hash": _stable_hash(current_baseline),
        "debt_catalog_hash": _stable_hash(debt),
        "delta": {
            "module_count": int(snapshot.get("module_count", 0)) - int(previous_baseline.get("module_count", 0)),
            "active_to_compatibility_import_count": current_count - previous_count,
            "previous_active_to_compatibility_import_count": previous_count,
            "current_active_to_compatibility_import_count": current_count,
            "compatibility_module_count": sum(
                1 for row in snapshot.get("modules", []) if row.get("layer") == "compatibility"
            ),
        },
        "interface_limits": interface,
        "compatibility_debt_count": len(debt.get("compatibility_entries") or []),
        "blockers": blockers,
    }
    return report


def verify_architecture_ratchet_report(
    repo_root: Path | str,
    report: dict[str, Any],
    *,
    current_baseline: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    expected = evaluate_architecture_ratchet(
        repo_root,
        current_baseline=current_baseline,
        snapshot=snapshot,
    )
    fields = (
        "status",
        "release_version",
        "previous_release_tag",
        "previous_release_commit",
        "previous_baseline_hash",
        "current_baseline_hash",
        "debt_catalog_hash",
        "delta",
        "interface_limits",
        "compatibility_debt_count",
        "blockers",
    )
    mismatches = [field for field in fields if report.get(field) != expected.get(field)]
    return {
        "status": "passed" if not mismatches and expected["status"] == "passed" else "failed",
        "mismatches": mismatches,
        "runtime_status": expected["status"],
    }


def evaluate_interface_limits(
    repo_root: Path | str,
    *,
    previous_tag: str,
    debt: dict[str, Any],
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    limits = debt.get("interface_limits") or {}
    module_limit = int(limits.get("module_max_lines", 600))
    new_module_limit = int(limits.get("new_module_max_lines", 400))
    function_limit = int(limits.get("function_max_lines", 80))
    route_limit = int(limits.get("route_handler_max_lines", 100))
    debt_rows = {str(row.get("path")): row for row in debt.get("interface_entries") or []}
    blockers: list[str] = []
    measurements: list[dict[str, Any]] = []
    for path in _interface_paths(root):
        relative = path.relative_to(root).as_posix()
        source = path.read_text(encoding="utf-8")
        previous_source = _git_source(root, previous_tag, relative)
        current_lines = len(source.splitlines())
        previous_lines = len(previous_source.splitlines()) if previous_source is not None else None
        debt_row = debt_rows.get(relative)
        function_debt = {
            str(row.get("name")): row
            for row in (debt_row or {}).get("functions") or []
            if row.get("name")
        }
        if previous_source is None and current_lines > new_module_limit:
            blockers.append(f"architecture_interface_new_module_limit:{relative}:{current_lines}>{new_module_limit}")
        elif current_lines > module_limit:
            if not debt_row:
                blockers.append(f"architecture_interface_module_debt_missing:{relative}")
            if previous_lines is not None and current_lines > previous_lines:
                blockers.append(f"architecture_interface_module_growth:{relative}:{current_lines}>{previous_lines}")
        function_rows = _function_rows(source, relative)
        previous_functions = _function_index(previous_source or "", relative)
        for row in function_rows:
            limit = route_limit if row["route_handler"] else function_limit
            if int(row["lines"]) <= limit:
                continue
            previous_function_lines = int(previous_functions.get(str(row["name"]), 0))
            declared_function = function_debt.get(str(row["name"]))
            if not debt_row or (not previous_function_lines and not declared_function):
                blockers.append(f"architecture_interface_function_debt_missing:{relative}:{row['name']}")
            declared_maximum = int((declared_function or {}).get("max_lines") or 0)
            candidates = [value for value in (previous_function_lines, declared_maximum) if value]
            maximum = min(candidates) if candidates else 0
            if not maximum or int(row["lines"]) > maximum:
                blockers.append(
                    f"architecture_interface_function_limit:{relative}:{row['name']}:{row['lines']}>{limit}"
                )
        measurements.append(
            {
                "path": relative,
                "lines": current_lines,
                "previous_lines": previous_lines,
                "debt": bool(debt_row),
                "oversized_function_count": sum(
                    1
                    for row in function_rows
                    if int(row["lines"]) > (route_limit if row["route_handler"] else function_limit)
                ),
            }
        )
    return {
        "status": "passed" if not blockers else "failed",
        "limits": {
            "module_max_lines": module_limit,
            "new_module_max_lines": new_module_limit,
            "function_max_lines": function_limit,
            "route_handler_max_lines": route_limit,
        },
        "measurements": measurements,
        "blockers": blockers,
    }


def build_architecture_debt_catalog(
    repo_root: Path | str,
    *,
    previous_release_tag: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    import_counts: dict[str, int] = {}
    for row in snapshot.get("active_to_compatibility_imports") or []:
        imported = str(row.get("imported") or "")
        import_counts[imported] = import_counts.get(imported, 0) + 1
    compatibility_entries = [
        {
            "module": str(row["module"]),
            "owner": f"musicforge-{row.get('context') or 'core'}",
            "reason": "Legacy production module awaiting migration behind an active modular boundary.",
            "removal_target_version": "13.8.0",
            "active_import_count": import_counts.get(str(row["module"]), 0),
        }
        for row in snapshot.get("modules") or []
        if row.get("layer") == "compatibility"
    ]
    historical_functions = _historical_interface_functions(root, previous_release_tag)
    interface_entries = []
    for path in _interface_paths(root):
        relative = path.relative_to(root).as_posix()
        previous = _git_source(root, previous_release_tag, relative)
        current = path.read_text(encoding="utf-8")
        current_functions = _function_rows(current, relative)
        previous_functions = _function_index(previous or "", relative)
        function_entries = []
        for row in current_functions:
            limit = 100 if row["route_handler"] else 80
            if int(row["lines"]) <= limit:
                continue
            origin = None
            if str(row["name"]) in previous_functions:
                origin = {
                    "path": relative,
                    "name": str(row["name"]),
                    "lines": int(previous_functions[str(row["name"])]),
                }
            else:
                candidates = historical_functions.get(str(row["name"])) or []
                candidates = [candidate for candidate in candidates if int(candidate["lines"]) >= int(row["lines"])]
                if candidates:
                    origin = min(candidates, key=lambda candidate: int(candidate["lines"]))
                else:
                    origin = _migrated_dispatch_origin(relative, str(row["name"]), int(row["lines"]))
            if origin:
                function_entries.append(
                    {
                        "name": str(row["name"]),
                        "max_lines": int(row["lines"]),
                        "migrated_from": f"{origin['path']}:{origin['name']}",
                    }
                )
        if len(current.splitlines()) <= 600 and not function_entries:
            continue
        interface_entries.append(
            {
                "path": relative,
                "owner": "musicforge-interfaces",
                "reason": "Pre-v13 interface surface exceeds the hard limit and is held to no growth until decomposition.",
                "removal_target_version": "13.8.0",
                "functions": function_entries,
            }
        )
    return {
        "schema_version": RATCHET_SCHEMA_VERSION,
        "previous_release_tag": previous_release_tag,
        "interface_limits": {
            "module_max_lines": 600,
            "new_module_max_lines": 400,
            "function_max_lines": 80,
            "route_handler_max_lines": 100,
        },
        "compatibility_entries": compatibility_entries,
        "interface_entries": interface_entries,
    }


def _historical_interface_functions(root: Path, tag: str) -> dict[str, list[dict[str, Any]]]:
    paths = _git_text(
        root,
        "ls-tree",
        "-r",
        "--name-only",
        tag,
        "song_agent/interfaces",
        "song_agent/cli.py",
        "song_agent/server.py",
        "song_agent/webui.py",
    ).splitlines()
    result: dict[str, list[dict[str, Any]]] = {}
    for relative in paths:
        if not relative.endswith(".py"):
            continue
        source = _git_source(root, tag, relative)
        if source is None:
            continue
        for row in _function_rows(source, relative):
            result.setdefault(str(row["name"]), []).append(
                {"path": relative, "name": str(row["name"]), "lines": int(row["lines"])}
            )
    return result


def _migrated_dispatch_origin(relative: str, name: str, lines: int) -> dict[str, Any] | None:
    origins = (
        (
            "song_agent/interfaces/api/routes/trust_portfolio_parts/",
            "_dispatch_portfolio_",
            "song_agent/interfaces/api/routes/trust.py",
            "_handle_release_portfolio_audits",
        ),
        (
            "song_agent/interfaces/api/routes/program_ucc_parts/",
            "_dispatch_ucc_",
            "song_agent/interfaces/api/routes/program.py",
            "_handle_unified_command_centers_route",
        ),
    )
    for path_prefix, name_prefix, origin_path, origin_name in origins:
        if relative.startswith(path_prefix) and name.startswith(name_prefix):
            return {"path": origin_path, "name": origin_name, "lines": lines}
    return None


def _declaration_checks(document: dict[str, Any]) -> list[str]:
    blockers = []
    if document.get("schema_version") != RATCHET_SCHEMA_VERSION:
        blockers.append("architecture_ratchet_schema")
    if not document.get("release_version"):
        blockers.append("architecture_ratchet_release_version")
    return blockers


def _baseline_checks(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field in ("mega_file_max_lines", "security_helper_max_counts"):
        previous_values = previous.get(field) or {}
        current_values = current.get(field) or {}
        for key, old_value in previous_values.items():
            if int(current_values.get(key, old_value)) > int(old_value):
                blockers.append(f"architecture_baseline_loosened:{field}:{key}")
    previous_exceptions = {_stable_hash(row) for row in previous.get("dependency_exceptions") or []}
    for row in current.get("dependency_exceptions") or []:
        if _stable_hash(row) not in previous_exceptions:
            blockers.append("architecture_baseline_dependency_exception_added")
    previous_cycles = {tuple(sorted(map(str, row))) for row in previous.get("allowed_cycles") or []}
    for row in current.get("allowed_cycles") or []:
        if tuple(sorted(map(str, row))) not in previous_cycles:
            blockers.append("architecture_baseline_cycle_added")
    return blockers


def _compatibility_checks(
    previous: dict[str, Any],
    snapshot: dict[str, Any],
    debt: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    debt_rows = {str(row.get("module")): row for row in debt.get("compatibility_entries") or []}
    import_counts: dict[str, int] = {}
    for row in snapshot.get("active_to_compatibility_imports") or []:
        imported = str(row.get("imported") or "")
        import_counts[imported] = import_counts.get(imported, 0) + 1
    previous_layers = {str(row.get("module")): str(row.get("layer")) for row in previous.get("modules") or []}
    current_compatibility = {
        str(row.get("module")) for row in snapshot.get("modules") or [] if row.get("layer") == "compatibility"
    }
    for module in sorted(current_compatibility):
        row = debt_rows.get(module)
        if not row:
            blockers.append(f"architecture_compatibility_debt_missing:{module}")
            continue
        for field in ("owner", "reason", "removal_target_version"):
            if not row.get(field):
                blockers.append(f"architecture_compatibility_debt_{field}_missing:{module}")
        if int(row.get("active_import_count", -1)) != import_counts.get(module, 0):
            blockers.append(f"architecture_compatibility_debt_import_count:{module}")
        if previous_layers.get(module) not in {None, "compatibility"} and not row.get("reason"):
            blockers.append(f"architecture_compatibility_reclassification_unapproved:{module}")
    unknown = sorted(set(debt_rows) - current_compatibility)
    blockers.extend(f"architecture_compatibility_debt_stale:{module}" for module in unknown)
    previous_imports = {
        (str(row.get("importer")), str(row.get("imported")))
        for row in previous.get("allowed_active_to_compatibility_imports") or []
    }
    current_imports = {
        (str(row.get("importer")), str(row.get("imported")))
        for row in snapshot.get("active_to_compatibility_imports") or []
    }
    previous_targets = {imported for _importer, imported in previous_imports}
    blockers.extend(
        f"architecture_compatibility_import_added:{left}->{right}"
        for left, right in sorted(current_imports - previous_imports)
        if not (
            left.startswith("song_agent.application.legacy_dependencies.")
            and right in previous_targets
        )
    )
    return blockers


def _interface_paths(root: Path) -> list[Path]:
    paths = list((root / "song_agent" / "interfaces").rglob("*.py"))
    paths.extend(root / "song_agent" / name for name in ("cli.py", "server.py", "webui.py"))
    return sorted(path for path in paths if path.is_file())


def _function_rows(source: str, relative: str) -> list[dict[str, Any]]:
    if not source:
        return []
    tree = ast.parse(source, filename=relative)
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        rows.append(
            {
                "name": node.name,
                "lines": int(node.end_lineno or node.lineno) - int(node.lineno) + 1,
                "route_handler": "/api/routes/" in f"/{relative}" and node.name.startswith("_handle"),
            }
        )
    return rows


def _function_index(source: str, relative: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in _function_rows(source, relative):
        name = str(row["name"])
        result[name] = max(result.get(name, 0), int(row["lines"]))
    return result


def _resolve(root: Path, value: Path | str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _git_json(root: Path, tag: str, path: str) -> dict[str, Any]:
    source = _git_source(root, tag, path)
    if source is None:
        return {}
    value = json.loads(source)
    return value if isinstance(value, dict) else {}


def _git_source(root: Path, tag: str, path: str) -> str | None:
    if not tag:
        return None
    completed = subprocess.run(
        ["git", "show", f"{tag}:{path}"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else None


def _git_text(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


def _stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
