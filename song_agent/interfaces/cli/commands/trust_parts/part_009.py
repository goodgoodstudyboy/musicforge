from __future__ import annotations

from .dependencies import *

from .part_003 import build_verify_public_trust_center_acceptance_board_parser, build_verify_public_trust_center_acceptance_board_signoff_archive_parser, build_verify_public_trust_center_distribution_kit_accepted_evidence_parser, build_verify_public_trust_center_distribution_kit_parser, build_verify_public_trust_center_publication_mirror_parser, build_verify_public_trust_center_publication_monitoring_parser, build_verify_public_trust_center_publication_parser, build_verify_trust_operations_hub_parser

def _execute_verify_public_trust_center_distribution_kit_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-distribution-kit-package', *argv]
    pass





    parser = build_verify_public_trust_center_distribution_kit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_distribution_kit_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_current=args.require_current,
        require_delivery_readiness=args.require_delivery_readiness,
        require_anchor_registry_current=args.require_anchor_registry_current,
        require_anchor_published=args.require_anchor_published,
        require_anchor_not_revoked=args.require_anchor_not_revoked,
        require_anchor_transparency_current=args.require_anchor_transparency_current,
        require_anchor_checkpoint=args.require_anchor_checkpoint,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        acceptance_board_signoff_archive_path=args.acceptance_board_signoff_archive,
        acceptance_board_path=args.acceptance_board,
        acceptance_board_verification_report_path=args.acceptance_board_verification_report,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_distribution_kit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_distribution_kit_verification_report(report)
    raise SystemExit(public_trust_center_distribution_kit_verification_exit_code(report))

def handle_verify_public_trust_center_distribution_kit_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_distribution_kit_package(argv)

def _execute_verify_public_trust_center_distribution_kit_accepted_evidence_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-distribution-kit-accepted-evidence-package', *argv]
    pass





    parser = build_verify_public_trust_center_distribution_kit_accepted_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_distribution_kit_accepted_evidence_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        distribution_kit_path=args.distribution_kit,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_distribution_kit_accepted_evidence_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_distribution_kit_accepted_evidence_verification_report(report)
    raise SystemExit(public_trust_center_distribution_kit_accepted_evidence_verification_exit_code(report))

def handle_verify_public_trust_center_distribution_kit_accepted_evidence_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_distribution_kit_accepted_evidence_package(argv)

