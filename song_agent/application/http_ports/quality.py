from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from song_agent.application.jobs.model import JobState
from song_agent.application.jobs.ports import JobRuntimePort
from song_agent.domains.creation.encoded_audio_acceptance import EncodedAudioAcceptanceStore
from song_agent.domains.creation.planning_rule_governance import PlanningRuleGovernanceStore
from song_agent.domains.creation.planning_rule_impact import PlanningRuleImpactStore
from song_agent.domains.creation.planning_rule_simulation import PlanningRuleSimulationReport, PlanningRuleSimulationStore
from song_agent.domains.creation.schemas.song import SongPlan
from song_agent.domains.delivery.format_decisions import FormatDecisionStore
from song_agent.domains.delivery.releases import ReleaseDocument, ReleaseStore
from song_agent.domains.delivery.rights_clearance import RightsClearanceStore
from song_agent.domains.quality.acceptance_analytics import AcceptanceAnalyticsStore
from song_agent.domains.quality.acceptance_fix_plan_reviews import AcceptanceFixPlanReviewStore
from song_agent.domains.quality.acceptance_fix_planning import AcceptanceFixPlanningStore
from song_agent.domains.quality.acceptance_fix_sprints import AcceptanceFixSprintStore
from song_agent.domains.quality.acceptance_kb import AcceptanceKnowledgeBaseStore
from song_agent.domains.quality.audio_campaign_governance import AudioCampaignGovernanceStore
from song_agent.domains.quality.audio_campaign_planner import AudioCampaignPlannerStore
from song_agent.domains.quality.audio_campaign_remediation import AudioCampaignRemediationStore
from song_agent.domains.quality.audio_campaigns import AudioCampaignStore
from song_agent.domains.quality.audio_encoding import AudioEncodingStore
from song_agent.domains.quality.audio_encoding_profiles import AudioEncodingProfileStore
from song_agent.domains.quality.audio_fix_sprints import AudioFixSprintStore
from song_agent.domains.quality.audio_lab import AudioLabStore
from song_agent.domains.quality.audio_profiles import AudioProfileStore, RendererProfile
from song_agent.domains.quality.audio_review_evidence import AudioReviewEvidenceStore
from song_agent.domains.quality.audio_revision import AudioRevisionStore
from song_agent.domains.quality.human_review_pack import HumanReviewPackStore
from song_agent.domains.quality.mastering_profiles import MasteringProfileStore
from song_agent.domains.quality.mastering_qa import MasteringStore
from song_agent.domains.quality.music_acceptance import AcceptanceStore
from song_agent.domains.quality.release_audio_baseline_governance import ReleaseAudioBaselineGovernanceStore
from song_agent.domains.quality.release_audio_certification import ReleaseAudioCertificationStore
from song_agent.domains.quality.release_audio_command_center import ReleaseAudioCommandCenterStore
from song_agent.domains.quality.release_audio_quality_action_signoff import ReleaseAudioQualityActionQueueSignoffStore
from song_agent.domains.quality.release_audio_quality_actions import ReleaseAudioQualityActionQueueStore
from song_agent.domains.quality.release_audio_quality_observatory import ReleaseAudioQualityObservatoryStore
from song_agent.domains.quality.release_audio_regression import ReleaseAudioRegressionStore
from song_agent.domains.quality.release_audio_regression_response import ReleaseAudioRegressionResponseStore
from song_agent.domains.quality.release_audio_timeline import ReleaseAudioTimelineStore
from song_agent.domains.studio.project_repository import ProjectDocument, ProjectStore, ProjectVersion
from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.verification.redaction import sanitize_sensitive_text

__all__ = (
    "PlanningRuleSimulationReport",
    "ReleaseDocument",
    "sanitize_sensitive_text",
)


