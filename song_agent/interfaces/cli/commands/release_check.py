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

def _add_ga_unified_command_center_evidence_args(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_add_ga_unified_command_center_evidence_args')(*args, **kwargs)

def _build_public_trust_center_publication_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_publication_store')(*args, **kwargs)

def _build_public_trust_center_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_store')(*args, **kwargs)

def _build_release_portfolio_governance_attestation_portal_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_release_portfolio_governance_attestation_portal_store')(*args, **kwargs)

def _print_audio_campaign_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_print_audio_campaign_result')(*args, **kwargs)

def _print_audio_fix_sprint_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_print_audio_fix_sprint_result')(*args, **kwargs)

def _print_audio_lab_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_print_audio_lab_result')(*args, **kwargs)

def _print_maintenance_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('maintenance', '_print_maintenance_result')(*args, **kwargs)

def _print_release_audio_certification_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_print_release_audio_certification_result')(*args, **kwargs)

def _release_audio_command_center_evidence_from_args(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_release_audio_command_center_evidence_from_args')(*args, **kwargs)

def _run_audio_campaign_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_audio_campaign_command')(*args, **kwargs)

def _run_audio_fix_sprint_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_audio_fix_sprint_command')(*args, **kwargs)

def _run_audio_lab_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_audio_lab_command')(*args, **kwargs)

def _run_maintenance_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('maintenance', '_run_maintenance_command')(*args, **kwargs)

def _run_release_audio_baseline_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_baseline_command')(*args, **kwargs)

def _run_release_audio_certification_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_certification_command')(*args, **kwargs)

def _run_release_audio_command_center_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_command_center_command')(*args, **kwargs)

def _run_release_audio_quality_actions_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_quality_actions_command')(*args, **kwargs)

def _run_release_audio_quality_observatory_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_quality_observatory_command')(*args, **kwargs)

def _run_release_audio_regression_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_regression_command')(*args, **kwargs)

def _run_release_audio_regression_response_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_regression_response_command')(*args, **kwargs)

def _run_release_audio_timeline_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_run_release_audio_timeline_command')(*args, **kwargs)

def _run_unified_command_center_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_command')(*args, **kwargs)

def _run_unified_command_center_drift_response_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_drift_response_command')(*args, **kwargs)

def _run_unified_command_center_evidence_review_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_evidence_review_command')(*args, **kwargs)

def _run_unified_command_center_release_train_change_control_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_release_train_change_control_command')(*args, **kwargs)

def _run_unified_command_center_release_train_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_release_train_command')(*args, **kwargs)

def _run_unified_command_center_release_train_handoff_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_release_train_handoff_command')(*args, **kwargs)

def _run_unified_command_center_release_train_lifecycle_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_release_train_lifecycle_command')(*args, **kwargs)

def _run_unified_command_center_review_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_review_command')(*args, **kwargs)

def _run_unified_command_center_reviewer_decision_board_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_command_center_reviewer_decision_board_command')(*args, **kwargs)

def _run_unified_release_program_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_command')(*args, **kwargs)

def _run_unified_release_program_continuity_acceptance_change_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_acceptance_change_command')(*args, **kwargs)

def _run_unified_release_program_continuity_acceptance_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_acceptance_command')(*args, **kwargs)

def _run_unified_release_program_continuity_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_command')(*args, **kwargs)

def _run_unified_release_program_continuity_command_center_acceptance_change_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_command_center_acceptance_change_command')(*args, **kwargs)

def _run_unified_release_program_continuity_command_center_acceptance_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_command_center_acceptance_command')(*args, **kwargs)

def _run_unified_release_program_continuity_command_center_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_command_center_command')(*args, **kwargs)

def _run_unified_release_program_continuity_command_center_signoff_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_command_center_signoff_command')(*args, **kwargs)

def _run_unified_release_program_continuity_distribution_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_continuity_distribution_command')(*args, **kwargs)

def _run_unified_release_program_handoff_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_handoff_command')(*args, **kwargs)

def _run_unified_release_program_operations_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_operations_command')(*args, **kwargs)

def _run_unified_release_program_vault_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_vault_command')(*args, **kwargs)

def _run_unified_release_program_vault_operations_command(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_run_unified_release_program_vault_operations_command')(*args, **kwargs)

def _trust_operations_assurance_source_payload(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_trust_operations_assurance_source_payload')(*args, **kwargs)

def _trust_operations_assurance_watch_source_payload(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_trust_operations_assurance_watch_source_payload')(*args, **kwargs)

def _trust_operations_final_readiness_source_payload(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_trust_operations_final_readiness_source_payload')(*args, **kwargs)

def _unified_command_center_evidence_from_args(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', '_unified_command_center_evidence_from_args')(*args, **kwargs)

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

def build_audio_campaign_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_audio_campaign_parser')(*args, **kwargs)

def build_audio_fix_sprint_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_audio_fix_sprint_parser')(*args, **kwargs)

def build_audio_health_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_audio_health_parser')(*args, **kwargs)

def build_audio_lab_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_audio_lab_parser')(*args, **kwargs)

def build_audio_profile_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_audio_profile_parser')(*args, **kwargs)

def build_encoded_audio_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_encoded_audio_acceptance_parser')(*args, **kwargs)

def build_format_decision_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_format_decision_parser')(*args, **kwargs)

def build_maintenance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('maintenance', 'build_maintenance_parser')(*args, **kwargs)

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

def build_public_trust_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_parser')(*args, **kwargs)

def build_public_trust_center_publication_monitor_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_publication_monitor_parser')(*args, **kwargs)

def build_public_trust_center_publication_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_publication_parser')(*args, **kwargs)

def build_release_audio_baseline_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_baseline_parser')(*args, **kwargs)

def build_release_audio_certification_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_certification_parser')(*args, **kwargs)

def build_release_audio_command_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_command_center_parser')(*args, **kwargs)

def build_release_audio_quality_actions_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_quality_actions_parser')(*args, **kwargs)

def build_release_audio_quality_observatory_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_quality_observatory_parser')(*args, **kwargs)

def build_release_audio_regression_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_regression_parser')(*args, **kwargs)

def build_release_audio_regression_response_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_regression_response_parser')(*args, **kwargs)

def build_release_audio_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_review_parser')(*args, **kwargs)

def build_release_audio_timeline_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_timeline_parser')(*args, **kwargs)

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

def build_release_portfolio_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_audit_parser')(*args, **kwargs)

def build_release_portfolio_governance_attestation_accepted_evidence_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_attestation_accepted_evidence_parser')(*args, **kwargs)

def build_release_portfolio_governance_attestation_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_attestation_parser')(*args, **kwargs)

def build_release_portfolio_governance_attestation_portal_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_attestation_portal_parser')(*args, **kwargs)

def build_release_portfolio_governance_attestation_portal_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_attestation_portal_review_parser')(*args, **kwargs)

def build_release_portfolio_governance_attestation_registry_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_attestation_registry_parser')(*args, **kwargs)

def build_release_portfolio_governance_attestation_transparency_acknowledgement_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_attestation_transparency_acknowledgement_parser')(*args, **kwargs)

def build_release_portfolio_governance_attestation_transparency_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_attestation_transparency_parser')(*args, **kwargs)

def build_release_portfolio_governance_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_audit_parser')(*args, **kwargs)

def build_release_portfolio_governance_evidence_vault_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_evidence_vault_parser')(*args, **kwargs)

def build_release_portfolio_governance_final_board_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_final_board_parser')(*args, **kwargs)

def build_release_portfolio_governance_queue_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_queue_parser')(*args, **kwargs)

def build_release_portfolio_governance_reviewer_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_reviewer_pack_parser')(*args, **kwargs)

def build_release_portfolio_governance_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_release_portfolio_governance_signoff_parser')(*args, **kwargs)

def build_trust_operations_assurance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_assurance_parser')(*args, **kwargs)

def build_trust_operations_assurance_watch_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_assurance_watch_parser')(*args, **kwargs)

def build_trust_operations_assurance_watch_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_assurance_watch_signoff_parser')(*args, **kwargs)

def build_trust_operations_control_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_control_signoff_parser')(*args, **kwargs)

def build_trust_operations_controls_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_controls_parser')(*args, **kwargs)

def build_trust_operations_final_readiness_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_final_readiness_parser')(*args, **kwargs)

def build_trust_operations_hub_incidents_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_hub_incidents_parser')(*args, **kwargs)

def build_trust_operations_hub_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_hub_parser')(*args, **kwargs)

def build_trust_operations_hub_runbook_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_hub_runbook_parser')(*args, **kwargs)

def build_trust_operations_incident_knowledge_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_trust_operations_incident_knowledge_parser')(*args, **kwargs)

def build_unified_command_center_drift_response_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_drift_response_parser')(*args, **kwargs)

def build_unified_command_center_evidence_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_evidence_review_parser')(*args, **kwargs)

def build_unified_command_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_parser')(*args, **kwargs)

def build_unified_command_center_release_train_change_control_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_release_train_change_control_parser')(*args, **kwargs)

def build_unified_command_center_release_train_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_release_train_handoff_parser')(*args, **kwargs)

def build_unified_command_center_release_train_lifecycle_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_release_train_lifecycle_parser')(*args, **kwargs)

def build_unified_command_center_release_train_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_release_train_parser')(*args, **kwargs)

def build_unified_command_center_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_review_parser')(*args, **kwargs)

def build_unified_command_center_reviewer_decision_board_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_command_center_reviewer_decision_board_parser')(*args, **kwargs)

def build_unified_release_program_continuity_acceptance_change_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_acceptance_change_parser')(*args, **kwargs)

def build_unified_release_program_continuity_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_acceptance_parser')(*args, **kwargs)

def build_unified_release_program_continuity_command_center_acceptance_change_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_command_center_acceptance_change_parser')(*args, **kwargs)

def build_unified_release_program_continuity_command_center_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_command_center_acceptance_parser')(*args, **kwargs)

def build_unified_release_program_continuity_command_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_command_center_parser')(*args, **kwargs)

def build_unified_release_program_continuity_command_center_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_command_center_signoff_parser')(*args, **kwargs)

def build_unified_release_program_continuity_distribution_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_distribution_parser')(*args, **kwargs)

def build_unified_release_program_continuity_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_continuity_parser')(*args, **kwargs)

def build_unified_release_program_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_handoff_parser')(*args, **kwargs)

def build_unified_release_program_operations_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_operations_parser')(*args, **kwargs)

def build_unified_release_program_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_parser')(*args, **kwargs)

def build_unified_release_program_vault_operations_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_vault_operations_parser')(*args, **kwargs)

def build_unified_release_program_vault_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_unified_release_program_vault_parser')(*args, **kwargs)

def build_verify_audio_campaign_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_audio_campaign_archive_parser')(*args, **kwargs)

def build_verify_audio_campaign_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_audio_campaign_parser')(*args, **kwargs)

def build_verify_audio_campaign_remediation_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_audio_campaign_remediation_parser')(*args, **kwargs)

def build_verify_distribution_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_distribution_parser')(*args, **kwargs)

def build_verify_human_review_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('studio', 'build_verify_human_review_pack_parser')(*args, **kwargs)

def build_verify_maintenance_backup_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('maintenance', 'build_verify_maintenance_backup_parser')(*args, **kwargs)

def build_verify_public_trust_center_acceptance_board_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_acceptance_board_parser')(*args, **kwargs)

def build_verify_public_trust_center_acceptance_board_signoff_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_acceptance_board_signoff_archive_parser')(*args, **kwargs)

def build_verify_public_trust_center_anchor_registry_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_anchor_registry_parser')(*args, **kwargs)

def build_verify_public_trust_center_anchor_transparency_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_anchor_transparency_parser')(*args, **kwargs)

def build_verify_public_trust_center_distribution_kit_accepted_evidence_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_distribution_kit_accepted_evidence_parser')(*args, **kwargs)

def build_verify_public_trust_center_distribution_kit_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_distribution_kit_parser')(*args, **kwargs)

def build_verify_public_trust_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_parser')(*args, **kwargs)

def build_verify_public_trust_center_publication_mirror_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_publication_mirror_parser')(*args, **kwargs)

def build_verify_public_trust_center_publication_monitoring_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_publication_monitoring_parser')(*args, **kwargs)

def build_verify_public_trust_center_publication_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_public_trust_center_publication_parser')(*args, **kwargs)

def build_verify_release_audio_baseline_registry_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_baseline_registry_parser')(*args, **kwargs)

def build_verify_release_audio_certification_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_certification_parser')(*args, **kwargs)

def build_verify_release_audio_command_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_command_center_parser')(*args, **kwargs)

def build_verify_release_audio_quality_action_queue_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_quality_action_queue_parser')(*args, **kwargs)

def build_verify_release_audio_quality_action_queue_signoff_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_quality_action_queue_signoff_archive_parser')(*args, **kwargs)

def build_verify_release_audio_quality_observatory_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_quality_observatory_parser')(*args, **kwargs)

def build_verify_release_audio_regression_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_regression_parser')(*args, **kwargs)

def build_verify_release_audio_regression_response_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_regression_response_parser')(*args, **kwargs)

def build_verify_release_audio_timeline_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_timeline_parser')(*args, **kwargs)

def build_verify_release_operations_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_release_operations_archive_parser')(*args, **kwargs)

def build_verify_release_operations_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_release_operations_audit_parser')(*args, **kwargs)

def build_verify_release_operations_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_release_operations_parser')(*args, **kwargs)

def build_verify_release_operations_reviewer_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_release_operations_reviewer_pack_parser')(*args, **kwargs)

def build_verify_release_operations_runbook_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_release_operations_runbook_parser')(*args, **kwargs)

def build_verify_release_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_release_parser')(*args, **kwargs)

def build_verify_release_portfolio_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_audit_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_archive_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_accepted_evidence_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_accepted_evidence_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_portal_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_portal_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_portal_response_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_portal_response_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_portal_review_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_portal_review_pack_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_registry_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_registry_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_transparency_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_attestation_transparency_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_audit_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_evidence_vault_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_evidence_vault_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_final_board_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_final_board_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_parser')(*args, **kwargs)

def build_verify_release_portfolio_governance_reviewer_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_release_portfolio_governance_reviewer_pack_parser')(*args, **kwargs)

def build_verify_submission_evidence_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_submission_evidence_parser')(*args, **kwargs)

def build_verify_submission_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', 'build_verify_submission_parser')(*args, **kwargs)

def build_verify_trust_operations_assurance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_assurance_parser')(*args, **kwargs)

def build_verify_trust_operations_assurance_watch_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_assurance_watch_parser')(*args, **kwargs)

def build_verify_trust_operations_assurance_watch_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_assurance_watch_signoff_parser')(*args, **kwargs)

def build_verify_trust_operations_control_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_control_parser')(*args, **kwargs)

def build_verify_trust_operations_control_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_control_signoff_parser')(*args, **kwargs)

def build_verify_trust_operations_final_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_final_handoff_parser')(*args, **kwargs)

def build_verify_trust_operations_hub_incident_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_hub_incident_parser')(*args, **kwargs)

def build_verify_trust_operations_hub_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_hub_parser')(*args, **kwargs)

def build_verify_trust_operations_hub_runbook_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_hub_runbook_parser')(*args, **kwargs)

def build_verify_trust_operations_incident_knowledge_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_verify_trust_operations_incident_knowledge_parser')(*args, **kwargs)

def build_verify_unified_command_center_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_archive_parser')(*args, **kwargs)

def build_verify_unified_command_center_continuous_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_continuous_review_parser')(*args, **kwargs)

def build_verify_unified_command_center_drift_response_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_drift_response_parser')(*args, **kwargs)

def build_verify_unified_command_center_evidence_review_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_evidence_review_acceptance_parser')(*args, **kwargs)

def build_verify_unified_command_center_evidence_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_evidence_review_parser')(*args, **kwargs)

def build_verify_unified_command_center_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_handoff_parser')(*args, **kwargs)

def build_verify_unified_command_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_parser')(*args, **kwargs)

def build_verify_unified_command_center_release_train_change_control_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_change_control_parser')(*args, **kwargs)

def build_verify_unified_command_center_release_train_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_handoff_parser')(*args, **kwargs)

def build_verify_unified_command_center_release_train_lifecycle_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_lifecycle_parser')(*args, **kwargs)

def build_verify_unified_command_center_release_train_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_parser')(*args, **kwargs)

def build_verify_unified_command_center_reviewer_decision_board_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_reviewer_decision_board_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_acceptance_change_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_acceptance_change_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_acceptance_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_acceptance_change_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_command_center_acceptance_change_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_command_center_acceptance_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_command_center_handoff_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_command_center_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_command_center_signoff_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_distribution_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_distribution_parser')(*args, **kwargs)

def build_verify_unified_release_program_continuity_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_continuity_parser')(*args, **kwargs)

def build_verify_unified_release_program_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_handoff_parser')(*args, **kwargs)

def build_verify_unified_release_program_operations_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_operations_parser')(*args, **kwargs)

def build_verify_unified_release_program_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_release_program_parser')(*args, **kwargs)

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

def build_release_check_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MusicForge release verification checks.")
    parser.add_argument("--profile", default="full", choices=["full", "quick", "latest", "v7", "v8", "v9", "v10", "v11", "v12", "ga", "publish"], help="Release-check profile to run.")
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

def print_ga_readiness_report(report: dict[str, Any]) -> None:
    print("MusicForge GA readiness")
    print(f"status: {report.get('status')}")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
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

def _execute_ga_check(argv: list[str]) -> None:
    raw_args = ['ga-check', *argv]
    from song_agent.ga_readiness import build_ga_readiness_report, write_ga_readiness_report
    parser = build_ga_check_parser()
    args = parser.parse_args(raw_args[1:])
    report = build_ga_readiness_report(
        strict=args.strict,
        allow_dirty=args.allow_dirty,
        require_manual_acceptance=args.require_manual_acceptance,
        require_audio=args.require_audio,
        require_audio_campaign=bool(args.audio_campaign_id),
        audio_campaign_id=args.audio_campaign_id,
        audio_campaign_archive_zip_path=args.audio_campaign_archive,
        audio_campaign_archive_verification_report_path=args.audio_campaign_archive_verification_report,
        require_audio_campaign_remediation=args.require_audio_campaign_remediation,
        audio_campaign_remediation_zip_path=args.audio_campaign_remediation,
        audio_campaign_remediation_verification_report_path=args.audio_campaign_remediation_verification_report,
        require_release_audio_certification=args.require_release_audio_certification,
        release_audio_certification_zip_path=args.release_audio_timeline_certification or args.release_audio_certification,
        release_audio_certification_verification_report_path=args.release_audio_timeline_certification_verification_report or args.release_audio_certification_verification_report,
        require_release_audio_timeline=args.require_release_audio_timeline,
        release_audio_timeline_zip_path=args.release_audio_timeline,
        release_audio_timeline_verification_report_path=args.release_audio_timeline_verification_report,
        require_release_audio_regression_guard=args.require_release_audio_regression_guard,
        release_audio_regression_zip_path=args.release_audio_regression,
        release_audio_regression_verification_report_path=args.release_audio_regression_verification_report,
        release_audio_regression_baseline_timeline_path=args.release_audio_regression_baseline_timeline,
        release_audio_regression_baseline_timeline_verification_report_path=args.release_audio_regression_baseline_timeline_verification_report,
        release_audio_regression_baseline_certification_path=args.release_audio_regression_baseline_certification,
        release_audio_regression_baseline_certification_verification_report_path=args.release_audio_regression_baseline_certification_verification_report,
        release_audio_regression_current_timeline_path=args.release_audio_regression_current_timeline or args.release_audio_timeline,
        release_audio_regression_current_timeline_verification_report_path=args.release_audio_regression_current_timeline_verification_report or args.release_audio_timeline_verification_report,
        release_audio_regression_current_certification_path=args.release_audio_regression_current_certification or args.release_audio_timeline_certification or args.release_audio_certification,
        release_audio_regression_current_certification_verification_report_path=args.release_audio_regression_current_certification_verification_report or args.release_audio_timeline_certification_verification_report or args.release_audio_certification_verification_report,
        require_release_audio_baseline_governance=args.require_release_audio_baseline_governance,
        release_audio_baseline_registry_zip_path=args.release_audio_baseline_registry,
        release_audio_baseline_registry_verification_report_path=args.release_audio_baseline_registry_verification_report,
        require_release_audio_regression_response=args.require_release_audio_regression_response,
        release_audio_regression_response_zip_path=args.release_audio_regression_response,
        release_audio_regression_response_verification_report_path=args.release_audio_regression_response_verification_report,
        release_audio_regression_response_regression_zip_path=args.release_audio_regression,
        release_audio_regression_response_regression_verification_report_path=args.release_audio_regression_verification_report,
        release_audio_regression_response_baseline_timeline_path=args.release_audio_regression_baseline_timeline,
        release_audio_regression_response_baseline_timeline_verification_report_path=args.release_audio_regression_baseline_timeline_verification_report,
        release_audio_regression_response_baseline_certification_path=args.release_audio_regression_baseline_certification,
        release_audio_regression_response_baseline_certification_verification_report_path=args.release_audio_regression_baseline_certification_verification_report,
        release_audio_regression_response_current_timeline_path=args.release_audio_regression_current_timeline or args.release_audio_timeline,
        release_audio_regression_response_current_timeline_verification_report_path=args.release_audio_regression_current_timeline_verification_report or args.release_audio_timeline_verification_report,
        release_audio_regression_response_current_certification_path=args.release_audio_regression_current_certification or args.release_audio_timeline_certification or args.release_audio_certification,
        release_audio_regression_response_current_certification_verification_report_path=args.release_audio_regression_current_certification_verification_report or args.release_audio_timeline_certification_verification_report or args.release_audio_certification_verification_report,
        require_release_audio_quality_observatory=args.require_release_audio_quality_observatory,
        release_audio_quality_observatory_zip_path=args.release_audio_quality_observatory,
        release_audio_quality_observatory_verification_report_path=args.release_audio_quality_observatory_verification_report,
        release_audio_quality_observatory_evidence_root=args.release_audio_quality_observatory_evidence_root,
        require_no_critical_audio_quality_risk=args.require_no_critical_audio_quality_risk,
        require_release_audio_quality_action_queue=args.require_release_audio_quality_action_queue,
        release_audio_quality_action_queue_zip_path=args.release_audio_quality_action_queue,
        release_audio_quality_action_queue_verification_report_path=args.release_audio_quality_action_queue_verification_report,
        require_release_audio_quality_action_queue_signoff=args.require_release_audio_quality_action_queue_signoff,
        release_audio_quality_action_queue_signoff_archive_path=args.release_audio_quality_action_queue_signoff_archive,
        release_audio_quality_action_queue_signoff_verification_report_path=args.release_audio_quality_action_queue_signoff_verification_report,
        require_release_audio_command_center=args.require_release_audio_command_center,
        release_audio_command_center_zip_path=args.release_audio_command_center,
        release_audio_command_center_verification_report_path=args.release_audio_command_center_verification_report,
        require_unified_command_center=args.require_unified_command_center,
        unified_command_center_zip_path=args.unified_command_center,
        unified_command_center_verification_report_path=args.unified_command_center_verification_report,
        require_unified_command_center_archive=args.require_unified_command_center_archive,
        unified_command_center_archive_zip_path=args.unified_command_center_archive,
        unified_command_center_archive_verification_report_path=args.unified_command_center_archive_verification_report,
        require_unified_command_center_handoff=args.require_unified_command_center_handoff,
        unified_command_center_handoff_zip_path=args.unified_command_center_handoff,
        unified_command_center_handoff_verification_report_path=args.unified_command_center_handoff_verification_report,
        require_unified_command_center_continuous_review=args.require_unified_command_center_continuous_review,
        unified_command_center_continuous_review_zip_path=args.unified_command_center_continuous_review,
        unified_command_center_continuous_review_verification_report_path=args.unified_command_center_continuous_review_verification_report,
        require_unified_command_center_drift_response=args.require_unified_command_center_drift_response,
        unified_command_center_drift_response_zip_path=args.unified_command_center_drift_response,
        unified_command_center_drift_response_verification_report_path=args.unified_command_center_drift_response_verification_report,
        unified_command_center_drift_source_review_zip_path=args.unified_command_center_drift_source_review,
        unified_command_center_drift_source_review_verification_report_path=args.unified_command_center_drift_source_review_verification_report,
        unified_command_center_drift_recheck_review_zip_path=args.unified_command_center_drift_recheck_review,
        unified_command_center_drift_recheck_review_verification_report_path=args.unified_command_center_drift_recheck_review_verification_report,
        unified_command_center_drift_change_request_binding_report_path=args.unified_command_center_drift_change_request_binding_report,
        require_unified_command_center_evidence_review=args.require_unified_command_center_evidence_review,
        unified_command_center_evidence_review_zip_path=args.unified_command_center_evidence_review,
        unified_command_center_evidence_review_verification_report_path=args.unified_command_center_evidence_review_verification_report,
        require_unified_command_center_evidence_review_accepted=args.require_unified_command_center_evidence_review_accepted,
        unified_command_center_evidence_review_acceptance_zip_path=args.unified_command_center_evidence_review_acceptance,
        unified_command_center_evidence_review_acceptance_verification_report_path=args.unified_command_center_evidence_review_acceptance_verification_report,
        unified_command_center_evidence_review_acceptance_response_verification_report_path=args.unified_command_center_evidence_review_acceptance_response_verification_report,
        require_unified_command_center_reviewer_decision_board=args.require_unified_command_center_reviewer_decision_board,
        unified_command_center_reviewer_decision_board_zip_path=args.unified_command_center_reviewer_decision_board,
        unified_command_center_reviewer_decision_board_verification_report_path=args.unified_command_center_reviewer_decision_board_verification_report,
        require_unified_command_center_reviewer_decision_board_signed=args.require_unified_command_center_reviewer_decision_board_signed,
        require_unified_command_center_reviewer_decision_board_quorum=args.require_unified_command_center_reviewer_decision_board_quorum,
        unified_command_center_reviewer_decision_board_evidence_review_zip_path=args.unified_command_center_reviewer_decision_board_evidence_review,
        unified_command_center_reviewer_decision_board_evidence_review_verification_report_path=args.unified_command_center_reviewer_decision_board_evidence_review_verification_report,
        unified_command_center_reviewer_decision_board_accepted_evidence_zip_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence,
        unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence_verification_report,
        unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report,
        require_unified_release_program_handoff=args.require_unified_release_program_handoff,
        unified_release_program_handoff_zip_path=args.unified_release_program_handoff,
        unified_release_program_handoff_verification_report_path=args.unified_release_program_handoff_verification_report,
        unified_release_program_handoff_external_evidence_manifest_path=args.unified_release_program_handoff_external_evidence_manifest,
        unified_release_program_handoff_signoff_binding_path=args.unified_release_program_handoff_signoff_binding,
        require_unified_release_program_vault=args.require_unified_release_program_vault,
        unified_release_program_vault_zip_path=args.unified_release_program_vault,
        unified_release_program_vault_verification_report_path=args.unified_release_program_vault_verification_report,
        unified_release_program_vault_anchor_path=args.unified_release_program_vault_anchor,
        require_unified_release_program_vault_operations=args.require_unified_release_program_vault_operations,
        unified_release_program_vault_operations_zip_path=args.unified_release_program_vault_operations,
        unified_release_program_vault_operations_verification_report_path=args.unified_release_program_vault_operations_verification_report,
        unified_release_program_vault_operations_signoff_binding_path=args.unified_release_program_vault_operations_signoff_binding,
        require_unified_release_program_continuity=args.require_unified_release_program_continuity,
        unified_release_program_continuity_zip_path=args.unified_release_program_continuity,
        unified_release_program_continuity_verification_report_path=args.unified_release_program_continuity_verification_report,
        unified_release_program_continuity_signoff_binding_path=args.unified_release_program_continuity_signoff_binding,
        require_unified_release_program_continuity_kit=args.require_unified_release_program_continuity_kit,
        unified_release_program_continuity_kit_zip_path=args.unified_release_program_continuity_kit,
        unified_release_program_continuity_kit_verification_report_path=args.unified_release_program_continuity_kit_verification_report,
        unified_release_program_continuity_kit_receiver_receipt_path=args.unified_release_program_continuity_kit_receiver_receipt,
        require_unified_release_program_continuity_acceptance=args.require_unified_release_program_continuity_acceptance,
        unified_release_program_continuity_acceptance_zip_path=args.unified_release_program_continuity_acceptance,
        unified_release_program_continuity_acceptance_verification_report_path=args.unified_release_program_continuity_acceptance_verification_report,
        unified_release_program_continuity_acceptance_signoff_binding_path=args.unified_release_program_continuity_acceptance_signoff_binding,
        require_unified_release_program_continuity_command_center=args.require_unified_release_program_continuity_command_center,
        unified_release_program_continuity_command_center_zip_path=args.unified_release_program_continuity_command_center,
        unified_release_program_continuity_command_center_verification_report_path=args.unified_release_program_continuity_command_center_verification_report,
        unified_release_program_continuity_command_center_external_evidence_manifest_path=args.unified_release_program_continuity_command_center_external_evidence_manifest,
        require_unified_release_program_continuity_command_center_signoff=args.require_unified_release_program_continuity_command_center_signoff,
        unified_release_program_continuity_command_center_signoff_archive_path=args.unified_release_program_continuity_command_center_signoff_archive,
        unified_release_program_continuity_command_center_signoff_verification_report_path=args.unified_release_program_continuity_command_center_signoff_verification_report,
        unified_release_program_continuity_command_center_signoff_binding_path=args.unified_release_program_continuity_command_center_signoff_binding,
        require_unified_release_program_continuity_command_center_acceptance=args.require_unified_release_program_continuity_command_center_acceptance,
        unified_release_program_continuity_command_center_acceptance_archive_path=args.unified_release_program_continuity_command_center_acceptance_archive,
        unified_release_program_continuity_command_center_acceptance_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_verification_report,
        unified_release_program_continuity_command_center_acceptance_signoff_binding_path=args.unified_release_program_continuity_command_center_acceptance_signoff_binding,
        unified_release_program_continuity_command_center_acceptance_review_pack_path=args.unified_release_program_continuity_command_center_acceptance_review_pack,
        unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_review_pack_verification_report,
        unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir=args.unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir,
        unified_release_program_continuity_command_center_acceptance_response_proof_dir=args.unified_release_program_continuity_command_center_acceptance_response_proof_dir,
        require_unified_release_program_continuity_command_center_acceptance_change_control=args.require_unified_release_program_continuity_command_center_acceptance_change_control,
        unified_release_program_continuity_command_center_acceptance_change_archive_path=args.unified_release_program_continuity_command_center_acceptance_change_archive,
        unified_release_program_continuity_command_center_acceptance_change_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_change_verification_report,
        unified_release_program_continuity_command_center_acceptance_previous_root=args.unified_release_program_continuity_command_center_acceptance_previous_root,
        unified_release_program_continuity_command_center_final_handoff_path=args.unified_release_program_continuity_command_center_final_handoff,
        unified_release_program_continuity_command_center_final_handoff_verification_report_path=args.unified_release_program_continuity_command_center_final_handoff_verification_report,
        unified_release_zip_path=args.unified_release_zip,
        unified_release_verification_report_path=args.unified_release_verification_report,
        unified_distribution_zip_paths=args.unified_distribution_zip,
        unified_distribution_verification_report_paths=args.unified_distribution_verification_report,
        unified_submission_zip_paths=args.unified_submission_zip,
        unified_submission_verification_report_paths=args.unified_submission_verification_report,
        unified_release_operations_zip_path=args.unified_release_operations_zip,
        unified_release_operations_verification_report_path=args.unified_release_operations_verification_report,
        unified_trust_operations_hub_zip_path=args.unified_trust_operations_hub,
        unified_trust_operations_hub_verification_report_path=args.unified_trust_operations_hub_verification_report,
        unified_public_trust_center_zip_path=args.unified_public_trust_center,
        unified_public_trust_center_verification_report_path=args.unified_public_trust_center_verification_report,
        unified_maintenance_backup_zip_path=args.unified_maintenance_backup,
        unified_maintenance_backup_verification_report_path=args.unified_maintenance_backup_verification_report,
        require_final_readiness=args.require_final_readiness,
        final_handoff_verification_report_path=args.final_handoff_verification_report,
        release_check_latest_report_path=args.release_check_latest_report,
        release_check_ga_report_path=args.release_check_ga_report,
        run_release_checks=args.run_release_checks,
        skip_tests=args.skip_tests,
    )
    if args.report_out is not None:
        write_ga_readiness_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_ga_readiness_report(report)
    if report.get("status") == "blocked":
        raise SystemExit(1)
    return


def handle_ga_check(argv: list[str]) -> None:
    _execute_ga_check(argv)

def _execute_verify_ga_readiness_report(argv: list[str]) -> None:
    raw_args = ['verify-ga-readiness-report', *argv]
    from song_agent.ga_readiness_verifier import verify_ga_readiness_report, write_ga_readiness_verification_report
    parser = build_verify_ga_readiness_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_ga_readiness_report(
        args.report_path,
        strict=args.strict,
        require_ready=args.require_ready,
        require_manual_acceptance=args.require_manual_acceptance,
        require_audio_campaign=args.require_audio_campaign,
        require_audio_campaign_remediation=args.require_audio_campaign_remediation,
        require_release_audio_certification=args.require_release_audio_certification,
        require_release_audio_timeline=args.require_release_audio_timeline,
        require_release_audio_regression_guard=args.require_release_audio_regression_guard,
        require_final_readiness=args.require_final_readiness,
        manual_acceptance_report_path=args.manual_acceptance_report,
        audio_campaign_archive_path=args.audio_campaign_archive,
        audio_campaign_archive_verification_report_path=args.audio_campaign_archive_verification_report,
        audio_campaign_remediation_path=args.audio_campaign_remediation,
        audio_campaign_remediation_verification_report_path=args.audio_campaign_remediation_verification_report,
        release_audio_certification_path=args.release_audio_timeline_certification or args.release_audio_certification,
        release_audio_certification_verification_report_path=args.release_audio_timeline_certification_verification_report or args.release_audio_certification_verification_report,
        release_audio_timeline_path=args.release_audio_timeline,
        release_audio_timeline_verification_report_path=args.release_audio_timeline_verification_report,
        release_audio_regression_path=args.release_audio_regression,
        release_audio_regression_verification_report_path=args.release_audio_regression_verification_report,
        release_audio_regression_baseline_timeline_path=args.release_audio_regression_baseline_timeline,
        release_audio_regression_baseline_timeline_verification_report_path=args.release_audio_regression_baseline_timeline_verification_report,
        release_audio_regression_baseline_certification_path=args.release_audio_regression_baseline_certification,
        release_audio_regression_baseline_certification_verification_report_path=args.release_audio_regression_baseline_certification_verification_report,
        release_audio_regression_current_timeline_path=args.release_audio_regression_current_timeline or args.release_audio_timeline,
        release_audio_regression_current_timeline_verification_report_path=args.release_audio_regression_current_timeline_verification_report or args.release_audio_timeline_verification_report,
        release_audio_regression_current_certification_path=args.release_audio_regression_current_certification or args.release_audio_timeline_certification or args.release_audio_certification,
        release_audio_regression_current_certification_verification_report_path=args.release_audio_regression_current_certification_verification_report or args.release_audio_timeline_certification_verification_report or args.release_audio_certification_verification_report,
        require_release_audio_baseline_governance=args.require_release_audio_baseline_governance,
        release_audio_baseline_registry_path=args.release_audio_baseline_registry,
        release_audio_baseline_registry_verification_report_path=args.release_audio_baseline_registry_verification_report,
        require_release_audio_regression_response=args.require_release_audio_regression_response,
        release_audio_regression_response_path=args.release_audio_regression_response,
        release_audio_regression_response_verification_report_path=args.release_audio_regression_response_verification_report,
        require_release_audio_quality_observatory=args.require_release_audio_quality_observatory,
        release_audio_quality_observatory_path=args.release_audio_quality_observatory,
        release_audio_quality_observatory_verification_report_path=args.release_audio_quality_observatory_verification_report,
        release_audio_quality_observatory_evidence_root=args.release_audio_quality_observatory_evidence_root,
        require_no_critical_audio_quality_risk=args.require_no_critical_audio_quality_risk,
        require_release_audio_quality_action_queue=args.require_release_audio_quality_action_queue,
        release_audio_quality_action_queue_path=args.release_audio_quality_action_queue,
        release_audio_quality_action_queue_verification_report_path=args.release_audio_quality_action_queue_verification_report,
        require_release_audio_quality_action_queue_signoff=args.require_release_audio_quality_action_queue_signoff,
        release_audio_quality_action_queue_signoff_archive_path=args.release_audio_quality_action_queue_signoff_archive,
        release_audio_quality_action_queue_signoff_verification_report_path=args.release_audio_quality_action_queue_signoff_verification_report,
        require_release_audio_command_center=args.require_release_audio_command_center,
        release_audio_command_center_path=args.release_audio_command_center,
        release_audio_command_center_verification_report_path=args.release_audio_command_center_verification_report,
        require_unified_command_center=args.require_unified_command_center,
        unified_command_center_path=args.unified_command_center,
        unified_command_center_verification_report_path=args.unified_command_center_verification_report,
        require_unified_command_center_archive=args.require_unified_command_center_archive,
        unified_command_center_archive_path=args.unified_command_center_archive,
        unified_command_center_archive_verification_report_path=args.unified_command_center_archive_verification_report,
        require_unified_command_center_handoff=args.require_unified_command_center_handoff,
        unified_command_center_handoff_path=args.unified_command_center_handoff,
        unified_command_center_handoff_verification_report_path=args.unified_command_center_handoff_verification_report,
        require_unified_command_center_continuous_review=args.require_unified_command_center_continuous_review,
        unified_command_center_continuous_review_path=args.unified_command_center_continuous_review,
        unified_command_center_continuous_review_verification_report_path=args.unified_command_center_continuous_review_verification_report,
        require_unified_command_center_drift_response=args.require_unified_command_center_drift_response,
        unified_command_center_drift_response_path=args.unified_command_center_drift_response,
        unified_command_center_drift_response_verification_report_path=args.unified_command_center_drift_response_verification_report,
        unified_command_center_drift_source_review_path=args.unified_command_center_drift_source_review,
        unified_command_center_drift_source_review_verification_report_path=args.unified_command_center_drift_source_review_verification_report,
        unified_command_center_drift_recheck_review_path=args.unified_command_center_drift_recheck_review,
        unified_command_center_drift_recheck_review_verification_report_path=args.unified_command_center_drift_recheck_review_verification_report,
        unified_command_center_drift_change_request_binding_report_path=args.unified_command_center_drift_change_request_binding_report,
        require_unified_command_center_evidence_review=args.require_unified_command_center_evidence_review,
        unified_command_center_evidence_review_path=args.unified_command_center_evidence_review,
        unified_command_center_evidence_review_verification_report_path=args.unified_command_center_evidence_review_verification_report,
        require_unified_command_center_evidence_review_accepted=args.require_unified_command_center_evidence_review_accepted,
        unified_command_center_evidence_review_acceptance_path=args.unified_command_center_evidence_review_acceptance,
        unified_command_center_evidence_review_acceptance_verification_report_path=args.unified_command_center_evidence_review_acceptance_verification_report,
        unified_command_center_evidence_review_acceptance_response_verification_report_path=args.unified_command_center_evidence_review_acceptance_response_verification_report,
        require_unified_command_center_reviewer_decision_board=args.require_unified_command_center_reviewer_decision_board,
        unified_command_center_reviewer_decision_board_path=args.unified_command_center_reviewer_decision_board,
        unified_command_center_reviewer_decision_board_verification_report_path=args.unified_command_center_reviewer_decision_board_verification_report,
        require_unified_command_center_reviewer_decision_board_signed=args.require_unified_command_center_reviewer_decision_board_signed,
        require_unified_command_center_reviewer_decision_board_quorum=args.require_unified_command_center_reviewer_decision_board_quorum,
        unified_command_center_reviewer_decision_board_evidence_review_path=args.unified_command_center_reviewer_decision_board_evidence_review,
        unified_command_center_reviewer_decision_board_evidence_review_verification_report_path=args.unified_command_center_reviewer_decision_board_evidence_review_verification_report,
        unified_command_center_reviewer_decision_board_accepted_evidence_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence,
        unified_command_center_reviewer_decision_board_accepted_evidence_verification_report_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence_verification_report,
        unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report_paths=args.unified_command_center_reviewer_decision_board_accepted_evidence_response_verification_report,
        require_unified_release_program_handoff=args.require_unified_release_program_handoff,
        unified_release_program_handoff_path=args.unified_release_program_handoff,
        unified_release_program_handoff_verification_report_path=args.unified_release_program_handoff_verification_report,
        unified_release_program_handoff_external_evidence_manifest_path=args.unified_release_program_handoff_external_evidence_manifest,
        unified_release_program_handoff_signoff_binding_path=args.unified_release_program_handoff_signoff_binding,
        require_unified_release_program_vault=args.require_unified_release_program_vault,
        unified_release_program_vault_path=args.unified_release_program_vault,
        unified_release_program_vault_verification_report_path=args.unified_release_program_vault_verification_report,
        unified_release_program_vault_anchor_path=args.unified_release_program_vault_anchor,
        require_unified_release_program_vault_operations=args.require_unified_release_program_vault_operations,
        unified_release_program_vault_operations_path=args.unified_release_program_vault_operations,
        unified_release_program_vault_operations_verification_report_path=args.unified_release_program_vault_operations_verification_report,
        unified_release_program_vault_operations_signoff_binding_path=args.unified_release_program_vault_operations_signoff_binding,
        require_unified_release_program_continuity=args.require_unified_release_program_continuity,
        unified_release_program_continuity_path=args.unified_release_program_continuity,
        unified_release_program_continuity_verification_report_path=args.unified_release_program_continuity_verification_report,
        unified_release_program_continuity_signoff_binding_path=args.unified_release_program_continuity_signoff_binding,
        require_unified_release_program_continuity_kit=args.require_unified_release_program_continuity_kit,
        unified_release_program_continuity_kit_path=args.unified_release_program_continuity_kit,
        unified_release_program_continuity_kit_verification_report_path=args.unified_release_program_continuity_kit_verification_report,
        unified_release_program_continuity_kit_receiver_receipt_path=args.unified_release_program_continuity_kit_receiver_receipt,
        require_unified_release_program_continuity_acceptance=args.require_unified_release_program_continuity_acceptance,
        unified_release_program_continuity_acceptance_path=args.unified_release_program_continuity_acceptance,
        unified_release_program_continuity_acceptance_verification_report_path=args.unified_release_program_continuity_acceptance_verification_report,
        unified_release_program_continuity_acceptance_signoff_binding_path=args.unified_release_program_continuity_acceptance_signoff_binding,
        require_unified_release_program_continuity_command_center=args.require_unified_release_program_continuity_command_center,
        unified_release_program_continuity_command_center_path=args.unified_release_program_continuity_command_center,
        unified_release_program_continuity_command_center_verification_report_path=args.unified_release_program_continuity_command_center_verification_report,
        unified_release_program_continuity_command_center_external_evidence_manifest_path=args.unified_release_program_continuity_command_center_external_evidence_manifest,
        require_unified_release_program_continuity_command_center_signoff=args.require_unified_release_program_continuity_command_center_signoff,
        unified_release_program_continuity_command_center_signoff_archive_path=args.unified_release_program_continuity_command_center_signoff_archive,
        unified_release_program_continuity_command_center_signoff_verification_report_path=args.unified_release_program_continuity_command_center_signoff_verification_report,
        unified_release_program_continuity_command_center_signoff_binding_path=args.unified_release_program_continuity_command_center_signoff_binding,
        require_unified_release_program_continuity_command_center_acceptance=args.require_unified_release_program_continuity_command_center_acceptance,
        unified_release_program_continuity_command_center_acceptance_path=args.unified_release_program_continuity_command_center_acceptance_archive,
        unified_release_program_continuity_command_center_acceptance_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_verification_report,
        unified_release_program_continuity_command_center_acceptance_signoff_binding_path=args.unified_release_program_continuity_command_center_acceptance_signoff_binding,
        unified_release_program_continuity_command_center_acceptance_review_pack_path=args.unified_release_program_continuity_command_center_acceptance_review_pack,
        unified_release_program_continuity_command_center_acceptance_review_pack_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_review_pack_verification_report,
        unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir=args.unified_release_program_continuity_command_center_acceptance_accepted_evidence_dir,
        unified_release_program_continuity_command_center_acceptance_response_proof_dir=args.unified_release_program_continuity_command_center_acceptance_response_proof_dir,
        require_unified_release_program_continuity_command_center_acceptance_change_control=args.require_unified_release_program_continuity_command_center_acceptance_change_control,
        unified_release_program_continuity_command_center_acceptance_change_path=args.unified_release_program_continuity_command_center_acceptance_change_archive,
        unified_release_program_continuity_command_center_acceptance_change_verification_report_path=args.unified_release_program_continuity_command_center_acceptance_change_verification_report,
        unified_release_program_continuity_command_center_acceptance_previous_root=args.unified_release_program_continuity_command_center_acceptance_previous_root,
        unified_release_program_continuity_command_center_final_handoff_path=args.unified_release_program_continuity_command_center_final_handoff,
        unified_release_program_continuity_command_center_final_handoff_verification_report_path=args.unified_release_program_continuity_command_center_final_handoff_verification_report,
        unified_release_path=args.unified_release_zip,
        unified_release_verification_report_path=args.unified_release_verification_report,
        unified_distribution_paths=args.unified_distribution_zip,
        unified_distribution_verification_report_paths=args.unified_distribution_verification_report,
        unified_submission_paths=args.unified_submission_zip,
        unified_submission_verification_report_paths=args.unified_submission_verification_report,
        unified_release_operations_path=args.unified_release_operations_zip,
        unified_release_operations_verification_report_path=args.unified_release_operations_verification_report,
        unified_trust_operations_hub_path=args.unified_trust_operations_hub,
        unified_trust_operations_hub_verification_report_path=args.unified_trust_operations_hub_verification_report,
        unified_public_trust_center_path=args.unified_public_trust_center,
        unified_public_trust_center_verification_report_path=args.unified_public_trust_center_verification_report,
        unified_maintenance_backup_path=args.unified_maintenance_backup,
        unified_maintenance_backup_verification_report_path=args.unified_maintenance_backup_verification_report,
        final_handoff_package_path=args.final_handoff_package,
        final_handoff_verification_report_path=args.final_handoff_verification_report,
        release_check_latest_report_path=args.release_check_latest_report,
        release_check_ga_report_path=args.release_check_ga_report,
    )
    if args.report_out is not None:
        write_ga_readiness_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge GA readiness verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    if report.get("status") == "failed":
        raise SystemExit(1)
    return


def handle_verify_ga_readiness_report(argv: list[str]) -> None:
    _execute_verify_ga_readiness_report(argv)

def _execute_release_check(argv: list[str]) -> None:
    raw_args = ['release-check', *argv]
    from song_agent.release_check_matrix import release_check_definitions_as_dicts, select_check_definitions
    from song_agent.release_check_runner import print_release_check_report, run_release_check_matrix, write_json_report, write_timing_report
    parser = build_release_check_parser()
    args = parser.parse_args(raw_args[1:])
    selected = select_check_definitions(
        profile=args.profile,
        groups=args.group,
        since=args.since,
        only=args.only,
        run_tests=not args.skip_tests,
    )
    if args.list:
        rows = release_check_definitions_as_dicts(selected)
        if args.json:
            print(json.dumps({"checks": rows}, ensure_ascii=False, indent=2))
        else:
            for item in rows:
                print(f"{item['check_id']}\t{item['group']}\t{item.get('version') or '-'}\t{item['name']}")
        return
    def _progress(definition: Any) -> None:
        print(f"[release-check] running {definition.check_id} ...", file=sys.stderr, flush=True)
    report = run_release_check_matrix(
        profile=args.profile,
        groups=args.group,
        since=args.since,
        only=args.only,
        run_tests=not args.skip_tests,
        fail_fast=args.fail_fast,
        timeout_seconds=args.timeout_seconds,
        progress=None if args.json else _progress,
    )
    if args.report_out is not None:
        write_json_report(report, args.report_out)
    if args.timing_out is not None:
        write_timing_report(report, args.timing_out)
    if args.json:
        print(json.dumps(report.to_json_report(), ensure_ascii=False, indent=2))
    else:
        print_release_check_report(report)
    if not report.ok:
        raise SystemExit(1)
    return


def handle_release_check(argv: list[str]) -> None:
    _execute_release_check(argv)


SPECS = (
    CommandSpec(name='ga-check', parser=build_acceptance_analytics_parser, handler=handle_ga_check, help='Ga Check', group='release_check'),
    CommandSpec(name='verify-ga-readiness-report', parser=build_acceptance_analytics_parser, handler=handle_verify_ga_readiness_report, help='Verify Ga Readiness Report', group='release_check'),
    CommandSpec(name='release-check', parser=build_acceptance_analytics_parser, handler=handle_release_check, help='Release Check', group='release_check'),
)
