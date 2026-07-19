from __future__ import annotations

from song_agent.platform.contracts import DomainDocument
from song_agent.platform.contracts.coercion import as_document as _as_document


from . import dependencies as _commands_quality_parts_dependencies

from .audio_lab_parser_and_adapters import build_audio_lab_parser

from .audio_fix_sprint import build_audio_campaign_parser, build_audio_fix_sprint_parser, build_release_audio_certification_parser

from .verify_release_audio_certification import build_release_audio_baseline_parser, build_release_audio_quality_observatory_parser, build_release_audio_regression_parser, build_release_audio_regression_response_parser, build_release_audio_timeline_parser, build_verify_release_audio_baseline_registry_parser, build_verify_release_audio_regression_response_parser

from .release_audio_quality_actions import build_release_audio_command_center_parser, build_release_audio_quality_actions_parser

from .acceptance_fix_plan import _run_audio_lab_command

from .audio_fix_sprint_command import _run_audio_campaign_command, _run_audio_fix_sprint_command, _run_release_audio_certification_command, _run_release_audio_timeline_command

from .release_audio_regression_command import _run_release_audio_baseline_command, _run_release_audio_quality_actions_command, _run_release_audio_quality_observatory_command, _run_release_audio_regression_command, _run_release_audio_regression_response_command

from .release_audio_command_center_command import _print_audio_campaign_result, _print_audio_fix_sprint_result, _print_audio_lab_result, _print_release_audio_certification_result, _run_release_audio_command_center_command
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, Any, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.Any, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def print_planning_ruleset_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    ruleset = _as_document(result.get("ruleset"))
    validation = _as_document(result.get("validation"))
    print("MusicForge planning-ruleset")
    if validation:
        print(f"validation: {validation.get('status')}")
        print(f"ruleset: {validation.get('ruleset_id')}")
        return
    print(f"ruleset: {summary.get('ruleset_id') or ruleset.get('ruleset_id') or '-'}")
    print(f"status: {summary.get('status') or ruleset.get('status') or '-'}")
    print(f"template: {summary.get('template') or '-'}")
    if result.get("rulesets") is not None:
        print(f"rulesets: {len(result.get('rulesets') or [])}")

def print_planning_simulation_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    simulation = _as_document(result.get("simulation"))
    print("MusicForge planning-simulation")
    print(f"simulation: {summary.get('simulation_id') or simulation.get('simulation_id') or '-'}")
    print(f"ruleset: {summary.get('ruleset_id') or simulation.get('ruleset_id') or '-'}")
    print(f"reviews: {summary.get('review_count', 0)}")
    print(f"items: {summary.get('item_count', 0)}")
    print(f"alignment: {summary.get('baseline_alignment_score')} -> {summary.get('simulated_alignment_score')} ({summary.get('alignment_delta')})")
    print(f"recommendation: {summary.get('recommendation') or '-'}")
    if result.get("simulations") is not None:
        print(f"simulations: {len(result.get('simulations') or [])}")

def print_planning_rule_governance_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    promotion = _as_document(result.get("promotion"))
    version = _as_document(result.get("version"))
    print("MusicForge planning-rule-governance")
    print(f"status: {summary.get('status') or version.get('status') or promotion.get('status') or '-'}")
    print(f"active_version: {summary.get('active_version_id') or version.get('version_id') or '-'}")
    if promotion:
        print(f"promotion: {promotion.get('promotion_id')}")
        print(f"recommendation: {(promotion.get('evidence') or {}).get('recommendation')}")
    if result.get("versions") is not None:
        print(f"versions: {len(result.get('versions') or [])}")
    if result.get("promotions") is not None:
        print(f"promotions: {len(result.get('promotions') or [])}")
    if result.get("events") is not None:
        print(f"events: {len(result.get('events') or [])}")

