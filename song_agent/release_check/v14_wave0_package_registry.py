from __future__ import annotations

import hashlib
from typing import cast

from song_agent.platform.contracts.packages import (
    MAX_PRODUCTION_WRITER_TYPES,
    PACKAGE_WRITER_ATTACK_CORPUS,
    PACKAGE_WRITER_GUARD_ALIAS,
    PACKAGE_WRITER_GUARD_BINDING_HASH,
    PACKAGE_WRITER_GUARD_SYMBOL,
)


PACKAGE_KINDS = {"top_level_package", "report", "sidecar", "event", "document"}
PACKAGE_VALUE_KINDS = PACKAGE_KINDS | {"legacy_label", "attack_corpus"}
def validate_package_registry(
    registry: dict[str, object],
    capability_ids: set[str],
    surface_owner: dict[str, dict[str, str]],
    blockers: list[str],
) -> None:
    groups = (
        ("package_types", "package_type", "package_types"),
        ("dynamic_sites", "site_id", "package_sites"),
        ("schemas", "schema_id", "schemas"),
    )
    for document_key, identity_key, surface_key in groups:
        rows = cast(list[dict[str, object]], registry.get(document_key) or [])
        _unique_ids(rows, identity_key, document_key, blockers)
        for row in rows:
            identity = str(row.get(identity_key) or "")
            capability_id = str(row.get("capability_id") or "")
            if capability_id not in capability_ids:
                blockers.append(f"v144_wave0_package_capability:{document_key}:{identity}")
            if surface_owner[surface_key].get(identity) != capability_id:
                blockers.append(f"v144_wave0_package_mapping:{document_key}:{identity}")
            if document_key == "package_types":
                _check_package_type(row, identity, blockers)
            elif document_key == "dynamic_sites":
                _check_dynamic_site(row, identity, blockers)
            elif row.get("version") in (None, "") or not str(row.get("source") or ""):
                blockers.append(f"v144_wave0_schema_declaration:{identity}")
    _check_type_sets_and_writers(registry, capability_ids, blockers)


def _check_package_type(row: dict[str, object], identity: str, blockers: list[str]) -> None:
    if row.get("kind") not in PACKAGE_KINDS or not cast(list[object], row.get("sources") or []):
        blockers.append(f"v144_wave0_package_declaration:{identity}")
    schema = row.get("schema_declaration")
    if (
        not isinstance(schema, dict)
        or schema.get("status") not in {"declared", "not_applicable"}
        or not str(schema.get("reason") or "")
        or not isinstance(row.get("schema_versions"), list)
    ):
        blockers.append(f"v144_wave0_package_schema:{identity}")


def _check_dynamic_site(row: dict[str, object], identity: str, blockers: list[str]) -> None:
    if (
        row.get("policy") != "registered_legacy_raw_write"
        or not str(row.get("expression") or "")
        or not isinstance(row.get("candidate_kinds"), list)
        or not cast(list[object], row.get("candidate_kinds") or [])
        or len(cast(list[object], row.get("candidate_kinds") or []))
        != len(set(cast(list[object], row.get("candidate_kinds") or [])))
        or any(not isinstance(kind, str) or not kind for kind in cast(list[object], row.get("candidate_kinds") or []))
        or cast(list[object], row.get("candidate_kinds") or [])
        != sorted(cast(list[object], row.get("candidate_kinds") or []), key=str)
        or len(str(row.get("expression_source_hash") or "")) != 64
        or len(str(row.get("scope_source_hash") or "")) != 64
        or not _valid_source_span(row)
    ):
        blockers.append(f"v144_wave0_package_dynamic:{identity}")


def _check_type_sets_and_writers(
    registry: dict[str, object],
    capability_ids: set[str],
    blockers: list[str],
) -> None:
    type_sets = cast(list[dict[str, object]], registry.get("package_type_sets") or [])
    type_set_ids = _unique_ids(type_sets, "type_set_id", "package_type_set", blockers)
    registered_type_kinds = {
        str(row.get("package_type") or ""): str(row.get("kind") or "")
        for row in cast(list[dict[str, object]], registry.get("package_types") or [])
    }
    allowed_types: set[str] = set()
    runtime_sets: dict[str, dict[str, object]] = {}
    for row in type_sets:
        type_set_id = str(row.get("type_set_id") or "")
        values = row.get("package_types")
        if not _valid_type_set(row, values):
            blockers.append(f"v144_wave0_package_type_set:{type_set_id}")
            continue
        values = cast(list[str], values)
        allowed_types.update(values)
        if row.get("purpose") == "runtime_writer":
            _check_runtime_type_set(row, values, registered_type_kinds, blockers)
            runtime_sets[type_set_id] = row
    if not set(registered_type_kinds) <= allowed_types:
        blockers.append("v144_wave0_package_type_set_incomplete")
    _check_writer_contracts(registry, capability_ids, type_set_ids, runtime_sets, blockers)


def _valid_type_set(row: dict[str, object], values: object) -> bool:
    return (
        row.get("policy") == "frozen_exact"
        and row.get("purpose") in {"runtime_writer", "source_literal"}
        and isinstance(values, list)
        and bool(values)
        and len(values) == len(set(values))
        and all(isinstance(value, str) and value for value in values)
    )


