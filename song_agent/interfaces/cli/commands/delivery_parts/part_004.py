from __future__ import annotations

from .dependencies import *

from .part_001 import build_verify_unified_release_program_continuity_command_center_handoff_parser, build_verify_unified_release_program_continuity_command_center_parser, build_verify_unified_release_program_continuity_command_center_signoff_parser, build_verify_unified_release_program_continuity_distribution_parser, build_verify_unified_release_program_continuity_parser, build_verify_unified_release_program_handoff_parser, build_verify_unified_release_program_operations_parser

from .part_002 import build_verify_unified_release_program_vault_operations_parser, build_verify_unified_release_program_vault_parser

def _execute_verify_unified_release_program_operations_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-operations-package', *argv]
    pass




    parser = build_verify_unified_release_program_operations_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_operations_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_signed_program=args.require_signed_program,
        require_continuous_review_clear=args.require_continuous_review_clear,
        require_lifecycle_audit=args.require_lifecycle_audit,
        program_zip_path=args.program_zip,
        program_verification_report_path=args.program_verification_report,
        program_signoff_binding_path=args.program_signoff_binding,
        external_evidence_manifest_path=args.external_evidence_manifest,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_operations_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Operations verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_operations_verification_exit_code(report))

def handle_verify_unified_release_program_operations_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_operations_package(argv)

def _execute_verify_unified_release_program_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-handoff-package', *argv]
    pass




    parser = build_verify_unified_release_program_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_accepted=args.require_accepted,
        require_signed=args.require_signed,
        external_evidence_manifest_path=args.external_evidence_manifest,
        handoff_signoff_binding_path=args.handoff_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_handoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Handoff verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_handoff_verification_exit_code(report))

def handle_verify_unified_release_program_handoff_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_handoff_package(argv)

def _execute_verify_unified_release_program_vault_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-vault-package', *argv]
    pass




    parser = build_verify_unified_release_program_vault_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_vault_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_anchor=args.require_anchor,
        vault_anchor_path=args.vault_anchor,
        require_current_program=args.require_current_program,
        require_current_operations=args.require_current_operations,
        require_current_handoff=args.require_current_handoff,
        require_accepted_evidence=not args.no_require_accepted_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_vault_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Evidence Vault verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_vault_verification_exit_code(report))

def handle_verify_unified_release_program_vault_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_vault_package(argv)

def _execute_verify_unified_release_program_vault_operations_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-vault-operations-package', *argv]
    pass




    parser = build_verify_unified_release_program_vault_operations_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_vault_operations_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_signed=args.require_signed,
        require_current_vault=args.require_current_vault,
        signoff_binding_path=args.signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_vault_operations_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Vault Operations verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_vault_operations_verification_exit_code(report))

def handle_verify_unified_release_program_vault_operations_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_vault_operations_package(argv)

def _execute_verify_unified_release_program_continuity_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_package(
        args.zip_path,
        strict=args.strict,
        deep_restore=args.deep_restore,
        require_signed=args.require_signed,
        require_current_vault_operations=args.require_current_vault_operations,
        signoff_binding_path=args.signoff_binding,
        vault_operations_archive_path=args.vault_operations_archive,
        vault_operations_verification_report_path=args.vault_operations_verification_report,
        vault_operations_signoff_binding_path=args.vault_operations_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_package(argv)

def _execute_verify_unified_release_program_continuity_kit_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-kit-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_distribution_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_distribution_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_receiver_receipt=args.require_receiver_receipt,
        receiver_receipt_path=args.receiver_receipt,
        kit_verification_report_path=args.verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_distribution_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Distribution Kit verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_distribution_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_kit_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_kit_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_ready=args.require_ready,
        evidence_manifest_path=args.evidence_manifest,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_command_center_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Command Center verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_command_center_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_command_center_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_signoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-signoff-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_command_center_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_signoff_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        signoff_binding_path=args.signoff_binding,
        command_center_zip_path=args.command_center,
        command_center_verification_report_path=args.command_center_verification_report,
        command_center_external_evidence_manifest_path=args.command_center_evidence_manifest,
    )
    if args.report_out:
        write_unified_release_program_continuity_command_center_signoff_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Continuity Command Center Signoff Archive verification: {report.get('status')}")
    raise SystemExit(command_center_signoff_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_command_center_signoff_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_signoff_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-handoff-package', *argv]
    pass




    parser = build_verify_unified_release_program_continuity_command_center_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_final_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_archive=args.require_archive,
        archive_zip_path=args.archive_zip,
        archive_verification_report_path=args.archive_verification_report,
        signoff_binding_path=args.signoff_binding,
        command_center_zip_path=args.command_center,
        command_center_verification_report_path=args.command_center_verification_report,
        command_center_external_evidence_manifest_path=args.command_center_evidence_manifest,
    )
    if args.report_out:
        write_unified_release_program_continuity_command_center_final_handoff_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Continuity Command Center Final Handoff verification: {report.get('status')}")
    raise SystemExit(command_center_signoff_verification_exit_code(report))

def handle_verify_unified_release_program_continuity_command_center_handoff_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_handoff_package(argv)

__all__ = ('_execute_verify_unified_release_program_operations_package', 'handle_verify_unified_release_program_operations_package', '_execute_verify_unified_release_program_handoff_package', 'handle_verify_unified_release_program_handoff_package', '_execute_verify_unified_release_program_vault_package', 'handle_verify_unified_release_program_vault_package', '_execute_verify_unified_release_program_vault_operations_package', 'handle_verify_unified_release_program_vault_operations_package', '_execute_verify_unified_release_program_continuity_package', 'handle_verify_unified_release_program_continuity_package', '_execute_verify_unified_release_program_continuity_kit_package', 'handle_verify_unified_release_program_continuity_kit_package', '_execute_verify_unified_release_program_continuity_command_center_package', 'handle_verify_unified_release_program_continuity_command_center_package', '_execute_verify_unified_release_program_continuity_command_center_signoff_package', 'handle_verify_unified_release_program_continuity_command_center_signoff_package', '_execute_verify_unified_release_program_continuity_command_center_handoff_package', 'handle_verify_unified_release_program_continuity_command_center_handoff_package')