def print_planning_rule_impact_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    report = _as_document(result.get("impact_report"))
    print("MusicForge planning-rule-impact")
    print(f"report: {summary.get('report_id') or report.get('report_id') or '-'}")
    print(f"status: {summary.get('status') or report.get('status') or '-'}")
    print(f"active_version: {summary.get('active_version_id') or '-'}")
    print(f"plans: {summary.get('observed_plan_count', 0)}")
    print(f"reviews: {summary.get('observed_review_count', 0)}")
    print(f"manual_reviews: {summary.get('manual_review_count', 0)}")
    print(f"synthetic_reviews: {summary.get('synthetic_review_count', 0)}")
    print(f"recommendation: {summary.get('recommendation') or '-'}")
    if result.get("reports") is not None:
        print(f"reports: {len(result.get('reports') or [])}")

def print_acceptance_kb_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    recommendation = _as_document(result.get("recommendation"))
    entry = _as_document(result.get("entry"))
    print("MusicForge acceptance-kb")
    if summary:
        print(f"status: {summary.get('status') or '-'}")
        print(f"entries: {summary.get('entry_count', 0)}")
        print(f"effective: {summary.get('effective_count', 0)}")
        print(f"average_score: {summary.get('average_effectiveness_score')}")
    if result.get("entries") is not None:
        print(f"listed_entries: {len(result.get('entries') or [])}")
    if recommendation:
        print(f"recommendation: {recommendation.get('status')}")
        print(f"matches: {recommendation.get('matching_entry_count', 0)}")
    if entry:
        print(f"entry: {entry.get('entry_id')}")

def _acceptance_analytics_fail_on(readiness: str, fail_on: str | None) -> bool:
    if not fail_on:
        return False
    order = {"ready": 0, "watch": 1, "needs_work": 2, "blocked": 3, "empty": 0, "missing": 0}
    return order.get(readiness, 0) >= order.get(fail_on, 0)

def _execute_audio_lab(argv: list[str]) -> None:
    raw_args = ['audio-lab', *argv]
    parser = build_audio_lab_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_lab_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_lab_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked"}:
        raise SystemExit(1)
    return

def handle_audio_lab(argv: list[str]) -> None:
    _execute_audio_lab(argv)

def _execute_audio_fix_sprint(argv: list[str]) -> None:
    raw_args = ['audio-fix-sprint', *argv]
    parser = build_audio_fix_sprint_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_fix_sprint_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_fix_sprint_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_audio_fix_sprint(argv: list[str]) -> None:
    _execute_audio_fix_sprint(argv)

def _execute_audio_campaign(argv: list[str]) -> None:
    raw_args = ['audio-campaign', *argv]
    parser = build_audio_campaign_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_campaign_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_campaign_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_audio_campaign(argv: list[str]) -> None:
    _execute_audio_campaign(argv)

def _execute_release_audio_certification(argv: list[str]) -> None:
    raw_args = ['release-audio-certification', *argv]
    parser = build_release_audio_certification_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_certification_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_certification(argv: list[str]) -> None:
    _execute_release_audio_certification(argv)

def _execute_release_audio_timeline(argv: list[str]) -> None:
    raw_args = ['release-audio-timeline', *argv]
    parser = build_release_audio_timeline_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_timeline_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_timeline(argv: list[str]) -> None:
    _execute_release_audio_timeline(argv)

def _execute_release_audio_regression(argv: list[str]) -> None:
    raw_args = ['release-audio-regression', *argv]
    parser = build_release_audio_regression_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_regression_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_regression(argv: list[str]) -> None:
    _execute_release_audio_regression(argv)

def _execute_release_audio_baseline(argv: list[str]) -> None:
    raw_args = ['release-audio-baseline', *argv]
    parser = build_release_audio_baseline_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_baseline_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_baseline(argv: list[str]) -> None:
    _execute_release_audio_baseline(argv)

def _execute_release_audio_regression_response(argv: list[str]) -> None:
    raw_args = ['release-audio-regression-response', *argv]
    parser = build_release_audio_regression_response_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_regression_response_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_regression_response(argv: list[str]) -> None:
    _execute_release_audio_regression_response(argv)

