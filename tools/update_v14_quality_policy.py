from __future__ import annotations

import argparse
import json
from pathlib import Path

from song_agent.platform.verification.hashing import stable_hash
from song_agent.release_check.v14_quality import (
    EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
    MYPY_CRITICAL_TARGETS,
    MYPY_ROOTS,
    QUALITY_POLICY_VERSION,
    V1421_EXPLICIT_ANY_FILE_BUDGETS_HASH,
    V1421_MODULE_DEBT_CEILINGS_HASH,
    V1421_RECOVERY_LIMITS,
    V1421_STABILIZATION_ADR,
    V1422_COLLECTOR_ADR,
    V1423_LAMBDA_COLLECTOR_ADR,
    V1424_DEFINITION_TIME_COLLECTOR_ADR,
    V1425_CLASS_GLOBAL_COLLECTOR_ADR,
    V1426_INDIRECT_TARGET_COLLECTOR_ADR,
    V1427_DERIVED_UNCERTAIN_COLLECTOR_ADR,
    V1428_OBJECT_ALIAS_COLLECTOR_ADR,
    V1429_ALIAS_DATAFLOW_ADR,
    V14210_ALIAS_FAIL_CLOSED_ADR,
    V14210_AFFECTED_FILE_CEILING,
    V14210_EXPLICIT_ANY_CEILING,
    V143_CALL_EFFECT_DATAFLOW_ADR,
    V143_CALL_EFFECT_SCHEMA_VERSION,
    V1431_COMPONENT_COMPACTION_ADR,
    V1432_EXPRESSION_SCAN_ADR,
    V1433_CALL_BINDING_ADR,
    V1433_CALL_BINDING_SCHEMA_VERSION,
    V1434_LEXICAL_CAPTURE_ADR,
    V1434_LEXICAL_CAPTURE_SCHEMA_VERSION,
    V1435_FIRST_GLOBAL_CAPTURE_ADR,
    V143_DEBT_SCHEDULE_ADR,
    active_source_tree_hash,
    build_v14_quality_policy,
    collect_complexity_metrics,
    collect_mypy_metrics,
    collect_typing_metrics,
    coverage_semantic_hash,
)
from song_agent.platform.verification.hashing import sha256_text_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the v14 typing, coverage, and complexity ratchet.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--coverage-report")
    parser.add_argument("--tracked-coverage-output", default="architecture-v14-coverage.json")
    parser.add_argument("--refresh-baseline", action="store_true")
    parser.add_argument("--ratchet-mypy", action="store_true")
    parser.add_argument("--ratchet-typing", action="store_true")
    parser.add_argument("--ratchet-complexity", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report = Path(args.coverage_report).resolve() if args.coverage_report else None
    path = root / "architecture-v14-quality.json"
    if path.is_file() and not args.refresh_baseline:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise RuntimeError("Existing v14 quality policy is invalid.")
    else:
        document = build_v14_quality_policy(root)
    if args.ratchet_mypy:
        _ratchet_mypy_policy(document, collect_mypy_metrics(root))
    if args.ratchet_typing:
        _ratchet_typing_policy(document, collect_typing_metrics(root))
    if args.ratchet_complexity:
        _ratchet_complexity_policy(document, root)
    _apply_v1421_stabilization_policy(document)
    if report is not None:
        output = (root / args.tracked_coverage_output).resolve()
        _write_compact_coverage(report, output, root)
        document["coverage"].update(
            {
                "report_path": output.relative_to(root).as_posix(),
                "report_sha256": _text_sha256(output),
                "source_tree_hash": active_source_tree_hash(root),
            }
        )
    document["integrity_hash"] = stable_hash(
        {key: value for key, value in document.items() if key != "integrity_hash"}
    )
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "path": path.relative_to(root).as_posix(),
                "raw_dict_str_any_max": document["typing"]["raw_dict_str_any_max_count"],
                "explicit_any_max": document["typing"].get("explicit_any_max_count", 0),
                "mypy_error_budget": document["mypy"]["max_total_errors"],
                "module_debt_count": len(document["module_size_debt"]),
                "coverage_bound": bool(document["coverage"]["report_sha256"]),
            },
            sort_keys=True,
        )
    )
    return 0


