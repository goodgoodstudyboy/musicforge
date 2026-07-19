from __future__ import annotations


from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.interfaces.cli.bindings import BINDINGS as CLI_BINDINGS

from . import dependencies as _commands_delivery_parts_dependencies
Any, AudioEncodingProfileStore, AudioEncodingStore, CommandSpec, DistributionStore, Path, ProjectStore, ProviderConfig, ProviderError, ReleaseOperationsAuditStore, ReleaseOperationsReviewerPackStore, ReleaseOperationsRunbookStore, ReleaseOperationsSignoffStore, ReleaseOperationsStore, ReleaseStore, SongRequest, SubmissionEvidenceStore, SubmissionStore, argparse, audit_summary, build_auth_config, command_center_signoff_verification_exit_code, distribution_verification_exit_code, generate_request, json, load_provider_config, operations_report_summary, operations_signoff_summary, os, print_distribution_verification_report, print_release_operations_archive_verification_report, print_release_operations_audit_verification_report, print_release_operations_reviewer_pack_verification_report, print_release_operations_runbook_verification_report, print_release_operations_verification_report, print_submission_evidence_verification_report, print_submission_verification_report, print_verification_report, provider_configured, read_json, release_operations_archive_verification_exit_code, release_operations_archive_verification_summary, release_operations_audit_verification_exit_code, release_operations_audit_verification_summary, release_operations_reviewer_pack_verification_exit_code, release_operations_reviewer_pack_verification_summary, release_operations_runbook_verification_exit_code, release_operations_runbook_verification_summary, release_operations_verification_exit_code, release_operations_verification_summary, release_verification_exit_code, retrospective_summary, reviewer_pack_summary, runbook_summary, submission_evidence_verification_exit_code, submission_verification_exit_code, sys, test_provider_config, unified_command_center_release_train_change_control_verification_exit_code, unified_command_center_release_train_handoff_verification_exit_code, unified_command_center_release_train_lifecycle_verification_exit_code, unified_command_center_release_train_verification_exit_code, unified_release_program_continuity_command_center_verification_exit_code, unified_release_program_continuity_distribution_verification_exit_code, unified_release_program_continuity_verification_exit_code, unified_release_program_handoff_verification_exit_code, unified_release_program_operations_verification_exit_code, unified_release_program_vault_operations_verification_exit_code, unified_release_program_vault_verification_exit_code, unified_release_program_verification_exit_code, verify_distribution_package, verify_release_operations_archive_package, verify_release_operations_audit_package, verify_release_operations_package, verify_release_operations_reviewer_pack, verify_release_operations_runbook_package, verify_release_zip, verify_submission_evidence_package, verify_submission_package, verify_unified_command_center_release_train_change_control_package, verify_unified_command_center_release_train_handoff_package, verify_unified_command_center_release_train_lifecycle_package, verify_unified_command_center_release_train_package, verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_package, verify_unified_release_program_continuity_command_center_signoff_package, verify_unified_release_program_continuity_distribution_package, verify_unified_release_program_continuity_package, verify_unified_release_program_handoff_package, verify_unified_release_program_operations_package, verify_unified_release_program_package, verify_unified_release_program_vault_operations_package, verify_unified_release_program_vault_package, write_distribution_verification_report, write_interface_document, write_json, write_release_operations_archive_verification_report, write_release_operations_audit_verification_report, write_release_operations_reviewer_pack_verification_report, write_release_operations_runbook_verification_report, write_submission_evidence_verification_report, write_submission_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report, write_verification_report = _commands_delivery_parts_dependencies.Any, _commands_delivery_parts_dependencies.AudioEncodingProfileStore, _commands_delivery_parts_dependencies.AudioEncodingStore, _commands_delivery_parts_dependencies.CommandSpec, _commands_delivery_parts_dependencies.DistributionStore, _commands_delivery_parts_dependencies.Path, _commands_delivery_parts_dependencies.ProjectStore, _commands_delivery_parts_dependencies.ProviderConfig, _commands_delivery_parts_dependencies.ProviderError, _commands_delivery_parts_dependencies.ReleaseOperationsAuditStore, _commands_delivery_parts_dependencies.ReleaseOperationsReviewerPackStore, _commands_delivery_parts_dependencies.ReleaseOperationsRunbookStore, _commands_delivery_parts_dependencies.ReleaseOperationsSignoffStore, _commands_delivery_parts_dependencies.ReleaseOperationsStore, _commands_delivery_parts_dependencies.ReleaseStore, _commands_delivery_parts_dependencies.SongRequest, _commands_delivery_parts_dependencies.SubmissionEvidenceStore, _commands_delivery_parts_dependencies.SubmissionStore, _commands_delivery_parts_dependencies.argparse, _commands_delivery_parts_dependencies.audit_summary, _commands_delivery_parts_dependencies.build_auth_config, _commands_delivery_parts_dependencies.command_center_signoff_verification_exit_code, _commands_delivery_parts_dependencies.distribution_verification_exit_code, _commands_delivery_parts_dependencies.generate_request, _commands_delivery_parts_dependencies.json, _commands_delivery_parts_dependencies.load_provider_config, _commands_delivery_parts_dependencies.operations_report_summary, _commands_delivery_parts_dependencies.operations_signoff_summary, _commands_delivery_parts_dependencies.os, _commands_delivery_parts_dependencies.print_distribution_verification_report, _commands_delivery_parts_dependencies.print_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.print_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.print_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.print_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.print_release_operations_verification_report, _commands_delivery_parts_dependencies.print_submission_evidence_verification_report, _commands_delivery_parts_dependencies.print_submission_verification_report, _commands_delivery_parts_dependencies.print_verification_report, _commands_delivery_parts_dependencies.provider_configured, _commands_delivery_parts_dependencies.read_json, _commands_delivery_parts_dependencies.release_operations_archive_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_archive_verification_summary, _commands_delivery_parts_dependencies.release_operations_audit_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_audit_verification_summary, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_summary, _commands_delivery_parts_dependencies.release_operations_runbook_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_runbook_verification_summary, _commands_delivery_parts_dependencies.release_operations_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_verification_summary, _commands_delivery_parts_dependencies.release_verification_exit_code, _commands_delivery_parts_dependencies.retrospective_summary, _commands_delivery_parts_dependencies.reviewer_pack_summary, _commands_delivery_parts_dependencies.runbook_summary, _commands_delivery_parts_dependencies.submission_evidence_verification_exit_code, _commands_delivery_parts_dependencies.submission_verification_exit_code, _commands_delivery_parts_dependencies.sys, _commands_delivery_parts_dependencies.test_provider_config, _commands_delivery_parts_dependencies.unified_command_center_release_train_change_control_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_lifecycle_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_command_center_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_distribution_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_verification_exit_code, _commands_delivery_parts_dependencies.verify_distribution_package, _commands_delivery_parts_dependencies.verify_release_operations_archive_package, _commands_delivery_parts_dependencies.verify_release_operations_audit_package, _commands_delivery_parts_dependencies.verify_release_operations_package, _commands_delivery_parts_dependencies.verify_release_operations_reviewer_pack, _commands_delivery_parts_dependencies.verify_release_operations_runbook_package, _commands_delivery_parts_dependencies.verify_release_zip, _commands_delivery_parts_dependencies.verify_submission_evidence_package, _commands_delivery_parts_dependencies.verify_submission_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_change_control_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_handoff_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_lifecycle_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_final_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_signoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_distribution_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_package, _commands_delivery_parts_dependencies.verify_unified_release_program_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_package, _commands_delivery_parts_dependencies.write_distribution_verification_report, _commands_delivery_parts_dependencies.write_interface_document, _commands_delivery_parts_dependencies.write_json, _commands_delivery_parts_dependencies.write_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.write_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.write_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.write_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.write_submission_evidence_verification_report, _commands_delivery_parts_dependencies.write_submission_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_final_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_signoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_verification_report, _commands_delivery_parts_dependencies.write_verification_report
build_verify_unified_release_program_vault_operations_parser = CLI_BINDINGS.program.build_verify_unified_release_program_vault_operations_parser