def _execute_release_audio_quality_observatory(argv: list[str]) -> None:
    raw_args = ['release-audio-quality-observatory', *argv]
    parser = build_release_audio_quality_observatory_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_quality_observatory_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_quality_observatory(argv: list[str]) -> None:
    _execute_release_audio_quality_observatory(argv)

def _execute_release_audio_quality_actions(argv: list[str]) -> None:
    raw_args = ['release-audio-quality-actions', *argv]
    parser = build_release_audio_quality_actions_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_quality_actions_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_quality_actions(argv: list[str]) -> None:
    _execute_release_audio_quality_actions(argv)

def _execute_release_audio_command_center(argv: list[str]) -> None:
    raw_args = ['release-audio-command-center', *argv]
    parser = build_release_audio_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_release_audio_command_center(argv: list[str]) -> None:
    _execute_release_audio_command_center(argv)

def _execute_verify_release_audio_baseline_registry_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-baseline-registry-package', *argv]
    pass




    parser = build_verify_release_audio_baseline_registry_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_baseline_registry_package(args.zip_path, strict=args.strict, require_active=args.require_active)
    if args.report_out is not None:
        write_release_audio_baseline_registry_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Baseline Registry verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_baseline_registry_verification_exit_code(report))

def handle_verify_release_audio_baseline_registry_package(argv: list[str]) -> None:
    _execute_verify_release_audio_baseline_registry_package(argv)

def _execute_verify_release_audio_regression_response_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-regression-response-package', *argv]
    pass




    parser = build_verify_release_audio_regression_response_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_regression_response_package(
        args.zip_path,
        strict=args.strict,
        require_closed=args.require_closed,
        require_signed=args.require_signed,
        require_regression_current=args.require_regression_current,
        release_audio_regression_path=args.release_audio_regression,
        release_audio_regression_verification_report_path=args.release_audio_regression_verification_report,
        baseline_timeline_path=args.baseline_timeline,
        baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
        baseline_certification_path=args.baseline_certification,
        baseline_certification_verification_report_path=args.baseline_certification_verification_report,
        current_timeline_path=args.current_timeline,
        current_timeline_verification_report_path=args.current_timeline_verification_report,
        current_certification_path=args.current_certification,
        current_certification_verification_report_path=args.current_certification_verification_report,
    )
    if args.report_out is not None:
        write_release_audio_regression_response_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Regression Response verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_regression_response_verification_exit_code(report))

def handle_verify_release_audio_regression_response_package(argv: list[str]) -> None:
    _execute_verify_release_audio_regression_response_package(argv)

__all__ = ('print_planning_ruleset_result', 'print_planning_simulation_result', 'print_planning_rule_governance_result', 'print_planning_rule_impact_result', 'print_acceptance_kb_result', '_acceptance_analytics_fail_on', '_execute_audio_lab', 'handle_audio_lab', '_execute_audio_fix_sprint', 'handle_audio_fix_sprint', '_execute_audio_campaign', 'handle_audio_campaign', '_execute_release_audio_certification', 'handle_release_audio_certification', '_execute_release_audio_timeline', 'handle_release_audio_timeline', '_execute_release_audio_regression', 'handle_release_audio_regression', '_execute_release_audio_baseline', 'handle_release_audio_baseline', '_execute_release_audio_regression_response', 'handle_release_audio_regression_response', '_execute_release_audio_quality_observatory', 'handle_release_audio_quality_observatory', '_execute_release_audio_quality_actions', 'handle_release_audio_quality_actions', '_execute_release_audio_command_center', 'handle_release_audio_command_center', '_execute_verify_release_audio_baseline_registry_package', 'handle_verify_release_audio_baseline_registry_package', '_execute_verify_release_audio_regression_response_package', 'handle_verify_release_audio_regression_response_package')