class QualityServerPort(Protocol):
    @property
    def acceptance_analytics_store(self) -> AcceptanceAnalyticsStore: ...

    @property
    def acceptance_fix_plan_review_store(self) -> AcceptanceFixPlanReviewStore: ...

    @property
    def acceptance_fix_plan_store(self) -> AcceptanceFixPlanningStore: ...

    @property
    def acceptance_fix_sprint_store(self) -> AcceptanceFixSprintStore: ...

    @property
    def acceptance_kb_store(self) -> AcceptanceKnowledgeBaseStore: ...

    @property
    def acceptance_store(self) -> AcceptanceStore: ...

    @property
    def audio_campaign_governance_store(self) -> AudioCampaignGovernanceStore: ...

    @property
    def audio_campaign_planner_store(self) -> AudioCampaignPlannerStore: ...

    @property
    def audio_campaign_remediation_store(self) -> AudioCampaignRemediationStore: ...

    @property
    def audio_campaign_store(self) -> AudioCampaignStore: ...

    @property
    def audio_encoding_profile_store(self) -> AudioEncodingProfileStore: ...

    @property
    def audio_encoding_store(self) -> AudioEncodingStore: ...

    @property
    def audio_fix_sprint_store(self) -> AudioFixSprintStore: ...

    @property
    def audio_lab_store(self) -> AudioLabStore: ...

    @property
    def audio_profile_store(self) -> AudioProfileStore: ...

    @property
    def audio_review_store(self) -> AudioReviewEvidenceStore: ...

    @property
    def audio_revision_store(self) -> AudioRevisionStore: ...

    @property
    def encoded_audio_acceptance_store(self) -> EncodedAudioAcceptanceStore: ...

    @property
    def format_decision_store(self) -> FormatDecisionStore: ...

    @property
    def mastering_profile_store(self) -> MasteringProfileStore: ...

    @property
    def mastering_store(self) -> MasteringStore: ...

    @property
    def planning_rule_governance_store(self) -> PlanningRuleGovernanceStore: ...

    @property
    def planning_rule_impact_store(self) -> PlanningRuleImpactStore: ...

    @property
    def planning_rule_simulation_store(self) -> PlanningRuleSimulationStore: ...

    @property
    def release_audio_baseline_governance_store(self) -> ReleaseAudioBaselineGovernanceStore: ...

    @property
    def release_audio_certification_store(self) -> ReleaseAudioCertificationStore: ...

    @property
    def release_audio_command_center_store(self) -> ReleaseAudioCommandCenterStore: ...

    @property
    def release_audio_quality_action_queue_store(self) -> ReleaseAudioQualityActionQueueStore: ...

    @property
    def release_audio_quality_action_signoff_store(self) -> ReleaseAudioQualityActionQueueSignoffStore: ...

    @property
    def release_audio_quality_observatory_store(self) -> ReleaseAudioQualityObservatoryStore: ...

    @property
    def release_audio_regression_response_store(self) -> ReleaseAudioRegressionResponseStore: ...

    @property
    def release_audio_regression_store(self) -> ReleaseAudioRegressionStore: ...

    @property
    def release_audio_timeline_store(self) -> ReleaseAudioTimelineStore: ...

    @property
    def rights_clearance_store(self) -> RightsClearanceStore: ...


class _QualityRouteContextTyping(QualityServerPort, Protocol):
    """Typed cross-route members supplied by API composition."""

    human_review_pack_store: HumanReviewPackStore
    project_store: ProjectStore
    release_store: ReleaseStore
    server: QualityServerPort
    store: JobRuntimePort

    def _job_audio_artifact_stale_reasons(self, job: JobState) -> list[str]: ...

    def _optional_json_body(self) -> JsonDocument: ...

    def _project_edit_parent(
        self,
        project_id: str,
        version_id: str,
    ) -> tuple[ProjectDocument, ProjectVersion, JobState, SongPlan]: ...

    def _read_json_body(self) -> JsonDocument: ...

    def _release_acceptance_fix_plan_gate(self, payload: JsonDocument) -> JsonDocument: ...

    def _release_acceptance_fix_plan_review_gate(self, payload: JsonDocument) -> JsonDocument: ...

    def _release_acceptance_fix_sprint_gate(self, payload: JsonDocument) -> JsonDocument: ...

    def _release_acceptance_kb_gate(self, payload: JsonDocument) -> JsonDocument: ...

    def _release_mix_gate(
        self,
        release_id: str,
        *,
        require_stem_health: bool,
        require_current_mix: bool,
    ) -> JsonDocument: ...

    def _release_planning_rule_governance_gate(self, payload: JsonDocument) -> JsonDocument: ...

    def _release_planning_rule_impact_gate(self, payload: JsonDocument) -> JsonDocument: ...

    def _release_planning_rule_simulation_gate(self, payload: JsonDocument) -> JsonDocument: ...

    def _renderer_profile_from_payload(self, payload: JsonDocument | None) -> RendererProfile | None: ...

    def _send_error(self, status: HTTPStatus, message: str) -> None: ...

    def _send_file(
        self,
        path: Path,
        content_type: str | None = None,
        *,
        filename: str | None = None,
    ) -> None: ...

    def _send_json(self, payload: object, *, status: HTTPStatus = HTTPStatus.OK) -> None: ...


if TYPE_CHECKING:
    QualityRouteContext = _QualityRouteContextTyping
else:

    class QualityRouteContext:
        """Runtime marker for Quality route mixins."""
