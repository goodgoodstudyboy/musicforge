from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.platform.verification.hashing import integrity_hash
from song_agent.release_check.matrix import all_check_definitions
from song_agent.release_check.v14_wave0_catalog_model import (
    BOUNDED_CONTEXTS,
    attach_capability,
    hash_json,
    module_constants,
    resolve_string,
)
from song_agent.release_check.v14_wave0_package_inventory import (
    named_assignment,
    package_writer_contract_observations,
    unregistered_package_literal_blockers,
)
from song_agent.release_check.v14_wave0_package_scan import (
    package_observations as _package_observations,
)
from song_agent.release_check.v14_wave0_registry import (
    capability_surface_owner,
    load_wave0_registries,
)
from song_agent.release_check.v14_wave0_surfaces import (
    collect_api_routes,
    collect_cli_commands,
    collect_cli_registrations,
    collect_panels,
)


CATALOG_PACKAGE_TYPE = "musicforge_v144_capability_catalog"

def _module_assignments(tree: ast.AST) -> list[tuple[str, ast.expr, int]]:
    return [row for node in ast.iter_child_nodes(tree) if (row := named_assignment(node)) is not None]

def module_schema_rows(tree: ast.AST, source: str, module: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, value, line in _module_assignments(tree):
        if name.endswith("SCHEMA_VERSION") and isinstance(value, ast.Constant) and isinstance(value.value, (str, int)):
            rows.append({"schema_id": f"{source}:{name}", "owner": module, "source": source, "line": line, "version": value.value})
    return rows

def module_package_constants(tree: ast.AST, source: str, module: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    constants = module_constants(tree)
    for name, value, line in _module_assignments(tree):
        resolved = resolve_string(value, constants)
        if "PACKAGE_TYPE" in name and resolved:
            rows.append({"package_id": f"{module}:{name}", "owner": module, "source": source, "line": line, "constant": name, "package_type": resolved})
    return rows

def build_wave0_catalog(
    root: Path,
    *,
    registries: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    registries = registries or load_wave0_registries(root)
    capability_registry = registries["capabilities"]
    capability_rows = cast(list[dict[str, object]], capability_registry["capabilities"])
    capability_context = {str(row["capability_id"]): str(row["bounded_context"]) for row in capability_rows}
    owners = capability_surface_owner(capability_registry)
    active, trees, source_texts = _active_sources(root)
    state_entries = {str(row["store_id"]): row for row in cast(list[dict[str, object]], registries["state"]["entries"])}
    stores = _store_inventory(active, trees, state_entries, owners["stores"], capability_context)
    package_groups = _package_inventory(
        active,
        trees,
        source_texts,
        registries["packages"],
        owners,
        capability_context,
    )
    package_writer_contracts = package_writer_contract_observations(
        trees,
        {module: str(active[module]["path"]) for module in active},
        source_texts,
    )
    package_literal_blockers = unregistered_package_literal_blockers(trees, registries["packages"])
    inventory: dict[str, object] = {
        "stores": stores,
        "cli_commands": attach_capability(
            collect_cli_commands(),
            inventory_name="cli_commands",
            owner=owners["cli_commands"],
            capability_context=capability_context,
        ),
        "cli_registration_points": attach_capability(
            collect_cli_registrations(active, trees),
            inventory_name="cli_registration_points",
            owner=owners["cli_registration_points"],
            capability_context=capability_context,
        ),
        "api_routes": attach_capability(
            collect_api_routes(),
            inventory_name="api_routes",
            owner=owners["api_routes"],
            capability_context=capability_context,
        ),
        **package_groups,
        "studio_panels": attach_capability(
            collect_panels(root),
            inventory_name="studio_panels",
            owner=owners["studio_panels"],
            capability_context=capability_context,
        ),
        "release_checks": _release_check_inventory(owners["release_checks"], capability_context),
    }
    counts = {key: len(cast(list[object], value)) for key, value in inventory.items()}
    counts["state_authorities"] = sum(row.get("role") == "authority" for row in stores)
    counts["state_adapters"] = sum(row.get("role") == "adapter" for row in stores)
    document: dict[str, object] = {
        "schema_version": 4,
        "package_type": CATALOG_PACKAGE_TYPE,
        "baseline_version": "14.3.5",
        "baseline_sha": "131258b4bcf9786bc155e3327a64836bf5aca037",
        "status": "frozen",
        "registry_hashes": {key: value["integrity_hash"] for key, value in registries.items()},
        "bounded_contexts": list(BOUNDED_CONTEXTS),
        "summary": {"capability_count": len(capability_rows), "package_writer_contracts": len(package_writer_contracts), **counts},
        "capabilities": capability_rows,
        "package_writer_contracts": package_writer_contracts,
        "package_literal_blockers": package_literal_blockers,
        "inventory": inventory,
    }
    document["inventory_hash"] = hash_json(inventory)
    document["integrity_hash"] = integrity_hash(document)
    return document

def _active_sources(
    root: Path,
) -> tuple[dict[str, dict[str, object]], dict[str, ast.AST], dict[str, str]]:
    snapshot = cast(dict[str, object], build_architecture_snapshot(root))
    active = {
        str(row["module"]): row
        for row in cast(list[dict[str, object]], snapshot["modules"])
        if str(row.get("layer")) not in {"compatibility", "release_check"}
    }
    source_texts = {
        module: (root / str(row["path"])).read_text(encoding="utf-8")
        for module, row in active.items()
    }
    trees: dict[str, ast.AST] = {
        module: ast.parse(source_texts[module], filename=str(row["path"]))
        for module, row in active.items()
    }
    return active, trees, source_texts

def _store_inventory(
    active: dict[str, dict[str, object]],
    trees: dict[str, ast.AST],
    state_entries: dict[str, dict[str, object]],
    owner: dict[str, str],
    capability_context: dict[str, str],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for module in sorted(active):
        source = str(active[module]["path"])
        for node in ast.walk(trees[module]):
            if not isinstance(node, ast.ClassDef) or not node.name.endswith("Store"):
                continue
            store_id = f"{module}.{node.name}"
            declared = state_entries.get(store_id, {})
            capability_id = owner.get(store_id, "")
            rows.append(
                {
                    **declared,
                    "store_id": store_id,
                    "capability_id": capability_id,
                    "bounded_context": capability_context.get(capability_id, ""),
                    "observed_source": source,
                    "observed_line": node.lineno,
                }
            )
    return sorted(rows, key=lambda row: str(row["store_id"]))

def _package_inventory(
    active: dict[str, dict[str, object]],
    trees: dict[str, ast.AST],
    source_texts: dict[str, str],
    registry: dict[str, object],
    owners: dict[str, dict[str, str]],
    capability_context: dict[str, str],
) -> dict[str, object]:
    registry_types = {str(row["package_type"]): row for row in cast(list[dict[str, object]], registry["package_types"])}
    registry_sites = {str(row["site_id"]): row for row in cast(list[dict[str, object]], registry["dynamic_sites"])}
    packages: list[dict[str, object]] = []
    verifiers: list[dict[str, object]] = []
    schemas: list[dict[str, object]] = []
    observations: list[dict[str, object]] = []
    for module in sorted(active):
        source = str(active[module]["path"])
        tree = trees[module]
        observations.extend(_package_observations(tree, source, source_texts[module]))
        packages.extend(module_package_constants(tree, source, module))
        schemas.extend(module_schema_rows(tree, source, module))
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("verify_"):
                verifiers.append(
                    {
                        "verifier_id": f"{module}.{node.name}",
                        "owner": module,
                        "source": source,
                        "line": node.lineno,
                    }
                )
    observations = _normalize_dynamic_site_ids(observations)
    grouped: dict[str, dict[str, object]] = {}
    dynamic: list[dict[str, object]] = []
    for observation in observations:
        package_type_value = str(observation.get("package_type") or "")
        if package_type_value:
            item = grouped.setdefault(package_type_value, {"sources": [], "schema_versions": []})
            cast(list[str], item["sources"]).append(str(observation["source_id"]))
            if observation.get("schema_version") not in (None, ""):
                cast(list[object], item["schema_versions"]).append(observation["schema_version"])
        else:
            site_id = str(observation["source_id"])
            declaration = registry_sites.get(site_id, {})
            dynamic.append(
                {
                    "site_id": site_id,
                    "expression": observation["expression"],
                    "expression_source_hash": observation["expression_source_hash"],
                    "scope_source_hash": observation["scope_source_hash"],
                    "line": observation["line"],
                    "column": observation["column"],
                    "end_line": observation["end_line"],
                    "end_column": observation["end_column"],
                    "candidate_kinds": observation["candidate_kinds"],
                    "policy": declaration.get("policy") or "",
                }
            )
    package_types = [
        {
            "package_type": value,
            "kind": registry_types.get(value, {}).get("kind") or "",
            "visibility": registry_types.get(value, {}).get("visibility") or "",
            "sources": sorted(set(cast(list[str], item["sources"]))),
            "schema_versions": sorted(set(cast(list[object], item["schema_versions"])), key=str),
            "schema_declaration": registry_types.get(value, {}).get("schema_declaration") or {},
        }
        for value, item in sorted(grouped.items())
    ]
    return {
        "packages": attach_capability(
            packages,
            inventory_name="packages",
            owner=owners["packages"],
            capability_context=capability_context,
        ),
        "package_types": attach_capability(
            package_types,
            inventory_name="package_types",
            owner=owners["package_types"],
            capability_context=capability_context,
        ),
        "package_sites": attach_capability(
            dynamic,
            inventory_name="package_sites",
            owner=owners["package_sites"],
            capability_context=capability_context,
        ),
        "verifiers": attach_capability(
            verifiers,
            inventory_name="verifiers",
            owner=owners["verifiers"],
            capability_context=capability_context,
        ),
        "schemas": attach_capability(
            schemas,
            inventory_name="schemas",
            owner=owners["schemas"],
            capability_context=capability_context,
        ),
    }


def _normalize_dynamic_site_ids(observations: list[dict[str, object]]) -> list[dict[str, object]]:
    static = [row for row in observations if row.get("package_type")]
    dynamic: dict[str, dict[str, object]] = {}
    for row in observations:
        if row.get("package_type"):
            continue
        source_id = str(row["source_id"])
        normalized = {
            **row,
            "candidate_kinds": [str(row.get("candidate_kind") or "")],
        }
        normalized.pop("candidate_kind", None)
        previous = dynamic.get(source_id)
        if previous is None:
            dynamic[source_id] = normalized
            continue
        previous_kinds = set(cast(list[str], previous.get("candidate_kinds") or []))
        current_kinds = set(cast(list[str], normalized.get("candidate_kinds") or []))
        previous_without_kinds = {key: value for key, value in previous.items() if key != "candidate_kinds"}
        current_without_kinds = {key: value for key, value in normalized.items() if key != "candidate_kinds"}
        if previous_without_kinds != current_without_kinds:
            raise ValueError(f"Package discriminator source span is ambiguous: {source_id}")
        previous["candidate_kinds"] = sorted(previous_kinds | current_kinds)
    return [*static, *(dynamic[key] for key in sorted(dynamic))]

def _release_check_inventory(owner: dict[str, str], capability_context: dict[str, str]) -> list[dict[str, object]]:
    rows = [
        {
            "release_check_id": definition.check_id,
            "owner": "song_agent.release_check",
            "group": definition.group,
            "version": definition.version or "",
            "risk": definition.risk,
            "profiles": sorted(definition.profiles),
        }
        for definition in all_check_definitions()
    ]
    return attach_capability(
        rows,
        inventory_name="release_checks",
        owner=owner,
        capability_context=capability_context,
    )
