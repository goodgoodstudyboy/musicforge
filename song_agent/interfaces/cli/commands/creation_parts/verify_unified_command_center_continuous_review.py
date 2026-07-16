from __future__ import annotations

from . import dependencies as _commands_creation_parts_dependencies

from .program_trust_parser_adapters import build_verify_human_review_pack_parser, build_verify_unified_command_center_continuous_review_parser, build_verify_unified_command_center_drift_response_parser, build_verify_unified_command_center_evidence_review_parser, build_verify_unified_command_center_reviewer_decision_board_parser

from .generation_commands_and_presenter_adapters import build_parser, generate_from_file
Any, CommandSpec, Path, ProviderConfig, ProviderError, SongRequest, argparse, build_auth_config, evidence_to_verifier_kwargs, generate_request, human_review_verification_exit_code, json, load_provider_config, os, print_human_review_verification_report, provider_configured, read_json, sys, test_provider_config, unified_command_center_archive_verification_exit_code, unified_command_center_continuous_review_verification_exit_code, unified_command_center_drift_response_verification_exit_code, unified_command_center_evidence_review_verification_exit_code, unified_command_center_handoff_verification_exit_code, unified_command_center_reviewer_decision_board_verification_exit_code, unified_command_center_verification_exit_code, verify_human_review_pack, verify_unified_command_center_archive_package, verify_unified_command_center_continuous_review_package, verify_unified_command_center_drift_response_package, verify_unified_command_center_evidence_review_package, verify_unified_command_center_handoff_package, verify_unified_command_center_package, verify_unified_command_center_reviewer_decision_board_package, write_human_review_verification_report, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report = _commands_creation_parts_dependencies.Any, _commands_creation_parts_dependencies.CommandSpec, _commands_creation_parts_dependencies.Path, _commands_creation_parts_dependencies.ProviderConfig, _commands_creation_parts_dependencies.ProviderError, _commands_creation_parts_dependencies.SongRequest, _commands_creation_parts_dependencies.argparse, _commands_creation_parts_dependencies.build_auth_config, _commands_creation_parts_dependencies.evidence_to_verifier_kwargs, _commands_creation_parts_dependencies.generate_request, _commands_creation_parts_dependencies.human_review_verification_exit_code, _commands_creation_parts_dependencies.json, _commands_creation_parts_dependencies.load_provider_config, _commands_creation_parts_dependencies.os, _commands_creation_parts_dependencies.print_human_review_verification_report, _commands_creation_parts_dependencies.provider_configured, _commands_creation_parts_dependencies.read_json, _commands_creation_parts_dependencies.sys, _commands_creation_parts_dependencies.test_provider_config, _commands_creation_parts_dependencies.unified_command_center_archive_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_continuous_review_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_drift_response_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_evidence_review_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_handoff_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_reviewer_decision_board_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_verification_exit_code, _commands_creation_parts_dependencies.verify_human_review_pack, _commands_creation_parts_dependencies.verify_unified_command_center_archive_package, _commands_creation_parts_dependencies.verify_unified_command_center_continuous_review_package, _commands_creation_parts_dependencies.verify_unified_command_center_drift_response_package, _commands_creation_parts_dependencies.verify_unified_command_center_evidence_review_package, _commands_creation_parts_dependencies.verify_unified_command_center_handoff_package, _commands_creation_parts_dependencies.verify_unified_command_center_package, _commands_creation_parts_dependencies.verify_unified_command_center_reviewer_decision_board_package, _commands_creation_parts_dependencies.write_human_review_verification_report, _commands_creation_parts_dependencies.write_interface_document, _commands_creation_parts_dependencies.write_json, _commands_creation_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_verification_report
def _execute_verify_unified_command_center_continuous_review_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-continuous-review-package', *argv]
    pass




    parser = build_verify_unified_command_center_continuous_review_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_continuous_review_package(
        args.zip_path,
        strict=args.strict,
        require_clear=args.require_clear,
        require_recovery_drill=args.require_recovery_drill,
        require_current_review=args.require_current_review,
        archive_zip_path=args.archive_zip,
        archive_verification_report_path=args.archive_verification_report,
        handoff_zip_path=args.handoff_zip,
        handoff_verification_report_path=args.handoff_verification_report,
        command_center_zip_path=args.command_center_zip,
        command_center_verification_report_path=args.command_center_verification_report,
        signoff_binding_path=args.signoff_binding,
    )
    if args.report_out is not None:
        write_unified_command_center_continuous_review_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Continuous Review verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_continuous_review_verification_exit_code(report))

def handle_verify_unified_command_center_continuous_review_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_continuous_review_package(argv)

