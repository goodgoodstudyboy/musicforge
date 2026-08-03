from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import types
import venv
from pathlib import Path

import pytest

import tools.update_v144_wave0_catalog as wave0_updater

from song_agent.platform.persistence.file_artifacts import (
    _runtime_state_freeze,
    STATE_POLICY_RESOURCE,
    build_runtime_state_authority_policy,
    load_runtime_state_authority_policy,
    validate_runtime_state_authority_policy,
)
from song_agent.platform.persistence.repository import validate_runtime_state_composition, validated_overlap_exceptions
from song_agent.platform.contracts.packages import (
    APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH,
    APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH,
    PACKAGE_WRITER_ATTACK_CORPUS,
    _document_hash as _runtime_policy_hash,
    _runtime_package_writer_index,
    build_runtime_package_writer_policy,
    load_runtime_package_registry_projection,
    load_runtime_package_writer_policy,
    require_registered_package_type,
    validate_runtime_package_registry_projection,
    validate_runtime_package_writer_policy,
)
from song_agent.platform.verification.model import build_verification_report
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok
from song_agent.release_check.v14_wave0 import (
    _catalog_blockers,
    _surface_blockers,
    evaluate_wave0,
)
from song_agent.release_check.v14_wave0_inventory import _normalize_dynamic_site_ids, build_wave0_catalog
from song_agent.release_check.v14_wave0_package_inventory import (
    package_writer_contract_observations,
    package_writer_registry_blockers,
    unregistered_package_literal_blockers,
)
from song_agent.release_check.v14_wave0_package_scan import package_observations
from song_agent.release_check.v14_wave0_source import (
    normalize_source_text,
    source_fragment_hash,
    source_site_id,
    source_text_hash,
)
from song_agent.release_check.v14_wave0_ratchet import (
    dependency_regressions,
    quality_regressions,
    registry_field_snapshot,
    registry_regressions,
    registry_value_hash,
)
from song_agent.release_check.v14_wave0_registry import (
    REGISTRY_CONTRACTS,
    _waiver_checks,
    load_wave0_registries,
    validate_wave0_registries,
)
from song_agent.release_check.v14_wave0_state_registry import (
    namespace_identity_hash,
    validate_runtime_state_namespaces,
)
from song_agent.interfaces.api.server import create_server, runtime_state_authority_blockers
from tools.merge_v144_wave0_coverage import WAVE0_CHANGED_SOURCES, merge_coverage_reports
from tools.migrate_v144_runtime_state_anchor import TARGET_HASHES as RUNTIME_ANCHOR_TARGET_HASHES
from tools.update_v144_wave0_catalog import (
    _baseline_regressions,
    build_runtime_package_registry_projection,
    _frozen_baseline_schema_current,
    _rebind_state_exceptions,
    _render_current_architecture_summary,
    _surface_additions,
    update,
)


ROOT = Path(__file__).resolve().parents[1]
UPDATER_SANDBOX_FILES = (
    "architecture-v14.4-capability-registry.json",
    "architecture-v14.4-package-schema-registry.json",
    "architecture-v14.4-state-authority-registry.json",
    "architecture-v14.4-wave0-baseline.json",
    "architecture-v14.4-wave0-waivers.json",
    "capability-catalog.json",
    "docs/architecture/CURRENT.md",
    "song_agent/platform/contracts/runtime-package-registry.json",
    "song_agent/platform/contracts/runtime-package-writer-policy.json",
    "song_agent/platform/persistence/runtime-state-authority-policy.json",
)


def _scan_packages(source: str, path: str) -> list[dict[str, object]]:
    return package_observations(ast.parse(source), path, source)


def _scan_writers(sources: dict[str, str]) -> list[dict[str, object]]:
    return package_writer_contract_observations(
        {module: ast.parse(source) for module, source in sources.items()},
        {module: f"{module}.py" for module in sources},
        sources,
    )


@pytest.fixture(scope="module")
def registries() -> dict[str, dict[str, object]]:
    return load_wave0_registries(ROOT)


