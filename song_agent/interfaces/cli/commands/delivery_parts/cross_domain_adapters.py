from __future__ import annotations

from song_agent.interfaces.cli.bindings import BINDINGS as CLI_BINDINGS

from . import dependencies as _commands_delivery_parts_dependencies; Any, AudioEncodingProfileStore, AudioEncodingStore, CommandSpec, DistributionStore, Path, ProjectStore, ProviderConfig, ProviderError, ReleaseOperationsAuditStore, ReleaseOperationsReviewerPackStore, ReleaseOperationsRunbookStore, ReleaseOperationsSignoffStore, ReleaseOperationsStore, ReleaseStore, SongRequest, SubmissionEvidenceStore, SubmissionStore, argparse, audit_summary, build_auth_config, command_center_signoff_verification_exit_code, distribution_verification_exit_code, generate_request, json, load_provider_config, operations_report_summary, operations_signoff_summary, os, print_distribution_verification_report, print_release_operations_archive_verification_report, print_release_operations_audit_verification_report, print_release_operations_reviewer_pack_verification_report, print_release_operations_runbook_verification_report, print_release_operations_verification_report, print_submission_evidence_verification_report, print_submission_verification_report, print_verification_report, provider_configured, read_json, release_operations_archive_verification_exit_code, release_operations_archive_verification_summary, release_operations_audit_verification_exit_code, release_operations_audit_verification_summary, release_operations_reviewer_pack_verification_exit_code, release_operations_reviewer_pack_verification_summary, release_operations_runbook_verification_exit_code, release_operations_runbook_verification_summary, release_operations_verification_exit_code, release_operations_verification_summary, release_verification_exit_code, retrospective_summary, reviewer_pack_summary, runbook_summary, submission_evidence_verification_exit_code, submission_verification_exit_code, sys, test_provider_config, unified_command_center_release_train_change_control_verification_exit_code, unified_command_center_release_train_handoff_verification_exit_code, unified_command_center_release_train_lifecycle_verification_exit_code, unified_command_center_release_train_verification_exit_code, unified_release_program_continuity_command_center_verification_exit_code, unified_release_program_continuity_distribution_verification_exit_code, unified_release_program_continuity_verification_exit_code, unified_release_program_handoff_verification_exit_code, unified_release_program_operations_verification_exit_code, unified_release_program_vault_operations_verification_exit_code, unified_release_program_vault_verification_exit_code, unified_release_program_verification_exit_code, verify_distribution_package, verify_release_operations_archive_package, verify_release_operations_audit_package, verify_release_operations_package, verify_release_operations_reviewer_pack, verify_release_operations_runbook_package, verify_release_zip, verify_submission_evidence_package, verify_submission_package, verify_unified_command_center_release_train_change_control_package, verify_unified_command_center_release_train_handoff_package, verify_unified_command_center_release_train_lifecycle_package, verify_unified_command_center_release_train_package, verify_unified_release_program_continuity_command_center_final_handoff_package, verify_unified_release_program_continuity_command_center_package, verify_unified_release_program_continuity_command_center_signoff_package, verify_unified_release_program_continuity_distribution_package, verify_unified_release_program_continuity_package, verify_unified_release_program_handoff_package, verify_unified_release_program_operations_package, verify_unified_release_program_package, verify_unified_release_program_vault_operations_package, verify_unified_release_program_vault_package, write_distribution_verification_report, write_interface_document, write_json, write_release_operations_archive_verification_report, write_release_operations_audit_verification_report, write_release_operations_reviewer_pack_verification_report, write_release_operations_runbook_verification_report, write_submission_evidence_verification_report, write_submission_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_release_program_continuity_command_center_final_handoff_verification_report, write_unified_release_program_continuity_command_center_signoff_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report, write_verification_report = (_commands_delivery_parts_dependencies.Any, _commands_delivery_parts_dependencies.AudioEncodingProfileStore, _commands_delivery_parts_dependencies.AudioEncodingStore, _commands_delivery_parts_dependencies.CommandSpec, _commands_delivery_parts_dependencies.DistributionStore, _commands_delivery_parts_dependencies.Path, _commands_delivery_parts_dependencies.ProjectStore, _commands_delivery_parts_dependencies.ProviderConfig, _commands_delivery_parts_dependencies.ProviderError, _commands_delivery_parts_dependencies.ReleaseOperationsAuditStore, _commands_delivery_parts_dependencies.ReleaseOperationsReviewerPackStore, _commands_delivery_parts_dependencies.ReleaseOperationsRunbookStore, _commands_delivery_parts_dependencies.ReleaseOperationsSignoffStore, _commands_delivery_parts_dependencies.ReleaseOperationsStore, _commands_delivery_parts_dependencies.ReleaseStore, _commands_delivery_parts_dependencies.SongRequest, _commands_delivery_parts_dependencies.SubmissionEvidenceStore, _commands_delivery_parts_dependencies.SubmissionStore, _commands_delivery_parts_dependencies.argparse, _commands_delivery_parts_dependencies.audit_summary, _commands_delivery_parts_dependencies.build_auth_config, _commands_delivery_parts_dependencies.command_center_signoff_verification_exit_code, _commands_delivery_parts_dependencies.distribution_verification_exit_code, _commands_delivery_parts_dependencies.generate_request, _commands_delivery_parts_dependencies.json, _commands_delivery_parts_dependencies.load_provider_config, _commands_delivery_parts_dependencies.operations_report_summary, _commands_delivery_parts_dependencies.operations_signoff_summary, _commands_delivery_parts_dependencies.os, _commands_delivery_parts_dependencies.print_distribution_verification_report, _commands_delivery_parts_dependencies.print_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.print_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.print_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.print_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.print_release_operations_verification_report, _commands_delivery_parts_dependencies.print_submission_evidence_verification_report, _commands_delivery_parts_dependencies.print_submission_verification_report, _commands_delivery_parts_dependencies.print_verification_report, _commands_delivery_parts_dependencies.provider_configured, _commands_delivery_parts_dependencies.read_json, _commands_delivery_parts_dependencies.release_operations_archive_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_archive_verification_summary, _commands_delivery_parts_dependencies.release_operations_audit_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_audit_verification_summary, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_reviewer_pack_verification_summary, _commands_delivery_parts_dependencies.release_operations_runbook_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_runbook_verification_summary, _commands_delivery_parts_dependencies.release_operations_verification_exit_code, _commands_delivery_parts_dependencies.release_operations_verification_summary, _commands_delivery_parts_dependencies.release_verification_exit_code, _commands_delivery_parts_dependencies.retrospective_summary, _commands_delivery_parts_dependencies.reviewer_pack_summary, _commands_delivery_parts_dependencies.runbook_summary, _commands_delivery_parts_dependencies.submission_evidence_verification_exit_code, _commands_delivery_parts_dependencies.submission_verification_exit_code, _commands_delivery_parts_dependencies.sys, _commands_delivery_parts_dependencies.test_provider_config, _commands_delivery_parts_dependencies.unified_command_center_release_train_change_control_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_lifecycle_verification_exit_code, _commands_delivery_parts_dependencies.unified_command_center_release_train_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_command_center_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_distribution_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_continuity_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_handoff_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_operations_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_vault_verification_exit_code, _commands_delivery_parts_dependencies.unified_release_program_verification_exit_code, _commands_delivery_parts_dependencies.verify_distribution_package, _commands_delivery_parts_dependencies.verify_release_operations_archive_package, _commands_delivery_parts_dependencies.verify_release_operations_audit_package, _commands_delivery_parts_dependencies.verify_release_operations_package, _commands_delivery_parts_dependencies.verify_release_operations_reviewer_pack, _commands_delivery_parts_dependencies.verify_release_operations_runbook_package, _commands_delivery_parts_dependencies.verify_release_zip, _commands_delivery_parts_dependencies.verify_submission_evidence_package, _commands_delivery_parts_dependencies.verify_submission_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_change_control_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_handoff_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_lifecycle_package, _commands_delivery_parts_dependencies.verify_unified_command_center_release_train_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_final_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_command_center_signoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_distribution_package, _commands_delivery_parts_dependencies.verify_unified_release_program_continuity_package, _commands_delivery_parts_dependencies.verify_unified_release_program_handoff_package, _commands_delivery_parts_dependencies.verify_unified_release_program_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_operations_package, _commands_delivery_parts_dependencies.verify_unified_release_program_vault_package, _commands_delivery_parts_dependencies.write_distribution_verification_report, _commands_delivery_parts_dependencies.write_interface_document, _commands_delivery_parts_dependencies.write_json, _commands_delivery_parts_dependencies.write_release_operations_archive_verification_report, _commands_delivery_parts_dependencies.write_release_operations_audit_verification_report, _commands_delivery_parts_dependencies.write_release_operations_reviewer_pack_verification_report, _commands_delivery_parts_dependencies.write_release_operations_runbook_verification_report, _commands_delivery_parts_dependencies.write_submission_evidence_verification_report, _commands_delivery_parts_dependencies.write_submission_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_delivery_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_final_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_signoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_delivery_parts_dependencies.write_unified_release_program_verification_report, _commands_delivery_parts_dependencies.write_verification_report)