build_verify_unified_release_program_vault_parser = CLI_BINDINGS.program.build_verify_unified_release_program_vault_parser

print_acceptance_analytics_report = CLI_BINDINGS.quality.print_acceptance_analytics_report

print_acceptance_check_report = CLI_BINDINGS.quality.print_acceptance_check_report

print_acceptance_diff_report = CLI_BINDINGS.quality.print_acceptance_diff_report

print_acceptance_fix_plan_result = CLI_BINDINGS.quality.print_acceptance_fix_plan_result

print_acceptance_fix_sprint_result = CLI_BINDINGS.quality.print_acceptance_fix_sprint_result

print_acceptance_kb_result = CLI_BINDINGS.quality.print_acceptance_kb_result

print_planning_rule_governance_result = CLI_BINDINGS.quality.print_planning_rule_governance_result

print_planning_rule_impact_result = CLI_BINDINGS.quality.print_planning_rule_impact_result

print_planning_ruleset_result = CLI_BINDINGS.quality.print_planning_ruleset_result

print_planning_simulation_result = CLI_BINDINGS.quality.print_planning_simulation_result

print_public_trust_center_result = CLI_BINDINGS.trust.print_public_trust_center_result

print_release_audio_review_result = CLI_BINDINGS.quality.print_release_audio_review_result

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