def _ratchet_mypy_policy(document: dict[str, object], metrics: dict[str, object]) -> None:
    policy = document.get("mypy")
    if not isinstance(policy, dict):
        raise RuntimeError("Existing v14 mypy policy is invalid.")
    current = int(metrics.get("total_errors") or 0)
    maximum = int(policy.get("max_total_errors") or 0)
    if metrics.get("status") != "measured" or metrics.get("strict_status") != "passed":
        raise RuntimeError("Mypy ownership cannot be ratcheted unless both measurements are valid.")
    if current > maximum:
        raise RuntimeError(f"Mypy ownership cannot grow: {current}>{maximum}.")
    budgets = metrics.get("error_budgets")
    if not isinstance(budgets, dict):
        raise RuntimeError("Measured mypy error budgets are invalid.")
    policy["active_roots"] = list(MYPY_ROOTS)
    policy["critical_targets"] = list(MYPY_CRITICAL_TARGETS)
    policy["max_total_errors"] = current
    policy["error_budgets"] = dict(sorted((str(key), int(value)) for key, value in budgets.items()))


def _ratchet_typing_policy(document: dict[str, object], metrics: dict[str, object]) -> None:
    policy = document.get("typing")
    if not isinstance(policy, dict):
        raise RuntimeError("Existing v14 typing policy is invalid.")
    raw = int(metrics.get("raw_dict_str_any_count") or 0)
    implementation = int(metrics.get("implementation_document_count") or 0)
    explicit_any = int(metrics.get("explicit_any_count") or 0)
    affected_files = int(metrics.get("explicit_any_affected_file_count") or 0)
    previous_raw = int(policy.get("raw_dict_str_any_max_count") or 0)
    previous_implementation = int(policy.get("implementation_document_max_count") or 0)
    has_explicit_any_budget = "explicit_any_max_count" in policy
    previous_explicit_any = int(policy.get("explicit_any_max_count") or explicit_any)
    previous_affected_files = int(policy.get("explicit_any_affected_file_max_count") or affected_files)
    if int(metrics.get("explicit_any_scope_blocker_count") or 0) != 0:
        raise RuntimeError("Typing ownership contains unsupported global/nonlocal alias flow.")
    if int(metrics.get("public_implementation_document_count") or 0) != 0:
        raise RuntimeError("Typing ownership cannot expose implementation documents publicly.")
    if int(metrics.get("untyped_public_function_count") or 0) != 0:
        raise RuntimeError("Typing ownership cannot introduce untyped public functions.")
    if explicit_any > previous_explicit_any:
        raise RuntimeError(f"Typing explicit Any cannot grow: {explicit_any}>{previous_explicit_any}.")
    if affected_files > previous_affected_files:
        raise RuntimeError(f"Typing explicit Any affected files cannot grow: {affected_files}>{previous_affected_files}.")
    previous_layers = {
        str(key): int(value)
        for key, value in (policy.get("explicit_any_layer_budgets") or {}).items()
    }
    current_layers = {
        str(key): int(value)
        for key, value in (metrics.get("explicit_any_by_layer") or {}).items()
    }
    if not has_explicit_any_budget:
        previous_layers = dict(current_layers)
    for layer, count in sorted(current_layers.items()):
        maximum = previous_layers.get(layer, 0)
        if count > maximum:
            raise RuntimeError(f"Typing explicit Any layer cannot grow: {layer} {count}>{maximum}.")
    previous_files = {
        str(key): int(value)
        for key, value in (policy.get("explicit_any_file_budgets") or {}).items()
    }
    current_files = {
        str(key): int(value)
        for key, value in (metrics.get("explicit_any_by_file") or {}).items()
    }
    if not has_explicit_any_budget:
        previous_files = dict(current_files)
    for path, count in sorted(current_files.items()):
        maximum = previous_files.get(path, 0)
        if count > maximum:
            raise RuntimeError(f"Typing explicit Any file cannot grow: {path} {count}>{maximum}.")
    if raw + implementation > previous_raw + previous_implementation:
        raise RuntimeError(
            "Typing ownership cannot grow: "
            f"{raw + implementation}>{previous_raw + previous_implementation}."
        )
    policy["raw_dict_str_any_max_count"] = raw
    policy["implementation_document_max_count"] = implementation
    policy["explicit_any_collector_schema_version"] = EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    policy["explicit_any_max_count"] = explicit_any
    policy["explicit_any_affected_file_max_count"] = affected_files
    policy["explicit_any_layer_budgets"] = dict(sorted(current_layers.items()))
    policy["explicit_any_file_budgets"] = dict(sorted(current_files.items()))


