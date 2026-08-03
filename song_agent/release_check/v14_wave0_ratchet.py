from __future__ import annotations

import hashlib
import json
from typing import cast


def quality_regressions(frozen: dict[str, object], current: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    _compare_max_tree(frozen.get("typing"), current.get("typing"), "typing", blockers)
    _compare_max_tree(frozen.get("complexity"), current.get("complexity"), "complexity", blockers)
    _compare_module_debt(frozen.get("module_size_debt"), current.get("module_size_debt"), blockers)
    _compare_mypy(frozen.get("mypy"), current.get("mypy"), blockers)
    _compare_min_tree(frozen.get("coverage_minimums"), current.get("coverage_minimums"), "coverage_minimums", blockers)
    _compare_max_tree(frozen.get("architecture_limits"), current.get("architecture_limits"), "architecture_limits", blockers)
    for key in (
        "profile_duration_budgets",
        "ci_profile_duration_budgets",
        "check_duration_budgets",
    ):
        _compare_max_tree(frozen.get(key), current.get(key), key, blockers)
    old_warning = {str(value) for value in cast(list[object], frozen.get("profile_budget_warning_only") or [])}
    new_warning = {str(value) for value in cast(list[object], current.get("profile_budget_warning_only") or [])}
    for profile in sorted(new_warning - old_warning):
        blockers.append(f"quality_warning_only_growth:{profile}")
    return sorted(set(blockers))


def dependency_regressions(frozen: dict[str, object], current: dict[str, object]) -> list[str]:
    blockers: list[str] = []
    for key in (
        "module_count",
        "total_source_lines",
        "production_cycle_count",
        "boundary_violation_count",
        "active_to_compatibility_import_count",
    ):
        _compare_max_value(frozen.get(key), current.get(key), f"dependency:{key}", blockers)
    for key in ("cross_domain_imports", "interface_domain_imports"):
        old = {_edge_identity(row) for row in cast(list[dict[str, object]], frozen.get(key) or [])}
        new = {_edge_identity(row) for row in cast(list[dict[str, object]], current.get(key) or [])}
        for edge in sorted(new - old):
            blockers.append(f"dependency_edge_growth:{key}:{edge}")
    return sorted(set(blockers))


def registry_regressions(
    frozen: dict[str, object],
    current: dict[str, object],
    waivers: dict[str, object],
    *,
    baseline_integrity_hash: str = "",
) -> list[str]:
    blockers: list[str] = []
    waiver_rows = cast(list[dict[str, object]], waivers.get("waivers") or [])
    for target_type in sorted(set(frozen) | set(current)):
        old_entries = cast(dict[str, object], frozen.get(target_type) or {})
        new_entries = cast(dict[str, object], current.get(target_type) or {})
        for target_id in sorted(set(old_entries) | set(new_entries)):
            old_fields = cast(dict[str, object], old_entries.get(target_id) or {})
            new_fields = cast(dict[str, object], new_entries.get(target_id) or {})
            if target_id not in old_entries:
                if not _waived(
                    waiver_rows,
                    target_type,
                    target_id,
                    "__new__",
                    None,
                    new_fields,
                    baseline_integrity_hash,
                ):
                    blockers.append(f"registry_entry_growth:{target_type}:{target_id}")
                continue
            if target_id not in new_entries:
                if not _waived(
                    waiver_rows,
                    target_type,
                    target_id,
                    "__removed__",
                    old_fields,
                    None,
                    baseline_integrity_hash,
                ):
                    blockers.append(f"registry_entry_removed:{target_type}:{target_id}")
                continue
            for field in sorted(set(old_fields) | set(new_fields)):
                if old_fields.get(field) != new_fields.get(field) and not _waived(
                    waiver_rows,
                    target_type,
                    target_id,
                    field,
                    old_fields.get(field),
                    new_fields.get(field),
                    baseline_integrity_hash,
                ):
                    blockers.append(f"registry_metadata_changed:{target_type}:{target_id}:{field}")
    return blockers


def registry_field_snapshot(registries: dict[str, dict[str, object]]) -> dict[str, object]:
    definitions = (
        ("capabilities", "capabilities", "capability_id"),
        ("state", "entries", "store_id"),
        ("state_roots", "roots", "root_authority_id"),
        ("state_overlap_exceptions", "writer_overlap_exceptions", "exception_id"),
        ("package_types", "package_types", "package_type"),
        ("package_sites", "dynamic_sites", "site_id"),
        ("package_type_sets", "package_type_sets", "type_set_id"),
        ("package_writer_contracts", "writer_contracts", "writer_id"),
        ("schemas", "schemas", "schema_id"),
    )
    result: dict[str, object] = {}
    for target_type, document_key, identity_key in definitions:
        registry_key = (
            "packages"
            if target_type in {"package_types", "package_sites", "package_type_sets", "package_writer_contracts", "schemas"}
            else "state"
            if target_type in {"state_roots", "state_overlap_exceptions"}
            else target_type
        )
        rows = cast(list[dict[str, object]], registries[registry_key][document_key])
        excluded = {identity_key}
        if target_type == "state_overlap_exceptions":
            # The exception binds the resulting Wave 0 baseline. Excluding only
            # that back-reference avoids a hash cycle; all semantic fields stay frozen.
            excluded.add("baseline_integrity_hash")
        result[target_type] = {str(row[identity_key]): {key: value for key, value in row.items() if key not in excluded} for row in rows}
    return result


def _compare_module_debt(old_value: object, new_value: object, blockers: list[str]) -> None:
    old = {str(row.get("path") or ""): row for row in cast(list[dict[str, object]], old_value or [])}
    new = {str(row.get("path") or ""): row for row in cast(list[dict[str, object]], new_value or [])}
    for path in sorted(set(new) - set(old)):
        blockers.append(f"quality_debt_growth:{path}")
    for path in sorted(set(old) & set(new)):
        _compare_max_value(old[path].get("max_lines"), new[path].get("max_lines"), f"module_size:{path}", blockers)
        if _version_key(str(new[path].get("expires_version") or "")) > _version_key(str(old[path].get("expires_version") or "")):
            blockers.append(f"quality_deadline_extended:{path}")


def _compare_mypy(old_value: object, new_value: object, blockers: list[str]) -> None:
    old = cast(dict[str, object], old_value or {})
    new = cast(dict[str, object], new_value or {})
    _compare_max_value(old.get("max_total_errors"), new.get("max_total_errors"), "mypy:max_total_errors", blockers)
    _compare_max_tree(old.get("error_budgets"), new.get("error_budgets"), "mypy:error_budgets", blockers)
    for key in ("active_roots", "critical_targets"):
        old_set = {str(value) for value in cast(list[object], old.get(key) or [])}
        new_set = {str(value) for value in cast(list[object], new.get(key) or [])}
        for value in sorted(old_set - new_set):
            blockers.append(f"quality_mypy_scope_reduced:{key}:{value}")
    if bool(old.get("strict_required")) and not bool(new.get("strict_required")):
        blockers.append("quality_mypy_strict_disabled")


def _compare_max_tree(old_value: object, new_value: object, path: str, blockers: list[str]) -> None:
    if isinstance(old_value, dict) and isinstance(new_value, dict):
        for key in sorted(set(old_value) | set(new_value)):
            child = f"{path}.{key}"
            if key not in old_value:
                blockers.append(f"quality_ceiling_added:{child}")
            elif key not in new_value:
                continue
            elif _is_numeric(old_value[key]) and _is_numeric(new_value[key]):
                if _is_minimum_or_schema(key):
                    _compare_min_value(old_value[key], new_value[key], child, blockers)
                elif _is_historical_or_hash(key):
                    continue
                else:
                    _compare_max_value(old_value[key], new_value[key], child, blockers)
            elif isinstance(old_value[key], dict) and isinstance(new_value[key], dict):
                _compare_max_tree(old_value[key], new_value[key], child, blockers)
            elif old_value[key] != new_value[key] and not _is_historical_or_hash(key):
                blockers.append(f"quality_policy_changed:{child}")
        return
    if old_value != new_value:
        blockers.append(f"quality_policy_changed:{path}")


def _compare_min_tree(old_value: object, new_value: object, path: str, blockers: list[str]) -> None:
    old = cast(dict[str, object], old_value or {})
    new = cast(dict[str, object], new_value or {})
    for key in sorted(set(old) | set(new)):
        child = f"{path}.{key}"
        if key not in new:
            blockers.append(f"quality_minimum_removed:{child}")
        elif key not in old:
            continue
        else:
            _compare_min_value(old[key], new[key], child, blockers)


def _compare_max_value(old: object, new: object, path: str, blockers: list[str]) -> None:
    if not _is_numeric(old) or not _is_numeric(new) or float(cast(int | float, new)) > float(cast(int | float, old)):
        blockers.append(f"quality_ceiling_raised:{path}")


def _compare_min_value(old: object, new: object, path: str, blockers: list[str]) -> None:
    if not _is_numeric(old) or not _is_numeric(new) or float(cast(int | float, new)) < float(cast(int | float, old)):
        blockers.append(f"quality_minimum_lowered:{path}")


def _edge_identity(row: dict[str, object]) -> str:
    return f"{row.get('importer', '')}->{row.get('imported', '')}"


def _waived(
    rows: list[dict[str, object]],
    target_type: str,
    target_id: str,
    field: str,
    old_value: object,
    new_value: object,
    baseline_integrity_hash: str,
) -> bool:
    return any(
        row.get("target_type") == target_type
        and row.get("target_id") == target_id
        and cast(list[object], row.get("fields") or []) == [field]
        and row.get("status") == "approved"
        and str(row.get("approved_by") or "") in {"architecture-reviewers", "release-owner", "security-reviewer"}
        and bool(str(row.get("approved_at") or ""))
        and str(row.get("owner") or "").strip().lower() not in {"", "nobody", "unknown", "none"}
        and row.get("baseline_integrity_hash") == baseline_integrity_hash
        and row.get("old_value_hash") == _value_hash(old_value)
        and row.get("new_value_hash") == _value_hash(new_value)
        and _version_key(str(row.get("expires_version") or "")) >= _version_key("14.4.0")
        for row in rows
    )


def registry_value_hash(value: object) -> str:
    return _value_hash(value)


def _value_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _version_key(value: str) -> tuple[int, ...]:
    parts = []
    for token in value.lstrip("v").split("."):
        try:
            parts.append(int(token))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_numeric(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_minimum_or_schema(key: str) -> bool:
    return key.endswith(("_minimum", "_minimum_percent", "_schema_version")) or key in {
        "explicit_any_collector_schema_version",
        "required_total_line_reduction",
    }


def _is_historical_or_hash(key: str) -> bool:
    return key.startswith(("previous_", "corrected_", "from_", "to_")) or key.endswith("_hash")
