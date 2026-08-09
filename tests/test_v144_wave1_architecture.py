from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from song_agent.architecture_guardrails import (
    _module_ownership,
    boundary_violations_for_sources,
    build_architecture_snapshot,
)
from song_agent.platform.verification.hashing import integrity_hash
from song_agent.platform.contracts.coercion import as_document, document_or
from song_agent.platform.contracts.documents import (
    is_json_document,
    is_json_value,
    normalize_json_document,
)
from song_agent.release_check.v14_wave0_package_scan import package_observations
from song_agent.release_check.v14_wave1 import (
    ATTACK_PROBES,
    LEGACY_APPLICATION_DOMAIN_DEBT,
    LEGACY_STORE_NAMESPACE_DEBT,
    _mypy_configuration_blockers,
    _run_mypy,
    evaluate_wave1,
    inspect_wave1_dependency_graph,
    inspect_wave1_sources,
)
from tools.migrate_v144_wave1_surfaces import TARGET_HASHES, migrate


ROOT = Path(__file__).resolve().parents[1]


def test_wave1_current_tree_passes_boundaries_without_nested_mypy() -> None:
    report = evaluate_wave1(ROOT, run_mypy=False)

    assert report["status"] == "passed", report["blockers"]
    assert report["summary"]["interface_domain_import_count"] == 0
    assert report["summary"]["non_composition_store_constructor_count"] == 0
    assert report["summary"]["dynamic_forwarding_count"] == 0
    assert all(report["summary"]["attack_probes"].values())


@pytest.mark.parametrize(("probe_id", "path", "source", "expected"), ATTACK_PROBES)
def test_wave1_structural_attack_probes_are_fail_closed(
    probe_id: str,
    path: str,
    source: str,
    expected: str,
) -> None:
    blockers = inspect_wave1_sources({path: source})

    assert any(expected in blocker for blocker in blockers), (probe_id, blockers)


def test_wave1_freezes_legacy_application_domain_debt_by_source_identity() -> None:
    path = next(iter(LEGACY_APPLICATION_DOMAIN_DEBT))
    source = (ROOT / path).read_text(encoding="utf-8")

    assert inspect_wave1_sources({path: source}) == []
    changed = inspect_wave1_sources({path: source + "\n# unreviewed implementation change\n"})
    assert any("legacy_domain_debt_changed" in blocker for blocker in changed)

    migrated = "from song_agent.domains.program.model import ProgramComponent\n"
    assert inspect_wave1_sources({path: migrated}) == []


def test_wave1_freezes_legacy_store_namespaces_by_source_identity() -> None:
    path = next(iter(LEGACY_STORE_NAMESPACE_DEBT))
    source = (ROOT / path).read_text(encoding="utf-8")

    assert inspect_wave1_sources({path: source}) == []
    changed = inspect_wave1_sources({path: source + "\n# namespace debt must be removed before editing\n"})
    assert any("concrete_store_namespace_import" in blocker for blocker in changed)
    explicit_factory = "from song_agent.interfaces.bootstrap.cli.stores import release_store\n"
    assert inspect_wave1_sources({"song_agent/interfaces/cli/commands/new.py": explicit_factory}) == []


def test_wave1_domain_contract_registry_is_symbol_scoped_and_relative_aware() -> None:
    allowed = inspect_wave1_sources(
        {
            "song_agent/application/program/absolute.py": ("from song_agent.domains.program.model import ProgramComponent\n"),
            "song_agent/application/program/relative.py": ("from ...domains.program.model import ProgramComponent\n"),
        }
    )
    assert allowed == []

    blockers = inspect_wave1_sources(
        {
            "song_agent/application/program/module.py": ("import song_agent.domains.program.model\n"),
            "song_agent/application/program/wildcard.py": ("from song_agent.domains.program.model import *\n"),
            "song_agent/application/program/symbol.py": ("from song_agent.domains.program.model import InternalProgramState\n"),
        }
    )
    assert sum("application_domain_implementation_import" in row for row in blockers) == 3

    root_only = inspect_wave1_sources(
        {"song_agent/application/program/root_package.py": ("from song_agent import domains\nregistry = domains.BOUNDED_CONTEXTS\n")}
    )
    assert any("application_domain_implementation_import" in row for row in root_only)


