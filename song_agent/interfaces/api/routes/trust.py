from __future__ import annotations

from song_agent.interfaces.api.route_contexts.core import CoreRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

from .trust_parts.trust_operations import TrustRoutesTrustOperations

from .trust_parts.trust_operations_assurance_watch import TrustRoutesTrustOperationsAssuranceWatch

from .trust_parts.trust_operations_knowledge import TrustRoutesTrustOperationsKnowledge

from .trust_parts.trust_operations_incidents import TrustRoutesTrustOperationsIncidents

from .trust_parts.public_trust_centers import TrustRoutesPublicTrustCenters

from .trust_parts.public_trust_center_acceptance_board import TrustRoutesPublicTrustCenterAcceptanceBoard

from .trust_parts.release_portfolio_governance_queues import TrustRoutesReleasePortfolioGovernanceQueues

from .trust_portfolio_parts.root import TrustPortfolioRootRoutes
from .trust_portfolio_parts.detail import TrustPortfolioDetailRoutes
from .trust_portfolio_parts.downloads import TrustPortfolioDownloadsRoutes
from .trust_portfolio_parts.audit import TrustPortfolioAuditRoutes
from .trust_portfolio_parts.reviewer import TrustPortfolioReviewerRoutes
from .trust_portfolio_parts.final_board import TrustPortfolioFinalBoardRoutes
from .trust_portfolio_parts.vault import TrustPortfolioVaultRoutes
from .trust_portfolio_parts.attestation import TrustPortfolioAttestationRoutes
from .trust_portfolio_parts.registry import TrustPortfolioRegistryRoutes
from .trust_portfolio_parts.portal import TrustPortfolioPortalRoutes
from .trust_portfolio_parts.portal_review import TrustPortfolioPortalReviewRoutes
from .trust_portfolio_parts.accepted_evidence import TrustPortfolioAcceptedEvidenceRoutes
from .trust_portfolio_parts.transparency import TrustPortfolioTransparencyRoutes
from .trust_portfolio_parts.acknowledgement import TrustPortfolioAcknowledgementRoutes
from .trust_portfolio_parts.final_actions import TrustPortfolioFinalActionsRoutes

class TrustRoutes(TrustRoutesTrustOperations, TrustRoutesTrustOperationsAssuranceWatch, TrustRoutesTrustOperationsKnowledge, TrustRoutesTrustOperationsIncidents, TrustRoutesPublicTrustCenters, TrustRoutesPublicTrustCenterAcceptanceBoard, TrustRoutesReleasePortfolioGovernanceQueues, TrustPortfolioRootRoutes, TrustPortfolioDetailRoutes, TrustPortfolioDownloadsRoutes, TrustPortfolioAuditRoutes, TrustPortfolioReviewerRoutes, TrustPortfolioFinalBoardRoutes, TrustPortfolioVaultRoutes, TrustPortfolioAttestationRoutes, TrustPortfolioRegistryRoutes, TrustPortfolioPortalRoutes, TrustPortfolioPortalReviewRoutes, TrustPortfolioAcceptedEvidenceRoutes, TrustPortfolioTransparencyRoutes, TrustPortfolioAcknowledgementRoutes, TrustPortfolioFinalActionsRoutes, CoreRouteContext):
    def _handle_release_portfolio_audits(self, method: str, path: str) -> None:
        try:
            prefix = '/api/release-portfolio-audits'
            tail = path[len(prefix):]
            if self._dispatch_portfolio_root(method, tail):
                return
            parts = [part for part in tail.strip('/').split('/') if part]
            if not parts:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Audit route not found.')
                return
            portfolio_id = parts[0]
            action = parts[1] if len(parts) > 1 else ''
            if self._dispatch_portfolio_detail(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_downloads(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_audit(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_reviewer(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_final_board(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_vault(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_attestation(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_registry(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_portal(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_portal_review(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_accepted_evidence(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_transparency(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_acknowledgement(method, parts, portfolio_id, action):
                return
            if self._dispatch_portfolio_final_actions(method, parts, portfolio_id, action):
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Audit route not found.')
        except (
            _interfaces_api_runtime.ReleasePortfolioAuditNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAuditNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceReviewerPackNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceFinalBoardNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceEvidenceVaultNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationRegistryNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationPortalNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationPortalReviewNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationAcceptedEvidenceNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationTransparencyNotFoundError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementNotFoundError,
            FileNotFoundError,
        ) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (
            _interfaces_api_runtime.ReleasePortfolioAuditStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAuditStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceReviewerPackStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceFinalBoardStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceEvidenceVaultStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationRegistryStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationPortalStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationPortalReviewStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationAcceptedEvidenceStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationTransparencyStateError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementStateError,
        ) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (
            _interfaces_api_runtime.ReleasePortfolioAuditError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAuditError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceReviewerPackError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceFinalBoardError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceEvidenceVaultError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationRegistryError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationPortalError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationPortalReviewError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationAcceptedEvidenceError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationTransparencyError,
            _interfaces_api_runtime.ReleasePortfolioGovernanceAttestationTransparencyAcknowledgementError,
        ) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
