from __future__ import annotations

from song_agent.interfaces.bootstrap.cli import stores as _quality_stores

from song_agent.platform.contracts.documents import JsonDocument

from . import dependencies as _commands_quality_parts_dependencies

from .audio_fix_sprint import build_verify_audio_campaign_archive_parser, build_verify_audio_campaign_parser, build_verify_audio_campaign_remediation_parser

from .verify_release_audio_certification import build_verify_release_audio_certification_parser, build_verify_release_audio_regression_parser, build_verify_release_audio_timeline_parser

from .release_audio_quality_actions import build_acceptance_check_parser, build_audio_health_parser, build_audio_profile_parser

from .release_audio_command_center_command import print_acceptance_check_report, run_acceptance_check
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def _execute_verify_audio_campaign_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-package', *argv]
    pass
    parser = build_verify_audio_campaign_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_package(
        args.zip_path,
        strict=args.strict,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_fix_sprints_closed=args.require_fix_sprints_closed,
        require_signed=args.require_signed,
        require_no_open_high=args.require_no_open_high,
        require_no_open_critical=args.require_no_open_critical,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_verification_exit_code(report))

def handle_verify_audio_campaign_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_package(argv)

def _execute_verify_audio_campaign_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-archive-package', *argv]
    pass




    parser = build_verify_audio_campaign_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_verification_passed=args.require_verification_passed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign Archive verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_archive_verification_exit_code(report))

def handle_verify_audio_campaign_archive_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_archive_package(argv)

def _execute_verify_audio_campaign_remediation_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-remediation-package', *argv]
    pass




    parser = build_verify_audio_campaign_remediation_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_remediation_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_remediation_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign Remediation verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_remediation_verification_exit_code(report))

def handle_verify_audio_campaign_remediation_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_remediation_package(argv)

def _execute_verify_release_audio_certification_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-certification-package', *argv]
    pass




    parser = build_verify_release_audio_certification_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_certification_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_remediation_when_needed=args.require_remediation_when_needed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_certification_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Certification verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_certification_verification_exit_code(report))

def handle_verify_release_audio_certification_package(argv: list[str]) -> None:
    _execute_verify_release_audio_certification_package(argv)

def _execute_verify_release_audio_timeline_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-timeline-package', *argv]
    pass




    parser = build_verify_release_audio_timeline_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_timeline_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_current_certification=args.require_current_certification,
        release_audio_certification_path=args.release_audio_certification,
        release_audio_certification_verification_report_path=args.release_audio_certification_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_timeline_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Timeline verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_timeline_verification_exit_code(report))

def handle_verify_release_audio_timeline_package(argv: list[str]) -> None:
    _execute_verify_release_audio_timeline_package(argv)

def _execute_verify_release_audio_regression_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-regression-package', *argv]
    pass




    parser = build_verify_release_audio_regression_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_regression_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_current=args.require_current,
        require_baseline_current=args.require_baseline_current,
        baseline_timeline_path=args.baseline_timeline,
        baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
        baseline_certification_path=args.baseline_certification,
        baseline_certification_verification_report_path=args.baseline_certification_verification_report,
        current_timeline_path=args.current_timeline,
        current_timeline_verification_report_path=args.current_timeline_verification_report,
        current_certification_path=args.current_certification,
        current_certification_verification_report_path=args.current_certification_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_regression_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Regression verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_regression_verification_exit_code(report))

def handle_verify_release_audio_regression_package(argv: list[str]) -> None:
    _execute_verify_release_audio_regression_package(argv)

def _execute_acceptance_check(argv: list[str]) -> None:
    raw_args = ['acceptance-check', *argv]
    parser = build_acceptance_check_parser()
    args = parser.parse_args(raw_args[1:])
    report = run_acceptance_check(
        out_dir=args.out,
        profile_id=args.profile,
        cases=args.cases,
        render_audio_mode=args.render_audio,
        auto_review=args.auto_review,
        min_rating=args.min_rating,
        manual_required=args.manual_required,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_acceptance_check_report(report)
    raise SystemExit(0 if report.get("status") in {"passed", "needs_review"} else 1)

def handle_acceptance_check(argv: list[str]) -> None:
    _execute_acceptance_check(argv)

def _execute_audio_health(argv: list[str]) -> None:
    raw_args = ['audio-health', *argv]
    pass
    parser = build_audio_health_parser()
    args = parser.parse_args(raw_args[1:])
    report = analyze_wav_health(
        args.wav_path,
        expected_sample_rate=args.expected_sample_rate,
        expected_channels=args.expected_channels,
        expected_bit_depth=args.expected_bit_depth,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge audio-health\nstatus: {report.get('status')}\nwav_sha256: {report.get('wav_sha256')}")
    raise SystemExit(0 if report.get("status") in {"passed", "warning"} else 1)

def handle_audio_health(argv: list[str]) -> None:
    _execute_audio_health(argv)

def _execute_audio_profile(argv: list[str]) -> None:
    raw_args = ['audio-profile', *argv]
    pass
    parser = build_audio_profile_parser()
    args = parser.parse_args(raw_args[1:])
    store = _quality_stores.audio_profile_store()
    result: JsonDocument
    if args.action == "list":
        result = {"profiles": [profile.public_summary() for profile in store.list_profiles(include_hidden=args.include_hidden)]}
    elif args.action == "create":
        profile = store.upsert_profile(
            {
                "profile_id": args.profile_id,
                "name": args.name,
                "engine": args.engine,
                "engine_path": args.engine_path,
                "soundfont_path": args.soundfont,
                "sample_rate": args.sample_rate,
                "gain": args.gain,
                "is_default": args.default,
            }
        )
        result = {"profile": profile.public_summary()}
    elif args.action == "test":
        result = store.test_profile(args.profile_id)
    elif args.action == "set-default":
        result = {"profile": store.set_default(args.profile_id).public_summary()}
    else:
        result = {}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("status") != "failed" else 1)

def handle_audio_profile(argv: list[str]) -> None:
    _execute_audio_profile(argv)

__all__ = ('_execute_verify_audio_campaign_package', 'handle_verify_audio_campaign_package', '_execute_verify_audio_campaign_archive_package', 'handle_verify_audio_campaign_archive_package', '_execute_verify_audio_campaign_remediation_package', 'handle_verify_audio_campaign_remediation_package', '_execute_verify_release_audio_certification_package', 'handle_verify_release_audio_certification_package', '_execute_verify_release_audio_timeline_package', 'handle_verify_release_audio_timeline_package', '_execute_verify_release_audio_regression_package', 'handle_verify_release_audio_regression_package', '_execute_acceptance_check', 'handle_acceptance_check', '_execute_audio_health', 'handle_audio_health', '_execute_audio_profile', 'handle_audio_profile')
