from __future__ import annotations

from .dependencies import *

from .part_003 import _warn_legacy_ga_flags, build_release_check_parser, build_verify_ga_readiness_parser

def _execute_verify_ga_readiness_report(argv: list[str]) -> None:
    raw_args = ['verify-ga-readiness-report', *argv]
    pass
    parser = build_verify_ga_readiness_parser()
    args = parser.parse_args(raw_args[1:])
    _warn_legacy_ga_flags(argv)
    report = verify_ga_readiness_report(
        args.report_path,
        policy=args.policy,
        evidence_manifest_path=args.evidence_manifest,
        strict=args.strict,
        require_ready=args.require_ready,
        require_manual_acceptance=args.require_manual_acceptance,
        require_audio_campaign=args.require_audio_campaign,
        require_audio_campaign_remediation=args.require_audio_campaign_remediation,
        require_release_audio_certification=args.require_release_audio_certification,
        require_release_audio_timeline=args.require_release_audio_timeline,
        require_release_audio_regression_guard=args.require_release_audio_regression_guard,
        require_final_readiness=args.require_final_readiness,
        manual_acceptance_report_path=args.manual_acceptance_report,
        audio_campaign_archive_path=args.audio_campaign_archive,
        audio_campaign_archive_verification_report_path=args.audio_campaign_archive_verification_report,
        audio_campaign_remediation_path=args.audio_campaign_remediation,
        audio_campaign_remediation_verification_report_path=args.audio_campaign_remediation_verification_report,
        release_audio_certification_path=args.release_audio_timeline_certification or args.release_audio_certification,
        release_audio_certification_verification_report_path=args.release_audio_timeline_certification_verification_report or args.release_audio_certification_verification_report,
        release_audio_timeline_path=args.release_audio_timeline,
        release_audio_timeline_verification_report_path=args.release_audio_timeline_verification_report,
        release_audio_regression_path=args.release_audio_regression,
        release_audio_regression_verification_report_path=args.release_audio_regression_verification_report,
        release_audio_regression_baseline_timeline_path=args.release_audio_regression_baseline_timeline,
        release_audio_regression_baseline_timeline_verification_report_path=args.release_audio_regression_baseline_timeline_verification_report,
        release_audio_regression_baseline_certification_path=args.release_audio_regression_baseline_certification,
        release_audio_regression_baseline_certification_verification_report_path=args.release_audio_regression_baseline_certification_verification_report,
        release_audio_regression_current_timeline_path=args.release_audio_regression_current_timeline or args.release_audio_timeline,
        release_audio_regression_current_timeline_verification_report_path=args.release_audio_regression_current_timeline_verification_report or args.release_audio_timeline_verification_report,
        release_audio_regression_current_certification_path=args.release_audio_regression_current_certification or args.release_audio_timeline_certification or args.release_audio_certification,
        release_audio_regression_current_certification_verification_report_path=args.release_audio_regression_current_certification_verification_report or args.release_audio_timeline_certification_verification_report or args.release_audio_certification_verification_report,
        require_release_audio_baseline_governance=args.require_release_audio_baseline_governance,
        release_audio_baseline_registry_path=args.release_audio_baseline_registry,
        release_audio_baseline_registry_verification_report_path=args.release_audio_baseline_registry_verification_report,
        require_release_audio_regression_response=args.require_release_audio_regression_response,
        release_audio_regression_response_path=args.release_audio_regression_response,
        release_audio_regression_response_verification_report_path=args.release_audio_regression_response_verification_report,
        require_release_audio_quality_observatory=args.require_release_audio_quality_observatory,
        release_audio_quality_observatory_path=args.release_audio_quality_observatory,
        release_audio_quality_observatory_verification_report_path=args.release_audio_quality_observatory_verification_report,
        release_audio_quality_observatory_evidence_root=args.release_audio_quality_observatory_evidence_root,
        require_no_critical_audio_quality_risk=args.require_no_critical_audio_quality_risk,
        require_release_audio_quality_action_queue=args.require_release_audio_quality_action_queue,
        release_audio_quality_action_queue_path=args.release_audio_quality_action_queue,
        release_audio_quality_action_queue_verification_report_path=args.release_audio_quality_action_queue_verification_report,
        require_release_audio_quality_action_queue_signoff=args.require_release_audio_quality_action_queue_signoff,
        release_audio_quality_action_queue_signoff_archive_path=args.release_audio_quality_action_queue_signoff_archive,
        release_audio_quality_action_queue_signoff_verification_report_path=args.release_audio_quality_action_queue_signoff_verification_report,
        require_release_audio_command_center=args.require_release_audio_command_center,
        release_audio_command_center_path=args.release_audio_command_center,
        release_audio_command_center_verification_report_path=args.release_audio_command_center_verification_report,
        require_unified_command_center=args.require_unified_command_center,
        unified_command_center_path=args.unified_command_center,
        unified_command_center_verification_report_path=args.unified_command_center_verification_report,
        require_unified_command_center_archive=args.require_unified_command_center_archive,
        unified_command_center_archive_path=args.unified_command_center_archive,
        unified_command_center_archive_verification_report_path=args.unified_command_center_archive_verification_report,
        require_unified_command_center_handoff=args.require_unified_command_center_handoff,
        unified_command_center_handoff_path=args.unified_command_center_handoff,
        unified_command_center_handoff_verification_report_path=args.unified_command_center_handoff_verification_report,
        require_unified_command_center_continuous_review=args.require_unified_command_center_continuous_review,
        unified_command_center_continuous_review_path=args.unified_command_center_continuous_review,
        unified_command_center_continuous_review_verification_report_path=args.unified_command_center_continuous_review_verification_report,
        require_unified_command_center_drift_response=args.require_unified_command_center_drift_response,
        unified_command_center_drift_response_path=args.unified_command_center_drift_response,
        unified_command_center_drift_response_verification_report_path=args.unified_command_center_drift_response_verification_report,
        unified_command_center_drift_source_review_path=args.unified_command_center_drift_source_review,
        unified_command_center_drift_source_review_verification_report_path=args.unified_command_center_drift_source_review_verification_report,
        unified_command_center_drift_recheck_review_path=args.unified_command_center_drift_recheck_review,
        unified_command_center_drift_recheck_review_verification_report_path=args.unified_command_center_drift_recheck_review_verification_report,
        unified_command_center_drift_change_request_binding_report_path=args.unified_command_center_drift_change_request_binding_report,
        require_unified_command_center_evidence_review=args.require_unified_command_center_evidence_review,
        unified_command_center_evidence_review_path=args.unified_command_center_evidence_review,
        unified_command_center_evidence_review_verification_report_path=args.unified_command_center_evidence_review_verification_report,
        require_unified_command_center_evidence_review_accepted=args.require_unified_command_center_evidence_review_accepted,
        unified_command_center_evidence_review_acceptance_path=args.unified_command_center_evidence_review_acceptance,
        unified_command_center_evidence_review_acceptance_verification_report_path=args.unified_command_center_evidence_review_acceptance_verification_report,
        unified_command_center_evidence_review_acceptance_response_verification_report_path=args.unified_command_center_evidence_review_acceptance_response_verification_report,
        require_unified_command_center_reviewer_decision_board=args.require_unified_command_center_reviewer_decision_board,
        unified_command_center_reviewer_decision_board_path=args.unified_command_center_reviewer_decision_board,
        unified_command_center_reviewer_decision_board_verification_report_path=args.unified_command_center_reviewer_decision_board_verification_report,
        require_unified_command_center_reviewer_decision_board_signed=args.require_unified_command_center_reviewer_decision_board_signed,
        require_unified_command_center_reviewer_decision_board_quorum=args.require_unified_command_center_reviewer_decision_board_quorum,
        unified_command_center_reviewer_decision_board_evidence_review_path=args.unified_command_center_reviewer_decision_board_evidence_review,
        unified_command_center_reviewer_decision_board_evidence_review_verification_report_path=args.unified_command_center_reviewer_decision_board_evidence_review_verification_report,
        unified_command_center_reviewer_decision_board_accepted_evidence_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence,
        unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence_verification_report,
        unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report,
        require_unified_release_program_handoff=args.require_unified_release_program_handoff,
        unified_release_program_handoff_path=args.unified_release_program_handoff,
        unified_release_program_handoff_verification_report_path=args.unified_release_program_handoff_verification_report,
        unified_release_program_handoff_external_evidence_manifest_path=args.unified_release_program_handoff_external_evidence_manifest,
        unified_release_program_handoff_signoff_binding_path=args.unified_release_program_handoff_signoff_binding,
        require_unified_release_program_vault=args.require_unified_release_program_vault,
        unified_release_program_vault_path=args.unified_release_program_vault,
        unified_release_program_vault_verification_report_path=args.unified_release_program_vault_verification_report,
        unified_release_program_vault_anchor_path=args.unified_release_program_vault_anchor,
        require_unified_release_program_vault_operations=args.require_unified_release_program_vault_operations,
        unified_release_program_vault_operations_path=args.unified_release_program_vault_operations,
        unified_release_program_vault_operations_verification_report_path=args.unified_release_program_vault_operations_verification_report,
        unified_release_program_vault_operations_signoff_binding_path=args.unified_release_program_vault_operations_signoff_binding,
        require_unified_release_program_continuity=args.require_unified_release_program_continuity,
        unified_release_program_continuity_path=args.unified_release_program_continuity,
        unified_release_program_continuity_verification_report_path=args.unified_release_program_continuity_verification_report,
        unified_release_program_continuity_signoff_binding_path=args.unified_release_program_continuity_signoff_binding,
        require_unified_release_program_continuity_kit=args.require_unified_release_program_continuity_kit,
        unified_release_program_continuity_kit_path=args.unified_release_program_continuity_kit,
        unified_release_program_continuity_kit_verification_report_path=args.unified_release_program_continuity_kit_verification_report,
        unified_release_program_continuity_kit_receiver_receipt_path=args.unified_release_program_continuity_kit_receiver_receipt,
        require_unified_release_program_continuity_acceptance=args.require_unified_release_program_continuity_acceptance,
        unified_release_program_continuity_acceptance_path=args.unified_release_program_continuity_acceptance,
        unified_release_program_continuity_acceptance_verification_report_path=args.unified_release_program_continuity_acceptance_verification_report,
        unified_release_program_continuity_acceptance_signoff_binding_path=args.unified_release_program_continuity_acceptance_signoff_binding,
        require_unified_release_program_continuity_command_center=args.require_unified_release_program_continuity_command_center,
        unified_release_program_continuity_command_center_path=args.unified_release_program_continuity_command_center,
        unified_release_program_continuity_command_center_verification_report_path=args.unified_release_program_continuity_command_center_verification_report,
        unified_release_program_continuity_command_center_external_evidence_manifest_path=args.unified_release_program_continuity_command_center_external_evidence_manifest,
        require_unified_release_program_continuity_command_center_signoff=args.require_unified_release_program_continuity_command_center_signoff,
        unified_release_program_continuity_command_center_signoff_archive_path=args.unified_release_program_continuity_command_center_signoff_archive,
        unified_release_program_continuity_command_center_signoff_verification_report_path=args.unified_release_program_continuity_command_center_signoff_verification_report,
        unified_release_program_continuity_command_center_signoff_binding_path=args.unified_release_program_continuity_command_center_signoff_binding,
        require_unified_release_program_continuity_command_center_acceptance=args.require_unified_release_program_continuity_command_center_acceptance,
        unified_release_program_continuity_command_center_acceptance_path=args.unified_release_program_continuity_command_center_acceptance_archive,
        unified_release_program_continuity_command_center_acceptance_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_verification_report,
        unified_release_program_continuity_command_center_acceptance_signoff_binding_path=args.unified_release_program_continuity_command_center_acceptance_signoff_binding,
        unified_release_program_continuity_command_center_acceptance_review_pack_path=args.unified_release_program_continuity_command_center_acceptance_review_pack,
        unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_review_pack_verification_report,
        unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir=args.unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir,
        unified_release_program_continuity_command_center_acceptance_response_proof_dir=args.unified_release_program_continuity_command_center_acceptance_response_proof_dir,
        require_unified_release_program_continuity_command_center_acceptance_change_control=args.require_unified_release_program_continuity_command_center_acceptance_change_control,
        unified_release_program_continuity_command_center_acceptance_change_path=args.unified_release_program_continuity_command_center_acceptance_change_archive,
        unified_release_program_continuity_command_center_acceptance_change_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_change_verification_report,
        unified_release_program_continuity_command_center_acceptance_previous_root=args.unified_release_program_continuity_command_center_acceptance_previous_root,
        unified_release_program_continuity_command_center_final_handoff_path=args.unified_release_program_continuity_command_center_final_handoff,
        unified_release_program_continuity_command_center_final_handoff_verification_report_path=args.unified_release_program_continuity_command_center_final_handoff_verification_report,
        unified_release_path=args.unified_release_zip,
        unified_release_verification_report_path=args.unified_release_verification_report,
        unified_distribution_paths=args.unified_distribution_zip,
        unified_distribution_verification_report_paths=args.unified_distribution_verification_report,
        unified_submission_paths=args.unified_submission_zip,
        unified_submission_verification_report_paths=args.unified_submission_verification_report,
        unified_release_operations_path=args.unified_release_operations_zip,
        unified_release_operations_verification_report_path=args.unified_release_operations_verification_report,
        unified_trust_operations_hub_path=args.unified_trust_operations_hub,
        unified_trust_operations_hub_verification_report_path=args.unified_trust_operations_hub_verification_report,
        unified_public_trust_center_path=args.unified_public_trust_center,
        unified_public_trust_center_verification_report_path=args.unified_public_trust_center_verification_report,
        unified_maintenance_backup_path=args.unified_maintenance_backup,
        unified_maintenance_backup_verification_report_path=args.unified_maintenance_backup_verification_report,
        final_handoff_package_path=args.final_handoff_package,
        final_handoff_verification_report_path=args.final_handoff_verification_report,
        release_check_latest_report_path=args.release_check_latest_report,
        release_check_ga_report_path=args.release_check_ga_report,
    )
    if args.report_out is not None:
        write_ga_readiness_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge GA readiness verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    if report.get("status") == "failed":
        raise SystemExit(1)
    return