def build_verify_release_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict-order warnings as failures.")
    verify_parser.add_argument("--require-audio", action="store_true", help="Require each track to include song.wav.")
    verify_parser.add_argument("--require-human-review", action="store_true", help="Require release signoff to include manual WAV review evidence.")
    verify_parser.add_argument("--require-audio-revisions", action="store_true", help="Require Audio Revision Workbench closeout evidence.")
    verify_parser.add_argument("--require-stems", action="store_true", help="Require each track to include a stems manifest and declared stem MIDI files.")
    verify_parser.add_argument("--require-mastering", action="store_true", help="Require Mastering QA and selected mastered WAV evidence.")
    verify_parser.add_argument("--require-encoded-audio", action="store_true", help="Require encoded audio summary evidence.")
    verify_parser.add_argument("--require-encoded-audio-review", action="store_true", help="Require manual encoded audio review evidence.")
    verify_parser.add_argument("--require-format-decision", action="store_true", help="Require Release Format Decision evidence.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require Rights Clearance evidence.")
    verify_parser.add_argument("--require-audio-formats", default="", help="Comma-separated encoded audio profile ids to require.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_distribution_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Distribution Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Distribution Package ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-audio", action="store_true", help="Require exported package layout audio files.")
    verify_parser.add_argument("--require-artwork", action="store_true", help="Require exported package artwork.")
    verify_parser.add_argument("--require-encoded-audio", action="store_true", help="Require encoded audio evidence for package audio files.")
    verify_parser.add_argument("--require-encoded-audio-review", action="store_true", help="Require manual encoded audio review evidence for encoded package audio.")
    verify_parser.add_argument("--require-format-decision", action="store_true", help="Require Distribution format decision evidence.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require Rights Clearance evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_submission_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Submission Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Submission Package ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-submitted", action="store_true", help="Require every item to have submitted-or-later status.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require every item to be accepted.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require Rights Clearance evidence.")
    verify_parser.add_argument("--deep", action="store_true", help="Run the Distribution Package verifier on nested target ZIP files.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=1024, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=10000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_submission_evidence_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Submission Evidence Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Submission Evidence Package ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Run the Submission Package verifier on the nested submission ZIP.")
    verify_parser.add_argument("--require-submitted", action="store_true", help="Require every item to have submitted-or-later evidence.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require every item to be accepted.")
    verify_parser.add_argument("--require-rights-clearance", action="store_true", help="Require nested Rights Clearance evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=1024, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=10000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_operations_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require Operations current_stage to be accepted or archived.")
    verify_parser.add_argument("--require-submission-evidence", action="store_true", help="Require the Submission Evidence domain to be ready.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_release_operations_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Release Operations reports and packages.")
    parser.add_argument("--release-id", required=True, help="Release id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh and persist the Operations Report.")
    parser.add_argument("--export", action="store_true", help="Build the Operations Export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Operations ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Operations ZIP package.")
    parser.add_argument("--require-accepted", action="store_true", help="When verifying, require accepted stage.")
    parser.add_argument("--require-submission-evidence", action="store_true", help="When verifying, require Submission Evidence readiness.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_verify_release_operations_runbook_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Runbook Package ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Runbook ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-completed", action="store_true", help="Require completed or blocked runbook evidence with no failed auto-safe item.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require the exported runbook to be current.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_operations_archive_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_operations_audit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Audit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Audit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current passed/warning Audit Report evidence.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence.")
    verify_parser.add_argument("--require-archive", action="store_true", help="Require Operations Archive evidence in the ledger.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_operations_reviewer_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Operations Reviewer Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Operations Reviewer Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require usable Audit evidence.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence.")
    verify_parser.add_argument("--require-archive", action="store_true", help="Require verified Operations Archive evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_release_operations_runbook_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and run local MusicForge Release Operations Runbooks.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--runbook-id", default="", help="Runbook id for detail/run/export actions.")
    parser.add_argument("--create", action="store_true", help="Create a runbook from the current Operations Report.")
    parser.add_argument("--list", action="store_true", help="List runbooks.")
    parser.add_argument("--run-safe", action="store_true", help="Run auto-safe actions.")
    parser.add_argument("--refresh-stale", action="store_true", help="Refresh stale status.")
    parser.add_argument("--export", action="store_true", help="Export runbook evidence.")
    parser.add_argument("--zip", action="store_true", help="Build runbook evidence ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify runbook ZIP.")
    parser.add_argument("--archive", action="store_true", help="Archive the runbook.")
    parser.add_argument("--require-completed", action="store_true", help="When verifying, require completed runbook evidence.")
    parser.add_argument("--require-current", action="store_true", help="When verifying, require current runbook evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_operations_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign or reset local MusicForge Release Operations archive evidence.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--sign", action="store_true", help="Create Operations Signoff.")
    parser.add_argument("--reset", action="store_true", help="Reset Operations Signoff.")
    parser.add_argument("--signed-by", default="local-user", help="Signer name.")
    parser.add_argument("--force", action="store_true", help="Force signoff through non-hard warnings.")
    parser.add_argument("--override-reason", default="", help="Required with --force when warnings are force accepted.")
    parser.add_argument("--reason", default="", help="Reset reason.")
    parser.add_argument("--change-request-id", default="", help="Approved change request id for reset.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_operations_archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export and verify local MusicForge Release Operations Archive packages.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--export", action="store_true", help="Build Operations Archive export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Operations Archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Operations Archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_operations_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Operations Audit ledger packages.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Operations Audit ledger and report.")
    parser.add_argument("--entries", action="store_true", help="List ledger entries.")
    parser.add_argument("--graph", action="store_true", help="Print graph summary.")
    parser.add_argument("--export", action="store_true", help="Build Operations Audit export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Operations Audit ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Operations Audit ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-current", action="store_true", help="Require current Audit Report evidence when verifying.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence when verifying.")
    parser.add_argument("--require-archive", action="store_true", help="Require Operations Archive evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_operations_reviewer_pack_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Operations Reviewer Packs.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Reviewer Report and Retrospective.")
    parser.add_argument("--export", action="store_true", help="Build Reviewer Pack export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Reviewer Pack ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Reviewer Pack ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-audit", action="store_true", help="Require usable Audit evidence when verifying.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Operations Signoff evidence when verifying.")
    parser.add_argument("--require-archive", action="store_true", help="Require verified Operations Archive evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_encode_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render local encoded audio derivatives for a Release.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--profiles", default="wav_master", help="Comma-separated audio encoding profile ids.")
    parser.add_argument("--force", action="store_true", help="Re-render existing encoded audio.")
    parser.add_argument("--json", action="store_true", help="Print result JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write result JSON.")
    return parser

