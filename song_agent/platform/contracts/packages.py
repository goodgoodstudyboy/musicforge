from __future__ import annotations

import hashlib
import json
import zipfile
from copy import deepcopy
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Callable, Literal, TypedDict, overload

from song_agent.platform.contracts.coercion import as_document as _as_document
from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.resource_access import PackagedResource, read_packaged_text

NestedZipPolicy = Literal["deny", "allowlisted"]


class SemanticVerificationContext(TypedDict):
    archive: zipfile.ZipFile
    manifest: JsonDocument
    names: list[str]
    summary: JsonDocument
    strict: bool


SemanticVerifier = Callable[[SemanticVerificationContext], list[JsonDocument]]
RUNTIME_PACKAGE_WRITER_POLICY_TYPE = "musicforge_v144_runtime_package_writer_policy"
RUNTIME_PACKAGE_WRITER_POLICY_RESOURCE = "runtime-package-writer-policy.json"
RUNTIME_PACKAGE_WRITER_POLICY_SCHEMA_VERSION = 2
RUNTIME_PACKAGE_REGISTRY_PROJECTION_RESOURCE = "runtime-package-registry.json"
APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH = "28a3d0f80ff9c697b8d1dbd0aa20bd76f9f29efc51d8e4ea0b17429bbb6d6127"
APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH = "a15ba1009cda23f5cfa011c57d5c389b527bdb0517dcda10a2a02c4808d40880"
PACKAGE_WRITER_GUARD_SYMBOL = "song_agent.platform.contracts.packages.require_registered_package_type"
PACKAGE_WRITER_GUARD_ALIAS = "_require_registered_package_type"
PACKAGE_WRITER_ATTACK_CORPUS = "song_agent.platform.verification.attack_corpus._write_package"
MAX_PRODUCTION_WRITER_TYPES = 32
_PACKAGE_GUARD_BINDING = {
    "alias": PACKAGE_WRITER_GUARD_ALIAS,
    "module": "song_agent.platform.contracts.packages",
    "name": "require_registered_package_type",
}
PACKAGE_WRITER_GUARD_BINDING_HASH = hashlib.sha256(
    json.dumps(_PACKAGE_GUARD_BINDING, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class _RuntimePackageWriterRule:
    nullable: bool
    package_types: frozenset[str]


@dataclass(frozen=True)
class PackageSpec:
    package_type: str
    verification_package_type: str
    check_prefix: str
    required_entries: frozenset[str] = field(default_factory=frozenset)
    optional_entries: frozenset[str] = field(default_factory=frozenset)
    co_required_entry_groups: tuple[frozenset[str], ...] = ()
    allowed_entry_patterns: tuple[str, ...] = ()
    nested_zip_policy: NestedZipPolicy = "deny"
    allowed_nested_entries: frozenset[str] = field(default_factory=frozenset)
    allowed_nested_patterns: tuple[str, ...] = ()
    manifest_entry: str = "manifest.json"
    max_zip_size_mb: int = 128
    max_uncompressed_size_mb: int = 512
    max_entry_count: int = 1000
    redaction_suffixes: tuple[str, ...] = (".json", ".jsonl", ".txt", ".md", ".html")
    semantic_verifier: SemanticVerifier | None = None
    schema_version: int = 1

    @property
    def allowed_entries(self) -> frozenset[str]:
        return self.required_entries | self.optional_entries

    def requiring(self, entries: set[str] | frozenset[str]) -> "PackageSpec":
        required = self.required_entries | frozenset(entries)
        return replace(self, required_entries=required, optional_entries=self.optional_entries - required)


def build_runtime_package_writer_policy(registry: dict[str, object]) -> dict[str, object]:
    writer_contracts = _object_rows(registry.get("writer_contracts"))
    referenced_type_sets = {str(row.get("allowed_type_set_id") or "") for row in writer_contracts}
    document: dict[str, object] = {
        "schema_version": RUNTIME_PACKAGE_WRITER_POLICY_SCHEMA_VERSION,
        "package_type": RUNTIME_PACKAGE_WRITER_POLICY_TYPE,
        "registry_integrity_hash": str(registry.get("integrity_hash") or ""),
        "package_type_sets": [
            {
                "type_set_id": row.get("type_set_id"),
                "purpose": row.get("purpose"),
                "writer_id": row.get("writer_id"),
                "policy": row.get("policy"),
                "package_types": _copy_list(row.get("package_types")),
                "package_type_kinds": _copy_object(row.get("package_type_kinds")),
                "allowed_package_kinds": _copy_list(row.get("allowed_package_kinds")),
            }
            for row in _object_rows(registry.get("package_type_sets"))
            if str(row.get("type_set_id") or "") in referenced_type_sets
        ],
        "writer_contracts": [
            {
                "writer_id": row.get("writer_id"),
                "allowed_type_set_id": row.get("allowed_type_set_id"),
                "allowed_package_kinds": _copy_list(row.get("allowed_package_kinds")),
                "contract_scope": row.get("contract_scope"),
                "nullable": row.get("nullable"),
                "guard_symbol": row.get("guard_symbol"),
                "guard_alias": row.get("guard_alias"),
                "guard_binding_hash": row.get("guard_binding_hash"),
            }
            for row in writer_contracts
        ],
    }
    document["integrity_hash"] = _document_hash(document)
    return document


def load_runtime_package_registry_projection() -> dict[str, object]:
    return deepcopy(_load_validated_runtime_package_registry_projection())


def load_runtime_package_writer_policy() -> dict[str, object]:
    document = _load_resource_object(RUNTIME_PACKAGE_WRITER_POLICY_RESOURCE, "Runtime package writer policy")
    registry = _load_validated_runtime_package_registry_projection()
    if validate_runtime_package_writer_policy(document, registry):
        raise RuntimeError("Runtime package writer policy failed integrity or schema validation.")
    return deepcopy(document)


@lru_cache(maxsize=1)
def _runtime_package_writer_index() -> tuple[tuple[str, _RuntimePackageWriterRule], ...]:
    registry = _load_validated_runtime_package_registry_projection()
    policy = _load_resource_object(RUNTIME_PACKAGE_WRITER_POLICY_RESOURCE, "Runtime package writer policy")
    if validate_runtime_package_writer_policy(policy, registry):
        raise RuntimeError("Runtime package writer policy failed integrity or schema validation.")
    type_sets = _object_rows(policy.get("package_type_sets"))
    contracts = _object_rows(policy.get("writer_contracts"))
    index: list[tuple[str, _RuntimePackageWriterRule]] = []
    for contract in contracts:
        writer_id = str(contract.get("writer_id") or "")
        type_set_id = str(contract.get("allowed_type_set_id") or "")
        type_set = next(
            (row for row in type_sets if row.get("type_set_id") == type_set_id),
            None,
        )
        values = type_set.get("package_types") if type_set else None
        nullable = contract.get("nullable")
        if (
            not writer_id
            or any(existing == writer_id for existing, _rule in index)
            or not isinstance(nullable, bool)
            or not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) or not value for value in values)
        ):
            raise RuntimeError("Runtime package writer index contains an invalid contract.")
        index.append((writer_id, _RuntimePackageWriterRule(nullable, frozenset(values))))
    if len(index) != len(contracts):
        raise RuntimeError("Runtime package writer index is incomplete.")
    return tuple(index)


