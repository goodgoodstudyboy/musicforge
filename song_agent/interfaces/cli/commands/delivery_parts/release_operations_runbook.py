from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument

from . import dependencies as _commands_delivery_parts_dependencies

from .verify_release_and_adapters import build_release_encode_parser, build_release_operations_archive_parser, build_release_operations_audit_parser, build_release_operations_reviewer_pack_parser, build_release_operations_runbook_parser, build_release_operations_signoff_parser

from .release_train_handoff_payload_from_args import print_release_operations_archive_result, print_release_operations_audit_result, print_release_operations_reviewer_pack_result, print_release_operations_runbook_result, print_release_operations_signoff_result
Any, AudioEncodingProfileStore, AudioEncodingStore, CommandSpec, DistributionStore, Path, ProjectStore, ProviderConfig, ProviderError, ReleaseOperationsAuditStore, ReleaseOperationsReviewerPackStore, ReleaseOperationsRunbookStore, ReleaseOperationsSignoffStore, ReleaseOperationsStore, ReleaseStore, SongRequest, SubmissionEvidenceStore, SubmissionStore, argparse, audit_summary, build_auth_config, command_center_signoff_verification_exit_code, distribution_verification_exit_code, generate_request, json, load_provider_config, operations_report_summary, operations_signoff_summary, os, print_distribution_verification_report, print_release_operations_archive_verification_report, print_release_operations_audit_verification_report, print_release_operations_reviewer_pack_verification_report, print_release_operations_runbook_verification_report, print_release_operations_verification_report, print_submission_evidence_verification_report, print_submission_verification_report, print_verification_report, provider_configured, read_json, release_operations_archive_verification_exit_code, release_operations_archive_verification_summary, release_operations_audit_verification_exit_code, release_operations_audit_verification_summary, release_operations_reviewer_pack_verification_exit_code, release_operations_reviewer_pack_verification_summary, release_operations_runbook_verification_exit_code, release_operations_runbook_verification_summary, release_operations_verification_exit_code, release_operations_verification_summary, release_verification_exit_code, retrospective_summary, reviewer_pack_summary, runbook_summary, submission_evidence_verification_exit_code, submission_verification_exit_code, sys, test_provider_config, unified_command_center_release_train_change_control_verification_exit_code, unified_command_center_release_train_handoff_verification_exit_code, unified_command_center_release_train_lifecycle_verification_exit_code, unified_command_center_release_train_verification_exit_code, unified_release_program_continuity_command_center_verification_exit_code, unified_release_program_continuity_distribution_verification_exit_code, unified_release_program_continuity_verification_exit_code, unified_release_program_handoff_verification_exit_code, unified_release_program_operations_verification_exit_code, unified_release_program_vault_operations_verification_exit_code, unified_release_program_vault_verification_exit_code, unified_release_program_verification_exit_code, verify_distribution_package, verify_release_operations_archive_package, verify_release_operations_audit_package, verify_release_operations_package, verify_release_operations_reviewer_pack, verify_release_operations_runbook_package, verify_release_zip, verify_submission_evidence_package, verify_submission_package, verify_unified_command_center_release_train_change_control_package, verify_unified_command_center_release_train_handoff_package, verify_unified_command_center_release_train_lifecycle_package, verify_unified_command_center_release_train_package, verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_package, verify_unified_release_program_continuity_command_center_signoff_package, verify_unified_release_program_continuity_distribution_package, verify_unified_release_program_continuity_package, verify_unified_release_program_handoff_package, verify_unified_release_program_operations_package, verify_unified_release_program_package, verify_unified_release_program_vault_operations_package, verify_unified_release_program_vault_package, write_distribution_verification_report, write_interface_document, write_json, write_release_operations_archive_verification_report, write_release_operations_audit_verification_report, write_release_operations_reviewer_pack_verification_report, write_release_operations_runbook_verification_report, write_submission_evidence_verification_report, write_submission_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report, write_verification_report = _commands_delivery_parts_dependencies.Any, _commands_delivery_parts_dependencies.AudioEncodingProfileStore, _commands_delivery_parts_dependencies.AudioEncodingStore, _commands_delivery_parts_dependencies.CommandSpec, _commands_delivery_parts_dependencies.DistributionStore, _commands_delivery_parts_dependencies.Path, _commands_delivery_parts_dependencies.ProjectStore, _commands_delivery_parts_dependencies.ProviderConfig, _commands_delivery_parts_dependencies.ProviderError, _commands_delivery_parts_dependencies.ReleaseOperationsAuditStore, _commands_delivery_parts_dependencies.ReleaseOperationsReviewerPackStore, _commands_delivery_parts_dependencies.ReleaseOperationsRunbookStore, _commands_delivery_parts_dependencies.ReleaseOperationsSignoffStore, _commands_delivery_parts_dependencies.ReleaseOperationsStore, _commands_delivery_parts_dependencies.ReleaseStore, _commands_delivery_parts_dependencies.SongRequest, _commands_delivery_parts_dependencies.SubmissionEvidenceStore, _commands_delivery_parts_dependencies.SubmissionStore, _commands_delivery_parts_dependencies.argparse, _commands_delivery_parts_dependencies.audit_summary, _commands_delivery_parts_dependencies.build_auth_config, _commands_delivery_parts_dependencies.command_center_signoff_verification_exit_code, _commands_delivery_parts_dependencies.distribution_verification_exit_code, _commands_delivery_parts_dependencies.generate_request, _commands_delivery_parts_dependencies.json, _commands_delivery_parts_dependencies.load_provider_config, _commands_delivery_parts_dependencies.operations_report_summary, _commands_delivery_parts_dependencies.operations_signoff_summary, _commands_delivery_parts_dependencies.os, _commands_delivery_parts_dependencies.print_distribution_verification_report, _commands_delivery_parts_dependencies.print_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.print_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.print_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.print_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.print_release_operations_verification_report, _commands_delivery_parts_dependencies.print_submission_evidence_verification_report, _commands_delivery_parts_dependencies.print_submission_verification_report, _commands_delivery_parts_dependencies.print_verification_report, _commands_delivery_parts_dependencies.provider_configured, _commands_delivery_parts_dependencies.read_json, _commands_delivery_parts_dependencies.release_operations_archive_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_archive_verification_summary, _commands_delivery_parts_dependencies.release_operations_audit_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_audit_verification_summary, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_summary, _commands_delivery_parts_dependencies.release_operations_runbook_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_runbook_verification_summary, _commands_delivery_parts_dependencies.release_operations_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_verification_summary, _commands_delivery_parts_dependencies.release_verification_exit_code, _commands_delivery_parts_dependencies.retrospective_summary, _commands_delivery_parts_dependencies.reviewer_pack_summary, _commands_delivery_parts_dependencies.runbook_summary, _commands_delivery_parts_dependencies.submission_evidence_verification_exit_code, _commands_delivery_parts_dependencies.submission_verification_exit_code, _commands_delivery_parts_dependencies.sys, _commands_delivery_parts_dependencies.test_provider_config, _commands_delivery_parts_dependencies.unified_command_center_release_train_change_control_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_lifecycle_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_command_center_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_distribution_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_verification_exit_code, _commands_delivery_parts_dependencies.verify_distribution_package, _commands_delivery_parts_dependencies.verify_release_operations_archive_package, _commands_delivery_parts_dependencies.verify_release_operations_audit_package, _commands_delivery_parts_dependencies.verify_release_operations_package, _commands_delivery_parts_dependencies.verify_release_operations_reviewer_pack, _commands_delivery_parts_dependencies.verify_release_operations_runbook_package, _commands_delivery_parts_dependencies.verify_release_zip, _commands_delivery_parts_dependencies.verify_submission_evidence_package, _commands_delivery_parts_dependencies.verify_submission_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_change_control_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_handoff_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_lifecycle_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_final_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_signoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_distribution_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_package, _commands_delivery_parts_dependencies.verify_unified_release_program_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_package, _commands_delivery_parts_dependencies.write_distribution_verification_report, _commands_delivery_parts_dependencies.write_interface_document, _commands_delivery_parts_dependencies.write_json, _commands_delivery_parts_dependencies.write_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.write_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.write_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.write_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.write_submission_evidence_verification_report, _commands_delivery_parts_dependencies.write_submission_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_final_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_signoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_verification_report, _commands_delivery_parts_dependencies.write_verification_report
def _execute_release_operations_runbook(argv: list[str]) -> None:
    raw_args = ['release-operations-runbook', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_release_operations_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    result: ImplementationDocument = {"ok": True, "release_id": args.release_id}
    if args.list:
        runbooks = store.list_runbooks(args.release_id, include_archived=True)
        result.update({"runbooks": runbooks, "summary": {"count": len(runbooks)}})
    elif args.create:
        runbook = store.create_from_operations_report(args.release_id)
        result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
    else:
        if not args.runbook_id:
            raise ValueError("--runbook-id is required unless --create or --list is used.")
        runbook = store.get_runbook(args.release_id, args.runbook_id)
        result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
        if args.run_safe:
            runbook = store.run_safe_actions(args.release_id, args.runbook_id)
            result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
        if args.refresh_stale:
            stale_result = store.refresh_stale_status(args.release_id, args.runbook_id)
            result.update(stale_result)
            result["summary"] = runbook_summary(stale_result.get("runbook", {}))
        if args.export:
            manifest = store.export_runbook(args.release_id, args.runbook_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(args.release_id, args.runbook_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_operations_runbook_package(store.zip_path(args.release_id, args.runbook_id), require_completed=args.require_completed, require_current=args.require_current)
            result.update({"verification": verification, "verification_summary": release_operations_runbook_verification_summary(verification)})
        if args.archive:
            runbook = store.archive_runbook(args.release_id, args.runbook_id)
            result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_runbook_result(result)
    raise SystemExit(0)

def handle_release_operations_runbook(argv: list[str]) -> None:
    _execute_release_operations_runbook(argv)

def _execute_release_operations_signoff(argv: list[str]) -> None:
    raw_args = ['release-operations-signoff', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_release_operations_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    result: ImplementationDocument = {"ok": True, "release_id": args.release_id}
    if args.reset:
        signoff = store.reset_signoff(args.release_id, {"reason": args.reason, "change_request_id": args.change_request_id})
    elif args.sign:
        signoff = store.signoff(args.release_id, {"signed_by": args.signed_by, "force": args.force, "override_reason": args.override_reason})
    else:
        signoff = store.read_signoff(args.release_id, default={})
        result["gate"] = store.gate(args.release_id, {})
    current_report = operations_store.build_report(args.release_id, persist=False) if signoff else None
    result.update({"signoff": signoff, "summary": operations_signoff_summary(signoff, current_report=current_report)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_signoff_result(result)
    raise SystemExit(0)

def handle_release_operations_signoff(argv: list[str]) -> None:
    _execute_release_operations_signoff(argv)

def _execute_release_operations_archive(argv: list[str]) -> None:
    raw_args = ['release-operations-archive', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_release_operations_archive_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    result: ImplementationDocument = {"ok": True, "release_id": args.release_id}
    if args.export:
        result["manifest"] = store.export_archive(args.release_id)
    if args.zip:
        result["zip"] = store.build_archive_zip(args.release_id)
    if args.verify:
        verification = verify_release_operations_archive_package(store.archive_zip_path(args.release_id), strict=args.strict, require_signed=args.require_signed)
        result.update({"verification": verification, "verification_summary": release_operations_archive_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_archive_result(result)
    raise SystemExit(0)

def handle_release_operations_archive(argv: list[str]) -> None:
    _execute_release_operations_archive(argv)

def _execute_release_operations_audit(argv: list[str]) -> None:
    raw_args = ['release-operations-audit', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_release_operations_audit_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    result: ImplementationDocument = {"ok": True, "release_id": args.release_id}
    if args.refresh:
        report = store.refresh(args.release_id)
        result.update({"report": report, "summary": audit_summary(report)})
    else:
        report = store.read_report(args.release_id, default={})
        result.update({"report": report, "summary": audit_summary(report) if report else {"status": "missing", "entry_count": 0}})
    if args.entries:
        entries = store.entries(args.release_id)
        result.update({"entries": entries, "entry_summary": {"entry_count": len(entries)}})
    if args.graph:
        result["graph"] = store.graph(args.release_id)
    if args.export:
        result["manifest"] = store.export_audit(args.release_id)
    if args.zip:
        result["zip"] = store.build_zip(args.release_id)
    if args.verify:
        verification = verify_release_operations_audit_package(store.zip_path(args.release_id), strict=args.strict, require_current=args.require_current, require_signed=args.require_signed, require_archive=args.require_archive)
        result.update({"verification": verification, "verification_summary": release_operations_audit_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_audit_result(result)
    raise SystemExit(0)

def handle_release_operations_audit(argv: list[str]) -> None:
    _execute_release_operations_audit(argv)

def _execute_release_operations_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['release-operations-reviewer-pack', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_release_operations_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
    result: ImplementationDocument = {"ok": True, "release_id": args.release_id}
    if args.refresh:
        report = store.refresh(args.release_id)
        result.update({"report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(store.read_retrospective(args.release_id, default={}))})
    else:
        report = store.read_report(args.release_id, default={})
        result.update({"report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(store.read_retrospective(args.release_id, default={})) if report else {"status": "missing"}})
    if args.export:
        manifest = store.export_pack(args.release_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(args.release_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_operations_reviewer_pack(store.zip_path(args.release_id), strict=args.strict, require_audit=args.require_audit, require_signed=args.require_signed, require_archive=args.require_archive)
        write_release_operations_reviewer_pack_verification_report(verification, store.verification_report_path(args.release_id))
        result.update({"verification": verification, "verification_summary": release_operations_reviewer_pack_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_reviewer_pack_result(result)
    raise SystemExit(0)

def handle_release_operations_reviewer_pack(argv: list[str]) -> None:
    _execute_release_operations_reviewer_pack(argv)

def _execute_release_encode(argv: list[str]) -> None:
    raw_args = ['release-encode', *argv]
    pass
    pass
    pass
    pass
    parser = build_release_encode_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
    store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
    result = store.render(args.release_id, {"profile_ids": [item.strip() for item in str(args.profiles or "").split(",") if item.strip()], "force": args.force})
    payload = {"ok": True, **result}
    if args.report_out is not None:
        write_interface_document(args.report_out, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload.get("summary", {})
        print(f"MusicForge release-encode\nrelease: {args.release_id}\nstatus: {summary.get('status')}\nprofiles: {summary.get('profile_count', 0)}")
    raise SystemExit(0 if payload.get("summary", {}).get("status") in {"completed", "warning"} else 1)

def handle_release_encode(argv: list[str]) -> None:
    _execute_release_encode(argv)

__all__ = ('_execute_release_operations_runbook', 'handle_release_operations_runbook', '_execute_release_operations_signoff', 'handle_release_operations_signoff', '_execute_release_operations_archive', 'handle_release_operations_archive', '_execute_release_operations_audit', 'handle_release_operations_audit', '_execute_release_operations_reviewer_pack', 'handle_release_operations_reviewer_pack', '_execute_release_encode', 'handle_release_encode')