@pytest.mark.parametrize(
    ("module", "expected_layer"),
    (
        ("song_agent.platform", "platform"),
        ("song_agent.application", "application"),
        ("song_agent.capabilities", "application"),
        ("song_agent.interfaces", "interface"),
        ("song_agent.domains", "domain"),
        ("song_agent.release_check", "release_check"),
        ("song_agent.interfaces_compat", "compatibility"),
    ),
)
def test_architecture_root_packages_use_exact_prefix_ownership(module: str, expected_layer: str) -> None:
    assert _module_ownership(module, module.replace(".", "/") + "/__init__.py")["layer"] == expected_layer


def test_wave1_interface_root_imports_are_blocked_by_central_boundary() -> None:
    sources = {
        "song_agent/application/probes/interface_root_import.py": "import song_agent.interfaces\n",
        "song_agent/application/probes/interface_root_from.py": "from song_agent import interfaces\n",
        "song_agent/domains/interface_root_relative.py": "from .. import interfaces\n",
        "song_agent/domains/probes/interface_root_alias.py": (
            "from song_agent import interfaces as boundary\napi = boundary.api\n"
        ),
    }

    violations = boundary_violations_for_sources(sources)
    violation_keys = {
        (row["importer"], row["imported"], row["reason"])
        for row in violations
    }
    assert (
        "song_agent.application.probes.interface_root_import",
        "song_agent.interfaces",
        "application_must_not_depend_on_interface_or_release_check",
    ) in violation_keys
    assert (
        "song_agent.application.probes.interface_root_from",
        "song_agent.interfaces",
        "application_must_not_depend_on_interface_or_release_check",
    ) in violation_keys
    assert (
        "song_agent.domains.interface_root_relative",
        "song_agent.interfaces",
        "domain_must_not_depend_on_interface_or_release_check",
    ) in violation_keys
    assert (
        "song_agent.domains.probes.interface_root_alias",
        "song_agent.interfaces",
        "domain_must_not_depend_on_interface_or_release_check",
    ) in violation_keys

    blockers = inspect_wave1_sources(sources)
    assert sum("central_boundary:application_must_not_depend_on_interface_or_release_check" in row for row in blockers) == 2
    assert sum("central_boundary:domain_must_not_depend_on_interface_or_release_check" in row for row in blockers) == 2


def test_full_architecture_snapshot_blocks_interface_root_dependencies(tmp_path: Path) -> None:
    files = {
        "song_agent/__init__.py": "",
        "song_agent/application/__init__.py": "",
        "song_agent/application/probe.py": "from song_agent import interfaces\n",
        "song_agent/domains/__init__.py": "",
        "song_agent/domains/probe.py": "from .. import interfaces\n",
    }
    for relative, source in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    snapshot = build_architecture_snapshot(tmp_path)
    import_pairs = {(row["importer"], row["imported"]) for row in snapshot["import_pairs"]}
    violations = {
        (row["importer"], row["imported"], row["reason"])
        for row in snapshot["boundary_violations"]
    }

    assert ("song_agent.application.probe", "song_agent.interfaces") in import_pairs
    assert ("song_agent.domains.probe", "song_agent.interfaces") in import_pairs
    assert (
        "song_agent.application.probe",
        "song_agent.interfaces",
        "application_must_not_depend_on_interface_or_release_check",
    ) in violations
    assert (
        "song_agent.domains.probe",
        "song_agent.interfaces",
        "domain_must_not_depend_on_interface_or_release_check",
    ) in violations


