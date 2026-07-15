from __future__ import annotations

from . import dependencies as _commands_program_parts_dependencies; Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = (_commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report)

from .program_component_and_cross_domain_adapters import _print_release_audio_certification_result

from .verify_unified_release_program_continuity import build_unified_release_program_continuity_acceptance_change_parser, build_unified_release_program_continuity_command_center_acceptance_parser, build_unified_release_program_continuity_command_center_parser, build_unified_release_program_continuity_command_center_signoff_parser

from .unified_release_program_continuity_command_center_acceptance_change import build_unified_release_program_continuity_command_center_acceptance_change_parser

from .unified_release_program_continuity_acceptance_command import _run_unified_release_program_continuity_acceptance_change_command, _run_unified_release_program_continuity_command_center_acceptance_command, _run_unified_release_program_continuity_command_center_command, _run_unified_release_program_continuity_command_center_signoff_command

from .unified_release_program_continuity_command_center_acceptance_change_command import _run_unified_release_program_continuity_command_center_acceptance_change_command

def _execute_unified_release_program_continuity_acceptance_change(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-acceptance-change', *argv]
    parser = build_unified_release_program_continuity_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_acceptance_change_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_acceptance_change(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_acceptance_change(argv)

def _execute_unified_release_program_continuity_command_center(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center', *argv]
    parser = build_unified_release_program_continuity_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center(argv)

def _execute_unified_release_program_continuity_command_center_signoff(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-signoff', *argv]
    parser = build_unified_release_program_continuity_command_center_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_signoff_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center_signoff(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_signoff(argv)

def _execute_unified_release_program_continuity_command_center_acceptance(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-acceptance', *argv]
    parser = build_unified_release_program_continuity_command_center_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_acceptance_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center_acceptance(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_acceptance(argv)

def _execute_unified_release_program_continuity_command_center_acceptance_change(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-acceptance-change', *argv]
    parser = build_unified_release_program_continuity_command_center_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_acceptance_change_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return

def handle_unified_release_program_continuity_command_center_acceptance_change(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_acceptance_change(argv)

__all__ = ('_execute_unified_release_program_continuity_acceptance_change', 'handle_unified_release_program_continuity_acceptance_change', '_execute_unified_release_program_continuity_command_center', 'handle_unified_release_program_continuity_command_center', '_execute_unified_release_program_continuity_command_center_signoff', 'handle_unified_release_program_continuity_command_center_signoff', '_execute_unified_release_program_continuity_command_center_acceptance', 'handle_unified_release_program_continuity_command_center_acceptance', '_execute_unified_release_program_continuity_command_center_acceptance_change', 'handle_unified_release_program_continuity_command_center_acceptance_change')
