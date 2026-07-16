from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_delivery_parts_dependencies

from .cross_domain_adapters import build_verify_unified_command_center_release_train_change_control_parser, build_verify_unified_command_center_release_train_handoff_parser, build_verify_unified_command_center_release_train_lifecycle_parser, build_verify_unified_command_center_release_train_parser, build_verify_unified_release_program_parser
Any, AudioEncodingProfileStore, AudioEncodingStore, CommandSpec, DistributionStore, Path, ProjectStore, ProviderConfig, ProviderError, ReleaseOperationsAuditStore, ReleaseOperationsReviewerPackStore, ReleaseOperationsRunbookStore, ReleaseOperationsSignoffStore, ReleaseOperationsStore, ReleaseStore, SongRequest, SubmissionEvidenceStore, SubmissionStore, argparse, audit_summary, build_auth_config, command_center_signoff_verification_exit_code, distribution_verification_exit_code, generate_request, json, load_provider_config, operations_report_summary, operations_signoff_summary, os, print_distribution_verification_report, print_release_operations_archive_verification_report, print_release_operations_audit_verification_report, print_release_operations_reviewer_pack_verification_report, print_release_operations_runbook_verification_report, print_release_operations_verification_report, print_submission_evidence_verification_report, print_submission_verification_report, print_verification_report, provider_configured, read_json, release_operations_archive_verification_exit_code, release_operations_archive_verification_summary, release_operations_audit_verification_exit_code, release_operations_audit_verification_summary, release_operations_reviewer_pack_verification_exit_code, release_operations_reviewer_pack_verification_summary, release_operations_runbook_verification_exit_code, release_operations_runbook_verification_summary, release_operations_verification_exit_code, release_operations_verification_summary, release_verification_exit_code, retrospective_summary, reviewer_pack_summary, runbook_summary, submission_evidence_verification_exit_code, submission_verification_exit_code, sys, test_provider_config, unified_command_center_release_train_change_control_verification_exit_code, unified_command_center_release_train_handoff_verification_exit_code, unified_command_center_release_train_lifecycle_verification_exit_code, unified_command_center_release_train_verification_exit_code, unified_release_program_continuity_command_center_verification_exit_code, unified_release_program_continuity_distribution_verification_exit_code, unified_release_program_continuity_verification_exit_code, unified_release_program_handoff_verification_exit_code, unified_release_program_operations_verification_exit_code, unified_release_program_vault_operations_verification_exit_code, unified_release_program_vault_verification_exit_code, unified_release_program_verification_exit_code, verify_distribution_package, verify_release_operations_archive_package, verify_release_operations_audit_package, verify_release_operations_package, verify_release_operations_reviewer_pack, verify_release_operations_runbook_package, verify_release_zip, verify_submission_evidence_package, verify_submission_package, verify_unified_command_center_release_train_change_control_package, verify_unified_command_center_release_train_handoff_package, verify_unified_command_center_release_train_lifecycle_package, verify_unified_command_center_release_train_package, verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_package, verify_unified_release_program_continuity_command_center_signoff_package, verify_unified_release_program_continuity_distribution_package, verify_unified_release_program_continuity_package, verify_unified_release_program_handoff_package, verify_unified_release_program_operations_package, verify_unified_release_program_package, verify_unified_release_program_vault_operations_package, verify_unified_release_program_vault_package, write_distribution_verification_report, write_interface_document, write_json, write_release_operations_archive_verification_report, write_release_operations_audit_verification_report, write_release_operations_reviewer_pack_verification_report, write_release_operations_runbook_verification_report, write_submission_evidence_verification_report, write_submission_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report, write_verification_report = _commands_delivery_parts_dependencies.Any, _commands_delivery_parts_dependencies.AudioEncodingProfileStore, _commands_delivery_parts_dependencies.AudioEncodingStore, _commands_delivery_parts_dependencies.CommandSpec, _commands_delivery_parts_dependencies.DistributionStore, _commands_delivery_parts_dependencies.Path, _commands_delivery_parts_dependencies.ProjectStore, _commands_delivery_parts_dependencies.ProviderConfig, _commands_delivery_parts_dependencies.ProviderError, _commands_delivery_parts_dependencies.ReleaseOperationsAuditStore, _commands_delivery_parts_dependencies.ReleaseOperationsReviewerPackStore, _commands_delivery_parts_dependencies.ReleaseOperationsRunbookStore, _commands_delivery_parts_dependencies.ReleaseOperationsSignoffStore, _commands_delivery_parts_dependencies.ReleaseOperationsStore, _commands_delivery_parts_dependencies.ReleaseStore, _commands_delivery_parts_dependencies.SongRequest, _commands_delivery_parts_dependencies.SubmissionEvidenceStore, _commands_delivery_parts_dependencies.SubmissionStore, _commands_delivery_parts_dependencies.argparse, _commands_delivery_parts_dependencies.audit_summary, _commands_delivery_parts_dependencies.build_auth_config, _commands_delivery_parts_dependencies.command_center_signoff_verification_exit_code, _commands_delivery_parts_dependencies.distribution_verification_exit_code, _commands_delivery_parts_dependencies.generate_request, _commands_delivery_parts_dependencies.json, _commands_delivery_parts_dependencies.load_provider_config, _commands_delivery_parts_dependencies.operations_report_summary, _commands_delivery_parts_dependencies.operations_signoff_summary, _commands_delivery_parts_dependencies.os, _commands_delivery_parts_dependencies.print_distribution_verification_report, _commands_delivery_parts_dependencies.print_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.print_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.print_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.print_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.print_release_operations_verification_report, _commands_delivery_parts_dependencies.print_submission_evidence_verification_report, _commands_delivery_parts_dependencies.print_submission_verification_report, _commands_delivery_parts_dependencies.print_verification_report, _commands_delivery_parts_dependencies.provider_configured, _commands_delivery_parts_dependencies.read_json, _commands_delivery_parts_dependencies.release_operations_archive_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_archive_verification_summary, _commands_delivery_parts_dependencies.release_operations_audit_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_audit_verification_summary, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_summary, _commands_delivery_parts_dependencies.release_operations_runbook_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_runbook_verification_summary, _commands_delivery_parts_dependencies.release_operations_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_verification_summary, _commands_delivery_parts_dependencies.release_verification_exit_code, _commands_delivery_parts_dependencies.retrospective_summary, _commands_delivery_parts_dependencies.reviewer_pack_summary, _commands_delivery_parts_dependencies.runbook_summary, _commands_delivery_parts_dependencies.submission_evidence_verification_exit_code, _commands_delivery_parts_dependencies.submission_verification_exit_code, _commands_delivery_parts_dependencies.sys, _commands_delivery_parts_dependencies.test_provider_config, _commands_delivery_parts_dependencies.unified_command_center_release_train_change_control_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_lifecycle_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_command_center_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_distribution_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_verification_exit_code, _commands_delivery_parts_dependencies.verify_distribution_package, _commands_delivery_parts_dependencies.verify_release_operations_archive_package, _commands_delivery_parts_dependencies.verify_release_operations_audit_package, _commands_delivery_parts_dependencies.verify_release_operations_package, _commands_delivery_parts_dependencies.verify_release_operations_reviewer_pack, _commands_delivery_parts_dependencies.verify_release_operations_runbook_package, _commands_delivery_parts_dependencies.verify_release_zip, _commands_delivery_parts_dependencies.verify_submission_evidence_package, _commands_delivery_parts_dependencies.verify_submission_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_change_control_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_handoff_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_lifecycle_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_final_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_signoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_distribution_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_package, _commands_delivery_parts_dependencies.verify_unified_release_program_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_package, _commands_delivery_parts_dependencies.write_distribution_verification_report, _commands_delivery_parts_dependencies.write_interface_document, _commands_delivery_parts_dependencies.write_json, _commands_delivery_parts_dependencies.write_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.write_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.write_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.write_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.write_submission_evidence_verification_report, _commands_delivery_parts_dependencies.write_submission_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_final_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_signoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_verification_report, _commands_delivery_parts_dependencies.write_verification_report
def _release_train_handoff_payload_from_args(args: argparse.Namespace) -> ImplementationDocument:
    return {
        "external_evidence_manifest": getattr(args, "external_evidence_manifest", None),
        "train_archive": getattr(args, "train_archive", None),
        "train_archive_verification_report": getattr(args, "train_archive_verification_report", None),
        "train_signoff_binding": getattr(args, "train_signoff_binding", None),
        "change_control_zip": getattr(args, "change_control_zip", None),
        "change_control_verification_report": getattr(args, "change_control_verification_report", None),
        "reset_proofs": [path for path in getattr(args, "reset_proof", []) if path],
        "lifecycle_zip": getattr(args, "lifecycle_zip", None),
        "lifecycle_verification_report": getattr(args, "lifecycle_verification_report", None),
    }

