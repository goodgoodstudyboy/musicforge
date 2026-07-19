from __future__ import annotations

from typing import Any as _InterfaceType

from song_agent.interfaces.cli.bindings import BINDINGS as CLI_BINDINGS

from . import dependencies as _commands_creation_parts_dependencies

from .cross_domain_adapters import _unified_command_center_evidence_from_args

from .program_trust_parser_adapters import build_verify_unified_command_center_archive_parser, build_verify_unified_command_center_handoff_parser, build_verify_unified_command_center_parser
Any, CommandSpec, Path, ProviderConfig, ProviderError, SongRequest, argparse, build_auth_config, evidence_to_verifier_kwargs, generate_request, human_review_verification_exit_code, json, load_provider_config, os, print_human_review_verification_report, provider_configured, read_json, sys, test_provider_config, unified_command_center_archive_verification_exit_code, unified_command_center_continuous_review_verification_exit_code, unified_command_center_drift_response_verification_exit_code, unified_command_center_evidence_review_verification_exit_code, unified_command_center_handoff_verification_exit_code, unified_command_center_reviewer_decision_board_verification_exit_code, unified_command_center_verification_exit_code, verify_human_review_pack, verify_unified_command_center_archive_package, verify_unified_command_center_continuous_review_package, verify_unified_command_center_drift_response_package, verify_unified_command_center_evidence_review_package, verify_unified_command_center_handoff_package, verify_unified_command_center_package, verify_unified_command_center_reviewer_decision_board_package, write_human_review_verification_report, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report = _commands_creation_parts_dependencies.Any, _commands_creation_parts_dependencies.CommandSpec, _commands_creation_parts_dependencies.Path, _commands_creation_parts_dependencies.ProviderConfig, _commands_creation_parts_dependencies.ProviderError, _commands_creation_parts_dependencies.SongRequest, _commands_creation_parts_dependencies.argparse, _commands_creation_parts_dependencies.build_auth_config, _commands_creation_parts_dependencies.evidence_to_verifier_kwargs, _commands_creation_parts_dependencies.generate_request, _commands_creation_parts_dependencies.human_review_verification_exit_code, _commands_creation_parts_dependencies.json, _commands_creation_parts_dependencies.load_provider_config, _commands_creation_parts_dependencies.os, _commands_creation_parts_dependencies.print_human_review_verification_report, _commands_creation_parts_dependencies.provider_configured, _commands_creation_parts_dependencies.read_json, _commands_creation_parts_dependencies.sys, _commands_creation_parts_dependencies.test_provider_config, _commands_creation_parts_dependencies.unified_command_center_archive_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_continuous_review_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_drift_response_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_evidence_review_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_handoff_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_reviewer_decision_board_verification_exit_code, _commands_creation_parts_dependencies.unified_command_center_verification_exit_code, _commands_creation_parts_dependencies.verify_human_review_pack, _commands_creation_parts_dependencies.verify_unified_command_center_archive_package, _commands_creation_parts_dependencies.verify_unified_command_center_continuous_review_package, _commands_creation_parts_dependencies.verify_unified_command_center_drift_response_package, _commands_creation_parts_dependencies.verify_unified_command_center_evidence_review_package, _commands_creation_parts_dependencies.verify_unified_command_center_handoff_package, _commands_creation_parts_dependencies.verify_unified_command_center_package, _commands_creation_parts_dependencies.verify_unified_command_center_reviewer_decision_board_package, _commands_creation_parts_dependencies.write_human_review_verification_report, _commands_creation_parts_dependencies.write_interface_document, _commands_creation_parts_dependencies.write_json, _commands_creation_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_creation_parts_dependencies.write_unified_command_center_verification_report
print_acceptance_check_report = CLI_BINDINGS.quality.print_acceptance_check_report

print_acceptance_diff_report = CLI_BINDINGS.quality.print_acceptance_diff_report

print_acceptance_fix_plan_result = CLI_BINDINGS.quality.print_acceptance_fix_plan_result

print_acceptance_fix_sprint_result = CLI_BINDINGS.quality.print_acceptance_fix_sprint_result

print_acceptance_kb_result = CLI_BINDINGS.quality.print_acceptance_kb_result

print_ga_readiness_report = CLI_BINDINGS.release_check.print_ga_readiness_report

print_planning_rule_governance_result = CLI_BINDINGS.quality.print_planning_rule_governance_result

print_planning_rule_impact_result = CLI_BINDINGS.quality.print_planning_rule_impact_result