@pytest.fixture(scope="module")
def catalog() -> dict[str, object]:
    return json.loads((ROOT / "capability-catalog.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def baseline() -> dict[str, object]:
    return json.loads((ROOT / "architecture-v14.4-wave0-baseline.json").read_text(encoding="utf-8"))


def test_wave0_registries_are_valid_and_catalog_is_current(registries: dict[str, dict[str, object]], catalog: dict[str, object]) -> None:
    current = build_wave0_catalog(ROOT)

    assert validate_wave0_registries(registries, root=ROOT) == []
    assert current == catalog
    assert integrity_ok(catalog)
    assert current["summary"] == {
        "api_routes": 117,
        "capability_count": 146,
        "cli_commands": 173,
        "cli_registration_points": 240,
        "package_sites": 2687,
        "package_types": 542,
        "package_writer_contracts": 35,
        "packages": 256,
        "release_checks": 203,
        "schemas": 246,
        "state_adapters": 5,
        "state_authorities": 95,
        "stores": 132,
        "studio_panels": 10,
        "verifiers": 101,
    }


def test_canonical_capability_links_store_public_entries_and_verifier(
    registries: dict[str, dict[str, object]],
) -> None:
    rows = {row["capability_id"]: row for row in registries["capabilities"]["capabilities"] if isinstance(row, dict)}
    capability = rows["trust.public-trust-center"]
    surfaces = capability["surfaces"]

    assert isinstance(surfaces, dict)
    assert surfaces["stores"] == ["song_agent.domains.trust.public_trust_center.PublicTrustCenterStore"]
    assert "public-trust-center" in surfaces["cli_commands"]
    assert "* /api/public-trust-centers" in surfaces["api_routes"]
    assert any(str(value).endswith("verify_public_trust_center_package") for value in surfaces["verifiers"])
    assert surfaces["package_types"]
    assert capability["tests"]


def test_every_capability_has_governance_declarations(
    registries: dict[str, dict[str, object]],
) -> None:
    capabilities = registries["capabilities"]["capabilities"]
    assert isinstance(capabilities, list)
    for row in capabilities:
        assert isinstance(row, dict)
        assert row["owner"] and row["source_of_truth"] and row["classification"]
        assert isinstance(row["depends_on"], list)
        assert row["dependency_declaration"]["reason"]
        assert row["tests"]
        assert row["migration"]["status"] in {"declared", "not_applicable"}
        assert row["migration"]["reason"]
        assert row["rollback"]["status"] in {"declared", "not_applicable"}
        assert row["rollback"]["reason"]


@pytest.mark.parametrize("field", ["tests", "migration", "rollback"])
def test_empty_capability_governance_field_is_blocked(registries: dict[str, dict[str, object]], field: str) -> None:
    changed = copy.deepcopy(registries)
    capability = changed["capabilities"]["capabilities"][0]
    assert isinstance(capability, dict)
    capability[field] = [] if field == "tests" else {}
    _resign(changed["capabilities"])

    blockers = validate_wave0_registries(changed, root=ROOT)

    assert any(f"capability_{field}" in blocker for blocker in blockers)


def test_state_authority_registry_uses_physical_namespaces(
    registries: dict[str, dict[str, object]],
) -> None:
    entries = registries["state"]["entries"]
    assert isinstance(entries, list)
    roles = {str(row["role"]) for row in entries if isinstance(row, dict)}
    namespaces = [
        (namespace["root_authority_id"], namespace["relative_path_template"])
        for row in entries
        if isinstance(row, dict) and row["access"]["write"]
        for namespace in row["physical_namespaces"]
    ]

    assert {"authority", "projection", "workflow", "evidence", "adapter"} <= roles
    assert all("Store" not in str(value[0]) for value in namespaces)
    assert ("workspace.musicforge", "batches/{batch_id}") in namespaces
    assert any(relative == "data/nodes/{node_name}.json" for _, relative in namespaces)
    assert all(
        isinstance(namespace["path_evidence"], dict)
        for row in entries
        for namespace in row["physical_namespaces"]
    )


def test_duplicate_physical_writer_namespace_is_blocked(
    registries: dict[str, dict[str, object]],
) -> None:
    changed = copy.deepcopy(registries)
    entries = changed["state"]["entries"]
    assert isinstance(entries, list)
    writers = [row for row in entries if isinstance(row, dict) and row["access"]["write"]]
    roots = changed["state"]["roots"]
    assert isinstance(roots, list)
    roots.append(
        {
            "root_authority_id": "test.collision",
            "kind": "filesystem",
            "path_template": "{configured:test_collision}",
            "composition_binding": "test:collision",
            "runtime_configurable": True,
            "disjointness": "runtime_required",
        }
    )
    writers[0]["physical_namespaces"] = [
        {
            "root_authority_id": "test.collision",
            "relative_path_template": "same/path",
        }
    ]
    writers[1]["physical_namespaces"] = copy.deepcopy(writers[0]["physical_namespaces"])
    _resign(changed["state"])

    blockers = validate_wave0_registries(changed, root=ROOT)

    assert any("v144_wave0_state_writer_overlap:test.collision" in blocker for blocker in blockers)


def test_parent_child_physical_writer_overlap_is_blocked(
    registries: dict[str, dict[str, object]],
) -> None:
    changed = copy.deepcopy(registries)
    writers = [row for row in changed["state"]["entries"] if row["access"]["write"]]
    changed["state"]["roots"].append(
        {
            "root_authority_id": "test.parent",
            "kind": "filesystem",
            "path_template": "{configured:test_parent}",
            "composition_binding": "test:parent",
            "runtime_configurable": True,
            "disjointness": "runtime_required",
        }
    )
    writers[0]["physical_namespaces"] = [{"root_authority_id": "test.parent", "relative_path_template": "items"}]
    writers[1]["physical_namespaces"] = [{"root_authority_id": "test.parent", "relative_path_template": "items/child"}]
    _resign(changed["state"])

    blockers = validate_wave0_registries(changed, root=ROOT)

    assert any("v144_wave0_state_writer_overlap:test.parent" in blocker for blocker in blockers)


def test_runtime_composition_rejects_distinct_roots_resolving_to_same_path(tmp_path: Path) -> None:
    registry = {
        "roots": [
            {"root_authority_id": "root.a"},
            {"root_authority_id": "root.b"},
        ],
        "entries": [
            {
                "store_id": "a.Store",
                "access": {"write": True},
                "physical_namespaces": [{"root_authority_id": "root.a", "relative_path_template": "."}],
            },
            {
                "store_id": "b.Store",
                "access": {"write": True},
                "physical_namespaces": [{"root_authority_id": "root.b", "relative_path_template": "child"}],
            },
        ],
    }

    blockers = validate_runtime_state_namespaces(registry, {"root.a": tmp_path, "root.b": tmp_path})

    assert any("v144_wave0_state_runtime_writer_overlap" in blocker for blocker in blockers)


def test_empty_runtime_registry_is_fail_closed(tmp_path: Path) -> None:
    assert "v144_wave0_state_runtime_registry_integrity" in validate_runtime_state_composition({}, object(), tmp_path)


def test_current_state_registry_runtime_composition_is_disjoint(registries: dict[str, dict[str, object]], tmp_path: Path) -> None:
    roots = registries["state"]["roots"]
    assert isinstance(roots, list)
    resolved = {str(row["root_authority_id"]): tmp_path / f"root-{index:03d}" for index, row in enumerate(roots) if isinstance(row, dict)}

    assert validate_runtime_state_namespaces(registries["state"], resolved) == []


def test_packaged_runtime_state_policy_is_current(registries: dict[str, dict[str, object]], baseline: dict[str, object]) -> None:
    expected = build_runtime_state_authority_policy(registries["state"], baseline)
    registry, baseline_hash, blockers = load_runtime_state_authority_policy()

    assert blockers == []
    assert registry == registries["state"]
    assert baseline_hash == baseline["integrity_hash"]
    assert validate_runtime_state_authority_policy(expected) == []


def test_runtime_state_policy_loader_fails_closed_when_package_data_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_resource(_package: str) -> object:
        raise FileNotFoundError

    monkeypatch.setattr("song_agent.platform.persistence.file_artifacts.resources.files", missing_resource)

    registry, baseline_hash, blockers = load_runtime_state_authority_policy()

    assert registry == {}
    assert baseline_hash == ""
    assert blockers == ["v144_wave0_state_runtime_policy_missing"]


@pytest.mark.parametrize(
    "attack",
    [
        "empty",
        "wrong_type",
        "wrong_schema",
        "tamper",
        "baseline_mismatch",
        "baseline_type",
        "policy_binding",
        "documents",
        "exception_binding",
    ],
)
def test_runtime_state_policy_fails_closed(
    registries: dict[str, dict[str, object]], baseline: dict[str, object], attack: str
) -> None:
    policy = build_runtime_state_authority_policy(copy.deepcopy(registries["state"]), copy.deepcopy(baseline))
    registry = policy["state_registry"]
    frozen = policy["wave0_baseline"]
    assert isinstance(registry, dict) and isinstance(frozen, dict)
    if attack == "empty":
        registry["roots"] = []
        registry["entries"] = []
        _resign(registry)
        policy["state_registry_integrity_hash"] = registry["integrity_hash"]
        _resign(policy)
    elif attack == "wrong_type":
        registry["package_type"] = "musicforge_wrong"
        _resign(registry)
        policy["state_registry_integrity_hash"] = registry["integrity_hash"]
        _resign(policy)
    elif attack == "wrong_schema":
        registry["schema_version"] = 0
        _resign(registry)
        policy["state_registry_integrity_hash"] = registry["integrity_hash"]
        _resign(policy)
    elif attack == "tamper":
        registry["entries"] = []
    elif attack == "baseline_mismatch":
        frozen["registry_freeze"]["state"] = {}
        _resign(frozen)
        policy["baseline_integrity_hash"] = frozen["integrity_hash"]
        _resign(policy)
    elif attack == "baseline_type":
        frozen["package_type"] = "musicforge_wrong"
        _resign(frozen)
        policy["baseline_integrity_hash"] = frozen["integrity_hash"]
        _resign(policy)
    elif attack == "policy_binding":
        policy["state_registry_integrity_hash"] = "f" * 64
        _resign(policy)
    elif attack == "documents":
        policy["state_registry"] = []
        _resign(policy)
    else:
        registry["writer_overlap_exceptions"][0]["baseline_integrity_hash"] = "f" * 64
        _resign(registry)
        policy["state_registry_integrity_hash"] = registry["integrity_hash"]
        _resign(policy)

    assert validate_runtime_state_authority_policy(policy)


def test_runtime_state_policy_rejects_consistent_full_resign(
    registries: dict[str, dict[str, object]], baseline: dict[str, object]
) -> None:
    policy = build_runtime_state_authority_policy(copy.deepcopy(registries["state"]), copy.deepcopy(baseline))
    registry = policy["state_registry"]
    frozen = policy["wave0_baseline"]
    assert isinstance(registry, dict) and isinstance(frozen, dict)
    entries = registry["entries"]
    assert isinstance(entries, list) and isinstance(entries[0], dict)
    entries[0]["entity"] = f"{entries[0].get('entity')}_forged"
    freeze = frozen["registry_freeze"]
    assert isinstance(freeze, dict)
    freeze.update(_runtime_state_freeze(registry))
    _resign(frozen)
    exceptions = registry["writer_overlap_exceptions"]
    assert isinstance(exceptions, list)
    for row in exceptions:
        assert isinstance(row, dict)
        row["baseline_integrity_hash"] = frozen["integrity_hash"]
    _resign(registry)
    policy["state_registry_integrity_hash"] = registry["integrity_hash"]
    policy["baseline_integrity_hash"] = frozen["integrity_hash"]
    _resign(policy)

    assert "v144_wave0_state_runtime_policy_integrity" in validate_runtime_state_authority_policy(policy)


def test_runtime_anchor_migration_targets_match_frozen_documents() -> None:
    documents = {
        "capability_registry_hash": "architecture-v14.4-capability-registry.json",
        "state_registry_hash": "architecture-v14.4-state-authority-registry.json",
        "package_registry_hash": "architecture-v14.4-package-schema-registry.json",
        "waiver_registry_hash": "architecture-v14.4-wave0-waivers.json",
        "catalog_hash": "capability-catalog.json",
        "baseline_hash": "architecture-v14.4-wave0-baseline.json",
        "package_projection_hash": "song_agent/platform/contracts/runtime-package-registry.json",
        "package_writer_policy_hash": "song_agent/platform/contracts/runtime-package-writer-policy.json",
        "state_policy_hash": "song_agent/platform/persistence/runtime-state-authority-policy.json",
    }
    for target, path in documents.items():
        document = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert RUNTIME_ANCHOR_TARGET_HASHES[target] == document["integrity_hash"]
    assert RUNTIME_ANCHOR_TARGET_HASHES["package_registry_hash"] == APPROVED_PACKAGE_REGISTRY_INTEGRITY_HASH
    assert RUNTIME_ANCHOR_TARGET_HASHES["package_projection_hash"] == APPROVED_PACKAGE_REGISTRY_PROJECTION_HASH
    assert RUNTIME_ANCHOR_TARGET_HASHES["state_policy_hash"] == STATE_POLICY_RESOURCE[1]


def test_overlap_exceptions_expire_at_v144(
    registries: dict[str, dict[str, object]], baseline: dict[str, object]
) -> None:
    state = registries["state"]
    roots = {str(row["root_authority_id"]): row for row in state["roots"]}
    blockers: list[str] = []

    validated_overlap_exceptions(
        state,
        roots,
        blockers,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
        current_version="14.4.0",
    )

    assert any("v144_wave0_state_overlap_exception_approval" in blocker for blocker in blockers)


def test_built_wheel_loads_runtime_policies_outside_repository(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copytree(
        ROOT / "song_agent",
        source / "song_agent",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    dist = tmp_path / "dist"
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(dist)],
        cwd=source,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(dist.glob("*.whl"))
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    clean_environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    doctor = subprocess.run(
        [str(python), "-m", "song_agent.cli", "doctor"],
        cwd=outside,
        env=clean_environment,
        check=True,
        capture_output=True,
        text=True,
    )
    server = subprocess.run(
        [
            str(python),
            "-c",
            "from song_agent.interfaces.api.server import create_server; s=create_server('127.0.0.1', 0); s.server_close()",
        ],
        cwd=outside,
        env=clean_environment,
        check=True,
        capture_output=True,
        text=True,
    )
    package_policy = subprocess.run(
        [
            str(python),
            "-c",
            (
                "from song_agent.platform.contracts.packages import "
                "RUNTIME_PACKAGE_WRITER_POLICY_RESOURCE,_document_hash,load_runtime_package_writer_policy,"
                "require_registered_package_type;from importlib import resources;from pathlib import Path;import json;"
                "p=load_runtime_package_writer_policy();w=p['writer_contracts'][0];"
                "s=next(x for x in p['package_type_sets'] if x['type_set_id']==w['allowed_type_set_id']);"
                "assert require_registered_package_type(s['package_types'][0],writer_id=w['writer_id']);"
                "\ntry: require_registered_package_type('musicforge_unregistered_wheel_attack',writer_id=w['writer_id'])"
                "\nexcept ValueError: print('package writer runtime: ok')"
                "\nelse: raise SystemExit('unregistered package type accepted')"
                "\nw=next(x for x in p['writer_contracts'] if x['writer_id']=='song_agent.platform.verification.model.build_verification_report')"
                "\ns=next(x for x in p['package_type_sets'] if x['type_set_id']==w['allowed_type_set_id'])"
                "\ns['package_types'].append('totally_unregistered_report')"
                "\ns['package_type_kinds']['totally_unregistered_report']='report'"
                "\np['integrity_hash']=_document_hash(p)"
                "\npath=Path(str(resources.files('song_agent.platform.contracts').joinpath(RUNTIME_PACKAGE_WRITER_POLICY_RESOURCE)))"
                "\npath.write_text(json.dumps(p),encoding='utf-8')"
                "\ntry: load_runtime_package_writer_policy()"
                "\nexcept RuntimeError: print('resigned package policy: rejected')"
                "\nelse: raise SystemExit('resigned package policy accepted')"
            ),
        ],
        cwd=outside,
        env=clean_environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "state authority runtime: ok" in doctor.stdout
    assert server.returncode == 0
    assert "package writer runtime: ok" in package_policy.stdout
    assert "resigned package policy: rejected" in package_policy.stdout


def test_state_path_evidence_rewrite_is_blocked(
    registries: dict[str, dict[str, object]],
) -> None:
    changed = copy.deepcopy(registries)
    changed["state"]["entries"][0]["physical_namespaces"][0]["path_evidence"]["expression_source_hash"] = "f" * 64
    _resign(changed["state"])

    blockers = validate_wave0_registries(changed, root=ROOT)

    assert any("v144_wave0_state_path_evidence_current" in blocker for blocker in blockers)


def test_resigned_invented_state_path_is_blocked(registries: dict[str, dict[str, object]]) -> None:
    changed = copy.deepcopy(registries)
    namespace = changed["state"]["entries"][0]["physical_namespaces"][0]
    namespace["relative_path_template"] = "invented/path/not/from/source"
    namespace["path_evidence"]["relative_path_template_hash"] = hashlib.sha256(
        namespace["relative_path_template"].encode("utf-8")
    ).hexdigest()
    _resign(changed["state"])

    blockers = validate_wave0_registries(changed, root=ROOT)

    assert any("v144_wave0_state_path_evidence_current" in blocker for blocker in blockers)


def test_resigned_state_path_cannot_insert_unproven_static_segment(
    registries: dict[str, dict[str, object]],
) -> None:
    changed = copy.deepcopy(registries)
    namespace = changed["state"]["entries"][0]["physical_namespaces"][0]
    namespace["relative_path_template"] = "batches/x/{batch_id}"
    namespace["path_evidence"]["relative_path_template_hash"] = hashlib.sha256(
        namespace["relative_path_template"].encode("utf-8")
    ).hexdigest()
    _resign(changed["state"])

    blockers = validate_wave0_registries(changed, root=ROOT)

    assert any("v144_wave0_state_path_evidence_current" in blocker for blocker in blockers)


def test_overlap_exception_cannot_be_rebound_to_another_namespace(
    registries: dict[str, dict[str, object]], baseline: dict[str, object]
) -> None:
    changed = copy.deepcopy(registries)
    exception = changed["state"]["writer_overlap_exceptions"][0]
    entry = next(
        row for row in changed["state"]["entries"] if row["store_id"] == exception["left_store_id"]
    )
    namespace = next(
        row
        for row in entry["physical_namespaces"]
        if namespace_identity_hash(entry["store_id"], row) == exception["left_namespace_hash"]
    )
    namespace["relative_path_template"] = "invented/rebound/path"
    namespace["path_evidence"]["relative_path_template_hash"] = hashlib.sha256(
        namespace["relative_path_template"].encode("utf-8")
    ).hexdigest()
    _resign(changed["state"])

    blockers = validate_wave0_registries(
        changed,
        root=ROOT,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
    )

    assert any("state_overlap_exception_namespace" in blocker for blocker in blockers)


def test_real_server_composition_rejects_two_roots_resolved_to_same_path(tmp_path: Path) -> None:
    server = create_server("127.0.0.1", 0)
    try:
        server.acceptance_analytics_store.root = tmp_path / "same"
        server.acceptance_kb_store.root = tmp_path / "same"

        blockers = runtime_state_authority_blockers(server, ROOT)
    finally:
        server.server_close()

    assert any("v144_wave0_state_runtime_writer_overlap" in blocker for blocker in blockers)


def test_real_server_composition_fails_closed_for_unresolved_required_root() -> None:
    server = create_server("127.0.0.1", 0)
    try:
        server.audio_lab_store.root = None

        blockers = runtime_state_authority_blockers(server, ROOT)
    finally:
        server.server_close()

    assert any("configured.quality.audio-lab.configured-root" in blocker for blocker in blockers)


@pytest.mark.parametrize("field,value", [("classification", "workflow"), ("owner", "forged.Owner")])
def test_resigned_capability_metadata_rewrite_is_blocked(registries: dict[str, dict[str, object]], field: str, value: str) -> None:
    frozen = registry_field_snapshot(registries)
    changed = copy.deepcopy(registries)
    capability = next(row for row in changed["capabilities"]["capabilities"] if isinstance(row, dict) and row.get(field) != value)
    assert isinstance(capability, dict)
    capability[field] = value
    _resign(changed["capabilities"])

    blockers = registry_regressions(frozen, registry_field_snapshot(changed), {"waivers": []})

    assert any(blocker.endswith(f":{field}") for blocker in blockers)


def test_exact_reviewed_waiver_is_required_for_metadata_change(
    registries: dict[str, dict[str, object]], baseline: dict[str, object]
) -> None:
    frozen = registry_field_snapshot(registries)
    changed = copy.deepcopy(registries)
    capability = changed["capabilities"]["capabilities"][0]
    capability["owner"] = "migration.owner"
    current = registry_field_snapshot(changed)
    target_id = capability["capability_id"]
    waiver = {
        "waivers": [
            {
                "waiver_id": "wave0-test-waiver",
                "target_type": "capabilities",
                "target_id": target_id,
                "fields": ["owner"],
                "reason": "Test-only migration authorization.",
                "owner": "architecture-reviewers",
                "expires_version": "14.4.0",
                "adr": "docs/architecture/ADR-033-v144-wave0-capability-freeze.md",
                "status": "approved",
                "approved_by": "architecture-reviewers",
                "approved_at": "2026-07-30T00:00:00+08:00",
                "baseline_integrity_hash": baseline["integrity_hash"],
                "old_value_hash": registry_value_hash(frozen["capabilities"][target_id]["owner"]),
                "new_value_hash": registry_value_hash("migration.owner"),
            }
        ]
    }

    assert (
        registry_regressions(
            frozen,
            current,
            waiver,
            baseline_integrity_hash=str(baseline["integrity_hash"]),
        )
        == []
    )
    waiver["waivers"][0]["fields"] = ["classification"]
    assert any(
        blocker.endswith(":owner")
        for blocker in registry_regressions(
            frozen,
            current,
            waiver,
            baseline_integrity_hash=str(baseline["integrity_hash"]),
        )
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "pending"),
        ("expires_version", "0.0.1"),
        ("old_value_hash", "f" * 64),
        ("new_value_hash", "e" * 64),
        ("baseline_integrity_hash", "d" * 64),
    ],
)
def test_waiver_cannot_be_unapproved_expired_rebound_or_reused(baseline: dict[str, object], field: str, value: str) -> None:
    frozen = {"capabilities": {"quality.probe": {"owner": "old"}}}
    current = {"capabilities": {"quality.probe": {"owner": "new"}}}
    waiver = {
        "waivers": [
            {
                "target_type": "capabilities",
                "target_id": "quality.probe",
                "fields": ["owner"],
                "status": "approved",
                "expires_version": "14.4.0",
                "baseline_integrity_hash": baseline["integrity_hash"],
                "old_value_hash": registry_value_hash("old"),
                "new_value_hash": registry_value_hash("new"),
            }
        ]
    }
    waiver["waivers"][0][field] = value

    blockers = registry_regressions(
        frozen,
        current,
        waiver,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
    )

    assert "registry_metadata_changed:capabilities:quality.probe:owner" in blockers


def test_waiver_registry_requires_approval_expiry_hashes_and_adr_binding(tmp_path: Path, baseline: dict[str, object]) -> None:
    old_hash = registry_value_hash("old")
    new_hash = registry_value_hash("new")
    waiver = {
        "waivers": [
            {
                "waiver_id": "waiver-001",
                "target_type": "capabilities",
                "target_id": "quality.probe",
                "fields": ["owner"],
                "reason": "Reviewed ownership migration.",
                "owner": "architecture-reviewers",
                "expires_version": "14.4.0",
                "adr": "ADR.md",
                "status": "approved",
                "approved_by": "architecture-reviewers",
                "approved_at": "2026-07-30T10:00:00+08:00",
                "baseline_integrity_hash": baseline["integrity_hash"],
                "old_value_hash": old_hash,
                "new_value_hash": new_hash,
            }
        ]
    }
    (tmp_path / "ADR.md").write_text(
        "\n".join(
            (
                "Waiver-ID: waiver-001",
                "Waiver-Target: capabilities/quality.probe",
                "Waiver-Field: owner",
                f"Waiver-Old-Value-SHA256: {old_hash}",
                f"Waiver-New-Value-SHA256: {new_hash}",
            )
        ),
        encoding="utf-8",
    )
    blockers: list[str] = []

    _waiver_checks(
        waiver,
        blockers,
        root=tmp_path,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
    )

    assert blockers == []
    waiver["waivers"][0]["approved_by"] = ""
    waiver["waivers"][0]["expires_version"] = "0.0.1"
    blockers = []
    _waiver_checks(
        waiver,
        blockers,
        root=tmp_path,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
    )
    assert any("waiver_field:waiver-001:approved_by" in item for item in blockers)
    assert "v144_wave0_waiver_expired:waiver-001" in blockers


def test_component_to_capability_reclassification_is_blocked(
    registries: dict[str, dict[str, object]],
) -> None:
    frozen = registry_field_snapshot(registries)
    changed = copy.deepcopy(registries)
    capabilities = changed["capabilities"]["capabilities"]
    assert isinstance(capabilities, list)
    source = next(row for row in capabilities if isinstance(row, dict) and row["surfaces"]["api_routes"])
    target = next(row for row in capabilities if isinstance(row, dict) and row is not source)
    route = source["surfaces"]["api_routes"].pop()
    target["surfaces"]["api_routes"].append(route)

    blockers = registry_regressions(frozen, registry_field_snapshot(changed), {"waivers": []})

    assert sum("registry_metadata_changed:capabilities:" in blocker for blocker in blockers) >= 2


def test_dependency_edge_swap_is_blocked_even_when_count_is_unchanged() -> None:
    frozen = _dependency_fixture([("quality.a", "trust.b"), ("studio.c", "quality.a")])
    current = _dependency_fixture([("quality.a", "program.d"), ("studio.c", "quality.a")])

    blockers = dependency_regressions(frozen, current)

    assert "dependency_edge_growth:cross_domain_imports:quality.a->program.d" in blockers


def test_directional_quality_ratchet_allows_debt_reduction_and_blocks_growth() -> None:
    frozen = _quality_fixture()
    reduced = copy.deepcopy(frozen)
    reduced["typing"]["explicit_any_max_count"] = 9
    reduced["typing"]["explicit_any_file_budgets"]["a.py"] = 4
    reduced["coverage_minimums"]["active"] = 61.0
    reduced["profile_duration_budgets"]["ga"] = 590.0

    assert quality_regressions(frozen, reduced) == []

    raised = copy.deepcopy(frozen)
    raised["typing"]["explicit_any_max_count"] = 11
    raised["typing"]["explicit_any_file_budgets"]["a.py"] = 6
    raised["coverage_minimums"]["active"] = 59.0
    raised["profile_duration_budgets"]["ga"] = 610.0
    blockers = quality_regressions(frozen, raised)
    assert any("explicit_any_max_count" in blocker for blocker in blockers)
    assert any("explicit_any_file_budgets.a.py" in blocker for blocker in blockers)
    assert any("coverage_minimums.active" in blocker for blocker in blockers)
    assert any("profile_duration_budgets.ga" in blocker for blocker in blockers)


def test_module_size_budget_is_per_file_and_cannot_be_offset() -> None:
    frozen = _quality_fixture()
    current = copy.deepcopy(frozen)
    current["module_size_debt"][0]["max_lines"] = 710
    current["module_size_debt"][1]["max_lines"] = 780

    blockers = quality_regressions(frozen, current)

    assert "quality_ceiling_raised:module_size:a.py" in blockers


def test_inline_package_type_and_schema_are_observed_and_unregistered_value_is_blocked(
    catalog: dict[str, object], registries: dict[str, dict[str, object]]
) -> None:
    source = 'document = {"schema_version": 7, "package_type": "musicforge_probe"}'
    observations = _scan_packages(source, "song_agent/domains/quality/probe.py")
    assert len(observations) == 1
    assert observations[0]["source_id"] == "song_agent/domains/quality/probe.py:1:11:1:68@1:49:1:67"
    assert observations[0]["package_type"] == "musicforge_probe"
    assert observations[0]["expression"] == '"musicforge_probe"'
    assert observations[0]["schema_version"] == 7
    assert len(str(observations[0]["scope_source_hash"])) == 64
    changed = copy.deepcopy(catalog)
    inventory = changed["inventory"]
    assert isinstance(inventory, dict)
    package_types = inventory["package_types"]
    assert isinstance(package_types, list)
    package_types.append(
        {
            "package_type": "musicforge_probe",
            "capability_id": "",
            "bounded_context": "",
            "kind": "report",
            "visibility": "internal",
            "sources": [observations[0]["source_id"]],
            "schema_versions": [7],
            "schema_declaration": {"status": "declared", "reason": "probe", "schema_ids": []},
        }
    )

    blockers = _catalog_blockers(changed, registries)

    assert "v144_wave0_unregistered:package_types:musicforge_probe" in blockers


def test_dict_constructor_package_type_is_observed() -> None:
    source = 'document = dict(schema_version=4, package_type="musicforge_dict_probe")'
    observations = _scan_packages(source, "song_agent/domains/quality/dict_probe.py")

    assert len(observations) == 1
    assert observations[0]["package_type"] == "musicforge_dict_probe"
    assert observations[0]["schema_version"] == 4


@pytest.mark.parametrize(
    "source",
    [
        'data = {}\ndata["package_type"] = "musicforge_assignment_probe"',
        'data = {}\ndata.update(package_type="musicforge_assignment_probe")',
        'data = {}\ndata.setdefault("package_type", "musicforge_assignment_probe")',
        'data = dict([("package_type", "musicforge_assignment_probe")])',
    ],
)
def test_common_package_discriminator_writes_are_observed(source: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/assignment_probe.py")

    assert len(observations) == 1
    assert observations[0]["package_type"] == "musicforge_assignment_probe"


@pytest.mark.parametrize(
    "source",
    [
        'KEY = "package_type"\ndata = {}\ndata[KEY] = "musicforge_alias_probe"',
        'KEY = "package_type"\ndata = {}\ndata.setdefault(KEY, "musicforge_alias_probe")',
        'data = {}\ndata.__setitem__("package_type", "musicforge_alias_probe")',
        'import operator\ndata = {}\noperator.setitem(data, "package_type", "musicforge_alias_probe")',
        'import operator as op\ndata = {}\nop.setitem(data, "package_type", "musicforge_alias_probe")',
        'from operator import setitem as put\ndata = {}\nput(data, "package_type", "musicforge_alias_probe")',
        'data = {}\ndict.__setitem__(data, "package_type", "musicforge_alias_probe")',
        'data = {}\ndict.setdefault(data, "package_type", "musicforge_alias_probe")',
    ],
)
def test_alias_and_generic_package_discriminator_writes_are_observed(source: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/alias_probe.py")

    assert len(observations) == 1
    assert observations[0]["package_type"] == "musicforge_alias_probe"


@pytest.mark.parametrize(
    "source",
    [
        "data[key] = make_package_type()",
        "data.__setitem__(key, make_package_type())",
        "import operator\noperator.setitem(data, key, make_package_type())",
        'getattr(data, "__setitem__")("package_type", "musicforge_probe")',
        "data = {key: value for key, value in pairs}",
        "data.update((key, value) for key, value in pairs)",
        'put = data.__setitem__\nput("package_type", "musicforge_probe")',
        'import operator\nput = operator.setitem\nput(data, "package_type", "musicforge_probe")',
    ],
)
def test_raw_package_discriminator_write_candidates_are_fail_closed(source: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/raw_write_probe.py")

    assert observations
    assert all(row["package_type"] == "" or row["package_type"] == "musicforge_probe" for row in observations)


@pytest.mark.parametrize(
    ("source", "package_type"),
    [
        (
            'def put(document, key, value):\n    document[key] = value\nput({}, "package_type", "musicforge_helper_positional")',
            "musicforge_helper_positional",
        ),
        (
            'def put(document, *, key, value):\n    document[key] = value\nput({}, key="package_type", value="musicforge_helper_keyword")',
            "musicforge_helper_keyword",
        ),
        (
            'def put(document, key="package_type", value="musicforge_helper_default"):\n    document[key] = value\nput({})',
            "musicforge_helper_default",
        ),
        (
            'def put(document, key, value):\n    document[key] = value\nput(*({}, "package_type", "musicforge_helper_star"))',
            "musicforge_helper_star",
        ),
        (
            'def put(document, key, value):\n    document[key] = value\nput(**{"document": {}, "key": "package_type", "value": "musicforge_helper_kwargs"})',
            "musicforge_helper_kwargs",
        ),
        (
            'def put(*values):\n    values[0][values[1]] = values[2]\nput({}, "package_type", "musicforge_helper_varargs")',
            "musicforge_helper_varargs",
        ),
        (
            'def put(**values):\n    values["document"][values["key"]] = values["value"]\nput(document={}, key="package_type", value="musicforge_helper_varkw")',
            "musicforge_helper_varkw",
        ),
    ],
)
def test_local_helper_call_effect_binds_python_arguments(source: str, package_type: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/helper_binding_probe.py")

    assert any(row["package_type"] == package_type for row in observations)
    assert any(str(row["candidate_kind"]).startswith("helper_call.put.") for row in observations)


@pytest.mark.parametrize(
    "source",
    [
        (
            'def put(document, key, value):\n    document[key] = value\n'
            'writer = put\nwriter({}, "package_type", "musicforge_helper_alias")'
        ),
        (
            'def put(document, key, value):\n    document[key] = value\n'
            'def wrap(document, key, value):\n    put(document, key, value)\n'
            'wrap({}, "package_type", "musicforge_helper_alias")'
        ),
    ],
)
def test_helper_alias_and_cross_function_calls_reproduce_write_effect(source: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/helper_path_probe.py")

    assert any(row["package_type"] == "musicforge_helper_alias" for row in observations)


def test_new_helper_call_changes_the_frozen_surface() -> None:
    definition = 'def put(document, key, value):\n    document[key] = value\n'
    before = _scan_packages(definition, "song_agent/domains/quality/helper_growth_probe.py")
    after_source = definition + 'put({}, "package_type", "musicforge_unregistered_new")\n'
    after = _scan_packages(after_source, "song_agent/domains/quality/helper_growth_probe.py")

    assert {str(row["source_id"]) for row in after} > {str(row["source_id"]) for row in before}
    assert any(row["package_type"] == "musicforge_unregistered_new" for row in after)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('document["package_type"] = value', "musicforge_fixed_subscript"),
        ("document.update(package_type=value)", "musicforge_fixed_update"),
        ('document.setdefault("package_type", value)', "musicforge_fixed_default"),
        ('return {"package_type": value}', "musicforge_fixed_return"),
    ],
)
def test_fixed_key_helper_effect_is_reproduced_at_callsite(body: str, expected: str) -> None:
    source = f"def put(document, value):\n    {body}\nput({{}}, {expected!r})"

    observations = _scan_packages(source, "song_agent/domains/quality/fixed_helper_probe.py")

    assert any(row["package_type"] == expected and str(row["candidate_kind"]).startswith("helper_call.put.") for row in observations)


def test_helper_summary_cache_is_bound_to_the_current_constant_environment() -> None:
    source = (
        'KEY = "other"\ndef put(document, value):\n    document[KEY] = value\n'
        'put({}, "not_a_package")\nKEY = "package_type"\nput({}, "musicforge_late_key")'
    )

    observations = _scan_packages(source, "song_agent/domains/quality/helper_cache_probe.py")

    assert any(row["package_type"] == "musicforge_late_key" for row in observations)


def test_lambda_helper_fixed_key_effect_is_reproduced_at_callsite() -> None:
    source = 'put = lambda document, value: document.__setitem__("package_type", value)\nput({}, "musicforge_lambda")'

    observations = _scan_packages(source, "song_agent/domains/quality/lambda_helper_probe.py")

    assert any(row["package_type"] == "musicforge_lambda" for row in observations)


@pytest.mark.parametrize(
    "source",
    [
        (
            'def put(document, key, value):\n    document[key] = value\n'
            'args = ("package_type", "musicforge_dynamic_star")\nput({}, *args)'
        ),
        (
            'def put(document, key, value):\n    document[key] = value\n'
            'kwargs = {"key": "package_type", "value": "musicforge_dynamic_kwargs"}\nput({}, **kwargs)'
        ),
    ],
)
def test_dynamic_helper_argument_binding_is_fail_closed_at_callsite(source: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/dynamic_helper_probe.py")

    assert any(str(row["candidate_kind"]).startswith("unresolved_helper_call.put") for row in observations)


@pytest.mark.parametrize(
    "call",
    [
        'external.put({}, "package_type", "musicforge_unknown")',
        'handlers["put"]({}, "package_type", "musicforge_unknown")',
        'getattr(external, "put")({}, "package_type", "musicforge_unknown")',
        'external.get({}, "package_type", "musicforge_unknown")',
    ],
)
def test_general_unknown_callable_with_package_key_is_fail_closed(call: str) -> None:
    observations = _scan_packages(call, "song_agent/domains/quality/unknown_callable_probe.py")

    assert any(row["candidate_kind"] == "unknown_helper_package_key" for row in observations)


def test_helper_call_effect_attacks_reach_catalog_and_surface_gates(
    catalog: dict[str, object],
    baseline: dict[str, object],
    registries: dict[str, dict[str, object]],
) -> None:
    source = (
        'def put(document, value):\n    document["package_type"] = value\n'
        'put({}, "musicforge_gate_attack")\nexternal.put({}, "package_type", "musicforge_unknown_attack")'
    )
    observations = _scan_packages(source, "song_agent/domains/quality/helper_gate_probe.py")
    changed = copy.deepcopy(catalog)
    inventory = changed["inventory"]
    assert isinstance(inventory, dict)
    package_types = inventory["package_types"]
    package_sites = inventory["package_sites"]
    assert isinstance(package_types, list) and isinstance(package_sites, list)
    package_types.append(
        {
            "package_type": "musicforge_gate_attack",
            "sources": [next(row["source_id"] for row in observations if row["package_type"] == "musicforge_gate_attack")],
            "schema_versions": [],
            "schema_declaration": {},
        }
    )
    unknown = next(row for row in observations if row["candidate_kind"] == "unknown_helper_package_key")
    package_sites.append({"site_id": unknown["source_id"], **unknown})

    blockers = [*_catalog_blockers(changed, registries), *_surface_blockers(changed, baseline)]

    assert any("musicforge_gate_attack" in blocker for blocker in blockers)
    assert any(str(unknown["source_id"]) in blocker for blocker in blockers)


@pytest.mark.parametrize(
    "source",
    [
        'from external import put\nput({}, "package_type", "musicforge_unregistered_new")',
        'from external import put as writer\nwriter({}, "package_type", "musicforge_unregistered_new")',
    ],
)
def test_unknown_helper_with_package_key_is_fail_closed(source: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/imported_helper_probe.py")

    assert len(observations) == 1
    assert observations[0]["package_type"] == ""
    assert observations[0]["candidate_kind"] == "unknown_helper_package_key"


def test_package_writer_contracts_match_the_active_tree(
    catalog: dict[str, object],
    registries: dict[str, dict[str, object]],
) -> None:
    rows = catalog["package_writer_contracts"]

    assert isinstance(rows, list)
    assert len(rows) == 35
    assert all(row["guarded"] is True for row in rows)
    assert package_writer_registry_blockers(rows, registries["packages"]) == []


def test_unguarded_parameterized_writer_is_blocked() -> None:
    source = 'class Writer:\n    def put(self, document, value):\n        document["package_type"] = value\n'
    trees = {"helpers": ast.parse(source)}
    rows = package_writer_contract_observations(trees, {"helpers": "helpers.py"}, {"helpers": source})
    assert len(rows) == 1
    contract = {
        **{key: value for key, value in rows[0].items() if key != "guarded"},
        "writer_kind": "legacy_parameterized",
        "call_policy": "runtime_guarded",
        "allowed_type_set_id": "wave0.runtime",
    }

    blockers = package_writer_registry_blockers(
        rows,
        {"writer_contracts": [contract], "package_type_sets": []},
    )

    assert blockers == ["v144_wave0_package_writer_unguarded:helpers.Writer.put"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expression_source_hash", "f" * 64),
        ("module_source_hash", "f" * 64),
        ("guard_symbol", "fake.require_registered_package_type"),
        ("guard_alias", "require_registered_package_type"),
        ("guard_binding_hash", "f" * 64),
    ],
)
def test_writer_contract_metadata_rewrite_is_blocked(
    catalog: dict[str, object],
    registries: dict[str, dict[str, object]],
    field: str,
    value: str,
) -> None:
    changed = copy.deepcopy(registries["packages"])
    changed["writer_contracts"][0][field] = value

    blockers = package_writer_registry_blockers(catalog["package_writer_contracts"], changed)

    assert any(blocker.endswith(f":{field}") for blocker in blockers)


def test_runtime_package_writer_policy_is_current(registries: dict[str, dict[str, object]]) -> None:
    expected = build_runtime_package_writer_policy(registries["packages"])
    expected_registry = build_runtime_package_registry_projection(registries["packages"])
    actual_registry = load_runtime_package_registry_projection()
    actual = load_runtime_package_writer_policy()

    assert validate_runtime_package_registry_projection(expected_registry) == []
    assert actual_registry == expected_registry
    assert validate_runtime_package_writer_policy(expected, expected_registry) == []
    assert actual == expected


def test_runtime_package_guard_isolated_from_public_loader_mutation() -> None:
    writer_id = "song_agent.platform.verification.model.build_verification_report"
    injected = "runtime_cache_injection_report"
    _runtime_package_writer_index.cache_clear()
    policy = load_runtime_package_writer_policy()
    projection = load_runtime_package_registry_projection()
    writer = next(row for row in policy["writer_contracts"] if row["writer_id"] == writer_id)
    type_set = next(
        row for row in policy["package_type_sets"] if row["type_set_id"] == writer["allowed_type_set_id"]
    )
    projected_set = next(
        row
        for row in projection["package_type_sets"]
        if row["type_set_id"] == writer["allowed_type_set_id"]
    )
    type_set["package_types"].append(injected)
    type_set["package_type_kinds"][injected] = "report"
    writer["nullable"] = True
    writer["allowed_type_set_id"] = "forged"
    projected_set["package_types"].append(injected)
    projection["writer_contracts"][0]["nullable"] = True

    with pytest.raises(ValueError, match="not authorized"):
        require_registered_package_type(injected, writer_id=writer_id)

    assert injected not in json.dumps(load_runtime_package_writer_policy(), sort_keys=True)
    assert injected not in json.dumps(load_runtime_package_registry_projection(), sort_keys=True)
    _runtime_package_writer_index.cache_clear()


def test_runtime_package_writer_policy_rejects_tamper(registries: dict[str, dict[str, object]]) -> None:
    policy = build_runtime_package_writer_policy(registries["packages"])
    policy["registry_integrity_hash"] = "f" * 64

    assert "v144_package_writer_policy_integrity" in validate_runtime_package_writer_policy(policy)


def test_runtime_package_writer_policy_rejects_resigned_unknown_formal_type(
    registries: dict[str, dict[str, object]],
) -> None:
    projection = build_runtime_package_registry_projection(registries["packages"])
    policy = build_runtime_package_writer_policy(registries["packages"])
    writer = next(
        row
        for row in policy["writer_contracts"]
        if row["writer_id"] == "song_agent.platform.verification.model.build_verification_report"
    )
    type_set = next(
        row for row in policy["package_type_sets"] if row["type_set_id"] == writer["allowed_type_set_id"]
    )
    type_set["package_types"].append("totally_unregistered_report")
    type_set["package_type_kinds"]["totally_unregistered_report"] = "report"
    policy["integrity_hash"] = _runtime_policy_hash(policy)

    blockers = validate_runtime_package_writer_policy(policy, projection)

    assert "v144_package_writer_policy_type_sets" in blockers


@pytest.mark.parametrize(
    ("attack", "expected_blocker"),
    [("guard", "v144_package_writer_policy_writers"), ("forged-type", "v144_package_writer_policy_type_sets")],
)
def test_runtime_package_writer_policy_rejects_resigned_contract_attacks(
    registries: dict[str, dict[str, object]],
    attack: str,
    expected_blocker: str,
) -> None:
    policy = build_runtime_package_writer_policy(registries["packages"])
    writer = next(row for row in policy["writer_contracts"] if row["contract_scope"] == "production")
    if attack == "guard":
        writer["guard_binding_hash"] = "f" * 64
    else:
        type_set = next(row for row in policy["package_type_sets"] if row["writer_id"] == writer["writer_id"])
        type_set["package_types"].append("forged_package_type")
        type_set["package_type_kinds"]["forged_package_type"] = "attack_corpus"
        type_set["allowed_package_kinds"].append("attack_corpus")
        writer["allowed_package_kinds"].append("attack_corpus")
    policy["integrity_hash"] = _runtime_policy_hash(policy)

    blockers = validate_runtime_package_writer_policy(policy)

    assert expected_blocker in blockers


@pytest.mark.parametrize("payload", [None, "not-json", '{"schema_version": 1}'])
def test_runtime_package_writer_policy_loader_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    payload: str | None,
) -> None:
    class Resource:
        def joinpath(self, _name: str) -> "Resource":
            return self

        def read_text(self, *, encoding: str) -> str:
            assert encoding == "utf-8"
            if payload is None:
                raise FileNotFoundError
            return payload

    monkeypatch.setattr("song_agent.platform.contracts.packages.resources.files", lambda _package: Resource())
    with pytest.raises(RuntimeError, match="package"):
        load_runtime_package_writer_policy()


def test_runtime_package_writer_policy_uses_writer_specific_minimal_sets(
    registries: dict[str, dict[str, object]],
) -> None:
    policy = build_runtime_package_writer_policy(registries["packages"])
    writers = policy["writer_contracts"]
    type_sets = {row["type_set_id"]: row for row in policy["package_type_sets"]}

    assert len(writers) == len(type_sets) == 35
    assert len({row["allowed_type_set_id"] for row in writers}) == len(writers)
    assert all(type_sets[row["allowed_type_set_id"]]["writer_id"] == row["writer_id"] for row in writers)
    assert max(len(row["package_types"]) for row in type_sets.values()) <= 32

    all_values = {value for row in type_sets.values() for value in row["package_types"]}
    for writer in writers:
        writer_id = str(writer["writer_id"])
        allowed = set(type_sets[writer["allowed_type_set_id"]]["package_types"])
        for value in allowed:
            assert require_registered_package_type(value, writer_id=writer_id) == value
        foreign = next(value for value in sorted(all_values - allowed))
        with pytest.raises(ValueError, match="not authorized"):
            require_registered_package_type(foreign, writer_id=writer_id)


def test_generation_writer_allows_only_its_two_existing_generation_documents() -> None:
    writer_id = "song_agent.platform.lifecycle.generation.GenerationService.build_document"
    allowed = {
        "musicforge_unified_release_program_continuity_acceptance_generation",
        "musicforge_unified_release_program_continuity_command_center_acceptance_generation",
    }

    for package_type in allowed:
        assert require_registered_package_type(package_type, writer_id=writer_id) == package_type
    with pytest.raises(ValueError, match="not authorized"):
        require_registered_package_type("musicforge_unified_release_program_record", writer_id=writer_id)


def test_shared_acceptance_manifest_writer_allows_only_its_existing_outputs() -> None:
    writer_id = "song_agent.domains.program.unified_release_program_continuity_acceptance._package_manifest"
    allowed = {
        "musicforge_unified_release_program_continuity_acceptance_archive",
        "musicforge_unified_release_program_continuity_acceptance_change_control_archive",
        "musicforge_unified_release_program_continuity_command_center",
    }

    for package_type in allowed:
        assert require_registered_package_type(package_type, writer_id=writer_id) == package_type
    with pytest.raises(ValueError, match="not authorized"):
        require_registered_package_type("musicforge_unified_release_program_record", writer_id=writer_id)


def test_attack_values_are_isolated_to_the_attack_corpus_writer(
    registries: dict[str, dict[str, object]],
) -> None:
    restricted_sets = [
        row
        for row in registries["packages"]["package_type_sets"]
        if row["purpose"] == "runtime_writer"
        if any(
            value == "forged_package_type"
            or value == "musicforge_"
            or str(value).startswith("musicforge_test_")
            for value in row["package_types"]
        )
    ]

    assert restricted_sets
    assert {row["writer_id"] for row in restricted_sets} == {PACKAGE_WRITER_ATTACK_CORPUS}


def test_package_registry_rejects_a_production_catch_all_set(
    registries: dict[str, dict[str, object]],
    baseline: dict[str, object],
) -> None:
    changed = copy.deepcopy(registries)
    packages = changed["packages"]
    writer = next(row for row in packages["writer_contracts"] if row["contract_scope"] == "production")
    type_set = next(row for row in packages["package_type_sets"] if row["writer_id"] == writer["writer_id"])
    formal = [
        row
        for row in packages["package_types"]
        if row["package_type"] not in {"forged_package_type", "musicforge_"}
        and not str(row["package_type"]).startswith("musicforge_test_")
    ][:33]
    values = [row["package_type"] for row in formal]
    kinds = {row["package_type"]: row["kind"] for row in formal}
    allowed_kinds = sorted(set(kinds.values()))
    type_set.update(
        {
            "package_types": values,
            "package_type_kinds": kinds,
            "allowed_package_kinds": allowed_kinds,
        }
    )
    writer["allowed_package_kinds"] = allowed_kinds
    packages["integrity_hash"] = integrity_hash(packages)

    blockers = validate_wave0_registries(
        changed,
        root=ROOT,
        baseline_integrity_hash=str(baseline["integrity_hash"]),
    )

    assert f"v144_wave0_package_type_set_catch_all:{type_set['type_set_id']}" in blockers


@pytest.mark.parametrize(
    "package_type",
    [
        "forged_package_type",
        "musicforge_",
        "musicforge_public_trust_center",
        "audio_campaign",
    ],
)
def test_verification_report_writer_rejects_cross_kind_and_attack_values(package_type: str) -> None:
    with pytest.raises(ValueError, match="not authorized"):
        build_verification_report(package_type=package_type, checks=[], summary={})


def test_runtime_package_writer_policy_is_fail_closed_for_none(
    registries: dict[str, dict[str, object]],
) -> None:
    policy = build_runtime_package_writer_policy(registries["packages"])

    with pytest.raises(ValueError, match="not registered"):
        require_registered_package_type(None, writer_id="unknown.writer")
    for writer in policy["writer_contracts"]:
        writer_id = str(writer["writer_id"])
        if writer["nullable"]:
            assert require_registered_package_type(None, writer_id=writer_id) is None
        else:
            with pytest.raises(ValueError, match="required"):
                require_registered_package_type(None, writer_id=writer_id)


@pytest.mark.parametrize(
    "source",
    [
        (
            "from fake_contracts import require_registered_package_type as _require_registered_package_type\n"
            "def put(document, value):\n"
            "    document['package_type'] = _require_registered_package_type(value, writer_id='helpers.put')\n"
        ),
        (
            "from song_agent.platform.contracts.packages import require_registered_package_type as "
            "_require_registered_package_type\n"
            "_require_registered_package_type = fake_guard\n"
            "def put(document, value):\n"
            "    document['package_type'] = _require_registered_package_type(value, writer_id='helpers.put')\n"
        ),
        (
            "from song_agent.platform.contracts.packages import require_registered_package_type as "
            "_require_registered_package_type\n"
            "if enabled:\n"
            "    _require_registered_package_type = fake_guard\n"
            "def put(document, value):\n"
            "    document['package_type'] = _require_registered_package_type(value, writer_id='helpers.put')\n"
        ),
        (
            "import fake_contracts\n"
            "def put(document, value):\n"
            "    document['package_type'] = fake_contracts.require_registered_package_type("
            "value, writer_id='helpers.put')\n"
        ),
        (
            "from song_agent.platform.contracts.packages import require_registered_package_type as "
            "_require_registered_package_type\n"
            "from fake import *\n"
            "def put(document, value):\n"
            "    document['package_type'] = _require_registered_package_type(value, writer_id='helpers.put')\n"
        ),
        (
            "from song_agent.platform.contracts.packages import (require_registered_package_type as "
            "_require_registered_package_type, fake as _require_registered_package_type)\n"
            "def put(document, value):\n"
            "    document['package_type'] = _require_registered_package_type(value, writer_id='helpers.put')\n"
        ),
    ],
    ids=[
        "fake-import",
        "post-shadow",
        "conditional-rebind",
        "attribute-lookalike",
        "wildcard-import",
        "same-node-duplicate-binding",
    ],
)
def test_package_writer_guard_requires_the_canonical_binding(source: str) -> None:
    rows = _scan_writers({"helpers": source})

    assert len(rows) == 1
    assert rows[0]["writer_id"] == "helpers.put"
    assert rows[0]["guarded"] is False


@pytest.mark.parametrize(
    "attack",
    [
        "globals()['_require_registered_package_type'] = fake_guard\n",
        "globals().update({'_require_registered_package_type': fake_guard})\n",
        "setattr(sys.modules[__name__], '_require_registered_package_type', fake_guard)\n",
    ],
    ids=["globals-subscript", "globals-update", "module-setattr"],
)
def test_writer_module_source_hash_blocks_dynamic_guard_rebinding(attack: str) -> None:
    base = (
        "import sys\n"
        "from song_agent.platform.contracts.packages import require_registered_package_type as "
        "_require_registered_package_type\n"
        "def put(document, value):\n"
        "    document['package_type'] = _require_registered_package_type("
        "value, writer_id='helpers.put')\n"
    )
    fake_guard = "def fake_guard(value, *, writer_id):\n    return value\n"
    frozen = _scan_writers({"helpers": base})[0]
    changed = _scan_writers({"helpers": base + fake_guard + attack})[0]

    assert changed["guarded"] is True
    assert changed["module_source_hash"] != frozen["module_source_hash"]
    registry = {"writer_contracts": [{key: value for key, value in frozen.items() if key != "guarded"}]}
    assert any(
        blocker.endswith(":module_source_hash")
        for blocker in package_writer_registry_blockers([changed], registry)
    )

    module_name = "wave0_dynamic_guard_probe"
    module = types.ModuleType(module_name)
    sys.modules[module_name] = module
    try:
        exec(compile(base + fake_guard + attack, "helpers.py", "exec"), module.__dict__)
        document: dict[str, object] = {}
        module.put(document, "totally_unregistered_report")
        assert document["package_type"] == "totally_unregistered_report"
    finally:
        del sys.modules[module_name]


def test_writer_module_source_hash_includes_comments_and_layout() -> None:
    compact = "def put(document, value):\n document['package_type'] = value\n"
    formatted = "# comment\n\ndef put(document, value):\n    document['package_type'] = value\n"
    first = _scan_writers({"helpers": compact})[0]
    second = _scan_writers({"helpers": formatted})[0]

    assert first["module_source_hash"] != second["module_source_hash"]


def test_writer_module_source_hash_does_not_normalize_string_contents() -> None:
    writer = "def put(document, value):\n document['package_type'] = value\n"
    first = _scan_writers({"helpers": "MARKER = 'left, type_params=[]right'\n" + writer})[0]
    second = _scan_writers({"helpers": "MARKER = 'leftright'\n" + writer})[0]

    assert first["module_source_hash"] != second["module_source_hash"]


def test_source_evidence_normalizes_only_line_endings() -> None:
    lf = "value = {\"package_type\": name}\n"
    crlf = lf.replace("\n", "\r\n")
    cr = lf.replace("\n", "\r")
    lf_tree = ast.parse(lf)
    crlf_tree = ast.parse(crlf)
    cr_tree = ast.parse(cr)
    lf_expression = next(node for node in ast.walk(lf_tree) if isinstance(node, ast.Name) and node.id == "name")
    crlf_expression = next(node for node in ast.walk(crlf_tree) if isinstance(node, ast.Name) and node.id == "name")
    cr_expression = next(node for node in ast.walk(cr_tree) if isinstance(node, ast.Name) and node.id == "name")

    assert normalize_source_text(crlf) == normalize_source_text(cr) == lf
    assert source_text_hash(lf) == source_text_hash(crlf) == source_text_hash(cr)
    assert source_fragment_hash(lf, lf_expression) == source_fragment_hash(crlf, crlf_expression)
    assert source_fragment_hash(lf, lf_expression) == source_fragment_hash(cr, cr_expression)
    assert source_site_id("probe.py", lf_expression) == source_site_id("probe.py", crlf_expression)


def test_dynamic_site_identity_does_not_depend_on_candidate_order() -> None:
    source = 'data[key] = "musicforge_dynamic_key_probe"'
    observed = _scan_packages(source, "song_agent/domains/quality/order_probe.py")[0]
    first = {**observed, "candidate_kind": "z-analysis"}
    second = {**observed, "candidate_kind": "a-analysis"}

    forward = _normalize_dynamic_site_ids([first, second])
    reverse = _normalize_dynamic_site_ids([second, first])

    assert forward == reverse
    assert forward[0]["source_id"] == observed["source_id"]
    assert forward[0]["candidate_kinds"] == ["a-analysis", "z-analysis"]


def test_wave0_runtime_evidence_does_not_serialize_python_ast() -> None:
    paths = [
        ROOT / "song_agent/release_check/v14_wave0_catalog_model.py",
        ROOT / "song_agent/release_check/v14_wave0_inventory.py",
        ROOT / "song_agent/release_check/v14_wave0_package_inventory.py",
        ROOT / "song_agent/release_check/v14_wave0_package_scan.py",
        ROOT / "song_agent/release_check/v14_wave0_source.py",
        ROOT / "song_agent/release_check/v14_wave0_state_registry.py",
    ]

    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "ast.dump(" not in source
        assert "ast.unparse(" not in source


def test_current_architecture_summary_is_generated_from_catalog(catalog: dict[str, object]) -> None:
    path = ROOT / "docs/architecture/CURRENT.md"
    text = path.read_text(encoding="utf-8")

    assert _render_current_architecture_summary(text, catalog) == text


def test_runtime_writer_guard_is_dispatch_independent(registries: dict[str, dict[str, object]]) -> None:
    contract = registries["packages"]["writer_contracts"][0]
    writer_id = str(contract["writer_id"])
    type_set = next(
        row
        for row in registries["packages"]["package_type_sets"]
        if row["type_set_id"] == contract["allowed_type_set_id"]
    )
    allowed = str(type_set["package_types"][0])

    class Writer:
        def put(self, value: str) -> str:
            return require_registered_package_type(value, writer_id=writer_id)

    class Child(Writer):
        pass

    factory = Child
    assert factory().put(allowed) == allowed
    with pytest.raises(ValueError, match="not authorized"):
        factory().put("musicforge_unregistered_dispatch_attack")


def test_inheritance_reexport_and_factory_attacks_change_the_frozen_literal_surface(
    registries: dict[str, dict[str, object]],
) -> None:
    trees = {
        "helpers": ast.parse(
            'class Writer:\n    def put(self, document, value):\n        document["package_type"] = value\n'
            'def put(document, value):\n    document["package_type"] = value\n'
            'def factory():\n    return Writer()\n'
        ),
        "bridge": ast.parse("from helpers import *\n"),
        "caller": ast.parse(
            'import pkg.helpers\nfrom bridge import Writer, put\nfrom helpers import factory\n'
            'class Child(Writer):\n    pass\n'
            'Child().put({}, "musicforge_inherited_new")\n'
            'pkg.helpers.Writer().put({}, "musicforge_dotted_new")\n'
            'put({}, "musicforge_wildcard_new")\n'
            'factory().put({}, "musicforge_factory_new")\n'
        ),
    }

    blockers = unregistered_package_literal_blockers(trees, registries["packages"])

    assert len(blockers) == 4
    assert any("musicforge_inherited_new" in blocker for blocker in blockers)
    assert any("musicforge_dotted_new" in blocker for blocker in blockers)
    assert any("musicforge_wildcard_new" in blocker for blocker in blockers)
    assert any("musicforge_factory_new" in blocker for blocker in blockers)


def test_unregistered_literal_reaches_the_wave0_catalog_gate(
    catalog: dict[str, object],
    registries: dict[str, dict[str, object]],
) -> None:
    changed = copy.deepcopy(catalog)
    changed["package_literal_blockers"] = [
        "v144_wave0_package_literal_unregistered:caller:1:musicforge_gate_attack"
    ]

    blockers = _catalog_blockers(changed, registries)

    assert "v144_wave0_package_literal_unregistered:caller:1:musicforge_gate_attack" in blockers


@pytest.mark.parametrize(
    ("source", "expected_type"),
    [
        ('data[key] |= "musicforge_augmented_dynamic"', ""),
        ('key = "package_type"\ndata[key] |= "musicforge_augmented_known"', "musicforge_augmented_known"),
    ],
)
def test_augmented_package_discriminator_write_is_observed(source: str, expected_type: str) -> None:
    observations = _scan_packages(source, "song_agent/domains/quality/augmented_probe.py")

    assert len(observations) == 1
    assert observations[0]["package_type"] == expected_type
    assert "augmented_assignment" in str(observations[0]["candidate_kind"])


def test_dynamic_package_key_write_is_fail_closed() -> None:
    source = 'data = {}\ndata[key] = "musicforge_dynamic_key_probe"'
    observations = _scan_packages(source, "song_agent/domains/quality/dynamic_key_probe.py")

    assert len(observations) == 1
    assert observations[0]["package_type"] == ""
    assert observations[0]["candidate_kind"] == "dynamic_key_assignment"


def test_lexical_package_key_rewrite_does_not_inherit_outer_constant() -> None:
    source = 'KEY = "package_type"\ndef build():\n    KEY = "other"\n    data[KEY] = "musicforge_not_a_package"\n'
    observations = _scan_packages(source, "song_agent/domains/quality/key_rewrite_probe.py")

    assert observations == []


def test_existing_non_literal_package_writes_are_registered(
    catalog: dict[str, object],
) -> None:
    inventory = catalog["inventory"]
    assert isinstance(inventory, dict)
    assert any(
        row.get("package_type") == "musicforge_release_train_handoff_response"
        and any(
            str(source).startswith(
                "song_agent/domains/program/unified_command_center_release_train_handoff.py:"
            )
            for source in row.get("sources", [])
        )
        for row in inventory["package_types"]
        if isinstance(row, dict)
    )
    assert any(
        row.get("package_type") == "musicforge_lts_migration_state"
        and any(
            str(source).startswith("song_agent/domains/creation/lts_maintenance.py:")
            for source in row.get("sources", [])
        )
        for row in inventory["package_types"]
        if isinstance(row, dict)
    )
    assert any(
        str(row.get("site_id") or "").startswith(
            "song_agent/domains/trust/release_portfolio_governance_attestation_portal_review.py:"
        )
        for row in inventory["package_sites"]
        if isinstance(row, dict)
    )


def test_dynamic_package_site_binds_lexical_scope() -> None:
    before_source = 'def build():\n    package_name = "musicforge_a"\n    return {"package_type": package_name}\n'
    after_source = 'def build():\n    package_name = "musicforge_b"\n    return {"package_type": package_name}\n'
    before = _scan_packages(before_source, "song_agent/domains/quality/dynamic_probe.py")
    after = _scan_packages(after_source, "song_agent/domains/quality/dynamic_probe.py")

    assert before[0]["source_id"] == after[0]["source_id"]
    assert before[0]["expression"] == after[0]["expression"] == "package_name"
    assert before[0]["scope_source_hash"] != after[0]["scope_source_hash"]


def test_dynamic_package_scope_rewrite_is_blocked(catalog: dict[str, object], registries: dict[str, dict[str, object]]) -> None:
    changed = copy.deepcopy(catalog)
    inventory = changed["inventory"]
    assert isinstance(inventory, dict)
    sites = inventory["package_sites"]
    assert isinstance(sites, list) and sites
    sites[0]["scope_source_hash"] = "f" * 64

    blockers = _catalog_blockers(changed, registries)

    assert f"v144_wave0_package_site:{sites[0]['site_id']}" in blockers


def test_declared_surface_missing_from_source_is_blocked(catalog: dict[str, object], registries: dict[str, dict[str, object]]) -> None:
    changed = copy.deepcopy(catalog)
    inventory = changed["inventory"]
    assert isinstance(inventory, dict)
    routes = inventory["api_routes"]
    assert isinstance(routes, list) and routes
    removed = routes.pop()

    blockers = _catalog_blockers(changed, registries)

    assert f"v144_wave0_declared_surface_missing:api_routes:{removed['route_id']}" in blockers


def test_package_schema_registry_covers_every_observed_discriminator(
    catalog: dict[str, object], registries: dict[str, dict[str, object]]
) -> None:
    inventory = catalog["inventory"]
    assert isinstance(inventory, dict)
    observed = {row["package_type"] for row in inventory["package_types"]}
    declared = {row["package_type"] for row in registries["packages"]["package_types"]}

    assert observed == declared
    assert len(observed) == 542
    assert all(row["schema_declaration"]["reason"] for row in registries["packages"]["package_types"])
    assert all(row["capability_id"] for row in inventory["package_sites"])


@pytest.mark.parametrize(
    "inventory_name,identity",
    [
        ("stores", "example.Store"),
        ("cli_commands", "new-command"),
        ("api_routes", "POST /api/new"),
        ("package_types", "musicforge_new_package"),
        ("studio_panels", "new-panel"),
        ("release_checks", "v999.new_check"),
    ],
)
def test_wave0_updater_rejects_surface_growth(baseline: dict[str, object], inventory_name: str, identity: str) -> None:
    changed = copy.deepcopy(baseline)
    values = changed["surface_freeze"]["identity_sets"][inventory_name]
    assert isinstance(values, list)
    values.append(identity)

    assert f"{inventory_name}:{identity}" in _surface_additions(baseline, changed)


def test_surface_identity_already_in_frozen_registry_can_be_restored(baseline: dict[str, object]) -> None:
    inconsistent = copy.deepcopy(baseline)
    identity = next(iter(inconsistent["registry_freeze"]["package_sites"]))
    inconsistent["surface_freeze"]["identity_sets"]["package_sites"].remove(identity)

    assert _surface_additions(inconsistent, baseline) == []


def test_updater_and_runtime_use_the_same_directional_ratchet(baseline: dict[str, object]) -> None:
    reduced = copy.deepcopy(baseline)
    reduced["quality_freeze"]["typing"]["explicit_any_max_count"] -= 1
    assert _baseline_regressions(baseline, reduced) == []

    raised = copy.deepcopy(baseline)
    raised["quality_freeze"]["typing"]["explicit_any_max_count"] += 1
    assert any("explicit_any_max_count" in item for item in _baseline_regressions(baseline, raised))


def test_registry_contract_schema_change_requires_an_exact_waiver(baseline: dict[str, object]) -> None:
    changed = copy.deepcopy(baseline)
    old_value = changed["registry_contracts"]["packages"]["schema_version"]
    changed["registry_contracts"]["packages"]["schema_version"] = old_value + 1
    expected = "registry_metadata_changed:registry_contracts:packages:schema_version"

    assert expected in _baseline_regressions(baseline, changed)
    waiver = {
        "waivers": [
            {
                "target_type": "registry_contracts",
                "target_id": "packages",
                "fields": ["schema_version"],
                "status": "approved",
                "approved_by": "architecture-reviewers",
                "approved_at": "2026-08-02T10:00:00+08:00",
                "owner": "architecture-reviewers",
                "expires_version": "14.4.0",
                "baseline_integrity_hash": baseline["integrity_hash"],
                "old_value_hash": registry_value_hash(old_value),
                "new_value_hash": registry_value_hash(old_value + 1),
            }
        ]
    }

    assert _baseline_regressions(baseline, changed, waiver) == []
    waiver["waivers"][0]["new_value_hash"] = "f" * 64
    assert expected in _baseline_regressions(baseline, changed, waiver)


def test_updater_rejects_baseline_schema_downgrade() -> None:
    assert _frozen_baseline_schema_current({"schema_version": 5, "package_type": "musicforge_v144_wave0_baseline"})
    assert not _frozen_baseline_schema_current({"schema_version": 4, "package_type": "musicforge_v144_wave0_baseline"})
    assert not _frozen_baseline_schema_current({"schema_version": 3, "package_type": "musicforge_v144_wave0_baseline"})
    assert not _frozen_baseline_schema_current({"schema_version": 1, "package_type": "musicforge_v144_wave0_baseline"})
    assert not _frozen_baseline_schema_current({"schema_version": 99, "package_type": "musicforge_v144_wave0_baseline"})


def test_every_registry_requires_the_exact_contract_schema(
    registries: dict[str, dict[str, object]],
) -> None:
    for key, contract in REGISTRY_CONTRACTS.items():
        changed = copy.deepcopy(registries)
        changed[key]["schema_version"] = 0
        _resign(changed[key])

        blockers = validate_wave0_registries(changed, root=ROOT)

        assert f"v144_wave0_registry_schema:{key}" in blockers
        assert changed[key]["package_type"] == contract["package_type"]


def test_updater_refuses_to_bootstrap_a_missing_baseline(tmp_path: Path) -> None:
    assert update(tmp_path) == 1


def test_updater_rejects_anchor_changing_reduction_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sandbox = _updater_sandbox(tmp_path)
    reduced = json.loads((sandbox / "architecture-v14.4-wave0-baseline.json").read_text(encoding="utf-8"))
    reduced["quality_freeze"]["typing"]["explicit_any_max_count"] -= 1
    _resign(reduced)
    _configure_updater_sandbox(monkeypatch, sandbox, candidate_baseline=reduced)
    before = _updater_bytes(sandbox)

    assert update(sandbox) == 1
    assert _updater_bytes(sandbox) == before
    assert not list(sandbox.rglob(".*.tmp"))


@pytest.mark.parametrize("failure", ["replace", "final_gate"])
def test_updater_rolls_back_every_file_on_transaction_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    sandbox = _updater_sandbox(tmp_path)
    _configure_updater_sandbox(monkeypatch, sandbox)
    catalog_path = sandbox / "capability-catalog.json"
    catalog_path.write_bytes(catalog_path.read_bytes() + b"\n")
    before = _updater_bytes(sandbox)
    if failure == "replace":
        real_replace = wave0_updater._commit_replace
        calls = 0

        def fail_second_replace(temporary: Path, path: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected replacement failure")
            real_replace(temporary, path)

        monkeypatch.setattr(wave0_updater, "_commit_replace", fail_second_replace)
    else:
        monkeypatch.setattr(
            wave0_updater,
            "evaluate_wave0",
            lambda _root: {"status": "failed", "blockers": ["injected_final_gate"]},
        )

    assert update(sandbox) == 1
    assert _updater_bytes(sandbox) == before
    assert not list(sandbox.rglob(".*.tmp"))


def test_updater_transaction_succeeds_when_documents_are_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sandbox = _updater_sandbox(tmp_path)
    _configure_updater_sandbox(monkeypatch, sandbox)

    assert update(sandbox) == 0
    assert update(sandbox, check=True) == 0
    assert not list(sandbox.rglob(".*.tmp"))


def test_updater_rebinds_state_exceptions_without_mutating_the_approved_input(
    registries: dict[str, dict[str, object]],
) -> None:
    original = registries["state"]
    rebound = _rebind_state_exceptions(original, "a" * 64)

    assert all(row["baseline_integrity_hash"] == "a" * 64 for row in rebound["writer_overlap_exceptions"])
    assert all(row["baseline_integrity_hash"] != "a" * 64 for row in original["writer_overlap_exceptions"])
    assert integrity_ok(rebound)


def test_wave0_gate_and_generator_pass_current_workspace() -> None:
    report = evaluate_wave0(ROOT)

    assert report["status"] == "passed", report["blockers"]
    assert report["blockers"] == []
    assert update(ROOT, check=True) == 0


def test_wave0_baseline_is_integrity_bound(baseline: dict[str, object]) -> None:
    assert integrity_ok(baseline)
    changed = copy.deepcopy(baseline)
    changed["status"] = "changed"
    assert not integrity_ok(changed)
    _resign(changed)
    assert integrity_ok(changed)


def test_wave0_governance_modules_respect_new_module_limit() -> None:
    paths = list((ROOT / "song_agent" / "release_check").glob("v14_wave0*.py"))
    assert paths
    assert all(len(path.read_text(encoding="utf-8").splitlines()) <= 400 for path in paths)


def test_wave0_mypy_targets_cover_every_wave0_module() -> None:
    from song_agent.release_check.v14_quality import MYPY_TARGETS

    expected = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "song_agent" / "release_check").glob("v14_wave0*.py")
    }
    assert expected <= set(MYPY_TARGETS)


def test_wave0_coverage_merge_requires_and_replaces_every_changed_source() -> None:
    base_files = {path: {"summary": {"covered_lines": 1, "num_statements": 2, "missing_lines": 1}} for path in WAVE0_CHANGED_SOURCES}
    base_files["song_agent/unchanged.py"] = {"summary": {"covered_lines": 3, "num_statements": 4, "missing_lines": 1}}
    overlay_files = {path: {"summary": {"covered_lines": 2, "num_statements": 2, "missing_lines": 0}} for path in WAVE0_CHANGED_SOURCES}
    merged = merge_coverage_reports({"meta": {}, "files": base_files}, {"meta": {"format": 3}, "files": overlay_files})
    assert merged["files"]["song_agent/unchanged.py"] == base_files["song_agent/unchanged.py"]
    assert merged["totals"]["covered_lines"] == len(WAVE0_CHANGED_SOURCES) * 2 + 3
    assert merged["totals"]["num_statements"] == len(WAVE0_CHANGED_SOURCES) * 2 + 4
    missing_overlay = copy.deepcopy(overlay_files)
    missing_overlay.pop(WAVE0_CHANGED_SOURCES[0])
    with pytest.raises(ValueError, match="missing changed sources"):
        merge_coverage_reports({"files": base_files}, {"files": missing_overlay})


def test_wave0_coverage_contract_declares_every_changed_runtime_surface(baseline: dict[str, object]) -> None:
    declared = set(WAVE0_CHANGED_SOURCES)
    required = {
        "song_agent/interfaces/cli/commands/delivery_parts/verify_release.py",
        "song_agent/interfaces/cli/commands/delivery_parts/verify_unified_release_program_operations.py",
        "song_agent/interfaces/cli/commands/quality_parts/verify_release_audio_quality_observatory.py",
        "song_agent/interfaces/cli/commands/trust_parts/public_trust_center_publication_store.py",
        "song_agent/interfaces/cli/commands/trust_parts/verify_public_trust_center_distribution_kit.py",
        "song_agent/interfaces/cli/commands/trust_parts/verify_release_portfolio_governance_attestation_portal.py",
        "song_agent/interfaces/cli/commands/trust_parts/verify_trust_operations_assurance_watch.py",
        "song_agent/release_check/v14_wave0_package_registry.py",
        "song_agent/release_check_evidence_policy.py",
        "song_agent/release_check_verification_kernel.py",
    }

    assert len(declared) == len(WAVE0_CHANGED_SOURCES)
    assert required <= declared
    assert all(path.startswith("song_agent/") and path.endswith(".py") for path in declared)
    assert all((ROOT / path).is_file() for path in declared)

    baseline_sha = str(baseline["baseline_sha"])
    changed_output = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", baseline_sha, "--", "song_agent"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    untracked_output = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "song_agent"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    changed = {
        path.replace("\\", "/")
        for path in [*changed_output.splitlines(), *untracked_output.splitlines()]
        if path.endswith(".py")
    }
    assert changed == declared


def _resign(document: dict[str, object]) -> None:
    document["integrity_hash"] = integrity_hash(document)


def _updater_sandbox(tmp_path: Path) -> Path:
    sandbox = tmp_path / "wave0-updater"
    for relative in UPDATER_SANDBOX_FILES:
        target = sandbox / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return sandbox


def _updater_bytes(root: Path) -> dict[str, bytes]:
    return {relative: (root / relative).read_bytes() for relative in UPDATER_SANDBOX_FILES}


def _configure_updater_sandbox(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
    *,
    candidate_baseline: dict[str, object] | None = None,
) -> None:
    catalog = json.loads((root / "capability-catalog.json").read_text(encoding="utf-8"))
    baseline = candidate_baseline or json.loads(
        (root / "architecture-v14.4-wave0-baseline.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(wave0_updater, "build_wave0_catalog", lambda _root: copy.deepcopy(catalog))
    monkeypatch.setattr(
        wave0_updater,
        "build_wave0_baseline",
        lambda _root, _catalog: copy.deepcopy(baseline),
    )
    monkeypatch.setattr(wave0_updater, "validate_wave0_registries", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        wave0_updater,
        "evaluate_wave0",
        lambda _root: {"status": "passed", "blockers": []},
    )


def _dependency_fixture(edges: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "module_count": 10,
        "total_source_lines": 100,
        "production_cycle_count": 0,
        "boundary_violation_count": 0,
        "active_to_compatibility_import_count": 0,
        "cross_domain_imports": [{"importer": importer, "imported": imported} for importer, imported in edges],
        "interface_domain_imports": [],
    }


def _quality_fixture() -> dict[str, object]:
    return {
        "typing": {
            "explicit_any_max_count": 10,
            "explicit_any_collector_schema_version": 17,
            "explicit_any_file_budgets": {"a.py": 5},
        },
        "complexity": {"module_default_max_lines": 600},
        "mypy": {
            "max_total_errors": 0,
            "error_budgets": {},
            "active_roots": ["song_agent"],
            "critical_targets": ["song_agent/platform"],
            "strict_required": True,
        },
        "module_size_debt": [
            {"path": "a.py", "max_lines": 700, "expires_version": "14.4.0"},
            {"path": "b.py", "max_lines": 800, "expires_version": "14.4.0"},
        ],
        "coverage_minimums": {"active": 60.0},
        "architecture_limits": {"boundary_violation_count": 0},
        "profile_duration_budgets": {"ga": 600.0},
        "ci_profile_duration_budgets": {"ga": 1080.0},
        "profile_budget_warning_only": [],
        "check_duration_budgets": {"v144.wave0": 120.0},
    }
