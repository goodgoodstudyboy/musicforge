from __future__ import annotations

from . import dependencies as _commands_quality_parts_dependencies; AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, Any, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = (_commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.Any, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report)

from .audio_lab_parser_and_adapters import build_verify_unified_command_center_evidence_review_acceptance_parser, build_verify_unified_release_program_continuity_acceptance_change_parser, build_verify_unified_release_program_continuity_acceptance_parser, build_verify_unified_release_program_continuity_command_center_acceptance_change_parser, build_verify_unified_release_program_continuity_command_center_acceptance_parser

from .verify_release_audio_certification import build_verify_release_audio_quality_observatory_parser

from .release_audio_quality_actions import build_verify_release_audio_command_center_parser, build_verify_release_audio_quality_action_queue_parser, build_verify_release_audio_quality_action_queue_signoff_archive_parser

from .release_audio_regression_command import _release_audio_command_center_evidence_from_args

def _execute_verify_release_audio_quality_observatory_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-quality-observatory-package', *argv]
    pass




    parser = build_verify_release_audio_quality_observatory_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_quality_observatory_package(
        args.zip_path,
        strict=args.strict,
        require_current_evidence=args.require_current_evidence,
        evidence_root=args.evidence_root,
        require_no_critical_risk=args.require_no_critical_risk,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_quality_observatory_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Quality Observatory verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_quality_observatory_verification_exit_code(report))

def handle_verify_release_audio_quality_observatory_package(argv: list[str]) -> None:
    _execute_verify_release_audio_quality_observatory_package(argv)

def _execute_verify_release_audio_quality_action_queue_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-quality-action-queue-package', *argv]
    pass




    parser = build_verify_release_audio_quality_action_queue_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_quality_action_queue_package(
        args.zip_path,
        strict=args.strict,
        require_current_observatory=args.require_current_observatory,
        observatory_zip_path=args.observatory_zip,
        observatory_verification_report_path=args.observatory_verification_report,
        evidence_root=args.evidence_root,
        require_no_blocking=not args.allow_blocking,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_quality_action_queue_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Quality Action Queue verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_quality_action_queue_verification_exit_code(report))

def handle_verify_release_audio_quality_action_queue_package(argv: list[str]) -> None:
    _execute_verify_release_audio_quality_action_queue_package(argv)

def _execute_verify_release_audio_quality_action_queue_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-quality-action-queue-signoff-archive-package', *argv]
    pass




    parser = build_verify_release_audio_quality_action_queue_signoff_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_quality_action_queue_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_current_queue=args.require_current_queue,
        require_signed=args.require_signed,
        queue_zip_path=args.queue_zip,
        queue_verification_report_path=args.queue_verification_report,
        observatory_zip_path=args.observatory_zip,
        observatory_verification_report_path=args.observatory_verification_report,
        evidence_root=args.evidence_root,
        require_no_unresolved_manual=not args.allow_unresolved_manual,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_quality_action_queue_signoff_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Quality Action Queue Signoff Archive verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_quality_action_queue_signoff_archive_verification_exit_code(report))

def handle_verify_release_audio_quality_action_queue_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_release_audio_quality_action_queue_signoff_archive_package(argv)

def _execute_verify_release_audio_command_center_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-command-center-package', *argv]
    pass
    pass




    parser = build_verify_release_audio_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    evidence = _release_audio_command_center_evidence_from_args(args)
    report = verify_release_audio_command_center_package(
        args.zip_path,
        strict=args.strict,
        require_ready=args.require_ready,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
        **evidence_to_verifier_kwargs(evidence),
    )
    if args.report_out is not None:
        write_release_audio_command_center_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Command Center verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
        print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_command_center_verification_exit_code(report))

def handle_verify_release_audio_command_center_package(argv: list[str]) -> None:
    _execute_verify_release_audio_command_center_package(argv)

def _execute_verify_unified_command_center_evidence_review_acceptance_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-evidence-review-acceptance-package', *argv]
    pass




    parser = build_verify_unified_command_center_evidence_review_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_evidence_review_acceptance_package(
        args.zip_path,
        strict=args.strict,
        require_accepted=args.require_accepted,
        review_pack_path=args.review_pack,
        review_pack_verification_report_path=args.review_pack_verification_report,
        response_verification_report_path=args.response_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_evidence_review_acceptance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Evidence Review Acceptance verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_evidence_review_acceptance_verification_exit_code(report))

