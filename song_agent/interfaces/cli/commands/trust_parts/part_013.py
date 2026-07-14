from __future__ import annotations

from .dependencies import *

from .part_002 import build_release_portfolio_governance_attestation_parser, build_release_portfolio_governance_attestation_portal_parser, build_release_portfolio_governance_attestation_portal_review_parser, build_release_portfolio_governance_attestation_registry_parser

from .part_006 import _build_release_portfolio_governance_attestation_portal_store, print_release_portfolio_governance_attestation_portal_result, print_release_portfolio_governance_attestation_portal_review_result, print_release_portfolio_governance_attestation_registry_result, print_release_portfolio_governance_attestation_result

def _execute_release_portfolio_governance_attestation(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation', *argv]
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
    pass
    parser = build_release_portfolio_governance_attestation_parser()
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
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    portfolio_id = args.portfolio_id
    payload = {"profile": args.profile, "require_no_force": args.require_no_force}
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        report = store.refresh_report(portfolio_id, payload)
        result.update({"report": report, "summary": portfolio_governance_attestation_summary(report), "stale": store.report_is_stale(portfolio_id, report, profile=args.profile)})
    else:
        report = store.read_report(portfolio_id, profile=args.profile, default={})
        summary = portfolio_governance_attestation_summary(report) if report else {"status": "missing", "profile": args.profile}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report, profile=args.profile)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    certificate = store.read_certificate(portfolio_id, profile=args.profile, default={})
    if certificate:
        result["certificate"] = certificate
    if args.export:
        manifest = store.export_attestation(portfolio_id, payload)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id, payload)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_attestation(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_vault=args.require_vault, require_final_board=args.require_final_board)
        write_release_portfolio_governance_attestation_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_attestation(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation(argv)

def _execute_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-registry', *argv]
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
    pass
    pass
    parser = build_release_portfolio_governance_attestation_registry_parser()
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
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
    portfolio_id = args.portfolio_id
    payload = {"profile": args.profile}
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.register_current:
        registered = store.register_current_attestation(portfolio_id, {**payload, "public_url": args.public_url, "distribution_note": args.distribution_note})
        result.update({"entry": registered.get("entry"), "registry": registered.get("registry"), "existing": bool(registered.get("existing"))})
    if args.publish:
        published = store.publish_entry(portfolio_id, args.publish, {**payload, "supersede_current": args.supersede_current, "public_url": args.public_url, "distribution_note": args.distribution_note, "published_by": "cli"})
        result.update({"entry": published.get("entry"), "registry": published.get("registry")})
    if args.revoke:
        revoked = store.revoke_entry(portfolio_id, args.revoke, {**payload, "reason": args.reason, "revoked_by": "cli"})
        result.update({"entry": revoked.get("entry"), "registry": revoked.get("registry")})
    if args.refresh:
        report = store.refresh_report(portfolio_id, payload)
        result.update({"report": report})
    else:
        report = store.read_report(portfolio_id, profile=args.profile, default={})
        if report:
            result["report"] = report
    registry = result.get("registry") if isinstance(result.get("registry"), dict) else store.read_registry(portfolio_id, profile=args.profile, default={})
    result["registry"] = registry
    result["summary"] = portfolio_governance_attestation_registry_summary(registry) if registry else {"status": "missing", "profile": args.profile}
    if args.export:
        manifest = store.export_registry(portfolio_id, payload)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id, payload)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_attestation_registry(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_current=args.require_current, require_published=args.require_published, require_no_revoked_current=args.require_no_revoked_current, require_accepted_evidence=args.require_accepted_evidence)
        write_release_portfolio_governance_attestation_registry_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_registry_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_registry_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_registry(argv)

def _execute_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-portal', *argv]
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
    pass
    pass
    pass
    parser = build_release_portfolio_governance_attestation_portal_parser()
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
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    registry_store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
    store = ReleasePortfolioGovernanceAttestationPortalStore(registry_store=registry_store, attestation_store=attestation_store)
    portfolio_id = args.portfolio_id
    payload = {"profile": args.profile}
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        report = store.refresh_report(portfolio_id, payload)
        result.update({"report": report, "summary": release_portfolio_governance_attestation_portal_summary(report), "stale": False})
    else:
        report = store.read_report(portfolio_id, profile=args.profile, default={})
        summary = release_portfolio_governance_attestation_portal_summary(report) if report else {"status": "missing", "profile": args.profile}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report, profile=args.profile)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        manifest = store.export_portal(portfolio_id, payload)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id, payload)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_attestation_portal(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_current=args.require_current, require_registry=args.require_registry, require_attestation=args.require_attestation, require_accepted_evidence=args.require_accepted_evidence)
        write_release_portfolio_governance_attestation_portal_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_portal_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_portal(argv)

def _execute_release_portfolio_governance_attestation_portal_review(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-portal-review', *argv]
    pass




    pass



    parser = build_release_portfolio_governance_attestation_portal_review_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh_pack:
        pack = store.refresh_pack(portfolio_id, {"profile": args.profile})
        result.update({"review_pack": pack, "summary": release_portfolio_governance_attestation_portal_review_pack_summary(pack), "stale": False})
    else:
        pack = store.read_pack(portfolio_id, profile=args.profile, default={})
        summary = release_portfolio_governance_attestation_portal_review_pack_summary(pack) if pack else {"status": "missing", "profile": args.profile}
        if pack:
            summary["stale"] = store.pack_is_stale(portfolio_id, pack, profile=args.profile)
        result.update({"review_pack": pack, "summary": summary, "stale": summary.get("stale", False)})
    if args.export_pack:
        manifest = store.export_pack(portfolio_id, {"profile": args.profile})
        result.update({"manifest": manifest})
    if args.zip_pack:
        zip_info = store.build_pack_zip(portfolio_id, {"profile": args.profile})
        result.update({"zip": zip_info})
    if args.verify_pack:
        verification = verify_release_portfolio_governance_attestation_portal_review_pack(
            store.pack_zip_path(portfolio_id, args.profile),
            strict=args.strict,
            require_current=args.require_current,
        )
        write_release_portfolio_governance_attestation_portal_review_pack_verification_report(verification, store.pack_verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification})
    if args.import_response:
        imported = store.import_response(portfolio_id, {"profile": args.profile, "content_base64": args.content_base64})
        result.update(imported)
    if args.responses:
        result.update({"responses": store.list_responses(portfolio_id, profile=args.profile)})
    if args.response_id and not args.verify_response and not args.create_change_request:
        response = store.get_response(portfolio_id, args.response_id, profile=args.profile)
        result.update({"response": response, "response_summary": release_portfolio_governance_attestation_portal_response_summary(response)})
    if args.verify_response:
        if not args.response_id:
            parser.error("--verify-response requires --response-id")
        verification = store.verify_response(portfolio_id, args.response_id, profile=args.profile)
        result.update({"response_verification": verification})
    if args.create_change_request:
        if not args.response_id:
            parser.error("--create-change-request requires --response-id")
        change = store.create_change_request(portfolio_id, args.response_id, {"created_by": "cli"}, profile=args.profile)
        result.update(change)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_review_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_attestation_portal_review(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_portal_review(argv)

__all__ = ('_execute_release_portfolio_governance_attestation', 'handle_release_portfolio_governance_attestation', '_execute_release_portfolio_governance_attestation_registry', 'handle_release_portfolio_governance_attestation_registry', '_execute_release_portfolio_governance_attestation_portal', 'handle_release_portfolio_governance_attestation_portal', '_execute_release_portfolio_governance_attestation_portal_review', 'handle_release_portfolio_governance_attestation_portal_review')