def validate_runtime_package_registry_projection(document: object) -> list[str]:
    valid = (
        isinstance(document, dict)
        and document.get("schema_version") == 1
        and document.get("registry_schema_version") == 7
        and document.get("registry_integrity_hash") == APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH
        and document.get("integrity_hash") == APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH
        and document.get("integrity_hash") == _document_hash(document)
        and isinstance(document.get("formal_type_kinds"), dict)
        and isinstance(document.get("compatibility_type_contracts"), dict)
        and isinstance(document.get("package_type_sets"), list)
        and isinstance(document.get("writer_contracts"), list)
    )
    return [] if valid else ["v144_package_registry_projection_integrity"]


def validate_runtime_package_writer_policy(
    document: object,
    registry_projection: object | None = None,
) -> list[str]:
    if not isinstance(document, dict):
        return ["v144_package_writer_policy_document"]
    if registry_projection is None:
        try:
            registry_projection = _load_validated_runtime_package_registry_projection()
        except RuntimeError:
            registry_projection = {}
    projection = _as_document(registry_projection)
    blockers = validate_runtime_package_registry_projection(projection)
    projection_rows = _object_rows(projection.get("package_type_sets"))
    projected_sets = {str(row.get("type_set_id") or ""): row for row in projection_rows}
    checks = {
        "v144_package_writer_policy_integrity": document.get("package_type") != RUNTIME_PACKAGE_WRITER_POLICY_TYPE
        or document.get("schema_version") != RUNTIME_PACKAGE_WRITER_POLICY_SCHEMA_VERSION
        or document.get("integrity_hash") != _document_hash(document),
        "v144_package_writer_policy_registry_binding": document.get("registry_integrity_hash") != projection.get("registry_integrity_hash"),
        "v144_package_writer_policy_type_sets": document.get("package_type_sets") != projection_rows
        or len(projected_sets) != len(projection_rows),
        "v144_package_writer_policy_writers": document.get("writer_contracts") != projection.get("writer_contracts"),
    }
    blockers.extend(check_id for check_id, failed in checks.items() if failed)
    return sorted(set(blockers))


