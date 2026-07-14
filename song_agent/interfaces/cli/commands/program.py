from __future__ import annotations
import argparse
import json
import sys
import os
from pathlib import Path
from typing import Any
from song_agent.application.program import ProgramApplicationService
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


def _program_component(name: str) -> Any:
    return ProgramApplicationService.build().component(name)

def _acceptance_analytics_fail_on(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_acceptance_analytics_fail_on')(*args, **kwargs)

def _add_command_center_acceptance_source_args(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_add_command_center_acceptance_source_args')(*args, **kwargs)

def _build_public_trust_center_publication_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_publication_store')(*args, **kwargs)

def _build_public_trust_center_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_store')(*args, **kwargs)

def _build_release_portfolio_governance_attestation_portal_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_release_portfolio_governance_attestation_portal_store')(*args, **kwargs)

def _command_center_acceptance_payload(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_command_center_acceptance_payload')(*args, **kwargs)

def _print_release_audio_certification_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_print_release_audio_certification_result')(*args, **kwargs)

def _release_audio_command_center_evidence_from_args(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('quality', '_release_audio_command_center_evidence_from_args')(*args, **kwargs)

def _release_train_handoff_payload_from_args(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', '_release_train_handoff_payload_from_args')(*args, **kwargs)

def _release_train_lifecycle_payload_from_args(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('delivery', '_release_train_lifecycle_payload_from_args')(*args, **kwargs)

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

def _add_ga_unified_command_center_evidence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--unified-release-zip", type=Path, default=None, help="Release ZIP referenced by Unified Command Center.")
    parser.add_argument("--unified-release-verification-report", type=Path, default=None, help="Release verification report referenced by Unified Command Center.")
    parser.add_argument("--unified-distribution-zip", action="append", default=[], type=Path, help="Distribution ZIP referenced by Unified Command Center. Repeat for multiple targets.")
    parser.add_argument("--unified-distribution-verification-report", action="append", default=[], type=Path, help="Distribution verification report referenced by Unified Command Center.")
    parser.add_argument("--unified-submission-zip", action="append", default=[], type=Path, help="Submission ZIP referenced by Unified Command Center. Repeat for multiple submissions.")
    parser.add_argument("--unified-submission-verification-report", action="append", default=[], type=Path, help="Submission verification report referenced by Unified Command Center.")
    parser.add_argument("--unified-release-operations-zip", type=Path, default=None, help="Release Operations ZIP referenced by Unified Command Center.")
    parser.add_argument("--unified-release-operations-verification-report", type=Path, default=None, help="Release Operations verification report referenced by Unified Command Center.")
    parser.add_argument("--unified-trust-operations-hub", type=Path, default=None, help="Trust Operations Hub ZIP referenced by Unified Command Center.")
    parser.add_argument("--unified-trust-operations-hub-verification-report", type=Path, default=None, help="Trust Operations Hub verification report referenced by Unified Command Center.")
    parser.add_argument("--unified-public-trust-center", type=Path, default=None, help="Public Trust Center ZIP referenced by Unified Command Center.")
    parser.add_argument("--unified-public-trust-center-verification-report", type=Path, default=None, help="Public Trust Center verification report referenced by Unified Command Center.")
    parser.add_argument("--unified-maintenance-backup", type=Path, default=None, help="Maintenance backup ZIP referenced by Unified Command Center.")
    parser.add_argument("--unified-maintenance-backup-verification-report", type=Path, default=None, help="Maintenance backup verification report referenced by Unified Command Center.")
    parser.add_argument("--require-unified-command-center-continuous-review", action="store_true", help="Require Unified Command Center Continuous Review evidence.")
    parser.add_argument("--unified-command-center-continuous-review", type=Path, default=None, help="Unified Command Center Continuous Review ZIP.")
    parser.add_argument("--unified-command-center-continuous-review-verification-report", type=Path, default=None, help="Unified Command Center Continuous Review verification report.")
    parser.add_argument("--require-unified-command-center-drift-response", action="store_true", help="Require Unified Command Center Drift Response evidence.")
    parser.add_argument("--unified-command-center-drift-response", type=Path, default=None, help="Unified Command Center Drift Response ZIP.")
    parser.add_argument("--unified-command-center-drift-response-verification-report", type=Path, default=None, help="Unified Command Center Drift Response verification report.")
    parser.add_argument("--unified-command-center-drift-source-review", type=Path, default=None, help="Source failed Continuous Review ZIP for Drift Response.")
    parser.add_argument("--unified-command-center-drift-source-review-verification-report", type=Path, default=None, help="Source failed Continuous Review verification report for Drift Response.")
    parser.add_argument("--unified-command-center-drift-recheck-review", type=Path, default=None, help="Clear recheck Continuous Review ZIP for Drift Response.")
    parser.add_argument("--unified-command-center-drift-recheck-review-verification-report", type=Path, default=None, help="Clear recheck Continuous Review verification report for Drift Response.")
    parser.add_argument("--unified-command-center-drift-change-request-binding-report", type=Path, default=None, help="External Change Request binding report for Drift Response.")
    parser.add_argument("--require-unified-command-center-evidence-review", action="store_true", help="Require Unified Command Center Evidence Review / Replay evidence.")
    parser.add_argument("--unified-command-center-evidence-review", type=Path, default=None, help="Unified Command Center Evidence Review ZIP.")
    parser.add_argument("--unified-command-center-evidence-review-verification-report", type=Path, default=None, help="Unified Command Center Evidence Review verification report.")
    parser.add_argument("--require-unified-command-center-evidence-review-accepted", action="store_true", help="Require accepted external Evidence Review response evidence.")
    parser.add_argument("--unified-command-center-evidence-review-acceptance", type=Path, default=None, help="Unified Command Center Evidence Review Acceptance ZIP.")
    parser.add_argument("--unified-command-center-evidence-review-acceptance-verification-report", type=Path, default=None, help="Unified Command Center Evidence Review Acceptance verification report.")
    parser.add_argument("--unified-command-center-evidence-review-acceptance-response-verification-report", type=Path, default=None, help="Original Evidence Review response verification summary bound by accepted evidence.")
    parser.add_argument("--require-unified-command-center-reviewer-decision-board", action="store_true", help="Require signed Unified Command Center Reviewer Decision Board evidence.")
    parser.add_argument("--unified-command-center-reviewer-decision-board", type=Path, default=None, help="Unified Command Center Reviewer Decision Board archive ZIP.")
    parser.add_argument("--unified-command-center-reviewer-decision-board-verification-report", type=Path, default=None, help="Unified Command Center Reviewer Decision Board verification report.")
    parser.add_argument("--no-require-unified-command-center-reviewer-decision-board-signed", dest="require_unified_command_center_reviewer_decision_board_signed", action="store_false", default=True, help="Do not require the Reviewer Decision Board to be signed.")
    parser.add_argument("--no-require-unified-command-center-reviewer-decision-board-quorum", dest="require_unified_command_center_reviewer_decision_board_quorum", action="store_false", default=True, help="Do not require the Reviewer Decision Board quorum to be passed.")
    parser.add_argument("--unified-command-center-reviewer-decision-board-evidence-review", type=Path, default=None, help="Evidence Review ZIP bound by the Reviewer Decision Board.")
    parser.add_argument("--unified-command-center-reviewer-decision-board-evidence-review-verification-report", type=Path, default=None, help="Evidence Review verification report bound by the Reviewer Decision Board.")
    parser.add_argument("--unified-command-center-reviewer-decision-board-accepted-evidence", action="append", default=[], type=Path, help="Accepted Evidence ZIP bound by the Reviewer Decision Board. Repeat for multiple reviewers.")
    parser.add_argument("--unified-command-center-reviewer-decision-board-accepted-evidence-verification-report", action="append", default=[], type=Path, help="Accepted Evidence verification report bound by the Reviewer Decision Board. Repeat in the same order.")
    parser.add_argument("--unified-command-center-reviewer-decision-board-accepted-evidence-response-verification-report", action="append", default=[], type=Path, help="Original accepted response verification summary bound by the Reviewer Decision Board. Repeat in the same order.")
    parser.add_argument("--require-unified-release-program-handoff", action="store_true", help="Require Unified Release Program Final Handoff evidence.")
    parser.add_argument("--unified-release-program-handoff", type=Path, default=None, help="Unified Release Program Final Handoff archive ZIP.")
    parser.add_argument("--unified-release-program-handoff-verification-report", type=Path, default=None, help="Unified Release Program Final Handoff verification report.")
    parser.add_argument("--unified-release-program-handoff-external-evidence-manifest", type=Path, default=None, help="External evidence manifest bound by the Unified Release Program Handoff.")
    parser.add_argument("--unified-release-program-handoff-signoff-binding", type=Path, default=None, help="Signoff binding summary bound by the Unified Release Program Handoff.")
    parser.add_argument("--require-unified-release-program-vault", action="store_true", help="Require Unified Release Program Evidence Vault evidence.")
    parser.add_argument("--unified-release-program-vault", type=Path, default=None, help="Unified Release Program Evidence Vault ZIP.")
    parser.add_argument("--unified-release-program-vault-verification-report", type=Path, default=None, help="Unified Release Program Evidence Vault verification report.")
    parser.add_argument("--unified-release-program-vault-anchor", type=Path, default=None, help="External Vault anchor bound to the Evidence Vault ZIP.")
    parser.add_argument("--require-unified-release-program-vault-operations", action="store_true", help="Require Unified Release Program Vault Operations evidence.")
    parser.add_argument("--unified-release-program-vault-operations", type=Path, default=None, help="Unified Release Program Vault Operations Archive ZIP.")
    parser.add_argument("--unified-release-program-vault-operations-verification-report", type=Path, default=None, help="Unified Release Program Vault Operations verification report.")
    parser.add_argument("--unified-release-program-vault-operations-signoff-binding", type=Path, default=None, help="External Vault Operations signoff binding summary.")
    parser.add_argument("--require-unified-release-program-continuity", action="store_true", help="Require Unified Release Program Continuity / Recovery Drill evidence.")
    parser.add_argument("--unified-release-program-continuity", type=Path, default=None, help="Unified Release Program Continuity Archive ZIP.")
    parser.add_argument("--unified-release-program-continuity-verification-report", type=Path, default=None, help="Unified Release Program Continuity verification report.")
    parser.add_argument("--unified-release-program-continuity-signoff-binding", type=Path, default=None, help="External Continuity signoff binding summary.")
    parser.add_argument("--require-unified-release-program-continuity-kit", action="store_true", help="Require Unified Release Program Continuity Distribution Kit evidence.")
    parser.add_argument("--unified-release-program-continuity-kit", type=Path, default=None, help="Unified Release Program Continuity Distribution Kit ZIP.")
    parser.add_argument("--unified-release-program-continuity-kit-verification-report", type=Path, default=None, help="Unified Release Program Continuity Distribution Kit verification report.")
    parser.add_argument("--unified-release-program-continuity-kit-receiver-receipt", type=Path, default=None, help="Receiver receipt bound to the Continuity Distribution Kit.")
    parser.add_argument("--require-unified-release-program-continuity-acceptance", action="store_true", help="Require Unified Release Program Continuity Acceptance Board evidence.")
    parser.add_argument("--unified-release-program-continuity-acceptance", type=Path, default=None, help="Unified Release Program Continuity Acceptance Board archive ZIP.")
    parser.add_argument("--unified-release-program-continuity-acceptance-verification-report", type=Path, default=None, help="Unified Release Program Continuity Acceptance Board verification report.")
    parser.add_argument("--unified-release-program-continuity-acceptance-signoff-binding", type=Path, default=None, help="External Continuity Acceptance Board signoff binding summary.")
    parser.add_argument("--require-unified-release-program-continuity-command-center", action="store_true", help="Require Unified Release Program Continuity Command Center evidence.")
    parser.add_argument("--unified-release-program-continuity-command-center", type=Path, default=None, help="Unified Release Program Continuity Command Center ZIP.")
    parser.add_argument("--unified-release-program-continuity-command-center-verification-report", type=Path, default=None, help="Unified Release Program Continuity Command Center verification report.")
    parser.add_argument("--unified-release-program-continuity-command-center-external-evidence-manifest", type=Path, default=None, help="External evidence manifest used for Command Center runtime verification.")
    parser.add_argument("--require-unified-release-program-continuity-command-center-signoff", action="store_true", help="Require signed Unified Release Program Continuity Command Center Archive evidence.")
    parser.add_argument("--unified-release-program-continuity-command-center-signoff-archive", type=Path, default=None, help="Continuity Command Center Signoff Archive ZIP.")
    parser.add_argument("--unified-release-program-continuity-command-center-signoff-verification-report", type=Path, default=None, help="Continuity Command Center Signoff Archive verification report.")
    parser.add_argument("--unified-release-program-continuity-command-center-signoff-binding", type=Path, default=None, help="Independent Continuity Command Center signoff binding summary.")
    parser.add_argument("--require-unified-release-program-continuity-command-center-acceptance", action="store_true", help="Require signed Continuity Command Center Receiver Acceptance evidence.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-archive", type=Path, default=None, help="Receiver Acceptance Archive ZIP.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-verification-report", type=Path, default=None, help="Receiver Acceptance Archive verification report.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-signoff-binding", type=Path, default=None, help="Independent Receiver Acceptance signoff binding summary.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-review-pack", type=Path, default=None, help="Receiver Handoff Review Pack ZIP.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-review-pack-verification-report", type=Path, default=None, help="Receiver Handoff Review Pack verification report.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-accepted-evidence-dir", type=Path, default=None, help="Receiver Accepted Evidence root directory.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-response-proof-dir", type=Path, default=None, help="Receiver response proof root directory.")
    parser.add_argument("--require-unified-release-program-continuity-command-center-acceptance-change-control", action="store_true", help="Require current Receiver Acceptance Change Control lifecycle evidence.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-change-archive", type=Path, default=None, help="Receiver Acceptance Change Control Archive ZIP.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-change-verification-report", type=Path, default=None, help="Receiver Acceptance Change Control verification report.")
    parser.add_argument("--unified-release-program-continuity-command-center-acceptance-previous-root", type=Path, default=None, help="Historical Receiver Acceptance generation evidence root.")
    parser.add_argument("--unified-release-program-continuity-command-center-final-handoff", type=Path, default=None, help="Continuity Command Center Final Handoff ZIP bound by Receiver Acceptance.")
    parser.add_argument("--unified-release-program-continuity-command-center-final-handoff-verification-report", type=Path, default=None, help="Continuity Command Center Final Handoff verification report.")

def _add_unified_command_center_evidence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--release-zip", type=Path, default=None, help="Release ZIP.")
    parser.add_argument("--release-verification-report", type=Path, default=None, help="Release ZIP verification report.")
    parser.add_argument("--release-audio-command-center", type=Path, default=None, help="Release Audio Command Center ZIP.")
    parser.add_argument("--release-audio-command-center-verification-report", type=Path, default=None, help="Release Audio Command Center verification report.")
    parser.add_argument("--distribution-zip", action="append", default=[], type=Path, help="Distribution Package ZIP. Repeat for multiple targets.")
    parser.add_argument("--distribution-verification-report", action="append", default=[], type=Path, help="Distribution verification report. Repeat in the same order as --distribution-zip.")
    parser.add_argument("--submission-zip", action="append", default=[], type=Path, help="Submission Package ZIP. Repeat for multiple submissions.")
    parser.add_argument("--submission-verification-report", action="append", default=[], type=Path, help="Submission verification report. Repeat in the same order as --submission-zip.")
    parser.add_argument("--release-operations-zip", type=Path, default=None, help="Release Operations ZIP.")
    parser.add_argument("--release-operations-verification-report", type=Path, default=None, help="Release Operations verification report.")
    parser.add_argument("--trust-operations-hub", type=Path, default=None, help="Trust Operations Hub ZIP.")
    parser.add_argument("--trust-operations-hub-verification-report", type=Path, default=None, help="Trust Operations Hub verification report.")
    parser.add_argument("--public-trust-center", type=Path, default=None, help="Public Trust Center ZIP.")
    parser.add_argument("--public-trust-center-verification-report", type=Path, default=None, help="Public Trust Center verification report.")
    parser.add_argument("--maintenance-backup", type=Path, default=None, help="Maintenance backup ZIP.")
    parser.add_argument("--maintenance-backup-verification-report", type=Path, default=None, help="Maintenance backup verification report.")
    parser.add_argument("--ga-readiness-report", type=Path, default=None, help="GA readiness report JSON.")
    parser.add_argument("--ga-readiness-verification-report", type=Path, default=None, help="GA readiness verification report JSON.")
    parser.add_argument("--release-check-report", type=Path, default=None, help="Release-check JSON report.")

def _add_unified_command_center_requirement_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--require-audio-command-center", action="store_true", help="Require Release Audio Command Center evidence.")
    parser.add_argument("--require-trust-operations-hub", action="store_true", help="Require Trust Operations Hub evidence.")
    parser.add_argument("--require-public-trust-center", action="store_true", help="Require Public Trust Center evidence.")
    parser.add_argument("--require-maintenance-backup", action="store_true", help="Require Maintenance backup evidence.")
    parser.add_argument("--require-ga-readiness", action="store_true", help="Require GA readiness evidence.")
    parser.add_argument("--require-release-check", action="store_true", help="Require release-check evidence.")
    parser.add_argument("--require-release-ready", action="store_true", help="Require Release ZIP verification evidence.")
    parser.add_argument("--require-distribution-ready", action="store_true", help="Require Distribution verification evidence.")
    parser.add_argument("--require-submission-ready", action="store_true", help="Require Submission verification evidence.")
    parser.add_argument("--require-operations-ready", action="store_true", help="Require Release Operations verification evidence.")
    parser.add_argument("--no-require-audio-command-center", dest="no_require_audio_command_center", action="store_true", help="Do not require Release Audio Command Center evidence.")
    parser.add_argument("--no-require-trust-operations-hub", dest="no_require_trust_operations_hub", action="store_true", help="Do not require Trust Operations Hub evidence.")
    parser.add_argument("--no-require-public-trust-center", dest="no_require_public_trust_center", action="store_true", help="Do not require Public Trust Center evidence.")
    parser.add_argument("--no-require-ga-readiness", dest="no_require_ga_readiness", action="store_true", help="Do not require GA readiness evidence.")
    parser.add_argument("--no-require-release-check", dest="no_require_release_check", action="store_true", help="Do not require release-check evidence.")
    parser.add_argument("--no-require-release-ready", dest="no_require_release_ready", action="store_true", help="Do not require Release ZIP verification evidence.")
    parser.add_argument("--no-require-distribution-ready", dest="no_require_distribution_ready", action="store_true", help="Do not require Distribution verification evidence.")
    parser.add_argument("--no-require-submission-ready", dest="no_require_submission_ready", action="store_true", help="Do not require Submission verification evidence.")
    parser.add_argument("--no-require-operations-ready", dest="no_require_operations_ready", action="store_true", help="Do not require Release Operations verification evidence.")

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

def _add_unified_command_center_release_train_lifecycle_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--external-evidence-manifest", type=Path, default=None)
    parser.add_argument("--train-archive", type=Path, default=None)
    parser.add_argument("--train-archive-verification-report", type=Path, default=None)
    parser.add_argument("--train-signoff-binding", type=Path, default=None)
    parser.add_argument("--change-control-zip", type=Path, default=None)
    parser.add_argument("--change-control-verification-report", type=Path, default=None)
    parser.add_argument("--reset-proof", type=Path, action="append", default=[])

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

def build_unified_release_program_continuity_command_center_acceptance_change_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Receiver Acceptance Change Control and lifecycle audit.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    actions = ("status", "create-cr", "approve-cr", "reset-signoff", "refresh-lifecycle", "export", "zip", "verify", "gate")
    for action in actions:
        cmd = subparsers.add_parser(action, help=f"{action} Receiver Acceptance Change Control.")
        cmd.add_argument("program_id")
        cmd.add_argument("--json", action="store_true")
        cmd.add_argument("--change-request-id", default=None)
        cmd.add_argument("--change-type", default=None)
        cmd.add_argument("--allowed-action", action="append", default=[])
        cmd.add_argument("--reason", default=None)
        cmd.add_argument("--requested-by", default=None)
        cmd.add_argument("--approved-by", default=None)
        cmd.add_argument("--role", default=None)
        cmd.add_argument("--approved-action", action="append", default=[])
        cmd.add_argument("--reset-by", default=None)
        cmd.add_argument("--archive-zip", type=Path, default=None)
        cmd.add_argument("--verification-report", type=Path, default=None)
        cmd.add_argument("--receiver-acceptance-archive", "--acceptance-archive", dest="acceptance_archive", type=Path, default=None)
        cmd.add_argument("--receiver-acceptance-verification-report", "--acceptance-verification-report", dest="acceptance_verification_report", type=Path, default=None)
        cmd.add_argument("--receiver-acceptance-signoff-binding", "--acceptance-signoff-binding", dest="acceptance_signoff_binding", type=Path, default=None)
        cmd.add_argument("--previous-acceptance-root", type=Path, default=None)
        cmd.add_argument("--strict", action="store_true")
        cmd.add_argument("--require-current", action="store_true")
        cmd.add_argument("--require-reset-proofs", action="store_true")
        cmd.add_argument("--report-out", type=Path, default=None)
        _add_command_center_acceptance_source_args(cmd)
    return parser

def build_verify_unified_release_program_continuity_command_center_acceptance_change_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a Receiver Acceptance Change Control Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current", action="store_true")
    parser.add_argument("--require-reset-proofs", action="store_true")
    parser.add_argument("--receiver-acceptance-archive", "--acceptance-archive", dest="acceptance_archive", type=Path, default=None)
    parser.add_argument("--receiver-acceptance-verification-report", "--acceptance-verification-report", dest="acceptance_verification_report", type=Path, default=None)
    parser.add_argument("--receiver-acceptance-signoff-binding", "--acceptance-signoff-binding", dest="acceptance_signoff_binding", type=Path, default=None)
    parser.add_argument("--previous-acceptance-root", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=2000)
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

def _unified_command_center_requirements_from_args(args: argparse.Namespace) -> dict[str, bool]:
    requirements: dict[str, bool] = {}
    mapping = {
        "require_audio_command_center": "require_audio_command_center",
        "require_trust_operations_hub": "require_trust_operations_hub",
        "require_public_trust_center": "require_public_trust_center",
        "require_maintenance_backup": "require_maintenance_backup",
        "require_ga_readiness": "require_ga_readiness",
        "require_release_check": "require_release_check",
        "require_release_ready": "require_release_ready",
        "require_distribution_ready": "require_distribution_ready",
        "require_submission_ready": "require_submission_ready",
        "require_operations_ready": "require_operations_ready",
    }
    for attr, key in mapping.items():
        if bool(getattr(args, attr, False)):
            requirements[key] = True
    negative = {
        "no_require_audio_command_center": "require_audio_command_center",
        "no_require_trust_operations_hub": "require_trust_operations_hub",
        "no_require_public_trust_center": "require_public_trust_center",
        "no_require_ga_readiness": "require_ga_readiness",
        "no_require_release_check": "require_release_check",
        "no_require_release_ready": "require_release_ready",
        "no_require_distribution_ready": "require_distribution_ready",
        "no_require_submission_ready": "require_submission_ready",
        "no_require_operations_ready": "require_operations_ready",
    }
    for attr, key in negative.items():
        if bool(getattr(args, attr, False)):
            requirements[key] = False
    return requirements

def _unified_command_center_evidence_from_args(args: argparse.Namespace) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "release": {
            "zip": getattr(args, "release_zip", None),
            "verification_report": getattr(args, "release_verification_report", None),
        },
        "audio-command-center": {
            "zip": getattr(args, "release_audio_command_center", None),
            "verification_report": getattr(args, "release_audio_command_center_verification_report", None),
        },
        "distribution": {
            "zips": getattr(args, "distribution_zip", []),
            "verification_reports": getattr(args, "distribution_verification_report", []),
        },
        "submission": {
            "zips": getattr(args, "submission_zip", []),
            "verification_reports": getattr(args, "submission_verification_report", []),
        },
        "operations": {
            "zip": getattr(args, "release_operations_zip", None),
            "verification_report": getattr(args, "release_operations_verification_report", None),
        },
        "trust-operations-hub": {
            "zip": getattr(args, "trust_operations_hub", None),
            "verification_report": getattr(args, "trust_operations_hub_verification_report", None),
        },
        "public-trust-center": {
            "zip": getattr(args, "public_trust_center", None),
            "verification_report": getattr(args, "public_trust_center_verification_report", None),
        },
        "maintenance": {
            "zip": getattr(args, "maintenance_backup", None),
            "verification_report": getattr(args, "maintenance_backup_verification_report", None),
        },
        "ga-readiness": {
            "report": getattr(args, "ga_readiness_report", None),
            "verification_report": getattr(args, "ga_readiness_verification_report", None),
        },
        "release-check": {"report": getattr(args, "release_check_report", None)},
    }
    requirements = _unified_command_center_requirements_from_args(args)
    if requirements:
        evidence["requirements"] = requirements
    return evidence

def _run_unified_command_center_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center import UnifiedCommandCenterStore
    from song_agent.unified_command_center_verifier import write_unified_command_center_verification_report
    from song_agent.unified_command_center_handoff import UnifiedCommandCenterHandoffStore
    from song_agent.unified_command_center_handoff_verifier import write_unified_command_center_handoff_verification_report
    from song_agent.unified_command_center_signoff import UnifiedCommandCenterSignoffStore
    from song_agent.unified_command_center_archive_verifier import write_unified_command_center_archive_verification_report

    store = UnifiedCommandCenterStore()
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    evidence = _unified_command_center_evidence_from_args(args)
    if args.action == "create":
        payload = {
            "center_id": args.center_id,
            "name": args.name,
            "scope": args.scope,
            "profile": args.profile,
            "primary_release_id": args.primary_release_id,
            "release_ids": args.release_id,
            "requirements": _unified_command_center_requirements_from_args(args),
        }
        center = store.create(payload)
        return {"ok": True, "center": center, "summary": {"center_id": center.get("center_id")}, "status": center.get("status")}
    if args.action == "list":
        centers = store.list_centers()
        return {"ok": True, "centers": centers, "summary": {"center_count": len(centers)}, "status": "passed"}
    if args.action == "status":
        center = store.read_center(args.center_id)
        report = store.read_report(args.center_id) if store.report_path(args.center_id).exists() else {}
        return {"ok": True, "center": center, "report": report, "summary": report.get("summary", {}), "status": center.get("status")}
    if args.action == "refresh":
        report = store.refresh(args.center_id, evidence)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "report":
        report = store.read_report(args.center_id)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "inventory":
        inventory = read_json(store.inventory_path(args.center_id))
        return {"ok": True, "inventory": inventory, "summary": inventory.get("summary", {}), "status": "passed"}
    if args.action == "readiness":
        readiness = read_json(store.readiness_path(args.center_id))
        return {"ok": readiness.get("overall_status") == "ready", "readiness": readiness, "summary": {"overall_status": readiness.get("overall_status")}, "status": readiness.get("overall_status")}
    if args.action == "gap-plan":
        gap_plan = read_json(store.gap_plan_path(args.center_id))
        return {"ok": int((gap_plan.get("summary") or {}).get("action_count") or 0) == 0, "gap_plan": gap_plan, "summary": gap_plan.get("summary", {}), "status": "passed" if int((gap_plan.get("summary") or {}).get("action_count") or 0) == 0 else "blocked"}
    if args.action == "runbook":
        runbook = store.create_runbook(args.center_id, evidence)
        return {"ok": True, "runbook": runbook, "summary": runbook.get("summary", {}), "status": "passed"}
    if args.action == "run-safe":
        result = store.run_safe(args.center_id, evidence)
        failed = int((result.get("summary") or {}).get("failed_count") or 0)
        return {"ok": failed == 0, "runbook_result": result, "summary": result.get("summary", {}), "status": "passed" if failed == 0 else "failed"}
    if args.action == "export":
        result = store.export_package(args.center_id, evidence)
        return {"ok": result.get("status") == "ready", **result, "summary": result.get("manifest", {})}
    if args.action == "zip":
        result = store.build_zip(args.center_id, evidence)
        return {"ok": result.get("status") == "ready", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(args.center_id, evidence=evidence, strict=args.strict, require_ready=args.require_ready)
        if args.report_out is not None:
            write_unified_command_center_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "signoff":
        signoff = signoff_store.signoff(args.center_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive":
        manifest = signoff_store.export_archive(args.center_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "archive-zip":
        result = signoff_store.build_archive_zip(args.center_id)
        return {"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-archive":
        report = signoff_store.verify_archive(args.center_id, {"strict": args.strict, "require_current_ucc": args.require_current_ucc})
        if args.report_out is not None:
            write_unified_command_center_archive_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "handoff":
        manifest = handoff_store.export_handoff(args.center_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "handoff-zip":
        result = handoff_store.build_handoff_zip(args.center_id)
        return {"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-handoff":
        report = handoff_store.verify_handoff(args.center_id, {"strict": args.strict, "require_archive": args.require_archive})
        if args.report_out is not None:
            write_unified_command_center_handoff_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "change-request-create":
        cr = signoff_store.create_change_request(args.center_id, {"created_by": args.created_by, "reason": args.reason, "risk": args.risk})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "change-request-approve":
        cr = signoff_store.approve_change_request(args.center_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "signoff-reset":
        result = signoff_store.reset_signoff(args.center_id, args.change_request_id, {"reason": args.reason})
        return {"ok": True, **result, "summary": {"change_request_id": args.change_request_id}}
    raise ValueError("Unsupported unified-command-center command.")

def _unified_command_center_review_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "review_id": getattr(args, "review_id", None),
        "created_by": getattr(args, "created_by", None),
        "include_handoff": getattr(args, "include_handoff", True),
        "archive_zip": getattr(args, "archive_zip", None),
        "archive_verification_report": getattr(args, "archive_verification_report", None),
        "handoff_zip": getattr(args, "handoff_zip", None),
        "handoff_verification_report": getattr(args, "handoff_verification_report", None),
        "command_center_zip": getattr(args, "command_center_zip", None),
        "command_center_verification_report": getattr(args, "command_center_verification_report", None),
        "signoff_binding": getattr(args, "signoff_binding", None),
        "ga_readiness_report": getattr(args, "ga_readiness_report", None),
        "release_check_report": getattr(args, "release_check_report", None),
    }

def _run_unified_command_center_review_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center import UnifiedCommandCenterStore
    from song_agent.unified_command_center_continuous_review import UnifiedCommandCenterContinuousReviewStore
    from song_agent.unified_command_center_continuous_review_verifier import write_unified_command_center_continuous_review_verification_report
    from song_agent.unified_command_center_handoff import UnifiedCommandCenterHandoffStore
    from song_agent.unified_command_center_signoff import UnifiedCommandCenterSignoffStore

    center_store = UnifiedCommandCenterStore()
    signoff_store = UnifiedCommandCenterSignoffStore(center_store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    store = UnifiedCommandCenterContinuousReviewStore(center_store, signoff_store=signoff_store, handoff_store=handoff_store)
    payload = _unified_command_center_review_payload_from_args(args)
    if args.action == "create":
        plan = store.create_plan(args.center_id, payload)
        return {"ok": True, "plan": plan, "summary": {"review_id": plan.get("review_id")}, "status": plan.get("status")}
    if args.action == "list":
        rows = store.list_reviews(args.center_id)
        return {"ok": True, "reviews": rows, "summary": {"review_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.read_review(args.center_id, args.review_id)
        drift = docs.get("drift_report") or {}
        return {"ok": bool(docs), "review": docs, "summary": drift.get("summary", {}), "status": drift.get("status") or docs.get("plan", {}).get("status")}
    if args.action == "run":
        result = store.run_review(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result}
    if args.action == "export":
        result = store.export_package(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}).get("summary", {})}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.center_id,
            args.review_id,
            {
                **payload,
                "strict": args.strict,
                "require_clear": args.require_clear,
                "require_recovery_drill": args.require_recovery_drill,
                "require_current_review": args.require_current_review,
            },
        )
        if args.report_out is not None:
            write_unified_command_center_continuous_review_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-review command.")

def _unified_command_center_drift_response_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "response_id": getattr(args, "response_id", None),
        "source_review_id": getattr(args, "source_review_id", None),
        "created_by": getattr(args, "created_by", None),
        "source_review_zip": getattr(args, "source_review_zip", None),
        "source_review_verification_report": getattr(args, "source_review_verification_report", None),
        "recheck_review_zip": getattr(args, "recheck_review_zip", None),
        "recheck_review_verification_report": getattr(args, "recheck_review_verification_report", None),
        "change_request_binding_report": getattr(args, "change_request_binding_report", None),
        "archive_zip": getattr(args, "archive_zip", None),
        "archive_verification_report": getattr(args, "archive_verification_report", None),
        "handoff_zip": getattr(args, "handoff_zip", None),
        "handoff_verification_report": getattr(args, "handoff_verification_report", None),
        "command_center_zip": getattr(args, "command_center_zip", None),
        "command_center_verification_report": getattr(args, "command_center_verification_report", None),
        "signoff_binding": getattr(args, "signoff_binding", None),
    }

def _run_unified_command_center_drift_response_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center import UnifiedCommandCenterStore
    from song_agent.unified_command_center_drift_response import UnifiedCommandCenterDriftResponseStore
    from song_agent.unified_command_center_drift_response_verifier import write_unified_command_center_drift_response_verification_report
    from song_agent.unified_command_center_handoff import UnifiedCommandCenterHandoffStore
    from song_agent.unified_command_center_signoff import UnifiedCommandCenterSignoffStore

    center_store = UnifiedCommandCenterStore()
    signoff_store = UnifiedCommandCenterSignoffStore(center_store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    store = UnifiedCommandCenterDriftResponseStore(center_store, signoff_store=signoff_store, handoff_store=handoff_store)
    payload = _unified_command_center_drift_response_payload_from_args(args)
    if args.action == "create":
        result = store.create_response(args.center_id, payload)
        case = result.get("case", {})
        return {"ok": True, **result, "summary": {"response_id": case.get("response_id")}, "status": case.get("status")}
    if args.action == "list":
        rows = store.list_responses(args.center_id)
        return {"ok": True, "responses": rows, "summary": {"response_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.read_response(args.center_id, args.response_id)
        closeout = docs.get("closeout") or {}
        return {"ok": True, "response": docs, "summary": closeout.get("summary", {}), "status": closeout.get("status") or docs.get("case", {}).get("status")}
    if args.action == "run-safe":
        result = store.run_safe(args.center_id, args.response_id, payload)
        failed = int((result.get("summary") or {}).get("failed_count") or 0)
        return {"ok": failed == 0, "action_results": result, "summary": result.get("summary", {}), "status": "passed" if failed == 0 else "failed"}
    if args.action == "bind-cr":
        result = store.bind_change_request(
            args.center_id,
            args.response_id,
            {"item_id": args.item_id, "change_request_id": args.change_request_id, "status": "approved", "approved_by": args.approved_by, "reason": args.reason},
        )
        return {"ok": True, "change_request_bindings": result, "summary": result.get("summary", {}), "status": "passed"}
    if args.action == "bind-recheck":
        result = store.bind_recheck(
            args.center_id,
            args.response_id,
            {"recheck_review_id": args.recheck_review_id, "recheck_review_zip": args.recheck_review_zip, "recheck_review_verification_report": args.recheck_review_verification_report},
        )
        return {"ok": result.get("status") == "passed", "recheck": result, "summary": result.get("summary", {}), "status": result.get("status")}
    if args.action == "closeout":
        result = store.closeout(args.center_id, args.response_id, {"closed_by": args.closed_by, "reason": args.reason})
        return {"ok": result.get("status") == "closed", "closeout": result, "summary": result.get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_package(args.center_id, args.response_id, payload)
        return {"ok": result.get("status") == "closed", **result, "summary": result.get("manifest", {}).get("summary", {})}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.response_id, payload)
        return {"ok": result.get("status") == "closed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.center_id,
            args.response_id,
            {
                **payload,
                "strict": args.strict,
                "require_closed": args.require_closed,
                "require_recheck_clear": args.require_recheck_clear,
                "require_current_review": args.require_current_review,
            },
        )
        if args.report_out is not None:
            write_unified_command_center_drift_response_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-drift-response command.")

def _unified_command_center_evidence_review_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "review_id": getattr(args, "review_id", None),
        "ucc_zip": getattr(args, "ucc_zip", None),
        "ucc_verification_report": getattr(args, "ucc_verification_report", None),
        "archive_zip": getattr(args, "archive_zip", None),
        "archive_verification_report": getattr(args, "archive_verification_report", None),
        "handoff_zip": getattr(args, "handoff_zip", None),
        "handoff_verification_report": getattr(args, "handoff_verification_report", None),
        "continuous_review_id": getattr(args, "continuous_review_id", None),
        "continuous_review_zip": getattr(args, "continuous_review_zip", None),
        "continuous_review_verification_report": getattr(args, "continuous_review_verification_report", None),
        "source_review_zip": getattr(args, "source_review_zip", None),
        "source_review_verification_report": getattr(args, "source_review_verification_report", None),
        "recheck_review_id": getattr(args, "recheck_review_id", None),
        "recheck_review_zip": getattr(args, "recheck_review_zip", None),
        "recheck_review_verification_report": getattr(args, "recheck_review_verification_report", None),
        "drift_response_id": getattr(args, "drift_response_id", None),
        "drift_response_zip": getattr(args, "drift_response_zip", None),
        "drift_response_verification_report": getattr(args, "drift_response_verification_report", None),
        "drift_change_request_binding_report": getattr(args, "drift_change_request_binding_report", None),
        "signoff_binding": getattr(args, "signoff_binding", None),
        "ga_readiness_report": getattr(args, "ga_readiness_report", None),
        "release_check_report": getattr(args, "release_check_report", None),
    }

def _run_unified_command_center_evidence_review_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center_evidence_review import UnifiedCommandCenterEvidenceReviewStore
    from song_agent.unified_command_center_evidence_review_verifier import (
        write_unified_command_center_evidence_review_acceptance_verification_report,
        write_unified_command_center_evidence_review_verification_report,
    )

    store = UnifiedCommandCenterEvidenceReviewStore()
    payload = _unified_command_center_evidence_review_payload_from_args(args)
    if args.action == "create":
        docs = store.create_review(args.center_id, payload)
        return {"ok": True, "review": docs, "summary": {"review_id": docs.get("source", {}).get("review_id")}, "status": docs.get("source", {}).get("status")}
    if args.action == "list":
        rows = store.list_reviews(args.center_id)
        return {"ok": True, "reviews": rows, "summary": {"review_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.get_review(args.center_id, args.review_id)
        replay = docs.get("replay_result") or {}
        return {"ok": True, "review": docs, "summary": replay.get("summary", {}), "status": replay.get("status") or docs.get("source", {}).get("status")}
    if args.action == "refresh":
        docs = store.refresh_review(args.center_id, args.review_id, payload)
        return {"ok": True, "review": docs, "summary": {"review_id": args.review_id}, "status": docs.get("source", {}).get("status")}
    if args.action == "replay":
        replay = store.run_replay(args.center_id, args.review_id, payload)
        return {"ok": replay.get("status") == "passed", "replay_result": replay, "summary": replay.get("summary", {}), "status": replay.get("status")}
    if args.action == "export":
        result = store.export_review(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"manifest_hash": result.get("manifest_hash")}}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(args.center_id, args.review_id, {**payload, "strict": args.strict, "require_replay_passed": args.require_replay_passed})
        if args.report_out is not None:
            write_unified_command_center_evidence_review_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "import-response":
        if args.response_json:
            payload = read_json(args.response_json)
        else:
            payload = {"response_base64": args.response_base64}
        response = store.import_response(args.center_id, args.review_id, payload)
        return {"ok": response.get("status") == "current", "response": response, "summary": {"response_id": response.get("response_id")}, "status": response.get("status")}
    if args.action == "acceptance-evidence":
        result = store.create_acceptance_evidence(args.center_id, args.review_id, args.response_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"evidence_id": result.get("evidence_id")}}
    if args.action == "verify-acceptance":
        report = store.verify_acceptance_evidence(args.center_id, args.review_id, args.evidence_id, {"strict": args.strict, "require_accepted": args.require_accepted})
        if args.report_out is not None:
            write_unified_command_center_evidence_review_acceptance_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-evidence-review command.")

def _unified_command_center_reviewer_decision_board_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    accepted_zips = list(getattr(args, "accepted_evidence", []) or [])
    accepted_reports = list(getattr(args, "accepted_evidence_verification_report", []) or [])
    accepted_response_reports = list(getattr(args, "accepted_evidence_response_verification_report", []) or [])
    accepted_rows = []
    for index, zip_path in enumerate(accepted_zips):
        accepted_rows.append(
            {
                "zip_path": zip_path,
                "verification_report_path": accepted_reports[index] if index < len(accepted_reports) else None,
                "response_verification_report_path": accepted_response_reports[index] if index < len(accepted_response_reports) else None,
            }
        )
    policy: dict[str, Any] = {}
    if getattr(args, "required_role", None):
        policy["required_roles"] = list(args.required_role)
    if getattr(args, "min_accepted_count", None) is not None:
        policy["min_accepted_count"] = args.min_accepted_count
    if getattr(args, "min_organization_count", None) is not None:
        policy["min_organization_count"] = args.min_organization_count
    return {
        "board_id": getattr(args, "board_id", None),
        "review_id": getattr(args, "review_id", None),
        "review_zip": getattr(args, "review_zip", None),
        "review_verification_report": getattr(args, "review_verification_report", None),
        "accepted_evidence": accepted_rows,
        "policy": policy,
    }

def _run_unified_command_center_reviewer_decision_board_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center_reviewer_decision_board import UnifiedCommandCenterReviewerDecisionBoardStore
    from song_agent.unified_command_center_reviewer_decision_board_verifier import write_unified_command_center_reviewer_decision_board_verification_report

    store = UnifiedCommandCenterReviewerDecisionBoardStore()
    payload = _unified_command_center_reviewer_decision_board_payload_from_args(args)
    if args.action == "create":
        docs = store.create_board(args.center_id, payload)
        return {"ok": docs.get("decision_report", {}).get("status") == "ready_for_signoff", "board": docs, "summary": docs.get("decision_report", {}).get("summary", {}), "status": docs.get("decision_report", {}).get("status")}
    if args.action == "list":
        rows = store.list_boards(args.center_id)
        return {"ok": True, "boards": rows, "summary": {"board_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.get_board(args.center_id, args.board_id)
        return {"ok": True, "board": docs, "summary": docs.get("decision_report", {}).get("summary", {}), "status": docs.get("decision_report", {}).get("status") or docs.get("source", {}).get("status")}
    if args.action == "refresh":
        docs = store.refresh_board(args.center_id, args.board_id, payload)
        return {"ok": docs.get("decision_report", {}).get("status") == "ready_for_signoff", "board": docs, "summary": docs.get("decision_report", {}).get("summary", {}), "status": docs.get("decision_report", {}).get("status")}
    if args.action == "signoff":
        signoff = store.signoff(args.center_id, args.board_id, {**payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "export":
        result = store.export_archive(args.center_id, args.board_id, payload)
        return {"ok": result.get("status") == "signed", **result, "summary": {"manifest_hash": result.get("manifest_hash")}}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.board_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_archive(args.center_id, args.board_id, {**payload, "strict": args.strict, "require_signed": args.require_signed, "require_quorum": args.require_quorum})
        if args.report_out is not None:
            write_unified_command_center_reviewer_decision_board_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-reviewer-decision-board command.")

def _run_unified_command_center_release_train_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore
    from song_agent.domains.program.unified_command_center_release_train_verifier import write_unified_command_center_release_train_verification_report

    store = UnifiedCommandCenterReleaseTrainStore()
    if args.action == "create":
        train = store.create_train(
            {
                "train_id": args.train_id,
                "name": args.name,
                "profile": args.profile,
                "allow_duplicate_center": args.allow_duplicate_center,
                "required_evidence": args.required_evidence,
            }
        )
        return {"ok": True, "train": train, "summary": {"train_id": train.get("train_id")}, "status": train.get("status")}
    if args.action == "list":
        trains = store.list_trains()
        return {"ok": True, "trains": trains, "summary": {"train_count": len(trains)}, "status": "passed"}
    if args.action == "add-item":
        item = store.add_item(
            args.train_id,
            {
                "item_id": args.item_id,
                "center_id": args.center_id,
                "label": args.label,
                "wave": args.wave,
                "depends_on": args.depends_on,
                "allow_duplicate_center": args.allow_duplicate_center,
                "required_evidence": args.required_evidence,
            },
        )
        return {"ok": True, "item": item, "summary": {"item_id": item.get("item_id")}, "status": item.get("status")}
    if args.action == "status":
        docs = store.read_docs(args.train_id) if store.report_path(args.train_id).exists() else {"train": store.read_train(args.train_id)}
        report = docs.get("report", {})
        return {"ok": True, "train": docs.get("train"), "report": report, "summary": report.get("summary", {}), "status": report.get("status") or docs.get("train", {}).get("status")}
    payload = {"external_evidence_manifest": getattr(args, "external_evidence_manifest", None)}
    if args.action == "refresh":
        report = store.refresh(args.train_id, payload)
        return {"ok": report.get("status") == "go", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "run-safe":
        result = store.run_safe(args.train_id, payload)
        failed = int((result.get("summary") or {}).get("failed_count") or 0)
        return {"ok": failed == 0, "runbook_result": result, "summary": result.get("summary", {}), "status": "passed" if failed == 0 else "failed"}
    if args.action == "signoff":
        signoff = store.signoff(args.train_id, {**payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "export":
        manifest = store.export_archive(args.train_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_archive(args.train_id, {**payload, "strict": args.strict, "require_go": args.require_go, "require_signed": args.require_signed, "signoff_binding": args.signoff_binding})
        if args.report_out is not None:
            write_unified_command_center_release_train_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train command.")

def _run_unified_command_center_release_train_change_control_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore
    from song_agent.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore
    from song_agent.domains.program.unified_command_center_release_train_change_control_verifier import write_unified_command_center_release_train_change_control_verification_report

    train_store = UnifiedCommandCenterReleaseTrainStore()
    store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    if args.action == "create-request":
        request = store.create_request(
            args.train_id,
            {
                "change_request_id": args.request_id,
                "requested_by": args.requested_by,
                "reason": args.reason,
                "change_type": args.change_type,
                "change_set": args.change,
                "external_evidence_manifest": args.external_evidence_manifest,
            },
        )
        return {"ok": True, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}
    if args.action == "approve":
        approval = store.approve_request(
            args.train_id,
            args.request_id,
            {
                "approved_by": args.approved_by,
                "role": args.role,
                "reason": args.reason,
                "external_evidence_manifest": args.external_evidence_manifest,
            },
        )
        return {"ok": approval.get("status") == "approved", "approval": approval, "summary": {"approval_hash": approval.get("integrity_hash")}, "status": approval.get("status")}
    if args.action == "reset":
        proof = store.reset_train_signoff(
            args.train_id,
            args.request_id,
            {
                "reset_by": args.reset_by,
                "reason": args.reason,
                "external_evidence_manifest": args.external_evidence_manifest,
            },
        )
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_event_hash": proof.get("reset_event_hash")}, "status": proof.get("status")}
    if args.action == "status":
        report = store.refresh_report(args.train_id) if store.change_dir(args.train_id).exists() else {"status": "not_configured", "summary": {}}
        return {"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_package(args.train_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.train_id,
            {
                "strict": args.strict,
                "require_reset_applied": args.require_reset_applied,
                "require_current_train": args.require_current_train,
                "train_archive": args.train_archive,
                "train_archive_verification_report": args.train_archive_verification_report,
                "train_signoff_binding": args.train_signoff_binding,
                "external_evidence_manifest": args.external_evidence_manifest,
                "reset_proof": args.reset_proof,
            },
        )
        if args.report_out is not None:
            write_unified_command_center_release_train_change_control_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train-change-control command.")

def _run_unified_command_center_release_train_lifecycle_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore
    from song_agent.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore
    from song_agent.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore
    from song_agent.domains.program.unified_command_center_release_train_lifecycle_verifier import write_unified_command_center_release_train_lifecycle_verification_report

    train_store = UnifiedCommandCenterReleaseTrainStore()
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    store = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    if args.action == "status":
        report = store.read_report(args.train_id) if store.report_path(args.train_id).exists() else {"status": "not_configured", "summary": {}}
        return {"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    payload = _release_train_lifecycle_payload_from_args(args)
    if args.action == "refresh":
        report = store.refresh_report(args.train_id, payload)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_package(args.train_id, payload)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.train_id,
            {**payload, "strict": args.strict, "require_current_train": args.require_current_train, "require_change_control": args.require_change_control},
        )
        if args.report_out is not None:
            write_unified_command_center_release_train_lifecycle_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train-lifecycle command.")

def _run_unified_command_center_release_train_handoff_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.projectio import read_json
    from song_agent.unified_command_center_release_train import UnifiedCommandCenterReleaseTrainStore
    from song_agent.unified_command_center_release_train_change_control import UnifiedCommandCenterReleaseTrainChangeControlStore
    from song_agent.unified_command_center_release_train_handoff import UnifiedCommandCenterReleaseTrainHandoffStore
    from song_agent.domains.program.unified_command_center_release_train_handoff_verifier import write_unified_command_center_release_train_handoff_verification_report
    from song_agent.unified_command_center_release_train_lifecycle import UnifiedCommandCenterReleaseTrainLifecycleStore

    train_store = UnifiedCommandCenterReleaseTrainStore()
    change_store = UnifiedCommandCenterReleaseTrainChangeControlStore(train_store)
    lifecycle_store = UnifiedCommandCenterReleaseTrainLifecycleStore(train_store, change_store)
    store = UnifiedCommandCenterReleaseTrainHandoffStore(train_store, change_store, lifecycle_store)
    handoff_id = getattr(args, "handoff_id", None)
    if args.action == "status":
        detail = store.get_handoff(args.train_id, handoff_id)
        report = detail.get("report", {})
        return {"ok": report.get("status") != "failed", **detail, "summary": report.get("summary", {}), "status": report.get("status")}
    payload = _release_train_handoff_payload_from_args(args)
    if args.action == "create":
        if getattr(args, "handoff_id", None):
            payload["handoff_id"] = args.handoff_id
        if getattr(args, "require_external_acceptance", False):
            payload["policy"] = {"require_external_acceptance": True}
        detail = store.create_handoff(args.train_id, payload)
        return {"ok": detail.get("report", {}).get("status") in {"ready", "manual_required"}, **detail, "summary": detail.get("report", {}).get("summary", {}), "status": detail.get("report", {}).get("status")}
    if args.action in {"refresh", "board"}:
        report = store.refresh_report(args.train_id, handoff_id, payload)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_handoff(args.train_id, handoff_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id, handoff_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.train_id,
            handoff_id,
            {
                **payload,
                "strict": args.strict,
                "require_current": args.require_current,
                "require_lifecycle": args.require_lifecycle,
                "require_signed": args.require_signed,
                "require_accepted": args.require_accepted,
                "handoff_signoff_binding": getattr(args, "handoff_signoff_binding", None),
                "accepted_evidence_dir": getattr(args, "accepted_evidence_dir", None),
            },
        )
        if args.report_out is not None:
            write_unified_command_center_release_train_handoff_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "import-response":
        response = store.import_response(args.train_id, args.handoff_id, read_json(args.response_json))
        return {"ok": response.get("verification", {}).get("status") == "passed", **response, "summary": response.get("verification", {}).get("summary", {}), "status": response.get("response", {}).get("decision")}
    if args.action == "accepted-evidence":
        evidence = store.create_accepted_evidence(args.train_id, args.handoff_id, args.response_id)
        return {"ok": True, "accepted_evidence": evidence, "summary": evidence.get("public_summary", {}), "status": "passed"}
    if args.action == "signoff":
        signoff = store.signoff(args.train_id, handoff_id, {**payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signed_by": signoff.get("signed_by")}, "status": signoff.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train-handoff command.")

def _run_unified_release_program_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.domains.program.unified_release_program_verifier import write_unified_release_program_verification_report

    store = _program_component("program")
    if args.action == "create":
        policy = {}
        if getattr(args, "require_external_handoff_acceptance", False):
            policy["require_external_handoff_acceptance"] = True
        return {"program": store.create_program({"program_id": args.program_id, "name": args.name, "policy": policy})}
    if args.action == "add-train":
        return {
            "item": store.add_train_item(
                args.program_id,
                {
                    "item_id": args.item_id,
                    "train_id": args.train_id,
                    "handoff_id": args.handoff_id,
                    "type": args.type,
                    "lane": args.lane,
                    "wave": args.wave,
                    "depends_on": args.depends_on,
                    "handoff_zip": args.handoff_zip,
                    "handoff_verification_report": args.handoff_verification_report,
                    "handoff_signoff_binding": args.handoff_signoff_binding,
                    "accepted_evidence_dir": args.accepted_evidence_dir,
                },
            )
        }
    if args.action == "status":
        return store.get_program(args.program_id)
    if args.action == "refresh":
        return {"report": store.refresh_report(args.program_id, {"external_evidence_manifest": args.external_evidence_manifest})}
    if args.action == "export":
        return {"manifest": store.export_program(args.program_id)}
    if args.action == "zip":
        return {"zip": store.build_zip(args.program_id)}
    if args.action == "verify":
        report = store.verify_package(
            args.program_id,
            {
                "strict": args.strict,
                "require_current": args.require_current,
                "require_signed": args.require_signed,
                "external_evidence_manifest": args.external_evidence_manifest,
                "program_signoff_binding": args.program_signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_verification_report(report, args.report_out)
        return {"verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "signoff":
        return {"signoff": store.signoff(args.program_id, {"external_evidence_manifest": args.external_evidence_manifest, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})}
    if args.action == "gate":
        return {
            "gate": store.gate(
                program_zip_path=args.program_zip,
                verification_report_path=args.program_verification_report,
                external_evidence_manifest_path=args.external_evidence_manifest,
                program_signoff_binding_path=args.program_signoff_binding,
            )
        }
    raise ValueError("Unsupported unified-release-program command.")

def _run_unified_release_program_operations_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.domains.program.unified_release_program_operations_verifier import write_unified_release_program_operations_verification_report


    store = _program_component("operations")
    payload = _unified_release_program_operations_payload_from_args(args)
    program_id = getattr(args, "program_id", None)
    if args.action == "change-request-create":
        request = store.create_change_request(program_id, payload)
        return {"ok": True, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}
    if args.action == "change-request-approve":
        approval = store.approve_change_request(program_id, args.change_request_id, payload)
        return {"ok": True, "approval": approval, "summary": {"change_request_id": approval.get("change_request_id")}, "status": approval.get("status")}
    if args.action == "reset-signoff":
        proof = store.reset_program_signoff(program_id, payload)
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_event_hash": proof.get("reset_event_hash")}, "status": proof.get("status")}
    if args.action == "runbook-create":
        runbook = store.create_runbook(program_id, payload)
        return {"ok": True, "runbook": runbook, "summary": runbook.get("summary", {}), "status": runbook.get("status")}
    if args.action == "runbook-run-safe":
        result = store.run_safe(program_id, args.runbook_id, payload)
        return {"ok": result.get("status") in {"completed", "completed_with_manual_actions"}, **result}
    if args.action == "continuous-review-refresh":
        review = store.refresh_continuous_review(program_id, payload)
        return {"ok": review.get("status") == "passed", "review": review, "summary": review.get("summary", {}), "status": review.get("status")}
    if args.action == "lifecycle-refresh":
        report = store.refresh_lifecycle_audit(program_id, payload)
        return {"ok": report.get("status") == "passed", "lifecycle": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "archive-export":
        manifest = store.export_operations_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_operations_archive_zip(program_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "archive-verify":
        report = store.verify_operations_archive_zip(
            program_id,
            {
                **payload,
                "strict": args.strict,
                "require_current": args.require_current,
                "require_signed_program": args.require_signed_program,
                "require_continuous_review_clear": args.require_continuous_review_clear,
                "require_lifecycle_audit": args.require_lifecycle_audit,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_operations_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            args.program_id,
            required=True,
            operations_archive_zip_path=args.operations_archive_zip,
            operations_archive_verification_report_path=args.operations_archive_verification_report,
            **payload,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-operations command.")

def _unified_release_program_operations_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "program_zip": getattr(args, "program_zip", None),
        "program_verification_report": getattr(args, "program_verification_report", None),
        "program_signoff_binding": getattr(args, "program_signoff_binding", None),
        "external_evidence_manifest": getattr(args, "external_evidence_manifest", None),
    }
    for name in ("change_request_id", "change_type", "reason", "requested_by", "approved_by", "role", "reset_by", "allowed_actions"):
        value = getattr(args, name, None)
        if value is not None:
            payload[name] = value
    return payload

def _run_unified_release_program_handoff_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.projectio import read_json
    from song_agent.domains.program.unified_release_program_handoff_verifier import (
        write_unified_release_program_accepted_evidence_verification_report,
        write_unified_release_program_handoff_verification_report,
        write_unified_release_program_review_pack_verification_report,
    )

    store = _program_component("handoff")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_handoff(program_id)
        status = (detail.get("report") or {}).get("status") or "unknown"
        return {"ok": True, **detail, "summary": (detail.get("report") or {}).get("summary", {}), "status": status}
    if args.action == "refresh":
        report = store.refresh_handoff(program_id, {"external_evidence_manifest": args.external_evidence_manifest})
        return {"ok": report.get("status") in {"ready_for_review", "ready_for_signoff"}, "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "review-pack":
        pack = store.export_review_pack(program_id, {"review_pack_id": args.review_pack_id, "audience": args.audience})
        return {"ok": pack.get("status") == "ready", "review_pack": pack, "summary": {"review_pack_id": pack.get("review_pack_id")}, "status": pack.get("status")}
    if args.action == "review-pack-zip":
        result = store.build_review_pack_zip(program_id, args.review_pack_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "review-pack-verify":
        report = store.verify_review_pack_zip(program_id, args.review_pack_id, {"strict": args.strict})
        if args.report_out is not None:
            write_unified_release_program_review_pack_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "import-response":
        response = store.import_response(program_id, read_json(args.response_json))
        return {"ok": response.get("status") in {"accepted", "accepted_with_notes"}, "response": response.get("response"), "verification": response.get("verification"), "summary": {"response_id": response.get("response", {}).get("response_id")}, "status": response.get("status")}
    if args.action == "accepted-evidence":
        result = store.create_accepted_evidence(program_id, args.response_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"evidence_id": result.get("evidence", {}).get("evidence_id")}}
    if args.action == "accepted-evidence-zip":
        result = store.build_accepted_evidence_zip(program_id, args.evidence_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "accepted-evidence-verify":
        report = store.verify_accepted_evidence_zip(
            program_id,
            args.evidence_id,
            {
                "strict": args.strict,
                "require_accepted": args.require_accepted,
                "response_verification_report": args.response_verification_report,
                "response_binding_summary": args.response_binding_summary,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_accepted_evidence_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "decision-board":
        policy: dict[str, Any] = {}
        if args.required_roles is not None:
            policy["required_roles"] = args.required_roles
        if args.minimum_acceptances is not None:
            policy["minimum_acceptances"] = args.minimum_acceptances
        if args.minimum_organizations is not None:
            policy["minimum_organizations"] = args.minimum_organizations
        board = store.refresh_decision_board(program_id, {"policy": policy} if policy else {})
        return {"ok": board.get("status") == "ready_for_signoff", "decision_board": board, "summary": board.get("readiness", {}), "status": board.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_handoff(program_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive-export":
        manifest = store.export_handoff_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_handoff_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "archive-verify":
        report = store.verify_handoff_archive_zip(
            program_id,
            {
                "strict": args.strict,
                "require_current": args.require_current,
                "require_accepted": args.require_accepted,
                "require_signed": args.require_signed,
                "external_evidence_manifest": args.external_evidence_manifest,
                "handoff_signoff_binding": args.handoff_signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_handoff_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            handoff_archive_zip_path=args.handoff_archive_zip,
            handoff_archive_verification_report_path=args.handoff_archive_verification_report,
            external_evidence_manifest=args.external_evidence_manifest,
            handoff_signoff_binding=args.handoff_signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-handoff command.")

def _run_unified_release_program_vault_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.domains.program.unified_release_program_vault_verifier import write_unified_release_program_vault_verification_report

    store = _program_component("vault")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_vault(program_id)
        status = (detail.get("report") or {}).get("status") or "unknown"
        return {"ok": True, **detail, "summary": (detail.get("report") or {}).get("summary", {}), "status": status}
    if args.action == "refresh":
        report = store.refresh_vault(program_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_vault(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_vault_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "anchor_path": result.get("anchor_path")}}
    if args.action == "verify":
        report = store.verify_vault_zip(
            program_id,
            {
                "strict": args.strict,
                "deep": args.deep,
                "require_anchor": args.require_anchor,
                "vault_anchor": args.vault_anchor,
                "require_current_program": args.require_current_program,
                "require_current_operations": args.require_current_operations,
                "require_current_handoff": args.require_current_handoff,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_vault_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            vault_zip_path=args.vault_zip,
            vault_verification_report_path=args.vault_verification_report,
            vault_anchor_path=args.vault_anchor,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-vault command.")

def _run_unified_release_program_vault_operations_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.domains.program.unified_release_program_vault_operations_verifier import write_unified_release_program_vault_operations_verification_report

    store = _program_component("vault_operations")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_operations(program_id)
        report = detail.get("report") or {}
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or (detail.get("signoff_state") or {}).get("status") or "unknown"}
    if args.action == "init-policy":
        policy = store.init_policy(program_id, {"review_interval_days": args.review_interval_days})
        return {"ok": policy.get("status") == "active", "policy": policy, "summary": {"policy_hash": policy.get("integrity_hash")}, "status": policy.get("status")}
    if args.action == "register-vault":
        registry = store.register_vault(program_id, {"vault_zip": args.vault_zip, "vault_anchor": args.vault_anchor, "vault_verification_report": args.vault_verification_report})
        return {"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "refresh-registry":
        registry = store.refresh_registry(program_id)
        return {"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "review":
        review = store.run_custody_review(program_id)
        return {"ok": review.get("status") == "passed", "review": review, "summary": review.get("summary", {}), "status": review.get("status")}
    if args.action == "rotation-plan":
        plan = store.create_rotation_plan(program_id, {"force_rotation": args.force_rotation, "reason": args.reason})
        return {"ok": plan.get("status") in {"not_required", "required"}, "rotation_plan": plan, "summary": {"plan_id": plan.get("plan_id")}, "status": plan.get("status")}
    if args.action == "supersede":
        registry = store.supersede_vault(program_id, {"old_generation_id": args.old_generation_id, "new_generation_id": args.new_generation_id, "vault_zip": args.vault_zip, "vault_anchor": args.vault_anchor, "vault_verification_report": args.vault_verification_report})
        return {"ok": registry.get("status") == "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "revoke":
        registry = store.revoke_vault(program_id, {"generation_id": args.generation_id, "reason": args.reason})
        return {"ok": registry.get("status") != "current", "registry": registry, "summary": registry.get("summary", {}), "status": registry.get("status")}
    if args.action == "transfer-pack":
        transfer = store.create_transfer_pack(program_id, {"recipient": args.recipient})
        return {"ok": transfer.get("status") == "ready", "transfer_report": transfer, "summary": transfer.get("summary", {}), "status": transfer.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_operations(program_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive-export":
        manifest = store.export_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "archive-verify":
        report = store.verify_archive_zip(
            program_id,
            {
                "strict": args.strict,
                "deep": args.deep,
                "require_signed": args.require_signed,
                "require_current_vault": args.require_current_vault,
                "signoff_binding": args.signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_vault_operations_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(program_id, required=True, archive_zip_path=args.archive_zip, verification_report_path=args.verification_report, signoff_binding_path=args.signoff_binding)
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-vault-ops command.")

def _run_unified_release_program_continuity_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.domains.program.unified_release_program_continuity_verifier import write_unified_release_program_continuity_verification_report

    store = _program_component("continuity")
    program_id = args.program_id
    evidence_payload = {
        "vault_operations_archive": getattr(args, "vault_operations_archive", None),
        "vault_operations_verification_report": getattr(args, "vault_operations_verification_report", None),
        "vault_operations_signoff_binding": getattr(args, "vault_operations_signoff_binding", None),
    }
    if args.action == "status":
        detail = store.get_continuity(program_id)
        report = detail.get("report") or {}
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or (detail.get("signoff_state") or {}).get("status") or "unknown"}
    if args.action == "init-policy":
        policy = store.init_policy(program_id, {})
        return {"ok": policy.get("status") == "active", "policy": policy, "summary": {"policy_hash": policy.get("integrity_hash")}, "status": policy.get("status")}
    if args.action == "plan":
        plan = store.create_recovery_plan(program_id, evidence_payload)
        return {"ok": plan.get("status") == "planned", "recovery_plan": plan, "summary": {"plan_hash": plan.get("integrity_hash")}, "status": plan.get("status")}
    if args.action == "drill":
        drill = store.run_recovery_drill(program_id, evidence_payload)
        return {"ok": drill.get("status") == "passed", "drill_report": drill, "summary": drill.get("summary", {}), "status": drill.get("status")}
    if args.action == "readiness":
        readiness = store.refresh_readiness(program_id, evidence_payload)
        return {"ok": readiness.get("status") == "passed", "readiness": readiness, "summary": readiness.get("summary", {}), "status": readiness.get("status")}
    if args.action == "runbook":
        runbook = store.generate_runbook(program_id, {})
        return {"ok": runbook.get("status") == "ready", "runbook": runbook, "summary": runbook.get("summary", {}), "status": runbook.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_continuity(program_id, {**evidence_payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive-export":
        manifest = store.export_archive(program_id, {})
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "archive-zip":
        result = store.build_archive_zip(program_id, {})
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "archive-verify":
        report = store.verify_archive_zip(
            program_id,
            {
                **evidence_payload,
                "strict": args.strict,
                "deep_restore": args.deep_restore,
                "require_signed": args.require_signed,
                "require_current_vault_operations": args.require_current_vault_operations,
                "signoff_binding": args.signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            signoff_binding_path=args.signoff_binding,
            vault_operations_archive_path=args.vault_operations_archive,
            vault_operations_verification_report_path=args.vault_operations_verification_report,
            vault_operations_signoff_binding_path=args.vault_operations_signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity command.")

def _run_unified_release_program_continuity_distribution_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.projectio import read_json
    from song_agent.domains.program.unified_release_program_continuity_distribution_verifier import write_unified_release_program_continuity_distribution_verification_report

    store = _program_component("continuity_distribution")
    program_id = args.program_id
    evidence_payload = {
        "continuity_archive": getattr(args, "continuity_archive", None),
        "continuity_verification_report": getattr(args, "continuity_verification_report", None),
        "continuity_signoff_binding": getattr(args, "continuity_signoff_binding", None),
        "vault_operations_archive": getattr(args, "vault_operations_archive", None),
        "vault_operations_verification_report": getattr(args, "vault_operations_verification_report", None),
        "vault_operations_signoff_binding": getattr(args, "vault_operations_signoff_binding", None),
        "evidence_vault": getattr(args, "evidence_vault", None),
        "vault_verification_report": getattr(args, "vault_verification_report", None),
        "vault_anchor": getattr(args, "vault_anchor", None),
    }
    if args.action == "status":
        detail = store.get_kit(program_id)
        source = detail.get("source_binding") or {}
        return {"ok": True, **detail, "summary": source, "status": source.get("status") or "unknown"}
    if args.action == "prepare":
        source = store.prepare_kit(program_id, evidence_payload)
        return {"ok": source.get("status") == "passed", "source_binding": source, "summary": source, "status": source.get("status")}
    if args.action == "export":
        manifest = store.export_kit(program_id, evidence_payload)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_kit_zip(program_id, evidence_payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_kit(program_id, {**evidence_payload, "strict": args.strict, "deep": args.deep, "require_receiver_receipt": args.require_receiver_receipt, "receiver_receipt": args.receiver_receipt})
        if args.report_out is not None:
            write_unified_release_program_continuity_distribution_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(program_id, required=True, kit_zip_path=args.kit_zip, verification_report_path=args.verification_report, require_receiver_receipt=args.require_receiver_receipt, receiver_receipt_path=args.receiver_receipt)
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    if args.action == "receipt-template":
        template = store.create_receiver_receipt_template(program_id)
        return {"ok": True, "receiver_receipt_template": template, "summary": {"kit_sha256": template.get("kit_sha256")}, "status": "passed"}
    if args.action == "import-receipt":
        receipt = store.import_receiver_receipt(program_id, read_json(args.receipt_json))
        return {"ok": receipt.get("decision") == "accepted", "receiver_receipt": receipt, "summary": {"receipt_id": receipt.get("receipt_id")}, "status": receipt.get("decision")}
    if args.action == "verify-receipt":
        report = store.verify_receiver_receipt(program_id, args.receipt_id)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-kit command.")

def _run_unified_release_program_continuity_acceptance_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.projectio import read_json
    from song_agent.domains.program.unified_release_program_continuity_acceptance_verifier import write_unified_release_program_continuity_acceptance_verification_report

    store = _program_component("continuity_acceptance")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_board(program_id)
        report = detail.get("report") or {}
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or "unknown"}
    if args.action == "import-response":
        result = store.import_response(
            program_id,
            {
                "response": read_json(args.response_json),
                "response_verification_report": read_json(args.response_verification_report),
                "response_binding_summary": read_json(args.response_binding_summary),
            },
        )
        return {"ok": result.get("status") == "imported", **result, "summary": {"response_id": result.get("response", {}).get("response_id")}, "status": result.get("status")}
    if args.action == "accept-evidence":
        result = store.create_accepted_evidence(program_id, args.response_id)
        return {"ok": result.get("status") == "accepted", **result, "summary": {"evidence_id": result.get("evidence", {}).get("evidence_id")}, "status": result.get("status")}
    if args.action == "board":
        policy = read_json(args.policy_json) if args.policy_json else None
        board = store.refresh_decision_board(program_id, {"policy": policy} if policy else {})
        return {"ok": board.get("status") == "ready_for_signoff", "board": board, "summary": board.get("readiness", {}), "status": board.get("status")}
    if args.action == "signoff":
        signoff = store.signoff_acceptance(program_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "export":
        manifest = store.export_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_archive_zip(
            program_id,
            {
                "archive_zip": args.archive_zip,
                "strict": args.strict,
                "require_current_kit": args.require_current_kit or True,
                "require_signed": args.require_signed or True,
                "require_quorum": args.require_quorum or True,
                "continuity_kit": args.continuity_kit,
                "continuity_kit_verification_report": args.continuity_kit_verification_report,
                "signoff_binding": args.signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_acceptance_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            continuity_kit=args.continuity_kit,
            continuity_kit_verification_report=args.continuity_kit_verification_report,
            signoff_binding=args.signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-acceptance command.")

def _run_unified_release_program_continuity_acceptance_change_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.domains.program.unified_release_program_continuity_acceptance_change_verifier import write_unified_release_program_continuity_acceptance_change_verification_report

    store = _program_component("continuity_acceptance_change")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_state(program_id)
        state = detail.get("state") or {}
        return {"ok": True, **detail, "summary": state, "status": state.get("status") or "unknown"}
    if args.action == "create-change-request":
        request = store.create_change_request(
            program_id,
            {
                "change_request_id": args.change_request_id,
                "change_type": args.change_type,
                "allowed_actions": args.allowed_action or None,
                "reason": args.reason,
                "requested_by": args.requested_by,
            },
        )
        return {"ok": request.get("status") in {"submitted", "approved"}, "change_request": request, "summary": {"change_request_id": request.get("change_request_id")}, "status": request.get("status")}
    if args.action == "approve-change-request":
        approval = store.approve_change_request(
            program_id,
            args.change_request_id,
            {
                "approved_by": args.approved_by,
                "role": args.role,
                "reason": args.reason,
                "approved_actions": args.approved_action or None,
            },
        )
        return {"ok": approval.get("status") == "approved", "approval": approval, "summary": {"approval_hash": approval.get("integrity_hash")}, "status": approval.get("status")}
    if args.action == "reset-signoff":
        proof = store.reset_acceptance_signoff(program_id, args.change_request_id, {"reset_by": args.reset_by, "reason": args.reason})
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "summary": {"reset_proof_hash": proof.get("integrity_hash")}, "status": proof.get("status")}
    if args.action == "lifecycle":
        report = store.refresh_lifecycle_audit(program_id)
        return {"ok": report.get("status") == "passed", "lifecycle_report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "export":
        manifest = store.export_archive(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_archive_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_archive_zip(
            program_id,
            {
                "archive_zip": args.archive_zip,
                "strict": args.strict,
                "require_current_acceptance": args.require_current_acceptance or True,
                "acceptance_archive": args.acceptance_archive,
                "acceptance_verification_report": args.acceptance_verification_report,
                "acceptance_signoff_binding": args.acceptance_signoff_binding,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_acceptance_change_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            acceptance_archive=args.acceptance_archive,
            acceptance_verification_report=args.acceptance_verification_report,
            acceptance_signoff_binding=args.acceptance_signoff_binding,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-acceptance-change command.")

def _run_unified_release_program_continuity_command_center_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.domains.program.unified_release_program_continuity_command_center_verifier import write_unified_release_program_continuity_command_center_verification_report

    store = _program_component("command_center")
    program_id = args.program_id
    if args.action == "status":
        detail = store.get_command_center(program_id)
        report = detail.get("report") or {}
        return {"ok": True, **detail, "summary": report.get("summary", {}), "status": report.get("status") or "unknown"}
    if args.action == "refresh":
        report = store.refresh_command_center(program_id)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "run-safe":
        result = store.run_safe(program_id)
        return {"ok": result.get("status") in {"passed", "warning"}, "runbook_result": result, "summary": result.get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        manifest = store.export_package(program_id)
        return {"ok": True, "manifest": manifest, "summary": {"manifest_hash": manifest.get("integrity_hash")}, "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(program_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256"), "manifest_hash": result.get("manifest_hash")}}
    if args.action == "verify":
        report = store.verify_zip(
            program_id,
            {
                "command_center_zip": args.command_center_zip,
                "strict": args.strict,
                "deep": args.deep or True,
                "require_ready": args.require_ready or True,
                "evidence_manifest": args.evidence_manifest,
            },
        )
        if args.report_out is not None:
            write_unified_release_program_continuity_command_center_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            command_center_zip_path=args.command_center_zip,
            verification_report_path=args.verification_report,
            evidence_manifest_path=args.evidence_manifest,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "summary": gate.get("summary", {}), "status": gate.get("status")}
    raise ValueError("Unsupported unified-release-program-continuity-command-center command.")

def _run_unified_release_program_continuity_command_center_signoff_command(args: argparse.Namespace) -> dict[str, Any]:

    store = _program_component("command_center_signoff")
    program_id = args.program_id
    payload = {
        "signed_by": args.signed_by,
        "role": args.role,
        "reason": args.reason,
        "change_request_id": args.change_request_id,
        "approved_by": args.approved_by,
        "reset_by": args.reset_by,
        "allowed_actions": args.allowed_action or None,
        "archive_zip": args.archive_zip,
        "archive_verification_report": args.archive_verification_report,
        "signoff_binding": args.signoff_binding,
        "command_center_zip": args.command_center,
        "command_center_verification_report": args.command_center_verification_report,
        "command_center_external_evidence_manifest": args.command_center_evidence_manifest,
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    if args.action == "status":
        state = store.get_state(program_id)
        return {"ok": True, **state, "summary": {"status": state.get("status")}}
    if args.action == "preflight":
        report = store.preflight(program_id, payload)
        return {"ok": report.get("status") == "passed", "preflight": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "sign":
        signoff = store.signoff(program_id, payload)
        return {"ok": True, "signoff": signoff, "status": signoff.get("status"), "summary": signoff.get("summary", {})}
    if args.action == "create-cr":
        request = store.create_change_request(program_id, payload)
        return {"ok": True, "change_request": request, "status": request.get("status"), "summary": {"change_request_id": request.get("change_request_id")}}
    if args.action == "approve-cr":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for approve-cr.")
        approval = store.approve_change_request(program_id, args.change_request_id, payload)
        return {"ok": True, "approval": approval, "status": approval.get("status"), "summary": {"change_request_id": args.change_request_id}}
    if args.action == "reset":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for reset.")
        proof = store.reset_signoff(program_id, args.change_request_id, payload)
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "status": proof.get("status"), "summary": {"reset_event_hash": proof.get("reset_event_hash")}}
    if args.action == "export":
        manifest = store.export_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "zip":
        return {"ok": True, **store.build_archive_zip(program_id, payload)}
    if args.action == "verify":
        report = store.verify_archive_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "handoff-export":
        manifest = store.export_final_handoff(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "handoff-zip":
        return {"ok": True, **store.build_final_handoff_zip(program_id, payload)}
    if args.action == "handoff-verify":
        report = store.verify_final_handoff_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            archive_verification_report_path=args.archive_verification_report,
            signoff_binding_path=args.signoff_binding,
            command_center_zip_path=args.command_center,
            command_center_verification_report_path=args.command_center_verification_report,
            command_center_external_evidence_manifest_path=args.command_center_evidence_manifest,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})}
    raise ValueError("Unsupported unified-release-program-continuity-command-center-signoff command.")

def _run_unified_release_program_continuity_command_center_acceptance_command(args: argparse.Namespace) -> dict[str, Any]:

    store = _program_component("receiver_acceptance")
    program_id = args.program_id
    payload = _command_center_acceptance_payload(args)
    if args.action == "status":
        state = store.status(program_id)
        return {"ok": True, **state}
    if args.action == "create-review-pack":
        return {"ok": True, **store.create_review_pack(program_id, payload)}
    if args.action == "verify-review-pack":
        report = store.verify_review_pack(program_id, payload)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action in {"import-response", "import-response-base64"}:
        if args.response is not None:
            payload["response"] = read_json(args.response)
        if args.response_verification_report is not None:
            payload["response_verification_report"] = read_json(args.response_verification_report)
        if args.response_binding_summary is not None:
            payload["response_binding_summary"] = read_json(args.response_binding_summary)
        if args.response_base64:
            payload["response_base64"] = args.response_base64
        if args.response_zip_base64:
            payload["response_zip_base64"] = args.response_zip_base64
        result = store.import_response(program_id, payload)
        return {"ok": True, **result, "summary": {"response_id": result["response"].get("response_id")}}
    if args.action == "create-accepted-evidence":
        if not args.response_id:
            raise ValueError("--response-id is required.")
        result = store.create_accepted_evidence(program_id, args.response_id, payload)
        return {"ok": True, **result}
    if args.action == "verify-accepted-evidence":
        if not args.response_id:
            raise ValueError("--response-id is required.")
        report = store.verify_accepted_evidence(program_id, args.response_id, payload)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "refresh-board":
        report = store.refresh_board(program_id, payload)
        return {"ok": report.get("status") == "ready_for_signoff", "report": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "signoff":
        signoff = store.signoff(program_id, payload)
        return {"ok": True, "signoff": signoff, "status": signoff.get("status"), "summary": {"signoff_hash": signoff.get("integrity_hash")}}
    if args.action == "export-archive":
        manifest = store.export_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "zip-archive":
        return {"ok": True, **store.build_archive_zip(program_id, payload)}
    if args.action == "verify-archive":
        report = store.verify_archive_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "gate":
        gate = store.gate(program_id, required=True, **payload)
        return {"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})}
    raise ValueError("Unsupported unified-release-program-continuity-command-center-acceptance command.")

def _run_unified_release_program_continuity_command_center_acceptance_change_command(args: argparse.Namespace) -> dict[str, Any]:

    store = _program_component("receiver_acceptance_change")
    program_id = args.program_id
    payload = {
        **_command_center_acceptance_payload(args),
        "archive_zip": args.archive_zip,
        "acceptance_archive": args.acceptance_archive,
        "acceptance_verification_report": args.acceptance_verification_report,
        "acceptance_signoff_binding": args.acceptance_signoff_binding,
        "previous_acceptance_root": args.previous_acceptance_root,
        "strict": args.strict,
        "require_current_acceptance": args.require_current or True,
        "require_reset_proofs": args.require_reset_proofs or True,
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    if args.action == "status":
        state = store.get_state(program_id)
        return {"ok": True, **state, "status": (state.get("state") or {}).get("status") or "not_configured"}
    if args.action == "create-cr":
        request = store.create_change_request(
            program_id,
            {
                "change_request_id": args.change_request_id,
                "change_type": args.change_type,
                "allowed_actions": args.allowed_action or None,
                "reason": args.reason,
                "requested_by": args.requested_by,
            },
        )
        return {"ok": True, "change_request": request, "status": request.get("status"), "summary": {"change_request_id": request.get("change_request_id")}}
    if args.action == "approve-cr":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for approve-cr.")
        approval = store.approve_change_request(
            program_id,
            args.change_request_id,
            {"approved_by": args.approved_by, "role": args.role, "reason": args.reason, "approved_actions": args.approved_action or None},
        )
        return {"ok": True, "approval": approval, "status": approval.get("status"), "summary": {"approval_hash": approval.get("integrity_hash")}}
    if args.action == "reset-signoff":
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for reset-signoff.")
        proof = store.reset_receiver_acceptance_signoff(
            program_id,
            args.change_request_id,
            {"reset_by": args.reset_by, "reason": args.reason},
        )
        return {"ok": proof.get("status") == "applied", "reset_proof": proof, "status": proof.get("status"), "summary": {"reset_proof_hash": proof.get("integrity_hash")}}
    if args.action == "refresh-lifecycle":
        report = store.refresh_lifecycle_audit(program_id, payload)
        return {"ok": report.get("status") == "passed", "lifecycle_report": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "export":
        manifest = store.export_archive(program_id, payload)
        return {"ok": True, "manifest": manifest, "status": "passed", "summary": {"manifest_hash": manifest.get("integrity_hash")}}
    if args.action == "zip":
        result = store.build_archive_zip(program_id, payload)
        return {"ok": result.get("status") == "passed", **result}
    if args.action == "verify":
        report = store.verify_archive_zip(program_id, payload)
        if args.report_out:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") == "passed", "verification": report, "status": report.get("status"), "summary": report.get("summary", {})}
    if args.action == "gate":
        gate = store.gate(
            program_id,
            required=True,
            archive_zip_path=args.archive_zip,
            verification_report_path=args.verification_report,
            **payload,
        )
        return {"ok": gate.get("status") == "passed", "gate": gate, "status": gate.get("status"), "summary": gate.get("summary", {})}
    raise ValueError("Unsupported unified-release-program-continuity-command-center-acceptance-change command.")

def _execute_unified_command_center(argv: list[str]) -> None:
    raw_args = ['unified-command-center', *argv]
    parser = build_unified_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "runtime_failed", "verification_failed"}:
        raise SystemExit(1)
    return


def handle_unified_command_center(argv: list[str]) -> None:
    _execute_unified_command_center(argv)

def _execute_unified_command_center_review(argv: list[str]) -> None:
    raw_args = ['unified-command-center-review', *argv]
    parser = build_unified_command_center_review_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_review_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_review(argv: list[str]) -> None:
    _execute_unified_command_center_review(argv)

def _execute_unified_command_center_drift_response(argv: list[str]) -> None:
    raw_args = ['unified-command-center-drift-response', *argv]
    parser = build_unified_command_center_drift_response_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_drift_response_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_drift_response(argv: list[str]) -> None:
    _execute_unified_command_center_drift_response(argv)

def _execute_unified_command_center_evidence_review(argv: list[str]) -> None:
    raw_args = ['unified-command-center-evidence-review', *argv]
    parser = build_unified_command_center_evidence_review_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_evidence_review_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_evidence_review(argv: list[str]) -> None:
    _execute_unified_command_center_evidence_review(argv)

def _execute_unified_command_center_reviewer_decision_board(argv: list[str]) -> None:
    raw_args = ['unified-command-center-reviewer-decision-board', *argv]
    parser = build_unified_command_center_reviewer_decision_board_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_reviewer_decision_board_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_reviewer_decision_board(argv: list[str]) -> None:
    _execute_unified_command_center_reviewer_decision_board(argv)

def _execute_unified_command_center_release_train(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train', *argv]
    parser = build_unified_command_center_release_train_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_release_train(argv: list[str]) -> None:
    _execute_unified_command_center_release_train(argv)

def _execute_unified_command_center_release_train_change_control(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train-change-control', *argv]
    parser = build_unified_command_center_release_train_change_control_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_change_control_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_release_train_change_control(argv: list[str]) -> None:
    _execute_unified_command_center_release_train_change_control(argv)

def _execute_unified_command_center_release_train_lifecycle(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train-lifecycle', *argv]
    parser = build_unified_command_center_release_train_lifecycle_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_lifecycle_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_release_train_lifecycle(argv: list[str]) -> None:
    _execute_unified_command_center_release_train_lifecycle(argv)

def _execute_unified_command_center_release_train_handoff(argv: list[str]) -> None:
    raw_args = ['unified-command-center-release-train-handoff', *argv]
    parser = build_unified_command_center_release_train_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_command_center_release_train_handoff_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_command_center_release_train_handoff(argv: list[str]) -> None:
    _execute_unified_command_center_release_train_handoff(argv)

def _execute_unified_release_program(argv: list[str]) -> None:
    raw_args = ['unified-release-program', *argv]
    parser = build_unified_release_program_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program(argv: list[str]) -> None:
    _execute_unified_release_program(argv)

def _execute_unified_release_program_operations(argv: list[str]) -> None:
    raw_args = ['unified-release-program-operations', *argv]
    parser = build_unified_release_program_operations_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_operations_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_operations(argv: list[str]) -> None:
    _execute_unified_release_program_operations(argv)

def _execute_unified_release_program_handoff(argv: list[str]) -> None:
    raw_args = ['unified-release-program-handoff', *argv]
    parser = build_unified_release_program_handoff_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_handoff_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_handoff(argv: list[str]) -> None:
    _execute_unified_release_program_handoff(argv)

def _execute_unified_release_program_vault(argv: list[str]) -> None:
    raw_args = ['unified-release-program-vault', *argv]
    parser = build_unified_release_program_vault_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_vault_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_vault(argv: list[str]) -> None:
    _execute_unified_release_program_vault(argv)

def _execute_unified_release_program_vault_ops(argv: list[str]) -> None:
    raw_args = ['unified-release-program-vault-ops', *argv]
    parser = build_unified_release_program_vault_operations_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_vault_operations_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_vault_ops(argv: list[str]) -> None:
    _execute_unified_release_program_vault_ops(argv)

def _execute_unified_release_program_continuity(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity', *argv]
    parser = build_unified_release_program_continuity_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity(argv: list[str]) -> None:
    _execute_unified_release_program_continuity(argv)

def _execute_unified_release_program_continuity_kit(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-kit', *argv]
    parser = build_unified_release_program_continuity_distribution_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_distribution_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity_kit(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_kit(argv)

def _execute_unified_release_program_continuity_acceptance(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-acceptance', *argv]
    parser = build_unified_release_program_continuity_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_acceptance_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity_acceptance(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_acceptance(argv)

def _execute_unified_release_program_continuity_acceptance_change(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-acceptance-change', *argv]
    parser = build_unified_release_program_continuity_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_acceptance_change_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity_acceptance_change(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_acceptance_change(argv)

def _execute_unified_release_program_continuity_command_center(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center', *argv]
    parser = build_unified_release_program_continuity_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity_command_center(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center(argv)

def _execute_unified_release_program_continuity_command_center_signoff(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-signoff', *argv]
    parser = build_unified_release_program_continuity_command_center_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_signoff_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity_command_center_signoff(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_signoff(argv)

def _execute_unified_release_program_continuity_command_center_acceptance(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-acceptance', *argv]
    parser = build_unified_release_program_continuity_command_center_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_acceptance_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity_command_center_acceptance(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_acceptance(argv)

def _execute_unified_release_program_continuity_command_center_acceptance_change(argv: list[str]) -> None:
    raw_args = ['unified-release-program-continuity-command-center-acceptance-change', *argv]
    parser = build_unified_release_program_continuity_command_center_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_unified_release_program_continuity_command_center_acceptance_change_command(args)
    _print_release_audio_certification_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale", "no_go"}:
        raise SystemExit(1)
    return


def handle_unified_release_program_continuity_command_center_acceptance_change(argv: list[str]) -> None:
    _execute_unified_release_program_continuity_command_center_acceptance_change(argv)


SPECS = (
    CommandSpec(name='unified-command-center', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center, help='Unified Command Center', group='program'),
    CommandSpec(name='unified-command-center-review', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_review, help='Unified Command Center Review', group='program'),
    CommandSpec(name='unified-command-center-drift-response', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_drift_response, help='Unified Command Center Drift Response', group='program'),
    CommandSpec(name='unified-command-center-evidence-review', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_evidence_review, help='Unified Command Center Evidence Review', group='program'),
    CommandSpec(name='unified-command-center-reviewer-decision-board', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_reviewer_decision_board, help='Unified Command Center Reviewer Decision Board', group='program'),
    CommandSpec(name='unified-command-center-release-train', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train, help='Unified Command Center Release Train', group='program'),
    CommandSpec(name='unified-command-center-release-train-change-control', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train_change_control, help='Unified Command Center Release Train Change Control', group='program'),
    CommandSpec(name='unified-command-center-release-train-lifecycle', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train_lifecycle, help='Unified Command Center Release Train Lifecycle', group='program'),
    CommandSpec(name='unified-command-center-release-train-handoff', parser=build_acceptance_analytics_parser, handler=handle_unified_command_center_release_train_handoff, help='Unified Command Center Release Train Handoff', group='program'),
    CommandSpec(name='unified-release-program', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program, help='Unified Release Program', group='program'),
    CommandSpec(name='unified-release-program-operations', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_operations, help='Unified Release Program Operations', group='program'),
    CommandSpec(name='unified-release-program-handoff', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_handoff, help='Unified Release Program Handoff', group='program'),
    CommandSpec(name='unified-release-program-vault', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_vault, help='Unified Release Program Vault', group='program'),
    CommandSpec(name='unified-release-program-vault-ops', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_vault_ops, help='Unified Release Program Vault Ops', group='program'),
    CommandSpec(name='unified-release-program-continuity', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity, help='Unified Release Program Continuity', group='program'),
    CommandSpec(name='unified-release-program-continuity-kit', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_kit, help='Unified Release Program Continuity Kit', group='program'),
    CommandSpec(name='unified-release-program-continuity-acceptance', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_acceptance, help='Unified Release Program Continuity Acceptance', group='program'),
    CommandSpec(name='unified-release-program-continuity-acceptance-change', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_acceptance_change, help='Unified Release Program Continuity Acceptance Change', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center, help='Unified Release Program Continuity Command Center', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center-signoff', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center_signoff, help='Unified Release Program Continuity Command Center Signoff', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center-acceptance', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center_acceptance, help='Unified Release Program Continuity Command Center Acceptance', group='program'),
    CommandSpec(name='unified-release-program-continuity-command-center-acceptance-change', parser=build_acceptance_analytics_parser, handler=handle_unified_release_program_continuity_command_center_acceptance_change, help='Unified Release Program Continuity Command Center Acceptance Change', group='program'),
)

# Active Program commands are registered by ``program_context``. This module
# retains UCC commands and import compatibility for older callers.
SPECS = tuple(spec for spec in SPECS if not spec.name.startswith("unified-release-program"))
