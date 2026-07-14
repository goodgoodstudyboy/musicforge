from __future__ import annotations

from http import HTTPStatus
from typing import Any, Protocol
from song_agent.domains.program.unified_release_program import (
    UnifiedReleaseProgramError,
    UnifiedReleaseProgramNotFoundError,
    UnifiedReleaseProgramStateError,
)
from song_agent.domains.program.unified_release_program_continuity import (
    UnifiedReleaseProgramContinuityError,
    UnifiedReleaseProgramContinuityNotFoundError,
    UnifiedReleaseProgramContinuityStateError,
)
from song_agent.domains.program.unified_release_program_continuity_acceptance import (
    UnifiedReleaseProgramContinuityAcceptanceError,
    UnifiedReleaseProgramContinuityAcceptanceNotFoundError,
    UnifiedReleaseProgramContinuityAcceptanceStateError,
)
from song_agent.domains.program.unified_release_program_continuity_acceptance_change import (
    UnifiedReleaseProgramContinuityAcceptanceChangeError,
    UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError,
    UnifiedReleaseProgramContinuityAcceptanceChangeStateError,
)
from song_agent.domains.program.unified_release_program_continuity_command_center import (
    UnifiedReleaseProgramContinuityCommandCenterError,
    UnifiedReleaseProgramContinuityCommandCenterStateError,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_acceptance_change import (
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError,
)
from song_agent.domains.program.unified_release_program_continuity_command_center_signoff import (
    UnifiedReleaseProgramContinuityCommandCenterSignoffError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffStateError,
)
from song_agent.domains.program.unified_release_program_continuity_distribution import (
    UnifiedReleaseProgramContinuityDistributionError,
    UnifiedReleaseProgramContinuityDistributionNotFoundError,
    UnifiedReleaseProgramContinuityDistributionStateError,
)
from song_agent.domains.program.unified_release_program_handoff import (
    UnifiedReleaseProgramHandoffError,
    UnifiedReleaseProgramHandoffNotFoundError,
    UnifiedReleaseProgramHandoffStateError,
)
from song_agent.domains.program.unified_release_program_operations import (
    UnifiedReleaseProgramOperationsError,
    UnifiedReleaseProgramOperationsNotFoundError,
    UnifiedReleaseProgramOperationsStateError,
)
from song_agent.domains.program.unified_release_program_vault import (
    UnifiedReleaseProgramVaultError,
    UnifiedReleaseProgramVaultNotFoundError,
    UnifiedReleaseProgramVaultStateError,
)
from song_agent.domains.program.unified_release_program_vault_operations import (
    UnifiedReleaseProgramVaultOperationsError,
    UnifiedReleaseProgramVaultOperationsNotFoundError,
    UnifiedReleaseProgramVaultOperationsStateError,
)

from .http_routes.root import ProgramRootHttpRoutes
from .http_routes.core import ProgramCoreHttpRoutes
from .http_routes.handoff import ProgramHandoffHttpRoutes
from .http_routes.vault import ProgramVaultHttpRoutes
from .http_routes.vault_operations import ProgramVaultOperationsHttpRoutes
from .http_routes.continuity import ProgramContinuityHttpRoutes
from .http_routes.continuity_kit import ProgramContinuityKitHttpRoutes
from .http_routes.acceptance import ProgramAcceptanceHttpRoutes
from .http_routes.acceptance_change import ProgramAcceptanceChangeHttpRoutes
from .http_routes.command_center import ProgramCommandCenterHttpRoutes
from .http_routes.command_center_signoff import ProgramCommandCenterSignoffHttpRoutes
from .http_routes.receiver_acceptance import ProgramReceiverAcceptanceHttpRoutes
from .http_routes.receiver_acceptance_change import ProgramReceiverAcceptanceChangeHttpRoutes
from .http_routes.operations import ProgramOperationsHttpRoutes
from .http_routes.download import ProgramDownloadHttpRoutes

class ProgramComponentProvider(Protocol):
    def component(self, component: str) -> Any: ...

_COMPONENT_ATTRIBUTES = {
    "unified_release_program_store": "program",
    "unified_release_program_operations_store": "operations",
    "unified_release_program_handoff_store": "handoff",
    "unified_release_program_vault_store": "vault",
    "unified_release_program_vault_operations_store": "vault_operations",
    "unified_release_program_continuity_store": "continuity",
    "unified_release_program_continuity_distribution_store": "continuity_distribution",
    "unified_release_program_continuity_acceptance_store": "continuity_acceptance",
    "unified_release_program_continuity_acceptance_change_store": "continuity_acceptance_change",
    "unified_release_program_continuity_command_center_store": "command_center",
    "unified_release_program_continuity_command_center_signoff_store": "command_center_signoff",
    "unified_release_program_continuity_command_center_acceptance_store": "receiver_acceptance",
    "unified_release_program_continuity_command_center_acceptance_change_store": "receiver_acceptance_change",
}

_NOT_FOUND_ERRORS = (
    UnifiedReleaseProgramVaultNotFoundError,
    UnifiedReleaseProgramVaultOperationsNotFoundError,
    UnifiedReleaseProgramContinuityNotFoundError,
    UnifiedReleaseProgramContinuityDistributionNotFoundError,
    UnifiedReleaseProgramContinuityAcceptanceNotFoundError,
    UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError,
    UnifiedReleaseProgramHandoffNotFoundError,
    UnifiedReleaseProgramOperationsNotFoundError,
    UnifiedReleaseProgramNotFoundError,
)
_STATE_ERRORS = (
    UnifiedReleaseProgramVaultStateError,
    UnifiedReleaseProgramVaultOperationsStateError,
    UnifiedReleaseProgramContinuityStateError,
    UnifiedReleaseProgramContinuityDistributionStateError,
    UnifiedReleaseProgramContinuityAcceptanceStateError,
    UnifiedReleaseProgramContinuityAcceptanceChangeStateError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffStateError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError,
    UnifiedReleaseProgramContinuityCommandCenterStateError,
    UnifiedReleaseProgramHandoffStateError,
    UnifiedReleaseProgramOperationsStateError,
    UnifiedReleaseProgramStateError,
)
_PROGRAM_ERRORS = (
    UnifiedReleaseProgramVaultError,
    UnifiedReleaseProgramVaultOperationsError,
    UnifiedReleaseProgramContinuityError,
    UnifiedReleaseProgramContinuityDistributionError,
    UnifiedReleaseProgramContinuityAcceptanceError,
    UnifiedReleaseProgramContinuityAcceptanceChangeError,
    UnifiedReleaseProgramContinuityCommandCenterSignoffError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceError,
    UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError,
    UnifiedReleaseProgramContinuityCommandCenterError,
    UnifiedReleaseProgramHandoffError,
    UnifiedReleaseProgramOperationsError,
    UnifiedReleaseProgramError,
)
_HANDLED_ERRORS = _NOT_FOUND_ERRORS + _STATE_ERRORS + _PROGRAM_ERRORS

class ProgramHttpApplication(ProgramRootHttpRoutes, ProgramCoreHttpRoutes, ProgramHandoffHttpRoutes, ProgramVaultHttpRoutes, ProgramVaultOperationsHttpRoutes, ProgramContinuityHttpRoutes, ProgramContinuityKitHttpRoutes, ProgramAcceptanceHttpRoutes, ProgramAcceptanceChangeHttpRoutes, ProgramCommandCenterHttpRoutes, ProgramCommandCenterSignoffHttpRoutes, ProgramReceiverAcceptanceHttpRoutes, ProgramReceiverAcceptanceChangeHttpRoutes, ProgramOperationsHttpRoutes, ProgramDownloadHttpRoutes):
    def __init__(self, service: ProgramComponentProvider, port: object) -> None:
        self.service = service
        self.port = port

    def __getattr__(self, name: str) -> Any:
        component = _COMPONENT_ATTRIBUTES.get(name)
        if component is not None:
            return self.service.component(component)
        return getattr(self.port, name)

    def dispatch(self, method: str, path: str) -> None:
        try:
            self._dispatch_request(method, path)
        except _HANDLED_ERRORS as exc:
            self._send_error(self._error_status(exc), str(exc))

    def _dispatch_request(self, method: str, path: str) -> None:
        if self._dispatch_root(method, path):
            return
        prefix = '/api/unified-release-programs/'
        if not path.startswith(prefix):
            self._send_error(HTTPStatus.NOT_FOUND, 'Unified Release Program route not found.')
            return
        parts = path.removeprefix(prefix).strip('/').split('/')
        program_id = parts[0]
        tail = '/' + '/'.join(parts[1:]) if len(parts) > 1 else ''
        handlers = (
            self._dispatch_core,
            self._dispatch_handoff,
            self._dispatch_vault,
            self._dispatch_vault_operations,
            self._dispatch_continuity,
            self._dispatch_continuity_kit,
            self._dispatch_acceptance,
            self._dispatch_acceptance_change,
            self._dispatch_command_center,
            self._dispatch_command_center_signoff,
            self._dispatch_receiver_acceptance,
            self._dispatch_receiver_acceptance_change,
            self._dispatch_operations,
            self._dispatch_download,
        )
        if any(handler(method, program_id, tail) for handler in handlers):
            return
        self._send_error(HTTPStatus.NOT_FOUND, 'Unified Release Program route not found.')

    @staticmethod
    def _error_status(exc: Exception) -> HTTPStatus:
        if isinstance(exc, _NOT_FOUND_ERRORS):
            return HTTPStatus.NOT_FOUND
        if isinstance(exc, _STATE_ERRORS):
            return HTTPStatus.CONFLICT
        return HTTPStatus.BAD_REQUEST