def test_wave1_dependency_graph_enforces_layer_direction_independently() -> None:
    sources = {
        "song_agent/application/probe.py": "from song_agent.domains.quality import audio_lab\n",
        "song_agent/platform/probe.py": "from song_agent.application import maintenance\n",
    }
    snapshot = {
        "modules": [
            {"module": "song_agent.application.probe", "path": "song_agent/application/probe.py"},
            {"module": "song_agent.platform.probe", "path": "song_agent/platform/probe.py"},
        ],
        "import_pairs": [
            {
                "importer": "song_agent.application.probe",
                "imported": "song_agent.domains.quality.audio_lab",
            },
            {
                "importer": "song_agent.platform.probe",
                "imported": "song_agent.application.maintenance",
            },
        ],
        "dynamic_internal_imports": [{"importer": "song_agent.application.probe"}],
        "boundary_violations": [
            {
                "importer": "song_agent.platform.probe",
                "imported": "song_agent.application.maintenance",
                "reason": "platform_must_not_depend_outward",
            },
            {
                "importer": "song_agent.application.probe",
                "imported": "song_agent.domains.quality.audio_lab",
                "reason": "dynamic_internal_import_at_line_1",
            },
        ],
    }

    blockers = inspect_wave1_dependency_graph(snapshot, sources)
    assert any("central_boundary:platform_must_not_depend_outward" in row for row in blockers)
    assert any("central_boundary:dynamic_internal_import_at_line_1" in row for row in blockers)


def test_wave1_dynamic_capability_allowlist_is_path_and_symbol_exact() -> None:
    assert inspect_wave1_sources({"song_agent/platform/resource_access.py": ("from importlib import resources as _resources\n")}) == []

    blockers = inspect_wave1_sources(
        {
            "song_agent/platform/contracts/packages.py": ("from importlib import resources\n"),
            "song_agent/interfaces/web/assets.py": "import importlib.resources\n",
        }
    )
    assert sum("dynamic_import:forbidden_module" in row for row in blockers) == 2


@pytest.mark.parametrize(
    "source",
    (
        "from builtins import __import__ as loader\nloader('song_agent.domains.quality')\n",
        "import sys\nregistry = vars(sys)['modules']\n",
        "import sys\nregistry = getattr(sys, 'modules')\n",
        "registry = __builtins__['__import__']\n",
        "namespace = locals\nnamespace()['forwarded'] = object()\n",
    ),
)
def test_wave1_dynamic_capabilities_cannot_be_recovered_indirectly(source: str) -> None:
    blockers = inspect_wave1_sources({"song_agent/application/dynamic_escape.py": source})

    assert any("dynamic_import" in row or "module_namespace_access" in row for row in blockers)


@pytest.mark.parametrize(
    "source",
    (
        "from song_agent.platform.resource_access import read_packaged_text\nloader = read_packaged_text.__globals__['_resources']\n",
        "from song_agent.platform.resource_access import read_packaged_text\nlookup = getattr\nloader = lookup(read_packaged_text, '__globals__')['_resources']\n",
        "from song_agent.platform.resource_access import read_packaged_text\nkey = '__glo' + 'bals__'\nloader = getattr(read_packaged_text, key)['_resources']\n",
    ),
)
def test_wave1_resource_adapter_cannot_leak_reflection_capabilities(source: str) -> None:
    blockers = inspect_wave1_sources({"song_agent/application/resource_escape.py": source})

    assert any("dynamic_reflection:callable_namespace" in row for row in blockers)


def test_wave1_requires_static_module_exports_and_namespace_immutability() -> None:
    assert inspect_wave1_sources({"song_agent/application/exports.py": "__all__ = ('first', 'second')\n"}) == []

    blockers = inspect_wave1_sources(
        {"song_agent/application/mutable_exports.py": ("namespace = globals\n__all__ = []\n__all__.extend(namespace())\n")}
    )
    assert any("module_namespace_access" in row for row in blockers)
    assert any("dynamic_all" in row for row in blockers)

    alias_mutation = inspect_wave1_sources(
        {"song_agent/application/aliased_exports.py": ("__all__ = []\nexports = __all__\nexports.append('late')\n")}
    )
    assert any("dynamic_all" in row for row in alias_mutation)


