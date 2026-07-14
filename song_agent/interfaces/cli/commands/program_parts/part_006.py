from __future__ import annotations

from .dependencies import *

from .part_001 import _add_command_center_acceptance_source_args

def build_verify_unified_release_program_continuity_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Continuity Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--deep-restore", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-current-vault-operations", action="store_true")
    parser.add_argument("--signoff-binding", type=Path, default=None)
    parser.add_argument("--vault-operations-archive", type=Path, default=None)
    parser.add_argument("--vault-operations-verification-report", type=Path, default=None)
    parser.add_argument("--vault-operations-signoff-binding", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=1024)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_unified_release_program_continuity_distribution_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Continuity Distribution Kit.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    def add_program_arg(cmd: argparse.ArgumentParser) -> None:
        cmd.add_argument("program_id")

    for action in ("status", "prepare", "export", "zip", "verify", "gate", "receipt-template", "import-receipt", "verify-receipt"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Continuity Distribution Kit.")
        add_program_arg(cmd)
        if action in {"prepare", "export", "zip", "verify", "gate"}:
            cmd.add_argument("--continuity-archive", type=Path, default=None)
            cmd.add_argument("--continuity-verification-report", type=Path, default=None)
            cmd.add_argument("--continuity-signoff-binding", type=Path, default=None)
            cmd.add_argument("--vault-operations-archive", type=Path, default=None)
            cmd.add_argument("--vault-operations-verification-report", type=Path, default=None)
            cmd.add_argument("--vault-operations-signoff-binding", type=Path, default=None)
            cmd.add_argument("--evidence-vault", type=Path, default=None)
            cmd.add_argument("--vault-verification-report", type=Path, default=None)
            cmd.add_argument("--vault-anchor", type=Path, default=None)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--deep", action="store_true")
            cmd.add_argument("--require-receiver-receipt", action="store_true")
            cmd.add_argument("--receiver-receipt", type=Path, default=None)
            cmd.add_argument("--report-out", type=Path, default=None)
        if action == "gate":
            cmd.add_argument("--kit-zip", type=Path, default=None)
            cmd.add_argument("--verification-report", type=Path, default=None)
            cmd.add_argument("--require-receiver-receipt", action="store_true")
            cmd.add_argument("--receiver-receipt", type=Path, default=None)
        if action == "import-receipt":
            cmd.add_argument("--receipt-json", type=Path, required=True)
        if action == "verify-receipt":
            cmd.add_argument("receipt_id")
    return parser

def build_verify_unified_release_program_continuity_distribution_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Continuity Distribution Kit ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--require-receiver-receipt", action="store_true")
    parser.add_argument("--receiver-receipt", type=Path, default=None)
    parser.add_argument("--verification-report", type=Path, default=None, help="Current Kit verification report required when checking receiver receipt binding.")
    parser.add_argument("--max-zip-size-mb", type=int, default=4096)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=8192)
    parser.add_argument("--max-entry-count", type=int, default=2000)
    return parser

def build_unified_release_program_continuity_acceptance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Continuity Acceptance Board.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    for action in ("status", "import-response", "accept-evidence", "board", "signoff", "export", "zip", "verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Program Continuity Acceptance Board.")
        cmd.add_argument("program_id")
        if action == "import-response":
            cmd.add_argument("--response-json", type=Path, required=True)
            cmd.add_argument("--response-verification-report", type=Path, required=True)
            cmd.add_argument("--response-binding-summary", type=Path, required=True)
        if action == "accept-evidence":
            cmd.add_argument("response_id")
        if action == "board":
            cmd.add_argument("--policy-json", type=Path, default=None)
        if action == "signoff":
            cmd.add_argument("--signed-by", default=None)
            cmd.add_argument("--role", default=None)
            cmd.add_argument("--reason", default=None)
        if action in {"verify", "gate"}:
            cmd.add_argument("--archive-zip", type=Path, default=None)
            cmd.add_argument("--verification-report", type=Path, default=None)
            cmd.add_argument("--continuity-kit", type=Path, default=None)
            cmd.add_argument("--continuity-kit-verification-report", type=Path, default=None)
            cmd.add_argument("--signoff-binding", type=Path, default=None)
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-current-kit", action="store_true")
            cmd.add_argument("--require-signed", action="store_true")
            cmd.add_argument("--require-quorum", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_release_program_continuity_acceptance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Continuity Acceptance Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-kit", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-quorum", action="store_true")
    parser.add_argument("--continuity-kit", type=Path, default=None)
    parser.add_argument("--continuity-kit-verification-report", type=Path, default=None)
    parser.add_argument("--signoff-binding", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=2000)
    return parser

