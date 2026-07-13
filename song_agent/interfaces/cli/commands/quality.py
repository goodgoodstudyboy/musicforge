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

def _build_public_trust_center_publication_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_publication_store')(*args, **kwargs)

def _build_public_trust_center_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_public_trust_center_store')(*args, **kwargs)

def _build_release_portfolio_governance_attestation_portal_store(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', '_build_release_portfolio_governance_attestation_portal_store')(*args, **kwargs)

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

def build_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('creation', 'build_parser')(*args, **kwargs)

def build_public_trust_center_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_parser')(*args, **kwargs)

def build_public_trust_center_publication_monitor_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_publication_monitor_parser')(*args, **kwargs)

def build_public_trust_center_publication_parser(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'build_public_trust_center_publication_parser')(*args, **kwargs)

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

def print_public_trust_center_result(*args: Any, **kwargs: Any) -> Any:
    return _resolve_symbol('trust', 'print_public_trust_center_result')(*args, **kwargs)

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

def build_audio_lab_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MusicForge Audio Lab environment, smoke, listening, and A/B checks.")
    subparsers = parser.add_subparsers(dest="section", required=True)

    status = subparsers.add_parser("status", help="Show Audio Lab environment status.")
    status.add_argument("--json", action="store_true")

    detect = subparsers.add_parser("detect", help="Detect local Audio Lab renderer readiness.")
    detect.add_argument("--json", action="store_true")

    test_profile = subparsers.add_parser("test-profile", help="Test the configured renderer profile.")
    test_profile.add_argument("--profile", "--profile-id", dest="profile_id", default=None)
    test_profile.add_argument("--json", action="store_true")

    setup_report = subparsers.add_parser("setup-report", help="Write and show the Audio Lab setup report.")
    setup_report.add_argument("--json", action="store_true")
    setup_report.add_argument("--report-out", type=Path, default=None)

    smoke = subparsers.add_parser("smoke", help="Create an Audio Lab smoke run.")
    smoke.add_argument("--cases", type=int, default=1)
    smoke.add_argument("--render-audio", choices=["auto", "required", "require", "never"], default="auto")
    smoke.add_argument("--profile", "--profile-id", dest="profile_id", default=None)
    smoke.add_argument("--json", action="store_true")
    smoke.add_argument("--report-out", type=Path, default=None)

    smoke_report = subparsers.add_parser("smoke-report", help="Show an Audio Lab smoke run report.")
    smoke_report.add_argument("smoke_run_id")
    smoke_report.add_argument("--json", action="store_true")
    smoke_report.add_argument("--report-out", type=Path, default=None)

    session = subparsers.add_parser("session", help="Manage Audio Lab listening sessions.")
    session_sub = session.add_subparsers(dest="session_action", required=True)
    session_create = session_sub.add_parser("create", help="Create a listening session from a smoke run.")
    session_create.add_argument("--from-smoke", required=True)
    session_create.add_argument("--json", action="store_true")
    session_list = session_sub.add_parser("list", help="List listening sessions.")
    session_list.add_argument("--json", action="store_true")
    session_detail = session_sub.add_parser("detail", help="Show a listening session.")
    session_detail.add_argument("session_id")
    session_detail.add_argument("--json", action="store_true")
    session_review = session_sub.add_parser("review", help="Write a manual listening review.")
    session_review.add_argument("session_id")
    session_review.add_argument("item_id")
    session_review.add_argument("--result", choices=["accepted", "needs_fix", "rejected"], required=True)
    session_review.add_argument("--rating", type=int, required=True)
    session_review.add_argument("--reviewer", default="developer")
    session_review.add_argument("--role", default="developer")
    session_review.add_argument("--notes", default="")
    session_review.add_argument("--playback-confirmed", action="store_true")
    session_review.add_argument("--json", action="store_true")
    session_marker = session_sub.add_parser("marker", help="Add an issue marker to a listening item.")
    session_marker.add_argument("session_id")
    session_marker.add_argument("item_id")
    session_marker.add_argument("--time-seconds", type=float, default=0.0)
    session_marker.add_argument("--category", default="other")
    session_marker.add_argument("--severity", default="medium")
    session_marker.add_argument("--message", default="")
    session_marker.add_argument("--json", action="store_true")
    session_task = session_sub.add_parser("create-review-task", help="Create a draft ReviewTask from a marker.")
    session_task.add_argument("session_id")
    session_task.add_argument("marker_id")
    session_task.add_argument("--title", default="")
    session_task.add_argument("--instruction", default="")
    session_task.add_argument("--json", action="store_true")
    session_revision = session_sub.add_parser("create-audio-revision-draft", help="Create an Audio Revision draft from a marker.")
    session_revision.add_argument("session_id")
    session_revision.add_argument("marker_id")
    session_revision.add_argument("--title", default="")
    session_revision.add_argument("--instruction", default="")
    session_revision.add_argument("--json", action="store_true")
    session_mix = session_sub.add_parser("create-mix-patch-draft", help="Create a Mix Patch draft from a marker.")
    session_mix.add_argument("session_id")
    session_mix.add_argument("marker_id")
    session_mix.add_argument("--title", default="")
    session_mix.add_argument("--instruction", default="")
    session_mix.add_argument("--json", action="store_true")
    session_report = session_sub.add_parser("report", help="Write and show a listening session report.")
    session_report.add_argument("session_id")
    session_report.add_argument("--json", action="store_true")
    session_close = session_sub.add_parser("close", help="Close a reviewed listening session.")
    session_close.add_argument("session_id")
    session_close.add_argument("--closed-by", default="audio-lab")
    session_close.add_argument("--json", action="store_true")

    compare = subparsers.add_parser("compare", help="Manage Audio Lab A/B comparisons.")
    compare_sub = compare.add_subparsers(dest="compare_action", required=True)
    compare_create = compare_sub.add_parser("create", help="Create an A/B comparison.")
    compare_create.add_argument("--left", required=True)
    compare_create.add_argument("--right", required=True)
    compare_create.add_argument("--json", action="store_true")
    compare_review = compare_sub.add_parser("review", help="Review an A/B comparison.")
    compare_review.add_argument("comparison_id")
    compare_review.add_argument("--preferred", choices=["left", "right", "same"], required=True)
    compare_review.add_argument("--rating", type=int, default=4)
    compare_review.add_argument("--rating-delta", type=int, default=0)
    compare_review.add_argument("--reviewer", default="developer")
    compare_review.add_argument("--role", default="developer")
    compare_review.add_argument("--notes", default="")
    compare_review.add_argument("--playback-confirmed", action="store_true")
    compare_review.add_argument("--json", action="store_true")
    compare_report = compare_sub.add_parser("report", help="Write and show an A/B comparison report.")
    compare_report.add_argument("comparison_id")
    compare_report.add_argument("--json", action="store_true")
    return parser

def build_audio_fix_sprint_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Audio Fix Sprints from Audio Lab needs_fix markers.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a sprint from one or more Audio Lab sessions.")
    create.add_argument("--from-session", "--session-id", dest="session_ids", action="append", required=True)
    create.add_argument("--name", default="")
    create.add_argument("--include-test-audio", action="store_true")
    create.add_argument("--json", action="store_true")

    listing = subparsers.add_parser("list", help="List Audio Fix Sprints.")
    listing.add_argument("--json", action="store_true")

    detail = subparsers.add_parser("detail", help="Show one Audio Fix Sprint.")
    detail.add_argument("sprint_id")
    detail.add_argument("--json", action="store_true")

    refresh = subparsers.add_parser("refresh", help="Refresh stale status for an Audio Fix Sprint.")
    refresh.add_argument("sprint_id")
    refresh.add_argument("--json", action="store_true")

    drafts = subparsers.add_parser("create-drafts", help="Create deterministic fix drafts for sprint items.")
    drafts.add_argument("sprint_id")
    drafts.add_argument("--draft-type", choices=["review_task", "audio_revision", "mix_patch"], default="review_task")
    drafts.add_argument("--item-id", dest="item_ids", action="append")
    drafts.add_argument("--json", action="store_true")

    candidates = subparsers.add_parser("generate-candidates", help="Generate local deterministic fix candidates.")
    candidates.add_argument("sprint_id")
    candidates.add_argument("--item-id", dest="item_ids", action="append")
    candidates.add_argument("--json", action="store_true")

    review = subparsers.add_parser("review-candidate", help="Write a manual A/B review for a candidate.")
    review.add_argument("sprint_id")
    review.add_argument("item_id")
    review.add_argument("candidate_id")
    review.add_argument("--preferred", choices=["left", "right", "same"], required=True)
    review.add_argument("--rating", type=int, default=4)
    review.add_argument("--rating-delta", type=int, default=0)
    review.add_argument("--reviewer", default="developer")
    review.add_argument("--role", default="developer")
    review.add_argument("--notes", default="")
    review.add_argument("--playback-confirmed", action="store_true")
    review.add_argument("--json", action="store_true")

    select = subparsers.add_parser("select-candidate", help="Select a manually reviewed candidate.")
    select.add_argument("sprint_id")
    select.add_argument("item_id")
    select.add_argument("candidate_id")
    select.add_argument("--selected-by", default="audio-fix-sprint")
    select.add_argument("--json", action="store_true")

    recheck = subparsers.add_parser("create-recheck-session", help="Create the manual recheck session from selected candidates.")
    recheck.add_argument("sprint_id")
    recheck.add_argument("--json", action="store_true")

    recheck_review = subparsers.add_parser("review-recheck", help="Review one recheck session item.")
    recheck_review.add_argument("sprint_id")
    recheck_review.add_argument("item_id")
    recheck_review.add_argument("--result", choices=["accepted", "needs_fix", "rejected"], required=True)
    recheck_review.add_argument("--rating", type=int, default=4)
    recheck_review.add_argument("--reviewer", default="developer")
    recheck_review.add_argument("--role", default="developer")
    recheck_review.add_argument("--notes", default="")
    recheck_review.add_argument("--playback-confirmed", action="store_true")
    recheck_review.add_argument("--json", action="store_true")

    closeout = subparsers.add_parser("closeout", help="Build and show the Audio Fix Sprint closeout report.")
    closeout.add_argument("sprint_id")
    closeout.add_argument("--json", action="store_true")

    close = subparsers.add_parser("close", help="Close a sprint after manual A/B and accepted recheck.")
    close.add_argument("sprint_id")
    close.add_argument("--closed-by", default="audio-fix-sprint")
    close.add_argument("--json", action="store_true")
    return parser

def build_audio_campaign_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage release candidate Audio Campaigns from Audio Lab sessions.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create an Audio Campaign from one or more Audio Lab sessions.")
    create.add_argument("--from-session", "--session-id", dest="session_ids", action="append", required=True)
    create.add_argument("--name", default="")
    create.add_argument("--profile", default="release_candidate")
    create.add_argument("--allow-test-audio", action="store_true")
    create.add_argument("--allow-synthetic-review", action="store_true")
    create.add_argument("--minimum-rating", type=int, default=4)
    create.add_argument("--json", action="store_true")

    listing = subparsers.add_parser("list", help="List Audio Campaigns.")
    listing.add_argument("--json", action="store_true")

    detail = subparsers.add_parser("detail", help="Show one Audio Campaign.")
    detail.add_argument("campaign_id")
    detail.add_argument("--json", action="store_true")

    refresh = subparsers.add_parser("refresh", help="Refresh Audio Campaign source snapshots.")
    refresh.add_argument("campaign_id")
    refresh.add_argument("--json", action="store_true")

    link_session = subparsers.add_parser("link-session", help="Add another Audio Lab listening session to a campaign.")
    link_session.add_argument("campaign_id")
    link_session.add_argument("--session-id", required=True)
    link_session.add_argument("--json", action="store_true")

    fix_sprints = subparsers.add_parser("create-fix-sprints", help="Create Audio Fix Sprints for campaign issues.")
    fix_sprints.add_argument("campaign_id")
    fix_sprints.add_argument("--json", action="store_true")

    report = subparsers.add_parser("report", help="Build and show the Audio Campaign report.")
    report.add_argument("campaign_id")
    report.add_argument("--json", action="store_true")

    signoff = subparsers.add_parser("signoff", help="Sign off a passed Audio Campaign.")
    signoff.add_argument("campaign_id")
    signoff.add_argument("--signed-by", required=True)
    signoff.add_argument("--role", default="audio-reviewer")
    signoff.add_argument("--reason", default="")
    signoff.add_argument("--json", action="store_true")

    export = subparsers.add_parser("export", help="Export the Audio Campaign evidence package directory.")
    export.add_argument("campaign_id")
    export.add_argument("--json", action="store_true")

    zip_cmd = subparsers.add_parser("zip", help="Build the Audio Campaign ZIP.")
    zip_cmd.add_argument("campaign_id")
    zip_cmd.add_argument("--json", action="store_true")

    verify = subparsers.add_parser("verify", help="Verify the Audio Campaign ZIP.")
    verify.add_argument("campaign_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-real-audio", action="store_true")
    verify.add_argument("--require-manual-review", action="store_true")
    verify.add_argument("--require-fix-sprints-closed", action="store_true")
    verify.add_argument("--require-signed", action="store_true")
    verify.add_argument("--json", action="store_true")
    verify.add_argument("--report-out", type=Path, default=None)

    governance = subparsers.add_parser("governance", help="Refresh the Audio Campaign governance report.")
    governance.add_argument("campaign_id")
    governance.add_argument("--json", action="store_true")

    analytics = subparsers.add_parser("analytics", help="Refresh the Audio Campaign analytics summary.")
    analytics.add_argument("campaign_id")
    analytics.add_argument("--json", action="store_true")

    archive = subparsers.add_parser("archive", help="Export signed Audio Campaign governance archive files.")
    archive.add_argument("campaign_id")
    archive.add_argument("--json", action="store_true")

    archive_zip = subparsers.add_parser("archive-zip", help="Build the signed Audio Campaign governance archive ZIP.")
    archive_zip.add_argument("campaign_id")
    archive_zip.add_argument("--json", action="store_true")

    verify_archive = subparsers.add_parser("verify-archive", help="Verify the signed Audio Campaign governance archive ZIP.")
    verify_archive.add_argument("campaign_id")
    verify_archive.add_argument("--strict", action="store_true")
    verify_archive.add_argument("--json", action="store_true")
    verify_archive.add_argument("--report-out", type=Path, default=None)

    remediation_plan = subparsers.add_parser("remediation-plan", help="Refresh Release Audio Campaign remediation plan.")
    remediation_plan.add_argument("release_id")
    remediation_plan.add_argument("--json", action="store_true")

    remediation_status = subparsers.add_parser("remediation-status", help="Show Release Audio Campaign remediation status.")
    remediation_status.add_argument("release_id")
    remediation_status.add_argument("--json", action="store_true")

    remediation_run = subparsers.add_parser("remediation-run-safe", help="Run safe remediation actions.")
    remediation_run.add_argument("release_id")
    remediation_run.add_argument("--closed-by", default="audio-campaign-remediation")
    remediation_run.add_argument("--json", action="store_true")

    remediation_closeout = subparsers.add_parser("remediation-closeout", help="Build Release Audio Campaign remediation closeout report.")
    remediation_closeout.add_argument("release_id")
    remediation_closeout.add_argument("--json", action="store_true")

    remediation_signoff = subparsers.add_parser("remediation-signoff", help="Sign off passed Release Audio Campaign remediation evidence.")
    remediation_signoff.add_argument("release_id")
    remediation_signoff.add_argument("--signed-by", required=True)
    remediation_signoff.add_argument("--role", default="audio-remediation-reviewer")
    remediation_signoff.add_argument("--reason", default="")
    remediation_signoff.add_argument("--json", action="store_true")

    remediation_export = subparsers.add_parser("remediation-export", help="Export Release Audio Campaign remediation evidence.")
    remediation_export.add_argument("release_id")
    remediation_export.add_argument("--json", action="store_true")

    remediation_zip = subparsers.add_parser("remediation-zip", help="Build Release Audio Campaign remediation ZIP.")
    remediation_zip.add_argument("release_id")
    remediation_zip.add_argument("--json", action="store_true")

    remediation_verify = subparsers.add_parser("remediation-verify", help="Verify Release Audio Campaign remediation ZIP.")
    remediation_verify.add_argument("release_id")
    remediation_verify.add_argument("--strict", action="store_true")
    remediation_verify.add_argument("--require-passed", action="store_true")
    remediation_verify.add_argument("--require-signed", action="store_true")
    remediation_verify.add_argument("--json", action="store_true")
    remediation_verify.add_argument("--report-out", type=Path, default=None)

    cr_create = subparsers.add_parser("change-request-create", help="Create an Audio Campaign signoff reset Change Request.")
    cr_create.add_argument("campaign_id")
    cr_create.add_argument("--created-by", default="developer")
    cr_create.add_argument("--reason", required=True)
    cr_create.add_argument("--risk", default="medium")
    cr_create.add_argument("--json", action="store_true")

    cr_approve = subparsers.add_parser("change-request-approve", help="Approve an Audio Campaign signoff reset Change Request.")
    cr_approve.add_argument("campaign_id")
    cr_approve.add_argument("change_request_id")
    cr_approve.add_argument("--approved-by", default="reviewer")
    cr_approve.add_argument("--reason", default="")
    cr_approve.add_argument("--json", action="store_true")

    reset = subparsers.add_parser("signoff-reset", help="Reset Audio Campaign signoff with an approved Change Request.")
    reset.add_argument("campaign_id")
    reset.add_argument("--change-request-id", required=True)
    reset.add_argument("--reason", required=True)
    reset.add_argument("--json", action="store_true")

    plan_release = subparsers.add_parser("plan-release", help="Create or refresh a release-bound Audio Campaign plan.")
    plan_release.add_argument("release_id")
    plan_release.add_argument("--json", action="store_true")

    preflight_release = subparsers.add_parser("preflight-release", help="Run Release Audio Campaign preflight.")
    preflight_release.add_argument("release_id")
    preflight_release.add_argument("--json", action="store_true")

    create_from_release = subparsers.add_parser("create-from-release", help="Create Audio Lab session and Audio Campaign from Release tracks.")
    create_from_release.add_argument("release_id")
    create_from_release.add_argument("--name", default="")
    create_from_release.add_argument("--minimum-rating", type=int, default=4)
    create_from_release.add_argument("--allow-failed-preflight", action="store_true")
    create_from_release.add_argument("--json", action="store_true")

    release_status = subparsers.add_parser("release-status", help="Show Release Audio Campaign plan status.")
    release_status.add_argument("release_id")
    release_status.add_argument("--json", action="store_true")

    release_link = subparsers.add_parser("release-link", help="Link an existing Audio Campaign to a Release plan.")
    release_link.add_argument("release_id")
    release_link.add_argument("--campaign-id", required=True)
    release_link.add_argument("--json", action="store_true")
    return parser

def build_verify_audio_campaign_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Audio Campaign ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-real-audio", action="store_true")
    parser.add_argument("--require-manual-review", action="store_true")
    parser.add_argument("--require-fix-sprints-closed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-no-open-high", action="store_true")
    parser.add_argument("--require-no-open-critical", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=5000)
    return parser

def build_verify_audio_campaign_archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Audio Campaign Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-verification-passed", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=5000)
    return parser

def build_verify_audio_campaign_remediation_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Audio Campaign Remediation ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-passed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_release_audio_certification_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Certification evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    refresh = subparsers.add_parser("refresh", help="Refresh Release Audio Certification report.")
    refresh.add_argument("release_id")
    status = subparsers.add_parser("status", help="Show Release Audio Certification status.")
    status.add_argument("release_id")
    signoff = subparsers.add_parser("signoff", help="Sign off a passed Release Audio Certification.")
    signoff.add_argument("release_id")
    signoff.add_argument("--signed-by", default="audio-certification")
    signoff.add_argument("--role", default="audio-certification-reviewer")
    signoff.add_argument("--reason", default="Release audio certification accepted.")
    export = subparsers.add_parser("export", help="Export Release Audio Certification package files.")
    export.add_argument("release_id")
    zip_cmd = subparsers.add_parser("zip", help="Build Release Audio Certification ZIP.")
    zip_cmd.add_argument("release_id")
    verify = subparsers.add_parser("verify", help="Verify Release Audio Certification ZIP.")
    verify.add_argument("release_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-passed", action="store_true")
    verify.add_argument("--require-signed", action="store_true")
    verify.add_argument("--require-real-audio", action="store_true")
    verify.add_argument("--require-manual-review", action="store_true")
    verify.add_argument("--require-remediation-when-needed", action="store_true")
    verify.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_certification_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Certification ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-passed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-real-audio", action="store_true")
    parser.add_argument("--require-manual-review", action="store_true")
    parser.add_argument("--require-remediation-when-needed", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_release_audio_timeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Certification Timeline evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    refresh = subparsers.add_parser("refresh", help="Refresh or create a Release Audio Timeline.")
    refresh.add_argument("release_id")
    refresh.add_argument("--force-new", action="store_true")
    status = subparsers.add_parser("status", help="Show Release Audio Timeline status.")
    status.add_argument("release_id")
    status.add_argument("--timeline-id", default=None)
    events = subparsers.add_parser("events", help="Show Release Audio Timeline event ledger.")
    events.add_argument("release_id")
    events.add_argument("--timeline-id", default=None)
    signoff = subparsers.add_parser("signoff", help="Sign off a passed Release Audio Timeline.")
    signoff.add_argument("release_id")
    signoff.add_argument("--timeline-id", default=None)
    signoff.add_argument("--signed-by", default="audio-timeline")
    signoff.add_argument("--role", default="audio-timeline-reviewer")
    signoff.add_argument("--reason", default="Release audio timeline accepted.")
    export = subparsers.add_parser("export", help="Export Release Audio Timeline package files.")
    export.add_argument("release_id")
    export.add_argument("--timeline-id", default=None)
    zip_cmd = subparsers.add_parser("zip", help="Build Release Audio Timeline ZIP.")
    zip_cmd.add_argument("release_id")
    zip_cmd.add_argument("--timeline-id", default=None)
    verify = subparsers.add_parser("verify", help="Verify Release Audio Timeline ZIP.")
    verify.add_argument("release_id")
    verify.add_argument("--timeline-id", default=None)
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-passed", action="store_true")
    verify.add_argument("--require-signed", action="store_true")
    verify.add_argument("--require-real-audio", action="store_true")
    verify.add_argument("--require-manual-review", action="store_true")
    verify.add_argument("--require-current-certification", action="store_true")
    verify.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_timeline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Timeline ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-passed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-real-audio", action="store_true")
    parser.add_argument("--require-manual-review", action="store_true")
    parser.add_argument("--require-current-certification", action="store_true")
    parser.add_argument("--release-audio-certification", type=Path, default=None)
    parser.add_argument("--release-audio-certification-verification-report", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def _add_release_audio_regression_external_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--baseline-timeline", type=Path, default=None)
    parser.add_argument("--baseline-timeline-verification-report", type=Path, default=None)
    parser.add_argument("--baseline-certification", type=Path, default=None)
    parser.add_argument("--baseline-certification-verification-report", type=Path, default=None)
    parser.add_argument("--current-timeline", type=Path, default=None)
    parser.add_argument("--current-timeline-verification-report", type=Path, default=None)
    parser.add_argument("--current-certification", type=Path, default=None)
    parser.add_argument("--current-certification-verification-report", type=Path, default=None)

def build_release_audio_regression_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Regression Guard evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    configure = subparsers.add_parser("configure", help="Configure a baseline/current audio regression comparison.")
    configure.add_argument("release_id")
    configure.add_argument("--baseline-release-id", default=None)
    _add_release_audio_regression_external_args(configure)
    configure.add_argument("--identity-mode", choices=["release_track_lineage", "same_artifact_repeat_check"], default=None)
    refresh = subparsers.add_parser("refresh", help="Refresh Release Audio Regression report.")
    refresh.add_argument("release_id")
    status = subparsers.add_parser("status", help="Show Release Audio Regression status.")
    status.add_argument("release_id")
    signoff = subparsers.add_parser("signoff", help="Sign off a passed Release Audio Regression report.")
    signoff.add_argument("release_id")
    signoff.add_argument("--signed-by", default="audio-regression")
    signoff.add_argument("--role", default="audio-regression-reviewer")
    signoff.add_argument("--reason", default="Release audio regression guard accepted.")
    export = subparsers.add_parser("export", help="Export Release Audio Regression package files.")
    export.add_argument("release_id")
    zip_cmd = subparsers.add_parser("zip", help="Build Release Audio Regression ZIP.")
    zip_cmd.add_argument("release_id")
    verify = subparsers.add_parser("verify", help="Verify Release Audio Regression ZIP.")
    verify.add_argument("release_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-passed", action="store_true")
    verify.add_argument("--require-signed", action="store_true")
    verify.add_argument("--require-current", action="store_true")
    verify.add_argument("--require-baseline-current", action="store_true")
    _add_release_audio_regression_external_args(verify)
    verify.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_regression_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Regression ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-passed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-current", action="store_true")
    parser.add_argument("--require-baseline-current", action="store_true")
    _add_release_audio_regression_external_args(parser)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def _add_release_audio_baseline_external_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--timeline", type=Path, default=None)
    parser.add_argument("--timeline-verification-report", type=Path, default=None)
    parser.add_argument("--certification", type=Path, default=None)
    parser.add_argument("--certification-verification-report", type=Path, default=None)

def build_release_audio_baseline_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Baseline Governance.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("from-release", help="Create a baseline candidate from signed Release Audio evidence.")
    create.add_argument("release_id")
    _add_release_audio_baseline_external_args(create)
    create.add_argument("--scope-type", default="release_line")
    create.add_argument("--release-line-id", default="default")
    approve = subparsers.add_parser("approve", help="Approve a baseline candidate.")
    approve.add_argument("baseline_id")
    approve.add_argument("--approved-by", default="audio-lead")
    approve.add_argument("--role", default="audio-lead")
    approve.add_argument("--reason", default="Release audio baseline approved.")
    activate = subparsers.add_parser("activate", help="Activate an approved baseline.")
    activate.add_argument("baseline_id")
    activate.add_argument("--supersede-existing", action="store_true")
    revoke = subparsers.add_parser("revoke", help="Revoke a baseline.")
    revoke.add_argument("baseline_id")
    revoke.add_argument("--reason", default="Release audio baseline revoked.")
    subparsers.add_parser("list", help="List baselines.")
    export = subparsers.add_parser("export", help="Export baseline registry.")
    zip_cmd = subparsers.add_parser("zip", help="Build baseline registry ZIP.")
    verify = subparsers.add_parser("verify", help="Verify baseline registry ZIP.")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-active", action="store_true")
    verify.add_argument("--report-out", type=Path, default=None)
    preflight = subparsers.add_parser("preflight-release", help="Preflight a release against a baseline.")
    preflight.add_argument("release_id")
    preflight.add_argument("baseline_id")
    _add_release_audio_baseline_external_args(preflight)
    return parser

def build_verify_release_audio_baseline_registry_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Baseline Registry ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-active", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    return parser

def build_release_audio_regression_response_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Regression Response evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create a regression response plan.")
    create.add_argument("release_id")
    waiver = subparsers.add_parser("waive", help="Add a warning-level waiver.")
    waiver.add_argument("release_id")
    waiver.add_argument("--action-id", required=True)
    waiver.add_argument("--reason", required=True)
    waiver.add_argument("--waived-by", default="audio-lead")
    run = subparsers.add_parser("run-safe", help="Prepare draft-only safe actions.")
    run.add_argument("release_id")
    closeout = subparsers.add_parser("closeout", help="Close response after passed Regression recheck.")
    closeout.add_argument("release_id")
    closeout.add_argument("--closed-by", default="audio-lead")
    closeout.add_argument("--reason", default="Regression response recheck passed.")
    signoff = subparsers.add_parser("signoff", help="Sign off closed response evidence.")
    signoff.add_argument("release_id")
    signoff.add_argument("--signed-by", default="audio-lead")
    signoff.add_argument("--role", default="audio-response-reviewer")
    signoff.add_argument("--reason", default="Release audio regression response accepted.")
    status = subparsers.add_parser("status", help="Show response status.")
    status.add_argument("release_id")
    export = subparsers.add_parser("export", help="Export response package files.")
    export.add_argument("release_id")
    zip_cmd = subparsers.add_parser("zip", help="Build response ZIP.")
    zip_cmd.add_argument("release_id")
    verify = subparsers.add_parser("verify", help="Verify response ZIP.")
    verify.add_argument("release_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-closed", action="store_true")
    verify.add_argument("--require-signed", action="store_true")
    verify.add_argument("--require-regression-current", action="store_true")
    verify.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_regression_response_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Regression Response ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-closed", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--require-regression-current", action="store_true")
    parser.add_argument("--release-audio-regression", type=Path, default=None)
    parser.add_argument("--release-audio-regression-verification-report", type=Path, default=None)
    _add_release_audio_regression_external_args(parser)
    parser.add_argument("--report-out", type=Path, default=None)
    return parser

def build_release_audio_quality_observatory_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Quality Observatory evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create an audio quality observatory.")
    create.add_argument("--name", default="Release Audio Quality Observatory")
    create.add_argument("--release-id", action="append", default=[], help="Release id to include. Can be repeated.")
    list_cmd = subparsers.add_parser("list", help="List observatories.")
    del list_cmd
    refresh = subparsers.add_parser("refresh", help="Refresh observatory reports from current audio evidence.")
    refresh.add_argument("observatory_id")
    status = subparsers.add_parser("status", help="Show observatory status.")
    status.add_argument("observatory_id")
    export = subparsers.add_parser("export", help="Export observatory package files.")
    export.add_argument("observatory_id")
    zip_cmd = subparsers.add_parser("zip", help="Build observatory ZIP.")
    zip_cmd.add_argument("observatory_id")
    verify = subparsers.add_parser("verify", help="Verify observatory ZIP.")
    verify.add_argument("observatory_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-current-evidence", action="store_true")
    verify.add_argument("--require-no-critical-risk", action="store_true")
    verify.add_argument("--evidence-root", type=Path, default=None)
    verify.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_quality_observatory_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Quality Observatory ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-evidence", action="store_true")
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--require-no-critical-risk", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def build_release_audio_quality_actions_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Quality Action Queue evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    create = subparsers.add_parser("create", help="Create an action queue from a quality observatory.")
    create.add_argument("observatory_id")
    create.add_argument("--name", default=None)
    create.add_argument("--severity-floor", default="warning")
    create.add_argument("--risks-only", action="store_true", help="Only generate actions from risk register rows.")
    create.add_argument("--recommendations-only", action="store_true", help="Only generate actions from recommendations.")
    list_cmd = subparsers.add_parser("list", help="List action queues.")
    del list_cmd
    status = subparsers.add_parser("status", help="Show queue status.")
    status.add_argument("queue_id")
    refresh = subparsers.add_parser("refresh", help="Refresh queue stale status.")
    refresh.add_argument("queue_id")
    run_safe = subparsers.add_parser("run-safe", help="Run only safe queue actions.")
    run_safe.add_argument("queue_id")
    export = subparsers.add_parser("export", help="Export action queue package files.")
    export.add_argument("queue_id")
    zip_cmd = subparsers.add_parser("zip", help="Build action queue ZIP.")
    zip_cmd.add_argument("queue_id")
    verify = subparsers.add_parser("verify", help="Verify action queue ZIP.")
    verify.add_argument("queue_id")
    verify.add_argument("--strict", action="store_true")
    verify.add_argument("--require-current-observatory", action="store_true")
    verify.add_argument("--observatory-zip", type=Path, default=None)
    verify.add_argument("--observatory-verification-report", type=Path, default=None)
    verify.add_argument("--evidence-root", type=Path, default=None)
    verify.add_argument("--allow-blocking", action="store_true", help="Do not fail verification on blocked queue actions.")
    verify.add_argument("--report-out", type=Path, default=None)
    manual = subparsers.add_parser("manual-items", help="List manual action items and resolutions.")
    manual.add_argument("queue_id")
    resolve = subparsers.add_parser("resolve-manual", help="Resolve a manual action item.")
    resolve.add_argument("queue_id")
    resolve.add_argument("item_id")
    resolve.add_argument("--status", default="completed", choices=["completed", "waived", "rejected", "deferred"])
    resolve.add_argument("--resolved-by", default="local-reviewer")
    resolve.add_argument("--role", default="audio_quality_reviewer")
    resolve.add_argument("--reason", default="Manual action completed.")
    closeout = subparsers.add_parser("closeout", help="Refresh closeout report.")
    closeout.add_argument("queue_id")
    signoff = subparsers.add_parser("signoff", help="Sign a passed closeout.")
    signoff.add_argument("queue_id")
    signoff.add_argument("--signed-by", default="audio-quality-lead")
    signoff.add_argument("--role", default="audio_quality_lead")
    signoff.add_argument("--reason", default="Audio Quality Action Queue closeout accepted.")
    archive = subparsers.add_parser("archive", help="Export signoff archive files.")
    archive.add_argument("queue_id")
    archive_zip = subparsers.add_parser("archive-zip", help="Build signoff archive ZIP.")
    archive_zip.add_argument("queue_id")
    verify_archive = subparsers.add_parser("verify-archive", help="Verify signoff archive ZIP.")
    verify_archive.add_argument("queue_id")
    verify_archive.add_argument("--strict", action="store_true")
    verify_archive.add_argument("--no-require-current-queue", dest="require_current_queue", action="store_false", default=True)
    verify_archive.add_argument("--no-require-signed", dest="require_signed", action="store_false", default=True)
    verify_archive.add_argument("--queue-zip", type=Path, default=None)
    verify_archive.add_argument("--queue-verification-report", type=Path, default=None)
    verify_archive.add_argument("--observatory-zip", type=Path, default=None)
    verify_archive.add_argument("--observatory-verification-report", type=Path, default=None)
    verify_archive.add_argument("--evidence-root", type=Path, default=None)
    verify_archive.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_quality_action_queue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Quality Action Queue ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-observatory", action="store_true")
    parser.add_argument("--observatory-zip", type=Path, default=None)
    parser.add_argument("--observatory-verification-report", type=Path, default=None)
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--allow-blocking", action="store_true", help="Do not fail verification on blocked queue actions.")
    parser.add_argument("--max-zip-size-mb", type=int, default=64)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=128)
    parser.add_argument("--max-entry-count", type=int, default=100)
    return parser

def build_verify_release_audio_quality_action_queue_signoff_archive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Quality Action Queue Signoff Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current-queue", action="store_true")
    parser.add_argument("--require-signed", action="store_true")
    parser.add_argument("--queue-zip", type=Path, default=None)
    parser.add_argument("--queue-verification-report", type=Path, default=None)
    parser.add_argument("--observatory-zip", type=Path, default=None)
    parser.add_argument("--observatory-verification-report", type=Path, default=None)
    parser.add_argument("--evidence-root", type=Path, default=None)
    parser.add_argument("--allow-unresolved-manual", action="store_true")
    parser.add_argument("--max-zip-size-mb", type=int, default=64)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=128)
    parser.add_argument("--max-entry-count", type=int, default=100)
    return parser

