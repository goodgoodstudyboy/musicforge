from __future__ import annotations

from . import dependencies as _commands_program_parts_dependencies; Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = (_commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report)

from .program_evidence_args_and_adapters import _add_unified_command_center_evidence_args, _add_unified_command_center_requirement_args

def build_unified_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage MusicForge Unified Command Center evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Unified Command Center.")
    create.add_argument("--center-id", default=None)
    create.add_argument("--name", default=None)
    create.add_argument("--scope", default="workspace")
    create.add_argument("--profile", default="ga")
    create.add_argument("--primary-release-id", default="")
    create.add_argument("--release-id", action="append", default=[])
    _add_unified_command_center_requirement_args(create)

    subparsers.add_parser("list", help="List Unified Command Centers.")

    for action, help_text in (
        ("status", "Show Unified Command Center status."),
        ("refresh", "Refresh Unified Command Center evidence."),
        ("report", "Show Unified Command Center report."),
        ("inventory", "Show evidence inventory."),
        ("readiness", "Show readiness matrix."),
        ("gap-plan", "Show gap plan."),
        ("runbook", "Show safe runbook."),
        ("run-safe", "Run only safe Unified Command Center actions."),
        ("export", "Export Unified Command Center package files."),
        ("zip", "Build Unified Command Center ZIP."),
        ("verify", "Verify Unified Command Center ZIP."),
        ("signoff", "Sign off a ready Unified Command Center."),
        ("archive", "Export signed Unified Command Center archive files."),
        ("archive-zip", "Build signed Unified Command Center archive ZIP."),
        ("verify-archive", "Verify signed Unified Command Center archive ZIP."),
        ("handoff", "Export Final Handoff Pack files."),
        ("handoff-zip", "Build Final Handoff Pack ZIP."),
        ("verify-handoff", "Verify Final Handoff Pack ZIP."),
    ):
        cmd = subparsers.add_parser(action, help=help_text)
        cmd.add_argument("center_id")
        if action in {"refresh", "runbook", "run-safe", "export", "zip", "verify"}:
            _add_unified_command_center_evidence_args(cmd)
            _add_unified_command_center_requirement_args(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-ready", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "signoff":
            cmd.add_argument("--signed-by", default="release-owner")
            cmd.add_argument("--role", default="release_owner")
            cmd.add_argument("--reason", default="Unified Command Center approved for handoff.")
        if action == "verify-archive":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--no-require-current-ucc", dest="require_current_ucc", action="store_false", default=True)
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "verify-handoff":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--no-require-archive", dest="require_archive", action="store_false", default=True)
            cmd.add_argument("--report-out", type=Path, default=None)

    cr_create = subparsers.add_parser("change-request-create", help="Create a Unified Command Center signoff reset Change Request.")
    cr_create.add_argument("center_id")
    cr_create.add_argument("--created-by", default="developer")
    cr_create.add_argument("--reason", required=True)
    cr_create.add_argument("--risk", default="medium")
    cr_approve = subparsers.add_parser("change-request-approve", help="Approve a Unified Command Center signoff reset Change Request.")
    cr_approve.add_argument("center_id")
    cr_approve.add_argument("change_request_id")
    cr_approve.add_argument("--approved-by", default="reviewer")
    cr_approve.add_argument("--reason", default=None)
    reset = subparsers.add_parser("signoff-reset", help="Reset Unified Command Center signoff with an approved Change Request.")
    reset.add_argument("center_id")
    reset.add_argument("change_request_id")
    reset.add_argument("--reason", default=None)
    return parser

def build_verify_unified_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--require-audio-ready", action="store_true")
    parser.add_argument("--require-trust-ready", action="store_true")
    parser.add_argument("--require-public-trust-ready", action="store_true")
    parser.add_argument("--require-release-ready", action="store_true")
    parser.add_argument("--require-distribution-ready", action="store_true")
    parser.add_argument("--require-submission-ready", action="store_true")
    parser.add_argument("--require-operations-ready", action="store_true")
    parser.add_argument("--require-maintenance-ready", action="store_true")
    parser.add_argument("--require-ga-ready", action="store_true")
    _add_unified_command_center_evidence_args(parser)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_verify_unified_command_center_archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-current-ucc", action="store_true")
    parser.add_argument("--command-center-zip", type=Path, default=None)
    parser.add_argument("--command-center-verification-report", type=Path, default=None)
    parser.add_argument("--signoff-binding", type=Path, default=None)
    return parser

def build_verify_unified_command_center_handoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Final Handoff Pack ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-archive", action="store_true")
    parser.add_argument("--archive-zip", type=Path, default=None)
    parser.add_argument("--archive-verification-report", type=Path, default=None)
    return parser

def _add_unified_command_center_review_evidence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--archive", dest="archive_zip", type=Path, default=None, help="Unified Command Center Archive ZIP.")
    parser.add_argument("--archive-verification-report", type=Path, default=None, help="Unified Command Center Archive verification report.")
    parser.add_argument("--handoff", dest="handoff_zip", type=Path, default=None, help="Unified Command Center Handoff ZIP.")
    parser.add_argument("--handoff-verification-report", type=Path, default=None, help="Unified Command Center Handoff verification report.")
    parser.add_argument("--unified-command-center", dest="command_center_zip", type=Path, default=None, help="Unified Command Center ZIP.")
    parser.add_argument("--unified-command-center-verification-report", dest="command_center_verification_report", type=Path, default=None, help="Unified Command Center verification report.")
    parser.add_argument("--signoff-binding", type=Path, default=None, help="Unified Command Center signoff binding summary.")
    parser.add_argument("--ga-readiness-report", type=Path, default=None, help="GA readiness report.")
    parser.add_argument("--release-check-report", type=Path, default=None, help="Release-check report.")

def build_unified_command_center_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Continuous Review packages.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create a Continuous Review plan.")
    create.add_argument("center_id")
    create.add_argument("--review-id", default=None)
    create.add_argument("--created-by", default="release-owner")
    create.add_argument("--no-handoff", dest="include_handoff", action="store_false", default=True)
    _add_unified_command_center_review_evidence_args(create)
    subparsers.add_parser("list", help="List Continuous Reviews.").add_argument("center_id")
    for action in ("run", "export", "zip", "verify", "status"):
        cmd = subparsers.add_parser(action, help=f"{action} a Continuous Review.")
        cmd.add_argument("center_id")
        cmd.add_argument("review_id")
        if action in {"run", "export", "zip", "verify"}:
            _add_unified_command_center_review_evidence_args(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--no-require-clear", dest="require_clear", action="store_false", default=True)
            cmd.add_argument("--no-require-recovery-drill", dest="require_recovery_drill", action="store_false", default=True)
            cmd.add_argument("--no-require-current-review", dest="require_current_review", action="store_false", default=True)
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_command_center_continuous_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Continuous Review ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-clear", action="store_true")
    parser.add_argument("--require-recovery-drill", action="store_true")
    parser.add_argument("--require-current-review", action="store_true")
    _add_unified_command_center_review_evidence_args(parser)
    return parser

def _add_unified_command_center_drift_response_evidence_args(parser: argparse.ArgumentParser) -> None:
    _add_unified_command_center_review_evidence_args(parser)
    parser.add_argument("--source-review", dest="source_review_zip", type=Path, default=None, help="Source failed Continuous Review ZIP.")
    parser.add_argument("--source-review-verification-report", type=Path, default=None, help="Source failed Continuous Review verification report.")
    parser.add_argument("--recheck-review", dest="recheck_review_zip", type=Path, default=None, help="Clear recheck Continuous Review ZIP.")
    parser.add_argument("--recheck-review-verification-report", type=Path, default=None, help="Clear recheck Continuous Review verification report.")
    parser.add_argument("--change-request-binding-report", type=Path, default=None, help="External Drift Response Change Request binding report.")

def build_unified_command_center_drift_response_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Drift Response packages.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create a Drift Response from a failed Continuous Review.")
    create.add_argument("center_id")
    create.add_argument("source_review_id")
    create.add_argument("--response-id", default=None)
    create.add_argument("--created-by", default="release-owner")
    subparsers.add_parser("list", help="List Drift Responses.").add_argument("center_id")
    for action in ("status", "run-safe", "export", "zip", "verify", "closeout"):
        cmd = subparsers.add_parser(action, help=f"{action} a Drift Response.")
        cmd.add_argument("center_id")
        cmd.add_argument("response_id")
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--no-require-closed", dest="require_closed", action="store_false", default=True)
            cmd.add_argument("--no-require-recheck-clear", dest="require_recheck_clear", action="store_false", default=True)
            cmd.add_argument("--no-require-current-review", dest="require_current_review", action="store_false", default=True)
            cmd.add_argument("--report-out", type=Path, default=None)
            _add_unified_command_center_drift_response_evidence_args(cmd)
        if action == "closeout":
            cmd.add_argument("--closed-by", default="release-owner")
            cmd.add_argument("--reason", default="Drift response closed after clear recheck.")
    bind_cr = subparsers.add_parser("bind-cr", help="Bind an approved Change Request to a manual response item.")
    bind_cr.add_argument("center_id")
    bind_cr.add_argument("response_id")
    bind_cr.add_argument("item_id")
    bind_cr.add_argument("--change-request-id", required=True)
    bind_cr.add_argument("--approved-by", default="reviewer")
    bind_cr.add_argument("--reason", default="Approved drift response manual action.")
    bind_recheck = subparsers.add_parser("bind-recheck", help="Bind a clear Continuous Review recheck.")
    bind_recheck.add_argument("center_id")
    bind_recheck.add_argument("response_id")
    bind_recheck.add_argument("recheck_review_id")
    bind_recheck.add_argument("--recheck-review", dest="recheck_review_zip", type=Path, default=None)
    bind_recheck.add_argument("--recheck-review-verification-report", type=Path, default=None)
    return parser

def build_verify_unified_command_center_drift_response_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Drift Response ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--require-recheck-clear", action="store_true")
    parser.add_argument("--require-current-review", action="store_true")
    _add_unified_command_center_drift_response_evidence_args(parser)
    return parser

def _add_unified_command_center_evidence_review_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--unified-command-center", dest="ucc_zip", type=Path, default=None, help="Unified Command Center ZIP.")
    parser.add_argument("--unified-command-center-verification-report", dest="ucc_verification_report", type=Path, default=None, help="Unified Command Center verification report.")
    parser.add_argument("--archive", dest="archive_zip", type=Path, default=None, help="Unified Command Center Archive ZIP.")
    parser.add_argument("--archive-verification-report", type=Path, default=None, help="Unified Command Center Archive verification report.")
    parser.add_argument("--handoff", dest="handoff_zip", type=Path, default=None, help="Final Handoff Pack ZIP.")
    parser.add_argument("--handoff-verification-report", type=Path, default=None, help="Final Handoff Pack verification report.")
    parser.add_argument("--continuous-review", dest="continuous_review_zip", type=Path, default=None, help="Unified Command Center Continuous Review ZIP.")
    parser.add_argument("--continuous-review-verification-report", type=Path, default=None, help="Unified Command Center Continuous Review verification report.")
    parser.add_argument("--continuous-review-id", default=None, help="Continuous Review id to bind when paths are omitted.")
    parser.add_argument("--source-review", dest="source_review_zip", type=Path, default=None, help="Source Continuous Review ZIP for Drift Response replay.")
    parser.add_argument("--source-review-verification-report", type=Path, default=None, help="Source Continuous Review verification report.")
    parser.add_argument("--recheck-review", dest="recheck_review_zip", type=Path, default=None, help="Recheck Continuous Review ZIP for Drift Response replay.")
    parser.add_argument("--recheck-review-verification-report", type=Path, default=None, help="Recheck Continuous Review verification report.")
    parser.add_argument("--recheck-review-id", default=None, help="Recheck Continuous Review id to bind when paths are omitted.")
    parser.add_argument("--drift-response", dest="drift_response_zip", type=Path, default=None, help="Unified Command Center Drift Response ZIP.")
    parser.add_argument("--drift-response-verification-report", type=Path, default=None, help="Unified Command Center Drift Response verification report.")
    parser.add_argument("--drift-response-id", default=None, help="Drift Response id to bind when paths are omitted.")
    parser.add_argument("--drift-change-request-binding-report", type=Path, default=None, help="External Drift Response Change Request binding report.")
    parser.add_argument("--signoff-binding", type=Path, default=None, help="Unified Command Center signoff binding summary.")
    parser.add_argument("--ga-readiness-report", type=Path, default=None, help="GA readiness report.")
    parser.add_argument("--release-check-report", type=Path, default=None, help="Release-check report.")

def build_unified_command_center_evidence_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Evidence Review / Replay packages.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create an Evidence Review plan.")
    create.add_argument("center_id")
    create.add_argument("--review-id", default=None)
    _add_unified_command_center_evidence_review_args(create)
    subparsers.add_parser("list", help="List Evidence Reviews.").add_argument("center_id")
    for action in ("status", "refresh", "replay", "export", "zip", "verify"):
        cmd = subparsers.add_parser(action, help=f"{action} an Evidence Review.")
        cmd.add_argument("center_id")
        cmd.add_argument("review_id")
        if action in {"refresh", "replay", "export", "zip", "verify"}:
            _add_unified_command_center_evidence_review_args(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--no-require-replay-passed", dest="require_replay_passed", action="store_false", default=True)
            cmd.add_argument("--report-out", type=Path, default=None)
    import_response = subparsers.add_parser("import-response", help="Import an external reviewer response JSON.")
    import_response.add_argument("center_id")
    import_response.add_argument("review_id")
    source = import_response.add_mutually_exclusive_group(required=True)
    source.add_argument("--response-json", type=Path, default=None)
    source.add_argument("--response-base64", default=None)
    acceptance = subparsers.add_parser("acceptance-evidence", help="Create accepted-response evidence.")
    acceptance.add_argument("center_id")
    acceptance.add_argument("review_id")
    acceptance.add_argument("response_id")
    verify_acceptance = subparsers.add_parser("verify-acceptance", help="Verify accepted-response evidence.")
    verify_acceptance.add_argument("center_id")
    verify_acceptance.add_argument("review_id")
    verify_acceptance.add_argument("evidence_id")
    verify_acceptance.add_argument("--strict", action="store_true")
    verify_acceptance.add_argument("--no-require-accepted", dest="require_accepted", action="store_false", default=True)
    verify_acceptance.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_command_center_evidence_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Evidence Review ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-replay-passed", action="store_true")
    _add_unified_command_center_evidence_review_args(parser)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_verify_unified_command_center_evidence_review_acceptance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Evidence Review Acceptance ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-accepted", action="store_true")
    parser.add_argument("--review-pack", type=Path, default=None)
    parser.add_argument("--review-pack-verification-report", type=Path, default=None)
    parser.add_argument("--response-verification-report", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=32)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=64)
    parser.add_argument("--max-entry-count", type=int, default=64)
    return parser

def _add_unified_command_center_reviewer_decision_board_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--review-id", default=None)
    parser.add_argument("--evidence-review", dest="review_zip", type=Path, default=None, help="Unified Command Center Evidence Review ZIP.")
    parser.add_argument("--evidence-review-verification-report", dest="review_verification_report", type=Path, default=None, help="Evidence Review verification report.")
    parser.add_argument("--accepted-evidence", dest="accepted_evidence", action="append", type=Path, default=[], help="Accepted evidence ZIP. Repeat for every reviewer.")
    parser.add_argument("--accepted-evidence-verification-report", dest="accepted_evidence_verification_report", action="append", type=Path, default=[], help="Accepted evidence verification report. Repeat in the same order.")
    parser.add_argument("--accepted-evidence-response-verification-report", dest="accepted_evidence_response_verification_report", action="append", type=Path, default=[], help="Original response verification summary. Repeat in the same order.")
    parser.add_argument("--required-role", action="append", default=[], help="Required reviewer role for quorum. Repeatable.")
    parser.add_argument("--min-accepted-count", type=int, default=None)
    parser.add_argument("--min-organization-count", type=int, default=None)

__all__ = ('build_unified_command_center_parser', 'build_verify_unified_command_center_parser', 'build_verify_unified_command_center_archive_parser', 'build_verify_unified_command_center_handoff_parser', '_add_unified_command_center_review_evidence_args', 'build_unified_command_center_review_parser', 'build_verify_unified_command_center_continuous_review_parser', '_add_unified_command_center_drift_response_evidence_args', 'build_unified_command_center_drift_response_parser', 'build_verify_unified_command_center_drift_response_parser', '_add_unified_command_center_evidence_review_args', 'build_unified_command_center_evidence_review_parser', 'build_verify_unified_command_center_evidence_review_parser', 'build_verify_unified_command_center_evidence_review_acceptance_parser', '_add_unified_command_center_reviewer_decision_board_args')
