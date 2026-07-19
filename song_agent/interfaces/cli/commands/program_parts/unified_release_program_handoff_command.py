from __future__ import annotations


from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_program_parts_dependencies

from .program_component_and_cross_domain_adapters import _program_component
Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = _commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report
def _run_unified_release_program_handoff_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass





    store = _program_component("handoff")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_handoff(program_id)
        status = (detail.get("report") or {}).get("status") or "unknown"
        return {"ok": True, **detail, "summary": (detail.get("report") or {}).get("summary", {}), "status": status}
    if args.action == "refresh":
        report = store.refresh_handoff(program_id, {"external_evidence_manifest": args.external_evidence_manifest})
        return {"ok": report.get("status") in {"ready_for_review", "ready_for_signoff"}, "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "review-pack":
        pack = store.export_review_pack(program_id, {"review_pack_id": args.review_pack_id, "audience": args.audience})
        return {"ok": pack.get("status") == "ready", "review_pack": pack, "summary": {"review_pack_id": pack.get("review_pack_id")}, "status": pack.get("status")}
    if args.action == "review-pack-zip":
        result = store.build_review_pack_zip(program_id, args.review_pack_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "review-pack-verify":
        report = store.verify_review_pack_zip(program_id, args.review_pack_id, {"strict": args.strict})
        if args.report_out is not None:
            write_unified_release_program_review_pack_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "import-response":
        response = store.import_response(program_id, read_json(args.response_json))
        return {"ok": response.get("status") in {"accepted", "accepted_with_notes"}, "response": response.get("response"), "verification": response.get("verification"), "summary": {"response_id": response.get("response", {}).get("response_id")}, "status": response.get("status")}
    if args.action == "accepted-evidence":
        result = store.create_accepted_evidence(program_id, args.response_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"evidence_id": result.get("evidence", {}).get("evidence_id")}}
    if args.action == "accepted-evidence-zip":
        result = store.build_accepted_evidence_zip(program_id, args.evidence_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "accepted-evidence-verify":
        report = store.verify_accepted_evidence_zip(
            program_id,
            args.evidence_id,
            {
                "strict": args.strict,
                "require_accepted": args.require_accepted,
                "response_verification_report": args.response_verification_report,
                "response_binding_summary": args.response_binding_summary,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_accepted_evidence_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "decision-board":
        policy: ImplementationDocument = {}
        if args.required_roles is not None:
            policy["required_roles"] = args.required_roles
        if args.minimum_acceptances is not None:
            policy["minimum_acceptances"] = args.minimum_acceptances
        if args.minimum_organizations is not None:
            policy["minimum_organizations"] = args.minimum_organizations
        board = store.refresh_decision_board(program_id, {"policy": policy} if policy else {})
        return {"ok": board.get("status") == "ready_for_signoff", "decision_board": board, "summary": board.get("readiness", {}), "status": board.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_handoff(program_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive-export":
        manifest = store.export_handoff_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_handoff_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "archive-verify":
        report = store.verify_handoff_archive_zip(
            program_id,
            {
                "strict": args.strict,
                "require_current": args.require_current,
                "require_accepted": args.require_accepted,
                "require_signed": args.require_signed,
                "external_evidence_manifest": args.external_evidence_manifest,
                "handoff_signoff_binding": args.handoff_signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_handoff_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            handoff_archive_zip_path=args.handoff_archive_zip,
            handoff_archive_verification_report_path=args.handoff_archive_verification_report,
            external_evidence_manifest=args.external_evidence_manifest,
            handoff_signoff_binding=args.handoff_signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-handoff command.")

def _run_unified_release_program_vault_command(args: argparse.Namespace) -> ImplementationDocument:
    pass

    store = _program_component("vault")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_vault(program_id)
        status = (detail.get("report") or {}).get("status") or "unknown"
        return {"ok": True, **detail, "summary": (detail.get("report") or {}).get("summary", {}), "status": status}
    if args.action == "refresh":
        report = store.refresh_vault(program_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_vault(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_vault_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "anchor_path": result.get("anchor_path")}}
    if args.action == "verify":
        report = store.verify_vault_zip(
            program_id,
            {
                "strict": args.strict,
                "deep": args.deep,
                "require_anchor": args.require_anchor,
                "vault_anchor": args.vault_anchor,
                "require_current_program": args.require_current_program,
                "require_current_operations": args.require_current_operations,
                "require_current_handoff": args.require_current_handoff,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_vault_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            vault_zip_path=args.vault_zip,
            vault_verification_report_path=args.vault_verification_report,
            vault_anchor_path=args.vault_anchor,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-vault command.")

def _run_unified_release_program_vault_operations_command(args: argparse.Namespace) -> ImplementationDocument:
    pass

    store = _program_component("vault_operations")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_operations(program_id)
        report = detail.get("report") or {}
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or (detail.get("signoff_state") or {}).get("status") or "unknown"}
    if args.action == "init-policy":
        policy = store.init_policy(program_id, {"review_interval_days": args.review_interval_days})
        return {"ok": policy.get("status") == "active", "policy": policy, "summary": {"policy_hash": policy.get("integrity_hash")}, "status": policy.get("status")}
    if args.action == "register-vault":
        registry = store.register_vault(program_id, {"vault_zip": args.vault_zip, "vault_anchor": args.vault_anchor, "vault_verification_report": args.vault_verification_report})
        return {"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "refresh-registry":
        registry = store.refresh_registry(program_id)
        return {"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "review":
        review = store.run_custody_review(program_id)
        return {"ok": review.get("status") == "passed", "review": review, "summary": review.get("summary", {}), "status": review.get("status")}
    if args.action == "rotation-plan":
        plan = store.create_rotation_plan(program_id, {"force_rotation": args.force_rotation, "reason": args.reason})
        return {"ok": plan.get("status") in {"not_required", "required"}, "rotation_plan": plan, "summary": {"plan_id": plan.get("plan_id")}, "status": plan.get("status")}
    if args.action == "supersede":
        registry = store.supersede_vault(program_id, {"old_generation_id": args.old_generation_id, "new_generation_id": args.new_generation_id, "vault_zip": args.vault_zip, "vault_anchor": args.vault_anchor, "vault_verification_report": args.vault_verification_report})
        return {"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "revoke":
        registry = store.revoke_vault(program_id, {"generation_id": args.generation_id, "reason": args.reason})
        return {"ok": registry.get("status") != "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "transfer-pack":
        transfer = store.create_transfer_pack(program_id, {"recipient": args.recipient})
        return {"ok": transfer.get("status") == "ready", "transfer_report": transfer, "summary": transfer.get("summary", {}), "status": transfer.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_operations(program_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive-export":
        manifest = store.export_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "archive-verify":
        report = store.verify_archive_zip(
            program_id,
            {
                "strict": args.strict,
                "deep": args.deep,
                "require_signed": args.require_signed,
                "require_current_vault": args.require_current_vault,
                "signoff_binding": args.signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_vault_operations_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(program_id, required=True, archive_zip_path=args.archive_zip, verification_report_path=args.verification_report, signoff_binding_path=args.signoff_binding)
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-vault-ops command.")

def _run_unified_release_program_continuity_command(args: argparse.Namespace) -> ImplementationDocument:
    pass

    store = _program_component("continuity")
    program_id = args.program_id
    evidence_payload = {
        "vault_operations_archive": getattr(args, "vault_operations_archive", None),
        "vault_operations_verification_report": getattr(args, "vault_operations_verification_report", None),
        "vault_operations_signoff_binding": getattr(args, "vault_operations_signoff_binding", None),
    }
    if args.action == "status":
        detail = store.get_continuity(program_id)
        report = detail.get("report") or {}
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or (detail.get("signoff_state") or {}).get("status") or "unknown"}
    if args.action == "init-policy":
        policy = store.init_policy(program_id, {})
        return {"ok": policy.get("status") == "active", "policy": policy, "summary": {"policy_hash": policy.get("integrity_hash")}, "status": policy.get("status")}
    if args.action == "plan":
        plan = store.create_recovery_plan(program_id, evidence_payload)
        return {"ok": plan.get("status") == "planned", "recovery_plan": plan, "summary": {"plan_hash": plan.get("integrity_hash")}, "status": plan.get("status")}
    if args.action == "drill":
        drill = store.run_recovery_drill(program_id, evidence_payload)
        return {"ok": drill.get("status") == "passed", "drill_report": drill, "summary": drill.get("summary", {}), "status": drill.get("status")}
    if args.action == "readiness":
        readiness = store.refresh_readiness(program_id, evidence_payload)
        return {"ok": readiness.get("status") == "passed", "readiness": readiness, "summary": readiness.get("summary", {}), "status": readiness.get("status")}
    if args.action == "runbook":
        runbook = store.generate_runbook(program_id, {})
        return {"ok": runbook.get("status") == "ready", "runbook": runbook, "summary": runbook.get("summary", {}), "status": runbook.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_continuity(program_id, {**evidence_payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive-export":
        manifest = store.export_archive(program_id, {})
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_archive_zip(program_id, {})
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "archive-verify":
        report = store.verify_archive_zip(
            program_id,
            {
                **evidence_payload,
                "strict": args.strict,
                "deep_restore": args.deep_restore,
                "require_signed": args.require_signed,
                "require_current_vault_operations": args.require_current_vault_operations,
                "signoff_binding": args.signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            signoff_binding_path=args.signoff_binding,
            vault_operations_archive_path=args.vault_operations_archive,
            vault_operations_verification_report_path=args.vault_operations_verification_report,
            vault_operations_signoff_binding_path=args.vault_operations_signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity command.")

def _run_unified_release_program_continuity_distribution_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass

    store = _program_component("continuity_distribution")
    program_id = args.program_id
    evidence_payload = {
        "continuity_archive": getattr(args, "continuity_archive", None),
        "continuity_verification_report": getattr(args, "continuity_verification_report", None),
        "continuity_signoff_binding": getattr(args, "continuity_signoff_binding", None),
        "vault_operations_archive": getattr(args, "vault_operations_archive", None),
        "vault_operations_verification_report": getattr(args, "vault_operations_verification_report", None),
        "vault_operations_signoff_binding": getattr(args, "vault_operations_signoff_binding", None),
        "evidence_vault": getattr(args, "evidence_vault", None),
        "vault_verification_report": getattr(args, "vault_verification_report", None),
        "vault_anchor": getattr(args, "vault_anchor", None),
    }
    if args.action == "status":
        detail = store.get_kit(program_id)
        source = detail.get("source_binding") or {}
        return {"ok": True, **detail, "summary": source, "status": source.get("status") or "unknown"}
    if args.action == "prepare":
        source = store.prepare_kit(program_id, evidence_payload)
        return {"ok": source.get("status") == "passed", "source_binding": source, "summary": source, "status": source.get("status")}
    if args.action == "export":
        manifest = store.export_kit(program_id, evidence_payload)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_kit_zip(program_id, evidence_payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_kit(program_id, {**evidence_payload, "strict": args.strict, "deep": args.deep, "require_receiver_receipt": args.require_receiver_receipt, "receiver_receipt": args.receiver_receipt})
        if args.report_out is not None:
            write_unified_release_program_continuity_distribution_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(program_id, required=True, kit_zip_path=args.kit_zip, verification_report_path=args.verification_report, require_receiver_receipt=args.require_receiver_receipt, receiver_receipt_path=args.receiver_receipt)
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    if args.action == "receipt-template":
        template = store.create_receiver_receipt_template(program_id)
        return {"ok": True, "receiver_receipt_template": template, "summary": {"kit_sha256": template.get("kit_sha256")}, "status": "passed"}
    if args.action == "import-receipt":
        receipt = store.import_receiver_receipt(program_id, read_json(args.receipt_json))
        return {"ok": receipt.get("decision") == "accepted", "receiver_receipt": receipt, "summary": {"receipt_id": receipt.get("receipt_id")}, "status": receipt.get("decision")}
    if args.action == "verify-receipt":
        report = store.verify_receiver_receipt(program_id, args.receipt_id)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-kit command.")

__all__ = ('_run_unified_release_program_handoff_command', '_run_unified_release_program_vault_command', '_run_unified_release_program_vault_operations_command', '_run_unified_release_program_continuity_command', '_run_unified_release_program_continuity_distribution_command')
