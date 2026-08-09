from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from song_agent.domains.trust.public_trust_center import PublicTrustCenterStore
from song_agent.domains.trust.public_trust_center_acceptance_board import PublicTrustCenterAcceptanceBoardStore
from song_agent.domains.trust.public_trust_center_anchor_registry import PublicTrustCenterAnchorRegistryStore
from song_agent.domains.trust.public_trust_center_anchor_transparency import PublicTrustCenterAnchorTransparencyStore
from song_agent.domains.trust.public_trust_center_distribution_kit import PublicTrustCenterDistributionKitStore
from song_agent.domains.trust.public_trust_center_distribution_kit_acceptance import PublicTrustCenterDistributionKitAcceptanceStore
from song_agent.domains.trust.release_portfolio_audit import ReleasePortfolioAuditStore
from song_agent.domains.trust.release_portfolio_governance import ReleasePortfolioGovernanceStore
from song_agent.domains.trust.release_portfolio_governance_attestation import ReleasePortfolioGovernanceAttestationStore
from song_agent.domains.trust.release_portfolio_governance_attestation_accepted_evidence import ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore
from song_agent.domains.trust.release_portfolio_governance_attestation_portal import ReleasePortfolioGovernanceAttestationPortalStore
from song_agent.domains.trust.release_portfolio_governance_attestation_portal_review import ReleasePortfolioGovernanceAttestationPortalReviewStore
from song_agent.domains.trust.release_portfolio_governance_attestation_registry import ReleasePortfolioGovernanceAttestationRegistryStore
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency import ReleasePortfolioGovernanceAttestationTransparencyStore
from song_agent.domains.trust.release_portfolio_governance_attestation_transparency_acknowledgement import ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore
from song_agent.domains.trust.release_portfolio_governance_audit import ReleasePortfolioGovernanceAuditStore
from song_agent.domains.trust.release_portfolio_governance_evidence_vault import ReleasePortfolioGovernanceEvidenceVaultStore
from song_agent.domains.trust.release_portfolio_governance_final_board import ReleasePortfolioGovernanceFinalBoardStore
from song_agent.domains.trust.release_portfolio_governance_reviewer_pack import ReleasePortfolioGovernanceReviewerPackStore
from song_agent.domains.trust.release_portfolio_governance_signoff import ReleasePortfolioGovernanceSignoffStore
from song_agent.domains.trust.trust_operations_assurance_watch import TrustOperationsAssuranceWatchStore
from song_agent.domains.trust.trust_operations_assurance_watch_signoff import TrustOperationsAssuranceWatchSignoffStore
from song_agent.domains.trust.trust_operations_continuous_assurance import TrustOperationsAssuranceStore
from song_agent.domains.trust.trust_operations_control_signoff import TrustOperationsControlSignoffStore
from song_agent.domains.trust.trust_operations_controls import TrustOperationsControlStore
from song_agent.domains.trust.trust_operations_final_readiness import TrustOperationsFinalReadinessStore
from song_agent.domains.trust.trust_operations_hub import TrustOperationsHubStore
from song_agent.domains.trust.trust_operations_hub_incidents import TrustOperationsIncidentStore
from song_agent.domains.trust.trust_operations_incident_knowledge import TrustOperationsIncidentKnowledgeStore
from song_agent.platform.contracts.documents import JsonDocument


