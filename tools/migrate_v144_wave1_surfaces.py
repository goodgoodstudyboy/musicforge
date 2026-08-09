from __future__ import annotations

import argparse
import copy
import json
import subprocess
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import cast

from song_agent.platform.contracts.packages import (
    APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH,
    APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH,
    _document_hash as package_document_hash,
    build_runtime_package_writer_policy,
)
from song_agent.platform.persistence.file_artifacts import (
    STATE_POLICY_RESOURCE,
    build_runtime_state_authority_policy,
)
from song_agent.platform.verification.hashing import integrity_hash
from song_agent.release_check.v14_wave0 import (
    build_dependency_snapshot,
    build_quality_snapshot,
    build_wave0_baseline,
    evaluate_wave0,
)
from song_agent.release_check.v14_wave0_inventory import (
    _active_sources,
    _normalize_dynamic_site_ids,
    _package_observations,
    build_wave0_catalog,
)
from song_agent.release_check.v14_wave0_package_inventory import (
    package_writer_contract_observations,
)
from song_agent.release_check.v14_wave0_registry import (
    validate_wave0_registries,
)
from song_agent.release_check.v14_wave0_ratchet import dependency_regressions, quality_regressions
from song_agent.release_check.v14_wave1 import evaluate_wave1
try:
    from tools.update_v144_wave0_catalog import (
        _encoded,
        _render_current_architecture_summary,
        _transactional_write,
        build_runtime_package_registry_projection,
    )
except ModuleNotFoundError:
    from update_v144_wave0_catalog import (
        _encoded,
        _render_current_architecture_summary,
        _transactional_write,
        build_runtime_package_registry_projection,
    )


MIGRATION_ID = "v14.4-wave1-platform-application-interfaces"
MIGRATION_PATH = "architecture-v14.4-wave1-surface-migration.json"
APPROVED_INPUT_COMMIT = "598412ef9d4a8f1ed0fe8f20f8da6b39c433eecd"
ARCHITECTURE_CAPABILITY = "studio.architecture-governance"
WAVE1_RELEASE_CHECK = "v144.wave1_platform_application_interfaces_smoke"
INPUT_HASHES = {
    "capabilities": "2ae5c43eb8c7ad6d99600737132796700807e9e571d87b0295b8c60bd97b2d29",
    "state": "1f353dd270a47efe05a23db997558bbd88bf72e42ee3dc765340c1d6b145742d",
    "packages": "c1cf7d2a35580200d0ed3d9c23949451708b2040b3b97d50dedc84d9991bdcf5",
    "waivers": "dd7f4d88165d58ea3ff7e3b7d2f144b561fbb92d66bc1c2f1dc3c30ced455aba",
    "baseline": "e8c1ec990d6f7f3330b7dd148e7abdbd6be45f37d74bf3ae671aebd3124f43e7",
    "catalog": "2e83d96e1e6ae2c7921a09af40490c75ab10c4f0b3d7d90d714bcb557e61a2c0",
    "package_projection": "45879327cf3444f1d9e4993c043d71bc495a0125596ef7791ec7bced312bfe69",
    "package_writer_policy": "e7b7674fcba0072ba7100e058edd915de7de83f7f9fff24082a0a28195e3d040",
    "state_policy": "21d23353bc5eb425bd66fdf1742035d8660e7df486d9183ac3b27811fa8cf967",
}
TARGET_HASHES: dict[str, object] = {
    "baseline_hash": "0e938231be949256431385504bbf04e6ae41dc0a3ae0cfae583512bfee6c3847",
    "capability_registry_hash": "bc901d2324f32d271567fecbad4c07d005a24750e71b23ed1e8207b3fa5dfd4c",
    "catalog_hash": "49294bf4d6fb156f8153afeae488ce859d65e490f5d34a3bac0d08145a551bea",
    "cli_registration_relocation_count": 78,
    "migration_manifest_hash": "a0757af4a398e8e55b849c35d710a1015d07ea39b435a0d26d4d37e5e2093208",
    "package_projection_hash": "a15ba1009cda23f5cfa011c57d5c389b527bdb0517dcda10a2a02c4808d40880",
    "package_registry_hash": "28a3d0f80ff9c697b8d1dbd0aa20bd76f9f29efc51d8e4ea0b17429bbb6d6127",
    "package_site_count": 2676,
    "package_site_relocation_count": 164,
    "package_site_retirement_count": 9,
    "package_site_rewrite_count": 12,
    "package_writer_policy_hash": "2232f406f609cb84006dbdef4acc05bbec118a47f16f82c3d7bd5b4bfea836bb",
    "release_check_count": 204,
    "state_policy_hash": "36f09b71009a715d8e559da9933d226d2d616ca18e89aef813c987483629c52b",
    "state_registry_hash": "850509af2239c7d2f9820e5cbbb7c4d0428080ce80f705525dbb2e27f8d3267b",
    "waiver_registry_hash": "dd7f4d88165d58ea3ff7e3b7d2f144b561fbb92d66bc1c2f1dc3c30ced455aba",
}
PATHS = {
    "capabilities": "architecture-v14.4-capability-registry.json",
    "state": "architecture-v14.4-state-authority-registry.json",
    "packages": "architecture-v14.4-package-schema-registry.json",
    "waivers": "architecture-v14.4-wave0-waivers.json",
    "baseline": "architecture-v14.4-wave0-baseline.json",
    "catalog": "capability-catalog.json",
    "package_projection": "song_agent/platform/contracts/runtime-package-registry.json",
    "package_writer_policy": "song_agent/platform/contracts/runtime-package-writer-policy.json",
    "state_policy": "song_agent/platform/persistence/runtime-state-authority-policy.json",
}

