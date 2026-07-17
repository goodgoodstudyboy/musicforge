from __future__ import annotations


from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_quality_parts_dependencies
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, Any, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.Any, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def build_acceptance_fix_plan_parser() -> argparse.ArgumentParser:
    plan_parser = argparse.ArgumentParser(description="Manage local MusicForge knowledge-assisted Acceptance Fix Plans.")
    subparsers = plan_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Fix Plan from Acceptance Analytics and KB history.")
    create.add_argument("--analytics-report-id", required=True, help="Source Acceptance Analytics report id.")
    create.add_argument("--kb-report-id", default=None, help="Optional Acceptance KB report id.")
    create.add_argument("--max-items", type=int, default=20, help="Maximum planned items.")
    create.add_argument("--include-hidden-kb", action="store_true", help="Allow hidden KB entries in planning evidence.")

    subparsers.add_parser("list", help="List Fix Plans.").add_argument("--include-archived", action="store_true")

    show = subparsers.add_parser("show", help="Show a Fix Plan.")
    show.add_argument("plan_id")

    refresh = subparsers.add_parser("refresh", help="Refresh an existing Fix Plan.")
    refresh.add_argument("plan_id")

    create_sprint = subparsers.add_parser("create-fix-sprint", help="Create a Fix Sprint from a Fix Plan.")
    create_sprint.add_argument("plan_id")
    create_sprint.add_argument("--name", default=None)
    create_sprint.add_argument("--planned-item-id", action="append", dest="planned_item_ids", default=[])
    create_sprint.add_argument("--profile", default=None)

    review = subparsers.add_parser("review", help="Show or refresh a Fix Plan Outcome Review.")
    review.add_argument("plan_id")
    review.add_argument("--refresh", action="store_true")

    recommend = subparsers.add_parser("recommend", help="Preview a non-persisted Fix Plan.")
    recommend.add_argument("--analytics-report-id", required=True)
    recommend.add_argument("--kb-report-id", default=None)
    recommend.add_argument("--max-items", type=int, default=20)
    recommend.add_argument("--include-hidden-kb", action="store_true")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return plan_parser

def build_planning_ruleset_parser() -> argparse.ArgumentParser:
    ruleset_parser = argparse.ArgumentParser(description="Manage local MusicForge Planning Rule Sets.")
    subparsers = ruleset_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Planning Rule Set.")
    create.add_argument("--template", default="baseline", help="Template: baseline, manual_conservative, kb_trust_light, waiver_strict, synthetic_strict.")
    create.add_argument("--name", default=None)
    create.add_argument("--description", default=None)

    subparsers.add_parser("list", help="List Planning Rule Sets.").add_argument("--include-archived", action="store_true")

    show = subparsers.add_parser("show", help="Show a Planning Rule Set.")
    show.add_argument("ruleset_id")

    clone = subparsers.add_parser("clone", help="Clone a Planning Rule Set.")
    clone.add_argument("ruleset_id")
    clone.add_argument("--name", default=None)

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Set.")
    archive.add_argument("ruleset_id")

    validate = subparsers.add_parser("validate", help="Validate a Planning Rule Set.")
    validate.add_argument("ruleset_id")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return ruleset_parser

def build_planning_simulation_parser() -> argparse.ArgumentParser:
    simulation_parser = argparse.ArgumentParser(description="Run local MusicForge Planning Rule Simulations.")
    subparsers = simulation_parser.add_subparsers(dest="action", required=True)

    run = subparsers.add_parser("run", help="Run a Planning Rule Simulation.")
    run.add_argument("--ruleset-id", required=True)
    run.add_argument("--release-id", default=None)
    run.add_argument("--project-id", default=None)
    run.add_argument("--review-id", action="append", dest="review_ids", default=[])
    run.add_argument("--include-warning-reviews", action="store_true", default=True)
    run.add_argument("--exclude-synthetic-only", action="store_true")

    show = subparsers.add_parser("show", help="Show a Planning Rule Simulation.")
    show.add_argument("simulation_id")

    refresh = subparsers.add_parser("refresh", help="Refresh a Planning Rule Simulation.")
    refresh.add_argument("simulation_id")

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Simulation.")
    archive.add_argument("simulation_id")

    subparsers.add_parser("list", help="List Planning Rule Simulations.").add_argument("--include-archived", action="store_true")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return simulation_parser