def _add_release_audio_command_center_evidence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--certification-zip", dest="certification_zip", type=Path, default=None)
    parser.add_argument("--certification-verification-report", dest="certification_verification_report", type=Path, default=None)
    parser.add_argument("--timeline-zip", dest="timeline_zip", type=Path, default=None)
    parser.add_argument("--timeline-verification-report", dest="timeline_verification_report", type=Path, default=None)
    parser.add_argument("--regression-zip", dest="regression_zip", type=Path, default=None)
    parser.add_argument("--regression-verification-report", dest="regression_verification_report", type=Path, default=None)
    parser.add_argument("--baseline-registry-zip", dest="baseline_registry_zip", type=Path, default=None)
    parser.add_argument("--baseline-registry-verification-report", dest="baseline_registry_verification_report", type=Path, default=None)
    parser.add_argument("--regression-response-zip", dest="regression_response_zip", type=Path, default=None)
    parser.add_argument("--regression-response-verification-report", dest="regression_response_verification_report", type=Path, default=None)
    parser.add_argument("--observatory-zip", dest="observatory_zip", type=Path, default=None)
    parser.add_argument("--observatory-verification-report", dest="observatory_verification_report", type=Path, default=None)
    parser.add_argument("--action-queue-zip", dest="action_queue_zip", type=Path, default=None)
    parser.add_argument("--action-queue-verification-report", dest="action_queue_verification_report", type=Path, default=None)
    parser.add_argument("--action-queue-signoff-archive", dest="action_queue_signoff_archive", type=Path, default=None)
    parser.add_argument("--action-queue-signoff-verification-report", dest="action_queue_signoff_verification_report", type=Path, default=None)
    parser.add_argument("--evidence-root", dest="evidence_root", type=Path, default=None)

def build_release_audio_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Release Audio Command Center evidence.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action, help_text in (
        ("refresh", "Refresh the Command Center report."),
        ("report", "Show the current Command Center report."),
        ("inventory", "Show the evidence inventory."),
        ("readiness", "Show the readiness matrix."),
        ("gap-plan", "Show the gap plan."),
        ("runbook", "Create or show the safe runbook."),
        ("run-safe", "Run only safe Command Center actions."),
        ("export", "Export Command Center package files."),
        ("zip", "Build Command Center ZIP."),
        ("verify", "Verify Command Center ZIP."),
    ):
        cmd = subparsers.add_parser(action, help=help_text)
        cmd.add_argument("release_id")
        if action in {"refresh", "runbook", "run-safe", "export", "zip", "verify"}:
            _add_release_audio_command_center_evidence_args(cmd)
        if action == "verify":
            cmd.add_argument("--strict", action="store_true")
            cmd.add_argument("--require-ready", action="store_true")
            cmd.add_argument("--report-out", type=Path, default=None)
    return parser

