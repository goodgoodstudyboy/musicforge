from __future__ import annotations

from song_agent.interfaces.bootstrap.cli import stores as _quality_stores

from song_agent.platform.contracts.documents import normalize_json_document

from . import dependencies as _commands_quality_parts_dependencies

from .acceptance_fix_plan import build_acceptance_kb_parser, build_planning_rule_governance_parser, build_planning_rule_impact_parser

from .planning_ruleset import print_acceptance_kb_result, print_planning_rule_governance_result, print_planning_rule_impact_result
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def _execute_planning_rule_governance(argv: list[str]) -> None:
    raw_args = ['planning-rule-governance', *argv]
    pass
    parser = build_planning_rule_governance_parser()
    args = parser.parse_args(raw_args[1:])
    store = _quality_stores.planning_rule_governance_store()
    if args.action == "active":
        version = store.active_version()
        result = {"ok": True, "active": store.active_pointer(), "version": version.to_dict() if version else {}, "summary": store.active_summary()}
    elif args.action == "versions":
        versions = store.list_versions(include_archived=args.include_archived)
        result = {"ok": True, "versions": [version.to_dict() for version in versions], "summary": {"version_count": len(versions), "active": store.active_summary()}}
    elif args.action == "version":
        version = store.read_version(args.version_id)
        result = {"ok": True, "version": version.to_dict(), "frozen_ruleset_summary": {}, "summary": governance_summary(version, active=store.active_pointer(), evidence_stale=store.version_evidence_is_stale(version))}
    elif args.action == "promotions":
        promotions = store.list_promotions(include_archived=args.include_archived)
        result = {"ok": True, "promotions": [promotion.to_dict() for promotion in promotions], "summary": {"promotion_count": len(promotions)}}
    elif args.action == "promotion":
        promotion = store.read_promotion(args.promotion_id)
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "promote-request":
        promotion = store.create_promotion({"ruleset_id": args.ruleset_id, "simulation_id": args.simulation_id, "note": args.note})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "approve":
        promotion = store.approve_promotion(args.promotion_id, {"approved_by": args.approved_by, "approval_note": args.note, "force": args.force, "override_reason": args.override_reason})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "reject":
        promotion = store.reject_promotion(args.promotion_id, {"rejected_by": args.rejected_by, "reason": args.reason})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "promote":
        promoted = store.promote(args.promotion_id, {"promoted_by": args.promoted_by, "activation_note": args.activation_note})
        result = {"ok": True, "version": promoted["version"].to_dict(), "active": promoted["active"], "promotion": promoted["promotion"].to_dict(), "summary": promoted["summary"]}
    elif args.action == "rollback":
        rolled_back = store.rollback({"target_version_id": args.target_version_id, "rolled_back_by": args.rolled_back_by, "reason": args.reason})
        result = {"ok": True, "version": rolled_back["version"].to_dict(), "active": rolled_back["active"], "summary": rolled_back["summary"]}
    elif args.action == "events":
        events = store.events(limit=args.limit)
        result = {"ok": True, "events": events, "summary": {"event_count": len(events)}}
    else:
        parser.error("unknown planning-rule-governance action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_rule_governance_result(normalize_json_document(result))
    raise SystemExit(0)

def handle_planning_rule_governance(argv: list[str]) -> None:
    _execute_planning_rule_governance(argv)

def _execute_planning_rule_impact(argv: list[str]) -> None:
    raw_args = ['planning-rule-impact', *argv]
    pass
    parser = build_planning_rule_impact_parser()
    args = parser.parse_args(raw_args[1:])
    store = _quality_stores.planning_rule_impact_store()
    if args.action == "refresh":
        scope = {"type": "release" if args.release_id else "project" if args.project_id else "global", "release_id": args.release_id, "project_id": args.project_id}
        report = store.refresh({"scope": scope, "include_legacy": not args.exclude_legacy, "include_superseded": not args.exclude_superseded})
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    elif args.action == "list":
        reports = store.list_reports(include_archived=args.include_archived, release_id=args.release_id, project_id=args.project_id)
        result = {"ok": True, "reports": [report.to_dict() for report in reports], "summary": {"report_count": len(reports), "latest": planning_rule_impact_summary(reports[0]) if reports else {"status": "missing"}}}
    elif args.action == "show":
        report = store.get_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report), "stale": store.report_is_stale(report), "integrity_ok": store.report_integrity_ok(report)}
    elif args.action == "refresh-existing":
        report = store.refresh_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    elif args.action == "archive":
        report = store.archive_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    else:
        parser.error("unknown planning-rule-impact action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_rule_impact_result(normalize_json_document(result))
    raise SystemExit(0)

def handle_planning_rule_impact(argv: list[str]) -> None:
    _execute_planning_rule_impact(argv)

def _execute_acceptance_kb(argv: list[str]) -> None:
    raw_args = ['acceptance-kb', *argv]
    pass
    parser = build_acceptance_kb_parser()
    args = parser.parse_args(raw_args[1:])
    store = _quality_stores.acceptance_knowledge_base_store()
    if args.action == "refresh":
        scope = {"type": "global", "project_id": args.project_id, "release_id": args.release_id}
        report = store.refresh(scope)
        result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
    elif args.action == "report":
        report = store.latest_report()
        result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
    elif args.action == "entries":
        entries = store.list_entries(include_hidden=args.include_hidden)
        result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
    elif args.action == "show":
        entry = store.read_entry(args.entry_id)
        result = {"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)}
    elif args.action == "search":
        query = {"issue_type": args.issue_type, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id, "outcome_status": args.outcome_status}
        entries = store.search_entries(query)
        result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
    elif args.action == "recommend":
        recommendation = store.recommend({"issue_types": args.issue_types, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id})
        result = {"ok": True, "recommendation": recommendation}
    else:
        parser.error("unknown acceptance-kb action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_acceptance_kb_result(normalize_json_document(result))
    raise SystemExit(0)

def handle_acceptance_kb(argv: list[str]) -> None:
    _execute_acceptance_kb(argv)

__all__ = ('_execute_planning_rule_governance', 'handle_planning_rule_governance', '_execute_planning_rule_impact', 'handle_planning_rule_impact', '_execute_acceptance_kb', 'handle_acceptance_kb')