PACKAGE_TRANSITIONS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("song_agent/domains/program/unified_command_center_release_train_lifecycle.py:279:41:279:138",),
        ("song_agent/domains/program/unified_command_center_release_train_lifecycle.py:279:41:279:128",),
    ),
    (
        ("song_agent/domains/program/unified_release_program_continuity_command_center_acceptance_change_verifier.py:474:25:478:5@475:51:475:56",),
        ("song_agent/domains/program/unified_release_program_continuity_command_center_acceptance_change_verifier.py:478:12:478:59@478:54:478:59",),
    ),
    (
        (
            "song_agent/domains/program/unified_release_program_continuity_command_center_verifier.py:430:22:430:82@430:39:430:42",
            "song_agent/domains/program/unified_release_program_continuity_command_center_verifier.py:431:20:431:85@431:37:431:40",
            "song_agent/domains/program/unified_release_program_continuity_command_center_verifier.py:432:21:432:90@432:38:432:41",
        ),
        ("song_agent/domains/program/unified_release_program_continuity_command_center_verifier.py:341:12:341:41@341:38:341:41",),
    ),
    (
        ("song_agent/interfaces/api/routes/creation_parts/audition_context_pack.py:235:8:235:73@235:54:235:73",),
        ("song_agent/interfaces/api/routes/creation_parts/audition_context_pack.py:330:8:330:41@330:38:330:41",),
    ),
    (
        ("song_agent/interfaces/api/routes/trust_parts/public_trust_center_acceptance_board.py:55:114:55:462@55:224:55:268",),
        ("song_agent/interfaces/api/routes/trust_parts/public_trust_center_acceptance_board.py:90:31:96:21@93:28:93:72",),
    ),
    (
        ("song_agent/interfaces/cli/commands/program_parts/unified_command_center_release_train_change_control_command.py:252:12:252:33@252:28:252:33",),
        ("song_agent/interfaces/cli/commands/program_parts/unified_command_center_release_train_change_control_command.py:254:12:254:55@254:28:254:55",),
    ),
    (
        ("song_agent/interfaces/cli/commands/trust_parts/trust_operations_final_readiness.py:21:8:21:59@21:22:21:58",),
        ("song_agent/interfaces/cli/commands/trust_parts/trust_operations_final_readiness.py:25:8:25:65@25:22:25:64",),
    ),
    (
        ("song_agent/platform/contracts/run_state.py:51:20:54:9@52:18:52:41",),
        ("song_agent/platform/contracts/run_state.py:58:16:62:17@58:34:62:17",),
    ),
    (
        ("song_agent/platform/lifecycle/change_control.py:68:8:68:36@68:22:68:35",),
        ("song_agent/platform/lifecycle/change_control.py:75:12:75:59@75:26:75:58",),
    ),
    (
        ("song_agent/platform/lifecycle/generation.py:32:12:32:34@32:28:32:33",),
        ("song_agent/platform/lifecycle/generation.py:33:12:33:59@33:28:33:58",),
    ),
    (
        ("song_agent/platform/persistence/v13_migration.py:168:17:180:9",),
        ("song_agent/platform/persistence/v13_migration.py:177:17:189:9",),
    ),
    (
        ("song_agent/platform/verification/model.py:65:8:65:28@65:22:65:27",),
        ("song_agent/platform/verification/model.py:75:8:75:53@75:22:75:52",),
    ),
)
RETIRED_PACKAGE_SITES = frozenset(
    {
        "song_agent/capabilities/registry.py:40:32:40:99@40:53:40:56",
        "song_agent/platform/persistence/v13_migration.py:183:23:183:112",
        "song_agent/platform/persistence/v14_migration.py:40:15:58:9",
        "song_agent/platform/persistence/v14_migration.py:85:21:96:13",
        "song_agent/platform/persistence/v14_migration.py:111:21:131:13",
        "song_agent/platform/persistence/v14_migration.py:135:21:147:13",
        "song_agent/platform/persistence/v14_migration.py:164:19:176:9",
        "song_agent/platform/persistence/v14_migration.py:229:19:244:13",
        "song_agent/platform/verification/registry.py:44:12:44:100@44:25:44:100",
    }
)


