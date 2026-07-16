from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_program_parts_dependencies; Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = (_commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report)

from .program_component_and_cross_domain_adapters import _command_center_acceptance_payload, _print_release_audio_certification_result, _program_component

from .unified_command_center import build_unified_command_center_drift_response_parser, build_unified_command_center_evidence_review_parser, build_unified_command_center_parser, build_unified_command_center_review_parser

from .unified_command_center_reviewer_decision_board import build_unified_command_center_release_train_change_control_parser, build_unified_command_center_release_train_handoff_parser, build_unified_command_center_release_train_lifecycle_parser, build_unified_command_center_release_train_parser, build_unified_command_center_reviewer_decision_board_parser, build_unified_release_program_parser

from .unified_release_program_operations import build_unified_release_program_continuity_parser, build_unified_release_program_handoff_parser, build_unified_release_program_operations_parser, build_unified_release_program_vault_operations_parser, build_unified_release_program_vault_parser

from .verify_unified_release_program_continuity import build_unified_release_program_continuity_acceptance_parser, build_unified_release_program_continuity_distribution_parser

from .unified_release_program_continuity_command_center_acceptance_change import _run_unified_command_center_command, _run_unified_command_center_review_command

from .unified_command_center_drift_response_command import _run_unified_command_center_drift_response_command, _run_unified_command_center_evidence_review_command, _run_unified_command_center_release_train_command, _run_unified_command_center_reviewer_decision_board_command

from .unified_command_center_release_train_change_control_command import _run_unified_command_center_release_train_change_control_command, _run_unified_command_center_release_train_handoff_command, _run_unified_command_center_release_train_lifecycle_command, _run_unified_release_program_command, _run_unified_release_program_operations_command

from .unified_release_program_handoff_command import _run_unified_release_program_continuity_command, _run_unified_release_program_continuity_distribution_command, _run_unified_release_program_handoff_command, _run_unified_release_program_vault_command, _run_unified_release_program_vault_operations_command

from .unified_release_program_continuity_acceptance_command import _run_unified_release_program_continuity_acceptance_command

def _run_unified_release_program_continuity_command_center_acceptance_change_command(args: argparse.Namespace) -> ImplementationDocument:

    store = _program_component("receiver_acceptance_change")
    program_id = args.program_id
    payload = {
        **_command_center_acceptance_payload(args),
        "archive_zip": args.archive_zip,
        "acceptance_archive": args.acceptance_archive,
        "acceptance_verification_report": args.acceptance_verification_report,
        "acceptance_signoff_binding": args.acceptance_signoff_binding,
        "previous_acceptance_root": args.previous_acceptance_root,
        "strict": args.strict,
        "require_current_acceptance": args.require_current or True,
        "require_reset_proofs": args.require_reset_proofs or True,
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    if args.action == "status":
        state = store.get_state(program_id)
        return {"ok": True, **state, "status": (state.get("state") or {}).get("status") or "not_configured"}
    if args.action == "create-cr":
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
        return {"ok": True, "change_request": request, "status": request.get("status"), "summary": {"change_request_id": request.get("change_request_id")}}
    if args.action == "approve-cr":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for approve-cr.")
        approval = store.approve_change_request(
            program_id,
            args.change_request_id,
            {"approved_by": args.approved_by, "role": args.role, "reason": args.reason, "approved_actions": args.approved_action or None},
        )
        return {"ok": True, "approval": approval, "status": approval.get("status"), "summary": {"approval_hash": approval.get("integrity_hash")}}
    if args.action == "reset-signoff":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for reset-signoff.")
        proof = store.reset_receiver_acceptance_signoff(
            program_id,
            args.change_request_id,
            {"reset_by": args.reset_by, "reason": args.reason},
        )
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "status": proof.get("status"), "summary": {"reset_proof_hash": proof.get("integrity_hash")}}
    if args.action == "refresh-lifecycle":
        report = store.refresh_lifecycle_audit(program_id, payload)
        return {"ok": report.get("status") == "passed", "lifecycle_report": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "export":
        manifest = store.export_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "zip":
        result = store.build_archive_zip(program_id, payload)
        return {"ok": result.get("status") == "passed", **result}
    if args.action == "verify":
        report = store.verify_archive_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            **payload,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})}
    raise ValueError("Unsupported unified-release-program-continuity-command-center-acceptance-change command.")

def _execute_unified_command_center(argv: list[str]) -> None:
    raw_args = ['unified-command-center', *argv]
    parser = build_unified_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "runtime_failed", "verification_failed"}:
        raise SystemExit(1)
    return

def handle_unified_command_center(argv: list[str]) -> None:
    _execute_unified_command_center(argv)

def _execute_unified_command_center_review(argv: list[str]) -> None:
    raw_args = ['unified-command-center-review', *argv]
    parser = build_unified_command_center_review_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_review_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_review(argv: list[str]) -> None:
    _execute_unified_command_center_review(argv)

def _execute_unified_command_center_drift_response(argv: list[str]) -> None:
    raw_args = ['unified-command-center-drift-response', *argv]
    parser = build_unified_command_center_drift_response_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_drift_response_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_drift_response(argv: list[str]) -> None:
    _execute_unified_command_center_drift_response(argv)

