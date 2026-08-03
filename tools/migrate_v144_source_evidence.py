from __future__ import annotations

import argparse
import ast
import copy
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import cast

from song_agent.platform.contracts.packages import (
    APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH,
    APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH,
    build_runtime_package_writer_policy,
)
from song_agent.platform.persistence.file_artifacts import build_runtime_state_authority_policy
from song_agent.platform.persistence.repository import namespace_identity_hash
from song_agent.platform.verification.hashing import integrity_hash
from song_agent.release_check.v14_wave0 import build_wave0_baseline, evaluate_wave0
from song_agent.release_check.v14_wave0_inventory import (
    _active_sources,
    _normalize_dynamic_site_ids,
    _package_observations,
    build_wave0_catalog,
)
from song_agent.release_check.v14_wave0_package_inventory import package_writer_contract_observations
from song_agent.release_check.v14_wave0_registry import validate_wave0_registries
from song_agent.release_check.v14_wave0_state_registry import namespace_path_evidence
try:
    from tools.update_v144_wave0_catalog import (
        _encoded,
        _render_current_architecture_summary,
        build_runtime_package_registry_projection,
    )
except ModuleNotFoundError:  # Direct execution places tools/, not the repository root, on sys.path.
    from update_v144_wave0_catalog import (
        _encoded,
        _render_current_architecture_summary,
        build_runtime_package_registry_projection,
    )


OLD_HASHES = {
    "capabilities": "138acd5d01c7e3d8ceee6da246f9eb93bf0382185964cf58217822e9db25ce17",
    "state": "e08459a5939b824511bc834d4c3704cdcc1b90d8cecea5602fc787fc07def745",
    "packages": "0ad599a70b56d7e8eeeba160a8790a217dcd9192f979c225f5888ae5a4cfccfc",
    "baseline": "d83b9c5638e2f445fcbaf7dc9b667bf8c01618b66a90d9cc04a4b6f614d544e0",
    "waivers": "dd7f4d88165d58ea3ff7e3b7d2f144b561fbb92d66bc1c2f1dc3c30ced455aba",
}
TARGET_SCHEMAS = {"capabilities": 1, "state": 4, "packages": 7, "baseline": 5, "waivers": 2}
TARGET_HASHES = {
    "capability_registry_hash": "2ae5c43eb8c7ad6d99600737132796700807e9e571d87b0295b8c60bd97b2d29",
    "state_registry_hash": "8d2c87d762d912e7effcebe2265898c2112d2d1b780105f2f94960e6079e5b0b",
    "package_registry_hash": "d0dba235e083e70b4f94a92551b9882234471f14d827ae815b582507ed522d20",
    "package_registry_projection_hash": "a6f8805e2dba2c74ef1944c6ce76c5ed58c2db10109270313d193821b5e81a0b",
    "catalog_hash": "9f8340ebd2c80c32287e3dbe0ab18ad094785eeebb6df242c56a8b43b7086ec5",
    "baseline_hash": "6899430a97dabce20158554d9cefaeb501d83173fdd88c0f1143590299c34787",
    "package_site_count": 2687,
}
PATHS = {
    "capabilities": "architecture-v14.4-capability-registry.json",
    "state": "architecture-v14.4-state-authority-registry.json",
    "packages": "architecture-v14.4-package-schema-registry.json",
    "baseline": "architecture-v14.4-wave0-baseline.json",
    "waivers": "architecture-v14.4-wave0-waivers.json",
}
_OLD_SITE = re.compile(r"^(.*\.py):(.*)#\d+$")
_CAPABILITY_RANK = {
    "authority": 4,
    "projection": 4,
    "evidence_package": 4,
    "workflow": 2,
    "compatibility_adapter": 1,
}


