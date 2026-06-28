from __future__ import annotations

from dataclasses import dataclass, field
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
    return selected


def release_check_definitions_as_dicts(definitions: Iterable[ReleaseCheckDefinition] | None = None) -> list[dict[str, object]]:
    source = CHECK_DEFINITIONS if definitions is None else definitions
    return [definition_to_dict(definition) for definition in source]


def definition_to_dict(definition: ReleaseCheckDefinition) -> dict[str, object]:
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
    }


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
    )


BASE_PROFILES = ("full", "quick", "latest", "ga")
LATEST_PROFILES = ("full", "quick", "latest")
V7_PROFILES = ("full", "v7")
GA_PROFILES = ("full", "quick", "latest", "ga")
V10_PROFILES = ("full", "quick", "latest", "ga", "v10")

CHECK_DEFINITIONS: tuple[ReleaseCheckDefinition, ...] = (
    _command("pytest.full", "pytest", ("python", "-m", "pytest", "-q"), group="core", kind="pytest", risk="critical", timeout_seconds=6000),
    _command("git.diff_check", "git diff --check", ("git", "diff", "--check"), group="git", kind="git", risk="high", timeout_seconds=60, profiles=BASE_PROFILES),
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
)

KNOWN_PROFILES = {"full", "quick", "latest", "v7", "v8", "v9", "v10", "ga", "publish"}
