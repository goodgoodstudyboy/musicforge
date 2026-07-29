from __future__ import annotations

import ast
from collections.abc import Callable, Iterable, Iterator
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

from song_agent.release_check.v14_quality import (
    EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
    QUALITY_POLICY_VERSION,
    _ExplicitAnyCollector,
    _annotation_any_count,
    _mypy_blockers,
    _policy_blockers,
    _typing_blockers,
    active_source_tree_hash,
    collect_v1421_static_violations,
    collect_complexity_metrics,
    collect_interface_application_metrics,
    collect_typing_metrics,
    evaluate_v14_quality,
    run_v14_interface_application_boundary_smoke,
    run_v141_quality_debt_closure_smoke,
    run_v1421_stabilization_rollback_smoke,
    run_v1422_explicit_any_scope_smoke,
    run_v1423_explicit_any_lambda_scope_smoke,
    run_v1424_explicit_any_definition_time_scope_smoke,
    run_v1425_explicit_any_class_global_scope_smoke,
    run_v1426_explicit_any_indirect_target_scope_smoke,
    run_v1427_explicit_any_derived_uncertain_scope_smoke,
    run_v1428_explicit_any_object_alias_scope_smoke,
    run_v1429_explicit_any_alias_dataflow_smoke,
    run_v14210_explicit_any_alias_fail_closed_smoke,
    run_v143_explicit_any_call_effect_dataflow_smoke,
    run_v1431_call_effect_component_compaction_smoke,
    run_v1432_expression_binding_single_pass_smoke,
    run_v1433_call_binding_lambda_effect_smoke,
    run_v1434_late_bound_lexical_capture_smoke,
    run_v1435_first_global_lexical_capture_smoke,
)
from song_agent.platform.contracts import as_document, as_float, as_int, as_list, as_path, as_text
from song_agent.platform.verification.hashing import stable_hash
from song_agent.interfaces.api.runtime_parts.helpers import api_info
from tools.adopt_v141_composition_types import adopt_composition_types
from tools.adopt_v141_document_coercions import adopt_document_coercions
from tools.consolidate_v141_contract_imports import consolidate_contract_imports
from tools.migrate_v14_private_document_types import migrate_private_document_types
from tools.split_v14_active_functions import split_active_functions
from tools.split_v14_interface_functions import _split_one, split_interfaces
from tools.update_v14_quality_policy import (
    _ratchet_complexity_policy,
    _ratchet_mypy_policy,
    _ratchet_typing_policy,
    _write_compact_coverage,
)


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def test_v14_typing_and_complexity_ratchets_pass_without_hiding_public_debt() -> None:
    policy = json.loads((ROOT / "architecture-v14-quality.json").read_text(encoding="utf-8"))
    report = evaluate_v14_quality(ROOT, run_mypy=False, require_coverage=False)

    assert report["status"] == "passed", report["blockers"]
    assert report["typing"]["raw_dict_str_any_count"] <= 8774
    assert report["typing"]["raw_dict_str_any_count"] <= int(12535 * 0.70)
    assert report["typing"]["explicit_any_count"] <= int(policy["typing"]["explicit_any_max_count"])
    assert report["typing"]["public_implementation_document_count"] == 0
    assert report["typing"]["untyped_public_function_count"] == 0
    assert report["complexity"]["oversized_function_count"] == 0


def test_v14_interface_boundary_uses_dedicated_structure_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_repeated_typing_scan(_root: Path) -> dict[str, object]:
        raise AssertionError("interface boundary must not repeat Explicit Any data-flow analysis")

    monkeypatch.setattr(
        "song_agent.release_check.v14_quality.collect_typing_metrics",
        fail_repeated_typing_scan,
    )

    passed, detail = run_v14_interface_application_boundary_smoke(ROOT)
    metrics = collect_interface_application_metrics(ROOT)

    assert passed, detail
    assert metrics["untyped_public_function_count"] == 0
    assert metrics["public_implementation_document_count"] == 0


def test_v14_interface_boundary_structure_scan_detects_public_contract_debt(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "contract_debt.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "def missing_annotation(value):\n"
        "    return value\n\n"
        "def dynamic_document(value: ImplementationDocument) -> ImplementationDocument:\n"
        "    return value\n",
        encoding="utf-8",
    )

    metrics = collect_interface_application_metrics(tmp_path)

    assert metrics["untyped_public_function_count"] == 1
    assert metrics["public_implementation_document_count"] == 1


def test_v14_mypy_metrics_use_one_authoritative_active_tree_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("song_agent.release_check.v14_quality.subprocess.run", fake_run)

    from song_agent.release_check.v14_quality import collect_mypy_metrics

    metrics = collect_mypy_metrics(tmp_path)

    assert len(calls) == 1
    assert calls[0][0:3] == [sys.executable, "-m", "mypy"]
    assert metrics["status"] == "measured"
    assert metrics["strict_status"] == "passed"
    assert metrics["strict_returncode"] == 0


def test_v14_migration_tools_are_idempotent() -> None:
    assert migrate_private_document_types(ROOT, write=False)["changed_file_count"] == 0
    assert split_active_functions(ROOT, write=False) == {"changed_files": [], "skipped": []}
    assert split_interfaces(ROOT, write=False) == {"selected": 0, "changed_files": [], "skipped": []}
    assert adopt_composition_types(ROOT, write=False)["changed_files"] == []
    assert adopt_document_coercions(ROOT, write=False)["changed_files"] == []
    assert consolidate_contract_imports(ROOT, write=False)["changed_files"] == []


def test_v141_contract_coercions_are_typed_and_fail_closed() -> None:
    assert as_document({"status": "passed"}) == {"status": "passed"}
    assert as_document(None) == {}
    assert as_list(["one", "two"]) == ["one", "two"]
    assert as_int("7") == 7
    assert as_float("1.5") == 1.5
    assert as_text("ready") == "ready"
    assert as_path("evidence/report.json") == Path("evidence/report.json")
    with pytest.raises((TypeError, ValueError)):
        as_path(None)
    with pytest.raises((TypeError, ValueError)):
        as_text(7)


def test_v141_open_folder_uses_optional_windows_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    opened: list[Path] = []
    monkeypatch.setattr(api_info.os, "name", "nt")
    monkeypatch.setattr(api_info.os, "startfile", opened.append, raising=False)

    api_info.open_folder(tmp_path)

    assert opened == [tmp_path]


def test_v14_splitter_preserves_cross_chunk_state_and_early_return() -> None:
    body = ["    total = value"]
    body.extend(f"    total += {index}" for index in range(85))
    body.extend(["    if value < 0:", "        return -1", "    return total"])
    source = "def route(value: int) -> int:\n" + "\n".join(body) + "\n"

    migrated = _split_one(source, "route", 1, limit=100)
    namespace: dict[str, object] = {}
    exec(migrated, namespace)

    assert namespace["route"](2) == 2 + sum(range(85))  # type: ignore[operator]
    assert namespace["route"](-2) == -1  # type: ignore[operator]
    assert "_route_part_01" in namespace


def test_v14_quality_policy_rejects_type_and_mypy_budget_growth() -> None:
    policy = json.loads((ROOT / "architecture-v14-quality.json").read_text(encoding="utf-8"))
    typing = collect_typing_metrics(ROOT)
    forged_typing = {**typing, "raw_dict_str_any_count": policy["typing"]["raw_dict_str_any_max_count"] + 1}
    assert any("typing_raw_dict_str_any" in value for value in _typing_blockers(forged_typing, policy))
    forged_explicit = {**typing, "explicit_any_count": policy["typing"]["explicit_any_max_count"] + 1}
    assert any("typing_explicit_any" in value for value in _typing_blockers(forged_explicit, policy))
    file_budgets = policy["typing"]["explicit_any_file_budgets"]
    path, budget = next(iter(file_budgets.items()))
    forged_file = {
        **typing,
        "explicit_any_by_file": {**typing["explicit_any_by_file"], path: budget + 1},
    }
    assert any("typing_explicit_any_file" in value for value in _typing_blockers(forged_file, policy))

    allowed = policy["mypy"]["error_budgets"]
    mypy = {
        "status": "measured",
        "total_errors": policy["mypy"]["max_total_errors"] + 1,
        "error_budgets": {**allowed, "song_agent/new.py|name-defined": 1},
        "strict_status": "passed",
    }
    blockers = _mypy_blockers(mypy, policy)
    assert any("mypy_total" in value for value in blockers)
    assert any("mypy_new_error_budget" in value for value in blockers)