def test_wave1_blocks_interface_domain_import_and_store_construction() -> None:
    blockers = inspect_wave1_sources(
        {
            "song_agent/interfaces/api/routes/probe.py": (
                "from song_agent.domains.quality.probe import ProbeStore\nstore = ProbeStore()\n"
            ),
            "song_agent/application/probe.py": (
                "from song_agent.release_check.runner import run_release_check_matrix\nstore = ProbeStore()\n"
            ),
        }
    )

    assert any("interface_domain_import" in blocker for blocker in blockers)
    assert any("interface_store_constructor" in blocker for blocker in blockers)
    assert any("central_boundary:application_must_not_depend_on_interface_or_release_check" in blocker for blocker in blockers)
    assert any("application_store_constructor" in blocker for blocker in blockers)


def test_wave1_blocks_relative_alias_and_dynamic_boundary_bypasses() -> None:
    blockers = inspect_wave1_sources(
        {
            "song_agent/interfaces/api/routes/probe.py": (
                "from .... import domains\nfrom ....domains.quality.audio_lab import AudioLabStore as Factory\nstore = Factory()\n"
            ),
            "song_agent/application/dynamic_probe.py": (
                "import importlib as loader\n"
                "load = loader.import_module\n"
                "module = load('song_agent.domains.quality.audio_lab')\n"
                "resolver = getattr(loader, 'import_module')\n"
            ),
            "song_agent/platform/reverse_probe.py": ("from song_agent.domains.quality import audio_lab\n"),
        }
    )

    assert any("interface_domain_import" in blocker for blocker in blockers)
    assert any("interface_domain_import" in blocker for blocker in blockers)
    assert any("dynamic_import:forbidden_module" in blocker for blocker in blockers)
    assert any("central_boundary:platform_must_not_depend_outward" in blocker for blocker in blockers)


def test_wave1_blocks_container_store_alias_and_namespace_factory_aliases() -> None:
    blockers = inspect_wave1_sources(
        {
            "song_agent/application/store_probe.py": (
                "from song_agent.domains.quality.audio_lab import AudioLabStore\n"
                "factories = {'primary': AudioLabStore}\n"
                "store = factories['primary']()\n"
            ),
            "song_agent/application/module_alias_probe.py": (
                "import sys as runtime\n"
                "namespace_factories = {'current': globals}\n"
                "namespace_factories['current']()['forwarded'] = object()\n"
                "runtime.modules[__name__].other = object()\n"
            ),
            "song_agent/application/import_alias_probe.py": (
                "from importlib import import_module\n"
                "resolvers = {'internal': import_module}\n"
                "resolvers['internal']('song_agent.domains.quality.audio_lab')\n"
            ),
        }
    )

    assert any("application_domain_implementation_import" in blocker for blocker in blockers)
    assert any("dynamic_forwarding:module_namespace_access" in blocker for blocker in blockers)
    assert any("dynamic_import:sys_modules" in blocker for blocker in blockers)
    assert any("dynamic_import:forbidden_module" in blocker for blocker in blockers)


def test_wave1_blocks_module_namespace_mutation_and_untyped_bootstrap() -> None:
    blockers = inspect_wave1_sources(
        {
            "song_agent/application/module_probe.py": (
                "import sys\nsetattr(sys.modules[__name__], 'forwarded', object())\nglobals().__setitem__('other', object())\n"
            ),
            "song_agent/interfaces/bootstrap/api/untyped_probe.py": (
                "def build(*arguments, **options):\n    return factory(*arguments, **options)\n"
            ),
        }
    )

    assert any("dynamic_forwarding:module_namespace_access" in blocker for blocker in blockers)
    assert any("dynamic_import:sys_modules" in blocker for blocker in blockers)
    assert any("untyped_composition_factory" in blocker for blocker in blockers)


def test_wave1_allows_concrete_dependencies_only_in_composition_roots() -> None:
    blockers = inspect_wave1_sources(
        {
            "song_agent/interfaces/bootstrap/api/probe.py": (
                "from song_agent.domains.quality.probe import ProbeStore\ndef build() -> ProbeStore:\n    return ProbeStore()\n"
            ),
            "song_agent/interfaces/api/server.py": ("from song_agent.domains.quality.probe import ProbeStore\nstore = ProbeStore()\n"),
        }
    )

    assert blockers == []


