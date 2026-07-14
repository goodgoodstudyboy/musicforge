from __future__ import annotations

from .dependencies import *

from .part_001 import build_verify_release_portfolio_audit_parser, build_verify_release_portfolio_governance_archive_parser, build_verify_release_portfolio_governance_parser

from .part_002 import build_verify_release_portfolio_governance_attestation_parser, build_verify_release_portfolio_governance_attestation_registry_parser, build_verify_release_portfolio_governance_audit_parser, build_verify_release_portfolio_governance_evidence_vault_parser, build_verify_release_portfolio_governance_final_board_parser, build_verify_release_portfolio_governance_reviewer_pack_parser

from .part_006 import _build_public_trust_center_store

def _build_public_trust_center_publication_store():
    pass
    pass
    pass
    pass
    pass
    pass

    trust_store = _build_public_trust_center_store()
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    distribution_kit_store = PublicTrustCenterDistributionKitStore(
        trust_center_store=trust_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
    )
    acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
    board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=acceptance_store)
    return PublicTrustCenterPublicationStore(
        trust_center_store=trust_store,
        distribution_kit_store=distribution_kit_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
        acceptance_store=acceptance_store,
        acceptance_board_store=board_store,
    )

def _execute_verify_release_portfolio_audit_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-audit-package', *argv]
    pass





    parser = build_verify_release_portfolio_audit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_audit_package(
        args.zip_path,
        strict=args.strict,
        require_reviewer_packs=args.require_reviewer_packs,
        require_audit=args.require_audit,
        require_archive=args.require_archive,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_audit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_audit_verification_report(report)
    raise SystemExit(release_portfolio_audit_verification_exit_code(report))

def handle_verify_release_portfolio_audit_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_audit_package(argv)

def _execute_verify_release_portfolio_governance_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-package', *argv]
    pass





    parser = build_verify_release_portfolio_governance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_package(
        args.zip_path,
        strict=args.strict,
        require_manual_actions=args.require_manual_actions,
        require_no_blocked=args.require_no_blocked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_verification_report(report)
    raise SystemExit(release_portfolio_governance_verification_exit_code(report))

def handle_verify_release_portfolio_governance_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_package(argv)

def _execute_verify_release_portfolio_governance_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-archive-package', *argv]
    pass





    parser = build_verify_release_portfolio_governance_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_no_force=args.require_no_force,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_archive_verification_report(report)
    raise SystemExit(release_portfolio_governance_archive_verification_exit_code(report))

def handle_verify_release_portfolio_governance_archive_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_archive_package(argv)

def _execute_verify_release_portfolio_governance_audit_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-audit-package', *argv]
    pass





    parser = build_verify_release_portfolio_governance_audit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_audit_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_archives=args.require_archives,
        require_no_force=args.require_no_force,
        require_reset_cr_causality=args.require_reset_cr_causality,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_audit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_audit_verification_report(report)
    raise SystemExit(release_portfolio_governance_audit_verification_exit_code(report))

def handle_verify_release_portfolio_governance_audit_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_audit_package(argv)

def _execute_verify_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-reviewer-pack', *argv]
    pass





    parser = build_verify_release_portfolio_governance_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_reviewer_pack(
        args.zip_path,
        strict=args.strict,
        require_audit=args.require_audit,
        require_signed=args.require_signed,
        require_archives=args.require_archives,
        require_no_force=args.require_no_force,
        require_reset_cr_causality=args.require_reset_cr_causality,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_reviewer_pack_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_reviewer_pack_verification_report(report)
    raise SystemExit(release_portfolio_governance_reviewer_pack_verification_exit_code(report))

def handle_verify_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_reviewer_pack(argv)

def _execute_verify_release_portfolio_governance_final_board(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-final-board', *argv]
    pass





    parser = build_verify_release_portfolio_governance_final_board_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_final_board_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_reviewer_pack=args.require_reviewer_pack,
        require_audit=args.require_audit,
        require_archives=args.require_archives,
        require_reviewer_response=args.require_reviewer_response,
        require_no_force=args.require_no_force,
        require_reset_cr_causality=args.require_reset_cr_causality,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_final_board_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_final_board_verification_report(report)
    raise SystemExit(release_portfolio_governance_final_board_verification_exit_code(report))

def handle_verify_release_portfolio_governance_final_board(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_final_board(argv)

def _execute_verify_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-evidence-vault', *argv]
    pass





    parser = build_verify_release_portfolio_governance_evidence_vault_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_evidence_vault_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_final_board=args.require_final_board,
        require_reviewer_pack=args.require_reviewer_pack,
        require_audit=args.require_audit,
        require_archives=args.require_archives,
        require_queue_packages=args.require_queue_packages,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_evidence_vault_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_evidence_vault_verification_report(report)
    raise SystemExit(release_portfolio_governance_evidence_vault_verification_exit_code(report))

def handle_verify_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_evidence_vault(argv)

def _execute_verify_release_portfolio_governance_attestation(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation(
        args.zip_path,
        strict=args.strict,
        require_vault=args.require_vault,
        require_final_board=args.require_final_board,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation(argv)

def _execute_verify_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-registry', *argv]
    pass





    parser = build_verify_release_portfolio_governance_attestation_registry_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_registry(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_published=args.require_published,
        require_no_revoked_current=args.require_no_revoked_current,
        require_accepted_evidence=args.require_accepted_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_registry_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_registry_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_registry_verification_exit_code(report))

def handle_verify_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_registry(argv)

__all__ = ('_build_public_trust_center_publication_store', '_execute_verify_release_portfolio_audit_package', 'handle_verify_release_portfolio_audit_package', '_execute_verify_release_portfolio_governance_package', 'handle_verify_release_portfolio_governance_package', '_execute_verify_release_portfolio_governance_archive_package', 'handle_verify_release_portfolio_governance_archive_package', '_execute_verify_release_portfolio_governance_audit_package', 'handle_verify_release_portfolio_governance_audit_package', '_execute_verify_release_portfolio_governance_reviewer_pack', 'handle_verify_release_portfolio_governance_reviewer_pack', '_execute_verify_release_portfolio_governance_final_board', 'handle_verify_release_portfolio_governance_final_board', '_execute_verify_release_portfolio_governance_evidence_vault', 'handle_verify_release_portfolio_governance_evidence_vault', '_execute_verify_release_portfolio_governance_attestation', 'handle_verify_release_portfolio_governance_attestation', '_execute_verify_release_portfolio_governance_attestation_registry', 'handle_verify_release_portfolio_governance_attestation_registry')
