from __future__ import annotations

from .dependencies import *

from .part_002 import build_verify_unified_command_center_evidence_review_acceptance_parser, build_verify_unified_release_program_continuity_acceptance_change_parser, build_verify_unified_release_program_continuity_acceptance_parser, build_verify_unified_release_program_continuity_command_center_acceptance_change_parser, build_verify_unified_release_program_continuity_command_center_acceptance_parser

from .part_004 import build_verify_release_audio_quality_observatory_parser

from .part_005 import build_verify_release_audio_command_center_parser, build_verify_release_audio_quality_action_queue_parser, build_verify_release_audio_quality_action_queue_signoff_archive_parser

from .part_008 import _release_audio_command_center_evidence_from_args

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