def test_wave1_blocks_dynamic_forwarding_forms() -> None:
    blockers = inspect_wave1_sources(
        {
            "song_agent/application/adapter.py": (
                "import sys\n"
                "from types import ModuleType\n"
                "def __getattr__(name: str) -> object:\n"
                "    return name\n"
                "class Adapter:\n"
                "    def __getattr__(self, name):\n"
                "        return name\n"
                "class DynamicModule(ModuleType):\n"
                "    def __setattr__(self, name, value):\n"
                "        super().__setattr__(name, value)\n"
                "globals()['replacement'] = object()\n"
                "Adapter.__module__ = __name__\n"
                "sys.modules[__name__].__class__ = DynamicModule\n"
                "__all__ = [name for name in globals()]\n"
            )
        }
    )

    kinds = {blocker.split(":")[1] for blocker in blockers if "dynamic_forwarding" in blocker}
    assert {
        "module_hook",
        "module_type_setattr",
        "module_namespace_access",
        "runtime_metadata",
        "dynamic_all",
    }.issubset(kinds)


@pytest.mark.parametrize(
    "source",
    (
        "def forward(name: str) -> object:\n    return name\n__getattr__ = forward\n",
        "__getattr__ = lambda name: name\n",
        "from provider import forward as __getattr__\n",
        "if enabled:\n    __dir__ = provider\n",
    ),
)
def test_wave1_blocks_all_module_pep562_hook_bindings(source: str) -> None:
    blockers = inspect_wave1_sources({"song_agent/application/module_hooks.py": source})

    assert any("dynamic_forwarding:module_hook" in blocker for blocker in blockers)


def test_wave1_blocks_nested_global_module_hooks_without_rejecting_instance_hooks() -> None:
    global_hook = (
        "def install() -> None:\n"
        "    global __getattr__\n"
        "    __getattr__ = lambda name: name\n"
    )
    blockers = inspect_wave1_sources({"song_agent/application/global_hook.py": global_hook})
    assert any("dynamic_forwarding:module_hook" in blocker for blocker in blockers)

    instance_hook = "class Adapter:\n    def __getattr__(self, name: str) -> object:\n        return name\n"
    assert inspect_wave1_sources({"song_agent/application/instance_hook.py": instance_hook}) == []


@pytest.mark.parametrize(
    "source, expected",
    (
        ("from provider import *\n", "dynamic_forwarding:wildcard_import"),
        ("namespace = vars(provider)\nnamespace['__getattr__'] = forward\n", "dynamic_forwarding:module_hook"),
        ("setattr(provider, '__dir__', forward)\n", "dynamic_forwarding:module_hook"),
    ),
)
def test_wave1_blocks_indirect_module_hook_injection(source: str, expected: str) -> None:
    blockers = inspect_wave1_sources({"song_agent/application/module_hook_injection.py": source})

    assert any(expected in blocker for blocker in blockers)


def test_wave1_composition_size_uses_bytes_and_ast_nodes() -> None:
    byte_heavy = "PAYLOAD = " + repr("x" * 24_100) + "\n"
    node_heavy = "\n".join(f"value_{index} = ({index}, {index})" for index in range(500))

    byte_blockers = inspect_wave1_sources({"song_agent/interfaces/bootstrap/api/byte_heavy.py": byte_heavy})
    node_blockers = inspect_wave1_sources({"song_agent/interfaces/bootstrap/api/node_heavy.py": node_heavy})
    line_blockers = inspect_wave1_sources(
        {"song_agent/interfaces/bootstrap/api/line_heavy.py": "PAYLOAD = " + repr("x" * 2_100) + "\n"}
    )

    assert any("composition_oversized_bytes" in blocker for blocker in byte_blockers)
    assert any("composition_oversized_ast" in blocker for blocker in node_blockers)
    assert any("composition_oversized_line" in blocker for blocker in line_blockers)