def migrate(root: Path, *, apply: bool) -> int:
    documents = {key: _read(root / path) for key, path in PATHS.items()}
    if _target_applied(documents, root):
        print("v14.4 Wave 1 surface migration is already applied")
        return 0
    try:
        _require_inputs(documents)
    except ValueError:
        documents = _approved_input_documents(root)
        _require_inputs(documents)
    registries = {
        key: copy.deepcopy(documents[key])
        for key in ("capabilities", "state", "packages", "waivers")
    }
    current_catalog = build_wave0_catalog(root, registries=registries)
    capability, cli_moves, package_moves, package_retirements, owners = _migrate_capabilities(
        documents["catalog"], current_catalog, registries["capabilities"], registries["packages"]
    )
    registries["capabilities"] = capability
    registries["packages"] = _migrate_packages(root, registries["packages"], owners)
    provisional_catalog = build_wave0_catalog(root, registries=registries)
    provisional_baseline = build_wave0_baseline(root, provisional_catalog, registries=registries)
    registries["state"] = _rebind_state_exceptions(
        registries["state"], str(provisional_baseline["integrity_hash"])
    )
    catalog = build_wave0_catalog(root, registries=registries)
    baseline = build_wave0_baseline(root, catalog, registries=registries)
    if baseline["integrity_hash"] != provisional_baseline["integrity_hash"]:
        raise ValueError("State exception rebinding changed the Wave 0 baseline hash.")
    regressions = [
        *quality_regressions(
            cast(dict[str, object], documents["baseline"]["quality_freeze"]),
            cast(dict[str, object], baseline["quality_freeze"]),
        ),
        *dependency_regressions(
            cast(dict[str, object], documents["baseline"]["dependency_baseline"]),
            cast(dict[str, object], baseline["dependency_baseline"]),
        ),
    ]
    regressions = [
        row for row in regressions
        if row != f"quality_ceiling_added:check_duration_budgets.{WAVE1_RELEASE_CHECK}"
    ]
    if regressions:
        raise ValueError("Wave 1 raised a frozen ceiling: " + ", ".join(regressions))
    blockers = validate_wave0_registries(
        registries,
        root=root,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
    )
    if blockers:
        raise ValueError("Wave 1 registries are invalid: " + ", ".join(blockers))
    projection = build_runtime_package_registry_projection(
        registries["packages"], approved_registry_hash=None
    )
    writer_policy = build_runtime_package_writer_policy(registries["packages"])
    state_policy = build_runtime_state_authority_policy(registries["state"], baseline)
    target_documents = {
        "capability_registry_hash": registries["capabilities"]["integrity_hash"],
        "state_registry_hash": registries["state"]["integrity_hash"],
        "package_registry_hash": registries["packages"]["integrity_hash"],
        "waiver_registry_hash": registries["waivers"]["integrity_hash"],
        "catalog_hash": catalog["integrity_hash"],
        "baseline_hash": baseline["integrity_hash"],
        "package_projection_hash": projection["integrity_hash"],
        "package_writer_policy_hash": writer_policy["integrity_hash"],
        "state_policy_hash": state_policy["integrity_hash"],
    }
    manifest = _migration_manifest(
        cli_moves,
        package_moves,
        package_retirements,
        target_documents,
        baseline,
    )
    plan = {
        **target_documents,
        "migration_manifest_hash": manifest["integrity_hash"],
        "cli_registration_relocation_count": len(cli_moves),
        "package_site_relocation_count": sum(
            1 for row in package_moves if row["transition"] == "source_relocation"
        ),
        "package_site_rewrite_count": sum(
            1 for row in package_moves if row["transition"] != "source_relocation"
        ),
        "package_site_retirement_count": len(package_retirements),
        "package_site_count": len(cast(list[object], registries["packages"]["dynamic_sites"])),
        "release_check_count": len(cast(list[object], catalog["inventory"]["release_checks"])),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    if not apply:
        return 0
    if plan != TARGET_HASHES:
        raise ValueError("Wave 1 surface migration target is not approved.")
    if (
        plan["package_registry_hash"] != APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH
        or plan["package_projection_hash"] != APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH
        or plan["state_policy_hash"] != STATE_POLICY_RESOURCE[1]
    ):
        raise ValueError("Wave 1 runtime anchors do not match the approved migration target.")
    output_documents = {
        root / PATHS["capabilities"]: registries["capabilities"],
        root / PATHS["state"]: registries["state"],
        root / PATHS["packages"]: registries["packages"],
        root / PATHS["catalog"]: catalog,
        root / PATHS["baseline"]: baseline,
        root / PATHS["package_projection"]: projection,
        root / PATHS["package_writer_policy"]: writer_policy,
        root / PATHS["state_policy"]: state_policy,
        root / MIGRATION_PATH: manifest,
    }
    current_path = root / "docs/architecture/CURRENT.md"
    outputs = {path: _encoded(document) for path, document in output_documents.items()}
    outputs[current_path] = _render_current_architecture_summary(
        current_path.read_text(encoding="utf-8"), catalog
    )
    _transactional_write(outputs, verify=lambda: _verify_applied(root, plan))
    print("v14.4 Wave 1 surface migration applied")
    return 0


def _migrate_capabilities(
    old_catalog: dict[str, object],
    current_catalog: dict[str, object],
    capability_registry: dict[str, object],
    package_registry: dict[str, object],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, str],
]:
    old_inventory = cast(dict[str, object], old_catalog["inventory"])
    current_inventory = cast(dict[str, object], current_catalog["inventory"])
    _require_expected_surface_changes(old_inventory, current_inventory)
    result = copy.deepcopy(capability_registry)
    rows = cast(list[dict[str, object]], result["capabilities"])
    cli_owners = _surface_owners(rows, "cli_registration_points")
    package_owners = _surface_owners(rows, "package_sites")
    cli_moves = _cli_relocations(
        cast(list[dict[str, object]], old_inventory["cli_registration_points"]),
        cast(list[dict[str, object]], current_inventory["cli_registration_points"]),
        cli_owners,
    )
    package_moves, package_retirements, owners = _package_relocations(
        cast(list[dict[str, object]], package_registry["dynamic_sites"]),
        cast(list[dict[str, object]], current_inventory["package_sites"]),
        package_owners,
    )
    cli_owner_current = {
        **{identity: owner for identity, owner in cli_owners.items() if identity in _inventory_ids(current_inventory, "cli_registration_points", "registration_id")},
        **{str(row["new_id"]): str(row["capability_id"]) for row in cli_moves},
    }
    for row in rows:
        surfaces = cast(dict[str, object], row["surfaces"])
        capability_id = str(row["capability_id"])
        surfaces["cli_registration_points"] = sorted(
            identity for identity, owner in cli_owner_current.items() if owner == capability_id
        )
        surfaces["package_sites"] = sorted(
            identity for identity, owner in owners.items() if owner == capability_id
        )
        checks = {str(value) for value in cast(list[object], surfaces["release_checks"])}
        if capability_id == ARCHITECTURE_CAPABILITY:
            checks.add(WAVE1_RELEASE_CHECK)
        surfaces["release_checks"] = sorted(checks)
    result["integrity_hash"] = integrity_hash(result)
    return result, cli_moves, package_moves, package_retirements, owners