def _acceptance_analytics_fail_on(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality._acceptance_analytics_fail_on(*args, **kwargs)

def _build_public_trust_center_publication_store(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust._build_public_trust_center_publication_store(*args, **kwargs)

def _build_public_trust_center_store(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust._build_public_trust_center_store(*args, **kwargs)

def _build_release_portfolio_governance_attestation_portal_store(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust._build_release_portfolio_governance_attestation_portal_store(*args, **kwargs)

def _trust_operations_assurance_source_payload(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust._trust_operations_assurance_source_payload(*args, **kwargs)

def _trust_operations_assurance_watch_source_payload(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust._trust_operations_assurance_watch_source_payload(*args, **kwargs)

def _trust_operations_final_readiness_source_payload(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust._trust_operations_final_readiness_source_payload(*args, **kwargs)

def build_acceptance_analytics_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_acceptance_analytics_parser(*args, **kwargs)

def build_acceptance_check_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_acceptance_check_parser(*args, **kwargs)

def build_acceptance_diff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_acceptance_diff_parser(*args, **kwargs)

def build_acceptance_fix_plan_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_acceptance_fix_plan_parser(*args, **kwargs)

def build_acceptance_fix_sprint_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_acceptance_fix_sprint_parser(*args, **kwargs)

def build_acceptance_kb_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_acceptance_kb_parser(*args, **kwargs)

def build_audio_health_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_audio_health_parser(*args, **kwargs)

def build_audio_profile_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_audio_profile_parser(*args, **kwargs)

def build_encoded_audio_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_encoded_audio_acceptance_parser(*args, **kwargs)

def build_format_decision_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_format_decision_parser(*args, **kwargs)

def build_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.creation.build_parser(*args, **kwargs)

def build_planning_rule_governance_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_planning_rule_governance_parser(*args, **kwargs)

def build_planning_rule_impact_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_planning_rule_impact_parser(*args, **kwargs)

def build_planning_ruleset_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_planning_ruleset_parser(*args, **kwargs)

def build_planning_simulation_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_planning_simulation_parser(*args, **kwargs)

def build_public_trust_center_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_public_trust_center_parser(*args, **kwargs)

def build_public_trust_center_publication_monitor_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_public_trust_center_publication_monitor_parser(*args, **kwargs)

def build_public_trust_center_publication_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_public_trust_center_publication_parser(*args, **kwargs)

def build_release_audio_review_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_release_audio_review_parser(*args, **kwargs)

def build_release_check_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.release_check.build_release_check_parser(*args, **kwargs)

def build_release_portfolio_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_audit_parser(*args, **kwargs)

def build_release_portfolio_governance_attestation_accepted_evidence_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_attestation_accepted_evidence_parser(*args, **kwargs)

def build_release_portfolio_governance_attestation_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_attestation_parser(*args, **kwargs)

def build_release_portfolio_governance_attestation_portal_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_attestation_portal_parser(*args, **kwargs)

def build_release_portfolio_governance_attestation_portal_review_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_attestation_portal_review_parser(*args, **kwargs)

def build_release_portfolio_governance_attestation_registry_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_attestation_registry_parser(*args, **kwargs)

def build_release_portfolio_governance_attestation_transparency_acknowledgement_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_attestation_transparency_acknowledgement_parser(*args, **kwargs)

def build_release_portfolio_governance_attestation_transparency_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_attestation_transparency_parser(*args, **kwargs)

def build_release_portfolio_governance_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_audit_parser(*args, **kwargs)

def build_release_portfolio_governance_evidence_vault_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_evidence_vault_parser(*args, **kwargs)

def build_release_portfolio_governance_final_board_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_final_board_parser(*args, **kwargs)

def build_release_portfolio_governance_queue_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_queue_parser(*args, **kwargs)

def build_release_portfolio_governance_reviewer_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_reviewer_pack_parser(*args, **kwargs)

def build_release_portfolio_governance_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_release_portfolio_governance_signoff_parser(*args, **kwargs)

def build_trust_operations_assurance_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_assurance_parser(*args, **kwargs)

def build_trust_operations_assurance_watch_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_assurance_watch_parser(*args, **kwargs)

def build_trust_operations_assurance_watch_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_assurance_watch_signoff_parser(*args, **kwargs)

def build_trust_operations_control_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_control_signoff_parser(*args, **kwargs)

def build_trust_operations_controls_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_controls_parser(*args, **kwargs)

def build_trust_operations_final_readiness_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_final_readiness_parser(*args, **kwargs)

def build_trust_operations_hub_incidents_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_hub_incidents_parser(*args, **kwargs)

def build_trust_operations_hub_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_hub_parser(*args, **kwargs)

def build_trust_operations_hub_runbook_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_hub_runbook_parser(*args, **kwargs)

def build_trust_operations_incident_knowledge_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_trust_operations_incident_knowledge_parser(*args, **kwargs)

def build_verify_audio_campaign_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_verify_audio_campaign_archive_parser(*args, **kwargs)

def build_verify_audio_campaign_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_verify_audio_campaign_parser(*args, **kwargs)

def build_verify_audio_campaign_remediation_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_verify_audio_campaign_remediation_parser(*args, **kwargs)

def build_verify_human_review_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.studio.build_verify_human_review_pack_parser(*args, **kwargs)

def build_verify_maintenance_backup_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.maintenance.build_verify_maintenance_backup_parser(*args, **kwargs)

def build_verify_public_trust_center_acceptance_board_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_acceptance_board_parser(*args, **kwargs)

def build_verify_public_trust_center_acceptance_board_signoff_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_acceptance_board_signoff_archive_parser(*args, **kwargs)

def build_verify_public_trust_center_anchor_registry_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_anchor_registry_parser(*args, **kwargs)

def build_verify_public_trust_center_anchor_transparency_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_anchor_transparency_parser(*args, **kwargs)

def build_verify_public_trust_center_distribution_kit_accepted_evidence_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_distribution_kit_accepted_evidence_parser(*args, **kwargs)

def build_verify_public_trust_center_distribution_kit_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_distribution_kit_parser(*args, **kwargs)

def build_verify_public_trust_center_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_parser(*args, **kwargs)

def build_verify_public_trust_center_publication_mirror_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_publication_mirror_parser(*args, **kwargs)

def build_verify_public_trust_center_publication_monitoring_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_publication_monitoring_parser(*args, **kwargs)

def build_verify_public_trust_center_publication_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_public_trust_center_publication_parser(*args, **kwargs)

def build_verify_release_audio_certification_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_verify_release_audio_certification_parser(*args, **kwargs)

def build_verify_release_audio_regression_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_verify_release_audio_regression_parser(*args, **kwargs)

def build_verify_release_audio_timeline_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.quality.build_verify_release_audio_timeline_parser(*args, **kwargs)

def build_verify_release_portfolio_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_audit_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_archive_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_archive_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_accepted_evidence_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_accepted_evidence_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_portal_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_portal_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_portal_response_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_portal_response_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_portal_review_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_portal_review_pack_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_registry_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_registry_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_attestation_transparency_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_attestation_transparency_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_audit_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_audit_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_evidence_vault_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_evidence_vault_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_final_board_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_final_board_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_parser(*args, **kwargs)

def build_verify_release_portfolio_governance_reviewer_pack_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_release_portfolio_governance_reviewer_pack_parser(*args, **kwargs)

def build_verify_trust_operations_assurance_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_assurance_parser(*args, **kwargs)

def build_verify_trust_operations_assurance_watch_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_assurance_watch_parser(*args, **kwargs)

def build_verify_trust_operations_assurance_watch_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_assurance_watch_signoff_parser(*args, **kwargs)

def build_verify_trust_operations_control_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_control_parser(*args, **kwargs)

def build_verify_trust_operations_control_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_control_signoff_parser(*args, **kwargs)

def build_verify_trust_operations_final_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_final_handoff_parser(*args, **kwargs)

def build_verify_trust_operations_hub_incident_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_hub_incident_parser(*args, **kwargs)

def build_verify_trust_operations_hub_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_hub_parser(*args, **kwargs)

def build_verify_trust_operations_hub_runbook_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_hub_runbook_parser(*args, **kwargs)

def build_verify_trust_operations_incident_knowledge_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.trust.build_verify_trust_operations_incident_knowledge_parser(*args, **kwargs)

def build_verify_unified_command_center_release_train_change_control_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_command_center_release_train_change_control_parser(*args, **kwargs)

def build_verify_unified_command_center_release_train_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_command_center_release_train_handoff_parser(*args, **kwargs)

def build_verify_unified_command_center_release_train_lifecycle_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_command_center_release_train_lifecycle_parser(*args, **kwargs)

def build_verify_unified_command_center_release_train_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_command_center_release_train_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_acceptance_change_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_acceptance_change_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_acceptance_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_acceptance_change_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_command_center_acceptance_change_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_acceptance_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_command_center_acceptance_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_command_center_handoff_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_command_center_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_command_center_signoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_command_center_signoff_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_distribution_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_distribution_parser(*args, **kwargs)

def build_verify_unified_release_program_continuity_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_continuity_parser(*args, **kwargs)

def build_verify_unified_release_program_handoff_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_handoff_parser(*args, **kwargs)

def build_verify_unified_release_program_operations_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_operations_parser(*args, **kwargs)

def build_verify_unified_release_program_parser(*args: Any, **kwargs: Any) -> Any:
    return CLI_BINDINGS.program.build_verify_unified_release_program_parser(*args, **kwargs)

__all__ = ('_acceptance_analytics_fail_on', '_build_public_trust_center_publication_store', '_build_public_trust_center_store', '_build_release_portfolio_governance_attestation_portal_store', '_trust_operations_assurance_source_payload', '_trust_operations_assurance_watch_source_payload', '_trust_operations_final_readiness_source_payload', 'build_acceptance_analytics_parser', 'build_acceptance_check_parser', 'build_acceptance_diff_parser', 'build_acceptance_fix_plan_parser', 'build_acceptance_fix_sprint_parser', 'build_acceptance_kb_parser', 'build_audio_health_parser', 'build_audio_profile_parser', 'build_encoded_audio_acceptance_parser', 'build_format_decision_parser', 'build_parser', 'build_planning_rule_governance_parser', 'build_planning_rule_impact_parser', 'build_planning_ruleset_parser', 'build_planning_simulation_parser', 'build_public_trust_center_parser', 'build_public_trust_center_publication_monitor_parser', 'build_public_trust_center_publication_parser', 'build_release_audio_review_parser', 'build_release_check_parser', 'build_release_portfolio_audit_parser', 'build_release_portfolio_governance_attestation_accepted_evidence_parser', 'build_release_portfolio_governance_attestation_parser', 'build_release_portfolio_governance_attestation_portal_parser', 'build_release_portfolio_governance_attestation_portal_review_parser', 'build_release_portfolio_governance_attestation_registry_parser', 'build_release_portfolio_governance_attestation_transparency_acknowledgement_parser', 'build_release_portfolio_governance_attestation_transparency_parser', 'build_release_portfolio_governance_audit_parser', 'build_release_portfolio_governance_evidence_vault_parser', 'build_release_portfolio_governance_final_board_parser', 'build_release_portfolio_governance_queue_parser', 'build_release_portfolio_governance_reviewer_pack_parser', 'build_release_portfolio_governance_signoff_parser', 'build_trust_operations_assurance_parser', 'build_trust_operations_assurance_watch_parser', 'build_trust_operations_assurance_watch_signoff_parser', 'build_trust_operations_control_signoff_parser', 'build_trust_operations_controls_parser', 'build_trust_operations_final_readiness_parser', 'build_trust_operations_hub_incidents_parser', 'build_trust_operations_hub_parser', 'build_trust_operations_hub_runbook_parser', 'build_trust_operations_incident_knowledge_parser', 'build_verify_audio_campaign_archive_parser', 'build_verify_audio_campaign_parser', 'build_verify_audio_campaign_remediation_parser', 'build_verify_human_review_pack_parser', 'build_verify_maintenance_backup_parser', 'build_verify_public_trust_center_acceptance_board_parser', 'build_verify_public_trust_center_acceptance_board_signoff_archive_parser', 'build_verify_public_trust_center_anchor_registry_parser', 'build_verify_public_trust_center_anchor_transparency_parser', 'build_verify_public_trust_center_distribution_kit_accepted_evidence_parser', 'build_verify_public_trust_center_distribution_kit_parser', 'build_verify_public_trust_center_parser', 'build_verify_public_trust_center_publication_mirror_parser', 'build_verify_public_trust_center_publication_monitoring_parser', 'build_verify_public_trust_center_publication_parser', 'build_verify_release_audio_certification_parser', 'build_verify_release_audio_regression_parser', 'build_verify_release_audio_timeline_parser', 'build_verify_release_portfolio_audit_parser', 'build_verify_release_portfolio_governance_archive_parser', 'build_verify_release_portfolio_governance_attestation_accepted_evidence_parser', 'build_verify_release_portfolio_governance_attestation_parser', 'build_verify_release_portfolio_governance_attestation_portal_parser', 'build_verify_release_portfolio_governance_attestation_portal_response_parser', 'build_verify_release_portfolio_governance_attestation_portal_review_pack_parser', 'build_verify_release_portfolio_governance_attestation_registry_parser', 'build_verify_release_portfolio_governance_attestation_transparency_acknowledgement_parser', 'build_verify_release_portfolio_governance_attestation_transparency_parser', 'build_verify_release_portfolio_governance_audit_parser', 'build_verify_release_portfolio_governance_evidence_vault_parser', 'build_verify_release_portfolio_governance_final_board_parser', 'build_verify_release_portfolio_governance_parser', 'build_verify_release_portfolio_governance_reviewer_pack_parser', 'build_verify_trust_operations_assurance_parser', 'build_verify_trust_operations_assurance_watch_parser', 'build_verify_trust_operations_assurance_watch_signoff_parser', 'build_verify_trust_operations_control_parser', 'build_verify_trust_operations_control_signoff_parser', 'build_verify_trust_operations_final_handoff_parser', 'build_verify_trust_operations_hub_incident_parser', 'build_verify_trust_operations_hub_parser', 'build_verify_trust_operations_hub_runbook_parser', 'build_verify_trust_operations_incident_knowledge_parser', 'build_verify_unified_command_center_release_train_change_control_parser', 'build_verify_unified_command_center_release_train_handoff_parser', 'build_verify_unified_command_center_release_train_lifecycle_parser', 'build_verify_unified_command_center_release_train_parser', 'build_verify_unified_release_program_continuity_acceptance_change_parser', 'build_verify_unified_release_program_continuity_acceptance_parser', 'build_verify_unified_release_program_continuity_command_center_acceptance_change_parser', 'build_verify_unified_release_program_continuity_command_center_acceptance_parser', 'build_verify_unified_release_program_continuity_command_center_handoff_parser', 'build_verify_unified_release_program_continuity_command_center_parser', 'build_verify_unified_release_program_continuity_command_center_signoff_parser', 'build_verify_unified_release_program_continuity_distribution_parser', 'build_verify_unified_release_program_continuity_parser', 'build_verify_unified_release_program_handoff_parser', 'build_verify_unified_release_program_operations_parser', 'build_verify_unified_release_program_parser')