def migrate(root: Path, *, apply: bool) -> int:
    old = {key: _read(root / path) for key, path in PATHS.items()}
    if _is_target(old):
        print("v14.4 source evidence migration is already applied")
        return 0
    _require_exact_old_documents(old)
    registries = _target_registries(root, old)
    provisional_catalog = build_wave0_catalog(root, registries=registries)
    provisional_baseline = build_wave0_baseline(root, provisional_catalog, registries=registries)
    registries["state"] = _rebind_state_exceptions(
        registries["state"], str(provisional_baseline["integrity_hash"])
    )
    catalog = build_wave0_catalog(root, registries=registries)
    baseline = build_wave0_baseline(root, catalog, registries=registries)
    if baseline["integrity_hash"] != provisional_baseline["integrity_hash"]:
        raise ValueError("State exception rebinding changed the Wave 0 baseline hash.")
    blockers = validate_wave0_registries(
        registries,
        root=root,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
    )
    if blockers:
        raise ValueError("Migrated registries are invalid: " + ", ".join(blockers))
    projection = build_runtime_package_registry_projection(
        registries["packages"], approved_registry_hash=None
    )
    plan = {
        "capability_registry_hash": registries["capabilities"]["integrity_hash"],
        "state_registry_hash": registries["state"]["integrity_hash"],
        "package_registry_hash": registries["packages"]["integrity_hash"],
        "package_registry_projection_hash": projection["integrity_hash"],
        "catalog_hash": catalog["integrity_hash"],
        "baseline_hash": baseline["integrity_hash"],
        "package_site_count": len(cast(list[object], registries["packages"]["dynamic_sites"])),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    if plan != TARGET_HASHES:
        raise ValueError("Wave 0 source evidence migration target does not match the approved plan.")
    if not apply:
        return 0
    if (
        plan["package_registry_hash"] != APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH
        or plan["package_registry_projection_hash"] != APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH
    ):
        raise ValueError("Runtime package registry anchors do not match the migration target.")
    documents = {
        root / PATHS["capabilities"]: registries["capabilities"],
        root / PATHS["state"]: registries["state"],
        root / PATHS["packages"]: registries["packages"],
        root / "capability-catalog.json": catalog,
        root / PATHS["baseline"]: baseline,
        root / "song_agent/platform/persistence/runtime-state-authority-policy.json": (
            build_runtime_state_authority_policy(registries["state"], baseline)
        ),
        root / "song_agent/platform/contracts/runtime-package-writer-policy.json": (
            build_runtime_package_writer_policy(registries["packages"])
        ),
        root / "song_agent/platform/contracts/runtime-package-registry.json": projection,
    }
    current_path = root / "docs/architecture/CURRENT.md"
    current_text = _render_current_architecture_summary(
        current_path.read_text(encoding="utf-8"), catalog
    )
    originals = {path: path.read_bytes() if path.exists() else None for path in documents}
    originals[current_path] = current_path.read_bytes()
    try:
        for path, document in documents.items():
            _atomic_write(path, _encoded(document))
        _atomic_write(current_path, current_text)
        report = evaluate_wave0(root)
        if report["status"] != "passed":
            raise ValueError("Migrated Wave 0 gate failed: " + ", ".join(cast(list[str], report["blockers"])))
    except Exception:
        for path, content in originals.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        raise
    print("v14.4 source evidence migration applied")
    return 0


def _target_registries(
    root: Path, old: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    active, trees, source_texts = _active_sources(root)
    source_paths = {module: str(active[module]["path"]).replace("\\", "/") for module in active}
    observations: list[dict[str, object]] = []
    for module, tree in trees.items():
        observations.extend(_package_observations(tree, source_paths[module], source_texts[module]))
    observations = _normalize_dynamic_site_ids(observations)
    capability, site_owners = _migrate_capabilities(old["capabilities"], old["packages"], observations)
    packages = _migrate_packages(
        old["packages"],
        observations,
        site_owners,
        package_writer_contract_observations(trees, source_paths, source_texts),
    )
    state = _migrate_state(root, old["state"])
    return {
        "capabilities": capability,
        "state": state,
        "packages": packages,
        "waivers": copy.deepcopy(old["waivers"]),
    }


def _migrate_capabilities(
    registry: dict[str, object],
    package_registry: dict[str, object],
    observations: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, str]]:
    result = copy.deepcopy(registry)
    capability_rows = cast(list[dict[str, object]], result["capabilities"])
    old_owners = {
        str(site): str(row["capability_id"])
        for row in capability_rows
        for site in cast(list[object], cast(dict[str, object], row["surfaces"])["package_sites"])
    }
    classifications = {str(row["capability_id"]): str(row["classification"]) for row in capability_rows}
    old_sites = cast(list[dict[str, object]], package_registry["dynamic_sites"])
    indexed = _legacy_site_indices(old_sites, old_owners)
    owners: dict[str, str] = {}
    for observation in observations:
        if observation.get("package_type"):
            continue
        site_id = str(observation["source_id"])
        candidates = _site_owner_candidates(observation, indexed)
        ranked = sorted(
            {
                (int(_CAPABILITY_RANK.get(classifications.get(capability_id, ""), 0)), capability_id)
                for capability_id in candidates
            },
            reverse=True,
        )
        if not ranked or (len(ranked) > 1 and ranked[0][0] == ranked[1][0]):
            raise ValueError(f"Package site ownership is ambiguous: {site_id}: {sorted(candidates)}")
        owners[site_id] = ranked[0][1]
    for row in capability_rows:
        surfaces = cast(dict[str, object], row["surfaces"])
        surfaces["package_sites"] = sorted(
            site_id for site_id, capability_id in owners.items() if capability_id == row["capability_id"]
        )
    if len(owners) != len(set(owners)) or len(owners) != sum(
        len(cast(list[object], cast(dict[str, object], row["surfaces"])["package_sites"]))
        for row in capability_rows
    ):
        raise ValueError("Package site capability migration is incomplete.")
    result["integrity_hash"] = integrity_hash(result)
    return result, owners


def _migrate_packages(
    registry: dict[str, object],
    observations: list[dict[str, object]],
    owners: dict[str, str],
    writer_observations: list[dict[str, object]],
) -> dict[str, object]:
    result = copy.deepcopy(registry)
    static: dict[str, dict[str, list[object]]] = defaultdict(lambda: {"sources": [], "schemas": []})
    dynamic: list[dict[str, object]] = []
    for row in observations:
        package_type = str(row.get("package_type") or "")
        if package_type:
            static[package_type]["sources"].append(row["source_id"])
            if row.get("schema_version") not in (None, ""):
                static[package_type]["schemas"].append(row["schema_version"])
            continue
        site_id = str(row["source_id"])
        dynamic.append(
            {
                "site_id": site_id,
                "capability_id": owners[site_id],
                "expression": row["expression"],
                "expression_source_hash": row["expression_source_hash"],
                "scope_source_hash": row["scope_source_hash"],
                "line": row["line"],
                "column": row["column"],
                "end_line": row["end_line"],
                "end_column": row["end_column"],
                "candidate_kinds": row["candidate_kinds"],
                "policy": "registered_legacy_raw_write",
            }
        )
    package_rows = cast(list[dict[str, object]], result["package_types"])
    if set(static) != {str(row["package_type"]) for row in package_rows}:
        raise ValueError("Package type surface changed during source evidence migration.")
    for row in package_rows:
        values = static[str(row["package_type"])]
        row["sources"] = sorted(set(cast(list[str], values["sources"])))
        row["schema_versions"] = sorted(set(values["schemas"]), key=str)
    old_writers = {str(row["writer_id"]): row for row in cast(list[dict[str, object]], result["writer_contracts"])}
    if set(old_writers) != {str(row["writer_id"]) for row in writer_observations}:
        raise ValueError("Package writer surface changed during source evidence migration.")
    migrated_writers: list[dict[str, object]] = []
    for observed in writer_observations:
        writer_id = str(observed["writer_id"])
        row = copy.deepcopy(old_writers[writer_id])
        row.pop("expression_hash", None)
        row.pop("module_semantic_hash", None)
        row.update({key: value for key, value in observed.items() if key != "guarded"})
        migrated_writers.append(row)
    result["schema_version"] = TARGET_SCHEMAS["packages"]
    result["dynamic_sites"] = sorted(dynamic, key=lambda row: str(row["site_id"]))
    result["writer_contracts"] = sorted(migrated_writers, key=lambda row: str(row["writer_id"]))
    result["integrity_hash"] = integrity_hash(result)
    return result


def _migrate_state(root: Path, registry: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(registry)
    old_to_new: dict[tuple[str, str, str], str] = {}
    for entry in cast(list[dict[str, object]], result["entries"]):
        store_id = str(entry["store_id"])
        class_name = store_id.rsplit(".", 1)[-1]
        for namespace in cast(list[dict[str, object]], entry.get("physical_namespaces") or []):
            root_id = str(namespace["root_authority_id"])
            old_hash = _legacy_namespace_hash(store_id, namespace)
            evidence = cast(dict[str, object], namespace["path_evidence"])
            replacement = namespace_path_evidence(
                root / str(evidence["source"]),
                str(evidence["source"]),
                class_name,
                root_id,
                str(namespace["relative_path_template"]),
            )
            if replacement is None:
                raise ValueError(f"State path evidence cannot be regenerated: {store_id}")
            namespace["path_evidence"] = replacement
            old_to_new[(store_id, root_id, old_hash)] = namespace_identity_hash(store_id, namespace)
    for row in cast(list[dict[str, object]], result["writer_overlap_exceptions"]):
        for side in ("left", "right"):
            key = (
                str(row[f"{side}_store_id"]),
                str(row[f"{side}_root_authority_id"]),
                str(row[f"{side}_namespace_hash"]),
            )
            if key not in old_to_new:
                raise ValueError(f"State overlap exception cannot be rebound: {row['exception_id']}:{side}")
            row[f"{side}_namespace_hash"] = old_to_new[key]
    result["schema_version"] = TARGET_SCHEMAS["state"]
    result["integrity_hash"] = integrity_hash(result)
    return result


def _legacy_site_indices(
    rows: list[dict[str, object]], owners: dict[str, str]
) -> list[tuple[tuple[str, ...], dict[tuple[str, ...], list[str]]]]:
    parsed: list[dict[str, str]] = []
    for row in rows:
        match = _OLD_SITE.fullmatch(str(row["site_id"]))
        if match is None or row["site_id"] not in owners:
            raise ValueError(f"Legacy package site cannot be decoded: {row['site_id']}")
        parsed.append(
            {
                "source": match.group(1),
                "candidate_kind": str(row["candidate_kind"]),
                "expression": _canonical_expression(match.group(2)),
                "capability_id": owners[str(row["site_id"])],
            }
        )
    result: list[tuple[tuple[str, ...], dict[tuple[str, ...], list[str]]]] = []
    for fields in (
        ("source", "candidate_kind", "expression"),
        ("source", "expression"),
        ("source", "candidate_kind"),
    ):
        index: dict[tuple[str, ...], list[str]] = defaultdict(list)
        for row in parsed:
            index[tuple(row[field] for field in fields)].append(row["capability_id"])
        result.append((fields, index))
    return result


def _site_owner_candidates(
    row: dict[str, object],
    indices: list[tuple[tuple[str, ...], dict[tuple[str, ...], list[str]]]],
) -> set[str]:
    source = str(row["source_id"]).split(":", 1)[0]
    expression = _canonical_expression(str(row["expression"]))
    candidate_kinds = cast(list[str], row["candidate_kinds"])
    for fields, index in indices:
        if "candidate_kind" in fields:
            keys = [
                tuple(
                    source if field == "source" else expression if field == "expression" else candidate_kind
                    for field in fields
                )
                for candidate_kind in candidate_kinds
            ]
        else:
            keys = [tuple(source if field == "source" else expression for field in fields)]
        candidates = {capability for key in keys for capability in index.get(key, [])}
        if candidates:
            return candidates
    return set()


def _canonical_expression(value: str) -> str:
    try:
        return ast.unparse(ast.parse(value, mode="eval").body)
    except (SyntaxError, ValueError):
        return value.strip()


def _legacy_namespace_hash(store_id: str, namespace: dict[str, object]) -> str:
    evidence = cast(dict[str, object], namespace["path_evidence"])
    payload = {
        "store_id": store_id,
        "root_authority_id": namespace.get("root_authority_id"),
        "relative_path_template": namespace.get("relative_path_template"),
        "source": evidence.get("source"),
        "line": evidence.get("line"),
        "column": evidence.get("column"),
        "expression_hash": evidence.get("expression_hash"),
        "relative_path_template_hash": evidence.get("relative_path_template_hash"),
    }
    return _json_hash(payload)


def _rebind_state_exceptions(registry: dict[str, object], baseline_hash: str) -> dict[str, object]:
    result = copy.deepcopy(registry)
    for row in cast(list[dict[str, object]], result["writer_overlap_exceptions"]):
        row["baseline_integrity_hash"] = baseline_hash
    result["integrity_hash"] = integrity_hash(result)
    return result


def _require_exact_old_documents(documents: dict[str, dict[str, object]]) -> None:
    for key, expected_hash in OLD_HASHES.items():
        document = documents[key]
        if document.get("integrity_hash") != expected_hash or integrity_hash(document) != expected_hash:
            raise ValueError(f"Wave 0 source evidence migration rejected unexpected {key} input.")


def _is_target(documents: dict[str, dict[str, object]]) -> bool:
    return all(
        document.get("schema_version") == TARGET_SCHEMAS[key]
        and document.get("integrity_hash") == integrity_hash(document)
        for key, document in documents.items()
    )


def _json_hash(value: object) -> str:
    import hashlib

    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, object], value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate approved Wave 0 evidence to source schema 1.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return migrate(Path(args.root).resolve(), apply=bool(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
