from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.release_check.v14_quality import (
    _mypy_blockers,
    _typing_blockers,
    active_source_tree_hash,
    collect_complexity_metrics,
    collect_typing_metrics,
    evaluate_v14_quality,
)
from song_agent.platform.contracts import as_document, as_float, as_int, as_list, as_path, as_text
from tools.adopt_v141_composition_types import adopt_composition_types
from tools.adopt_v141_document_coercions import adopt_document_coercions
from tools.consolidate_v141_contract_imports import consolidate_contract_imports
from tools.migrate_v14_private_document_types import migrate_private_document_types
from tools.split_v14_active_functions import split_active_functions
from tools.split_v14_interface_functions import _split_one, split_interfaces
from tools.update_v14_quality_policy import _ratchet_mypy_policy, _ratchet_typing_policy, _write_compact_coverage


ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.contract


def test_v14_typing_and_complexity_ratchets_pass_without_hiding_public_debt() -> None:
    report = evaluate_v14_quality(ROOT, run_mypy=False, require_coverage=False)

    assert report["status"] == "passed", report["blockers"]
    assert report["typing"]["raw_dict_str_any_count"] <= 8774
    assert report["typing"]["raw_dict_str_any_count"] <= int(12535 * 0.70)
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
    assert all(row["expires_version"] == "14.2.0" for row in policy["module_size_debt"])
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

    assert policy["release_version"] == "14.1.0"
    assert policy["mypy"]["max_total_errors"] == 0
    assert policy["mypy"]["error_budgets"] == {}
    assert '"song_agent/domains"' in configured
    assert "python -m ruff check song_agent tests tools" in workflow
    assert "python -m mypy --no-incremental" in workflow


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
        }
    }
    _ratchet_typing_policy(
        policy,
        {
            "raw_dict_str_any_count": 5,
            "implementation_document_count": 6,
            "public_implementation_document_count": 0,
            "untyped_public_function_count": 0,
        },
    )
    assert policy["typing"] == {
        "raw_dict_str_any_max_count": 5,
        "implementation_document_max_count": 6,
    }

    with pytest.raises(RuntimeError, match="cannot grow"):
        _ratchet_typing_policy(
            policy,
            {
                "raw_dict_str_any_count": 6,
                "implementation_document_count": 6,
                "public_implementation_document_count": 0,
                "untyped_public_function_count": 0,
            },
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
