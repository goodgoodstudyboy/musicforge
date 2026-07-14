from __future__ import annotations

from .dependencies import *

from .part_002 import build_release_portfolio_governance_attestation_accepted_evidence_parser, build_release_portfolio_governance_attestation_transparency_acknowledgement_parser, build_release_portfolio_governance_attestation_transparency_parser

from .part_004 import build_public_trust_center_publication_parser

from .part_006 import _build_public_trust_center_store, _build_release_portfolio_governance_attestation_portal_store, print_release_portfolio_governance_attestation_accepted_evidence_result, print_release_portfolio_governance_attestation_transparency_acknowledgement_result, print_release_portfolio_governance_attestation_transparency_result

def _execute_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-accepted-evidence', *argv]
    from song_agent.application.legacy_dependencies.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore, accepted_evidence_summary
    pass
    pass
    parser = build_release_portfolio_governance_attestation_accepted_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        payload = {"profile": args.profile}
        if args.response_id:
            payload["response_id"] = args.response_id
        evidence = store.refresh_evidence(portfolio_id, payload)
        result.update({"accepted_evidence": evidence, "summary": accepted_evidence_summary(evidence), "stale": False})
    else:
        evidence = store.read_evidence(portfolio_id, profile=args.profile, default={})
        summary = accepted_evidence_summary(evidence) if evidence else {"status": "missing", "external_review_status": "missing", "profile": args.profile}
        if evidence:
            summary["stale"] = store.evidence_is_stale(portfolio_id, evidence, profile=args.profile)
        result.update({"accepted_evidence": evidence, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        result["manifest"] = store.export_evidence(portfolio_id, {"profile": args.profile})
    if args.zip:
        result["zip"] = store.build_zip(portfolio_id, {"profile": args.profile})
    if args.verify:
        verification = store.verify_evidence(portfolio_id, {"profile": args.profile, "strict": args.strict, "require_current": args.require_current})
        write_release_portfolio_governance_attestation_accepted_evidence_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result["verification"] = verification
    if args.archive:
        result["accepted_evidence"] = store.archive_evidence(portfolio_id, {"profile": args.profile, "reason": args.reason})
        result["summary"] = accepted_evidence_summary(result["accepted_evidence"])
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_accepted_evidence_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_accepted_evidence(argv)

def _execute_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-transparency', *argv]
    pass
    pass
    pass
    pass
    parser = build_release_portfolio_governance_attestation_transparency_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        feed = store.refresh_feed(portfolio_id, {"profile": args.profile, "require_accepted_evidence": args.require_accepted_evidence})
        result.update({"feed": feed, "summary": transparency_summary(feed), "stale": False})
    else:
        feed = store.read_feed(portfolio_id, profile=args.profile, default={})
        summary = transparency_summary(feed) if feed else {"status": "missing", "profile": args.profile}
        if feed:
            summary["stale"] = store.feed_is_stale(portfolio_id, feed, profile=args.profile)
        result.update({"feed": feed, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        result["manifest"] = store.export_transparency(portfolio_id, {"profile": args.profile})
    if args.zip:
        result["zip"] = store.build_zip(portfolio_id, {"profile": args.profile})
    if args.verify:
        verification = store.verify_transparency(
            portfolio_id,
            {
                "profile": args.profile,
                "strict": args.strict,
                "require_current": args.require_current,
                "require_accepted_evidence": args.require_accepted_evidence,
                "require_no_revoked_current": args.require_no_revoked_current,
                "require_contiguous_chain": args.require_contiguous_chain,
            },
        )
        write_release_portfolio_governance_attestation_transparency_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result["verification"] = verification
    if args.notices:
        result["notices"] = store.list_notices(portfolio_id, profile=args.profile)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_transparency(argv)

def _execute_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-transparency-acknowledgement', *argv]
    pass
    pass
    pass
    pass
    pass



    parser = build_release_portfolio_governance_attestation_transparency_acknowledgement_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(transparency_store=transparency_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh_pack:
        pack = store.refresh_pack(portfolio_id, {"profile": args.profile})
        result.update({"pack": pack, "summary": {"status": pack.get("status"), "pack_id": pack.get("pack_id"), "source_hash": pack.get("source_hash")}})
    else:
        pack = store.read_pack(portfolio_id, profile=args.profile, default={})
        result.update({"pack": pack, "summary": {"status": pack.get("status", "missing") if pack else "missing", "pack_id": pack.get("pack_id") if pack else None}})
    if args.export_pack:
        result["pack_manifest"] = store.export_pack(portfolio_id, {"profile": args.profile})
    if args.zip_pack:
        result["pack_zip"] = store.build_pack_zip(portfolio_id, {"profile": args.profile})
    if args.verify_pack:
        report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
            store.pack_zip_path(portfolio_id, args.profile),
            strict=args.strict,
            require_pack=True,
            require_transparency=args.require_transparency,
        )
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, store.pack_verification_report_path(portfolio_id, args.profile))
        result["pack_verification"] = report
    if args.import_response:
        payload: dict[str, Any] = {"profile": args.profile}
        if args.content_base64:
            payload["content_base64"] = args.content_base64
        imported = store.import_response(portfolio_id, payload)
        result.update(imported)
    if args.refresh_evidence:
        payload = {"profile": args.profile}
        if args.response_id:
            payload["response_id"] = args.response_id
        evidence = store.refresh_evidence(portfolio_id, payload)
        result.update({"acknowledgement_evidence": evidence, "evidence_summary": acknowledgement_summary(evidence)})
    if args.export_evidence:
        result["evidence_manifest"] = store.export_evidence(portfolio_id, {"profile": args.profile})
    if args.zip_evidence:
        result["evidence_zip"] = store.build_evidence_zip(portfolio_id, {"profile": args.profile})
    if args.verify_evidence:
        report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
            store.evidence_zip_path(portfolio_id, args.profile),
            strict=args.strict,
            require_response=True,
            require_accepted=args.require_accepted,
        )
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, store.evidence_verification_report_path(portfolio_id, args.profile))
        result["evidence_verification"] = report
    if args.create_change_request:
        if not args.response_id:
            raise SystemExit("--response-id is required with --create-change-request")
        result["change_request"] = store.create_change_request(portfolio_id, args.response_id, {"profile": args.profile})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_acknowledgement_result(result)
    raise SystemExit(0)

def handle_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_transparency_acknowledgement(argv)

def _execute_public_trust_center_publication(argv: list[str]) -> None:
    raw_args = ['public-trust-center-publication', *argv]
    pass
    pass


    parser = build_public_trust_center_publication_parser()
    args = parser.parse_args(raw_args[1:])
    trust_store = _build_public_trust_center_store()
    pass
    pass
    pass
    pass
    pass
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    distribution_kit_store = PublicTrustCenterDistributionKitStore(trust_center_store=trust_store, anchor_registry_store=anchor_store, anchor_transparency_store=anchor_transparency_store)
    acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
    board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=acceptance_store)
    store = PublicTrustCenterPublicationStore(
        trust_center_store=trust_store,
        distribution_kit_store=distribution_kit_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
        acceptance_store=acceptance_store,
        acceptance_board_store=board_store,
    )
    result: dict[str, Any] = {"ok": True, "center_id": args.center_id, "channel_id": args.channel_id}
    if args.create_channel:
        result["channel"] = store.create_channel(args.center_id, {"channel_id": args.channel_id, "name": args.channel_name, "channel_type": args.channel_type})
    else:
        try:
            result["channel"] = store.read_channel(args.center_id, args.channel_id)
        except Exception:
            result["channel"] = store.create_channel(args.center_id, {"channel_id": args.channel_id, "name": args.channel_name, "channel_type": args.channel_type})
    publication_id = args.publication_id
    if args.refresh:
        report = store.refresh_publication(args.center_id, args.channel_id)
        publication_id = str(report.get("publication_id") or publication_id or "")
        result["publication"] = report
        result["summary"] = publication_summary(report)
    if args.supersede:
        report = store.supersede_publication(args.center_id, args.channel_id, publication_id, {"reason": args.reason})
        publication_id = str(report.get("publication_id") or publication_id or "")
        result["publication"] = report
        result["summary"] = publication_summary(report)
    if args.revoke:
        if not publication_id:
            publication_id = store._current_publication_id(args.center_id, args.channel_id)
        report = store.revoke_publication(args.center_id, args.channel_id, publication_id, {"reason": args.reason})
        result["publication"] = report
        result["summary"] = publication_summary(report)
    if args.export:
        result["manifest"] = store.export_publication(args.center_id, args.channel_id, publication_id)
        publication_id = str(result["manifest"].get("publication_id") or publication_id or "")
    if args.zip:
        result["zip"] = store.build_publication_zip(args.center_id, args.channel_id, publication_id)
        publication_id = str(result["zip"].get("publication_id") or publication_id or "")
    if args.verify:
        verification = store.verify_publication_zip(
            args.center_id,
            args.channel_id,
            publication_id,
            {
                "strict": args.strict,
                "deep": args.deep,
                "require_ready": args.require_ready,
                "require_acceptance_board_signoff": args.require_acceptance_board_signoff,
                "require_anchor_current": args.require_anchor_current,
                "require_no_revoked": args.require_no_revoked,
                "publication_channel_state_path": args.publication_channel_state,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.verify_mirror:
        if not publication_id:
            publication_id = store._current_publication_id(args.center_id, args.channel_id)
        mirror_dir = args.mirror_dir or store.export_dir(args.center_id, args.channel_id, publication_id)
        verification = store.verify_mirror_directory(
            args.center_id,
            args.channel_id,
            publication_id,
            mirror_dir,
            {
                "strict": args.strict,
                "require_ready": args.require_ready,
                "require_acceptance_board_signoff": args.require_acceptance_board_signoff,
                "require_anchor_current": args.require_anchor_current,
                "require_no_revoked": args.require_no_revoked,
                "publication_channel_state_path": args.publication_channel_state,
            },
        )
        result["mirror_verification"] = verification
        result["mirror_verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_public_trust_center_publication_verification_report(result["verification"])
        elif "mirror_verification" in result:
            print_public_trust_center_publication_verification_report(result["mirror_verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_public_trust_center_publication(argv: list[str]) -> None:
    _execute_public_trust_center_publication(argv)

__all__ = ('_execute_release_portfolio_governance_attestation_accepted_evidence', 'handle_release_portfolio_governance_attestation_accepted_evidence', '_execute_release_portfolio_governance_attestation_transparency', 'handle_release_portfolio_governance_attestation_transparency', '_execute_release_portfolio_governance_attestation_transparency_acknowledgement', 'handle_release_portfolio_governance_attestation_transparency_acknowledgement', '_execute_public_trust_center_publication', 'handle_public_trust_center_publication')
