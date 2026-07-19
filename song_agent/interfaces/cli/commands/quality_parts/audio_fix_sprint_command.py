from __future__ import annotations



from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_quality_parts_dependencies
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, Any, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.Any, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def _run_audio_fix_sprint_command(args: argparse.Namespace) -> ImplementationDocument:
    pass

    store = AudioFixSprintStore()
    if args.action == "create":
        sprint = store.create_sprint({"session_ids": args.session_ids, "name": args.name, "include_test_audio": args.include_test_audio})
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "list":
        sprints = store.list_sprints()
        return {"ok": True, "sprints": sprints, "summary": {"sprint_count": len(sprints)}, "status": "passed"}
    if args.action == "detail":
        sprint = store.read_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "refresh":
        sprint = store.refresh_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "create-drafts":
        result = store.create_drafts(args.sprint_id, {"draft_type": args.draft_type, "item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "generate-candidates":
        result = store.generate_candidates(args.sprint_id, {"item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "review-candidate":
        result = store.review_candidate(
            args.sprint_id,
            args.item_id,
            args.candidate_id,
            {
                "preferred": args.preferred,
                "rating": args.rating,
                "rating_delta": args.rating_delta,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("candidate", {}).get("status")}
    if args.action == "select-candidate":
        result = store.select_candidate(args.sprint_id, args.item_id, args.candidate_id, {"selected_by": args.selected_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "create-recheck-session":
        result = store.create_recheck_session(args.sprint_id)
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "review-recheck":
        result = store.review_recheck_item(
            args.sprint_id,
            args.item_id,
            {
                "result": args.result,
                "rating": args.rating,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "closeout":
        report = store.closeout_report(args.sprint_id)
        return {"ok": report.get("status") == "passed", "closeout": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "close":
        result = store.close_sprint(args.sprint_id, {"closed_by": args.closed_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    raise ValueError("Unsupported audio-fix-sprint command.")

def _run_audio_campaign_command_part_01(args: argparse.Namespace, _split_state):
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    store = AudioCampaignStore()
    _split_state['governance_store'] = AudioCampaignGovernanceStore(campaign_store=store)
    planner_store = AudioCampaignPlannerStore(audio_lab_store=store.audio_lab_store, audio_campaign_store=store)
    _split_state['remediation_store'] = AudioCampaignRemediationStore(planner_store=planner_store, campaign_store=store, fix_sprint_store=store.audio_fix_sprint_store)
    if args.action == 'plan-release':
        _split_state['plan'] = planner_store.refresh_plan(args.release_id)
        return (True, {'ok': _split_state['plan'].get('status') != 'blocked', 'plan': _split_state['plan'], 'summary': _split_state['plan'].get('preflight_summary', {}), 'status': _split_state['plan'].get('status')})
    if args.action == 'preflight-release':
        preflight = planner_store.preflight(args.release_id)
        return (True, {'ok': preflight.get('status') == 'passed', 'preflight': preflight, 'summary': preflight.get('summary', {}), 'status': preflight.get('status')})
    if args.action == 'create-from-release':
        _split_state['result'] = planner_store.create_campaign_from_release(args.release_id, {'name': args.name, 'minimum_rating': args.minimum_rating, 'allow_failed_preflight': args.allow_failed_preflight})
        return (True, {'ok': True, **_split_state['result'], 'summary': _split_state['result'].get('link', {}).get('coverage', {}), 'status': _split_state['result'].get('campaign', {}).get('status')})
    if args.action == 'release-status':
        status = planner_store.status(args.release_id)
        return (True, {'ok': status.get('status') != 'failed', **status})
    if args.action == 'release-link':
        link = planner_store.link_campaign(args.release_id, args.campaign_id)
        return (True, {'ok': True, 'link': link, 'summary': link.get('coverage', {}), 'status': link.get('coverage_status')})
    if args.action == 'create':
        campaign = store.create_campaign({'session_ids': args.session_ids, 'name': args.name, 'profile': args.profile, 'allow_test_audio': args.allow_test_audio, 'allow_synthetic_review': args.allow_synthetic_review, 'minimum_rating': args.minimum_rating})
        return (True, {'ok': True, 'campaign': campaign, 'summary': campaign.get('summary', {}), 'status': campaign.get('status')})
    if args.action == 'list':
        campaigns = store.list_campaigns()
        return (True, {'ok': True, 'campaigns': campaigns, 'summary': {'campaign_count': len(campaigns)}, 'status': 'passed'})
    if args.action == 'detail':
        campaign = store.read_campaign(args.campaign_id)
        return (True, {'ok': True, 'campaign': campaign, 'summary': campaign.get('summary', {}), 'status': campaign.get('status')})
    if args.action == 'refresh':
        campaign = store.refresh_campaign(args.campaign_id)
        return (True, {'ok': True, 'campaign': campaign, 'summary': campaign.get('summary', {}), 'status': campaign.get('status')})
    if args.action == 'link-session':
        campaign = store.link_listening_session(args.campaign_id, args.session_id)
        return (True, {'ok': True, 'campaign': campaign, 'summary': campaign.get('summary', {}), 'status': campaign.get('status')})
    if args.action == 'create-fix-sprints':
        _split_state['result'] = store.create_fix_sprints(args.campaign_id)
        return (True, {'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': _split_state['result'].get('report', {}).get('summary', {})})
    if args.action == 'report':
        _split_state['report'] = store.refresh_report(args.campaign_id)
        return (True, {'ok': _split_state['report'].get('status') == 'passed', 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
    if args.action == 'signoff':
        _split_state['result'] = store.signoff(args.campaign_id, {'signed_by': args.signed_by, 'role': args.role, 'reason': args.reason})
        return (True, {'ok': True, **_split_state['result'], 'summary': _split_state['result'].get('report', {}).get('summary', {})})
    if args.action == 'export':
        _split_state['result'] = store.export_campaign(args.campaign_id)
        return (True, {'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': _split_state['result'].get('manifest', {})})
    if args.action == 'zip':
        _split_state['result'] = store.build_zip(args.campaign_id)
        return (True, {'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}})
    if args.action == 'verify':
        _split_state['report'] = store.verify_zip(args.campaign_id, strict=args.strict, require_real_audio=args.require_real_audio, require_manual_review=args.require_manual_review, require_fix_sprints_closed=args.require_fix_sprints_closed, require_signed=args.require_signed)
        if args.report_out is not None:
            write_audio_campaign_verification_report(_split_state['report'], args.report_out)
        return (True, {'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
    if args.action == 'governance':
        _split_state['report'] = _split_state['governance_store'].refresh_governance_report(args.campaign_id)
        return (True, {'ok': _split_state['report'].get('status') == 'signed', 'governance': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
    if args.action == 'analytics':
        analytics = _split_state['governance_store'].refresh_analytics(args.campaign_id)
        return (True, {'ok': True, 'analytics': analytics, 'summary': analytics.get('summary', {}), 'status': analytics.get('status')})
    if args.action == 'archive':
        manifest = _split_state['governance_store'].export_archive(args.campaign_id)
        return (True, {'ok': True, 'manifest': manifest, 'summary': manifest.get('summary', {}), 'status': 'passed'})
    if args.action == 'archive-zip':
        _split_state['result'] = _split_state['governance_store'].build_archive_zip(args.campaign_id)
        return (True, {'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}})
    return (False, None)

def _run_audio_campaign_command_part_02(args: argparse.Namespace, _split_state):
    if args.action == 'verify-archive':
        _split_state['report'] = _split_state['governance_store'].verify_archive(args.campaign_id, {'strict': args.strict, 'require_signed': True, 'require_verification_passed': True})
        if args.report_out is not None:
            write_audio_campaign_archive_verification_report(_split_state['report'], args.report_out)
        return (True, {'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
    if args.action == 'remediation-plan':
        _split_state['plan'] = _split_state['remediation_store'].refresh_plan(args.release_id)
        return (True, {'ok': _split_state['plan'].get('status') != 'blocked', 'plan': _split_state['plan'], 'summary': _split_state['plan'].get('summary', {}), 'status': _split_state['plan'].get('status')})
    if args.action == 'remediation-status':
        _split_state['plan'] = _split_state['remediation_store'].refresh_plan(args.release_id)
        queue = _split_state['remediation_store'].build_action_queue(args.release_id)
        closeout = _split_state['remediation_store'].closeout_report(args.release_id)
        return (True, {'ok': closeout.get('status') == 'passed', 'plan': _split_state['plan'], 'queue': queue, 'closeout': closeout, 'summary': closeout.get('summary', {}), 'status': closeout.get('status')})
    if args.action == 'remediation-run-safe':
        _split_state['result'] = _split_state['remediation_store'].run_safe_actions(args.release_id, {'closed_by': args.closed_by})
        return (True, {'ok': True, **_split_state['result'], 'summary': _split_state['result'].get('closeout', {}).get('summary', {}), 'status': _split_state['result'].get('closeout', {}).get('status')})
    if args.action == 'remediation-closeout':
        closeout = _split_state['remediation_store'].closeout_report(args.release_id)
        return (True, {'ok': closeout.get('status') == 'passed', 'closeout': closeout, 'summary': closeout.get('summary', {}), 'status': closeout.get('status')})
    if args.action == 'remediation-signoff':
        _split_state['result'] = _split_state['remediation_store'].signoff(args.release_id, {'signed_by': args.signed_by, 'role': args.role, 'reason': args.reason})
        return (True, {'ok': True, **_split_state['result'], 'summary': _split_state['result'].get('closeout', {}).get('summary', {}), 'status': _split_state['result'].get('status')})
    if args.action == 'remediation-export':
        _split_state['result'] = _split_state['remediation_store'].export_package(args.release_id)
        return (True, {'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': _split_state['result'].get('manifest', {}), 'status': _split_state['result'].get('status')})
    if args.action == 'remediation-zip':
        _split_state['result'] = _split_state['remediation_store'].build_zip(args.release_id)
        return (True, {'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}, 'status': _split_state['result'].get('status')})
    if args.action == 'remediation-verify':
        _split_state['report'] = _split_state['remediation_store'].verify_zip(args.release_id, strict=args.strict, require_passed=args.require_passed, require_signed=args.require_signed)
        if args.report_out is not None:
            write_audio_campaign_remediation_verification_report(_split_state['report'], args.report_out)
        return (True, {'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
    if args.action == 'change-request-create':
        cr = _split_state['governance_store'].create_change_request(args.campaign_id, {'created_by': args.created_by, 'reason': args.reason, 'risk': args.risk})
        return (True, {'ok': True, 'change_request': cr, 'summary': {'change_request_id': cr.get('change_request_id')}, 'status': cr.get('status')})
    if args.action == 'change-request-approve':
        cr = _split_state['governance_store'].approve_change_request(args.campaign_id, args.change_request_id, {'approved_by': args.approved_by, 'reason': args.reason})
        return (True, {'ok': True, 'change_request': cr, 'summary': {'change_request_id': cr.get('change_request_id')}, 'status': cr.get('status')})
    if args.action == 'signoff-reset':
        _split_state['result'] = _split_state['governance_store'].reset_signoff(args.campaign_id, args.change_request_id, {'reason': args.reason})
        return (True, {'ok': True, **_split_state['result'], 'summary': {'change_request_id': _split_state['result'].get('change_request', {}).get('change_request_id')}, 'status': _split_state['result'].get('status')})
    raise ValueError('Unsupported audio-campaign command.')
    return (False, None)

def _run_audio_campaign_command(args: argparse.Namespace) -> ImplementationDocument:
    _split_state: ImplementationDocument = {}
    _split_result = _run_audio_campaign_command_part_01(args, _split_state)
    if _split_result[0]:
        return _split_result[1]
    _split_result = _run_audio_campaign_command_part_02(args, _split_state)
    if _split_result[0]:
        return _split_result[1]
    raise RuntimeError("_run_audio_campaign_command did not produce a result.")

def _run_release_audio_certification_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass

    store = ReleaseAudioCertificationStore()
    if args.action == "refresh":
        report = store.refresh_report(args.release_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "status":
        report = store.read_report(args.release_id, default={})
        matrix = store.read_matrix(args.release_id, default={})
        evidence = store.read_evidence_index(args.release_id, default={})
        blockers = store.read_blocker_register(args.release_id, default={})
        return {"ok": report.get("status") == "passed", "report": report, "matrix": matrix, "evidence_index": evidence, "blocker_register": blockers, "summary": report.get("summary", {}), "status": report.get("status") or "missing"}
    if args.action == "signoff":
        result = store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_package(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.release_id,
            strict=args.strict,
            require_passed=args.require_passed,
            require_signed=args.require_signed,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_remediation_when_needed=args.require_remediation_when_needed,
        )
        if args.report_out is not None:
            write_release_audio_certification_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-certification command.")

def _run_release_audio_timeline_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass

    store = ReleaseAudioTimelineStore()
    if args.action == "refresh":
        result = store.refresh_timeline(args.release_id, force_new=bool(args.force_new))
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "status":
        timeline_id = args.timeline_id or None
        report = store.read_timeline(args.release_id, timeline_id)
        signoff = read_json(store.signoff_path(args.release_id, timeline_id)) if store.signoff_path(args.release_id, timeline_id).exists() else {}
        return {"ok": report.get("status") == "passed", "timeline_id": report.get("timeline_id"), "report": report, "signoff": signoff, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "events":
        result = store.read_events(args.release_id, args.timeline_id or None)
        return {"ok": True, **result, "summary": {"event_count": len(result.get("events") or [])}, "status": "passed"}
    if args.action == "signoff":
        result = store.signoff_timeline(args.release_id, args.timeline_id or None, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_timeline(args.release_id, args.timeline_id or None)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id, args.timeline_id or None)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.release_id,
            args.timeline_id or None,
            strict=args.strict,
            require_passed=args.require_passed,
            require_signed=args.require_signed,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_current_certification=args.require_current_certification,
        )
        if args.report_out is not None:
            write_release_audio_timeline_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-timeline command.")

__all__ = ('_run_audio_fix_sprint_command', '_run_audio_campaign_command', '_run_release_audio_certification_command', '_run_release_audio_timeline_command')
