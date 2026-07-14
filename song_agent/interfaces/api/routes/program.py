from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from .program_parts.part_001 import ProgramRoutesPart001

from .program_parts.part_002 import ProgramRoutesPart002

from .program_parts.part_003 import ProgramRoutesPart003

from .program_ucc_parts.root import ProgramUccRootRoutes
from .program_ucc_parts.reviews import ProgramUccReviewsRoutes
from .program_ucc_parts.drifts import ProgramUccDriftsRoutes
from .program_ucc_parts.evidence_root import ProgramUccEvidence_RootRoutes
from .program_ucc_parts.evidence_detail import ProgramUccEvidence_DetailRoutes
from .program_ucc_parts.boards import ProgramUccBoardsRoutes
from .program_ucc_parts.core import ProgramUccCoreRoutes
from .program_ucc_parts.handoff import ProgramUccHandoffRoutes

class ProgramRoutes(ProgramRoutesPart001, ProgramRoutesPart002, ProgramRoutesPart003, ProgramUccRootRoutes, ProgramUccReviewsRoutes, ProgramUccDriftsRoutes, ProgramUccEvidence_RootRoutes, ProgramUccEvidence_DetailRoutes, ProgramUccBoardsRoutes, ProgramUccCoreRoutes, ProgramUccHandoffRoutes):
    def _handle_unified_command_centers_route(self, method: str, path: str) -> None:
        try:
            if self._dispatch_ucc_root(method, path):
                return
            prefix = '/api/unified-command-centers/'
            if not path.startswith(prefix):
                self._send_error(HTTPStatus.NOT_FOUND, 'Unified Command Center route not found.')
                return
            parts = path.removeprefix(prefix).strip('/').split('/')
            center_id = parts[0]
            tail = '/' + '/'.join(parts[1:]) if len(parts) > 1 else ''
            if self._dispatch_ucc_reviews(method, center_id, tail):
                return
            if self._dispatch_ucc_drifts(method, center_id, tail):
                return
            if self._dispatch_ucc_evidence_root(method, center_id, tail):
                return
            if self._dispatch_ucc_evidence_detail(method, center_id, tail):
                return
            if self._dispatch_ucc_boards(method, center_id, tail):
                return
            if self._dispatch_ucc_core(method, center_id, tail):
                return
            if self._dispatch_ucc_handoff(method, center_id, tail):
                return
            self._send_error(HTTPStatus.NOT_FOUND, 'Unified Command Center route not found.')
        except UnifiedCommandCenterNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (UnifiedCommandCenterSignoffNotFoundError,) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterContinuousReviewNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterDriftResponseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterEvidenceReviewNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterReviewerDecisionBoardNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except UnifiedCommandCenterStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (UnifiedCommandCenterSignoffStateError, UnifiedCommandCenterHandoffStateError, UnifiedCommandCenterContinuousReviewStateError, UnifiedCommandCenterDriftResponseStateError, UnifiedCommandCenterEvidenceReviewStateError, UnifiedCommandCenterReviewerDecisionBoardStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except UnifiedCommandCenterError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (UnifiedCommandCenterSignoffError, UnifiedCommandCenterHandoffError, UnifiedCommandCenterContinuousReviewError, UnifiedCommandCenterDriftResponseError, UnifiedCommandCenterEvidenceReviewError, UnifiedCommandCenterReviewerDecisionBoardError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