def test_v14_module_debt_is_registered_and_function_limits_are_hard() -> None:
    policy = json.loads((ROOT / "architecture-v14-quality.json").read_text(encoding="utf-8"))
    report = collect_complexity_metrics(ROOT, policy)

    assert report["status"] == "passed", report["blockers"]
    assert report["registered_oversized_module_count"] == len(policy["module_size_debt"])
    assert all(row["expires_version"] == "14.4.0" for row in policy["module_size_debt"])
    aggregate = policy["complexity"]["aggregate_debt"]
    assert report["aggregate"]["oversized_module_count"] <= aggregate["max_oversized_module_count"]
    assert report["aggregate"]["modules_over_1000_lines"] <= aggregate["max_modules_over_1000_lines"]
    assert report["aggregate"]["largest_module_lines"] <= aggregate["max_largest_module_lines"]
    assert report["aggregate"]["total_oversized_module_lines"] <= aggregate["max_total_oversized_module_lines"]
    assert aggregate["required_total_line_reduction"] > 0
    assert (ROOT / aggregate["architecture_decision"]).is_file()


def test_v141_quality_policy_closes_active_mypy_debt_and_checks_full_repository() -> None:
    policy = json.loads((ROOT / "architecture-v14-quality.json").read_text(encoding="utf-8"))
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    configured = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert policy["release_version"] == QUALITY_POLICY_VERSION
    assert policy["mypy"]["max_total_errors"] == 0
    assert policy["mypy"]["error_budgets"] == {}
    typing = collect_typing_metrics(ROOT)
    assert policy["typing"]["explicit_any_collector_schema_version"] == typing["collector_schema_version"]
    assert policy["typing"]["explicit_any_max_count"] == typing["explicit_any_count"]
    assert set(policy["typing"]["explicit_any_layer_budgets"]) >= {"platform", "application", "capabilities"}
    assert '"song_agent/domains"' in configured
    assert "python -m ruff check song_agent tests tools" in workflow
    assert "python -m mypy --no-incremental" in workflow


def test_v1412_explicit_any_collector_counts_alias_module_nested_and_quoted_annotations(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "sample.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "\n".join(
            [
                "from typing import Any, Any as _InterfaceType",
                "from typing_extensions import Any as _InferenceType",
                "import typing as t",
                "import typing_extensions as tx",
                "",
                "direct: Any",
                "alias: _InterfaceType",
                "module_alias: t.Any",
                "extension_alias: _InferenceType",
                "extension_module_alias: tx.Any",
                "nested: dict[str, list[_InterfaceType | t.Any]]",
                "quoted: \"_InterfaceType\"",
                "quoted_nested: \"dict[str, tx.Any]\"",
                "class Handler:",
                "    def route(self, value: \"_InferenceType\") -> list[\"t.Any\"]:",
                "        return []",
                "",
            ]
        ),
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    assert typing["explicit_any_count"] == 11
    assert typing["explicit_any_by_layer"] == {"interfaces": 11}
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/sample.py": 11}