def _ratchet_complexity_policy(document: dict[str, object], root: Path) -> None:
    rows = document.get("module_size_debt")
    complexity = document.get("complexity")
    if not isinstance(rows, list) or not isinstance(complexity, dict):
        raise RuntimeError("Existing v14 complexity policy is invalid.")
    previous = {
        str(row["path"]): int(row["max_lines"])
        for row in rows
        if isinstance(row, dict) and row.get("path")
    }
    metrics = collect_complexity_metrics(root, document)
    current = {str(row["path"]): int(row["lines"]) for row in metrics["oversized_modules"]}
    added = sorted(set(current) - set(previous))
    if added:
        raise RuntimeError(f"Complexity debt cannot add oversized modules: {added}.")
    grown = {path: (previous[path], current[path]) for path in sorted(current) if current[path] > previous.get(path, 0)}
    if grown:
        raise RuntimeError(f"Complexity debt cannot grow registered modules: {grown}.")
    previous_total = sum(previous.values())
    current_total = sum(current.values())
    if len(current) > len(previous):
        raise RuntimeError(f"Oversized module count cannot grow: {len(current)}>{len(previous)}.")
    if current_total >= previous_total:
        raise RuntimeError(f"Oversized module lines must decrease: {current_total}>={previous_total}.")
    document["module_size_debt"] = [
        {"path": path, "max_lines": lines, "expires_version": "14.4.0"}
        for path, lines in sorted(current.items())
    ]
    aggregate = dict(metrics["aggregate"])
    complexity["aggregate_debt"] = {
        "architecture_decision": V1421_STABILIZATION_ADR,
        "expires_version": "14.4.0",
        "previous_oversized_module_count": len(previous),
        "previous_total_oversized_module_lines": previous_total,
        "required_total_line_reduction": previous_total - current_total,
        "max_oversized_module_count": aggregate["oversized_module_count"],
        "max_modules_over_1000_lines": aggregate["modules_over_1000_lines"],
        "max_largest_module_lines": aggregate["largest_module_lines"],
        "max_total_oversized_module_lines": aggregate["total_oversized_module_lines"],
    }


