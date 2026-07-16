from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_program_parts_dependencies

from .program_component_and_cross_domain_adapters import _program_component, _release_train_handoff_payload_from_args, _release_train_lifecycle_payload_from_args
Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = _commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report
def _run_unified_command_center_release_train_change_control_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass
    pass

    train_store = UnifiedCommandCenterReleaseTrainStore()
    store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    if args.action == "create-request":
        request = store.create_request(
            args.train_id,
            {
                "change_request_id": args.request_id,
                "requested_by": args.requested_by,
                "reason": args.reason,
                "change_type": args.change_type,
                "change_set": args.change,
                "external_evidence_manifest": args.external_evidence_manifest,
            },
        )
        return {"ok": True, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}
    if args.action == "approve":
        approval = store.approve_request(
            args.train_id,
            args.request_id,
            {
                "approved_by": args.approved_by,
                "role": args.role,
                "reason": args.reason,
                "external_evidence_manifest": args.external_evidence_manifest,
            },
        )
        return {"ok": approval.get("status") == "approved", "approval": approval, "summary": {"approval_hash": approval.get("integrity_hash")}, "status": approval.get("status")}
    if args.action == "reset":
        proof = store.reset_train_signoff(
            args.train_id,
            args.request_id,
            {
                "reset_by": args.reset_by,
                "reason": args.reason,
                "external_evidence_manifest": args.external_evidence_manifest,
            },
        )
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_event_hash": proof.get("reset_event_hash")}, "status": proof.get("status")}
    if args.action == "status":
        report = store.refresh_report(args.train_id) if store.change_dir(args.train_id).exists() else {"status": "not_configured", "summary": {}}
        return {"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_package(args.train_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.train_id,
            {
                "strict": args.strict,
                "require_reset_applied": args.require_reset_applied,
                "require_current_train": args.require_current_train,
                "train_archive": args.train_archive,
                "train_archive_verification_report": args.train_archive_verification_report,
                "train_signoff_binding": args.train_signoff_binding,
                "external_evidence_manifest": args.external_evidence_manifest,
                "reset_proof": args.reset_proof,
            },
        )
        if args.report_out is not None:
            write_unified_command_center_release_train_change_control_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train-change-control command.")

def _run_unified_command_center_release_train_lifecycle_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass
    pass
    pass

    train_store = UnifiedCommandCenterReleaseTrainStore()
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    store = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    if args.action == "status":
        report = store.read_report(args.train_id) if store.report_path(args.train_id).exists() else {"status": "not_configured", "summary": {}}
        return {"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    payload = _release_train_lifecycle_payload_from_args(args)
    if args.action == "refresh":
        report = store.refresh_report(args.train_id, payload)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_package(args.train_id, payload)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.train_id,
            {**payload, "strict": args.strict, "require_current_train": args.require_current_train, "require_change_control": args.require_change_control},
        )
        if args.report_out is not None:
            write_unified_command_center_release_train_lifecycle_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train-lifecycle command.")

