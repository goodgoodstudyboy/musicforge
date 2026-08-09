from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Protocol

from song_agent.domains.quality.audio_encoding import AudioEncodingStore
from song_agent.platform.contracts.documents import JsonDocument


class DocumentOperation(Protocol):
    def __call__(self, *arguments: object, **options: object) -> JsonDocument: ...


class GateStorePort(Protocol):
    gate: DocumentOperation


class ReleaseDocumentPort(Protocol):
    status: str
    latest_signoff_summary: JsonDocument

    def to_dict(self) -> JsonDocument: ...


class ReleaseStorePort(Protocol):
    def read_signoff(self, release_id: str, *, default: JsonDocument) -> JsonDocument: ...

    def get_release(self, release_id: str) -> ReleaseDocumentPort: ...

    def zip_path(self, release_id: str) -> Path: ...

    def release_dir(self, release_id: str) -> Path: ...

    def export_dir(self, release_id: str) -> Path: ...

    def write_signoff(self, release_id: str, document: JsonDocument) -> JsonDocument: ...

    def update_signoff_summary(self, release_id: str, summary: JsonDocument) -> ReleaseDocumentPort: ...

    def append_event(self, release_id: str, event_type: str, payload: JsonDocument) -> object: ...


class JsonSender(Protocol):
    def __call__(self, payload: object, *, status: HTTPStatus = HTTPStatus.OK) -> None: ...


class ErrorSender(Protocol):
    def __call__(self, status: HTTPStatus, message: str) -> None: ...


class ReleaseSignoffCompositionPort(Protocol):
    audio_encoding_store: AudioEncodingStore
    release_store: ReleaseStorePort
    audio_campaign_remediation_store: GateStorePort
    encoded_audio_acceptance_store: GateStorePort
    format_decision_store: GateStorePort
    mastering_store: GateStorePort
    release_audio_baseline_governance_store: GateStorePort
    release_audio_certification_store: GateStorePort
    release_audio_command_center_store: GateStorePort
    release_audio_quality_action_queue_store: GateStorePort
    release_audio_quality_action_signoff_store: GateStorePort
    release_audio_quality_observatory_store: GateStorePort
    release_audio_regression_response_store: GateStorePort
    release_audio_regression_store: GateStorePort
    release_audio_timeline_store: GateStorePort
    rights_clearance_store: GateStorePort
    unified_command_center_continuous_review_store: GateStorePort
    unified_command_center_drift_response_store: GateStorePort
    unified_command_center_evidence_review_store: GateStorePort
    unified_command_center_handoff_store: GateStorePort
    unified_command_center_release_train_store: GateStorePort
    unified_command_center_reviewer_decision_board_store: GateStorePort
    unified_command_center_signoff_store: GateStorePort
    unified_command_center_store: GateStorePort
    unified_release_program_continuity_acceptance_store: GateStorePort
    unified_release_program_continuity_command_center_acceptance_change_store: GateStorePort
    unified_release_program_continuity_command_center_acceptance_store: GateStorePort
    unified_release_program_continuity_command_center_signoff_store: GateStorePort
    unified_release_program_continuity_command_center_store: GateStorePort
    unified_release_program_continuity_distribution_store: GateStorePort
    unified_release_program_continuity_store: GateStorePort
    unified_release_program_handoff_store: GateStorePort
    unified_release_program_vault_operations_store: GateStorePort
    unified_release_program_vault_store: GateStorePort


class ReleaseSignoffHandlerPort(Protocol):
    server: ReleaseSignoffCompositionPort
    _get_or_refresh_release_qa: DocumentOperation
    _optional_json_body: DocumentOperation
    _release_acceptance_gate: DocumentOperation
    _release_audio_campaign_gate: DocumentOperation
    _release_audio_gate: DocumentOperation
    _release_declarative_policy_gate: DocumentOperation
    _release_encoded_audio_acceptance_export_gate: DocumentOperation
    _release_encoded_audio_export_gate: DocumentOperation
    _release_format_decision_export_gate: DocumentOperation
    _release_mastering_export_gate: DocumentOperation
    _release_rights_clearance_export_gate: DocumentOperation
    _send_error: ErrorSender
    _send_json: JsonSender


__all__ = (
    "DocumentOperation",
    "ErrorSender",
    "GateStorePort",
    "JsonSender",
    "ReleaseDocumentPort",
    "ReleaseSignoffCompositionPort",
    "ReleaseSignoffHandlerPort",
    "ReleaseStorePort",
)
