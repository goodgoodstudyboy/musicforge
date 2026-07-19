from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document

from typing import Any as _InterfaceType

from song_agent.interfaces.cli.bindings import BINDINGS as CLI_BINDINGS

from . import dependencies as _commands_release_check_parts_dependencies

from .cross_domain_adapters import _add_ga_unified_command_center_evidence_args
Any, CommandSpec, Path, ProviderConfig, ProviderError, SongRequest, argparse, build_auth_config, build_ga_readiness_report, generate_request, json, load_provider_config, os, print_release_check_report, provider_configured, read_json, release_check_definitions_as_dicts, release_check_profiles, run_release_check_matrix, select_check_definitions, sys, test_provider_config, verify_ga_readiness_report, write_ga_readiness_report, write_ga_readiness_verification_report, write_interface_document, write_json, write_json_report, write_timing_report = _commands_release_check_parts_dependencies.Any, _commands_release_check_parts_dependencies.CommandSpec, _commands_release_check_parts_dependencies.Path, _commands_release_check_parts_dependencies.ProviderConfig, _commands_release_check_parts_dependencies.ProviderError, _commands_release_check_parts_dependencies.SongRequest, _commands_release_check_parts_dependencies.argparse, _commands_release_check_parts_dependencies.build_auth_config, _commands_release_check_parts_dependencies.build_ga_readiness_report, _commands_release_check_parts_dependencies.generate_request, _commands_release_check_parts_dependencies.json, _commands_release_check_parts_dependencies.load_provider_config, _commands_release_check_parts_dependencies.os, _commands_release_check_parts_dependencies.print_release_check_report, _commands_release_check_parts_dependencies.provider_configured, _commands_release_check_parts_dependencies.read_json, _commands_release_check_parts_dependencies.release_check_definitions_as_dicts, _commands_release_check_parts_dependencies.release_check_profiles, _commands_release_check_parts_dependencies.run_release_check_matrix, _commands_release_check_parts_dependencies.select_check_definitions, _commands_release_check_parts_dependencies.sys, _commands_release_check_parts_dependencies.test_provider_config, _commands_release_check_parts_dependencies.verify_ga_readiness_report, _commands_release_check_parts_dependencies.write_ga_readiness_report, _commands_release_check_parts_dependencies.write_ga_readiness_verification_report, _commands_release_check_parts_dependencies.write_interface_document, _commands_release_check_parts_dependencies.write_json, _commands_release_check_parts_dependencies.write_json_report, _commands_release_check_parts_dependencies.write_timing_report
def print_acceptance_fix_plan_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_acceptance_fix_plan_result(*args, **kwargs)

def print_acceptance_fix_sprint_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_acceptance_fix_sprint_result(*args, **kwargs)

def print_acceptance_kb_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_acceptance_kb_result(*args, **kwargs)

def print_planning_rule_governance_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_planning_rule_governance_result(*args, **kwargs)

def print_planning_rule_impact_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_planning_rule_impact_result(*args, **kwargs)

def print_planning_ruleset_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_planning_ruleset_result(*args, **kwargs)

def print_planning_simulation_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_planning_simulation_result(*args, **kwargs)

def print_public_trust_center_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_public_trust_center_result(*args, **kwargs)

def print_release_audio_review_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.print_release_audio_review_result(*args, **kwargs)

def print_release_operations_archive_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.delivery.print_release_operations_archive_result(*args, **kwargs)

def print_release_operations_audit_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.delivery.print_release_operations_audit_result(*args, **kwargs)

def print_release_operations_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.delivery.print_release_operations_result(*args, **kwargs)

def print_release_operations_reviewer_pack_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.delivery.print_release_operations_reviewer_pack_result(*args, **kwargs)

def print_release_operations_runbook_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.delivery.print_release_operations_runbook_result(*args, **kwargs)

def print_release_operations_signoff_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.delivery.print_release_operations_signoff_result(*args, **kwargs)

def print_release_portfolio_audit_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_audit_result(*args, **kwargs)

def print_release_portfolio_governance_attestation_accepted_evidence_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_accepted_evidence_result(*args, **kwargs)

def print_release_portfolio_governance_attestation_portal_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_portal_result(*args, **kwargs)

def print_release_portfolio_governance_attestation_portal_review_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_portal_review_result(*args, **kwargs)

def print_release_portfolio_governance_attestation_registry_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_registry_result(*args, **kwargs)

def print_release_portfolio_governance_attestation_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_result(*args, **kwargs)