def build_verify_release_audio_command_center_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge Release Audio Command Center ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    _add_release_audio_command_center_evidence_args(parser)
    parser.add_argument("--max-zip-size-mb", type=int, default=128)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=1000)
    return parser

def _add_command_center_acceptance_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--review-pack", type=Path, default=None)
    parser.add_argument("--review-pack-verification-report", type=Path, default=None)
    parser.add_argument("--accepted-evidence-dir", type=Path, default=None)
    parser.add_argument("--response-proof-dir", type=Path, default=None)
    parser.add_argument("--command-center-signoff-archive", type=Path, default=None)
    parser.add_argument("--command-center-signoff-archive-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-final-handoff", type=Path, default=None)
    parser.add_argument("--command-center-final-handoff-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-signoff-binding", type=Path, default=None)
    parser.add_argument("--command-center", type=Path, default=None)
    parser.add_argument("--command-center-verification-report", type=Path, default=None)
    parser.add_argument("--command-center-evidence-manifest", type=Path, default=None)

def build_acceptance_check_parser() -> argparse.ArgumentParser:
    acceptance_parser = argparse.ArgumentParser(description="Run a local Music Acceptance Lab suite.")
    acceptance_parser.add_argument("--out", type=Path, default=Path(".musicforge") / "acceptance", help="Acceptance workspace directory.")
    acceptance_parser.add_argument("--profile", default="developer_manual", help="Acceptance profile: midi_smoke, developer_manual, release_candidate, or audio_required.")
    acceptance_parser.add_argument("--cases", type=int, default=6, help="Number of representative generated songs.")
    acceptance_parser.add_argument("--render-audio", choices=["auto", "always", "never", "require"], default="auto", help="Whether to render WAV audio.")
    acceptance_parser.add_argument("--manual-required", action="store_true", help="Require manual reviews; auto-review will not be treated as release evidence.")
    acceptance_parser.add_argument("--auto-review", action="store_true", help="Write synthetic reviews for CI/smoke use.")
    acceptance_parser.add_argument("--min-rating", type=int, default=3, help="Minimum accepted review rating.")
    acceptance_parser.add_argument("--json", action="store_true", help="Print the full acceptance report as JSON.")
    acceptance_parser.add_argument("--report-out", type=Path, default=None, help="Write the acceptance report to this JSON file.")
    return acceptance_parser

def build_audio_health_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run deterministic WAV audio health checks.")
    parser.add_argument("wav_path", type=Path, help="Path to a WAV file.")
    parser.add_argument("--json", action="store_true", help="Print the full audio health report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the audio health report to this JSON file.")
    parser.add_argument("--expected-sample-rate", type=int, default=None, help="Expected WAV sample rate.")
    parser.add_argument("--expected-channels", type=int, default=None, help="Expected channel count.")
    parser.add_argument("--expected-bit-depth", type=int, default=None, help="Expected PCM bit depth.")
    return parser

def build_audio_profile_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local renderer profiles.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", help="List audio profiles.").add_argument("--include-hidden", action="store_true")
    create = subparsers.add_parser("create", help="Create or update an audio profile.")
    create.add_argument("--profile-id", default=None)
    create.add_argument("--name", required=True)
    create.add_argument("--engine", default="fluidsynth")
    create.add_argument("--engine-path", default="fluidsynth")
    create.add_argument("--soundfont", default="")
    create.add_argument("--sample-rate", type=int, default=44100)
    create.add_argument("--gain", type=float, default=0.6)
    create.add_argument("--default", action="store_true")
    test = subparsers.add_parser("test", help="Test an audio profile.")
    test.add_argument("profile_id")
    default = subparsers.add_parser("set-default", help="Set the default audio profile.")
    default.add_argument("profile_id")
    return parser

def build_release_audio_review_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage per-track Release audio review evidence.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    listing = subparsers.add_parser("list", help="List audio reviews for a Release.")
    listing.add_argument("release_id")
    summary = subparsers.add_parser("summary", help="Build the current per-track audio review summary.")
    summary.add_argument("release_id")
    summary.add_argument("--write", action="store_true", help="Persist release-audio-review-summary.json.")
    add = subparsers.add_parser("add", help="Create a per-track audio review.")
    add.add_argument("release_id")
    add.add_argument("--track-id", required=True)
    add.add_argument("--status", choices=["accepted", "needs_fix", "rejected", "waived"], default="accepted")
    add.add_argument("--review-mode", choices=["manual", "synthetic"], default="manual")
    add.add_argument("--rating", type=int, default=4)
    add.add_argument("--reviewer", default="local-user")
    add.add_argument("--notes", default="")
    add.add_argument("--playback-confirmed", action="store_true", default=False)
    task = subparsers.add_parser("create-task", help="Create a ReviewTask from an audio review marker.")
    task.add_argument("release_id")
    task.add_argument("review_id")
    task.add_argument("marker_id")
    task.add_argument("--title", default="")
    task.add_argument("--instruction", default="")
    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON output.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write command result to this JSON file.")
    return parser

def build_encoded_audio_acceptance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build encoded audio health and review acceptance evidence for a Release.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--profiles", default="", help="Comma-separated encoded audio profile ids.")
    parser.add_argument("--refresh-health", action="store_true", help="Refresh encoded audio health before building the summary.")
    parser.add_argument("--write", action="store_true", help="Persist encoded audio acceptance summary.")
    parser.add_argument("--json", action="store_true", help="Print result JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write result JSON.")
    return parser

def build_format_decision_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a Release Format Decision session and report.")
    parser.add_argument("release_id", help="Release id.")
    parser.add_argument("--profiles", default="", help="Comma-separated candidate encoded audio profile ids.")
    parser.add_argument("--select", default="", help="Comma-separated selected delivery profile ids.")
    parser.add_argument("--archive", default="", help="Comma-separated archive profile ids.")
    parser.add_argument("--fallback", default="", help="Comma-separated fallback profile ids.")
    parser.add_argument("--reject", default="", help="Comma-separated rejected profile ids.")
    parser.add_argument("--decided-by", default="local-user", help="Human decision owner.")
    parser.add_argument("--reason", default="", help="Decision rationale.")
    parser.add_argument("--activate", action="store_true", help="Set the generated session as active.")
    parser.add_argument("--json", action="store_true", help="Print result JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write result JSON.")
    return parser

def build_acceptance_diff_parser() -> argparse.ArgumentParser:
    diff_parser = argparse.ArgumentParser(description="Compare two Music Acceptance reports by regression song id.")
    diff_parser.add_argument("left_report", type=Path, help="Baseline music-acceptance-report.json.")
    diff_parser.add_argument("right_report", type=Path, help="Current music-acceptance-report.json.")
    diff_parser.add_argument("--json", action="store_true", help="Print the full diff report as JSON.")
    diff_parser.add_argument("--report-out", type=Path, default=None, help="Write the diff report to this JSON file.")
    return diff_parser

def build_acceptance_analytics_parser() -> argparse.ArgumentParser:
    analytics_parser = argparse.ArgumentParser(description="Build or read local MusicForge Acceptance Analytics.")
    analytics_parser.add_argument("--scope", choices=["global", "suite", "release", "project"], default="global", help="Analytics scope.")
    analytics_parser.add_argument("--suite-id", default=None, help="Suite id for suite scope.")
    analytics_parser.add_argument("--release-id", default=None, help="Release id for release scope.")
    analytics_parser.add_argument("--project-id", default=None, help="Project id for project scope.")
    analytics_parser.add_argument("--refresh", action="store_true", help="Recalculate and persist a fresh analytics report.")
    analytics_parser.add_argument("--json", action="store_true", help="Print the full analytics report as JSON.")
    analytics_parser.add_argument("--report-out", type=Path, default=None, help="Write the analytics report to this JSON file.")
    analytics_parser.add_argument("--fail-on", choices=["blocked", "needs_work", "watch"], default=None, help="Exit 1 when readiness is at or above this severity.")
    return analytics_parser

def build_acceptance_fix_sprint_parser() -> argparse.ArgumentParser:
    fix_parser = argparse.ArgumentParser(description="Manage local MusicForge Acceptance Fix Sprints.")
    subparsers = fix_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Fix Sprint from an Acceptance Analytics report.")
    create.add_argument("--analytics-report-id", required=True, help="Source Acceptance Analytics report id.")
    create.add_argument("--name", default=None, help="Fix Sprint name.")
    create.add_argument("--max-items", type=int, default=20, help="Maximum recommendations to import.")
    create.add_argument("--recommendation-id", action="append", dest="recommendation_ids", default=[], help="Recommendation id to include. Can be repeated.")

    show = subparsers.add_parser("show", help="Show a Fix Sprint.")
    show.add_argument("fix_sprint_id")

    listing = subparsers.add_parser("list", help="List Fix Sprints.")
    listing.add_argument("--include-archived", action="store_true")

    tasks = subparsers.add_parser("create-review-tasks", help="Create or bind ReviewTasks for Fix Sprint items.")
    tasks.add_argument("fix_sprint_id")
    tasks.add_argument("--item-id", default=None)

    recheck = subparsers.add_parser("create-recheck-suite", help="Create a recheck Acceptance Suite.")
    recheck.add_argument("fix_sprint_id")
    recheck.add_argument("--profile", default=None)

    delta = subparsers.add_parser("delta", help="Read or refresh a Fix Sprint delta report.")
    delta.add_argument("fix_sprint_id")
    delta.add_argument("--refresh", action="store_true")

    close = subparsers.add_parser("close", help="Close a Fix Sprint after recheck and delta.")
    close.add_argument("fix_sprint_id")
    close.add_argument("--force", action="store_true")
    close.add_argument("--override-reason", default="")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return fix_parser

def build_acceptance_fix_plan_parser() -> argparse.ArgumentParser:
    plan_parser = argparse.ArgumentParser(description="Manage local MusicForge knowledge-assisted Acceptance Fix Plans.")
    subparsers = plan_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Fix Plan from Acceptance Analytics and KB history.")
    create.add_argument("--analytics-report-id", required=True, help="Source Acceptance Analytics report id.")
    create.add_argument("--kb-report-id", default=None, help="Optional Acceptance KB report id.")
    create.add_argument("--max-items", type=int, default=20, help="Maximum planned items.")
    create.add_argument("--include-hidden-kb", action="store_true", help="Allow hidden KB entries in planning evidence.")

    subparsers.add_parser("list", help="List Fix Plans.").add_argument("--include-archived", action="store_true")

    show = subparsers.add_parser("show", help="Show a Fix Plan.")
    show.add_argument("plan_id")

    refresh = subparsers.add_parser("refresh", help="Refresh an existing Fix Plan.")
    refresh.add_argument("plan_id")

    create_sprint = subparsers.add_parser("create-fix-sprint", help="Create a Fix Sprint from a Fix Plan.")
    create_sprint.add_argument("plan_id")
    create_sprint.add_argument("--name", default=None)
    create_sprint.add_argument("--planned-item-id", action="append", dest="planned_item_ids", default=[])
    create_sprint.add_argument("--profile", default=None)

    review = subparsers.add_parser("review", help="Show or refresh a Fix Plan Outcome Review.")
    review.add_argument("plan_id")
    review.add_argument("--refresh", action="store_true")

    recommend = subparsers.add_parser("recommend", help="Preview a non-persisted Fix Plan.")
    recommend.add_argument("--analytics-report-id", required=True)
    recommend.add_argument("--kb-report-id", default=None)
    recommend.add_argument("--max-items", type=int, default=20)
    recommend.add_argument("--include-hidden-kb", action="store_true")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return plan_parser

def build_planning_ruleset_parser() -> argparse.ArgumentParser:
    ruleset_parser = argparse.ArgumentParser(description="Manage local MusicForge Planning Rule Sets.")
    subparsers = ruleset_parser.add_subparsers(dest="action", required=True)

    create = subparsers.add_parser("create", help="Create a Planning Rule Set.")
    create.add_argument("--template", default="baseline", help="Template: baseline, manual_conservative, kb_trust_light, waiver_strict, synthetic_strict.")
    create.add_argument("--name", default=None)
    create.add_argument("--description", default=None)

    subparsers.add_parser("list", help="List Planning Rule Sets.").add_argument("--include-archived", action="store_true")

    show = subparsers.add_parser("show", help="Show a Planning Rule Set.")
    show.add_argument("ruleset_id")

    clone = subparsers.add_parser("clone", help="Clone a Planning Rule Set.")
    clone.add_argument("ruleset_id")
    clone.add_argument("--name", default=None)

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Set.")
    archive.add_argument("ruleset_id")

    validate = subparsers.add_parser("validate", help="Validate a Planning Rule Set.")
    validate.add_argument("ruleset_id")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return ruleset_parser

def build_planning_simulation_parser() -> argparse.ArgumentParser:
    simulation_parser = argparse.ArgumentParser(description="Run local MusicForge Planning Rule Simulations.")
    subparsers = simulation_parser.add_subparsers(dest="action", required=True)

    run = subparsers.add_parser("run", help="Run a Planning Rule Simulation.")
    run.add_argument("--ruleset-id", required=True)
    run.add_argument("--release-id", default=None)
    run.add_argument("--project-id", default=None)
    run.add_argument("--review-id", action="append", dest="review_ids", default=[])
    run.add_argument("--include-warning-reviews", action="store_true", default=True)
    run.add_argument("--exclude-synthetic-only", action="store_true")

    show = subparsers.add_parser("show", help="Show a Planning Rule Simulation.")
    show.add_argument("simulation_id")

    refresh = subparsers.add_parser("refresh", help="Refresh a Planning Rule Simulation.")
    refresh.add_argument("simulation_id")

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Simulation.")
    archive.add_argument("simulation_id")

    subparsers.add_parser("list", help="List Planning Rule Simulations.").add_argument("--include-archived", action="store_true")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return simulation_parser

def build_planning_rule_governance_parser() -> argparse.ArgumentParser:
    governance_parser = argparse.ArgumentParser(description="Govern local MusicForge Planning Rule promotions and active versions.")
    subparsers = governance_parser.add_subparsers(dest="action", required=True)

    subparsers.add_parser("active", help="Show the current active Planning Rule Version.")
    subparsers.add_parser("versions", help="List Planning Rule Versions.").add_argument("--include-archived", action="store_true")

    version = subparsers.add_parser("version", help="Show one Planning Rule Version.")
    version.add_argument("version_id")

    subparsers.add_parser("promotions", help="List Planning Rule Promotions.").add_argument("--include-archived", action="store_true")

    promotion = subparsers.add_parser("promotion", help="Show one Planning Rule Promotion.")
    promotion.add_argument("promotion_id")

    request = subparsers.add_parser("promote-request", help="Create a Planning Rule Promotion request.")
    request.add_argument("--ruleset-id", required=True)
    request.add_argument("--simulation-id", required=True)
    request.add_argument("--note", default="")

    approve = subparsers.add_parser("approve", help="Approve a Planning Rule Promotion.")
    approve.add_argument("promotion_id")
    approve.add_argument("--approved-by", default="developer")
    approve.add_argument("--note", default="")
    approve.add_argument("--force", action="store_true")
    approve.add_argument("--override-reason", default="")

    reject = subparsers.add_parser("reject", help="Reject a Planning Rule Promotion.")
    reject.add_argument("promotion_id")
    reject.add_argument("--rejected-by", default="developer")
    reject.add_argument("--reason", required=True)

    promote = subparsers.add_parser("promote", help="Promote an approved Planning Rule Promotion to active.")
    promote.add_argument("promotion_id")
    promote.add_argument("--promoted-by", default="developer")
    promote.add_argument("--activation-note", default="")

    rollback = subparsers.add_parser("rollback", help="Rollback active Planning Rules to a previous version.")
    rollback.add_argument("--target-version-id", required=True)
    rollback.add_argument("--rolled-back-by", default="developer")
    rollback.add_argument("--reason", required=True)

    subparsers.add_parser("events", help="List Planning Rule Governance events.").add_argument("--limit", type=int, default=50)

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return governance_parser

def build_planning_rule_impact_parser() -> argparse.ArgumentParser:
    impact_parser = argparse.ArgumentParser(description="Monitor active MusicForge Planning Rule impact.")
    subparsers = impact_parser.add_subparsers(dest="action", required=True)

    refresh = subparsers.add_parser("refresh", help="Refresh a Planning Rule Impact report.")
    refresh.add_argument("--release-id", default=None)
    refresh.add_argument("--project-id", default=None)
    refresh.add_argument("--include-legacy", action="store_true", default=True)
    refresh.add_argument("--exclude-legacy", action="store_true")
    refresh.add_argument("--include-superseded", action="store_true", default=True)
    refresh.add_argument("--exclude-superseded", action="store_true")

    listing = subparsers.add_parser("list", help="List Planning Rule Impact reports.")
    listing.add_argument("--include-archived", action="store_true")
    listing.add_argument("--release-id", default=None)
    listing.add_argument("--project-id", default=None)

    show = subparsers.add_parser("show", help="Show one Planning Rule Impact report.")
    show.add_argument("report_id")

    refresh_existing = subparsers.add_parser("refresh-existing", help="Refresh an existing Planning Rule Impact report.")
    refresh_existing.add_argument("report_id")

    archive = subparsers.add_parser("archive", help="Archive a Planning Rule Impact report.")
    archive.add_argument("report_id")

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return impact_parser

def build_acceptance_kb_parser() -> argparse.ArgumentParser:
    kb_parser = argparse.ArgumentParser(description="Manage the local MusicForge Acceptance Knowledge Base.")
    subparsers = kb_parser.add_subparsers(dest="action", required=True)

    refresh = subparsers.add_parser("refresh", help="Refresh Acceptance KB entries and report.")
    refresh.add_argument("--project-id", default=None)
    refresh.add_argument("--release-id", default=None)

    subparsers.add_parser("report", help="Show the latest Acceptance KB report.")

    entries = subparsers.add_parser("entries", help="List Acceptance KB entries.")
    entries.add_argument("--include-hidden", action="store_true")

    show = subparsers.add_parser("show", help="Show one Acceptance KB entry.")
    show.add_argument("entry_id")

    search = subparsers.add_parser("search", help="Search Acceptance KB entries.")
    search.add_argument("--issue-type", default=None)
    search.add_argument("--style", default=None)
    search.add_argument("--song-id", default=None)
    search.add_argument("--project-id", default=None)
    search.add_argument("--release-id", default=None)
    search.add_argument("--outcome-status", default=None)

    recommend = subparsers.add_parser("recommend", help="Recommend next actions from Acceptance KB history.")
    recommend.add_argument("--issue-type", action="append", dest="issue_types", default=[])
    recommend.add_argument("--style", default=None)
    recommend.add_argument("--song-id", default=None)
    recommend.add_argument("--project-id", default=None)
    recommend.add_argument("--release-id", default=None)

    for subparser in subparsers.choices.values():
        subparser.add_argument("--json", action="store_true", help="Print JSON.")
        subparser.add_argument("--report-out", type=Path, default=None, help="Write the command result as JSON.")
    return kb_parser

