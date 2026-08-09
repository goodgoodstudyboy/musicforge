from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from song_agent.domains.creation.encoded_audio_acceptance import EncodedAudioAcceptanceStore
from song_agent.domains.creation.schemas.song import SongPlan
from song_agent.domains.delivery.distribution import DistributionStore, DistributionTarget
from song_agent.domains.delivery.distribution_artwork import latest_distribution_artwork
from song_agent.domains.delivery.distribution_templates import TemplatePackStore
from song_agent.domains.delivery.format_decisions import FormatDecisionStore
from song_agent.domains.delivery.releases import ReleaseDocument, ReleaseStore
from song_agent.domains.delivery.rights_clearance import RightsClearanceStore
from song_agent.domains.delivery.submission_evidence import SubmissionEvidenceStore
from song_agent.domains.delivery.submissions import SubmissionBatch, SubmissionStore
from song_agent.domains.quality.audio_revision import AudioRevisionStore
from song_agent.domains.studio.project_repository import ProjectStore
from song_agent.domains.trust.release_operations import ReleaseOperationsStore
from song_agent.domains.trust.release_operations_audit import ReleaseOperationsAuditStore
from song_agent.domains.trust.release_operations_reviewer_pack import ReleaseOperationsReviewerPackStore
from song_agent.domains.trust.release_operations_runbook import ReleaseOperationsRunbookStore
from song_agent.domains.trust.release_operations_signoff import ReleaseOperationsSignoffStore
from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.verification.redaction import sanitize_sensitive_text

__all__ = (
    "SongPlan",
    "latest_distribution_artwork",
    "sanitize_sensitive_text",
)


class DeliveryServerPort(Protocol):
    @property
    def audio_revision_store(self) -> AudioRevisionStore: ...

    @property
    def distribution_store(self) -> DistributionStore: ...

    @property
    def distribution_template_store(self) -> TemplatePackStore: ...

    @property
    def encoded_audio_acceptance_store(self) -> EncodedAudioAcceptanceStore: ...

    @property
    def format_decision_store(self) -> FormatDecisionStore: ...

    @property
    def project_store(self) -> ProjectStore: ...

    @property
    def release_operations_audit_store(self) -> ReleaseOperationsAuditStore: ...

    @property
    def release_operations_reviewer_pack_store(self) -> ReleaseOperationsReviewerPackStore: ...

    @property
    def release_operations_runbook_store(self) -> ReleaseOperationsRunbookStore: ...

    @property
    def release_operations_signoff_store(self) -> ReleaseOperationsSignoffStore: ...

    @property
    def release_operations_store(self) -> ReleaseOperationsStore: ...

    @property
    def release_store(self) -> ReleaseStore: ...

    @property
    def rights_clearance_store(self) -> RightsClearanceStore: ...

    @property
    def submission_evidence_store(self) -> SubmissionEvidenceStore: ...

    @property
    def submission_store(self) -> SubmissionStore: ...


class _DeliveryRouteContextTyping(DeliveryServerPort, Protocol):
    """Typed cross-route members supplied by API composition."""

    path: str
    server: DeliveryServerPort

    def _build_distribution_layout(self, release_id: str, target: DistributionTarget) -> JsonDocument: ...

    def _distribution_encoded_audio_acceptance_export_gate(
        self,
        export_manifest: JsonDocument,
        acceptance_gate: JsonDocument,
    ) -> JsonDocument: ...

    def _distribution_format_decision_export_gate(
        self,
        export_manifest: JsonDocument,
        format_decision_gate: JsonDocument,
    ) -> JsonDocument: ...

    def _ensure_release_export_mutable(self, release_id: str, *, document: ReleaseDocument | None = None) -> None: ...

    def _get_or_refresh_distribution_qa(
        self,
        release_id: str,
        target: DistributionTarget,
        *,
        refresh: bool,
    ) -> JsonDocument: ...

    def _get_or_refresh_release_metadata_qa(self, release_id: str, *, refresh: bool) -> JsonDocument: ...

    def _get_or_refresh_release_qa(
        self,
        release_id: str,
        *,
        refresh: bool,
        options: JsonDocument,
    ) -> JsonDocument: ...

    def _get_or_refresh_submission_qa(
        self,
        release_id: str,
        batch: SubmissionBatch,
        *,
        refresh: bool,
    ) -> JsonDocument: ...

    def _handle_distribution_route(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_acceptance_analytics(self, method: str, release_id: str) -> None: ...

    def _handle_release_acceptance_analytics_refresh(self, method: str, release_id: str) -> None: ...

    def _handle_release_audio_campaign_plan(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_campaign_remediation(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_certification(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_command_center(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_qa(self, method: str, release_id: str) -> None: ...

    def _handle_release_audio_regression(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_regression_response(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_reviews(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_revisions(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_audio_timeline(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_encoded_audio(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_format_decisions(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_mastering(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_operations(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_operations_reviewer_pack(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_operations_runbooks(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_rights(self, method: str, release_id: str, tail: str) -> None: ...

    def _handle_release_signoff(self, method: str, release_id: str) -> None: ...

    def _handle_release_signoff_reset(self, method: str, release_id: str) -> None: ...

    def _handle_submission_route(self, method: str, release_id: str, tail: str) -> None: ...

    def _optional_json_body(self) -> JsonDocument: ...

    def _package_rights_clearance_export_gate(
        self,
        export_manifest: JsonDocument,
        rights_gate: JsonDocument,
        *,
        package_label: str,
    ) -> JsonDocument: ...

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

    def _submission_payload_with_evidence_summary(
        self,
        release_id: str,
        batch: SubmissionBatch,
    ) -> JsonDocument: ...


if TYPE_CHECKING:
    DeliveryRouteContext = _DeliveryRouteContextTyping
else:

    class DeliveryRouteContext:
        """Runtime marker for Delivery route mixins."""
