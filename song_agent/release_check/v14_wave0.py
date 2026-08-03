from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import cast

from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.platform.contracts.packages import (
    _document_hash as _runtime_policy_hash,
    build_runtime_package_writer_policy,
    load_runtime_package_registry_projection,
    load_runtime_package_writer_policy,
    require_registered_package_type,
    validate_runtime_package_writer_policy,
)
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok
from song_agent.release_check.matrix import all_check_definitions
from song_agent.release_check.performance import CI_PROFILE_DURATION_BUDGET_SECONDS, PROFILE_BUDGET_WARNING_ONLY, PROFILE_DURATION_BUDGET_SECONDS
from song_agent.release_check.v14_wave0_catalog_model import BOUNDED_CONTEXTS, INVENTORY_IDENTITIES, inventory_identity_sets
from song_agent.release_check.v14_wave0_inventory import build_wave0_catalog
from song_agent.release_check.v14_wave0_package_inventory import (
    package_writer_contract_observations,
    package_writer_registry_blockers,
    unregistered_package_literal_blockers,
)
from song_agent.release_check.v14_wave0_ratchet import (
    dependency_regressions,
    quality_regressions,
    registry_field_snapshot,
    registry_regressions,
)
from song_agent.release_check.v14_wave0_registry import (
    REGISTRY_CONTRACTS,
    capability_surface_owner,
    load_wave0_registries,
    validate_wave0_registries,
)


