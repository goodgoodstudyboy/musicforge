from __future__ import annotations

from .dependencies import *

from .part_001 import build_release_portfolio_audit_parser, build_release_portfolio_governance_audit_parser, build_release_portfolio_governance_queue_parser, build_release_portfolio_governance_signoff_parser

from .part_005 import print_release_portfolio_audit_result, print_release_portfolio_governance_result

from .part_006 import print_release_portfolio_governance_audit_result, print_release_portfolio_governance_signoff_result

def _execute_release_portfolio_audit(argv: list[str]) -> None:
    raw_args = ['release-portfolio-audit', *argv]
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
    parser = build_release_portfolio_audit_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
    store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    result: dict[str, Any] = {"ok": True}
    release_ids = [item.strip() for item in str(args.release_ids or "").split(",") if item.strip()]
    payload = {
        "name": args.name,
        "release_ids": release_ids,
        "include_hidden": args.include_hidden,
        "include_archived": not args.exclude_archived,
        "max_releases": args.max_releases,
        "require_reviewer_packs": args.require_reviewer_packs,
        "require_audit": args.require_audit,
        "require_archive": args.require_archive,
    }
    if args.list:
        portfolios = store.list_portfolios(include_archived=True)
        result.update({"portfolios": portfolios, "summary": {"count": len(portfolios)}})
    else:
        if args.create:
            portfolio = store.create(payload)
            result.update({"portfolio": portfolio, "portfolio_id": portfolio.get("portfolio_id")})
        else:
            if not args.portfolio_id:
                raise ValueError("--portfolio-id is required unless --create or --list is used.")
            portfolio = store.get_portfolio(args.portfolio_id)
            result.update({"portfolio": portfolio, "portfolio_id": args.portfolio_id})
        portfolio_id = str(result.get("portfolio_id") or args.portfolio_id)
        if args.refresh:
            report = store.refresh(portfolio_id, payload)
            summary = portfolio_audit_summary(report)
            summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary["stale"], "trend_report": store.read_trend_report(portfolio_id, default={}), "risk_register": store.read_risk_register(portfolio_id, default={})})
        elif not args.create:
            report = store.read_report(portfolio_id, default={})
            summary = portfolio_audit_summary(report) if report else {"status": "missing"}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        if args.export:
            manifest = store.export_portfolio(portfolio_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_audit_package(store.zip_path(portfolio_id), strict=args.strict, require_reviewer_packs=args.require_reviewer_packs, require_audit=args.require_audit, require_archive=args.require_archive)
            write_release_portfolio_audit_verification_report(verification, store.verification_report_path(portfolio_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_audit_verification_summary(verification)})
        if args.archive:
            portfolio = store.archive(portfolio_id)
            result.update({"portfolio": portfolio})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_audit_result(result)
    raise SystemExit(0)

def handle_release_portfolio_audit(argv: list[str]) -> None:
    _execute_release_portfolio_audit(argv)

def _execute_release_portfolio_governance_queue(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-queue', *argv]
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
    parser = build_release_portfolio_governance_queue_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=audit_store, signoff_store=signoff_store)
    result: dict[str, Any] = {"ok": True}
    if args.list:
        queues = store.list_queues(portfolio_id=args.portfolio_id or None, include_archived=True)
        result.update({"queues": queues, "summary": {"count": len(queues)}})
    else:
        if args.create:
            if not args.portfolio_id:
                raise ValueError("--portfolio-id is required with --create.")
            queue = store.create_from_portfolio(args.portfolio_id, {"name": args.name, "force_new": args.force_new})
            result.update({"queue": queue, "queue_id": queue.get("queue_id"), "summary": queue_summary(queue)})
        else:
            if not args.queue_id:
                raise ValueError("--queue-id is required unless --create or --list is used.")
            queue = store.get_queue(args.queue_id)
            execution = store.read_execution_report(args.queue_id, default={})
            result.update({"queue": queue, "queue_id": args.queue_id, "summary": queue_summary(queue, execution), "execution_report": execution})
        queue_id = str(result.get("queue_id") or args.queue_id)
        if args.run_safe:
            queue = store.run_safe_actions(queue_id, {"refresh_portfolio_after_safe_actions": args.refresh_portfolio_after_safe_actions})
            execution = store.read_execution_report(queue_id, default={})
            result.update({"queue": queue, "execution_report": execution, "summary": queue_summary(queue, execution)})
        if args.export:
            manifest = store.export_queue(queue_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(queue_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_package(store.zip_path(queue_id), strict=args.strict, require_manual_actions=args.require_manual_actions, require_no_blocked=args.require_no_blocked)
            write_release_portfolio_governance_verification_report(verification, store.verification_report_path(queue_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_verification_summary(verification)})
        if args.archive:
            queue = store.archive(queue_id)
            result.update({"queue": queue, "summary": queue_summary(queue)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_queue(argv: list[str]) -> None:
    _execute_release_portfolio_governance_queue(argv)

def _execute_release_portfolio_governance_signoff(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-signoff', *argv]
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
    parser = build_release_portfolio_governance_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=audit_store, signoff_store=operations_signoff_store)
    store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    queue_id = args.queue_id
    result: dict[str, Any] = {"ok": True, "queue_id": queue_id}
    if args.create_change_request:
        change = store.create_change_request(queue_id, {"reason": args.reason, "requested_by": args.signed_by})
        result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
    if args.approve_change_request:
        change = store.update_change_request_status(queue_id, args.approve_change_request, "approve", {"approved_by": args.approved_by})
        result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
    if args.reject_change_request:
        change = store.update_change_request_status(queue_id, args.reject_change_request, "reject", {"reason": args.reason or "Rejected by local reviewer"})
        result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
    if args.reset:
        signoff = store.reset_signoff(queue_id, {"reason": args.reason, "change_request_id": args.change_request_id, "reset_by": args.signed_by})
        result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff)})
    if args.sign:
        manual = governance_store.read_manual_action_list(queue_id, default={})
        acknowledgements = [
            {"item_id": item.get("item_id"), "action_type": item.get("action_type"), "resolution": "accepted_for_followup", "owner": args.signed_by, "due_note": "tracked outside CLI signoff"}
            for item in manual.get("items", [])
            if isinstance(item, dict)
        ]
        signoff = store.signoff(queue_id, {"signed_by": args.signed_by, "force": args.force, "override_reason": args.override_reason, "manual_acknowledgements": acknowledgements})
        result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff)})
    if args.export_archive:
        manifest = store.export_archive(queue_id)
        result.update({"manifest": manifest, "archive_summary": store.archive_summary(queue_id)})
    if args.zip:
        zip_info = store.build_archive_zip(queue_id)
        result.update({"zip": zip_info, "archive_summary": store.archive_summary(queue_id)})
    if args.verify:
        verification = verify_release_portfolio_governance_archive_package(store.archive_zip_path(queue_id), strict=args.strict, require_signed=args.require_signed, require_no_force=args.require_no_force)
        write_release_portfolio_governance_archive_verification_report(verification, store.archive_verification_report_path(queue_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_archive_verification_summary(verification)})
    if "summary" not in result:
        signoff = store.read_signoff(queue_id, default={})
        result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff), "archive_summary": store.archive_summary(queue_id), "change_request_summary": store.change_request_summary(queue_id)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_signoff_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_signoff(argv: list[str]) -> None:
    _execute_release_portfolio_governance_signoff(argv)