def build_unified_release_program_continuity_acceptance_change_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Continuity Acceptance Change Control.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    for action in ("status", "create-change-request", "approve-change-request", "reset-signoff", "lifecycle", "export", "zip", "verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Continuity Acceptance Change Control.")
        cmd.add_argument("program_id")
        if action in {"approve-change-request", "reset-signoff"}:
            cmd.add_argument("change_request_id")
        if action == "create-change-request":
            cmd.add_argument("--change-request-id", default=None)
            cmd.add_argument("--change-type", default=None)
            cmd.add_argument("--allowed-action", action="append", default=[])
            cmd.add_argument("--reason", default=None)
            cmd.add_argument("--requested-by", default=None)
        if action == "approve-change-request":
            cmd.add_argument("--approved-by", default=None)
            cmd.add_argument("--role", default=None)
            cmd.add_argument("--reason", default=None)
            cmd.add_argument("--approved-action", action="append", default=[])
        if action == "reset-signoff":
            cmd.add_argument("--reset-by", default=None)
            cmd.add_argument("--reason", default=None)
        if action in {"verify", "gate"}:
            cmd.add_argument("--archive-zip", type=Path, default=None)
            cmd.add_argument("--verification-report", type=Path, default=None)
            cmd.add_argument("--acceptance-archive", type=Path, default=None)
            cmd.add_argument("--acceptance-verification-report", type=Path, default=None)
            cmd.add_argument("--acceptance-signoff-binding", type=Path, default=None)
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-current-acceptance", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_release_program_continuity_acceptance_change_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Continuity Acceptance Change Control Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-acceptance", action="store_true")
    parser.add_argument("--acceptance-archive", type=Path, default=None)
    parser.add_argument("--acceptance-verification-report", type=Path, default=None)
    parser.add_argument("--acceptance-signoff-binding", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=2000)
    return parser

def build_unified_release_program_continuity_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Continuity Command Center.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    for action in ("status", "refresh", "run-safe", "export", "zip", "verify", "gate"):
        cmd = subparsers.add_parser(action, help=f"{action} Continuity Command Center.")
        cmd.add_argument("program_id")
        if action in {"verify", "gate"}:
            cmd.add_argument("--command-center-zip", type=Path, default=None)
            cmd.add_argument("--verification-report", type=Path, default=None)
            cmd.add_argument("--evidence-manifest", type=Path, default=None)
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--deep", action="store_true")
            cmd.add_argument("--require-ready", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_release_program_continuity_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Unified Release Program Continuity Command Center ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--evidence-manifest", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_unified_release_program_continuity_command_center_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Unified Release Program Continuity Command Center signoff and handoff.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    actions = (
        "status",
        "preflight",
        "sign",
        "create-cr",
        "approve-cr",
        "reset",
        "export",
        "zip",
        "verify",
        "handoff-export",
        "handoff-zip",
        "handoff-verify",
        "gate",
    )
    for action in actions:
        cmd = subparsers.add_parser(action, help=f"{action} Continuity Command Center signoff evidence.")
        cmd.add_argument("program_id")
        cmd.add_argument("--json", action="store_true")
        cmd.add_argument("--signed-by", default=None)
        cmd.add_argument("--role", default=None)
        cmd.add_argument("--reason", default=None)
        cmd.add_argument("--change-request-id", default=None)
        cmd.add_argument("--approved-by", default=None)
        cmd.add_argument("--reset-by", default=None)
        cmd.add_argument("--allowed-action", action="append", default=[])
        cmd.add_argument("--archive-zip", type=Path, default=None)
        cmd.add_argument("--archive-verification-report", type=Path, default=None)
        cmd.add_argument("--signoff-binding", type=Path, default=None)
        cmd.add_argument("--command-center", type=Path, default=None)
        cmd.add_argument("--command-center-verification-report", type=Path, default=None)
        cmd.add_argument("--command-center-evidence-manifest", type=Path, default=None)
        cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_unified_release_program_continuity_command_center_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a Continuity Command Center Signoff Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--signoff-binding", type=Path, default=None)
    parser.add_argument("--command-center", type=Path, default=None)
    parser.add_argument("--command-center-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-evidence-manifest", type=Path, default=None)
    return parser

