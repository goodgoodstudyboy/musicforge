from __future__ import annotations

from . import dependencies as _commands_program_parts_dependencies; Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = (_commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report)

from .unified_command_center import _add_unified_command_center_reviewer_decision_board_args

def build_unified_command_center_reviewer_decision_board_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Reviewer Decision Board archives.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create a Reviewer Decision Board.")
    create.add_argument("center_id")
    create.add_argument("--board-id", default=None)
    _add_unified_command_center_reviewer_decision_board_args(create)
    subparsers.add_parser("list", help="List Reviewer Decision Boards.").add_argument("center_id")
    for action in ("status", "refresh", "signoff", "export", "zip", "verify"):
        cmd = subparsers.add_parser(action, help=f"{action} a Reviewer Decision Board.")
        cmd.add_argument("center_id")
        cmd.add_argument("board_id")
        if action in {"refresh", "signoff", "export", "zip", "verify"}:
            _add_unified_command_center_reviewer_decision_board_args(cmd)
        if action == "signoff":
            cmd.add_argument("--signed-by", default=None)
            cmd.add_argument("--role", default=None)
            cmd.add_argument("--reason", default=None)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--require-quorum", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_command_center_reviewer_decision_board_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Reviewer Decision Board archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-quorum", action="store_true")
    _add_unified_command_center_reviewer_decision_board_args(parser)
    return parser

def build_unified_command_center_release_train_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Release Train archives.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create a Release Train.")
    create.add_argument("--train-id", default=None)
    create.add_argument("--name", default=None)
    create.add_argument("--profile", default="ga")
    create.add_argument("--allow-duplicate-center", action="store_true")
    create.add_argument("--required-evidence", action="append", default=[])
    list_cmd = subparsers.add_parser("list", help="List Release Trains.")
    del list_cmd
    add_item = subparsers.add_parser("add-item", help="Add a UCC item to a Release Train.")
    add_item.add_argument("train_id")
    add_item.add_argument("--item-id", default=None)
    add_item.add_argument("--center-id", required=True)
    add_item.add_argument("--label", default=None)
    add_item.add_argument("--wave", type=int, default=1)
    add_item.add_argument("--depends-on", action="append", default=[])
    add_item.add_argument("--allow-duplicate-center", action="store_true")
    add_item.add_argument("--required-evidence", action="append", default=[])
    for action in ("status", "refresh", "run-safe", "signoff", "export", "zip", "verify"):
        cmd = subparsers.add_parser(action, help=f"{action} a Release Train.")
        cmd.add_argument("train_id")
        if action in {"refresh", "run-safe", "signoff", "verify"}:
            cmd.add_argument("--external-evidence-manifest", type=Path, default=None)
        if action == "signoff":
            cmd.add_argument("--signed-by", default="release-train-owner")
            cmd.add_argument("--role", default="release_train_owner")
            cmd.add_argument("--reason", default="Unified Command Center Release Train approved for release.")
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-go", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--signoff-binding", type=Path, default=None)
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_command_center_release_train_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Release Train archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-go", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--signoff-binding", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_unified_command_center_release_train_change_control_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Release Train Change Control.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create-request", help="Create a Train Change Request.")
    create.add_argument("train_id")
    create.add_argument("--request-id", default=None)
    create.add_argument("--requested-by", default="release-train-operator")
    create.add_argument("--reason", default="Release Train evidence changed after signoff.")
    create.add_argument("--change-type", default="evidence_refresh")
    create.add_argument("--change", action="append", default=[])
    create.add_argument("--external-evidence-manifest", type=Path, required=True)
    approve = subparsers.add_parser("approve", help="Approve a Train Change Request.")
    approve.add_argument("train_id")
    approve.add_argument("request_id")
    approve.add_argument("--approved-by", default="release-train-owner")
    approve.add_argument("--role", default="release_train_owner")
    approve.add_argument("--reason", default="Approved controlled Release Train reset.")
    approve.add_argument("--external-evidence-manifest", type=Path, required=True)
    reset = subparsers.add_parser("reset", help="Apply an approved Change Request and reset a signed Release Train.")
    reset.add_argument("train_id")
    reset.add_argument("request_id")
    reset.add_argument("--reset-by", default="release-train-owner")
    reset.add_argument("--reason", default="Approved Release Train reset.")
    reset.add_argument("--external-evidence-manifest", type=Path, required=True)
    for action in ("status", "export", "zip", "verify"):
        cmd = subparsers.add_parser(action, help=f"{action} Release Train Change Control.")
        cmd.add_argument("train_id")
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-reset-applied", action="store_true")
            cmd.add_argument("--require-current-train", action="store_true")
            cmd.add_argument("--train-archive", type=Path, default=None)
            cmd.add_argument("--train-archive-verification-report", type=Path, default=None)
            cmd.add_argument("--train-signoff-binding", type=Path, default=None)
            cmd.add_argument("--external-evidence-manifest", type=Path, default=None)
            cmd.add_argument("--reset-proof", type=Path, default=None)
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_command_center_release_train_change_control_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Release Train Change Control ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-reset-applied", action="store_true")
    parser.add_argument("--require-current-train", action="store_true")
    parser.add_argument("--train-archive", type=Path, default=None)
    parser.add_argument("--train-archive-verification-report", type=Path, default=None)
    parser.add_argument("--train-signoff-binding", type=Path, default=None)
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--reset-proof", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def _add_unified_command_center_release_train_lifecycle_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--train-archive", type=Path, default=None)
    parser.add_argument("--train-archive-verification-report", type=Path, default=None)
    parser.add_argument("--train-signoff-binding", type=Path, default=None)
    parser.add_argument("--change-control-zip", type=Path, default=None)
    parser.add_argument("--change-control-verification-report", type=Path, default=None)
    parser.add_argument("--reset-proof", type=Path, action="append", default=[])