CATALOG_PATH = "capability-catalog.json"
BASELINE_PATH = "architecture-v14.4-wave0-baseline.json"
BASELINE_PACKAGE_TYPE = "musicforge_v144_wave0_baseline"
_GUARDED_WRITER_PROBE = (
    "def put(document, value):\n document['package_type'] = "
    "_require_registered_package_type(value, writer_id='guard_probe.put')\n"
)
_REPORT_WRITER_ID = "song_agent.platform.verification.model.build_verification_report"
def build_wave0_baseline(
    root: Path,
    catalog: dict[str, object] | None = None,
    *,
    registries: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    current_catalog = catalog or build_wave0_catalog(root)
    registries = registries or load_wave0_registries(root)
    document: dict[str, object] = {
        "schema_version": 5,
        "package_type": BASELINE_PACKAGE_TYPE,
        "baseline_version": "14.3.5",
        "baseline_sha": "131258b4bcf9786bc155e3327a64836bf5aca037",
        "status": "frozen",
        "feature_freeze": {
            "business_features": "frozen",
            "allowed_changes": [
                "P0/P1",
                "security",
                "data-corruption",
                "compatibility-regression",
                "architecture-debt",
            ],
            "forbidden_surface_growth": ["store", "cli", "api", "studio_panel", "package"],
        },
        "surface_freeze": {
            "identity_sets": inventory_identity_sets(cast(dict[str, object], current_catalog["inventory"])),
            "catalog_inventory_hash": current_catalog["inventory_hash"],
        },
        "registry_contracts": REGISTRY_CONTRACTS,
        "registry_freeze": registry_field_snapshot(registries),
        "dependency_baseline": build_dependency_snapshot(root),
        "quality_freeze": build_quality_snapshot(root),
    }
    document["integrity_hash"] = integrity_hash(document)
    return document
def evaluate_wave0(
    root: Path,
    *,
    catalog_path: str = CATALOG_PATH,
    baseline_path: str = BASELINE_PATH,
) -> dict[str, object]:
    blockers: list[str] = []
    catalog = _read_object(root / catalog_path)
    baseline = _read_object(root / baseline_path)
    registries = load_wave0_registries(root)
    current = build_wave0_catalog(root)
    if (
        catalog.get("package_type") != "musicforge_v144_capability_catalog"
        or catalog.get("schema_version") != 4
        or not integrity_ok(catalog)
    ):
        blockers.append("v144_wave0_catalog_integrity")
    if baseline.get("package_type") != BASELINE_PACKAGE_TYPE or baseline.get("schema_version") != 5 or not integrity_ok(baseline):
        blockers.append("v144_wave0_baseline_integrity")
    if baseline.get("registry_contracts") != REGISTRY_CONTRACTS:
        blockers.append("v144_wave0_registry_contracts")
    if catalog != current:
        blockers.append("v144_wave0_catalog_current")
    blockers.extend(
        validate_wave0_registries(
            registries,
            root=root,
            baseline_integrity_hash=str(baseline.get("integrity_hash") or ""),
        )
    )
    blockers.extend(_runtime_composition_blockers(root))
    blockers.extend(_catalog_blockers(current, registries))
    blockers.extend(_surface_blockers(current, baseline))
    blockers.extend(_package_writer_contract_probe())
    blockers.extend(_runtime_package_policy_probe(registries["packages"]))
    blockers.extend(
        registry_regressions(
            cast(dict[str, object], baseline.get("registry_freeze") or {}),
            registry_field_snapshot(registries),
            registries["waivers"],
            baseline_integrity_hash=str(baseline.get("integrity_hash") or ""),
        )
    )
    blockers.extend(
        dependency_regressions(
            cast(dict[str, object], baseline.get("dependency_baseline") or {}),
            build_dependency_snapshot(root),
        )
    )
    blockers.extend(
        quality_regressions(
            cast(dict[str, object], baseline.get("quality_freeze") or {}),
            build_quality_snapshot(root),
        )
    )
    blockers = sorted(set(blockers))
    return {
        "schema_version": 5,
        "package_type": "musicforge_v144_wave0_verification",
        "status": "passed" if not blockers else "failed",
        "blockers": blockers,
        "summary": cast(dict[str, object], current.get("summary") or {}),
    }
def run_v144_wave0_catalog_baseline_smoke(root: Path) -> tuple[bool, str]:
    report = evaluate_wave0(root)
    return report["status"] == "passed", json.dumps(report, ensure_ascii=False, sort_keys=True)
def _package_writer_contract_probe() -> list[str]:
    sources = {
        "helpers": 'class Writer:\n def put(self, document, value):\n  document["package_type"] = value\n'
        'def put(document, value):\n document["package_type"] = value\ndef factory():\n return Writer()\n',
        "bridge": "from helpers import *\n",
        "caller": 'import pkg.helpers\nfrom bridge import Writer, put\nclass Child(Writer):\n pass\n'
        'Child().put({}, "musicforge_inherited_new")\npkg.helpers.Writer().put({}, "musicforge_dotted_new")\n'
        'put({}, "musicforge_wildcard_new")\nfactory().put({}, "musicforge_factory_new")\n',
    }
    trees: dict[str, ast.AST] = {name: ast.parse(source) for name, source in sources.items()}
    registry: dict[str, object] = {"writer_contracts": [], "package_type_sets": [{"type_set_id": "wave0", "package_types": []}]}
    rows = package_writer_contract_observations(
        trees,
        {name: f"{name}.py" for name in trees},
        sources,
    )
    base_passed = bool(package_writer_registry_blockers(rows, registry)) and len(
        unregistered_package_literal_blockers(trees, registry)
    ) == 4
    guard_attacks = (
        "from song_agent.platform.contracts.packages import require_registered_package_type as "
        "_require_registered_package_type\nfrom fake import *\n",
        "from song_agent.platform.contracts.packages import (require_registered_package_type as "
        "_require_registered_package_type, fake as _require_registered_package_type)\n",
    )
    binding_passed = all(
        not package_writer_contract_observations(
            {"guard_probe": ast.parse(source + _GUARDED_WRITER_PROBE)},
            {"guard_probe": "guard_probe.py"},
            {"guard_probe": source + _GUARDED_WRITER_PROBE},
        )[0]["guarded"]
        for source in guard_attacks
    )
    base_source = (
        "from song_agent.platform.contracts.packages import require_registered_package_type as "
        "_require_registered_package_type\n"
        + _GUARDED_WRITER_PROBE
    )
    base_row = package_writer_contract_observations(
        {"guard_probe": ast.parse(base_source)},
        {"guard_probe": "guard_probe.py"},
        {"guard_probe": base_source},
    )[0]
    frozen_contract = {key: value for key, value in base_row.items() if key != "guarded"}
    semantic_attacks = (
        "def fake_guard(value, *, writer_id):\n return value\n"
        "globals()['_require_registered_package_type'] = fake_guard\n",
        "def fake_guard(value, *, writer_id):\n return value\n"
        "globals().update({'_require_registered_package_type': fake_guard})\n",
        "import sys\ndef fake_guard(value, *, writer_id):\n return value\n"
        "setattr(sys.modules[__name__], '_require_registered_package_type', fake_guard)\n",
    )
    semantic_passed = all(
        any(
            blocker.endswith(":module_source_hash")
            for blocker in package_writer_registry_blockers(
                package_writer_contract_observations(
                    {"guard_probe": ast.parse(base_source + attack)},
                    {"guard_probe": "guard_probe.py"},
                    {"guard_probe": base_source + attack},
                ),
                {"writer_contracts": [frozen_contract]},
            )
        )
        for attack in semantic_attacks
    )
    return [] if base_passed and binding_passed and semantic_passed else ["v144_wave0_package_writer_contract_probe"]
def _runtime_package_policy_probe(registry: dict[str, object]) -> list[str]:
    projection = load_runtime_package_registry_projection()
    policy = build_runtime_package_writer_policy(registry)
    writer = _row(policy["writer_contracts"], "writer_id", _REPORT_WRITER_ID)
    type_set = _row(policy["package_type_sets"], "type_set_id", writer.get("allowed_type_set_id"))
    values = cast(list[object], type_set["package_types"])
    kinds = cast(dict[str, object], type_set["package_type_kinds"])
    values.append("totally_unregistered_report")
    kinds["totally_unregistered_report"] = "report"
    policy["integrity_hash"] = _runtime_policy_hash(policy)
    resigned_blocked = bool(validate_runtime_package_writer_policy(policy, projection))

    public_policy = load_runtime_package_writer_policy()
    public_projection = load_runtime_package_registry_projection()
    public_writer = _row(public_policy["writer_contracts"], "writer_id", _REPORT_WRITER_ID)
    public_set = _row(public_policy["package_type_sets"], "type_set_id", public_writer.get("allowed_type_set_id"))
    cast(list[object], public_set["package_types"]).append("runtime_cache_injection_report")
    public_writer["nullable"] = True
    projection_set = _row(public_projection["package_type_sets"], "type_set_id", public_writer.get("allowed_type_set_id"))
    cast(list[object], projection_set["package_types"]).append("runtime_cache_injection_report")
    try:
        require_registered_package_type("runtime_cache_injection_report", writer_id=_REPORT_WRITER_ID)
    except ValueError:
        cache_mutation_blocked = True
    else:
        cache_mutation_blocked = False
    fresh_policy = load_runtime_package_writer_policy()
    fresh_projection = load_runtime_package_registry_projection()
    fresh_payload = json.dumps([fresh_policy, fresh_projection], ensure_ascii=False, sort_keys=True)
    fresh_documents_clean = "runtime_cache_injection_report" not in fresh_payload
    passed = resigned_blocked and cache_mutation_blocked and fresh_documents_clean
    return [] if passed else ["v144_wave0_runtime_package_policy_resign_probe"]
def _row(rows: object, key: str, value: object) -> dict[str, object]:
    return next(row for row in cast(list[dict[str, object]], rows) if row.get(key) == value)
def _runtime_composition_blockers(root: Path) -> list[str]:
    from song_agent.interfaces.api.server import create_server, runtime_state_authority_blockers

    try:
        server = create_server("127.0.0.1", 0)
    except RuntimeError as exc:
        return [f"v144_wave0_state_runtime_startup:{exc}"]
    try:
        return runtime_state_authority_blockers(server, root)
    finally:
        server.server_close()
def build_dependency_snapshot(root: Path) -> dict[str, object]:
    snapshot = cast(dict[str, object], build_architecture_snapshot(root))
    modules = {str(row["module"]): row for row in cast(list[dict[str, object]], snapshot["modules"])}
    cross_domain: list[dict[str, object]] = []
    interface_domain: list[dict[str, object]] = []
    for pair in cast(list[dict[str, object]], snapshot["import_pairs"]):
        importer = modules[str(pair["importer"])]
        imported = modules[str(pair["imported"])]
        importer_context = str(importer.get("context") or "")
        imported_context = str(imported.get("context") or "")
        if (
            importer.get("layer") == "domain"
            and imported.get("layer") == "domain"
            and importer_context in BOUNDED_CONTEXTS
            and imported_context in BOUNDED_CONTEXTS
            and importer_context != imported_context
        ):
            cross_domain.append(pair)
        if importer.get("layer") == "interface" and imported.get("layer") == "domain":
            interface_domain.append(pair)
    return {
        "module_count": snapshot["module_count"],
        "total_source_lines": snapshot["total_source_lines"],
        "production_cycle_count": len(cast(list[object], snapshot["cycles"])),
        "boundary_violation_count": len(cast(list[object], snapshot["boundary_violations"])),
        "active_to_compatibility_import_count": len(cast(list[object], snapshot["active_to_compatibility_imports"])),
        "cross_domain_imports": sorted(cross_domain, key=_edge_key),
        "interface_domain_imports": sorted(interface_domain, key=_edge_key),
    }
def build_quality_snapshot(root: Path) -> dict[str, object]:
    quality = _read_object(root / "architecture-v14-quality.json")
    architecture = _read_object(root / "architecture-v14-policy.json")
    return {
        "typing": quality.get("typing") or {},
        "complexity": quality.get("complexity") or {},
        "mypy": quality.get("mypy") or {},
        "module_size_debt": quality.get("module_size_debt") or [],
        "coverage_minimums": cast(dict[str, object], quality.get("coverage") or {}).get("minimum_percent") or {},
        "architecture_limits": architecture.get("limits") or {},
        "profile_duration_budgets": dict(PROFILE_DURATION_BUDGET_SECONDS),
        "ci_profile_duration_budgets": dict(CI_PROFILE_DURATION_BUDGET_SECONDS),
        "profile_budget_warning_only": sorted(PROFILE_BUDGET_WARNING_ONLY),
        "check_duration_budgets": {
            definition.check_id: definition.duration_budget_seconds
            for definition in all_check_definitions()
            if definition.duration_budget_seconds is not None
        },
    }
def _catalog_blockers(catalog: dict[str, object], registries: dict[str, dict[str, object]]) -> list[str]:
    blockers: list[str] = []
    blockers.extend(
        package_writer_registry_blockers(
            cast(list[dict[str, object]], catalog.get("package_writer_contracts") or []),
            registries["packages"],
        )
    )
    blockers.extend(str(value) for value in cast(list[object], catalog.get("package_literal_blockers") or []))
    inventory = cast(dict[str, object], catalog.get("inventory") or {})
    declared_owners = capability_surface_owner(registries["capabilities"])
    for key, identity_key in INVENTORY_IDENTITIES.items():
        rows = cast(list[dict[str, object]], inventory.get(key) or [])
        observed = {str(row.get(identity_key) or "") for row in rows}
        for identity in sorted(set(declared_owners[key]) - observed):
            blockers.append(f"v144_wave0_declared_surface_missing:{key}:{identity}")
        for row in rows:
            identity = str(row.get(identity_key) or "")
            if not str(row.get("capability_id") or ""):
                blockers.append(f"v144_wave0_unregistered:{key}:{identity}")
            if not str(row.get("bounded_context") or ""):
                blockers.append(f"v144_wave0_unclassified:{key}:{identity}")
    state = {str(row["store_id"]): row for row in cast(list[dict[str, object]], registries["state"]["entries"])}
    for row in cast(list[dict[str, object]], inventory.get("stores") or []):
        store_id = str(row["store_id"])
        declared = state.get(store_id)
        if declared is None or row.get("observed_source") != declared.get("source"):
            blockers.append(f"v144_wave0_state_source:{store_id}")
    package_registry = registries["packages"]
    package_types = {str(row["package_type"]): row for row in cast(list[dict[str, object]], package_registry["package_types"])}
    for row in cast(list[dict[str, object]], inventory.get("package_types") or []):
        declared = package_types.get(str(row["package_type"]))
        if (
            declared is None
            or row.get("sources") != declared.get("sources")
            or row.get("schema_versions") != declared.get("schema_versions")
            or row.get("schema_declaration") != declared.get("schema_declaration")
        ):
            blockers.append(f"v144_wave0_package_sources:{row['package_type']}")
    package_sites = {str(row["site_id"]): row for row in cast(list[dict[str, object]], package_registry["dynamic_sites"])}
    for row in cast(list[dict[str, object]], inventory.get("package_sites") or []):
        declared = package_sites.get(str(row["site_id"]))
        if (
            declared is None
            or any(
                row.get(field) != declared.get(field)
                for field in (
                    "expression",
                    "expression_source_hash",
                    "scope_source_hash",
                    "line",
                    "column",
                    "end_line",
                    "end_column",
                    "candidate_kinds",
                )
            )
        ):
            blockers.append(f"v144_wave0_package_site:{row['site_id']}")
    return blockers
def _surface_blockers(current: dict[str, object], baseline: dict[str, object]) -> list[str]:
    freeze = cast(dict[str, object], baseline.get("surface_freeze") or {})
    frozen_sets = cast(dict[str, object], freeze.get("identity_sets") or {})
    current_sets = inventory_identity_sets(cast(dict[str, object], current["inventory"]))
    blockers: list[str] = []
    for key, current_values in current_sets.items():
        frozen = {str(value) for value in cast(list[object], frozen_sets.get(key) or [])}
        for identity in sorted(set(current_values) - frozen):
            blockers.append(f"v144_wave0_surface_growth:{key}:{identity}")
    return blockers
def _edge_key(row: dict[str, object]) -> tuple[str, str]:
    return str(row.get("importer") or ""), str(row.get("imported") or "")
def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return cast(dict[str, object], value)
