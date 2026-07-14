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
            if self._dispatch_root(method, path):
                return
            prefix = '/api/unified-release-programs/'
            if not path.startswith(prefix):
                self._send_error(HTTPStatus.NOT_FOUND, 'Unified Release Program route not found.')
                return
            parts = path.removeprefix(prefix).strip('/').split('/')
            program_id = parts[0]
            tail = '/' + '/'.join(parts[1:]) if len(parts) > 1 else ''
            if self._dispatch_core(method, program_id, tail):
                return
            if self._dispatch_handoff(method, program_id, tail):
                return
            if self._dispatch_vault(method, program_id, tail):
                return
            if self._dispatch_vault_operations(method, program_id, tail):
                return
            if self._dispatch_continuity(method, program_id, tail):
                return
            if self._dispatch_continuity_kit(method, program_id, tail):
                return
            if self._dispatch_acceptance(method, program_id, tail):
                return
            if self._dispatch_acceptance_change(method, program_id, tail):
                return
            if self._dispatch_command_center(method, program_id, tail):
                return
            if self._dispatch_command_center_signoff(method, program_id, tail):
                return
            if self._dispatch_receiver_acceptance(method, program_id, tail):
                return
            if self._dispatch_receiver_acceptance_change(method, program_id, tail):
                return
            if self._dispatch_operations(method, program_id, tail):
                return
            if self._dispatch_download(method, program_id, tail):
                return
            self._send_error(HTTPStatus.NOT_FOUND, 'Unified Release Program route not found.')
        except UnifiedReleaseProgramVaultNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramVaultStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramVaultError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramVaultOperationsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramVaultOperationsStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramVaultOperationsError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityDistributionNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityDistributionStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityDistributionError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceChangeNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceChangeStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityAcceptanceChangeError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterAcceptanceChangeError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramContinuityCommandCenterError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramHandoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramHandoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramHandoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramOperationsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramOperationsStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramOperationsError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except UnifiedReleaseProgramNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedReleaseProgramStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedReleaseProgramError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