def test_wave1_blocks_object_passthrough_composition_factory() -> None:
    blockers = inspect_wave1_sources(
        {
            "song_agent/interfaces/bootstrap/api/probe.py": (
                "def build(*arguments: object, **options: object) -> object:\n    return factory(*arguments, **options)\n"
            )
        }
    )

    assert blockers == ["v144_wave1_untyped_composition_factory:song_agent/interfaces/bootstrap/api/probe.py"]

    fixed = inspect_wave1_sources({"song_agent/interfaces/bootstrap/api/probe.py": "def build(dependency):\n    return dependency\n"})
    assert fixed == ["v144_wave1_untyped_composition_factory:song_agent/interfaces/bootstrap/api/probe.py"]


@pytest.mark.parametrize(
    "source",
    (
        "def build(*items: tuple[object, ...]) -> Provider:\n    return Provider()\n",
        "Boundary = object\ndef build(*items: Boundary) -> Provider:\n    return Provider()\n",
        "from typing import Any as Boundary\ndef build(value: Boundary) -> Provider:\n    return Provider()\n",
        "def build(value: 'object | None') -> Provider:\n    return Provider()\n",
    ),
)
def test_wave1_composition_factories_reject_nested_aliased_and_quoted_escape_types(source: str) -> None:
    blockers = inspect_wave1_sources({"song_agent/interfaces/bootstrap/api/typed_escape.py": source})

    assert blockers == ["v144_wave1_untyped_composition_factory:song_agent/interfaces/bootstrap/api/typed_escape.py"]


@pytest.mark.parametrize(
    "source",
    (
        "setattr(Target, '__module__', 'song_agent.domains.fake')\n",
        "object.__setattr__(Target, '__class__', Replacement)\n",
        "Target.__dict__['__module__'] = 'song_agent.domains.fake'\n",
        "vars(Target).update(__class__=Replacement)\n",
    ),
)
def test_wave1_blocks_runtime_metadata_mutation_by_operation_identity(source: str) -> None:
    blockers = inspect_wave1_sources({"song_agent/application/runtime_metadata.py": source})

    assert any("dynamic_forwarding:runtime_metadata" in blocker for blocker in blockers)


def test_wave1_resolves_module_type_alias_identity() -> None:
    source = (
        "from types import ModuleType as Base\n"
        "class DynamicModule(Base):\n"
        "    def __setattr__(self, name: str, value: object) -> None:\n"
        "        super().__setattr__(name, value)\n"
    )

    blockers = inspect_wave1_sources({"song_agent/application/dynamic_module.py": source})
    assert any("dynamic_forwarding:module_type_setattr" in blocker for blocker in blockers)


def test_recursive_json_contract_checks_nested_values() -> None:
    document = {"name": "release", "checks": [{"ok": True, "count": 2}], "reason": None}

    assert is_json_document(document) is True
    assert is_json_value([document]) is True
    assert is_json_document({"invalid": object()}) is False
    normalized = normalize_json_document(document)
    assert normalized == document
    assert normalized is not document
    assert normalized["checks"] is not document["checks"]
    with pytest.raises(ValueError):
        as_document(object())


def test_json_contract_rejects_unknown_sensitive_and_non_finite_values() -> None:
    class Secret:
        def __str__(self) -> str:
            return "api_key=must-not-leak"

    invalid = (
        {"marker": object()},
        {"secret": Secret()},
        {"value": float("nan")},
        {"value": float("inf")},
        {"nested": [{"value": float("-inf")}]},
    )
    for document in invalid:
        assert is_json_document(document) is False
        with pytest.raises(ValueError):
            normalize_json_document(document)
        with pytest.raises(ValueError):
            as_document(document)


def test_json_coercion_validates_fallbacks_and_approved_paths(tmp_path: Path) -> None:
    source = {"path": tmp_path / "evidence.json", "nested": [{"ok": True}]}
    normalized = as_document(source)

    assert normalized == {
        "path": str(tmp_path / "evidence.json"),
        "nested": [{"ok": True}],
    }
    assert normalized["nested"] is not source["nested"]
    with pytest.raises(ValueError):
        document_or(None, {"invalid": object()})


