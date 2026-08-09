from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class TrustPortfolioRegistryRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_registry(self, method: str, parts: list[str], portfolio_id: str, action: str) -> bool:
        if action == 'governance-attestation-registry':
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            query_profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                registry = self.release_portfolio_governance_attestation_registry_store.read_registry(portfolio_id, profile=query_profile, default={})
                report = self.release_portfolio_governance_attestation_registry_store.read_report(portfolio_id, profile=query_profile, default={})
                verification_path = self.release_portfolio_governance_attestation_registry_store.verification_report_path(portfolio_id, query_profile)
                summary = _interfaces_api_runtime.portfolio_governance_attestation_registry_summary(registry) if registry else {'status': 'missing', 'profile': query_profile}
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'profile': query_profile, 'registry': registry, 'report': report, 'verification': _interfaces_api_runtime.read_json(verification_path) if verification_path.exists() else {}, 'summary': summary})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'register-current' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                result = self.release_portfolio_governance_attestation_registry_store.register_current_attestation(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                status = _interfaces_api_runtime.HTTPStatus.OK if result.get('existing') else _interfaces_api_runtime.HTTPStatus.CREATED
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'entry': result.get('entry'), 'registry': result.get('registry'), 'summary': _interfaces_api_runtime.portfolio_governance_attestation_registry_summary(result.get('registry', {})), 'existing': bool(result.get('existing'))}, status=status)
                return True
            if subaction == 'entries' and len(parts) == 5 and (parts[4] == 'publish'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                result = self.release_portfolio_governance_attestation_registry_store.publish_entry(portfolio_id, parts[3], payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'entry': result.get('entry'), 'registry': result.get('registry'), 'summary': _interfaces_api_runtime.portfolio_governance_attestation_registry_summary(result.get('registry', {}))})
                return True
            if subaction == 'entries' and len(parts) == 5 and (parts[4] == 'revoke'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                result = self.release_portfolio_governance_attestation_registry_store.revoke_entry(portfolio_id, parts[3], payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'entry': result.get('entry'), 'registry': result.get('registry'), 'summary': _interfaces_api_runtime.portfolio_governance_attestation_registry_summary(result.get('registry', {}))})
                return True
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                report = self.release_portfolio_governance_attestation_registry_store.refresh_report(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                registry = self.release_portfolio_governance_attestation_registry_store.read_registry(portfolio_id, profile=str(payload.get('profile') or 'public_summary'), default={})
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': _interfaces_api_runtime.portfolio_governance_attestation_registry_summary(registry)})
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                manifest = self.release_portfolio_governance_attestation_registry_store.export_registry(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                zip_info = self.release_portfolio_governance_attestation_registry_store.build_zip(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                profile = str(payload.get('profile') or query_profile)
                report = _interfaces_api_runtime.verify_release_portfolio_governance_attestation_registry(self.release_portfolio_governance_attestation_registry_store.zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_current=bool(payload.get('require_current', False)), require_published=bool(payload.get('require_published', False)), require_no_revoked_current=bool(payload.get('require_no_revoked_current', False)), require_accepted_evidence=bool(payload.get('require_accepted_evidence', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_attestation_registry_verification_report(report, self.release_portfolio_governance_attestation_registry_store.verification_report_path(portfolio_id, profile))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'verification_summary': _interfaces_api_runtime.portfolio_governance_attestation_registry_verification_summary(report)})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Attestation Registry route not found.')
            return True
        return False