def _cli_relocations(
    old_rows: list[dict[str, object]],
    new_rows: list[dict[str, object]],
    owners: dict[str, str],
) -> list[dict[str, object]]:
    old = {str(row["registration_id"]): row for row in old_rows}
    new = {str(row["registration_id"]): row for row in new_rows}
    removed = [old[value] for value in sorted(set(old) - set(new))]
    added = [new[value] for value in sorted(set(new) - set(old))]
    old_groups = _group_rows(removed, _cli_key)
    new_groups = _group_rows(added, _cli_key)
    if set(old_groups) != set(new_groups) or any(
        len(old_groups[key]) != len(new_groups[key]) for key in old_groups
    ):
        raise ValueError("CLI registration relocation is not a semantic bijection.")
    moves: list[dict[str, object]] = []
    for key in sorted(old_groups):
        for before, after in zip(old_groups[key], new_groups[key], strict=True):
            old_id = str(before["registration_id"])
            moves.append(
                {
                    "old_id": old_id,
                    "new_id": str(after["registration_id"]),
                    "capability_id": owners[old_id],
                    "source": before["source"],
                    "function": before["function"],
                    "command": before["command"],
                }
            )
    if len(moves) != 78:
        raise ValueError(f"Expected 78 CLI registration relocations, found {len(moves)}.")
    return sorted(moves, key=lambda row: str(row["old_id"]))