def test_json_contract_rejects_cycles_non_string_keys_and_bytes() -> None:
    recursive: list[object] = []
    recursive.append(recursive)

    for value in (recursive, {1: "invalid"}, {"payload": b"secret"}):
        assert is_json_value(value) is False
        with pytest.raises(ValueError):
            normalize_json_document({"value": value})


def test_mypy_config_enforces_explicit_any_for_wave1_roots() -> None:
    assert _mypy_configuration_blockers(ROOT) == []


def test_mypy_config_requires_strict_bootstrap_definitions(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.mypy]\n"
        "[[tool.mypy.overrides]]\n"
        'module = ["song_agent.platform.*", "song_agent.application.*", '
        '"song_agent.interfaces.*"]\n'
        "disallow_any_explicit = true\n"
        "[[tool.mypy.overrides]]\n"
        'module = ["song_agent.interfaces.bootstrap.*"]\n'
        "disallow_any_explicit = true\n",
        encoding="utf-8",
    )

    assert "v144_wave1_mypy_bootstrap_strict_missing" in _mypy_configuration_blockers(tmp_path)


def test_mypy_rejects_alias_and_quoted_explicit_any(tmp_path: Path) -> None:
    package = tmp_path / "song_agent" / "platform"
    package.mkdir(parents=True)
    (tmp_path / "song_agent" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "probe.py").write_text(
        "from __future__ import annotations\nfrom typing import Any as Alias\ndirect: Alias\nquoted: 'Alias'\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.mypy]\n"
        "python_version = '3.11'\n"
        "files = ['song_agent/platform']\n"
        "[[tool.mypy.overrides]]\n"
        "module = ['song_agent.platform.*', 'song_agent.application.*', 'song_agent.interfaces.*']\n"
        "disallow_any_explicit = true\n",
        encoding="utf-8",
    )

    blockers, detail = _run_mypy(tmp_path)

    assert blockers == ["v144_wave1_mypy_failed"]
    assert "errors" in detail or "error" in detail


def test_wave1_surface_migration_is_exact_and_debt_reducing() -> None:
    path = ROOT / "architecture-v14.4-wave1-surface-migration.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))

    assert manifest["integrity_hash"] == integrity_hash(manifest)
    assert manifest["integrity_hash"] == TARGET_HASHES["migration_manifest_hash"]
    assert len(manifest["cli_registration_relocations"]) == 78
    transitions = manifest["package_site_transitions"]
    assert sum(row["transition"] == "source_relocation" for row in transitions) == 164
    assert sum(row["transition"] != "source_relocation" for row in transitions) == 12
    assert len(manifest["package_site_retirements"]) == 9
    assert manifest["package_site_additions"] == []
    assert manifest["invariants"]["package_site_count_before"] == 2687
    assert manifest["invariants"]["package_site_count_after"] == 2676
    targets = manifest["target_hashes"]
    for key, relative in {
        "capability_registry_hash": "architecture-v14.4-capability-registry.json",
        "state_registry_hash": "architecture-v14.4-state-authority-registry.json",
        "package_registry_hash": "architecture-v14.4-package-schema-registry.json",
        "catalog_hash": "capability-catalog.json",
        "baseline_hash": "architecture-v14.4-wave0-baseline.json",
    }.items():
        document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        assert document["integrity_hash"] == targets[key]


def test_wave1_surface_migration_is_idempotent() -> None:
    tracked = [
        ROOT / "architecture-v14.4-capability-registry.json",
        ROOT / "architecture-v14.4-state-authority-registry.json",
        ROOT / "architecture-v14.4-package-schema-registry.json",
        ROOT / "architecture-v14.4-wave0-baseline.json",
        ROOT / "capability-catalog.json",
    ]
    before = {path: path.read_bytes() for path in tracked}

    assert migrate(ROOT, apply=True) == 0
    assert {path: path.read_bytes() for path in tracked} == before


def test_wave1_json_normalizers_do_not_create_package_writer_sites() -> None:
    path = ROOT / "song_agent" / "platform" / "contracts" / "documents.py"
    source = path.read_text(encoding="utf-8")

    assert package_observations(ast.parse(source), path.as_posix(), source) == []