class TrustServerPort(Protocol):
    @property
    def public_trust_center_acceptance_board_store(self) -> PublicTrustCenterAcceptanceBoardStore: ...

    @property
    def public_trust_center_anchor_registry_store(self) -> PublicTrustCenterAnchorRegistryStore: ...

    @property
    def public_trust_center_anchor_transparency_store(self) -> PublicTrustCenterAnchorTransparencyStore: ...

    @property
    def public_trust_center_distribution_kit_acceptance_store(
        self,
    ) -> PublicTrustCenterDistributionKitAcceptanceStore: ...

    @property
    def public_trust_center_distribution_kit_store(self) -> PublicTrustCenterDistributionKitStore: ...

    @property
    def public_trust_center_store(self) -> PublicTrustCenterStore: ...

    @property
    def release_portfolio_audit_store(self) -> ReleasePortfolioAuditStore: ...

    @property
    def release_portfolio_governance_attestation_accepted_evidence_store(
        self,
    ) -> ReleasePortfolioGovernanceAttestationAcceptedEvidenceStore: ...

    @property
    def release_portfolio_governance_attestation_portal_review_store(
        self,
    ) -> ReleasePortfolioGovernanceAttestationPortalReviewStore: ...

    @property
    def release_portfolio_governance_attestation_portal_store(
        self,
    ) -> ReleasePortfolioGovernanceAttestationPortalStore: ...

    @property
    def release_portfolio_governance_attestation_registry_store(
        self,
    ) -> ReleasePortfolioGovernanceAttestationRegistryStore: ...

    @property
    def release_portfolio_governance_attestation_store(self) -> ReleasePortfolioGovernanceAttestationStore: ...

    @property
    def release_portfolio_governance_attestation_transparency_acknowledgement_store(
        self,
    ) -> ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStore: ...

    @property
    def release_portfolio_governance_attestation_transparency_store(
        self,
    ) -> ReleasePortfolioGovernanceAttestationTransparencyStore: ...

    @property
    def release_portfolio_governance_audit_store(self) -> ReleasePortfolioGovernanceAuditStore: ...

    @property
    def release_portfolio_governance_evidence_vault_store(
        self,
    ) -> ReleasePortfolioGovernanceEvidenceVaultStore: ...

    @property
    def release_portfolio_governance_final_board_store(self) -> ReleasePortfolioGovernanceFinalBoardStore: ...

    @property
    def release_portfolio_governance_reviewer_pack_store(
        self,
    ) -> ReleasePortfolioGovernanceReviewerPackStore: ...

    @property
    def release_portfolio_governance_signoff_store(self) -> ReleasePortfolioGovernanceSignoffStore: ...

    @property
    def release_portfolio_governance_store(self) -> ReleasePortfolioGovernanceStore: ...

    @property
    def trust_operations_assurance_store(self) -> TrustOperationsAssuranceStore: ...

    @property
    def trust_operations_assurance_watch_signoff_store(self) -> TrustOperationsAssuranceWatchSignoffStore: ...

    @property
    def trust_operations_assurance_watch_store(self) -> TrustOperationsAssuranceWatchStore: ...

    @property
    def trust_operations_control_signoff_store(self) -> TrustOperationsControlSignoffStore: ...

    @property
    def trust_operations_control_store(self) -> TrustOperationsControlStore: ...

    @property
    def trust_operations_final_readiness_store(self) -> TrustOperationsFinalReadinessStore: ...

    @property
    def trust_operations_hub_store(self) -> TrustOperationsHubStore: ...

    @property
    def trust_operations_incident_knowledge_store(self) -> TrustOperationsIncidentKnowledgeStore: ...

    @property
    def trust_operations_incident_store(self) -> TrustOperationsIncidentStore: ...


class _TrustRouteContextTyping(TrustServerPort, Protocol):
    """Typed cross-route members supplied by API composition."""

    path: str
    server: TrustServerPort

    def _handle_public_trust_center_acceptance_board(self, method: str, center_id: str, parts: list[str]) -> None: ...

    def _handle_public_trust_center_distribution_kit_acceptance(self, method: str, center_id: str, parts: list[str]) -> None: ...

    def _handle_trust_operations_assurance(self, method: str, tail: str) -> None: ...

    def _handle_trust_operations_assurance_watch(self, method: str, tail: str) -> None: ...

    def _handle_trust_operations_control_signoff(self, method: str, hub_id: str, tail: str) -> None: ...

    def _handle_trust_operations_controls(self, method: str, hub_id: str, tail: str) -> None: ...

    def _handle_trust_operations_final_readiness(self, method: str, tail: str) -> None: ...

    def _handle_trust_operations_incidents(self, method: str, hub_id: str, tail: str) -> None: ...

    def _handle_trust_operations_knowledge(self, method: str, hub_id: str, tail: str) -> None: ...

    def _optional_json_body(self) -> JsonDocument: ...

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
    TrustRouteContext = _TrustRouteContextTyping
else:

    class TrustRouteContext:
        """Runtime marker for Trust route mixins."""


class _TrustPortfolioRouteContextTyping(TrustServerPort, Protocol):
    """Typed members shared by Release Portfolio route mixins."""

    path: str

    def _optional_json_body(self) -> JsonDocument: ...

    def _read_json_body(self) -> JsonDocument: ...

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
    TrustPortfolioRouteContext = _TrustPortfolioRouteContextTyping
else:

    class TrustPortfolioRouteContext:
        """Runtime marker for Release Portfolio route mixins."""
