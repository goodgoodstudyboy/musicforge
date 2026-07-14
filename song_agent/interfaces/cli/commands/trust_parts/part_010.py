from __future__ import annotations

from .dependencies import *

from .part_003 import build_verify_trust_operations_assurance_watch_parser, build_verify_trust_operations_assurance_watch_signoff_parser, build_verify_trust_operations_final_handoff_parser

from .part_004 import build_verify_trust_operations_assurance_parser, build_verify_trust_operations_control_parser, build_verify_trust_operations_control_signoff_parser, build_verify_trust_operations_hub_incident_parser, build_verify_trust_operations_hub_runbook_parser, build_verify_trust_operations_incident_knowledge_parser

from .part_005 import _trust_operations_assurance_source_payload, _trust_operations_assurance_watch_source_payload, _trust_operations_final_readiness_source_payload

def _execute_verify_trust_operations_assurance_watch_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-assurance-watch-package', *argv]
    pass





    parser = build_verify_trust_operations_assurance_watch_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_assurance_watch_package(
        args.zip_path,
        strict=args.strict,
        require_clear=args.require_clear,
        require_current=args.require_current,
        **_trust_operations_assurance_watch_source_payload(args),
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_assurance_watch_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_assurance_watch_verification_report(report)
    raise SystemExit(trust_operations_assurance_watch_verification_exit_code(report))

def handle_verify_trust_operations_assurance_watch_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_assurance_watch_package(argv)

def _execute_verify_trust_operations_assurance_watch_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-assurance-watch-signoff-archive-package', *argv]
    pass





    parser = build_verify_trust_operations_assurance_watch_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_assurance_watch_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        watch_package_path=args.watch_package,
        watch_verification_report_path=args.watch_verification_report,
        hub_package_path=args.hub_package,
        hub_verification_report_path=args.hub_verification_report,
        continuous_assurance_report_path=args.continuous_assurance_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_assurance_watch_signoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_assurance_watch_signoff_verification_report(report)
    raise SystemExit(trust_operations_assurance_watch_signoff_verification_exit_code(report))

def handle_verify_trust_operations_assurance_watch_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_assurance_watch_signoff_archive_package(argv)

def _execute_verify_trust_operations_final_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-final-handoff-package', *argv]
    pass





    parser = build_verify_trust_operations_final_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_final_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        **_trust_operations_final_readiness_source_payload(args),
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_final_handoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_final_handoff_verification_report(report)
    raise SystemExit(trust_operations_final_handoff_verification_exit_code(report))

def handle_verify_trust_operations_final_handoff_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_final_handoff_package(argv)

def _execute_verify_trust_operations_assurance_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-assurance-package', *argv]
    pass





    parser = build_verify_trust_operations_assurance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_assurance_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_current=args.require_current,
        **_trust_operations_assurance_source_payload(args),
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_assurance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_assurance_verification_report(report)
    raise SystemExit(trust_operations_assurance_verification_exit_code(report))

def handle_verify_trust_operations_assurance_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_assurance_package(argv)

def _execute_verify_trust_operations_control_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-control-package', *argv]
    pass





    parser = build_verify_trust_operations_control_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_control_package(
        args.zip_path,
        strict=args.strict,
        require_policy_passed=args.require_policy_passed,
        hub_package_path=args.hub_package,
        hub_verification_report_path=args.hub_verification_report,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        incident_knowledge_package_path=args.incident_knowledge_package,
        incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_control_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_control_verification_report(report)
    raise SystemExit(trust_operations_control_verification_exit_code(report))

def handle_verify_trust_operations_control_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_control_package(argv)

def _execute_verify_trust_operations_control_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-control-signoff-archive-package', *argv]
    pass





    parser = build_verify_trust_operations_control_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_control_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        control_package_path=args.control_package,
        control_verification_report_path=args.control_verification_report,
        hub_package_path=args.hub_package,
        hub_verification_report_path=args.hub_verification_report,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        incident_knowledge_package_path=args.incident_knowledge_package,
        incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_control_signoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_control_signoff_verification_report(report)
    raise SystemExit(trust_operations_control_signoff_verification_exit_code(report))

def handle_verify_trust_operations_control_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_control_signoff_archive_package(argv)

def _execute_verify_trust_operations_incident_knowledge_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-incident-knowledge-package', *argv]
    pass





    parser = build_verify_trust_operations_incident_knowledge_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_incident_knowledge_package(
        args.zip_path,
        strict=args.strict,
        require_guards_passed=args.require_guards_passed,
        require_no_open_recurrence=args.require_no_open_recurrence,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        hub_verification_report_path=args.hub_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_incident_knowledge_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_incident_knowledge_verification_report(report)
    raise SystemExit(trust_operations_incident_knowledge_verification_exit_code(report))

def handle_verify_trust_operations_incident_knowledge_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_incident_knowledge_package(argv)

def _execute_verify_trust_operations_hub_incident_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-hub-incident-package', *argv]
    pass





    parser = build_verify_trust_operations_hub_incident_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_hub_incident_package(
        args.zip_path,
        strict=args.strict,
        require_no_open_critical=args.require_no_open_critical,
        require_no_open_blocking=args.require_no_open_blocking,
        require_current_hub=args.require_current_hub,
        hub_verification_report_path=args.hub_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_hub_incident_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_hub_incident_verification_report(report)
    raise SystemExit(trust_operations_hub_incident_verification_exit_code(report))

def handle_verify_trust_operations_hub_incident_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_hub_incident_package(argv)

def _execute_verify_trust_operations_hub_runbook_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-hub-runbook-package', *argv]
    pass





    parser = build_verify_trust_operations_hub_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_hub_runbook_package(
        args.zip_path,
        strict=args.strict,
        require_completed=args.require_completed,
        require_no_blocked=args.require_no_blocked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_hub_runbook_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_hub_runbook_verification_report(report)
    raise SystemExit(trust_operations_hub_runbook_verification_exit_code(report))

def handle_verify_trust_operations_hub_runbook_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_hub_runbook_package(argv)

__all__ = ('_execute_verify_trust_operations_assurance_watch_package', 'handle_verify_trust_operations_assurance_watch_package', '_execute_verify_trust_operations_assurance_watch_signoff_archive_package', 'handle_verify_trust_operations_assurance_watch_signoff_archive_package', '_execute_verify_trust_operations_final_handoff_package', 'handle_verify_trust_operations_final_handoff_package', '_execute_verify_trust_operations_assurance_package', 'handle_verify_trust_operations_assurance_package', '_execute_verify_trust_operations_control_package', 'handle_verify_trust_operations_control_package', '_execute_verify_trust_operations_control_signoff_archive_package', 'handle_verify_trust_operations_control_signoff_archive_package', '_execute_verify_trust_operations_incident_knowledge_package', 'handle_verify_trust_operations_incident_knowledge_package', '_execute_verify_trust_operations_hub_incident_package', 'handle_verify_trust_operations_hub_incident_package', '_execute_verify_trust_operations_hub_runbook_package', 'handle_verify_trust_operations_hub_runbook_package')