def handle_verify_ga_readiness_report(argv: list[str]) -> None:
    _execute_verify_ga_readiness_report(argv)

def _execute_release_check(argv: list[str]) -> None:
    raw_args = ['release-check', *argv]
    pass
    pass
    parser = build_release_check_parser()
    args = parser.parse_args(raw_args[1:])
    selected = select_check_definitions(
        profile=args.profile,
        groups=args.group,
        since=args.since,
        only=args.only,
        run_tests=not args.skip_tests,
    )
    if args.list:
        rows = release_check_definitions_as_dicts(selected)
        if args.json:
            print(json.dumps({"checks": rows}, ensure_ascii=False, indent=2))
        else:
            for item in rows:
                print(f"{item['check_id']}\t{item['group']}\t{item.get('version') or '-'}\t{item['name']}")
        return
    def _progress(definition: Any) -> None:
        print(f"[release-check] running {definition.check_id} ...", file=sys.stderr, flush=True)
    report = run_release_check_matrix(
        profile=args.profile,
        groups=args.group,
        since=args.since,
        only=args.only,
        run_tests=not args.skip_tests,
        fail_fast=args.fail_fast,
        timeout_seconds=args.timeout_seconds,
        progress=None if args.json else _progress,
    )
    if args.report_out is not None:
        write_json_report(report, args.report_out)
    if args.timing_out is not None:
        write_timing_report(report, args.timing_out)
    if args.json:
        print(json.dumps(report.to_json_report(), ensure_ascii=False, indent=2))
    else:
        print_release_check_report(report)
    if not report.ok:
        raise SystemExit(1)
    return

def handle_release_check(argv: list[str]) -> None:
    _execute_release_check(argv)

__all__ = ('_execute_verify_ga_readiness_report', 'handle_verify_ga_readiness_report', '_execute_release_check', 'handle_release_check')
