from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable


@dataclass(frozen=True)
class ReleaseCheckDefinition:
    check_id: str
    name: str
    group: str
    version: str | None
    kind: str
    risk: str
    timeout_seconds: int
    callable_name: str | None = None
    command: tuple[str, ...] | None = None
    expected_warnings: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    profiles: tuple[str, ...] = ("full",)
    duration_budget_seconds: float | None = None
    budget_enforced_profiles: tuple[str, ...] = field(default_factory=tuple)
    budget_warning_only: bool = True
    budget_exception_reason: str = ""
    budget_exception_expires_version: str = ""


class ReleaseCheckMatrixError(ValueError):
    pass


def all_check_definitions() -> tuple[ReleaseCheckDefinition, ...]:
    return CHECK_DEFINITIONS


def get_check_definition(check_id: str, definitions: Iterable[ReleaseCheckDefinition] | None = None) -> ReleaseCheckDefinition:
    for definition in definitions or CHECK_DEFINITIONS:
        if definition.check_id == check_id:
            return definition
    raise ReleaseCheckMatrixError(f"Unknown release-check id: {check_id}")


def select_check_definitions(
    *,
    profile: str = "full",
    groups: list[str] | None = None,
    since: str | None = None,
    only: list[str] | None = None,
    run_tests: bool = True,
    definitions: Iterable[ReleaseCheckDefinition] | None = None,
) -> list[ReleaseCheckDefinition]:
    source = list(definitions or CHECK_DEFINITIONS)
    _ensure_unique_ids(source)
    profile = str(profile or "full")
    if only:
        wanted = _normalize_only(only)
        selected: list[ReleaseCheckDefinition] = []
        for check_id in wanted:
            selected.append(get_check_definition(check_id, source))
    else:
        if profile not in KNOWN_PROFILES:
            raise ReleaseCheckMatrixError(f"Unknown release-check profile: {profile}")
        profile_key = "full" if profile == "publish" else profile
        selected = [definition for definition in source if profile_key in definition.profiles]
        if groups:
            normalized_groups = {str(group).strip().lower() for group in groups if str(group).strip()}
            known_groups = {definition.group.lower() for definition in source}
            known_tags = {tag.lower() for definition in source for tag in definition.tags}
            unknown = sorted(normalized_groups - known_groups - known_tags)
            if unknown:
                raise ReleaseCheckMatrixError(f"Unknown release-check group: {', '.join(unknown)}")
            selected = [
                definition
                for definition in selected
                if definition.group.lower() in normalized_groups or any(tag.lower() in normalized_groups for tag in definition.tags)
            ]
        if since:
            since_key = _version_key(since)
            selected = [definition for definition in selected if definition.version is not None and _version_key(definition.version) >= since_key]
    if not run_tests:
        selected = [definition for definition in selected if definition.check_id != "pytest.full"]
    if not only:
        _reject_legacy_current_profile(profile, selected)
    return selected


def release_check_definitions_as_dicts(definitions: Iterable[ReleaseCheckDefinition] | None = None) -> list[dict[str, object]]:
    source = CHECK_DEFINITIONS if definitions is None else definitions
    return [definition_to_dict(definition) for definition in source]


def definition_to_dict(definition: ReleaseCheckDefinition) -> dict[str, object]:
    from song_agent.release_check.checks.registry import callable_provenance, check_domain

    return {
        "check_id": definition.check_id,
        "name": definition.name,
        "group": definition.group,
        "version": definition.version,
        "kind": definition.kind,
        "risk": definition.risk,
        "timeout_seconds": definition.timeout_seconds,
        "callable_name": definition.callable_name,
        "command": list(definition.command or ()),
        "expected_warnings": list(definition.expected_warnings),
        "description": definition.description,
        "tags": list(definition.tags),
        "profiles": list(definition.profiles),
        "duration_budget_seconds": definition.duration_budget_seconds,
        "budget_enforced_profiles": list(definition.budget_enforced_profiles),
        "budget_warning_only": definition.budget_warning_only,
        "budget_exception_reason": definition.budget_exception_reason,
        "budget_exception_expires_version": definition.budget_exception_expires_version,
        "domain": check_domain(group=definition.group, tags=definition.tags, callable_name=definition.callable_name),
        "callable_provenance": callable_provenance(definition.callable_name) if definition.callable_name else "command",
    }


def _reject_legacy_current_profile(profile: str, definitions: list[ReleaseCheckDefinition]) -> None:
    if profile not in CURRENT_NO_LEGACY_PROFILES:
        return
    from song_agent.release_check.checks.registry import callable_provenance

    legacy = [
        row.check_id
        for row in definitions
        if row.callable_name and callable_provenance(row.callable_name) != "active"
    ]
    if legacy:
        raise ReleaseCheckMatrixError(
            f"Current release-check profile {profile} contains non-active callables: {', '.join(legacy)}"
        )


def validate_check_definitions(definitions: Iterable[ReleaseCheckDefinition] | None = None) -> None:
    source = list(definitions or CHECK_DEFINITIONS)
    _ensure_unique_ids(source)
    for definition in source:
        if not definition.name:
            raise ReleaseCheckMatrixError(f"Release check {definition.check_id} has no name.")
        if not definition.group:
            raise ReleaseCheckMatrixError(f"Release check {definition.check_id} has no group.")
        if definition.command and definition.callable_name:
            raise ReleaseCheckMatrixError(f"Release check {definition.check_id} cannot define both command and callable_name.")
        if not definition.command and not definition.callable_name:
            raise ReleaseCheckMatrixError(f"Release check {definition.check_id} must define command or callable_name.")
        if definition.duration_budget_seconds is None:
            raise ReleaseCheckMatrixError(f"Release check {definition.check_id} has no duration budget.")
        if definition.budget_warning_only and not (
            definition.budget_exception_reason and definition.budget_exception_expires_version
        ):
            raise ReleaseCheckMatrixError(f"Release check {definition.check_id} has an undocumented duration budget exception.")


