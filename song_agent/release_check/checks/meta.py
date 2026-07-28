from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from song_agent.release_check_architecture import run_architecture_guardrails_smoke, run_architecture_ratchet_smoke
from song_agent.release_check.checks.legacy import delegated_check
from song_agent.release_check.repository_checks import (
    git_status_check,
    musicforge_configs_ignored_check,
    musicforge_configs_untracked_check,
    remote_url_token_check,
    version_consistency,
)
from song_agent.release_check_interfaces import run_interface_registry_smoke
from song_agent.release_check_persistence_kernel import run_persistence_kernel_smoke, run_program_persistence_authority_smoke
from song_agent.release_check_program_vertical import run_program_vertical_slice_smoke
from song_agent.release_check.lts_cutover import run_lts_cutover_smoke
from song_agent.release_check_evidence_policy import run_policy_gate_cutover_smoke
from song_agent.release_check_governance_v137 import run_release_check_ci_docs_governance_smoke
from song_agent.release_check.lts_recertification import run_lts_recertification_smoke
from song_agent.release_check.v14_architecture import run_v14_architecture_cutover_smoke
from song_agent.release_check.v14_compatibility import run_v14_compatibility_zero_smoke
from song_agent.release_check.v14_certification import (
    run_v14_domain_vertical_slice_smoke,
    run_v14_migration_rollback_smoke,
)
from song_agent.release_check.v14_contracts import run_v14_public_contract_compatibility_smoke
from song_agent.release_check.v14_reviewer import run_v14_reviewer_package_smoke
from song_agent.release_check.v14_quality import (
    run_v14_interface_application_boundary_smoke,
    run_v14_typing_coverage_ratchet_smoke,
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
)


DOMAIN = "meta"
GROUPS = frozenset({"core", "git", "meta", "release-check", "architecture"})
TAGS = frozenset({"architecture", "performance", "fixture-cache"})


def run_release_check_governance_smoke(root: Path) -> tuple[bool, str]:
    try:
        from song_agent.release_check.checks.registry import provider_inventory
        from song_agent.release_check.matrix import all_check_definitions
        from song_agent.release_check.performance import PROFILE_BUDGET_WARNING_ONLY
        from song_agent.release_check.runner import run_release_check_matrix

        facade_removed = not (root / "song_agent" / "release_checks.py").exists()
        legacy = root / "song_agent" / "release_check" / "checks" / "legacy" / "monolith.py"
        marker_text = (root / "pyproject.toml").read_text(encoding="utf-8")
        workflow = root / ".github" / "workflows" / "quality.yml"
        catalog_path = root / "docs" / "deprecations.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        definitions = list(all_check_definitions())
        current = [
            row
            for row in definitions
            if row.version and _version_key(row.version) >= (12, 13) and "legacy" not in row.tags
        ]
        hard_budgets = all(
            row.duration_budget_seconds is not None
            and not row.budget_warning_only
            and {"v12", "latest", "ga"}.intersection(row.profiles).issubset(row.budget_enforced_profiles)
            for row in current
        )
        empty = run_release_check_matrix(repo_root=root, profile="latest", since="99.0", run_tests=False)
        details: dict[str, Any] = {
            "expired_facade_removed": facade_removed,
            "facade_under_300": facade_removed,
            "legacy_preserved": legacy.is_file(),
            "providers": len(provider_inventory()),
            "markers_configured": all(f'"{name}:' in marker_text for name in ("unit", "contract", "security", "integration", "legacy", "slow", "platform_windows")),
            "ci_present": workflow.is_file(),
            "deprecation_catalog": catalog.get("schema_version") == 1 and bool(catalog.get("entries")),
            "hard_current_budgets": hard_budgets,
            "profile_budgets_hard": not PROFILE_BUDGET_WARNING_ONLY,
            "empty_selection_failed": not empty.ok and empty.results[0].check_id == "release_check.selection",
        }
        return all(details.values()), json.dumps(details, sort_keys=True)
    except Exception as exc:
        return False, str(exc)


def _version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else 0 for part in str(value).split("."))


