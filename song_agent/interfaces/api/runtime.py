from __future__ import annotations
import json
import hashlib
import mimetypes
import os
import re
import shutil
import threading
import time
import webbrowser
from dataclasses import replace
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.parse import parse_qs
from song_agent.platform.version import VERSION as __version__
from song_agent.agent.multinode_pipeline import rerun_multinode_from_node
from song_agent.application.audio_campaigns.release_coverage import audio_campaign_release_track_coverage
from song_agent.application.generation.service import generate_request
from song_agent.application.jobs.model import JobState
from song_agent.auth import AuthConfig, validate_bearer_header
from song_agent.audio_artifacts import (
    AUDIO_ARTIFACT_FILENAME,
    audio_artifact_current,
    audio_artifact_summary,
    audio_artifact_stale_reasons_for_profile,
    build_audio_artifact_manifest,
    read_audio_artifact_manifest,
    write_audio_artifact_manifest,
)
from song_agent.assets import (
    AssetStore,
    apply_asset_refs_to_plan,
    asset_audio_path,
    asset_midi_path,
    asset_public_dict,
    asset_prompt_summaries,
    asset_refs_snapshot,
    extract_assets_from_song_plan,
    write_asset_refs_snapshot,
)
from song_agent.batching import BatchDocument, BatchStore, now_iso
from song_agent.candidate_groups import (
    CandidateGroup,
    CandidateGroupStore,
    candidate_audio_path,
    candidate_group_stale,
    candidate_midi_path,
)
from song_agent.candidate_scoring import score_provider_edit_candidate
from song_agent.edits import (
    EditIntent,
    EditedSongPlanResult,
    apply_edit_intent,
    build_edit_metadata,
    build_edit_targets,
    edit_change_summary,
    edit_variant_type,
    validate_edit_intent,
)
from song_agent.edit_presets import EditPresetStore, merge_preset_intent
from song_agent.editor_clips import (
    EditorClipError,
    EditorClipUnavailableError,
    build_clip_insert_patch,
    build_editor_clip_from_ref,
    list_editor_clips,
)
from song_agent.editor_templates import (
    EditorTemplateError,
    EditorTemplateStore,
    EditorTemplateUnavailableError,
    build_multitrack_clip_from_ref,
    build_multitrack_clip_insert_patch,
    section_template_public_dict,
    suggest_lane_mappings,
    track_template_public_dict,
)
from song_agent.editor_audition import (
    EditorAuditionError,
    EditorAuditionStore,
    EditorAuditionUnavailableError,
    audition_summary_for_preview,
)
from song_agent.editor_review import EditorReviewError, audition_asset_payload
from song_agent.editor_view import build_editor_diff, build_editor_view, build_editor_view_from_result
from song_agent.final_export import (
    FinalExportError,
    FinalExportOptions,
    build_final_export_bundle,
    build_final_export_zip,
    final_export_dir,
    final_export_zip_path,
    read_final_export_manifest,
)
from song_agent.delivery_qa import (
    build_delivery_qa_report,
    build_delivery_signoff_record,
    delivery_qa_allows_signoff,
    delivery_qa_source_hash,
    delivery_qa_summary,
    delivery_signoff_summary,
    mark_delivery_qa_stale,
    signoff_history_event,
)
from song_agent.release_export import (
    ReleaseExportError,
    build_release_export_bundle,
    build_release_export_zip,
    read_release_export_manifest,
    refresh_release_export_signoff_summary,
    release_export_summary,
)
from song_agent.release_operations import ReleaseOperationsError, ReleaseOperationsStore, operations_report_summary
from song_agent.release_operations_runbook import (
    ReleaseOperationsRunbookError,
    ReleaseOperationsRunbookNotFoundError,
    ReleaseOperationsRunbookStateError,
    ReleaseOperationsRunbookStore,
    runbook_summary,
)
from song_agent.release_operations_runbook_verifier import (
    release_operations_runbook_verification_summary,
    verify_release_operations_runbook_package,
    write_release_operations_runbook_verification_report,
)
from song_agent.trust_operations_hub import TrustOperationsHubStore
from song_agent.trust_operations_controls import (
    TrustOperationsControlNotFoundError,
    TrustOperationsControlStateError,
    TrustOperationsControlStore,
)
from song_agent.trust_operations_control_signoff import (
    TrustOperationsControlSignoffNotFoundError,
    TrustOperationsControlSignoffStateError,
    TrustOperationsControlSignoffStore,
)
from song_agent.trust_operations_control_signoff_verifier import write_trust_operations_control_signoff_verification_report
from song_agent.trust_operations_controls_verifier import write_trust_operations_control_verification_report
from song_agent.trust_operations_continuous_assurance import (
    TrustOperationsAssuranceNotFoundError,
    TrustOperationsAssuranceStateError,
    TrustOperationsAssuranceStore,
)
from song_agent.trust_operations_continuous_assurance_verifier import write_trust_operations_assurance_verification_report
from song_agent.trust_operations_assurance_watch import (
    TrustOperationsAssuranceWatchNotFoundError,
    TrustOperationsAssuranceWatchStateError,
    TrustOperationsAssuranceWatchStore,
)
from song_agent.trust_operations_assurance_watch_verifier import write_trust_operations_assurance_watch_verification_report
from song_agent.trust_operations_assurance_watch_signoff import (
    TrustOperationsAssuranceWatchSignoffNotFoundError,
    TrustOperationsAssuranceWatchSignoffStateError,
    TrustOperationsAssuranceWatchSignoffStore,
)
from song_agent.trust_operations_assurance_watch_signoff_verifier import write_trust_operations_assurance_watch_signoff_verification_report
from song_agent.trust_operations_final_readiness import (
    TrustOperationsFinalReadinessNotFoundError,
    TrustOperationsFinalReadinessStateError,
    TrustOperationsFinalReadinessStore,
)
from song_agent.trust_operations_final_readiness_verifier import write_trust_operations_final_handoff_verification_report
from song_agent.trust_operations_hub_incidents import (
    TrustOperationsIncidentNotFoundError,
    TrustOperationsIncidentStateError,
    TrustOperationsIncidentStore,
)
from song_agent.trust_operations_hub_incident_verifier import write_trust_operations_hub_incident_verification_report
from song_agent.trust_operations_incident_knowledge import (
    TrustOperationsIncidentKnowledgeStore,
    TrustOperationsKnowledgeNotFoundError,
    TrustOperationsKnowledgeStateError,
)
from song_agent.trust_operations_incident_knowledge_verifier import write_trust_operations_incident_knowledge_verification_report
from song_agent.release_operations_archive_verifier import (
    release_operations_archive_verification_summary,
    verify_release_operations_archive_package,
    write_release_operations_archive_verification_report,
)
from song_agent.release_operations_audit import (
    ReleaseOperationsAuditError,
    ReleaseOperationsAuditNotFoundError,
    ReleaseOperationsAuditStateError,
    ReleaseOperationsAuditStore,
    audit_summary,
)
from song_agent.release_operations_audit_verifier import (
    release_operations_audit_verification_summary,
    verify_release_operations_audit_package,
    write_release_operations_audit_verification_report,
)
from song_agent.release_operations_reviewer_pack import (
    ReleaseOperationsReviewerPackError,
    ReleaseOperationsReviewerPackNotFoundError,
    ReleaseOperationsReviewerPackStateError,
    ReleaseOperationsReviewerPackStore,
    reviewer_pack_summary,
)
from song_agent.release_operations_reviewer_pack_verifier import (
    release_operations_reviewer_pack_verification_summary,
    verify_release_operations_reviewer_pack,
    write_release_operations_reviewer_pack_verification_report,
)
from song_agent.release_operations_retrospective import retrospective_summary
from song_agent.release_portfolio_audit import (
    ReleasePortfolioAuditError,
    ReleasePortfolioAuditNotFoundError,
    ReleasePortfolioAuditStateError,
    ReleasePortfolioAuditStore,
    portfolio_audit_summary,
)
from song_agent.release_portfolio_audit_verifier import (
    release_portfolio_audit_verification_summary,
    verify_release_portfolio_audit_package,
    write_release_portfolio_audit_verification_report,
)
from song_agent.release_portfolio_governance import (
    ReleasePortfolioGovernanceError,
    ReleasePortfolioGovernanceNotFoundError,
    ReleasePortfolioGovernanceStateError,
    ReleasePortfolioGovernanceStore,
    queue_summary,
)
from song_agent.release_portfolio_governance_archive_verifier import (
    release_portfolio_governance_archive_verification_summary,
    verify_release_portfolio_governance_archive_package,
    write_release_portfolio_governance_archive_verification_report,
)
from song_agent.release_portfolio_governance_signoff import (
    ReleasePortfolioGovernanceSignoffError,
    ReleasePortfolioGovernanceSignoffNotFoundError,
    ReleasePortfolioGovernanceSignoffStateError,
    ReleasePortfolioGovernanceSignoffStore,
)
from song_agent.release_portfolio_governance_audit import (
    ReleasePortfolioGovernanceAuditError,
    ReleasePortfolioGovernanceAuditNotFoundError,
    ReleasePortfolioGovernanceAuditStateError,
    ReleasePortfolioGovernanceAuditStore,
    audit_summary as portfolio_governance_audit_summary,
)
from song_agent.release_portfolio_governance_audit_verifier import (
    release_portfolio_governance_audit_verification_summary,
    verify_release_portfolio_governance_audit_package,
    write_release_portfolio_governance_audit_verification_report,
)
from song_agent.release_portfolio_governance_reviewer_pack import (
    ReleasePortfolioGovernanceReviewerPackError,
    ReleasePortfolioGovernanceReviewerPackNotFoundError,
    ReleasePortfolioGovernanceReviewerPackStateError,
    ReleasePortfolioGovernanceReviewerPackStore,
    reviewer_pack_summary as portfolio_governance_reviewer_pack_summary,
)
from song_agent.release_portfolio_governance_reviewer_pack_verifier import (
    release_portfolio_governance_reviewer_pack_verification_summary,
    verify_release_portfolio_governance_reviewer_pack,
    write_release_portfolio_governance_reviewer_pack_verification_report,
)
from song_agent.release_portfolio_governance_final_board import (
    ReleasePortfolioGovernanceFinalBoardError,
    ReleasePortfolioGovernanceFinalBoardNotFoundError,
    ReleasePortfolioGovernanceFinalBoardStateError,
    ReleasePortfolioGovernanceFinalBoardStore,
    final_board_signoff_summary as portfolio_governance_final_board_signoff_summary,
    final_board_summary as portfolio_governance_final_board_summary,
)
from song_agent.release_portfolio_governance_final_board_verifier import (
    release_portfolio_governance_final_board_verification_summary,
    verify_release_portfolio_governance_final_board_package,
    write_release_portfolio_governance_final_board_verification_report,
)
from song_agent.release_portfolio_governance_evidence_vault import (
    ReleasePortfolioGovernanceEvidenceVaultError,
    ReleasePortfolioGovernanceEvidenceVaultNotFoundError,
    ReleasePortfolioGovernanceEvidenceVaultStateError,
    ReleasePortfolioGovernanceEvidenceVaultStore,
    evidence_vault_summary as portfolio_governance_evidence_vault_summary,
)
from song_agent.release_portfolio_governance_evidence_vault_verifier import (
    verify_release_portfolio_governance_evidence_vault_package,
    write_release_portfolio_governance_evidence_vault_verification_report,
)
from song_agent.release_portfolio_governance_attestation import (
    ReleasePortfolioGovernanceAttestationError,
    ReleasePortfolioGovernanceAttestationNotFoundError,
    ReleasePortfolioGovernanceAttestationStateError,
    ReleasePortfolioGovernanceAttestationStore,
    attestation_summary as portfolio_governance_attestation_summary,
)
from song_agent.release_portfolio_governance_attestation_verifier import (
    verify_release_portfolio_governance_attestation,
    write_release_portfolio_governance_attestation_verification_report,
)
from song_agent.release_portfolio_governance_attestation_registry import (
    ReleasePortfolioGovernanceAttestationRegistryError,
    ReleasePortfolioGovernanceAttestationRegistryNotFoundError,
    ReleasePortfolioGovernanceAttestationRegistryStateError,
    ReleasePortfolioGovernanceAttestationRegistryStore,
    registry_summary as portfolio_governance_attestation_registry_summary,
    registry_verification_summary as portfolio_governance_attestation_registry_verification_summary,
)
from song_agent.release_portfolio_governance_attestation_registry_verifier import (
    verify_release_portfolio_governance_attestation_registry,
    write_release_portfolio_governance_attestation_registry_verification_report,
)
from song_agent.release_portfolio_governance_attestation_portal import (
    ReleasePortfolioGovernanceAttestationPortalError,
    ReleasePortfolioGovernanceAttestationPortalNotFoundError,
    ReleasePortfolioGovernanceAttestationPortalStateError,
    ReleasePortfolioGovernanceAttestationPortalStore,
    portal_summary as portfolio_governance_attestation_portal_summary,
    portal_verification_summary as portfolio_governance_attestation_portal_verification_summary,
)
from song_agent.release_portfolio_governance_attestation_portal_verifier import (
    verify_release_portfolio_governance_attestation_portal,
    write_release_portfolio_governance_attestation_portal_verification_report,
)
from song_agent.release_portfolio_governance_attestation_portal_review import (
    ReleasePortfolioGovernanceAttestationPortalReviewError,
    ReleasePortfolioGovernanceAttestationPortalReviewNotFoundError,
    ReleasePortfolioGovernanceAttestationPortalReviewStateError,
    ReleasePortfolioGovernanceAttestationPortalReviewStore,
    response_summary as portfolio_governance_attestation_portal_response_summary,
    review_pack_summary as portfolio_governance_attestation_portal_review_pack_summary,
)
from song_agent.release_portfolio_governance_attestation_portal_review_verifier import (
    verify_release_portfolio_governance_attestation_portal_review_pack,
    write_release_portfolio_governance_attestation_portal_review_pack_verification_report,
)
from song_agent.release_portfolio_governance_attestation_accepted_evidence import (
    ReleasePortfolioGovernanceAttestationAcceptedEvidenceError,
    ReleasePortfolioGovernanceAttestationAcceptedEvidenceNotFoundError,
    ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError,
    ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore,
    accepted_evidence_summary as portfolio_governance_attestation_accepted_evidence_summary,
)
from song_agent.release_portfolio_governance_attestation_accepted_evidence_verifier import (
    verify_release_portfolio_governance_attestation_accepted_evidence,
    write_release_portfolio_governance_attestation_accepted_evidence_verification_report,
)
from song_agent.release_portfolio_governance_attestation_transparency import (
    ReleasePortfolioGovernanceAttestationTransparencyError,
    ReleasePortfolioGovernanceAttestationTransparencyNotFoundError,
    ReleasePortfolioGovernanceAttestationTransparencyStateError,
    ReleasePortfolioGovernanceAttestationTransparencyStore,
    transparency_summary as portfolio_governance_attestation_transparency_summary,
)
from song_agent.release_portfolio_governance_attestation_transparency_verifier import (
    verify_release_portfolio_governance_attestation_transparency,
    write_release_portfolio_governance_attestation_transparency_verification_report,
)
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement import (
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError,
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError,
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError,
    ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore,
    acknowledgement_summary as portfolio_governance_attestation_transparency_acknowledgement_summary,
)
from song_agent.release_portfolio_governance_attestation_transparency_acknowledgement_verifier import (
    verify_release_portfolio_governance_attestation_transparency_acknowledgement_package,
    write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report,
)
from song_agent.public_trust_center import (
    PublicTrustCenterError,
    PublicTrustCenterNotFoundError,
    PublicTrustCenterStateError,
    PublicTrustCenterStore,
    public_trust_center_summary,
)
from song_agent.public_trust_center_anchor_registry import (
    PublicTrustCenterAnchorRegistryError,
    PublicTrustCenterAnchorRegistryNotFoundError,
    PublicTrustCenterAnchorRegistryStateError,
    PublicTrustCenterAnchorRegistryStore,
    anchor_registry_summary as public_trust_center_anchor_registry_summary,
)
from song_agent.public_trust_center_anchor_registry_verifier import (
    verify_public_trust_center_anchor_registry_package,
    write_public_trust_center_anchor_registry_verification_report,
)
from song_agent.public_trust_center_anchor_transparency import (
    PublicTrustCenterAnchorTransparencyError,
    PublicTrustCenterAnchorTransparencyNotFoundError,
    PublicTrustCenterAnchorTransparencyStateError,
    PublicTrustCenterAnchorTransparencyStore,
    anchor_transparency_summary as public_trust_center_anchor_transparency_summary,
)
from song_agent.public_trust_center_anchor_transparency_verifier import (
    verify_public_trust_center_anchor_transparency_package,
    write_public_trust_center_anchor_transparency_verification_report,
)
from song_agent.public_trust_center_distribution_kit import (
    PublicTrustCenterDistributionKitError,
    PublicTrustCenterDistributionKitNotFoundError,
    PublicTrustCenterDistributionKitStateError,
    PublicTrustCenterDistributionKitStore,
    distribution_kit_summary as public_trust_center_distribution_kit_summary,
)
from song_agent.public_trust_center_distribution_kit_acceptance import (
    PublicTrustCenterDistributionKitAcceptanceError,
    PublicTrustCenterDistributionKitAcceptanceNotFoundError,
    PublicTrustCenterDistributionKitAcceptanceStateError,
    PublicTrustCenterDistributionKitAcceptanceStore,
    accepted_evidence_summary as public_trust_center_distribution_kit_accepted_evidence_summary,
)
from song_agent.public_trust_center_acceptance_board import (
    PublicTrustCenterAcceptanceBoardError,
    PublicTrustCenterAcceptanceBoardNotFoundError,
    PublicTrustCenterAcceptanceBoardStateError,
    PublicTrustCenterAcceptanceBoardStore,
)
from song_agent.public_trust_center_verifier import (
    verify_public_trust_center_package,
    write_public_trust_center_verification_report,
)
from song_agent.release_portfolio_governance_verifier import (
    release_portfolio_governance_verification_summary,
    verify_release_portfolio_governance_package,
    write_release_portfolio_governance_verification_report,
)
from song_agent.release_operations_signoff import (
    ReleaseOperationsSignoffError,
    ReleaseOperationsSignoffNotFoundError,
    ReleaseOperationsSignoffStateError,
    ReleaseOperationsSignoffStore,
    operations_change_request_integrity_ok,
    operations_signoff_summary,
)
from song_agent.release_operations_verifier import (
    release_operations_verification_summary,
    verify_release_operations_package,
    write_release_operations_verification_report,
)
from song_agent.release_metadata import (
    ReleaseMetadataError,
    attach_metadata_export_to_manifest,
    export_release_metadata_files,
    initialize_release_metadata,
    metadata_export_summary,
    read_release_metadata,
    read_release_metadata_history,
    read_release_metadata_qa,
    release_metadata_source_hash,
    release_metadata_summary,
    write_release_metadata,
    write_release_metadata_qa,
)
from song_agent.release_metadata_qa import (
    build_release_metadata_qa_report,
    mark_release_metadata_qa_stale,
    release_metadata_qa_summary,
)
from song_agent.release_qa import (
    build_release_qa_report,
    build_release_signoff_record,
    mark_release_qa_stale,
    release_qa_allows_signoff,
    release_qa_summary,
    release_signoff_summary,
    release_source_hash,
    signoff_history_event as release_signoff_history_event,
)
from song_agent.release_audio import (
    build_release_audio_qa_report,
    read_release_audio_qa,
    release_audio_allows_signoff,
    release_audio_report_integrity_ok,
    release_audio_source_hash,
    release_audio_summary,
    write_release_audio_qa,
)
from song_agent.audio_review_evidence import (
    AudioReviewEvidenceError,
    AudioReviewEvidenceNotFoundError,
    AudioReviewEvidenceStateError,
    AudioReviewEvidenceStore,
    audio_review_summary_allows_signoff,
    audio_review_summary_public,
    release_audio_review_gate,
)
from song_agent.audio_revision import (
    AudioRevisionError,
    AudioRevisionNotFoundError,
    AudioRevisionStateError,
    AudioRevisionStore,
)
from song_agent.audio_lab import (
    AudioLabError,
    AudioLabNotFoundError,
    AudioLabStateError,
    AudioLabStore,
    AudioLabValidationError,
)
from song_agent.audio_fix_sprints import (
    AudioFixSprintError,
    AudioFixSprintNotFoundError,
    AudioFixSprintStateError,
    AudioFixSprintStore,
    AudioFixSprintValidationError,
)
from song_agent.audio_campaigns import (
    AudioCampaignError,
    AudioCampaignNotFoundError,
    AudioCampaignStateError,
    AudioCampaignStore,
    AudioCampaignValidationError,
)
from song_agent.audio_campaign_governance import (
    AudioCampaignGovernanceError,
    AudioCampaignGovernanceNotFoundError,
    AudioCampaignGovernanceStateError,
    AudioCampaignGovernanceStore,
)
from song_agent.audio_campaign_planner import (
    AudioCampaignPlannerError,
    AudioCampaignPlannerNotFoundError,
    AudioCampaignPlannerStateError,
    AudioCampaignPlannerStore,
    AudioCampaignPlannerValidationError,
)
from song_agent.audio_campaign_remediation import (
    AudioCampaignRemediationError,
    AudioCampaignRemediationNotFoundError,
    AudioCampaignRemediationStateError,
    AudioCampaignRemediationStore,
    AudioCampaignRemediationValidationError,
)
from song_agent.release_audio_certification import (
    ReleaseAudioCertificationError,
    ReleaseAudioCertificationNotFoundError,
    ReleaseAudioCertificationStateError,
    ReleaseAudioCertificationStore,
    ReleaseAudioCertificationValidationError,
)
from song_agent.release_audio_timeline import (
    ReleaseAudioTimelineError,
    ReleaseAudioTimelineNotFoundError,
    ReleaseAudioTimelineStateError,
    ReleaseAudioTimelineStore,
    ReleaseAudioTimelineValidationError,
)
from song_agent.release_audio_regression import (
    ReleaseAudioRegressionError,
    ReleaseAudioRegressionNotFoundError,
    ReleaseAudioRegressionStateError,
    ReleaseAudioRegressionStore,
    ReleaseAudioRegressionValidationError,
)
from song_agent.release_audio_baseline_governance import (
    ReleaseAudioBaselineGovernanceError,
    ReleaseAudioBaselineGovernanceNotFoundError,
    ReleaseAudioBaselineGovernanceStateError,
    ReleaseAudioBaselineGovernanceStore,
    ReleaseAudioBaselineGovernanceValidationError,
)
from song_agent.release_audio_regression_response import (
    ReleaseAudioRegressionResponseError,
    ReleaseAudioRegressionResponseNotFoundError,
    ReleaseAudioRegressionResponseStateError,
    ReleaseAudioRegressionResponseStore,
    ReleaseAudioRegressionResponseValidationError,
)
from song_agent.release_audio_quality_observatory import (
    ReleaseAudioQualityObservatoryError,
    ReleaseAudioQualityObservatoryNotFoundError,
    ReleaseAudioQualityObservatoryStateError,
    ReleaseAudioQualityObservatoryStore,
    ReleaseAudioQualityObservatoryValidationError,
)
from song_agent.release_audio_quality_actions import (
    ReleaseAudioQualityActionQueueError,
    ReleaseAudioQualityActionQueueNotFoundError,
    ReleaseAudioQualityActionQueueStateError,
    ReleaseAudioQualityActionQueueStore,
    ReleaseAudioQualityActionQueueValidationError,
)
from song_agent.release_audio_quality_action_signoff import (
    ReleaseAudioQualityActionQueueSignoffError,
    ReleaseAudioQualityActionQueueSignoffNotFoundError,
    ReleaseAudioQualityActionQueueSignoffStateError,
    ReleaseAudioQualityActionQueueSignoffStore,
    ReleaseAudioQualityActionQueueSignoffValidationError,
)
from song_agent.release_audio_command_center import (
    ReleaseAudioCommandCenterError,
    ReleaseAudioCommandCenterNotFoundError,
    ReleaseAudioCommandCenterStateError,
    ReleaseAudioCommandCenterStore,
)
from song_agent.unified_command_center import (
    UnifiedCommandCenterError,
    UnifiedCommandCenterNotFoundError,
    UnifiedCommandCenterStateError,
    UnifiedCommandCenterStore,
)
from song_agent.unified_command_center_continuous_review import (
    UnifiedCommandCenterContinuousReviewError,
    UnifiedCommandCenterContinuousReviewNotFoundError,
    UnifiedCommandCenterContinuousReviewStateError,
    UnifiedCommandCenterContinuousReviewStore,
)
from song_agent.unified_command_center_drift_response import (
    UnifiedCommandCenterDriftResponseError,
    UnifiedCommandCenterDriftResponseNotFoundError,
    UnifiedCommandCenterDriftResponseStateError,
    UnifiedCommandCenterDriftResponseStore,
)
from song_agent.unified_command_center_evidence_review import (
    UnifiedCommandCenterEvidenceReviewError,
    UnifiedCommandCenterEvidenceReviewNotFoundError,
    UnifiedCommandCenterEvidenceReviewStateError,
    UnifiedCommandCenterEvidenceReviewStore,
)
from song_agent.unified_command_center_reviewer_decision_board import (
    UnifiedCommandCenterReviewerDecisionBoardError,
    UnifiedCommandCenterReviewerDecisionBoardNotFoundError,
    UnifiedCommandCenterReviewerDecisionBoardStateError,
    UnifiedCommandCenterReviewerDecisionBoardStore,
)
from song_agent.unified_command_center_release_train import (
    UnifiedCommandCenterReleaseTrainError,
    UnifiedCommandCenterReleaseTrainNotFoundError,
    UnifiedCommandCenterReleaseTrainStateError,
    UnifiedCommandCenterReleaseTrainStore,
)
from song_agent.unified_command_center_release_train_change_control import (
    UnifiedCommandCenterReleaseTrainChangeControlError,
    UnifiedCommandCenterReleaseTrainChangeControlNotFoundError,
    UnifiedCommandCenterReleaseTrainChangeControlStateError,
    UnifiedCommandCenterReleaseTrainChangeControlStore,
)
from song_agent.unified_command_center_release_train_lifecycle import (
    UnifiedCommandCenterReleaseTrainLifecycleError,
    UnifiedCommandCenterReleaseTrainLifecycleNotFoundError,
    UnifiedCommandCenterReleaseTrainLifecycleStateError,
    UnifiedCommandCenterReleaseTrainLifecycleStore,
)
from song_agent.unified_command_center_release_train_handoff import (
    UnifiedCommandCenterReleaseTrainHandoffError,
    UnifiedCommandCenterReleaseTrainHandoffNotFoundError,
    UnifiedCommandCenterReleaseTrainHandoffStateError,
    UnifiedCommandCenterReleaseTrainHandoffStore,
)
from song_agent.unified_release_program import (
    UnifiedReleaseProgramError,
    UnifiedReleaseProgramNotFoundError,
    UnifiedReleaseProgramStateError,
    UnifiedReleaseProgramStore,
)
from song_agent.unified_release_program_operations import (
    UnifiedReleaseProgramOperationsError,
    UnifiedReleaseProgramOperationsNotFoundError,
    UnifiedReleaseProgramOperationsStateError,
    UnifiedReleaseProgramOperationsStore,
)
from song_agent.unified_release_program_handoff import (
    UnifiedReleaseProgramHandoffError,
    UnifiedReleaseProgramHandoffNotFoundError,
    UnifiedReleaseProgramHandoffStateError,
    UnifiedReleaseProgramHandoffStore,
)
from song_agent.unified_release_program_vault import (
    UnifiedReleaseProgramVaultError,
    UnifiedReleaseProgramVaultNotFoundError,
    UnifiedReleaseProgramVaultStateError,
    UnifiedReleaseProgramVaultStore,
)
from song_agent.unified_release_program_vault_operations import (
    UnifiedReleaseProgramVaultOperationsError,
    UnifiedReleaseProgramVaultOperationsNotFoundError,
    UnifiedReleaseProgramVaultOperationsStateError,
    UnifiedReleaseProgramVaultOperationsStore,
)
from song_agent.unified_release_program_continuity import (
    UnifiedReleaseProgramContinuityError,
    UnifiedReleaseProgramContinuityNotFoundError,
    UnifiedReleaseProgramContinuityStateError,
    UnifiedReleaseProgramContinuityStore,
)
from song_agent.unified_release_program_continuity_distribution import (
    UnifiedReleaseProgramContinuityDistributionError,
    UnifiedReleaseProgramContinuityDistributionNotFoundError,
    UnifiedReleaseProgramContinuityDistributionStateError,
    UnifiedReleaseProgramContinuityDistributionStore,
)
from song_agent.unified_release_program_continuity_acceptance import (
    UnifiedReleaseProgramContinuityAcceptanceError,
    UnifiedReleaseProgramContinuityAcceptanceNotFoundError,
    UnifiedReleaseProgramContinuityAcceptanceStateError,
    UnifiedReleaseProgramContinuityAcceptanceStore,
)
from song_agent.unified_release_program_continuity_acceptance_change import (
    UnifiedReleaseProgramContinuityAcceptanceChangeError,
    UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError,
    UnifiedReleaseProgramContinuityAcceptanceChangeStateError,
    UnifiedReleaseProgramContinuityAcceptanceChangeStore,
)
from song_agent.unified_release_program_continuity_command_center import (
    UnifiedReleaseProgramContinuityCommandCenterError,
    UnifiedReleaseProgramContinuityCommandCenterStateError,
    UnifiedReleaseProgramContinuityCommandCenterStore,
)
from song_agent.unified_release_program_continuity_command_center_signoff import (
    UnifiedReleaseProgramContinuityCommandCenterSignoffError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffStateError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffStore,
)
from song_agent.unified_release_program_continuity_command_center_acceptance import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore,
)
from song_agent.unified_release_program_continuity_command_center_acceptance_change import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore,
)
from song_agent.unified_command_center_handoff import (
    UnifiedCommandCenterHandoffError,
    UnifiedCommandCenterHandoffStateError,
    UnifiedCommandCenterHandoffStore,
)
from song_agent.unified_command_center_signoff import (
    UnifiedCommandCenterSignoffError,
    UnifiedCommandCenterSignoffNotFoundError,
    UnifiedCommandCenterSignoffStateError,
    UnifiedCommandCenterSignoffStore,
)
from song_agent.audio_encoding import AudioEncodingError, AudioEncodingNotFoundError, AudioEncodingStateError, AudioEncodingStore, encoded_audio_gate, normalize_required_profiles, resolve_target_audio_format_profiles
from song_agent.encoded_audio_acceptance import (
    EncodedAudioAcceptanceError,
    EncodedAudioAcceptanceNotFoundError,
    EncodedAudioAcceptanceStateError,
    EncodedAudioAcceptanceStore,
    encoded_audio_acceptance_summary_hash,
    encoded_audio_acceptance_summary_integrity_ok,
    encoded_audio_review_integrity_hash,
    encoded_audio_review_integrity_ok,
)
from song_agent.format_decisions import (
    FormatDecisionError,
    FormatDecisionNotFoundError,
    FormatDecisionStateError,
    FormatDecisionStore,
    distribution_target_format_decision_coverage,
)
from song_agent.rights_clearance import (
    RightsClearanceError,
    RightsClearanceNotFoundError,
    RightsClearanceStateError,
    RightsClearanceStore,
)
from song_agent.audio_encoding_profiles import AudioEncodingProfileError, AudioEncodingProfileNotFoundError, AudioEncodingProfileStore
from song_agent.releases import (
    ReleaseConflictError,
    ReleaseNotFoundError,
    ReleaseStateError,
    ReleaseStore,
    ReleaseValidationError,
    release_summary,
    stable_hash,
)
from song_agent.distribution import (
    DistributionNotFoundError,
    DistributionStateError,
    DistributionStore,
    DistributionValidationError,
    distribution_signoff_summary,
    distribution_target_summary,
)
from song_agent.distribution_artwork import (
    delete_distribution_artwork,
    distribution_artwork_file_path,
    distribution_artwork_summary,
    import_distribution_artwork,
    list_distribution_artwork,
    read_distribution_artwork,
)
from song_agent.distribution_export import (
    DistributionExportError,
    build_distribution_export_package,
    build_distribution_package_zip,
    distribution_export_summary,
    read_distribution_export_manifest,
    sign_distribution_package,
)
from song_agent.distribution_profiles import get_distribution_profile, list_distribution_profiles
from song_agent.distribution_templates import DistributionTemplateError, TemplatePackStore, template_summary
from song_agent.distribution_layout import build_distribution_layout_plan, layout_summary
from song_agent.distribution_checklist import (
    DistributionChecklistError,
    checklist_summary,
    initialize_distribution_checklist,
    read_distribution_checklist,
    reconcile_distribution_checklist,
    update_distribution_checklist_item,
)
from song_agent.distribution_qa import (
    build_distribution_qa_report,
    distribution_source_state,
    distribution_qa_summary,
    mark_distribution_qa_stale,
)
from song_agent.release_metadata import read_release_metadata
from song_agent.distribution_verifier import (
    distribution_verification_summary,
    verify_distribution_package,
    write_distribution_verification_report,
)
from song_agent.submissions import (
    SubmissionNotFoundError,
    SubmissionStateError,
    SubmissionStore,
    SubmissionValidationError,
    submission_batch_summary,
    submission_signoff_summary,
)
from song_agent.submission_qa import (
    build_submission_qa_report,
    mark_submission_qa_stale,
    submission_qa_summary,
    submission_source_state,
)
from song_agent.submission_export import (
    SubmissionExportError,
    build_submission_export_bundle,
    build_submission_package_zip,
    read_submission_export_manifest,
    sign_submission_package,
    submission_export_summary,
)
from song_agent.submission_verifier import (
    submission_verification_summary,
    verify_submission_package,
    write_submission_verification_report,
)
from song_agent.submission_evidence import (
    SubmissionEvidenceNotFoundError,
    SubmissionEvidenceStateError,
    SubmissionEvidenceStore,
    SubmissionEvidenceValidationError,
    submission_evidence_report_summary,
    submission_evidence_signoff_summary,
)
from song_agent.submission_evidence_verifier import (
    submission_evidence_verification_summary,
    verify_submission_evidence_package,
    write_submission_evidence_verification_report,
)
from song_agent.acceptance_analytics import (
    AcceptanceAnalyticsError,
    AcceptanceAnalyticsNotFoundError,
    AcceptanceAnalyticsStateError,
    AcceptanceAnalyticsStore,
    AnalyticsScope,
    acceptance_analytics_summary,
    release_acceptance_analytics_evidence,
)
from song_agent.acceptance_fix_sprints import (
    AcceptanceFixSprintError,
    AcceptanceFixSprintNotFoundError,
    AcceptanceFixSprintStateError,
    AcceptanceFixSprintStore,
    acceptance_fix_closeout_summary,
    fix_sprint_summary,
    latest_fix_sprint_summary,
)
from song_agent.acceptance_fix_planning import (
    AcceptanceFixPlanError,
    AcceptanceFixPlanNotFoundError,
    AcceptanceFixPlanStateError,
    AcceptanceFixPlanningStore,
    fix_plan_summary,
    latest_fix_plan_summary,
)
from song_agent.acceptance_fix_plan_reviews import (
    AcceptanceFixPlanReviewError,
    AcceptanceFixPlanReviewNotFoundError,
    AcceptanceFixPlanReviewStateError,
    AcceptanceFixPlanReviewStore,
    REVIEW_READY_STATUSES,
    fix_plan_review_summary,
    latest_fix_plan_review_summary,
)
from song_agent.acceptance_kb import (
    AcceptanceKnowledgeBaseError,
    AcceptanceKnowledgeBaseNotFoundError,
    AcceptanceKnowledgeBaseStore,
    knowledge_entry_summary,
    knowledge_report_summary,
)
from song_agent.planning_rule_simulation import (
    PlanningRuleSimulationError,
    PlanningRuleSimulationNotFoundError,
    PlanningRuleSimulationStateError,
    PlanningRuleSimulationStore,
    planning_simulation_summary,
    ruleset_summary,
)
from song_agent.planning_rule_governance import (
    PlanningRuleGovernanceError,
    PlanningRuleGovernanceNotFoundError,
    PlanningRuleGovernanceStateError,
    PlanningRuleGovernanceStore,
    active_governance_summary,
    governance_summary,
    promotion_summary,
)
from song_agent.planning_rule_impact import (
    PlanningRuleImpactError,
    PlanningRuleImpactNotFoundError,
    PlanningRuleImpactStateError,
    PlanningRuleImpactStore,
    planning_rule_impact_report_hash,
    planning_rule_impact_summary,
)
from song_agent.acceptance_diff import build_acceptance_diff
from song_agent.acceptance_profiles import list_acceptance_profiles
from song_agent.audio_profiles import AudioProfileError, AudioProfileNotFoundError, AudioProfileStore
from song_agent.mastering_profiles import MasteringProfileError, MasteringProfileNotFoundError, MasteringProfileStore
from song_agent.mastering_qa import MasteringNotFoundError, MasteringQAError, MasteringStateError, MasteringStore
from song_agent.music_acceptance import (
    AcceptanceNotFoundError,
    AcceptanceStateError,
    AcceptanceStore,
    AcceptanceValidationError,
    acceptance_report_summary,
    acceptance_signoff_summary,
    acceptance_suite_summary,
    listening_review_summary,
)
from song_agent.mix_controls import (
    MixControlError,
    MixControlStateError,
    MixControlStore,
    mix_state_hash,
    mix_state_integrity_ok,
    mix_state_stale_reasons,
)
from song_agent.mix_render import MixRenderStore, mix_preview_integrity_ok
from song_agent.stem_health import (
    read_stem_health_report,
    stem_health_allows_signoff,
    stem_health_integrity_ok,
    stem_health_source_state,
    stem_health_stale_reasons,
    stem_health_summary,
)
from song_agent.human_review_pack import (
    HumanReviewPackNotFoundError,
    HumanReviewPackStateError,
    HumanReviewPackStore,
    HumanReviewPackValidationError,
)
from song_agent.regression_songbook import builtin_songbook
from song_agent.context_packs import (
    ContextPackStaleError,
    ContextPackStore,
    apply_context_pack,
    context_pack_public_dict,
    context_pack_snapshot,
    merge_context_refs,
    write_context_pack_snapshot,
)
from song_agent.library_index import LibraryIndexStore, asset_source_hash, recommend_library_context, search_library
from song_agent.node_graph import affected_nodes_for_retry, downstream_nodes, upstream_nodes
from song_agent.node_store import NodeStore
from song_agent.prompt_templates import PromptTemplateStore
from song_agent.projectio import ProjectPaths, append_event, read_json, slugify, write_json
from song_agent.project_compare import compare_project_versions
from song_agent.provider_edits import (
    ProviderEditPatch,
    apply_provider_edit_patch,
    create_provider_edit_preview,
    delete_provider_edit_preview,
    generate_provider_edit_candidates,
    generate_provider_edit_patch,
    mark_provider_edit_preview_applied,
    preview_candidate_plan,
    preview_patch,
    preview_stale,
    read_provider_edit_preview,
    song_plan_hash,
)
from song_agent.review_edits import (
    ReviewEditError,
    ReviewEditStore,
    ReviewEditUnavailableError,
    apply_review_edit,
    build_review_edit,
    review_edit_instruction_for_provider,
    review_edit_metadata,
    review_edit_summary,
)
from song_agent.review_tasks import (
    ReviewTaskError,
    ReviewTaskStateError,
    ReviewTaskStore,
    apply_candidate_intents,
    build_provider_review_candidates,
    build_review_decision_report,
    build_local_review_candidates,
    candidate_apply_metadata,
    ensure_candidate_current,
    _ensure_task_open_for_apply,
    ensure_task_current,
    mark_task_archived,
    mark_task_resolved,
    review_candidate_summary,
    review_candidate_source_breakdown,
    review_decision_summary,
    review_task_summary,
    task_list_summary,
)
from song_agent.review_judge import (
    REVIEW_JUDGE_TEMPLATE_ID,
    judge_report_summary,
    judge_summary_for_apply,
    mark_judge_report_stale,
    read_judge_report_with_stale,
    run_provider_review_judge,
    sprint_judge_summary,
)
from song_agent.review_sprints import (
    ReviewSprintError,
    ReviewSprintStateError,
    ReviewSprintStore,
    review_sprint_export_summary,
)
from song_agent.review_sprint_recommendations import (
    build_review_sprint_recommendation_report,
    recommendation_report_summary,
)
from song_agent.review_sprint_actions import (
    ReviewSprintActionQueueStore,
    SprintActionItem,
    SprintActionQueue,
    action_queue_collection_summary,
    action_queue_summary,
    build_action_queue_from_recommendation_report,
    queue_report_is_stale,
)
from song_agent.review_sprint_metrics import (
    ReviewMetricsStore,
    build_project_review_metrics,
    build_sprint_metrics_report,
    project_review_metrics_summary,
    sprint_metrics_summary,
)
from song_agent.review_sprint_closeout import (
    build_closeout_report,
    build_signoff_record,
    closeout_allows_close,
    closeout_report_summary,
    closeout_source_hash,
    mark_closeout_report_forced,
    mark_closeout_report_stale,
    signoff_summary,
)
from song_agent.provider_usage import (
    build_provider_usage_report,
    collect_candidate_group_provider_usage_records,
    collect_project_provider_usage_records,
    usage_record_from_file,
)
from song_agent.prompt_ab import PromptABStore
from song_agent.projects import ProjectStore
from song_agent.references import (
    MAX_REFERENCE_WAV_BYTES,
    ReferenceStore,
    reference_file_url,
    reference_prompt_summaries,
    reference_public_dict,
    reference_refs_snapshot,
    write_reference_refs_snapshot,
)
from song_agent.redaction import sanitize_metadata
from song_agent.reference_analysis import (
    ReferenceAnalysisError,
    analyze_reference,
    create_asset_from_slice,
    generate_slices,
    get_analysis_report,
    get_slice_manifest,
    render_reference_slice_audio,
    render_reference_slice_midi,
    require_fresh_analysis,
    require_fresh_slices,
    slice_audio_path,
    slice_midi_path,
)
from song_agent.project_quality import (
    QualityGateConfig,
    evaluate_quality_gate,
    load_quality_gate_config,
    save_quality_gate_config,
)
from song_agent.provider import (
    ProviderError,
    load_provider_config,
    provider_configured,
    reset_provider_config,
    save_provider_config_from_dict,
    test_provider_config,
)
from song_agent.renderers.midi import render_midi
from song_agent.renderers.audio import (
    RendererError,
    load_renderer_config,
    render_audio,
    renderer_configured,
    reset_renderer_config,
    save_renderer_config_from_dict,
    test_renderer_config,
)
from song_agent.runtime_views import (
    build_timeline_view,
    build_tracks_view,
    build_validator_view,
    build_quality_view,
)
from song_agent.schemas.song import SongPlan, SongRequest
from song_agent.song_editor import (
    EditorPatchError,
    EditorPatchStaleError,
    EditorPreviewStore,
    apply_editor_patch,
    build_editor_state,
    editor_edit_metadata,
    song_plan_hash as editor_song_plan_hash,
)
from song_agent.stems import (
    StemManifest,
    clear_stem_artifacts,
    load_or_preview_stem_manifest,
    read_stem_manifest,
    render_stem_audio,
    render_stem_midis,
    stem_manifest_stale,
    stem_audio_path,
    stem_midi_path,
)
from song_agent.webui import panel_html