def build_unified_command_center_release_train_lifecycle_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Release Train Lifecycle Audit.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("status", "refresh", "export", "zip", "verify"):
        cmd = subparsers.add_parser(action, help=f"{action} Release Train Lifecycle Audit.")
        cmd.add_argument("train_id")
        if action in {"refresh", "export", "zip", "verify"}:
            _add_unified_command_center_release_train_lifecycle_args(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-current-train", action="store_true")
            cmd.add_argument("--require-change-control", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_command_center_release_train_lifecycle_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Release Train Lifecycle Audit ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-train", action="store_true")
    parser.add_argument("--require-change-control", action="store_true")
    _add_unified_command_center_release_train_lifecycle_args(parser)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def _add_unified_command_center_release_train_handoff_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--train-archive", type=Path, default=None)
    parser.add_argument("--train-archive-verification-report", type=Path, default=None)
    parser.add_argument("--train-signoff-binding", type=Path, default=None)
    parser.add_argument("--change-control-zip", type=Path, default=None)
    parser.add_argument("--change-control-verification-report", type=Path, default=None)
    parser.add_argument("--reset-proof", type=Path, action="append", default=[])
    parser.add_argument("--lifecycle-zip", type=Path, default=None)
    parser.add_argument("--lifecycle-verification-report", type=Path, default=None)

def build_unified_command_center_release_train_handoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Command Center Release Train Final Handoff Board.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create a Release Train Handoff.")
    create.add_argument("train_id")
    create.add_argument("--handoff-id", default=None)
    create.add_argument("--require-external-acceptance", action="store_true")
    _add_unified_command_center_release_train_handoff_args(create)
    for action in ("status", "refresh", "export", "zip", "verify", "board", "signoff"):
        cmd = subparsers.add_parser(action, help=f"{action} Release Train Handoff.")
        cmd.add_argument("train_id")
        cmd.add_argument("--handoff-id", default=None)
        if action in {"refresh", "verify", "signoff"}:
            _add_unified_command_center_release_train_handoff_args(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-current", action="store_true")
            cmd.add_argument("--require-lifecycle", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--require-accepted", action="store_true")
            cmd.add_argument("--handoff-signoff-binding", type=Path, default=None)
            cmd.add_argument("--accepted-evidence-dir", type=Path, default=None)
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "signoff":
            cmd.add_argument("--signed-by", default="release-train-handoff-chair")
            cmd.add_argument("--role", default="release_owner")
            cmd.add_argument("--reason", default="Release Train Handoff accepted.")
    response = subparsers.add_parser("import-response", help="Import an external handoff response JSON.")
    response.add_argument("train_id")
    response.add_argument("handoff_id")
    response.add_argument("--response-json", type=Path, required=True)
    accepted = subparsers.add_parser("accepted-evidence", help="Create accepted handoff evidence from a response.")
    accepted.add_argument("train_id")
    accepted.add_argument("handoff_id")
    accepted.add_argument("response_id")
    return parser

def build_verify_unified_command_center_release_train_handoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Command Center Release Train Handoff ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current", action="store_true")
    parser.add_argument("--require-lifecycle", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-accepted", action="store_true")
    _add_unified_command_center_release_train_handoff_args(parser)
    parser.add_argument("--handoff-signoff-binding", type=Path, default=None)
    parser.add_argument("--accepted-evidence-dir", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_unified_release_program_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Board.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create a Unified Release Program.")
    create.add_argument("--program-id", default=None)
    create.add_argument("--name", default="Unified Release Program")
    create.add_argument("--require-external-handoff-acceptance", action="store_true")
    add = subparsers.add_parser("add-train", help="Add a Release Train Handoff item.")
    add.add_argument("program_id")
    add.add_argument("--item-id", required=True)
    add.add_argument("--train-id", required=True)
    add.add_argument("--handoff-id", required=True)
    add.add_argument("--type", default="required", choices=["required", "optional", "advisory", "deferred"])
    add.add_argument("--lane", default="release")
    add.add_argument("--wave", default="wave-1")
    add.add_argument("--depends-on", action="append", default=[])
    add.add_argument("--handoff-zip", type=Path, default=None)
    add.add_argument("--handoff-verification-report", type=Path, default=None)
    add.add_argument("--handoff-signoff-binding", type=Path, default=None)
    add.add_argument("--accepted-evidence-dir", type=Path, default=None)
    for action in ("status", "refresh", "export", "zip", "verify", "signoff", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Unified Release Program.")
        if action != "gate":
            cmd.add_argument("program_id")
        if action in {"refresh", "verify", "signoff"}:
            cmd.add_argument("--external-evidence-manifest", type=Path, default=None)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-current", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--program-signoff-binding", type=Path, default=None)
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "signoff":
            cmd.add_argument("--signed-by", default="program-owner")
            cmd.add_argument("--role", default="release_owner")
            cmd.add_argument("--reason", default="Unified Release Program ready.")
        if action == "gate":
            cmd.add_argument("--program-zip", type=Path, required=True)
            cmd.add_argument("--program-verification-report", type=Path, required=True)
            cmd.add_argument("--external-evidence-manifest", type=Path, required=True)
            cmd.add_argument("--program-signoff-binding", type=Path, required=True)
    return parser

def build_verify_unified_release_program_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--program-signoff-binding", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

__all__ = ('build_unified_command_center_reviewer_decision_board_parser', 'build_verify_unified_command_center_reviewer_decision_board_parser', 'build_unified_command_center_release_train_parser', 'build_verify_unified_command_center_release_train_parser', 'build_unified_command_center_release_train_change_control_parser', 'build_verify_unified_command_center_release_train_change_control_parser', '_add_unified_command_center_release_train_lifecycle_args', 'build_unified_command_center_release_train_lifecycle_parser', 'build_verify_unified_command_center_release_train_lifecycle_parser', '_add_unified_command_center_release_train_handoff_args', 'build_unified_command_center_release_train_handoff_parser', 'build_verify_unified_command_center_release_train_handoff_parser', 'build_unified_release_program_parser', 'build_verify_unified_release_program_parser')