def _execute_verify_unified_command_center_drift_response_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-drift-response-package', *argv]
    pass




    parser = build_verify_unified_command_center_drift_response_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_drift_response_package(
        args.zip_path,
        strict=args.strict,
        require_closed=args.require_closed,
        require_recheck_clear=args.require_recheck_clear,
        require_current_review=args.require_current_review,
        source_review_zip_path=args.source_review_zip,
        source_review_verification_report_path=args.source_review_verification_report,
        recheck_review_zip_path=args.recheck_review_zip,
        recheck_review_verification_report_path=args.recheck_review_verification_report,
        archive_zip_path=args.archive_zip,
        archive_verification_report_path=args.archive_verification_report,
        handoff_zip_path=args.handoff_zip,
        handoff_verification_report_path=args.handoff_verification_report,
        command_center_zip_path=args.command_center_zip,
        command_center_verification_report_path=args.command_center_verification_report,
        signoff_binding_path=args.signoff_binding,
        change_request_binding_report_path=args.change_request_binding_report,
    )
    if args.report_out is not None:
        write_unified_command_center_drift_response_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Drift Response verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_drift_response_verification_exit_code(report))

def handle_verify_unified_command_center_drift_response_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_drift_response_package(argv)

def _execute_verify_unified_command_center_evidence_review_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-evidence-review-package', *argv]
    pass




    parser = build_verify_unified_command_center_evidence_review_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_evidence_review_package(
        args.zip_path,
        strict=args.strict,
        require_replay_passed=args.require_replay_passed,
        ucc_zip_path=args.ucc_zip,
        ucc_verification_report_path=args.ucc_verification_report,
        archive_zip_path=args.archive_zip,
        archive_verification_report_path=args.archive_verification_report,
        handoff_zip_path=args.handoff_zip,
        handoff_verification_report_path=args.handoff_verification_report,
        continuous_review_zip_path=args.continuous_review_zip,
        continuous_review_verification_report_path=args.continuous_review_verification_report,
        source_review_zip_path=args.source_review_zip,
        source_review_verification_report_path=args.source_review_verification_report,
        recheck_review_zip_path=args.recheck_review_zip,
        recheck_review_verification_report_path=args.recheck_review_verification_report,
        drift_response_zip_path=args.drift_response_zip,
        drift_response_verification_report_path=args.drift_response_verification_report,
        drift_change_request_binding_report_path=args.drift_change_request_binding_report,
        signoff_binding_path=args.signoff_binding,
        ga_readiness_report_path=args.ga_readiness_report,
        release_check_report_path=args.release_check_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_evidence_review_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Evidence Review verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_evidence_review_verification_exit_code(report))

def handle_verify_unified_command_center_evidence_review_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_evidence_review_package(argv)

def _execute_verify_unified_command_center_reviewer_decision_board_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-reviewer-decision-board-package', *argv]
    pass




    parser = build_verify_unified_command_center_reviewer_decision_board_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_reviewer_decision_board_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_quorum=args.require_quorum,
        evidence_review_path=args.review_zip,
        evidence_review_verification_report_path=args.review_verification_report,
        accepted_evidence_paths=args.accepted_evidence,
        accepted_evidence_verification_report_paths=args.accepted_evidence_verification_report,
        accepted_evidence_response_verification_report_paths=args.accepted_evidence_response_verification_report,
    )
    if args.report_out is not None:
        write_unified_command_center_reviewer_decision_board_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Reviewer Decision Board verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_reviewer_decision_board_verification_exit_code(report))

def handle_verify_unified_command_center_reviewer_decision_board_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_reviewer_decision_board_package(argv)

def _execute_verify_human_review_pack(argv: list[str]) -> None:
    raw_args = ['verify-human-review-pack', *argv]
    pass





    parser = build_verify_human_review_pack_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_human_review_pack(
        args.zip_path,
        strict=args.strict,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_human_review_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human_review_verification_report(report)
    raise SystemExit(human_review_verification_exit_code(report))

def handle_verify_human_review_pack(argv: list[str]) -> None:
    _execute_verify_human_review_pack(argv)

def handle_default_generate(argv: list[str]) -> None:
    raw_args = list(argv)
    parser = build_parser()
    args = parser.parse_args(raw_args)
    request_path = args.request
    if request_path is None:
        parser.error("the following arguments are required: request")

    generate_from_file(
        request_path,
        out_dir=args.out,
        dry_run=args.dry_run,
        resume=args.resume,
        force=args.force,
        pipeline_mode=args.pipeline_mode,
    )

__all__ = ('_execute_verify_unified_command_center_continuous_review_package', 'handle_verify_unified_command_center_continuous_review_package', '_execute_verify_unified_command_center_drift_response_package', 'handle_verify_unified_command_center_drift_response_package', '_execute_verify_unified_command_center_evidence_review_package', 'handle_verify_unified_command_center_evidence_review_package', '_execute_verify_unified_command_center_reviewer_decision_board_package', 'handle_verify_unified_command_center_reviewer_decision_board_package', '_execute_verify_human_review_pack', 'handle_verify_human_review_pack', 'handle_default_generate')