RUNS_DIR = Path("runs")

REFERENCE_IMPORT_MAX_BODY_BYTES = int(MAX_REFERENCE_WAV_BYTES * 4 / 3) + 1_000_000

class JobCancelled(Exception):
    """Raised when a job stops at a stage boundary after cancellation."""

class JobStore:
    def __init__(
        self,
        runs_dir: Path = RUNS_DIR,
        asset_store: AssetStore | None = None,
        reference_store: ReferenceStore | None = None,
        context_pack_store: ContextPackStore | None = None,
    ) -> None:
        self.runs_dir = Path(runs_dir).resolve()
        self.asset_store = asset_store or AssetStore()
        self.reference_store = reference_store or ReferenceStore()
        self.context_pack_store = context_pack_store or ContextPackStore()
        self.lock = threading.RLock()
        self.jobs: dict[str, JobState] = {}
        self.load_existing_jobs()

    def load_existing_jobs(self) -> None:
        if not self.runs_dir.exists():
            return
        for state_path in self.runs_dir.glob("*/data/job-state.json"):
            try:
                job = JobState.from_dict(read_json(state_path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if job.status in {"queued", "running", "waiting_retry", "paused"}:
                job.status = "interrupted"
                job.step = "interrupted"
                job.message = "This job was interrupted by a previous server shutdown."
                job.error = "Job was running when the server stopped."
                job.interrupted = True
                job.updated_at = _utc_now()
                self._write_job(job)
            self.jobs[job.job_id] = job

    def list_jobs(self, include_hidden: bool = False) -> list[JobState]:
        with self.lock:
            return sorted(
                [
                    job
                    for job in self.jobs.values()
                    if include_hidden or not job.hidden
                ],
                key=lambda job: job.created_at,
                reverse=True,
            )

    def get_job(self, job_id: str) -> JobState | None:
        with self.lock:
            return self.jobs.get(job_id)

    def create_job(self, payload: dict[str, Any], start_immediately: bool = True) -> JobState:
        request = SongRequest.from_dict(payload)
        asset_refs = payload.get("asset_refs") if isinstance(payload.get("asset_refs"), list) else []
        reference_refs = payload.get("reference_refs") if isinstance(payload.get("reference_refs"), list) else []
        context_pack = payload.get("context_pack") if isinstance(payload.get("context_pack"), dict) else None
        generation_mode = _generation_mode(payload)
        pipeline_mode = _pipeline_mode(payload)
        provider_snapshot: dict[str, Any]
        if generation_mode == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            provider_snapshot = provider_config.to_snapshot("provider", _utc_now())
        else:
            provider_snapshot = {"mode": "local", "summary": "Local deterministic composer"}
        with self.lock:
            run_dir = self._reserve_run_dir(request.title)
            job_id = run_dir.name
            now = _utc_now()
            job = JobState(
                job_id=job_id,
                title=request.title,
                output_dir=str(run_dir),
                status="queued",
                created_at=now,
                updated_at=now,
                step="queued",
                message="Queued for local deterministic generation.",
                input_payload={
                    **request.to_dict(),
                    **({"asset_refs": asset_refs} if asset_refs else {}),
                    **({"reference_refs": reference_refs} if reference_refs else {}),
                    **({"context_pack": context_pack} if context_pack else {}),
                },
                provider_snapshot=provider_snapshot,
                heartbeat_at=now,
                generation_mode=generation_mode,
                pipeline_mode=pipeline_mode,
            )
            self.jobs[job_id] = job
            self._write_job(job)

        if start_immediately:
            self.start_job(job_id)
        return job

    def create_edit_job(
        self,
        *,
        project_id: str,
        parent_version_id: str,
        parent_job: JobState,
        parent_plan: SongPlan,
        intent: EditIntent,
        preset: dict[str, Any] | None = None,
        name: str = "",
        start_immediately: bool = True,
        provider_patch: dict[str, Any] | None = None,
        provider_usage: dict[str, Any] | None = None,
        provider_snapshot: dict[str, Any] | None = None,
        template_id: str | None = None,
        preview_id: str | None = None,
        candidate_group_id: str | None = None,
        candidate_id: str | None = None,
        candidate: dict[str, Any] | None = None,
        asset_refs: list[dict[str, Any]] | None = None,
        reference_refs: list[dict[str, Any]] | None = None,
        context_pack: dict[str, Any] | None = None,
    ) -> JobState:
        validate_edit_intent(parent_plan, intent)
        if intent.provider_mode == "provider" and provider_patch is None:
            raise NotImplementedError("Provider-backed edit is not implemented in v1.1.0.")
        with self.lock:
            title = _clean_title(name) or f"{parent_plan.title} {intent.edit_type}"
            run_dir = self._reserve_run_dir(title)
            job_id = run_dir.name
            now = _utc_now()
            metadata = build_edit_metadata(
                project_id=project_id,
                parent_version_id=parent_version_id,
                parent_job_id=parent_job.job_id,
                intent=intent,
                created_at=now,
            )
            metadata["preset"] = preset
            if provider_patch is not None:
                metadata["provider_patch"] = provider_patch
                metadata["provider"] = provider_snapshot or {}
                metadata["provider_usage"] = provider_usage or {}
                metadata["template_id"] = template_id
                metadata["preview_id"] = preview_id
                if candidate_group_id:
                    metadata["candidate_group_id"] = candidate_group_id
                if candidate_id:
                    metadata["candidate_id"] = candidate_id
                if candidate:
                    metadata["candidate"] = _candidate_source_summary(candidate)
            if asset_refs:
                metadata["asset_refs"] = list(asset_refs)
            if reference_refs:
                metadata["reference_refs"] = list(reference_refs)
            if context_pack:
                metadata["context_pack"] = dict(context_pack)
            job = JobState(
                job_id=job_id,
                title=title,
                output_dir=str(run_dir),
                status="queued",
                created_at=now,
                updated_at=now,
                step="queued",
                message="Queued for local deterministic edit.",
                input_payload={
                    **parent_job.input_payload,
                    "edit_type": intent.edit_type,
                    "parent_job_id": parent_job.job_id,
                    "parent_version_id": parent_version_id,
                    "project_id": project_id,
                    **({"asset_refs": list(asset_refs)} if asset_refs else {}),
                    **({"reference_refs": list(reference_refs)} if reference_refs else {}),
                    **({"context_pack": dict(context_pack)} if context_pack else {}),
                },
                provider_snapshot=provider_snapshot or {"mode": "local", "summary": "Local deterministic edit engine"},
                heartbeat_at=now,
                generation_mode=intent.provider_mode,
                pipeline_mode=parent_job.pipeline_mode,
                job_type="edit",
                edit_metadata=metadata,
            )
            if preset:
                job.input_payload["preset_id"] = preset.get("preset_id")
            if provider_patch is not None:
                job.input_payload["provider_patch"] = {
                    "summary": provider_patch.get("summary"),
                    "operation_count": len(provider_patch.get("operations", [])),
                }
                job.input_payload["template_id"] = template_id
                job.input_payload["preview_id"] = preview_id
                if candidate_group_id:
                    job.input_payload["candidate_group_id"] = candidate_group_id
                if candidate_id:
                    job.input_payload["candidate_id"] = candidate_id
                if candidate:
                    job.input_payload["candidate"] = _candidate_source_summary(candidate)
            self.jobs[job_id] = job
            self._write_job(job)
            write_json(ProjectPaths.create(run_dir).data / "edit-metadata.json", metadata)
        if start_immediately:
            self.start_job(job_id)
        return job

    def start_job(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        if job is None or job.status != "queued":
            return False
        if job.cancel_requested:
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
            )
            return False
        thread = threading.Thread(
            target=self._run_edit_job if job.job_type == "edit" else self._run_job,
            args=(job_id,),
            name=f"musicforge-{job.job_type}-job-{job_id}",
            daemon=True,
        )
        thread.start()
        return True

    def hide_job(self, job_id: str, hidden: bool) -> JobState | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        self._update_job(job, hidden=hidden)
        return job

    def cancel_job(self, job_id: str) -> tuple[JobState | None, HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return None, HTTPStatus.NOT_FOUND, "Job not found."
        if job.status == "queued":
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
                cancel_requested=True,
            )
            return job, HTTPStatus.OK, None
        if job.status == "running":
            self._update_job(
                job,
                cancel_requested=True,
                message="Cancellation requested; job will stop at the next stage boundary.",
            )
            return job, HTTPStatus.OK, None
        if job.status == "cancelled":
            return job, HTTPStatus.OK, None
        return job, HTTPStatus.CONFLICT, f"Cannot cancel a {job.status} job."

    def retry_job(self, job_id: str) -> tuple[JobState | None, HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return None, HTTPStatus.NOT_FOUND, "Job not found."
        if job.status not in {"failed", "stalled", "interrupted"}:
            return job, HTTPStatus.CONFLICT, f"Cannot retry a {job.status} job."

        try:
            provider_snapshot = self._provider_snapshot_for_retry(job)
        except ProviderError as exc:
            return job, HTTPStatus.BAD_REQUEST, str(exc)

        previous_error = job.error or job.last_error
        self._update_job(
            job,
            status="queued",
            step="queued",
            message="Retry queued.",
            error=None,
            last_error=previous_error,
            retry_requested=True,
            retry_count=job.retry_count + 1,
            cancel_requested=False,
            stalled=False,
            interrupted=False,
            finished_at=None,
            provider_snapshot=provider_snapshot,
            heartbeat_at=_utc_now(),
        )
        append_event(
            ProjectPaths.create(Path(job.output_dir)),
            {"event": "retry_requested", "retry_count": job.retry_count},
        )
        self.start_job(job_id)
        return job, HTTPStatus.OK, None

    def retry_job_node(
        self,
        job_id: str,
        node_name: str,
    ) -> tuple[JobState | None, HTTPStatus, str | None, dict[str, Any]]:
        job = self.get_job(job_id)
        if job is None:
            return None, HTTPStatus.NOT_FOUND, "Job not found.", {}
        try:
            affected_nodes = affected_nodes_for_retry(node_name)
        except ValueError as exc:
            if str(exc).startswith("Unknown node:"):
                return job, HTTPStatus.NOT_FOUND, "Node record not found.", {}
            return job, HTTPStatus.BAD_REQUEST, str(exc), {}
        if job.pipeline_mode != "multinode":
            return job, HTTPStatus.CONFLICT, "Node retry requires a multinode job.", {}
        if job.status == "running":
            return job, HTTPStatus.CONFLICT, "Cannot retry a node while the job is running.", {}
        if job.status not in {"completed", "failed", "stalled", "interrupted"}:
            return job, HTTPStatus.CONFLICT, f"Cannot retry a node for a {job.status} job.", {}

        node_store = NodeStore(Path(job.output_dir))
        try:
            node_store.read_node(node_name)
        except FileNotFoundError:
            return job, HTTPStatus.NOT_FOUND, "Node record not found.", {}
        except ValueError as exc:
            return job, HTTPStatus.BAD_REQUEST, str(exc), {}

        try:
            provider_snapshot = self._provider_snapshot_for_retry(job)
        except ProviderError as exc:
            return job, HTTPStatus.BAD_REQUEST, str(exc), {}

        retry = {"node": node_name, "affected_nodes": affected_nodes}
        self._update_job(
            job,
            status="running",
            step=f"retry:{node_name}",
            message=f"Retrying node {node_name}.",
            error=None,
            retry_requested=True,
            retry_count=job.retry_count + 1,
            cancel_requested=False,
            stalled=False,
            interrupted=False,
            finished_at=None,
            provider_snapshot=provider_snapshot,
            heartbeat_at=_utc_now(),
        )
        thread = threading.Thread(
            target=self._run_node_retry,
            args=(job.job_id, node_name, affected_nodes, provider_snapshot),
            name=f"musicforge-node-retry-{job.job_id}-{node_name}",
            daemon=True,
        )
        thread.start()
        return job, HTTPStatus.ACCEPTED, None, retry

    def run_watchdog_tick(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        marked = 0
        with self.lock:
            jobs = list(self.jobs.values())
        for job in jobs:
            if job.status != "running":
                continue
            heartbeat = _parse_iso_datetime(job.heartbeat_at or job.updated_at)
            if heartbeat is None:
                continue
            elapsed = (now - heartbeat).total_seconds()
            if elapsed > job.stall_timeout_seconds:
                self._update_job(
                    job,
                    status="stalled",
                    step="stalled",
                    message="Job stalled because no heartbeat was observed.",
                    error="No heartbeat within stall timeout.",
                    last_error="No heartbeat within stall timeout.",
                    stalled=True,
                    finished_at=_utc_now(),
                )
                marked += 1
        return marked

    def delete_job(self, job_id: str) -> tuple[bool, HTTPStatus, str | None]:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return False, HTTPStatus.NOT_FOUND, "Job not found."
            if job.status == "running":
                return False, HTTPStatus.CONFLICT, "Cannot delete a running job. Cancel it first."
            try:
                run_dir = self._ensure_run_dir_is_safe(Path(job.output_dir))
            except ValueError as exc:
                return False, HTTPStatus.CONFLICT, str(exc)
            if run_dir.exists():
                shutil.rmtree(run_dir)
            self.jobs.pop(job_id, None)
            return True, HTTPStatus.OK, None

    def render_job_audio(self, job_id: str, *, config: Any | None = None, audio_profile: Any | None = None) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        midi_path = run_dir / "renders" / "song.mid"
        if not midi_path.exists():
            return {}, HTTPStatus.CONFLICT, "song.mid is not available for this job yet."
        try:
            if config is None:
                config, _sources = load_renderer_config()
            wav_path = render_audio(midi_path, run_dir / "renders" / "song.wav", config)
            manifest = build_audio_artifact_manifest(
                artifact_id=f"job-{job_id}",
                scope="job",
                wav_path=wav_path,
                midi_path=midi_path,
                song_plan_path=run_dir / "data" / "song-plan.json",
                renderer_config=config,
                profile=audio_profile,
                extra_source={"job_id": job_id},
                now=_utc_now(),
            )
            write_audio_artifact_manifest(run_dir / "renders" / AUDIO_ARTIFACT_FILENAME, manifest)
        except RendererError as exc:
            error_path = run_dir / "logs" / "audio-render-error.json"
            write_json(
                error_path,
                {
                    "error": str(exc),
                    "checked_at": _utc_now(),
                },
            )
            return {}, HTTPStatus.BAD_REQUEST, str(exc)

        validator_report_path = run_dir / "data" / "validator-report.json"
        if validator_report_path.exists():
            report = read_json(validator_report_path)
            report["audio"] = _audio_report(wav_path)
            report["audio_artifact"] = audio_artifact_summary(manifest)
            write_json(validator_report_path, report)
        artifacts = dict(job.artifacts)
        artifacts["audio"] = str(wav_path)
        artifacts["audio_artifact"] = str(run_dir / "renders" / AUDIO_ARTIFACT_FILENAME)
        self._update_job(job, artifacts=artifacts)
        return {
            "audio": str(wav_path),
            "artifact": _artifact_dict(wav_path),
            "audio_artifact": manifest,
            "audio_artifact_summary": audio_artifact_summary(manifest),
        }, HTTPStatus.OK, None

    def get_job_stems(self, job_id: str) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            return {}, HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet."
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            manifest = load_or_preview_stem_manifest(plan, run_dir, job.job_id, now=_utc_now())
        except ValueError as exc:
            return {}, HTTPStatus.CONFLICT, str(exc)
        return _manifest_response(job.job_id, manifest), HTTPStatus.OK, None

    def render_job_stems(
        self,
        job_id: str,
        *,
        force: bool = False,
    ) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            return {}, HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet."
        try:
            plan = SongPlan.from_dict(read_json(plan_path))
            existing_manifest = read_stem_manifest(run_dir)
            if existing_manifest is not None and stem_manifest_stale(existing_manifest, plan):
                clear_stem_artifacts(run_dir)
            manifest = render_stem_midis(plan, run_dir, job.job_id, now=_utc_now(), force=force)
        except ValueError as exc:
            return {}, HTTPStatus.CONFLICT, str(exc)
        artifacts = dict(job.artifacts)
        artifacts["stems"] = str(run_dir / "stems" / "manifest.json")
        self._update_job(job, artifacts=artifacts)
        return _manifest_response(job.job_id, manifest, status=_stem_midi_manifest_status(manifest)), HTTPStatus.OK, None

    def render_job_stem_audio(
        self,
        job_id: str,
        *,
        stem_ids: list[str] | None = None,
        force: bool = False,
    ) -> tuple[dict[str, Any], HTTPStatus, str | None]:
        job = self.get_job(job_id)
        if job is None:
            return {}, HTTPStatus.NOT_FOUND, "Job not found."
        run_dir = Path(job.output_dir)
        plan_path = run_dir / "data" / "song-plan.json"
        if not plan_path.exists():
            return {}, HTTPStatus.CONFLICT, "song-plan.json is not available for this job yet."
        try:
            manifest = read_stem_manifest(run_dir)
            if manifest is None:
                plan = SongPlan.from_dict(read_json(plan_path))
                manifest = render_stem_midis(plan, run_dir, job.job_id, now=_utc_now())
            else:
                plan = SongPlan.from_dict(read_json(plan_path))
                if stem_manifest_stale(manifest, plan):
                    clear_stem_artifacts(run_dir)
                    return {}, HTTPStatus.CONFLICT, "Stem manifest is stale. Render stems again."
            config, _sources = load_renderer_config()
            config.validate_ready_for_render()
            manifest = render_stem_audio(
                run_dir,
                config,
                plan=plan,
                stem_ids=stem_ids,
                force=force,
                now=_utc_now(),
            )
        except FileNotFoundError as exc:
            return {}, HTTPStatus.NOT_FOUND, str(exc) or "Stem not found."
        except RendererError as exc:
            return {}, HTTPStatus.BAD_REQUEST, str(exc)
        except ValueError as exc:
            return {}, HTTPStatus.CONFLICT, str(exc)
        artifacts = dict(job.artifacts)
        artifacts["stems"] = str(run_dir / "stems" / "manifest.json")
        if any(stem.audio_exists for stem in manifest.stems):
            artifacts["stem_audio"] = str(run_dir / "stems" / "audio")
        self._update_job(job, artifacts=artifacts)
        return _manifest_response(job.job_id, manifest, status=_stem_audio_manifest_status(manifest)), HTTPStatus.OK, None

    def _run_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job is None:
            return

        request = SongRequest.from_dict(job.input_payload)
        provider_config = None
        provider_snapshot = job.provider_snapshot
        if provider_snapshot.get("mode") == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            ProjectPaths.create(Path(job.output_dir))
            write_json(
                Path(job.output_dir) / "data" / "provider-snapshot.json",
                provider_snapshot,
            )
        if job.cancel_requested:
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Job was cancelled before generation started.",
            )
            return
        self._update_job(
            job,
            status="running",
            step="generate",
            message="Generating song plan and MIDI.",
            attempt_count=job.attempt_count + 1,
            started_at=job.started_at or _utc_now(),
            heartbeat_at=_utc_now(),
            stalled=False,
        )
        try:
            append_event(
                ProjectPaths.create(Path(job.output_dir)),
                {"event": "attempt_started", "attempt_count": job.attempt_count},
            )
            job = self.get_job(job_id)
            if job is None or job.cancel_requested:
                if job is not None:
                    self._update_job(
                        job,
                        status="cancelled",
                        step="cancelled",
                        message="Job was cancelled before generation started.",
                    )
                return
            self._heartbeat(job)
            context_snapshot = self._prepare_context_pack_for_job(job)
            asset_snapshot = self._prepare_asset_refs_for_job(job)
            reference_snapshot = self._prepare_reference_refs_for_job(job)
            plan_path, midi_path = generate_request(
                request,
                out_dir=Path(job.output_dir),
                force=False,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot if provider_config is not None else None,
                control=self._control_callback(job_id),
                pipeline_mode=job.pipeline_mode,
            )
            if asset_snapshot["asset_refs"]:
                plan = SongPlan.from_dict(read_json(plan_path))
                plan = apply_asset_refs_to_plan(plan, self.asset_store, asset_snapshot["asset_refs"])
                write_json(plan_path, plan.to_dict())
                render_midi(plan, midi_path)
                write_asset_refs_snapshot(Path(job.output_dir), asset_snapshot)
                self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "job_generation", "job_id": job.job_id})
            if reference_snapshot["reference_refs"]:
                write_reference_refs_snapshot(Path(job.output_dir), reference_snapshot)
                self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "job_generation", "job_id": job.job_id})
            clear_stem_artifacts(Path(job.output_dir))
            job = self.get_job(job_id)
            if job is None:
                return
            if job.cancel_requested:
                self._update_job(
                    job,
                    status="cancelled",
                    step="cancelled",
                    message="Job was cancelled after the generation stage.",
                    finished_at=_utc_now(),
                )
                return
            self._heartbeat(job)
            validator_report_path = Path(job.output_dir) / "data" / "validator-report.json"
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            artifacts = {
                "request": str(Path(job.output_dir) / "data" / "request.json"),
                "song_plan": str(plan_path),
                "run_summary": str(Path(job.output_dir) / "data" / "run-summary.json"),
                "validator_report": str(validator_report_path),
                "job_state": str(Path(job.output_dir) / "data" / "job-state.json"),
                "events": str(Path(job.output_dir) / "logs" / "events.jsonl"),
                "midi": str(midi_path),
            }
            provider_snapshot_path = Path(job.output_dir) / "data" / "provider-snapshot.json"
            if provider_snapshot_path.exists():
                artifacts["provider_snapshot"] = str(provider_snapshot_path)
            nodes_dir = Path(job.output_dir) / "data" / "nodes"
            if nodes_dir.exists():
                artifacts["nodes"] = str(nodes_dir)
            if (Path(job.output_dir) / "data" / "asset-refs.json").exists():
                artifacts["asset_refs"] = str(Path(job.output_dir) / "data" / "asset-refs.json")
            if (Path(job.output_dir) / "data" / "reference-refs.json").exists():
                artifacts["reference_refs"] = str(Path(job.output_dir) / "data" / "reference-refs.json")
            if (Path(job.output_dir) / "data" / "context-pack.json").exists():
                artifacts["context_pack"] = str(Path(job.output_dir) / "data" / "context-pack.json")
            self._update_job(
                job,
                status="completed",
                step="completed",
                message="Song generation completed.",
                summary=summary,
                error=None,
                last_error=None,
                finished_at=_utc_now(),
                artifacts=artifacts,
            )
        except JobCancelled:
            job = self.get_job(job_id)
            if job is not None:
                self._update_job(
                    job,
                    status="cancelled",
                    step="cancelled",
                    message="Job was cancelled at a stage boundary.",
                    finished_at=_utc_now(),
                )
        except Exception as exc:
            self._update_job(
                job,
                status="failed",
                step="failed",
                message="Song generation failed.",
                error=str(exc),
                last_error=str(exc),
                finished_at=_utc_now(),
            )

    def _run_edit_job(self, job_id: str) -> None:
        job = self.get_job(job_id)
        if job is None:
            return
        run_dir = Path(job.output_dir)
        paths = ProjectPaths.create(run_dir)
        if job.cancel_requested:
            self._update_job(
                job,
                status="cancelled",
                step="cancelled",
                message="Edit job was cancelled before generation started.",
            )
            return
        self._update_job(
            job,
            status="running",
            step="edit",
            message="Applying local edit intent.",
            attempt_count=job.attempt_count + 1,
            started_at=job.started_at or _utc_now(),
            heartbeat_at=_utc_now(),
            stalled=False,
        )
        try:
            metadata = dict(job.edit_metadata)
            intent = EditIntent.from_dict(metadata)
            parent_job_id = str(metadata.get("parent_job_id") or "")
            parent_job = self.get_job(parent_job_id)
            if parent_job is None:
                raise FileNotFoundError("Parent version job is missing.")
            parent_plan_path = Path(parent_job.output_dir) / "data" / "song-plan.json"
            if not parent_plan_path.exists():
                raise FileNotFoundError("Parent song-plan.json is missing.")
            parent_plan = SongPlan.from_dict(read_json(parent_plan_path))
            append_event(paths, {"event": "edit_started", "edit_type": intent.edit_type, "target": intent.target.to_dict()})
            self._heartbeat(job)
            context_snapshot = self._prepare_context_pack_for_job(job)
            asset_snapshot = self._prepare_asset_refs_for_job(job)
            reference_snapshot = self._prepare_reference_refs_for_job(job)
            provider_patch_data = metadata.get("provider_patch")
            if provider_patch_data:
                patch = ProviderEditPatch.from_dict(provider_patch_data)
                result = apply_provider_edit_patch(parent_plan, patch)
            else:
                result = apply_edit_intent(parent_plan, intent)
            if asset_snapshot["asset_refs"]:
                result_plan = apply_asset_refs_to_plan(result.plan, self.asset_store, asset_snapshot["asset_refs"])
                result = EditedSongPlanResult(plan=result_plan, summary=result.summary, warnings=result.warnings)
            if metadata.get("edit_source") == "audition_review" and isinstance(metadata.get("review_edit"), dict):
                from song_agent.review_edits import ReviewEditIntent

                review_edit_result = apply_review_edit(parent_plan, ReviewEditIntent.from_dict(metadata["review_edit"]))
                result = review_edit_result
                if asset_snapshot["asset_refs"]:
                    result_plan = apply_asset_refs_to_plan(result.plan, self.asset_store, asset_snapshot["asset_refs"])
                    result = EditedSongPlanResult(plan=result_plan, summary=result.summary, warnings=result.warnings)
            if metadata.get("edit_source") == "review_task_candidate" and isinstance(metadata.get("review_candidate_intents"), list):
                intents = [EditIntent.from_dict(dict(item)) for item in metadata["review_candidate_intents"] if isinstance(item, dict)]
                result = apply_candidate_intents(parent_plan, intents)
                if asset_snapshot["asset_refs"]:
                    result_plan = apply_asset_refs_to_plan(result.plan, self.asset_store, asset_snapshot["asset_refs"])
                    result = EditedSongPlanResult(plan=result_plan, summary=result.summary, warnings=result.warnings)
            if job.cancel_requested:
                raise JobCancelled()
            plan_path = paths.data / "song-plan.json"
            midi_path = paths.renders / "song.mid"
            validator_report_path = paths.data / "validator-report.json"
            request_path = paths.data / "request.json"
            write_json(request_path, job.input_payload)
            edit_metadata = build_edit_metadata(
                project_id=str(metadata.get("project_id") or ""),
                parent_version_id=str(metadata.get("parent_version_id") or ""),
                parent_job_id=parent_job.job_id,
                intent=intent,
                created_at=str(metadata.get("created_at") or job.created_at),
                summary=result.summary,
                warnings=result.warnings,
            )
            edit_metadata["preset"] = metadata.get("preset")
            if provider_patch_data:
                edit_metadata["provider_mode"] = "provider"
                edit_metadata["provider_patch"] = provider_patch_data
                edit_metadata["provider"] = metadata.get("provider") or {}
                edit_metadata["template_id"] = metadata.get("template_id")
                edit_metadata["preview_id"] = metadata.get("preview_id")
                if metadata.get("candidate_group_id"):
                    edit_metadata["candidate_group_id"] = metadata.get("candidate_group_id")
                if metadata.get("candidate_id"):
                    edit_metadata["candidate_id"] = metadata.get("candidate_id")
                if metadata.get("candidate"):
                    edit_metadata["candidate"] = _candidate_source_summary(metadata.get("candidate"))
            if asset_snapshot["asset_refs"]:
                edit_metadata["asset_refs"] = list(asset_snapshot["asset_refs"])
            if reference_snapshot["reference_refs"]:
                edit_metadata["reference_refs"] = list(reference_snapshot["reference_refs"])
            if context_snapshot:
                edit_metadata["context_pack"] = context_snapshot
            if metadata.get("edit_source") == "audition_review":
                edit_metadata.update(
                    {
                        "edit_source": "audition_review",
                        "review_edit": metadata.get("review_edit"),
                        "review_summary": metadata.get("review_summary") or {},
                    }
                )
            if metadata.get("edit_source") == "review_task_candidate":
                edit_metadata.update(
                    {
                        "edit_source": "review_task_candidate",
                        "operation_count": len(metadata.get("review_candidate_intents") or []),
                        "review_task": metadata.get("review_task") if isinstance(metadata.get("review_task"), dict) else {},
                        "review_candidate": metadata.get("review_candidate") if isinstance(metadata.get("review_candidate"), dict) else {},
                        "review_candidate_source": metadata.get("review_candidate_source") if isinstance(metadata.get("review_candidate_source"), dict) else {},
                        "review_provider_patch": metadata.get("review_provider_patch") if isinstance(metadata.get("review_provider_patch"), dict) else {},
                        "review_decision": metadata.get("review_decision") if isinstance(metadata.get("review_decision"), dict) else {},
                        "review_judge": metadata.get("review_judge") if isinstance(metadata.get("review_judge"), dict) else {},
                        "review_sprint": metadata.get("review_sprint") if isinstance(metadata.get("review_sprint"), dict) else {},
                        "review_sprint_recommendation": metadata.get("review_sprint_recommendation") if isinstance(metadata.get("review_sprint_recommendation"), dict) else {},
                        "review_sprint_action_queue": metadata.get("review_sprint_action_queue") if isinstance(metadata.get("review_sprint_action_queue"), dict) else {},
                        "review_edit": metadata.get("review_edit") if isinstance(metadata.get("review_edit"), dict) else {},
                        "review_candidate_intents": metadata.get("review_candidate_intents") if isinstance(metadata.get("review_candidate_intents"), list) else [],
                    }
                )
            write_json(paths.data / "edit-metadata.json", edit_metadata)
            if asset_snapshot["asset_refs"]:
                write_asset_refs_snapshot(run_dir, asset_snapshot)
                self.asset_store.mark_used(asset_snapshot["asset_refs"], {"usage_type": "edit", "job_id": job.job_id, "project_id": metadata.get("project_id"), "version_id": metadata.get("parent_version_id")})
            if reference_snapshot["reference_refs"]:
                write_reference_refs_snapshot(run_dir, reference_snapshot)
                self.reference_store.mark_used(reference_snapshot["reference_refs"], {"usage_type": "edit", "job_id": job.job_id, "project_id": metadata.get("project_id"), "version_id": metadata.get("parent_version_id")})
            if metadata.get("provider_usage"):
                usage = dict(metadata["provider_usage"])
                usage["completed_at"] = _utc_now()
                usage["status"] = "completed"
                write_json(paths.data / "provider-usage.json", usage)
            write_json(plan_path, result.plan.to_dict())
            render_midi(result.plan, midi_path)
            clear_stem_artifacts(run_dir)
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            summary["edit"] = result.summary
            write_json(paths.data / "run-summary.json", summary)
            artifacts = _job_artifacts(run_dir, plan_path, midi_path, validator_report_path)
            artifacts["edit_metadata"] = str(paths.data / "edit-metadata.json")
            if (paths.data / "asset-refs.json").exists():
                artifacts["asset_refs"] = str(paths.data / "asset-refs.json")
            if (paths.data / "reference-refs.json").exists():
                artifacts["reference_refs"] = str(paths.data / "reference-refs.json")
            if (paths.data / "context-pack.json").exists():
                artifacts["context_pack"] = str(paths.data / "context-pack.json")
            if (paths.data / "provider-usage.json").exists():
                artifacts["provider_usage"] = str(paths.data / "provider-usage.json")
            self._update_job(
                job,
                status="completed",
                step="completed",
                message="Edit job completed.",
                summary=summary,
                error=None,
                last_error=None,
                finished_at=_utc_now(),
                artifacts=artifacts,
                edit_metadata=edit_metadata,
            )
            append_event(paths, {"event": "edit_completed", "summary": result.summary})
        except JobCancelled:
            latest = self.get_job(job_id)
            if latest is not None:
                self._update_job(
                    latest,
                    status="cancelled",
                    step="cancelled",
                    message="Edit job was cancelled at a stage boundary.",
                    finished_at=_utc_now(),
                )
        except Exception as exc:
            latest = self.get_job(job_id) or job
            self._update_job(
                latest,
                status="failed",
                step="failed",
                message="Edit job failed.",
                error=str(exc),
                last_error=str(exc),
                finished_at=_utc_now(),
            )

    def _prepare_asset_refs_for_job(self, job: JobState) -> dict[str, Any]:
        snapshot = asset_refs_snapshot(self.asset_store, job.input_payload.get("asset_refs"), captured_at=_utc_now())
        if snapshot["asset_refs"]:
            ProjectPaths.create(Path(job.output_dir))
            write_asset_refs_snapshot(Path(job.output_dir), snapshot)
        return snapshot

    def _prepare_reference_refs_for_job(self, job: JobState) -> dict[str, Any]:
        snapshot = reference_refs_snapshot(self.reference_store, job.input_payload.get("reference_refs"), captured_at=_utc_now())
        if snapshot["reference_refs"]:
            ProjectPaths.create(Path(job.output_dir))
            write_reference_refs_snapshot(Path(job.output_dir), snapshot)
        return snapshot

    def _prepare_context_pack_for_job(self, job: JobState) -> dict[str, Any] | None:
        context_pack = job.input_payload.get("context_pack")
        if not isinstance(context_pack, dict) or not context_pack.get("pack_id"):
            return None
        pack = self.context_pack_store.read_pack(str(context_pack["pack_id"]))
        applied = {
            "asset_refs": job.input_payload.get("asset_refs") if isinstance(job.input_payload.get("asset_refs"), list) else [],
            "reference_refs": job.input_payload.get("reference_refs") if isinstance(job.input_payload.get("reference_refs"), list) else [],
        }
        snapshot = context_pack_snapshot(pack, applied, captured_at=_utc_now())
        ProjectPaths.create(Path(job.output_dir))
        write_context_pack_snapshot(Path(job.output_dir), snapshot)
        return snapshot

    def _run_node_retry(
        self,
        job_id: str,
        node_name: str,
        affected_nodes: list[str],
        provider_snapshot: dict[str, Any],
    ) -> None:
        job = self.get_job(job_id)
        if job is None:
            return
        request = SongRequest.from_dict(job.input_payload)
        run_dir = Path(job.output_dir)
        paths = ProjectPaths.create(run_dir)
        node_store = NodeStore(run_dir)
        provider_config = None
        if provider_snapshot.get("mode") == "provider":
            provider_config, _sources = load_provider_config()
            provider_config.validate_ready_for_provider()
            write_json(paths.data / "provider-snapshot.json", provider_snapshot)
        try:
            append_event(
                paths,
                {"event": "node_retry_requested", "node": node_name, "affected_nodes": affected_nodes},
            )
            invalidated = node_store.invalidate_nodes(affected_nodes, invalidated_by=node_name)
            for record in invalidated:
                append_event(
                    paths,
                    {"event": "node_invalidated", "node": record.node, "invalidated_by": node_name},
                )
            if job.cancel_requested:
                raise JobCancelled()
            self._heartbeat(job)
            plan = rerun_multinode_from_node(
                request,
                node_name,
                provider_config=provider_config,
                provider_snapshot=provider_snapshot if provider_config is not None else None,
                node_store=node_store,
                control=self._control_callback(job_id),
            )
            plan.validate()
            plan_path = paths.data / "song-plan.json"
            midi_path = paths.renders / "song.mid"
            validator_report_path = paths.data / "validator-report.json"
            write_json(plan_path, plan.to_dict())
            render_midi(plan, midi_path)
            clear_stem_artifacts(run_dir)
            write_json(validator_report_path, _build_validator_report(plan_path, midi_path))
            summary = _build_summary(plan_path, midi_path)
            artifacts = _job_artifacts(run_dir, plan_path, midi_path, validator_report_path)
            self._update_job(
                job,
                status="completed",
                step="completed",
                message=f"Node {node_name} retry completed.",
                summary=summary,
                error=None,
                last_error=None,
                finished_at=_utc_now(),
                artifacts=artifacts,
            )
            append_event(
                paths,
                {"event": "node_retry_completed", "node": node_name, "affected_nodes": affected_nodes},
            )
        except JobCancelled:
            latest = self.get_job(job_id)
            if latest is not None:
                self._update_job(
                    latest,
                    status="cancelled",
                    step="cancelled",
                    message="Node retry was cancelled at a stage boundary.",
                    finished_at=_utc_now(),
                )
        except Exception as exc:
            latest = self.get_job(job_id) or job
            self._update_job(
                latest,
                status="failed",
                step="failed",
                message=f"Node {node_name} retry failed.",
                error=str(exc),
                last_error=str(exc),
                finished_at=_utc_now(),
            )

    def _update_job(self, job: JobState, **changes: Any) -> None:
        with self.lock:
            for key, value in changes.items():
                setattr(job, key, value)
            job.updated_at = _utc_now()
            self.jobs[job.job_id] = job
            self._write_job(job)

    def _heartbeat(self, job: JobState) -> None:
        self._update_job(job, heartbeat_at=_utc_now(), last_seen_at=_utc_now())

    def _control_callback(self, job_id: str):
        def control(phase: str, step_name: str) -> None:
            job = self.get_job(job_id)
            if job is None:
                raise JobCancelled()
            self._update_job(
                job,
                heartbeat_at=_utc_now(),
                last_seen_at=_utc_now(),
                step=step_name,
            )
            if job.cancel_requested:
                raise JobCancelled()

        return control

    def _write_job(self, job: JobState) -> None:
        paths = ProjectPaths.create(Path(job.output_dir))
        write_json(paths.data / "job-state.json", job.to_dict())

    def _reserve_run_dir(self, title: str) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(title)
        for index in range(1, 10_000):
            name = slug if index == 1 else f"{slug}-{index}"
            candidate = self.runs_dir / name
            try:
                candidate.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                continue
            return candidate
        raise RuntimeError(f"Could not allocate a unique run directory for {title!r}.")

    def _ensure_run_dir_is_safe(self, run_dir: Path) -> Path:
        base = self.runs_dir.resolve()
        target = run_dir.resolve()
        if target == base:
            raise ValueError("Refusing to delete runs directory.")
        if base not in target.parents:
            raise ValueError("Refusing to delete outside runs directory.")
        return target

    def _provider_snapshot_for_retry(self, job: JobState) -> dict[str, Any]:
        if job.provider_snapshot.get("mode") != "provider":
            return job.provider_snapshot
        provider_config, _sources = load_provider_config()
        provider_config.validate_ready_for_provider()
        return provider_config.to_snapshot("provider", _utc_now())