def print_release_operations_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations")
    print(f"release: {result.get('release_id') or report.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or report.get('status') or '-'}")
    print(f"stage: {summary.get('current_stage') or report.get('current_stage') or '-'} -> {report.get('next_stage') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")
    board_summary = result.get("acceptance_board_summary") if isinstance(result.get("acceptance_board_summary"), dict) else {}
    board_verification = result.get("acceptance_board_verification") if isinstance(result.get("acceptance_board_verification"), dict) else {}
    if board_summary:
        print(f"acceptance board: {board_summary.get('readiness') or '-'} / accepted={board_summary.get('accepted_count', 0)}")
    if board_verification:
        print(f"acceptance board verify: {board_verification.get('status')}")
    signoff = result.get("acceptance_board_signoff") if isinstance(result.get("acceptance_board_signoff"), dict) else {}
    archive_verification = result.get("acceptance_board_signoff_archive_verification") if isinstance(result.get("acceptance_board_signoff_archive_verification"), dict) else {}
    if signoff:
        print(f"acceptance board signoff: {signoff.get('status')}")
    if result.get("acceptance_board_signoff_archive_zip"):
        print(f"acceptance board signoff archive zip: {(result.get('acceptance_board_signoff_archive_zip') or {}).get('sha256')}")
    if archive_verification:
        print(f"acceptance board signoff archive verify: {archive_verification.get('status')}")