print_planning_ruleset_result = CLI_BINDINGS.quality.print_planning_ruleset_result

print_planning_simulation_result = CLI_BINDINGS.quality.print_planning_simulation_result

print_public_trust_center_result = CLI_BINDINGS.trust.print_public_trust_center_result

print_release_audio_review_result = CLI_BINDINGS.quality.print_release_audio_review_result

print_release_operations_archive_result = CLI_BINDINGS.delivery.print_release_operations_archive_result

print_release_operations_audit_result = CLI_BINDINGS.delivery.print_release_operations_audit_result

print_release_operations_result = CLI_BINDINGS.delivery.print_release_operations_result

print_release_operations_reviewer_pack_result = CLI_BINDINGS.delivery.print_release_operations_reviewer_pack_result

print_release_operations_runbook_result = CLI_BINDINGS.delivery.print_release_operations_runbook_result

print_release_operations_signoff_result = CLI_BINDINGS.delivery.print_release_operations_signoff_result

print_release_portfolio_audit_result = CLI_BINDINGS.trust.print_release_portfolio_audit_result

print_release_portfolio_governance_attestation_accepted_evidence_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_accepted_evidence_result

print_release_portfolio_governance_attestation_portal_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_portal_result

print_release_portfolio_governance_attestation_portal_review_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_portal_review_result

print_release_portfolio_governance_attestation_registry_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_registry_result

print_release_portfolio_governance_attestation_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_result

print_release_portfolio_governance_attestation_transparency_acknowledgement_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_transparency_acknowledgement_result

print_release_portfolio_governance_attestation_transparency_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_transparency_result

print_release_portfolio_governance_audit_result = CLI_BINDINGS.trust.print_release_portfolio_governance_audit_result

print_release_portfolio_governance_evidence_vault_result = CLI_BINDINGS.trust.print_release_portfolio_governance_evidence_vault_result

print_release_portfolio_governance_final_board_result = CLI_BINDINGS.trust.print_release_portfolio_governance_final_board_result

print_release_portfolio_governance_result = CLI_BINDINGS.trust.print_release_portfolio_governance_result

print_release_portfolio_governance_reviewer_pack_result = CLI_BINDINGS.trust.print_release_portfolio_governance_reviewer_pack_result

print_release_portfolio_governance_signoff_result = CLI_BINDINGS.trust.print_release_portfolio_governance_signoff_result

run_acceptance_check = CLI_BINDINGS.quality.run_acceptance_check

run_doctor = CLI_BINDINGS.maintenance.run_doctor

def _add_generate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "request",
        type=Path,
        nargs="?",
        help="Path to a song request JSON file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Run output directory. Defaults to runs/<request-title-slug>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the normalized request without calling an LLM.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip graph steps whose expected artifacts already exist.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output directory instead of resuming it.",
    )
    parser.add_argument(
        "--pipeline-mode",
        choices=["single", "multinode"],
        default="single",
        help="Pipeline to run: single or multinode.",
    )

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a local MIDI song demo.")
    _add_generate_args(parser)
    return parser