class BatchRunner:
    def __init__(self, batch_store: BatchStore, job_store: JobStore, project_store: ProjectStore | None = None) -> None:
        self.batch_store = batch_store
        self.job_store = job_store
        self.project_store = project_store
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.threads: dict[str, threading.Thread] = {}
        self.audio_threads: dict[str, threading.Thread] = {}
        self.stem_threads: dict[str, threading.Thread] = {}
        self.recover_existing_batches()

    def recover_existing_batches(self) -> None:
        for document in self.batch_store.list_batches(include_hidden=True):
            recovered_audio = self._recover_interrupted_audio(document)
            if recovered_audio:
                self.batch_store.save_batch(document)
                self.batch_store.append_event(
                    document.state.batch_id,
                    "batch_audio_recovered_failed",
                    {"failed_count": recovered_audio},
                )
            if document.state.status not in {"queued", "running", "paused"}:
                continue
            synced = self._sync_running_items(document.state.batch_id)
            if synced is None:
                continue
            if synced.state.queued_count == 0 and synced.state.running_count == 0:
                self._finish_batch(synced)
                continue
            if synced.state.status in {"queued", "running"}:
                synced.state.status = "paused"
                synced.state.error = "Batch was interrupted by a previous server shutdown."
                self.batch_store.save_batch(synced)
                self.batch_store.append_event(
                    synced.state.batch_id,
                    "batch_recovered_paused",
                    {"queued_count": synced.state.queued_count},
                )

    @staticmethod
    def _recover_interrupted_audio(document: BatchDocument) -> int:
        recovered = 0
        for item in document.items:
            if item.audio_status in {"queued", "running"}:
                item.audio_status = "failed"
                item.audio_error = "Audio render was interrupted by a previous server shutdown."
                item.updated_at = now_iso()
                recovered += 1
            if item.stem_status in {"queued", "running"}:
                item.stem_status = "failed"
                item.stem_error = "Stem render was interrupted by a previous server shutdown."
                item.updated_at = now_iso()
                recovered += 1
        return recovered

    def launch_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running":
            return document, HTTPStatus.CONFLICT, "Batch is already running.", 0
        if not any(item.status == "queued" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch has no queued items to launch.", 0
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error, 0

        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        started = self._start_available_items(batch_id)
        document = self.batch_store.get_batch(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(batch_id, "batch_launched", {"started_count": started})
        return document, HTTPStatus.ACCEPTED, None, started

    def pause_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status not in {"running", "queued"}:
            return document, HTTPStatus.CONFLICT, "Only a running batch can be paused."
        document.state.status = "paused"
        document.state.error = None
        self.batch_store.save_batch(document)
        self.batch_store.append_event(batch_id, "batch_paused", {})
        return document, HTTPStatus.OK, None

    def resume_batch(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status != "paused":
            return document, HTTPStatus.CONFLICT, "Only a paused batch can be resumed."
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error
        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        self._start_available_items(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(batch_id, "batch_resumed", {})
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None

    def retry_failed(self, batch_id: str) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        if document.state.status == "running":
            return document, HTTPStatus.CONFLICT, "Cannot retry failed items while the batch is running.", 0
        reset_count = 0
        for item in document.items:
            if item.status in {"failed", "cancelled"}:
                item.status = "queued"
                item.error = None
                item.job_id = None
                item.output_dir = None
                item.audio_status = "not_started"
                item.audio_path = None
                item.audio_error = None
                item.stem_status = "not_started"
                item.stem_manifest_path = None
                item.stem_count = 0
                item.stem_audio_completed_count = 0
                item.stem_error = None
                item.updated_at = now_iso()
                reset_count += 1
        if reset_count == 0:
            return document, HTTPStatus.CONFLICT, "Batch has no failed items to retry.", 0
        provider_error = self._provider_readiness_error(document)
        if provider_error is not None:
            return document, HTTPStatus.BAD_REQUEST, provider_error, 0
        document.state.status = "running"
        document.state.error = None
        self.batch_store.save_batch(document)
        started = self._start_available_items(batch_id)
        document = self.batch_store.get_batch(batch_id)
        self._ensure_thread(batch_id)
        self.batch_store.append_event(
            batch_id,
            "batch_retry_failed",
            {"reset_count": reset_count, "started_count": started},
        )
        return document, HTTPStatus.ACCEPTED, None, reset_count

    def render_audio(
        self,
        batch_id: str,
        *,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Cannot render batch audio while batch generation is running.", 0
        if any(item.audio_status in {"queued", "running"} for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch audio render is already running.", 0
        renderer_error = self._renderer_readiness_error()
        if renderer_error is not None:
            return document, HTTPStatus.BAD_REQUEST, renderer_error, 0

        queued_count = 0
        for item in document.items:
            if failed_only and item.audio_status != "failed":
                continue
            if item.status != "completed":
                if not failed_only and item.audio_status == "not_started":
                    item.audio_status = "skipped"
                    item.audio_error = "Batch item is not completed."
                    item.updated_at = now_iso()
                continue
            if not failed_only and item.audio_status == "completed" and item.audio_path:
                continue
            item.audio_status = "queued"
            item.audio_path = None
            item.audio_error = None
            item.updated_at = now_iso()
            queued_count += 1

        if queued_count == 0:
            message = (
                "Batch has no failed audio renders to retry."
                if failed_only
                else "Batch has no completed items that need audio render."
            )
            return document, HTTPStatus.CONFLICT, message, 0

        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            batch_id,
            "batch_audio_render_requested",
            {"queued_count": queued_count, "failed_only": failed_only},
        )
        self._start_available_audio_items(batch_id)
        self._ensure_audio_thread(batch_id)
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None, queued_count

    def render_stems(
        self,
        batch_id: str,
        *,
        audio: bool = False,
        failed_only: bool = False,
    ) -> tuple[BatchDocument | None, HTTPStatus, str | None, int]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return None, HTTPStatus.NOT_FOUND, "Batch not found.", 0
        except ValueError as exc:
            return None, HTTPStatus.BAD_REQUEST, str(exc), 0
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return document, HTTPStatus.CONFLICT, "Cannot render batch stems while batch generation is running.", 0
        if any(item.stem_status in {"queued", "running"} for item in document.items):
            return document, HTTPStatus.CONFLICT, "Batch stem render is already running.", 0
        if audio:
            renderer_error = self._renderer_readiness_error()
            if renderer_error is not None:
                return document, HTTPStatus.BAD_REQUEST, renderer_error, 0

        queued_count = 0
        for item in document.items:
            if failed_only and item.stem_status not in {"failed", "partial_failed"}:
                continue
            if item.status != "completed":
                if not failed_only and item.stem_status == "not_started":
                    item.stem_status = "skipped"
                    item.stem_error = "Batch item is not completed."
                    item.updated_at = now_iso()
                continue
            if (
                not audio
                and not failed_only
                and item.stem_status == "completed"
                and item.stem_manifest_path
            ):
                continue
            if (
                audio
                and item.stem_status == "completed"
                and item.stem_count
                and item.stem_audio_completed_count >= item.stem_count
            ):
                continue
            if audio and not item.stem_manifest_path and item.stem_status not in {"failed", "partial_failed"}:
                continue
            if not audio:
                item.stem_manifest_path = None
                item.stem_count = 0
                item.stem_audio_completed_count = 0
            item.stem_status = "queued"
            item.stem_error = None
            item.updated_at = now_iso()
            queued_count += 1

        if queued_count == 0:
            if failed_only:
                message = "Batch has no failed stem renders to retry."
            elif audio:
                message = "Batch has no completed items that need stem audio render."
            else:
                message = "Batch has no completed items that need stem render."
            return document, HTTPStatus.CONFLICT, message, 0

        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            batch_id,
            "batch_stem_render_requested",
            {"queued_count": queued_count, "audio": audio, "failed_only": failed_only},
        )
        self._start_available_stem_items(batch_id, audio=audio)
        self._ensure_stem_thread(batch_id, audio=audio)
        return self.batch_store.get_batch(batch_id), HTTPStatus.ACCEPTED, None, queued_count

    def delete_batch(self, batch_id: str) -> tuple[bool, HTTPStatus, str | None]:
        try:
            document = self.batch_store.get_batch(batch_id)
        except FileNotFoundError:
            return False, HTTPStatus.NOT_FOUND, "Batch not found."
        if document.state.status == "running" or any(item.status == "running" for item in document.items):
            return False, HTTPStatus.CONFLICT, "Cannot delete a running batch. Pause it first."
        self.batch_store.delete_batch(batch_id)
        return True, HTTPStatus.OK, None

    def shutdown(self) -> None:
        self.stop_event.set()
        with self.lock:
            threads = [*self.threads.values(), *self.audio_threads.values(), *self.stem_threads.values()]
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2)

    def _run_batch(self, batch_id: str) -> None:
        try:
            while not self.stop_event.is_set():
                document = self._sync_running_items(batch_id)
                if document is None:
                    return
                if document.state.status == "paused":
                    if document.state.running_count == 0:
                        return
                    time.sleep(0.1)
                    continue
                if document.state.status != "running":
                    return
                self._start_available_items(batch_id)
                document = self._sync_running_items(batch_id)
                if document is None:
                    return
                if document.state.status == "running" and document.state.queued_count == 0 and document.state.running_count == 0:
                    self._finish_batch(document)
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.threads.pop(batch_id, None)

    def _run_batch_audio(self, batch_id: str) -> None:
        try:
            while not self.stop_event.is_set():
                self._start_available_audio_items(batch_id)
                document = self._sync_audio_items(batch_id)
                if document is None:
                    return
                if not any(item.audio_status in {"queued", "running"} for item in document.items):
                    self.batch_store.append_event(
                        batch_id,
                        "batch_audio_render_finished",
                        self._audio_counts(document),
                    )
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.audio_threads.pop(batch_id, None)

    def _run_batch_stems(self, batch_id: str, audio: bool) -> None:
        try:
            while not self.stop_event.is_set():
                self._start_available_stem_items(batch_id, audio=audio)
                document = self._sync_stem_items(batch_id)
                if document is None:
                    return
                if not any(item.stem_status in {"queued", "running"} for item in document.items):
                    self.batch_store.append_event(
                        batch_id,
                        "batch_stem_render_finished",
                        self._stem_counts(document),
                    )
                    return
                time.sleep(0.1)
        finally:
            with self.lock:
                self.stem_threads.pop(batch_id, None)

    def _ensure_thread(self, batch_id: str) -> None:
        with self.lock:
            existing = self.threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch,
                args=(batch_id,),
                name=f"musicforge-batch-{batch_id}",
                daemon=True,
            )
            self.threads[batch_id] = thread
            thread.start()

    def _ensure_audio_thread(self, batch_id: str) -> None:
        with self.lock:
            existing = self.audio_threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch_audio,
                args=(batch_id,),
                name=f"musicforge-batch-audio-{batch_id}",
                daemon=True,
            )
            self.audio_threads[batch_id] = thread
            thread.start()

    def _ensure_stem_thread(self, batch_id: str, *, audio: bool) -> None:
        with self.lock:
            existing = self.stem_threads.get(batch_id)
            if existing is not None and existing.is_alive():
                return
            thread = threading.Thread(
                target=self._run_batch_stems,
                args=(batch_id, audio),
                name=f"musicforge-batch-stems-{batch_id}",
                daemon=True,
            )
            self.stem_threads[batch_id] = thread
            thread.start()

    def _start_available_items(self, batch_id: str) -> int:
        with self.lock:
            document = self.batch_store.get_batch(batch_id)
            if document.state.status != "running":
                return 0
            running_count = sum(1 for item in document.items if item.status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            for item in document.items:
                if item.status != "queued" or started >= available:
                    continue
                try:
                    job = self.job_store.create_job(item.request, start_immediately=True)
                except Exception as exc:
                    item.status = "failed"
                    item.error = str(exc)
                    item.updated_at = now_iso()
                    document.state.error = str(exc)
                    continue
                item.status = "running"
                item.job_id = job.job_id
                item.output_dir = job.output_dir
                item.error = None
                item.attempt_count += 1
                item.updated_at = now_iso()
                started += 1
                self.batch_store.append_event(
                    batch_id,
                    "batch_item_started",
                    {
                        "item_id": item.item_id,
                        "job_id": job.job_id,
                        "attempt_count": item.attempt_count,
                    },
                )
            self.batch_store.save_batch(document)
            return started

    def _sync_running_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None
            changed = False
            for item in document.items:
                if item.status != "running" or not item.job_id:
                    continue
                job = self.job_store.get_job(item.job_id)
                if job is None:
                    item.status = "failed"
                    item.error = "Linked job is missing."
                    item.updated_at = now_iso()
                    changed = True
                    continue
                if job.output_dir:
                    item.output_dir = job.output_dir
                if job.status == "completed":
                    item.status = "completed"
                    item.error = None
                    item.updated_at = now_iso()
                    changed = True
                    self.batch_store.append_event(
                        batch_id,
                        "batch_item_completed",
                        {
                            "item_id": item.item_id,
                            "job_id": job.job_id,
                            "project_id": item.project_id,
                            "version_id": item.version_id,
                        },
                    )
                elif job.status == "cancelled":
                    item.status = "cancelled"
                    item.error = job.error or "Job was cancelled."
                    item.updated_at = now_iso()
                    changed = True
                elif job.status in {"failed", "interrupted", "stalled"}:
                    item.status = "failed"
                    item.error = job.error or job.last_error or f"Job ended with status {job.status}."
                    item.updated_at = now_iso()
                    changed = True
            if self._archive_completed_project_items(document):
                changed = True
            if changed:
                self.batch_store.save_batch(document)
                document = self.batch_store.get_batch(batch_id)
            return document

    def _archive_completed_project_items(self, document: BatchDocument) -> bool:
        changed = False
        for item in sorted(document.items, key=lambda batch_item: batch_item.index):
            if item.status != "completed" or not item.project:
                continue
            if item.project_id and item.version_id:
                continue
            if self._has_unarchived_prior_project_item(document, item):
                continue
            if not item.job_id:
                continue
            job = self.job_store.get_job(item.job_id)
            if job is None or job.status != "completed":
                continue
            self._archive_item_to_project(document, item, job)
            changed = True
        return changed

    @staticmethod
    def _has_unarchived_prior_project_item(document: BatchDocument, item: Any) -> bool:
        for prior in document.items:
            if prior.index >= item.index or prior.project != item.project:
                continue
            if prior.status in {"queued", "running"}:
                return True
            if prior.status == "completed" and not prior.version_id:
                return True
        return False

    def _archive_item_to_project(self, document: BatchDocument, item: Any, job: JobState) -> None:
        if self.project_store is None or not item.project:
            return
        if item.project_id and item.version_id:
            return
        project = self.project_store.find_or_create_project(item.project)
        item.project_id = project.state.project_id
        try:
            updated = self.project_store.add_version_from_job(
                project.state.project_id,
                job,
                name=item.version_name or "",
                note=item.version_note or "",
            )
        except ValueError as exc:
            if "already attached" not in str(exc):
                raise
            updated = self.project_store.get_project(project.state.project_id)
        version = next((version for version in updated.versions if version.job_id == job.job_id), None)
        if version is not None:
            item.version_id = version.version_id
        self.batch_store.append_event(
            document.state.batch_id,
            "batch_item_archived_to_project",
            {
                "item_id": item.item_id,
                "job_id": job.job_id,
                "project_id": item.project_id,
                "version_id": item.version_id,
            },
        )

    def _start_available_audio_items(self, batch_id: str) -> int:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return 0
            running_count = sum(1 for item in document.items if item.audio_status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            threads_to_start: list[threading.Thread] = []
            for item in document.items:
                if item.audio_status != "queued" or started >= available:
                    continue
                if item.status != "completed" or not item.job_id:
                    item.audio_status = "failed"
                    item.audio_error = "Batch item does not have a completed job."
                    item.updated_at = now_iso()
                    continue
                item.audio_status = "running"
                item.audio_error = None
                item.updated_at = now_iso()
                started += 1
                threads_to_start.append(
                    threading.Thread(
                        target=self._render_audio_item,
                        args=(batch_id, item.item_id, item.job_id),
                        name=f"musicforge-batch-audio-item-{batch_id}-{item.item_id}",
                        daemon=True,
                    )
                )
                self.batch_store.append_event(
                    batch_id,
                    "batch_audio_item_started",
                    {"item_id": item.item_id, "job_id": item.job_id},
                )
            self.batch_store.save_batch(document)
            for thread in threads_to_start:
                thread.start()
            return started

    def _render_audio_item(self, batch_id: str, item_id: str, job_id: str) -> None:
        audio, status, error = self.job_store.render_job_audio(job_id)
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return
            for item in document.items:
                if item.item_id != item_id:
                    continue
                if error is None and status == HTTPStatus.OK:
                    item.audio_status = "completed"
                    item.audio_path = audio.get("audio")
                    item.audio_error = None
                    event_type = "batch_audio_item_completed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "audio": item.audio_path}
                else:
                    item.audio_status = "failed"
                    item.audio_path = None
                    item.audio_error = error or f"Audio render failed with status {status.value}."
                    event_type = "batch_audio_item_failed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "error": item.audio_error}
                item.updated_at = now_iso()
                self.batch_store.save_batch(document)
                self.batch_store.append_event(batch_id, event_type, payload)
                return

    def _start_available_stem_items(self, batch_id: str, *, audio: bool) -> int:
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return 0
            running_count = sum(1 for item in document.items if item.stem_status == "running")
            available = max(0, document.state.max_concurrency - running_count)
            if available == 0:
                return 0
            started = 0
            threads_to_start: list[threading.Thread] = []
            for item in document.items:
                if item.stem_status != "queued" or started >= available:
                    continue
                if item.status != "completed" or not item.job_id:
                    item.stem_status = "failed"
                    item.stem_error = "Batch item does not have a completed job."
                    item.updated_at = now_iso()
                    continue
                item.stem_status = "running"
                item.stem_error = None
                item.updated_at = now_iso()
                started += 1
                threads_to_start.append(
                    threading.Thread(
                        target=self._render_stem_item,
                        args=(batch_id, item.item_id, item.job_id, audio),
                        name=f"musicforge-batch-stem-item-{batch_id}-{item.item_id}",
                        daemon=True,
                    )
                )
                self.batch_store.append_event(
                    batch_id,
                    "batch_stem_item_started",
                    {"item_id": item.item_id, "job_id": item.job_id, "audio": audio},
                )
            self.batch_store.save_batch(document)
            for thread in threads_to_start:
                thread.start()
            return started

    def _render_stem_item(self, batch_id: str, item_id: str, job_id: str, audio: bool) -> None:
        if audio:
            data, status, error = self.job_store.render_job_stem_audio(job_id)
        else:
            data, status, error = self.job_store.render_job_stems(job_id)
        with self.lock:
            try:
                document = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return
            for item in document.items:
                if item.item_id != item_id:
                    continue
                job = self.job_store.get_job(job_id)
                if error is None and status == HTTPStatus.OK:
                    manifest = data.get("manifest", {})
                    stems = manifest.get("stems", [])
                    item.stem_manifest_path = str(Path(job.output_dir) / "stems" / "manifest.json") if job else item.stem_manifest_path
                    item.stem_count = len(stems)
                    item.stem_audio_completed_count = sum(1 for stem in stems if stem.get("audio_status") in {"completed", "skipped"})
                    item.stem_status = data.get("status", "completed")
                    item.stem_error = (
                        "One or more stems failed."
                        if item.stem_status in {"partial_failed", "failed"}
                        else None
                    )
                    event_type = "batch_stem_item_completed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "status": item.stem_status}
                else:
                    item.stem_status = "failed"
                    item.stem_error = error or f"Stem render failed with status {status.value}."
                    event_type = "batch_stem_item_failed"
                    payload = {"item_id": item.item_id, "job_id": job_id, "error": item.stem_error}
                item.updated_at = now_iso()
                self.batch_store.save_batch(document)
                self.batch_store.append_event(batch_id, event_type, payload)
                return

    def _sync_audio_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                return self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None

    def _sync_stem_items(self, batch_id: str) -> BatchDocument | None:
        with self.lock:
            try:
                return self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                return None

    def _finish_batch(self, document: BatchDocument) -> None:
        if document.state.failed_count or document.state.cancelled_count:
            document.state.status = "completed_with_errors"
            document.state.error = "One or more batch items failed."
        else:
            document.state.status = "completed"
            document.state.error = None
        self.batch_store.save_batch(document)
        self.batch_store.append_event(
            document.state.batch_id,
            "batch_finished",
            {"status": document.state.status},
        )

    @staticmethod
    def _provider_readiness_error(document: BatchDocument) -> str | None:
        if not any(
            item.status == "queued" and item.request.get("generation_mode") == "provider"
            for item in document.items
        ):
            return None
        provider_config, _sources = load_provider_config()
        try:
            provider_config.validate_ready_for_provider()
        except ProviderError as exc:
            return str(exc)
        return None

    @staticmethod
    def _renderer_readiness_error() -> str | None:
        config, _sources = load_renderer_config()
        try:
            config.validate_ready_for_render()
        except RendererError as exc:
            return str(exc)
        return None

    @staticmethod
    def _audio_counts(document: BatchDocument) -> dict[str, int]:
        counts = {
            "not_started": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in document.items:
            counts[item.audio_status] = counts.get(item.audio_status, 0) + 1
        return counts

    @staticmethod
    def _stem_counts(document: BatchDocument) -> dict[str, int]:
        counts = {
            "not_started": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "partial_completed": 0,
            "partial_failed": 0,
            "failed": 0,
            "skipped": 0,
        }
        for item in document.items:
            counts[item.stem_status] = counts.get(item.stem_status, 0) + 1
        return counts

def api_info(
    auth_config: AuthConfig | None = None,
    *,
    authorized: bool = True,
) -> dict[str, Any]:
    auth_required = bool(auth_config and auth_config.enabled)
    public_info: dict[str, Any] = {
        "app": "MusicForge",
        "version": __version__,
        "auth_required": auth_required,
    }
    if auth_required and not authorized:
        return public_info
    return {
        **public_info,
        "cwd": str(Path.cwd()),
        "runs_dir": str(RUNS_DIR),
        "mode": "local-deterministic",
        "provider": {"enabled": False, "summary": "Local deterministic composer"},
    }

def api_template() -> dict[str, Any]:
    return {
        "defaults": {
            "title": "Rainy Convenience Store",
            "language": "zh",
            "style": "city pop, soft rock, warm synths, clean electric guitar",
            "theme": "a person remembers an old friend during a rainy night in the city",
            "duration_seconds": 180,
            "vocal_mode": "guide_melody",
            "tempo_bpm": 92,
            "key": "C major",
        },
        "presets": [
            {
                "name": "City Pop 120s",
                "style": "city pop, soft rock, warm synths, clean electric guitar",
                "duration_seconds": 120,
                "tempo_bpm": 92,
                "key": "C major",
            },
            {
                "name": "Lo-fi Loop 60s",
                "style": "lo-fi hip hop, mellow keys, dusty drums",
                "duration_seconds": 60,
                "tempo_bpm": 78,
                "key": "A minor",
            },
            {
                "name": "Game Battle Loop 45s",
                "style": "game battle loop, synth bass, tight drums",
                "duration_seconds": 45,
                "tempo_bpm": 132,
                "key": "D minor",
            },
        ],
    }

def discover_artifacts(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            artifacts.append(
                _artifact_dict(path)
            )
    return artifacts

def open_folder(path: Path) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    webbrowser.open(path.resolve().as_uri())

def _build_summary(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    tracks = plan.get("tracks", [])
    sections = plan.get("sections", [])
    return {
        "title": plan.get("title"),
        "tempo_bpm": plan.get("tempo_bpm"),
        "key": plan.get("key"),
        "meter": plan.get("meter"),
        "section_count": len(sections),
        "track_count": len(tracks),
        "note_count": sum(len(track.get("notes", [])) for track in tracks),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
    }

def _build_validator_report(plan_path: Path, midi_path: Path) -> dict[str, Any]:
    plan = read_json(plan_path)
    return {
        "status": "passed",
        "checks": [
            "song_request_schema",
            "song_plan_schema",
            "song_plan_validation",
            "midi_render",
        ],
        "title": plan.get("title"),
        "midi_path": str(midi_path),
        "midi_exists": midi_path.exists(),
        "midi_size": midi_path.stat().st_size if midi_path.exists() else 0,
        "checked_at": _utc_now(),
    }

def _provider_usage_record(
    *,
    config_snapshot: dict[str, Any],
    operation: str,
    template_id: str,
    started_at: str,
    status: str,
    provider_usage: dict[str, Any] | None = None,
    request_id: Any = None,
) -> dict[str, Any]:
    provider_usage = provider_usage or {}
    prompt_tokens = _usage_int(provider_usage, "prompt_tokens")
    completion_tokens = _usage_int(provider_usage, "completion_tokens")
    total_tokens = _usage_int(provider_usage, "total_tokens") or prompt_tokens + completion_tokens
    return {
        "provider_type": config_snapshot.get("wire_api") or "unknown",
        "model": config_snapshot.get("model") or "",
        "operation": operation,
        "template_id": template_id,
        "started_at": started_at,
        "completed_at": _utc_now() if status != "queued" else None,
        "latency_ms": None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "estimated_cost": None,
        "request_id": None if request_id is None else str(request_id),
        "status": status,
    }

def _try_read_review_decision_report(task_store: ReviewTaskStore, task_id: str) -> dict[str, Any]:
    try:
        return task_store.read_decision_report(task_id)
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}

def _review_sprints_list_summary(sprints: list[dict[str, Any]]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    total_conflicts = 0
    blocking_conflicts = 0
    for sprint in sprints:
        status = str(sprint.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        summary = sprint.get("summary") if isinstance(sprint.get("summary"), dict) else {}
        counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}
        total_conflicts += int(counts.get("conflict_count") or 0)
        blocking_conflicts += int(counts.get("blocking_conflict_count") or 0)
    return sanitize_metadata(
        {
            "total": len(sprints),
            "statuses": statuses,
            "conflict_count": total_conflicts,
            "blocking_conflict_count": blocking_conflicts,
        }
    )

def _select_action_queue_items(queue: SprintActionQueue, selected_ids: list[str], *, rerun_failed: bool = False) -> list[SprintActionItem]:
    selected = set(selected_ids)
    items = []
    for item in queue.items:
        if selected and item.item_id not in selected:
            continue
        if item.status == "pending" or (rerun_failed and item.status == "failed"):
            items.append(item)
    return sorted(items, key=_action_queue_run_sort_key)

def _action_queue_run_sort_key(item: SprintActionItem) -> tuple[int, int, int, str]:
    order = {
        "refresh_conflicts": 0,
        "refresh_recommendations": 1,
        "save_recommended_context_pack": 2,
        "generate_local_candidates": 3,
        "generate_provider_candidates": 4,
        "refresh_decision_report": 5,
    }.get(item.action, 9)
    return (order, int(item.rank or 9999), -int(item.priority or 0), item.item_id)

def _usage_int(usage: dict[str, Any], field_name: str) -> int:
    value = usage.get(field_name)
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0

def _audio_report(audio_path: Path) -> dict[str, Any]:
    return {
        "exists": audio_path.exists(),
        "path": str(audio_path),
        "size_bytes": audio_path.stat().st_size if audio_path.exists() else 0,
    }

def _manifest_response(
    job_id: str,
    manifest: StemManifest,
    *,
    status: str | None = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": status or _stem_manifest_status(manifest),
        "manifest": manifest.to_dict(),
    }

def _stem_midi_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    if all(stem.midi_exists or stem.audio_status == "skipped" for stem in manifest.stems):
        return "completed"
    if any(stem.midi_exists for stem in manifest.stems):
        return "partial_failed"
    return "failed"

def _stem_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    if any(stem.audio_exists for stem in manifest.stems):
        return _stem_audio_manifest_status(manifest)
    if any(stem.midi_exists for stem in manifest.stems):
        return _stem_midi_manifest_status(manifest)
    return "not_started"

def _stem_audio_manifest_status(manifest: StemManifest) -> str:
    if not manifest.stems:
        return "not_started"
    statuses = {stem.audio_status for stem in manifest.stems}
    if statuses <= {"completed", "skipped"}:
        return "completed"
    if "failed" in statuses and ("completed" in statuses or "skipped" in statuses):
        return "partial_failed"
    if "failed" in statuses:
        return "failed"
    if "completed" in statuses:
        return "partial_completed"
    return "not_started"

def _job_artifacts(
    run_dir: Path,
    plan_path: Path,
    midi_path: Path,
    validator_report_path: Path,
) -> dict[str, str]:
    artifacts = {
        "request": str(run_dir / "data" / "request.json"),
        "song_plan": str(plan_path),
        "run_summary": str(run_dir / "data" / "run-summary.json"),
        "validator_report": str(validator_report_path),
        "job_state": str(run_dir / "data" / "job-state.json"),
        "events": str(run_dir / "logs" / "events.jsonl"),
        "midi": str(midi_path),
    }
    provider_snapshot_path = run_dir / "data" / "provider-snapshot.json"
    if provider_snapshot_path.exists():
        artifacts["provider_snapshot"] = str(provider_snapshot_path)
    edit_metadata_path = run_dir / "data" / "edit-metadata.json"
    if edit_metadata_path.exists():
        artifacts["edit_metadata"] = str(edit_metadata_path)
    nodes_dir = run_dir / "data" / "nodes"
    if nodes_dir.exists():
        artifacts["nodes"] = str(nodes_dir)
    return artifacts

def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events

def _read_critic_report(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "data" / "nodes" / "critic.json"
    if not path.exists():
        return None
    try:
        record = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    output = record.get("output")
    return output if isinstance(output, dict) else None

def _read_edit_metadata_for_run(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "data" / "edit-metadata.json"
    if not path.exists():
        return None
    try:
        metadata = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return metadata

def _top_ranked_candidate_id(group: Any) -> str | None:
    if group.ranking:
        return str(group.ranking[0].get("candidate_id") or "") or None
    ready = [candidate for candidate in group.candidates if candidate.status == "ready"]
    if not ready:
        return None
    return max(ready, key=lambda candidate: int(candidate.scores.get("combined") or 0)).candidate_id

def _candidate_source_summary(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    return {
        "candidate_group_id": str(data.get("candidate_group_id") or ""),
        "candidate_id": str(data.get("candidate_id") or ""),
        "rank": _optional_positive_int(data.get("rank")),
        "score": _optional_positive_int(data.get("score")),
        "quality_overall": _optional_positive_int(data.get("quality_overall")),
        "summary": str(data.get("summary") or "")[:240],
        "status": str(data.get("status") or ""),
        "created_at": str(data.get("created_at") or ""),
    }

def _optional_positive_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None

def _prompt_ab_template_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("template_ids must be a list.")
    template_ids = [str(item).strip() for item in value if str(item).strip()]
    if len(template_ids) < 2:
        raise ValueError("Prompt A/B requires at least two template ids.")
    if len(template_ids) > 4:
        raise ValueError("Prompt A/B supports at most four template ids.")
    return template_ids

def _match_job_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/jobs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if "/" in rest:
        job_id, tail = rest.split("/", 1)
        return unquote(job_id), "/" + tail
    return unquote(rest), ""

def _match_batch_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/batches/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "import-csv":
        return None
    if "/" in rest:
        batch_id, tail = rest.split("/", 1)
        return unquote(batch_id), "/" + tail
    return unquote(rest), ""

def _match_project_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/projects/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        project_id, tail = rest.split("/", 1)
        return unquote(project_id), "/" + tail
    return unquote(rest), ""

def _match_release_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/releases/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        release_id, tail = rest.split("/", 1)
        return unquote(release_id), "/" + tail
    return unquote(rest), ""

def _match_acceptance_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/suites/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        suite_id, tail = rest.split("/", 1)
        return unquote(suite_id), "/" + tail
    return unquote(rest), ""

def _match_acceptance_analytics_report_route(path: str) -> str | None:
    prefix = "/api/acceptance/analytics/reports/"
    if not path.startswith(prefix):
        return None
    report_id = unquote(path[len(prefix) :].strip("/"))
    return report_id or None

def _match_acceptance_analytics_recommendation_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/analytics/reports/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 4 and parts[1] == "recommendations" and parts[3] == "create-review-task":
        return parts[0], parts[2]
    return None

def _match_acceptance_kb_report_route(path: str) -> str | None:
    prefix = "/api/acceptance/kb/reports/"
    if not path.startswith(prefix):
        return None
    report_id = unquote(path[len(prefix) :].strip("/"))
    return report_id or None

def _match_acceptance_kb_entry_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/kb/entries/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"hide", "unhide"}:
        return parts[0], parts[1]
    return None

def _match_acceptance_fix_plan_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/fix-plans/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive", "create-fix-sprint", "outcome-review"}:
        return parts[0], parts[1]
    if len(parts) == 3 and parts[1] == "outcome-review" and parts[2] == "refresh":
        return parts[0], "outcome-review/refresh"
    return None

def _match_acceptance_fix_plan_review_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/fix-plan-reviews/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive"}:
        return parts[0], parts[1]
    return None

def _match_planning_ruleset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rulesets/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"clone", "archive", "validate"}:
        return parts[0], parts[1]
    return None

def _match_planning_simulation_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-simulations/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive"}:
        return parts[0], parts[1]
    return None

def _match_planning_rule_governance_version_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rule-governance/versions/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 1:
        return parts[0], ""
    return None

def _match_planning_rule_governance_promotion_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rule-governance/promotions/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"approve", "reject", "promote"}:
        return parts[0], parts[1]
    return None

def _match_planning_rule_impact_report_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/acceptance/planning-rule-impact/reports/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"refresh", "archive"}:
        return parts[0], parts[1]
    return None

def _match_acceptance_fix_sprint_route(path: str) -> tuple[str, list[str]] | None:
    prefix = "/api/acceptance/fix-sprints/"
    if not path.startswith(prefix):
        return None
    parts = [unquote(part) for part in path[len(prefix) :].strip("/").split("/") if part]
    if not parts:
        return None
    return parts[0], parts[1:]

def _analytics_scope_from_query(query_string: str) -> AnalyticsScope:
    query = parse_qs(query_string)
    return AnalyticsScope.from_values(
        scope_type=_query_value(query, "scope") or "global",
        suite_id=_query_value(query, "suite_id") or None,
        release_id=_query_value(query, "release_id") or None,
        project_id=_query_value(query, "project_id") or None,
    )

def _match_distribution_profile_route(path: str) -> str | None:
    prefix = "/api/distribution/profiles/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or "/" in rest:
        return None
    return unquote(rest)

def _match_distribution_template_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/distribution/template-packs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    parts = [unquote(part) for part in rest.split("/") if part]
    if not parts or parts[0] == "import":
        return None
    if len(parts) == 1:
        return parts[0], ""
    if len(parts) == 2 and parts[1] in {"clone", "delete", "export", "validate"}:
        return parts[0], parts[1]
    return None

def _match_distribution_target_tail(tail: str) -> tuple[str, str] | None:
    parts = [part for part in tail.strip("/").split("/") if part]
    if len(parts) < 2 or parts[0] != "targets":
        return None
    target_id = unquote(parts[1])
    if len(parts) == 2:
        return target_id, ""
    if parts[2:] == ["delete"]:
        return target_id, "delete"
    if parts[2:] == ["qa"]:
        return target_id, "qa"
    if parts[2:] == ["qa", "refresh"]:
        return target_id, "qa-refresh"
    if parts[2:] == ["checklist"]:
        return target_id, "checklist"
    if parts[2:] == ["layout"] or parts[2:] == ["layout", "refresh"]:
        return target_id, "layout"
    if len(parts) == 5 and parts[2:4] == ["checklist", "items"]:
        return target_id, "checklist-item:" + unquote(parts[4])
    if parts[2:] == ["export"]:
        return target_id, "export"
    if parts[2:] == ["export", "zip"]:
        return target_id, "export-zip"
    if parts[2:] == ["export.zip"]:
        return target_id, "export-zip-download"
    if parts[2:] == ["verify"]:
        return target_id, "verify"
    if parts[2:] == ["signoff"]:
        return target_id, "signoff"
    if parts[2:] == ["signoff", "reset"]:
        return target_id, "signoff-reset"
    return None

def _match_distribution_artwork_tail(tail: str) -> tuple[str, str] | None:
    parts = [part for part in tail.strip("/").split("/") if part]
    if len(parts) < 2 or parts[0] != "artwork":
        return None
    artwork_id = unquote(parts[1])
    if len(parts) == 2:
        return artwork_id, ""
    if len(parts) == 3 and parts[2] in {"download", "delete"}:
        return artwork_id, parts[2]
    return None

def _match_submission_tail(tail: str) -> tuple[str, str, str | None] | None:
    parts = [unquote(part) for part in tail.strip("/").split("/") if part]
    if not parts:
        return None
    if parts[0] == "batches" and len(parts) >= 2:
        parts = parts[1:]
    submission_id = parts[0]
    if len(parts) == 1:
        return submission_id, "", None
    rest = parts[1:]
    if rest == ["targets"]:
        return submission_id, "targets", None
    if rest == ["refresh"]:
        return submission_id, "refresh", None
    if rest == ["qa"]:
        return submission_id, "qa", None
    if rest == ["qa", "refresh"]:
        return submission_id, "qa-refresh", None
    if rest == ["export"]:
        return submission_id, "export", None
    if rest == ["export", "zip"]:
        return submission_id, "export-zip", None
    if rest == ["export.zip"]:
        return submission_id, "export-zip-download", None
    if rest == ["signoff"]:
        return submission_id, "signoff", None
    if rest == ["signoff", "reset"]:
        return submission_id, "signoff-reset", None
    if rest == ["verify"]:
        return submission_id, "verify", None
    if rest == ["evidence"]:
        return submission_id, "evidence", None
    if rest == ["evidence", "report", "refresh"]:
        return submission_id, "evidence-report-refresh", None
    if rest == ["evidence", "export"]:
        return submission_id, "evidence-export", None
    if rest == ["evidence", "export", "zip"]:
        return submission_id, "evidence-export-zip", None
    if rest == ["evidence", "export.zip"]:
        return submission_id, "evidence-export-zip-download", None
    if rest == ["evidence", "signoff"]:
        return submission_id, "evidence-signoff", None
    if rest == ["evidence", "signoff", "reset"]:
        return submission_id, "evidence-signoff-reset", None
    if rest == ["evidence", "verify"]:
        return submission_id, "evidence-verify", None
    if rest == ["archive"]:
        return submission_id, "archive", None
    if len(rest) == 4 and rest[0] == "items" and rest[2] == "evidence":
        item_id = rest[1]
        action = rest[3]
        if action == "attachments":
            return submission_id, "evidence-upload-attachment", item_id
        if action == "submission-receipt":
            return submission_id, "evidence-submission-receipt", item_id
        if action == "feedback":
            return submission_id, "evidence-feedback", item_id
        if action == "acceptance":
            return submission_id, "evidence-acceptance", item_id
        if action == "resubmission-round":
            return submission_id, "evidence-resubmission-round", item_id
    if len(rest) == 3 and rest[0] == "items":
        item_id = rest[1]
        action = rest[2]
        if action == "remove":
            return submission_id, "remove-item", item_id
        if action == "record-submission":
            return submission_id, "record-submission", item_id
        if action == "record-feedback":
            return submission_id, "record-feedback", item_id
        if action == "accepted":
            return submission_id, "mark-accepted", item_id
    return None

def _match_release_track_tail(tail: str) -> tuple[str, str] | None:
    parts = [part for part in tail.strip("/").split("/") if part]
    if len(parts) != 3 or parts[0] != "tracks":
        return None
    action = parts[2]
    if action not in {"refresh", "remove"}:
        return None
    return unquote(parts[1]), action

def _merge_editor_patch_metadata(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for source in (left, right):
        if not isinstance(source, dict):
            continue
        for key, value in source.items():
            if key in {"clip_inserts", "template_inserts"}:
                continue
            merged[key] = value
    inserts: list[dict[str, Any]] = []
    template_inserts: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_templates: set[str] = set()
    for source in (left, right):
        raw_inserts = source.get("clip_inserts") if isinstance(source, dict) else None
        if not isinstance(raw_inserts, list):
            continue
        for item in raw_inserts:
            if not isinstance(item, dict):
                continue
            group_id = str(item.get("clip_group_id") or "")
            key = group_id or json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            inserts.append(sanitize_metadata(dict(item)))
    if inserts:
        merged["clip_inserts"] = inserts[:20]
    for source in (left, right):
        raw_inserts = source.get("template_inserts") if isinstance(source, dict) else None
        if not isinstance(raw_inserts, list):
            continue
        for item in raw_inserts:
            if not isinstance(item, dict):
                continue
            group_id = str(item.get("template_group_id") or "")
            key = group_id or json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen_templates:
                continue
            seen_templates.add(key)
            template_inserts.append(sanitize_metadata(dict(item)))
    if template_inserts:
        merged["template_inserts"] = template_inserts[:20]
    return sanitize_metadata(merged)

def _match_editor_template_route(path: str) -> tuple[str, str, str] | None:
    prefix = "/api/editor-templates/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    parts = rest.split("/")
    if len(parts) < 2 or parts[0] not in {"sections", "tracks"}:
        return None
    template_id = unquote(parts[1])
    tail = "" if len(parts) == 2 else "/" + "/".join(parts[2:])
    return parts[0], template_id, tail

def _match_edit_preset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/edit-presets/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "reset":
        return None
    if "/" in rest:
        preset_id, tail = rest.split("/", 1)
        return unquote(preset_id), "/" + tail
    return unquote(rest), ""

def _match_prompt_template_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/prompt-templates/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "reset":
        return None
    if "/" in rest:
        template_id, tail = rest.split("/", 1)
        return unquote(template_id), "/" + tail
    return unquote(rest), ""

def _match_asset_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/assets/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest.startswith("extract/"):
        return None
    if "/" in rest:
        asset_id, tail = rest.split("/", 1)
        return unquote(asset_id), "/" + tail
    return unquote(rest), ""

def _match_reference_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/references/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest or rest == "import":
        return None
    if "/" in rest:
        reference_id, tail = rest.split("/", 1)
        return unquote(reference_id), "/" + tail
    return unquote(rest), ""

def _match_context_pack_route(path: str) -> tuple[str, str] | None:
    prefix = "/api/context-packs/"
    if not path.startswith(prefix):
        return None
    rest = path[len(prefix) :]
    if not rest:
        return None
    if "/" in rest:
        pack_id, tail = rest.split("/", 1)
        return unquote(pack_id), "/" + tail
    return unquote(rest), ""

def _match_project_variation_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "variation":
        return unquote(parts[1])
    return None

def _match_project_editor_state_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-state":
        return unquote(parts[1])
    return None

def _match_project_editor_view_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-view":
        return unquote(parts[1])
    return None

def _match_project_editor_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-draft":
        return unquote(parts[1])
    return None

def _match_project_editor_clips_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-clips":
        return unquote(parts[1])
    return None

def _match_project_editor_clip_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-clip-draft":
        return unquote(parts[1])
    return None

def _match_project_section_template_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "section-templates":
        return unquote(parts[1])
    return None

def _match_project_track_template_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "track-templates":
        return unquote(parts[1])
    return None

def _match_project_editor_template_mapping_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-template-mapping":
        return unquote(parts[1])
    return None

def _match_project_editor_multitrack_clip_draft_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-multitrack-clip-draft":
        return unquote(parts[1])
    return None

def _match_project_editor_preview_create_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "editor-preview":
        return unquote(parts[1])
    return None

def _match_project_version_audio_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] in {"audio", "render-audio"}:
        return unquote(parts[1]), parts[2]
    return None

def _match_project_mix_tail(tail: str) -> tuple[str, str, str | None] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "mix-state":
        return unquote(parts[1]), "mix-state", None
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-state" and parts[3] == "reset":
        return unquote(parts[1]), "mix-state-reset", None
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "mix-preview":
        return unquote(parts[1]), "mix-preview-create", None
    if len(parts) == 5 and parts[0] == "versions" and parts[2] == "mix-preview":
        action = parts[4]
        if action in {"midi", "audio", "render-audio", "apply", "delete"}:
            return unquote(parts[1]), f"mix-preview-{action}", unquote(parts[3])
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-previews":
        return unquote(parts[1]), "mix-preview-detail", unquote(parts[3])
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-stems" and parts[3] == "render":
        return unquote(parts[1]), "mix-stems-render", None
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "mix-stems" and parts[3] == "health":
        return unquote(parts[1]), "mix-stems-health", None
    return None

def _match_project_editor_preview_root_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 1 and parts[0] == "editor-previews":
        return "list"
    if len(parts) == 2 and parts[0] == "editor-previews" and parts[1] == "cleanup":
        return "cleanup"
    return None

def _match_project_editor_auditions_root_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] == "auditions":
        return unquote(parts[1])
    return None

def _match_project_editor_audition_reviews_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] == "audition-reviews":
        return unquote(parts[1])
    return None

def _match_project_editor_audition_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 4 and parts[0] == "editor-previews" and parts[2] == "auditions":
        return unquote(parts[1]), unquote(parts[3]), "detail"
    if len(parts) == 5 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] in {
        "midi",
        "audio",
        "render-audio",
        "review",
        "markers",
        "create-asset",
        "review-edit-preview",
        "review-edit",
        "provider-review-edit-preview",
        "create-context-pack",
        "review-task",
        "delete",
    }:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_editor_audition_marker_tail(tail: str) -> tuple[str, str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 6 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] == "markers":
        return unquote(parts[1]), unquote(parts[3]), unquote(parts[5]), "update"
    if len(parts) == 7 and parts[0] == "editor-previews" and parts[2] == "auditions" and parts[4] == "markers" and parts[6] == "delete":
        return unquote(parts[1]), unquote(parts[3]), unquote(parts[5]), "delete"
    return None

def _match_project_editor_preview_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "editor-previews":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "editor-previews" and parts[2] in {"patch", "song-plan", "midi", "audio", "render-audio", "delete", "apply"}:
        return unquote(parts[1]), parts[2]
    return None

def _match_project_edit_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] in {"edit", "edit-targets"}:
        return unquote(parts[1]), parts[2]
    return None

def _match_project_edit_preview_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "edit-preview":
        return unquote(parts[1]), "", "create"
    if len(parts) == 5 and parts[0] == "versions" and parts[2] == "edit-preview" and parts[4] in {"apply", "delete"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_edit_candidates_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "edit-candidates":
        return unquote(parts[1]), "create"
    if len(parts) == 4 and parts[0] == "versions" and parts[2] == "edit-candidates" and parts[3] == "ab":
        return unquote(parts[1]), "ab"
    return None

def _match_project_candidate_group_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "candidate-groups":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] in {"apply", "delete"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] in {"render-midi", "render-audio"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 3 and parts[0] == "candidate-groups" and parts[2] == "usage":
        return unquote(parts[1]), "usage"
    return None

def _match_project_candidate_artifact_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 5 and parts[0] == "candidate-groups" and parts[2] == "candidates" and parts[4] in {"midi", "audio", "render-midi", "render-audio"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_review_task_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "review-tasks":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "review-tasks" and parts[2] in {"candidates", "provider-candidates", "decision-report", "judge-report", "resolve", "needs-more-work", "archive"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 4 and parts[0] == "review-tasks" and parts[2] == "decision-report" and parts[3] == "refresh":
        return unquote(parts[1]), "decision-report-refresh"
    if len(parts) == 4 and parts[0] == "review-tasks" and parts[2] == "judge-report" and parts[3] == "refresh":
        return unquote(parts[1]), "judge-report-refresh"
    return None

def _match_project_review_sprint_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "review-sprints":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "review-sprints" and parts[2] in {"refresh", "close", "archive", "tasks", "generate-local-candidates", "generate-provider-candidates", "conflicts", "recommendations", "metrics", "judge-summary", "closeout", "signoff"}:
        return unquote(parts[1]), parts[2]
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "tasks" and parts[3] in {"remove", "reorder"}:
        return unquote(parts[1]), f"tasks-{parts[3]}"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "conflicts" and parts[3] == "refresh":
        return unquote(parts[1]), "conflicts-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "recommendations" and parts[3] == "refresh":
        return unquote(parts[1]), "recommendations-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "metrics" and parts[3] == "refresh":
        return unquote(parts[1]), "metrics-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "judge-summary" and parts[3] == "refresh":
        return unquote(parts[1]), "judge-summary-refresh"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "closeout" and parts[3] == "refresh":
        return unquote(parts[1]), "closeout-refresh"
    if len(parts) == 5 and parts[0] == "review-sprints" and parts[2] == "recommendations" and parts[4] == "context-pack":
        return unquote(parts[1]), f"recommendation-context-pack:{unquote(parts[3])}"
    if len(parts) == 3 and parts[0] == "review-sprints" and parts[2] == "action-queues":
        return unquote(parts[1]), "action-queues"
    if len(parts) == 4 and parts[0] == "review-sprints" and parts[2] == "action-queues":
        return unquote(parts[1]), f"action-queue:{unquote(parts[3])}:detail"
    if len(parts) == 5 and parts[0] == "review-sprints" and parts[2] == "action-queues" and parts[4] in {"run", "archive"}:
        return unquote(parts[1]), f"action-queue:{unquote(parts[3])}:{parts[4]}"
    return None

def _recommendation_action_for_task(report: dict[str, Any], task_id: str) -> dict[str, Any]:
    actions = report.get("recommended_actions") if isinstance(report, dict) else []
    for action in actions if isinstance(actions, list) else []:
        if isinstance(action, dict) and action.get("task_id") == task_id:
            return action
    return {}

def _context_ref_count(preview: Any) -> int:
    if not isinstance(preview, dict):
        return 0
    return len(preview.get("asset_refs") or []) + len(preview.get("reference_refs") or [])

def _match_project_review_task_candidate_tail(tail: str) -> tuple[str, str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 5 and parts[0] == "review-tasks" and parts[2] == "candidates" and parts[4] in {"midi", "audio", "render-midi", "render-audio", "apply"}:
        return unquote(parts[1]), unquote(parts[3]), parts[4]
    return None

def _match_project_prompt_ab_tail(tail: str) -> tuple[str, str] | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 1 and parts[0] == "prompt-ab":
        return "", "list"
    if len(parts) == 2 and parts[0] == "prompt-ab":
        return unquote(parts[1]), "detail"
    if len(parts) == 3 and parts[0] == "prompt-ab" and parts[2] == "delete":
        return unquote(parts[1]), "delete"
    return None

def _match_project_evaluate_tail(tail: str) -> str | None:
    parts = tail.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "versions" and parts[2] == "evaluate":
        return unquote(parts[1])
    return None

VARIATION_REQUEST_FIELDS = {
    "title",
    "language",
    "style",
    "theme",
    "duration_seconds",
    "vocal_mode",
    "tempo_bpm",
    "key",
    "lyrics",
    "generation_mode",
    "pipeline_mode",
}

def _variation_request_payload(
    parent_request: dict[str, Any],
    request_patch: dict[str, Any],
    *,
    generation_mode: Any = None,
    pipeline_mode: Any = None,
) -> dict[str, Any]:
    unknown = sorted(set(request_patch) - VARIATION_REQUEST_FIELDS)
    if unknown:
        raise ValueError(f"request_patch contains unsupported fields: {', '.join(unknown)}.")
    payload = {key: value for key, value in parent_request.items() if key in VARIATION_REQUEST_FIELDS}
    payload.update(request_patch)
    if generation_mode is not None:
        payload["generation_mode"] = generation_mode
    if pipeline_mode is not None:
        payload["pipeline_mode"] = pipeline_mode
    SongRequest.from_dict(payload)
    _generation_mode(payload)
    _pipeline_mode(payload)
    return payload

def _query_value(query: dict[str, list[str]], name: str) -> str:
    return str(query.get(name, [""])[0] or "").strip()

def _project_matches_filters(
    document: Any,
    *,
    q: str,
    status: str,
    variant_type: str,
    hidden: str,
) -> bool:
    if hidden == "true" and not document.state.hidden:
        return False
    if hidden == "false" and document.state.hidden:
        return False
    if status:
        if status == "selected" and not document.state.selected_version_id:
            return False
        elif status == "final" and not document.state.final_version_id:
            return False
        elif status == "gate_failed" and not any(version.quality_gate_status == "failed" for version in document.versions):
            return False
        elif status not in {"selected", "final", "gate_failed"} and document.state.status != status:
            return False
    if variant_type and not any(version.variant_type == variant_type for version in document.versions):
        return False
    if q:
        needle = q.lower()
        haystack = " ".join(
            [
                document.state.name,
                document.state.description,
                " ".join(document.state.tags),
                *[version.name for version in document.versions],
                *[version.note for version in document.versions],
            ]
        ).lower()
        if needle not in haystack:
            return False
    return True

def _artifact_kind(path: Path) -> str:
    if path.suffix == ".json":
        return "json"
    if path.suffix == ".jsonl":
        return "events"
    if path.suffix == ".mid":
        return "midi"
    if path.suffix == ".wav":
        return "audio"
    return "file"

def _artifact_dict(path: Path) -> dict[str, Any]:
    return {
        "name": path.name,
        "path": str(path),
        "kind": _artifact_kind(path),
        "size": path.stat().st_size,
        "size_bytes": path.stat().st_size,
    }

def _content_disposition_filename(filename: str) -> str:
    ascii_name = _safe_download_filename(filename)
    utf8_name = "".join(char for char in str(filename) if ord(char) >= 32 and char not in {'"', "\r", "\n"})
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{_rfc5987_quote(utf8_name)}"

def _safe_download_filename(filename: str) -> str:
    name = Path(str(filename or "download")).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    cleaned = cleaned.strip(" ._")
    if not cleaned:
        cleaned = "download"
    if len(cleaned) > 120:
        suffix = Path(cleaned).suffix[:16]
        stem = Path(cleaned).stem[: max(1, 120 - len(suffix))]
        cleaned = f"{stem}{suffix}"
    return cleaned

def _rfc5987_quote(value: str) -> str:
    allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$&+-.^_`|~"
    return "".join(char if char in allowed else f"%{byte:02X}" for char in value for byte in char.encode("utf-8"))

def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def _server_file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_read_release_export_manifest(release_store: ReleaseStore, release_id: str) -> dict[str, Any]:
    try:
        return read_release_export_manifest(release_store, release_id)
    except FileNotFoundError:
        return {}

def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("tags must be a list.")
    return [str(item).strip() for item in value if str(item).strip()]

def _clean_title(value: Any) -> str:
    return str(value or "").strip()

def _generation_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("generation_mode", "local") or "local")
    if mode not in {"local", "provider"}:
        raise ValueError("generation_mode must be either local or provider.")
    return mode

def _pipeline_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("pipeline_mode", "single") or "single")
    if mode not in {"single", "multinode"}:
        raise ValueError("pipeline_mode must be either single or multinode.")
    return mode

def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed

def _start_watchdog(store: JobStore, stop_event: threading.Event) -> threading.Thread:
    def run() -> None:
        while not stop_event.wait(5):
            store.run_watchdog_tick()

    thread = threading.Thread(target=run, name="musicforge-watchdog", daemon=True)
    thread.start()
    return thread

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

__all__ = [name for name in globals() if not name.startswith('__')]