def build_planning_rule_governance_parser() -> argparse.ArgumentParser:
    governance_parser = argparse.ArgumentParser(description="Govern local MusicForge Planning Rule promotions and active versions.")
    subparsers = governance_parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("active", help="Show the current active Planning Rule Version.")
    subparsers.add_parser("versions", help="List Planning Rule Versions.").add_argument("--include-archived", action="store_true")

    version = subparsers.add_parser("version", help="Show one Planning Rule Version.")
    version.add_argument("version_id")

    subparsers.add_parser("promotions", help="List Planning Rule Promotions.").add_argument("--include-archived", action="store_true")

    promotion = subparsers.add_parser("promotion", help="Show one Planning Rule Promotion.")
    promotion.add_argument("promotion_id")

    request = subparsers.add_parser("promote-request", help="Create a Planning Rule Promotion request.")
    request.add_argument("--ruleset-id", required=True)
    request.add_argument("--simulation-id", required=True)
    request.add_argument("--note", default="")

    approve = subparsers.add_parser("approve", help="Approve a Planning Rule Promotion.")
    approve.add_argument("promotion_id")
    approve.add_argument("--approved-by", default="developer")
    approve.add_argument("--note", default="")
    approve.add_argument("--force", action="store_true")
    approve.add_argument("--override-reason", default="")

    reject = subparsers.add_parser("reject", help="Reject a Planning Rule Promotion.")
    reject.add_argument("promotion_id")
    reject.add_argument("--rejected-by", default="developer")
    reject.add_argument("--reason", required=True)

    promote = subparsers.add_parser("promote", help="Promote an approved Planning Rule Promotion to active.")
    promote.add_argument("promotion_id")
    promote.add_argument("--promoted-by", default="developer")
    promote.add_argument("--activation-note", default="")

    rollback = subparsers.add_parser("rollback", help="Rollback active Planning Rules to a previous version.")
    rollback.add_argument("--target-version-id", required=True)
    rollback.add_argument("--rolled-back-by", default="developer")
    rollback.add_argument("--reason", required=True)

    subparsers.add_parser("events", help="List Planning Rule Governance events.").add_argument("--limit", type=int, default=50)

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return governance_parser

def build_planning_rule_impact_parser() -> argparse.ArgumentParser:
    impact_parser = argparse.ArgumentParser(description="Monitor active MusicForge Planning Rule impact.")
    subparsers = impact_parser.add_subparsers(dest="action", required=True)

    refresh = subparsers.add_parser("refresh", help="Refresh a Planning Rule Impact report.")
    refresh.add_argument("--release-id", default=None)
    refresh.add_argument("--project-id", default=None)
    refresh.add_argument("--include-legacy", action="store_true", default=True)
    refresh.add_argument("--exclude-legacy", action="store_true")
    refresh.add_argument("--include-superseded", action="store_true", default=True)
    refresh.add_argument("--exclude-superseded", action="store_true")

    listing = subparsers.add_parser("list", help="List Planning Rule Impact reports.")
    listing.add_argument("--include-archived", action="store_true")
    listing.add_argument("--release-id", default=None)
    listing.add_argument("--project-id", default=None)

    show = subparsers.add_parser("show", help="Show one Planning Rule Impact report.")
    show.add_argument("report_id")

    refresh_existing = subparsers.add_parser("refresh-existing", help="Refresh an existing Planning Rule Impact report.")
    refresh_existing.add_argument("report_id")

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Impact report.")
    archive.add_argument("report_id")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return impact_parser

def build_acceptance_kb_parser() -> argparse.ArgumentParser:
    kb_parser = argparse.ArgumentParser(description="Manage the local MusicForge Acceptance Knowledge Base.")
    subparsers = kb_parser.add_subparsers(dest="action", required=True)

    refresh = subparsers.add_parser("refresh", help="Refresh Acceptance KB entries and report.")
    refresh.add_argument("--project-id", default=None)
    refresh.add_argument("--release-id", default=None)

    subparsers.add_parser("report", help="Show the latest Acceptance KB report.")

    entries = subparsers.add_parser("entries", help="List Acceptance KB entries.")
    entries.add_argument("--include-hidden", action="store_true")

    show = subparsers.add_parser("show", help="Show one Acceptance KB entry.")
    show.add_argument("entry_id")

    search = subparsers.add_parser("search", help="Search Acceptance KB entries.")
    search.add_argument("--issue-type", default=None)
    search.add_argument("--style", default=None)
    search.add_argument("--song-id", default=None)
    search.add_argument("--project-id", default=None)
    search.add_argument("--release-id", default=None)
    search.add_argument("--outcome-status", default=None)

    recommend = subparsers.add_parser("recommend", help="Recommend next actions from Acceptance KB history.")
    recommend.add_argument("--issue-type", action="append", dest="issue_types", default=[])
    recommend.add_argument("--style", default=None)
    recommend.add_argument("--song-id", default=None)
    recommend.add_argument("--project-id", default=None)
    recommend.add_argument("--release-id", default=None)

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return kb_parser