def _apply_v1421_stabilization_policy(document: dict[str, object]) -> None:
    document["release_version"] = QUALITY_POLICY_VERSION
    rows = document.get("module_size_debt")
    complexity = document.get("complexity")
    if not isinstance(rows, list) or not isinstance(complexity, dict):
        raise RuntimeError("Existing v14 complexity policy is invalid.")
    for row in rows:
        if isinstance(row, dict):
            row["expires_version"] = "14.4.0"
    aggregate = dict(complexity.get("aggregate_debt") or {})
    aggregate.update(
        {
            "architecture_decision": V1421_STABILIZATION_ADR,
            "expires_version": "14.4.0",
            "max_oversized_module_count": V1421_RECOVERY_LIMITS["oversized_module_max_count"],
            "max_modules_over_1000_lines": V1421_RECOVERY_LIMITS["modules_over_1000_max_count"],
            "max_largest_module_lines": V1421_RECOVERY_LIMITS["largest_module_max_lines"],
            "max_total_oversized_module_lines": V1421_RECOVERY_LIMITS["total_oversized_module_max_lines"],
        }
    )
    complexity["aggregate_debt"] = aggregate
    document["stabilization"] = {
        "architecture_decision": V1421_STABILIZATION_ADR,
        "collector_decision": V1422_COLLECTOR_ADR,
        "lambda_collector_decision": V1423_LAMBDA_COLLECTOR_ADR,
        "definition_time_collector_decision": V1424_DEFINITION_TIME_COLLECTOR_ADR,
        "class_global_collector_decision": V1425_CLASS_GLOBAL_COLLECTOR_ADR,
        "indirect_target_collector_decision": V1426_INDIRECT_TARGET_COLLECTOR_ADR,
        "derived_uncertain_collector_decision": V1427_DERIVED_UNCERTAIN_COLLECTOR_ADR,
        "object_alias_collector_decision": V1428_OBJECT_ALIAS_COLLECTOR_ADR,
        "alias_dataflow_collector_decision": V1429_ALIAS_DATAFLOW_ADR,
        "alias_fail_closed_collector_decision": V14210_ALIAS_FAIL_CLOSED_ADR,
        "call_effect_dataflow_collector_decision": V143_CALL_EFFECT_DATAFLOW_ADR,
        "call_effect_component_compaction_decision": V1431_COMPONENT_COMPACTION_ADR,
        "expression_binding_single_pass_decision": V1432_EXPRESSION_SCAN_ADR,
        "call_binding_lambda_effect_decision": V1433_CALL_BINDING_ADR,
        "late_bound_lexical_capture_decision": V1434_LEXICAL_CAPTURE_ADR,
        "first_global_lexical_capture_decision": V1435_FIRST_GLOBAL_CAPTURE_ADR,
        "debt_schedule_decision": V143_DEBT_SCHEDULE_ADR,
        "strategy": "rollback_generated_v142_split_to_v14.1.2_structure",
        "collector_migration": {
            "from_schema_version": 2,
            "to_schema_version": 4,
            "previous_explicit_any_count": 11744,
            "recovered_explicit_any_count": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
        },
        "collector_hotfix": {
            "from_schema_version": 4,
            "to_schema_version": 5,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "lambda_collector_hotfix": {
            "from_schema_version": 5,
            "to_schema_version": 6,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "definition_time_collector_hotfix": {
            "from_schema_version": 6,
            "to_schema_version": 7,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "class_global_collector_hotfix": {
            "from_schema_version": 7,
            "to_schema_version": 8,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "indirect_target_collector_hotfix": {
            "from_schema_version": 8,
            "to_schema_version": 9,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "derived_uncertain_collector_hotfix": {
            "from_schema_version": 9,
            "to_schema_version": 10,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "object_alias_collector_hotfix": {
            "from_schema_version": 10,
            "to_schema_version": 11,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "alias_dataflow_collector_hotfix": {
            "from_schema_version": 11,
            "to_schema_version": 12,
            "previous_explicit_any_ceiling": V1421_RECOVERY_LIMITS["explicit_any_max_count"],
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "alias_fail_closed_collector_hotfix": {
            "from_schema_version": 12,
            "to_schema_version": 13,
            "previous_explicit_any_ceiling": V14210_EXPLICIT_ANY_CEILING,
            "previous_affected_file_ceiling": V14210_AFFECTED_FILE_CEILING,
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "call_effect_dataflow_collector_migration": {
            "from_schema_version": 13,
            "to_schema_version": V143_CALL_EFFECT_SCHEMA_VERSION,
            "previous_explicit_any_ceiling": V14210_EXPLICIT_ANY_CEILING,
            "previous_affected_file_ceiling": V14210_AFFECTED_FILE_CEILING,
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "call_binding_lambda_effect_collector_migration": {
            "from_schema_version": V143_CALL_EFFECT_SCHEMA_VERSION,
            "to_schema_version": V1433_CALL_BINDING_SCHEMA_VERSION,
            "previous_explicit_any_ceiling": V14210_EXPLICIT_ANY_CEILING,
            "previous_affected_file_ceiling": V14210_AFFECTED_FILE_CEILING,
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "late_bound_lexical_capture_collector_migration": {
            "from_schema_version": V1433_CALL_BINDING_SCHEMA_VERSION,
            "to_schema_version": V1434_LEXICAL_CAPTURE_SCHEMA_VERSION,
            "previous_explicit_any_ceiling": V14210_EXPLICIT_ANY_CEILING,
            "previous_affected_file_ceiling": V14210_AFFECTED_FILE_CEILING,
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "first_global_lexical_capture_collector_migration": {
            "from_schema_version": V1434_LEXICAL_CAPTURE_SCHEMA_VERSION,
            "to_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "previous_explicit_any_ceiling": V14210_EXPLICIT_ANY_CEILING,
            "previous_affected_file_ceiling": V14210_AFFECTED_FILE_CEILING,
            "corrected_explicit_any_count": int((document.get("typing") or {}).get("explicit_any_max_count") or 0),
        },
        "hard_limits": V1421_RECOVERY_LIMITS,
        "explicit_any_file_budgets_hash": V1421_EXPLICIT_ANY_FILE_BUDGETS_HASH,
        "module_debt_ceilings_hash": V1421_MODULE_DEBT_CEILINGS_HASH,
    }


def _write_compact_coverage(source: Path, target: Path, root: Path) -> None:
    raw = json.loads(source.read_text(encoding="utf-8"))
    files = {}
    for raw_path, row in (raw.get("files") or {}).items():
        path = Path(str(raw_path))
        if path.is_absolute():
            try:
                normalized = path.resolve().relative_to(root).as_posix()
            except ValueError as exc:
                raise RuntimeError("Coverage report contains a path outside the repository.") from exc
        else:
            normalized = str(raw_path).replace("\\", "/")
        if normalized.startswith("../") or "/../" in normalized:
            raise RuntimeError("Coverage report contains an unsafe relative path.")
        summary = row.get("summary") if isinstance(row, dict) else {}
        files[normalized] = {
            "summary": {
                "num_statements": int((summary or {}).get("num_statements") or 0),
                "covered_lines": int((summary or {}).get("covered_lines") or 0),
                "missing_lines": int((summary or {}).get("missing_lines") or 0),
            }
        }
    document = {
        "schema_version": 2,
        "package_type": "musicforge_v14_coverage_evidence",
        "source_report_semantic_hash": coverage_semantic_hash(files),
        "file_count": len(files),
        "files": dict(sorted(files.items())),
    }
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text_sha256(path: Path) -> str:
    value = sha256_text_file(path)
    if value is None:
        raise FileNotFoundError(path)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
