from __future__ import annotations

from .dependencies import *

from .part_002 import build_verify_release_portfolio_governance_attestation_accepted_evidence_parser, build_verify_release_portfolio_governance_attestation_portal_parser, build_verify_release_portfolio_governance_attestation_portal_response_parser, build_verify_release_portfolio_governance_attestation_portal_review_pack_parser, build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser, build_verify_release_portfolio_governance_attestation_transparency_parser

from .part_003 import build_verify_public_trust_center_anchor_registry_parser, build_verify_public_trust_center_anchor_transparency_parser, build_verify_public_trust_center_parser

def _execute_verify_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-portal', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_portal_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_portal(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_registry=args.require_registry,
        require_attestation=args.require_attestation,
        require_accepted_evidence=args.require_accepted_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_portal_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_portal_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_portal(argv)

def _execute_verify_release_portfolio_governance_attestation_portal_review_pack(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-portal-review-pack', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_portal_review_pack_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_portal_review_pack(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_portal_review_pack_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_review_pack_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_portal_review_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation_portal_review_pack(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_portal_review_pack(argv)

def _execute_verify_release_portfolio_governance_attestation_portal_response(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-portal-response', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_portal_response_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_portal_response(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_pack=args.require_pack,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_portal_response_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_response_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_portal_review_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation_portal_response(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_portal_response(argv)

def _execute_verify_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-accepted-evidence', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_accepted_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_accepted_evidence(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_accepted_evidence_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_accepted_evidence_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_accepted_evidence_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_accepted_evidence(argv)

def _execute_verify_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-transparency', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_transparency_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_transparency(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_accepted_evidence=args.require_accepted_evidence,
        require_no_revoked_current=args.require_no_revoked_current,
        require_contiguous_chain=args.require_contiguous_chain,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_transparency_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_transparency_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_transparency(argv)

def _execute_verify_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-transparency-acknowledgement', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
        args.zip_path,
        strict=args.strict,
        require_pack=args.require_pack,
        require_response=args.require_response,
        require_accepted=args.require_accepted,
        require_transparency=args.require_transparency,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_transparency_acknowledgement_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_transparency_acknowledgement(argv)

def _execute_verify_public_trust_center_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-package', *argv]
    pass





    parser = build_verify_public_trust_center_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_package(
        args.zip_path,
        strict=args.strict,
        require_release_readiness=args.require_release_readiness,
        require_public_attestation=args.require_public_attestation,
        require_registry_current=args.require_registry_current,
        require_portal_current=args.require_portal_current,
        require_transparency_current=args.require_transparency_current,
        require_acknowledgement_current=args.require_acknowledgement_current,
        require_delivery_readiness=args.require_delivery_readiness,
        require_distribution_ready=args.require_distribution_ready,
        require_submission_accepted=args.require_submission_accepted,
        require_submission_evidence=args.require_submission_evidence,
        require_operations_signed=args.require_operations_signed,
        require_operations_audit=args.require_operations_audit,
        require_operations_reviewer_pack=args.require_operations_reviewer_pack,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        delivery_anchor_path=args.delivery_anchor,
        anchor_registry_path=args.anchor_registry,
        anchor_transparency_path=args.anchor_transparency,
        anchor_checkpoint_path=args.anchor_checkpoint,
        acceptance_board_signoff_archive_path=args.acceptance_board_signoff_archive,
        acceptance_board_path=args.acceptance_board,
        acceptance_board_verification_report_path=args.acceptance_board_verification_report,
        distribution_kit_path=args.distribution_kit,
        accepted_evidence_dir=args.accepted_evidence_dir,
        require_anchor_registry_current=args.require_anchor_registry_current,
        require_anchor_published=args.require_anchor_published,
        require_anchor_not_revoked=args.require_anchor_not_revoked,
        require_anchor_transparency_current=args.require_anchor_transparency_current,
        require_anchor_checkpoint=args.require_anchor_checkpoint,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_verification_report(report)
    raise SystemExit(public_trust_center_verification_exit_code(report))

def handle_verify_public_trust_center_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_package(argv)

def _execute_verify_public_trust_center_anchor_registry_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-anchor-registry-package', *argv]
    pass





    parser = build_verify_public_trust_center_anchor_registry_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_anchor_registry_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_anchor_published=args.require_anchor_published,
        require_anchor_not_revoked=args.require_anchor_not_revoked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_anchor_registry_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_anchor_registry_verification_report(report)
    raise SystemExit(public_trust_center_anchor_registry_verification_exit_code(report))

def handle_verify_public_trust_center_anchor_registry_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_anchor_registry_package(argv)

def _execute_verify_public_trust_center_anchor_transparency_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-anchor-transparency-package', *argv]
    pass





    parser = build_verify_public_trust_center_anchor_transparency_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_anchor_transparency_package(
        args.zip_path,
        strict=args.strict,
        checkpoint_path=args.checkpoint,
        anchor_registry_path=args.anchor_registry,
        require_current_checkpoint=args.require_current_checkpoint,
        require_published_anchor=args.require_published_anchor,
        require_not_revoked=args.require_not_revoked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_anchor_transparency_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_anchor_transparency_verification_report(report)
    raise SystemExit(public_trust_center_anchor_transparency_verification_exit_code(report))

def handle_verify_public_trust_center_anchor_transparency_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_anchor_transparency_package(argv)

__all__ = ('_execute_verify_release_portfolio_governance_attestation_portal', 'handle_verify_release_portfolio_governance_attestation_portal', '_execute_verify_release_portfolio_governance_attestation_portal_review_pack', 'handle_verify_release_portfolio_governance_attestation_portal_review_pack', '_execute_verify_release_portfolio_governance_attestation_portal_response', 'handle_verify_release_portfolio_governance_attestation_portal_response', '_execute_verify_release_portfolio_governance_attestation_accepted_evidence', 'handle_verify_release_portfolio_governance_attestation_accepted_evidence', '_execute_verify_release_portfolio_governance_attestation_transparency', 'handle_verify_release_portfolio_governance_attestation_transparency', '_execute_verify_release_portfolio_governance_attestation_transparency_acknowledgement', 'handle_verify_release_portfolio_governance_attestation_transparency_acknowledgement', '_execute_verify_public_trust_center_package', 'handle_verify_public_trust_center_package', '_execute_verify_public_trust_center_anchor_registry_package', 'handle_verify_public_trust_center_anchor_registry_package', '_execute_verify_public_trust_center_anchor_transparency_package', 'handle_verify_public_trust_center_anchor_transparency_package')
