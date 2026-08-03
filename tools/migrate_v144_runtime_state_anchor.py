from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import cast

from song_agent.platform.contracts.packages import (
    APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH,
    APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH,
    build_runtime_package_writer_policy,
)
from song_agent.platform.persistence.file_artifacts import STATE_POLICY_RESOURCE, build_runtime_state_authority_policy
from song_agent.platform.verification.hashing import integrity_hash
from song_agent.release_check.v14_wave0 import build_wave0_baseline, evaluate_wave0
from song_agent.release_check.v14_wave0_inventory import (
    _active_sources,
    _normalize_dynamic_site_ids,
    _package_observations,
    build_wave0_catalog,
)
from song_agent.release_check.v14_wave0_package_inventory import package_writer_contract_observations
from song_agent.release_check.v14_wave0_registry import load_wave0_registries, validate_wave0_registries
from tools.update_v144_wave0_catalog import (
    _encoded,
    _render_current_architecture_summary,
    build_runtime_package_registry_projection,
)


INPUT_HASHES = {
    "capabilities": "2ae5c43eb8c7ad6d99600737132796700807e9e571d87b0295b8c60bd97b2d29",
    "state": "069ff26be2e69bd45608b45a7dd4cfb6bfb4883e8088c3d2b495fe33f9ea4ff7",
    "packages": "d0dba235e083e70b4f94a92551b9882234471f14d827ae815b582507ed522d20",
    "waivers": "dd7f4d88165d58ea3ff7e3b7d2f144b561fbb92d66bc1c2f1dc3c30ced455aba",
    "baseline": "81c023d085601fe3ce99126c2efd72eb45aeb3395fa96da5219bf2656058b3bf",
}
TARGET_HASHES: dict[str, object] = {
    "baseline_hash": "e8c1ec990d6f7f3330b7dd148e7abdbd6be45f37d74bf3ae671aebd3124f43e7",
    "capability_registry_hash": "2ae5c43eb8c7ad6d99600737132796700807e9e571d87b0295b8c60bd97b2d29",
    "catalog_hash": "2e83d96e1e6ae2c7921a09af40490c75ab10c4f0b3d7d90d714bcb557e61a2c0",
    "package_projection_hash": "45879327cf3444f1d9e4993c043d71bc495a0125596ef7791ec7bced312bfe69",
    "package_registry_hash": "c1cf7d2a35580200d0ed3d9c23949451708b2040b3b97d50dedc84d9991bdcf5",
    "package_site_count": 2687,
    "package_writer_policy_hash": "e7b7674fcba0072ba7100e058edd915de7de83f7f9fff24082a0a28195e3d040",
    "state_policy_hash": "21d23353bc5eb425bd66fdf1742035d8660e7df486d9183ac3b27811fa8cf967",
    "state_registry_hash": "1f353dd270a47efe05a23db997558bbd88bf72e42ee3dc765340c1d6b145742d",
    "waiver_registry_hash": "dd7f4d88165d58ea3ff7e3b7d2f144b561fbb92d66bc1c2f1dc3c30ced455aba",
}
PATHS = {
    "capabilities": "architecture-v14.4-capability-registry.json",
    "state": "architecture-v14.4-state-authority-registry.json",
    "packages": "architecture-v14.4-package-schema-registry.json",
    "waivers": "architecture-v14.4-wave0-waivers.json",
    "baseline": "architecture-v14.4-wave0-baseline.json",
}


