from __future__ import annotations

from .dependencies import *

from .part_002 import build_release_operations_parser, build_verify_distribution_parser, build_verify_release_operations_archive_parser, build_verify_release_operations_audit_parser, build_verify_release_operations_parser, build_verify_release_operations_reviewer_pack_parser, build_verify_release_operations_runbook_parser, build_verify_release_parser, build_verify_submission_evidence_parser, build_verify_submission_parser

from .part_003 import print_release_operations_result

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
    result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
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