def print_release_portfolio_governance_attestation_transparency_acknowledgement_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_transparency_acknowledgement_result(*args, **kwargs)

def print_release_portfolio_governance_attestation_transparency_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_transparency_result(*args, **kwargs)

def print_release_portfolio_governance_audit_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_audit_result(*args, **kwargs)

def print_release_portfolio_governance_evidence_vault_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_evidence_vault_result(*args, **kwargs)

def print_release_portfolio_governance_final_board_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_final_board_result(*args, **kwargs)

def print_release_portfolio_governance_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_result(*args, **kwargs)

def print_release_portfolio_governance_reviewer_pack_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_reviewer_pack_result(*args, **kwargs)

def print_release_portfolio_governance_signoff_result(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.trust.print_release_portfolio_governance_signoff_result(*args, **kwargs)

def run_acceptance_check(*args: _InterfaceType, **kwargs: _InterfaceType) -> _InterfaceType:
    return CLI_BINDINGS.quality.run_acceptance_check(*args, **kwargs)

def build_release_check_parser() -> argparse.ArgumentParser:
    pass

    parser = argparse.ArgumentParser(description="Run MusicForge release verification checks.")
    parser.add_argument("--profile", default="full", choices=release_check_profiles(), help="Release-check profile to run.")
    parser.add_argument("--group", action="append", default=[], help="Run checks matching this group or tag. Can be repeated.")
    parser.add_argument("--since", default=None, help="Run versioned checks from this version onward, for example 7.0.")
    parser.add_argument("--only", action="append", default=[], help="Run only one or more check ids. Comma-separated values are accepted.")
    parser.add_argument("--list", action="store_true", help="List selected checks without running them.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the JSON report to this path.")
    parser.add_argument("--timing-out", type=Path, default=None, help="Write a lightweight timing report to this path.")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed check.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Override per-command timeout. Minimum is 10 seconds.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the full pytest check when selected.")
    return parser

def build_ga_check_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MusicForge GA/LTS readiness checks.")
    parser.add_argument("--policy", choices=("ga.standard", "ga.lts"), default=None, help="Evaluate a declarative GA policy against the external evidence manifest.")
    parser.add_argument("--evidence-manifest", type=Path, default=None, help="Runtime-verifiable Evidence Graph manifest used by --policy.")
    parser.add_argument("--json", action="store_true", help="Print the full GA readiness report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the GA readiness report to this JSON file.")
    parser.add_argument("--strict", action="store_true", help="Treat a dirty working tree and missing required evidence as blocking.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow dirty working tree as a warning even with --strict.")
    parser.add_argument("--require-manual-acceptance", action="store_true", help="Require manual listening acceptance evidence.")
    parser.add_argument("--require-audio", action="store_true", help="Require renderer/audio acceptance readiness.")
    parser.add_argument("--require-final-readiness", action="store_true", help="Require a passed Final Handoff verification report.")
    parser.add_argument("--final-handoff-verification-report", type=Path, default=None, help="Path to Final Handoff verification report JSON.")
    parser.add_argument("--require-audio-campaign", dest="audio_campaign_id", default=None, help="Require a signed Audio Campaign id.")
    parser.add_argument("--audio-campaign-archive", type=Path, default=None, help="Path to Audio Campaign Archive ZIP.")
    parser.add_argument("--audio-campaign-archive-verification-report", type=Path, default=None, help="Path to Audio Campaign Archive verification report JSON.")
    parser.add_argument("--require-audio-campaign-remediation", action="store_true", help="Require passed Release Audio Campaign remediation evidence.")
    parser.add_argument("--audio-campaign-remediation", type=Path, default=None, help="Path to Release Audio Campaign Remediation ZIP.")
    parser.add_argument("--audio-campaign-remediation-verification-report", type=Path, default=None, help="Path to Release Audio Campaign Remediation verification report JSON.")
    parser.add_argument("--require-release-audio-certification", action="store_true", help="Require passed signed Release Audio Certification evidence.")
    parser.add_argument("--release-audio-certification", type=Path, default=None, help="Path to Release Audio Certification ZIP.")
    parser.add_argument("--release-audio-certification-verification-report", type=Path, default=None, help="Path to Release Audio Certification verification report JSON.")
    parser.add_argument("--require-release-audio-timeline", action="store_true", help="Require passed signed Release Audio Timeline evidence.")
    parser.add_argument("--release-audio-timeline", type=Path, default=None, help="Path to Release Audio Timeline ZIP.")
    parser.add_argument("--release-audio-timeline-verification-report", type=Path, default=None, help="Path to Release Audio Timeline verification report JSON.")
    parser.add_argument("--release-audio-timeline-certification", type=Path, default=None, help="Path to the Release Audio Certification ZIP bound by the timeline.")
    parser.add_argument("--release-audio-timeline-certification-verification-report", type=Path, default=None, help="Path to the Release Audio Certification verification report bound by the timeline.")
    parser.add_argument("--require-release-audio-regression-guard", action="store_true", help="Require passed signed Release Audio Regression Guard evidence.")
    parser.add_argument("--release-audio-regression", type=Path, default=None, help="Path to Release Audio Regression ZIP.")
    parser.add_argument("--release-audio-regression-verification-report", type=Path, default=None, help="Path to Release Audio Regression verification report JSON.")
    parser.add_argument("--release-audio-regression-baseline-timeline", type=Path, default=None, help="Baseline Release Audio Timeline ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-baseline-timeline-verification-report", type=Path, default=None, help="Baseline Release Audio Timeline verification report.")
    parser.add_argument("--release-audio-regression-baseline-certification", type=Path, default=None, help="Baseline Release Audio Certification ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-baseline-certification-verification-report", type=Path, default=None, help="Baseline Release Audio Certification verification report.")
    parser.add_argument("--release-audio-regression-current-timeline", type=Path, default=None, help="Current Release Audio Timeline ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-current-timeline-verification-report", type=Path, default=None, help="Current Release Audio Timeline verification report.")
    parser.add_argument("--release-audio-regression-current-certification", type=Path, default=None, help="Current Release Audio Certification ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-current-certification-verification-report", type=Path, default=None, help="Current Release Audio Certification verification report.")
    parser.add_argument("--require-release-audio-baseline-governance", action="store_true", help="Require approved active Release Audio Baseline Governance evidence.")
    parser.add_argument("--release-audio-baseline-registry", type=Path, default=None, help="Release Audio Baseline Registry ZIP.")
    parser.add_argument("--release-audio-baseline-registry-verification-report", type=Path, default=None, help="Release Audio Baseline Registry verification report.")
    parser.add_argument("--require-release-audio-regression-response", action="store_true", help="Require closed signed Release Audio Regression Response evidence.")
    parser.add_argument("--release-audio-regression-response", type=Path, default=None, help="Release Audio Regression Response ZIP.")
    parser.add_argument("--release-audio-regression-response-verification-report", type=Path, default=None, help="Release Audio Regression Response verification report.")
    parser.add_argument("--require-release-audio-quality-observatory", action="store_true", help="Require passed Release Audio Quality Observatory evidence.")
    parser.add_argument("--release-audio-quality-observatory", type=Path, default=None, help="Release Audio Quality Observatory ZIP.")
    parser.add_argument("--release-audio-quality-observatory-verification-report", type=Path, default=None, help="Release Audio Quality Observatory verification report.")
    parser.add_argument("--release-audio-quality-observatory-evidence-root", type=Path, default=None, help="Release evidence root used to verify Observatory source bindings.")
    parser.add_argument("--require-no-critical-audio-quality-risk", action="store_true", help="Require Observatory evidence to have no critical audio quality risk.")
    parser.add_argument("--require-release-audio-quality-action-queue", action="store_true", help="Require passed Release Audio Quality Action Queue evidence.")
    parser.add_argument("--release-audio-quality-action-queue", type=Path, default=None, help="Release Audio Quality Action Queue ZIP.")
    parser.add_argument("--release-audio-quality-action-queue-verification-report", type=Path, default=None, help="Release Audio Quality Action Queue verification report.")
    parser.add_argument("--require-release-audio-quality-action-queue-signoff", action="store_true", help="Require signed Release Audio Quality Action Queue closeout archive evidence.")
    parser.add_argument("--release-audio-quality-action-queue-signoff-archive", type=Path, default=None, help="Release Audio Quality Action Queue Signoff Archive ZIP.")
    parser.add_argument("--release-audio-quality-action-queue-signoff-verification-report", type=Path, default=None, help="Release Audio Quality Action Queue Signoff Archive verification report.")
    parser.add_argument("--require-release-audio-command-center", action="store_true", help="Require Release Audio Command Center evidence.")
    parser.add_argument("--release-audio-command-center", type=Path, default=None, help="Release Audio Command Center ZIP.")
    parser.add_argument("--release-audio-command-center-verification-report", type=Path, default=None, help="Release Audio Command Center verification report.")
    parser.add_argument("--require-unified-command-center", action="store_true", help="Require Unified Command Center evidence.")
    parser.add_argument("--unified-command-center", type=Path, default=None, help="Unified Command Center ZIP.")
    parser.add_argument("--unified-command-center-verification-report", type=Path, default=None, help="Unified Command Center verification report.")
    parser.add_argument("--require-unified-command-center-archive", action="store_true", help="Require Unified Command Center Signoff Archive evidence.")
    parser.add_argument("--unified-command-center-archive", type=Path, default=None, help="Unified Command Center Signoff Archive ZIP.")
    parser.add_argument("--unified-command-center-archive-verification-report", type=Path, default=None, help="Unified Command Center Signoff Archive verification report.")
    parser.add_argument("--require-unified-command-center-handoff", action="store_true", help="Require Unified Command Center Final Handoff evidence.")
    parser.add_argument("--unified-command-center-handoff", type=Path, default=None, help="Unified Command Center Final Handoff ZIP.")
    parser.add_argument("--unified-command-center-handoff-verification-report", type=Path, default=None, help="Unified Command Center Final Handoff verification report.")
    _add_ga_unified_command_center_evidence_args(parser)
    parser.add_argument("--release-check-latest-report", type=Path, default=None, help="Path to an existing latest release-check JSON report.")
    parser.add_argument("--release-check-ga-report", type=Path, default=None, help="Path to an existing ga release-check JSON report.")
    parser.add_argument("--run-release-checks", action="store_true", help="Run latest and ga release-check profiles during ga-check.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip full pytest if --run-release-checks selects it.")
    return parser

def build_verify_ga_readiness_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge GA readiness report.")
    parser.add_argument("report_path", type=Path, help="Path to ga-readiness-report.json.")
    parser.add_argument("--policy", choices=("ga.standard", "ga.lts"), default=None, help="Require the GA report to match this current Evidence Graph policy.")
    parser.add_argument("--evidence-manifest", type=Path, default=None, help="External Evidence Graph manifest used for current runtime verification.")
    parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    parser.add_argument("--strict", action="store_true", help="Require GA status ready, not warning.")
    parser.add_argument("--require-ready", action="store_true", help="Require GA readiness status ready.")
    parser.add_argument("--require-manual-acceptance", action="store_true", help="Require external manual acceptance evidence.")
    parser.add_argument("--manual-acceptance-report", type=Path, default=None, help="External music acceptance report JSON to bind manual readiness.")
    parser.add_argument("--require-final-readiness", action="store_true", help="Require external final readiness evidence.")
    parser.add_argument("--final-handoff-package", type=Path, default=None, help="External Trust Operations Final Handoff ZIP.")
    parser.add_argument("--final-handoff-verification-report", type=Path, default=None, help="External Trust Operations Final Handoff verification report JSON.")
    parser.add_argument("--require-audio-campaign", action="store_true", help="Require external Audio Campaign governance evidence.")
    parser.add_argument("--audio-campaign-archive", type=Path, default=None, help="External Audio Campaign Archive ZIP.")
    parser.add_argument("--audio-campaign-archive-verification-report", type=Path, default=None, help="External Audio Campaign Archive verification report JSON.")
    parser.add_argument("--require-audio-campaign-remediation", action="store_true", help="Require external Audio Campaign remediation evidence.")
    parser.add_argument("--audio-campaign-remediation", type=Path, default=None, help="External Audio Campaign Remediation ZIP.")
    parser.add_argument("--audio-campaign-remediation-verification-report", type=Path, default=None, help="External Audio Campaign Remediation verification report JSON.")
    parser.add_argument("--require-release-audio-certification", action="store_true", help="Require external Release Audio Certification evidence.")
    parser.add_argument("--release-audio-certification", type=Path, default=None, help="External Release Audio Certification ZIP.")
    parser.add_argument("--release-audio-certification-verification-report", type=Path, default=None, help="External Release Audio Certification verification report JSON.")
    parser.add_argument("--require-release-audio-timeline", action="store_true", help="Require external Release Audio Timeline evidence.")
    parser.add_argument("--release-audio-timeline", type=Path, default=None, help="External Release Audio Timeline ZIP.")
    parser.add_argument("--release-audio-timeline-verification-report", type=Path, default=None, help="External Release Audio Timeline verification report JSON.")
    parser.add_argument("--release-audio-timeline-certification", type=Path, default=None, help="External Release Audio Certification ZIP bound by the timeline.")
    parser.add_argument("--release-audio-timeline-certification-verification-report", type=Path, default=None, help="External Release Audio Certification verification report bound by the timeline.")
    parser.add_argument("--require-release-audio-regression-guard", action="store_true", help="Require external Release Audio Regression Guard evidence.")
    parser.add_argument("--release-audio-regression", type=Path, default=None, help="External Release Audio Regression ZIP.")
    parser.add_argument("--release-audio-regression-verification-report", type=Path, default=None, help="External Release Audio Regression verification report JSON.")
    parser.add_argument("--release-audio-regression-baseline-timeline", type=Path, default=None, help="Baseline Release Audio Timeline ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-baseline-timeline-verification-report", type=Path, default=None, help="Baseline Release Audio Timeline verification report.")
    parser.add_argument("--release-audio-regression-baseline-certification", type=Path, default=None, help="Baseline Release Audio Certification ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-baseline-certification-verification-report", type=Path, default=None, help="Baseline Release Audio Certification verification report.")
    parser.add_argument("--release-audio-regression-current-timeline", type=Path, default=None, help="Current Release Audio Timeline ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-current-timeline-verification-report", type=Path, default=None, help="Current Release Audio Timeline verification report.")
    parser.add_argument("--release-audio-regression-current-certification", type=Path, default=None, help="Current Release Audio Certification ZIP bound by the regression guard.")
    parser.add_argument("--release-audio-regression-current-certification-verification-report", type=Path, default=None, help="Current Release Audio Certification verification report.")
    parser.add_argument("--require-release-audio-baseline-governance", action="store_true", help="Require external Release Audio Baseline Governance evidence.")
    parser.add_argument("--release-audio-baseline-registry", type=Path, default=None, help="Release Audio Baseline Registry ZIP.")
    parser.add_argument("--release-audio-baseline-registry-verification-report", type=Path, default=None, help="Release Audio Baseline Registry verification report JSON.")
    parser.add_argument("--require-release-audio-regression-response", action="store_true", help="Require external Release Audio Regression Response evidence.")
    parser.add_argument("--release-audio-regression-response", type=Path, default=None, help="Release Audio Regression Response ZIP.")
    parser.add_argument("--release-audio-regression-response-verification-report", type=Path, default=None, help="Release Audio Regression Response verification report JSON.")
    parser.add_argument("--require-release-audio-quality-observatory", action="store_true", help="Require external Release Audio Quality Observatory evidence.")
    parser.add_argument("--release-audio-quality-observatory", type=Path, default=None, help="External Release Audio Quality Observatory ZIP.")
    parser.add_argument("--release-audio-quality-observatory-verification-report", type=Path, default=None, help="Release Audio Quality Observatory verification report JSON.")
    parser.add_argument("--release-audio-quality-observatory-evidence-root", type=Path, default=None, help="Release evidence root used to verify Observatory source bindings.")
    parser.add_argument("--require-no-critical-audio-quality-risk", action="store_true", help="Require Observatory evidence to have no critical audio quality risk.")
    parser.add_argument("--require-release-audio-quality-action-queue", action="store_true", help="Require external Release Audio Quality Action Queue evidence.")
    parser.add_argument("--release-audio-quality-action-queue", type=Path, default=None, help="External Release Audio Quality Action Queue ZIP.")
    parser.add_argument("--release-audio-quality-action-queue-verification-report", type=Path, default=None, help="Release Audio Quality Action Queue verification report JSON.")
    parser.add_argument("--require-release-audio-quality-action-queue-signoff", action="store_true", help="Require external Release Audio Quality Action Queue signoff archive evidence.")
    parser.add_argument("--release-audio-quality-action-queue-signoff-archive", type=Path, default=None, help="External Release Audio Quality Action Queue Signoff Archive ZIP.")
    parser.add_argument("--release-audio-quality-action-queue-signoff-verification-report", type=Path, default=None, help="Release Audio Quality Action Queue Signoff Archive verification report JSON.")
    parser.add_argument("--require-release-audio-command-center", action="store_true", help="Require external Release Audio Command Center evidence.")
    parser.add_argument("--release-audio-command-center", type=Path, default=None, help="External Release Audio Command Center ZIP.")
    parser.add_argument("--release-audio-command-center-verification-report", type=Path, default=None, help="Release Audio Command Center verification report JSON.")
    parser.add_argument("--require-unified-command-center", action="store_true", help="Require external Unified Command Center evidence.")
    parser.add_argument("--unified-command-center", type=Path, default=None, help="External Unified Command Center ZIP.")
    parser.add_argument("--unified-command-center-verification-report", type=Path, default=None, help="Unified Command Center verification report JSON.")
    parser.add_argument("--require-unified-command-center-archive", action="store_true", help="Require external Unified Command Center Signoff Archive evidence.")
    parser.add_argument("--unified-command-center-archive", type=Path, default=None, help="External Unified Command Center Signoff Archive ZIP.")
    parser.add_argument("--unified-command-center-archive-verification-report", type=Path, default=None, help="Unified Command Center Signoff Archive verification report JSON.")
    parser.add_argument("--require-unified-command-center-handoff", action="store_true", help="Require external Unified Command Center Final Handoff evidence.")
    parser.add_argument("--unified-command-center-handoff", type=Path, default=None, help="External Unified Command Center Final Handoff ZIP.")
    parser.add_argument("--unified-command-center-handoff-verification-report", type=Path, default=None, help="Unified Command Center Final Handoff verification report JSON.")
    _add_ga_unified_command_center_evidence_args(parser)
    parser.add_argument("--release-check-latest-report", type=Path, default=None, help="External latest release-check JSON report.")
    parser.add_argument("--release-check-ga-report", type=Path, default=None, help="External ga release-check JSON report.")
    return parser

def print_ga_readiness_report(report: dict[str, _InterfaceType]) -> None:
    print("MusicForge GA readiness")
    print(f"status: {report.get('status')}")
    summary = _as_document(report.get("summary"))
    for key in (
        "doctor_status",
        "release_check_latest_status",
        "release_check_ga_status",
        "acceptance_status",
        "renderer_status",
        "provider_status",
        "trust_final_readiness_status",
        "git_status",
    ):
        print(f"{key}: {summary.get(key, 'unknown')}")
    for check in report.get("checks") or []:
        if not isinstance(check, dict):
            continue
        print(f"{check.get('check_id')}: {check.get('status')} ({check.get('severity')})")
        if check.get("message"):
            print(f"  {check.get('message')}")
    actions = [item for item in report.get("next_actions") or [] if isinstance(item, dict)]
    if actions:
        print("next actions:")
        for item in actions[:10]:
            print(f"- {item.get('check_id')}: {item.get('action')}")

def _warn_legacy_ga_flags(argv: list[str]) -> None:
    legacy = sorted({value.split("=", 1)[0] for value in argv if value.startswith("--require-") or value.startswith("--no-require-")})
    if legacy:
        print(
            "Deprecated GA evidence flags are compatibility aliases and will be removed in v13.0; use --policy with --evidence-manifest: "
            + ", ".join(legacy),
            file=sys.stderr,
        )

__all__ = ('print_acceptance_fix_plan_result', 'print_acceptance_fix_sprint_result', 'print_acceptance_kb_result', 'print_planning_rule_governance_result', 'print_planning_rule_impact_result', 'print_planning_ruleset_result', 'print_planning_simulation_result', 'print_public_trust_center_result', 'print_release_audio_review_result', 'print_release_operations_archive_result', 'print_release_operations_audit_result', 'print_release_operations_result', 'print_release_operations_reviewer_pack_result', 'print_release_operations_runbook_result', 'print_release_operations_signoff_result', 'print_release_portfolio_audit_result', 'print_release_portfolio_governance_attestation_accepted_evidence_result', 'print_release_portfolio_governance_attestation_portal_result', 'print_release_portfolio_governance_attestation_portal_review_result', 'print_release_portfolio_governance_attestation_registry_result', 'print_release_portfolio_governance_attestation_result', 'print_release_portfolio_governance_attestation_transparency_acknowledgement_result', 'print_release_portfolio_governance_attestation_transparency_result', 'print_release_portfolio_governance_audit_result', 'print_release_portfolio_governance_evidence_vault_result', 'print_release_portfolio_governance_final_board_result', 'print_release_portfolio_governance_result', 'print_release_portfolio_governance_reviewer_pack_result', 'print_release_portfolio_governance_signoff_result', 'run_acceptance_check', 'build_release_check_parser', 'build_ga_check_parser', 'build_verify_ga_readiness_parser', 'print_ga_readiness_report', '_warn_legacy_ga_flags')