def test_v1412_explicit_any_alias_growth_is_not_hidden_from_ratchet(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "alias_growth.py"
    target.parent.mkdir(parents=True)
    annotations = [f"field_{index}: _InterfaceType" for index in range(100)]
    target.write_text(
        "from typing import Any as _InterfaceType\n" + "\n".join(annotations) + "\n",
        encoding="utf-8",
    )
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": typing["collector_schema_version"],
            "explicit_any_max_count": 99,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/alias_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)

    assert typing["explicit_any_count"] == 100
    assert any("typing_explicit_any" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


def test_v1421_explicit_any_collector_counts_function_bodies_and_nested_scopes(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "nested.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        """from typing import Any as Alias, TYPE_CHECKING, TypeAlias
import typing as t

if TYPE_CHECKING:
    from typing_extensions import Any as CheckedAlias

DocumentAlias: TypeAlias = Alias

def outer(value: Alias) -> t.Any:
    local: Alias

    def nested(item: CheckedAlias) -> DocumentAlias:
        nested_local: t.Any
        return item

    return value

class Handler:
    from typing import Any as ScopedAlias

    def method(self, value: ScopedAlias) -> None:
        method_local: ScopedAlias

async def async_handler() -> Alias:
    return None
""",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    assert typing["explicit_any_count"] == 9
    assert typing["explicit_any_affected_file_count"] == 1


def test_v1421_explicit_any_local_growth_is_not_hidden_from_ratchet(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "local_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"    local_{index}: Alias" for index in range(100))
    target.write_text(f"from typing import Any as Alias\n\ndef route() -> None:\n{annotations}\n", encoding="utf-8")

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 100
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/local_growth.py": 100}


def test_v1422_explicit_any_collector_counts_control_flow_scope_imports(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "conditional.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        """if enabled:
    from typing import Any as ConditionalAlias
conditional_values: tuple[ConditionalAlias, ConditionalAlias]

future_value: FutureAlias
if enabled:
    from typing import Any as FutureAlias

try:
    from typing_extensions import Any as TryAlias
except ImportError:
    TryAlias = object
try_value: TryAlias

with context():
    import typing as scoped_typing
with_value: scoped_typing.Any

for item in items:
    from typing import Any as LoopAlias
loop_value: LoopAlias

match subject:
    case "typed":
        from typing import Any as MatchAlias
match_value: MatchAlias

def route() -> None:
    if enabled:
        from typing import Any as FunctionAlias
    local: FunctionAlias
""",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    assert typing["explicit_any_count"] == 8
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/conditional.py": 8}


def test_v1422_explicit_any_collector_honors_non_typing_shadow_bindings(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "shadowed.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        """from typing import Any as ClassAny
class ClassAny:
    pass
class_value: ClassAny

from typing import Any as FunctionAny
def FunctionAny() -> None:
    pass
function_value: FunctionAny

from typing import Any as AssignmentAny
AssignmentAny = int
assignment_value: AssignmentAny

class Any:
    pass
plain_shadow: Any
""",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_affected_file_count"] == 0


def test_v1422_explicit_any_collector_keeps_conflicting_future_and_outer_bindings_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "conflicts.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        """from __future__ import annotations

future_value: FutureAlias
if enabled:
    from typing import Any as FutureAlias
else:
    import typing as FutureAlias
qualified_future_value: FutureAlias.Any

from typing import Any as OuterAlias
class Handler:
    if enabled:
        OuterAlias = int
    value: OuterAlias
""",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 3
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/conflicts.py": 3}


def test_v1422_explicit_any_collector_propagates_module_and_mixed_alias_assignments(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "assigned_aliases.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        """import typing
ModuleAlias = typing
module_value: ModuleAlias.Any

if enabled:
    from typing import Any as MixedAlias
else:
    import typing as MixedAlias
AssignedMixedAlias = MixedAlias
mixed_direct: AssignedMixedAlias
mixed_qualified: AssignedMixedAlias.Any
""",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 3
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/assigned_aliases.py": 3}


def test_v1422_conditional_alias_growth_is_not_hidden_from_ratchet(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "conditional_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    target.write_text(f"if enabled:\n    from typing import Any as Alias\n{annotations}\n", encoding="utf-8")
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/conditional_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)

    assert typing["explicit_any_count"] == 100
    assert any("typing_explicit_any" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


def test_v1423_lambda_scope_cannot_hide_outer_any_growth(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "lambda_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    target.write_text(
        "from typing import Any as Alias\n"
        "parameter_shadow = lambda Alias: Alias\n"
        "walrus_shadow = lambda: (Alias := int)\n"
        "nested_shadow = lambda: (lambda: (Alias := int))\n"
        f"{annotations}\n",
        encoding="utf-8",
    )
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/lambda_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)

    assert typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    assert typing["explicit_any_count"] == 100
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/lambda_growth.py": 100}
    assert any("typing_explicit_any" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


@pytest.mark.parametrize(
    "definition",
    [
        '    registry = {"fn": lambda value=(Alias := t.Any): value}\n',
        "    def factory(value=(Alias := t.Any)):\n        return value\n",
        "    async def factory(*, value=(Alias := t.Any)):\n        return value\n",
    ],
)
def test_v1424_definition_time_defaults_cannot_hide_outer_any_growth(
    tmp_path: Path,
    definition: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "definition_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        f"{definition}"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/definition_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    assert typing["explicit_any_count"] == 100
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/definition_growth.py": 100}
    assert any("typing_explicit_any" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


def test_v1424_function_and_class_definition_expressions_use_outer_runtime_order(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "definition_order.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "import typing as t\n"
        "decorators = {t.Any: lambda value: value}\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "def ordered(value=(Alias := int)):\n    pass\n"
        "function_value: Alias\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "class Ordered((Alias := int, object)[1]):\n    pass\n"
        "class_value: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_affected_file_count"] == 0


def test_v1424_function_and_class_definition_expressions_propagate_any(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "definition_sources.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "import typing as t\n"
        "decorators = {t.Any: lambda value: value}\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "def decorated():\n    pass\n"
        "decorated_value: Alias\n"
        "Alias = int\n"
        "async def async_default(*, value=(Alias := t.Any)):\n    pass\n"
        "async_value: Alias\n"
        "Alias = int\n"
        "@decorators[(Alias := t.Any)]\n"
        "class Decorated:\n    pass\n"
        "decorated_class_value: Alias\n"
        "Alias = int\n"
        "class Based((Alias := t.Any, object)[1]):\n    pass\n"
        "base_value: Alias\n"
        "Alias = int\n"
        "class Meta(object, metaclass=(Alias := t.Any, type)[1]):\n    pass\n"
        "metaclass_value: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["collector_schema_version"] == EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION
    assert typing["explicit_any_count"] == 5
    assert typing["explicit_any_by_file"] == {"song_agent/interfaces/api/definition_sources.py": 5}


@pytest.mark.parametrize(
    "class_body",
    [
        "        Alias = t.Any\n",
        "        from typing import Any as Alias\n",
    ],
)
def test_v1425_class_global_binding_cannot_hide_outer_any_growth(
    tmp_path: Path,
    class_body: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "class_global_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        f"{class_body}"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/class_global_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert typing["explicit_any_count"] == 100
    assert typing["explicit_any_scope_blocker_count"] == 0
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


@pytest.mark.parametrize(
    "source",
    [
        "import typing as t\nAlias = int\ndef mutate():\n    global Alias\n    Alias = t.Any\nfield: Alias\n",
        "import typing as t\nAlias = int\nclass Probe:\n    global Alias\n    if enabled:\n        Alias = t.Any\nfield: Alias\n",
        "import typing as t\ndef outer():\n    Alias = int\n    def mutate():\n        nonlocal Alias\n        Alias = t.Any\n        field: Alias\n",
    ],
)
def test_v1425_unsupported_cross_scope_alias_flow_fails_closed(tmp_path: Path, source: str) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "unsupported_scope.py"
    target.parent.mkdir(parents=True)
    target.write_text(source, encoding="utf-8")

    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 100,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 100},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/unsupported_scope.py": 100},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)

    assert typing["explicit_any_scope_blocker_count"] >= 1
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)


def test_v1425_non_type_global_state_does_not_trigger_scope_blocker(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "ordinary_global.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "counter = 0\ndef increment():\n    global counter\n    counter += 1\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_scope_blocker_count"] == 0


@pytest.mark.parametrize(
    ("extra_import", "class_body"),
    [
        ("", "        for Alias in (t.Any,):\n            pass\n"),
        (
            "import contextlib\n",
            "        with contextlib.nullcontext(t.Any) as Alias:\n            pass\n",
        ),
        ("", "        match t.Any:\n            case Alias:\n                pass\n"),
    ],
)
def test_v1426_indirect_class_global_binding_fails_closed(
    tmp_path: Path,
    extra_import: str,
    class_body: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "indirect_target_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        f"{extra_import}"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        f"{class_body}"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/indirect_target_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert typing["explicit_any_scope_blockers"] == [
        {
            "path": "song_agent/interfaces/api/indirect_target_growth.py",
            "detail": "uncertain_annotation_binding:Alias",
        }
    ]
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


def test_v1426_indirect_non_type_global_without_annotation_is_not_blocked(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "ordinary_indirect_global.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "class Probe:\n    global value\n    for value in (1,):\n        pass\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


@pytest.mark.parametrize(
    ("extra_import", "class_body"),
    [
        (
            "",
            "        for Alias in ((t.Any,),):\n"
            "            pass\n"
            "        Alias = Alias[0]\n",
        ),
        (
            "import contextlib\n",
            "        with contextlib.nullcontext((t.Any,)) as Alias:\n"
            "            Alias = Alias[0]\n",
        ),
        (
            "",
            "        match (t.Any,):\n"
            "            case (Alias,):\n"
            "                Alias = (Alias,)[0]\n",
        ),
        (
            "",
            "        for Alias in ((t.Any,),):\n"
            "            pass\n"
            "        class Holder:\n"
            "            pass\n"
            "        Holder.value = Alias\n"
            "        Alias = Holder.value[0]\n",
        ),
        (
            "",
            "        for Alias in ((t.Any,),):\n"
            "            pass\n"
            "        Holder = [None]\n"
            "        Holder[0] = Alias\n"
            "        Alias = Holder[0][0]\n",
        ),
    ],
)
def test_v1427_derived_uncertain_class_global_binding_fails_closed(
    tmp_path: Path,
    extra_import: str,
    class_body: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "derived_uncertain_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        f"{extra_import}"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        f"{class_body}"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/derived_uncertain_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert typing["explicit_any_scope_blockers"] == [
        {
            "path": "song_agent/interfaces/api/derived_uncertain_growth.py",
            "detail": "uncertain_annotation_binding:Alias",
        }
    ]
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


@pytest.mark.parametrize(
    "class_body",
    [
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = Alias[0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = (Alias,)[0][0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = (lambda value: value)(Alias[0])\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = Alias[0] if True else int\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = Alias[0] or int\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Derived = Alias\n        Alias = Derived[0]\n",
        "        class Holder:\n            value = t.Any\n        for Alias in (Holder,):\n            pass\n        Alias = Alias.value\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Alias = (Alias[0], (Alias := int))[0]\n",
        "        for Alias in ([t.Any],):\n            pass\n        Alias += []\n        Alias = Alias[0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        class Holder:\n            pass\n        Holder.value = Alias\n        Alias = Holder.value[0]\n",
        "        for Alias in ((t.Any,),):\n            pass\n        Holder = [None]\n        Holder[0] = Alias\n        Alias = Holder[0][0]\n",
    ],
)
def test_v1427_uncertain_propagates_through_compound_expressions(
    tmp_path: Path,
    class_body: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "derived_expression.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    target.write_text(
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        f"{class_body}"
        f"{annotations}\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 100
    assert len(typing["explicit_any_scope_blockers"]) == 1
    assert typing["explicit_any_scope_blockers"][0]["path"] == "song_agent/interfaces/api/derived_expression.py"
    assert typing["explicit_any_scope_blockers"][0]["detail"] in {
        "uncertain_annotation_binding:Alias",
        "unknown_annotation_binding:Alias",
    }


@pytest.mark.parametrize(
    "class_body",
    [
        "        Holder = [None]\n        Ref = Holder\n        Ref[0] = Alias\n        Alias = Holder[0][0]\n",
        "        class Holder:\n            value = [None]\n        Ref = Holder\n        Ref.value = Alias\n        Alias = Holder.value[0]\n",
        "        Holder = [None]\n        Ref = Holder\n        Ref2 = Ref\n        Ref2[0] = Alias\n        Alias = Holder[0][0]\n",
        "        Holder = [None]\n        if bool(1):\n            Ref = Holder\n        else:\n            Ref = [None]\n        Ref[0] = Alias\n        Alias = Holder[0][0]\n",
        "        Holder = [None]\n        def store(target, value):\n            target[0] = value\n        store(Holder, Alias)\n        Alias = Holder[0][0]\n",
        "        Holder = [None]\n        def store(target, value):\n            target[0] = value\n        store(Holder, t.Any)\n        Alias = Holder[0]\n",
        "        Holder = []\n        Ref = Holder\n        Ref += [Alias]\n        Alias = Holder[0][0]\n",
        "        Holder = []\n        Ref = Holder\n        Ref += [t.Any]\n        Alias = Holder[0]\n",
    ],
)
def test_v1428_object_alias_mutation_propagates_uncertain(
    tmp_path: Path,
    class_body: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "object_alias_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        "        for Alias in ((t.Any,),):\n"
        "            pass\n"
        f"{class_body}"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/object_alias_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }
    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert typing["explicit_any_scope_blockers"] == [
        {
            "path": "song_agent/interfaces/api/object_alias_growth.py",
            "detail": "uncertain_annotation_binding:Alias",
        }
    ]
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


def test_v1428_object_alias_rebind_breaks_previous_group(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "object_alias_rebind.py"
    target.parent.mkdir(parents=True)
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        "        for Alias in ((t.Any,),):\n"
        "            pass\n"
        "        Holder = [int]\n"
        "        Ref = Holder\n"
        "        Ref = [None]\n"
        "        Ref[0] = Alias\n"
        "        Alias = Holder[0]\n"
        "field: Alias\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)

    typing = collect_typing_metrics(tmp_path)

    assert namespace["Alias"] is int
    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


@pytest.mark.parametrize(
    ("extra_source", "class_body"),
    [
        (
            "",
            "        Holder = [None]\n"
            "        Ref, = (Holder,)\n"
            "        Ref[0] = Alias\n"
            "        Alias = Holder[0][0]\n",
        ),
        (
            "",
            "        Holder = [None]\n"
            "        Store = [Holder]\n"
            "        Ref = Store[0]\n"
            "        Ref[0] = Alias\n"
            "        Alias = Holder[0][0]\n",
        ),
        (
            "",
            "        Holder = [None]\n"
            "        class Box:\n"
            "            pass\n"
            "        Box.value = Holder\n"
            "        Ref = Box.value\n"
            "        Ref[0] = Alias\n"
            "        Alias = Holder[0][0]\n",
        ),
        (
            "from typing import TypeVar\n"
            "T = TypeVar(\"T\")\n"
            "def identity(value: T) -> T:\n"
            "    return value\n",
            "        Holder = [None]\n"
            "        Ref = identity(Holder)\n"
            "        Ref[0] = Alias\n"
            "        Alias = Holder[0][0]\n",
        ),
    ],
)
def test_v1429_non_direct_alias_sources_fail_closed(
    tmp_path: Path,
    extra_source: str,
    class_body: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "non_direct_alias_growth.py"
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        f"{extra_source}"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        "        for Alias in ((t.Any,),):\n"
        "            pass\n"
        f"{class_body}"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/non_direct_alias_growth.py": 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }
    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert any(
        row == {
            "path": "song_agent/interfaces/api/non_direct_alias_growth.py",
            "detail": "uncertain_annotation_binding:Alias",
        }
        for row in typing["explicit_any_scope_blockers"]
    )
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


def test_v1429_dynamic_alias_without_any_mutation_does_not_poison_source(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "safe_dynamic_alias.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import TypeVar\n"
        "T = TypeVar(\"T\")\n"
        "def identity(value: T) -> T:\n"
        "    return value\n"
        "Holder = [int]\n"
        "Ref = identity(Holder)\n"
        "Ref[0] = str\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


@pytest.mark.parametrize(
    ("case_name", "class_body", "expected_scope_blocker"),
    [
        (
            "annotation_only",
            "        Holder = [None]\n"
            "        Ref = Holder\n"
            "        Ref: object\n"
            "        Ref[0] = Alias\n"
            "        Alias = Holder[0][0]\n",
            "uncertain_annotation_binding:Alias",
        ),
        (
            "starred_suffix",
            "        Holder = [None]\n"
            "        Head, *Middle, Ref = (None, None, None, Holder)\n"
            "        Ref[0] = Alias\n"
            "        Alias = Holder[0][0]\n",
            "uncertain_annotation_binding:Alias",
        ),
        (
            "interprocedural_write",
            "        Holder = [None]\n"
            "        def store(target):\n"
            "            target[0] = Alias\n"
            "        store(Holder)\n"
            "        Alias = Holder[0][0]\n",
            "unsupported_interprocedural_any_write",
        ),
    ],
)
def test_v14210_alias_dataflow_cases_fail_closed_at_every_ratchet_layer(
    tmp_path: Path,
    case_name: str,
    class_body: str,
    expected_scope_blocker: str,
) -> None:
    relative = f"song_agent/interfaces/api/v14210_{case_name}.py"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        "        for Alias in ((t.Any,),):\n"
        "            pass\n"
        f"{class_body}"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)

    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {relative: 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }
    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert any(
        row["detail"] == expected_scope_blocker
        or row["detail"].startswith(expected_scope_blocker + ":")
        for row in typing["explicit_any_scope_blockers"]
    )
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


def test_v14210_safe_interprocedural_member_write_does_not_create_a_blocker(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "safe_interprocedural_write.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "def store(target: list[type[object]]) -> None:\n"
        "    target[0] = str\n"
        "Holder: list[type[object]] = [int]\n"
        "store(Holder)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


@pytest.mark.parametrize(
    "call",
    ["store(Holder)", "store(target=Holder)", "writer(Holder)"],
)
def test_v14210_parameter_alias_write_summary_propagates_to_callers(
    tmp_path: Path,
    call: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "parameter_alias_write.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        "Holder = [None]\n"
        "def store(target):\n"
        "    alias = target\n"
        "    target = [None]\n"
        "    alias[0] = Any\n"
        "writer = store\n"
        f"{call}\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 1
    assert any(
        row["detail"].startswith("unsupported_interprocedural_any_write:any")
        for row in typing["explicit_any_scope_blockers"]
    )


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("target.append(Any)", "unsupported_interprocedural_any_call"),
        ("setattr(target, 'value', Any)", "unsupported_interprocedural_any_call"),
    ],
)
def test_v14210_unresolved_any_call_effects_fail_closed(
    tmp_path: Path,
    statement: str,
    expected: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "unresolved_call_effect.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        "Holder = []\n"
        "def store(target):\n"
        f"    {statement}\n"
        "store(Holder)\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert any(row["detail"] == expected for row in typing["explicit_any_scope_blockers"])


@pytest.mark.parametrize(
    ("case_name", "class_body"),
    [
        (
            "append",
            "        Holder = [None]\n"
            "        Store = []\n"
            "        Store.append(Holder)\n"
            "        Ref = Store[0]\n",
        ),
        (
            "extend",
            "        Holder = [None]\n"
            "        Store = []\n"
            "        Store.extend([Holder])\n"
            "        Ref = Store[0]\n",
        ),
        (
            "setattr",
            "        Holder = [None]\n"
            "        class Box:\n"
            "            pass\n"
            "        setattr(Box, 'value', Holder)\n"
            "        Ref = Box.value\n",
        ),
        (
            "helper_store",
            "        Holder = [None]\n"
            "        Store = []\n"
            "        def retain(target, value):\n"
            "            target.append(value)\n"
            "        retain(Store, Holder)\n"
            "        Ref = Store[0]\n",
        ),
        (
            "helper_global_store",
            "        Holder = [None]\n"
            "        global Store\n"
            "        Store = []\n"
            "        def retain(value):\n"
            "            Store.append(value)\n"
            "        retain(Holder)\n"
            "        Ref = Store[0]\n",
        ),
        (
            "method_alias",
            "        Holder = [None]\n"
            "        Store = []\n"
            "        sink = Store.append\n"
            "        sink(Holder)\n"
            "        Ref = Store[0]\n",
        ),
        (
            "classmethod_alias",
            "        class Helper:\n"
            "            @classmethod\n"
            "            def retain(cls, target, value):\n"
            "                target.append(value)\n"
            "        Holder = [None]\n"
            "        Store = []\n"
            "        sink = Helper.retain\n"
            "        sink(Store, Holder)\n"
            "        Ref = Store[0]\n",
        ),
        (
            "return_alias",
            "        Holder = [None]\n"
            "        def identity(value):\n"
            "            return value\n"
            "        Ref = identity(Holder)\n",
        ),
        (
            "decorated_helper",
            "        def transport(fn):\n"
            "            def wrapped(target, value):\n"
            "                target.append(value)\n"
            "            return wrapped\n"
            "        @transport\n"
            "        def observe(target, value):\n"
            "            return None\n"
            "        Holder = [None]\n"
            "        Store = []\n"
            "        observe(Store, Holder)\n"
            "        Ref = Store[0]\n",
        ),
        (
            "decorated_class",
            "        def transport(cls):\n"
            "            class Replacement:\n"
            "                @staticmethod\n"
            "                def observe(target, value):\n"
            "                    target.append(value)\n"
            "            return Replacement\n"
            "        @transport\n"
            "        class Helper:\n"
            "            @staticmethod\n"
            "            def observe(target, value):\n"
            "                return None\n"
            "        Holder = [None]\n"
            "        Store = []\n"
            "        Helper.observe(Store, Holder)\n"
            "        Ref = Store[0]\n",
        ),
        (
            "callable_instance",
            "        class Sink:\n"
            "            def __init__(self):\n"
            "                self.values = []\n"
            "            def __call__(self, value):\n"
            "                self.values.append(value)\n"
            "        Holder = [None]\n"
            "        sink = Sink()\n"
            "        sink(Holder)\n"
            "        Ref = sink.values[0]\n",
        ),
    ],
)
def test_v143_call_effect_alias_transport_fails_closed_at_every_ratchet_layer(
    tmp_path: Path,
    case_name: str,
    class_body: str,
) -> None:
    relative = f"song_agent/interfaces/api/v143_{case_name}.py"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    class Probe:\n"
        "        global Alias\n"
        "        for Alias in ((t.Any,),):\n"
        "            pass\n"
        f"{class_body}"
        "        Ref[0] = Alias\n"
        "        Alias = Holder[0][0]\n"
        f"{annotations}\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {relative: 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }

    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert any(row["detail"].endswith("annotation_binding:Alias") for row in typing["explicit_any_scope_blockers"])
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


@pytest.mark.parametrize(
    ("case_name", "body"),
    [
        (
            "positional_default",
            "        def retain(value, target=Store):\n"
            "            target.append(value)\n"
            "        retain(Holder)\n",
        ),
        (
            "keyword_only_default",
            "        def retain(value, *, target=Store):\n"
            "            target.append(value)\n"
            "        retain(Holder)\n",
        ),
        (
            "varargs",
            "        def retain(*values):\n"
            "            Store.append(values[0])\n"
            "        retain(Holder)\n",
        ),
        (
            "kwargs",
            "        def retain(**values):\n"
            "            values['target'].append(values['value'])\n"
            "        retain(target=Store, value=Holder)\n",
        ),
        (
            "starred_positional",
            "        def retain(value, target):\n"
            "            target.append(value)\n"
            "        retain(*(Holder, Store))\n",
        ),
        (
            "expanded_keyword",
            "        def retain(value, target):\n"
            "            target.append(value)\n"
            "        retain(**{'value': Holder, 'target': Store})\n",
        ),
        (
            "dynamic_starred_positional",
            "        def retain(value, target):\n"
            "            target.append(value)\n"
            "        packed = (Holder, Store)\n"
            "        retain(*packed)\n",
        ),
        (
            "dynamic_expanded_keyword",
            "        def retain(value, target):\n"
            "            target.append(value)\n"
            "        packed = {'value': Holder, 'target': Store}\n"
            "        retain(**packed)\n",
        ),
        (
            "lambda_closure",
            "        registry = {'retain': lambda value: Store.append(value)}\n"
            "        retain = registry['retain']\n"
            "        retain(Holder)\n",
        ),
        (
            "lambda_default",
            "        registry = {'retain': lambda value, target=Store: target.append(value)}\n"
            "        retain = registry['retain']\n"
            "        retain(Holder)\n",
        ),
        (
            "function_late_bound_rebind",
            "        def retain(value):\n"
            "            Store.append(value)\n"
            "        Store = []\n"
            "        retain(Holder)\n",
        ),
        (
            "lambda_late_bound_rebind",
            "        registry = {'retain': lambda value: Store.append(value)}\n"
            "        retain = registry['retain']\n"
            "        Store = []\n"
            "        retain(Holder)\n",
        ),
        (
            "lambda_factory",
            "        def factory(target):\n"
            "            return lambda value: target.append(value)\n"
            "        retain = factory(Store)\n"
            "        retain(Holder)\n",
        ),
    ],
)
def test_v1433_callable_binding_and_lambda_effects_fail_closed(
    tmp_path: Path,
    case_name: str,
    body: str,
) -> None:
    relative = f"song_agent/interfaces/api/v1433_{case_name}.py"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    for Alias in ((t.Any,),):\n"
        "        pass\n"
        "    Holder = [None]\n"
        "    Store = []\n"
        + textwrap.indent(textwrap.dedent(body), "    ")
        + "    Ref = Store[0]\n"
        + "    Ref[0] = Alias\n"
        + "    Alias = Holder[0][0]\n"
        + textwrap.indent(annotations, "    ")
        + "\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {relative: 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }
    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert any(row["detail"].endswith("annotation_binding:Alias") for row in typing["explicit_any_scope_blockers"])
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


@pytest.mark.parametrize(
    ("case_name", "body"),
    [
        (
            "named_function",
            "def retain(value):\n"
            "    Store.append(value)\n"
            "Store = []\n"
            "retain(Holder)\n",
        ),
        (
            "lambda",
            "registry = {'retain': lambda value: Store.append(value)}\n"
            "Store = []\n"
            "registry['retain'](Holder)\n",
        ),
        (
            "factory",
            "def factory():\n"
            "    def retain(value):\n"
            "        Store.append(value)\n"
            "    Store = []\n"
            "    return retain, Store\n"
            "retain, Store = factory()\n"
            "retain(Holder)\n",
        ),
        (
            "nested_function",
            "def outer():\n"
            "    def middle():\n"
            "        def retain(value):\n"
            "            Store.append(value)\n"
            "        Store = []\n"
            "        return retain, Store\n"
            "    return middle()\n"
            "retain, Store = outer()\n"
            "retain(Holder)\n",
        ),
        (
            "named_expression",
            "def retain(value):\n"
            "    Store.append(value)\n"
            "registry = {'store': (Store := [])}\n"
            "retain(Holder)\n",
        ),
        (
            "explicit_nonlocal",
            "def factory():\n"
            "    def retain(value):\n"
            "        nonlocal Store\n"
            "        Store.append(value)\n"
            "    Store = []\n"
            "    return retain, Store\n"
            "retain, Store = factory()\n"
            "retain(Holder)\n",
        ),
        (
            "sibling_nonlocal_rebind",
            "def factory():\n"
            "    Store = []\n"
            "    def retain(value):\n"
            "        Store.append(value)\n"
            "    def replace():\n"
            "        nonlocal Store\n"
            "        Store = []\n"
            "    replace()\n"
            "    return retain, Store\n"
            "retain, Store = factory()\n"
            "retain(Holder)\n",
        ),
        (
            "helper_global_rebind",
            "Store = []\n"
            "def retain(value):\n"
            "    Store.append(value)\n"
            "def replace():\n"
            "    global Store\n"
            "    Store = []\n"
            "replace()\n"
            "retain(Holder)\n",
        ),
    ],
)
def test_v1434_late_bound_lexical_captures_fail_closed(
    tmp_path: Path,
    case_name: str,
    body: str,
) -> None:
    relative = f"song_agent/interfaces/api/v1434_{case_name}.py"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"    field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    for Alias in ((t.Any,),):\n"
        "        pass\n"
        "    Holder = [None]\n"
        + textwrap.indent(body, "    ")
        + "    Ref = Store[0]\n"
        "    Ref[0] = Alias\n"
        "    Alias = Holder[0][0]\n"
        + annotations
        + "\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {relative: 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }
    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert any(
        row["detail"].endswith("annotation_binding:Alias")
        for row in typing["explicit_any_scope_blockers"]
    )
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


@pytest.mark.parametrize(
    ("case_name", "body"),
    [
        (
            "named_function",
            "def retain(value: object) -> None:\n"
            "    Store.append(value)  # type: ignore[name-defined]  # noqa: F821\n"
            "def replace() -> None:\n"
            "    global Store\n"
            "    Store = []  # type: ignore[var-annotated]\n"
            "replace()\n"
            "retain(Holder)\n",
        ),
        (
            "lambda",
            "retain = lambda value: Store.append(value)  # type: ignore[name-defined]  # noqa: E731, F821\n"
            "def replace() -> None:\n"
            "    global Store\n"
            "    Store = []  # type: ignore[var-annotated]\n"
            "replace()\n"
            "retain(Holder)\n",
        ),
        (
            "factory",
            "def factory() -> Callable[[object], None]:\n"
            "    def retain(value: object) -> None:\n"
            "        Store.append(value)  # type: ignore[name-defined]  # noqa: F821\n"
            "    return retain\n"
            "def replace() -> None:\n"
            "    global Store\n"
            "    Store = []  # type: ignore[var-annotated]\n"
            "replace()\n"
            "retain = factory()\n"
            "retain(Holder)\n",
        ),
        (
            "nested_function",
            "def outer() -> Callable[[object], None]:\n"
            "    def middle() -> Callable[[object], None]:\n"
            "        def retain(value: object) -> None:\n"
            "            Store.append(value)  # type: ignore[name-defined]  # noqa: F821\n"
            "        return retain\n"
            "    return middle()\n"
            "def replace() -> None:\n"
            "    global Store\n"
            "    Store = []  # type: ignore[var-annotated]\n"
            "replace()\n"
            "retain = outer()\n"
            "retain(Holder)\n",
        ),
    ],
)
def test_v1435_first_global_lexical_captures_fail_closed(
    tmp_path: Path,
    case_name: str,
    body: str,
) -> None:
    relative = f"song_agent/interfaces/api/v1435_{case_name}.py"
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    annotations = "\n".join(f"    field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "from collections.abc import Callable  # noqa: F401\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    for Alias in ((t.Any,),):\n"
        "        pass\n"
        "    Holder = [None]\n"
        + textwrap.indent(body, "    ")
        + "    Ref = Store[0]\n"
        "    Ref[0] = Alias\n"
        "    Alias = Holder[0][0]\n"
        + annotations
        + "\n"
    )
    target.write_text(source, encoding="utf-8")
    namespace: dict[str, object] = {}
    exec(compile(source, str(target), "exec"), namespace)
    typing = collect_typing_metrics(tmp_path)
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {relative: 99},
            "public_implementation_document_max_count": 0,
            "untyped_public_function_max_count": 0,
        }
    }
    blockers = _typing_blockers(typing, policy)
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    mypy = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--config-file", str(ROOT / "pyproject.toml"), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert ruff.returncode == 0, ruff.stdout + ruff.stderr
    assert mypy.returncode == 0, mypy.stdout + mypy.stderr
    assert typing["explicit_any_count"] == 100
    assert any(
        row["detail"].endswith("annotation_binding:Alias")
        for row in typing["explicit_any_scope_blockers"]
    )
    assert any("typing_explicit_any_scope_flow" in value for value in blockers)
    assert any("typing_explicit_any:" in value for value in blockers)
    assert any("typing_explicit_any_layer" in value for value in blockers)
    assert any("typing_explicit_any_file" in value for value in blockers)


@pytest.mark.parametrize(
    "body",
    [
        "    registry = {'get': lambda: Holder}\n    Ref = registry['get']()\n",
        "    def get():\n        return Holder\n    Ref = get()\n",
        "    def first(*values):\n        return values[0]\n    Ref = first(Holder)\n",
        "    def get(**values):\n        return values['target']\n    Ref = get(target=Holder)\n",
    ],
)
def test_v1433_callable_return_aliases_preserve_captured_and_member_origins(body: str) -> None:
    annotations = "\n".join(f"    field_{index}: Alias" for index in range(100))
    source = (
        "from __future__ import annotations\n"
        "import typing as t\n"
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    Alias = int\n"
        "else:\n"
        "    for Alias in ((t.Any,),):\n"
        "        pass\n"
        "    Holder = [None]\n"
        + body
        + "    Ref[0] = Alias\n"
        + "    Alias = Holder[0][0]\n"
        + annotations
        + "\n"
    )
    namespace: dict[str, object] = {}
    exec(compile(source, "<v1433-return-alias>", "exec"), namespace)
    collector = _ExplicitAnyCollector()
    collector.visit(ast.parse(source))

    assert namespace["Alias"] is __import__("typing").Any
    assert len(namespace["__annotations__"]) == 100
    assert collector.count == 100
    assert any(value.endswith("annotation_binding:Alias") for value in collector.blockers)


def test_v143_ordinary_call_alias_transport_without_any_is_not_blocked(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "safe_call_transport.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "Holder = [int]\n"
        "Store = []\n"
        "Store.append(Holder)\n"
        "Ref = Store[0]\n"
        "Ref[0] = str\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


def test_v143_local_isinstance_shadow_uses_function_summary(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "shadowed_isinstance.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        "Holder = [None]\n"
        "def isinstance(target, value):\n"
        "    target[0] = value\n"
        "isinstance(Holder, Any)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 1


def test_v143_known_pure_helper_does_not_cross_taint_arguments(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "safe_local_helper.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        "Holder = [int]\n"
        "def observe(target, value):\n"
        "    return None\n"
        "observe(Holder, Any)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


def test_v143_staticmethod_summary_does_not_shift_positional_arguments(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "staticmethod_summary.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        "class Helper:\n"
        "    @staticmethod\n"
        "    def store(target, value):\n"
        "        target[0] = value\n"
        "Holder = [None]\n"
        "Helper.store(Holder, Any)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 1


def test_v143_classmethod_factory_does_not_taint_class_object(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "classmethod_factory.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        "class Factory:\n"
        "    @classmethod\n"
        "    def make(cls, value):\n"
        "        return cls()\n"
        "Result = Factory.make(Any)\n"
        "Alias = Factory\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


def test_v143_classmethod_payload_does_not_alias_the_class_object(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "classmethod_payload.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "class Factory:\n"
        "    @classmethod\n"
        "    def parse(cls, payload):\n"
        "        observe(payload)\n"
        "        return cls()\n"
        "payload = {'value': 1}\n"
        "Factory.parse(payload)\n"
        "Alias = Factory\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


def test_v143_comprehension_result_does_not_alias_the_called_class(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "comprehension_callable.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "class Item:\n"
        "    @classmethod\n"
        "    def parse(cls, value):\n"
        "        return cls()\n"
        "values = [1, 2]\n"
        "items = [Item.parse(value) for value in values]\n"
        "observe(items)\n"
        "Alias = Item\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


@pytest.mark.parametrize(
    "import_source,decorator",
    [
        ("from dataclasses import dataclass\n", "@dataclass(frozen=True)"),
        ("import dataclasses as dc\n", "@dc.dataclass(frozen=True)"),
    ],
)
def test_v143_dataclass_preserves_proven_class_surface(
    tmp_path: Path,
    import_source: str,
    decorator: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "dataclass_surface.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        f"{import_source}"
        f"{decorator}\n"
        "class Helper:\n"
        "    label: str = 'helper'\n"
        "    @staticmethod\n"
        "    def store(target, value):\n"
        "        target[0] = value\n"
        "Holder = [None]\n"
        "Helper.store(Holder, Any)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 1


@pytest.mark.parametrize("decorator_name", ["staticmethod", "classmethod"])
def test_v143_shadowed_builtin_method_decorator_is_not_trusted(
    tmp_path: Path,
    decorator_name: str,
) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / f"shadowed_{decorator_name}.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "import builtins\n"
        "from typing import Any\n"
        "def replacement(target, value):\n"
        "    target[0] = value\n"
        f"def {decorator_name}(fn):\n"
        "    return builtins.staticmethod(replacement)\n"
        "class Helper:\n"
        f"    @{decorator_name}\n"
        "    def observe(target, value):\n"
        "        return None\n"
        "Holder = [None]\n"
        "Helper.observe(Holder, Any)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 1


def test_v143_shadowed_dataclass_decorator_is_not_trusted(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "shadowed_dataclass.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
        "def replacement(target, value):\n"
        "    target[0] = value\n"
        "class Replacement:\n"
        "    observe = staticmethod(replacement)\n"
        "def transport(cls):\n"
        "    return Replacement\n"
        "dataclass = transport\n"
        "@dataclass\n"
        "class Helper:\n"
        "    @staticmethod\n"
        "    def observe(target, value):\n"
        "        return None\n"
        "Holder = [None]\n"
        "Helper.observe(Holder, Any)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 1


def test_v143_conditional_dataclass_binding_is_not_trusted(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "conditional_dataclass.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from dataclasses import dataclass as real_dataclass\n"
        "from typing import Any\n"
        "def replacement(target, value):\n"
        "    target[0] = value\n"
        "class Replacement:\n"
        "    observe = staticmethod(replacement)\n"
        "def transport(cls):\n"
        "    return Replacement\n"
        "if bool(1):\n"
        "    dataclass = transport\n"
        "else:\n"
        "    dataclass = real_dataclass\n"
        "@dataclass\n"
        "class Helper:\n"
        "    @staticmethod\n"
        "    def observe(target, value):\n"
        "        return None\n"
        "Holder = [None]\n"
        "Helper.observe(Holder, Any)\n"
        "Alias = Holder[0]\n"
        "field: Alias\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 1


def test_v1427_derived_non_type_global_without_annotation_is_not_blocked(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "interfaces" / "api" / "ordinary_derived_global.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "class Probe:\n"
        "    global value\n"
        "    for value in ((1,),):\n"
        "        pass\n"
        "    value = value[0]\n",
        encoding="utf-8",
    )

    typing = collect_typing_metrics(tmp_path)

    assert typing["explicit_any_count"] == 0
    assert typing["explicit_any_scope_blocker_count"] == 0


def test_v1421_quality_metric_caches_invalidate_on_source_change(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "application" / "cache_probe.py"
    target.parent.mkdir(parents=True)
    target.write_text("from typing import Any\nvalue: Any\n", encoding="utf-8")
    policy = {
        "complexity": {"module_default_max_lines": 600, "aggregate_debt": {}},
        "module_size_debt": [],
    }

    first_typing = collect_typing_metrics(tmp_path)
    first_complexity = collect_complexity_metrics(tmp_path, policy)
    first_typing["explicit_any_count"] = -1
    target.write_text(
        "from typing import Any\nvalue: Any\nother: Any\n\ndef oversized() -> None:\n"
        + "    value = 1\n" * 151,
        encoding="utf-8",
    )

    second_typing = collect_typing_metrics(tmp_path)
    second_complexity = collect_complexity_metrics(tmp_path, policy)

    assert second_typing["explicit_any_count"] == 2
    assert second_complexity["oversized_function_count"] == 1
    assert first_complexity["oversized_function_count"] == 0


def test_v1421_typing_cache_uses_content_hash_for_same_length_changes(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "application" / "same_length.py"
    target.parent.mkdir(parents=True)
    target.write_text("from typing import Any\nvalue: Any\n", encoding="utf-8")
    first = collect_typing_metrics(tmp_path)

    target.write_text("from typing import Any\nvalue: int\n", encoding="utf-8")
    second = collect_typing_metrics(tmp_path)

    assert first["explicit_any_count"] == 1
    assert second["explicit_any_count"] == 0


def test_v1435_parallel_typing_collection_matches_single_file_metrics(tmp_path: Path) -> None:
    from song_agent.release_check.v14_quality import _collect_typing_file_metrics

    target = tmp_path / "song_agent" / "application" / "parallel_probe.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from typing import Any\n"
        "value: Any\n"
        "def route(item: Any) -> Any:\n"
        "    return item\n",
        encoding="utf-8",
    )

    row = _collect_typing_file_metrics((str(target), str(tmp_path)))
    aggregate = collect_typing_metrics(tmp_path)

    assert row["explicit_any_count"] == 3
    assert aggregate["explicit_any_count"] == row["explicit_any_count"]
    assert aggregate["explicit_any_by_file"] == {"song_agent/application/parallel_probe.py": 3}


def test_v1435_typing_collection_avoids_nested_xdist_process_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from song_agent.release_check.v14_quality import _typing_worker_count

    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")

    assert _typing_worker_count() == 1


def test_v1435_typing_collection_uses_bounded_parallel_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import song_agent.release_check.v14_quality as quality

    observed: dict[str, int] = {}

    class ImmediateExecutor:
        def __init__(self, *, max_workers: int) -> None:
            observed["max_workers"] = max_workers

        def __enter__(self) -> ImmediateExecutor:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def map(
            self,
            function: Callable[[tuple[str, str]], dict[str, object]],
            arguments: Iterable[tuple[str, str]],
            *,
            chunksize: int,
        ) -> Iterator[dict[str, object]]:
            observed["chunksize"] = chunksize
            return map(function, arguments)

    root = tmp_path / "song_agent" / "application"
    root.mkdir(parents=True)
    for index in range(quality.TYPING_PARALLEL_FILE_THRESHOLD):
        (root / f"parallel_{index:02d}.py").write_text(
            "from typing import Any\nvalue: Any\n",
            encoding="utf-8",
        )
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    monkeypatch.setattr(quality, "ProcessPoolExecutor", ImmediateExecutor)
    monkeypatch.setattr(quality, "_typing_worker_count", lambda: quality.TYPING_MAX_WORKERS)

    metrics = quality._collect_typing_metrics_uncached(tmp_path)

    assert metrics["explicit_any_count"] == quality.TYPING_PARALLEL_FILE_THRESHOLD
    assert observed == {"max_workers": quality.TYPING_MAX_WORKERS, "chunksize": 4}


def test_v1421_static_gate_detects_generated_split_suppressions_and_mypy_exclusion(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "domains" / "v142_generated.py"
    target.parent.mkdir(parents=True)
    target.write_text("# mypy: ignore-errors\n# ruff: noqa\nbind_globals(globals())\n", encoding="utf-8")
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "split_v142_oversized_modules.py").write_text("# forbidden\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """[tool.mypy]
files = ["song_agent/platform"]
exclude = "v142_.*\\\\.py$"
""",
        encoding="utf-8",
    )

    violations = collect_v1421_static_violations(tmp_path)

    assert violations["generated_modules"] == ["song_agent/domains/v142_generated.py"]
    assert violations["splitter_present"] is True
    assert violations["suppressions"] == ["song_agent/domains/v142_generated.py"]
    assert violations["runtime_global_binders"] == ["song_agent/domains/v142_generated.py"]
    assert violations["mypy_roots_complete"] is False
    assert violations["mypy_exclude"]


def test_v141_quality_debt_closure_smoke_is_self_consistent() -> None:
    passed, detail = run_v141_quality_debt_closure_smoke(ROOT)

    assert passed, detail


def test_v14_mypy_ownership_ratchet_only_moves_down() -> None:
    policy = {"mypy": {"max_total_errors": 3, "error_budgets": {"old.py|name-defined": 3}}}
    _ratchet_mypy_policy(
        policy,
        {
            "status": "measured",
            "strict_status": "passed",
            "total_errors": 2,
            "error_budgets": {"new.py|attr-defined": 2},
        },
    )
    assert policy["mypy"] == {"max_total_errors": 2, "error_budgets": {"new.py|attr-defined": 2}}

    with pytest.raises(RuntimeError, match="cannot grow"):
        _ratchet_mypy_policy(
            policy,
            {
                "status": "measured",
                "strict_status": "passed",
                "total_errors": 3,
                "error_budgets": {"new.py|attr-defined": 3},
            },
        )


def test_v14_typing_ownership_ratchet_preserves_the_combined_ceiling() -> None:
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 8,
            "implementation_document_max_count": 4,
            "explicit_any_max_count": 3,
            "explicit_any_layer_budgets": {"application": 3},
            "explicit_any_file_budgets": {"song_agent/application/a.py": 2, "song_agent/application/b.py": 1},
        }
    }
    _ratchet_typing_policy(
        policy,
        {
            "raw_dict_str_any_count": 5,
            "implementation_document_count": 6,
            "explicit_any_count": 3,
            "explicit_any_by_layer": {"application": 3},
            "explicit_any_by_file": {"song_agent/application/a.py": 2, "song_agent/application/b.py": 1},
            "public_implementation_document_count": 0,
            "untyped_public_function_count": 0,
        },
    )
    assert policy["typing"] == {
        "raw_dict_str_any_max_count": 5,
        "implementation_document_max_count": 6,
        "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
        "explicit_any_max_count": 3,
        "explicit_any_affected_file_max_count": 0,
        "explicit_any_layer_budgets": {"application": 3},
        "explicit_any_file_budgets": {"song_agent/application/a.py": 2, "song_agent/application/b.py": 1},
    }

    with pytest.raises(RuntimeError, match="cannot grow"):
        _ratchet_typing_policy(
            policy,
            {
                "raw_dict_str_any_count": 6,
                "implementation_document_count": 6,
                "explicit_any_count": 3,
                "explicit_any_by_layer": {"application": 3},
                "explicit_any_by_file": {"song_agent/application/a.py": 2, "song_agent/application/b.py": 1},
                "public_implementation_document_count": 0,
                "untyped_public_function_count": 0,
            },
        )

    with pytest.raises(RuntimeError, match="explicit Any file cannot grow"):
        _ratchet_typing_policy(
            policy,
            {
                "raw_dict_str_any_count": 5,
                "implementation_document_count": 6,
                "explicit_any_count": 3,
                "explicit_any_by_layer": {"application": 3},
                "explicit_any_by_file": {"song_agent/application/a.py": 3},
                "public_implementation_document_count": 0,
                "untyped_public_function_count": 0,
            },
        )


def test_v1422_collector_schema_upgrade_cannot_relax_any_budget() -> None:
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": 4,
            "explicit_any_max_count": 99,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 99},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/conditional.py": 99},
        }
    }
    metrics = {
        "raw_dict_str_any_count": 0,
        "implementation_document_count": 0,
        "explicit_any_count": 100,
        "explicit_any_affected_file_count": 1,
        "explicit_any_by_layer": {"interfaces": 100},
        "explicit_any_by_file": {"song_agent/interfaces/api/conditional.py": 100},
        "public_implementation_document_count": 0,
        "untyped_public_function_count": 0,
    }

    with pytest.raises(RuntimeError, match="explicit Any cannot grow"):
        _ratchet_typing_policy(policy, metrics)


def test_v1425_typing_updater_rejects_unsupported_scope_flow() -> None:
    policy = {
        "typing": {
            "raw_dict_str_any_max_count": 0,
            "implementation_document_max_count": 0,
            "explicit_any_collector_schema_version": EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
            "explicit_any_max_count": 1,
            "explicit_any_affected_file_max_count": 1,
            "explicit_any_layer_budgets": {"interfaces": 1},
            "explicit_any_file_budgets": {"song_agent/interfaces/api/probe.py": 1},
        }
    }
    metrics = {
        "raw_dict_str_any_count": 0,
        "implementation_document_count": 0,
        "explicit_any_count": 1,
        "explicit_any_affected_file_count": 1,
        "explicit_any_by_layer": {"interfaces": 1},
        "explicit_any_by_file": {"song_agent/interfaces/api/probe.py": 1},
        "explicit_any_scope_blocker_count": 1,
        "public_implementation_document_count": 0,
        "untyped_public_function_count": 0,
    }

    with pytest.raises(RuntimeError, match="unsupported global/nonlocal alias flow"):
        _ratchet_typing_policy(policy, metrics)


def test_v14_complexity_ratchet_rejects_file_growth_even_when_total_decreases(tmp_path: Path) -> None:
    root = tmp_path
    first = root / "song_agent" / "domains" / "sample_a.py"
    second = root / "song_agent" / "domains" / "sample_b.py"
    first.parent.mkdir(parents=True)
    first.write_text("# a\n" * 710, encoding="utf-8")
    second.write_text("# b\n" * 780, encoding="utf-8")
    policy = {
        "complexity": {
            "module_default_max_lines": 600,
            "aggregate_debt": {
                "max_oversized_module_count": 2,
                "max_modules_over_1000_lines": 0,
                "max_largest_module_lines": 800,
                "max_total_oversized_module_lines": 1500,
            },
        },
        "module_size_debt": [
            {"path": "song_agent/domains/sample_a.py", "max_lines": 700},
            {"path": "song_agent/domains/sample_b.py", "max_lines": 800},
        ],
    }

    with pytest.raises(RuntimeError, match="cannot grow registered modules"):
        _ratchet_complexity_policy(policy, root)


def test_v1421_stabilization_rollback_smoke_is_self_consistent() -> None:
    passed, detail = run_v1421_stabilization_rollback_smoke(ROOT)

    assert passed, detail


def test_v1422_explicit_any_scope_smoke_is_self_consistent() -> None:
    passed, detail = run_v1422_explicit_any_scope_smoke(ROOT)

    assert passed, detail


def test_v1423_explicit_any_lambda_scope_smoke_is_self_consistent() -> None:
    passed, detail = run_v1423_explicit_any_lambda_scope_smoke(ROOT)

    assert passed, detail


def test_v1424_explicit_any_definition_time_scope_smoke_is_self_consistent() -> None:
    passed, detail = run_v1424_explicit_any_definition_time_scope_smoke(ROOT)

    assert passed, detail


def test_v1425_explicit_any_class_global_scope_smoke_is_self_consistent() -> None:
    passed, detail = run_v1425_explicit_any_class_global_scope_smoke(ROOT)

    assert passed, detail


def test_v1426_explicit_any_indirect_target_scope_smoke_is_self_consistent() -> None:
    passed, detail = run_v1426_explicit_any_indirect_target_scope_smoke(ROOT)

    assert passed, detail


def test_v1427_explicit_any_derived_uncertain_scope_smoke_is_self_consistent() -> None:
    passed, detail = run_v1427_explicit_any_derived_uncertain_scope_smoke(ROOT)

    assert passed, detail


def test_v1428_explicit_any_object_alias_scope_smoke_is_self_consistent() -> None:
    passed, detail = run_v1428_explicit_any_object_alias_scope_smoke(ROOT)

    assert passed, detail


def test_v1429_explicit_any_alias_dataflow_smoke_is_self_consistent() -> None:
    passed, detail = run_v1429_explicit_any_alias_dataflow_smoke(ROOT)

    assert passed, detail


def test_v14210_explicit_any_alias_fail_closed_smoke_is_self_consistent() -> None:
    passed, detail = run_v14210_explicit_any_alias_fail_closed_smoke(ROOT)

    assert passed, detail


def test_v143_explicit_any_call_effect_dataflow_smoke_is_self_consistent() -> None:
    passed, detail = run_v143_explicit_any_call_effect_dataflow_smoke(ROOT)

    assert passed, detail


def test_v1431_call_effect_component_compaction_smoke_is_self_consistent() -> None:
    passed, detail = run_v1431_call_effect_component_compaction_smoke(ROOT)

    assert passed, detail


def test_v1432_expression_binding_single_pass_smoke_is_self_consistent() -> None:
    passed, detail = run_v1432_expression_binding_single_pass_smoke(ROOT)

    assert passed, detail


def test_v1433_call_binding_lambda_effect_smoke_is_self_consistent() -> None:
    passed, detail = run_v1433_call_binding_lambda_effect_smoke(ROOT)

    assert passed, detail


def test_v1434_late_bound_lexical_capture_smoke_is_self_consistent() -> None:
    passed, detail = run_v1434_late_bound_lexical_capture_smoke(ROOT)

    assert passed, detail


def test_v1435_first_global_lexical_capture_smoke_is_self_consistent() -> None:
    passed, detail = run_v1435_first_global_lexical_capture_smoke(ROOT)

    assert passed, detail


def test_v1432_expression_value_is_reused_for_one_ast_occurrence() -> None:
    tree = ast.parse("holder = [None]\nref = holder[0]")
    collector = _ExplicitAnyCollector()
    collector.visit(tree)
    assignment = tree.body[1]

    assert isinstance(assignment, ast.Assign)
    first = collector._expression_value(assignment.value)
    second = collector._expression_value(assignment.value)

    assert first is second


def test_v1432_quoted_annotation_parse_cache_keeps_scope_sensitive_counts() -> None:
    tree = ast.parse(
        "from typing import Any as Alias\n"
        "before: 'Alias'\n"
        "Alias = int\n"
        "after: 'Alias'\n"
    )
    collector = _ExplicitAnyCollector()

    collector.visit(tree)

    assert collector.count == 1
    assert set(collector._quoted_annotation_expressions) == {"Alias"}


def test_v1432_single_pass_annotation_scan_only_deduplicates_confirmed_typing_base() -> None:
    tree = ast.parse(
        "from typing import Any as Alias\n"
        "field: Alias.Any\n"
    )
    collector = _ExplicitAnyCollector()

    collector.visit(tree)

    assert collector.count == 1
    annotation = ast.parse("Alias.Any", mode="eval").body
    assert _annotation_any_count(annotation, {"Alias"}, set()) == 1
    assert _annotation_any_count(annotation, set(), {"Alias"}) == 1


def test_v1421_policy_full_resign_cannot_reallocate_file_or_module_ceilings() -> None:
    baseline = json.loads((ROOT / "architecture-v14-quality.json").read_text(encoding="utf-8"))
    typing_forged = json.loads(json.dumps(baseline))
    typing_path = next(iter(typing_forged["typing"]["explicit_any_file_budgets"]))
    typing_forged["typing"]["explicit_any_file_budgets"][typing_path] += 1
    typing_forged["integrity_hash"] = stable_hash(
        {key: value for key, value in typing_forged.items() if key != "integrity_hash"}
    )
    module_forged = json.loads(json.dumps(baseline))
    module_forged["module_size_debt"][0]["max_lines"] += 1
    module_forged["integrity_hash"] = stable_hash(
        {key: value for key, value in module_forged.items() if key != "integrity_hash"}
    )
    schema13_forged = json.loads(json.dumps(baseline))
    schema13_forged["typing"]["explicit_any_max_count"] += 1
    schema13_forged["typing"]["explicit_any_affected_file_max_count"] += 1
    schema13_forged["typing"]["explicit_any_layer_budgets"]["interfaces"] += 1
    schema13_forged["stabilization"]["alias_fail_closed_collector_hotfix"][
        "previous_explicit_any_ceiling"
    ] += 1
    schema13_forged["integrity_hash"] = stable_hash(
        {key: value for key, value in schema13_forged.items() if key != "integrity_hash"}
    )
    schema14_forged = json.loads(json.dumps(baseline))
    schema14_forged["typing"]["explicit_any_max_count"] += 1
    schema14_forged["stabilization"]["call_effect_dataflow_collector_migration"][
        "previous_explicit_any_ceiling"
    ] += 1
    schema14_forged["integrity_hash"] = stable_hash(
        {key: value for key, value in schema14_forged.items() if key != "integrity_hash"}
    )
    schema15_forged = json.loads(json.dumps(baseline))
    schema15_forged["stabilization"]["call_binding_lambda_effect_collector_migration"][
        "previous_explicit_any_ceiling"
    ] += 1
    schema15_forged["integrity_hash"] = stable_hash(
        {key: value for key, value in schema15_forged.items() if key != "integrity_hash"}
    )

    assert "v14_quality_policy_stabilization_typing_file_budgets" in _policy_blockers(typing_forged)
    assert "v14_quality_policy_stabilization_module_debt" in _policy_blockers(module_forged)
    schema13_blockers = _policy_blockers(schema13_forged)
    assert "v14_quality_policy_alias_fail_closed_collector_migration" in schema13_blockers
    assert "v14_quality_policy_alias_fail_closed_ceilings" in schema13_blockers
    schema14_blockers = _policy_blockers(schema14_forged)
    assert "v14_quality_policy_call_effect_dataflow_collector_migration" in schema14_blockers
    assert "v14_quality_policy_alias_fail_closed_ceilings" in schema14_blockers
    assert "v14_quality_policy_call_binding_lambda_effect_collector_migration" in _policy_blockers(
        schema15_forged
    )


def test_v14_source_tree_hash_is_independent_of_line_endings(tmp_path: Path) -> None:
    target = tmp_path / "song_agent" / "platform" / "sample.py"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"VALUE = 1\n")
    expected = active_source_tree_hash(tmp_path)

    target.write_bytes(b"VALUE = 1\r\n")

    assert active_source_tree_hash(tmp_path) == expected


def test_v14_compact_coverage_excludes_machine_specific_metadata(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    files = {
        "song_agent/platform/sample.py": {
            "summary": {"num_statements": 2, "covered_lines": 2, "missing_lines": 0}
        }
    }
    first = root / "first.json"
    second = root / "second.json"
    first.write_text(json.dumps({"meta": {"generated_at": "one"}, "files": files}), encoding="utf-8")
    second.write_text(json.dumps({"meta": {"generated_at": "two"}, "files": files}), encoding="utf-8")
    first_output = root / "first-compact.json"
    second_output = root / "second-compact.json"

    _write_compact_coverage(first, first_output, root)
    _write_compact_coverage(second, second_output, root)

    first_document = json.loads(first_output.read_text(encoding="utf-8"))
    assert first_document == json.loads(second_output.read_text(encoding="utf-8"))
    assert first_document["schema_version"] == 2
    assert "source_report_sha256" not in first_document