def migrate(root: Path, *, apply: bool) -> int:
    documents = {key: _read(root / path) for key, path in PATHS.items()}
    _require_inputs(documents)
    registries = load_wave0_registries(root)
    registries["packages"] = _refreshed_package_registry(root, registries["packages"])
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
        raise ValueError("Migrated Wave 0 registries are invalid: " + ", ".join(blockers))
    projection = build_runtime_package_registry_projection(
        registries["packages"], approved_registry_hash=None
    )
    writer_policy = build_runtime_package_writer_policy(registries["packages"])
    state_policy = build_runtime_state_authority_policy(registries["state"], baseline)
    plan = {
        "capability_registry_hash": registries["capabilities"]["integrity_hash"],
        "state_registry_hash": registries["state"]["integrity_hash"],
        "package_registry_hash": registries["packages"]["integrity_hash"],
        "waiver_registry_hash": registries["waivers"]["integrity_hash"],
        "catalog_hash": catalog["integrity_hash"],
        "baseline_hash": baseline["integrity_hash"],
        "package_projection_hash": projection["integrity_hash"],
        "package_writer_policy_hash": writer_policy["integrity_hash"],
        "state_policy_hash": state_policy["integrity_hash"],
        "package_site_count": len(cast(list[object], registries["packages"]["dynamic_sites"])),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    if not apply:
        return 0
    if plan != TARGET_HASHES:
        raise ValueError("Runtime State Authority anchor migration target is not approved.")
    if (
        plan["package_registry_hash"] != APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH
        or plan["package_projection_hash"] != APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH
        or plan["state_policy_hash"] != STATE_POLICY_RESOURCE[1]
    ):
        raise ValueError("Runtime source anchors do not match the approved migration target.")
    output = {
        root / PATHS["state"]: registries["state"],
        root / PATHS["packages"]: registries["packages"],
        root / "capability-catalog.json": catalog,
        root / PATHS["baseline"]: baseline,
        root / "song_agent/platform/contracts/runtime-package-registry.json": projection,
        root / "song_agent/platform/contracts/runtime-package-writer-policy.json": writer_policy,
        root / "song_agent/platform/persistence/runtime-state-authority-policy.json": state_policy,
    }
    current_path = root / "docs/architecture/CURRENT.md"
    current = _render_current_architecture_summary(current_path.read_text(encoding="utf-8"), catalog)
    originals = {path: path.read_bytes() if path.exists() else None for path in output}
    originals[current_path] = current_path.read_bytes()
    try:
        for path, document in output.items():
            _atomic_write(path, _encoded(document))
        _atomic_write(current_path, current)
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
    print("v14.4 runtime State Authority anchor migration applied")
    return 0


def _refreshed_package_registry(root: Path, registry: dict[str, object]) -> dict[str, object]:
    active, trees, source_texts = _active_sources(root)
    source_paths = {module: str(active[module]["path"]).replace("\\", "/") for module in active}
    observations: list[dict[str, object]] = []
    for module, tree in trees.items():
        observations.extend(_package_observations(tree, source_paths[module], source_texts[module]))
    dynamic = {
        str(row["source_id"]): row
        for row in _normalize_dynamic_site_ids(observations)
        if not row.get("package_type")
    }
    result = copy.deepcopy(registry)
    rows = cast(list[dict[str, object]], result["dynamic_sites"])
    if {str(row["site_id"]) for row in rows} != set(dynamic):
        raise ValueError("Runtime anchor migration changed the frozen package site identities.")
    evidence_fields = {
        "expression",
        "expression_source_hash",
        "scope_source_hash",
        "line",
        "column",
        "end_line",
        "end_column",
        "candidate_kinds",
    }
    for row in rows:
        current = dynamic[str(row["site_id"])]
        row.update({key: current[key] for key in evidence_fields})
    current_writers = {
        str(row["writer_id"]): row
        for row in package_writer_contract_observations(trees, source_paths, source_texts)
    }
    writers = cast(list[dict[str, object]], result["writer_contracts"])
    if {str(row["writer_id"]) for row in writers} != set(current_writers):
        raise ValueError("Runtime anchor migration changed the frozen package writer identities.")
    writer_fields = {
        "source",
        "line",
        "write_lines",
        "value_parameters",
        "expression_source_hash",
        "module_source_hash",
        "guard_symbol",
        "guard_alias",
        "guard_binding_hash",
    }
    for row in writers:
        current = current_writers[str(row["writer_id"])]
        row.update({key: current[key] for key in writer_fields})
    result["integrity_hash"] = integrity_hash(result)
    return result


def _rebind_state_exceptions(registry: dict[str, object], baseline_hash: str) -> dict[str, object]:
    result = copy.deepcopy(registry)
    for row in cast(list[dict[str, object]], result["writer_overlap_exceptions"]):
        row["baseline_integrity_hash"] = baseline_hash
    result["integrity_hash"] = integrity_hash(result)
    return result


def _require_inputs(documents: dict[str, dict[str, object]]) -> None:
    for key, expected in INPUT_HASHES.items():
        document = documents[key]
        if document.get("integrity_hash") != expected or integrity_hash(document) != expected:
            raise ValueError(f"Runtime anchor migration rejected unexpected {key} input.")


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, object], value)


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate Wave 0 to an independently anchored runtime State Authority policy.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return migrate(Path(args.root).resolve(), apply=bool(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
