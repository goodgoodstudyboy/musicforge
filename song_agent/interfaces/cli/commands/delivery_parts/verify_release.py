from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument

from . import dependencies as _commands_delivery_parts_dependencies

from .verify_release_and_adapters import build_release_operations_parser, build_verify_distribution_parser, build_verify_release_operations_archive_parser, build_verify_release_operations_audit_parser, build_verify_release_operations_parser, build_verify_release_operations_reviewer_pack_parser, build_verify_release_operations_runbook_parser, build_verify_release_parser, build_verify_submission_evidence_parser, build_verify_submission_parser

from .release_train_handoff_payload_from_args import print_release_operations_result
Any, AudioEncodingProfileStore, AudioEncodingStore, CommandSpec, DistributionStore, Path, ProjectStore, ProviderConfig, ProviderError, ReleaseOperationsAuditStore, ReleaseOperationsReviewerPackStore, ReleaseOperationsRunbookStore, ReleaseOperationsSignoffStore, ReleaseOperationsStore, ReleaseStore, SongRequest, SubmissionEvidenceStore, SubmissionStore, argparse, audit_summary, build_auth_config, command_center_signoff_verification_exit_code, distribution_verification_exit_code, generate_request, json, load_provider_config, operations_report_summary, operations_signoff_summary, os, print_distribution_verification_report, print_release_operations_archive_verification_report, print_release_operations_audit_verification_report, print_release_operations_reviewer_pack_verification_report, print_release_operations_runbook_verification_report, print_release_operations_verification_report, print_submission_evidence_verification_report, print_submission_verification_report, print_verification_report, provider_configured, read_json, release_operations_archive_verification_exit_code, release_operations_archive_verification_summary, release_operations_audit_verification_exit_code, release_operations_audit_verification_summary, release_operations_reviewer_pack_verification_exit_code, release_operations_reviewer_pack_verification_summary, release_operations_runbook_verification_exit_code, release_operations_runbook_verification_summary, release_operations_verification_exit_code, release_operations_verification_summary, release_verification_exit_code, retrospective_summary, reviewer_pack_summary, runbook_summary, submission_evidence_verification_exit_code, submission_verification_exit_code, sys, test_provider_config, unified_command_center_release_train_change_control_verification_exit_code, unified_command_center_release_train_handoff_verification_exit_code, unified_command_center_release_train_lifecycle_verification_exit_code, unified_command_center_release_train_verification_exit_code, unified_release_program_continuity_command_center_verification_exit_code, unified_release_program_continuity_distribution_verification_exit_code, unified_release_program_continuity_verification_exit_code, unified_release_program_handoff_verification_exit_code, unified_release_program_operations_verification_exit_code, unified_release_program_vault_operations_verification_exit_code, unified_release_program_vault_verification_exit_code, unified_release_program_verification_exit_code, verify_distribution_package, verify_release_operations_archive_package, verify_release_operations_audit_package, verify_release_operations_package, verify_release_operations_reviewer_pack, verify_release_operations_runbook_package, verify_release_zip, verify_submission_evidence_package, verify_submission_package, verify_unified_command_center_release_train_change_control_package, verify_unified_command_center_release_train_handoff_package, verify_unified_command_center_release_train_lifecycle_package, verify_unified_command_center_release_train_package, verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_package, verify_unified_release_program_continuity_command_center_signoff_package, verify_unified_release_program_continuity_distribution_package, verify_unified_release_program_continuity_package, verify_unified_release_program_handoff_package, verify_unified_release_program_operations_package, verify_unified_release_program_package, verify_unified_release_program_vault_operations_package, verify_unified_release_program_vault_package, write_distribution_verification_report, write_interface_document, write_json, write_release_operations_archive_verification_report, write_release_operations_audit_verification_report, write_release_operations_reviewer_pack_verification_report, write_release_operations_runbook_verification_report, write_submission_evidence_verification_report, write_submission_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report, write_verification_report = _commands_delivery_parts_dependencies.Any, _commands_delivery_parts_dependencies.AudioEncodingProfileStore, _commands_delivery_parts_dependencies.AudioEncodingStore, _commands_delivery_parts_dependencies.CommandSpec, _commands_delivery_parts_dependencies.DistributionStore, _commands_delivery_parts_dependencies.Path, _commands_delivery_parts_dependencies.ProjectStore, _commands_delivery_parts_dependencies.ProviderConfig, _commands_delivery_parts_dependencies.ProviderError, _commands_delivery_parts_dependencies.ReleaseOperationsAuditStore, _commands_delivery_parts_dependencies.ReleaseOperationsReviewerPackStore, _commands_delivery_parts_dependencies.ReleaseOperationsRunbookStore, _commands_delivery_parts_dependencies.ReleaseOperationsSignoffStore, _commands_delivery_parts_dependencies.ReleaseOperationsStore, _commands_delivery_parts_dependencies.ReleaseStore, _commands_delivery_parts_dependencies.SongRequest, _commands_delivery_parts_dependencies.SubmissionEvidenceStore, _commands_delivery_parts_dependencies.SubmissionStore, _commands_delivery_parts_dependencies.argparse, _commands_delivery_parts_dependencies.audit_summary, _commands_delivery_parts_dependencies.build_auth_config, _commands_delivery_parts_dependencies.command_center_signoff_verification_exit_code, _commands_delivery_parts_dependencies.distribution_verification_exit_code, _commands_delivery_parts_dependencies.generate_request, _commands_delivery_parts_dependencies.json, _commands_delivery_parts_dependencies.load_provider_config, _commands_delivery_parts_dependencies.operations_report_summary, _commands_delivery_parts_dependencies.operations_signoff_summary, _commands_delivery_parts_dependencies.os, _commands_delivery_parts_dependencies.print_distribution_verification_report, _commands_delivery_parts_dependencies.print_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.print_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.print_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.print_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.print_release_operations_verification_report, _commands_delivery_parts_dependencies.print_submission_evidence_verification_report, _commands_delivery_parts_dependencies.print_submission_verification_report, _commands_delivery_parts_dependencies.print_verification_report, _commands_delivery_parts_dependencies.provider_configured, _commands_delivery_parts_dependencies.read_json, _commands_delivery_parts_dependencies.release_operations_archive_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_archive_verification_summary, _commands_delivery_parts_dependencies.release_operations_audit_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_audit_verification_summary, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_summary, _commands_delivery_parts_dependencies.release_operations_runbook_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_runbook_verification_summary, _commands_delivery_parts_dependencies.release_operations_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_verification_summary, _commands_delivery_parts_dependencies.release_verification_exit_code, _commands_delivery_parts_dependencies.retrospective_summary, _commands_delivery_parts_dependencies.reviewer_pack_summary, _commands_delivery_parts_dependencies.runbook_summary, _commands_delivery_parts_dependencies.submission_evidence_verification_exit_code, _commands_delivery_parts_dependencies.submission_verification_exit_code, _commands_delivery_parts_dependencies.sys, _commands_delivery_parts_dependencies.test_provider_config, _commands_delivery_parts_dependencies.unified_command_center_release_train_change_control_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_lifecycle_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_command_center_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_distribution_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_verification_exit_code, _commands_delivery_parts_dependencies.verify_distribution_package, _commands_delivery_parts_dependencies.verify_release_operations_archive_package, _commands_delivery_parts_dependencies.verify_release_operations_audit_package, _commands_delivery_parts_dependencies.verify_release_operations_package, _commands_delivery_parts_dependencies.verify_release_operations_reviewer_pack, _commands_delivery_parts_dependencies.verify_release_operations_runbook_package, _commands_delivery_parts_dependencies.verify_release_zip, _commands_delivery_parts_dependencies.verify_submission_evidence_package, _commands_delivery_parts_dependencies.verify_submission_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_change_control_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_handoff_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_lifecycle_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_final_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_signoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_distribution_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_package, _commands_delivery_parts_dependencies.verify_unified_release_program_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_package, _commands_delivery_parts_dependencies.write_distribution_verification_report, _commands_delivery_parts_dependencies.write_interface_document, _commands_delivery_parts_dependencies.write_json, _commands_delivery_parts_dependencies.write_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.write_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.write_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.write_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.write_submission_evidence_verification_report, _commands_delivery_parts_dependencies.write_submission_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_final_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_signoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_verification_report, _commands_delivery_parts_dependencies.write_verification_report
def _execute_verify_release(argv: list[str]) -> None:
    raw_args = ['verify-release', *argv]
    pass
    parser = build_verify_release_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_zip(
        args.zip_path,
        strict=args.strict,
        require_audio=args.require_audio,
        require_human_review=args.require_human_review,
        require_audio_revisions=args.require_audio_revisions,
        require_stems=args.require_stems,
        require_mastering=args.require_mastering,
        require_encoded_audio=args.require_encoded_audio,
        require_encoded_audio_review=args.require_encoded_audio_review,
        require_format_decision=args.require_format_decision,
        require_rights_clearance=args.require_rights_clearance,
        required_audio_format_profiles=[item.strip() for item in str(args.require_audio_formats or "").split(",") if item.strip()],
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_verification_report(report)
    raise SystemExit(release_verification_exit_code(report))

def handle_verify_release(argv: list[str]) -> None:
    _execute_verify_release(argv)

def _execute_verify_distribution_package(argv: list[str]) -> None:
    raw_args = ['verify-distribution-package', *argv]
    pass





    parser = build_verify_distribution_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_distribution_package(
        args.zip_path,
        strict=args.strict,
        require_audio=args.require_audio,
        require_artwork=args.require_artwork,
        require_encoded_audio=args.require_encoded_audio,
        require_encoded_audio_review=args.require_encoded_audio_review,
        require_format_decision=args.require_format_decision,
        require_rights_clearance=args.require_rights_clearance,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_distribution_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_distribution_verification_report(report)
    raise SystemExit(distribution_verification_exit_code(report))

def handle_verify_distribution_package(argv: list[str]) -> None:
    _execute_verify_distribution_package(argv)

def _execute_verify_submission_package(argv: list[str]) -> None:
    raw_args = ['verify-submission-package', *argv]
    pass





    parser = build_verify_submission_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_submission_package(
        args.zip_path,
        strict=args.strict,
        require_submitted=args.require_submitted,
        require_accepted=args.require_accepted,
        require_rights_clearance=args.require_rights_clearance,
        deep=args.deep,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_submission_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_submission_verification_report(report)
    raise SystemExit(submission_verification_exit_code(report))

def handle_verify_submission_package(argv: list[str]) -> None:
    _execute_verify_submission_package(argv)

def _execute_verify_submission_evidence_package(argv: list[str]) -> None:
    raw_args = ['verify-submission-evidence-package', *argv]
    pass





    parser = build_verify_submission_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_submission_evidence_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_submitted=args.require_submitted,
        require_accepted=args.require_accepted,
        require_rights_clearance=args.require_rights_clearance,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_submission_evidence_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_submission_evidence_verification_report(report)
    raise SystemExit(submission_evidence_verification_exit_code(report))

def handle_verify_submission_evidence_package(argv: list[str]) -> None:
    _execute_verify_submission_evidence_package(argv)

def _execute_verify_release_operations_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-package', *argv]
    pass




    parser = build_verify_release_operations_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_package(
        args.zip_path,
        strict=args.strict,
        require_accepted=args.require_accepted,
        require_submission_evidence=args.require_submission_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_verification_report(report)
    raise SystemExit(release_operations_verification_exit_code(report))

def handle_verify_release_operations_package(argv: list[str]) -> None:
    _execute_verify_release_operations_package(argv)

def _execute_verify_release_operations_runbook_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-runbook-package', *argv]
    pass





    parser = build_verify_release_operations_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_runbook_package(
        args.zip_path,
        strict=args.strict,
        require_completed=args.require_completed,
        require_current=args.require_current,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_runbook_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_runbook_verification_report(report)
    raise SystemExit(release_operations_runbook_verification_exit_code(report))

def handle_verify_release_operations_runbook_package(argv: list[str]) -> None:
    _execute_verify_release_operations_runbook_package(argv)

def _execute_verify_release_operations_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-archive-package', *argv]
    pass





    parser = build_verify_release_operations_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_archive_verification_report(report)
    raise SystemExit(release_operations_archive_verification_exit_code(report))

def handle_verify_release_operations_archive_package(argv: list[str]) -> None:
    _execute_verify_release_operations_archive_package(argv)

def _execute_verify_release_operations_audit_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-audit-package', *argv]
    pass





    parser = build_verify_release_operations_audit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_audit_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_signed=args.require_signed,
        require_archive=args.require_archive,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_audit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_audit_verification_report(report)
    raise SystemExit(release_operations_audit_verification_exit_code(report))

def handle_verify_release_operations_audit_package(argv: list[str]) -> None:
    _execute_verify_release_operations_audit_package(argv)

def _execute_verify_release_operations_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-reviewer-pack', *argv]
    pass





    parser = build_verify_release_operations_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_reviewer_pack(
        args.zip_path,
        strict=args.strict,
        require_audit=args.require_audit,
        require_signed=args.require_signed,
        require_archive=args.require_archive,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_reviewer_pack_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_reviewer_pack_verification_report(report)
    raise SystemExit(release_operations_reviewer_pack_verification_exit_code(report))

def handle_verify_release_operations_reviewer_pack(argv: list[str]) -> None:
    _execute_verify_release_operations_reviewer_pack(argv)

def _execute_release_operations(argv: list[str]) -> None:
    raw_args = ['release-operations', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_release_operations_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    store = ReleaseOperationsStore(
        release_store=release_store,
        distribution_store=distribution_store,
        submission_store=submission_store,
        submission_evidence_store=SubmissionEvidenceStore(submission_store),
    )
    result: ImplementationDocument = {"ok": True, "release_id": args.release_id}
    if args.refresh:
        report = store.refresh(args.release_id)
        result.update({"report": report, "summary": operations_report_summary(report)})
    else:
        overview = store.overview(args.release_id)
        result.update(overview)
    if args.export:
        manifest = store.export_operations(args.release_id)
        result.update({"manifest": manifest, "export_summary": manifest.get("summary", {})})
    if args.zip:
        zip_info = store.build_zip(args.release_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_operations_package(store.zip_path(args.release_id), require_accepted=args.require_accepted, require_submission_evidence=args.require_submission_evidence)
        result.update({"verification": verification, "verification_summary": release_operations_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_result(result)
    raise SystemExit(0)

def handle_release_operations(argv: list[str]) -> None:
    _execute_release_operations(argv)

__all__ = ('_execute_verify_release', 'handle_verify_release', '_execute_verify_distribution_package', 'handle_verify_distribution_package', '_execute_verify_submission_package', 'handle_verify_submission_package', '_execute_verify_submission_evidence_package', 'handle_verify_submission_evidence_package', '_execute_verify_release_operations_package', 'handle_verify_release_operations_package', '_execute_verify_release_operations_runbook_package', 'handle_verify_release_operations_runbook_package', '_execute_verify_release_operations_archive_package', 'handle_verify_release_operations_archive_package', '_execute_verify_release_operations_audit_package', 'handle_verify_release_operations_audit_package', '_execute_verify_release_operations_reviewer_pack', 'handle_verify_release_operations_reviewer_pack', '_execute_release_operations', 'handle_release_operations')
