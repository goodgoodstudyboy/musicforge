from __future__ import annotations

from .dependencies import *

from .part_001 import build_release_portfolio_governance_evidence_vault_parser, build_release_portfolio_governance_final_board_parser, build_release_portfolio_governance_reviewer_pack_parser

from .part_006 import print_release_portfolio_governance_evidence_vault_result, print_release_portfolio_governance_final_board_result, print_release_portfolio_governance_reviewer_pack_result

def _execute_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-reviewer-pack', *argv]
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
    pass
    pass
    pass
    pass
    parser = build_release_portfolio_governance_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=signoff_store)
    store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=audit_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    if args.refresh:
        report = store.refresh(portfolio_id)
        result.update({"report": report, "summary": portfolio_governance_reviewer_pack_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_reviewer_pack_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    result.update({"retrospective": store.read_retrospective(portfolio_id, default={}), "evidence_index": store.read_evidence_index(portfolio_id, default={}), "timeline": store.read_timeline(portfolio_id, default={})})
    if args.export:
        manifest = store.export_pack(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_reviewer_pack(
            store.zip_path(portfolio_id),
            strict=args.strict,
            require_audit=args.require_audit,
            require_signed=args.require_signed,
            require_archives=args.require_archives,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
        )
        write_release_portfolio_governance_reviewer_pack_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_reviewer_pack_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_reviewer_pack_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    _execute_release_portfolio_governance_reviewer_pack(argv)

def _execute_release_portfolio_governance_final_board(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-final-board', *argv]
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
    pass
    pass
    pass
    pass
    pass
    parser = build_release_portfolio_governance_final_board_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    if args.import_reviewer_response is not None:
        response_payload = read_json(args.import_reviewer_response)
        response = store.import_reviewer_response(portfolio_id, response_payload)
        result.update({"reviewer_response": response})
    refresh_payload = {"require_reviewer_response": args.require_reviewer_response, "require_no_force": args.require_no_force}
    if args.refresh or args.import_reviewer_response is not None:
        report = store.refresh_report(portfolio_id, refresh_payload)
        result.update({"report": report, "summary": portfolio_governance_final_board_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_final_board_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.create_change_request:
        change = store.create_change_request(portfolio_id, {"reason": args.reason or "Final Board archive change requested."})
        result.update({"change_request": change})
    if args.approve_change_request:
        change = store.update_change_request_status(portfolio_id, args.approve_change_request, "approve", {"approved_by": args.approved_by or args.signed_by or "local-user"})
        result.update({"change_request": change})
    if args.reject_change_request:
        change = store.update_change_request_status(portfolio_id, args.reject_change_request, "reject", {"reason": args.reason or "Final Board change rejected."})
        result.update({"change_request": change})
    if args.reset_signoff:
        reset = store.reset_signoff(portfolio_id, {"reason": args.reason or "Final Board signoff reset requested.", "change_request_id": args.change_request_id, "reset_by": args.signed_by or "local-user"})
        result.update({"signoff": reset, "signoff_summary": store.signoff_summary(portfolio_id, signoff=reset)})
    if args.sign or args.force_sign:
        signoff = store.signoff(
            portfolio_id,
            {
                "signed_by": args.signed_by or "local-user",
                "role": args.role,
                "reason": args.reason,
                "force": bool(args.force_sign),
                "allow_warning_signoff": bool(args.allow_warning_signoff),
                "override_reason": args.override_reason,
            },
        )
        result.update({"signoff": signoff, "signoff_summary": store.signoff_summary(portfolio_id, signoff=signoff)})
    if args.export:
        manifest = store.export_archive(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_archive_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_final_board_package(
            store.archive_zip_path(portfolio_id),
            strict=args.strict,
            require_signed=args.require_signed,
            require_reviewer_pack=args.require_reviewer_pack,
            require_audit=args.require_audit,
            require_archives=args.require_archives,
            require_reviewer_response=args.require_reviewer_response,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
        )
        write_release_portfolio_governance_final_board_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_final_board_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_final_board_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_final_board(argv: list[str]) -> None:
    _execute_release_portfolio_governance_final_board(argv)

def _execute_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-evidence-vault', *argv]
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
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_release_portfolio_governance_evidence_vault_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    refresh_payload = {
        "require_final_board": True,
        "require_reviewer_pack": True,
        "require_audit": True,
        "require_archives": True,
        "require_queue_packages": args.require_queue_packages,
    }
    if args.refresh:
        report = store.refresh_report(portfolio_id, refresh_payload)
        result.update({"report": report, "summary": portfolio_governance_evidence_vault_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_evidence_vault_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    result.update({"package_index": store.read_package_index(portfolio_id, default={}), "verification_index": store.read_verification_index(portfolio_id, default={}), "chain_of_custody": store.read_chain_of_custody(portfolio_id, default={})})
    if args.export:
        manifest = store.export_vault(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_evidence_vault_package(
            store.zip_path(portfolio_id),
            strict=args.strict,
            deep=args.deep,
            require_final_board=args.require_final_board,
            require_reviewer_pack=args.require_reviewer_pack,
            require_audit=args.require_audit,
            require_archives=args.require_archives,
            require_queue_packages=args.require_queue_packages,
        )
        write_release_portfolio_governance_evidence_vault_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_evidence_vault_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_evidence_vault_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    _execute_release_portfolio_governance_evidence_vault(argv)

__all__ = ('_execute_release_portfolio_governance_reviewer_pack', 'handle_release_portfolio_governance_reviewer_pack', '_execute_release_portfolio_governance_final_board', 'handle_release_portfolio_governance_final_board', '_execute_release_portfolio_governance_evidence_vault', 'handle_release_portfolio_governance_evidence_vault')
