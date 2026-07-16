from __future__ import annotations

from . import dependencies as _commands_program_parts_dependencies
Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = _commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report
def build_unified_release_program_operations_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Operations Center.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    def add_program_arg(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("program_id")

    def add_current_args(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("--program-zip", type=Path, default=None)
        cmd.add_argument("--program-verification-report", type=Path, default=None)
        cmd.add_argument("--program-signoff-binding", type=Path, default=None)
        cmd.add_argument("--external-evidence-manifest", type=Path, default=None)

    create_cr = subparsers.add_parser("change-request-create", help="Create a Program Change Request.")
    add_program_arg(create_cr)
    add_current_args(create_cr)
    create_cr.add_argument("--change-request-id", default=None)
    create_cr.add_argument("--change-type", default="reset_signoff")
    create_cr.add_argument("--reason", default="Program evidence changed after signoff.")
    create_cr.add_argument("--requested-by", default="program-operator")
    create_cr.add_argument("--allowed-action", dest="allowed_actions", action="append", default=None)

    approve_cr = subparsers.add_parser("change-request-approve", help="Approve a Program Change Request.")
    add_program_arg(approve_cr)
    add_current_args(approve_cr)
    approve_cr.add_argument("change_request_id")
    approve_cr.add_argument("--approved-by", default="program-owner")
    approve_cr.add_argument("--role", default="program_owner")
    approve_cr.add_argument("--reason", default="Approved Program reset.")

    reset = subparsers.add_parser("reset-signoff", help="Reset Program signoff with an approved Change Request.")
    add_program_arg(reset)
    add_current_args(reset)
    reset.add_argument("--change-request-id", required=True)
    reset.add_argument("--reset-by", default="program-owner")
    reset.add_argument("--reason", default="Approved Program reset.")

    runbook_create = subparsers.add_parser("runbook-create", help="Create a Program Operations runbook.")
    add_program_arg(runbook_create)

    runbook_run = subparsers.add_parser("runbook-run-safe", help="Run safe Program Operations actions.")
    add_program_arg(runbook_run)
    add_current_args(runbook_run)
    runbook_run.add_argument("runbook_id")

    for action in ("continuous-review-refresh", "lifecycle-refresh", "archive-export", "archive-zip", "archive-verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Operations.")
        if action != "gate":
            add_program_arg(cmd)
        add_current_args(cmd)
        if action == "archive-verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-current", action="store_true")
            cmd.add_argument("--require-signed-program", action="store_true")
            cmd.add_argument("--require-continuous-review-clear", action="store_true")
            cmd.add_argument("--require-lifecycle-audit", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "gate":
            cmd.add_argument("--program-id", required=True)
            cmd.add_argument("--operations-archive-zip", type=Path, required=True)
            cmd.add_argument("--operations-archive-verification-report", type=Path, required=True)
    return parser

def build_verify_unified_release_program_operations_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Operations Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current", action="store_true")
    parser.add_argument("--require-signed-program", action="store_true")
    parser.add_argument("--require-continuous-review-clear", action="store_true")
    parser.add_argument("--require-lifecycle-audit", action="store_true")
    parser.add_argument("--program-zip", type=Path, default=None)
    parser.add_argument("--program-verification-report", type=Path, default=None)
    parser.add_argument("--program-signoff-binding", type=Path, default=None)
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_unified_release_program_handoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Final Handoff Board.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    def add_program_arg(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("program_id")

    def add_external_args(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("--external-evidence-manifest", type=Path, default=None)

    for action in ("status", "refresh"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Handoff.")
        add_program_arg(cmd)
        if action == "refresh":
            add_external_args(cmd)

    review_pack = subparsers.add_parser("review-pack", help="Export a Program Handoff review pack.")
    add_program_arg(review_pack)
    review_pack.add_argument("--review-pack-id", default=None)
    review_pack.add_argument("--audience", default="release_owner")

    review_pack_zip = subparsers.add_parser("review-pack-zip", help="Build a Program Handoff review pack ZIP.")
    add_program_arg(review_pack_zip)
    review_pack_zip.add_argument("review_pack_id")

    review_pack_verify = subparsers.add_parser("review-pack-verify", help="Verify a Program Handoff review pack ZIP.")
    add_program_arg(review_pack_verify)
    review_pack_verify.add_argument("review_pack_id")
    review_pack_verify.add_argument("--strict", action="store_true")
    review_pack_verify.add_argument("--report-out", type=Path, default=None)

    import_response = subparsers.add_parser("import-response", help="Import an external Program Handoff review response JSON.")
    add_program_arg(import_response)
    import_response.add_argument("response_json", type=Path)

    accepted = subparsers.add_parser("accepted-evidence", help="Create accepted evidence from an accepted response.")
    add_program_arg(accepted)
    accepted.add_argument("response_id")

    accepted_zip = subparsers.add_parser("accepted-evidence-zip", help="Build an accepted evidence ZIP.")
    add_program_arg(accepted_zip)
    accepted_zip.add_argument("evidence_id")

    accepted_verify = subparsers.add_parser("accepted-evidence-verify", help="Verify an accepted evidence ZIP.")
    add_program_arg(accepted_verify)
    accepted_verify.add_argument("evidence_id")
    accepted_verify.add_argument("--strict", action="store_true")
    accepted_verify.add_argument("--require-accepted", action="store_true")
    accepted_verify.add_argument("--response-verification-report", type=Path, default=None)
    accepted_verify.add_argument("--response-binding-summary", type=Path, default=None)
    accepted_verify.add_argument("--report-out", type=Path, default=None)

    board = subparsers.add_parser("decision-board", help="Refresh the Program Handoff decision board.")
    add_program_arg(board)
    board.add_argument("--required-role", dest="required_roles", action="append", default=None)
    board.add_argument("--minimum-acceptances", type=int, default=None)
    board.add_argument("--minimum-organizations", type=int, default=None)

    signoff = subparsers.add_parser("signoff", help="Sign off the Program Handoff.")
    add_program_arg(signoff)
    signoff.add_argument("--signed-by", default="program-handoff-chair")
    signoff.add_argument("--role", default="release_owner")
    signoff.add_argument("--reason", default="Unified Release Program final handoff accepted.")

    for action in ("archive-export", "archive-zip", "archive-verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Handoff Archive.")
        add_program_arg(cmd)
        if action in {"archive-verify", "gate"}:
            add_external_args(cmd)
            cmd.add_argument("--handoff-signoff-binding", type=Path, default=None)
        if action == "archive-verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-current", action="store_true")
            cmd.add_argument("--require-accepted", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "gate":
            cmd.add_argument("--handoff-archive-zip", type=Path, default=None)
            cmd.add_argument("--handoff-archive-verification-report", type=Path, default=None)
    return parser

def build_verify_unified_release_program_handoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Final Handoff Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current", action="store_true")
    parser.add_argument("--require-accepted", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--handoff-signoff-binding", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_unified_release_program_vault_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Evidence Vault.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    def add_program_arg(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("program_id")

    for action in ("status", "refresh", "export", "zip", "verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Evidence Vault.")
        add_program_arg(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--deep", action="store_true")
            cmd.add_argument("--require-anchor", action="store_true")
            cmd.add_argument("--vault-anchor", type=Path, default=None)
            cmd.add_argument("--require-current-program", action="store_true")
            cmd.add_argument("--require-current-operations", action="store_true")
            cmd.add_argument("--require-current-handoff", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "gate":
            cmd.add_argument("--vault-zip", type=Path, default=None)
            cmd.add_argument("--vault-verification-report", type=Path, default=None)
            cmd.add_argument("--vault-anchor", type=Path, default=None)
    return parser

def build_verify_unified_release_program_vault_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Evidence Vault ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--require-anchor", action="store_true")
    parser.add_argument("--vault-anchor", type=Path, default=None)
    parser.add_argument("--require-current-program", action="store_true")
    parser.add_argument("--require-current-operations", action="store_true")
    parser.add_argument("--require-current-handoff", action="store_true")
    parser.add_argument("--no-require-accepted-evidence", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=512)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048)
    parser.add_argument("--max-entry-count", type=int, default=5000)
    return parser

def build_unified_release_program_vault_operations_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Vault Operations.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    def add_program_arg(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("program_id")

    for action in ("status", "init-policy", "register-vault", "refresh-registry", "review", "rotation-plan", "supersede", "revoke", "transfer-pack", "signoff", "archive-export", "archive-zip", "archive-verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Vault Operations.")
        add_program_arg(cmd)
        if action in {"register-vault", "supersede"}:
            cmd.add_argument("--vault-zip", type=Path, default=None)
            cmd.add_argument("--vault-anchor", type=Path, default=None)
            cmd.add_argument("--vault-verification-report", type=Path, default=None)
        if action == "init-policy":
            cmd.add_argument("--review-interval-days", type=int, default=90)
        if action == "rotation-plan":
            cmd.add_argument("--force-rotation", action="store_true")
            cmd.add_argument("--reason", default=None)
        if action == "supersede":
            cmd.add_argument("--old-generation-id", default=None)
            cmd.add_argument("--new-generation-id", default=None)
        if action == "revoke":
            cmd.add_argument("--generation-id", default=None)
            cmd.add_argument("--reason", default=None)
        if action == "transfer-pack":
            cmd.add_argument("--recipient", default=None)
        if action == "signoff":
            cmd.add_argument("--signed-by", default="program-custodian")
            cmd.add_argument("--role", default="custody_owner")
            cmd.add_argument("--reason", default="Unified Release Program Vault Operations accepted.")
        if action == "archive-verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--deep", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--require-current-vault", action="store_true")
            cmd.add_argument("--signoff-binding", type=Path, default=None)
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "gate":
            cmd.add_argument("--archive-zip", type=Path, default=None)
            cmd.add_argument("--verification-report", type=Path, default=None)
            cmd.add_argument("--signoff-binding", type=Path, default=None)
    return parser

def build_verify_unified_release_program_vault_operations_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Vault Operations Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-current-vault", action="store_true")
    parser.add_argument("--signoff-binding", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=1024)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096)
    parser.add_argument("--max-entry-count", type=int, default=5000)
    return parser

def build_unified_release_program_continuity_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Continuity / Recovery Drill.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    def add_program_arg(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("program_id")

    for action in ("status", "init-policy", "plan", "drill", "readiness", "runbook", "signoff", "archive-export", "archive-zip", "archive-verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Continuity.")
        add_program_arg(cmd)
        if action in {"plan", "drill", "readiness", "signoff", "archive-verify", "gate"}:
            cmd.add_argument("--vault-operations-archive", type=Path, default=None)
            cmd.add_argument("--vault-operations-verification-report", type=Path, default=None)
            cmd.add_argument("--vault-operations-signoff-binding", type=Path, default=None)
        if action == "signoff":
            cmd.add_argument("--signed-by", default="continuity-lead")
            cmd.add_argument("--role", default="continuity_owner")
            cmd.add_argument("--reason", default="Recovery drill passed.")
        if action == "archive-verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--deep-restore", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--require-current-vault-operations", action="store_true")
            cmd.add_argument("--signoff-binding", type=Path, default=None)
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "gate":
            cmd.add_argument("--archive-zip", type=Path, default=None)
            cmd.add_argument("--verification-report", type=Path, default=None)
            cmd.add_argument("--signoff-binding", type=Path, default=None)
    return parser

__all__ = ('build_unified_release_program_operations_parser', 'build_verify_unified_release_program_operations_parser', 'build_unified_release_program_handoff_parser', 'build_verify_unified_release_program_handoff_parser', 'build_unified_release_program_vault_parser', 'build_verify_unified_release_program_vault_parser', 'build_unified_release_program_vault_operations_parser', 'build_verify_unified_release_program_vault_operations_parser', 'build_unified_release_program_continuity_parser')
