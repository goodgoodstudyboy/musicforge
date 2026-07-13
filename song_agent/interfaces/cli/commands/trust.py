from __future__ import annotations
import argparse
import json
import sys
import os
from pathlib import Path
from typing import Any
from song_agent.application.generation.service import generate_request
from song_agent.auth import build_auth_config
from song_agent.projectio import read_json, write_json
from song_agent.provider import (
    ProviderConfig,
    ProviderError,
    load_provider_config,
    provider_configured,
    test_provider_config,
)
from song_agent.schemas.song import SongRequest

from song_agent.application.interface_persistence import write_interface_document

from song_agent.interfaces.cli.registry import CommandSpec
from song_agent.interfaces.cli.symbols import resolve as _resolve_symbol

def _acceptance_analytics_fail_on(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_acceptance_analytics_fail_on')(*args, **kwargs)

def build_acceptance_analytics_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_acceptance_analytics_parser')(*args, **kwargs)

def build_acceptance_check_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_acceptance_check_parser')(*args, **kwargs)

def build_acceptance_diff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_acceptance_diff_parser')(*args, **kwargs)

def build_acceptance_fix_plan_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_acceptance_fix_plan_parser')(*args, **kwargs)

def build_acceptance_fix_sprint_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_acceptance_fix_sprint_parser')(*args, **kwargs)

def build_acceptance_kb_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_acceptance_kb_parser')(*args, **kwargs)

def build_audio_health_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_audio_health_parser')(*args, **kwargs)

def build_audio_profile_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_audio_profile_parser')(*args, **kwargs)

def build_encoded_audio_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_encoded_audio_acceptance_parser')(*args, **kwargs)

def build_format_decision_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_format_decision_parser')(*args, **kwargs)

def build_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('creation', 'build_parser')(*args, **kwargs)

def build_planning_rule_governance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_planning_rule_governance_parser')(*args, **kwargs)

def build_planning_rule_impact_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_planning_rule_impact_parser')(*args, **kwargs)

def build_planning_ruleset_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_planning_ruleset_parser')(*args, **kwargs)

def build_planning_simulation_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_planning_simulation_parser')(*args, **kwargs)

def build_release_audio_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_review_parser')(*args, **kwargs)

def build_release_encode_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_release_encode_parser')(*args, **kwargs)

def build_release_operations_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_release_operations_archive_parser')(*args, **kwargs)

def build_release_operations_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_release_operations_audit_parser')(*args, **kwargs)

def build_release_operations_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_release_operations_parser')(*args, **kwargs)

def build_release_operations_reviewer_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_release_operations_reviewer_pack_parser')(*args, **kwargs)

def build_release_operations_runbook_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_release_operations_runbook_parser')(*args, **kwargs)

def build_release_operations_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_release_operations_signoff_parser')(*args, **kwargs)

def build_verify_human_review_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('studio', 'build_verify_human_review_pack_parser')(*args, **kwargs)

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

def print_release_audio_review_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'print_release_audio_review_result')(*args, **kwargs)

def print_release_operations_archive_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'print_release_operations_archive_result')(*args, **kwargs)

def print_release_operations_audit_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'print_release_operations_audit_result')(*args, **kwargs)

def print_release_operations_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'print_release_operations_result')(*args, **kwargs)

def print_release_operations_reviewer_pack_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'print_release_operations_reviewer_pack_result')(*args, **kwargs)

def print_release_operations_runbook_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'print_release_operations_runbook_result')(*args, **kwargs)

def print_release_operations_signoff_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'print_release_operations_signoff_result')(*args, **kwargs)

def run_acceptance_check(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'run_acceptance_check')(*args, **kwargs)

