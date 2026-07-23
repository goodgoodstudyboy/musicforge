from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from song_agent.release_check.v14_quality import (
    EXPLICIT_ANY_COLLECTOR_SCHEMA_VERSION,
    QUALITY_POLICY_VERSION,
    _mypy_blockers,
    _policy_blockers,
    _typing_blockers,
    active_source_tree_hash,
    collect_v1421_static_violations,
    collect_complexity_metrics,
    collect_typing_metrics,
    evaluate_v14_quality,
    run_v141_quality_debt_closure_smoke,
    run_v1421_stabilization_rollback_smoke,
    run_v1422_explicit_any_scope_smoke,
    run_v1423_explicit_any_lambda_scope_smoke,
    run_v1424_explicit_any_definition_time_scope_smoke,
    run_v1425_explicit_any_class_global_scope_smoke,
    run_v1426_explicit_any_indirect_target_scope_smoke,
    run_v1427_explicit_any_derived_uncertain_scope_smoke,
    run_v1428_explicit_any_object_alias_scope_smoke,
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
    assert all(row["expires_version"] == "14.3.0" for row in policy["module_size_debt"])
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

    assert "v14_quality_policy_stabilization_typing_file_budgets" in _policy_blockers(typing_forged)
    assert "v14_quality_policy_stabilization_module_debt" in _policy_blockers(module_forged)


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