def handle_verify_unified_command_center_evidence_review_acceptance_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_evidence_review_acceptance_package(argv)

def _execute_verify_unified_release_program_continuity_acceptance_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-acceptance-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_acceptance_package(
        args.zip_path,
        strict=args.strict,
        require_current_kit=args.require_current_kit,
        require_signed=args.require_signed,
        require_quorum=args.require_quorum,
        continuity_kit_path=args.continuity_kit,
        continuity_kit_verification_report_path=args.continuity_kit_verification_report,
        signoff_binding_path=args.signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_acceptance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Acceptance verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_acceptance_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_acceptance_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_acceptance_package(argv)

def _execute_verify_unified_release_program_continuity_acceptance_change_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-acceptance-change-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_acceptance_change_package(
        args.zip_path,
        strict=args.strict,
        require_current_acceptance=args.require_current_acceptance,
        acceptance_archive_path=args.acceptance_archive,
        acceptance_verification_report_path=args.acceptance_verification_report,
        acceptance_signoff_binding_path=args.acceptance_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_acceptance_change_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Acceptance Change Control verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_acceptance_change_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_acceptance_change_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_acceptance_change_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_acceptance_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-acceptance-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_command_center_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_acceptance_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        signoff_binding_path=args.signoff_binding,
        review_pack_path=args.review_pack,
        review_pack_verification_report_path=args.review_pack_verification_report,
        accepted_evidence_dir=args.accepted_evidence_dir,
        response_proof_dir=args.response_proof_dir,
        command_center_signoff_archive_path=args.command_center_signoff_archive,
        command_center_signoff_archive_verification_report_path=args.command_center_signoff_archive_verification_report,
        command_center_final_handoff_path=args.command_center_final_handoff,
        command_center_final_handoff_verification_report_path=args.command_center_final_handoff_verification_report,
        command_center_signoff_binding_path=args.command_center_signoff_binding,
        command_center_path=args.command_center,
        command_center_verification_report_path=args.command_center_verification_report,
        command_center_evidence_manifest_path=args.command_center_evidence_manifest,
    )
    if args.report_out:
        write_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Continuity Command Center Receiver Acceptance verification: {report.get('status')}")
    raise SystemExit(verification_exit_code(report))

def handle_verify_unified_release_program_continuity_command_center_acceptance_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_acceptance_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_acceptance_change_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-acceptance-change-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_command_center_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_acceptance_change_package(
        args.zip_path,
        strict=args.strict,
        require_current_acceptance=args.require_current,
        acceptance_archive_path=args.acceptance_archive,
        acceptance_verification_report_path=args.acceptance_verification_report,
        acceptance_signoff_binding_path=args.acceptance_signoff_binding,
        previous_acceptance_root=args.previous_acceptance_root,
        require_reset_proofs=args.require_reset_proofs,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out:
        write_unified_release_program_continuity_command_center_acceptance_change_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Receiver Acceptance Change Control verification: {report.get('status')}")
    raise SystemExit(unified_release_program_continuity_command_center_acceptance_change_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_command_center_acceptance_change_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_acceptance_change_package(argv)

__all__ = ('_execute_verify_release_audio_quality_observatory_package', 'handle_verify_release_audio_quality_observatory_package', '_execute_verify_release_audio_quality_action_queue_package', 'handle_verify_release_audio_quality_action_queue_package', '_execute_verify_release_audio_quality_action_queue_signoff_archive_package', 'handle_verify_release_audio_quality_action_queue_signoff_archive_package', '_execute_verify_release_audio_command_center_package', 'handle_verify_release_audio_command_center_package', '_execute_verify_unified_command_center_evidence_review_acceptance_package', 'handle_verify_unified_command_center_evidence_review_acceptance_package', '_execute_verify_unified_release_program_continuity_acceptance_package', 'handle_verify_unified_release_program_continuity_acceptance_package', '_execute_verify_unified_release_program_continuity_acceptance_change_package', 'handle_verify_unified_release_program_continuity_acceptance_change_package', '_execute_verify_unified_release_program_continuity_command_center_acceptance_package', 'handle_verify_unified_release_program_continuity_command_center_acceptance_package', '_execute_verify_unified_release_program_continuity_command_center_acceptance_change_package', 'handle_verify_unified_release_program_continuity_command_center_acceptance_change_package')