def _check_runtime_type_set(
    row: dict[str, object],
    values: list[str],
    registered_type_kinds: dict[str, str],
    blockers: list[str],
) -> None:
    type_set_id = str(row.get("type_set_id") or "")
    writer_id = str(row.get("writer_id") or "")
    value_kinds = row.get("package_type_kinds")
    allowed_kinds = row.get("allowed_package_kinds")
    if (
        not writer_id
        or type_set_id != _writer_type_set_id(writer_id)
        or not isinstance(value_kinds, dict)
        or set(value_kinds) != set(values)
        or not isinstance(allowed_kinds, list)
        or not allowed_kinds
        or len(allowed_kinds) != len(set(allowed_kinds))
        or not set(allowed_kinds) <= PACKAGE_VALUE_KINDS
        or any(value_kinds.get(value) not in allowed_kinds for value in values)
    ):
        blockers.append(f"v144_wave0_package_type_set_writer:{type_set_id}")
    for value in values:
        formal_kind = registered_type_kinds.get(value)
        if formal_kind and isinstance(value_kinds, dict) and value_kinds.get(value) != formal_kind:
            blockers.append(f"v144_wave0_package_type_set_kind:{type_set_id}:{value}")
    restricted = {
        value
        for value in values
        if value == "forged_package_type" or value == "musicforge_" or value.startswith("musicforge_test_")
    }
    if restricted and writer_id != PACKAGE_WRITER_ATTACK_CORPUS:
        blockers.append(f"v144_wave0_package_type_set_test_scope:{type_set_id}")
    if isinstance(allowed_kinds, list) and "attack_corpus" in allowed_kinds and writer_id != PACKAGE_WRITER_ATTACK_CORPUS:
        blockers.append(f"v144_wave0_package_type_set_attack_scope:{type_set_id}")
    if writer_id != PACKAGE_WRITER_ATTACK_CORPUS and len(values) > MAX_PRODUCTION_WRITER_TYPES:
        blockers.append(f"v144_wave0_package_type_set_catch_all:{type_set_id}")


def _check_writer_contracts(
    registry: dict[str, object],
    capability_ids: set[str],
    type_set_ids: set[str],
    runtime_sets: dict[str, dict[str, object]],
    blockers: list[str],
) -> None:
    writer_rows = cast(list[dict[str, object]], registry.get("writer_contracts") or [])
    _unique_ids(writer_rows, "writer_id", "package_writer_contract", blockers)
    referenced_sets: list[str] = []
    for row in writer_rows:
        writer_id = str(row.get("writer_id") or "")
        allowed_type_set_id = str(row.get("allowed_type_set_id") or "")
        referenced_sets.append(allowed_type_set_id)
        type_set = runtime_sets.get(allowed_type_set_id)
        if str(row.get("capability_id") or "") not in capability_ids:
            blockers.append(f"v144_wave0_package_writer_capability:{writer_id}")
        if not _valid_writer_contract(row, writer_id, allowed_type_set_id, type_set_ids, type_set):
            blockers.append(f"v144_wave0_package_writer_contract:{writer_id}")
    if len(referenced_sets) != len(set(referenced_sets)) or set(referenced_sets) != set(runtime_sets):
        blockers.append("v144_wave0_package_writer_type_set_ownership")


def _valid_writer_contract(
    row: dict[str, object],
    writer_id: str,
    allowed_type_set_id: str,
    type_set_ids: set[str],
    type_set: dict[str, object] | None,
) -> bool:
    line = row.get("line")
    write_lines = row.get("write_lines")
    value_parameters = row.get("value_parameters")
    return bool(
        row.get("writer_kind") == "legacy_parameterized"
        and row.get("call_policy") == "runtime_guarded"
        and row.get("guard_symbol") == PACKAGE_WRITER_GUARD_SYMBOL
        and row.get("guard_alias") == PACKAGE_WRITER_GUARD_ALIAS
        and row.get("guard_binding_hash") == PACKAGE_WRITER_GUARD_BINDING_HASH
        and type_set is not None
        and row.get("allowed_package_kinds") == type_set.get("allowed_package_kinds")
        and row.get("contract_scope") in {"production", "attack_corpus"}
        and (row.get("contract_scope") == "attack_corpus") == (writer_id == PACKAGE_WRITER_ATTACK_CORPUS)
        and isinstance(row.get("nullable"), bool)
        and allowed_type_set_id in type_set_ids
        and type_set.get("writer_id") == writer_id
        and str(row.get("source") or "")
        and isinstance(line, int)
        and line >= 1
        and isinstance(write_lines, list)
        and write_lines
        and all(isinstance(write_line, int) and write_line > 0 for write_line in write_lines)
        and isinstance(value_parameters, list)
        and value_parameters
        and len(value_parameters) == len(set(value_parameters))
        and len(str(row.get("expression_source_hash") or "")) == 64
        and len(str(row.get("module_source_hash") or "")) == 64
    )


def _valid_source_span(row: dict[str, object]) -> bool:
    values = [row.get(field) for field in ("line", "column", "end_line", "end_column")]
    if any(not isinstance(value, int) for value in values):
        return False
    line, column, end_line, end_column = cast(list[int], values)
    return line >= 1 and column >= 0 and end_line >= line and end_column >= 0


def _writer_type_set_id(writer_id: str) -> str:
    return f"writer.{hashlib.sha256(writer_id.encode('utf-8')).hexdigest()[:16]}"


def _unique_ids(rows: list[dict[str, object]], key: str, label: str, blockers: list[str]) -> set[str]:
    values = [str(row.get(key) or "") for row in rows]
    if "" in values or len(values) != len(set(values)):
        blockers.append(f"v144_wave0_registry_ids:{label}")
    return set(values) - {""}
