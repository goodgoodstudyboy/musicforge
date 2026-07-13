from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from .runtime import *
from .router import api_inventory, configure_route_registry
from .routes.creation import CreationRoutes
from .routes.studio import StudioRoutes
from .routes.quality import QualityRoutes
from .routes.delivery import DeliveryRoutes
from .routes.trust import TrustRoutes
from .routes.program import ProgramRoutes
from .routes.maintenance import MaintenanceRoutes


class MusicForgeHandler(CreationRoutes, StudioRoutes, QualityRoutes, DeliveryRoutes, TrustRoutes, ProgramRoutes, MaintenanceRoutes, BaseHTTPRequestHandler):
    server_version = "MusicForgeHTTP/0.1"


MusicForgeHandler.route_registry = configure_route_registry(MusicForgeHandler._handle_request)


class MusicForgeHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        auth_config: AuthConfig | None = None,
    ) -> None:
        super().__init__(server_address, MusicForgeHandler)
        self.auth_config = auth_config or AuthConfig(enabled=False)
        self.asset_store = AssetStore()
        self.reference_store = ReferenceStore()
        self.library_index_store = LibraryIndexStore()
        self.context_pack_store = ContextPackStore()
        self.job_store = JobStore(asset_store=self.asset_store, reference_store=self.reference_store, context_pack_store=self.context_pack_store)
        self.batch_store = BatchStore()
        self.project_store = ProjectStore()
        self.release_store = ReleaseStore(project_store=self.project_store)
        self.audio_review_store = AudioReviewEvidenceStore(self.release_store, self.project_store)
        self.audio_revision_store = AudioRevisionStore(self.release_store, project_store=self.project_store, job_store=self.job_store, audio_review_store=self.audio_review_store)
        self.audio_lab_store = AudioLabStore()
        self.audio_fix_sprint_store = AudioFixSprintStore(audio_lab_store=self.audio_lab_store)
        self.audio_campaign_store = AudioCampaignStore(audio_lab_store=self.audio_lab_store, audio_fix_sprint_store=self.audio_fix_sprint_store)
        self.audio_campaign_governance_store = AudioCampaignGovernanceStore(campaign_store=self.audio_campaign_store)
        self.audio_campaign_planner_store = AudioCampaignPlannerStore(release_store=self.release_store, project_store=self.project_store, audio_lab_store=self.audio_lab_store, audio_campaign_store=self.audio_campaign_store)
        self.audio_campaign_remediation_store = AudioCampaignRemediationStore(release_store=self.release_store, project_store=self.project_store, planner_store=self.audio_campaign_planner_store, campaign_store=self.audio_campaign_store, fix_sprint_store=self.audio_fix_sprint_store)
        self.release_audio_certification_store = ReleaseAudioCertificationStore(release_store=self.release_store, project_store=self.project_store, planner_store=self.audio_campaign_planner_store, campaign_store=self.audio_campaign_store, governance_store=self.audio_campaign_governance_store, remediation_store=self.audio_campaign_remediation_store)
        self.release_audio_timeline_store = ReleaseAudioTimelineStore(release_store=self.release_store, project_store=self.project_store, planner_store=self.audio_campaign_planner_store, campaign_store=self.audio_campaign_store, governance_store=self.audio_campaign_governance_store, remediation_store=self.audio_campaign_remediation_store, certification_store=self.release_audio_certification_store)
        self.release_audio_regression_store = ReleaseAudioRegressionStore(release_store=self.release_store, certification_store=self.release_audio_certification_store, timeline_store=self.release_audio_timeline_store)
        self.release_audio_baseline_governance_store = ReleaseAudioBaselineGovernanceStore(release_store=self.release_store)
        self.release_audio_regression_response_store = ReleaseAudioRegressionResponseStore(release_store=self.release_store, regression_store=self.release_audio_regression_store)
        self.release_audio_quality_observatory_store = ReleaseAudioQualityObservatoryStore(release_store=self.release_store)
        self.release_audio_quality_action_queue_store = ReleaseAudioQualityActionQueueStore(release_store=self.release_store, observatory_store=self.release_audio_quality_observatory_store)
        self.release_audio_quality_action_signoff_store = ReleaseAudioQualityActionQueueSignoffStore(queue_store=self.release_audio_quality_action_queue_store, release_store=self.release_store)
        self.release_audio_command_center_store = ReleaseAudioCommandCenterStore(release_store=self.release_store, observatory_store=self.release_audio_quality_observatory_store, action_queue_store=self.release_audio_quality_action_queue_store, action_signoff_store=self.release_audio_quality_action_signoff_store)
        self.unified_command_center_store = UnifiedCommandCenterStore(release_store=self.release_store)
        self.unified_command_center_signoff_store = UnifiedCommandCenterSignoffStore(self.unified_command_center_store)
        self.unified_command_center_handoff_store = UnifiedCommandCenterHandoffStore(self.unified_command_center_signoff_store)
        self.unified_command_center_continuous_review_store = UnifiedCommandCenterContinuousReviewStore(self.unified_command_center_store, signoff_store=self.unified_command_center_signoff_store, handoff_store=self.unified_command_center_handoff_store)
        self.unified_command_center_drift_response_store = UnifiedCommandCenterDriftResponseStore(self.unified_command_center_store, signoff_store=self.unified_command_center_signoff_store, handoff_store=self.unified_command_center_handoff_store, review_store=self.unified_command_center_continuous_review_store)
        self.unified_command_center_evidence_review_store = UnifiedCommandCenterEvidenceReviewStore(self.unified_command_center_store, signoff_store=self.unified_command_center_signoff_store, handoff_store=self.unified_command_center_handoff_store, review_store=self.unified_command_center_continuous_review_store, drift_response_store=self.unified_command_center_drift_response_store)
        self.unified_command_center_reviewer_decision_board_store = UnifiedCommandCenterReviewerDecisionBoardStore(self.unified_command_center_store, evidence_review_store=self.unified_command_center_evidence_review_store)
        self.unified_command_center_release_train_store = UnifiedCommandCenterReleaseTrainStore(release_store=self.release_store)
        self.unified_command_center_release_train_change_control_store = UnifiedCommandCenterReleaseTrainChangeControlStore(self.unified_command_center_release_train_store)
        self.unified_command_center_release_train_lifecycle_store = UnifiedCommandCenterReleaseTrainLifecycleStore(self.unified_command_center_release_train_store, self.unified_command_center_release_train_change_control_store)
        self.unified_command_center_release_train_handoff_store = UnifiedCommandCenterReleaseTrainHandoffStore(self.unified_command_center_release_train_store, self.unified_command_center_release_train_change_control_store, self.unified_command_center_release_train_lifecycle_store)
        self.unified_release_program_store = UnifiedReleaseProgramStore(release_store=self.release_store)
        self.unified_release_program_operations_store = UnifiedReleaseProgramOperationsStore(self.unified_release_program_store)
        self.unified_release_program_handoff_store = UnifiedReleaseProgramHandoffStore(self.unified_release_program_store)
        self.unified_release_program_vault_store = UnifiedReleaseProgramVaultStore(self.unified_release_program_store)
        self.unified_release_program_vault_operations_store = UnifiedReleaseProgramVaultOperationsStore(self.unified_release_program_store)
        self.unified_release_program_continuity_store = UnifiedReleaseProgramContinuityStore(self.unified_release_program_store)
        self.unified_release_program_continuity_distribution_store = UnifiedReleaseProgramContinuityDistributionStore(self.unified_release_program_store)
        self.unified_release_program_continuity_acceptance_store = UnifiedReleaseProgramContinuityAcceptanceStore(self.unified_release_program_store)
        self.unified_release_program_continuity_acceptance_change_store = UnifiedReleaseProgramContinuityAcceptanceChangeStore(self.unified_release_program_store)
        self.unified_release_program_continuity_command_center_store = UnifiedReleaseProgramContinuityCommandCenterStore(self.unified_release_program_store)
        self.unified_release_program_continuity_command_center_signoff_store = UnifiedReleaseProgramContinuityCommandCenterSignoffStore(self.unified_release_program_store)
        self.unified_release_program_continuity_command_center_acceptance_store = UnifiedReleaseProgramContinuityCommandCenterAcceptanceStore(self.unified_release_program_store)
        self.unified_release_program_continuity_command_center_acceptance_change_store = UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStore(self.unified_release_program_store)
        self.distribution_store = DistributionStore(self.release_store)
        self.submission_store = SubmissionStore(self.release_store, self.distribution_store)
        self.submission_evidence_store = SubmissionEvidenceStore(self.submission_store)
        self.acceptance_store = AcceptanceStore(project_store=self.project_store)
        self.human_review_pack_store = HumanReviewPackStore(self.acceptance_store, project_store=self.project_store)
        self.acceptance_analytics_store = AcceptanceAnalyticsStore(acceptance_store=self.acceptance_store, project_store=self.project_store, release_store=self.release_store)
        self.acceptance_fix_sprint_store = AcceptanceFixSprintStore(acceptance_store=self.acceptance_store, analytics_store=self.acceptance_analytics_store, project_store=self.project_store)
        self.acceptance_kb_store = AcceptanceKnowledgeBaseStore(fix_sprint_store=self.acceptance_fix_sprint_store, project_store=self.project_store)
        self.acceptance_fix_plan_store = AcceptanceFixPlanningStore(analytics_store=self.acceptance_analytics_store, kb_store=self.acceptance_kb_store, fix_sprint_store=self.acceptance_fix_sprint_store, project_store=self.project_store)
        self.acceptance_fix_plan_review_store = AcceptanceFixPlanReviewStore(plan_store=self.acceptance_fix_plan_store, fix_sprint_store=self.acceptance_fix_sprint_store, kb_store=self.acceptance_kb_store, project_store=self.project_store)
        self.planning_rule_simulation_store = PlanningRuleSimulationStore(review_store=self.acceptance_fix_plan_review_store, project_store=self.project_store)
        self.planning_rule_governance_store = PlanningRuleGovernanceStore(simulation_store=self.planning_rule_simulation_store, project_store=self.project_store)
        self.acceptance_fix_plan_store.planning_rule_governance_store = self.planning_rule_governance_store
        self.planning_rule_impact_store = PlanningRuleImpactStore(governance_store=self.planning_rule_governance_store, plan_store=self.acceptance_fix_plan_store, review_store=self.acceptance_fix_plan_review_store, project_store=self.project_store)
        self.audio_profile_store = AudioProfileStore(self.release_store.root.parent / "audio-profiles")
        self.mastering_profile_store = MasteringProfileStore(self.release_store.root.parent / "mastering-profiles")
        self.mastering_store = MasteringStore(self.release_store, project_store=self.project_store, profile_store=self.mastering_profile_store)
        self.audio_encoding_profile_store = AudioEncodingProfileStore(self.release_store.root.parent / "audio-encoding-profiles")
        self.audio_encoding_store = AudioEncodingStore(self.release_store, project_store=self.project_store, profile_store=self.audio_encoding_profile_store)
        self.encoded_audio_acceptance_store = EncodedAudioAcceptanceStore(self.release_store, project_store=self.project_store, audio_encoding_store=self.audio_encoding_store)
        self.format_decision_store = FormatDecisionStore(self.release_store, project_store=self.project_store, encoding_store=self.audio_encoding_store, distribution_store=self.distribution_store)
        self.rights_clearance_store = RightsClearanceStore(
            self.release_store,
            asset_store=self.asset_store,
            reference_store=self.reference_store,
            context_pack_store=self.context_pack_store,
        )
        self.release_operations_store = ReleaseOperationsStore(
            release_store=self.release_store,
            project_store=self.project_store,
            distribution_store=self.distribution_store,
            submission_store=self.submission_store,
            submission_evidence_store=self.submission_evidence_store,
            audio_review_store=self.audio_review_store,
            mastering_store=self.mastering_store,
            audio_encoding_store=self.audio_encoding_store,
            encoded_audio_acceptance_store=self.encoded_audio_acceptance_store,
            format_decision_store=self.format_decision_store,
            rights_clearance_store=self.rights_clearance_store,
        )
        self.release_operations_runbook_store = ReleaseOperationsRunbookStore(
            operations_store=self.release_operations_store,
            release_store=self.release_store,
            distribution_store=self.distribution_store,
            submission_store=self.submission_store,
            submission_evidence_store=self.submission_evidence_store,
        )
        self.release_operations_signoff_store = ReleaseOperationsSignoffStore(
            operations_store=self.release_operations_store,
            runbook_store=self.release_operations_runbook_store,
            release_store=self.release_store,
        )
        self.release_operations_audit_store = ReleaseOperationsAuditStore(
            operations_store=self.release_operations_store,
            runbook_store=self.release_operations_runbook_store,
            signoff_store=self.release_operations_signoff_store,
            release_store=self.release_store,
        )
        self.release_operations_reviewer_pack_store = ReleaseOperationsReviewerPackStore(
            audit_store=self.release_operations_audit_store,
            signoff_store=self.release_operations_signoff_store,
            release_store=self.release_store,
        )
        self.release_portfolio_audit_store = ReleasePortfolioAuditStore(
            release_store=self.release_store,
            operations_store=self.release_operations_store,
            runbook_store=self.release_operations_runbook_store,
            signoff_store=self.release_operations_signoff_store,
            audit_store=self.release_operations_audit_store,
            reviewer_pack_store=self.release_operations_reviewer_pack_store,
        )
        self.release_portfolio_governance_store = ReleasePortfolioGovernanceStore(
            portfolio_store=self.release_portfolio_audit_store,
            reviewer_pack_store=self.release_operations_reviewer_pack_store,
            audit_store=self.release_operations_audit_store,
            signoff_store=self.release_operations_signoff_store,
        )
        self.release_portfolio_governance_signoff_store = ReleasePortfolioGovernanceSignoffStore(
            governance_store=self.release_portfolio_governance_store,
        )
        self.release_portfolio_governance_audit_store = ReleasePortfolioGovernanceAuditStore(
            portfolio_store=self.release_portfolio_audit_store,
            governance_store=self.release_portfolio_governance_store,
            signoff_store=self.release_portfolio_governance_signoff_store,
        )
        self.release_portfolio_governance_reviewer_pack_store = ReleasePortfolioGovernanceReviewerPackStore(
            audit_store=self.release_portfolio_governance_audit_store,
        )
        self.release_portfolio_governance_final_board_store = ReleasePortfolioGovernanceFinalBoardStore(
            portfolio_store=self.release_portfolio_audit_store,
            audit_store=self.release_portfolio_governance_audit_store,
            reviewer_pack_store=self.release_portfolio_governance_reviewer_pack_store,
        )
        self.release_portfolio_governance_evidence_vault_store = ReleasePortfolioGovernanceEvidenceVaultStore(
            portfolio_store=self.release_portfolio_audit_store,
            governance_store=self.release_portfolio_governance_store,
            signoff_store=self.release_portfolio_governance_signoff_store,
            audit_store=self.release_portfolio_governance_audit_store,
            reviewer_pack_store=self.release_portfolio_governance_reviewer_pack_store,
            final_board_store=self.release_portfolio_governance_final_board_store,
        )
        self.release_portfolio_governance_attestation_store = ReleasePortfolioGovernanceAttestationStore(
            portfolio_store=self.release_portfolio_audit_store,
            final_board_store=self.release_portfolio_governance_final_board_store,
            evidence_vault_store=self.release_portfolio_governance_evidence_vault_store,
        )
        self.release_portfolio_governance_attestation_registry_store = ReleasePortfolioGovernanceAttestationRegistryStore(
            attestation_store=self.release_portfolio_governance_attestation_store,
        )
        self.release_portfolio_governance_attestation_portal_store = ReleasePortfolioGovernanceAttestationPortalStore(
            registry_store=self.release_portfolio_governance_attestation_registry_store,
            attestation_store=self.release_portfolio_governance_attestation_store,
        )
        self.release_portfolio_governance_attestation_portal_review_store = ReleasePortfolioGovernanceAttestationPortalReviewStore(
            portal_store=self.release_portfolio_governance_attestation_portal_store,
        )
        self.release_portfolio_governance_attestation_accepted_evidence_store = ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore(
            review_store=self.release_portfolio_governance_attestation_portal_review_store,
        )
        self.release_portfolio_governance_attestation_transparency_store = ReleasePortfolioGovernanceAttestationTransparencyStore(
            attestation_store=self.release_portfolio_governance_attestation_store,
            registry_store=self.release_portfolio_governance_attestation_registry_store,
            portal_store=self.release_portfolio_governance_attestation_portal_store,
            accepted_evidence_store=self.release_portfolio_governance_attestation_accepted_evidence_store,
        )
        self.release_portfolio_governance_attestation_transparency_acknowledgement_store = ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore(
            transparency_store=self.release_portfolio_governance_attestation_transparency_store,
        )
        self.public_trust_center_store = PublicTrustCenterStore(
            release_store=self.release_store,
            portfolio_store=self.release_portfolio_audit_store,
            registry_store=self.release_portfolio_governance_attestation_registry_store,
            portal_store=self.release_portfolio_governance_attestation_portal_store,
            transparency_store=self.release_portfolio_governance_attestation_transparency_store,
            acknowledgement_store=self.release_portfolio_governance_attestation_transparency_acknowledgement_store,
            distribution_store=self.distribution_store,
            submission_store=self.submission_store,
            submission_evidence_store=self.submission_evidence_store,
            operations_store=self.release_operations_store,
            operations_runbook_store=self.release_operations_runbook_store,
            operations_signoff_store=self.release_operations_signoff_store,
            operations_audit_store=self.release_operations_audit_store,
            operations_reviewer_pack_store=self.release_operations_reviewer_pack_store,
        )
        self.public_trust_center_anchor_registry_store = PublicTrustCenterAnchorRegistryStore(
            trust_center_store=self.public_trust_center_store,
        )
        self.public_trust_center_anchor_transparency_store = PublicTrustCenterAnchorTransparencyStore(
            anchor_registry_store=self.public_trust_center_anchor_registry_store,
        )
        self.public_trust_center_distribution_kit_store = PublicTrustCenterDistributionKitStore(
            trust_center_store=self.public_trust_center_store,
            anchor_registry_store=self.public_trust_center_anchor_registry_store,
            anchor_transparency_store=self.public_trust_center_anchor_transparency_store,
        )
        self.public_trust_center_distribution_kit_acceptance_store = PublicTrustCenterDistributionKitAcceptanceStore(
            distribution_kit_store=self.public_trust_center_distribution_kit_store,
        )
        self.public_trust_center_acceptance_board_store = PublicTrustCenterAcceptanceBoardStore(
            acceptance_store=self.public_trust_center_distribution_kit_acceptance_store,
        )
        self.trust_operations_hub_store = TrustOperationsHubStore(self.release_store.root.parent / "trust-operations")
        self.trust_operations_incident_store = TrustOperationsIncidentStore(
            self.release_store.root.parent / "trust-operations-incidents",
            hub_store=self.trust_operations_hub_store,
        )
        self.trust_operations_incident_knowledge_store = TrustOperationsIncidentKnowledgeStore(
            self.release_store.root.parent / "trust-operations-knowledge",
            hub_store=self.trust_operations_hub_store,
            incident_store=self.trust_operations_incident_store,
        )
        self.trust_operations_control_store = TrustOperationsControlStore(
            self.release_store.root.parent / "trust-operations-controls",
            hub_store=self.trust_operations_hub_store,
            incident_store=self.trust_operations_incident_store,
            knowledge_store=self.trust_operations_incident_knowledge_store,
        )
        self.trust_operations_control_signoff_store = TrustOperationsControlSignoffStore(
            self.release_store.root.parent / "trust-operations-control-signoffs",
            control_store=self.trust_operations_control_store,
            hub_store=self.trust_operations_hub_store,
            incident_store=self.trust_operations_incident_store,
            knowledge_store=self.trust_operations_incident_knowledge_store,
        )
        self.trust_operations_assurance_store = TrustOperationsAssuranceStore(
            self.release_store.root.parent / "trust-operations-assurance",
            hub_store=self.trust_operations_hub_store,
        )
        self.trust_operations_assurance_watch_store = TrustOperationsAssuranceWatchStore(
            self.release_store.root.parent / "trust-operations-assurance-watch",
            assurance_store=self.trust_operations_assurance_store,
            hub_store=self.trust_operations_hub_store,
        )
        self.trust_operations_assurance_watch_signoff_store = TrustOperationsAssuranceWatchSignoffStore(
            self.release_store.root.parent / "trust-operations-assurance-watch-signoffs",
            watch_store=self.trust_operations_assurance_watch_store,
            assurance_store=self.trust_operations_assurance_store,
            hub_store=self.trust_operations_hub_store,
        )
        self.trust_operations_final_readiness_store = TrustOperationsFinalReadinessStore(
            self.release_store.root.parent / "trust-operations-final-readiness",
        )
        self.distribution_template_store = TemplatePackStore(self.release_store.root.parent / "distribution-templates")
        self.edit_preset_store = EditPresetStore()
        self.prompt_template_store = PromptTemplateStore()
        self.editor_template_store = EditorTemplateStore()
        self.batch_runner = BatchRunner(self.batch_store, self.job_store, self.project_store)
        self.watchdog_stop = threading.Event()
        self.watchdog_thread = _start_watchdog(self.job_store, self.watchdog_stop)

    def server_close(self) -> None:
        self.batch_runner.shutdown()
        self.watchdog_stop.set()
        if self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=2)
        super().server_close()


def create_server(
    host: str = "127.0.0.1",
    port: int = 8787,
    auth_config: AuthConfig | None = None,
) -> MusicForgeHTTPServer:
    return MusicForgeHTTPServer((host, port), auth_config=auth_config)

def serve(
    host: str = "127.0.0.1",
    port: int = 8787,
    auth_config: AuthConfig | None = None,
) -> None:
    server = create_server(host, port, auth_config=auth_config)
    url = f"http://{host}:{port}"
    print(f"MusicForge Studio running at {url}")
    if server.auth_config.enabled:
        print("Access control: enabled")
    else:
        print("Access control: disabled for localhost")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping MusicForge Studio.")
    finally:
        server.server_close()


__all__ = ["MusicForgeHandler", "MusicForgeHTTPServer", "create_server", "serve", "api_inventory"]
