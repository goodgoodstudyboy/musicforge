from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

from .program_parts.program_application import ProgramRoutesProgramApplication

from .program_parts.unified_command_center_release_trains import ProgramRoutesUnifiedCommandCenterReleaseTrains

from .program_parts.unified_command_center_evidence_from_payload import ProgramRoutesUnifiedCommandCenterEvidenceFromPayload

from .program_ucc_parts.root import ProgramUccRootRoutes
from .program_ucc_parts.reviews import ProgramUccReviewsRoutes
from .program_ucc_parts.drifts import ProgramUccDriftsRoutes
from .program_ucc_parts.evidence_root import ProgramUccEvidence_RootRoutes
from .program_ucc_parts.evidence_detail import ProgramUccEvidence_DetailRoutes
from .program_ucc_parts.boards import ProgramUccBoardsRoutes
from .program_ucc_parts.core import ProgramUccCoreRoutes
from .program_ucc_parts.handoff import ProgramUccHandoffRoutes

class ProgramRoutes(ProgramRoutesProgramApplication, ProgramRoutesUnifiedCommandCenterReleaseTrains, ProgramRoutesUnifiedCommandCenterEvidenceFromPayload, ProgramUccRootRoutes, ProgramUccReviewsRoutes, ProgramUccDriftsRoutes, ProgramUccEvidence_RootRoutes, ProgramUccEvidence_DetailRoutes, ProgramUccBoardsRoutes, ProgramUccCoreRoutes, ProgramUccHandoffRoutes):
    def _handle_unified_command_centers_route(self, method: str, path: str) -> None:
        try:
            if self._dispatch_ucc_root(method, path):
                return
            prefix = '/api/unified-command-centers/'
            if not path.startswith(prefix):
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Unified Command Center route not found.')
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
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Unified Command Center route not found.')
        except _interfaces_api_runtime.UnifiedCommandCenterNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.UnifiedCommandCenterSignoffNotFoundError,) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterContinuousReviewNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterDriftResponseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterEvidenceReviewNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReviewerDecisionBoardNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.UnifiedCommandCenterSignoffStateError, _interfaces_api_runtime.UnifiedCommandCenterHandoffStateError, _interfaces_api_runtime.UnifiedCommandCenterContinuousReviewStateError, _interfaces_api_runtime.UnifiedCommandCenterDriftResponseStateError, _interfaces_api_runtime.UnifiedCommandCenterEvidenceReviewStateError, _interfaces_api_runtime.UnifiedCommandCenterReviewerDecisionBoardStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except (_interfaces_api_runtime.UnifiedCommandCenterSignoffError, _interfaces_api_runtime.UnifiedCommandCenterHandoffError, _interfaces_api_runtime.UnifiedCommandCenterContinuousReviewError, _interfaces_api_runtime.UnifiedCommandCenterDriftResponseError, _interfaces_api_runtime.UnifiedCommandCenterEvidenceReviewError, _interfaces_api_runtime.UnifiedCommandCenterReviewerDecisionBoardError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
