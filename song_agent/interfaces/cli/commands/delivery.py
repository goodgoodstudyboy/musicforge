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

def _build_public_trust_center_publication_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_publication_store')(*args, **kwargs)

def _build_public_trust_center_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_store')(*args, **kwargs)

def _build_release_portfolio_governance_attestation_portal_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_release_portfolio_governance_attestation_portal_store')(*args, **kwargs)

def _trust_operations_assurance_source_payload(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_trust_operations_assurance_source_payload')(*args, **kwargs)

def _trust_operations_assurance_watch_source_payload(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_trust_operations_assurance_watch_source_payload')(*args, **kwargs)

def _trust_operations_final_readiness_source_payload(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_trust_operations_final_readiness_source_payload')(*args, **kwargs)

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

def build_public_trust_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_parser')(*args, **kwargs)

def build_public_trust_center_publication_monitor_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_publication_monitor_parser')(*args, **kwargs)

def build_public_trust_center_publication_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_publication_parser')(*args, **kwargs)

def build_release_audio_review_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_release_audio_review_parser')(*args, **kwargs)

def build_release_check_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('release_check', 'build_release_check_parser')(*args, **kwargs)

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

def build_verify_audio_campaign_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_audio_campaign_archive_parser')(*args, **kwargs)

def build_verify_audio_campaign_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_audio_campaign_parser')(*args, **kwargs)

def build_verify_audio_campaign_remediation_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_audio_campaign_remediation_parser')(*args, **kwargs)

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

def build_verify_release_audio_certification_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_certification_parser')(*args, **kwargs)

def build_verify_release_audio_regression_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_regression_parser')(*args, **kwargs)

def build_verify_release_audio_timeline_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', 'build_verify_release_audio_timeline_parser')(*args, **kwargs)

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

def build_verify_unified_command_center_release_train_change_control_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_change_control_parser')(*args, **kwargs)

def build_verify_unified_command_center_release_train_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_handoff_parser')(*args, **kwargs)

def build_verify_unified_command_center_release_train_lifecycle_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_lifecycle_parser')(*args, **kwargs)

def build_verify_unified_command_center_release_train_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('program', 'build_verify_unified_command_center_release_train_parser')(*args, **kwargs)

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

def _release_train_handoff_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "external_evidence_manifest": getattr(args, "external_evidence_manifest", None),
        "train_archive": getattr(args, "train_archive", None),
        "train_archive_verification_report": getattr(args, "train_archive_verification_report", None),
        "train_signoff_binding": getattr(args, "train_signoff_binding", None),
        "change_control_zip": getattr(args, "change_control_zip", None),
        "change_control_verification_report": getattr(args, "change_control_verification_report", None),
        "reset_proofs": [path for path in getattr(args, "reset_proof", []) if path],
        "lifecycle_zip": getattr(args, "lifecycle_zip", None),
        "lifecycle_verification_report": getattr(args, "lifecycle_verification_report", None),
    }

def print_release_operations_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations")
    print(f"release: {result.get('release_id') or report.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or report.get('status') or '-'}")
    print(f"stage: {summary.get('current_stage') or report.get('current_stage') or '-'} -> {report.get('next_stage') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")
    board_summary = result.get("acceptance_board_summary") if isinstance(result.get("acceptance_board_summary"), dict) else {}
    board_verification = result.get("acceptance_board_verification") if isinstance(result.get("acceptance_board_verification"), dict) else {}
    if board_summary:
        print(f"acceptance board: {board_summary.get('readiness') or '-'} / accepted={board_summary.get('accepted_count', 0)}")
    if board_verification:
        print(f"acceptance board verify: {board_verification.get('status')}")
    signoff = result.get("acceptance_board_signoff") if isinstance(result.get("acceptance_board_signoff"), dict) else {}
    archive_verification = result.get("acceptance_board_signoff_archive_verification") if isinstance(result.get("acceptance_board_signoff_archive_verification"), dict) else {}
    if signoff:
        print(f"acceptance board signoff: {signoff.get('status')}")
    if result.get("acceptance_board_signoff_archive_zip"):
        print(f"acceptance board signoff archive zip: {(result.get('acceptance_board_signoff_archive_zip') or {}).get('sha256')}")
    if archive_verification:
        print(f"acceptance board signoff archive verify: {archive_verification.get('status')}")

def print_release_operations_runbook_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    print("MusicForge release-operations-runbook")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"runbook: {summary.get('runbook_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"safe: {summary.get('safe_count', 0)}")
    print(f"manual_required: {summary.get('manual_required_count', 0)}")
    print(f"failed: {summary.get('failed_count', 0)}")
    if manifest:
        print(f"export: {'stale' if manifest.get('stale') else 'current'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_operations_signoff_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    gate = result.get("gate") if isinstance(result.get("gate"), dict) else {}
    print("MusicForge release-operations-signoff")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"stale: {summary.get('stale', False)}")
    print(f"integrity: {summary.get('integrity_ok', False)}")
    if gate:
        print(f"gate: {gate.get('status')} signable={gate.get('signable')}")

def print_release_operations_archive_result(result: dict[str, Any]) -> None:
    manifest = result.get("manifest") if isinstance(result.get("manifest"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-archive")
    print(f"release: {result.get('release_id') or manifest.get('release_id') or '-'}")
    if manifest:
        print(f"archive: {manifest.get('summary', {}).get('status') if isinstance(manifest.get('summary'), dict) else '-'}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_operations_audit_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-audit")
    print(f"release: {result.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"entries: {summary.get('entry_count', 0)}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def print_release_operations_reviewer_pack_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    verification = result.get("verification_summary") if isinstance(result.get("verification_summary"), dict) else {}
    print("MusicForge release-operations-reviewer-pack")
    print(f"release: {result.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or '-'}")
    print(f"readiness: {summary.get('readiness') or '-'}")
    print(f"blockers: {summary.get('blocker_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    if result.get("zip"):
        print(f"zip: {(result.get('zip') or {}).get('filename')}")
    if verification:
        print(f"verify: {verification.get('status')}")

def _execute_verify_unified_command_center_release_train_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-package', *argv]
    from song_agent.unified_command_center_release_train_verifier import (
        unified_command_center_release_train_verification_exit_code,
        verify_unified_command_center_release_train_package,
        write_unified_command_center_release_train_verification_report,
    )
    parser = build_verify_unified_command_center_release_train_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_package(
        args.zip_path,
        strict=args.strict,
        require_go=args.require_go,
        require_signed=args.require_signed,
        external_evidence_manifest_path=args.external_evidence_manifest,
        signoff_binding_path=args.signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_verification_exit_code(report))


def handle_verify_unified_command_center_release_train_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_package(argv)

def _execute_verify_unified_command_center_release_train_change_control_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-change-control-package', *argv]
    from song_agent.unified_command_center_release_train_change_control_verifier import (
        unified_command_center_release_train_change_control_verification_exit_code,
        verify_unified_command_center_release_train_change_control_package,
        write_unified_command_center_release_train_change_control_verification_report,
    )
    parser = build_verify_unified_command_center_release_train_change_control_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_change_control_package(
        args.zip_path,
        strict=args.strict,
        require_reset_applied=args.require_reset_applied,
        require_current_train=args.require_current_train,
        train_archive_path=args.train_archive,
        train_archive_verification_report_path=args.train_archive_verification_report,
        train_signoff_binding_path=args.train_signoff_binding,
        external_evidence_manifest_path=args.external_evidence_manifest,
        reset_proof_path=args.reset_proof,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_change_control_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train Change Control verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_change_control_verification_exit_code(report))


def handle_verify_unified_command_center_release_train_change_control_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_change_control_package(argv)

def _execute_verify_unified_command_center_release_train_lifecycle_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-lifecycle-package', *argv]
    from song_agent.unified_command_center_release_train_lifecycle_verifier import (
        unified_command_center_release_train_lifecycle_verification_exit_code,
        verify_unified_command_center_release_train_lifecycle_package,
        write_unified_command_center_release_train_lifecycle_verification_report,
    )
    parser = build_verify_unified_command_center_release_train_lifecycle_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_lifecycle_package(
        args.zip_path,
        strict=args.strict,
        require_current_train=args.require_current_train,
        require_change_control=args.require_change_control,
        train_archive_path=args.train_archive,
        train_archive_verification_report_path=args.train_archive_verification_report,
        train_signoff_binding_path=args.train_signoff_binding,
        external_evidence_manifest_path=args.external_evidence_manifest,
        change_control_zip_path=args.change_control_zip,
        change_control_verification_report_path=args.change_control_verification_report,
        reset_proof_paths=args.reset_proof,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_lifecycle_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train Lifecycle verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_lifecycle_verification_exit_code(report))


def handle_verify_unified_command_center_release_train_lifecycle_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_lifecycle_package(argv)

def _execute_verify_unified_command_center_release_train_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-release-train-handoff-package', *argv]
    from song_agent.unified_command_center_release_train_handoff_verifier import (
        unified_command_center_release_train_handoff_verification_exit_code,
        verify_unified_command_center_release_train_handoff_package,
        write_unified_command_center_release_train_handoff_verification_report,
    )
    parser = build_verify_unified_command_center_release_train_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_release_train_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_lifecycle=args.require_lifecycle,
        require_signed=args.require_signed,
        require_accepted=args.require_accepted,
        external_evidence_manifest_path=args.external_evidence_manifest,
        train_archive_path=args.train_archive,
        train_archive_verification_report_path=args.train_archive_verification_report,
        train_signoff_binding_path=args.train_signoff_binding,
        change_control_zip_path=args.change_control_zip,
        change_control_verification_report_path=args.change_control_verification_report,
        reset_proof_paths=args.reset_proof,
        lifecycle_zip_path=args.lifecycle_zip,
        lifecycle_verification_report_path=args.lifecycle_verification_report,
        handoff_signoff_binding_path=args.handoff_signoff_binding,
        accepted_evidence_dir=args.accepted_evidence_dir,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_release_train_handoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Release Train Handoff verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_release_train_handoff_verification_exit_code(report))


def handle_verify_unified_command_center_release_train_handoff_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_release_train_handoff_package(argv)

def _execute_verify_unified_release_program_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-package', *argv]
    from song_agent.unified_release_program_verifier import (
        unified_release_program_verification_exit_code,
        verify_unified_release_program_package,
        write_unified_release_program_verification_report,
    )
    parser = build_verify_unified_release_program_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_signed=args.require_signed,
        external_evidence_manifest_path=args.external_evidence_manifest,
        program_signoff_binding_path=args.program_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_verification_exit_code(report))


def handle_verify_unified_release_program_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_package(argv)

def _execute_verify_unified_release_program_operations_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-operations-package', *argv]
    from song_agent.unified_release_program_operations_verifier import (
        unified_release_program_operations_verification_exit_code,
        verify_unified_release_program_operations_package,
        write_unified_release_program_operations_verification_report,
    )
    parser = build_verify_unified_release_program_operations_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_operations_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_signed_program=args.require_signed_program,
        require_continuous_review_clear=args.require_continuous_review_clear,
        require_lifecycle_audit=args.require_lifecycle_audit,
        program_zip_path=args.program_zip,
        program_verification_report_path=args.program_verification_report,
        program_signoff_binding_path=args.program_signoff_binding,
        external_evidence_manifest_path=args.external_evidence_manifest,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_operations_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Operations verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_operations_verification_exit_code(report))


def handle_verify_unified_release_program_operations_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_operations_package(argv)

def _execute_verify_unified_release_program_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-handoff-package', *argv]
    from song_agent.unified_release_program_handoff_verifier import (
        unified_release_program_handoff_verification_exit_code,
        verify_unified_release_program_handoff_package,
        write_unified_release_program_handoff_verification_report,
    )
    parser = build_verify_unified_release_program_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_accepted=args.require_accepted,
        require_signed=args.require_signed,
        external_evidence_manifest_path=args.external_evidence_manifest,
        handoff_signoff_binding_path=args.handoff_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_handoff_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Handoff verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_handoff_verification_exit_code(report))


def handle_verify_unified_release_program_handoff_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_handoff_package(argv)

def _execute_verify_unified_release_program_vault_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-vault-package', *argv]
    from song_agent.unified_release_program_vault_verifier import (
        unified_release_program_vault_verification_exit_code,
        verify_unified_release_program_vault_package,
        write_unified_release_program_vault_verification_report,
    )
    parser = build_verify_unified_release_program_vault_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_vault_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_anchor=args.require_anchor,
        vault_anchor_path=args.vault_anchor,
        require_current_program=args.require_current_program,
        require_current_operations=args.require_current_operations,
        require_current_handoff=args.require_current_handoff,
        require_accepted_evidence=not args.no_require_accepted_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_vault_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Evidence Vault verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_vault_verification_exit_code(report))


def handle_verify_unified_release_program_vault_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_vault_package(argv)

def _execute_verify_unified_release_program_vault_operations_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-vault-operations-package', *argv]
    from song_agent.unified_release_program_vault_operations_verifier import (
        unified_release_program_vault_operations_verification_exit_code,
        verify_unified_release_program_vault_operations_package,
        write_unified_release_program_vault_operations_verification_report,
    )
    parser = build_verify_unified_release_program_vault_operations_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_vault_operations_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_signed=args.require_signed,
        require_current_vault=args.require_current_vault,
        signoff_binding_path=args.signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_vault_operations_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Vault Operations verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_vault_operations_verification_exit_code(report))


