from __future__ import annotations

from .dependencies import *

def build_verify_unified_release_program_vault_operations_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_vault_operations_parser')(*args, **kwargs)

def build_verify_unified_release_program_vault_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_vault_parser')(*args, **kwargs)

def print_acceptance_analytics_report(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_acceptance_analytics_report')(*args, **kwargs)

def print_acceptance_check_report(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_acceptance_check_report')(*args, **kwargs)

def print_acceptance_diff_report(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_acceptance_diff_report')(*args, **kwargs)

def print_acceptance_fix_plan_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_acceptance_fix_plan_result')(*args, **kwargs)

def print_acceptance_fix_sprint_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_acceptance_fix_sprint_result')(*args, **kwargs)

def print_acceptance_kb_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_acceptance_kb_result')(*args, **kwargs)

def print_planning_rule_governance_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_planning_rule_governance_result')(*args, **kwargs)

def print_planning_rule_impact_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_planning_rule_impact_result')(*args, **kwargs)

def print_planning_ruleset_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_planning_ruleset_result')(*args, **kwargs)

def print_planning_simulation_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_planning_simulation_result')(*args, **kwargs)

def print_public_trust_center_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_public_trust_center_result')(*args, **kwargs)

def print_release_audio_review_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_release_audio_review_result')(*args, **kwargs)

def print_release_portfolio_audit_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_audit_result')(*args, **kwargs)

def print_release_portfolio_governance_attestation_accepted_evidence_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_attestation_accepted_evidence_result')(*args, **kwargs)

def print_release_portfolio_governance_attestation_portal_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_attestation_portal_result')(*args, **kwargs)

def print_release_portfolio_governance_attestation_portal_review_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_attestation_portal_review_result')(*args, **kwargs)

def print_release_portfolio_governance_attestation_registry_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_attestation_registry_result')(*args, **kwargs)

def print_release_portfolio_governance_attestation_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_attestation_result')(*args, **kwargs)

def print_release_portfolio_governance_attestation_transparency_acknowledgement_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_attestation_transparency_acknowledgement_result')(*args, **kwargs)

def print_release_portfolio_governance_attestation_transparency_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_attestation_transparency_result')(*args, **kwargs)

def print_release_portfolio_governance_audit_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_audit_result')(*args, **kwargs)

def print_release_portfolio_governance_evidence_vault_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_evidence_vault_result')(*args, **kwargs)

def print_release_portfolio_governance_final_board_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_final_board_result')(*args, **kwargs)

def print_release_portfolio_governance_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_result')(*args, **kwargs)

def print_release_portfolio_governance_reviewer_pack_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_reviewer_pack_result')(*args, **kwargs)

def print_release_portfolio_governance_signoff_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_release_portfolio_governance_signoff_result')(*args, **kwargs)

def run_acceptance_check(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'run_acceptance_check')(*args, **kwargs)

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

def _release_train_lifecycle_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
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