def _run_audio_lab_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.audio_lab import AudioLabStore

    store = AudioLabStore()
    if args.section == "status":
        return {"ok": True, "environment": store.environment_status()}
    if args.section == "detect":
        return {"ok": True, "environment": store.detect_environment()}
    if args.section == "test-profile":
        result = store.test_profile(args.profile_id)
        return {"ok": result.get("status") != "failed", "profile_test": result, "status": result.get("status")}
    if args.section == "setup-report":
        report = store.setup_report()
        if args.report_out is not None:
            write_interface_document(args.report_out, report)
        return {"ok": True, "setup_report": report, "status": report.get("status")}
    if args.section == "smoke":
        report = store.run_smoke({"cases": args.cases, "render_audio": args.render_audio, "profile_id": args.profile_id})
        if args.report_out is not None:
            write_interface_document(args.report_out, report)
        return {"ok": report.get("status") != "failed", "smoke_run": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.section == "smoke-report":
        report = store.read_smoke_report(args.smoke_run_id)
        if args.report_out is not None:
            write_interface_document(args.report_out, report)
        return {"ok": True, "smoke_run": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.section == "session":
        if args.session_action == "create":
            session = store.create_session({"from_smoke": args.from_smoke})
            return {"ok": True, "session": session, "summary": session.get("summary", {}), "status": session.get("status")}
        if args.session_action == "list":
            sessions = store.list_sessions()
            return {"ok": True, "sessions": sessions, "summary": {"session_count": len(sessions)}, "status": "passed"}
        if args.session_action == "detail":
            session = store.read_session(args.session_id)
            return {"ok": True, "session": session, "summary": session.get("summary", {}), "status": session.get("status")}
        if args.session_action == "review":
            result = store.write_item_review(
                args.session_id,
                args.item_id,
                {
                    "result": args.result,
                    "rating": args.rating,
                    "reviewer": {"name": args.reviewer, "role": args.role},
                    "notes": args.notes,
                    "playback_confirmed": args.playback_confirmed,
                },
            )
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
        if args.session_action == "marker":
            result = store.add_marker(args.session_id, args.item_id, {"time_seconds": args.time_seconds, "category": args.category, "severity": args.severity, "message": args.message})
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
        if args.session_action == "create-review-task":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "review_task", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "create-audio-revision-draft":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "audio_revision", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "create-mix-patch-draft":
            return {"ok": True, **store.create_marker_draft(args.session_id, args.marker_id, "mix_patch", {"title": args.title, "instruction": args.instruction}), "status": "draft"}
        if args.session_action == "report":
            report = store.session_report(args.session_id)
            return {"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
        if args.session_action == "close":
            result = store.close_session(args.session_id, {"closed_by": args.closed_by})
            return {"ok": True, **result, "status": result.get("session", {}).get("status")}
    if args.section == "compare":
        if args.compare_action == "create":
            comparison = store.create_comparison({"left": args.left, "right": args.right})
            return {"ok": True, "comparison": comparison, "status": "created"}
        if args.compare_action == "review":
            comparison = store.review_comparison(
                args.comparison_id,
                {
                    "preferred": args.preferred,
                    "rating": args.rating,
                    "rating_delta": args.rating_delta,
                    "reviewer": {"name": args.reviewer, "role": args.role},
                    "notes": args.notes,
                    "playback_confirmed": args.playback_confirmed,
                },
            )
            return {"ok": True, "comparison": comparison, "status": "reviewed"}
        if args.compare_action == "report":
            report = store.comparison_report(args.comparison_id)
            return {"ok": report.get("status") != "failed", "report": report, "status": report.get("status")}
    raise ValueError("Unsupported audio-lab command.")

def _run_audio_fix_sprint_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.audio_fix_sprints import AudioFixSprintStore

    store = AudioFixSprintStore()
    if args.action == "create":
        sprint = store.create_sprint({"session_ids": args.session_ids, "name": args.name, "include_test_audio": args.include_test_audio})
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "list":
        sprints = store.list_sprints()
        return {"ok": True, "sprints": sprints, "summary": {"sprint_count": len(sprints)}, "status": "passed"}
    if args.action == "detail":
        sprint = store.read_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "refresh":
        sprint = store.refresh_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "create-drafts":
        result = store.create_drafts(args.sprint_id, {"draft_type": args.draft_type, "item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "generate-candidates":
        result = store.generate_candidates(args.sprint_id, {"item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "review-candidate":
        result = store.review_candidate(
            args.sprint_id,
            args.item_id,
            args.candidate_id,
            {
                "preferred": args.preferred,
                "rating": args.rating,
                "rating_delta": args.rating_delta,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("candidate", {}).get("status")}
    if args.action == "select-candidate":
        result = store.select_candidate(args.sprint_id, args.item_id, args.candidate_id, {"selected_by": args.selected_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "create-recheck-session":
        result = store.create_recheck_session(args.sprint_id)
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "review-recheck":
        result = store.review_recheck_item(
            args.sprint_id,
            args.item_id,
            {
                "result": args.result,
                "rating": args.rating,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "closeout":
        report = store.closeout_report(args.sprint_id)
        return {"ok": report.get("status") == "passed", "closeout": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "close":
        result = store.close_sprint(args.sprint_id, {"closed_by": args.closed_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    raise ValueError("Unsupported audio-fix-sprint command.")

def _run_audio_campaign_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.audio_campaigns import AudioCampaignStore
    from song_agent.audio_campaign_verifier import write_audio_campaign_verification_report
    from song_agent.audio_campaign_governance import AudioCampaignGovernanceStore
    from song_agent.audio_campaign_archive_verifier import write_audio_campaign_archive_verification_report
    from song_agent.audio_campaign_planner import AudioCampaignPlannerStore
    from song_agent.audio_campaign_remediation import AudioCampaignRemediationStore
    from song_agent.audio_campaign_remediation_verifier import write_audio_campaign_remediation_verification_report

    store = AudioCampaignStore()
    governance_store = AudioCampaignGovernanceStore(campaign_store=store)
    planner_store = AudioCampaignPlannerStore(audio_lab_store=store.audio_lab_store, audio_campaign_store=store)
    remediation_store = AudioCampaignRemediationStore(planner_store=planner_store, campaign_store=store, fix_sprint_store=store.audio_fix_sprint_store)
    if args.action == "plan-release":
        plan = planner_store.refresh_plan(args.release_id)
        return {"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("preflight_summary", {}), "status": plan.get("status")}
    if args.action == "preflight-release":
        preflight = planner_store.preflight(args.release_id)
        return {"ok": preflight.get("status") == "passed", "preflight": preflight, "summary": preflight.get("summary", {}), "status": preflight.get("status")}
    if args.action == "create-from-release":
        result = planner_store.create_campaign_from_release(args.release_id, {"name": args.name, "minimum_rating": args.minimum_rating, "allow_failed_preflight": args.allow_failed_preflight})
        return {"ok": True, **result, "summary": result.get("link", {}).get("coverage", {}), "status": result.get("campaign", {}).get("status")}
    if args.action == "release-status":
        status = planner_store.status(args.release_id)
        return {"ok": status.get("status") != "failed", **status}
    if args.action == "release-link":
        link = planner_store.link_campaign(args.release_id, args.campaign_id)
        return {"ok": True, "link": link, "summary": link.get("coverage", {}), "status": link.get("coverage_status")}
    if args.action == "create":
        campaign = store.create_campaign(
            {
                "session_ids": args.session_ids,
                "name": args.name,
                "profile": args.profile,
                "allow_test_audio": args.allow_test_audio,
                "allow_synthetic_review": args.allow_synthetic_review,
                "minimum_rating": args.minimum_rating,
            }
        )
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "list":
        campaigns = store.list_campaigns()
        return {"ok": True, "campaigns": campaigns, "summary": {"campaign_count": len(campaigns)}, "status": "passed"}
    if args.action == "detail":
        campaign = store.read_campaign(args.campaign_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "refresh":
        campaign = store.refresh_campaign(args.campaign_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "link-session":
        campaign = store.link_listening_session(args.campaign_id, args.session_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "create-fix-sprints":
        result = store.create_fix_sprints(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("report", {}).get("summary", {})}
    if args.action == "report":
        report = store.refresh_report(args.campaign_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "signoff":
        result = store.signoff(args.campaign_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {})}
    if args.action == "export":
        result = store.export_campaign(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {})}
    if args.action == "zip":
        result = store.build_zip(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(
            args.campaign_id,
            strict=args.strict,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_fix_sprints_closed=args.require_fix_sprints_closed,
            require_signed=args.require_signed,
        )
        if args.report_out is not None:
            write_audio_campaign_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "governance":
        report = governance_store.refresh_governance_report(args.campaign_id)
        return {"ok": report.get("status") == "signed", "governance": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "analytics":
        analytics = governance_store.refresh_analytics(args.campaign_id)
        return {"ok": True, "analytics": analytics, "summary": analytics.get("summary", {}), "status": analytics.get("status")}
    if args.action == "archive":
        manifest = governance_store.export_archive(args.campaign_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "archive-zip":
        result = governance_store.build_archive_zip(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-archive":
        report = governance_store.verify_archive(args.campaign_id, {"strict": args.strict, "require_signed": True, "require_verification_passed": True})
        if args.report_out is not None:
            write_audio_campaign_archive_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "remediation-plan":
        plan = remediation_store.refresh_plan(args.release_id)
        return {"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("summary", {}), "status": plan.get("status")}
    if args.action == "remediation-status":
        plan = remediation_store.refresh_plan(args.release_id)
        queue = remediation_store.build_action_queue(args.release_id)
        closeout = remediation_store.closeout_report(args.release_id)
        return {"ok": closeout.get("status") == "passed", "plan": plan, "queue": queue, "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "remediation-run-safe":
        result = remediation_store.run_safe_actions(args.release_id, {"closed_by": args.closed_by})
        return {"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {}), "status": result.get("closeout", {}).get("status")}
    if args.action == "remediation-closeout":
        closeout = remediation_store.closeout_report(args.release_id)
        return {"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "remediation-signoff":
        result = remediation_store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "remediation-export":
        result = remediation_store.export_package(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "remediation-zip":
        result = remediation_store.build_zip(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "remediation-verify":
        report = remediation_store.verify_zip(args.release_id, strict=args.strict, require_passed=args.require_passed, require_signed=args.require_signed)
        if args.report_out is not None:
            write_audio_campaign_remediation_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "change-request-create":
        cr = governance_store.create_change_request(args.campaign_id, {"created_by": args.created_by, "reason": args.reason, "risk": args.risk})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "change-request-approve":
        cr = governance_store.approve_change_request(args.campaign_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "signoff-reset":
        result = governance_store.reset_signoff(args.campaign_id, args.change_request_id, {"reason": args.reason})
        return {"ok": True, **result, "summary": {"change_request_id": result.get("change_request", {}).get("change_request_id")}, "status": result.get("status")}
    raise ValueError("Unsupported audio-campaign command.")

def _run_release_audio_certification_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_certification import ReleaseAudioCertificationStore
    from song_agent.release_audio_certification_verifier import write_release_audio_certification_verification_report

    store = ReleaseAudioCertificationStore()
    if args.action == "refresh":
        report = store.refresh_report(args.release_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "status":
        report = store.read_report(args.release_id, default={})
        matrix = store.read_matrix(args.release_id, default={})
        evidence = store.read_evidence_index(args.release_id, default={})
        blockers = store.read_blocker_register(args.release_id, default={})
        return {"ok": report.get("status") == "passed", "report": report, "matrix": matrix, "evidence_index": evidence, "blocker_register": blockers, "summary": report.get("summary", {}), "status": report.get("status") or "missing"}
    if args.action == "signoff":
        result = store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_package(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.release_id,
            strict=args.strict,
            require_passed=args.require_passed,
            require_signed=args.require_signed,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_remediation_when_needed=args.require_remediation_when_needed,
        )
        if args.report_out is not None:
            write_release_audio_certification_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-certification command.")

def _run_release_audio_timeline_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_timeline import ReleaseAudioTimelineStore
    from song_agent.release_audio_timeline_verifier import write_release_audio_timeline_verification_report

    store = ReleaseAudioTimelineStore()
    if args.action == "refresh":
        result = store.refresh_timeline(args.release_id, force_new=bool(args.force_new))
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "status":
        timeline_id = args.timeline_id or None
        report = store.read_timeline(args.release_id, timeline_id)
        signoff = read_json(store.signoff_path(args.release_id, timeline_id)) if store.signoff_path(args.release_id, timeline_id).exists() else {}
        return {"ok": report.get("status") == "passed", "timeline_id": report.get("timeline_id"), "report": report, "signoff": signoff, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "events":
        result = store.read_events(args.release_id, args.timeline_id or None)
        return {"ok": True, **result, "summary": {"event_count": len(result.get("events") or [])}, "status": "passed"}
    if args.action == "signoff":
        result = store.signoff_timeline(args.release_id, args.timeline_id or None, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_timeline(args.release_id, args.timeline_id or None)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id, args.timeline_id or None)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.release_id,
            args.timeline_id or None,
            strict=args.strict,
            require_passed=args.require_passed,
            require_signed=args.require_signed,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_current_certification=args.require_current_certification,
        )
        if args.report_out is not None:
            write_release_audio_timeline_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-timeline command.")

def _run_release_audio_regression_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_regression import ReleaseAudioRegressionStore
    from song_agent.release_audio_regression_verifier import write_release_audio_regression_verification_report

    store = ReleaseAudioRegressionStore()
    if args.action == "configure":
        policy = {}
        if args.identity_mode:
            policy["identity_mode"] = args.identity_mode
        config = store.configure_baseline(
            args.release_id,
            {
                "baseline_release_id": args.baseline_release_id,
                "baseline_timeline": args.baseline_timeline,
                "baseline_timeline_verification_report": args.baseline_timeline_verification_report,
                "baseline_certification": args.baseline_certification,
                "baseline_certification_verification_report": args.baseline_certification_verification_report,
                "current_timeline": args.current_timeline,
                "current_timeline_verification_report": args.current_timeline_verification_report,
                "current_certification": args.current_certification,
                "current_certification_verification_report": args.current_certification_verification_report,
                "policy": policy,
            },
        )
        return {"ok": True, "config": config, "summary": {"baseline_release_id": (config.get("baseline") or {}).get("release_id")}, "status": "configured"}
    if args.action == "refresh":
        report = store.refresh_report(args.release_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "status":
        report = store.read_report(args.release_id, default={})
        config = store.read_config(args.release_id, default={})
        signoff = read_json(store.signoff_path(args.release_id)) if store.signoff_path(args.release_id).exists() else {}
        return {"ok": report.get("status") == "passed", "config": config, "report": report, "signoff": signoff, "summary": report.get("summary", {}), "status": report.get("status") or "missing"}
    if args.action == "signoff":
        result = store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_package(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.release_id,
            strict=args.strict,
            require_passed=args.require_passed,
            require_signed=args.require_signed,
            require_current=args.require_current,
            require_baseline_current=args.require_baseline_current,
            baseline_timeline_path=args.baseline_timeline,
            baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
            baseline_certification_path=args.baseline_certification,
            baseline_certification_verification_report_path=args.baseline_certification_verification_report,
            current_timeline_path=args.current_timeline,
            current_timeline_verification_report_path=args.current_timeline_verification_report,
            current_certification_path=args.current_certification,
            current_certification_verification_report_path=args.current_certification_verification_report,
        )
        if args.report_out is not None:
            write_release_audio_regression_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-regression command.")

def _run_release_audio_baseline_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_baseline_governance import ReleaseAudioBaselineGovernanceStore
    from song_agent.release_audio_baseline_governance_verifier import write_release_audio_baseline_registry_verification_report

    store = ReleaseAudioBaselineGovernanceStore()
    if args.action == "from-release":
        baseline = store.create_from_release(
            args.release_id,
            {
                "timeline": args.timeline,
                "timeline_verification_report": args.timeline_verification_report,
                "certification": args.certification,
                "certification_verification_report": args.certification_verification_report,
                "scope_type": args.scope_type,
                "release_line_id": args.release_line_id,
            },
        )
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "approve":
        baseline = store.approve(args.baseline_id, {"approved_by": args.approved_by, "role": args.role, "reason": args.reason})
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "activate":
        baseline = store.activate(args.baseline_id, {"supersede_existing": args.supersede_existing})
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "revoke":
        baseline = store.revoke(args.baseline_id, {"reason": args.reason})
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "list":
        rows = store.list_baselines()
        return {"ok": True, "baselines": rows, "summary": {"baseline_count": len(rows)}, "status": "passed"}
    if args.action == "preflight-release":
        result = store.preflight_release(
            args.release_id,
            args.baseline_id,
            {
                "timeline": args.timeline,
                "timeline_verification_report": args.timeline_verification_report,
                "certification": args.certification,
                "certification_verification_report": args.certification_verification_report,
            },
        )
        return {"ok": result.get("status") == "passed", **result, "summary": {"baseline_id": args.baseline_id}, "status": result.get("status")}
    if args.action == "export":
        result = store.export_registry()
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip()
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(strict=args.strict, require_active=args.require_active)
        if args.report_out is not None:
            write_release_audio_baseline_registry_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-baseline command.")

def _run_release_audio_regression_response_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_regression_response import ReleaseAudioRegressionResponseStore
    from song_agent.release_audio_regression_response_verifier import write_release_audio_regression_response_verification_report

    store = ReleaseAudioRegressionResponseStore()
    if args.action == "create":
        plan = store.create_plan(args.release_id)
        return {"ok": True, "plan": plan, "summary": plan.get("summary", {}), "status": plan.get("status")}
    if args.action == "waive":
        waivers = store.add_waiver(args.release_id, {"action_id": args.action_id, "reason": args.reason, "waived_by": args.waived_by})
        return {"ok": True, "waivers": waivers, "summary": {"waiver_count": len(waivers.get("waivers", []))}, "status": "waived"}
    if args.action == "run-safe":
        result = store.run_safe_actions(args.release_id)
        return {"ok": True, **result, "summary": {"result_count": len(result.get("results", []))}, "status": result.get("status")}
    if args.action == "closeout":
        closeout = store.closeout(args.release_id, {"closed_by": args.closed_by, "reason": args.reason})
        return {"ok": closeout.get("status") == "closed", "closeout": closeout, "summary": closeout, "status": closeout.get("status")}
    if args.action == "signoff":
        result = store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("closeout", {}), "status": result.get("status")}
    if args.action == "status":
        plan = store.read_plan(args.release_id, default={})
        closeout = read_json(store.closeout_path(args.release_id)) if store.closeout_path(args.release_id).exists() else {}
        signoff = read_json(store.signoff_path(args.release_id)) if store.signoff_path(args.release_id).exists() else {}
        return {"ok": bool(plan), "plan": plan, "closeout": closeout, "signoff": signoff, "summary": plan.get("summary", {}), "status": signoff.get("status") or closeout.get("status") or plan.get("status") or "missing"}
    if args.action == "export":
        result = store.export_package(args.release_id)
        return {"ok": result.get("status") in {"closed", "signed"}, **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id)
        return {"ok": result.get("status") in {"closed", "signed"}, **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(args.release_id, strict=args.strict, require_closed=args.require_closed, require_signed=args.require_signed, require_regression_current=args.require_regression_current, **store._response_verifier_kwargs(args.release_id))  # noqa: SLF001 - CLI uses store-resolved external evidence.
        if args.report_out is not None:
            write_release_audio_regression_response_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-regression-response command.")

def _run_release_audio_quality_observatory_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
    from song_agent.release_audio_quality_observatory_verifier import write_release_audio_quality_observatory_verification_report

    store = ReleaseAudioQualityObservatoryStore()
    if args.action == "create":
        config = store.create({"name": args.name, "release_ids": args.release_id})
        return {"ok": True, "observatory": config, "summary": {"observatory_id": config.get("observatory_id")}, "status": "created"}
    if args.action == "list":
        rows = store.list_observatories()
        return {"ok": True, "observatories": rows, "summary": {"observatory_count": len(rows)}, "status": "passed"}
    if args.action == "refresh":
        summary = store.refresh(args.observatory_id)
        return {"ok": summary.get("status") == "passed", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")}
    if args.action == "status":
        config = store.read_config(args.observatory_id)
        summary = store.read_summary(args.observatory_id) if store.summary_path(args.observatory_id).exists() else {}
        return {"ok": bool(config), "observatory": config, "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status") or "missing"}
    if args.action == "export":
        result = store.export_package(args.observatory_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.observatory_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.observatory_id,
            strict=args.strict,
            require_current_evidence=args.require_current_evidence,
            evidence_root=args.evidence_root,
            require_no_critical_risk=args.require_no_critical_risk,
        )
        if args.report_out is not None:
            write_release_audio_quality_observatory_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-quality-observatory command.")

def _run_release_audio_quality_actions_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_quality_actions import ReleaseAudioQualityActionQueueStore
    from song_agent.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStore
    from song_agent.release_audio_quality_action_signoff_verifier import write_release_audio_quality_action_queue_signoff_archive_verification_report
    from song_agent.release_audio_quality_actions_verifier import write_release_audio_quality_action_queue_verification_report

    store = ReleaseAudioQualityActionQueueStore()
    signoff_store = ReleaseAudioQualityActionQueueSignoffStore(queue_store=store, release_store=store.release_store)
    if args.action == "create":
        include_risks = not bool(args.recommendations_only)
        include_recommendations = not bool(args.risks_only)
        queue = store.create_from_observatory(
            args.observatory_id,
            name=args.name,
            include_risks=include_risks,
            include_recommendations=include_recommendations,
            severity_floor=args.severity_floor,
        )
        return {"ok": True, "queue": queue, "summary": queue.get("summary", {}), "status": queue.get("status")}
    if args.action == "list":
        rows = store.list_queues()
        return {"ok": True, "queues": rows, "summary": {"queue_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        queue = store.read_queue(args.queue_id)
        summary = store.read_summary(args.queue_id)
        return {"ok": bool(queue), "queue": queue, "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status") or queue.get("status")}
    if args.action == "refresh":
        summary = store.refresh_status(args.queue_id)
        return {"ok": summary.get("status") != "stale", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")}
    if args.action == "run-safe":
        result = store.run_safe(args.queue_id)
        return {"ok": result.get("status") not in {"failed", "stale"}, **result}
    if args.action == "export":
        result = store.export_package(args.queue_id)
        return {"ok": result.get("status") not in {"failed", "stale"}, **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.queue_id)
        return {"ok": result.get("status") not in {"failed", "stale"}, **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.queue_id,
            strict=args.strict,
            require_current_observatory=args.require_current_observatory,
            observatory_zip_path=args.observatory_zip,
            observatory_verification_report_path=args.observatory_verification_report,
            evidence_root=args.evidence_root,
            require_no_blocking=not args.allow_blocking,
        )
        if args.report_out is not None:
            write_release_audio_quality_action_queue_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "manual-items":
        result = signoff_store.list_manual_items(args.queue_id)
        return {"ok": True, **result, "status": "passed"}
    if args.action == "resolve-manual":
        resolution = signoff_store.resolve_manual_item(
            args.queue_id,
            args.item_id,
            {"status": args.status, "resolved_by": args.resolved_by, "role": args.role, "reason": args.reason},
        )
        return {"ok": True, "resolution": resolution, "status": "passed"}
    if args.action == "closeout":
        closeout = signoff_store.refresh_closeout(args.queue_id)
        return {"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "signoff":
        result = signoff_store.signoff(args.queue_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result}
    if args.action == "archive":
        result = signoff_store.export_archive(args.queue_id)
        return {"ok": result.get("status") == "passed", **result}
    if args.action == "archive-zip":
        result = signoff_store.build_archive_zip(args.queue_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-archive":
        report = signoff_store.verify_archive(
            args.queue_id,
            strict=args.strict,
            require_current_queue=args.require_current_queue,
            require_signed=args.require_signed,
            queue_zip_path=args.queue_zip,
            queue_verification_report_path=args.queue_verification_report,
            observatory_zip_path=args.observatory_zip,
            observatory_verification_report_path=args.observatory_verification_report,
            evidence_root=args.evidence_root,
        )
        if args.report_out is not None:
            write_release_audio_quality_action_queue_signoff_archive_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-quality-actions command.")

def _release_audio_command_center_evidence_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "certification": {"zip": getattr(args, "certification_zip", None), "verification_report": getattr(args, "certification_verification_report", None)},
        "timeline": {"zip": getattr(args, "timeline_zip", None), "verification_report": getattr(args, "timeline_verification_report", None)},
        "regression": {"zip": getattr(args, "regression_zip", None), "verification_report": getattr(args, "regression_verification_report", None)},
        "baseline_governance": {"zip": getattr(args, "baseline_registry_zip", None), "verification_report": getattr(args, "baseline_registry_verification_report", None)},
        "regression_response": {"zip": getattr(args, "regression_response_zip", None), "verification_report": getattr(args, "regression_response_verification_report", None)},
        "observatory": {"zip": getattr(args, "observatory_zip", None), "verification_report": getattr(args, "observatory_verification_report", None)},
        "action_queue": {"zip": getattr(args, "action_queue_zip", None), "verification_report": getattr(args, "action_queue_verification_report", None)},
        "action_queue_signoff": {"zip": getattr(args, "action_queue_signoff_archive", None), "verification_report": getattr(args, "action_queue_signoff_verification_report", None)},
        "evidence_root": getattr(args, "evidence_root", None),
    }

def _run_release_audio_command_center_command(args: argparse.Namespace) -> dict[str, Any]:
    from song_agent.release_audio_command_center import ReleaseAudioCommandCenterStore
    from song_agent.release_audio_command_center_verifier import write_release_audio_command_center_verification_report

    store = ReleaseAudioCommandCenterStore()
    evidence = _release_audio_command_center_evidence_from_args(args)
    if args.action == "refresh":
        report = store.refresh(args.release_id, evidence)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "report":
        report = store.read_report(args.release_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "inventory":
        inventory = store.read_inventory(args.release_id)
        return {"ok": True, "inventory": inventory, "summary": inventory.get("summary", {}), "status": "passed"}
    if args.action == "readiness":
        readiness = read_json(store.readiness_path(args.release_id))
        return {"ok": readiness.get("status") == "ready", "readiness": readiness, "summary": readiness.get("summary", {}), "status": readiness.get("status")}
    if args.action == "gap-plan":
        gap_plan = read_json(store.gap_plan_path(args.release_id))
        return {"ok": gap_plan.get("status") == "passed", "gap_plan": gap_plan, "summary": gap_plan.get("summary", {}), "status": gap_plan.get("status")}
    if args.action == "runbook":
        runbook = store.create_runbook(args.release_id, evidence)
        return {"ok": True, "runbook": runbook, "summary": runbook.get("summary", {}), "status": "passed"}
    if args.action == "run-safe":
        result = store.run_safe(args.release_id, evidence)
        return {"ok": int((result.get("summary") or {}).get("failed_count") or 0) == 0, "runbook_results": result, "summary": result.get("summary", {}), "status": "passed" if int((result.get("summary") or {}).get("failed_count") or 0) == 0 else "failed"}
    if args.action == "export":
        result = store.export_package(args.release_id, evidence)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {})}
    if args.action == "zip":
        result = store.build_zip(args.release_id, evidence)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(args.release_id, evidence=evidence, strict=args.strict, require_ready=args.require_ready)
        if args.report_out is not None:
            write_release_audio_command_center_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-command-center command.")

def _command_center_acceptance_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload = {
        "review_pack": getattr(args, "review_pack", None),
        "review_pack_verification_report": getattr(args, "review_pack_verification_report", None),
        "accepted_evidence_dir": getattr(args, "accepted_evidence_dir", None),
        "response_proof_dir": getattr(args, "response_proof_dir", None),
        "command_center_signoff_archive": getattr(args, "command_center_signoff_archive", None),
        "command_center_signoff_archive_verification_report": getattr(args, "command_center_signoff_archive_verification_report", None),
        "command_center_final_handoff": getattr(args, "command_center_final_handoff", None),
        "command_center_final_handoff_verification_report": getattr(args, "command_center_final_handoff_verification_report", None),
        "command_center_signoff_binding": getattr(args, "command_center_signoff_binding", None),
        "command_center": getattr(args, "command_center", None),
        "command_center_verification_report": getattr(args, "command_center_verification_report", None),
        "command_center_evidence_manifest": getattr(args, "command_center_evidence_manifest", None),
        "signed_by": getattr(args, "signed_by", None),
        "role": getattr(args, "role", None),
        "reason": getattr(args, "reason", None),
    }
    policy = {}
    if getattr(args, "min_accepted_count", None) is not None:
        policy["min_accepted_count"] = args.min_accepted_count
    if getattr(args, "min_organization_count", None) is not None:
        policy["min_organization_count"] = args.min_organization_count
    if getattr(args, "required_role", None):
        policy["required_roles"] = args.required_role
    if policy:
        payload["policy"] = policy
    return {key: value for key, value in payload.items() if value is not None}

def _print_audio_lab_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("environment", {}).get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Lab")
    print(f"status: {status}")
    if "environment" in result:
        summary = result["environment"].get("summary", {})
        print(f"renderer: {summary.get('renderer_status')}")
        print(f"real_audio_ready: {summary.get('real_audio_ready')}")
    if "smoke_run" in result:
        smoke = result["smoke_run"]
        print(f"smoke_run: {smoke.get('smoke_run_id')}")
    if "session" in result:
        session = result["session"]
        print(f"session: {session.get('session_id')}")
    if "comparison" in result:
        comparison = result["comparison"]
        print(f"comparison: {comparison.get('comparison_id')}")

def _print_audio_fix_sprint_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Fix Sprint")
    print(f"status: {status}")
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    if summary:
        details = []
        for key in ("issue_count", "candidate_count", "selected_count", "resolved_count", "manual_recheck_count", "test_fake_count"):
            if key in summary:
                details.append(f"{key}={summary.get(key)}")
        if details:
            print("summary: " + " ".join(details))
    if "sprint" in result:
        sprint = result["sprint"]
        print(f"sprint: {sprint.get('fix_sprint_id')} stale={sprint.get('stale', False)}")
    if "closeout" in result:
        closeout = result["closeout"]
        blockers = closeout.get("blockers") or []
        print(f"closeout: {closeout.get('status')} blockers={','.join(blockers) if blockers else '-'}")

def _print_audio_campaign_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Campaign")
    print(f"status: {status}")
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    details = []
    for key in ("case_count", "manual_review_count", "real_audio_count", "test_fake_count", "open_fix_sprint_count"):
        if key in summary:
            details.append(f"{key}={summary.get(key)}")
    if details:
        print("summary: " + " ".join(details))
    if "campaign" in result:
        campaign = result["campaign"]
        print(f"campaign: {campaign.get('campaign_id')} {campaign.get('name')}")
    if "verification" in result:
        verification = result["verification"]
        print(f"verification: {verification.get('status')} blockers={verification.get('blockers') or []}")

def _print_release_audio_certification_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Release Audio Certification")
    print(f"status: {status}")
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    details = []
    for key in ("track_count", "manual_accepted_track_count", "real_audio_track_count", "blocker_count", "remediation_status"):
        if key in summary:
            details.append(f"{key}={summary.get(key)}")
    if details:
        print("summary: " + " ".join(details))
    if "verification" in result:
        verification = result["verification"]
        print(f"verification: {verification.get('status')} blockers={verification.get('blockers') or []}")

def run_acceptance_check(
    *,
    out_dir: Path,
    profile_id: str,
    cases: int,
    render_audio_mode: str,
    auto_review: bool,
    min_rating: int,
    manual_required: bool = False,
) -> dict[str, Any]:
    from song_agent.acceptance_profiles import get_acceptance_profile
    from song_agent.music_acceptance import AcceptanceStore, build_acceptance_report, default_acceptance_song_cases
    from song_agent.music_health import music_health_allows_review

    profile = get_acceptance_profile(profile_id)
    if cases == 6 and profile.case_count != 6:
        cases = profile.case_count
    if render_audio_mode == "require":
        render_audio_mode = "always"
    render_audio_mode = render_audio_mode if render_audio_mode != "auto" or profile.render_audio == "auto" else profile.render_audio
    store = AcceptanceStore(out_dir)
    suite_payload = {
        "name": f"v4.5 {profile.profile_id} music acceptance",
        "mode": profile.profile_id,
        "profile_id": profile.profile_id,
        "min_rating": max(min_rating, profile.min_rating),
        "require_audio_if_renderer_configured": profile.require_audio_if_renderer_configured,
        "allow_synthetic_review": profile.allow_synthetic_review and not manual_required,
        "require_manual_review": profile.require_manual_review or manual_required,
        "release_ready_profile": profile.release_ready,
    }
    if render_audio_mode == "never":
        suite_payload["require_audio_if_renderer_configured"] = False
    suite = store.create_suite(suite_payload)
    for index, song in enumerate(default_acceptance_song_cases(cases), start=1):
        request = song["request"]
        case = store.add_case(
            suite.suite_id,
            {
                "name": song.get("title") or request.get("style"),
                "source_type": "regression_songbook",
                "song_id": song.get("song_id"),
                "songbook_id": song.get("songbook_id") or "builtin_v1",
                "songbook_version": song.get("songbook_version") or "2026-05-19",
                "expectations": song.get("expectations") or {},
                "request": request,
            },
        )
        store.generate_case(suite.suite_id, case.case_id, render_audio_mode=render_audio_mode)
        health = store.run_health(suite.suite_id, case.case_id)
        if auto_review and profile.allow_synthetic_review and music_health_allows_review(health):
            store.write_review(
                suite.suite_id,
                case.case_id,
                {
                    "rating": max(min_rating, 4),
                    "status": "accepted",
                    "playback_confirmed": True,
                    "listened_by": "acceptance-check",
                    "audio_mode": "midi",
                    "review_mode": "synthetic",
                    "notes": f"Synthetic acceptance smoke review for case {index}; MIDI artifact was generated and health checks were reviewed.",
                },
            )
    report = store.build_report(suite.suite_id) if auto_review else build_acceptance_report(store, store.get_suite(suite.suite_id))
    if not auto_review:
        report = {**report, "status": "needs_review", "summary": {**report.get("summary", {}), "review_required": True}}
        write_interface_document(store.report_path(suite.suite_id), report)
    elif report.get("status") == "passed":
        store.signoff(suite.suite_id, {"signed_by": "acceptance-check", "notes": "Synthetic CI acceptance signoff."})
        report = store.read_report(suite.suite_id)
    return report

def print_acceptance_check_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge acceptance-check")
    print(f"status: {report.get('status')}")
    print(f"suite: {report.get('suite_id')}")
    print(f"cases: {summary.get('case_count', 0)}")
    print(f"accepted: {summary.get('accepted_count', 0)}")
    print(f"average_rating: {summary.get('average_rating')}")
    print(f"renderer: {summary.get('renderer_status')}")
    print(f"acceptance_status: {summary.get('acceptance_status')}")

def print_acceptance_diff_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    print("MusicForge acceptance-diff")
    print(f"status: {report.get('status')}")
    print(f"left: {report.get('left_suite_id')}")
    print(f"right: {report.get('right_suite_id')}")
    print(f"songs: {summary.get('song_count', 0)}")
    print(f"new_blockers: {summary.get('new_blocker_count', 0)}")
    print(f"rating_regressions: {summary.get('rating_regression_count', 0)}")

def print_release_audio_review_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    review = result.get("review") if isinstance(result.get("review"), dict) else {}
    print("MusicForge release-audio-review")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or review.get('status') or result.get('status') or '-'}")
    print(f"tracks: {summary.get('track_count', 0)}")
    print(f"manual accepted: {summary.get('manual_accepted_track_count', 0)}")
    print(f"missing: {len(summary.get('missing_track_ids', []) or [])}")
    print(f"stale: {summary.get('stale_review_count', 0)}")
    print(f"needs_fix: {summary.get('needs_fix_track_count', 0)}")
    if review:
        print(f"review: {review.get('review_id')}")
    if result.get("task_id"):
        print(f"task: {result.get('task_id')}")
    if result.get("reviews") is not None:
        print(f"reviews: {len(result.get('reviews') or [])}")

def print_acceptance_analytics_report(report: dict[str, Any]) -> None:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    source = report.get("source_summary") if isinstance(report.get("source_summary"), dict) else {}
    print("MusicForge acceptance-analytics")
    print(f"readiness: {summary.get('readiness_status')}")
    print(f"scope: {(report.get('scope') or {}).get('type') if isinstance(report.get('scope'), dict) else 'global'}")
    print(f"report: {report.get('report_id')}")
    print(f"suites: {source.get('suite_count', 0)}")
    print(f"cases: {summary.get('case_count', 0)}")
    print(f"manual_coverage: {summary.get('manual_coverage_rate', 0.0)}")
    print(f"average_rating: {summary.get('average_rating')}")
    print(f"issues: {summary.get('issue_count', 0)}")
    print(f"recommendations: {summary.get('recommendation_count', 0)}")

def print_acceptance_fix_sprint_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    sprint = result.get("fix_sprint") if isinstance(result.get("fix_sprint"), dict) else {}
    delta = result.get("delta_report") if isinstance(result.get("delta_report"), dict) else {}
    closeout = result.get("closeout_report") if isinstance(result.get("closeout_report"), dict) else {}
    print("MusicForge acceptance-fix-sprint")
    print(f"fix_sprint: {summary.get('fix_sprint_id') or sprint.get('fix_sprint_id') or delta.get('fix_sprint_id') or closeout.get('fix_sprint_id') or '-'}")
    print(f"status: {summary.get('status') or sprint.get('status') or closeout.get('status') or '-'}")
    if "item_count" in summary:
        print(f"items: {summary.get('item_count', 0)}")
        print(f"open_items: {summary.get('open_item_count', 0)}")
    if result.get("results"):
        print(f"task_results: {len(result.get('results') or [])}")
    if delta:
        print(f"delta_status: {(delta.get('summary') or {}).get('status')}")
    if closeout:
        print(f"closeout_status: {closeout.get('status')}")

def print_acceptance_fix_plan_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    plan = result.get("fix_plan") or result.get("fix_plan_preview")
    plan = plan if isinstance(plan, dict) else {}
    review = result.get("outcome_review") if isinstance(result.get("outcome_review"), dict) else {}
    if review:
        print("MusicForge acceptance-fix-plan review")
        print(f"review: {summary.get('review_id') or review.get('review_id') or '-'}")
        print(f"plan: {summary.get('plan_id') or review.get('plan_id') or '-'}")
        print(f"sprint: {summary.get('fix_sprint_id') or review.get('fix_sprint_id') or '-'}")
        print(f"status: {summary.get('status') or review.get('status') or '-'}")
        print(f"effectiveness: {summary.get('plan_effectiveness_score') if summary.get('plan_effectiveness_score') is not None else '-'}")
        print(f"kb_helpfulness: {summary.get('kb_evidence_helpfulness') or '-'}")
        print(f"warnings: {summary.get('warning_count', 0)}")
        return
    print("MusicForge acceptance-fix-plan")
    print(f"plan: {summary.get('plan_id') or plan.get('plan_id') or '-'}")
    print(f"status: {summary.get('status') or plan.get('status') or '-'}")
    print(f"items: {summary.get('planned_item_count', 0)}")
    print(f"kb_matches: {summary.get('kb_match_count', 0)}")
    if result.get("fix_sprint"):
        print(f"created_fix_sprint: {(result.get('fix_sprint') or {}).get('fix_sprint_id')}")

def print_planning_ruleset_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    ruleset = result.get("ruleset") if isinstance(result.get("ruleset"), dict) else {}
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    print("MusicForge planning-ruleset")
    if validation:
        print(f"validation: {validation.get('status')}")
        print(f"ruleset: {validation.get('ruleset_id')}")
        return
    print(f"ruleset: {summary.get('ruleset_id') or ruleset.get('ruleset_id') or '-'}")
    print(f"status: {summary.get('status') or ruleset.get('status') or '-'}")
    print(f"template: {summary.get('template') or '-'}")
    if result.get("rulesets") is not None:
        print(f"rulesets: {len(result.get('rulesets') or [])}")

def print_planning_simulation_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    simulation = result.get("simulation") if isinstance(result.get("simulation"), dict) else {}
    print("MusicForge planning-simulation")
    print(f"simulation: {summary.get('simulation_id') or simulation.get('simulation_id') or '-'}")
    print(f"ruleset: {summary.get('ruleset_id') or simulation.get('ruleset_id') or '-'}")
    print(f"reviews: {summary.get('review_count', 0)}")
    print(f"items: {summary.get('item_count', 0)}")
    print(f"alignment: {summary.get('baseline_alignment_score')} -> {summary.get('simulated_alignment_score')} ({summary.get('alignment_delta')})")
    print(f"recommendation: {summary.get('recommendation') or '-'}")
    if result.get("simulations") is not None:
        print(f"simulations: {len(result.get('simulations') or [])}")

def print_planning_rule_governance_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    promotion = result.get("promotion") if isinstance(result.get("promotion"), dict) else {}
    version = result.get("version") if isinstance(result.get("version"), dict) else {}
    print("MusicForge planning-rule-governance")
    print(f"status: {summary.get('status') or version.get('status') or promotion.get('status') or '-'}")
    print(f"active_version: {summary.get('active_version_id') or version.get('version_id') or '-'}")
    if promotion:
        print(f"promotion: {promotion.get('promotion_id')}")
        print(f"recommendation: {(promotion.get('evidence') or {}).get('recommendation')}")
    if result.get("versions") is not None:
        print(f"versions: {len(result.get('versions') or [])}")
    if result.get("promotions") is not None:
        print(f"promotions: {len(result.get('promotions') or [])}")
    if result.get("events") is not None:
        print(f"events: {len(result.get('events') or [])}")

def print_planning_rule_impact_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    report = result.get("impact_report") if isinstance(result.get("impact_report"), dict) else {}
    print("MusicForge planning-rule-impact")
    print(f"report: {summary.get('report_id') or report.get('report_id') or '-'}")
    print(f"status: {summary.get('status') or report.get('status') or '-'}")
    print(f"active_version: {summary.get('active_version_id') or '-'}")
    print(f"plans: {summary.get('observed_plan_count', 0)}")
    print(f"reviews: {summary.get('observed_review_count', 0)}")
    print(f"manual_reviews: {summary.get('manual_review_count', 0)}")
    print(f"synthetic_reviews: {summary.get('synthetic_review_count', 0)}")
    print(f"recommendation: {summary.get('recommendation') or '-'}")
    if result.get("reports") is not None:
        print(f"reports: {len(result.get('reports') or [])}")

def print_acceptance_kb_result(result: dict[str, Any]) -> None:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    recommendation = result.get("recommendation") if isinstance(result.get("recommendation"), dict) else {}
    entry = result.get("entry") if isinstance(result.get("entry"), dict) else {}
    print("MusicForge acceptance-kb")
    if summary:
        print(f"status: {summary.get('status') or '-'}")
        print(f"entries: {summary.get('entry_count', 0)}")
        print(f"effective: {summary.get('effective_count', 0)}")
        print(f"average_score: {summary.get('average_effectiveness_score')}")
    if result.get("entries") is not None:
        print(f"listed_entries: {len(result.get('entries') or [])}")
    if recommendation:
        print(f"recommendation: {recommendation.get('status')}")
        print(f"matches: {recommendation.get('matching_entry_count', 0)}")
    if entry:
        print(f"entry: {entry.get('entry_id')}")

def _acceptance_analytics_fail_on(readiness: str, fail_on: str | None) -> bool:
    if not fail_on:
        return False
    order = {"ready": 0, "watch": 1, "needs_work": 2, "blocked": 3, "empty": 0, "missing": 0}
    return order.get(readiness, 0) >= order.get(fail_on, 0)

def _execute_audio_lab(argv: list[str]) -> None:
    raw_args = ['audio-lab', *argv]
    parser = build_audio_lab_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_lab_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_lab_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked"}:
        raise SystemExit(1)
    return


def handle_audio_lab(argv: list[str]) -> None:
    _execute_audio_lab(argv)

def _execute_audio_fix_sprint(argv: list[str]) -> None:
    raw_args = ['audio-fix-sprint', *argv]
    parser = build_audio_fix_sprint_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_fix_sprint_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_fix_sprint_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_audio_fix_sprint(argv: list[str]) -> None:
    _execute_audio_fix_sprint(argv)

def _execute_audio_campaign(argv: list[str]) -> None:
    raw_args = ['audio-campaign', *argv]
    parser = build_audio_campaign_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_audio_campaign_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_audio_campaign_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_audio_campaign(argv: list[str]) -> None:
    _execute_audio_campaign(argv)

def _execute_release_audio_certification(argv: list[str]) -> None:
    raw_args = ['release-audio-certification', *argv]
    parser = build_release_audio_certification_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_certification_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_certification(argv: list[str]) -> None:
    _execute_release_audio_certification(argv)

def _execute_release_audio_timeline(argv: list[str]) -> None:
    raw_args = ['release-audio-timeline', *argv]
    parser = build_release_audio_timeline_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_timeline_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_timeline(argv: list[str]) -> None:
    _execute_release_audio_timeline(argv)

def _execute_release_audio_regression(argv: list[str]) -> None:
    raw_args = ['release-audio-regression', *argv]
    parser = build_release_audio_regression_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_regression_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_regression(argv: list[str]) -> None:
    _execute_release_audio_regression(argv)

def _execute_release_audio_baseline(argv: list[str]) -> None:
    raw_args = ['release-audio-baseline', *argv]
    parser = build_release_audio_baseline_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_baseline_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_baseline(argv: list[str]) -> None:
    _execute_release_audio_baseline(argv)

def _execute_release_audio_regression_response(argv: list[str]) -> None:
    raw_args = ['release-audio-regression-response', *argv]
    parser = build_release_audio_regression_response_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_regression_response_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_regression_response(argv: list[str]) -> None:
    _execute_release_audio_regression_response(argv)

def _execute_release_audio_quality_observatory(argv: list[str]) -> None:
    raw_args = ['release-audio-quality-observatory', *argv]
    parser = build_release_audio_quality_observatory_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_quality_observatory_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_quality_observatory(argv: list[str]) -> None:
    _execute_release_audio_quality_observatory(argv)

def _execute_release_audio_quality_actions(argv: list[str]) -> None:
    raw_args = ['release-audio-quality-actions', *argv]
    parser = build_release_audio_quality_actions_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_quality_actions_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_quality_actions(argv: list[str]) -> None:
    _execute_release_audio_quality_actions(argv)

def _execute_release_audio_command_center(argv: list[str]) -> None:
    raw_args = ['release-audio-command-center', *argv]
    parser = build_release_audio_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_release_audio_command_center_command(args)
    json_output = bool(getattr(args, "json", False))
    _print_release_audio_certification_result(result, json_output=json_output)
    status = str(result.get("status") or result.get("summary", {}).get("status") or "")
    if result.get("ok") is False or status in {"failed", "blocked", "stale"}:
        raise SystemExit(1)
    return


def handle_release_audio_command_center(argv: list[str]) -> None:
    _execute_release_audio_command_center(argv)

def _execute_verify_release_audio_baseline_registry_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-baseline-registry-package', *argv]
    from song_agent.release_audio_baseline_governance_verifier import (
        release_audio_baseline_registry_verification_exit_code,
        verify_release_audio_baseline_registry_package,
        write_release_audio_baseline_registry_verification_report,
    )
    parser = build_verify_release_audio_baseline_registry_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_baseline_registry_package(args.zip_path, strict=args.strict, require_active=args.require_active)
    if args.report_out is not None:
        write_release_audio_baseline_registry_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Baseline Registry verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_baseline_registry_verification_exit_code(report))


def handle_verify_release_audio_baseline_registry_package(argv: list[str]) -> None:
    _execute_verify_release_audio_baseline_registry_package(argv)

def _execute_verify_release_audio_regression_response_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-regression-response-package', *argv]
    from song_agent.release_audio_regression_response_verifier import (
        release_audio_regression_response_verification_exit_code,
        verify_release_audio_regression_response_package,
        write_release_audio_regression_response_verification_report,
    )
    parser = build_verify_release_audio_regression_response_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_regression_response_package(
        args.zip_path,
        strict=args.strict,
        require_closed=args.require_closed,
        require_signed=args.require_signed,
        require_regression_current=args.require_regression_current,
        release_audio_regression_path=args.release_audio_regression,
        release_audio_regression_verification_report_path=args.release_audio_regression_verification_report,
        baseline_timeline_path=args.baseline_timeline,
        baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
        baseline_certification_path=args.baseline_certification,
        baseline_certification_verification_report_path=args.baseline_certification_verification_report,
        current_timeline_path=args.current_timeline,
        current_timeline_verification_report_path=args.current_timeline_verification_report,
        current_certification_path=args.current_certification,
        current_certification_verification_report_path=args.current_certification_verification_report,
    )
    if args.report_out is not None:
        write_release_audio_regression_response_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Regression Response verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_regression_response_verification_exit_code(report))


def handle_verify_release_audio_regression_response_package(argv: list[str]) -> None:
    _execute_verify_release_audio_regression_response_package(argv)

def _execute_verify_release_audio_quality_observatory_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-quality-observatory-package', *argv]
    from song_agent.release_audio_quality_observatory_verifier import (
        release_audio_quality_observatory_verification_exit_code,
        verify_release_audio_quality_observatory_package,
        write_release_audio_quality_observatory_verification_report,
    )
    parser = build_verify_release_audio_quality_observatory_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_quality_observatory_package(
        args.zip_path,
        strict=args.strict,
        require_current_evidence=args.require_current_evidence,
        evidence_root=args.evidence_root,
        require_no_critical_risk=args.require_no_critical_risk,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_quality_observatory_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Quality Observatory verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_quality_observatory_verification_exit_code(report))


def handle_verify_release_audio_quality_observatory_package(argv: list[str]) -> None:
    _execute_verify_release_audio_quality_observatory_package(argv)

def _execute_verify_release_audio_quality_action_queue_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-quality-action-queue-package', *argv]
    from song_agent.release_audio_quality_actions_verifier import (
        release_audio_quality_action_queue_verification_exit_code,
        verify_release_audio_quality_action_queue_package,
        write_release_audio_quality_action_queue_verification_report,
    )
    parser = build_verify_release_audio_quality_action_queue_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_quality_action_queue_package(
        args.zip_path,
        strict=args.strict,
        require_current_observatory=args.require_current_observatory,
        observatory_zip_path=args.observatory_zip,
        observatory_verification_report_path=args.observatory_verification_report,
        evidence_root=args.evidence_root,
        require_no_blocking=not args.allow_blocking,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_quality_action_queue_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Quality Action Queue verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_quality_action_queue_verification_exit_code(report))


def handle_verify_release_audio_quality_action_queue_package(argv: list[str]) -> None:
    _execute_verify_release_audio_quality_action_queue_package(argv)

def _execute_verify_release_audio_quality_action_queue_signoff_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-quality-action-queue-signoff-archive-package', *argv]
    from song_agent.release_audio_quality_action_signoff_verifier import (
        release_audio_quality_action_queue_signoff_archive_verification_exit_code,
        verify_release_audio_quality_action_queue_signoff_archive_package,
        write_release_audio_quality_action_queue_signoff_archive_verification_report,
    )
    parser = build_verify_release_audio_quality_action_queue_signoff_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_quality_action_queue_signoff_archive_package(
        args.zip_path,
        strict=args.strict,
        require_current_queue=args.require_current_queue,
        require_signed=args.require_signed,
        queue_zip_path=args.queue_zip,
        queue_verification_report_path=args.queue_verification_report,
        observatory_zip_path=args.observatory_zip,
        observatory_verification_report_path=args.observatory_verification_report,
        evidence_root=args.evidence_root,
        require_no_unresolved_manual=not args.allow_unresolved_manual,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_quality_action_queue_signoff_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Quality Action Queue Signoff Archive verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_quality_action_queue_signoff_archive_verification_exit_code(report))


def handle_verify_release_audio_quality_action_queue_signoff_archive_package(argv: list[str]) -> None:
    _execute_verify_release_audio_quality_action_queue_signoff_archive_package(argv)

def _execute_verify_release_audio_command_center_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-command-center-package', *argv]
    from song_agent.release_audio_command_center import evidence_to_verifier_kwargs
    from song_agent.release_audio_command_center_verifier import (
        release_audio_command_center_verification_exit_code,
        verify_release_audio_command_center_package,
        write_release_audio_command_center_verification_report,
    )
    parser = build_verify_release_audio_command_center_parser()
    args = parser.parse_args(raw_args[1:])
    evidence = _release_audio_command_center_evidence_from_args(args)
    report = verify_release_audio_command_center_package(
        args.zip_path,
        strict=args.strict,
        require_ready=args.require_ready,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
        **evidence_to_verifier_kwargs(evidence),
    )
    if args.report_out is not None:
        write_release_audio_command_center_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Command Center verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
        print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_command_center_verification_exit_code(report))


def handle_verify_release_audio_command_center_package(argv: list[str]) -> None:
    _execute_verify_release_audio_command_center_package(argv)

def _execute_verify_unified_command_center_evidence_review_acceptance_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-command-center-evidence-review-acceptance-package', *argv]
    from song_agent.unified_command_center_evidence_review_verifier import (
        unified_command_center_evidence_review_acceptance_verification_exit_code,
        verify_unified_command_center_evidence_review_acceptance_package,
        write_unified_command_center_evidence_review_acceptance_verification_report,
    )
    parser = build_verify_unified_command_center_evidence_review_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_command_center_evidence_review_acceptance_package(
        args.zip_path,
        strict=args.strict,
        require_accepted=args.require_accepted,
        review_pack_path=args.review_pack,
        review_pack_verification_report_path=args.review_pack_verification_report,
        response_verification_report_path=args.response_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_command_center_evidence_review_acceptance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Command Center Evidence Review Acceptance verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_command_center_evidence_review_acceptance_verification_exit_code(report))


def handle_verify_unified_command_center_evidence_review_acceptance_package(argv: list[str]) -> None:
    _execute_verify_unified_command_center_evidence_review_acceptance_package(argv)

def _execute_verify_unified_release_program_continuity_acceptance_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-acceptance-package', *argv]
    from song_agent.unified_release_program_continuity_acceptance_verifier import (
        unified_release_program_continuity_acceptance_verification_exit_code,
        verify_unified_release_program_continuity_acceptance_package,
        write_unified_release_program_continuity_acceptance_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_acceptance_package(
        args.zip_path,
        strict=args.strict,
        require_current_kit=args.require_current_kit,
        require_signed=args.require_signed,
        require_quorum=args.require_quorum,
        continuity_kit_path=args.continuity_kit,
        continuity_kit_verification_report_path=args.continuity_kit_verification_report,
        signoff_binding_path=args.signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_acceptance_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Acceptance verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_acceptance_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_acceptance_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_acceptance_package(argv)

def _execute_verify_unified_release_program_continuity_acceptance_change_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-acceptance-change-package', *argv]
    from song_agent.unified_release_program_continuity_acceptance_change_verifier import (
        unified_release_program_continuity_acceptance_change_verification_exit_code,
        verify_unified_release_program_continuity_acceptance_change_package,
        write_unified_release_program_continuity_acceptance_change_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_acceptance_change_package(
        args.zip_path,
        strict=args.strict,
        require_current_acceptance=args.require_current_acceptance,
        acceptance_archive_path=args.acceptance_archive,
        acceptance_verification_report_path=args.acceptance_verification_report,
        acceptance_signoff_binding_path=args.acceptance_signoff_binding,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_unified_release_program_continuity_acceptance_change_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Unified Release Program Continuity Acceptance Change Control verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(unified_release_program_continuity_acceptance_change_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_acceptance_change_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_acceptance_change_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_acceptance_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-acceptance-package', *argv]
    from song_agent.unified_release_program_continuity_command_center_acceptance_verifier import (
        verification_exit_code,
        verify_unified_release_program_continuity_command_center_acceptance_package,
        write_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_command_center_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_acceptance_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        signoff_binding_path=args.signoff_binding,
        review_pack_path=args.review_pack,
        review_pack_verification_report_path=args.review_pack_verification_report,
        accepted_evidence_dir=args.accepted_evidence_dir,
        response_proof_dir=args.response_proof_dir,
        command_center_signoff_archive_path=args.command_center_signoff_archive,
        command_center_signoff_archive_verification_report_path=args.command_center_signoff_archive_verification_report,
        command_center_final_handoff_path=args.command_center_final_handoff,
        command_center_final_handoff_verification_report_path=args.command_center_final_handoff_verification_report,
        command_center_signoff_binding_path=args.command_center_signoff_binding,
        command_center_path=args.command_center,
        command_center_verification_report_path=args.command_center_verification_report,
        command_center_evidence_manifest_path=args.command_center_evidence_manifest,
    )
    if args.report_out:
        write_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Continuity Command Center Receiver Acceptance verification: {report.get('status')}")
    raise SystemExit(verification_exit_code(report))


def handle_verify_unified_release_program_continuity_command_center_acceptance_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_acceptance_package(argv)

def _execute_verify_unified_release_program_continuity_command_center_acceptance_change_package(argv: list[str]) -> None:
    raw_args = ['verify-unified-release-program-continuity-command-center-acceptance-change-package', *argv]
    from song_agent.unified_release_program_continuity_command_center_acceptance_change_verifier import (
        unified_release_program_continuity_command_center_acceptance_change_verification_exit_code,
        verify_unified_release_program_continuity_command_center_acceptance_change_package,
        write_unified_release_program_continuity_command_center_acceptance_change_verification_report,
    )
    parser = build_verify_unified_release_program_continuity_command_center_acceptance_change_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_unified_release_program_continuity_command_center_acceptance_change_package(
        args.zip_path,
        strict=args.strict,
        require_current_acceptance=args.require_current,
        acceptance_archive_path=args.acceptance_archive,
        acceptance_verification_report_path=args.acceptance_verification_report,
        acceptance_signoff_binding_path=args.acceptance_signoff_binding,
        previous_acceptance_root=args.previous_acceptance_root,
        require_reset_proofs=args.require_reset_proofs,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out:
        write_unified_release_program_continuity_command_center_acceptance_change_verification_report(report, args.report_out)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else f"Receiver Acceptance Change Control verification: {report.get('status')}")
    raise SystemExit(unified_release_program_continuity_command_center_acceptance_change_verification_exit_code(report))


def handle_verify_unified_release_program_continuity_command_center_acceptance_change_package(argv: list[str]) -> None:
    _execute_verify_unified_release_program_continuity_command_center_acceptance_change_package(argv)

def _execute_verify_audio_campaign_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-package', *argv]
    from song_agent.audio_campaign_verifier import audio_campaign_verification_exit_code, verify_audio_campaign_package, write_audio_campaign_verification_report
    parser = build_verify_audio_campaign_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_package(
        args.zip_path,
        strict=args.strict,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_fix_sprints_closed=args.require_fix_sprints_closed,
        require_signed=args.require_signed,
        require_no_open_high=args.require_no_open_high,
        require_no_open_critical=args.require_no_open_critical,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_verification_exit_code(report))


def handle_verify_audio_campaign_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_package(argv)

def _execute_verify_audio_campaign_archive_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-archive-package', *argv]
    from song_agent.audio_campaign_archive_verifier import (
        audio_campaign_archive_verification_exit_code,
        verify_audio_campaign_archive_package,
        write_audio_campaign_archive_verification_report,
    )
    parser = build_verify_audio_campaign_archive_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_archive_package(
        args.zip_path,
        strict=args.strict,
        require_signed=args.require_signed,
        require_verification_passed=args.require_verification_passed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_archive_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign Archive verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_archive_verification_exit_code(report))


def handle_verify_audio_campaign_archive_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_archive_package(argv)

def _execute_verify_audio_campaign_remediation_package(argv: list[str]) -> None:
    raw_args = ['verify-audio-campaign-remediation-package', *argv]
    from song_agent.audio_campaign_remediation_verifier import (
        audio_campaign_remediation_verification_exit_code,
        verify_audio_campaign_remediation_package,
        write_audio_campaign_remediation_verification_report,
    )
    parser = build_verify_audio_campaign_remediation_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_audio_campaign_remediation_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_audio_campaign_remediation_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Audio Campaign Remediation verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(audio_campaign_remediation_verification_exit_code(report))


def handle_verify_audio_campaign_remediation_package(argv: list[str]) -> None:
    _execute_verify_audio_campaign_remediation_package(argv)

def _execute_verify_release_audio_certification_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-certification-package', *argv]
    from song_agent.release_audio_certification_verifier import (
        release_audio_certification_verification_exit_code,
        verify_release_audio_certification_package,
        write_release_audio_certification_verification_report,
    )
    parser = build_verify_release_audio_certification_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_certification_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_remediation_when_needed=args.require_remediation_when_needed,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_certification_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Certification verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_certification_verification_exit_code(report))


def handle_verify_release_audio_certification_package(argv: list[str]) -> None:
    _execute_verify_release_audio_certification_package(argv)

def _execute_verify_release_audio_timeline_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-timeline-package', *argv]
    from song_agent.release_audio_timeline_verifier import (
        release_audio_timeline_verification_exit_code,
        verify_release_audio_timeline_package,
        write_release_audio_timeline_verification_report,
    )
    parser = build_verify_release_audio_timeline_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_timeline_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_real_audio=args.require_real_audio,
        require_manual_review=args.require_manual_review,
        require_current_certification=args.require_current_certification,
        release_audio_certification_path=args.release_audio_certification,
        release_audio_certification_verification_report_path=args.release_audio_certification_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_timeline_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Timeline verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_timeline_verification_exit_code(report))


def handle_verify_release_audio_timeline_package(argv: list[str]) -> None:
    _execute_verify_release_audio_timeline_package(argv)

def _execute_verify_release_audio_regression_package(argv: list[str]) -> None:
    raw_args = ['verify-release-audio-regression-package', *argv]
    from song_agent.release_audio_regression_verifier import (
        release_audio_regression_verification_exit_code,
        verify_release_audio_regression_package,
        write_release_audio_regression_verification_report,
    )
    parser = build_verify_release_audio_regression_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_release_audio_regression_package(
        args.zip_path,
        strict=args.strict,
        require_passed=args.require_passed,
        require_signed=args.require_signed,
        require_current=args.require_current,
        require_baseline_current=args.require_baseline_current,
        baseline_timeline_path=args.baseline_timeline,
        baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
        baseline_certification_path=args.baseline_certification,
        baseline_certification_verification_report_path=args.baseline_certification_verification_report,
        current_timeline_path=args.current_timeline,
        current_timeline_verification_report_path=args.current_timeline_verification_report,
        current_certification_path=args.current_certification,
        current_certification_verification_report_path=args.current_certification_verification_report,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_release_audio_regression_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge Release Audio Regression verification: {report.get('status')}")
        for check in report.get("checks", []):
            marker = "ok" if check.get("status") == "passed" else check.get("status")
            print(f"- {check.get('check_id')}: {marker} - {check.get('message')}")
    raise SystemExit(release_audio_regression_verification_exit_code(report))


def handle_verify_release_audio_regression_package(argv: list[str]) -> None:
    _execute_verify_release_audio_regression_package(argv)

def _execute_acceptance_check(argv: list[str]) -> None:
    raw_args = ['acceptance-check', *argv]
    parser = build_acceptance_check_parser()
    args = parser.parse_args(raw_args[1:])
    report = run_acceptance_check(
        out_dir=args.out,
        profile_id=args.profile,
        cases=args.cases,
        render_audio_mode=args.render_audio,
        auto_review=args.auto_review,
        min_rating=args.min_rating,
        manual_required=args.manual_required,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_acceptance_check_report(report)
    raise SystemExit(0 if report.get("status") in {"passed", "needs_review"} else 1)


def handle_acceptance_check(argv: list[str]) -> None:
    _execute_acceptance_check(argv)

def _execute_audio_health(argv: list[str]) -> None:
    raw_args = ['audio-health', *argv]
    from song_agent.audio_health import analyze_wav_health
    parser = build_audio_health_parser()
    args = parser.parse_args(raw_args[1:])
    report = analyze_wav_health(
        args.wav_path,
        expected_sample_rate=args.expected_sample_rate,
        expected_channels=args.expected_channels,
        expected_bit_depth=args.expected_bit_depth,
    )
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge audio-health\nstatus: {report.get('status')}\nwav_sha256: {report.get('wav_sha256')}")
    raise SystemExit(0 if report.get("status") in {"passed", "warning"} else 1)


def handle_audio_health(argv: list[str]) -> None:
    _execute_audio_health(argv)

def _execute_audio_profile(argv: list[str]) -> None:
    raw_args = ['audio-profile', *argv]
    from song_agent.audio_profiles import AudioProfileStore
    parser = build_audio_profile_parser()
    args = parser.parse_args(raw_args[1:])
    store = AudioProfileStore()
    if args.action == "list":
        result = {"profiles": [profile.public_summary() for profile in store.list_profiles(include_hidden=args.include_hidden)]}
    elif args.action == "create":
        profile = store.upsert_profile(
            {
                "profile_id": args.profile_id,
                "name": args.name,
                "engine": args.engine,
                "engine_path": args.engine_path,
                "soundfont_path": args.soundfont,
                "sample_rate": args.sample_rate,
                "gain": args.gain,
                "is_default": args.default,
            }
        )
        result = {"profile": profile.public_summary()}
    elif args.action == "test":
        result = store.test_profile(args.profile_id)
    elif args.action == "set-default":
        result = {"profile": store.set_default(args.profile_id).public_summary()}
    else:
        result = {}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("status") != "failed" else 1)


def handle_audio_profile(argv: list[str]) -> None:
    _execute_audio_profile(argv)

def _execute_release_audio_review(argv: list[str]) -> None:
    raw_args = ['release-audio-review', *argv]
    from song_agent.audio_review_evidence import AudioReviewEvidenceStore, audio_review_summary_public
    from song_agent.projects import ProjectStore
    from song_agent.releases import ReleaseStore
    parser = build_release_audio_review_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    store = AudioReviewEvidenceStore(release_store, project_store)
    if args.action == "list":
        reviews = store.list_reviews(args.release_id)
        summary = store.build_summary(args.release_id)
        result = {"ok": True, "release_id": args.release_id, "reviews": reviews, "summary": audio_review_summary_public(summary)}
    elif args.action == "summary":
        summary = store.write_summary(args.release_id) if args.write else store.build_summary(args.release_id)
        result = {"ok": True, "release_id": args.release_id, "summary": audio_review_summary_public(summary), "audio_review_summary": summary}
    elif args.action == "add":
        review = store.create_review(
            args.release_id,
            {
                "track_id": args.track_id,
                "status": args.status,
                "review_mode": args.review_mode,
                "rating": args.rating,
                "reviewer": {"name": args.reviewer},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        summary = store.build_summary(args.release_id)
        result = {"ok": True, "release_id": args.release_id, "review": review, "summary": audio_review_summary_public(summary)}
    elif args.action == "create-task":
        payload = {key: value for key, value in {"title": args.title, "instruction": args.instruction}.items() if value}
        result = {"ok": True, "release_id": args.release_id, **store.create_review_task_from_marker(args.release_id, args.review_id, args.marker_id, payload)}
    else:
        parser.error("unknown release-audio-review action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_audio_review_result(result)
    raise SystemExit(0)


def handle_release_audio_review(argv: list[str]) -> None:
    _execute_release_audio_review(argv)

def _execute_encoded_audio_acceptance(argv: list[str]) -> None:
    raw_args = ['encoded-audio-acceptance', *argv]
    from song_agent.audio_encoding import AudioEncodingStore, normalize_required_profiles
    from song_agent.audio_encoding_profiles import AudioEncodingProfileStore
    from song_agent.encoded_audio_acceptance import EncodedAudioAcceptanceStore, encoded_audio_acceptance_summary_public
    from song_agent.projects import ProjectStore
    from song_agent.releases import ReleaseStore
    parser = build_encoded_audio_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
    encoding_store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
    store = EncodedAudioAcceptanceStore(release_store, project_store=project_store, audio_encoding_store=encoding_store)
    profiles = normalize_required_profiles(args.profiles)
    health = store.refresh_health(args.release_id, profiles) if args.refresh_health else {"profiles": store.list_health(args.release_id)}
    summary = store.write_summary(args.release_id, required_profiles=profiles) if args.write else store.build_summary(args.release_id, required_profiles=profiles)
    payload = {"ok": True, "release_id": args.release_id, "health": health, "summary": encoded_audio_acceptance_summary_public(summary), "encoded_audio_acceptance": summary}
    if args.report_out is not None:
        write_interface_document(args.report_out, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge encoded-audio-acceptance\nrelease: {args.release_id}\nstatus: {summary.get('status')}\nprofiles: {summary.get('profile_count', 0)}")
    raise SystemExit(0 if summary.get("status") == "passed" else 1)


def handle_encoded_audio_acceptance(argv: list[str]) -> None:
    _execute_encoded_audio_acceptance(argv)

def _execute_format_decision(argv: list[str]) -> None:
    raw_args = ['format-decision', *argv]
    from song_agent.audio_encoding import AudioEncodingStore, normalize_required_profiles
    from song_agent.audio_encoding_profiles import AudioEncodingProfileStore
    from song_agent.distribution import DistributionStore
    from song_agent.format_decisions import FormatDecisionStore
    from song_agent.projects import ProjectStore
    from song_agent.releases import ReleaseStore
    parser = build_format_decision_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
    encoding_store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
    distribution_store = DistributionStore(release_store)
    store = FormatDecisionStore(release_store, project_store=project_store, encoding_store=encoding_store, distribution_store=distribution_store)
    session = store.create_session(args.release_id, {"profiles": normalize_required_profiles(args.profiles)})
    matrix = store.build_matrix(args.release_id, session["session_id"])
    recommendation = store.build_recommendation(args.release_id, session["session_id"])
    selected = normalize_required_profiles(args.select) or recommendation.get("selected_defaults", [])
    archive = normalize_required_profiles(args.archive) or recommendation.get("archive_defaults", [])
    fallback = normalize_required_profiles(args.fallback)
    rejected = normalize_required_profiles(args.reject) or recommendation.get("rejected_defaults", [])
    session = store.select_profiles(
        args.release_id,
        session["session_id"],
        {
            "selected_profiles": selected,
            "archive_profiles": archive,
            "fallback_profiles": fallback,
            "rejected_profiles": rejected,
            "decided_by": args.decided_by,
            "reason": args.reason,
        },
    )
    report = store.build_report(args.release_id, session["session_id"])
    active = store.activate_session(args.release_id, session["session_id"]) if args.activate else {}
    payload = {"ok": True, "release_id": args.release_id, "session": session, "matrix": matrix, "recommendation": recommendation, "report": report, "active_session": active}
    if args.report_out is not None:
        write_interface_document(args.report_out, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge format-decision\nrelease: {args.release_id}\nstatus: {report.get('status')}\nselected: {', '.join(report.get('decision', {}).get('selected_profiles', []))}")
    raise SystemExit(0 if report.get("status") in {"passed", "warning"} else 1)


def handle_format_decision(argv: list[str]) -> None:
    _execute_format_decision(argv)

def _execute_acceptance_diff(argv: list[str]) -> None:
    raw_args = ['acceptance-diff', *argv]
    from song_agent.acceptance_diff import build_acceptance_diff
    parser = build_acceptance_diff_parser()
    args = parser.parse_args(raw_args[1:])
    report = build_acceptance_diff(read_json(args.left_report), read_json(args.right_report))
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_acceptance_diff_report(report)
    raise SystemExit(0 if report.get("status") == "passed" else 1)


def handle_acceptance_diff(argv: list[str]) -> None:
    _execute_acceptance_diff(argv)

def _execute_acceptance_analytics(argv: list[str]) -> None:
    raw_args = ['acceptance-analytics', *argv]
    from song_agent.acceptance_analytics import AcceptanceAnalyticsStore, AnalyticsScope, acceptance_analytics_summary
    parser = build_acceptance_analytics_parser()
    args = parser.parse_args(raw_args[1:])
    scope = AnalyticsScope.from_values(scope_type=args.scope, suite_id=args.suite_id, release_id=args.release_id, project_id=args.project_id)
    store = AcceptanceAnalyticsStore()
    report = store.refresh(scope) if args.refresh else store.latest_report(scope)
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_acceptance_analytics_report(report)
    summary = acceptance_analytics_summary(report)
    raise SystemExit(1 if _acceptance_analytics_fail_on(str(summary.get("readiness_status") or ""), args.fail_on) else 0)


def handle_acceptance_analytics(argv: list[str]) -> None:
    _execute_acceptance_analytics(argv)

def _execute_acceptance_fix_sprint(argv: list[str]) -> None:
    raw_args = ['acceptance-fix-sprint', *argv]
    from song_agent.acceptance_fix_sprints import AcceptanceFixSprintStore, fix_sprint_summary
    parser = build_acceptance_fix_sprint_parser()
    args = parser.parse_args(raw_args[1:])
    store = AcceptanceFixSprintStore()
    if args.action == "create":
        sprint = store.create_from_analytics(
            {
                "analytics_report_id": args.analytics_report_id,
                "name": args.name,
                "max_items": args.max_items,
                "recommendation_ids": args.recommendation_ids,
            }
        )
        items = store.read_items(sprint.fix_sprint_id)
        result = {"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)}
    elif args.action == "show":
        sprint = store.read_sprint(args.fix_sprint_id)
        items = store.read_items(args.fix_sprint_id)
        result = {"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)}
    elif args.action == "list":
        sprints = store.list_sprints(include_archived=args.include_archived)
        result = {"ok": True, "fix_sprints": [sprint.to_dict() for sprint in sprints], "summary": {"fix_sprint_count": len(sprints)}}
    elif args.action == "create-review-tasks":
        result = {"ok": True, **store.create_review_tasks(args.fix_sprint_id, item_id=args.item_id)}
    elif args.action == "create-recheck-suite":
        result = {"ok": True, **store.create_recheck_suite(args.fix_sprint_id, {"profile_id": args.profile} if args.profile else {})}
    elif args.action == "delta":
        report = store.refresh_delta(args.fix_sprint_id) if args.refresh else store.read_delta(args.fix_sprint_id)
        result = {"ok": True, "delta_report": report, "summary": report.get("summary", {})}
    elif args.action == "close":
        report = store.close(args.fix_sprint_id, {"force": args.force, "override_reason": args.override_reason})
        result = {"ok": True, "closeout_report": report, "summary": report.get("summary", {})}
    else:
        parser.error("unknown acceptance-fix-sprint action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_acceptance_fix_sprint_result(result)
    raise SystemExit(0)


def handle_acceptance_fix_sprint(argv: list[str]) -> None:
    _execute_acceptance_fix_sprint(argv)

def _execute_acceptance_fix_plan(argv: list[str]) -> None:
    raw_args = ['acceptance-fix-plan', *argv]
    from song_agent.acceptance_fix_planning import AcceptanceFixPlanningStore, fix_plan_summary
    from song_agent.acceptance_fix_plan_reviews import AcceptanceFixPlanReviewStore, fix_plan_review_summary
    parser = build_acceptance_fix_plan_parser()
    args = parser.parse_args(raw_args[1:])
    store = AcceptanceFixPlanningStore()
    if args.action == "create":
        plan = store.create({"analytics_report_id": args.analytics_report_id, "kb_report_id": args.kb_report_id, "max_items": args.max_items, "include_hidden_kb": args.include_hidden_kb})
        result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
    elif args.action == "list":
        plans = store.list_plans(include_archived=args.include_archived)
        result = {"ok": True, "fix_plans": [plan.to_dict() for plan in plans], "summary": {"plan_count": len(plans)}}
    elif args.action == "show":
        plan = store.read_plan(args.plan_id)
        result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
    elif args.action == "refresh":
        plan = store.refresh_plan(args.plan_id)
        result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
    elif args.action == "create-fix-sprint":
        result = {"ok": True, **store.create_fix_sprint(args.plan_id, {"name": args.name, "planned_item_ids": args.planned_item_ids, "profile_id": args.profile})}
    elif args.action == "review":
        review_store = AcceptanceFixPlanReviewStore(plan_store=store, fix_sprint_store=store.fix_sprint_store, kb_store=store.kb_store, project_store=store.project_store)
        if args.refresh:
            review = review_store.refresh_for_plan(args.plan_id)
            result = {"ok": True, "outcome_review": review.to_dict(), "summary": fix_plan_review_summary(review)}
        else:
            review = review_store.get_or_missing_for_plan(args.plan_id)
            result = {"ok": True, "outcome_review": review, "summary": fix_plan_review_summary(review)}
    elif args.action == "recommend":
        preview = store.preview({"analytics_report_id": args.analytics_report_id, "kb_report_id": args.kb_report_id, "max_items": args.max_items, "include_hidden_kb": args.include_hidden_kb})
        result = {"ok": True, "fix_plan_preview": preview, "summary": fix_plan_summary(preview)}
    else:
        parser.error("unknown acceptance-fix-plan action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_acceptance_fix_plan_result(result)
    raise SystemExit(0)


def handle_acceptance_fix_plan(argv: list[str]) -> None:
    _execute_acceptance_fix_plan(argv)

def _execute_planning_ruleset(argv: list[str]) -> None:
    raw_args = ['planning-ruleset', *argv]
    from song_agent.planning_rule_simulation import PlanningRuleSimulationStore, ruleset_summary
    parser = build_planning_ruleset_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleSimulationStore()
    if args.action == "create":
        payload = {"template": args.template, "name": args.name, "description": args.description}
        ruleset = store.create_ruleset(payload)
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "list":
        rulesets = store.list_rulesets(include_archived=args.include_archived)
        result = {"ok": True, "rulesets": [ruleset.to_dict() for ruleset in rulesets], "summary": {"ruleset_count": len(rulesets)}}
    elif args.action == "show":
        ruleset = store.read_ruleset(args.ruleset_id)
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "clone":
        ruleset = store.clone_ruleset(args.ruleset_id, {"name": args.name} if args.name else {})
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "archive":
        ruleset = store.archive_ruleset(args.ruleset_id)
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "validate":
        result = {"ok": True, "validation": store.validate_ruleset(args.ruleset_id)}
    else:
        parser.error("unknown planning-ruleset action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_ruleset_result(result)
    raise SystemExit(0)


def handle_planning_ruleset(argv: list[str]) -> None:
    _execute_planning_ruleset(argv)

def _execute_planning_simulation(argv: list[str]) -> None:
    raw_args = ['planning-simulation', *argv]
    from song_agent.planning_rule_simulation import PlanningRuleSimulationStore, planning_simulation_summary
    parser = build_planning_simulation_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleSimulationStore()
    if args.action == "run":
        scope = {"type": "release" if args.release_id else "project" if args.project_id else "global", "release_id": args.release_id, "project_id": args.project_id}
        simulation = store.create_simulation({"ruleset_id": args.ruleset_id, "scope": scope, "review_ids": args.review_ids, "include_warning_reviews": args.include_warning_reviews, "exclude_synthetic_only": args.exclude_synthetic_only})
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "show":
        simulation = store.read_simulation(args.simulation_id)
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "refresh":
        simulation = store.refresh_simulation(args.simulation_id)
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "archive":
        simulation = store.archive_simulation(args.simulation_id)
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "list":
        simulations = store.list_simulations(include_archived=args.include_archived)
        result = {"ok": True, "simulations": [simulation.to_dict() for simulation in simulations], "summary": {"simulation_count": len(simulations)}}
    else:
        parser.error("unknown planning-simulation action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_simulation_result(result)
    raise SystemExit(0)


def handle_planning_simulation(argv: list[str]) -> None:
    _execute_planning_simulation(argv)

def _execute_planning_rule_governance(argv: list[str]) -> None:
    raw_args = ['planning-rule-governance', *argv]
    from song_agent.planning_rule_governance import PlanningRuleGovernanceStore, governance_summary, promotion_summary
    parser = build_planning_rule_governance_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleGovernanceStore()
    if args.action == "active":
        version = store.active_version()
        result = {"ok": True, "active": store.active_pointer(), "version": version.to_dict() if version else {}, "summary": store.active_summary()}
    elif args.action == "versions":
        versions = store.list_versions(include_archived=args.include_archived)
        result = {"ok": True, "versions": [version.to_dict() for version in versions], "summary": {"version_count": len(versions), "active": store.active_summary()}}
    elif args.action == "version":
        version = store.read_version(args.version_id)
        result = {"ok": True, "version": version.to_dict(), "frozen_ruleset_summary": {}, "summary": governance_summary(version, active=store.active_pointer(), evidence_stale=store.version_evidence_is_stale(version))}
    elif args.action == "promotions":
        promotions = store.list_promotions(include_archived=args.include_archived)
        result = {"ok": True, "promotions": [promotion.to_dict() for promotion in promotions], "summary": {"promotion_count": len(promotions)}}
    elif args.action == "promotion":
        promotion = store.read_promotion(args.promotion_id)
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "promote-request":
        promotion = store.create_promotion({"ruleset_id": args.ruleset_id, "simulation_id": args.simulation_id, "note": args.note})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "approve":
        promotion = store.approve_promotion(args.promotion_id, {"approved_by": args.approved_by, "approval_note": args.note, "force": args.force, "override_reason": args.override_reason})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "reject":
        promotion = store.reject_promotion(args.promotion_id, {"rejected_by": args.rejected_by, "reason": args.reason})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "promote":
        promoted = store.promote(args.promotion_id, {"promoted_by": args.promoted_by, "activation_note": args.activation_note})
        result = {"ok": True, "version": promoted["version"].to_dict(), "active": promoted["active"], "promotion": promoted["promotion"].to_dict(), "summary": promoted["summary"]}
    elif args.action == "rollback":
        rolled_back = store.rollback({"target_version_id": args.target_version_id, "rolled_back_by": args.rolled_back_by, "reason": args.reason})
        result = {"ok": True, "version": rolled_back["version"].to_dict(), "active": rolled_back["active"], "summary": rolled_back["summary"]}
    elif args.action == "events":
        events = store.events(limit=args.limit)
        result = {"ok": True, "events": events, "summary": {"event_count": len(events)}}
    else:
        parser.error("unknown planning-rule-governance action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_rule_governance_result(result)
    raise SystemExit(0)


def handle_planning_rule_governance(argv: list[str]) -> None:
    _execute_planning_rule_governance(argv)

def _execute_planning_rule_impact(argv: list[str]) -> None:
    raw_args = ['planning-rule-impact', *argv]
    from song_agent.planning_rule_impact import PlanningRuleImpactStore, planning_rule_impact_summary
    parser = build_planning_rule_impact_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleImpactStore()
    if args.action == "refresh":
        scope = {"type": "release" if args.release_id else "project" if args.project_id else "global", "release_id": args.release_id, "project_id": args.project_id}
        report = store.refresh({"scope": scope, "include_legacy": not args.exclude_legacy, "include_superseded": not args.exclude_superseded})
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    elif args.action == "list":
        reports = store.list_reports(include_archived=args.include_archived, release_id=args.release_id, project_id=args.project_id)
        result = {"ok": True, "reports": [report.to_dict() for report in reports], "summary": {"report_count": len(reports), "latest": planning_rule_impact_summary(reports[0]) if reports else {"status": "missing"}}}
    elif args.action == "show":
        report = store.get_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report), "stale": store.report_is_stale(report), "integrity_ok": store.report_integrity_ok(report)}
    elif args.action == "refresh-existing":
        report = store.refresh_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    elif args.action == "archive":
        report = store.archive_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    else:
        parser.error("unknown planning-rule-impact action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_rule_impact_result(result)
    raise SystemExit(0)


def handle_planning_rule_impact(argv: list[str]) -> None:
    _execute_planning_rule_impact(argv)

def _execute_acceptance_kb(argv: list[str]) -> None:
    raw_args = ['acceptance-kb', *argv]
    from song_agent.acceptance_kb import AcceptanceKnowledgeBaseStore, knowledge_entry_summary, knowledge_report_summary
    parser = build_acceptance_kb_parser()
    args = parser.parse_args(raw_args[1:])
    store = AcceptanceKnowledgeBaseStore()
    if args.action == "refresh":
        scope = {"type": "global", "project_id": args.project_id, "release_id": args.release_id}
        report = store.refresh(scope)
        result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
    elif args.action == "report":
        report = store.latest_report()
        result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
    elif args.action == "entries":
        entries = store.list_entries(include_hidden=args.include_hidden)
        result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
    elif args.action == "show":
        entry = store.read_entry(args.entry_id)
        result = {"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)}
    elif args.action == "search":
        query = {"issue_type": args.issue_type, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id, "outcome_status": args.outcome_status}
        entries = store.search_entries(query)
        result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
    elif args.action == "recommend":
        recommendation = store.recommend({"issue_types": args.issue_types, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id})
        result = {"ok": True, "recommendation": recommendation}
    else:
        parser.error("unknown acceptance-kb action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_acceptance_kb_result(result)
    raise SystemExit(0)


def handle_acceptance_kb(argv: list[str]) -> None:
    _execute_acceptance_kb(argv)


SPECS = (
    CommandSpec(name='audio-lab', parser=build_acceptance_analytics_parser, handler=handle_audio_lab, help='Audio Lab', group='quality'),
    CommandSpec(name='audio-fix-sprint', parser=build_acceptance_analytics_parser, handler=handle_audio_fix_sprint, help='Audio Fix Sprint', group='quality'),
    CommandSpec(name='audio-campaign', parser=build_acceptance_analytics_parser, handler=handle_audio_campaign, help='Audio Campaign', group='quality'),
    CommandSpec(name='release-audio-certification', parser=build_acceptance_analytics_parser, handler=handle_release_audio_certification, help='Release Audio Certification', group='quality'),
    CommandSpec(name='release-audio-timeline', parser=build_acceptance_analytics_parser, handler=handle_release_audio_timeline, help='Release Audio Timeline', group='quality'),
    CommandSpec(name='release-audio-regression', parser=build_acceptance_analytics_parser, handler=handle_release_audio_regression, help='Release Audio Regression', group='quality'),
    CommandSpec(name='release-audio-baseline', parser=build_acceptance_analytics_parser, handler=handle_release_audio_baseline, help='Release Audio Baseline', group='quality'),
    CommandSpec(name='release-audio-regression-response', parser=build_acceptance_analytics_parser, handler=handle_release_audio_regression_response, help='Release Audio Regression Response', group='quality'),
    CommandSpec(name='release-audio-quality-observatory', parser=build_acceptance_analytics_parser, handler=handle_release_audio_quality_observatory, help='Release Audio Quality Observatory', group='quality'),
    CommandSpec(name='release-audio-quality-actions', parser=build_acceptance_analytics_parser, handler=handle_release_audio_quality_actions, help='Release Audio Quality Actions', group='quality'),
    CommandSpec(name='release-audio-command-center', parser=build_acceptance_analytics_parser, handler=handle_release_audio_command_center, help='Release Audio Command Center', group='quality'),
    CommandSpec(name='verify-release-audio-baseline-registry-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_baseline_registry_package, help='Verify Release Audio Baseline Registry Package', group='quality'),
    CommandSpec(name='verify-release-audio-regression-response-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_regression_response_package, help='Verify Release Audio Regression Response Package', group='quality'),
    CommandSpec(name='verify-release-audio-quality-observatory-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_quality_observatory_package, help='Verify Release Audio Quality Observatory Package', group='quality'),
    CommandSpec(name='verify-release-audio-quality-action-queue-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_quality_action_queue_package, help='Verify Release Audio Quality Action Queue Package', group='quality'),
    CommandSpec(name='verify-release-audio-quality-action-queue-signoff-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_quality_action_queue_signoff_archive_package, help='Verify Release Audio Quality Action Queue Signoff Archive Package', group='quality'),
    CommandSpec(name='verify-release-audio-command-center-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_command_center_package, help='Verify Release Audio Command Center Package', group='quality'),
    CommandSpec(name='verify-unified-command-center-evidence-review-acceptance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_command_center_evidence_review_acceptance_package, help='Verify Unified Command Center Evidence Review Acceptance Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-acceptance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_acceptance_package, help='Verify Unified Release Program Continuity Acceptance Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-acceptance-change-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_acceptance_change_package, help='Verify Unified Release Program Continuity Acceptance Change Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-acceptance-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_acceptance_package, help='Verify Unified Release Program Continuity Command Center Acceptance Package', group='quality'),
    CommandSpec(name='verify-unified-release-program-continuity-command-center-acceptance-change-package', parser=build_acceptance_analytics_parser, handler=handle_verify_unified_release_program_continuity_command_center_acceptance_change_package, help='Verify Unified Release Program Continuity Command Center Acceptance Change Package', group='quality'),
    CommandSpec(name='verify-audio-campaign-package', parser=build_acceptance_analytics_parser, handler=handle_verify_audio_campaign_package, help='Verify Audio Campaign Package', group='quality'),
    CommandSpec(name='verify-audio-campaign-archive-package', parser=build_acceptance_analytics_parser, handler=handle_verify_audio_campaign_archive_package, help='Verify Audio Campaign Archive Package', group='quality'),
    CommandSpec(name='verify-audio-campaign-remediation-package', parser=build_acceptance_analytics_parser, handler=handle_verify_audio_campaign_remediation_package, help='Verify Audio Campaign Remediation Package', group='quality'),
    CommandSpec(name='verify-release-audio-certification-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_certification_package, help='Verify Release Audio Certification Package', group='quality'),
    CommandSpec(name='verify-release-audio-timeline-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_timeline_package, help='Verify Release Audio Timeline Package', group='quality'),
    CommandSpec(name='verify-release-audio-regression-package', parser=build_acceptance_analytics_parser, handler=handle_verify_release_audio_regression_package, help='Verify Release Audio Regression Package', group='quality'),
    CommandSpec(name='acceptance-check', parser=build_acceptance_analytics_parser, handler=handle_acceptance_check, help='Acceptance Check', group='quality'),
    CommandSpec(name='audio-health', parser=build_acceptance_analytics_parser, handler=handle_audio_health, help='Audio Health', group='quality'),
    CommandSpec(name='audio-profile', parser=build_acceptance_analytics_parser, handler=handle_audio_profile, help='Audio Profile', group='quality'),
    CommandSpec(name='release-audio-review', parser=build_acceptance_analytics_parser, handler=handle_release_audio_review, help='Release Audio Review', group='quality'),
    CommandSpec(name='encoded-audio-acceptance', parser=build_acceptance_analytics_parser, handler=handle_encoded_audio_acceptance, help='Encoded Audio Acceptance', group='quality'),
    CommandSpec(name='format-decision', parser=build_acceptance_analytics_parser, handler=handle_format_decision, help='Format Decision', group='quality'),
    CommandSpec(name='acceptance-diff', parser=build_acceptance_analytics_parser, handler=handle_acceptance_diff, help='Acceptance Diff', group='quality'),
    CommandSpec(name='acceptance-analytics', parser=build_acceptance_analytics_parser, handler=handle_acceptance_analytics, help='Acceptance Analytics', group='quality'),
    CommandSpec(name='acceptance-fix-sprint', parser=build_acceptance_fix_plan_parser, handler=handle_acceptance_fix_sprint, help='Acceptance Fix Sprint', group='quality'),
    CommandSpec(name='acceptance-fix-plan', parser=build_acceptance_fix_plan_parser, handler=handle_acceptance_fix_plan, help='Acceptance Fix Plan', group='quality'),
    CommandSpec(name='planning-ruleset', parser=build_acceptance_kb_parser, handler=handle_planning_ruleset, help='Planning Ruleset', group='quality'),
    CommandSpec(name='planning-simulation', parser=build_acceptance_kb_parser, handler=handle_planning_simulation, help='Planning Simulation', group='quality'),
    CommandSpec(name='planning-rule-governance', parser=build_acceptance_kb_parser, handler=handle_planning_rule_governance, help='Planning Rule Governance', group='quality'),
    CommandSpec(name='planning-rule-impact', parser=build_acceptance_kb_parser, handler=handle_planning_rule_impact, help='Planning Rule Impact', group='quality'),
    CommandSpec(name='acceptance-kb', parser=build_acceptance_kb_parser, handler=handle_acceptance_kb, help='Acceptance Kb', group='quality'),
)