def _execute_verify_public_trust_center_acceptance_board_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-acceptance-board-package', *argv]
    pass





    parser = build_verify_public_trust_center_acceptance_board_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_acceptance_board_package(
        args.zip_path,
        strict=args.strict,
        require_ready=args.require_ready,
        require_quorum=args.require_quorum,
        require_no_conflicts=args.require_no_conflicts,
        min_accepted_count=args.min_accepted_count,
        min_accepted_organizations=args.min_accepted_organizations,
        required_roles=args.required_roles,
        distribution_kit_path=args.distribution_kit,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_acceptance_board_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_acceptance_board_verification_report(report)
    raise SystemExit(public_trust_center_acceptance_board_verification_exit_code(report))

def handle_verify_public_trust_center_acceptance_board_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_acceptance_board_package(argv)

def _execute_verify_public_trust_center_acceptance_board_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-acceptance-board-signoff-archive-package', *argv]
    pass





    parser = build_verify_public_trust_center_acceptance_board_signoff_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_acceptance_board_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        require_ready=args.require_ready,
        board_zip_path=args.board_zip,
        board_verification_report_path=args.board_verification_report,
        distribution_kit_path=args.distribution_kit,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_acceptance_board_signoff_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_acceptance_board_signoff_archive_verification_report(report)
    raise SystemExit(public_trust_center_acceptance_board_signoff_archive_verification_exit_code(report))

def handle_verify_public_trust_center_acceptance_board_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_acceptance_board_signoff_archive_package(argv)

def _execute_verify_public_trust_center_publication_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-publication-package', *argv]
    pass





    parser = build_verify_public_trust_center_publication_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_publication_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_ready=args.require_ready,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        require_anchor_current=args.require_anchor_current,
        require_no_revoked=args.require_no_revoked,
        publication_channel_state_path=args.publication_channel_state,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_publication_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_publication_verification_report(report)
    raise SystemExit(public_trust_center_publication_verification_exit_code(report))

def handle_verify_public_trust_center_publication_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_publication_package(argv)

def _execute_verify_public_trust_center_publication_mirror(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-publication-mirror', *argv]
    pass





    parser = build_verify_public_trust_center_publication_mirror_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_publication_mirror(
        args.mirror_dir,
        strict=args.strict,
        require_ready=args.require_ready,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        require_anchor_current=args.require_anchor_current,
        require_no_revoked=args.require_no_revoked,
        publication_channel_state_path=args.publication_channel_state,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_publication_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_publication_verification_report(report)
    raise SystemExit(public_trust_center_publication_verification_exit_code(report))

def handle_verify_public_trust_center_publication_mirror(argv: list[str]) -> None:
    _execute_verify_public_trust_center_publication_mirror(argv)

def _execute_verify_public_trust_center_publication_monitoring_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-publication-monitoring-package', *argv]
    pass





    parser = build_verify_public_trust_center_publication_monitoring_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_publication_monitoring_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_no_revoked=args.require_no_revoked,
        require_ready=args.require_ready,
        require_no_drift=args.require_no_drift,
        require_no_open_critical_incidents=args.require_no_open_critical_incidents,
        allow_waived_incidents=args.allow_waived_incidents,
        publication_channel_state_path=args.publication_channel_state,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_publication_monitoring_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_publication_monitoring_verification_report(report)
    raise SystemExit(public_trust_center_publication_monitoring_verification_exit_code(report))

def handle_verify_public_trust_center_publication_monitoring_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_publication_monitoring_package(argv)

def _execute_verify_trust_operations_hub_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-hub-package', *argv]
    pass





    parser = build_verify_trust_operations_hub_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_hub_package(
        args.zip_path,
        strict=args.strict,
        require_ready=args.require_ready,
        require_signed=args.require_signed,
        require_current=args.require_current,
        require_no_critical_blockers=args.require_no_critical_blockers,
        require_publication_monitoring_clean=args.require_publication_monitoring_clean,
        require_delivery_ready=args.require_delivery_ready,
        require_incident_closeout=args.require_incident_closeout,
        require_incident_regression_guards=args.require_incident_regression_guards,
        require_trust_controls=args.require_trust_controls,
        require_trust_control_signoff=args.require_trust_control_signoff,
        require_continuous_assurance=args.require_continuous_assurance,
        publication_channel_state_path=args.publication_channel_state,
        public_trust_center_verification_path=args.public_trust_center_verification,
        publication_monitoring_verification_path=args.publication_monitoring_verification,
        release_verification_paths=args.release_verification,
        distribution_verification_paths=args.distribution_verification,
        submission_verification_paths=args.submission_verification,
        submission_evidence_verification_paths=args.submission_evidence_verification,
        release_operations_verification_paths=args.release_operations_verification,
        hub_signoff_path=args.hub_signoff,
        hub_verification_report_path=args.hub_verification_report,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        incident_knowledge_package_path=args.incident_knowledge_package,
        incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
        trust_control_package_path=args.trust_control_package,
        trust_control_verification_report_path=args.trust_control_verification_report,
        trust_control_signoff_archive_path=args.trust_control_signoff_archive,
        trust_control_signoff_verification_report_path=args.trust_control_signoff_verification_report,
        continuous_assurance_archive_path=args.continuous_assurance_archive,
        continuous_assurance_verification_report_path=args.continuous_assurance_verification_report,
        require_assurance_watch_clear=args.require_assurance_watch_clear,
        assurance_watch_package_path=args.assurance_watch_package,
        assurance_watch_verification_report_path=args.assurance_watch_verification_report,
        require_assurance_watch_signoff=args.require_assurance_watch_signoff,
        assurance_watch_signoff_archive_path=args.assurance_watch_signoff_archive,
        assurance_watch_signoff_verification_report_path=args.assurance_watch_signoff_verification_report,
        require_final_readiness=args.require_final_readiness,
        final_handoff_package_path=args.final_handoff_package,
        final_handoff_verification_report_path=args.final_handoff_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_hub_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_hub_verification_report(report)
    raise SystemExit(trust_operations_hub_verification_exit_code(report))

def handle_verify_trust_operations_hub_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_hub_package(argv)

__all__ = ('_execute_verify_public_trust_center_distribution_kit_package', 'handle_verify_public_trust_center_distribution_kit_package', '_execute_verify_public_trust_center_distribution_kit_accepted_evidence_package', 'handle_verify_public_trust_center_distribution_kit_accepted_evidence_package', '_execute_verify_public_trust_center_acceptance_board_package', 'handle_verify_public_trust_center_acceptance_board_package', '_execute_verify_public_trust_center_acceptance_board_signoff_archive_package', 'handle_verify_public_trust_center_acceptance_board_signoff_archive_package', '_execute_verify_public_trust_center_publication_package', 'handle_verify_public_trust_center_publication_package', '_execute_verify_public_trust_center_publication_mirror', 'handle_verify_public_trust_center_publication_mirror', '_execute_verify_public_trust_center_publication_monitoring_package', 'handle_verify_public_trust_center_publication_monitoring_package', '_execute_verify_trust_operations_hub_package', 'handle_verify_trust_operations_hub_package')