def _package_relocations(
    old_rows: list[dict[str, object]],
    new_rows: list[dict[str, object]],
    old_owners: dict[str, str],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, str]]:
    old = {str(row["site_id"]): row for row in old_rows}
    new = {str(row["site_id"]): row for row in new_rows}
    owners = {identity: old_owners[identity] for identity in set(old) & set(new)}
    removed = {identity: old[identity] for identity in set(old) - set(new)}
    added = {identity: new[identity] for identity in set(new) - set(old)}
    moves: list[dict[str, object]] = []
    old_groups = _group_rows(list(removed.values()), _package_key)
    new_groups = _group_rows(list(added.values()), _package_key)
    for key in sorted(set(old_groups) & set(new_groups), key=str):
        count = min(len(old_groups[key]), len(new_groups[key]))
        for before, after in zip(old_groups[key][:count], new_groups[key][:count], strict=True):
            old_id = str(before["site_id"])
            new_id = str(after["site_id"])
            capability_id = old_owners[old_id]
            owners[new_id] = capability_id
            moves.append(_package_move(before, after, capability_id, "source_relocation"))
            removed.pop(old_id)
            added.pop(new_id)
    for old_ids, new_ids in PACKAGE_TRANSITIONS:
        if any(identity not in removed for identity in old_ids) or any(identity not in added for identity in new_ids):
            raise ValueError(f"Package transition does not match the current tree: {old_ids} -> {new_ids}")
        capabilities = {old_owners[identity] for identity in old_ids}
        if len(capabilities) != 1:
            raise ValueError(f"Package transition crosses capability ownership: {old_ids}")
        capability_id = capabilities.pop()
        for identity in new_ids:
            owners[identity] = capability_id
        moves.append(
            {
                "old_ids": list(old_ids),
                "new_ids": list(new_ids),
                "capability_id": capability_id,
                "transition": "semantic_rewrite" if len(old_ids) == len(new_ids) else "semantic_consolidation",
                "old_expression_hashes": [old[identity]["expression_source_hash"] for identity in old_ids],
                "new_expression_hashes": [new[identity]["expression_source_hash"] for identity in new_ids],
            }
        )
        for identity in old_ids:
            removed.pop(identity)
        for identity in new_ids:
            added.pop(identity)
    if set(removed) != RETIRED_PACKAGE_SITES or added:
        raise ValueError(
            "Unexpected package surface change: "
            f"removed={sorted(removed)}, added={sorted(added)}"
        )
    retirements = [
        {
            "site_id": identity,
            "capability_id": old_owners[identity],
            "expression_source_hash": old[identity]["expression_source_hash"],
            "reason": "Typed control flow removed an unresolved or duplicate legacy raw-write observation.",
        }
        for identity in sorted(removed)
    ]
    if len(moves) != 176 or len(owners) != len(new):
        raise ValueError("Package surface migration is incomplete.")
    return sorted(moves, key=lambda row: str(row.get("old_id") or row.get("old_ids"))), retirements, owners


