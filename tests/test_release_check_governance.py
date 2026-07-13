from __future__ import annotations

import json
from pathlib import Path

from song_agent.release_check.checks.registry import check_domain, provider_inventory, resolve_callable
from song_agent.release_check.matrix import all_check_definitions, definition_to_dict, get_check_definition, select_check_definitions, validate_check_definitions
from song_agent.release_check.performance import PROFILE_BUDGET_WARNING_ONLY


ROOT = Path(__file__).resolve().parents[1]


def test_release_check_facade_and_domain_registry() -> None:
    assert len((ROOT / "song_agent" / "release_checks.py").read_text(encoding="utf-8").splitlines()) < 300
    assert len(provider_inventory()) == 8
    assert check_domain(group="audio") == "quality"
    assert check_domain(group="command-center") == "program"
    assert callable(resolve_callable("_v1219_evidence_policy_smoke"))
    assert definition_to_dict(get_check_definition("v1215.verification_kernel_smoke"))["domain"] == "security"
    assert definition_to_dict(get_check_definition("v1212.receiver_acceptance_change_control_semantics"))["domain"] == "program"


def test_current_profiles_exclude_historical_monolith() -> None:
    for profile in ("latest", "ga", "v12"):
        definitions = select_check_definitions(profile=profile, run_tests=False)
        assert all(not row.version or tuple(int(part) for part in row.version.split(".")) >= (12, 9) for row in definitions)
    legacy = select_check_definitions(profile="nightly", run_tests=False)
    assert any(row.version and row.version.startswith("7.") for row in legacy)
    assert all("legacy" in row.tags for row in legacy)


def test_matrix_budgets_are_hard_or_documented() -> None:
    validate_check_definitions()
    assert not PROFILE_BUDGET_WARNING_ONLY
    for definition in all_check_definitions():
        assert definition.duration_budget_seconds is not None
        if definition.budget_warning_only:
            assert definition.budget_exception_reason
            assert definition.budget_exception_expires_version


def test_deprecation_catalog_is_machine_readable() -> None:
    payload = json.loads((ROOT / "docs" / "deprecations.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    required = {
        "old_path",
        "replacement",
        "import_usage_count",
        "cli_api_aliases",
        "data_schema_impact",
        "introduced_version",
        "removal_version",
        "rollback_strategy",
    }
    assert payload["entries"]
    assert all(required <= set(row) for row in payload["entries"])