def build_serve_parser() -> argparse.ArgumentParser:
    serve_parser = argparse.ArgumentParser(description="Start the local web panel.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    serve_parser.add_argument("--port", type=int, default=8787, help="Port to bind.")
    serve_parser.add_argument(
        "--access-token",
        default=None,
        help="Bearer token required for Studio/API access.",
    )
    return serve_parser

def build_generate_parser() -> argparse.ArgumentParser:
    generate_parser = argparse.ArgumentParser(
        description="Generate a MIDI song demo from a request JSON file."
    )
    _add_generate_args(generate_parser)
    return generate_parser

def generate_from_file(
    request_path: _InterfaceType,
    *,
    out_dir: _InterfaceType | None = None,
    dry_run: bool = False,
    resume: bool = False,
    force: bool = False,
    pipeline_mode: str = "single",
) -> tuple[_InterfaceType, _InterfaceType] | None:
    raw = json.loads(request_path.read_text(encoding="utf-8"))
    request = SongRequest.from_dict(raw)

    if dry_run:
        print(json.dumps(request.to_dict(), ensure_ascii=False, indent=2))
        return None

    plan_path, midi_path = generate_request(
        request,
        out_dir=out_dir,
        resume=resume,
        force=force,
        pipeline_mode=pipeline_mode,
    )
    print(f"Wrote song plan: {plan_path}")
    print(f"Wrote MIDI: {midi_path}")
    return plan_path, midi_path

def _execute_generate(argv: list[str]) -> None:
    raw_args = ['generate', *argv]
    parser = build_generate_parser()
    args = parser.parse_args(raw_args[1:])
    request_path = args.request
    if request_path is None:
        parser.error("the following arguments are required: request")

    generate_from_file(
        request_path,
        out_dir=args.out,
        dry_run=args.dry_run,
        resume=args.resume,
        force=args.force,
        pipeline_mode=args.pipeline_mode,
    )

def handle_generate(argv: list[str]) -> None:
    _execute_generate(argv)

def _execute_verify_unified_command_center_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-package', *argv]
    pass
    pass




    parser = build_verify_unified_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    evidence = _unified_command_center_evidence_from_args(args)
    report = verify_unified_command_center_package(
        args.zip_path,
        strict=args.strict,
        require_ready=args.require_ready,
        require_audio_ready=args.require_audio_ready,
        require_trust_ready=args.require_trust_ready,
        require_public_trust_ready=args.require_public_trust_ready,
        require_release_ready=args.require_release_ready,
        require_distribution_ready=args.require_distribution_ready,
        require_submission_ready=args.require_submission_ready,
        require_operations_ready=args.require_operations_ready,
        require_maintenance_ready=args.require_maintenance_ready,
        require_ga_ready=args.require_ga_ready,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
        **evidence_to_verifier_kwargs(evidence),
    )
    if args.report_out is not None:
        write_unified_command_center_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_verification_exit_code(report))

def handle_verify_unified_command_center_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_package(argv)

def _execute_verify_unified_command_center_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-archive-package', *argv]
    pass




    parser = build_verify_unified_command_center_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current_ucc=args.require_current_ucc,
        command_center_zip_path=args.command_center_zip,
        command_center_verification_report_path=args.command_center_verification_report,
        signoff_binding_path=args.signoff_binding,
    )
    if args.report_out is not None:
        write_unified_command_center_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Archive verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_archive_verification_exit_code(report))

def handle_verify_unified_command_center_archive_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_archive_package(argv)

def _execute_verify_unified_command_center_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-handoff-package', *argv]
    pass




    parser = build_verify_unified_command_center_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_archive=args.require_archive,
        archive_zip_path=args.archive_zip,
        archive_verification_report_path=args.archive_verification_report,
    )
    if args.report_out is not None:
        write_unified_command_center_handoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Final Handoff Pack verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_handoff_verification_exit_code(report))

def handle_verify_unified_command_center_handoff_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_handoff_package(argv)

__all__ = ('print_acceptance_check_report', 'print_acceptance_diff_report', 'print_acceptance_fix_plan_result', 'print_acceptance_fix_sprint_result', 'print_acceptance_kb_result', 'print_ga_readiness_report', 'print_planning_rule_governance_result', 'print_planning_rule_impact_result', 'print_planning_ruleset_result', 'print_planning_simulation_result', 'print_public_trust_center_result', 'print_release_audio_review_result', 'print_release_operations_archive_result', 'print_release_operations_audit_result', 'print_release_operations_result', 'print_release_operations_reviewer_pack_result', 'print_release_operations_runbook_result', 'print_release_operations_signoff_result', 'print_release_portfolio_audit_result', 'print_release_portfolio_governance_attestation_accepted_evidence_result', 'print_release_portfolio_governance_attestation_portal_result', 'print_release_portfolio_governance_attestation_portal_review_result', 'print_release_portfolio_governance_attestation_registry_result', 'print_release_portfolio_governance_attestation_result', 'print_release_portfolio_governance_attestation_transparency_acknowledgement_result', 'print_release_portfolio_governance_attestation_transparency_result', 'print_release_portfolio_governance_audit_result', 'print_release_portfolio_governance_evidence_vault_result', 'print_release_portfolio_governance_final_board_result', 'print_release_portfolio_governance_result', 'print_release_portfolio_governance_reviewer_pack_result', 'print_release_portfolio_governance_signoff_result', 'run_acceptance_check', 'run_doctor', '_add_generate_args', 'build_parser', 'build_serve_parser', 'build_generate_parser', 'generate_from_file', '_execute_generate', 'handle_generate', '_execute_verify_unified_command_center_package', 'handle_verify_unified_command_center_package', '_execute_verify_unified_command_center_archive_package', 'handle_verify_unified_command_center_archive_package', '_execute_verify_unified_command_center_handoff_package', 'handle_verify_unified_command_center_handoff_package')