def handle_verify_unified_release_program_vault_operations_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_vault_operations_package(argv)

def _execute_verify_unified_release_program_continuity_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-package', *argv]
    from song_agent.unified_release_program_continuity_verifier import (
        unified_release_program_continuity_verification_exit_code,
        verify_unified_release_program_continuity_package,
        write_unified_release_program_continuity_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_package(
        args.zip_path,
        strict=args.strict,
        deep_restore=args.deep_restore,
        require_signed=args.require_signed,
        require_current_vault_operations=args.require_current_vault_operations,
        signoff_binding_path=args.signoff_binding,
        vault_operations_archive_path=args.vault_operations_archive,
        vault_operations_verification_report_path=args.vault_operations_verification_report,
        vault_operations_signoff_binding_path=args.vault_operations_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_package(argv)

def _execute_verify_unified_release_program_continuity_kit_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-kit-package', *argv]
    from song_agent.unified_release_program_continuity_distribution_verifier import (
        unified_release_program_continuity_distribution_verification_exit_code,
        verify_unified_release_program_continuity_distribution_package,
        write_unified_release_program_continuity_distribution_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_distribution_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_distribution_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_receiver_receipt=args.require_receiver_receipt,
        receiver_receipt_path=args.receiver_receipt,
        kit_verification_report_path=args.verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_distribution_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Distribution Kit verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_distribution_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_kit_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_kit_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-package', *argv]
    from song_agent.unified_release_program_continuity_command_center_verifier import (
        unified_release_program_continuity_command_center_verification_exit_code,
        verify_unified_release_program_continuity_command_center_package,
        write_unified_release_program_continuity_command_center_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_ready=args.require_ready,
        evidence_manifest_path=args.evidence_manifest,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_command_center_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Command Center verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_command_center_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_command_center_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_signoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-signoff-package', *argv]
    from song_agent.unified_release_program_continuity_command_center_signoff_verifier import (
        command_center_signoff_verification_exit_code,
        verify_unified_release_program_continuity_command_center_signoff_package,
        write_unified_release_program_continuity_command_center_signoff_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_command_center_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_signoff_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        signoff_binding_path=args.signoff_binding,
        command_center_zip_path=args.command_center,
        command_center_verification_report_path=args.command_center_verification_report,
        command_center_external_evidence_manifest_path=args.command_center_evidence_manifest,
    )
    if args.report_out:
        write_unified_release_program_continuity_command_center_signoff_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Continuity Command Center Signoff Archive verification: {report.get('status')}")
    raise SystemExit(command_center_signoff_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_command_center_signoff_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_signoff_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_handoff_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-handoff-package', *argv]
    from song_agent.unified_release_program_continuity_command_center_signoff_verifier import (
        command_center_signoff_verification_exit_code,
        verify_unified_release_program_continuity_command_center_final_handoff_package,
        write_unified_release_program_continuity_command_center_final_handoff_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_command_center_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_final_handoff_package(
        args.zip_path,
        strict=args.strict,
        require_archive=args.require_archive,
        archive_zip_path=args.archive_zip,
        archive_verification_report_path=args.archive_verification_report,
        signoff_binding_path=args.signoff_binding,
        command_center_zip_path=args.command_center,
        command_center_verification_report_path=args.command_center_verification_report,
        command_center_external_evidence_manifest_path=args.command_center_evidence_manifest,
    )
    if args.report_out:
        write_unified_release_program_continuity_command_center_final_handoff_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Continuity Command Center Final Handoff verification: {report.get('status')}")
    raise SystemExit(command_center_signoff_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_command_center_handoff_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_handoff_package(argv)

def _execute_verify_release(argv: list[str]) -> None:
    raw_args = ['verify-release', *argv]
    from song_agent.release_verifier import release_verification_exit_code, print_verification_report, verify_release_zip, write_verification_report
    parser = build_verify_release_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_zip(
        args.zip_path,
        strict=args.strict,
        require_audio=args.require_audio,
        require_human_review=args.require_human_review,
        require_audio_revisions=args.require_audio_revisions,
        require_stems=args.require_stems,
        require_mastering=args.require_mastering,
        require_encoded_audio=args.require_encoded_audio,
        require_encoded_audio_review=args.require_encoded_audio_review,
        require_format_decision=args.require_format_decision,
        require_rights_clearance=args.require_rights_clearance,
        required_audio_format_profiles=[item.strip() for item in str(args.require_audio_formats or "").split(",") if item.strip()],
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_verification_report(report)
    raise SystemExit(release_verification_exit_code(report))


def handle_verify_release(argv: list[str]) -> None:
    _execute_verify_release(argv)

def _execute_verify_distribution_package(argv: list[str]) -> None:
    raw_args = ['verify-distribution-package', *argv]
    from song_agent.distribution_verifier import (
        distribution_verification_exit_code,
        print_distribution_verification_report,
        verify_distribution_package,
        write_distribution_verification_report,
    )
    parser = build_verify_distribution_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_distribution_package(
        args.zip_path,
        strict=args.strict,
        require_audio=args.require_audio,
        require_artwork=args.require_artwork,
        require_encoded_audio=args.require_encoded_audio,
        require_encoded_audio_review=args.require_encoded_audio_review,
        require_format_decision=args.require_format_decision,
        require_rights_clearance=args.require_rights_clearance,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_distribution_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_distribution_verification_report(report)
    raise SystemExit(distribution_verification_exit_code(report))


def handle_verify_distribution_package(argv: list[str]) -> None:
    _execute_verify_distribution_package(argv)

def _execute_verify_submission_package(argv: list[str]) -> None:
    raw_args = ['verify-submission-package', *argv]
    from song_agent.submission_verifier import (
        print_submission_verification_report,
        submission_verification_exit_code,
        verify_submission_package,
        write_submission_verification_report,
    )
    parser = build_verify_submission_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_submission_package(
        args.zip_path,
        strict=args.strict,
        require_submitted=args.require_submitted,
        require_accepted=args.require_accepted,
        require_rights_clearance=args.require_rights_clearance,
        deep=args.deep,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_submission_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_submission_verification_report(report)
    raise SystemExit(submission_verification_exit_code(report))


def handle_verify_submission_package(argv: list[str]) -> None:
    _execute_verify_submission_package(argv)

def _execute_verify_submission_evidence_package(argv: list[str]) -> None:
    raw_args = ['verify-submission-evidence-package', *argv]
    from song_agent.submission_evidence_verifier import (
        print_submission_evidence_verification_report,
        submission_evidence_verification_exit_code,
        verify_submission_evidence_package,
        write_submission_evidence_verification_report,
    )
    parser = build_verify_submission_evidence_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_submission_evidence_package(
        args.zip_path,
        strict=args.strict,
        deep=args.deep,
        require_submitted=args.require_submitted,
        require_accepted=args.require_accepted,
        require_rights_clearance=args.require_rights_clearance,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_submission_evidence_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_submission_evidence_verification_report(report)
    raise SystemExit(submission_evidence_verification_exit_code(report))


def handle_verify_submission_evidence_package(argv: list[str]) -> None:
    _execute_verify_submission_evidence_package(argv)

def _execute_verify_release_operations_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-package', *argv]
    from song_agent.release_operations_verifier import (
        print_release_operations_verification_report,
        release_operations_verification_exit_code,
        verify_release_operations_package,
    )
    parser = build_verify_release_operations_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_package(
        args.zip_path,
        strict=args.strict,
        require_accepted=args.require_accepted,
        require_submission_evidence=args.require_submission_evidence,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_verification_report(report)
    raise SystemExit(release_operations_verification_exit_code(report))


def handle_verify_release_operations_package(argv: list[str]) -> None:
    _execute_verify_release_operations_package(argv)

def _execute_verify_release_operations_runbook_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-runbook-package', *argv]
    from song_agent.release_operations_runbook_verifier import (
        print_release_operations_runbook_verification_report,
        release_operations_runbook_verification_exit_code,
        verify_release_operations_runbook_package,
        write_release_operations_runbook_verification_report,
    )
    parser = build_verify_release_operations_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_runbook_package(
        args.zip_path,
        strict=args.strict,
        require_completed=args.require_completed,
        require_current=args.require_current,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_runbook_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_runbook_verification_report(report)
    raise SystemExit(release_operations_runbook_verification_exit_code(report))


def handle_verify_release_operations_runbook_package(argv: list[str]) -> None:
    _execute_verify_release_operations_runbook_package(argv)

def _execute_verify_release_operations_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-archive-package', *argv]
    from song_agent.release_operations_archive_verifier import (
        print_release_operations_archive_verification_report,
        release_operations_archive_verification_exit_code,
        verify_release_operations_archive_package,
        write_release_operations_archive_verification_report,
    )
    parser = build_verify_release_operations_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_archive_verification_report(report)
    raise SystemExit(release_operations_archive_verification_exit_code(report))


def handle_verify_release_operations_archive_package(argv: list[str]) -> None:
    _execute_verify_release_operations_archive_package(argv)

def _execute_verify_release_operations_audit_package(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-audit-package', *argv]
    from song_agent.release_operations_audit_verifier import (
        print_release_operations_audit_verification_report,
        release_operations_audit_verification_exit_code,
        verify_release_operations_audit_package,
        write_release_operations_audit_verification_report,
    )
    parser = build_verify_release_operations_audit_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_audit_package(
        args.zip_path,
        strict=args.strict,
        require_current=args.require_current,
        require_signed=args.require_signed,
        require_archive=args.require_archive,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_audit_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_audit_verification_report(report)
    raise SystemExit(release_operations_audit_verification_exit_code(report))


def handle_verify_release_operations_audit_package(argv: list[str]) -> None:
    _execute_verify_release_operations_audit_package(argv)

def _execute_verify_release_operations_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['verify-release-operations-reviewer-pack', *argv]
    from song_agent.release_operations_reviewer_pack_verifier import (
        print_release_operations_reviewer_pack_verification_report,
        release_operations_reviewer_pack_verification_exit_code,
        verify_release_operations_reviewer_pack,
        write_release_operations_reviewer_pack_verification_report,
    )
    parser = build_verify_release_operations_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_operations_reviewer_pack(
        args.zip_path,
        strict=args.strict,
        require_audit=args.require_audit,
        require_signed=args.require_signed,
        require_archive=args.require_archive,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_operations_reviewer_pack_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_release_operations_reviewer_pack_verification_report(report)
    raise SystemExit(release_operations_reviewer_pack_verification_exit_code(report))


def handle_verify_release_operations_reviewer_pack(argv: list[str]) -> None:
    _execute_verify_release_operations_reviewer_pack(argv)

def _execute_release_operations(argv: list[str]) -> None:
    raw_args = ['release-operations', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore, operations_report_summary
    from song_agent.release_operations_verifier import release_operations_verification_summary, verify_release_operations_package
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_operations_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    store = ReleaseOperationsStore(
        release_store=release_store,
        distribution_store=distribution_store,
        submission_store=submission_store,
        submission_evidence_store=SubmissionEvidenceStore(submission_store),
    )
    result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
    if args.refresh:
        report = store.refresh(args.release_id)
        result.update({"report": report, "summary": operations_report_summary(report)})
    else:
        overview = store.overview(args.release_id)
        result.update(overview)
    if args.export:
        manifest = store.export_operations(args.release_id)
        result.update({"manifest": manifest, "export_summary": manifest.get("summary", {})})
    if args.zip:
        zip_info = store.build_zip(args.release_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_operations_package(store.zip_path(args.release_id), require_accepted=args.require_accepted, require_submission_evidence=args.require_submission_evidence)
        result.update({"verification": verification, "verification_summary": release_operations_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_result(result)
    raise SystemExit(0)


def handle_release_operations(argv: list[str]) -> None:
    _execute_release_operations(argv)

def _execute_release_operations_runbook(argv: list[str]) -> None:
    raw_args = ['release-operations-runbook', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore, runbook_summary
    from song_agent.release_operations_runbook_verifier import release_operations_runbook_verification_summary, verify_release_operations_runbook_package
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_operations_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
    if args.list:
        runbooks = store.list_runbooks(args.release_id, include_archived=True)
        result.update({"runbooks": runbooks, "summary": {"count": len(runbooks)}})
    elif args.create:
        runbook = store.create_from_operations_report(args.release_id)
        result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
    else:
        if not args.runbook_id:
            raise ValueError("--runbook-id is required unless --create or --list is used.")
        runbook = store.get_runbook(args.release_id, args.runbook_id)
        result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
        if args.run_safe:
            runbook = store.run_safe_actions(args.release_id, args.runbook_id)
            result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
        if args.refresh_stale:
            stale_result = store.refresh_stale_status(args.release_id, args.runbook_id)
            result.update(stale_result)
            result["summary"] = runbook_summary(stale_result.get("runbook", {}))
        if args.export:
            manifest = store.export_runbook(args.release_id, args.runbook_id)
            result.update({"manifest": manifest})
        if args.zip:
            zip_info = store.build_zip(args.release_id, args.runbook_id)
            result.update({"zip": zip_info})
        if args.verify:
            verification = verify_release_operations_runbook_package(store.zip_path(args.release_id, args.runbook_id), require_completed=args.require_completed, require_current=args.require_current)
            result.update({"verification": verification, "verification_summary": release_operations_runbook_verification_summary(verification)})
        if args.archive:
            runbook = store.archive_runbook(args.release_id, args.runbook_id)
            result.update({"runbook": runbook, "summary": runbook_summary(runbook)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_runbook_result(result)
    raise SystemExit(0)


def handle_release_operations_runbook(argv: list[str]) -> None:
    _execute_release_operations_runbook(argv)

def _execute_release_operations_signoff(argv: list[str]) -> None:
    raw_args = ['release-operations-signoff', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore, operations_signoff_summary
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_operations_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
    if args.reset:
        signoff = store.reset_signoff(args.release_id, {"reason": args.reason, "change_request_id": args.change_request_id})
    elif args.sign:
        signoff = store.signoff(args.release_id, {"signed_by": args.signed_by, "force": args.force, "override_reason": args.override_reason})
    else:
        signoff = store.read_signoff(args.release_id, default={})
        result["gate"] = store.gate(args.release_id, {})
    current_report = operations_store.build_report(args.release_id, persist=False) if signoff else None
    result.update({"signoff": signoff, "summary": operations_signoff_summary(signoff, current_report=current_report)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_signoff_result(result)
    raise SystemExit(0)


def handle_release_operations_signoff(argv: list[str]) -> None:
    _execute_release_operations_signoff(argv)

def _execute_release_operations_archive(argv: list[str]) -> None:
    raw_args = ['release-operations-archive', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_archive_verifier import release_operations_archive_verification_summary, verify_release_operations_archive_package
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_operations_archive_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
    if args.export:
        result["manifest"] = store.export_archive(args.release_id)
    if args.zip:
        result["zip"] = store.build_archive_zip(args.release_id)
    if args.verify:
        verification = verify_release_operations_archive_package(store.archive_zip_path(args.release_id), strict=args.strict, require_signed=args.require_signed)
        result.update({"verification": verification, "verification_summary": release_operations_archive_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_archive_result(result)
    raise SystemExit(0)


def handle_release_operations_archive(argv: list[str]) -> None:
    _execute_release_operations_archive(argv)

def _execute_release_operations_audit(argv: list[str]) -> None:
    raw_args = ['release-operations-audit', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore, audit_summary
    from song_agent.release_operations_audit_verifier import release_operations_audit_verification_summary, verify_release_operations_audit_package
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_operations_audit_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
    if args.refresh:
        report = store.refresh(args.release_id)
        result.update({"report": report, "summary": audit_summary(report)})
    else:
        report = store.read_report(args.release_id, default={})
        result.update({"report": report, "summary": audit_summary(report) if report else {"status": "missing", "entry_count": 0}})
    if args.entries:
        entries = store.entries(args.release_id)
        result.update({"entries": entries, "entry_summary": {"entry_count": len(entries)}})
    if args.graph:
        result["graph"] = store.graph(args.release_id)
    if args.export:
        result["manifest"] = store.export_audit(args.release_id)
    if args.zip:
        result["zip"] = store.build_zip(args.release_id)
    if args.verify:
        verification = verify_release_operations_audit_package(store.zip_path(args.release_id), strict=args.strict, require_current=args.require_current, require_signed=args.require_signed, require_archive=args.require_archive)
        result.update({"verification": verification, "verification_summary": release_operations_audit_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_audit_result(result)
    raise SystemExit(0)


def handle_release_operations_audit(argv: list[str]) -> None:
    _execute_release_operations_audit(argv)

def _execute_release_operations_reviewer_pack(argv: list[str]) -> None:
    raw_args = ['release-operations-reviewer-pack', *argv]
    from song_agent.distribution import DistributionStore
    from song_agent.release_operations import ReleaseOperationsStore
    from song_agent.release_operations_audit import ReleaseOperationsAuditStore
    from song_agent.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore, reviewer_pack_summary
    from song_agent.release_operations_reviewer_pack_verifier import release_operations_reviewer_pack_verification_summary, verify_release_operations_reviewer_pack, write_release_operations_reviewer_pack_verification_report
    from song_agent.release_operations_runbook import ReleaseOperationsRunbookStore
    from song_agent.release_operations_signoff import ReleaseOperationsSignoffStore
    from song_agent.release_operations_retrospective import retrospective_summary
    from song_agent.releases import ReleaseStore
    from song_agent.submission_evidence import SubmissionEvidenceStore
    from song_agent.submissions import SubmissionStore
    parser = build_release_operations_reviewer_pack_parser()
    args = parser.parse_args(raw_args[1:])
    release_store = ReleaseStore()
    distribution_store = DistributionStore(release_store)
    submission_store = SubmissionStore(release_store, distribution_store)
    evidence_store = SubmissionEvidenceStore(submission_store)
    operations_store = ReleaseOperationsStore(release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    runbook_store = ReleaseOperationsRunbookStore(operations_store=operations_store, release_store=release_store, distribution_store=distribution_store, submission_store=submission_store, submission_evidence_store=evidence_store)
    signoff_store = ReleaseOperationsSignoffStore(operations_store=operations_store, runbook_store=runbook_store, release_store=release_store)
    audit_store = ReleaseOperationsAuditStore(operations_store=operations_store, runbook_store=runbook_store, signoff_store=signoff_store, release_store=release_store)
    store = ReleaseOperationsReviewerPackStore(audit_store=audit_store, signoff_store=signoff_store, release_store=release_store)
    result: dict[str, Any] = {"ok": True, "release_id": args.release_id}
    if args.refresh:
        report = store.refresh(args.release_id)
        result.update({"report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(store.read_retrospective(args.release_id, default={}))})
    else:
        report = store.read_report(args.release_id, default={})
        result.update({"report": report, "summary": reviewer_pack_summary(report), "retrospective_summary": retrospective_summary(store.read_retrospective(args.release_id, default={})) if report else {"status": "missing"}})
    if args.export:
        manifest = store.export_pack(args.release_id)
        result.update({"manifest": manifest})
    if args.zip:
        zip_info = store.build_zip(args.release_id)
        result.update({"zip": zip_info})
    if args.verify:
        verification = verify_release_operations_reviewer_pack(store.zip_path(args.release_id), strict=args.strict, require_audit=args.require_audit, require_signed=args.require_signed, require_archive=args.require_archive)
        write_release_operations_reviewer_pack_verification_report(verification, store.verification_report_path(args.release_id))
        result.update({"verification": verification, "verification_summary": release_operations_reviewer_pack_verification_summary(verification)})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_operations_reviewer_pack_result(result)
    raise SystemExit(0)


def handle_release_operations_reviewer_pack(argv: list[str]) -> None:
    _execute_release_operations_reviewer_pack(argv)

def _execute_release_encode(argv: list[str]) -> None:
    raw_args = ['release-encode', *argv]
    from song_agent.audio_encoding import AudioEncodingStore
    from song_agent.audio_encoding_profiles import AudioEncodingProfileStore
    from song_agent.projects import ProjectStore
    from song_agent.releases import ReleaseStore
    parser = build_release_encode_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
    store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
    result = store.render(args.release_id, {"profile_ids": [item.strip() for item in str(args.profiles or "").split(",") if item.strip()], "force": args.force})
    payload = {"ok": True, **result}
    if args.report_out is not None:
        write_interface_document(args.report_out, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload.get("summary", {})
        print(f"MusicForge release-encode\nrelease: {args.release_id}\nstatus: {summary.get('status')}\nprofiles: {summary.get('profile_count', 0)}")
    raise SystemExit(0 if payload.get("summary", {}).get("status") in {"completed", "warning"} else 1)


def handle_release_encode(argv: list[str]) -> None:
    _execute_release_encode(argv)


SPECS = (
    CommandSpec(name='verify-unified-command-center-release-train-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_package, help='Verify Unified Command Center Release Train Package', group='delivery'),
    CommandSpec(name='verify-unified-command-center-release-train-change-control-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_change_control_package, help='Verify Unified Command Center Release Train Change Control Package', group='delivery'),
    CommandSpec(name='verify-unified-command-center-release-train-lifecycle-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_lifecycle_package, help='Verify Unified Command Center Release Train Lifecycle Package', group='delivery'),
    CommandSpec(name='verify-unified-command-center-release-train-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_release_train_handoff_package, help='Verify Unified Command Center Release Train Handoff Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_package, help='Verify Unified Release Program Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-operations-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_operations_package, help='Verify Unified Release Program Operations Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_handoff_package, help='Verify Unified Release Program Handoff Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-vault-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_vault_package, help='Verify Unified Release Program Vault Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-vault-operations-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_vault_operations_package, help='Verify Unified Release Program Vault Operations Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_package, help='Verify Unified Release Program Continuity Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-kit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_kit_package, help='Verify Unified Release Program Continuity Kit Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_package, help='Verify Unified Release Program Continuity Command Center Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-signoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_signoff_package, help='Verify Unified Release Program Continuity Command Center Signoff Package', group='delivery'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-handoff-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_handoff_package, help='Verify Unified Release Program Continuity Command Center Handoff Package', group='delivery'),
    CommandSpec(name='verify-release', parser=build_acceptance_analytics_parser, handler=handle_verify_release, help='Verify Release', group='delivery'),
    CommandSpec(name='verify-distribution-package', parser=build_acceptance_analytics_parser, handler=handle_verify_distribution_package, help='Verify Distribution Package', group='delivery'),
    CommandSpec(name='verify-submission-package', parser=build_acceptance_analytics_parser, handler=handle_verify_submission_package, help='Verify Submission Package', group='delivery'),
    CommandSpec(name='verify-submission-evidence-package', parser=build_acceptance_analytics_parser, handler=handle_verify_submission_evidence_package, help='Verify Submission Evidence Package', group='delivery'),
    CommandSpec(name='verify-release-operations-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_package, help='Verify Release Operations Package', group='delivery'),
    CommandSpec(name='verify-release-operations-runbook-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_runbook_package, help='Verify Release Operations Runbook Package', group='delivery'),
    CommandSpec(name='verify-release-operations-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_archive_package, help='Verify Release Operations Archive Package', group='delivery'),
    CommandSpec(name='verify-release-operations-audit-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_audit_package, help='Verify Release Operations Audit Package', group='delivery'),
    CommandSpec(name='verify-release-operations-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_verify_release_operations_reviewer_pack, help='Verify Release Operations Reviewer Pack', group='delivery'),
    CommandSpec(name='release-operations', parser=build_acceptance_analytics_parser, handler=handle_release_operations, help='Release Operations', group='delivery'),
    CommandSpec(name='release-operations-runbook', parser=build_acceptance_analytics_parser, handler=handle_release_operations_runbook, help='Release Operations Runbook', group='delivery'),
    CommandSpec(name='release-operations-signoff', parser=build_acceptance_analytics_parser, handler=handle_release_operations_signoff, help='Release Operations Signoff', group='delivery'),
    CommandSpec(name='release-operations-archive', parser=build_acceptance_analytics_parser, handler=handle_release_operations_archive, help='Release Operations Archive', group='delivery'),
    CommandSpec(name='release-operations-audit', parser=build_acceptance_analytics_parser, handler=handle_release_operations_audit, help='Release Operations Audit', group='delivery'),
    CommandSpec(name='release-operations-reviewer-pack', parser=build_acceptance_analytics_parser, handler=handle_release_operations_reviewer_pack, help='Release Operations Reviewer Pack', group='delivery'),
    CommandSpec(name='release-encode', parser=build_acceptance_analytics_parser, handler=handle_release_encode, help='Release Encode', group='delivery'),
)