def build_verify_unified_release_program_continuity_command_center_handoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a Continuity Command Center Final Handoff ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-archive", action="store_true")
    parser.add_argument("--archive-zip", type=Path, default=None)
    parser.add_argument("--archive-verification-report", type=Path, default=None)
    parser.add_argument("--signoff-binding", type=Path, default=None)
    parser.add_argument("--command-center", type=Path, default=None)
    parser.add_argument("--command-center-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-evidence-manifest", type=Path, default=None)
    return parser

def build_unified_release_program_continuity_command_center_acceptance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Continuity Command Center Receiver Acceptance evidence.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    actions = (
        "status",
        "create-review-pack",
        "verify-review-pack",
        "import-response",
        "import-response-base64",
        "create-accepted-evidence",
        "verify-accepted-evidence",
        "refresh-board",
        "signoff",
        "export-archive",
        "zip-archive",
        "verify-archive",
        "gate",
    )
    for action in actions:
        cmd = subparsers.add_parser(action, help=f"{action} Receiver Acceptance evidence.")
        cmd.add_argument("program_id")
        cmd.add_argument("--json", action="store_true")
        cmd.add_argument("--response", type=Path, default=None)
        cmd.add_argument("--response-verification-report", type=Path, default=None)
        cmd.add_argument("--response-binding-summary", type=Path, default=None)
        cmd.add_argument("--response-base64", default=None)
        cmd.add_argument("--response-zip-base64", default=None)
        cmd.add_argument("--response-id", default=None)
        cmd.add_argument("--signed-by", default=None)
        cmd.add_argument("--role", default=None)
        cmd.add_argument("--reason", default=None)
        cmd.add_argument("--min-accepted-count", type=int, default=None)
        cmd.add_argument("--min-organization-count", type=int, default=None)
        cmd.add_argument("--required-role", action="append", default=[])
        cmd.add_argument("--report-out", type=Path, default=None)
        _add_command_center_acceptance_source_args(cmd)
    return parser

def build_verify_unified_release_program_continuity_command_center_acceptance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a Continuity Command Center Receiver Acceptance Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--signoff-binding", type=Path, default=None)
    _add_command_center_acceptance_source_args(parser)
    return parser

__all__ = ('build_verify_unified_release_program_continuity_parser', 'build_unified_release_program_continuity_distribution_parser', 'build_verify_unified_release_program_continuity_distribution_parser', 'build_unified_release_program_continuity_acceptance_parser', 'build_verify_unified_release_program_continuity_acceptance_parser', 'build_unified_release_program_continuity_acceptance_change_parser', 'build_verify_unified_release_program_continuity_acceptance_change_parser', 'build_unified_release_program_continuity_command_center_parser', 'build_verify_unified_release_program_continuity_command_center_parser', 'build_unified_release_program_continuity_command_center_signoff_parser', 'build_verify_unified_release_program_continuity_command_center_signoff_parser', 'build_verify_unified_release_program_continuity_command_center_handoff_parser', 'build_unified_release_program_continuity_command_center_acceptance_parser', 'build_verify_unified_release_program_continuity_command_center_acceptance_parser')
