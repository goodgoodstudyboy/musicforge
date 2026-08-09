from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Protocol

from song_agent.platform.contracts.documents import JsonDocument


class DocumentOperation(Protocol):
    def __call__(self, *arguments: object, **options: object) -> JsonDocument: ...


class DocumentListOperation(Protocol):
    def __call__(self, *arguments: object, **options: object) -> list[JsonDocument]: ...


class PathOperation(Protocol):
    def __call__(self, *arguments: object, **options: object) -> Path: ...


class JsonBodyReader(Protocol):
    def __call__(self) -> JsonDocument: ...


class JsonSender(Protocol):
    def __call__(
        self,
        payload: object,
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None: ...


class ErrorSender(Protocol):
    def __call__(self, status: HTTPStatus, message: str) -> None: ...


class RouteDispatcher(Protocol):
    def __call__(self, method: str, program_id: str, tail: str) -> bool: ...


class ProgramServicePort(Protocol):
    def component(self, component: str) -> object: ...

    def list_programs(self) -> list[JsonDocument]: ...

    def create_program(self, payload: JsonDocument | None = None) -> JsonDocument: ...

    def get_program(self, program_id: str) -> JsonDocument: ...

    def evaluate_gate(
        self,
        program_id: str,
        payload: JsonDocument,
    ) -> JsonDocument: ...

    def dispatch_http(self, port: object, method: str, path: str) -> None: ...


class ProgramHttpPort(Protocol):
    def _optional_json_body(self) -> JsonDocument: ...

    def _read_json_body(self) -> JsonDocument: ...

    def _send_error(self, status: HTTPStatus, message: str) -> None: ...

    def _send_json(
        self,
        payload: object,
        *,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None: ...


class ProgramStorePort(Protocol):
    list_programs: DocumentListOperation
    create_program: DocumentOperation
    get_program: DocumentOperation
    add_train_item: DocumentOperation
    refresh_report: DocumentOperation
    signoff: DocumentOperation
    export_program: DocumentOperation
    build_zip: DocumentOperation
    verify_package: DocumentOperation
    gate: DocumentOperation


class OperationsStorePort(Protocol):
    create_change_request: DocumentOperation
    approve_change_request: DocumentOperation
    reset_program_signoff: DocumentOperation
    create_runbook: DocumentOperation
    run_safe: DocumentOperation
    refresh_continuous_review: DocumentOperation
    refresh_lifecycle_audit: DocumentOperation
    export_operations_archive: DocumentOperation
    build_operations_archive_zip: DocumentOperation
    verify_operations_archive_zip: DocumentOperation
    gate: DocumentOperation


class HandoffStorePort(Protocol):
    get_handoff: DocumentOperation
    refresh_handoff: DocumentOperation
    export_review_pack: DocumentOperation
    build_review_pack_zip: DocumentOperation
    verify_review_pack_zip: DocumentOperation
    import_response: DocumentOperation
    create_accepted_evidence: DocumentOperation
    build_accepted_evidence_zip: DocumentOperation
    verify_accepted_evidence_zip: DocumentOperation
    refresh_decision_board: DocumentOperation
    signoff_handoff: DocumentOperation
    export_handoff_archive: DocumentOperation
    build_handoff_archive_zip: DocumentOperation
    verify_handoff_archive_zip: DocumentOperation
    gate: DocumentOperation


class VaultStorePort(Protocol):
    get_vault: DocumentOperation
    refresh_vault: DocumentOperation
    export_vault: DocumentOperation
    build_vault_zip: DocumentOperation
    verify_vault_zip: DocumentOperation
    gate: DocumentOperation


class VaultOperationsStorePort(Protocol):
    get_operations: DocumentOperation
    init_policy: DocumentOperation
    register_vault: DocumentOperation
    refresh_registry: DocumentOperation
    run_custody_review: DocumentOperation
    create_rotation_plan: DocumentOperation
    supersede_vault: DocumentOperation
    revoke_vault: DocumentOperation
    create_transfer_pack: DocumentOperation
    signoff_operations: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive_zip: DocumentOperation
    gate: DocumentOperation


class ContinuityStorePort(Protocol):
    get_continuity: DocumentOperation
    init_policy: DocumentOperation
    create_recovery_plan: DocumentOperation
    run_recovery_drill: DocumentOperation
    refresh_readiness: DocumentOperation
    generate_runbook: DocumentOperation
    signoff_continuity: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive_zip: DocumentOperation
    gate: DocumentOperation


class ContinuityDistributionStorePort(Protocol):
    get_kit: DocumentOperation
    prepare_kit: DocumentOperation
    export_kit: DocumentOperation
    build_kit_zip: DocumentOperation
    verify_kit: DocumentOperation
    create_receiver_receipt_template: DocumentOperation
    import_receiver_receipt: DocumentOperation
    verify_receiver_receipt: DocumentOperation
    gate: DocumentOperation


class AcceptanceStorePort(Protocol):
    get_board: DocumentOperation
    import_response: DocumentOperation
    create_accepted_evidence: DocumentOperation
    refresh_decision_board: DocumentOperation
    signoff_acceptance: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive_zip: DocumentOperation
    gate: DocumentOperation


class AcceptanceChangeStorePort(Protocol):
    get_state: DocumentOperation
    create_change_request: DocumentOperation
    approve_change_request: DocumentOperation
    reset_acceptance_signoff: DocumentOperation
    refresh_lifecycle_audit: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive_zip: DocumentOperation
    gate: DocumentOperation


class CommandCenterStorePort(Protocol):
    get_command_center: DocumentOperation
    refresh_command_center: DocumentOperation
    run_safe: DocumentOperation
    export_package: DocumentOperation
    build_zip: DocumentOperation
    verify_zip: DocumentOperation
    gate: DocumentOperation


class CommandCenterSignoffStorePort(Protocol):
    get_state: DocumentOperation
    preflight: DocumentOperation
    signoff: DocumentOperation
    create_change_request: DocumentOperation
    approve_change_request: DocumentOperation
    reset_signoff: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive_zip: DocumentOperation
    export_final_handoff: DocumentOperation
    build_final_handoff_zip: DocumentOperation
    verify_final_handoff_zip: DocumentOperation
    gate: DocumentOperation


class ReceiverAcceptanceStorePort(Protocol):
    status: DocumentOperation
    create_review_pack: DocumentOperation
    verify_review_pack: DocumentOperation
    import_response: DocumentOperation
    create_accepted_evidence: DocumentOperation
    verify_accepted_evidence: DocumentOperation
    refresh_board: DocumentOperation
    signoff: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive_zip: DocumentOperation
    gate: DocumentOperation


class ReceiverAcceptanceChangeStorePort(Protocol):
    get_state: DocumentOperation
    create_change_request: DocumentOperation
    approve_change_request: DocumentOperation
    reset_receiver_acceptance_signoff: DocumentOperation
    refresh_lifecycle_audit: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive_zip: DocumentOperation
    gate: DocumentOperation


class UnifiedCommandCenterStorePort(Protocol):
    list_centers: DocumentListOperation
    create: DocumentOperation
    read_center: DocumentOperation
    read_report: DocumentOperation
    refresh: DocumentOperation
    create_runbook: DocumentOperation
    run_safe: DocumentOperation
    export_package: DocumentOperation
    build_zip: DocumentOperation
    verify_zip: DocumentOperation
    report_path: PathOperation
    inventory_path: PathOperation
    readiness_path: PathOperation
    gap_plan_path: PathOperation
    runbook_path: PathOperation
    zip_path: PathOperation


class UnifiedCommandCenterSignoffStorePort(Protocol):
    signoff: DocumentOperation
    create_change_request: DocumentOperation
    approve_change_request: DocumentOperation
    reset_signoff: DocumentOperation
    export_archive: DocumentOperation
    build_archive_zip: DocumentOperation
    verify_archive: DocumentOperation
    archive_manifest_path: PathOperation
    archive_zip_path: PathOperation


class UnifiedCommandCenterHandoffStorePort(Protocol):
    export_handoff: DocumentOperation
    build_handoff_zip: DocumentOperation
    verify_handoff: DocumentOperation
    manifest_path: PathOperation
    zip_path: PathOperation


class UnifiedCommandCenterReviewStorePort(Protocol):
    list_reviews: DocumentListOperation
    create_plan: DocumentOperation
    read_review: DocumentOperation
    run_review: DocumentOperation
    export_package: DocumentOperation
    build_zip: DocumentOperation
    verify_package: DocumentOperation
    zip_path: PathOperation


class UnifiedCommandCenterDriftStorePort(Protocol):
    list_responses: DocumentListOperation
    create_response: DocumentOperation
    read_response: DocumentOperation
    bind_change_request: DocumentOperation
    run_safe: DocumentOperation
    bind_recheck: DocumentOperation
    closeout: DocumentOperation
    export_package: DocumentOperation
    build_zip: DocumentOperation
    verify_package: DocumentOperation
    zip_path: PathOperation


class UnifiedCommandCenterEvidenceReviewStorePort(Protocol):
    list_reviews: DocumentListOperation
    create_review: DocumentOperation
    get_review: DocumentOperation
    refresh_review: DocumentOperation
    run_replay: DocumentOperation
    export_review: DocumentOperation
    build_zip: DocumentOperation
    verify_zip: DocumentOperation
    list_responses: DocumentListOperation
    import_response: DocumentOperation
    create_acceptance_evidence: DocumentOperation
    verify_acceptance_evidence: DocumentOperation
    accepted_evidence_zip_path: PathOperation
    zip_path: PathOperation


class UnifiedCommandCenterBoardStorePort(Protocol):
    list_boards: DocumentListOperation
    create_board: DocumentOperation
    get_board: DocumentOperation
    refresh_board: DocumentOperation
    signoff: DocumentOperation
    export_archive: DocumentOperation
    build_zip: DocumentOperation
    verify_archive: DocumentOperation
    zip_path: PathOperation


class ReleaseTrainStorePort(Protocol):
    list_trains: DocumentListOperation
    create_train: DocumentOperation
    read_train: DocumentOperation
    read_docs: DocumentOperation
    add_item: DocumentOperation
    refresh: DocumentOperation
    run_safe: DocumentOperation
    signoff: DocumentOperation
    export_archive: DocumentOperation
    build_zip: DocumentOperation
    verify_archive: DocumentOperation
    report_path: PathOperation
    archive_manifest_path: PathOperation
    zip_path: PathOperation


class ReleaseTrainChangeStorePort(Protocol):
    list_requests: DocumentListOperation
    create_request: DocumentOperation
    read_request: DocumentOperation
    approve_request: DocumentOperation
    reset_train_signoff: DocumentOperation
    refresh_report: DocumentOperation
    export_package: DocumentOperation
    build_zip: DocumentOperation
    verify_package: DocumentOperation
    change_dir: PathOperation
    zip_path: PathOperation


class ReleaseTrainLifecycleStorePort(Protocol):
    read_report: DocumentOperation
    refresh_report: DocumentOperation
    export_package: DocumentOperation
    build_zip: DocumentOperation
    verify_package: DocumentOperation
    report_path: PathOperation
    zip_path: PathOperation


class ReleaseTrainHandoffStorePort(Protocol):
    list_handoffs: DocumentListOperation
    create_handoff: DocumentOperation
    get_handoff: DocumentOperation
    refresh_report: DocumentOperation
    import_response: DocumentOperation
    create_accepted_evidence: DocumentOperation
    signoff: DocumentOperation
    export_handoff: DocumentOperation
    build_zip: DocumentOperation
    verify_package: DocumentOperation
    zip_path: PathOperation


class ProgramHttpContext:
    """Typed members supplied by the Program HTTP composition root."""

    _dispatch_command_center_signoff_archive: RouteDispatcher
    _dispatch_command_center_signoff_workflow: RouteDispatcher
    _dispatch_continuity_archive: RouteDispatcher
    _dispatch_continuity_workflow: RouteDispatcher
    _dispatch_handoff_decision: RouteDispatcher
    _dispatch_handoff_responses: RouteDispatcher
    _dispatch_handoff_review: RouteDispatcher
    _dispatch_vault_operations_archive: RouteDispatcher
    _dispatch_vault_operations_custody: RouteDispatcher
    _optional_json_body: JsonBodyReader
    _read_json_body: JsonBodyReader
    _send_error: ErrorSender
    _send_json: JsonSender
    service: ProgramServicePort
    unified_release_program_store: ProgramStorePort
    unified_release_program_operations_store: OperationsStorePort
    unified_release_program_handoff_store: HandoffStorePort
    unified_release_program_vault_store: VaultStorePort
    unified_release_program_vault_operations_store: VaultOperationsStorePort
    unified_release_program_continuity_store: ContinuityStorePort
    unified_release_program_continuity_distribution_store: ContinuityDistributionStorePort
    unified_release_program_continuity_acceptance_store: AcceptanceStorePort
    unified_release_program_continuity_acceptance_change_store: AcceptanceChangeStorePort
    unified_release_program_continuity_command_center_store: CommandCenterStorePort
    unified_release_program_continuity_command_center_signoff_store: CommandCenterSignoffStorePort
    unified_release_program_continuity_command_center_acceptance_store: ReceiverAcceptanceStorePort
    unified_release_program_continuity_command_center_acceptance_change_store: ReceiverAcceptanceChangeStorePort
