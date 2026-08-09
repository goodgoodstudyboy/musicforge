from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from song_agent.application.program.http_context import AcceptanceChangeStorePort, AcceptanceStorePort, CommandCenterSignoffStorePort, CommandCenterStorePort, ContinuityDistributionStorePort, ContinuityStorePort, ErrorSender, HandoffStorePort, JsonBodyReader, JsonSender, OperationsStorePort, ProgramServicePort, ProgramStorePort, ReceiverAcceptanceChangeStorePort, ReceiverAcceptanceStorePort, ReleaseTrainChangeStorePort, ReleaseTrainHandoffStorePort, ReleaseTrainLifecycleStorePort, ReleaseTrainStorePort, UnifiedCommandCenterBoardStorePort, UnifiedCommandCenterDriftStorePort, UnifiedCommandCenterEvidenceReviewStorePort, UnifiedCommandCenterHandoffStorePort, UnifiedCommandCenterReviewStorePort, UnifiedCommandCenterSignoffStorePort, UnifiedCommandCenterStorePort, VaultOperationsStorePort, VaultStorePort
from song_agent.platform.contracts.documents import JsonDocument


class FileSender(Protocol):
    def __call__(
        self,
        path: Path,
        content_type: str,
        *,
        filename: str | None = None,
    ) -> None: ...


class ProgramServerPort(Protocol):
    @property
    def program_application_service(self) -> ProgramServicePort: ...

    @property
    def unified_release_program_store(self) -> ProgramStorePort: ...

    @property
    def unified_release_program_operations_store(self) -> OperationsStorePort: ...

    @property
    def unified_release_program_handoff_store(self) -> HandoffStorePort: ...

    @property
    def unified_release_program_vault_store(self) -> VaultStorePort: ...

    @property
    def unified_release_program_vault_operations_store(self) -> VaultOperationsStorePort: ...

    @property
    def unified_release_program_continuity_store(self) -> ContinuityStorePort: ...

    @property
    def unified_release_program_continuity_distribution_store(self) -> ContinuityDistributionStorePort: ...

    @property
    def unified_release_program_continuity_acceptance_store(self) -> AcceptanceStorePort: ...

    @property
    def unified_release_program_continuity_acceptance_change_store(self) -> AcceptanceChangeStorePort: ...

    @property
    def unified_release_program_continuity_command_center_store(self) -> CommandCenterStorePort: ...

    @property
    def unified_release_program_continuity_command_center_signoff_store(self) -> CommandCenterSignoffStorePort: ...

    @property
    def unified_release_program_continuity_command_center_acceptance_store(self) -> ReceiverAcceptanceStorePort: ...

    @property
    def unified_release_program_continuity_command_center_acceptance_change_store(
        self,
    ) -> ReceiverAcceptanceChangeStorePort: ...

    @property
    def unified_command_center_store(self) -> UnifiedCommandCenterStorePort: ...

    @property
    def unified_command_center_signoff_store(self) -> UnifiedCommandCenterSignoffStorePort: ...

    @property
    def unified_command_center_handoff_store(self) -> UnifiedCommandCenterHandoffStorePort: ...

    @property
    def unified_command_center_continuous_review_store(self) -> UnifiedCommandCenterReviewStorePort: ...

    @property
    def unified_command_center_drift_response_store(self) -> UnifiedCommandCenterDriftStorePort: ...

    @property
    def unified_command_center_evidence_review_store(self) -> UnifiedCommandCenterEvidenceReviewStorePort: ...

    @property
    def unified_command_center_reviewer_decision_board_store(self) -> UnifiedCommandCenterBoardStorePort: ...

    @property
    def unified_command_center_release_train_store(self) -> ReleaseTrainStorePort: ...

    @property
    def unified_command_center_release_train_change_control_store(self) -> ReleaseTrainChangeStorePort: ...

    @property
    def unified_command_center_release_train_lifecycle_store(self) -> ReleaseTrainLifecycleStorePort: ...

    @property
    def unified_command_center_release_train_handoff_store(self) -> ReleaseTrainHandoffStorePort: ...


class _ProgramRouteContextTyping(ProgramServerPort, Protocol):
    """Static Program route contract supplied by API composition."""

    def _handle_unified_command_center_release_trains_route_part_01(
        self, method: str, path: str, state: JsonDocument
    ) -> tuple[bool, object | None]: ...

    def _handle_unified_command_center_release_trains_route_part_02(
        self, method: str, path: str, state: JsonDocument
    ) -> tuple[bool, object | None]: ...

    def _handle_unified_command_center_release_trains_route_part_03(
        self, method: str, path: str, state: JsonDocument
    ) -> tuple[bool, object | None]: ...

    def _handle_unified_command_center_release_trains_route_part_04(
        self, method: str, path: str, state: JsonDocument
    ) -> tuple[bool, object | None]: ...

    def _handle_unified_command_center_release_trains_route_part_05(
        self, method: str, path: str, state: JsonDocument
    ) -> tuple[bool, object | None]: ...

    _optional_json_body: JsonBodyReader
    _read_json_body: JsonBodyReader
    _send_error: ErrorSender
    _send_file: FileSender
    _send_json: JsonSender
    @property
    def program_application(self) -> ProgramServicePort: ...

    server: ProgramServerPort


if TYPE_CHECKING:
    ProgramRouteContext = _ProgramRouteContextTyping
else:

    class ProgramRouteContext:
        """Runtime marker for Program route mixins."""