def _migrate_packages(
    root: Path,
    registry: dict[str, object],
    owners: dict[str, str],
) -> dict[str, object]:
    active, trees, source_texts = _active_sources(root)
    source_paths = {module: str(active[module]["path"]).replace("\\", "/") for module in active}
    observations: list[dict[str, object]] = []
    for module, tree in trees.items():
        observations.extend(_package_observations(tree, source_paths[module], source_texts[module]))
    observations = _normalize_dynamic_site_ids(observations)
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
        raise ValueError("Wave 1 changed the registered package type set.")
    for row in package_rows:
        values = static[str(row["package_type"])]
        row["sources"] = sorted(set(cast(list[str], values["sources"])))
        row["schema_versions"] = sorted(set(values["schemas"]), key=str)
    current_writers = {
        str(row["writer_id"]): row
        for row in package_writer_contract_observations(trees, source_paths, source_texts)
    }
    old_writers = {
        str(row["writer_id"]): row
        for row in cast(list[dict[str, object]], result["writer_contracts"])
    }
    if set(old_writers) != set(current_writers):
        raise ValueError("Wave 1 changed the registered package writer set.")
    migrated_writers: list[dict[str, object]] = []
    for writer_id, observed in sorted(current_writers.items()):
        row = copy.deepcopy(old_writers[writer_id])
        row.update({key: value for key, value in observed.items() if key != "guarded"})
        migrated_writers.append(row)
    result["dynamic_sites"] = sorted(dynamic, key=lambda row: str(row["site_id"]))
    result["writer_contracts"] = migrated_writers
    result["integrity_hash"] = integrity_hash(result)
    return result


def _migration_manifest(
    cli_moves: list[dict[str, object]],
    package_moves: list[dict[str, object]],
    retirements: list[dict[str, object]],
    target_hashes: dict[str, object],
    baseline: dict[str, object],
) -> dict[str, object]:
    dependency = cast(dict[str, object], baseline["dependency_baseline"])
    document: dict[str, object] = {
        "schema_version": 1,
        "package_type": "musicforge_v144_wave1_surface_migration",
        "migration_id": MIGRATION_ID,
        "status": "candidate",
        "input_hashes": INPUT_HASHES,
        "target_hashes": target_hashes,
        "cli_registration_relocations": cli_moves,
        "package_site_transitions": package_moves,
        "package_site_retirements": retirements,
        "package_site_additions": [],
        "release_check_additions": [WAVE1_RELEASE_CHECK],
        "invariants": {
            "business_surface_added": False,
            "package_type_set_changed": False,
            "package_writer_set_changed": False,
            "package_site_count_before": 2687,
            "package_site_count_after": 2676,
            "production_cycle_count": dependency["production_cycle_count"],
            "boundary_violation_count": dependency["boundary_violation_count"],
            "active_to_compatibility_import_count": dependency["active_to_compatibility_import_count"],
        },
    }
    document["integrity_hash"] = integrity_hash(document)
    return document


