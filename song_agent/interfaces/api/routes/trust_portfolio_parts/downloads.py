from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustPortfolioDownloadsRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_downloads(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-audit.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_audit_store.zip_path(portfolio_id), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-audit.zip')
            return True
        if action == 'governance-reviewer-pack.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_reviewer_pack_store.zip_path(portfolio_id), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-reviewer-pack.zip')
            return True
        if action == 'governance-final-board.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_final_board_store.archive_zip_path(portfolio_id), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-final-board-archive.zip')
            return True
        if action == 'governance-evidence-vault.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_evidence_vault_store.zip_path(portfolio_id), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-evidence-vault.zip')
            return True
        if action == 'governance-attestation.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_attestation_store.zip_path(portfolio_id, profile), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-public-attestation.zip')
            return True
        if action == 'governance-attestation-registry.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_attestation_registry_store.zip_path(portfolio_id, profile), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-attestation-registry.zip')
            return True
        if action == 'governance-attestation-portal.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_attestation_portal_store.zip_path(portfolio_id, profile), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-attestation-portal.zip')
            return True
        if action == 'governance-attestation-portal-review-pack.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_attestation_portal_review_store.pack_zip_path(portfolio_id, profile), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-attestation-portal-review-pack.zip')
            return True
        if action == 'governance-attestation-accepted-evidence.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_attestation_accepted_evidence_store.zip_path(portfolio_id, profile), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-attestation-accepted-evidence.zip')
            return True
        if action == 'governance-attestation-transparency.zip' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_governance_attestation_transparency_store.zip_path(portfolio_id, profile), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-governance-attestation-transparency.zip')
            return True
        if action in {'governance-attestation-transparency-acknowledgement-pack.zip', 'governance-attestation-transparency-acknowledgement-evidence.zip'} and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            self.release_portfolio_audit_store.portfolio_store.get_portfolio(portfolio_id)
            if action.endswith('pack.zip'):
                path = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_zip_path(portfolio_id, profile)
                filename = f'musicforge-{portfolio_id}-portfolio-governance-attestation-transparency-acknowledgement-pack.zip'
            else:
                path = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_zip_path(portfolio_id, profile)
                filename = f'musicforge-{portfolio_id}-portfolio-governance-attestation-transparency-acknowledgement-evidence.zip'
            self._send_file(path, 'application/zip', filename=filename)
            return True
        return False
