from __future__ import annotations

from .dependencies import *

from .part_005 import build_public_trust_center_parser

from .part_006 import _build_public_trust_center_store, print_public_trust_center_result

def _execute_public_trust_center(argv: list[str]) -> None:
    raw_args = ['public-trust-center', *argv]
    pass
    pass
    pass



    pass
    pass



    pass
    from song_agent.application.legacy_dependencies.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore, accepted_evidence_summary
    pass
    parser = build_public_trust_center_parser()
    args = parser.parse_args(raw_args[1:])
    store = _build_public_trust_center_store()
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    distribution_kit_store = PublicTrustCenterDistributionKitStore(
        trust_center_store=store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
    )
    distribution_kit_acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
    acceptance_board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=distribution_kit_acceptance_store)
    payload: dict[str, Any] = {
        "center_id": args.center_id,
        "attestation_profile": args.profile,
        "release_ids": args.release_ids,
        "portfolio_ids": args.portfolio_ids,
        "include_all_releases": not bool(args.release_ids),
        "include_all_portfolios": not bool(args.portfolio_ids),
        "require_registry_current": True,
        "require_portal_current": True,
        "require_transparency_current": True,
        "require_acknowledgement_current": args.require_acknowledgement_current,
        "include_delivery": args.include_delivery,
        "include_distribution": args.include_delivery and args.include_distribution,
        "include_submission": args.include_delivery and args.include_submission,
        "include_submission_evidence": args.include_delivery and args.include_submission_evidence,
        "include_operations": args.include_delivery and args.include_operations,
        "require_release_signoff": args.require_release_signoff,
        "require_distribution_signed": args.require_distribution_signed,
        "require_submission_accepted": args.require_submission_accepted,
        "require_submission_evidence_signed": args.require_submission_evidence_signed,
        "require_operations_signed": args.require_operations_signed,
        "require_operations_audit_verified": args.require_operations_audit_verified,
        "require_operations_reviewer_pack_verified": args.require_operations_reviewer_pack_verified,
    }
    if args.name:
        payload["name"] = args.name
    result: dict[str, Any] = {"ok": True, "center_id": args.center_id}
    if args.refresh:
        report = store.refresh_report(args.center_id, payload)
        result.update({"report": report, "summary": public_trust_center_summary(report), "stale": False})
    else:
        config = store.read_config(args.center_id, default={}) or store.create_or_update_center(payload)
        report = store.read_report(args.center_id, default={})
        summary = public_trust_center_summary(report) if report else {"status": "missing", "center_id": args.center_id}
        if report:
            summary["stale"] = store.report_is_stale(args.center_id, report)
        result.update({"config": config, "report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        result["manifest"] = store.export_center(args.center_id)
    if args.zip:
        result["zip"] = store.build_zip(args.center_id)
    if args.verify:
        verify_payload = {
            "strict": args.strict,
            "require_registry_current": args.require_registry_current,
            "require_portal_current": args.require_portal_current,
            "require_transparency_current": args.require_transparency_current,
            "require_acknowledgement_current": args.require_acknowledgement_current,
            "require_release_readiness": args.require_release_readiness,
            "require_delivery_readiness": args.require_delivery_readiness,
            "require_distribution_ready": args.require_distribution_ready,
            "require_submission_accepted": args.require_submission_accepted,
            "require_submission_evidence": args.require_submission_evidence,
            "require_operations_signed": args.require_operations_signed,
            "require_operations_audit": args.require_operations_audit,
            "require_operations_reviewer_pack": args.require_operations_reviewer_pack,
            "require_anchor_registry_current": args.require_anchor_registry_current,
            "require_anchor_published": args.require_anchor_published,
            "require_anchor_not_revoked": args.require_anchor_not_revoked,
            "require_anchor_transparency_current": args.require_anchor_transparency_current,
            "require_anchor_checkpoint": args.require_anchor_checkpoint,
        }
        if args.require_anchor_registry_current or args.require_anchor_published or args.require_anchor_not_revoked:
            verify_payload["anchor_registry_path"] = anchor_store.zip_path(args.center_id)
        if args.require_anchor_transparency_current or args.require_anchor_checkpoint:
            verify_payload["anchor_transparency_path"] = anchor_transparency_store.zip_path(args.center_id)
        if args.require_anchor_checkpoint:
            verify_payload["anchor_checkpoint_path"] = anchor_transparency_store.current_checkpoint_path(args.center_id)
        verification = store.verify_zip(args.center_id, verify_payload)
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.archive:
        result["archive"] = store.archive_snapshot(args.center_id)
    if args.anchor_register:
        registered = anchor_store.register_current_anchor(args.center_id, {"reason": args.anchor_reason})
        result["anchor_registry"] = registered
        result["anchor_summary"] = anchor_registry_summary(registered.get("registry") if isinstance(registered.get("registry"), dict) else {})
    if args.anchor_publish:
        registry = anchor_store.read_registry(args.center_id, default={})
        entry_id = str(registry.get("current_entry_id") or "")
        if not entry_id:
            registered = anchor_store.register_current_anchor(args.center_id, {"reason": args.anchor_reason})
            entry_id = str((registered.get("entry") if isinstance(registered.get("entry"), dict) else {}).get("entry_id") or "")
        published = anchor_store.publish_entry(args.center_id, entry_id, {"reason": args.anchor_reason, "supersede_current": True})
        result["anchor_publish"] = published
        result["anchor_summary"] = anchor_registry_summary(published.get("registry") if isinstance(published.get("registry"), dict) else {})
    if args.anchor_revoke:
        revoked = anchor_store.revoke_entry(args.center_id, args.anchor_revoke, {"reason": args.anchor_reason})
        result["anchor_revoke"] = revoked
        result["anchor_summary"] = anchor_registry_summary(revoked.get("registry") if isinstance(revoked.get("registry"), dict) else {})
    if args.anchor_export:
        result["anchor_manifest"] = anchor_store.export_registry(args.center_id)
    if args.anchor_zip:
        result["anchor_zip"] = anchor_store.build_zip(args.center_id)
    if args.anchor_verify:
        anchor_verification = verify_public_trust_center_anchor_registry_package(
            anchor_store.zip_path(args.center_id),
            strict=args.strict,
            require_current=args.require_anchor_registry_current,
            require_anchor_published=args.require_anchor_published,
            require_anchor_not_revoked=args.require_anchor_not_revoked,
        )
        write_public_trust_center_anchor_registry_verification_report(anchor_verification, anchor_store.verification_report_path(args.center_id))
        result["anchor_verification"] = anchor_verification
        result["anchor_verification_summary"] = anchor_verification.get("summary", {})
    if args.anchor_transparency_refresh:
        report = anchor_transparency_store.refresh_report(args.center_id, {"reason": args.anchor_reason})
        result["anchor_transparency"] = report
        result["anchor_transparency_summary"] = anchor_transparency_summary(report)
    if args.anchor_checkpoint_create:
        checkpoint = anchor_transparency_store.create_checkpoint(args.center_id, {"reason": args.anchor_reason})
        result["anchor_checkpoint"] = checkpoint
    if args.anchor_transparency_export:
        result["anchor_transparency_manifest"] = anchor_transparency_store.export_transparency(args.center_id)
    if args.anchor_transparency_zip:
        result["anchor_transparency_zip"] = anchor_transparency_store.build_zip(args.center_id)
    if args.anchor_transparency_verify:
        transparency_verification = verify_public_trust_center_anchor_transparency_package(
            anchor_transparency_store.zip_path(args.center_id),
            strict=args.strict,
            checkpoint_path=anchor_transparency_store.current_checkpoint_path(args.center_id),
            anchor_registry_path=anchor_store.zip_path(args.center_id),
            require_current_checkpoint=args.require_anchor_transparency_current or args.require_anchor_checkpoint,
            require_published_anchor=args.require_anchor_published or args.require_anchor_registry_current,
            require_not_revoked=args.require_anchor_not_revoked,
        )
        write_public_trust_center_anchor_transparency_verification_report(transparency_verification, anchor_transparency_store.verification_report_path(args.center_id))
        result["anchor_transparency_verification"] = transparency_verification
        result["anchor_transparency_verification_summary"] = transparency_verification.get("summary", {})
    if args.distribution_kit_refresh:
        kit_report = distribution_kit_store.refresh_report(args.center_id)
        result["distribution_kit"] = kit_report
        result["distribution_kit_summary"] = distribution_kit_summary(kit_report)
    if args.distribution_kit_export:
        result["distribution_kit_manifest"] = distribution_kit_store.export_kit(args.center_id)
    if args.distribution_kit_zip:
        result["distribution_kit_zip"] = distribution_kit_store.build_zip(args.center_id)
    if args.distribution_kit_verify:
        kit_verification = distribution_kit_store.verify_zip(
            args.center_id,
            {
                "strict": args.strict,
                "deep": True,
                "require_current": True,
                "require_delivery_readiness": args.require_delivery_readiness,
                "require_anchor_registry_current": True,
                "require_anchor_published": True,
                "require_anchor_not_revoked": True,
                "require_anchor_transparency_current": True,
                "require_anchor_checkpoint": True,
            },
        )
        result["distribution_kit_verification"] = kit_verification
        result["distribution_kit_verification_summary"] = kit_verification.get("summary", {})
    if args.distribution_kit_acceptance_template:
        template = distribution_kit_acceptance_store.create_response_template(args.center_id)
        result["distribution_kit_acceptance_template"] = template
    if args.distribution_kit_acceptance_response_file is not None or args.distribution_kit_acceptance_response_base64:
        import_payload: dict[str, Any] = {}
        if args.distribution_kit_acceptance_response_file is not None:
            import_payload["content"] = args.distribution_kit_acceptance_response_file.read_text(encoding="utf-8")
        if args.distribution_kit_acceptance_response_base64:
            import_payload["content_base64"] = args.distribution_kit_acceptance_response_base64
        imported = distribution_kit_acceptance_store.import_response(args.center_id, import_payload)
        result["distribution_kit_acceptance_import"] = imported
        result["distribution_kit_acceptance_summary"] = imported.get("response", {})
    if args.distribution_kit_acceptance_verify_response:
        if not args.distribution_kit_acceptance_response_id:
            raise SystemExit("--distribution-kit-acceptance-response-id is required with --distribution-kit-acceptance-verify-response")
        verification = distribution_kit_acceptance_store.verify_response(args.center_id, args.distribution_kit_acceptance_response_id)
        result["distribution_kit_acceptance_response_verification"] = verification
    if args.distribution_kit_accepted_evidence_export:
        manifest = distribution_kit_acceptance_store.export_accepted_evidence(args.center_id, args.distribution_kit_acceptance_response_id)
        result["distribution_kit_accepted_evidence_manifest"] = manifest
    if args.distribution_kit_accepted_evidence_zip:
        zip_info = distribution_kit_acceptance_store.build_accepted_evidence_zip(args.center_id, args.distribution_kit_acceptance_response_id)
        result["distribution_kit_accepted_evidence_zip"] = zip_info
        evidence = distribution_kit_acceptance_store.read_evidence(args.center_id, zip_info.get("evidence_id"), default={})
        result["distribution_kit_accepted_evidence_summary"] = accepted_evidence_summary(evidence)
    if args.distribution_kit_accepted_evidence_verify:
        evidence_id = None
        if args.distribution_kit_acceptance_response_id:
            evidence = distribution_kit_acceptance_store.refresh_accepted_evidence(args.center_id, {"response_id": args.distribution_kit_acceptance_response_id})
            evidence_id = str(evidence.get("evidence_id") or "")
        verification = distribution_kit_acceptance_store.verify_accepted_evidence_zip(args.center_id, evidence_id, {"strict": args.strict, "require_current": True})
        result["distribution_kit_accepted_evidence_verification"] = verification
        result["distribution_kit_accepted_evidence_verification_summary"] = verification.get("summary", {})
    if args.distribution_kit_acceptance_change_request:
        if not args.distribution_kit_acceptance_response_id:
            raise SystemExit("--distribution-kit-acceptance-response-id is required with --distribution-kit-acceptance-change-request")
        result["distribution_kit_acceptance_change_request"] = distribution_kit_acceptance_store.create_change_request_draft(args.center_id, args.distribution_kit_acceptance_response_id, {"source": "cli"})
    if args.acceptance_board_policy_save is not None:
        result["acceptance_board_policy"] = acceptance_board_store.save_policy(args.center_id, read_json(args.acceptance_board_policy_save))
    if args.acceptance_board_refresh:
        board = acceptance_board_store.refresh_report(args.center_id)
        result["acceptance_board"] = board
        result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
    if args.acceptance_board_export:
        result["acceptance_board_manifest"] = acceptance_board_store.export_board(args.center_id)
    if args.acceptance_board_zip:
        result["acceptance_board_zip"] = acceptance_board_store.build_zip(args.center_id)
    if args.acceptance_board_verify:
        board_verification = acceptance_board_store.verify_zip(
            args.center_id,
            {
                "strict": args.strict,
                "require_ready": args.require_ready,
                "require_quorum": args.require_quorum,
                "require_no_conflicts": args.require_no_conflicts,
                "min_accepted_count": args.min_accepted_count,
                "min_accepted_organizations": args.min_accepted_organizations,
                "required_roles": args.required_roles,
                "use_distribution_kit": True,
            },
        )
        result["acceptance_board_verification"] = board_verification
        result["acceptance_board_verification_summary"] = board_verification.get("summary", {})
    if args.acceptance_board_signoff_draft:
        result["acceptance_board_signoff_draft"] = acceptance_board_store.create_signoff_draft(args.center_id, {"source": "cli"})
    if args.acceptance_board_signoff:
        signoff = acceptance_board_store.signoff(args.center_id, {"signed_by": args.acceptance_board_signed_by, "reason": args.acceptance_board_signoff_reason})
        result["acceptance_board_signoff"] = signoff
        result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
    if args.acceptance_board_change_request_create:
        change = acceptance_board_store.create_change_request(args.center_id, {"reason": args.acceptance_board_signoff_reason, "requested_by": args.acceptance_board_signed_by})
        result["acceptance_board_change_request"] = change
    if args.acceptance_board_change_request_approve:
        if not args.acceptance_board_change_request_id:
            raise SystemExit("--acceptance-board-change-request-id is required with --acceptance-board-change-request-approve")
        change = acceptance_board_store.approve_change_request(args.center_id, args.acceptance_board_change_request_id, {"approved_by": args.acceptance_board_signed_by, "reason": args.acceptance_board_signoff_reason})
        result["acceptance_board_change_request"] = change
    if args.acceptance_board_reset_signoff:
        if not args.acceptance_board_change_request_id:
            raise SystemExit("--acceptance-board-change-request-id is required with --acceptance-board-reset-signoff")
        reset = acceptance_board_store.reset_signoff(args.center_id, {"change_request_id": args.acceptance_board_change_request_id, "reason": args.acceptance_board_signoff_reason})
        result["acceptance_board_signoff_reset"] = reset
        result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
    if args.acceptance_board_signoff_archive_export:
        result["acceptance_board_signoff_archive_manifest"] = acceptance_board_store.export_signoff_archive(args.center_id)
    if args.acceptance_board_signoff_archive_zip:
        result["acceptance_board_signoff_archive_zip"] = acceptance_board_store.build_signoff_archive_zip(args.center_id)
    if args.acceptance_board_signoff_archive_verify:
        archive_verification = acceptance_board_store.verify_signoff_archive_zip(
            args.center_id,
            {
                "strict": args.strict,
                "require_signed": True,
                "require_current": True,
                "require_ready": True,
                "use_board_zip": True,
                "use_board_verification": True,
                "use_distribution_kit": True,
                "use_accepted_evidence": True,
            },
        )
        result["acceptance_board_signoff_archive_verification"] = archive_verification
        result["acceptance_board_signoff_archive_verification_summary"] = archive_verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_result(result)
    raise SystemExit(0)

def handle_public_trust_center(argv: list[str]) -> None:
    _execute_public_trust_center(argv)

__all__ = ('_execute_public_trust_center', 'handle_public_trust_center')