def _require_expected_surface_changes(
    old_inventory: dict[str, object], current_inventory: dict[str, object]
) -> None:
    identity_keys = {
        "stores": "store_id",
        "cli_commands": "command_id",
        "cli_registration_points": "registration_id",
        "api_routes": "route_id",
        "packages": "package_id",
        "package_types": "package_type",
        "package_sites": "site_id",
        "verifiers": "verifier_id",
        "schemas": "schema_id",
        "studio_panels": "panel_id",
        "release_checks": "release_check_id",
    }
    for name, identity_key in identity_keys.items():
        old_ids = _inventory_ids(old_inventory, name, identity_key)
        new_ids = _inventory_ids(current_inventory, name, identity_key)
        if name == "cli_registration_points":
            if len(old_ids - new_ids) != 78 or len(new_ids - old_ids) != 78:
                raise ValueError("Unexpected CLI registration surface change.")
        elif name == "package_sites":
            if len(old_ids - new_ids) != 187 or len(new_ids - old_ids) != 176:
                raise ValueError("Unexpected package site surface change.")
        elif name == "release_checks":
            if new_ids - old_ids != {WAVE1_RELEASE_CHECK} or old_ids - new_ids:
                raise ValueError("Unexpected release-check surface change.")
        elif old_ids != new_ids:
            raise ValueError(f"Unexpected {name} surface change.")


def _package_move(
    before: dict[str, object],
    after: dict[str, object],
    capability_id: str,
    transition: str,
) -> dict[str, object]:
    return {
        "old_id": before["site_id"],
        "new_id": after["site_id"],
        "capability_id": capability_id,
        "transition": transition,
        "expression_source_hash": before["expression_source_hash"],
        "candidate_kinds": before["candidate_kinds"],
    }


def _package_key(row: dict[str, object]) -> tuple[object, ...]:
    return (
        str(row["site_id"]).split(":", 1)[0],
        row.get("expression_source_hash"),
        tuple(cast(list[object], row.get("candidate_kinds") or [])),
        row.get("expression"),
    )


def _cli_key(row: dict[str, object]) -> tuple[object, ...]:
    return row.get("source"), row.get("owner"), row.get("function"), row.get("command")