CALLABLES = {
    "_git_status_check": git_status_check,
    "_remote_url_token_check": remote_url_token_check,
    "_musicforge_configs_untracked_check": musicforge_configs_untracked_check,
    "_musicforge_configs_ignored_check": musicforge_configs_ignored_check,
    "_version_consistency": version_consistency,
    "_v1213_release_check_acceleration_smoke": delegated_check("_v1213_release_check_acceleration_smoke"),
    "_v1214_architecture_guardrails_smoke": run_architecture_guardrails_smoke,
    "_v131_architecture_ratchet_smoke": run_architecture_ratchet_smoke,
    "_v1217_persistence_kernel_smoke": run_persistence_kernel_smoke,
    "_v133_program_persistence_authority_smoke": run_program_persistence_authority_smoke,
    "_v134_program_vertical_slice_smoke": run_program_vertical_slice_smoke,
    "_v135_interface_decomposition_smoke": run_interface_registry_smoke,
    "_v136_policy_gate_cutover_smoke": run_policy_gate_cutover_smoke,
    "_v137_release_check_ci_docs_governance_smoke": run_release_check_ci_docs_governance_smoke,
    "_v138_lts_recertification_smoke": run_lts_recertification_smoke,
    "_v140_architecture_cutover_smoke": run_v14_architecture_cutover_smoke,
    "_v140_compatibility_zero_smoke": run_v14_compatibility_zero_smoke,
    "_v140_interface_application_boundary_smoke": run_v14_interface_application_boundary_smoke,
    "_v140_domain_vertical_slice_smoke": run_v14_domain_vertical_slice_smoke,
    "_v140_migration_rollback_smoke": run_v14_migration_rollback_smoke,
    "_v140_public_contract_compatibility_smoke": run_v14_public_contract_compatibility_smoke,
    "_v140_reviewer_package_smoke": run_v14_reviewer_package_smoke,
    "_v140_typing_coverage_ratchet_smoke": run_v14_typing_coverage_ratchet_smoke,
    "_v141_quality_debt_closure_smoke": run_v141_quality_debt_closure_smoke,
    "_v1421_stabilization_rollback_smoke": run_v1421_stabilization_rollback_smoke,
    "_v1422_explicit_any_scope_smoke": run_v1422_explicit_any_scope_smoke,
    "_v1423_explicit_any_lambda_scope_smoke": run_v1423_explicit_any_lambda_scope_smoke,
    "_v1424_explicit_any_definition_time_scope_smoke": run_v1424_explicit_any_definition_time_scope_smoke,
    "_v1425_explicit_any_class_global_scope_smoke": run_v1425_explicit_any_class_global_scope_smoke,
    "_v1426_explicit_any_indirect_target_scope_smoke": run_v1426_explicit_any_indirect_target_scope_smoke,
    "_v1427_explicit_any_derived_uncertain_scope_smoke": run_v1427_explicit_any_derived_uncertain_scope_smoke,
    "_v1428_explicit_any_object_alias_scope_smoke": run_v1428_explicit_any_object_alias_scope_smoke,
    "_v1429_explicit_any_alias_dataflow_smoke": run_v1429_explicit_any_alias_dataflow_smoke,
    "_v14210_explicit_any_alias_fail_closed_smoke": run_v14210_explicit_any_alias_fail_closed_smoke,
    "_v143_explicit_any_call_effect_dataflow_smoke": run_v143_explicit_any_call_effect_dataflow_smoke,
    "_v1431_call_effect_component_compaction_smoke": run_v1431_call_effect_component_compaction_smoke,
    "_v1432_expression_binding_single_pass_smoke": run_v1432_expression_binding_single_pass_smoke,
    "_v1433_call_binding_lambda_effect_smoke": run_v1433_call_binding_lambda_effect_smoke,
    "_v1434_late_bound_lexical_capture_smoke": run_v1434_late_bound_lexical_capture_smoke,
    "_v1218_interface_registry_smoke": run_interface_registry_smoke,
    "_v1220_release_check_governance_smoke": run_release_check_governance_smoke,
    "_v130_lts_cutover_smoke": run_lts_cutover_smoke,
}