def _execute_unified_command_center_evidence_review(argv: list[str]) -> None:
    raw_args = ['unified-command-center-evidence-review', *argv]
    parser = build_unified_command_center_evidence_review_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_evidence_review_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_evidence_review(argv: list[str]) -> None:
    _execute_unified_command_center_evidence_review(argv)

def _execute_unified_command_center_reviewer_decision_board(argv: list[str]) -> None:
    raw_args = ['unified-command-center-reviewer-decision-board', *argv]
    parser = build_unified_command_center_reviewer_decision_board_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_reviewer_decision_board_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_reviewer_decision_board(argv: list[str]) -> None:
    _execute_unified_command_center_reviewer_decision_board(argv)

def _execute_unified_command_center_release_train(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train', *argv]
    parser = build_unified_command_center_release_train_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_release_train(argv: list[str]) -> None:
    _execute_unified_command_center_release_train(argv)

def _execute_unified_command_center_release_train_change_control(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train-change-control', *argv]
    parser = build_unified_command_center_release_train_change_control_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_change_control_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_release_train_change_control(argv: list[str]) -> None:
    _execute_unified_command_center_release_train_change_control(argv)

def _execute_unified_command_center_release_train_lifecycle(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train-lifecycle', *argv]
    parser = build_unified_command_center_release_train_lifecycle_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_lifecycle_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_release_train_lifecycle(argv: list[str]) -> None:
    _execute_unified_command_center_release_train_lifecycle(argv)

def _execute_unified_command_center_release_train_handoff(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train-handoff', *argv]
    parser = build_unified_command_center_release_train_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_handoff_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_command_center_release_train_handoff(argv: list[str]) -> None:
    _execute_unified_command_center_release_train_handoff(argv)

def _execute_unified_release_program(argv: list[str]) -> None:
    raw_args = ['unified-release-program', *argv]
    parser = build_unified_release_program_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program(argv: list[str]) -> None:
    _execute_unified_release_program(argv)

def _execute_unified_release_program_operations(argv: list[str]) -> None:
    raw_args = ['unified-release-program-operations', *argv]
    parser = build_unified_release_program_operations_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_operations_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_operations(argv: list[str]) -> None:
    _execute_unified_release_program_operations(argv)

def _execute_unified_release_program_handoff(argv: list[str]) -> None:
    raw_args = ['unified-release-program-handoff', *argv]
    parser = build_unified_release_program_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_handoff_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_handoff(argv: list[str]) -> None:
    _execute_unified_release_program_handoff(argv)

def _execute_unified_release_program_vault(argv: list[str]) -> None:
    raw_args = ['unified-release-program-vault', *argv]
    parser = build_unified_release_program_vault_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_vault_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_vault(argv: list[str]) -> None:
    _execute_unified_release_program_vault(argv)

def _execute_unified_release_program_vault_ops(argv: list[str]) -> None:
    raw_args = ['unified-release-program-vault-ops', *argv]
    parser = build_unified_release_program_vault_operations_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_vault_operations_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_vault_ops(argv: list[str]) -> None:
    _execute_unified_release_program_vault_ops(argv)

def _execute_unified_release_program_continuity(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity', *argv]
    parser = build_unified_release_program_continuity_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity(argv: list[str]) -> None:
    _execute_unified_release_program_continuity(argv)

def _execute_unified_release_program_continuity_kit(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-kit', *argv]
    parser = build_unified_release_program_continuity_distribution_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_distribution_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_kit(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_kit(argv)

def _execute_unified_release_program_continuity_acceptance(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-acceptance', *argv]
    parser = build_unified_release_program_continuity_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_acceptance_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_acceptance(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_acceptance(argv)

__all__ = ('_run_unified_release_program_continuity_command_center_acceptance_change_command', '_execute_unified_command_center', 'handle_unified_command_center', '_execute_unified_command_center_review', 'handle_unified_command_center_review', '_execute_unified_command_center_drift_response', 'handle_unified_command_center_drift_response', '_execute_unified_command_center_evidence_review', 'handle_unified_command_center_evidence_review', '_execute_unified_command_center_reviewer_decision_board', 'handle_unified_command_center_reviewer_decision_board', '_execute_unified_command_center_release_train', 'handle_unified_command_center_release_train', '_execute_unified_command_center_release_train_change_control', 'handle_unified_command_center_release_train_change_control', '_execute_unified_command_center_release_train_lifecycle', 'handle_unified_command_center_release_train_lifecycle', '_execute_unified_command_center_release_train_handoff', 'handle_unified_command_center_release_train_handoff', '_execute_unified_release_program', 'handle_unified_release_program', '_execute_unified_release_program_operations', 'handle_unified_release_program_operations', '_execute_unified_release_program_handoff', 'handle_unified_release_program_handoff', '_execute_unified_release_program_vault', 'handle_unified_release_program_vault', '_execute_unified_release_program_vault_ops', 'handle_unified_release_program_vault_ops', '_execute_unified_release_program_continuity', 'handle_unified_release_program_continuity', '_execute_unified_release_program_continuity_kit', 'handle_unified_release_program_continuity_kit', '_execute_unified_release_program_continuity_acceptance', 'handle_unified_release_program_continuity_acceptance')