def build_verify_release_portfolio_audit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Audit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Audit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-reviewer-packs", action="store_true", help="Require passed Reviewer Pack verification for every release.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Audit package verification for every release.")
    verify_parser.add_argument("--require-archive", action="store_true", help="Require passed Operations Archive verification for every release.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Queue ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Queue ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-manual-actions", action="store_true", help="Require manual-action-list coverage for manual-required items.")
    verify_parser.add_argument("--require-no-blocked", action="store_true", help="Fail when blocked or failed queue items remain.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_archive_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Governance Signoff evidence.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when Governance Signoff was force signed.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_release_portfolio_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Audits.")
    parser.add_argument("--portfolio-id", default="", help="Portfolio Audit id.")
    parser.add_argument("--list", action="store_true", help="List Portfolio Audits.")
    parser.add_argument("--create", action="store_true", help="Create a Portfolio Audit.")
    parser.add_argument("--name", default="", help="Portfolio name when creating.")
    parser.add_argument("--release-ids", default="", help="Comma-separated Release ids to include. Empty means all releases.")
    parser.add_argument("--include-hidden", action="store_true", help="Include hidden releases.")
    parser.add_argument("--exclude-archived", action="store_true", help="Exclude archived releases.")
    parser.add_argument("--max-releases", type=int, default=None, help="Maximum number of releases to include.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Portfolio Audit reports.")
    parser.add_argument("--export", action="store_true", help="Build Portfolio Audit export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Portfolio Audit ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Portfolio Audit ZIP.")
    parser.add_argument("--archive", action="store_true", help="Archive the Portfolio Audit.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-reviewer-packs", action="store_true", help="Require passed Reviewer Pack verification.")
    parser.add_argument("--require-audit", action="store_true", help="Require passed Audit package verification.")
    parser.add_argument("--require-archive", action="store_true", help="Require passed Operations Archive verification.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_queue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and run local MusicForge Release Portfolio Governance Queues.")
    parser.add_argument("--queue-id", default="", help="Governance Queue id.")
    parser.add_argument("--portfolio-id", default="", help="Portfolio Audit id.")
    parser.add_argument("--list", action="store_true", help="List Governance Queues.")
    parser.add_argument("--create", action="store_true", help="Create a Governance Queue from the current Portfolio Audit report.")
    parser.add_argument("--name", default="", help="Queue name when creating.")
    parser.add_argument("--force-new", action="store_true", help="Create a new queue even when an open queue already exists for the same source.")
    parser.add_argument("--run-safe", action="store_true", help="Run auto-safe governance actions.")
    parser.add_argument("--refresh-portfolio-after-safe-actions", action="store_true", help="Refresh Portfolio Audit after safe actions change underlying evidence.")
    parser.add_argument("--export", action="store_true", help="Build Governance Queue export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Governance Queue ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Governance Queue ZIP.")
    parser.add_argument("--archive", action="store_true", help="Archive the Governance Queue.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-manual-actions", action="store_true", help="Require manual-action-list coverage when verifying.")
    parser.add_argument("--require-no-blocked", action="store_true", help="Fail verification when blocked or failed items remain.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign, reset, and archive local MusicForge Release Portfolio Governance Queue evidence.")
    parser.add_argument("--queue-id", required=True, help="Governance Queue id.")
    parser.add_argument("--sign", action="store_true", help="Create Portfolio Governance Signoff.")
    parser.add_argument("--reset", action="store_true", help="Reset Portfolio Governance Signoff.")
    parser.add_argument("--signed-by", default="local-user", help="Signer name.")
    parser.add_argument("--force", action="store_true", help="Force signoff through manual acknowledgement warnings.")
    parser.add_argument("--override-reason", default="", help="Required with --force.")
    parser.add_argument("--reason", default="", help="Change Request or reset reason.")
    parser.add_argument("--change-request-id", default="", help="Approved Change Request id for reset.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Governance Change Request.")
    parser.add_argument("--approve-change-request", default="", help="Approve a Governance Change Request id.")
    parser.add_argument("--reject-change-request", default="", help="Reject a Governance Change Request id.")
    parser.add_argument("--approved-by", default="local-user", help="Approver name.")
    parser.add_argument("--export-archive", action="store_true", help="Build Governance Archive export directory.")
    parser.add_argument("--zip", action="store_true", help="Build Governance Archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify Governance Archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-signed", action="store_true", help="Require signed Governance Signoff when verifying.")
    parser.add_argument("--require-no-force", action="store_true", help="Fail verification when signoff is force signed.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_audit_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Release Portfolio Governance Audit reports and packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh and persist the Governance Audit report and ledger.")
    parser.add_argument("--ledger", action="store_true", help="Include ledger entries in output.")
    parser.add_argument("--ledger-limit", type=int, default=0, help="Limit output ledger entries to the last N rows.")
    parser.add_argument("--export", action="store_true", help="Build the Governance Audit export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Governance Audit ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Governance Audit ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat strict verifier warnings as failures.")
    parser.add_argument("--require-signed", action="store_true", help="When verifying, require every queue to be signed.")
    parser.add_argument("--require-archives", action="store_true", help="When verifying, require signed queues to have verified archives.")
    parser.add_argument("--require-no-force", action="store_true", help="When verifying, fail on force-signed governance evidence.")
    parser.add_argument("--require-reset-cr-causality", action="store_true", help="When verifying, require reset events to bind to applied Change Requests.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_reviewer_pack_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Reviewer Packs.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Portfolio Governance Reviewer Report.")
    parser.add_argument("--export", action="store_true", help="Build the Portfolio Governance Reviewer Pack export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Portfolio Governance Reviewer Pack ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Portfolio Governance Reviewer Pack ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries as verifier failures.")
    parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence when verifying.")
    parser.add_argument("--require-signed", action="store_true", help="Require every Governance Queue to be signed when verifying.")
    parser.add_argument("--require-archives", action="store_true", help="Require signed queues to have verified Governance Archives.")
    parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_final_board_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, sign, archive, and verify local MusicForge Release Portfolio Governance Final Board evidence.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Final Board Report.")
    parser.add_argument("--require-reviewer-response", action="store_true", help="Require an accepted external reviewer response.")
    parser.add_argument("--require-no-force", action="store_true", help="Treat force-signed governance evidence as blocking.")
    parser.add_argument("--import-reviewer-response", type=Path, default=None, help="Import an external reviewer response JSON file.")
    parser.add_argument("--sign", action="store_true", help="Sign the Final Board evidence.")
    parser.add_argument("--force-sign", action="store_true", help="Force sign when only warnings remain.")
    parser.add_argument("--allow-warning-signoff", action="store_true", help="Allow warning signoff without force.")
    parser.add_argument("--signed-by", default=None, help="Signer name for Final Board Signoff.")
    parser.add_argument("--role", default=None, help="Signer role.")
    parser.add_argument("--reason", default=None, help="Signoff/reset/change request reason.")
    parser.add_argument("--override-reason", default=None, help="Required for force signoff.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Final Board Change Request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a Final Board Change Request id.")
    parser.add_argument("--reject-change-request", default=None, help="Reject a Final Board Change Request id.")
    parser.add_argument("--change-request-id", default=None, help="Change Request id for reset.")
    parser.add_argument("--approved-by", default=None, help="Approver name for Change Request approval.")
    parser.add_argument("--reset-signoff", action="store_true", help="Reset Final Board Signoff using an approved Change Request.")
    parser.add_argument("--export", action="store_true", help="Build the Final Board Archive export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Final Board Archive ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Final Board Archive ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-signed", action="store_true", help="When verifying, require signed Final Board Signoff.")
    parser.add_argument("--require-reviewer-pack", action="store_true", help="When verifying, require Reviewer Pack evidence.")
    parser.add_argument("--require-audit", action="store_true", help="When verifying, require Governance Audit evidence.")
    parser.add_argument("--require-archives", action="store_true", help="When verifying, require verified Governance Archive coverage.")
    parser.add_argument("--require-reset-cr-causality", action="store_true", help="When verifying, require reset events to bind to applied Change Requests.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_evidence_vault_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Evidence Vault packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Evidence Vault Report.")
    parser.add_argument("--export", action="store_true", help="Build the Evidence Vault export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Evidence Vault ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Evidence Vault ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--deep", action="store_true", help="Run nested package verifiers.")
    parser.add_argument("--require-final-board", action="store_true", help="Require passed Final Board Archive evidence.")
    parser.add_argument("--require-reviewer-pack", action="store_true", help="Require passed Governance Reviewer Pack evidence.")
    parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    parser.add_argument("--require-archives", action="store_true", help="Require signed queue Governance Archive evidence.")
    parser.add_argument("--require-queue-packages", action="store_true", help="Require Governance Queue ZIP evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_attestation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Public Attestation packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile: public_summary, partner_due_diligence, or internal_public_preview.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Public Attestation Report.")
    parser.add_argument("--export", action="store_true", help="Build the Public Attestation export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Public Attestation ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Public Attestation ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-vault", action="store_true", help="Require passed deep Evidence Vault verification.")
    parser.add_argument("--require-final-board", action="store_true", help="Require Final Board signoff evidence.")
    parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_attestation_registry_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Release Portfolio Governance Public Attestation registries.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--register-current", action="store_true", help="Register the current verified Public Attestation ZIP.")
    parser.add_argument("--publish", metavar="ENTRY_ID", default=None, help="Publish a registry entry.")
    parser.add_argument("--supersede-current", action="store_true", help="Allow publish to supersede the current entry.")
    parser.add_argument("--revoke", metavar="ENTRY_ID", default=None, help="Revoke a published or superseded registry entry.")
    parser.add_argument("--reason", default="", help="Revocation reason.")
    parser.add_argument("--public-url", default="", help="Optional public URL for the published entry.")
    parser.add_argument("--distribution-note", default="", help="Optional public distribution note.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the registry report.")
    parser.add_argument("--export", action="store_true", help="Build the registry export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the registry ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the registry ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    parser.add_argument("--require-published", action="store_true", help="Require at least one published registry entry.")
    parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_attestation_portal_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify local MusicForge Release Portfolio Governance Public Attestation Portal snapshots.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Attestation Portal Report.")
    parser.add_argument("--export", action="store_true", help="Build the Attestation Portal export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Attestation Portal ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Attestation Portal ZIP package.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require a current published portal entry.")
    parser.add_argument("--require-registry", action="store_true", help="Require passed Attestation Registry evidence.")
    parser.add_argument("--require-attestation", action="store_true", help="Require passed Public Attestation evidence.")
    parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_attestation_portal_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Public Attestation Portal review packs and import external responses.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh-pack", action="store_true", help="Refresh the Portal Review Pack.")
    parser.add_argument("--export-pack", action="store_true", help="Build the Portal Review Pack export directory.")
    parser.add_argument("--zip-pack", action="store_true", help="Build the Portal Review Pack ZIP.")
    parser.add_argument("--verify-pack", action="store_true", help="Verify the Portal Review Pack ZIP.")
    parser.add_argument("--import-response", action="store_true", help="Import an external Portal Review Response from content_base64.")
    parser.add_argument("--content-base64", default="", help="Base64 JSON or ZIP response payload for --import-response.")
    parser.add_argument("--response-id", default="", help="Response id for detail, verify, or Change Request creation.")
    parser.add_argument("--responses", action="store_true", help="List imported responses.")
    parser.add_argument("--verify-response", action="store_true", help="Verify an imported response.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Change Request draft from a needs_changes/rejected response.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require current source evidence when verifying.")
    parser.add_argument("--require-pack", action="store_true", help="Require response to bind to a Review Pack source.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_attestation_accepted_evidence_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Public Attestation Accepted Evidence packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Accepted Evidence from an accepted Portal Review Response.")
    parser.add_argument("--response-id", default="", help="Accepted Portal Review Response id.")
    parser.add_argument("--export", action="store_true", help="Build the Accepted Evidence export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Accepted Evidence ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Accepted Evidence ZIP package.")
    parser.add_argument("--archive", action="store_true", help="Archive current Accepted Evidence.")
    parser.add_argument("--reason", default="", help="Archive reason.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require current accepted evidence when verifying.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_attestation_transparency_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Public Attestation Transparency Feed packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Transparency Feed.")
    parser.add_argument("--export", action="store_true", help="Build the Transparency export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Transparency ZIP package.")
    parser.add_argument("--verify", action="store_true", help="Verify the Transparency ZIP package.")
    parser.add_argument("--notices", action="store_true", help="List current change notices.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    parser.add_argument("--require-contiguous-chain", action="store_true", help="Require a valid contiguous transparency event chain.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_release_portfolio_governance_attestation_transparency_acknowledgement_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge Public Attestation Transparency Acknowledgement packages.")
    parser.add_argument("--portfolio-id", required=True, help="Release Portfolio Audit id.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh-pack", action="store_true", help="Refresh the Transparency Acknowledgement Pack.")
    parser.add_argument("--export-pack", action="store_true", help="Build the Acknowledgement Pack export directory.")
    parser.add_argument("--zip-pack", action="store_true", help="Build the Acknowledgement Pack ZIP package.")
    parser.add_argument("--verify-pack", action="store_true", help="Verify the Acknowledgement Pack ZIP package.")
    parser.add_argument("--import-response", action="store_true", help="Import an uploaded acknowledgement response.")
    parser.add_argument("--content-base64", default="", help="Base64-encoded acknowledgement response JSON or ZIP.")
    parser.add_argument("--response-id", default="", help="Acknowledgement response id.")
    parser.add_argument("--refresh-evidence", action="store_true", help="Refresh accepted acknowledgement evidence.")
    parser.add_argument("--export-evidence", action="store_true", help="Build the Acknowledgement Evidence export directory.")
    parser.add_argument("--zip-evidence", action="store_true", help="Build the Acknowledgement Evidence ZIP package.")
    parser.add_argument("--verify-evidence", action="store_true", help="Verify the Acknowledgement Evidence ZIP package.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Change Request draft from a needs_changes/rejected response.")
    parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    parser.add_argument("--require-pack", action="store_true", help="Require an Acknowledgement Pack package when verifying.")
    parser.add_argument("--require-response", action="store_true", help="Require Acknowledgement Evidence when verifying.")
    parser.add_argument("--require-accepted", action="store_true", help="Require accepted acknowledgement evidence when verifying.")
    parser.add_argument("--require-transparency", action="store_true", help="Require passed Transparency verification and semantics.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_verify_release_portfolio_governance_audit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Audit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Audit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require every Governance Queue in the audit to be signed.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require signed queues to have verified Governance Archives.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    verify_parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_reviewer_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Reviewer Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Reviewer Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require every Governance Queue in the pack to be signed.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require signed queues to have verified Governance Archives.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    verify_parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_final_board_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Final Board Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Final Board Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Final Board Signoff.")
    verify_parser.add_argument("--require-reviewer-pack", action="store_true", help="Require passed Governance Reviewer Pack evidence.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require verified Governance Archive coverage.")
    verify_parser.add_argument("--require-reviewer-response", action="store_true", help="Require accepted external reviewer response.")
    verify_parser.add_argument("--require-no-force", action="store_true", help="Fail when force-signed governance evidence is present.")
    verify_parser.add_argument("--require-reset-cr-causality", action="store_true", help="Require signoff reset events to be bound to applied Change Requests.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=128, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=5000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_evidence_vault_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Evidence Vault ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Evidence Vault ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Run nested package verifiers.")
    verify_parser.add_argument("--require-final-board", action="store_true", help="Require passed Final Board Archive evidence.")
    verify_parser.add_argument("--require-reviewer-pack", action="store_true", help="Require passed Governance Reviewer Pack evidence.")
    verify_parser.add_argument("--require-audit", action="store_true", help="Require passed Governance Audit evidence.")
    verify_parser.add_argument("--require-archives", action="store_true", help="Require signed queue Governance Archive evidence.")
    verify_parser.add_argument("--require-queue-packages", action="store_true", help="Require Governance Queue ZIP evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=1024, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=4096, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=20000, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Public Attestation ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Public Attestation ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-vault", action="store_true", help="Require passed deep Evidence Vault verification.")
    verify_parser.add_argument("--require-final-board", action="store_true", help="Require Final Board signoff evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_registry_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Public Attestation Registry ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Public Attestation Registry ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    verify_parser.add_argument("--require-published", action="store_true", help="Require at least one published registry entry.")
    verify_parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    verify_parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_portal_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Release Portfolio Governance Public Attestation Portal ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Release Portfolio Governance Public Attestation Portal ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current published portal entry.")
    verify_parser.add_argument("--require-registry", action="store_true", help="Require passed Attestation Registry evidence.")
    verify_parser.add_argument("--require-attestation", action="store_true", help="Require passed Public Attestation evidence.")
    verify_parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_portal_review_pack_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Portal Review Pack ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Portal Review Pack ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current verified Portal evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_portal_response_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Portal Review Response ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Portal Review Response ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current response source evidence.")
    verify_parser.add_argument("--require-pack", action="store_true", help="Require response to bind to a Review Pack source.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_accepted_evidence_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Accepted Evidence ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Accepted Evidence ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_transparency_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Transparency ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Attestation Transparency ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current published registry entry.")
    verify_parser.add_argument("--require-accepted-evidence", action="store_true", help="Require current accepted external review evidence.")
    verify_parser.add_argument("--require-no-revoked-current", action="store_true", help="Fail when the current registry entry is revoked.")
    verify_parser.add_argument("--require-contiguous-chain", action="store_true", help="Require a valid contiguous transparency event chain.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=300, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Attestation Transparency Acknowledgement ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Transparency Acknowledgement Pack/Evidence ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-pack", action="store_true", help="Require an Acknowledgement Pack package.")
    verify_parser.add_argument("--require-response", action="store_true", help="Require Acknowledgement Evidence.")
    verify_parser.add_argument("--require-accepted", action="store_true", help="Require accepted acknowledgement evidence.")
    verify_parser.add_argument("--require-transparency", action="store_true", help="Require passed Transparency verification and semantics.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=300, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a portable MusicForge Public Trust Center ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Public Trust Center ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-release-readiness", action="store_true", help="Require selected releases to be ready.")
    verify_parser.add_argument("--require-public-attestation", action="store_true", help="Require registry, portal, and transparency evidence.")
    verify_parser.add_argument("--require-registry-current", action="store_true", help="Require current Registry evidence.")
    verify_parser.add_argument("--require-portal-current", action="store_true", help="Require current Portal evidence.")
    verify_parser.add_argument("--require-transparency-current", action="store_true", help="Require current Transparency evidence.")
    verify_parser.add_argument("--require-acknowledgement-current", action="store_true", help="Require current accepted acknowledgement evidence.")
    verify_parser.add_argument("--require-delivery-readiness", action="store_true", help="Require selected delivery chain rows to be ready.")
    verify_parser.add_argument("--require-distribution-ready", action="store_true", help="Require distribution evidence to be signed and verified.")
    verify_parser.add_argument("--require-submission-accepted", action="store_true", help="Require submission batches to be accepted.")
    verify_parser.add_argument("--require-submission-evidence", action="store_true", help="Require signed submission evidence packages.")
    verify_parser.add_argument("--require-operations-signed", action="store_true", help="Require Release Operations Signoff evidence.")
    verify_parser.add_argument("--require-operations-audit", action="store_true", help="Require verified Release Operations Audit evidence.")
    verify_parser.add_argument("--require-operations-reviewer-pack", action="store_true", help="Require verified Release Operations Reviewer Pack evidence.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require current Acceptance Board signoff archive evidence.")
    verify_parser.add_argument("--delivery-anchor", type=Path, default=None, help="Path to an external Public Trust Center delivery anchor JSON file.")
    verify_parser.add_argument("--anchor-registry", type=Path, default=None, help="Path to a Public Trust Center Anchor Registry ZIP.")
    verify_parser.add_argument("--anchor-transparency", type=Path, default=None, help="Path to a Public Trust Center Anchor Transparency ZIP.")
    verify_parser.add_argument("--anchor-checkpoint", type=Path, default=None, help="Path to an external Anchor Transparency checkpoint JSON.")
    verify_parser.add_argument("--acceptance-board-signoff-archive", type=Path, default=None, help="Path to an external Acceptance Board Signoff Archive ZIP.")
    verify_parser.add_argument("--acceptance-board", type=Path, default=None, help="Path to an external Acceptance Board ZIP.")
    verify_parser.add_argument("--acceptance-board-verification-report", type=Path, default=None, help="Path to the stored Acceptance Board verification report.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="Path to an external Distribution Kit ZIP for signoff archive binding.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs for signoff archive binding.")
    verify_parser.add_argument("--require-anchor-registry-current", action="store_true", help="Require the Anchor Registry current entry to match this package.")
    verify_parser.add_argument("--require-anchor-published", action="store_true", help="Require the Anchor Registry current entry to be published.")
    verify_parser.add_argument("--require-anchor-not-revoked", action="store_true", help="Require the Anchor Registry current entry not to be revoked.")
    verify_parser.add_argument("--require-anchor-transparency-current", action="store_true", help="Require Anchor Transparency evidence to match this package.")
    verify_parser.add_argument("--require-anchor-checkpoint", action="store_true", help="Require an external Anchor Transparency checkpoint.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=250, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_anchor_registry_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Anchor Registry ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Anchor Registry ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require a current anchor entry.")
    verify_parser.add_argument("--require-anchor-published", action="store_true", help="Require the current anchor entry to be published.")
    verify_parser.add_argument("--require-anchor-not-revoked", action="store_true", help="Require the current anchor entry not to be revoked.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=200, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_anchor_transparency_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Anchor Transparency ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Anchor Transparency ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--checkpoint", type=Path, default=None, help="External Anchor Transparency checkpoint JSON.")
    verify_parser.add_argument("--anchor-registry", type=Path, default=None, help="External Anchor Registry ZIP.")
    verify_parser.add_argument("--require-current-checkpoint", action="store_true", help="Require a current checkpoint.")
    verify_parser.add_argument("--require-published-anchor", action="store_true", help="Require the checkpoint current anchor to be published.")
    verify_parser.add_argument("--require-not-revoked", action="store_true", help="Require the checkpoint current anchor not to be revoked.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=250, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_distribution_kit_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Distribution Kit ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Distribution Kit ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat extra ZIP entries and strict warnings as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Re-run nested Public Trust Center, Anchor Registry, and Anchor Transparency verification.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current nested evidence.")
    verify_parser.add_argument("--require-delivery-readiness", dest="require_delivery_readiness", action="store_true", default=True, help="Require delivery readiness in nested PTC verification.")
    verify_parser.add_argument("--no-require-delivery-readiness", dest="require_delivery_readiness", action="store_false", help="Do not require delivery readiness in nested PTC verification.")
    verify_parser.add_argument("--require-anchor-registry-current", action="store_true", default=True, help="Require current Anchor Registry evidence.")
    verify_parser.add_argument("--require-anchor-published", action="store_true", default=True, help="Require published current anchor.")
    verify_parser.add_argument("--require-anchor-not-revoked", action="store_true", default=True, help="Require current anchor not revoked.")
    verify_parser.add_argument("--require-anchor-transparency-current", action="store_true", default=True, help="Require current Anchor Transparency evidence.")
    verify_parser.add_argument("--require-anchor-checkpoint", action="store_true", default=True, help="Require the included checkpoint.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require current Acceptance Board signoff archive evidence.")
    verify_parser.add_argument("--acceptance-board-signoff-archive", type=Path, default=None, help="Path to an external Acceptance Board Signoff Archive ZIP.")
    verify_parser.add_argument("--acceptance-board", type=Path, default=None, help="Path to an external Acceptance Board ZIP.")
    verify_parser.add_argument("--acceptance-board-verification-report", type=Path, default=None, help="Path to the stored Acceptance Board verification report.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs for signoff archive binding.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=256, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=512, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=400, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_distribution_kit_accepted_evidence_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Distribution Kit Accepted Evidence ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Accepted Evidence ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require the external Distribution Kit ZIP to match the evidence binding.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="External Distribution Kit ZIP for current binding checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_acceptance_board_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Acceptance Board ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Acceptance Board ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require the board to be ready.")
    verify_parser.add_argument("--require-quorum", action="store_true", help="Require the board quorum gate to pass.")
    verify_parser.add_argument("--require-no-conflicts", action="store_true", help="Require no blocking board conflicts.")
    verify_parser.add_argument("--min-accepted-count", type=int, default=0, help="Minimum accepted evidence count required by the verifier.")
    verify_parser.add_argument("--min-accepted-organizations", type=int, default=0, help="Minimum accepted organization count required by the verifier.")
    verify_parser.add_argument("--required-role", action="append", dest="required_roles", default=[], help="Required reviewer role. Can be repeated.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="External Distribution Kit ZIP for binding checks.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs for future deep checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=160, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_acceptance_board_signoff_archive_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Acceptance Board Signoff Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Acceptance Board Signoff Archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require a signed Acceptance Board signoff.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require external current board/evidence bindings.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require a ready and verified board.")
    verify_parser.add_argument("--board-zip", type=Path, default=None, help="External Acceptance Board ZIP for current checks.")
    verify_parser.add_argument("--board-verification-report", type=Path, default=None, help="Stored Acceptance Board verification report.")
    verify_parser.add_argument("--distribution-kit", type=Path, default=None, help="External Distribution Kit ZIP for binding checks.")
    verify_parser.add_argument("--accepted-evidence-dir", type=Path, default=None, help="Directory containing Accepted Evidence ZIPs.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_publication_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Publication ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Publication ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--deep", action="store_true", help="Re-run nested package verifiers.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require publication ready status.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require Acceptance Board signoff evidence.")
    verify_parser.add_argument("--require-anchor-current", action="store_true", help="Require current Anchor Registry and Transparency evidence.")
    verify_parser.add_argument("--require-no-revoked", action="store_true", help="Fail revoked publication snapshots.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for revoke/supersede checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=512, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=512, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_public_trust_center_publication_mirror_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Publication mirror directory.")
    verify_parser.add_argument("mirror_dir", type=Path, help="Path to the Publication mirror directory to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require publication ready status.")
    verify_parser.add_argument("--require-acceptance-board-signoff", action="store_true", help="Require Acceptance Board signoff evidence.")
    verify_parser.add_argument("--require-anchor-current", action="store_true", help="Require current Anchor Registry and Anchor Transparency evidence.")
    verify_parser.add_argument("--require-no-revoked", action="store_true", help="Fail if the publication snapshot is revoked.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for revoke/supersede checks.")
    verify_parser.add_argument("--max-entry-count", type=int, default=512, help="Maximum number of mirror files.")
    return verify_parser

def build_verify_public_trust_center_publication_monitoring_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Public Trust Center Publication Monitoring ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Publication Monitoring ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict warnings as failures.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require the monitoring run to match current external channel state.")
    verify_parser.add_argument("--require-no-revoked", action="store_true", help="Fail revoked or superseded monitored publications.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require a passed monitoring run and publication verification.")
    verify_parser.add_argument("--require-no-drift", action="store_true", help="Require no critical/high drift.")
    verify_parser.add_argument("--require-no-open-critical-incidents", action="store_true", help="Require no open critical incident.")
    verify_parser.add_argument("--allow-waived-incidents", action="store_true", help="Allow waived high/critical incidents as warnings.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for current/revoke checks.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=256, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_hub_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Hub ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Hub ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-ready", action="store_true", help="Require Hub readiness to be ready.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require Hub signoff summary.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external source evidence.")
    verify_parser.add_argument("--require-no-critical-blockers", action="store_true", help="Require no critical blockers.")
    verify_parser.add_argument("--require-publication-monitoring-clean", action="store_true", help="Require clean publication monitoring evidence.")
    verify_parser.add_argument("--require-delivery-ready", action="store_true", help="Require full delivery-chain verification evidence.")
    verify_parser.add_argument("--require-incident-closeout", action="store_true", help="Require external Trust Operations Incident closeout evidence.")
    verify_parser.add_argument("--require-incident-regression-guards", action="store_true", help="Require external Trust Operations Incident Knowledge regression guard evidence.")
    verify_parser.add_argument("--require-trust-controls", action="store_true", help="Require Trust Operations Control Catalog policy evidence.")
    verify_parser.add_argument("--require-trust-control-signoff", action="store_true", help="Require Trust Operations Control Signoff archive evidence.")
    verify_parser.add_argument("--require-continuous-assurance", action="store_true", help="Require Trust Operations Continuous Assurance evidence.")
    verify_parser.add_argument("--require-assurance-watch-clear", action="store_true", help="Require Trust Operations Assurance Watch queue to be clear.")
    verify_parser.add_argument("--require-assurance-watch-signoff", action="store_true", help="Require Trust Operations Assurance Watch Signoff archive evidence.")
    verify_parser.add_argument("--require-final-readiness", action="store_true", help="Require Trust Operations Final Readiness handoff evidence.")
    verify_parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for current/revoke checks.")
    verify_parser.add_argument("--public-trust-center-verification", type=Path, default=None, help="External Public Trust Center verification report.")
    verify_parser.add_argument("--publication-monitoring-verification", type=Path, default=None, help="External Publication Monitoring verification report.")
    verify_parser.add_argument("--release-verification", type=Path, action="append", default=[], help="External Release ZIP verification report. Can be repeated.")
    verify_parser.add_argument("--distribution-verification", type=Path, action="append", default=[], help="External Distribution package verification report. Can be repeated.")
    verify_parser.add_argument("--submission-verification", type=Path, action="append", default=[], help="External Submission package verification report. Can be repeated.")
    verify_parser.add_argument("--submission-evidence-verification", type=Path, action="append", default=[], help="External Submission Evidence verification report. Can be repeated.")
    verify_parser.add_argument("--release-operations-verification", type=Path, action="append", default=[], help="External Release Operations verification report. Can be repeated.")
    verify_parser.add_argument("--hub-signoff", type=Path, default=None, help="External Trust Operations Hub signoff sidecar JSON.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report used for signoff.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    verify_parser.add_argument("--trust-control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    verify_parser.add_argument("--trust-control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    verify_parser.add_argument("--trust-control-signoff-archive", type=Path, default=None, help="External Trust Operations Control Signoff Archive ZIP.")
    verify_parser.add_argument("--trust-control-signoff-verification-report", type=Path, default=None, help="External Trust Operations Control Signoff verification report.")
    verify_parser.add_argument("--continuous-assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    verify_parser.add_argument("--continuous-assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    verify_parser.add_argument("--assurance-watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    verify_parser.add_argument("--assurance-watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    verify_parser.add_argument("--assurance-watch-signoff-archive", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff Archive ZIP.")
    verify_parser.add_argument("--assurance-watch-signoff-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff verification report.")
    verify_parser.add_argument("--final-handoff-package", type=Path, default=None, help="External Trust Operations Final Handoff ZIP.")
    verify_parser.add_argument("--final-handoff-verification-report", type=Path, default=None, help="External Trust Operations Final Handoff verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=256, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_assurance_watch_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Assurance Watch ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Assurance Watch ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-clear", action="store_true", help="Require the Watch queue to be clear.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external Assurance and Hub evidence.")
    _add_trust_operations_assurance_watch_source_args(verify_parser)
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_assurance_watch_signoff_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Assurance Watch Signoff Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Assurance Watch Signoff archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Assurance Watch Signoff evidence.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external Watch/Hub/Assurance evidence.")
    verify_parser.add_argument("--watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    verify_parser.add_argument("--watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    verify_parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--continuous-assurance-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_final_handoff_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Final Handoff ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Final Handoff ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Final Handoff evidence.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external source evidence.")
    _add_trust_operations_final_readiness_source_args(verify_parser)
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=256, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=96, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_assurance_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Continuous Assurance Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Assurance archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-passed", action="store_true", help="Require Assurance status to be passed.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external source evidence.")
    _add_trust_operations_assurance_source_args(verify_parser)
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_hub_runbook_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Hub Runbook ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Hub Runbook ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-completed", action="store_true", help="Require safe runbook actions to have run.")
    verify_parser.add_argument("--require-no-blocked", action="store_true", help="Require no blocked safe action results.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_hub_incident_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Incident Board ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-no-open-critical", action="store_true", help="Require no open critical incidents.")
    verify_parser.add_argument("--require-no-open-blocking", action="store_true", help="Require no open blocking incidents.")
    verify_parser.add_argument("--require-current-hub", action="store_true", help="Require external current Hub verification evidence.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_incident_knowledge_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Incident Knowledge ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-guards-passed", action="store_true", help="Require regression guards to have passed runs.")
    verify_parser.add_argument("--require-no-open-recurrence", action="store_true", help="Require no open incident recurrence.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_control_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Control ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Control ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-policy-passed", action="store_true", help="Require the control policy assessment to pass.")
    verify_parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=64, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=128, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def build_verify_trust_operations_control_signoff_parser() -> argparse.ArgumentParser:
    verify_parser = argparse.ArgumentParser(description="Verify a MusicForge Trust Operations Control Signoff Archive ZIP.")
    verify_parser.add_argument("zip_path", type=Path, help="Path to the Trust Operations Control Signoff archive ZIP to verify.")
    verify_parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    verify_parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    verify_parser.add_argument("--strict", action="store_true", help="Treat strict package checks as failures.")
    verify_parser.add_argument("--require-signed", action="store_true", help="Require signed Control Signoff evidence.")
    verify_parser.add_argument("--require-current", action="store_true", help="Require current external Control/Hub/Incident/Knowledge evidence.")
    verify_parser.add_argument("--control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    verify_parser.add_argument("--control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    verify_parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    verify_parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    verify_parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    verify_parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    verify_parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    verify_parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    verify_parser.add_argument("--max-zip-size-mb", type=int, default=32, help="Maximum compressed ZIP size in MiB.")
    verify_parser.add_argument("--max-uncompressed-size-mb", type=int, default=64, help="Maximum total uncompressed entry size in MiB.")
    verify_parser.add_argument("--max-entry-count", type=int, default=64, help="Maximum number of ZIP entries.")
    return verify_parser

def _add_trust_operations_assurance_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--control-signoff-archive", type=Path, default=None, help="External Trust Operations Control Signoff Archive ZIP.")
    parser.add_argument("--control-signoff-verification-report", type=Path, default=None, help="External Trust Operations Control Signoff verification report.")
    parser.add_argument("--control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    parser.add_argument("--control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--release-verification", type=Path, action="append", default=[], help="External Release ZIP verification report. Can be repeated.")
    parser.add_argument("--distribution-verification", type=Path, action="append", default=[], help="External Distribution package verification report. Can be repeated.")
    parser.add_argument("--submission-verification", type=Path, action="append", default=[], help="External Submission package verification report. Can be repeated.")
    parser.add_argument("--submission-evidence-verification", type=Path, action="append", default=[], help="External Submission Evidence verification report. Can be repeated.")
    parser.add_argument("--release-operations-verification", type=Path, action="append", default=[], help="External Release Operations verification report. Can be repeated.")

def build_public_trust_center_publication_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify MusicForge Public Trust Center Publication channels.")
    parser.add_argument("--center-id", default="ptc-default", help="Public Trust Center id.")
    parser.add_argument("--channel-id", default="public-release", help="Publication channel id.")
    parser.add_argument("--channel-name", default="Public Release Channel", help="Publication channel name.")
    parser.add_argument("--channel-type", default="public_release", help="Publication channel type.")
    parser.add_argument("--create-channel", action="store_true", help="Create the publication channel if needed.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the current publication report.")
    parser.add_argument("--export", action="store_true", help="Export the publication mirror directory.")
    parser.add_argument("--zip", action="store_true", help="Build the publication ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the publication ZIP.")
    parser.add_argument("--verify-mirror", action="store_true", help="Verify the publication mirror directory.")
    parser.add_argument("--mirror-dir", type=Path, default=None, help="External mirror directory to verify. Defaults to current export.")
    parser.add_argument("--publication-id", default=None, help="Publication id. Defaults to the current publication.")
    parser.add_argument("--revoke", action="store_true", help="Revoke the publication snapshot.")
    parser.add_argument("--supersede", action="store_true", help="Create a new publication and mark the previous current one superseded.")
    parser.add_argument("--reason", default="Public Trust Center publication operation.", help="Reason for revoke/supersede operations.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--deep", action="store_true", help="Run nested package verification.")
    parser.add_argument("--require-ready", action="store_true", default=True, help="Verifier requires ready publication state.")
    parser.add_argument("--no-require-ready", dest="require_ready", action="store_false", help="Do not require ready publication state.")
    parser.add_argument("--require-acceptance-board-signoff", action="store_true", default=True, help="Verifier requires Acceptance Board signoff.")
    parser.add_argument("--no-require-acceptance-board-signoff", dest="require_acceptance_board_signoff", action="store_false", help="Do not require Acceptance Board signoff.")
    parser.add_argument("--require-anchor-current", action="store_true", default=True, help="Verifier requires current anchor evidence.")
    parser.add_argument("--no-require-anchor-current", dest="require_anchor_current", action="store_false", help="Do not require current anchor evidence.")
    parser.add_argument("--require-no-revoked", action="store_true", help="Verifier fails revoked snapshots.")
    parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for revoke/supersede checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_public_trust_center_publication_monitor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run and export MusicForge Public Trust Center Publication monitoring.")
    parser.add_argument("--center-id", default="ptc-default", help="Public Trust Center id.")
    parser.add_argument("--channel-id", default="public-release", help="Publication channel id.")
    parser.add_argument("--monitor-id", default=None, help="Publication monitor id.")
    parser.add_argument("--run-id", default=None, help="Monitoring run id.")
    parser.add_argument("--create-monitor", action="store_true", help="Create a monitor if needed.")
    parser.add_argument("--monitor-name", default="Public Release Monitor", help="Monitor display name.")
    parser.add_argument("--publication-id", default=None, help="Publication id, or current.")
    parser.add_argument("--mirror-dir", type=Path, default=None, help="Mirror directory to monitor. Defaults to publication export dir.")
    parser.add_argument("--run", action="store_true", help="Run the monitor.")
    parser.add_argument("--export", action="store_true", help="Export the monitoring package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the monitoring ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the monitoring ZIP.")
    parser.add_argument("--ack-incident", default=None, help="Acknowledge an incident id.")
    parser.add_argument("--resolve-incident", default=None, help="Resolve an incident id.")
    parser.add_argument("--waive-incident", default=None, help="Waive an incident id.")
    parser.add_argument("--reopen-incident", default=None, help="Reopen an incident id.")
    parser.add_argument("--reason", default="Publication monitoring operation.", help="Reason for incident transitions.")
    parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json used for current/revoke checks.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-current", action="store_true", help="Verifier requires current external channel state.")
    parser.add_argument("--require-no-revoked", action="store_true", help="Verifier fails revoked/superseded monitored publications.")
    parser.add_argument("--require-ready", action="store_true", help="Verifier requires a passed monitoring run.")
    parser.add_argument("--require-no-drift", action="store_true", help="Verifier requires no critical/high drift.")
    parser.add_argument("--require-no-open-critical-incidents", action="store_true", help="Verifier requires no open critical incident.")
    parser.add_argument("--allow-waived-incidents", action="store_true", help="Allow waived high/critical incidents as warnings.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_hub_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, sign, and verify MusicForge Trust Operations Hub packages.")
    parser.add_argument("--hub-id", default=None, help="Trust Operations Hub id.")
    parser.add_argument("--name", default="Default Trust Operations Hub", help="Hub display name.")
    parser.add_argument("--create", action="store_true", help="Create the Hub if it does not exist.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Hub report.")
    parser.add_argument("--report-id", default=None, help="Hub report id. Defaults to current report when possible.")
    parser.add_argument("--export", action="store_true", help="Export the Hub package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Hub ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Hub ZIP.")
    parser.add_argument("--signoff", action="store_true", help="Sign off the verified Hub ZIP.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name for Hub signoff.")
    parser.add_argument("--reason", default="Trust Operations Hub operation.", help="Reason for signoff/change request/reset.")
    parser.add_argument("--force", action="store_true", help="Force signoff when allowed.")
    parser.add_argument("--override-reason", default="", help="Required reason for forced signoff.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Hub change request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a Hub change request id.")
    parser.add_argument("--reset-signoff", action="store_true", help="Reset Hub signoff with an approved change request.")
    parser.add_argument("--change-request-id", default=None, help="Change request id for reset.")
    parser.add_argument("--publication-channel-state", type=Path, default=None, help="External publication-channel-state.json.")
    parser.add_argument("--public-trust-center-verification", type=Path, default=None, help="External Public Trust Center verification report.")
    parser.add_argument("--publication-monitoring-verification", type=Path, default=None, help="External Publication Monitoring verification report.")
    parser.add_argument("--release-verification", type=Path, action="append", default=[], help="External Release ZIP verification report. Can be repeated.")
    parser.add_argument("--distribution-verification", type=Path, action="append", default=[], help="External Distribution package verification report. Can be repeated.")
    parser.add_argument("--submission-verification", type=Path, action="append", default=[], help="External Submission package verification report. Can be repeated.")
    parser.add_argument("--submission-evidence-verification", type=Path, action="append", default=[], help="External Submission Evidence verification report. Can be repeated.")
    parser.add_argument("--release-operations-verification", type=Path, action="append", default=[], help="External Release Operations verification report. Can be repeated.")
    parser.add_argument("--hub-signoff", type=Path, default=None, help="External Trust Operations Hub signoff sidecar JSON.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report used for signoff.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-ready", action="store_true", help="Verifier requires ready Hub.")
    parser.add_argument("--require-signed", action="store_true", help="Verifier requires Hub signoff summary.")
    parser.add_argument("--require-current", action="store_true", help="Verifier requires current external source evidence.")
    parser.add_argument("--require-no-critical-blockers", action="store_true", help="Verifier requires no critical blockers.")
    parser.add_argument("--require-publication-monitoring-clean", action="store_true", help="Verifier requires clean publication monitoring evidence.")
    parser.add_argument("--require-delivery-ready", action="store_true", help="Verifier requires full delivery-chain verification evidence.")
    parser.add_argument("--require-incident-closeout", action="store_true", help="Verifier requires Trust Operations Incident closeout evidence.")
    parser.add_argument("--require-incident-regression-guards", action="store_true", help="Verifier requires Trust Operations Incident Knowledge regression guard evidence.")
    parser.add_argument("--require-trust-controls", action="store_true", help="Verifier requires Trust Operations Control policy evidence.")
    parser.add_argument("--trust-control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    parser.add_argument("--trust-control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    parser.add_argument("--require-trust-control-signoff", action="store_true", help="Verifier requires Trust Operations Control Signoff archive evidence.")
    parser.add_argument("--trust-control-signoff-archive", type=Path, default=None, help="External Trust Operations Control Signoff Archive ZIP.")
    parser.add_argument("--trust-control-signoff-verification-report", type=Path, default=None, help="External Trust Operations Control Signoff verification report.")
    parser.add_argument("--require-continuous-assurance", action="store_true", help="Verifier requires Trust Operations Continuous Assurance evidence.")
    parser.add_argument("--continuous-assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    parser.add_argument("--continuous-assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--require-assurance-watch-clear", action="store_true", help="Verifier requires Trust Operations Assurance Watch clear evidence.")
    parser.add_argument("--assurance-watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    parser.add_argument("--assurance-watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    parser.add_argument("--require-assurance-watch-signoff", action="store_true", help="Verifier requires Trust Operations Assurance Watch Signoff archive evidence.")
    parser.add_argument("--assurance-watch-signoff-archive", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff Archive ZIP.")
    parser.add_argument("--assurance-watch-signoff-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_assurance_watch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify Trust Operations Assurance Watch queues.")
    parser.add_argument("--schedule-id", default="default", help="Assurance Watch schedule id.")
    parser.add_argument("--queue-id", default=None, help="Assurance Watch queue id.")
    parser.add_argument("--hub-id", default=None, help="Trust Operations Hub id.")
    parser.add_argument("--write-schedule", action="store_true", help="Create or update the Assurance Watch schedule.")
    parser.add_argument("--interval-days", type=int, default=None, help="Schedule interval in days.")
    parser.add_argument("--grace-days", type=int, default=None, help="Schedule grace window in days.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Watch queue.")
    parser.add_argument("--list", action="store_true", help="List Watch queues.")
    parser.add_argument("--export", action="store_true", help="Export the Watch archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Watch ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Watch ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-clear", action="store_true", default=True, help="Verifier requires the Watch queue to be clear.")
    parser.add_argument("--no-require-clear", dest="require_clear", action="store_false", help="Do not require the Watch queue to be clear.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    _add_trust_operations_assurance_watch_source_args(parser)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_assurance_watch_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign, archive, and verify Trust Operations Assurance Watch closeout evidence.")
    parser.add_argument("--queue-id", required=True, help="Assurance Watch queue id.")
    parser.add_argument("--refresh-closeout", action="store_true", help="Refresh the Assurance Watch closeout.")
    parser.add_argument("--sign", action="store_true", help="Sign the current passed closeout.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name.")
    parser.add_argument("--role", default="owner", help="Signer role.")
    parser.add_argument("--reason", default="Assurance Watch queue clear and verified.", help="Signoff/change request reason.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a signoff reset change request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a change request id.")
    parser.add_argument("--reset-signoff", default=None, help="Reset signoff with an approved change request id.")
    parser.add_argument("--export", action="store_true", help="Export the signoff archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the signoff archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the signoff archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-signed", action="store_true", default=True, help="Verifier requires signed evidence.")
    parser.add_argument("--no-require-signed", dest="require_signed", action="store_false", help="Do not require signed evidence.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    parser.add_argument("--watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    parser.add_argument("--watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--continuous-assurance-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_final_readiness_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, sign, archive, and verify Trust Operations Final Readiness handoff evidence.")
    parser.add_argument("--refresh-report", action="store_true", help="Refresh the Final Readiness report.")
    parser.add_argument("--create-certificate", action="store_true", help="Create the Final Readiness certificate.")
    parser.add_argument("--sign", action="store_true", help="Sign the Final Handoff.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name.")
    parser.add_argument("--role", default="owner", help="Signer role.")
    parser.add_argument("--reason", default="Trust Operations final readiness accepted.", help="Signoff/change request reason.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Final Handoff reset change request.")
    parser.add_argument("--approve-change-request", default=None, help="Approve a change request id.")
    parser.add_argument("--reset-signoff", default=None, help="Reset Final Handoff with an approved change request id.")
    parser.add_argument("--export", action="store_true", help="Export the Final Handoff directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Final Handoff ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Final Handoff ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-signed", action="store_true", default=True, help="Verifier requires signed evidence.")
    parser.add_argument("--no-require-signed", dest="require_signed", action="store_false", help="Do not require signed evidence.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    _add_trust_operations_final_readiness_source_args(parser)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_assurance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and verify Trust Operations Continuous Assurance archives.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--run-id", default=None, help="Assurance run id.")
    parser.add_argument("--policy-id", default="default", help="Assurance policy id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh and persist an Assurance run.")
    parser.add_argument("--list", action="store_true", help="List Assurance runs.")
    parser.add_argument("--export", action="store_true", help="Export the Assurance archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Assurance ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Assurance ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-passed", action="store_true", default=True, help="Verifier requires passed Assurance.")
    parser.add_argument("--no-require-passed", dest="require_passed", action="store_false", help="Do not require passed Assurance.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    _add_trust_operations_assurance_source_args(parser)
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_control_signoff_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sign, archive, and verify Trust Operations Controls.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--assessment-id", default=None, help="Control assessment id.")
    parser.add_argument("--sign", action="store_true", help="Sign the current Control verification evidence.")
    parser.add_argument("--signed-by", default="local-reviewer", help="Signer name.")
    parser.add_argument("--reason", default="Trust Operations control signoff operation.", help="Reason for signoff/change request/exception.")
    parser.add_argument("--request-exception", action="store_true", help="Request a Control exception.")
    parser.add_argument("--approve-exception", action="store_true", help="Approve a Control exception.")
    parser.add_argument("--reject-exception", action="store_true", help="Reject a Control exception.")
    parser.add_argument("--exception-id", default=None, help="Control exception id.")
    parser.add_argument("--control-id", default=None, help="Control id for an exception.")
    parser.add_argument("--requested-by", default="local-operator", help="Exception requester.")
    parser.add_argument("--approved-by", default="local-reviewer", help="Exception or CR approver.")
    parser.add_argument("--expires-at", default=None, help="Exception expiry timestamp.")
    parser.add_argument("--mitigation", default="", help="Exception mitigation note.")
    parser.add_argument("--create-change-request", action="store_true", help="Create a Control Signoff change request.")
    parser.add_argument("--approve-change-request", action="store_true", help="Approve a Control Signoff change request.")
    parser.add_argument("--change-request-id", default=None, help="Change request id.")
    parser.add_argument("--reset", action="store_true", help="Reset Control Signoff with an approved change request.")
    parser.add_argument("--export", action="store_true", help="Export the Control Signoff archive directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Control Signoff archive ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Control Signoff archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-signed", action="store_true", default=True, help="Verifier requires signed evidence.")
    parser.add_argument("--no-require-signed", dest="require_signed", action="store_false", help="Do not require signed evidence.")
    parser.add_argument("--require-current", action="store_true", default=True, help="Verifier requires current external evidence.")
    parser.add_argument("--no-require-current", dest="require_current", action="store_false", help="Do not require current external evidence.")
    parser.add_argument("--control-package", type=Path, default=None, help="External Trust Operations Control ZIP.")
    parser.add_argument("--control-verification-report", type=Path, default=None, help="External Trust Operations Control verification report.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_hub_runbook_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, run, export, and verify Trust Operations Hub Runbooks.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--report-id", default=None, help="Hub report id. Defaults to current report when possible.")
    parser.add_argument("--runbook-id", default=None, help="Runbook id. Defaults to current or new runbook.")
    parser.add_argument("--create", action="store_true", help="Create a runbook from the current Hub report.")
    parser.add_argument("--run-safe", action="store_true", help="Run only safe automated actions.")
    parser.add_argument("--export", action="store_true", help="Export the runbook package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the runbook ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the runbook ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-completed", action="store_true", help="Verifier requires completed runbook results.")
    parser.add_argument("--require-no-blocked", action="store_true", help="Verifier requires no blocked safe action results.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_hub_incidents_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, remediate, export, and verify Trust Operations Incidents.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--report-id", default=None, help="Hub report id. Defaults to current report.")
    parser.add_argument("--incident-id", default=None, help="Incident id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Incident Board from Hub blockers.")
    parser.add_argument("--list", action="store_true", help="List incidents.")
    parser.add_argument("--triage", action="store_true", help="Triage an incident.")
    parser.add_argument("--severity", default=None, help="Incident severity.")
    parser.add_argument("--owner", default="local-user", help="Triage owner.")
    parser.add_argument("--notes", default="", help="Triage notes.")
    parser.add_argument("--create-plan", action="store_true", help="Create a remediation plan.")
    parser.add_argument("--add-evidence", action="store_true", help="Add JSON verification evidence.")
    parser.add_argument("--evidence-kind", default="external_verification_report", help="Evidence kind.")
    parser.add_argument("--component-type", default=None, help="Evidence component type.")
    parser.add_argument("--component-id", default=None, help="Evidence component id.")
    parser.add_argument("--content-base64", default=None, help="Base64 encoded evidence JSON.")
    parser.add_argument("--evidence-file", type=Path, default=None, help="Evidence JSON file to read and import.")
    parser.add_argument("--verify-fix", action="store_true", help="Verify incident fix evidence.")
    parser.add_argument("--close", action="store_true", help="Close an incident.")
    parser.add_argument("--closed-by", default="local-user", help="Closeout actor.")
    parser.add_argument("--reason", default="Trust Operations incident remediated.", help="Closeout reason.")
    parser.add_argument("--archive", action="store_true", help="Archive a closed incident.")
    parser.add_argument("--export", action="store_true", help="Export the Incident Board package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Incident Board ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Incident Board ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-no-open-critical", action="store_true", help="Verifier requires no open critical incidents.")
    parser.add_argument("--require-no-open-blocking", action="store_true", help="Verifier requires no open blocking incidents.")
    parser.add_argument("--require-current-hub", action="store_true", help="Verifier requires current Hub verification evidence.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_incident_knowledge_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, run, export, and verify Trust Operations Incident Knowledge regression guards.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--refresh", action="store_true", help="Refresh Knowledge entries from closed incidents.")
    parser.add_argument("--list-entries", action="store_true", help="List Knowledge entries.")
    parser.add_argument("--entry-id", default=None, help="Knowledge entry id.")
    parser.add_argument("--hide-entry", action="store_true", help="Hide a Knowledge entry.")
    parser.add_argument("--unhide-entry", action="store_true", help="Unhide a Knowledge entry.")
    parser.add_argument("--create-guard", action="store_true", help="Create a regression guard for a Knowledge entry.")
    parser.add_argument("--guard-id", default=None, help="Regression guard id.")
    parser.add_argument("--guard-type", default=None, help="Regression guard type.")
    parser.add_argument("--run-guard", action="store_true", help="Run a single regression guard.")
    parser.add_argument("--run-all-guards", action="store_true", help="Run all regression guards.")
    parser.add_argument("--refresh-recurrence", action="store_true", help="Refresh incident recurrence report.")
    parser.add_argument("--export", action="store_true", help="Export the Knowledge package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Knowledge ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Knowledge ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-guards-passed", action="store_true", help="Verifier requires passed guard runs.")
    parser.add_argument("--require-no-open-recurrence", action="store_true", help="Verifier requires no open recurrence.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_trust_operations_controls_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create, assess, export, and verify Trust Operations Controls.")
    parser.add_argument("--hub-id", default="hub", help="Trust Operations Hub id.")
    parser.add_argument("--policy-id", default=None, help="Control policy id.")
    parser.add_argument("--assessment-id", default=None, help="Control assessment id.")
    parser.add_argument("--refresh-catalog", action="store_true", help="Refresh the Control Catalog.")
    parser.add_argument("--create-policy", action="store_true", help="Create a Control Policy Bundle.")
    parser.add_argument("--policy-name", default="Default Trust Operations Controls", help="Control policy display name.")
    parser.add_argument("--assess", action="store_true", help="Assess a Control Policy Bundle.")
    parser.add_argument("--export", action="store_true", help="Export the Control package directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Control ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Control ZIP.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")
    parser.add_argument("--incident-board-package", type=Path, default=None, help="External Trust Operations Incident Board ZIP.")
    parser.add_argument("--incident-board-verification-report", type=Path, default=None, help="External Trust Operations Incident Board verification report.")
    parser.add_argument("--incident-knowledge-package", type=Path, default=None, help="External Trust Operations Incident Knowledge ZIP.")
    parser.add_argument("--incident-knowledge-verification-report", type=Path, default=None, help="External Trust Operations Incident Knowledge verification report.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-policy-passed", action="store_true", help="Verifier requires the control policy assessment to pass.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_public_trust_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build local MusicForge Public Trust Center reports and packages.")
    parser.add_argument("--center-id", default="ptc-default", help="Public Trust Center id.")
    parser.add_argument("--name", default=None, help="Display name.")
    parser.add_argument("--release-id", action="append", dest="release_ids", default=[], help="Release id to include. Can be repeated.")
    parser.add_argument("--portfolio-id", action="append", dest="portfolio_ids", default=[], help="Portfolio id to include. Can be repeated.")
    parser.add_argument("--profile", default="public_summary", help="Attestation profile.")
    parser.add_argument("--refresh", action="store_true", help="Refresh the Public Trust Center report.")
    parser.add_argument("--export", action="store_true", help="Build the static Trust Center export directory.")
    parser.add_argument("--zip", action="store_true", help="Build the Public Trust Center ZIP.")
    parser.add_argument("--verify", action="store_true", help="Verify the Public Trust Center ZIP.")
    parser.add_argument("--archive", action="store_true", help="Append an archive event for the current ZIP.")
    parser.add_argument("--anchor-register", action="store_true", help="Register the current delivery anchor in the Anchor Registry.")
    parser.add_argument("--anchor-publish", action="store_true", help="Publish the current Anchor Registry entry.")
    parser.add_argument("--anchor-revoke", default=None, help="Revoke an Anchor Registry entry id.")
    parser.add_argument("--anchor-export", action="store_true", help="Export the Anchor Registry package directory.")
    parser.add_argument("--anchor-zip", action="store_true", help="Build the Anchor Registry ZIP.")
    parser.add_argument("--anchor-verify", action="store_true", help="Verify the Anchor Registry ZIP.")
    parser.add_argument("--anchor-reason", default="Public Trust Center anchor registry operation", help="Reason for Anchor Registry state changes.")
    parser.add_argument("--anchor-transparency-refresh", action="store_true", help="Refresh the Anchor Transparency ledger/report.")
    parser.add_argument("--anchor-checkpoint-create", action="store_true", help="Create the current Anchor Transparency checkpoint.")
    parser.add_argument("--anchor-transparency-export", action="store_true", help="Export the Anchor Transparency package directory.")
    parser.add_argument("--anchor-transparency-zip", action="store_true", help="Build the Anchor Transparency ZIP.")
    parser.add_argument("--anchor-transparency-verify", action="store_true", help="Verify the Anchor Transparency ZIP.")
    parser.add_argument("--distribution-kit-refresh", action="store_true", help="Refresh the Public Trust Center Distribution Kit report.")
    parser.add_argument("--distribution-kit-export", action="store_true", help="Export the Public Trust Center Distribution Kit directory.")
    parser.add_argument("--distribution-kit-zip", action="store_true", help="Build the Public Trust Center Distribution Kit ZIP.")
    parser.add_argument("--distribution-kit-verify", action="store_true", help="Verify the Public Trust Center Distribution Kit ZIP.")
    parser.add_argument("--distribution-kit-acceptance-template", action="store_true", help="Create a Distribution Kit external acceptance response template.")
    parser.add_argument("--distribution-kit-acceptance-response-file", type=Path, default=None, help="Import a Distribution Kit acceptance response JSON file.")
    parser.add_argument("--distribution-kit-acceptance-response-base64", default=None, help="Import a base64-encoded Distribution Kit acceptance response.")
    parser.add_argument("--distribution-kit-acceptance-response-id", default=None, help="Distribution Kit acceptance response id.")
    parser.add_argument("--distribution-kit-acceptance-verify-response", action="store_true", help="Verify an imported Distribution Kit acceptance response.")
    parser.add_argument("--distribution-kit-accepted-evidence-export", action="store_true", help="Export accepted Distribution Kit evidence for the response.")
    parser.add_argument("--distribution-kit-accepted-evidence-zip", action="store_true", help="Build accepted Distribution Kit evidence ZIP for the response.")
    parser.add_argument("--distribution-kit-accepted-evidence-verify", action="store_true", help="Verify the accepted Distribution Kit evidence ZIP.")
    parser.add_argument("--distribution-kit-acceptance-change-request", action="store_true", help="Create a draft follow-up from a needs_changes/rejected Distribution Kit response.")
    parser.add_argument("--acceptance-board-policy-save", type=Path, default=None, help="Save Acceptance Board policy from a JSON file.")
    parser.add_argument("--acceptance-board-refresh", action="store_true", help="Refresh the Acceptance Board report.")
    parser.add_argument("--acceptance-board-export", action="store_true", help="Export the Acceptance Board directory.")
    parser.add_argument("--acceptance-board-zip", action="store_true", help="Build the Acceptance Board ZIP.")
    parser.add_argument("--acceptance-board-verify", action="store_true", help="Verify the Acceptance Board ZIP.")
    parser.add_argument("--acceptance-board-signoff-draft", action="store_true", help="Create an Acceptance Board signoff draft.")
    parser.add_argument("--acceptance-board-signoff", action="store_true", help="Sign the current ready Acceptance Board.")
    parser.add_argument("--acceptance-board-signed-by", default="MusicForge Operator", help="Signer name for Acceptance Board signoff.")
    parser.add_argument("--acceptance-board-signoff-reason", default="Acceptance Board ready for public release.", help="Reason for Acceptance Board signoff.")
    parser.add_argument("--acceptance-board-change-request-create", action="store_true", help="Create an Acceptance Board signoff Change Request.")
    parser.add_argument("--acceptance-board-change-request-approve", action="store_true", help="Approve an Acceptance Board signoff Change Request.")
    parser.add_argument("--acceptance-board-change-request-id", default=None, help="Acceptance Board Change Request id.")
    parser.add_argument("--acceptance-board-reset-signoff", action="store_true", help="Reset Acceptance Board signoff using an approved Change Request.")
    parser.add_argument("--acceptance-board-signoff-archive-export", action="store_true", help="Export the Acceptance Board signoff archive directory.")
    parser.add_argument("--acceptance-board-signoff-archive-zip", action="store_true", help="Build the Acceptance Board signoff archive ZIP.")
    parser.add_argument("--acceptance-board-signoff-archive-verify", action="store_true", help="Verify the Acceptance Board signoff archive ZIP.")
    parser.add_argument("--strict", action="store_true", help="Use strict verifier mode.")
    parser.add_argument("--require-ready", action="store_true", help="Verifier requires ready board/package state.")
    parser.add_argument("--require-quorum", action="store_true", help="Verifier requires board quorum.")
    parser.add_argument("--require-no-conflicts", action="store_true", help="Verifier requires no board conflicts.")
    parser.add_argument("--min-accepted-count", type=int, default=0, help="Minimum accepted evidence count required by the verifier.")
    parser.add_argument("--min-accepted-organizations", type=int, default=0, help="Minimum accepted organization count required by the verifier.")
    parser.add_argument("--required-role", action="append", dest="required_roles", default=[], help="Required Acceptance Board role. Can be repeated.")
    parser.add_argument("--require-registry-current", action="store_true", help="Require current Registry evidence.")
    parser.add_argument("--require-portal-current", action="store_true", help="Require current Portal evidence.")
    parser.add_argument("--require-transparency-current", action="store_true", help="Require current Transparency evidence.")
    parser.add_argument("--require-acknowledgement-current", action="store_true", help="Require current accepted acknowledgement evidence.")
    parser.add_argument("--include-delivery", dest="include_delivery", action="store_true", default=True, help="Include delivery chain summaries.")
    parser.add_argument("--no-include-delivery", dest="include_delivery", action="store_false", help="Do not include delivery chain summaries.")
    parser.add_argument("--include-distribution", dest="include_distribution", action="store_true", default=True, help="Include Distribution target summaries.")
    parser.add_argument("--no-include-distribution", dest="include_distribution", action="store_false", help="Do not include Distribution target summaries.")
    parser.add_argument("--include-submission", dest="include_submission", action="store_true", default=True, help="Include Submission batch summaries.")
    parser.add_argument("--no-include-submission", dest="include_submission", action="store_false", help="Do not include Submission batch summaries.")
    parser.add_argument("--include-submission-evidence", dest="include_submission_evidence", action="store_true", default=True, help="Include Submission Evidence summaries.")
    parser.add_argument("--no-include-submission-evidence", dest="include_submission_evidence", action="store_false", help="Do not include Submission Evidence summaries.")
    parser.add_argument("--include-operations", dest="include_operations", action="store_true", default=True, help="Include Release Operations summaries.")
    parser.add_argument("--no-include-operations", dest="include_operations", action="store_false", help="Do not include Release Operations summaries.")
    parser.add_argument("--require-release-signoff", dest="require_release_signoff", action="store_true", default=True, help="Require Release Signoff in the Trust Center report.")
    parser.add_argument("--no-require-release-signoff", dest="require_release_signoff", action="store_false", help="Do not require Release Signoff in the Trust Center report.")
    parser.add_argument("--require-distribution-signed", action="store_true", help="Require signed and verified Distribution packages in the report.")
    parser.add_argument("--require-submission-accepted", action="store_true", help="Require accepted Submission batches in the report.")
    parser.add_argument("--require-submission-evidence-signed", action="store_true", help="Require signed Submission Evidence packages in the report.")
    parser.add_argument("--require-operations-signed", action="store_true", help="Require Release Operations Signoff in the report.")
    parser.add_argument("--require-operations-audit-verified", action="store_true", help="Require verified Release Operations Audit evidence in the report.")
    parser.add_argument("--require-operations-reviewer-pack-verified", action="store_true", help="Require verified Release Operations Reviewer Pack evidence in the report.")
    parser.add_argument("--require-release-readiness", action="store_true", help="Verifier requires selected releases to be ready.")
    parser.add_argument("--require-delivery-readiness", action="store_true", help="Verifier requires delivery readiness.")
    parser.add_argument("--require-distribution-ready", action="store_true", help="Verifier requires distribution readiness.")
    parser.add_argument("--require-submission-evidence", action="store_true", help="Verifier requires submission evidence.")
    parser.add_argument("--require-operations-audit", action="store_true", help="Verifier requires operations audit evidence.")
    parser.add_argument("--require-operations-reviewer-pack", action="store_true", help="Verifier requires operations reviewer pack evidence.")
    parser.add_argument("--require-anchor-registry-current", action="store_true", help="Verifier requires current Anchor Registry evidence.")
    parser.add_argument("--require-anchor-published", action="store_true", help="Verifier requires a published Anchor Registry current entry.")
    parser.add_argument("--require-anchor-not-revoked", action="store_true", help="Verifier requires the Anchor Registry current entry not to be revoked.")
    parser.add_argument("--require-anchor-transparency-current", action="store_true", help="Verifier requires current Anchor Transparency evidence.")
    parser.add_argument("--require-anchor-checkpoint", action="store_true", help="Verifier requires an external Anchor Transparency checkpoint.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def _trust_operations_assurance_source_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "hub_package_path": getattr(args, "hub_package", None),
        "hub_verification_report_path": getattr(args, "hub_verification_report", None),
        "control_signoff_archive_path": getattr(args, "control_signoff_archive", None),
        "control_signoff_verification_report_path": getattr(args, "control_signoff_verification_report", None),
        "control_package_path": getattr(args, "control_package", None),
        "control_verification_report_path": getattr(args, "control_verification_report", None),
        "incident_board_package_path": getattr(args, "incident_board_package", None),
        "incident_board_verification_report_path": getattr(args, "incident_board_verification_report", None),
        "incident_knowledge_package_path": getattr(args, "incident_knowledge_package", None),
        "incident_knowledge_verification_report_path": getattr(args, "incident_knowledge_verification_report", None),
        "release_verification_paths": getattr(args, "release_verification", []),
        "distribution_verification_paths": getattr(args, "distribution_verification", []),
        "submission_verification_paths": getattr(args, "submission_verification", []),
        "submission_evidence_verification_paths": getattr(args, "submission_evidence_verification", []),
        "release_operations_verification_paths": getattr(args, "release_operations_verification", []),
    }

def _add_trust_operations_assurance_watch_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    parser.add_argument("--assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--hub-package", type=Path, default=None, help="External Trust Operations Hub ZIP.")
    parser.add_argument("--hub-verification-report", type=Path, default=None, help="External Trust Operations Hub verification report.")

def _trust_operations_assurance_watch_source_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "assurance_archive_path": getattr(args, "assurance_archive", None),
        "assurance_verification_report_path": getattr(args, "assurance_verification_report", None),
        "hub_package_path": getattr(args, "hub_package", None),
        "hub_verification_report_path": getattr(args, "hub_verification_report", None),
    }

def _add_trust_operations_final_readiness_source_args(parser: argparse.ArgumentParser) -> None:
    _add_trust_operations_assurance_source_args(parser)
    parser.add_argument("--continuous-assurance-archive", type=Path, default=None, help="External Trust Operations Continuous Assurance Archive ZIP.")
    parser.add_argument("--continuous-assurance-verification-report", type=Path, default=None, help="External Trust Operations Continuous Assurance verification report.")
    parser.add_argument("--assurance-watch-package", type=Path, default=None, help="External Trust Operations Assurance Watch ZIP.")
    parser.add_argument("--assurance-watch-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch verification report.")
    parser.add_argument("--assurance-watch-signoff-archive", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff Archive ZIP.")
    parser.add_argument("--assurance-watch-signoff-verification-report", type=Path, default=None, help="External Trust Operations Assurance Watch Signoff verification report.")

def _trust_operations_final_readiness_source_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = _trust_operations_assurance_source_payload(args)
    payload.update(
        {
            "continuous_assurance_archive_path": getattr(args, "continuous_assurance_archive", None),
            "continuous_assurance_verification_report_path": getattr(args, "continuous_assurance_verification_report", None),
            "assurance_watch_package_path": getattr(args, "assurance_watch_package", None),
            "assurance_watch_verification_report_path": getattr(args, "assurance_watch_verification_report", None),
            "assurance_watch_signoff_archive_path": getattr(args, "assurance_watch_signoff_archive", None),
            "assurance_watch_signoff_verification_report_path": getattr(args, "assurance_watch_signoff_verification_report", None),
        }
    )
    return payload

def print_release_portfolio_audit_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    portfolio = result.get("portfolio") if isinstance(result.get("portfolio"), dict) else {}
    print("MusicForge release-portfolio-audit")
    print(f"portfolio: {result.get('portfolio_id') or portfolio.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or portfolio.get('status') or '-'}")
    print(f"releases: {summary.get('release_count', 0)}")
    print(f"risk_score: {summary.get('risk_score') if summary.get('risk_score') is not None else '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("portfolios") is not None:
        print(f"portfolios: {len(result.get('portfolios') or [])}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    queue = result.get("queue") if isinstance(result.get("queue"), dict) else {}
    print("MusicForge release-portfolio-governance-queue")
    print(f"queue: {result.get('queue_id') or queue.get('queue_id') or '-'}")
    print(f"portfolio: {queue.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or queue.get('status') or '-'}")
    print(f"items: {summary.get('total_items', 0)}")
    print(f"safe_completed: {summary.get('safe_completed', 0)}")
    print(f"manual_required: {summary.get('manual_required', 0)}")
    print(f"blocked: {summary.get('blocked', 0)}")
    print(f"failed: {summary.get('failed', 0)}")
    if result.get("queues") is not None:
        print(f"queues: {len(result.get('queues') or [])}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_signoff_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    archive = result.get("archive_summary") if isinstance(result.get("archive_summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-signoff")
    print(f"queue: {result.get('queue_id') or summary.get('queue_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"integrity: {summary.get('integrity_ok', False)}")
    if archive:
        print(f"archive: {archive.get('status') or '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_audit_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-audit")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"queues: {summary.get('queue_count', 0)}")
    print(f"signed_queues: {summary.get('signed_queue_count', 0)}")
    print(f"archive_verified: {summary.get('archive_verified_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_reviewer_pack_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-reviewer-pack")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"audit: {summary.get('audit_status') or '-'}")
    print(f"queues: {summary.get('queue_count', 0)}")
    print(f"signed_queues: {summary.get('signed_queue_count', 0)}")
    print(f"archive_verified: {summary.get('archive_verified_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_final_board_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    signoff = result.get("signoff_summary") if isinstance(result.get("signoff_summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-final-board")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"reviewer_response: {summary.get('reviewer_response_status') or '-'}")
    print(f"audit: {summary.get('audit_verification_status') or '-'}")
    print(f"reviewer_pack: {summary.get('reviewer_pack_verification_status') or '-'}")
    print(f"signoff: {signoff.get('status') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_evidence_vault_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-evidence-vault")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"final_board: {summary.get('final_board_signoff_status') or '-'}")
    print(f"nested_required: {summary.get('required_package_count', 0)}")
    print(f"nested_current: {summary.get('current_required_package_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_attestation_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    certificate = result.get("certificate") if isinstance(result.get("certificate"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"certificate: {certificate.get('certificate_id') or summary.get('certificate_id') or '-'}")
    print(f"vault: {summary.get('vault_verification_status') or '-'} / deep {summary.get('deep_verification_status') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_attestation_registry_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    entry = result.get("entry") if isinstance(result.get("entry"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation-registry")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"published: {summary.get('published_count', 0)}")
    print(f"revoked: {summary.get('revoked_count', 0)}")
    if entry:
        print(f"entry: {entry.get('entry_id') or '-'} / {entry.get('status') or '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_attestation_portal_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation-portal")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    print(f"current certificate: {summary.get('current_certificate_id') or '-'}")
    print(f"registry: {summary.get('registry_status') or '-'}")
    print(f"attestation: {summary.get('attestation_status') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_portfolio_governance_attestation_portal_review_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    response = result.get("response") if isinstance(result.get("response"), dict) else {}
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    response_verification = result.get("response_verification") if isinstance(result.get("response_verification"), dict) else {}
    change = result.get("change_request") if isinstance(result.get("change_request"), dict) else {}
    print("MusicForge release-portfolio-governance-attestation-portal-review")
    print(f"portfolio: {result.get('portfolio_id') or '-'}")
    print(f"profile: {result.get('profile') or summary.get('profile') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"review pack: {summary.get('review_pack_id') or '-'}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify pack: {verification.get('status')}")
    if response:
        print(f"response: {response.get('response_id') or '-'} / {response.get('decision') or '-'}")
    if response_verification:
        print(f"verify response: {response_verification.get('status')}")
    if change:
        print(f"change request: {change.get('change_request_id') or '-'} / {change.get('status') or '-'}")

def print_release_portfolio_governance_attestation_accepted_evidence_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    evidence = result.get("accepted_evidence") if isinstance(result.get("accepted_evidence"), dict) else {}
    print("MusicForge release portfolio governance attestation accepted evidence")
    print(f"portfolio: {result.get('portfolio_id')}")
    print(f"status: {summary.get('status') or evidence.get('status') or 'missing'}")
    print(f"external review: {summary.get('external_review_status') or 'missing'}")
    print(f"accepted evidence: {summary.get('accepted_evidence_id') or evidence.get('accepted_evidence_id') or '-'}")
    print(f"response: {summary.get('response_id') or '-'}")
    if result.get("verification"):
        print(f"verification: {result.get('verification', {}).get('status')}")

def print_release_portfolio_governance_attestation_transparency_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    print("MusicForge release portfolio governance attestation transparency")
    print(f"portfolio: {result.get('portfolio_id')}")
    print(f"status: {summary.get('status') or 'missing'}")
    print(f"current entry: {summary.get('current_entry_id') or '-'}")
    print(f"external review: {summary.get('external_review_status') or 'missing'}")
    print(f"events: {summary.get('event_count', 0)}")
    print(f"notices: {summary.get('notice_count', 0)}")
    if result.get("verification"):
        print(f"verification: {result.get('verification', {}).get('status')}")

def print_release_portfolio_governance_attestation_transparency_acknowledgement_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    evidence_summary = result.get("evidence_summary") if isinstance(result.get("evidence_summary"), dict) else {}
    response = result.get("response") if isinstance(result.get("response"), dict) else {}
    print("MusicForge release portfolio governance attestation transparency acknowledgement")
    print(f"portfolio: {result.get('portfolio_id')}")
    print(f"pack: {summary.get('status') or 'missing'} / {summary.get('pack_id') or '-'}")
    if response:
        print(f"response: {response.get('response_id') or '-'} / {response.get('status') or '-'}")
    if evidence_summary:
        print(f"evidence: {evidence_summary.get('status') or 'missing'} / {evidence_summary.get('acknowledgement_id') or '-'}")
    if result.get("pack_verification"):
        print(f"pack verification: {result.get('pack_verification', {}).get('status')}")
    if result.get("evidence_verification"):
        print(f"evidence verification: {result.get('evidence_verification', {}).get('status')}")
    if result.get("change_request"):
        change = result["change_request"]
        print(f"change request: {change.get('change_request_id') or '-'} / {change.get('status') or '-'}")

def print_public_trust_center_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification") if isinstance(result.get("verification"), dict) else {}
    print("MusicForge public-trust-center")
    print(f"center: {result.get('center_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"readiness: {summary.get('readiness') or '-'}")
    print(f"stale: {summary.get('stale', result.get('stale', False))}")
    print(f"releases: {summary.get('release_count', 0)}")
    print(f"portfolios: {summary.get('portfolio_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('sha256') or (result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def _build_release_portfolio_governance_attestation_portal_store():
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
    from song_agent.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore
    from song_agent.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore
    from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
    from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore

    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    registry_store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
    return ReleasePortfolioGovernanceAttestationPortalStore(registry_store=registry_store, attestation_store=attestation_store)

def _build_public_trust_center_store():
    from song_agent.public_trust_center import PublicTrustCenterStore
    from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
    from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore
    from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore

    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    acknowledgement_store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(transparency_store=transparency_store)
    portfolio_store = portal_store.attestation_store.portfolio_store
    return PublicTrustCenterStore(
        release_store=portfolio_store.release_store,
        portfolio_store=portfolio_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        transparency_store=transparency_store,
        acknowledgement_store=acknowledgement_store,
        distribution_store=portfolio_store.operations_store.distribution_store,
        submission_store=portfolio_store.operations_store.submission_store,
        submission_evidence_store=portfolio_store.operations_store.submission_evidence_store,
        operations_store=portfolio_store.operations_store,
        operations_runbook_store=portfolio_store.runbook_store,
        operations_signoff_store=portfolio_store.signoff_store,
        operations_audit_store=portfolio_store.audit_store,
        operations_reviewer_pack_store=portfolio_store.reviewer_pack_store,
    )

def _build_public_trust_center_publication_store():
    from song_agent.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore
    from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
    from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore
    from song_agent.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore
    from song_agent.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore
    from song_agent.public_trust_center_publication import PublicTrustCenterPublicationStore

    trust_store = _build_public_trust_center_store()
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    distribution_kit_store = PublicTrustCenterDistributionKitStore(
        trust_center_store=trust_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
    )
    acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
    board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=acceptance_store)
    return PublicTrustCenterPublicationStore(
        trust_center_store=trust_store,
        distribution_kit_store=distribution_kit_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
        acceptance_store=acceptance_store,
        acceptance_board_store=board_store,
    )

def _execute_verify_release_portfolio_audit_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-audit-package', *argv]
    from song_agent.release_portfolio_audit_verifier import (
        print_release_portfolio_audit_verification_report,
        release_portfolio_audit_verification_exit_code,
        verify_release_portfolio_audit_package,
        write_release_portfolio_audit_verification_report,
    )
    parser = build_verify_release_portfolio_audit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_audit_package(
        args.zip_path,
        strict=args.strict,
        require_reviewer_packs=args.require_reviewer_packs,
        require_audit=args.require_audit,
        require_archive=args.require_archive,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_audit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_audit_verification_report(report)
    raise SystemExit(release_portfolio_audit_verification_exit_code(report))


def handle_verify_release_portfolio_audit_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_audit_package(argv)

def _execute_verify_release_portfolio_governance_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-package', *argv]
    from song_agent.release_portfolio_governance_verifier import (
        print_release_portfolio_governance_verification_report,
        release_portfolio_governance_verification_exit_code,
        verify_release_portfolio_governance_package,
        write_release_portfolio_governance_verification_report,
    )
    parser = build_verify_release_portfolio_governance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_package(
        args.zip_path,
        strict=args.strict,
        require_manual_actions=args.require_manual_actions,
        require_no_blocked=args.require_no_blocked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_verification_report(report)
    raise SystemExit(release_portfolio_governance_verification_exit_code(report))


def handle_verify_release_portfolio_governance_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_package(argv)

def _execute_verify_release_portfolio_governance_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-archive-package', *argv]
    from song_agent.release_portfolio_governance_archive_verifier import (
        print_release_portfolio_governance_archive_verification_report,
        release_portfolio_governance_archive_verification_exit_code,
        verify_release_portfolio_governance_archive_package,
        write_release_portfolio_governance_archive_verification_report,
    )
    parser = build_verify_release_portfolio_governance_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_no_force=args.require_no_force,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_archive_verification_report(report)
    raise SystemExit(release_portfolio_governance_archive_verification_exit_code(report))


def handle_verify_release_portfolio_governance_archive_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_archive_package(argv)

def _execute_verify_release_portfolio_governance_audit_package(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-audit-package', *argv]
    from song_agent.release_portfolio_governance_audit_verifier import (
        print_release_portfolio_governance_audit_verification_report,
        release_portfolio_governance_audit_verification_exit_code,
        verify_release_portfolio_governance_audit_package,
        write_release_portfolio_governance_audit_verification_report,
    )
    parser = build_verify_release_portfolio_governance_audit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_audit_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_archives=args.require_archives,
        require_no_force=args.require_no_force,
        require_reset_cr_causality=args.require_reset_cr_causality,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_audit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_audit_verification_report(report)
    raise SystemExit(release_portfolio_governance_audit_verification_exit_code(report))


def handle_verify_release_portfolio_governance_audit_package(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_audit_package(argv)

def _execute_verify_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-reviewer-pack', *argv]
    from song_agent.release_portfolio_governance_reviewer_pack_verifier import (
        print_release_portfolio_governance_reviewer_pack_verification_report,
        release_portfolio_governance_reviewer_pack_verification_exit_code,
        verify_release_portfolio_governance_reviewer_pack,
        write_release_portfolio_governance_reviewer_pack_verification_report,
    )
    parser = build_verify_release_portfolio_governance_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_reviewer_pack(
        args.zip_path,
        strict=args.strict,
        require_audit=args.require_audit,
        require_signed=args.require_signed,
        require_archives=args.require_archives,
        require_no_force=args.require_no_force,
        require_reset_cr_causality=args.require_reset_cr_causality,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_reviewer_pack_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_reviewer_pack_verification_report(report)
    raise SystemExit(release_portfolio_governance_reviewer_pack_verification_exit_code(report))


def handle_verify_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_reviewer_pack(argv)

def _execute_verify_release_portfolio_governance_final_board(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-final-board', *argv]
    from song_agent.release_portfolio_governance_final_board_verifier import (
        print_release_portfolio_governance_final_board_verification_report,
        release_portfolio_governance_final_board_verification_exit_code,
        verify_release_portfolio_governance_final_board_package,
        write_release_portfolio_governance_final_board_verification_report,
    )
    parser = build_verify_release_portfolio_governance_final_board_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_final_board_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_reviewer_pack=args.require_reviewer_pack,
        require_audit=args.require_audit,
        require_archives=args.require_archives,
        require_reviewer_response=args.require_reviewer_response,
        require_no_force=args.require_no_force,
        require_reset_cr_causality=args.require_reset_cr_causality,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_final_board_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_final_board_verification_report(report)
    raise SystemExit(release_portfolio_governance_final_board_verification_exit_code(report))


def handle_verify_release_portfolio_governance_final_board(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_final_board(argv)

def _execute_verify_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-evidence-vault', *argv]
    from song_agent.release_portfolio_governance_evidence_vault_verifier import (
        print_release_portfolio_governance_evidence_vault_verification_report,
        release_portfolio_governance_evidence_vault_verification_exit_code,
        verify_release_portfolio_governance_evidence_vault_package,
        write_release_portfolio_governance_evidence_vault_verification_report,
    )
    parser = build_verify_release_portfolio_governance_evidence_vault_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_evidence_vault_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_final_board=args.require_final_board,
        require_reviewer_pack=args.require_reviewer_pack,
        require_audit=args.require_audit,
        require_archives=args.require_archives,
        require_queue_packages=args.require_queue_packages,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_evidence_vault_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_evidence_vault_verification_report(report)
    raise SystemExit(release_portfolio_governance_evidence_vault_verification_exit_code(report))


def handle_verify_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_evidence_vault(argv)

def _execute_verify_release_portfolio_governance_attestation(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation', *argv]
    from song_agent.release_portfolio_governance_attestation_verifier import (
        print_release_portfolio_governance_attestation_verification_report,
        release_portfolio_governance_attestation_verification_exit_code,
        verify_release_portfolio_governance_attestation,
        write_release_portfolio_governance_attestation_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation(
        args.zip_path,
        strict=args.strict,
        require_vault=args.require_vault,
        require_final_board=args.require_final_board,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation(argv)

def _execute_verify_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-registry', *argv]
    from song_agent.release_portfolio_governance_attestation_registry_verifier import (
        print_release_portfolio_governance_attestation_registry_verification_report,
        release_portfolio_governance_attestation_registry_verification_exit_code,
        verify_release_portfolio_governance_attestation_registry,
        write_release_portfolio_governance_attestation_registry_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_registry_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_registry(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_published=args.require_published,
        require_no_revoked_current=args.require_no_revoked_current,
        require_accepted_evidence=args.require_accepted_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_registry_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_registry_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_registry_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_registry(argv)

def _execute_verify_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-portal', *argv]
    from song_agent.release_portfolio_governance_attestation_portal_verifier import (
        print_release_portfolio_governance_attestation_portal_verification_report,
        release_portfolio_governance_attestation_portal_verification_exit_code,
        verify_release_portfolio_governance_attestation_portal,
        write_release_portfolio_governance_attestation_portal_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_portal_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_portal(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_registry=args.require_registry,
        require_attestation=args.require_attestation,
        require_accepted_evidence=args.require_accepted_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_portal_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_portal_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_portal(argv)

def _execute_verify_release_portfolio_governance_attestation_portal_review_pack(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-portal-review-pack', *argv]
    from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
        print_release_portfolio_governance_attestation_portal_review_pack_verification_report,
        release_portfolio_governance_attestation_portal_review_verification_exit_code,
        verify_release_portfolio_governance_attestation_portal_review_pack,
        write_release_portfolio_governance_attestation_portal_review_pack_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_portal_review_pack_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_portal_review_pack(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_portal_review_pack_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_review_pack_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_portal_review_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation_portal_review_pack(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_portal_review_pack(argv)

def _execute_verify_release_portfolio_governance_attestation_portal_response(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-portal-response', *argv]
    from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
        print_release_portfolio_governance_attestation_portal_response_verification_report,
        release_portfolio_governance_attestation_portal_review_verification_exit_code,
        verify_release_portfolio_governance_attestation_portal_response,
        write_release_portfolio_governance_attestation_portal_response_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_portal_response_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_portal_response(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_pack=args.require_pack,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_portal_response_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_response_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_portal_review_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation_portal_response(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_portal_response(argv)

def _execute_verify_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-accepted-evidence', *argv]
    from song_agent.release_portfolio_governance_attestation_accepted_evidence_verifier import (
        print_release_portfolio_governance_attestation_accepted_evidence_verification_report,
        release_portfolio_governance_attestation_accepted_evidence_verification_exit_code,
        verify_release_portfolio_governance_attestation_accepted_evidence,
        write_release_portfolio_governance_attestation_accepted_evidence_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_accepted_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_accepted_evidence(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_accepted_evidence_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_accepted_evidence_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_accepted_evidence_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_accepted_evidence(argv)

def _execute_verify_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-transparency', *argv]
    from song_agent.release_portfolio_governance_attestation_transparency_verifier import (
        print_release_portfolio_governance_attestation_transparency_verification_report,
        release_portfolio_governance_attestation_transparency_verification_exit_code,
        verify_release_portfolio_governance_attestation_transparency,
        write_release_portfolio_governance_attestation_transparency_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_transparency_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_transparency(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_accepted_evidence=args.require_accepted_evidence,
        require_no_revoked_current=args.require_no_revoked_current,
        require_contiguous_chain=args.require_contiguous_chain,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_transparency_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_transparency_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_transparency(argv)

def _execute_verify_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    raw_args = ['verify-release-portfolio-governance-attestation-transparency-acknowledgement', *argv]
    from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import (
        print_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
        release_portfolio_governance_attestation_transparency_acknowledgement_verification_exit_code,
        verify_release_portfolio_governance_attestation_transparency_acknowledgement_package,
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
    )
    parser = build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
        args.zip_path,
        strict=args.strict,
        require_pack=args.require_pack,
        require_response=args.require_response,
        require_accepted=args.require_accepted,
        require_transparency=args.require_transparency,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report)
    raise SystemExit(release_portfolio_governance_attestation_transparency_acknowledgement_verification_exit_code(report))


def handle_verify_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    _execute_verify_release_portfolio_governance_attestation_transparency_acknowledgement(argv)

def _execute_verify_public_trust_center_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-package', *argv]
    from song_agent.public_trust_center_verifier import (
        print_public_trust_center_verification_report,
        public_trust_center_verification_exit_code,
        verify_public_trust_center_package,
        write_public_trust_center_verification_report,
    )
    parser = build_verify_public_trust_center_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_package(
        args.zip_path,
        strict=args.strict,
        require_release_readiness=args.require_release_readiness,
        require_public_attestation=args.require_public_attestation,
        require_registry_current=args.require_registry_current,
        require_portal_current=args.require_portal_current,
        require_transparency_current=args.require_transparency_current,
        require_acknowledgement_current=args.require_acknowledgement_current,
        require_delivery_readiness=args.require_delivery_readiness,
        require_distribution_ready=args.require_distribution_ready,
        require_submission_accepted=args.require_submission_accepted,
        require_submission_evidence=args.require_submission_evidence,
        require_operations_signed=args.require_operations_signed,
        require_operations_audit=args.require_operations_audit,
        require_operations_reviewer_pack=args.require_operations_reviewer_pack,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        delivery_anchor_path=args.delivery_anchor,
        anchor_registry_path=args.anchor_registry,
        anchor_transparency_path=args.anchor_transparency,
        anchor_checkpoint_path=args.anchor_checkpoint,
        acceptance_board_signoff_archive_path=args.acceptance_board_signoff_archive,
        acceptance_board_path=args.acceptance_board,
        acceptance_board_verification_report_path=args.acceptance_board_verification_report,
        distribution_kit_path=args.distribution_kit,
        accepted_evidence_dir=args.accepted_evidence_dir,
        require_anchor_registry_current=args.require_anchor_registry_current,
        require_anchor_published=args.require_anchor_published,
        require_anchor_not_revoked=args.require_anchor_not_revoked,
        require_anchor_transparency_current=args.require_anchor_transparency_current,
        require_anchor_checkpoint=args.require_anchor_checkpoint,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_verification_report(report)
    raise SystemExit(public_trust_center_verification_exit_code(report))


def handle_verify_public_trust_center_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_package(argv)

def _execute_verify_public_trust_center_anchor_registry_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-anchor-registry-package', *argv]
    from song_agent.public_trust_center_anchor_registry_verifier import (
        print_public_trust_center_anchor_registry_verification_report,
        public_trust_center_anchor_registry_verification_exit_code,
        verify_public_trust_center_anchor_registry_package,
        write_public_trust_center_anchor_registry_verification_report,
    )
    parser = build_verify_public_trust_center_anchor_registry_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_anchor_registry_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_anchor_published=args.require_anchor_published,
        require_anchor_not_revoked=args.require_anchor_not_revoked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_anchor_registry_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_anchor_registry_verification_report(report)
    raise SystemExit(public_trust_center_anchor_registry_verification_exit_code(report))


def handle_verify_public_trust_center_anchor_registry_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_anchor_registry_package(argv)

def _execute_verify_public_trust_center_anchor_transparency_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-anchor-transparency-package', *argv]
    from song_agent.public_trust_center_anchor_transparency_verifier import (
        print_public_trust_center_anchor_transparency_verification_report,
        public_trust_center_anchor_transparency_verification_exit_code,
        verify_public_trust_center_anchor_transparency_package,
        write_public_trust_center_anchor_transparency_verification_report,
    )
    parser = build_verify_public_trust_center_anchor_transparency_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_anchor_transparency_package(
        args.zip_path,
        strict=args.strict,
        checkpoint_path=args.checkpoint,
        anchor_registry_path=args.anchor_registry,
        require_current_checkpoint=args.require_current_checkpoint,
        require_published_anchor=args.require_published_anchor,
        require_not_revoked=args.require_not_revoked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_anchor_transparency_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_anchor_transparency_verification_report(report)
    raise SystemExit(public_trust_center_anchor_transparency_verification_exit_code(report))


def handle_verify_public_trust_center_anchor_transparency_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_anchor_transparency_package(argv)

def _execute_verify_public_trust_center_distribution_kit_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-distribution-kit-package', *argv]
    from song_agent.public_trust_center_distribution_kit_verifier import (
        print_public_trust_center_distribution_kit_verification_report,
        public_trust_center_distribution_kit_verification_exit_code,
        verify_public_trust_center_distribution_kit_package,
        write_public_trust_center_distribution_kit_verification_report,
    )
    parser = build_verify_public_trust_center_distribution_kit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_distribution_kit_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_current=args.require_current,
        require_delivery_readiness=args.require_delivery_readiness,
        require_anchor_registry_current=args.require_anchor_registry_current,
        require_anchor_published=args.require_anchor_published,
        require_anchor_not_revoked=args.require_anchor_not_revoked,
        require_anchor_transparency_current=args.require_anchor_transparency_current,
        require_anchor_checkpoint=args.require_anchor_checkpoint,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        acceptance_board_signoff_archive_path=args.acceptance_board_signoff_archive,
        acceptance_board_path=args.acceptance_board,
        acceptance_board_verification_report_path=args.acceptance_board_verification_report,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_distribution_kit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_distribution_kit_verification_report(report)
    raise SystemExit(public_trust_center_distribution_kit_verification_exit_code(report))


def handle_verify_public_trust_center_distribution_kit_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_distribution_kit_package(argv)

def _execute_verify_public_trust_center_distribution_kit_accepted_evidence_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-distribution-kit-accepted-evidence-package', *argv]
    from song_agent.public_trust_center_distribution_kit_acceptance_verifier import (
        print_public_trust_center_distribution_kit_accepted_evidence_verification_report,
        public_trust_center_distribution_kit_accepted_evidence_verification_exit_code,
        verify_public_trust_center_distribution_kit_accepted_evidence_package,
        write_public_trust_center_distribution_kit_accepted_evidence_verification_report,
    )
    parser = build_verify_public_trust_center_distribution_kit_accepted_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_distribution_kit_accepted_evidence_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        distribution_kit_path=args.distribution_kit,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_distribution_kit_accepted_evidence_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_distribution_kit_accepted_evidence_verification_report(report)
    raise SystemExit(public_trust_center_distribution_kit_accepted_evidence_verification_exit_code(report))


def handle_verify_public_trust_center_distribution_kit_accepted_evidence_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_distribution_kit_accepted_evidence_package(argv)

def _execute_verify_public_trust_center_acceptance_board_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-acceptance-board-package', *argv]
    from song_agent.public_trust_center_acceptance_board_verifier import (
        print_public_trust_center_acceptance_board_verification_report,
        public_trust_center_acceptance_board_verification_exit_code,
        verify_public_trust_center_acceptance_board_package,
        write_public_trust_center_acceptance_board_verification_report,
    )
    parser = build_verify_public_trust_center_acceptance_board_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_acceptance_board_package(
        args.zip_path,
        strict=args.strict,
        require_ready=args.require_ready,
        require_quorum=args.require_quorum,
        require_no_conflicts=args.require_no_conflicts,
        min_accepted_count=args.min_accepted_count,
        min_accepted_organizations=args.min_accepted_organizations,
        required_roles=args.required_roles,
        distribution_kit_path=args.distribution_kit,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_acceptance_board_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_acceptance_board_verification_report(report)
    raise SystemExit(public_trust_center_acceptance_board_verification_exit_code(report))


def handle_verify_public_trust_center_acceptance_board_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_acceptance_board_package(argv)

def _execute_verify_public_trust_center_acceptance_board_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-acceptance-board-signoff-archive-package', *argv]
    from song_agent.public_trust_center_acceptance_board_signoff_verifier import (
        print_public_trust_center_acceptance_board_signoff_archive_verification_report,
        public_trust_center_acceptance_board_signoff_archive_verification_exit_code,
        verify_public_trust_center_acceptance_board_signoff_archive_package,
        write_public_trust_center_acceptance_board_signoff_archive_verification_report,
    )
    parser = build_verify_public_trust_center_acceptance_board_signoff_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_acceptance_board_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        require_ready=args.require_ready,
        board_zip_path=args.board_zip,
        board_verification_report_path=args.board_verification_report,
        distribution_kit_path=args.distribution_kit,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_acceptance_board_signoff_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_acceptance_board_signoff_archive_verification_report(report)
    raise SystemExit(public_trust_center_acceptance_board_signoff_archive_verification_exit_code(report))


def handle_verify_public_trust_center_acceptance_board_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_acceptance_board_signoff_archive_package(argv)

def _execute_verify_public_trust_center_publication_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-publication-package', *argv]
    from song_agent.public_trust_center_publication_verifier import (
        print_public_trust_center_publication_verification_report,
        public_trust_center_publication_verification_exit_code,
        verify_public_trust_center_publication_package,
        write_public_trust_center_publication_verification_report,
    )
    parser = build_verify_public_trust_center_publication_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_publication_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_ready=args.require_ready,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        require_anchor_current=args.require_anchor_current,
        require_no_revoked=args.require_no_revoked,
        publication_channel_state_path=args.publication_channel_state,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_publication_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_publication_verification_report(report)
    raise SystemExit(public_trust_center_publication_verification_exit_code(report))


def handle_verify_public_trust_center_publication_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_publication_package(argv)

def _execute_verify_public_trust_center_publication_mirror(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-publication-mirror', *argv]
    from song_agent.public_trust_center_publication_verifier import (
        print_public_trust_center_publication_verification_report,
        public_trust_center_publication_verification_exit_code,
        verify_public_trust_center_publication_mirror,
        write_public_trust_center_publication_verification_report,
    )
    parser = build_verify_public_trust_center_publication_mirror_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_publication_mirror(
        args.mirror_dir,
        strict=args.strict,
        require_ready=args.require_ready,
        require_acceptance_board_signoff=args.require_acceptance_board_signoff,
        require_anchor_current=args.require_anchor_current,
        require_no_revoked=args.require_no_revoked,
        publication_channel_state_path=args.publication_channel_state,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_publication_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_publication_verification_report(report)
    raise SystemExit(public_trust_center_publication_verification_exit_code(report))


def handle_verify_public_trust_center_publication_mirror(argv: list[str]) -> None:
    _execute_verify_public_trust_center_publication_mirror(argv)

def _execute_verify_public_trust_center_publication_monitoring_package(argv: list[str]) -> None:
    raw_args = ['verify-public-trust-center-publication-monitoring-package', *argv]
    from song_agent.public_trust_center_publication_monitoring_verifier import (
        print_public_trust_center_publication_monitoring_verification_report,
        public_trust_center_publication_monitoring_verification_exit_code,
        verify_public_trust_center_publication_monitoring_package,
        write_public_trust_center_publication_monitoring_verification_report,
    )
    parser = build_verify_public_trust_center_publication_monitoring_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_public_trust_center_publication_monitoring_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_no_revoked=args.require_no_revoked,
        require_ready=args.require_ready,
        require_no_drift=args.require_no_drift,
        require_no_open_critical_incidents=args.require_no_open_critical_incidents,
        allow_waived_incidents=args.allow_waived_incidents,
        publication_channel_state_path=args.publication_channel_state,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_public_trust_center_publication_monitoring_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_publication_monitoring_verification_report(report)
    raise SystemExit(public_trust_center_publication_monitoring_verification_exit_code(report))


def handle_verify_public_trust_center_publication_monitoring_package(argv: list[str]) -> None:
    _execute_verify_public_trust_center_publication_monitoring_package(argv)

def _execute_verify_trust_operations_hub_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-hub-package', *argv]
    from song_agent.trust_operations_hub_verifier import (
        print_trust_operations_hub_verification_report,
        trust_operations_hub_verification_exit_code,
        verify_trust_operations_hub_package,
        write_trust_operations_hub_verification_report,
    )
    parser = build_verify_trust_operations_hub_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_hub_package(
        args.zip_path,
        strict=args.strict,
        require_ready=args.require_ready,
        require_signed=args.require_signed,
        require_current=args.require_current,
        require_no_critical_blockers=args.require_no_critical_blockers,
        require_publication_monitoring_clean=args.require_publication_monitoring_clean,
        require_delivery_ready=args.require_delivery_ready,
        require_incident_closeout=args.require_incident_closeout,
        require_incident_regression_guards=args.require_incident_regression_guards,
        require_trust_controls=args.require_trust_controls,
        require_trust_control_signoff=args.require_trust_control_signoff,
        require_continuous_assurance=args.require_continuous_assurance,
        publication_channel_state_path=args.publication_channel_state,
        public_trust_center_verification_path=args.public_trust_center_verification,
        publication_monitoring_verification_path=args.publication_monitoring_verification,
        release_verification_paths=args.release_verification,
        distribution_verification_paths=args.distribution_verification,
        submission_verification_paths=args.submission_verification,
        submission_evidence_verification_paths=args.submission_evidence_verification,
        release_operations_verification_paths=args.release_operations_verification,
        hub_signoff_path=args.hub_signoff,
        hub_verification_report_path=args.hub_verification_report,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        incident_knowledge_package_path=args.incident_knowledge_package,
        incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
        trust_control_package_path=args.trust_control_package,
        trust_control_verification_report_path=args.trust_control_verification_report,
        trust_control_signoff_archive_path=args.trust_control_signoff_archive,
        trust_control_signoff_verification_report_path=args.trust_control_signoff_verification_report,
        continuous_assurance_archive_path=args.continuous_assurance_archive,
        continuous_assurance_verification_report_path=args.continuous_assurance_verification_report,
        require_assurance_watch_clear=args.require_assurance_watch_clear,
        assurance_watch_package_path=args.assurance_watch_package,
        assurance_watch_verification_report_path=args.assurance_watch_verification_report,
        require_assurance_watch_signoff=args.require_assurance_watch_signoff,
        assurance_watch_signoff_archive_path=args.assurance_watch_signoff_archive,
        assurance_watch_signoff_verification_report_path=args.assurance_watch_signoff_verification_report,
        require_final_readiness=args.require_final_readiness,
        final_handoff_package_path=args.final_handoff_package,
        final_handoff_verification_report_path=args.final_handoff_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_hub_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_hub_verification_report(report)
    raise SystemExit(trust_operations_hub_verification_exit_code(report))


def handle_verify_trust_operations_hub_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_hub_package(argv)

def _execute_verify_trust_operations_assurance_watch_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-assurance-watch-package', *argv]
    from song_agent.trust_operations_assurance_watch_verifier import (
        print_trust_operations_assurance_watch_verification_report,
        trust_operations_assurance_watch_verification_exit_code,
        verify_trust_operations_assurance_watch_package,
        write_trust_operations_assurance_watch_verification_report,
    )
    parser = build_verify_trust_operations_assurance_watch_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_assurance_watch_package(
        args.zip_path,
        strict=args.strict,
        require_clear=args.require_clear,
        require_current=args.require_current,
        **_trust_operations_assurance_watch_source_payload(args),
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_assurance_watch_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_assurance_watch_verification_report(report)
    raise SystemExit(trust_operations_assurance_watch_verification_exit_code(report))


def handle_verify_trust_operations_assurance_watch_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_assurance_watch_package(argv)

def _execute_verify_trust_operations_assurance_watch_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-assurance-watch-signoff-archive-package', *argv]
    from song_agent.trust_operations_assurance_watch_signoff_verifier import (
        print_trust_operations_assurance_watch_signoff_verification_report,
        trust_operations_assurance_watch_signoff_verification_exit_code,
        verify_trust_operations_assurance_watch_signoff_archive_package,
        write_trust_operations_assurance_watch_signoff_verification_report,
    )
    parser = build_verify_trust_operations_assurance_watch_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_assurance_watch_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        watch_package_path=args.watch_package,
        watch_verification_report_path=args.watch_verification_report,
        hub_package_path=args.hub_package,
        hub_verification_report_path=args.hub_verification_report,
        continuous_assurance_report_path=args.continuous_assurance_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_assurance_watch_signoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_assurance_watch_signoff_verification_report(report)
    raise SystemExit(trust_operations_assurance_watch_signoff_verification_exit_code(report))


def handle_verify_trust_operations_assurance_watch_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_assurance_watch_signoff_archive_package(argv)

def _execute_verify_trust_operations_final_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-final-handoff-package', *argv]
    from song_agent.trust_operations_final_readiness_verifier import (
        print_trust_operations_final_handoff_verification_report,
        trust_operations_final_handoff_verification_exit_code,
        verify_trust_operations_final_handoff_package,
        write_trust_operations_final_handoff_verification_report,
    )
    parser = build_verify_trust_operations_final_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_final_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        **_trust_operations_final_readiness_source_payload(args),
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_final_handoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_final_handoff_verification_report(report)
    raise SystemExit(trust_operations_final_handoff_verification_exit_code(report))


def handle_verify_trust_operations_final_handoff_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_final_handoff_package(argv)

def _execute_verify_trust_operations_assurance_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-assurance-package', *argv]
    from song_agent.trust_operations_continuous_assurance_verifier import (
        print_trust_operations_assurance_verification_report,
        trust_operations_assurance_verification_exit_code,
        verify_trust_operations_assurance_package,
        write_trust_operations_assurance_verification_report,
    )
    parser = build_verify_trust_operations_assurance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_assurance_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_current=args.require_current,
        **_trust_operations_assurance_source_payload(args),
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_assurance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_assurance_verification_report(report)
    raise SystemExit(trust_operations_assurance_verification_exit_code(report))


def handle_verify_trust_operations_assurance_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_assurance_package(argv)

def _execute_verify_trust_operations_control_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-control-package', *argv]
    from song_agent.trust_operations_controls_verifier import (
        print_trust_operations_control_verification_report,
        trust_operations_control_verification_exit_code,
        verify_trust_operations_control_package,
        write_trust_operations_control_verification_report,
    )
    parser = build_verify_trust_operations_control_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_control_package(
        args.zip_path,
        strict=args.strict,
        require_policy_passed=args.require_policy_passed,
        hub_package_path=args.hub_package,
        hub_verification_report_path=args.hub_verification_report,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        incident_knowledge_package_path=args.incident_knowledge_package,
        incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_control_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_control_verification_report(report)
    raise SystemExit(trust_operations_control_verification_exit_code(report))


def handle_verify_trust_operations_control_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_control_package(argv)

def _execute_verify_trust_operations_control_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-control-signoff-archive-package', *argv]
    from song_agent.trust_operations_control_signoff_verifier import (
        print_trust_operations_control_signoff_verification_report,
        trust_operations_control_signoff_verification_exit_code,
        verify_trust_operations_control_signoff_archive_package,
        write_trust_operations_control_signoff_verification_report,
    )
    parser = build_verify_trust_operations_control_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_control_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_current=args.require_current,
        control_package_path=args.control_package,
        control_verification_report_path=args.control_verification_report,
        hub_package_path=args.hub_package,
        hub_verification_report_path=args.hub_verification_report,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        incident_knowledge_package_path=args.incident_knowledge_package,
        incident_knowledge_verification_report_path=args.incident_knowledge_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_control_signoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_control_signoff_verification_report(report)
    raise SystemExit(trust_operations_control_signoff_verification_exit_code(report))


def handle_verify_trust_operations_control_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_control_signoff_archive_package(argv)

def _execute_verify_trust_operations_incident_knowledge_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-incident-knowledge-package', *argv]
    from song_agent.trust_operations_incident_knowledge_verifier import (
        print_trust_operations_incident_knowledge_verification_report,
        trust_operations_incident_knowledge_verification_exit_code,
        verify_trust_operations_incident_knowledge_package,
        write_trust_operations_incident_knowledge_verification_report,
    )
    parser = build_verify_trust_operations_incident_knowledge_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_incident_knowledge_package(
        args.zip_path,
        strict=args.strict,
        require_guards_passed=args.require_guards_passed,
        require_no_open_recurrence=args.require_no_open_recurrence,
        incident_board_package_path=args.incident_board_package,
        incident_board_verification_report_path=args.incident_board_verification_report,
        hub_verification_report_path=args.hub_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_incident_knowledge_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_incident_knowledge_verification_report(report)
    raise SystemExit(trust_operations_incident_knowledge_verification_exit_code(report))


def handle_verify_trust_operations_incident_knowledge_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_incident_knowledge_package(argv)

def _execute_verify_trust_operations_hub_incident_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-hub-incident-package', *argv]
    from song_agent.trust_operations_hub_incident_verifier import (
        print_trust_operations_hub_incident_verification_report,
        trust_operations_hub_incident_verification_exit_code,
        verify_trust_operations_hub_incident_package,
        write_trust_operations_hub_incident_verification_report,
    )
    parser = build_verify_trust_operations_hub_incident_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_hub_incident_package(
        args.zip_path,
        strict=args.strict,
        require_no_open_critical=args.require_no_open_critical,
        require_no_open_blocking=args.require_no_open_blocking,
        require_current_hub=args.require_current_hub,
        hub_verification_report_path=args.hub_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_hub_incident_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_hub_incident_verification_report(report)
    raise SystemExit(trust_operations_hub_incident_verification_exit_code(report))


def handle_verify_trust_operations_hub_incident_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_hub_incident_package(argv)

def _execute_verify_trust_operations_hub_runbook_package(argv: list[str]) -> None:
    raw_args = ['verify-trust-operations-hub-runbook-package', *argv]
    from song_agent.trust_operations_hub_runbook_verifier import (
        print_trust_operations_hub_runbook_verification_report,
        trust_operations_hub_runbook_verification_exit_code,
        verify_trust_operations_hub_runbook_package,
        write_trust_operations_hub_runbook_verification_report,
    )
    parser = build_verify_trust_operations_hub_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_trust_operations_hub_runbook_package(
        args.zip_path,
        strict=args.strict,
        require_completed=args.require_completed,
        require_no_blocked=args.require_no_blocked,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_trust_operations_hub_runbook_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_trust_operations_hub_runbook_verification_report(report)
    raise SystemExit(trust_operations_hub_runbook_verification_exit_code(report))


def handle_verify_trust_operations_hub_runbook_package(argv: list[str]) -> None:
    _execute_verify_trust_operations_hub_runbook_package(argv)

def _execute_release_portfolio_audit(argv: list[str]) -> None:
    raw_args = ['release-portfolio-audit', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore, portfolio_audit_summary
    from song_agent.release_portfolio_audit_verifier import release_portfolio_audit_verification_summary, verify_release_portfolio_audit_package, write_release_portfolio_audit_verification_report
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_audit_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
    store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    result: dict[str, Any] = {"ok": True}
    release_ids = [item.strip() for item in str(args.release_ids or "").split(",") if item.strip()]
    payload = {
        "name": args.name,
        "release_ids": release_ids,
        "include_hidden": args.include_hidden,
        "include_archived": not args.exclude_archived,
        "max_releases": args.max_releases,
        "require_reviewer_packs": args.require_reviewer_packs,
        "require_audit": args.require_audit,
        "require_archive": args.require_archive,
    }
    if args.list:
        portfolios = store.list_portfolios(include_archived=True)
        result.update({"portfolios": portfolios, "summary": {"count": len(portfolios)}})
    else:
        if args.create:
            portfolio = store.create(payload)
            result.update({"portfolio": portfolio, "portfolio_id": portfolio.get("portfolio_id")})
        else:
            if not args.portfolio_id:
                raise ValueError("--portfolio-id is required unless --create or --list is used.")
            portfolio = store.get_portfolio(args.portfolio_id)
            result.update({"portfolio": portfolio, "portfolio_id": args.portfolio_id})
        portfolio_id = str(result.get("portfolio_id") or args.portfolio_id)
        if args.refresh:
            report = store.refresh(portfolio_id, payload)
            summary = portfolio_audit_summary(report)
            summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary["stale"], "trend_report": store.read_trend_report(portfolio_id, default={}), "risk_register": store.read_risk_register(portfolio_id, default={})})
        elif not args.create:
            report = store.read_report(portfolio_id, default={})
            summary = portfolio_audit_summary(report) if report else {"status": "missing"}
            if report:
                summary["stale"] = store.report_is_stale(portfolio_id, report)
            result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
        if args.export:
            manifest = store.export_portfolio(portfolio_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(portfolio_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_audit_package(store.zip_path(portfolio_id), strict=args.strict, require_reviewer_packs=args.require_reviewer_packs, require_audit=args.require_audit, require_archive=args.require_archive)
            write_release_portfolio_audit_verification_report(verification, store.verification_report_path(portfolio_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_audit_verification_summary(verification)})
        if args.archive:
            portfolio = store.archive(portfolio_id)
            result.update({"portfolio": portfolio})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_audit_result(result)
    raise SystemExit(0)


def handle_release_portfolio_audit(argv: list[str]) -> None:
    _execute_release_portfolio_audit(argv)

def _execute_release_portfolio_governance_queue(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-queue', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore, queue_summary
    from song_agent.release_portfolio_governance_verifier import release_portfolio_governance_verification_summary, verify_release_portfolio_governance_package, write_release_portfolio_governance_verification_report
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_queue_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=audit_store, signoff_store=signoff_store)
    result: dict[str, Any] = {"ok": True}
    if args.list:
        queues = store.list_queues(portfolio_id=args.portfolio_id or None, include_archived=True)
        result.update({"queues": queues, "summary": {"count": len(queues)}})
    else:
        if args.create:
            if not args.portfolio_id:
                raise ValueError("--portfolio-id is required with --create.")
            queue = store.create_from_portfolio(args.portfolio_id, {"name": args.name, "force_new": args.force_new})
            result.update({"queue": queue, "queue_id": queue.get("queue_id"), "summary": queue_summary(queue)})
        else:
            if not args.queue_id:
                raise ValueError("--queue-id is required unless --create or --list is used.")
            queue = store.get_queue(args.queue_id)
            execution = store.read_execution_report(args.queue_id, default={})
            result.update({"queue": queue, "queue_id": args.queue_id, "summary": queue_summary(queue, execution), "execution_report": execution})
        queue_id = str(result.get("queue_id") or args.queue_id)
        if args.run_safe:
            queue = store.run_safe_actions(queue_id, {"refresh_portfolio_after_safe_actions": args.refresh_portfolio_after_safe_actions})
            execution = store.read_execution_report(queue_id, default={})
            result.update({"queue": queue, "execution_report": execution, "summary": queue_summary(queue, execution)})
        if args.export:
            manifest = store.export_queue(queue_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(queue_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_portfolio_governance_package(store.zip_path(queue_id), strict=args.strict, require_manual_actions=args.require_manual_actions, require_no_blocked=args.require_no_blocked)
            write_release_portfolio_governance_verification_report(verification, store.verification_report_path(queue_id))
            result.update({"verification": verification, "verification_summary": release_portfolio_governance_verification_summary(verification)})
        if args.archive:
            queue = store.archive(queue_id)
            result.update({"queue": queue, "summary": queue_summary(queue)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_queue(argv: list[str]) -> None:
    _execute_release_portfolio_governance_queue(argv)

def _execute_release_portfolio_governance_signoff(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-signoff', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_archive_verifier import release_portfolio_governance_archive_verification_summary, verify_release_portfolio_governance_archive_package, write_release_portfolio_governance_archive_verification_report
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=audit_store, reviewer_pack_store=reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=audit_store, signoff_store=operations_signoff_store)
    store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    queue_id = args.queue_id
    result: dict[str, Any] = {"ok": True, "queue_id": queue_id}
    if args.create_change_request:
        change = store.create_change_request(queue_id, {"reason": args.reason, "requested_by": args.signed_by})
        result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
    if args.approve_change_request:
        change = store.update_change_request_status(queue_id, args.approve_change_request, "approve", {"approved_by": args.approved_by})
        result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
    if args.reject_change_request:
        change = store.update_change_request_status(queue_id, args.reject_change_request, "reject", {"reason": args.reason or "Rejected by local reviewer"})
        result.update({"change_request": change, "change_request_summary": store.change_request_summary(queue_id)})
    if args.reset:
        signoff = store.reset_signoff(queue_id, {"reason": args.reason, "change_request_id": args.change_request_id, "reset_by": args.signed_by})
        result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff)})
    if args.sign:
        manual = governance_store.read_manual_action_list(queue_id, default={})
        acknowledgements = [
            {"item_id": item.get("item_id"), "action_type": item.get("action_type"), "resolution": "accepted_for_followup", "owner": args.signed_by, "due_note": "tracked outside CLI signoff"}
            for item in manual.get("items", [])
            if isinstance(item, dict)
        ]
        signoff = store.signoff(queue_id, {"signed_by": args.signed_by, "force": args.force, "override_reason": args.override_reason, "manual_acknowledgements": acknowledgements})
        result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff)})
    if args.export_archive:
        manifest = store.export_archive(queue_id)
        result.update({"manifest": manifest, "archive_summary": store.archive_summary(queue_id)})
    if args.zip:
        zip_info = store.build_archive_zip(queue_id)
        result.update({"zip": zip_info, "archive_summary": store.archive_summary(queue_id)})
    if args.verify:
        verification = verify_release_portfolio_governance_archive_package(store.archive_zip_path(queue_id), strict=args.strict, require_signed=args.require_signed, require_no_force=args.require_no_force)
        write_release_portfolio_governance_archive_verification_report(verification, store.archive_verification_report_path(queue_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_archive_verification_summary(verification)})
    if "summary" not in result:
        signoff = store.read_signoff(queue_id, default={})
        result.update({"signoff": signoff, "summary": store.signoff_summary(queue_id, signoff=signoff), "archive_summary": store.archive_summary(queue_id), "change_request_summary": store.change_request_summary(queue_id)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_signoff_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_signoff(argv: list[str]) -> None:
    _execute_release_portfolio_governance_signoff(argv)

def _execute_release_portfolio_governance_audit(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-audit', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore, audit_summary as portfolio_governance_audit_summary
    from song_agent.release_portfolio_governance_audit_verifier import release_portfolio_governance_audit_verification_summary, verify_release_portfolio_governance_audit_package, write_release_portfolio_governance_audit_verification_report
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_audit_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=signoff_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    if args.refresh:
        report = store.refresh(portfolio_id)
        result.update({"report": report, "summary": portfolio_governance_audit_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_audit_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.ledger:
        entries = store.read_ledger(portfolio_id)
        if args.ledger_limit and args.ledger_limit > 0:
            entries = entries[-args.ledger_limit :]
        result.update({"ledger": entries, "ledger_summary": {"entry_count": len(entries)}})
    if args.export:
        manifest = store.export_audit(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_audit_package(
            store.zip_path(portfolio_id),
            strict=args.strict,
            require_signed=args.require_signed,
            require_archives=args.require_archives,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
        )
        write_release_portfolio_governance_audit_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_audit_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_audit_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_audit(argv: list[str]) -> None:
    _execute_release_portfolio_governance_audit(argv)

def _execute_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-reviewer-pack', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore, reviewer_pack_summary as portfolio_governance_reviewer_pack_summary
    from song_agent.release_portfolio_governance_reviewer_pack_verifier import release_portfolio_governance_reviewer_pack_verification_summary, verify_release_portfolio_governance_reviewer_pack, write_release_portfolio_governance_reviewer_pack_verification_report
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=signoff_store)
    store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=audit_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    if args.refresh:
        report = store.refresh(portfolio_id)
        result.update({"report": report, "summary": portfolio_governance_reviewer_pack_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_reviewer_pack_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    result.update({"retrospective": store.read_retrospective(portfolio_id, default={}), "evidence_index": store.read_evidence_index(portfolio_id, default={}), "timeline": store.read_timeline(portfolio_id, default={})})
    if args.export:
        manifest = store.export_pack(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_reviewer_pack(
            store.zip_path(portfolio_id),
            strict=args.strict,
            require_audit=args.require_audit,
            require_signed=args.require_signed,
            require_archives=args.require_archives,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
        )
        write_release_portfolio_governance_reviewer_pack_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_reviewer_pack_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_reviewer_pack_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_reviewer_pack(argv: list[str]) -> None:
    _execute_release_portfolio_governance_reviewer_pack(argv)

def _execute_release_portfolio_governance_final_board(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-final-board', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore, final_board_summary as portfolio_governance_final_board_summary
    from song_agent.release_portfolio_governance_final_board_verifier import release_portfolio_governance_final_board_verification_summary, verify_release_portfolio_governance_final_board_package, write_release_portfolio_governance_final_board_verification_report
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_final_board_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    if args.import_reviewer_response is not None:
        response_payload = read_json(args.import_reviewer_response)
        response = store.import_reviewer_response(portfolio_id, response_payload)
        result.update({"reviewer_response": response})
    refresh_payload = {"require_reviewer_response": args.require_reviewer_response, "require_no_force": args.require_no_force}
    if args.refresh or args.import_reviewer_response is not None:
        report = store.refresh_report(portfolio_id, refresh_payload)
        result.update({"report": report, "summary": portfolio_governance_final_board_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_final_board_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.create_change_request:
        change = store.create_change_request(portfolio_id, {"reason": args.reason or "Final Board archive change requested."})
        result.update({"change_request": change})
    if args.approve_change_request:
        change = store.update_change_request_status(portfolio_id, args.approve_change_request, "approve", {"approved_by": args.approved_by or args.signed_by or "local-user"})
        result.update({"change_request": change})
    if args.reject_change_request:
        change = store.update_change_request_status(portfolio_id, args.reject_change_request, "reject", {"reason": args.reason or "Final Board change rejected."})
        result.update({"change_request": change})
    if args.reset_signoff:
        reset = store.reset_signoff(portfolio_id, {"reason": args.reason or "Final Board signoff reset requested.", "change_request_id": args.change_request_id, "reset_by": args.signed_by or "local-user"})
        result.update({"signoff": reset, "signoff_summary": store.signoff_summary(portfolio_id, signoff=reset)})
    if args.sign or args.force_sign:
        signoff = store.signoff(
            portfolio_id,
            {
                "signed_by": args.signed_by or "local-user",
                "role": args.role,
                "reason": args.reason,
                "force": bool(args.force_sign),
                "allow_warning_signoff": bool(args.allow_warning_signoff),
                "override_reason": args.override_reason,
            },
        )
        result.update({"signoff": signoff, "signoff_summary": store.signoff_summary(portfolio_id, signoff=signoff)})
    if args.export:
        manifest = store.export_archive(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_archive_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_final_board_package(
            store.archive_zip_path(portfolio_id),
            strict=args.strict,
            require_signed=args.require_signed,
            require_reviewer_pack=args.require_reviewer_pack,
            require_audit=args.require_audit,
            require_archives=args.require_archives,
            require_reviewer_response=args.require_reviewer_response,
            require_no_force=args.require_no_force,
            require_reset_cr_causality=args.require_reset_cr_causality,
        )
        write_release_portfolio_governance_final_board_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_final_board_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_final_board_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_final_board(argv: list[str]) -> None:
    _execute_release_portfolio_governance_final_board(argv)

def _execute_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-evidence-vault', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore, evidence_vault_summary as portfolio_governance_evidence_vault_summary, evidence_vault_verification_summary as release_portfolio_governance_evidence_vault_verification_summary
    from song_agent.release_portfolio_governance_evidence_vault_verifier import verify_release_portfolio_governance_evidence_vault_package, write_release_portfolio_governance_evidence_vault_verification_report
    from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_evidence_vault_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id}
    refresh_payload = {
        "require_final_board": True,
        "require_reviewer_pack": True,
        "require_audit": True,
        "require_archives": True,
        "require_queue_packages": args.require_queue_packages,
    }
    if args.refresh:
        report = store.refresh_report(portfolio_id, refresh_payload)
        result.update({"report": report, "summary": portfolio_governance_evidence_vault_summary(report), "stale": store.report_is_stale(portfolio_id, report)})
    else:
        report = store.read_report(portfolio_id, default={})
        summary = portfolio_governance_evidence_vault_summary(report) if report else {"status": "missing"}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    result.update({"package_index": store.read_package_index(portfolio_id, default={}), "verification_index": store.read_verification_index(portfolio_id, default={}), "chain_of_custody": store.read_chain_of_custody(portfolio_id, default={})})
    if args.export:
        manifest = store.export_vault(portfolio_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_evidence_vault_package(
            store.zip_path(portfolio_id),
            strict=args.strict,
            deep=args.deep,
            require_final_board=args.require_final_board,
            require_reviewer_pack=args.require_reviewer_pack,
            require_audit=args.require_audit,
            require_archives=args.require_archives,
            require_queue_packages=args.require_queue_packages,
        )
        write_release_portfolio_governance_evidence_vault_verification_report(verification, store.verification_report_path(portfolio_id))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_evidence_vault_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_evidence_vault_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_evidence_vault(argv: list[str]) -> None:
    _execute_release_portfolio_governance_evidence_vault(argv)

def _execute_release_portfolio_governance_attestation(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore, attestation_summary as portfolio_governance_attestation_summary, attestation_verification_summary as release_portfolio_governance_attestation_verification_summary
    from song_agent.release_portfolio_governance_attestation_verifier import verify_release_portfolio_governance_attestation, write_release_portfolio_governance_attestation_verification_report
    from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
    from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_attestation_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    portfolio_id = args.portfolio_id
    payload = {"profile": args.profile, "require_no_force": args.require_no_force}
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        report = store.refresh_report(portfolio_id, payload)
        result.update({"report": report, "summary": portfolio_governance_attestation_summary(report), "stale": store.report_is_stale(portfolio_id, report, profile=args.profile)})
    else:
        report = store.read_report(portfolio_id, profile=args.profile, default={})
        summary = portfolio_governance_attestation_summary(report) if report else {"status": "missing", "profile": args.profile}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report, profile=args.profile)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    certificate = store.read_certificate(portfolio_id, profile=args.profile, default={})
    if certificate:
        result["certificate"] = certificate
    if args.export:
        manifest = store.export_attestation(portfolio_id, payload)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id, payload)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_attestation(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_vault=args.require_vault, require_final_board=args.require_final_board)
        write_release_portfolio_governance_attestation_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_attestation(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation(argv)

def _execute_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-registry', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
    from song_agent.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore, registry_summary as portfolio_governance_attestation_registry_summary, registry_verification_summary as release_portfolio_governance_attestation_registry_verification_summary
    from song_agent.release_portfolio_governance_attestation_registry_verifier import verify_release_portfolio_governance_attestation_registry, write_release_portfolio_governance_attestation_registry_verification_report
    from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
    from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_attestation_registry_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
    portfolio_id = args.portfolio_id
    payload = {"profile": args.profile}
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.register_current:
        registered = store.register_current_attestation(portfolio_id, {**payload, "public_url": args.public_url, "distribution_note": args.distribution_note})
        result.update({"entry": registered.get("entry"), "registry": registered.get("registry"), "existing": bool(registered.get("existing"))})
    if args.publish:
        published = store.publish_entry(portfolio_id, args.publish, {**payload, "supersede_current": args.supersede_current, "public_url": args.public_url, "distribution_note": args.distribution_note, "published_by": "cli"})
        result.update({"entry": published.get("entry"), "registry": published.get("registry")})
    if args.revoke:
        revoked = store.revoke_entry(portfolio_id, args.revoke, {**payload, "reason": args.reason, "revoked_by": "cli"})
        result.update({"entry": revoked.get("entry"), "registry": revoked.get("registry")})
    if args.refresh:
        report = store.refresh_report(portfolio_id, payload)
        result.update({"report": report})
    else:
        report = store.read_report(portfolio_id, profile=args.profile, default={})
        if report:
            result["report"] = report
    registry = result.get("registry") if isinstance(result.get("registry"), dict) else store.read_registry(portfolio_id, profile=args.profile, default={})
    result["registry"] = registry
    result["summary"] = portfolio_governance_attestation_registry_summary(registry) if registry else {"status": "missing", "profile": args.profile}
    if args.export:
        manifest = store.export_registry(portfolio_id, payload)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id, payload)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_attestation_registry(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_current=args.require_current, require_published=args.require_published, require_no_revoked_current=args.require_no_revoked_current, require_accepted_evidence=args.require_accepted_evidence)
        write_release_portfolio_governance_attestation_registry_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_registry_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_registry_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_attestation_registry(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_registry(argv)

def _execute_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-portal', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_portfolio_audit import ReleasePortfolioAuditStore
    from song_agent.release_portfolio_governance import ReleasePortfolioGovernanceStore
    from song_agent.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
    from song_agent.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
    from song_agent.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore, portal_summary as release_portfolio_governance_attestation_portal_summary, portal_verification_summary as release_portfolio_governance_attestation_portal_verification_summary
    from song_agent.release_portfolio_governance_attestation_portal_verifier import verify_release_portfolio_governance_attestation_portal, write_release_portfolio_governance_attestation_portal_verification_report
    from song_agent.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore
    from song_agent.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
    from song_agent.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
    from song_agent.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
    from song_agent.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_portfolio_governance_attestation_portal_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    operations_signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    operations_audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, release_store=release_store)
    operations_reviewer_store = ReleaseOperationsReviewerPackStore(audit_store=operations_audit_store, signoff_store=operations_signoff_store, release_store=release_store)
    portfolio_store = ReleasePortfolioAuditStore(release_store=release_store, operations_store=operations_store, runbook_store=runbook_store, signoff_store=operations_signoff_store, audit_store=operations_audit_store, reviewer_pack_store=operations_reviewer_store)
    governance_store = ReleasePortfolioGovernanceStore(portfolio_store=portfolio_store, reviewer_pack_store=operations_reviewer_store, audit_store=operations_audit_store, signoff_store=operations_signoff_store)
    governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(governance_store=governance_store)
    governance_audit_store = ReleasePortfolioGovernanceAuditStore(portfolio_store=portfolio_store, governance_store=governance_store, signoff_store=governance_signoff_store)
    governance_reviewer_store = ReleasePortfolioGovernanceReviewerPackStore(audit_store=governance_audit_store)
    final_board_store = ReleasePortfolioGovernanceFinalBoardStore(portfolio_store=portfolio_store, audit_store=governance_audit_store, reviewer_pack_store=governance_reviewer_store)
    vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
        portfolio_store=portfolio_store,
        governance_store=governance_store,
        signoff_store=governance_signoff_store,
        audit_store=governance_audit_store,
        reviewer_pack_store=governance_reviewer_store,
        final_board_store=final_board_store,
    )
    attestation_store = ReleasePortfolioGovernanceAttestationStore(portfolio_store=portfolio_store, final_board_store=final_board_store, evidence_vault_store=vault_store)
    registry_store = ReleasePortfolioGovernanceAttestationRegistryStore(attestation_store=attestation_store)
    store = ReleasePortfolioGovernanceAttestationPortalStore(registry_store=registry_store, attestation_store=attestation_store)
    portfolio_id = args.portfolio_id
    payload = {"profile": args.profile}
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        report = store.refresh_report(portfolio_id, payload)
        result.update({"report": report, "summary": release_portfolio_governance_attestation_portal_summary(report), "stale": False})
    else:
        report = store.read_report(portfolio_id, profile=args.profile, default={})
        summary = release_portfolio_governance_attestation_portal_summary(report) if report else {"status": "missing", "profile": args.profile}
        if report:
            summary["stale"] = store.report_is_stale(portfolio_id, report, profile=args.profile)
        result.update({"report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        manifest = store.export_portal(portfolio_id, payload)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(portfolio_id, payload)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_portfolio_governance_attestation_portal(store.zip_path(portfolio_id, args.profile), strict=args.strict, require_current=args.require_current, require_registry=args.require_registry, require_attestation=args.require_attestation, require_accepted_evidence=args.require_accepted_evidence)
        write_release_portfolio_governance_attestation_portal_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification, "verification_summary": release_portfolio_governance_attestation_portal_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_attestation_portal(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_portal(argv)

def _execute_release_portfolio_governance_attestation_portal_review(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-portal-review', *argv]
    from song_agent.release_portfolio_governance_attestation_portal_review import (
        ReleasePortfolioGovernanceAttestationPortalReviewStore,
        response_summary as release_portfolio_governance_attestation_portal_response_summary,
        review_pack_summary as release_portfolio_governance_attestation_portal_review_pack_summary,
    )
    from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
        verify_release_portfolio_governance_attestation_portal_review_pack,
        write_release_portfolio_governance_attestation_portal_review_pack_verification_report,
    )
    parser = build_release_portfolio_governance_attestation_portal_review_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh_pack:
        pack = store.refresh_pack(portfolio_id, {"profile": args.profile})
        result.update({"review_pack": pack, "summary": release_portfolio_governance_attestation_portal_review_pack_summary(pack), "stale": False})
    else:
        pack = store.read_pack(portfolio_id, profile=args.profile, default={})
        summary = release_portfolio_governance_attestation_portal_review_pack_summary(pack) if pack else {"status": "missing", "profile": args.profile}
        if pack:
            summary["stale"] = store.pack_is_stale(portfolio_id, pack, profile=args.profile)
        result.update({"review_pack": pack, "summary": summary, "stale": summary.get("stale", False)})
    if args.export_pack:
        manifest = store.export_pack(portfolio_id, {"profile": args.profile})
        result.update({"manifest": manifest})
    if args.zip_pack:
        zip_info = store.build_pack_zip(portfolio_id, {"profile": args.profile})
        result.update({"zip": zip_info})
    if args.verify_pack:
        verification = verify_release_portfolio_governance_attestation_portal_review_pack(
            store.pack_zip_path(portfolio_id, args.profile),
            strict=args.strict,
            require_current=args.require_current,
        )
        write_release_portfolio_governance_attestation_portal_review_pack_verification_report(verification, store.pack_verification_report_path(portfolio_id, args.profile))
        result.update({"verification": verification})
    if args.import_response:
        imported = store.import_response(portfolio_id, {"profile": args.profile, "content_base64": args.content_base64})
        result.update(imported)
    if args.responses:
        result.update({"responses": store.list_responses(portfolio_id, profile=args.profile)})
    if args.response_id and not args.verify_response and not args.create_change_request:
        response = store.get_response(portfolio_id, args.response_id, profile=args.profile)
        result.update({"response": response, "response_summary": release_portfolio_governance_attestation_portal_response_summary(response)})
    if args.verify_response:
        if not args.response_id:
            parser.error("--verify-response requires --response-id")
        verification = store.verify_response(portfolio_id, args.response_id, profile=args.profile)
        result.update({"response_verification": verification})
    if args.create_change_request:
        if not args.response_id:
            parser.error("--create-change-request requires --response-id")
        change = store.create_change_request(portfolio_id, args.response_id, {"created_by": "cli"}, profile=args.profile)
        result.update(change)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_portal_review_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_attestation_portal_review(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_portal_review(argv)

def _execute_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-accepted-evidence', *argv]
    from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore, accepted_evidence_summary
    from song_agent.release_portfolio_governance_attestation_accepted_evidence_verifier import write_release_portfolio_governance_attestation_accepted_evidence_verification_report
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
    parser = build_release_portfolio_governance_attestation_accepted_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        payload = {"profile": args.profile}
        if args.response_id:
            payload["response_id"] = args.response_id
        evidence = store.refresh_evidence(portfolio_id, payload)
        result.update({"accepted_evidence": evidence, "summary": accepted_evidence_summary(evidence), "stale": False})
    else:
        evidence = store.read_evidence(portfolio_id, profile=args.profile, default={})
        summary = accepted_evidence_summary(evidence) if evidence else {"status": "missing", "external_review_status": "missing", "profile": args.profile}
        if evidence:
            summary["stale"] = store.evidence_is_stale(portfolio_id, evidence, profile=args.profile)
        result.update({"accepted_evidence": evidence, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        result["manifest"] = store.export_evidence(portfolio_id, {"profile": args.profile})
    if args.zip:
        result["zip"] = store.build_zip(portfolio_id, {"profile": args.profile})
    if args.verify:
        verification = store.verify_evidence(portfolio_id, {"profile": args.profile, "strict": args.strict, "require_current": args.require_current})
        write_release_portfolio_governance_attestation_accepted_evidence_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result["verification"] = verification
    if args.archive:
        result["accepted_evidence"] = store.archive_evidence(portfolio_id, {"profile": args.profile, "reason": args.reason})
        result["summary"] = accepted_evidence_summary(result["accepted_evidence"])
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_accepted_evidence_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_attestation_accepted_evidence(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_accepted_evidence(argv)

def _execute_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-transparency', *argv]
    from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
    from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore, transparency_summary
    from song_agent.release_portfolio_governance_attestation_transparency_verifier import write_release_portfolio_governance_attestation_transparency_verification_report
    parser = build_release_portfolio_governance_attestation_transparency_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh:
        feed = store.refresh_feed(portfolio_id, {"profile": args.profile, "require_accepted_evidence": args.require_accepted_evidence})
        result.update({"feed": feed, "summary": transparency_summary(feed), "stale": False})
    else:
        feed = store.read_feed(portfolio_id, profile=args.profile, default={})
        summary = transparency_summary(feed) if feed else {"status": "missing", "profile": args.profile}
        if feed:
            summary["stale"] = store.feed_is_stale(portfolio_id, feed, profile=args.profile)
        result.update({"feed": feed, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        result["manifest"] = store.export_transparency(portfolio_id, {"profile": args.profile})
    if args.zip:
        result["zip"] = store.build_zip(portfolio_id, {"profile": args.profile})
    if args.verify:
        verification = store.verify_transparency(
            portfolio_id,
            {
                "profile": args.profile,
                "strict": args.strict,
                "require_current": args.require_current,
                "require_accepted_evidence": args.require_accepted_evidence,
                "require_no_revoked_current": args.require_no_revoked_current,
                "require_contiguous_chain": args.require_contiguous_chain,
            },
        )
        write_release_portfolio_governance_attestation_transparency_verification_report(verification, store.verification_report_path(portfolio_id, args.profile))
        result["verification"] = verification
    if args.notices:
        result["notices"] = store.list_notices(portfolio_id, profile=args.profile)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_attestation_transparency(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_transparency(argv)

def _execute_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    raw_args = ['release-portfolio-governance-attestation-transparency-acknowledgement', *argv]
    from song_agent.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
    from song_agent.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
    from song_agent.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore
    from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore, acknowledgement_summary
    from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import (
        verify_release_portfolio_governance_attestation_transparency_acknowledgement_package,
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
    )
    parser = build_release_portfolio_governance_attestation_transparency_acknowledgement_parser()
    args = parser.parse_args(raw_args[1:])
    portal_store = _build_release_portfolio_governance_attestation_portal_store()
    review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(portal_store=portal_store)
    accepted_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(review_store=review_store)
    transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
        attestation_store=portal_store.attestation_store,
        registry_store=portal_store.registry_store,
        portal_store=portal_store,
        accepted_evidence_store=accepted_store,
    )
    store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(transparency_store=transparency_store)
    portfolio_id = args.portfolio_id
    result: dict[str, Any] = {"ok": True, "portfolio_id": portfolio_id, "profile": args.profile}
    if args.refresh_pack:
        pack = store.refresh_pack(portfolio_id, {"profile": args.profile})
        result.update({"pack": pack, "summary": {"status": pack.get("status"), "pack_id": pack.get("pack_id"), "source_hash": pack.get("source_hash")}})
    else:
        pack = store.read_pack(portfolio_id, profile=args.profile, default={})
        result.update({"pack": pack, "summary": {"status": pack.get("status", "missing") if pack else "missing", "pack_id": pack.get("pack_id") if pack else None}})
    if args.export_pack:
        result["pack_manifest"] = store.export_pack(portfolio_id, {"profile": args.profile})
    if args.zip_pack:
        result["pack_zip"] = store.build_pack_zip(portfolio_id, {"profile": args.profile})
    if args.verify_pack:
        report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
            store.pack_zip_path(portfolio_id, args.profile),
            strict=args.strict,
            require_pack=True,
            require_transparency=args.require_transparency,
        )
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, store.pack_verification_report_path(portfolio_id, args.profile))
        result["pack_verification"] = report
    if args.import_response:
        payload: dict[str, Any] = {"profile": args.profile}
        if args.content_base64:
            payload["content_base64"] = args.content_base64
        imported = store.import_response(portfolio_id, payload)
        result.update(imported)
    if args.refresh_evidence:
        payload = {"profile": args.profile}
        if args.response_id:
            payload["response_id"] = args.response_id
        evidence = store.refresh_evidence(portfolio_id, payload)
        result.update({"acknowledgement_evidence": evidence, "evidence_summary": acknowledgement_summary(evidence)})
    if args.export_evidence:
        result["evidence_manifest"] = store.export_evidence(portfolio_id, {"profile": args.profile})
    if args.zip_evidence:
        result["evidence_zip"] = store.build_evidence_zip(portfolio_id, {"profile": args.profile})
    if args.verify_evidence:
        report = verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(
            store.evidence_zip_path(portfolio_id, args.profile),
            strict=args.strict,
            require_response=True,
            require_accepted=args.require_accepted,
        )
        write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, store.evidence_verification_report_path(portfolio_id, args.profile))
        result["evidence_verification"] = report
    if args.create_change_request:
        if not args.response_id:
            raise SystemExit("--response-id is required with --create-change-request")
        result["change_request"] = store.create_change_request(portfolio_id, args.response_id, {"profile": args.profile})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_portfolio_governance_attestation_transparency_acknowledgement_result(result)
    raise SystemExit(0)


def handle_release_portfolio_governance_attestation_transparency_acknowledgement(argv: list[str]) -> None:
    _execute_release_portfolio_governance_attestation_transparency_acknowledgement(argv)

def _execute_public_trust_center_publication(argv: list[str]) -> None:
    raw_args = ['public-trust-center-publication', *argv]
    from song_agent.public_trust_center_publication import PublicTrustCenterPublicationStore, publication_summary
    from song_agent.public_trust_center_publication_verifier import (
        print_public_trust_center_publication_verification_report,
    )
    parser = build_public_trust_center_publication_parser()
    args = parser.parse_args(raw_args[1:])
    trust_store = _build_public_trust_center_store()
    from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
    from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore
    from song_agent.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore
    from song_agent.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore
    from song_agent.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=trust_store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    distribution_kit_store = PublicTrustCenterDistributionKitStore(trust_center_store=trust_store, anchor_registry_store=anchor_store, anchor_transparency_store=anchor_transparency_store)
    acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
    board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=acceptance_store)
    store = PublicTrustCenterPublicationStore(
        trust_center_store=trust_store,
        distribution_kit_store=distribution_kit_store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
        acceptance_store=acceptance_store,
        acceptance_board_store=board_store,
    )
    result: dict[str, Any] = {"ok": True, "center_id": args.center_id, "channel_id": args.channel_id}
    if args.create_channel:
        result["channel"] = store.create_channel(args.center_id, {"channel_id": args.channel_id, "name": args.channel_name, "channel_type": args.channel_type})
    else:
        try:
            result["channel"] = store.read_channel(args.center_id, args.channel_id)
        except Exception:
            result["channel"] = store.create_channel(args.center_id, {"channel_id": args.channel_id, "name": args.channel_name, "channel_type": args.channel_type})
    publication_id = args.publication_id
    if args.refresh:
        report = store.refresh_publication(args.center_id, args.channel_id)
        publication_id = str(report.get("publication_id") or publication_id or "")
        result["publication"] = report
        result["summary"] = publication_summary(report)
    if args.supersede:
        report = store.supersede_publication(args.center_id, args.channel_id, publication_id, {"reason": args.reason})
        publication_id = str(report.get("publication_id") or publication_id or "")
        result["publication"] = report
        result["summary"] = publication_summary(report)
    if args.revoke:
        if not publication_id:
            publication_id = store._current_publication_id(args.center_id, args.channel_id)
        report = store.revoke_publication(args.center_id, args.channel_id, publication_id, {"reason": args.reason})
        result["publication"] = report
        result["summary"] = publication_summary(report)
    if args.export:
        result["manifest"] = store.export_publication(args.center_id, args.channel_id, publication_id)
        publication_id = str(result["manifest"].get("publication_id") or publication_id or "")
    if args.zip:
        result["zip"] = store.build_publication_zip(args.center_id, args.channel_id, publication_id)
        publication_id = str(result["zip"].get("publication_id") or publication_id or "")
    if args.verify:
        verification = store.verify_publication_zip(
            args.center_id,
            args.channel_id,
            publication_id,
            {
                "strict": args.strict,
                "deep": args.deep,
                "require_ready": args.require_ready,
                "require_acceptance_board_signoff": args.require_acceptance_board_signoff,
                "require_anchor_current": args.require_anchor_current,
                "require_no_revoked": args.require_no_revoked,
                "publication_channel_state_path": args.publication_channel_state,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.verify_mirror:
        if not publication_id:
            publication_id = store._current_publication_id(args.center_id, args.channel_id)
        mirror_dir = args.mirror_dir or store.export_dir(args.center_id, args.channel_id, publication_id)
        verification = store.verify_mirror_directory(
            args.center_id,
            args.channel_id,
            publication_id,
            mirror_dir,
            {
                "strict": args.strict,
                "require_ready": args.require_ready,
                "require_acceptance_board_signoff": args.require_acceptance_board_signoff,
                "require_anchor_current": args.require_anchor_current,
                "require_no_revoked": args.require_no_revoked,
                "publication_channel_state_path": args.publication_channel_state,
            },
        )
        result["mirror_verification"] = verification
        result["mirror_verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_public_trust_center_publication_verification_report(result["verification"])
        elif "mirror_verification" in result:
            print_public_trust_center_publication_verification_report(result["mirror_verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_public_trust_center_publication(argv: list[str]) -> None:
    _execute_public_trust_center_publication(argv)

def _execute_public_trust_center_publication_monitor(argv: list[str]) -> None:
    raw_args = ['public-trust-center-publication-monitor', *argv]
    from song_agent.public_trust_center_publication_monitoring import PublicTrustCenterPublicationMonitoringStore, monitoring_summary
    from song_agent.public_trust_center_publication_monitoring_verifier import print_public_trust_center_publication_monitoring_verification_report
    parser = build_public_trust_center_publication_monitor_parser()
    args = parser.parse_args(raw_args[1:])
    publication_store = _build_public_trust_center_publication_store()
    store = PublicTrustCenterPublicationMonitoringStore(publication_store=publication_store)
    result: dict[str, Any] = {"ok": True, "center_id": args.center_id, "channel_id": args.channel_id}
    monitor_id = args.monitor_id
    if args.create_monitor:
        monitor = store.create_monitor(args.center_id, args.channel_id, {"monitor_id": monitor_id, "name": args.monitor_name, "publication_id": args.publication_id, "mirror_dir": args.mirror_dir})
        monitor_id = str(monitor.get("monitor_id") or monitor_id or "")
        result["monitor"] = monitor
    elif monitor_id:
        result["monitor"] = store.read_monitor(args.center_id, args.channel_id, monitor_id)
    else:
        monitors = store.list_monitors(args.center_id, args.channel_id)
        if monitors:
            monitor_id = str(monitors[0].get("monitor_id") or "")
            result["monitor"] = monitors[0]
        else:
            monitor = store.create_monitor(args.center_id, args.channel_id, {"name": args.monitor_name, "publication_id": args.publication_id, "mirror_dir": args.mirror_dir})
            monitor_id = str(monitor.get("monitor_id") or "")
            result["monitor"] = monitor
    if not monitor_id:
        raise ValueError("--monitor-id is required.")
    run_id = args.run_id
    if args.run:
        run_result = store.run_monitor(args.center_id, args.channel_id, monitor_id, {"publication_id": args.publication_id, "mirror_dir": args.mirror_dir, "publication_channel_state_path": args.publication_channel_state})
        run_id = str((run_result.get("monitor_run") or {}).get("run_id") or run_id or "")
        result.update(run_result)
        result["summary"] = monitoring_summary(run_result.get("monitor_run") or {})
    if args.ack_incident:
        result["incident"] = store.acknowledge_incident(args.center_id, args.channel_id, monitor_id, args.ack_incident, {"reason": args.reason})
    if args.resolve_incident:
        result["incident"] = store.resolve_incident(args.center_id, args.channel_id, monitor_id, args.resolve_incident, {"resolution_note": args.reason})
    if args.waive_incident:
        result["incident"] = store.waive_incident(args.center_id, args.channel_id, monitor_id, args.waive_incident, {"waiver_reason": args.reason})
    if args.reopen_incident:
        result["incident"] = store.reopen_incident(args.center_id, args.channel_id, monitor_id, args.reopen_incident, {"reason": args.reason})
    if args.export:
        if not run_id:
            raise ValueError("--run-id is required for --export unless --run was used.")
        result["manifest"] = store.export_monitoring_run(args.center_id, args.channel_id, monitor_id, run_id)
    if args.zip:
        if not run_id:
            raise ValueError("--run-id is required for --zip unless --run was used.")
        result["zip"] = store.build_monitoring_zip(args.center_id, args.channel_id, monitor_id, run_id)
    if args.verify:
        if not run_id:
            raise ValueError("--run-id is required for --verify unless --run was used.")
        verification = store.verify_monitoring_zip(
            args.center_id,
            args.channel_id,
            monitor_id,
            run_id,
            {
                "strict": args.strict,
                "require_current": args.require_current,
                "require_no_revoked": args.require_no_revoked,
                "require_ready": args.require_ready,
                "require_no_drift": args.require_no_drift,
                "require_no_open_critical_incidents": args.require_no_open_critical_incidents,
                "allow_waived_incidents": args.allow_waived_incidents,
                "publication_channel_state_path": args.publication_channel_state,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_public_trust_center_publication_monitoring_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_public_trust_center_publication_monitor(argv: list[str]) -> None:
    _execute_public_trust_center_publication_monitor(argv)

def _execute_trust_operations_hub(argv: list[str]) -> None:
    raw_args = ['trust-operations-hub', *argv]
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    from song_agent.trust_operations_hub_verifier import print_trust_operations_hub_verification_report
    parser = build_trust_operations_hub_parser()
    args = parser.parse_args(raw_args[1:])
    store = TrustOperationsHubStore()
    result: dict[str, Any] = {"ok": True}
    hub_id = args.hub_id
    if args.create or not hub_id:
        if hub_id and store.hub_path(hub_id).exists():
            hub = store.read_hub(hub_id)
        else:
            hub = store.create_hub({"hub_id": hub_id, "name": args.name})
        hub_id = str(hub.get("hub_id") or hub_id or "")
        result["hub"] = hub
    if not hub_id:
        hubs = store.list_hubs()
        if not hubs:
            hub = store.create_hub({"name": args.name})
            hubs = [hub]
        hub_id = str(hubs[0].get("hub_id") or "")
        result["hub"] = hubs[0]
    if not hub_id:
        raise ValueError("--hub-id is required.")
    report_id = args.report_id
    source_payload = {
        "publication_channel_state_path": args.publication_channel_state,
        "public_trust_center_verification_path": args.public_trust_center_verification,
        "publication_monitoring_verification_path": args.publication_monitoring_verification,
        "release_verification_paths": args.release_verification,
        "distribution_verification_paths": args.distribution_verification,
        "submission_verification_paths": args.submission_verification,
        "submission_evidence_verification_paths": args.submission_evidence_verification,
        "release_operations_verification_paths": args.release_operations_verification,
    }
    if args.refresh:
        refreshed = store.refresh_report(hub_id, source_payload)
        report_id = str((refreshed.get("hub_report") or {}).get("report_id") or report_id or "")
        result.update(refreshed)
    if not report_id:
        current = read_json(store.current_report_path(hub_id)) if store.current_report_path(hub_id).exists() else {}
        report_id = str(current.get("report_id") or "")
    if args.create_change_request:
        result["change_request"] = store.create_change_request(hub_id, {"reason": args.reason, "change_request_id": args.change_request_id})
    if args.approve_change_request:
        result["change_request"] = store.approve_change_request(hub_id, args.approve_change_request)
    if args.reset_signoff:
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for --reset-signoff.")
        result["reset"] = store.reset_signoff(hub_id, args.change_request_id)
    if args.export:
        if not report_id:
            raise ValueError("--report-id is required for --export unless --refresh was used.")
        result["manifest"] = store.export_report(hub_id, report_id)
    if args.zip:
        if not report_id:
            raise ValueError("--report-id is required for --zip unless --refresh was used.")
        result["zip"] = store.build_zip(hub_id, report_id)
    if args.verify:
        if not report_id:
            raise ValueError("--report-id is required for --verify unless --refresh was used.")
        verification = store.verify_zip(
            hub_id,
            report_id,
            {
                "strict": args.strict,
                "require_ready": args.require_ready,
                "require_signed": args.require_signed,
                "require_current": args.require_current,
                "require_no_critical_blockers": args.require_no_critical_blockers,
                "require_publication_monitoring_clean": args.require_publication_monitoring_clean,
                "require_delivery_ready": args.require_delivery_ready,
                "require_incident_closeout": args.require_incident_closeout,
                "require_incident_regression_guards": args.require_incident_regression_guards,
                "require_trust_controls": args.require_trust_controls,
                "require_trust_control_signoff": args.require_trust_control_signoff,
                "require_continuous_assurance": args.require_continuous_assurance,
                "publication_channel_state_path": args.publication_channel_state,
                "public_trust_center_verification_path": args.public_trust_center_verification,
                "publication_monitoring_verification_path": args.publication_monitoring_verification,
                "release_verification_paths": args.release_verification,
                "distribution_verification_paths": args.distribution_verification,
                "submission_verification_paths": args.submission_verification,
                "submission_evidence_verification_paths": args.submission_evidence_verification,
                "release_operations_verification_paths": args.release_operations_verification,
                "hub_signoff_path": args.hub_signoff,
                "hub_verification_report_path": args.hub_verification_report,
                "incident_board_package_path": args.incident_board_package,
                "incident_board_verification_report_path": args.incident_board_verification_report,
                "incident_knowledge_package_path": args.incident_knowledge_package,
                "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
                "trust_control_package_path": args.trust_control_package,
                "trust_control_verification_report_path": args.trust_control_verification_report,
                "trust_control_signoff_archive_path": args.trust_control_signoff_archive,
                "trust_control_signoff_verification_report_path": args.trust_control_signoff_verification_report,
                "continuous_assurance_archive_path": args.continuous_assurance_archive,
                "continuous_assurance_verification_report_path": args.continuous_assurance_verification_report,
                "require_assurance_watch_clear": args.require_assurance_watch_clear,
                "assurance_watch_package_path": args.assurance_watch_package,
                "assurance_watch_verification_report_path": args.assurance_watch_verification_report,
                "require_assurance_watch_signoff": args.require_assurance_watch_signoff,
                "assurance_watch_signoff_archive_path": args.assurance_watch_signoff_archive,
                "assurance_watch_signoff_verification_report_path": args.assurance_watch_signoff_verification_report,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.signoff:
        if not report_id:
            raise ValueError("--report-id is required for --signoff unless --refresh was used.")
        result["signoff"] = store.signoff(hub_id, report_id, {"signed_by": args.signed_by, "reason": args.reason, "force": args.force, "override_reason": args.override_reason})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_hub_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": hub_id, "report_id": report_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_hub(argv: list[str]) -> None:
    _execute_trust_operations_hub(argv)

def _execute_trust_operations_assurance_watch(argv: list[str]) -> None:
    raw_args = ['trust-operations-assurance-watch', *argv]
    from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
    from song_agent.trust_operations_assurance_watch_verifier import print_trust_operations_assurance_watch_verification_report
    from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    parser = build_trust_operations_assurance_watch_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    assurance_store = TrustOperationsAssuranceStore(hub_store=hub_store)
    store = TrustOperationsAssuranceWatchStore(assurance_store=assurance_store, hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "schedule_id": args.schedule_id}
    source_payload = _trust_operations_assurance_watch_source_payload(args)
    schedule_patch: dict[str, Any] = {}
    if args.hub_id:
        schedule_patch.setdefault("scope", {})["hub_ids"] = [args.hub_id]
    if args.interval_days is not None or args.grace_days is not None:
        schedule_patch.setdefault("cadence", {})
        if args.interval_days is not None:
            schedule_patch["cadence"]["interval_days"] = args.interval_days
        if args.grace_days is not None:
            schedule_patch["cadence"]["grace_days"] = args.grace_days
    if args.write_schedule:
        result["schedule"] = store.write_schedule({"schedule_id": args.schedule_id, **schedule_patch})
    if args.list:
        result["queues"] = store.list_queues(args.schedule_id)
    if args.refresh:
        refresh_payload: dict[str, Any] = {**source_payload}
        if args.queue_id:
            refresh_payload["queue_id"] = args.queue_id
        if args.hub_id:
            refresh_payload["hub_id"] = args.hub_id
        refreshed = store.refresh_queue(refresh_payload, schedule_id=args.schedule_id)
        result.update(refreshed)
        args.queue_id = str((refreshed.get("queue") or {}).get("queue_id") or args.queue_id or "")
    if args.export:
        if not args.queue_id:
            raise ValueError("--queue-id is required for --export unless --refresh was used.")
        result["manifest"] = store.export_watch(args.queue_id, source_payload)
    if args.zip:
        if not args.queue_id:
            raise ValueError("--queue-id is required for --zip unless --refresh was used.")
        result["zip"] = store.build_watch_zip(args.queue_id, source_payload)
    if args.verify:
        if not args.queue_id:
            raise ValueError("--queue-id is required for --verify unless --refresh was used.")
        verification = store.verify_watch_zip(args.queue_id, {**source_payload, "strict": args.strict, "require_clear": args.require_clear, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.write_schedule, args.list, args.refresh, args.export, args.zip, args.verify]):
        result["summary"] = store.summary(args.queue_id) if args.queue_id else {"schedule": store.read_schedule(args.schedule_id), "queues": store.list_queues(args.schedule_id)}
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_assurance_watch_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "queue_id": args.queue_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_assurance_watch(argv: list[str]) -> None:
    _execute_trust_operations_assurance_watch(argv)

def _execute_trust_operations_assurance_watch_signoff(argv: list[str]) -> None:
    raw_args = ['trust-operations-assurance-watch-signoff', *argv]
    from song_agent.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
    from song_agent.trust_operations_assurance_watch_signoff import TrustOperationsAssuranceWatchSignoffStore
    from song_agent.trust_operations_assurance_watch_signoff_verifier import print_trust_operations_assurance_watch_signoff_verification_report
    from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    parser = build_trust_operations_assurance_watch_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    assurance_store = TrustOperationsAssuranceStore(hub_store=hub_store)
    watch_store = TrustOperationsAssuranceWatchStore(assurance_store=assurance_store, hub_store=hub_store)
    store = TrustOperationsAssuranceWatchSignoffStore(watch_store=watch_store, assurance_store=assurance_store, hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "queue_id": args.queue_id}
    source_payload = {
        "watch_package_path": args.watch_package,
        "watch_verification_report_path": args.watch_verification_report,
        "hub_package_path": args.hub_package,
        "hub_verification_report_path": args.hub_verification_report,
        "continuous_assurance_report_path": args.continuous_assurance_report,
    }
    if args.refresh_closeout:
        result["closeout"] = store.refresh_closeout(args.queue_id, source_payload)
    if args.sign:
        result["signoff"] = store.sign(args.queue_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
    if args.create_change_request:
        result["change_request"] = store.create_change_request(args.queue_id, {"reason": args.reason, "requested_by": args.signed_by})
    if args.approve_change_request:
        result["change_request"] = store.approve_change_request(args.queue_id, args.approve_change_request, {"approved_by": args.signed_by})
    if args.reset_signoff:
        result["reset"] = store.reset_signoff(args.queue_id, args.reset_signoff)
    if args.export:
        result["manifest"] = store.export_archive(args.queue_id, source_payload)
    if args.zip:
        result["zip"] = store.build_archive_zip(args.queue_id)
    if args.verify:
        verification = store.verify_archive_zip(args.queue_id, {**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.refresh_closeout, args.sign, args.create_change_request, args.approve_change_request, args.reset_signoff, args.export, args.zip, args.verify]):
        result["summary"] = store.summary(args.queue_id)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_assurance_watch_signoff_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "queue_id": args.queue_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_assurance_watch_signoff(argv: list[str]) -> None:
    _execute_trust_operations_assurance_watch_signoff(argv)

def _execute_trust_operations_final_readiness(argv: list[str]) -> None:
    raw_args = ['trust-operations-final-readiness', *argv]
    from song_agent.trust_operations_final_readiness import TrustOperationsFinalReadinessStore
    from song_agent.trust_operations_final_readiness_verifier import print_trust_operations_final_handoff_verification_report
    parser = build_trust_operations_final_readiness_parser()
    args = parser.parse_args(raw_args[1:])
    store = TrustOperationsFinalReadinessStore()
    result: dict[str, Any] = {"ok": True}
    source_payload = _trust_operations_final_readiness_source_payload(args)
    if args.refresh_report:
        result.update(store.refresh_report(source_payload))
    if args.create_certificate:
        result["certificate"] = store.create_certificate()
    if args.sign:
        result["signoff"] = store.sign({"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
    if args.create_change_request:
        result["change_request"] = store.create_change_request({"reason": args.reason, "requested_by": args.signed_by})
    if args.approve_change_request:
        result["change_request"] = store.approve_change_request(args.approve_change_request, {"approved_by": args.signed_by})
    if args.reset_signoff:
        result["reset"] = store.reset_signoff(args.reset_signoff)
    if args.export:
        result["manifest"] = store.export_handoff(source_payload)
    if args.zip:
        result["zip"] = store.build_handoff_zip()
    if args.verify:
        verification = store.verify_handoff_zip({**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.refresh_report, args.create_certificate, args.sign, args.create_change_request, args.approve_change_request, args.reset_signoff, args.export, args.zip, args.verify]):
        result["summary"] = store.summary()
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_final_handoff_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_final_readiness(argv: list[str]) -> None:
    _execute_trust_operations_final_readiness(argv)

def _execute_trust_operations_controls(argv: list[str]) -> None:
    raw_args = ['trust-operations-controls', *argv]
    from song_agent.trust_operations_controls import TrustOperationsControlStore
    from song_agent.trust_operations_controls_verifier import print_trust_operations_control_verification_report
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
    from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore
    parser = build_trust_operations_controls_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
    knowledge_store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
    store = TrustOperationsControlStore(hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    source_payload = {
        "hub_package_path": args.hub_package,
        "hub_verification_report_path": args.hub_verification_report,
        "incident_board_package_path": args.incident_board_package,
        "incident_board_verification_report_path": args.incident_board_verification_report,
        "incident_knowledge_package_path": args.incident_knowledge_package,
        "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
    }
    if args.refresh_catalog:
        result["catalog"] = store.refresh_catalog(args.hub_id, source_payload)
    if args.create_policy:
        policy = store.create_policy_bundle(args.hub_id, {"policy_id": args.policy_id, "name": args.policy_name})
        args.policy_id = str(policy.get("policy_id") or args.policy_id or "")
        result["policy"] = policy
    if args.assess:
        if not args.policy_id:
            policies = store.list_policies(args.hub_id)
            if not policies:
                raise ValueError("--policy-id is required when no policy exists.")
            args.policy_id = str(policies[0].get("policy_id") or "")
        assessed = store.assess_policy(args.hub_id, str(args.policy_id), {**source_payload, "assessment_id": args.assessment_id})
        args.assessment_id = str((assessed.get("assessment") or {}).get("assessment_id") or args.assessment_id or "")
        result.update(assessed)
    if not args.assessment_id and (args.export or args.zip or args.verify):
        assessments = sorted(store.assessments_dir(args.hub_id).glob("*/control-assessment-report.json")) if store.assessments_dir(args.hub_id).exists() else []
        if assessments:
            args.assessment_id = assessments[-1].parent.name
    if args.export:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --export unless --assess was used.")
        result["manifest"] = store.export_controls(args.hub_id, str(args.assessment_id))
    if args.zip:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --zip unless --assess was used.")
        result["zip"] = store.build_zip(args.hub_id, str(args.assessment_id))
    if args.verify:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --verify unless --assess was used.")
        verification = store.verify_zip(args.hub_id, str(args.assessment_id), {**source_payload, "strict": args.strict, "require_policy_passed": args.require_policy_passed})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_control_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "assessment_id": args.assessment_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_controls(argv: list[str]) -> None:
    _execute_trust_operations_controls(argv)

def _execute_trust_operations_assurance(argv: list[str]) -> None:
    raw_args = ['trust-operations-assurance', *argv]
    from song_agent.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
    from song_agent.trust_operations_continuous_assurance_verifier import print_trust_operations_assurance_verification_report
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    parser = build_trust_operations_assurance_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    store = TrustOperationsAssuranceStore(hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    source_payload = _trust_operations_assurance_source_payload(args)
    if args.list:
        result["runs"] = store.list_runs(args.hub_id)
    if args.refresh:
        refreshed = store.refresh_run(args.hub_id, {**source_payload, "run_id": args.run_id}, policy_id=args.policy_id)
        result.update(refreshed)
        args.run_id = str((refreshed.get("run") or {}).get("run_id") or args.run_id or "")
    if args.export:
        if not args.run_id:
            raise ValueError("--run-id is required for --export unless --refresh was used.")
        result["manifest"] = store.export_archive(args.run_id, source_payload)
    if args.zip:
        if not args.run_id:
            raise ValueError("--run-id is required for --zip unless --refresh was used.")
        result["zip"] = store.build_archive_zip(args.run_id, source_payload)
    if args.verify:
        if not args.run_id:
            raise ValueError("--run-id is required for --verify unless --refresh was used.")
        verification = store.verify_archive_zip(args.run_id, {**source_payload, "strict": args.strict, "require_passed": args.require_passed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.list, args.refresh, args.export, args.zip, args.verify]):
        if not args.run_id:
            result["runs"] = store.list_runs(args.hub_id)
        else:
            result["summary"] = store.summary(args.run_id)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_assurance_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "run_id": args.run_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_assurance(argv: list[str]) -> None:
    _execute_trust_operations_assurance(argv)

def _execute_trust_operations_control_signoff(argv: list[str]) -> None:
    raw_args = ['trust-operations-control-signoff', *argv]
    from song_agent.trust_operations_control_signoff import TrustOperationsControlSignoffStore
    from song_agent.trust_operations_control_signoff_verifier import print_trust_operations_control_signoff_verification_report
    from song_agent.trust_operations_controls import TrustOperationsControlStore
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
    from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore
    parser = build_trust_operations_control_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
    knowledge_store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
    control_store = TrustOperationsControlStore(hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    store = TrustOperationsControlSignoffStore(control_store=control_store, hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    source_payload = {
        "control_package_path": args.control_package,
        "control_verification_report_path": args.control_verification_report,
        "hub_package_path": args.hub_package,
        "hub_verification_report_path": args.hub_verification_report,
        "incident_board_package_path": args.incident_board_package,
        "incident_board_verification_report_path": args.incident_board_verification_report,
        "incident_knowledge_package_path": args.incident_knowledge_package,
        "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
    }
    if args.sign:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --sign.")
        result["signoff"] = store.sign(args.hub_id, str(args.assessment_id), {**source_payload, "signed_by": args.signed_by, "reason": args.reason})
    if args.request_exception:
        if not args.assessment_id or not args.control_id:
            raise ValueError("--assessment-id and --control-id are required for --request-exception.")
        result["exception"] = store.request_exception(args.hub_id, {"assessment_id": args.assessment_id, "control_id": args.control_id, "requested_by": args.requested_by, "reason": args.reason, "expires_at": args.expires_at, "mitigation": args.mitigation})
    if args.approve_exception:
        if not args.exception_id:
            raise ValueError("--exception-id is required for --approve-exception.")
        result["exception"] = store.approve_exception(args.hub_id, args.exception_id, {"approved_by": args.approved_by, "reason": args.reason})
    if args.reject_exception:
        if not args.exception_id:
            raise ValueError("--exception-id is required for --reject-exception.")
        result["exception"] = store.reject_exception(args.hub_id, args.exception_id, {"approved_by": args.approved_by, "reason": args.reason})
    if args.create_change_request:
        result["change_request"] = store.create_change_request(args.hub_id, {"reason": args.reason, "created_by": args.requested_by, "change_request_id": args.change_request_id})
    if args.approve_change_request:
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for --approve-change-request.")
        result["change_request"] = store.approve_change_request(args.hub_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
    if args.reset:
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for --reset.")
        result["reset"] = store.reset_signoff(args.hub_id, args.change_request_id)
    if args.export:
        result["manifest"] = store.export_archive(args.hub_id, source_payload)
    if args.zip:
        result["zip"] = store.build_archive_zip(args.hub_id)
    if args.verify:
        verification = store.verify_archive_zip(args.hub_id, {**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.sign, args.request_exception, args.approve_exception, args.reject_exception, args.create_change_request, args.approve_change_request, args.reset, args.export, args.zip, args.verify]):
        result["summary"] = store.summary(args.hub_id)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_control_signoff_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_control_signoff(argv: list[str]) -> None:
    _execute_trust_operations_control_signoff(argv)

def _execute_trust_operations_hub_runbook(argv: list[str]) -> None:
    raw_args = ['trust-operations-hub-runbook', *argv]
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    from song_agent.trust_operations_hub_runbook import TrustOperationsHubRunbookStore
    from song_agent.trust_operations_hub_runbook_verifier import print_trust_operations_hub_runbook_verification_report, verify_trust_operations_hub_runbook_package
    parser = build_trust_operations_hub_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    store = TrustOperationsHubRunbookStore(hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    report_id = args.report_id
    if not report_id:
        current = read_json(hub_store.current_report_path(args.hub_id)) if hub_store.current_report_path(args.hub_id).exists() else {}
        report_id = str(current.get("report_id") or "")
    runbook_id = args.runbook_id
    if args.create:
        if not report_id:
            raise ValueError("--report-id is required for --create unless a current Hub report exists.")
        runbook = store.create_runbook(args.hub_id, report_id, {"runbook_id": runbook_id})
        runbook_id = str(runbook.get("runbook_id") or runbook_id or "")
        result["runbook"] = runbook
    if not runbook_id:
        raise ValueError("--runbook-id is required unless --create was used.")
    if args.run_safe:
        result["result"] = store.run_safe_actions(args.hub_id, runbook_id)
    if args.export:
        result["manifest"] = store.export_runbook(args.hub_id, runbook_id)
    if args.zip:
        result["zip"] = store.build_zip(args.hub_id, runbook_id)
    if args.verify:
        verification = verify_trust_operations_hub_runbook_package(store.zip_path(args.hub_id, runbook_id), strict=args.strict, require_completed=args.require_completed, require_no_blocked=args.require_no_blocked)
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_hub_runbook_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "runbook_id": runbook_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_hub_runbook(argv: list[str]) -> None:
    _execute_trust_operations_hub_runbook(argv)

def _execute_trust_operations_hub_incidents(argv: list[str]) -> None:
    raw_args = ['trust-operations-hub-incidents', *argv]
    import base64
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    from song_agent.trust_operations_hub_incident_verifier import print_trust_operations_hub_incident_verification_report
    from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
    parser = build_trust_operations_hub_incidents_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    store = TrustOperationsIncidentStore(hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    incident_id = args.incident_id
    if args.refresh:
        refreshed = store.refresh_board(args.hub_id, {"report_id": args.report_id} if args.report_id else {})
        result.update(refreshed)
    if args.list:
        result["incidents"] = store.list_incidents(args.hub_id)
    if any([args.triage, args.create_plan, args.add_evidence, args.verify_fix, args.close, args.archive]) and not incident_id:
        incidents = store.list_incidents(args.hub_id)
        if not incidents:
            raise ValueError("--incident-id is required when no incidents exist.")
        incident_id = str(incidents[0].get("incident_id") or "")
    if args.triage:
        result["incident"] = store.triage_incident(args.hub_id, str(incident_id), {"severity": args.severity, "owner": args.owner, "notes": args.notes})
    if args.create_plan:
        result["plan"] = store.create_plan(args.hub_id, str(incident_id))
    if args.add_evidence:
        content_base64 = args.content_base64
        if args.evidence_file is not None:
            content_base64 = base64.b64encode(args.evidence_file.read_bytes()).decode("ascii")
        result["evidence"] = store.add_evidence(
            args.hub_id,
            str(incident_id),
            {
                "kind": args.evidence_kind,
                "component_type": args.component_type,
                "component_id": args.component_id,
                "content_base64": content_base64,
            },
        )
    if args.verify_fix:
        result["fix_verification"] = store.verify_fix(args.hub_id, str(incident_id))
    if args.close:
        result["closeout"] = store.close_incident(args.hub_id, str(incident_id), {"closed_by": args.closed_by, "reason": args.reason})
    if args.archive:
        result["incident"] = store.archive_incident(args.hub_id, str(incident_id))
    if args.export:
        result["manifest"] = store.export_board(args.hub_id)
    if args.zip:
        result["zip"] = store.build_zip(args.hub_id)
    if args.verify:
        verification = store.verify_zip(
            args.hub_id,
            {
                "strict": args.strict,
                "require_no_open_critical": args.require_no_open_critical,
                "require_no_open_blocking": args.require_no_open_blocking,
                "require_current_hub": args.require_current_hub,
                "hub_verification_report_path": args.hub_verification_report,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_hub_incident_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "incident_id": incident_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_hub_incidents(argv: list[str]) -> None:
    _execute_trust_operations_hub_incidents(argv)

def _execute_trust_operations_incident_knowledge(argv: list[str]) -> None:
    raw_args = ['trust-operations-incident-knowledge', *argv]
    from song_agent.trust_operations_hub import TrustOperationsHubStore
    from song_agent.trust_operations_hub_incidents import TrustOperationsIncidentStore
    from song_agent.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore
    from song_agent.trust_operations_incident_knowledge_verifier import print_trust_operations_incident_knowledge_verification_report
    parser = build_trust_operations_incident_knowledge_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
    store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    if args.refresh:
        result.update(store.refresh(args.hub_id, {"incident_board_verification_report_path": args.incident_board_verification_report, "hub_verification_report_path": args.hub_verification_report}))
    if args.list_entries:
        result["entries"] = store.list_entries(args.hub_id)
    if any([args.hide_entry, args.unhide_entry, args.create_guard]) and not args.entry_id:
        entries = store.list_entries(args.hub_id)
        if not entries:
            raise ValueError("--entry-id is required when no entries exist.")
        args.entry_id = str(entries[0].get("entry_id") or "")
    if args.hide_entry:
        result["entry"] = store.hide_entry(args.hub_id, str(args.entry_id))
    if args.unhide_entry:
        result["entry"] = store.unhide_entry(args.hub_id, str(args.entry_id))
    if args.create_guard:
        result["guard"] = store.create_guard(args.hub_id, str(args.entry_id), {"guard_id": args.guard_id, "guard_type": args.guard_type})
        args.guard_id = str(result["guard"].get("guard_id") or args.guard_id or "")
    if args.run_guard:
        if not args.guard_id:
            guards = store.list_guards(args.hub_id)
            if not guards:
                raise ValueError("--guard-id is required when no guards exist.")
            args.guard_id = str(guards[0].get("guard_id") or "")
        result["guard_run"] = store.run_guard(args.hub_id, str(args.guard_id))
    if args.run_all_guards:
        result["guard_runs"] = store.run_all_guards(args.hub_id)
    if args.refresh_recurrence:
        result["recurrence"] = store.refresh_recurrence(args.hub_id)
    if args.export:
        result["manifest"] = store.export_knowledge(args.hub_id)
    if args.zip:
        result["zip"] = store.build_zip(args.hub_id)
    if args.verify:
        verification = store.verify_zip(
            args.hub_id,
            {
                "strict": args.strict,
                "require_guards_passed": args.require_guards_passed,
                "require_no_open_recurrence": args.require_no_open_recurrence,
                "incident_board_package_path": args.incident_board_package,
                "incident_board_verification_report_path": args.incident_board_verification_report,
                "hub_verification_report_path": args.hub_verification_report,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_incident_knowledge_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)


def handle_trust_operations_incident_knowledge(argv: list[str]) -> None:
    _execute_trust_operations_incident_knowledge(argv)

def _execute_public_trust_center(argv: list[str]) -> None:
    raw_args = ['public-trust-center', *argv]
    from song_agent.public_trust_center import public_trust_center_summary
    from song_agent.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore, anchor_registry_summary
    from song_agent.public_trust_center_anchor_registry_verifier import (
        verify_public_trust_center_anchor_registry_package,
        write_public_trust_center_anchor_registry_verification_report,
    )
    from song_agent.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore, anchor_transparency_summary
    from song_agent.public_trust_center_anchor_transparency_verifier import (
        verify_public_trust_center_anchor_transparency_package,
        write_public_trust_center_anchor_transparency_verification_report,
    )
    from song_agent.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore
    from song_agent.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore, accepted_evidence_summary
    from song_agent.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore, distribution_kit_summary
    parser = build_public_trust_center_parser()
    args = parser.parse_args(raw_args[1:])
    store = _build_public_trust_center_store()
    anchor_store = PublicTrustCenterAnchorRegistryStore(trust_center_store=store)
    anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(anchor_registry_store=anchor_store)
    distribution_kit_store = PublicTrustCenterDistributionKitStore(
        trust_center_store=store,
        anchor_registry_store=anchor_store,
        anchor_transparency_store=anchor_transparency_store,
    )
    distribution_kit_acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(distribution_kit_store=distribution_kit_store)
    acceptance_board_store = PublicTrustCenterAcceptanceBoardStore(acceptance_store=distribution_kit_acceptance_store)
    payload: dict[str, Any] = {
        "center_id": args.center_id,
        "attestation_profile": args.profile,
        "release_ids": args.release_ids,
        "portfolio_ids": args.portfolio_ids,
        "include_all_releases": not bool(args.release_ids),
        "include_all_portfolios": not bool(args.portfolio_ids),
        "require_registry_current": True,
        "require_portal_current": True,
        "require_transparency_current": True,
        "require_acknowledgement_current": args.require_acknowledgement_current,
        "include_delivery": args.include_delivery,
        "include_distribution": args.include_delivery and args.include_distribution,
        "include_submission": args.include_delivery and args.include_submission,
        "include_submission_evidence": args.include_delivery and args.include_submission_evidence,
        "include_operations": args.include_delivery and args.include_operations,
        "require_release_signoff": args.require_release_signoff,
        "require_distribution_signed": args.require_distribution_signed,
        "require_submission_accepted": args.require_submission_accepted,
        "require_submission_evidence_signed": args.require_submission_evidence_signed,
        "require_operations_signed": args.require_operations_signed,
        "require_operations_audit_verified": args.require_operations_audit_verified,
        "require_operations_reviewer_pack_verified": args.require_operations_reviewer_pack_verified,
    }
    if args.name:
        payload["name"] = args.name
    result: dict[str, Any] = {"ok": True, "center_id": args.center_id}
    if args.refresh:
        report = store.refresh_report(args.center_id, payload)
        result.update({"report": report, "summary": public_trust_center_summary(report), "stale": False})
    else:
        config = store.read_config(args.center_id, default={}) or store.create_or_update_center(payload)
        report = store.read_report(args.center_id, default={})
        summary = public_trust_center_summary(report) if report else {"status": "missing", "center_id": args.center_id}
        if report:
            summary["stale"] = store.report_is_stale(args.center_id, report)
        result.update({"config": config, "report": report, "summary": summary, "stale": summary.get("stale", False)})
    if args.export:
        result["manifest"] = store.export_center(args.center_id)
    if args.zip:
        result["zip"] = store.build_zip(args.center_id)
    if args.verify:
        verify_payload = {
            "strict": args.strict,
            "require_registry_current": args.require_registry_current,
            "require_portal_current": args.require_portal_current,
            "require_transparency_current": args.require_transparency_current,
            "require_acknowledgement_current": args.require_acknowledgement_current,
            "require_release_readiness": args.require_release_readiness,
            "require_delivery_readiness": args.require_delivery_readiness,
            "require_distribution_ready": args.require_distribution_ready,
            "require_submission_accepted": args.require_submission_accepted,
            "require_submission_evidence": args.require_submission_evidence,
            "require_operations_signed": args.require_operations_signed,
            "require_operations_audit": args.require_operations_audit,
            "require_operations_reviewer_pack": args.require_operations_reviewer_pack,
            "require_anchor_registry_current": args.require_anchor_registry_current,
            "require_anchor_published": args.require_anchor_published,
            "require_anchor_not_revoked": args.require_anchor_not_revoked,
            "require_anchor_transparency_current": args.require_anchor_transparency_current,
            "require_anchor_checkpoint": args.require_anchor_checkpoint,
        }
        if args.require_anchor_registry_current or args.require_anchor_published or args.require_anchor_not_revoked:
            verify_payload["anchor_registry_path"] = anchor_store.zip_path(args.center_id)
        if args.require_anchor_transparency_current or args.require_anchor_checkpoint:
            verify_payload["anchor_transparency_path"] = anchor_transparency_store.zip_path(args.center_id)
        if args.require_anchor_checkpoint:
            verify_payload["anchor_checkpoint_path"] = anchor_transparency_store.current_checkpoint_path(args.center_id)
        verification = store.verify_zip(args.center_id, verify_payload)
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.archive:
        result["archive"] = store.archive_snapshot(args.center_id)
    if args.anchor_register:
        registered = anchor_store.register_current_anchor(args.center_id, {"reason": args.anchor_reason})
        result["anchor_registry"] = registered
        result["anchor_summary"] = anchor_registry_summary(registered.get("registry") if isinstance(registered.get("registry"), dict) else {})
    if args.anchor_publish:
        registry = anchor_store.read_registry(args.center_id, default={})
        entry_id = str(registry.get("current_entry_id") or "")
        if not entry_id:
            registered = anchor_store.register_current_anchor(args.center_id, {"reason": args.anchor_reason})
            entry_id = str((registered.get("entry") if isinstance(registered.get("entry"), dict) else {}).get("entry_id") or "")
        published = anchor_store.publish_entry(args.center_id, entry_id, {"reason": args.anchor_reason, "supersede_current": True})
        result["anchor_publish"] = published
        result["anchor_summary"] = anchor_registry_summary(published.get("registry") if isinstance(published.get("registry"), dict) else {})
    if args.anchor_revoke:
        revoked = anchor_store.revoke_entry(args.center_id, args.anchor_revoke, {"reason": args.anchor_reason})
        result["anchor_revoke"] = revoked
        result["anchor_summary"] = anchor_registry_summary(revoked.get("registry") if isinstance(revoked.get("registry"), dict) else {})
    if args.anchor_export:
        result["anchor_manifest"] = anchor_store.export_registry(args.center_id)
    if args.anchor_zip:
        result["anchor_zip"] = anchor_store.build_zip(args.center_id)
    if args.anchor_verify:
        anchor_verification = verify_public_trust_center_anchor_registry_package(
            anchor_store.zip_path(args.center_id),
            strict=args.strict,
            require_current=args.require_anchor_registry_current,
            require_anchor_published=args.require_anchor_published,
            require_anchor_not_revoked=args.require_anchor_not_revoked,
        )
        write_public_trust_center_anchor_registry_verification_report(anchor_verification, anchor_store.verification_report_path(args.center_id))
        result["anchor_verification"] = anchor_verification
        result["anchor_verification_summary"] = anchor_verification.get("summary", {})
    if args.anchor_transparency_refresh:
        report = anchor_transparency_store.refresh_report(args.center_id, {"reason": args.anchor_reason})
        result["anchor_transparency"] = report
        result["anchor_transparency_summary"] = anchor_transparency_summary(report)
    if args.anchor_checkpoint_create:
        checkpoint = anchor_transparency_store.create_checkpoint(args.center_id, {"reason": args.anchor_reason})
        result["anchor_checkpoint"] = checkpoint
    if args.anchor_transparency_export:
        result["anchor_transparency_manifest"] = anchor_transparency_store.export_transparency(args.center_id)
    if args.anchor_transparency_zip:
        result["anchor_transparency_zip"] = anchor_transparency_store.build_zip(args.center_id)
    if args.anchor_transparency_verify:
        transparency_verification = verify_public_trust_center_anchor_transparency_package(
            anchor_transparency_store.zip_path(args.center_id),
            strict=args.strict,
            checkpoint_path=anchor_transparency_store.current_checkpoint_path(args.center_id),
            anchor_registry_path=anchor_store.zip_path(args.center_id),
            require_current_checkpoint=args.require_anchor_transparency_current or args.require_anchor_checkpoint,
            require_published_anchor=args.require_anchor_published or args.require_anchor_registry_current,
            require_not_revoked=args.require_anchor_not_revoked,
        )
        write_public_trust_center_anchor_transparency_verification_report(transparency_verification, anchor_transparency_store.verification_report_path(args.center_id))
        result["anchor_transparency_verification"] = transparency_verification
        result["anchor_transparency_verification_summary"] = transparency_verification.get("summary", {})
    if args.distribution_kit_refresh:
        kit_report = distribution_kit_store.refresh_report(args.center_id)
        result["distribution_kit"] = kit_report
        result["distribution_kit_summary"] = distribution_kit_summary(kit_report)
    if args.distribution_kit_export:
        result["distribution_kit_manifest"] = distribution_kit_store.export_kit(args.center_id)
    if args.distribution_kit_zip:
        result["distribution_kit_zip"] = distribution_kit_store.build_zip(args.center_id)
    if args.distribution_kit_verify:
        kit_verification = distribution_kit_store.verify_zip(
            args.center_id,
            {
                "strict": args.strict,
                "deep": True,
                "require_current": True,
                "require_delivery_readiness": args.require_delivery_readiness,
                "require_anchor_registry_current": True,
                "require_anchor_published": True,
                "require_anchor_not_revoked": True,
                "require_anchor_transparency_current": True,
                "require_anchor_checkpoint": True,
            },
        )
        result["distribution_kit_verification"] = kit_verification
        result["distribution_kit_verification_summary"] = kit_verification.get("summary", {})
    if args.distribution_kit_acceptance_template:
        template = distribution_kit_acceptance_store.create_response_template(args.center_id)
        result["distribution_kit_acceptance_template"] = template
    if args.distribution_kit_acceptance_response_file is not None or args.distribution_kit_acceptance_response_base64:
        import_payload: dict[str, Any] = {}
        if args.distribution_kit_acceptance_response_file is not None:
            import_payload["content"] = args.distribution_kit_acceptance_response_file.read_text(encoding="utf-8")
        if args.distribution_kit_acceptance_response_base64:
            import_payload["content_base64"] = args.distribution_kit_acceptance_response_base64
        imported = distribution_kit_acceptance_store.import_response(args.center_id, import_payload)
        result["distribution_kit_acceptance_import"] = imported
        result["distribution_kit_acceptance_summary"] = imported.get("response", {})
    if args.distribution_kit_acceptance_verify_response:
        if not args.distribution_kit_acceptance_response_id:
            raise SystemExit("--distribution-kit-acceptance-response-id is required with --distribution-kit-acceptance-verify-response")
        verification = distribution_kit_acceptance_store.verify_response(args.center_id, args.distribution_kit_acceptance_response_id)
        result["distribution_kit_acceptance_response_verification"] = verification
    if args.distribution_kit_accepted_evidence_export:
        manifest = distribution_kit_acceptance_store.export_accepted_evidence(args.center_id, args.distribution_kit_acceptance_response_id)
        result["distribution_kit_accepted_evidence_manifest"] = manifest
    if args.distribution_kit_accepted_evidence_zip:
        zip_info = distribution_kit_acceptance_store.build_accepted_evidence_zip(args.center_id, args.distribution_kit_acceptance_response_id)
        result["distribution_kit_accepted_evidence_zip"] = zip_info
        evidence = distribution_kit_acceptance_store.read_evidence(args.center_id, zip_info.get("evidence_id"), default={})
        result["distribution_kit_accepted_evidence_summary"] = accepted_evidence_summary(evidence)
    if args.distribution_kit_accepted_evidence_verify:
        evidence_id = None
        if args.distribution_kit_acceptance_response_id:
            evidence = distribution_kit_acceptance_store.refresh_accepted_evidence(args.center_id, {"response_id": args.distribution_kit_acceptance_response_id})
            evidence_id = str(evidence.get("evidence_id") or "")
        verification = distribution_kit_acceptance_store.verify_accepted_evidence_zip(args.center_id, evidence_id, {"strict": args.strict, "require_current": True})
        result["distribution_kit_accepted_evidence_verification"] = verification
        result["distribution_kit_accepted_evidence_verification_summary"] = verification.get("summary", {})
    if args.distribution_kit_acceptance_change_request:
        if not args.distribution_kit_acceptance_response_id:
            raise SystemExit("--distribution-kit-acceptance-response-id is required with --distribution-kit-acceptance-change-request")
        result["distribution_kit_acceptance_change_request"] = distribution_kit_acceptance_store.create_change_request_draft(args.center_id, args.distribution_kit_acceptance_response_id, {"source": "cli"})
    if args.acceptance_board_policy_save is not None:
        result["acceptance_board_policy"] = acceptance_board_store.save_policy(args.center_id, read_json(args.acceptance_board_policy_save))
    if args.acceptance_board_refresh:
        board = acceptance_board_store.refresh_report(args.center_id)
        result["acceptance_board"] = board
        result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
    if args.acceptance_board_export:
        result["acceptance_board_manifest"] = acceptance_board_store.export_board(args.center_id)
    if args.acceptance_board_zip:
        result["acceptance_board_zip"] = acceptance_board_store.build_zip(args.center_id)
    if args.acceptance_board_verify:
        board_verification = acceptance_board_store.verify_zip(
            args.center_id,
            {
                "strict": args.strict,
                "require_ready": args.require_ready,
                "require_quorum": args.require_quorum,
                "require_no_conflicts": args.require_no_conflicts,
                "min_accepted_count": args.min_accepted_count,
                "min_accepted_organizations": args.min_accepted_organizations,
                "required_roles": args.required_roles,
                "use_distribution_kit": True,
            },
        )
        result["acceptance_board_verification"] = board_verification
        result["acceptance_board_verification_summary"] = board_verification.get("summary", {})
    if args.acceptance_board_signoff_draft:
        result["acceptance_board_signoff_draft"] = acceptance_board_store.create_signoff_draft(args.center_id, {"source": "cli"})
    if args.acceptance_board_signoff:
        signoff = acceptance_board_store.signoff(args.center_id, {"signed_by": args.acceptance_board_signed_by, "reason": args.acceptance_board_signoff_reason})
        result["acceptance_board_signoff"] = signoff
        result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
    if args.acceptance_board_change_request_create:
        change = acceptance_board_store.create_change_request(args.center_id, {"reason": args.acceptance_board_signoff_reason, "requested_by": args.acceptance_board_signed_by})
        result["acceptance_board_change_request"] = change
    if args.acceptance_board_change_request_approve:
        if not args.acceptance_board_change_request_id:
            raise SystemExit("--acceptance-board-change-request-id is required with --acceptance-board-change-request-approve")
        change = acceptance_board_store.approve_change_request(args.center_id, args.acceptance_board_change_request_id, {"approved_by": args.acceptance_board_signed_by, "reason": args.acceptance_board_signoff_reason})
        result["acceptance_board_change_request"] = change
    if args.acceptance_board_reset_signoff:
        if not args.acceptance_board_change_request_id:
            raise SystemExit("--acceptance-board-change-request-id is required with --acceptance-board-reset-signoff")
        reset = acceptance_board_store.reset_signoff(args.center_id, {"change_request_id": args.acceptance_board_change_request_id, "reason": args.acceptance_board_signoff_reason})
        result["acceptance_board_signoff_reset"] = reset
        result["acceptance_board_summary"] = acceptance_board_store.summary(args.center_id)
    if args.acceptance_board_signoff_archive_export:
        result["acceptance_board_signoff_archive_manifest"] = acceptance_board_store.export_signoff_archive(args.center_id)
    if args.acceptance_board_signoff_archive_zip:
        result["acceptance_board_signoff_archive_zip"] = acceptance_board_store.build_signoff_archive_zip(args.center_id)
    if args.acceptance_board_signoff_archive_verify:
        archive_verification = acceptance_board_store.verify_signoff_archive_zip(
            args.center_id,
            {
                "strict": args.strict,
                "require_signed": True,
                "require_current": True,
                "require_ready": True,
                "use_board_zip": True,
                "use_board_verification": True,
                "use_distribution_kit": True,
                "use_accepted_evidence": True,
            },
        )
        result["acceptance_board_signoff_archive_verification"] = archive_verification
        result["acceptance_board_signoff_archive_verification_summary"] = archive_verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_public_trust_center_result(result)
    raise SystemExit(0)


def handle_public_trust_center(argv: list[str]) -> None:
    _execute_public_trust_center(argv)


SPECS = (
    CommandSpec(name='verify-release-portfolio-audit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_audit_package, help='Verify Release Portfolio Audit Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_package, help='Verify Release Portfolio Governance Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_archive_package, help='Verify Release Portfolio Governance Archive Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-audit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_audit_package, help='Verify Release Portfolio Governance Audit Package', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_reviewer_pack, help='Verify Release Portfolio Governance Reviewer Pack', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-final-board', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_final_board, help='Verify Release Portfolio Governance Final Board', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-evidence-vault', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_evidence_vault, help='Verify Release Portfolio Governance Evidence Vault', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation, help='Verify Release Portfolio Governance Attestation', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-registry', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_registry, help='Verify Release Portfolio Governance Attestation Registry', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-portal', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_portal, help='Verify Release Portfolio Governance Attestation Portal', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-portal-review-pack', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_portal_review_pack, help='Verify Release Portfolio Governance Attestation Portal Review Pack', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-portal-response', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_portal_response, help='Verify Release Portfolio Governance Attestation Portal Response', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-accepted-evidence', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_accepted_evidence, help='Verify Release Portfolio Governance Attestation Accepted Evidence', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-transparency', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_transparency, help='Verify Release Portfolio Governance Attestation Transparency', group='trust'),
    CommandSpec(name='verify-release-portfolio-governance-attestation-transparency-acknowledgement', parser=build_acceptance_analytics_parser, handler=handle_verify_release_portfolio_governance_attestation_transparency_acknowledgement, help='Verify Release Portfolio Governance Attestation Transparency Acknowledgement', group='trust'),
    CommandSpec(name='verify-public-trust-center-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_package, help='Verify Public Trust Center Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-anchor-registry-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_anchor_registry_package, help='Verify Public Trust Center Anchor Registry Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-anchor-transparency-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_anchor_transparency_package, help='Verify Public Trust Center Anchor Transparency Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-distribution-kit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_distribution_kit_package, help='Verify Public Trust Center Distribution Kit Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-distribution-kit-accepted-evidence-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_distribution_kit_accepted_evidence_package, help='Verify Public Trust Center Distribution Kit Accepted Evidence Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-acceptance-board-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_acceptance_board_package, help='Verify Public Trust Center Acceptance Board Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-acceptance-board-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_acceptance_board_signoff_archive_package, help='Verify Public Trust Center Acceptance Board Signoff Archive Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-publication-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_publication_package, help='Verify Public Trust Center Publication Package', group='trust'),
    CommandSpec(name='verify-public-trust-center-publication-mirror', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_publication_mirror, help='Verify Public Trust Center Publication Mirror', group='trust'),
    CommandSpec(name='verify-public-trust-center-publication-monitoring-package', parser=build_acceptance_analytics_parser, handler=handle_verify_public_trust_center_publication_monitoring_package, help='Verify Public Trust Center Publication Monitoring Package', group='trust'),
    CommandSpec(name='verify-trust-operations-hub-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_hub_package, help='Verify Trust Operations Hub Package', group='trust'),
    CommandSpec(name='verify-trust-operations-assurance-watch-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_assurance_watch_package, help='Verify Trust Operations Assurance Watch Package', group='trust'),
    CommandSpec(name='verify-trust-operations-assurance-watch-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_assurance_watch_signoff_archive_package, help='Verify Trust Operations Assurance Watch Signoff Archive Package', group='trust'),
    CommandSpec(name='verify-trust-operations-final-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_final_handoff_package, help='Verify Trust Operations Final Handoff Package', group='trust'),
    CommandSpec(name='verify-trust-operations-assurance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_assurance_package, help='Verify Trust Operations Assurance Package', group='trust'),
    CommandSpec(name='verify-trust-operations-control-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_control_package, help='Verify Trust Operations Control Package', group='trust'),
    CommandSpec(name='verify-trust-operations-control-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_control_signoff_archive_package, help='Verify Trust Operations Control Signoff Archive Package', group='trust'),
    CommandSpec(name='verify-trust-operations-incident-knowledge-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_incident_knowledge_package, help='Verify Trust Operations Incident Knowledge Package', group='trust'),
    CommandSpec(name='verify-trust-operations-hub-incident-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_hub_incident_package, help='Verify Trust Operations Hub Incident Package', group='trust'),
    CommandSpec(name='verify-trust-operations-hub-runbook-package', parser=build_acceptance_analytics_parser, handler=handle_verify_trust_operations_hub_runbook_package, help='Verify Trust Operations Hub Runbook Package', group='trust'),
    CommandSpec(name='release-portfolio-audit', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_audit, help='Release Portfolio Audit', group='trust'),
    CommandSpec(name='release-portfolio-governance-queue', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_queue, help='Release Portfolio Governance Queue', group='trust'),
    CommandSpec(name='release-portfolio-governance-signoff', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_signoff, help='Release Portfolio Governance Signoff', group='trust'),
    CommandSpec(name='release-portfolio-governance-audit', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_audit, help='Release Portfolio Governance Audit', group='trust'),
    CommandSpec(name='release-portfolio-governance-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_reviewer_pack, help='Release Portfolio Governance Reviewer Pack', group='trust'),
    CommandSpec(name='release-portfolio-governance-final-board', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_final_board, help='Release Portfolio Governance Final Board', group='trust'),
    CommandSpec(name='release-portfolio-governance-evidence-vault', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_evidence_vault, help='Release Portfolio Governance Evidence Vault', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation, help='Release Portfolio Governance Attestation', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-registry', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_registry, help='Release Portfolio Governance Attestation Registry', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-portal', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_portal, help='Release Portfolio Governance Attestation Portal', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-portal-review', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_portal_review, help='Release Portfolio Governance Attestation Portal Review', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-accepted-evidence', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_accepted_evidence, help='Release Portfolio Governance Attestation Accepted Evidence', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-transparency', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_transparency, help='Release Portfolio Governance Attestation Transparency', group='trust'),
    CommandSpec(name='release-portfolio-governance-attestation-transparency-acknowledgement', parser=build_acceptance_analytics_parser, handler=handle_release_portfolio_governance_attestation_transparency_acknowledgement, help='Release Portfolio Governance Attestation Transparency Acknowledgement', group='trust'),
    CommandSpec(name='public-trust-center-publication', parser=build_acceptance_analytics_parser, handler=handle_public_trust_center_publication, help='Public Trust Center Publication', group='trust'),
    CommandSpec(name='public-trust-center-publication-monitor', parser=build_acceptance_analytics_parser, handler=handle_public_trust_center_publication_monitor, help='Public Trust Center Publication Monitor', group='trust'),
    CommandSpec(name='trust-operations-hub', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_hub, help='Trust Operations Hub', group='trust'),
    CommandSpec(name='trust-operations-assurance-watch', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_assurance_watch, help='Trust Operations Assurance Watch', group='trust'),
    CommandSpec(name='trust-operations-assurance-watch-signoff', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_assurance_watch_signoff, help='Trust Operations Assurance Watch Signoff', group='trust'),
    CommandSpec(name='trust-operations-final-readiness', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_final_readiness, help='Trust Operations Final Readiness', group='trust'),
    CommandSpec(name='trust-operations-controls', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_controls, help='Trust Operations Controls', group='trust'),
    CommandSpec(name='trust-operations-assurance', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_assurance, help='Trust Operations Assurance', group='trust'),
    CommandSpec(name='trust-operations-control-signoff', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_control_signoff, help='Trust Operations Control Signoff', group='trust'),
    CommandSpec(name='trust-operations-hub-runbook', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_hub_runbook, help='Trust Operations Hub Runbook', group='trust'),
    CommandSpec(name='trust-operations-hub-incidents', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_hub_incidents, help='Trust Operations Hub Incidents', group='trust'),
    CommandSpec(name='trust-operations-incident-knowledge', parser=build_acceptance_analytics_parser, handler=handle_trust_operations_incident_knowledge, help='Trust Operations Incident Knowledge', group='trust'),
    CommandSpec(name='public-trust-center', parser=build_acceptance_analytics_parser, handler=handle_public_trust_center, help='Public Trust Center', group='trust'),
)