def _run_audio_lab_command(args: argparse.Namespace) -> ImplementationDocument:
    pass

    store = AudioLabStore()
    if args.section == "status":
        return {"ok": True, "environment": store.environment_status()}
    if args.section == "detect":
        return {"ok": True, "environment": store.detect_environment()}
    if args.section == "test-profile":
        result = store.test_profile(args.profile_id)
        return {"ok": result.get("status") != "failed", "profile_test": result, "status": result.get("status")}
    if args.section == "setup-report":
        report = store.setup_report()
        if args.report_out is not None:
            write_interface_document(args.report_out, report)
        return {"ok": True, "setup_report": report, "status": report.get("status")}
    if args.section == "smoke":
        report = store.run_smoke({"cases": args.cases, "render_audio": args.render_audio, "profile_id": args.profile_id})
        if args.report_out is not None:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") != "failed", "smoke_run": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.section == "smoke-report":
        report = store.read_smoke_report(args.smoke_run_id)
        if args.report_out is not None:
            write_interface_document(args.report_out, report)
        return {"ok": True, "smoke_run": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.section == "session":
        if args.session_action == "create":
            session = store.create_session({"from_smoke": args.from_smoke})
            return {"ok": True, "session": session, "summary": session.get("summary", {}), "status": session.get("status")}
        if args.session_action == "list":
            sessions = store.list_sessions()
            return {"ok": True, "sessions": sessions, "summary": {"session_count": len(sessions)}, "status": "passed"}
        if args.session_action == "detail":
            session = store.read_session(args.session_id)
            return {"ok": True, "session": session, "summary": session.get("summary", {}), "status": session.get("status")}
        if args.session_action == "review":
            result = store.write_item_review(
                args.session_id,
                args.item_id,
                {
                    "result": args.result,
                    "rating": args.rating,
                    "reviewer": {"name": args.reviewer, "role": args.role},
                    "notes": args.notes,
                    "playback_confirmed": args.playback_confirmed,
                },
            )
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
        if args.session_action == "marker":
            result = store.add_marker(args.session_id, args.item_id, {"time_seconds": args.time_seconds, "category": args.category, "severity": args.severity, "message": args.message})
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
        if args.session_action == "create-review-task":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "review_task", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "create-audio-revision-draft":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "audio_revision", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "create-mix-patch-draft":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "mix_patch", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "report":
            report = store.session_report(args.session_id)
            return {"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
        if args.session_action == "close":
            result = store.close_session(args.session_id, {"closed_by": args.closed_by})
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
    if args.section == "compare":
        if args.compare_action == "create":
            comparison = store.create_comparison({"left": args.left, "right": args.right})
            return {"ok": True, "comparison": comparison, "status": "created"}
        if args.compare_action == "review":
            comparison = store.review_comparison(
                args.comparison_id,
                {
                    "preferred": args.preferred,
                    "rating": args.rating,
                    "rating_delta": args.rating_delta,
                    "reviewer": {"name": args.reviewer, "role": args.role},
                    "notes": args.notes,
                    "playback_confirmed": args.playback_confirmed,
                },
            )
            return {"ok": True, "comparison": comparison, "status": "reviewed"}
        if args.compare_action == "report":
            report = store.comparison_report(args.comparison_id)
            return {"ok": report.get("status") != "failed", "report": report, "status": report.get("status")}
    raise ValueError("Unsupported audio-lab command.")

__all__ = ('build_acceptance_fix_plan_parser', 'build_planning_ruleset_parser', 'build_planning_simulation_parser', 'build_planning_rule_governance_parser', 'build_planning_rule_impact_parser', 'build_acceptance_kb_parser', '_run_audio_lab_command')