def _ensure_unique_ids(definitions: list[ReleaseCheckDefinition]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for definition in definitions:
        if definition.check_id in seen:
            duplicates.add(definition.check_id)
        seen.add(definition.check_id)
    if duplicates:
        raise ReleaseCheckMatrixError(f"Duplicate release-check ids: {', '.join(sorted(duplicates))}")


def _normalize_only(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        normalized.extend(part.strip() for part in str(value).split(",") if part.strip())
    return normalized


def _version_key(value: str) -> tuple[int, ...]:
    text = str(value or "").strip().lower().removeprefix("v")
    parts: list[int] = []
    for item in text.split("."):
        try:
            parts.append(int(item))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _callable(
    check_id: str,
    name: str,
    callable_name: str,
    *,
    group: str,
    version: str | None = None,
    risk: str = "normal",
    timeout_seconds: int = 300,
    tags: tuple[str, ...] = (),
    profiles: tuple[str, ...] = ("full",),
    expected_warnings: tuple[str, ...] = (),
    duration_budget_seconds: float | None = 90.0,
    budget_enforced_profiles: tuple[str, ...] = (),
    budget_warning_only: bool = False,
    budget_exception_reason: str = "",
    budget_exception_expires_version: str = "",
) -> ReleaseCheckDefinition:
    return ReleaseCheckDefinition(
        check_id=check_id,
        name=name,
        group=group,
        version=version,
        kind="smoke" if version else group,
        risk=risk,
        timeout_seconds=timeout_seconds,
        callable_name=callable_name,
        expected_warnings=expected_warnings,
        tags=tags,
        profiles=profiles,
        duration_budget_seconds=duration_budget_seconds,
        budget_enforced_profiles=budget_enforced_profiles or profiles,
        budget_warning_only=budget_warning_only,
        budget_exception_reason=budget_exception_reason,
        budget_exception_expires_version=budget_exception_expires_version,
    )


def _command(
    check_id: str,
    name: str,
    command: tuple[str, ...],
    *,
    group: str,
    kind: str,
    risk: str = "normal",
    timeout_seconds: int = 60,
    tags: tuple[str, ...] = (),
    profiles: tuple[str, ...] = ("full",),
    duration_budget_seconds: float | None = 90.0,
    budget_enforced_profiles: tuple[str, ...] = (),
    budget_warning_only: bool = False,
    budget_exception_reason: str = "",
    budget_exception_expires_version: str = "",
) -> ReleaseCheckDefinition:
    return ReleaseCheckDefinition(
        check_id=check_id,
        name=name,
        group=group,
        version=None,
        kind=kind,
        risk=risk,
        timeout_seconds=timeout_seconds,
        command=command,
        tags=tags,
        profiles=profiles,
        duration_budget_seconds=duration_budget_seconds,
        budget_enforced_profiles=budget_enforced_profiles or profiles,
        budget_warning_only=budget_warning_only,
        budget_exception_reason=budget_exception_reason,
        budget_exception_expires_version=budget_exception_expires_version,
    )


BASE_PROFILES = ("full", "quick", "latest", "ga", "v13", "v14")
LATEST_PROFILES = ("full", "quick", "latest")
V7_PROFILES = ("full", "v7")
GA_PROFILES = ("full", "quick", "latest", "ga")
V10_PROFILES = ("full", "quick", "latest", "ga", "v10")
V11_PROFILES = ("full", "quick", "latest", "ga", "v11")
V12_PROFILES = ("full", "quick", "latest", "ga", "v12")
V12_ACCELERATED_PROFILES = ("full", "latest", "ga", "v12")
V13_PROFILES = ("full", "latest", "ga", "v13")
V14_PROFILES = ("full", "latest", "ga", "security", "v14")
CURRENT_NO_LEGACY_PROFILES = frozenset({"latest", "ga", "v13", "v14", "security"})

LEGACY_COMPATIBILITY_CALLABLES = frozenset(
    {
        "_final_export_smoke",
        "_edit_smoke",
        "_v1213_v12_fixture_prepare_smoke",
        "_v129_command_center_runtime_inventory",
        "_v129_command_center_external_binding",
        "_v129_command_center_ga_gate",
        "_v1210_command_center_signoff_semantics",
        "_v1210_command_center_signoff_archive_verifier",
        "_v1210_command_center_signoff_reset_guard",
        "_v1211_receiver_acceptance_semantics",
        "_v1211_receiver_acceptance_zip_security",
        "_v1211_receiver_acceptance_ga_gate",
        "_v1212_receiver_acceptance_change_control_semantics",
        "_v1212_receiver_acceptance_change_control_zip_security",
        "_v1212_receiver_acceptance_change_control_external_binding",
        "_v1212_receiver_acceptance_change_control_signed_mutation",
        "_v1212_receiver_acceptance_change_control_thin_integration",
        "_v1213_release_check_acceleration_smoke",
    }
)

_RAW_CHECK_DEFINITIONS: tuple[ReleaseCheckDefinition, ...] = (
    _command(
        "pytest.full",
        "pytest",
        ("python", "-m", "pytest", "-q", "-W", "ignore:Duplicate name:UserWarning"),
        group="core",
        kind="pytest",
        risk="critical",
        timeout_seconds=6000,
        duration_budget_seconds=3600,
    ),
    _command("git.diff_check", "git diff --check", ("git", "-c", "core.safecrlf=false", "diff", "--check"), group="git", kind="git", risk="high", timeout_seconds=60, profiles=BASE_PROFILES),
    _callable("git.status", "git status", "_git_status_check", group="git", risk="high", timeout_seconds=60, profiles=("full", "ga")),
    _callable("git.remote_url_token", "remote url token check", "_remote_url_token_check", group="git", risk="high", timeout_seconds=60, profiles=("full", "ga")),
    _callable("git.musicforge_configs_untracked", ".musicforge configs untracked", "_musicforge_configs_untracked_check", group="git", risk="normal", timeout_seconds=60, profiles=("full", "ga")),
    _callable("git.musicforge_configs_ignored", ".musicforge configs ignored", "_musicforge_configs_ignored_check", group="git", risk="normal", timeout_seconds=60, profiles=("full", "ga")),
    _callable("meta.version_consistency", "version consistency", "_version_consistency", group="meta", risk="critical", timeout_seconds=60, profiles=BASE_PROFILES),
    _callable("security.secret_scan", "secret scan", "_secret_scan", group="security", risk="critical", timeout_seconds=60, profiles=BASE_PROFILES),
    _callable("core.final_export_smoke", "final export smoke", "_final_export_smoke", group="core", risk="high", timeout_seconds=300, profiles=("full", "quick")),
    _callable("editing.edit_smoke", "edit smoke", "_edit_smoke", group="editing", risk="high", timeout_seconds=300, profiles=("full", "quick")),
    _callable("v12.workflow_smoke", "v1.2 workflow smoke", "_v12_workflow_smoke", group="core", version="1.2", tags=("legacy",)),
    _callable("v121.hardening_smoke", "v1.2.1 hardening smoke", "_v121_hardening_smoke", group="core", version="1.2.1", tags=("legacy",)),
    _callable("v13.provider_edit_smoke", "v1.3 provider edit smoke", "_v13_provider_edit_smoke", group="editing", version="1.3", tags=("provider", "legacy")),
    _callable("v14.candidate_edit_smoke", "v1.4 candidate edit smoke", "_v14_candidate_edit_smoke", group="editing", version="1.4", tags=("candidate", "legacy")),
    _callable("v15.candidate_audition_usage_smoke", "v1.5 candidate audition and usage smoke", "_v15_candidate_audition_usage_smoke", group="editing", version="1.5", tags=("candidate", "legacy")),
    _callable("v16.creative_assets_smoke", "v1.6 creative assets smoke", "_v16_creative_assets_smoke", group="editing", version="1.6", tags=("assets", "legacy")),
    _callable("v17.reference_library_smoke", "v1.7 reference library smoke", "_v17_reference_library_smoke", group="editing", version="1.7", tags=("references", "legacy")),
    _callable("v18.reference_analysis_smoke", "v1.8 reference analysis smoke", "_v18_reference_analysis_smoke", group="editing", version="1.8", tags=("references", "legacy")),
    _callable("v19.library_context_smoke", "v1.9 library context smoke", "_v19_library_context_smoke", group="editing", version="1.9", tags=("library", "legacy")),
    _callable("v20.visual_editor_smoke", "v2.0 visual editor smoke", "_v20_visual_editor_smoke", group="editing", version="2.0", tags=("editor",)),
    _callable("v21.structure_editor_smoke", "v2.1 structure editor smoke", "_v21_structure_editor_smoke", group="editing", version="2.1", tags=("editor",)),
    _callable("v22.interactive_editor_smoke", "v2.2 interactive editor smoke", "_v22_interactive_editor_smoke", group="editing", version="2.2", tags=("editor",)),
    _callable("v23.editor_clip_insert_smoke", "v2.3 editor clip insert smoke", "_v23_editor_clip_insert_smoke", group="editing", version="2.3", tags=("editor",)),
    _callable("v24.editor_template_smoke", "v2.4 editor template smoke", "_v24_editor_template_smoke", group="editing", version="2.4", tags=("editor",)),
    _callable("v25.editor_audition_smoke", "v2.5 editor audition smoke", "_v25_editor_audition_smoke", group="editing", version="2.5", tags=("editor",)),
    _callable("v26.audition_review_smoke", "v2.6 audition review smoke", "_v26_audition_review_smoke", group="editing", version="2.6", tags=("review",)),
    _callable("v27.review_edit_smoke", "v2.7 review edit smoke", "_v27_review_edit_smoke", group="editing", version="2.7", tags=("review",)),
    _callable("v28.review_task_smoke", "v2.8 review task smoke", "_v28_review_task_smoke", group="editing", version="2.8", tags=("review",)),
    _callable("v29.provider_review_candidates_smoke", "v2.9 provider review candidates smoke", "_v29_provider_review_candidates_smoke", group="editing", version="2.9", tags=("review", "provider")),
    _callable("v30.review_sprint_smoke", "v3.0 review sprint smoke", "_v30_review_sprint_smoke", group="editing", version="3.0", tags=("review",)),
    _callable("v31.review_sprint_recommendations_smoke", "v3.1 review sprint recommendations smoke", "_v31_review_sprint_recommendations_smoke", group="editing", version="3.1", tags=("review",)),
    _callable("v32.review_sprint_action_queue_smoke", "v3.2 review sprint action queue smoke", "_v32_review_sprint_action_queue_smoke", group="editing", version="3.2", tags=("review",)),
    _callable("v33.review_sprint_dashboard_metrics_smoke", "v3.3 review sprint dashboard metrics smoke", "_v33_review_sprint_dashboard_metrics_smoke", group="editing", version="3.3", tags=("review",)),
    _callable("v34.provider_review_judge_smoke", "v3.4 provider review judge smoke", "_v34_provider_review_judge_smoke", group="editing", version="3.4", tags=("review", "provider")),
    _callable("v35.review_sprint_closeout_smoke", "v3.5 review sprint closeout smoke", "_v35_review_sprint_closeout_smoke", group="editing", version="3.5", tags=("review",)),
    _callable("v36.delivery_qa_handoff_smoke", "v3.6 delivery qa handoff smoke", "_v36_delivery_qa_handoff_smoke", group="distribution", version="3.6", tags=("delivery",)),
    _callable("v37.release_workspace_smoke", "v3.7 release workspace smoke", "_v37_release_workspace_smoke", group="distribution", version="3.7", tags=("release",)),
    _callable("v38.release_zip_verifier_smoke", "v3.8 release zip verifier smoke", "_v38_release_zip_verifier_smoke", group="distribution", version="3.8", tags=("release", "verifier")),
    _callable("v39.release_metadata_smoke", "v3.9 release metadata smoke", "_v39_release_metadata_smoke", group="distribution", version="3.9", tags=("release", "metadata")),
    _callable("v40.distribution_prep_smoke", "v4.0 distribution prep smoke", "_v40_distribution_prep_smoke", group="distribution", version="4.0"),
    _callable("v41.distribution_template_packs_smoke", "v4.1 distribution template packs smoke", "_v41_distribution_template_packs_smoke", group="distribution", version="4.1", tags=("template",)),
    _callable("v42.distribution_layout_contract_smoke", "v4.2 distribution layout contract smoke", "_v42_distribution_layout_contract_smoke", group="distribution", version="4.2", tags=("layout",)),
    _callable("v43.submission_workspace_smoke", "v4.3 submission workspace smoke", "_v43_submission_workspace_smoke", group="submission", version="4.3"),
    _callable("v44.music_acceptance_lab_smoke", "v4.4 music acceptance lab smoke", "_v44_music_acceptance_lab_smoke", group="acceptance", version="4.4"),
    _callable("v45.acceptance_profiles_songbook_smoke", "v4.5 acceptance profiles songbook smoke", "_v45_acceptance_profiles_songbook_smoke", group="acceptance", version="4.5"),
    _callable("v46.human_review_pack_smoke", "v4.6 human review pack smoke", "_v46_human_review_pack_smoke", group="acceptance", version="4.6"),
    _callable("v47.acceptance_analytics_smoke", "v4.7 acceptance analytics smoke", "_v47_acceptance_analytics_smoke", group="acceptance", version="4.7"),
    _callable("v48.acceptance_fix_sprint_smoke", "v4.8 acceptance fix sprint smoke", "_v48_acceptance_fix_sprint_smoke", group="acceptance", version="4.8"),
    _callable("v49.acceptance_knowledge_base_smoke", "v4.9 acceptance knowledge base smoke", "_v49_acceptance_knowledge_base_smoke", group="acceptance", version="4.9"),
    _callable("v410.knowledge_assisted_fix_planning_smoke", "v4.10 knowledge-assisted fix planning smoke", "_v410_knowledge_assisted_fix_planning_smoke", group="acceptance", version="4.10"),
    _callable("v411.fix_plan_outcome_review_smoke", "v4.11 fix plan outcome review smoke", "_v411_fix_plan_outcome_review_smoke", group="acceptance", version="4.11"),
    _callable("v412.planning_rule_simulation_smoke", "v4.12 planning rule simulation smoke", "_v412_planning_rule_simulation_smoke", group="acceptance", version="4.12"),
    _callable("v413.planning_rule_governance_smoke", "v4.13 planning rule governance smoke", "_v413_planning_rule_governance_smoke", group="acceptance", version="4.13"),
    _callable("v414.planning_rule_impact_smoke", "v4.14 planning rule impact smoke", "_v414_planning_rule_impact_smoke", group="acceptance", version="4.14"),
    _callable("v50.real_audio_baseline_smoke", "v5.0 real audio baseline smoke", "_v50_real_audio_baseline_smoke", group="audio", version="5.0"),
    _callable("v51.per_track_audio_review_smoke", "v5.1 per-track audio review smoke", "_v51_per_track_audio_review_smoke", group="audio", version="5.1"),
    _callable("v52.arrangement_mix_controls_smoke", "v5.2 arrangement mix controls smoke", "_v52_arrangement_mix_controls_smoke", group="audio", version="5.2"),
    _callable("v53.audio_revision_workbench_smoke", "v5.3 audio revision workbench smoke", "_v53_audio_revision_workbench_smoke", group="audio", version="5.3"),
    _callable("v54.mastering_qa_smoke", "v5.4 mastering qa smoke", "_v54_mastering_qa_smoke", group="audio", version="5.4"),
    _callable("v55.distribution_audio_formats_smoke", "v5.5 distribution audio formats smoke", "_v55_distribution_audio_formats_smoke", group="audio", version="5.5", tags=("distribution",)),
    _callable("v56.encoded_audio_acceptance_smoke", "v5.6 encoded audio acceptance smoke", "_v56_encoded_audio_acceptance_smoke", group="audio", version="5.6", tags=("acceptance",)),
    _callable("v57.release_format_decision_smoke", "v5.7 release format decision smoke", "_v57_release_format_decision_smoke", group="distribution", version="5.7"),
    _callable("v58.rights_clearance_smoke", "v5.8 rights clearance smoke", "_v58_rights_clearance_smoke", group="distribution", version="5.8", tags=("rights",)),
    _callable("v59.submission_evidence_archive_smoke", "v5.9 submission evidence archive smoke", "_v59_submission_evidence_archive_smoke", group="submission", version="5.9"),
    _callable("v60.release_operations_dashboard_smoke", "v6.0 release operations dashboard smoke", "_v60_release_operations_dashboard_smoke", group="operations", version="6.0"),
    _callable("v61.release_operations_runbook_smoke", "v6.1 release operations runbook smoke", "_v61_release_operations_runbook_smoke", group="operations", version="6.1"),
    _callable("v62.release_operations_signoff_archive_smoke", "v6.2 release operations signoff archive smoke", "_v62_release_operations_signoff_archive_smoke", group="operations", version="6.2"),
    _callable("v63.release_operations_audit_ledger_smoke", "v6.3 release operations audit ledger smoke", "_v63_release_operations_audit_ledger_smoke", group="operations", version="6.3"),
    _callable("v64.release_operations_reviewer_pack_smoke", "v6.4 release operations reviewer pack smoke", "_v64_release_operations_reviewer_pack_smoke", group="operations", version="6.4"),
    _callable("v65.release_portfolio_audit_smoke", "v6.5 release portfolio audit smoke", "_v65_release_portfolio_audit_smoke", group="portfolio", version="6.5"),
    _callable("v66.release_portfolio_governance_queue_smoke", "v6.6 release portfolio governance queue smoke", "_v66_release_portfolio_governance_queue_smoke", group="portfolio", version="6.6", tags=("governance",)),
    _callable("v67.release_portfolio_governance_signoff_smoke", "v6.7 release portfolio governance signoff smoke", "_v67_release_portfolio_governance_signoff_smoke", group="portfolio", version="6.7", tags=("governance",)),
    _callable("v68.release_portfolio_governance_audit_ledger_smoke", "v6.8 release portfolio governance audit ledger smoke", "_v68_release_portfolio_governance_audit_ledger_smoke", group="portfolio", version="6.8", tags=("governance",)),
    _callable("v69.release_portfolio_governance_reviewer_pack_smoke", "v6.9 release portfolio governance reviewer pack smoke", "_v69_release_portfolio_governance_reviewer_pack_smoke", group="portfolio", version="6.9", tags=("governance",)),
    _callable("v70.release_portfolio_governance_final_board_smoke", "v7.0 release portfolio governance final board smoke", "_v70_release_portfolio_governance_final_board_smoke", group="governance", version="7.0", risk="high", timeout_seconds=600, tags=("v7", "portfolio"), profiles=V7_PROFILES),
    _callable("v71.release_portfolio_governance_evidence_vault_smoke", "v7.1 release portfolio governance evidence vault smoke", "_v71_release_portfolio_governance_evidence_vault_smoke", group="governance", version="7.1", risk="high", timeout_seconds=600, tags=("v7", "portfolio", "vault"), profiles=V7_PROFILES),
    _callable("v72.release_portfolio_governance_attestation_smoke", "v7.2 release portfolio governance public attestation smoke", "_v72_release_portfolio_governance_attestation_smoke", group="attestation", version="7.2", risk="high", timeout_seconds=600, tags=("v7", "governance"), profiles=V7_PROFILES),
    _callable("v73.release_portfolio_governance_attestation_registry_smoke", "v7.3 release portfolio governance attestation registry smoke", "_v73_release_portfolio_governance_attestation_registry_smoke", group="attestation", version="7.3", risk="high", timeout_seconds=600, tags=("v7", "governance", "registry"), profiles=V7_PROFILES),
    _callable("v74.attestation_portal_smoke", "v7.4 release portfolio governance attestation portal smoke", "_v74_release_portfolio_governance_attestation_portal_smoke", group="portal", version="7.4", risk="critical", timeout_seconds=600, tags=("v7", "governance", "attestation"), profiles=("full", "v7", "quick", "latest"), expected_warnings=("Duplicate name:",)),
    _callable("v75.release_check_matrix_smoke", "v7.5 release check verification matrix smoke", "_v75_release_check_matrix_smoke", group="meta", version="7.5", risk="critical", timeout_seconds=300, tags=("v7", "release_check"), profiles=("full", "v7", "quick", "latest", "ga")),
    _callable("v76.attestation_portal_review_response_smoke", "v7.6 release portfolio governance attestation portal review response smoke", "_v76_attestation_portal_review_response_smoke", group="portal", version="7.6", risk="critical", timeout_seconds=600, tags=("v7", "governance", "attestation", "review"), profiles=("full", "v7", "quick", "latest"), expected_warnings=("Duplicate name:",)),
    _callable("v77.attestation_accepted_evidence_smoke", "v7.7 release portfolio governance attestation accepted evidence smoke", "_v77_attestation_accepted_evidence_smoke", group="portal", version="7.7", risk="critical", timeout_seconds=600, tags=("v7", "governance", "attestation", "review"), profiles=("full", "v7", "quick", "latest"), expected_warnings=("Duplicate name:",)),
    _callable("v78.attestation_transparency_feed_smoke", "v7.8 release portfolio governance attestation transparency feed smoke", "_v78_attestation_transparency_feed_smoke", group="portal", version="7.8", risk="critical", timeout_seconds=600, tags=("v7", "governance", "attestation", "transparency"), profiles=("full", "v7", "quick", "latest"), expected_warnings=("Duplicate name:",)),
    _callable("v79.attestation_transparency_acknowledgement_smoke", "v7.9 release portfolio governance attestation transparency acknowledgement smoke", "_v79_attestation_transparency_acknowledgement_smoke", group="portal", version="7.9", risk="critical", timeout_seconds=600, tags=("v7", "governance", "attestation", "transparency", "review"), profiles=("full", "v7", "quick", "latest"), expected_warnings=("Duplicate name:",)),
    _callable("v80.public_trust_center_smoke", "v8.0 public trust center smoke", "_v80_public_trust_center_smoke", group="trust", version="8.0", risk="critical", timeout_seconds=600, tags=("v8", "trust", "portal", "attestation"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v81.public_trust_center_delivery_smoke", "v8.1 public trust center delivery smoke", "_v81_public_trust_center_delivery_smoke", group="trust", version="8.1", risk="critical", timeout_seconds=600, tags=("v8", "trust", "delivery", "operations", "submission"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v82.public_trust_center_anchor_registry_smoke", "v8.2 public trust center anchor registry smoke", "_v82_public_trust_center_anchor_registry_smoke", group="trust", version="8.2", risk="critical", timeout_seconds=600, tags=("v8", "trust", "anchor", "registry"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v83.public_trust_center_anchor_transparency_smoke", "v8.3 public trust center anchor transparency smoke", "_v83_public_trust_center_anchor_transparency_smoke", group="trust", version="8.3", risk="critical", timeout_seconds=600, tags=("v8", "trust", "anchor", "transparency"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v84.public_trust_center_distribution_kit_smoke", "v8.4 public trust center distribution kit smoke", "_v84_public_trust_center_distribution_kit_smoke", group="trust", version="8.4", risk="critical", timeout_seconds=600, tags=("v8", "trust", "distribution-kit", "anchor"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v85.public_trust_center_distribution_kit_acceptance_smoke", "v8.5 public trust center distribution kit acceptance smoke", "_v85_public_trust_center_distribution_kit_acceptance_smoke", group="trust", version="8.5", risk="critical", timeout_seconds=600, tags=("v8", "trust", "distribution-kit", "acceptance"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v86.public_trust_center_acceptance_board_smoke", "v8.6 public trust center acceptance board smoke", "_v86_public_trust_center_acceptance_board_smoke", group="trust", version="8.6", risk="critical", timeout_seconds=600, tags=("v8", "trust", "acceptance-board", "quorum"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v87.public_trust_center_acceptance_board_signoff_smoke", "v8.7 public trust center acceptance board signoff archive smoke", "_v87_public_trust_center_acceptance_board_signoff_smoke", group="trust", version="8.7", risk="critical", timeout_seconds=600, tags=("v8", "trust", "acceptance-board", "signoff"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v88.public_trust_center_publication_channels_smoke", "v8.8 public trust center publication channels smoke", "_v88_public_trust_center_publication_channels_smoke", group="trust", version="8.8", risk="critical", timeout_seconds=600, tags=("v8", "trust", "publication", "mirror"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v89.public_trust_center_publication_monitoring_smoke", "v8.9 public trust center publication monitoring smoke", "_v89_public_trust_center_publication_monitoring_smoke", group="trust", version="8.9", risk="critical", timeout_seconds=600, tags=("v8", "trust", "publication", "monitoring", "incident"), profiles=("full", "quick", "latest", "v8"), expected_warnings=("Duplicate name:",)),
    _callable("v90.trust_operations_hub_smoke", "v9.0 trust operations hub smoke", "_v90_trust_operations_hub_smoke", group="trust", version="9.0", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "operations"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v91.trust_operations_hub_delivery_runbook_smoke", "v9.1 trust operations hub delivery and runbook smoke", "_v91_trust_operations_hub_delivery_runbook_smoke", group="trust", version="9.1", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "delivery", "runbook"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v92.trust_operations_hub_incident_response_smoke", "v9.2 trust operations hub incident response smoke", "_v92_trust_operations_hub_incident_response_smoke", group="trust", version="9.2", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "incident"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v93.trust_operations_incident_knowledge_smoke", "v9.3 trust operations incident knowledge and regression guard smoke", "_v93_trust_operations_incident_knowledge_smoke", group="trust", version="9.3", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "incident", "knowledge"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v94.trust_operations_control_catalog_smoke", "v9.4 trust operations control catalog smoke", "_v94_trust_operations_control_catalog_smoke", group="trust", version="9.4", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "controls"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v95.trust_operations_control_signoff_smoke", "v9.5 trust operations control signoff smoke", "_v95_trust_operations_control_signoff_smoke", group="trust", version="9.5", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "controls", "signoff"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v96.trust_operations_continuous_assurance_smoke", "v9.6 trust operations continuous assurance smoke", "_v96_trust_operations_continuous_assurance_smoke", group="trust", version="9.6", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "assurance"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v97.trust_operations_assurance_watch_smoke", "v9.7 trust operations assurance watch smoke", "_v97_trust_operations_assurance_watch_smoke", group="trust", version="9.7", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "assurance", "watch"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v98.trust_operations_assurance_watch_signoff_smoke", "v9.8 trust operations assurance watch signoff smoke", "_v98_trust_operations_assurance_watch_signoff_smoke", group="trust", version="9.8", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "assurance", "watch", "signoff"), profiles=("full", "quick", "latest", "v9"), expected_warnings=("Duplicate name:",)),
    _callable("v99.trust_operations_final_readiness_smoke", "v9.9 trust operations final readiness handoff smoke", "_v99_trust_operations_final_readiness_smoke", group="trust", version="9.9", risk="critical", timeout_seconds=600, tags=("v9", "trust", "hub", "final-readiness", "handoff"), profiles=("full", "quick", "latest", "v9", "ga"), expected_warnings=("Duplicate name:",)),
    _callable("v100.ga_lts_readiness_smoke", "v10.0 GA/LTS readiness smoke", "_v100_ga_lts_readiness_smoke", group="ga", version="10.0", risk="critical", timeout_seconds=300, tags=("v10", "ga", "lts", "readiness"), profiles=V10_PROFILES),
    _callable("v101.lts_maintenance_backup_restore_smoke", "v10.1 LTS maintenance backup and restore smoke", "_v101_lts_maintenance_backup_restore_smoke", group="maintenance", version="10.1", risk="critical", timeout_seconds=300, tags=("v10", "ga", "lts", "maintenance"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v102.audio_lab_real_listening_smoke", "v10.2 Audio Lab real listening workflow smoke", "_v102_audio_lab_real_listening_smoke", group="audio", version="10.2", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "listening"), profiles=V10_PROFILES),
    _callable("v103.audio_fix_sprint_smoke", "v10.3 Audio Fix Sprint and manual recheck smoke", "_v103_audio_fix_sprint_smoke", group="audio", version="10.3", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "fix-sprint"), profiles=V10_PROFILES),
    _callable("v104.audio_campaign_smoke", "v10.4 release candidate Audio Campaign smoke", "_v104_audio_campaign_smoke", group="audio", version="10.4", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "campaign"), profiles=V10_PROFILES),
    _callable("v105.audio_campaign_governance_smoke", "v10.5 Audio Campaign Governance archive and GA gate smoke", "_v105_audio_campaign_governance_smoke", group="audio", version="10.5", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "campaign", "governance"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v106.release_driven_audio_campaign_smoke", "v10.6 Release-driven Audio Campaign planner smoke", "_v106_release_driven_audio_campaign_smoke", group="audio", version="10.6", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "campaign", "release-driven"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v107.release_audio_campaign_remediation_smoke", "v10.7 Release Audio Campaign remediation smoke", "_v107_release_audio_campaign_remediation_smoke", group="audio", version="10.7", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "campaign", "remediation"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v108.release_audio_certification_smoke", "v10.8 Release Audio Certification gate smoke", "_v108_release_audio_certification_smoke", group="audio", version="10.8", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "certification"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v109.release_audio_timeline_smoke", "v10.9 Release Audio Certification Timeline smoke", "_v109_release_audio_timeline_smoke", group="audio", version="10.9", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "certification", "timeline"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v1010.release_audio_regression_guard_smoke", "v10.10 Release Audio Regression Guard smoke", "_v1010_release_audio_regression_guard_smoke", group="audio", version="10.10", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "certification", "timeline", "regression"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v1011.release_audio_baseline_response_smoke", "v10.11 Release Audio Baseline Governance and Regression Response smoke", "_v1011_release_audio_baseline_response_smoke", group="audio", version="10.11", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "baseline", "regression", "response"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v1012.release_audio_quality_observatory_smoke", "v10.12 Release Audio Quality Observatory smoke", "_v1012_release_audio_quality_observatory_smoke", group="audio", version="10.12", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "quality", "observatory"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v1013.release_audio_quality_action_queue_smoke", "v10.13 Release Audio Quality Action Queue smoke", "_v1013_release_audio_quality_action_queue_smoke", group="audio", version="10.13", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "quality", "observatory", "action-queue"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v1014.release_audio_quality_action_queue_signoff_smoke", "v10.14 Release Audio Quality Action Queue signoff archive smoke", "_v1014_release_audio_quality_action_queue_signoff_smoke", group="audio", version="10.14", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "quality", "observatory", "action-queue", "signoff"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v1015.release_audio_command_center_smoke", "v10.15 Release Audio Command Center smoke", "_v1015_release_audio_command_center_smoke", group="audio", version="10.15", risk="critical", timeout_seconds=300, tags=("v10", "ga", "audio", "command-center", "readiness"), profiles=V10_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v110.unified_command_center_smoke", "v11.0 Unified Command Center smoke", "_v110_unified_command_center_smoke", group="command-center", version="11.0", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "readiness"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v111.unified_command_center_signoff_archive_smoke", "v11.1 Unified Command Center signoff archive smoke", "_v111_unified_command_center_signoff_archive_smoke", group="command-center", version="11.1", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "signoff", "archive", "handoff"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v112.unified_command_center_continuous_review_smoke", "v11.2 Unified Command Center continuous review smoke", "_v112_unified_command_center_continuous_review_smoke", group="command-center", version="11.2", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "continuous-review"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v113.unified_command_center_drift_response_smoke", "v11.3 Unified Command Center drift response smoke", "_v113_unified_command_center_drift_response_smoke", group="command-center", version="11.3", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "continuous-review", "drift-response"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v114.unified_command_center_evidence_review_smoke", "v11.4 Unified Command Center evidence review replay smoke", "_v114_unified_command_center_evidence_review_smoke", group="command-center", version="11.4", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "evidence-review", "replay"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v115.unified_command_center_reviewer_decision_board_smoke", "v11.5 Unified Command Center reviewer decision board smoke", "_v115_unified_command_center_reviewer_decision_board_smoke", group="command-center", version="11.5", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "evidence-review", "decision-board", "quorum"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v116.unified_command_center_release_train_smoke", "v11.6 Unified Command Center Release Train smoke", "_v116_unified_command_center_release_train_smoke", group="command-center", version="11.6", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "release-train"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v117.unified_command_center_release_train_change_control_smoke", "v11.7 Unified Command Center Release Train Change Control smoke", "_v117_unified_command_center_release_train_change_control_smoke", group="command-center", version="11.7", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "release-train", "change-control"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v118.unified_command_center_release_train_lifecycle_smoke", "v11.8 Unified Command Center Release Train Lifecycle Audit smoke", "_v118_unified_command_center_release_train_lifecycle_smoke", group="command-center", version="11.8", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "release-train", "lifecycle"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v119.unified_command_center_release_train_handoff_smoke", "v11.9 Unified Command Center Release Train Final Handoff Board smoke", "_v119_unified_command_center_release_train_handoff_smoke", group="command-center", version="11.9", risk="critical", timeout_seconds=300, tags=("v11", "ga", "unified-command-center", "release-train", "handoff"), profiles=V11_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v120.unified_release_program_board_smoke", "v12.0 Unified Release Program Board smoke", "_v120_unified_release_program_board_smoke", group="command-center", version="12.0", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "release-train", "program-board"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v121.unified_release_program_operations_smoke", "v12.1 Unified Release Program Operations Center smoke", "_v121_unified_release_program_operations_smoke", group="command-center", version="12.1", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "operations", "change-control"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v122.unified_release_program_final_handoff_smoke", "v12.2 Unified Release Program Final Handoff Board smoke", "_v122_unified_release_program_final_handoff_smoke", group="command-center", version="12.2", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "handoff", "review-board"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v123.unified_release_program_evidence_vault_smoke", "v12.3 Unified Release Program Evidence Vault smoke", "_v123_unified_release_program_evidence_vault_smoke", group="command-center", version="12.3", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "evidence-vault", "deep-verify"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v124.unified_release_program_vault_operations_smoke", "v12.4 Unified Release Program Vault Operations smoke", "_v124_unified_release_program_vault_operations_smoke", group="command-center", version="12.4", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "evidence-vault", "vault-operations"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v125.unified_release_program_continuity_recovery_smoke", "v12.5 Unified Release Program Continuity Recovery smoke", "_v125_unified_release_program_continuity_recovery_smoke", group="command-center", version="12.5", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "continuity", "recovery"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v126.unified_release_program_continuity_distribution_kit_smoke", "v12.6 Unified Release Program Continuity Distribution Kit smoke", "_v126_unified_release_program_continuity_distribution_kit_smoke", group="command-center", version="12.6", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "continuity", "distribution-kit"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v127.unified_release_program_continuity_acceptance_board_smoke", "v12.7 Unified Release Program Continuity Acceptance Board smoke", "_v127_unified_release_program_continuity_acceptance_board_smoke", group="command-center", version="12.7", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "continuity", "acceptance-board"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v128.unified_release_program_continuity_acceptance_change_control_smoke", "v12.8 Unified Release Program Continuity Acceptance Change Control smoke", "_v128_unified_release_program_continuity_acceptance_change_control_smoke", group="command-center", version="12.8", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "continuity", "acceptance-change-control"), profiles=V12_PROFILES, expected_warnings=("Duplicate name:",)),
    _callable("v129.unified_release_program_continuity_command_center_smoke", "v12.9 Unified Release Program Continuity Command Center full smoke", "_v129_unified_release_program_continuity_command_center_smoke", group="command-center", version="12.9", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "continuity", "command-center", "full-only"), profiles=("full",), expected_warnings=("Duplicate name:",), duration_budget_seconds=120),
    _callable("v1210.unified_release_program_continuity_command_center_signoff_smoke", "v12.10 Unified Release Program Continuity Command Center Signoff full smoke", "_v1210_unified_release_program_continuity_command_center_signoff_smoke", group="command-center", version="12.10", risk="critical", timeout_seconds=300, tags=("v12", "ga", "unified-release-program", "continuity", "command-center", "signoff", "full-only"), profiles=("full",), expected_warnings=("Duplicate name:",), duration_budget_seconds=120),
    _callable("v1211.unified_release_program_continuity_command_center_receiver_acceptance_smoke", "v12.11 Unified Release Program Continuity Command Center Receiver Acceptance full smoke", "_v1211_unified_release_program_continuity_command_center_receiver_acceptance_smoke", group="command-center", version="12.11", risk="critical", timeout_seconds=600, tags=("v12", "ga", "unified-release-program", "continuity", "command-center", "receiver-acceptance", "full-only"), profiles=("full",), expected_warnings=("Duplicate name:",), duration_budget_seconds=120),
    _callable("v1212.unified_release_program_continuity_command_center_receiver_acceptance_change_control_smoke", "v12.12 Receiver Acceptance Change Control full smoke", "_v1212_unified_release_program_continuity_command_center_receiver_acceptance_change_control_smoke", group="command-center", version="12.12", risk="critical", timeout_seconds=900, tags=("v12", "ga", "unified-release-program", "continuity", "command-center", "receiver-acceptance", "change-control", "lifecycle", "full-only"), profiles=("full",), expected_warnings=("Duplicate name:",), duration_budget_seconds=120),
    _callable("v1213.v12_continuity_fixture_prepare", "v12 continuity prepared fixture", "_v1213_v12_fixture_prepare_smoke", group="command-center", version="12.13", risk="critical", timeout_seconds=600, tags=("v12", "ga", "fixture", "continuity"), profiles=(*V12_ACCELERATED_PROFILES, "security"), duration_budget_seconds=240),
    _callable("v129.command_center_runtime_inventory", "v12.9 Command Center runtime inventory", "_v129_command_center_runtime_inventory", group="command-center", version="12.9", risk="critical", timeout_seconds=120, tags=("v12", "ga", "runtime", "continuity"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v129.command_center_external_binding", "v12.9 Command Center external binding", "_v129_command_center_external_binding", group="command-center", version="12.9", risk="critical", timeout_seconds=120, tags=("v12", "ga", "external-binding", "continuity"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v129.command_center_ga_gate", "v12.9 Command Center GA gate", "_v129_command_center_ga_gate", group="command-center", version="12.9", risk="critical", timeout_seconds=120, tags=("v12", "ga", "gate", "continuity"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1210.command_center_signoff_semantics", "v12.10 Command Center signoff semantics", "_v1210_command_center_signoff_semantics", group="command-center", version="12.10", risk="critical", timeout_seconds=120, tags=("v12", "ga", "signoff", "semantics"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1210.command_center_signoff_archive_verifier", "v12.10 Command Center signoff archive verifier", "_v1210_command_center_signoff_archive_verifier", group="command-center", version="12.10", risk="critical", timeout_seconds=120, tags=("v12", "ga", "signoff", "zip-security"), profiles=V12_ACCELERATED_PROFILES, expected_warnings=("Duplicate name:",), duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1210.command_center_signoff_reset_guard", "v12.10 Command Center signoff reset guard", "_v1210_command_center_signoff_reset_guard", group="command-center", version="12.10", risk="critical", timeout_seconds=120, tags=("v12", "ga", "signoff", "reset"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1211.receiver_acceptance_semantics", "v12.11 Receiver Acceptance semantics", "_v1211_receiver_acceptance_semantics", group="command-center", version="12.11", risk="critical", timeout_seconds=120, tags=("v12", "ga", "receiver-acceptance", "semantics"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1211.receiver_acceptance_zip_security", "v12.11 Receiver Acceptance ZIP security", "_v1211_receiver_acceptance_zip_security", group="command-center", version="12.11", risk="critical", timeout_seconds=120, tags=("v12", "ga", "receiver-acceptance", "zip-security"), profiles=V12_ACCELERATED_PROFILES, expected_warnings=("Duplicate name:",), duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1211.receiver_acceptance_ga_gate", "v12.11 Receiver Acceptance GA gate", "_v1211_receiver_acceptance_ga_gate", group="command-center", version="12.11", risk="critical", timeout_seconds=120, tags=("v12", "ga", "receiver-acceptance", "gate"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1212.receiver_acceptance_change_control_semantics", "v12.12 Receiver Acceptance Change Control semantics", "_v1212_receiver_acceptance_change_control_semantics", group="command-center", version="12.12", risk="critical", timeout_seconds=120, tags=("v12", "ga", "receiver-acceptance", "change-control", "semantics"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1212.receiver_acceptance_change_control_zip_security", "v12.12 Receiver Acceptance Change Control ZIP security", "_v1212_receiver_acceptance_change_control_zip_security", group="command-center", version="12.12", risk="critical", timeout_seconds=120, tags=("v12", "ga", "receiver-acceptance", "change-control", "zip-security"), profiles=V12_ACCELERATED_PROFILES, expected_warnings=("Duplicate name:",), duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1212.receiver_acceptance_change_control_external_binding", "v12.12 Receiver Acceptance Change Control external binding", "_v1212_receiver_acceptance_change_control_external_binding", group="command-center", version="12.12", risk="critical", timeout_seconds=120, tags=("v12", "ga", "receiver-acceptance", "change-control", "external-binding"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1212.receiver_acceptance_change_control_signed_mutation", "v12.12 Receiver Acceptance Change Control signed mutation", "_v1212_receiver_acceptance_change_control_signed_mutation", group="command-center", version="12.12", risk="critical", timeout_seconds=120, tags=("v12", "ga", "receiver-acceptance", "change-control", "signed-mutation"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1212.receiver_acceptance_change_control_thin_integration", "v12.12 Receiver Acceptance Change Control thin integration", "_v1212_receiver_acceptance_change_control_thin_integration", group="command-center", version="12.12", risk="critical", timeout_seconds=180, tags=("v12", "ga", "receiver-acceptance", "change-control", "integration"), profiles=V12_ACCELERATED_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1213.release_check_acceleration_smoke", "v12.13 Release Check acceleration smoke", "_v1213_release_check_acceleration_smoke", group="release-check", version="12.13", risk="high", timeout_seconds=60, tags=("v12", "ga", "performance", "fixture-cache"), profiles=V12_PROFILES, duration_budget_seconds=30, budget_enforced_profiles=("v12", "latest", "ga")),
    _callable("v1214.architecture_guardrails_smoke", "v12.14 Architecture guardrails smoke", "_v1214_architecture_guardrails_smoke", group="architecture", version="12.14", risk="critical", timeout_seconds=120, tags=("v12", "ga", "architecture", "dependencies", "ratchet"), profiles=(*V12_ACCELERATED_PROFILES, "v13"), duration_budget_seconds=60, budget_enforced_profiles=("v12", "latest", "ga", "v13")),
    _callable("v1215.verification_kernel_smoke", "v12.15 Verification Kernel smoke", "_v1215_verification_kernel_smoke", group="architecture", version="12.15", risk="critical", timeout_seconds=120, tags=("v12", "ga", "architecture", "verification", "zip-security"), profiles=(*V12_ACCELERATED_PROFILES, "v13"), duration_budget_seconds=60, budget_enforced_profiles=("v12", "latest", "ga", "v13")),
    _callable("v1216.lifecycle_kernel_smoke", "v12.16 Evidence and Lifecycle Kernel smoke", "_v1216_lifecycle_kernel_smoke", group="architecture", version="12.16", risk="critical", timeout_seconds=120, tags=("v12", "ga", "architecture", "lifecycle", "change-control"), profiles=(*V12_ACCELERATED_PROFILES, "v13"), duration_budget_seconds=60, budget_enforced_profiles=("v12", "latest", "ga", "v13")),
    _callable("v1217.persistence_kernel_smoke", "v12.17 Persistence, concurrency, and migration smoke", "_v1217_persistence_kernel_smoke", group="architecture", version="12.17", risk="critical", timeout_seconds=120, tags=("v12", "ga", "architecture", "persistence", "concurrency", "migration"), profiles=(*V12_ACCELERATED_PROFILES, "v13"), duration_budget_seconds=60, budget_enforced_profiles=("v12", "latest", "ga", "v13")),
    _callable("v1218.interface_registry_smoke", "v12.18 CLI, API, and Web interface registry smoke", "_v1218_interface_registry_smoke", group="architecture", version="12.18", risk="critical", timeout_seconds=120, tags=("v12", "ga", "architecture", "interfaces", "compatibility"), profiles=(*V12_ACCELERATED_PROFILES, "v13"), duration_budget_seconds=60, budget_enforced_profiles=("v12", "latest", "ga", "v13")),
    _callable("v1219.evidence_policy_smoke", "v12.19 Evidence Graph and policy engine smoke", "_v1219_evidence_policy_smoke", group="architecture", version="12.19", risk="critical", timeout_seconds=120, tags=("v12", "ga", "architecture", "evidence-graph", "policy"), profiles=(*V12_ACCELERATED_PROFILES, "v13"), duration_budget_seconds=60, budget_enforced_profiles=("v12", "latest", "ga", "v13")),
    _callable("v1220.release_check_governance_smoke", "v12.20 Release Check and CI governance smoke", "_v1220_release_check_governance_smoke", group="release-check", version="12.20", risk="critical", timeout_seconds=120, tags=("v12", "ga", "release-check", "ci", "documentation"), profiles=(*V12_ACCELERATED_PROFILES, "v13"), duration_budget_seconds=60, budget_enforced_profiles=("v12", "latest", "ga", "v13")),
    _callable("v130.lts_cutover_smoke", "v13.0 modular monolith cutover and LTS smoke", "_v130_lts_cutover_smoke", group="architecture", version="13.0", risk="critical", timeout_seconds=180, tags=("v13", "ga", "architecture", "migration", "lts"), profiles=V13_PROFILES, duration_budget_seconds=120, budget_enforced_profiles=("v13", "latest", "ga")),
    _callable("v1301.shared_kernel_security_smoke", "v13.0.1 shared kernel security hotfix smoke", "_v1301_shared_kernel_security_smoke", group="security", version="13.0.1", risk="critical", timeout_seconds=120, tags=("v13", "ga", "architecture", "verification", "lifecycle", "evidence-graph", "change-control", "zip-security"), profiles=(*V13_PROFILES, "security"), duration_budget_seconds=60, budget_enforced_profiles=("v13", "latest", "ga", "security")),
    _callable("v131.architecture_ratchet_smoke", "v13.1 architecture ratchet smoke", "_v131_architecture_ratchet_smoke", group="architecture", version="13.1", risk="critical", timeout_seconds=120, tags=("v13", "ga", "architecture", "dependencies", "ratchet", "interfaces"), profiles=V13_PROFILES, duration_budget_seconds=90, budget_enforced_profiles=("v13", "latest", "ga")),
    _callable("v132.kernel_adoption_smoke", "v13.2 Verification and Lifecycle Kernel adoption smoke", "_v132_kernel_adoption_smoke", group="security", version="13.2", risk="critical", timeout_seconds=180, tags=("v13", "ga", "verification", "lifecycle", "zip-security", "change-control", "adoption"), profiles=(*V13_PROFILES, "security"), duration_budget_seconds=120, budget_enforced_profiles=("v13", "latest", "ga", "security")),
    _callable("v133.program_persistence_authority_smoke", "v13.3 Program persistence authority and migration smoke", "_v133_program_persistence_authority_smoke", group="architecture", version="13.3", risk="critical", timeout_seconds=180, tags=("v13", "ga", "persistence", "migration", "recovery", "program"), profiles=V13_PROFILES, duration_budget_seconds=120, budget_enforced_profiles=("v13", "latest", "ga")),
    _callable("v134.program_vertical_slice_smoke", "v13.4 Program bounded-context vertical slice smoke", "_v134_program_vertical_slice_smoke", group="architecture", version="13.4", risk="critical", timeout_seconds=180, tags=("v13", "ga", "architecture", "program", "vertical-slice", "interfaces"), profiles=V13_PROFILES, duration_budget_seconds=120, budget_enforced_profiles=("v13", "latest", "ga")),
    _callable("v135.interface_decomposition_smoke", "v13.5 real CLI, API, runtime, and Web module decomposition smoke", "_v135_interface_decomposition_smoke", group="architecture", version="13.5", risk="critical", timeout_seconds=180, tags=("v13", "ga", "architecture", "interfaces", "web", "compatibility"), profiles=V13_PROFILES, duration_budget_seconds=120, budget_enforced_profiles=("v13", "latest", "ga")),
    _callable("v136.policy_gate_cutover_smoke", "v13.6 Evidence Graph and Policy main-gate cutover smoke", "_v136_policy_gate_cutover_smoke", group="architecture", version="13.6", risk="critical", timeout_seconds=180, tags=("v13", "ga", "architecture", "evidence-graph", "policy", "capabilities"), profiles=V13_PROFILES, duration_budget_seconds=120, budget_enforced_profiles=("v13", "latest", "ga")),
    _callable("v137.release_check_ci_docs_governance_smoke", "v13.7 Release Check, CI, test marker, and documentation governance smoke", "_v137_release_check_ci_docs_governance_smoke", group="release-check", version="13.7", risk="critical", timeout_seconds=180, tags=("v13", "ga", "release-check", "ci", "documentation", "reviewer-package"), profiles=(*V13_PROFILES, "security"), duration_budget_seconds=120, budget_enforced_profiles=("v13", "latest", "ga", "security")),
    _callable("v138.lts_recertification_smoke", "v13.8 final LTS recertification smoke", "_v138_lts_recertification_smoke", group="architecture", version="13.8", risk="critical", timeout_seconds=240, tags=("v13", "ga", "architecture", "lts", "migration", "reviewer-package"), profiles=(*V13_PROFILES, "security"), duration_budget_seconds=180, budget_enforced_profiles=("v13", "latest", "ga", "security", "full")),
    _callable("v140.architecture_cutover_smoke", "v14.0 domain cutover architecture ratchet", "_v140_architecture_cutover_smoke", group="architecture", version="14.0", risk="critical", timeout_seconds=120, tags=("v14", "ga", "architecture", "compatibility", "ratchet"), profiles=V14_PROFILES, duration_budget_seconds=60, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.compatibility_zero_smoke", "v14.0 compatibility retirement hard gate", "_v140_compatibility_zero_smoke", group="architecture", version="14.0", risk="critical", timeout_seconds=120, tags=("v14", "ga", "architecture", "compatibility", "retirement"), profiles=V14_PROFILES, duration_budget_seconds=60, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.interface_application_boundary_smoke", "v14.0 interface and application boundary ratchet", "_v140_interface_application_boundary_smoke", group="architecture", version="14.0", risk="critical", timeout_seconds=240, tags=("v14", "ga", "architecture", "interfaces", "typing", "complexity"), profiles=V14_PROFILES, duration_budget_seconds=180, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.domain_vertical_slice_smoke", "v14.0 bounded-context vertical slice certification", "_v140_domain_vertical_slice_smoke", group="architecture", version="14.0", risk="critical", timeout_seconds=120, tags=("v14", "ga", "architecture", "domains", "vertical-slice"), profiles=V14_PROFILES, duration_budget_seconds=60, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.verification_lifecycle_security_smoke", "v14.0 verification and lifecycle security certification", "_v140_verification_lifecycle_security_smoke", group="security", version="14.0", risk="critical", timeout_seconds=180, tags=("v14", "ga", "security", "verification", "lifecycle", "zip-security"), profiles=V14_PROFILES, duration_budget_seconds=120, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.migration_rollback_smoke", "v14.0 migration and byte-identical rollback certification", "_v140_migration_rollback_smoke", group="architecture", version="14.0", risk="critical", timeout_seconds=120, tags=("v14", "ga", "persistence", "migration", "rollback"), profiles=V14_PROFILES, duration_budget_seconds=60, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.typing_coverage_ratchet_smoke", "v14.0 typing and coverage ratchet", "_v140_typing_coverage_ratchet_smoke", group="quality", version="14.0", risk="critical", timeout_seconds=300, tags=("v14", "ga", "typing", "coverage", "ratchet"), profiles=V14_PROFILES, duration_budget_seconds=240, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.public_contract_compatibility_smoke", "v14.0 CLI API and Studio public contract compatibility", "_v140_public_contract_compatibility_smoke", group="architecture", version="14.0", risk="critical", timeout_seconds=120, tags=("v14", "ga", "interfaces", "contracts", "compatibility"), profiles=V14_PROFILES, duration_budget_seconds=60, budget_enforced_profiles=V14_PROFILES),
    _callable("v140.reviewer_package_smoke", "v14.0 final reviewer package independent verification", "_v140_reviewer_package_smoke", group="release-check", version="14.0", risk="critical", timeout_seconds=420, tags=("v14", "ga", "reviewer-package", "certification"), profiles=V14_PROFILES, duration_budget_seconds=300, budget_enforced_profiles=V14_PROFILES),
)


def _govern_definition(definition: ReleaseCheckDefinition) -> ReleaseCheckDefinition:
    profiles = list(definition.profiles)
    tags = list(definition.tags)
    key = _version_key(definition.version or "999")
    full_only = "full-only" in tags
    compatibility_callable = definition.callable_name in LEGACY_COMPATIBILITY_CALLABLES
    if compatibility_callable:
        profiles = [item for item in profiles if item not in CURRENT_NO_LEGACY_PROFILES]
        for item in ("full", "nightly"):
            if item not in profiles:
                profiles.append(item)
        if "legacy" not in tags:
            tags.append("legacy")
        return replace(
            definition,
            profiles=tuple(profiles),
            tags=tuple(tags),
            duration_budget_seconds=definition.duration_budget_seconds or 90.0,
            budget_enforced_profiles=tuple(profiles),
            budget_warning_only=True,
            budget_exception_reason="Compatibility smoke is isolated to full/nightly or its historical major profile.",
            budget_exception_expires_version="14.0",
        )
    historical = bool(definition.version) and (key < (12, 0) or (12, 0) <= key < (12, 9) or full_only)
    if historical:
        profiles = [item for item in profiles if item not in {"quick", "latest", "ga", "v12"}]
        for item in ("full", "nightly"):
            if item not in profiles:
                profiles.append(item)
        if "legacy" not in tags:
            tags.append("legacy")
        return replace(
            definition,
            profiles=tuple(profiles),
            tags=tuple(tags),
            duration_budget_seconds=definition.duration_budget_seconds or 90.0,
            budget_enforced_profiles=tuple(profiles),
            budget_warning_only=True,
            budget_exception_reason="Historical monolith is retained only in the explicitly labeled full/nightly compatibility suite.",
            budget_exception_expires_version="14.0",
        )
    if definition.group == "security" or {"zip-security", "verification"}.intersection(tags):
        if "security" not in profiles:
            profiles.append("security")
    return replace(
        definition,
        profiles=tuple(profiles),
        duration_budget_seconds=definition.duration_budget_seconds or 90.0,
        budget_enforced_profiles=tuple(dict.fromkeys((*definition.budget_enforced_profiles, *profiles))),
        budget_warning_only=False,
        budget_exception_reason="",
        budget_exception_expires_version="",
    )


CHECK_DEFINITIONS = tuple(_govern_definition(definition) for definition in _RAW_CHECK_DEFINITIONS)

KNOWN_PROFILES = {"full", "nightly", "security", "quick", "latest", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "ga", "publish"}
PROFILE_ORDER = ("full", "quick", "latest", "security", "nightly", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14", "ga", "publish")


def release_check_profiles() -> tuple[str, ...]:
    return PROFILE_ORDER
