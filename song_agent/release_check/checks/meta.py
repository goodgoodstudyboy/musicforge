from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from song_agent.release_check_architecture import run_architecture_guardrails_smoke
from song_agent.release_check.checks.legacy import delegated_check
from song_agent.release_check_interfaces import run_interface_registry_smoke
from song_agent.release_check_persistence_kernel import run_persistence_kernel_smoke
from song_agent.release_check.lts_cutover import run_lts_cutover_smoke


DOMAIN = "meta"
GROUPS = frozenset({"core", "git", "meta", "release-check", "architecture"})
TAGS = frozenset({"architecture", "performance", "fixture-cache"})


def run_release_check_governance_smoke(root: Path) -> tuple[bool, str]:
    try:
        from song_agent.release_check.checks.registry import provider_inventory
        from song_agent.release_check.matrix import all_check_definitions
        from song_agent.release_check.performance import PROFILE_BUDGET_WARNING_ONLY
        from song_agent.release_check.runner import run_release_check_matrix

        facade_lines = len((root / "song_agent" / "release_checks.py").read_text(encoding="utf-8").splitlines())
        legacy = root / "song_agent" / "release_check" / "checks" / "legacy" / "monolith.py"
        marker_text = (root / "pyproject.toml").read_text(encoding="utf-8")
        workflow = root / ".github" / "workflows" / "quality.yml"
        catalog_path = root / "docs" / "deprecations.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        definitions = list(all_check_definitions())
        current = [row for row in definitions if row.version and _version_key(row.version) >= (12, 13)]
        hard_budgets = all(
            row.duration_budget_seconds is not None
            and not row.budget_warning_only
            and {"v12", "latest", "ga"}.intersection(row.profiles).issubset(row.budget_enforced_profiles)
            for row in current
        )
        empty = run_release_check_matrix(repo_root=root, profile="latest", since="99.0", run_tests=False)
        details: dict[str, Any] = {
            "facade_under_300": facade_lines < 300,
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
    "_git_status_check": delegated_check("_git_status_check"),
    "_remote_url_token_check": delegated_check("_remote_url_token_check"),
    "_musicforge_configs_untracked_check": delegated_check("_musicforge_configs_untracked_check"),
    "_musicforge_configs_ignored_check": delegated_check("_musicforge_configs_ignored_check"),
    "_version_consistency": delegated_check("_version_consistency"),
    "_v1213_release_check_acceleration_smoke": delegated_check("_v1213_release_check_acceleration_smoke"),
    "_v1214_architecture_guardrails_smoke": run_architecture_guardrails_smoke,
    "_v1217_persistence_kernel_smoke": run_persistence_kernel_smoke,
    "_v1218_interface_registry_smoke": run_interface_registry_smoke,
    "_v1220_release_check_governance_smoke": run_release_check_governance_smoke,
    "_v130_lts_cutover_smoke": run_lts_cutover_smoke,
}
