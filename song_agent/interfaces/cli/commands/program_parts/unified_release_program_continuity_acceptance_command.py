from __future__ import annotations

from argparse import Namespace

from song_agent.platform.contracts.coercion import as_document as _as_document
from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document

from . import dependencies as _commands_program_parts_dependencies

from song_agent.interfaces.cli.commands.program_parts.program_component_and_cross_domain_adapters import _program_component
from song_agent.interfaces.cli.commands.quality_parts.release_audio_command_center_command import _command_center_acceptance_payload
CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report
def _run_unified_release_program_continuity_acceptance_command(args: Namespace) -> JsonDocument:
    pass
    pass

    store = _program_component("continuity_acceptance")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_board(program_id)
        report = _as_document(detail.get("report"))
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or "unknown"}
    if args.action == "import-response":
        result = store.import_response(
            program_id,
            {
                "response": read_json(args.response_json),
                "response_verification_report": read_json(args.response_verification_report),
                "response_binding_summary": read_json(args.response_binding_summary),
            },
        )
        response = _as_document(result.get("response"))
        return {"ok": result.get("status") == "imported", **result, "summary": {"response_id": response.get("response_id")}, "status": result.get("status")}
    if args.action == "accept-evidence":
        result = store.create_accepted_evidence(program_id, args.response_id)
        evidence = _as_document(result.get("evidence"))
        return {"ok": result.get("status") == "accepted", **result, "summary": {"evidence_id": evidence.get("evidence_id")}, "status": result.get("status")}
    if args.action == "board":
        policy = read_json(args.policy_json) if args.policy_json else None
        board = store.refresh_decision_board(program_id, {"policy": policy} if policy else {})
        return {"ok": board.get("status") == "ready_for_signoff", "board": board, "summary": board.get("readiness", {}), "status": board.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_acceptance(program_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "export":
        manifest = store.export_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_archive_zip(
            program_id,
            {
                "archive_zip": args.archive_zip,
                "strict": args.strict,
                "require_current_kit": args.require_current_kit or True,
                "require_signed": args.require_signed or True,
                "require_quorum": args.require_quorum or True,
                "continuity_kit": args.continuity_kit,
                "continuity_kit_verification_report": args.continuity_kit_verification_report,
                "signoff_binding": args.signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_acceptance_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            continuity_kit=args.continuity_kit,
            continuity_kit_verification_report=args.continuity_kit_verification_report,
            signoff_binding=args.signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-acceptance command.")

def _run_unified_release_program_continuity_acceptance_change_command(args: Namespace) -> JsonDocument:
    pass

    store = _program_component("continuity_acceptance_change")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_state(program_id)
        state = _as_document(detail.get("state"))
        return {"ok": True, **detail, "summary": state, "status": state.get("status") or "unknown"}
    if args.action == "create-change-request":
        request = store.create_change_request(
            program_id,
            {
                "change_request_id": args.change_request_id,
                "change_type": args.change_type,
                "allowed_actions": args.allowed_action or None,
                "reason": args.reason,
                "requested_by": args.requested_by,
            },
        )
        return {"ok": request.get("status") in {"submitted", "approved"}, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}
    if args.action == "approve-change-request":
        approval = store.approve_change_request(
            program_id,
            args.change_request_id,
            {
                "approved_by": args.approved_by,
                "role": args.role,
                "reason": args.reason,
                "approved_actions": args.approved_action or None,
            },
        )
        return {"ok": approval.get("status") == "approved", "approval": approval, "summary": {"approval_hash": approval.get("integrity_hash")}, "status": approval.get("status")}
    if args.action == "reset-signoff":
        proof = store.reset_acceptance_signoff(program_id, args.change_request_id, {"reset_by": args.reset_by, "reason": args.reason})
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_proof_hash": proof.get("integrity_hash")}, "status": proof.get("status")}
    if args.action == "lifecycle":
        report = store.refresh_lifecycle_audit(program_id)
        return {"ok": report.get("status") == "passed", "lifecycle_report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_archive_zip(
            program_id,
            {
                "archive_zip": args.archive_zip,
                "strict": args.strict,
                "require_current_acceptance": args.require_current_acceptance or True,
                "acceptance_archive": args.acceptance_archive,
                "acceptance_verification_report": args.acceptance_verification_report,
                "acceptance_signoff_binding": args.acceptance_signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_acceptance_change_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            acceptance_archive=args.acceptance_archive,
            acceptance_verification_report=args.acceptance_verification_report,
            acceptance_signoff_binding=args.acceptance_signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-acceptance-change command.")

def _run_unified_release_program_continuity_command_center_command(args: Namespace) -> JsonDocument:
    pass

    store = _program_component("command_center")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_command_center(program_id)
        report = _as_document(detail.get("report"))
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or "unknown"}
    if args.action == "refresh":
        report = store.refresh_command_center(program_id)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "run-safe":
        result = store.run_safe(program_id)
        return {"ok": result.get("status") in {"passed", "warning"}, "runbook_result": result, "summary": result.get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        manifest = store.export_package(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_zip(
            program_id,
            {
                "command_center_zip": args.command_center_zip,
                "strict": args.strict,
                "deep": args.deep or True,
                "require_ready": args.require_ready or True,
                "evidence_manifest": args.evidence_manifest,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_command_center_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            command_center_zip_path=args.command_center_zip,
            verification_report_path=args.verification_report,
            evidence_manifest_path=args.evidence_manifest,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-command-center command.")

def _run_unified_release_program_continuity_command_center_signoff_command(args: Namespace) -> JsonDocument:

    store = _program_component("command_center_signoff")
    program_id = args.program_id
    payload = {
        "signed_by": args.signed_by,
        "role": args.role,
        "reason": args.reason,
        "change_request_id": args.change_request_id,
        "approved_by": args.approved_by,
        "reset_by": args.reset_by,
        "allowed_actions": args.allowed_action or None,
        "archive_zip": args.archive_zip,
        "archive_verification_report": args.archive_verification_report,
        "signoff_binding": args.signoff_binding,
        "command_center_zip": args.command_center,
        "command_center_verification_report": args.command_center_verification_report,
        "command_center_external_evidence_manifest": args.command_center_evidence_manifest,
    }
    payload = normalize_json_document({key: value for key, value in payload.items() if value is not None})
    if args.action == "status":
        state = store.get_state(program_id)
        return {"ok": True, **state, "summary": {"status": state.get("status")}}
    if args.action == "preflight":
        report = store.preflight(program_id, payload)
        return {"ok": report.get("status") == "passed", "preflight": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "sign":
        signoff = store.signoff(program_id, payload)
        return {"ok": True, "signoff": signoff, "status": signoff.get("status"), "summary": signoff.get("summary", {})}
    if args.action == "create-cr":
        request = store.create_change_request(program_id, payload)
        return {"ok": True, "change_request": request, "status": request.get("status"), "summary": {"change_request_id": request.get("change_request_id")}}
    if args.action == "approve-cr":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for approve-cr.")
        approval = store.approve_change_request(program_id, args.change_request_id, payload)
        return {"ok": True, "approval": approval, "status": approval.get("status"), "summary": {"change_request_id": args.change_request_id}}
    if args.action == "reset":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for reset.")
        proof = store.reset_signoff(program_id, args.change_request_id, payload)
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "status": proof.get("status"), "summary": {"reset_event_hash": proof.get("reset_event_hash")}}
    if args.action == "export":
        manifest = store.export_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "zip":
        return {"ok": True, **store.build_archive_zip(program_id, payload)}
    if args.action == "verify":
        report = store.verify_archive_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "handoff-export":
        manifest = store.export_final_handoff(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "handoff-zip":
        return {"ok": True, **store.build_final_handoff_zip(program_id, payload)}
    if args.action == "handoff-verify":
        report = store.verify_final_handoff_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            archive_verification_report_path=args.archive_verification_report,
            signoff_binding_path=args.signoff_binding,
            command_center_zip_path=args.command_center,
            command_center_verification_report_path=args.command_center_verification_report,
            command_center_external_evidence_manifest_path=args.command_center_evidence_manifest,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})}
    raise ValueError("Unsupported unified-release-program-continuity-command-center-signoff command.")

def _run_unified_release_program_continuity_command_center_acceptance_command(args: Namespace) -> JsonDocument:

    store = _program_component("receiver_acceptance")
    program_id = args.program_id
    payload = _command_center_acceptance_payload(args)
    if args.action == "status":
        state = store.status(program_id)
        return {"ok": True, **state}
    if args.action == "create-review-pack":
        return {"ok": True, **store.create_review_pack(program_id, payload)}
    if args.action == "verify-review-pack":
        report = store.verify_review_pack(program_id, payload)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action in {"import-response", "import-response-base64"}:
        if args.response is not None:
            payload["response"] = read_json(args.response)
        if args.response_verification_report is not None:
            payload["response_verification_report"] = read_json(args.response_verification_report)
        if args.response_binding_summary is not None:
            payload["response_binding_summary"] = read_json(args.response_binding_summary)
        if args.response_base64:
            payload["response_base64"] = args.response_base64
        if args.response_zip_base64:
            payload["response_zip_base64"] = args.response_zip_base64
        result = store.import_response(program_id, payload)
        response = _as_document(result.get("response"))
        return {"ok": True, **result, "summary": {"response_id": response.get("response_id")}}
    if args.action == "create-accepted-evidence":
        if not args.response_id:
            raise ValueError("--response-id is required.")
        result = store.create_accepted_evidence(program_id, args.response_id, payload)
        return {"ok": True, **result}
    if args.action == "verify-accepted-evidence":
        if not args.response_id:
            raise ValueError("--response-id is required.")
        report = store.verify_accepted_evidence(program_id, args.response_id, payload)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "refresh-board":
        report = store.refresh_board(program_id, payload)
        return {"ok": report.get("status") == "ready_for_signoff", "report": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "signoff":
        signoff = store.signoff(program_id, payload)
        return {"ok": True, "signoff": signoff, "status": signoff.get("status"), "summary": {"signoff_hash": signoff.get("integrity_hash")}}
    if args.action == "export-archive":
        manifest = store.export_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "zip-archive":
        return {"ok": True, **store.build_archive_zip(program_id, payload)}
    if args.action == "verify-archive":
        report = store.verify_archive_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "gate":
        gate = store.gate(program_id, required=True, **payload)
        return {"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})}
    raise ValueError("Unsupported unified-release-program-continuity-command-center-acceptance command.")

__all__ = ('_run_unified_release_program_continuity_acceptance_command', '_run_unified_release_program_continuity_acceptance_change_command', '_run_unified_release_program_continuity_command_center_command', '_run_unified_release_program_continuity_command_center_signoff_command', '_run_unified_release_program_continuity_command_center_acceptance_command')