def _run_unified_command_center_release_train_handoff_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass
    pass
    pass
    pass
    pass

    train_store = UnifiedCommandCenterReleaseTrainStore()
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    lifecycle_store = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    store = UnifiedCommandCenterReleaseTrainHandoffStore(train_store, change_store, lifecycle_store)
    handoff_id = getattr(args, "handoff_id", None)
    if args.action == "status":
        detail = store.get_handoff(args.train_id, handoff_id)
        report = detail.get("report", {})
        return {"ok": report.get("status") != "failed", **detail, "summary": report.get("summary", {}), "status": report.get("status")}
    payload = _release_train_handoff_payload_from_args(args)
    if args.action == "create":
        if getattr(args, "handoff_id", None):
            payload["handoff_id"] = args.handoff_id
        if getattr(args, "require_external_acceptance", False):
            payload["policy"] = {"require_external_acceptance": True}
        detail = store.create_handoff(args.train_id, payload)
        return {"ok": detail.get("report", {}).get("status") in {"ready", "manual_required"}, **detail, "summary": detail.get("report", {}).get("summary", {}), "status": detail.get("report", {}).get("status")}
    if args.action in {"refresh", "board"}:
        report = store.refresh_report(args.train_id, handoff_id, payload)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_handoff(args.train_id, handoff_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id, handoff_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.train_id,
            handoff_id,
            {
                **payload,
                "strict": args.strict,
                "require_current": args.require_current,
                "require_lifecycle": args.require_lifecycle,
                "require_signed": args.require_signed,
                "require_accepted": args.require_accepted,
                "handoff_signoff_binding": getattr(args, "handoff_signoff_binding", None),
                "accepted_evidence_dir": getattr(args, "accepted_evidence_dir", None),
            },
        )
        if args.report_out is not None:
            write_unified_command_center_release_train_handoff_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "import-response":
        response = store.import_response(args.train_id, args.handoff_id, read_json(args.response_json))
        return {"ok": response.get("verification", {}).get("status") == "passed", **response, "summary": response.get("verification", {}).get("summary", {}), "status": response.get("response", {}).get("decision")}
    if args.action == "accepted-evidence":
        evidence = store.create_accepted_evidence(args.train_id, args.handoff_id, args.response_id)
        return {"ok": True, "accepted_evidence": evidence, "summary": evidence.get("public_summary", {}), "status": "passed"}
    if args.action == "signoff":
        signoff = store.signoff(args.train_id, handoff_id, {**payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signed_by": signoff.get("signed_by")}, "status": signoff.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train-handoff command.")

def _run_unified_release_program_command(args: argparse.Namespace) -> ImplementationDocument:
    pass

    store = _program_component("program")
    if args.action == "create":
        policy = {}
        if getattr(args, "require_external_handoff_acceptance", False):
            policy["require_external_handoff_acceptance"] = True
        return {"program": store.create_program({"program_id": args.program_id, "name": args.name, "policy": policy})}
    if args.action == "add-train":
        return {
            "item": store.add_train_item(
                args.program_id,
                {
                    "item_id": args.item_id,
                    "train_id": args.train_id,
                    "handoff_id": args.handoff_id,
                    "type": args.type,
                    "lane": args.lane,
                    "wave": args.wave,
                    "depends_on": args.depends_on,
                    "handoff_zip": args.handoff_zip,
                    "handoff_verification_report": args.handoff_verification_report,
                    "handoff_signoff_binding": args.handoff_signoff_binding,
                    "accepted_evidence_dir": args.accepted_evidence_dir,
                },
            )
        }
    if args.action == "status":
        return store.get_program(args.program_id)
    if args.action == "refresh":
        return {"report": store.refresh_report(args.program_id, {"external_evidence_manifest": args.external_evidence_manifest})}
    if args.action == "export":
        return {"manifest": store.export_program(args.program_id)}
    if args.action == "zip":
        return {"zip": store.build_zip(args.program_id)}
    if args.action == "verify":
        report = store.verify_package(
            args.program_id,
            {
                "strict": args.strict,
                "require_current": args.require_current,
                "require_signed": args.require_signed,
                "external_evidence_manifest": args.external_evidence_manifest,
                "program_signoff_binding": args.program_signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_verification_report(report, args.report_out)
        return {"verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "signoff":
        return {"signoff": store.signoff(args.program_id, {"external_evidence_manifest": args.external_evidence_manifest, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})}
    if args.action == "gate":
        return {
            "gate": store.gate(
                program_zip_path=args.program_zip,
                verification_report_path=args.program_verification_report,
                external_evidence_manifest_path=args.external_evidence_manifest,
                program_signoff_binding_path=args.program_signoff_binding,
            )
        }
    raise ValueError("Unsupported unified-release-program command.")

def _unified_release_program_operations_payload_from_args(args: argparse.Namespace) -> ImplementationDocument:
    payload: dict[str, Any] = {
        "program_zip": getattr(args, "program_zip", None),
        "program_verification_report": getattr(args, "program_verification_report", None),
        "program_signoff_binding": getattr(args, "program_signoff_binding", None),
        "external_evidence_manifest": getattr(args, "external_evidence_manifest", None),
    }
    for name in ("change_request_id", "change_type", "reason", "requested_by", "approved_by", "role", "reset_by", "allowed_actions"):
        value = getattr(args, name, None)
        if value is not None:
            payload[name] = value
    return payload

def _run_unified_release_program_operations_command(args: argparse.Namespace) -> ImplementationDocument:
    pass


    store = _program_component("operations")
    payload = _unified_release_program_operations_payload_from_args(args)
    program_id = getattr(args, "program_id", None)
    if args.action == "change-request-create":
        request = store.create_change_request(program_id, payload)
        return {"ok": True, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}
    if args.action == "change-request-approve":
        approval = store.approve_change_request(program_id, args.change_request_id, payload)
        return {"ok": True, "approval": approval, "summary": {"change_request_id": approval.get("change_request_id")}, "status": approval.get("status")}
    if args.action == "reset-signoff":
        proof = store.reset_program_signoff(program_id, payload)
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_event_hash": proof.get("reset_event_hash")}, "status": proof.get("status")}
    if args.action == "runbook-create":
        runbook = store.create_runbook(program_id, payload)
        return {"ok": True, "runbook": runbook, "summary": runbook.get("summary", {}), "status": runbook.get("status")}
    if args.action == "runbook-run-safe":
        result = store.run_safe(program_id, args.runbook_id, payload)
        return {"ok": result.get("status") in {"completed", "completed_with_manual_actions"}, **result}
    if args.action == "continuous-review-refresh":
        review = store.refresh_continuous_review(program_id, payload)
        return {"ok": review.get("status") == "passed", "review": review, "summary": review.get("summary", {}), "status": review.get("status")}
    if args.action == "lifecycle-refresh":
        report = store.refresh_lifecycle_audit(program_id, payload)
        return {"ok": report.get("status") == "passed", "lifecycle": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "archive-export":
        manifest = store.export_operations_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_operations_archive_zip(program_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "archive-verify":
        report = store.verify_operations_archive_zip(
            program_id,
            {
                **payload,
                "strict": args.strict,
                "require_current": args.require_current,
                "require_signed_program": args.require_signed_program,
                "require_continuous_review_clear": args.require_continuous_review_clear,
                "require_lifecycle_audit": args.require_lifecycle_audit,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_operations_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            args.program_id,
            required=True,
            operations_archive_zip_path=args.operations_archive_zip,
            operations_archive_verification_report_path=args.operations_archive_verification_report,
            **payload,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-operations command.")

__all__ = ('_run_unified_command_center_release_train_change_control_command', '_run_unified_command_center_release_train_lifecycle_command', '_run_unified_command_center_release_train_handoff_command', '_run_unified_release_program_command', '_unified_release_program_operations_payload_from_args', '_run_unified_release_program_operations_command')