def print_release_operations_runbook_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    print("MusicForge release-operations-runbook")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"runbook: {summary.get('runbook_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"safe: {summary.get('safe_count', 0)}")
    print(f"manual_required: {summary.get('manual_required_count', 0)}")
    print(f"failed: {summary.get('failed_count', 0)}")
    if manifest:
        print(f"export: {'stale' if manifest.get('stale') else 'current'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_operations_signoff_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    gate = result.get("gate") if isinstance(result.get("gate"), dict) else {}
    print("MusicForge release-operations-signoff")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"integrity: {summary.get('integrity_ok', False)}")
    if gate:
        print(f"gate: {gate.get('status')} signable={gate.get('signable')}")

def print_release_operations_archive_result(result: dict[str, Any]) -> None:
    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-archive")
    print(f"release: {result.get('release_id') or manifest.get('release_id') or '-'}")
    if manifest:
        print(f"archive: {manifest.get('summary', {}).get('status') if isinstance(manifest.get('summary'), dict) else '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_operations_audit_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-audit")
    print(f"release: {result.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_operations_reviewer_pack_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-reviewer-pack")
    print(f"release: {result.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"readiness: {summary.get('readiness') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def _execute_verify_unified_command_center_release_train_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-package', *argv]
    pass




    parser = build_verify_unified_command_center_release_train_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_package(
        args.zip_path,
        strict=args.strict,
        require_go=args.require_go,
        require_signed=args.require_signed,
        external_evidence_manifest_path=args.external_evidence_manifest,
        signoff_binding_path=args.signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_verification_exit_code(report))

def handle_verify_unified_command_center_release_train_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_package(argv)

def _execute_verify_unified_command_center_release_train_change_control_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-change-control-package', *argv]
    pass




    parser = build_verify_unified_command_center_release_train_change_control_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_change_control_package(
        args.zip_path,
        strict=args.strict,
        require_reset_applied=args.require_reset_applied,
        require_current_train=args.require_current_train,
        train_archive_path=args.train_archive,
        train_archive_verification_report_path=args.train_archive_verification_report,
        train_signoff_binding_path=args.train_signoff_binding,
        external_evidence_manifest_path=args.external_evidence_manifest,
        reset_proof_path=args.reset_proof,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_change_control_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train Change Control verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_change_control_verification_exit_code(report))

def handle_verify_unified_command_center_release_train_change_control_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_change_control_package(argv)

def _execute_verify_unified_command_center_release_train_lifecycle_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-lifecycle-package', *argv]
    pass




    parser = build_verify_unified_command_center_release_train_lifecycle_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_lifecycle_package(
        args.zip_path,
        strict=args.strict,
        require_current_train=args.require_current_train,
        require_change_control=args.require_change_control,
        train_archive_path=args.train_archive,
        train_archive_verification_report_path=args.train_archive_verification_report,
        train_signoff_binding_path=args.train_signoff_binding,
        external_evidence_manifest_path=args.external_evidence_manifest,
        change_control_zip_path=args.change_control_zip,
        change_control_verification_report_path=args.change_control_verification_report,
        reset_proof_paths=args.reset_proof,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_lifecycle_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train Lifecycle verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_lifecycle_verification_exit_code(report))

def handle_verify_unified_command_center_release_train_lifecycle_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_lifecycle_package(argv)

def _execute_verify_unified_command_center_release_train_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-handoff-package', *argv]
    pass




    parser = build_verify_unified_command_center_release_train_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_lifecycle=args.require_lifecycle,
        require_signed=args.require_signed,
        require_accepted=args.require_accepted,
        external_evidence_manifest_path=args.external_evidence_manifest,
        train_archive_path=args.train_archive,
        train_archive_verification_report_path=args.train_archive_verification_report,
        train_signoff_binding_path=args.train_signoff_binding,
        change_control_zip_path=args.change_control_zip,
        change_control_verification_report_path=args.change_control_verification_report,
        reset_proof_paths=args.reset_proof,
        lifecycle_zip_path=args.lifecycle_zip,
        lifecycle_verification_report_path=args.lifecycle_verification_report,
        handoff_signoff_binding_path=args.handoff_signoff_binding,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_handoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train Handoff verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_handoff_verification_exit_code(report))

def handle_verify_unified_command_center_release_train_handoff_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_handoff_package(argv)

def _execute_verify_unified_release_program_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-package', *argv]
    pass




    parser = build_verify_unified_release_program_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_signed=args.require_signed,
        external_evidence_manifest_path=args.external_evidence_manifest,
        program_signoff_binding_path=args.program_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_verification_exit_code(report))

def handle_verify_unified_release_program_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_package(argv)

__all__ = ('_release_train_handoff_payload_from_args', 'print_release_operations_result', 'print_release_operations_runbook_result', 'print_release_operations_signoff_result', 'print_release_operations_archive_result', 'print_release_operations_audit_result', 'print_release_operations_reviewer_pack_result', '_execute_verify_unified_command_center_release_train_package', 'handle_verify_unified_command_center_release_train_package', '_execute_verify_unified_command_center_release_train_change_control_package', 'handle_verify_unified_command_center_release_train_change_control_package', '_execute_verify_unified_command_center_release_train_lifecycle_package', 'handle_verify_unified_command_center_release_train_lifecycle_package', '_execute_verify_unified_command_center_release_train_handoff_package', 'handle_verify_unified_command_center_release_train_handoff_package', '_execute_verify_unified_release_program_package', 'handle_verify_unified_release_program_package')
