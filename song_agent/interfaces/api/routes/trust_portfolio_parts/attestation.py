from __future__ import annotations

from song_agent.platform.contracts.documents import JsonDocument

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class TrustPortfolioAttestationRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_attestation(self, method: str, parts: list[str], portfolio_id: str, action: str) -> bool:
        if action == 'governance-attestation':
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            query_profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_attestation_store.read_report(portfolio_id, profile=query_profile, default={})
                stale = self.release_portfolio_governance_attestation_store.report_is_stale(portfolio_id, report, profile=query_profile) if report else False
                summary: JsonDocument = _interfaces_api_runtime.sanitize_metadata(
                    _interfaces_api_runtime.portfolio_governance_attestation_summary(report)
                    if report
                    else {"status": "missing", "profile": query_profile}
                )
                summary['stale'] = stale
                certificate = self.release_portfolio_governance_attestation_store.read_certificate(portfolio_id, profile=query_profile, default={})
                verification_path = self.release_portfolio_governance_attestation_store.verification_report_path(portfolio_id, query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'profile': query_profile, 'report': report, 'certificate': certificate, 'verification': _interfaces_api_runtime.read_json(verification_path) if verification_path.exists() else {}, 'summary': summary, 'stale': stale})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                report = self.release_portfolio_governance_attestation_store.refresh_report(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': _interfaces_api_runtime.portfolio_governance_attestation_summary(report)})
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                manifest = self.release_portfolio_governance_attestation_store.export_attestation(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                zip_info = self.release_portfolio_governance_attestation_store.build_zip(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                manifest = self.release_portfolio_governance_attestation_store.read_export_manifest(portfolio_id, profile=str(payload.get('profile') or 'public_summary'))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info, 'summary': manifest.get('summary', {})})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                profile = str(payload.get('profile') or 'public_summary')
                report = _interfaces_api_runtime.verify_release_portfolio_governance_attestation(self.release_portfolio_governance_attestation_store.zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_vault=bool(payload.get('require_vault', False)), require_final_board=bool(payload.get('require_final_board', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_attestation_verification_report(report, self.release_portfolio_governance_attestation_store.verification_report_path(portfolio_id, profile))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'summary': _interfaces_api_runtime.portfolio_governance_attestation_summary(self.release_portfolio_governance_attestation_store.read_report(portfolio_id, profile=profile, default={}))})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Public Attestation route not found.')
            return True
        return False