def _release_train_lifecycle_payload_from_args(args: argparse.Namespace) -> ImplementationDocument:
    return {
        "external_evidence_manifest": getattr(args, "external_evidence_manifest", None),
        "train_archive": getattr(args, "train_archive", None),
        "train_archive_verification_report": getattr(args, "train_archive_verification_report", None),
        "train_signoff_binding": getattr(args, "train_signoff_binding", None),
        "change_control_zip": getattr(args, "change_control_zip", None),
        "change_control_verification_report": getattr(args, "change_control_verification_report", None),
        "reset_proofs": [path for path in getattr(args, "reset_proof", []) if path],
    }

__all__ = ('build_verify_unified_release_program_vault_operations_parser', 'build_verify_unified_release_program_vault_parser', 'print_acceptance_analytics_report', 'print_acceptance_check_report', 'print_acceptance_diff_report', 'print_acceptance_fix_plan_result', 'print_acceptance_fix_sprint_result', 'print_acceptance_kb_result', 'print_planning_rule_governance_result', 'print_planning_rule_impact_result', 'print_planning_ruleset_result', 'print_planning_simulation_result', 'print_public_trust_center_result', 'print_release_audio_review_result', 'print_release_portfolio_audit_result', 'print_release_portfolio_governance_attestation_accepted_evidence_result', 'print_release_portfolio_governance_attestation_portal_result', 'print_release_portfolio_governance_attestation_portal_review_result', 'print_release_portfolio_governance_attestation_registry_result', 'print_release_portfolio_governance_attestation_result', 'print_release_portfolio_governance_attestation_transparency_acknowledgement_result', 'print_release_portfolio_governance_attestation_transparency_result', 'print_release_portfolio_governance_audit_result', 'print_release_portfolio_governance_evidence_vault_result', 'print_release_portfolio_governance_final_board_result', 'print_release_portfolio_governance_result', 'print_release_portfolio_governance_reviewer_pack_result', 'print_release_portfolio_governance_signoff_result', 'run_acceptance_check', 'build_verify_release_parser', 'build_verify_distribution_parser', 'build_verify_submission_parser', 'build_verify_submission_evidence_parser', 'build_verify_release_operations_parser', 'build_release_operations_parser', 'build_verify_release_operations_runbook_parser', 'build_verify_release_operations_archive_parser', 'build_verify_release_operations_audit_parser', 'build_verify_release_operations_reviewer_pack_parser', 'build_release_operations_runbook_parser', 'build_release_operations_signoff_parser', 'build_release_operations_archive_parser', 'build_release_operations_audit_parser', 'build_release_operations_reviewer_pack_parser', 'build_release_encode_parser', '_release_train_lifecycle_payload_from_args')