def _execute_release_portfolio_governance_audit(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-audit', *argv]
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
    parser = build_release_portfolio_governance_audit_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=signoff_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    if args.refresh:
        report = store.refresh(portfolio_id)
        result.update({"report": report, "summary": portfolio_governance_audit_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_audit_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.ledger:
        entries = store.read_ledger(portfolio_id)
        if args.ledger_limit and args.ledger_limit > 0:
            entries = entries[-args.ledger_limit :]
        result.update({"ledger": entries, "ledger_summary": {"entry_count": len(entries)}})
    if args.export:
        manifest = store.export_audit(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_audit_package(
            store.zip_path(portfolio_id),
            strict=args.strict,
            require_signed=args.require_signed,
            require_archives=args.require_archives,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
        )
        write_release_portfolio_governance_audit_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_audit_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_audit_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_audit(argv: list[str]) -> None:
    _execute_release_portfolio_governance_audit(argv)

__all__ = ('_execute_release_portfolio_audit', 'handle_release_portfolio_audit', '_execute_release_portfolio_governance_queue', 'handle_release_portfolio_governance_queue', '_execute_release_portfolio_governance_signoff', 'handle_release_portfolio_governance_signoff', '_execute_release_portfolio_governance_audit', 'handle_release_portfolio_governance_audit')