@overload
def require_registered_package_type(value: str, *, writer_id: str) -> str: ...


@overload
def require_registered_package_type(value: None, *, writer_id: str) -> None: ...


@overload
def require_registered_package_type(value: object, *, writer_id: str) -> str | None: ...


def require_registered_package_type(value: object, *, writer_id: str) -> str | None:
    rule = next(
        (candidate for current_id, candidate in _runtime_package_writer_index() if current_id == writer_id),
        None,
    )
    if rule is None:
        raise ValueError(f"Package writer is not registered: {writer_id}")
    if value is None:
        if rule.nullable:
            return None
        raise ValueError(f"Package type is required for writer {writer_id}.")
    package_type = value if isinstance(value, str) else ""
    if not package_type or package_type not in rule.package_types:
        raise ValueError(f"Package type is not authorized for writer {writer_id}: {package_type or '<invalid>'}")
    return package_type


def _document_hash(document: dict[str, object]) -> str:
    payload = sorted((key, value) for key, value in document.items() if key != "integrity_hash")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_resource_object(resource_name: str, label: str) -> dict[str, object]:
    resources_by_name = {
        RUNTIME_PACKAGE_WRITER_POLICY_RESOURCE: PackagedResource.PACKAGE_WRITER_POLICY,
        RUNTIME_PACKAGE_REGISTRY_PROJECTION_RESOURCE: PackagedResource.PACKAGE_REGISTRY,
    }
    try:
        resource = resources_by_name[resource_name]
        payload = read_packaged_text(resource)
        document = json.loads(payload)
    except (FileNotFoundError, KeyError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"{label} is unavailable.") from exc
    if not isinstance(document, dict):
        raise RuntimeError(f"{label} must be a JSON object.")
    return document


def _load_validated_runtime_package_registry_projection() -> dict[str, object]:
    document = _load_resource_object(
        RUNTIME_PACKAGE_REGISTRY_PROJECTION_RESOURCE,
        "Runtime package registry projection",
    )
    if validate_runtime_package_registry_projection(document):
        raise RuntimeError("Runtime package registry projection failed integrity or schema validation.")
    return document


def _object_rows(value: object) -> list[dict[str, object]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _copy_list(value: object) -> list[object]:
    return value.copy() if isinstance(value, list) else []


def _copy_object(value: object) -> dict[str, object]:
    return value.copy() if isinstance(value, dict) else {}


def _writer_type_set_id(writer_id: str) -> str:
    return f"writer.{hashlib.sha256(writer_id.encode('utf-8')).hexdigest()[:16]}"