def _group_rows(
    rows: list[dict[str, object]],
    key: Callable[[dict[str, object]], tuple[object, ...]],
) -> dict[tuple[object, ...], list[dict[str, object]]]:
    groups: dict[tuple[object, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        identity = key(row)
        groups[identity].append(row)
    for values in groups.values():
        values.sort(key=lambda row: (_integer(row.get("line")), _integer(row.get("column"))))
    return groups


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _surface_owners(rows: list[dict[str, object]], surface: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in rows:
        capability_id = str(row["capability_id"])
        surfaces = cast(dict[str, object], row["surfaces"])
        for identity in cast(list[object], surfaces[surface]):
            text = str(identity)
            if text in result:
                raise ValueError(f"Duplicate {surface} owner: {text}")
            result[text] = capability_id
    return result


def _inventory_ids(
    inventory: dict[str, object], name: str, identity_key: str
) -> set[str]:
    return {
        str(row[identity_key])
        for row in cast(list[dict[str, object]], inventory[name])
    }


def _rebind_state_exceptions(
    registry: dict[str, object], baseline_hash: str
) -> dict[str, object]:
    result = copy.deepcopy(registry)
    for row in cast(list[dict[str, object]], result["writer_overlap_exceptions"]):
        row["baseline_integrity_hash"] = baseline_hash
    result["integrity_hash"] = integrity_hash(result)
    return result


def _verify_applied(root: Path, plan: dict[str, object]) -> None:
    documents = {key: _read(root / path) for key, path in PATHS.items()}
    current = {
        "capability_registry_hash": documents["capabilities"]["integrity_hash"],
        "state_registry_hash": documents["state"]["integrity_hash"],
        "package_registry_hash": documents["packages"]["integrity_hash"],
        "waiver_registry_hash": documents["waivers"]["integrity_hash"],
        "catalog_hash": documents["catalog"]["integrity_hash"],
        "baseline_hash": documents["baseline"]["integrity_hash"],
        "package_projection_hash": documents["package_projection"]["integrity_hash"],
        "package_writer_policy_hash": documents["package_writer_policy"]["integrity_hash"],
        "state_policy_hash": documents["state_policy"]["integrity_hash"],
    }
    expected = {key: plan[key] for key in current}
    if current != expected:
        raise ValueError("Wave 1 migration outputs do not match the approved plan.")
    manifest = _read(root / MIGRATION_PATH)
    if manifest.get("integrity_hash") != plan["migration_manifest_hash"] or integrity_hash(manifest) != manifest.get("integrity_hash"):
        raise ValueError("Wave 1 migration manifest is invalid.")
    wave0 = evaluate_wave0(root)
    wave1 = evaluate_wave1(root, run_mypy=False)
    if wave0["status"] != "passed" or wave1["status"] != "passed":
        raise ValueError(
            "Wave 1 migration gates failed: "
            + ", ".join(
                [
                    *cast(list[str], wave0["blockers"]),
                    *cast(list[str], wave1["blockers"]),
                ]
            )
        )


def _target_applied(documents: dict[str, dict[str, object]], root: Path) -> bool:
    if not TARGET_HASHES or not (root / MIGRATION_PATH).is_file():
        return False
    manifest = _read(root / MIGRATION_PATH)
    if (
        manifest.get("integrity_hash") != TARGET_HASHES["migration_manifest_hash"]
        or integrity_hash(manifest) != manifest.get("integrity_hash")
    ):
        return False
    expected = {
        "capabilities": "capability_registry_hash",
        "state": "state_registry_hash",
        "packages": "package_registry_hash",
        "waivers": "waiver_registry_hash",
        "baseline": "baseline_hash",
        "catalog": "catalog_hash",
        "package_projection": "package_projection_hash",
        "package_writer_policy": "package_writer_policy_hash",
        "state_policy": "state_policy_hash",
    }
    for key, target in expected.items():
        document = documents[key]
        calculated = (
            package_document_hash(document)
            if key in {"package_projection", "package_writer_policy"}
            else integrity_hash(document)
        )
        if document.get("integrity_hash") != TARGET_HASHES[target] or calculated != document.get("integrity_hash"):
            return False
    registries = {
        key: documents[key]
        for key in ("capabilities", "state", "packages", "waivers")
    }
    current_catalog = build_wave0_catalog(root, registries=registries)
    baseline = documents["baseline"]
    if (
        current_catalog.get("integrity_hash") != documents["catalog"].get("integrity_hash")
        or baseline.get("dependency_baseline") != build_dependency_snapshot(root)
        or baseline.get("quality_freeze") != build_quality_snapshot(root)
    ):
        return False
    wave0 = evaluate_wave0(root)
    wave1 = evaluate_wave1(root, run_mypy=False)
    return wave0["status"] == "passed" and wave1["status"] == "passed"


def _approved_input_documents(root: Path) -> dict[str, dict[str, object]]:
    documents: dict[str, dict[str, object]] = {}
    for key, relative in PATHS.items():
        completed = subprocess.run(
            ["git", "show", f"{APPROVED_INPUT_COMMIT}:{relative}"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise ValueError(
                "Wave 1 migration requires the approved Wave 0 input commit."
            )
        value = json.loads(completed.stdout)
        if not isinstance(value, dict):
            raise ValueError(f"Expected an approved JSON object: {relative}")
        documents[key] = cast(dict[str, object], value)
    return documents


def _require_inputs(documents: dict[str, dict[str, object]]) -> None:
    for key, expected in INPUT_HASHES.items():
        document = documents[key]
        calculated = (
            package_document_hash(document)
            if key in {"package_projection", "package_writer_policy"}
            else integrity_hash(document)
        )
        if document.get("integrity_hash") != expected or calculated != expected:
            raise ValueError(f"Wave 1 migration rejected unexpected {key} input.")


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return cast(dict[str, object], value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate the approved Wave 0 surfaces to the v14.4 Wave 1 source layout."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    return migrate(Path(args.root).resolve(), apply=bool(args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
