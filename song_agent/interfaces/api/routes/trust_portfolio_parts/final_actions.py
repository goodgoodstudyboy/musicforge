from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class TrustPortfolioFinalActionsRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_final_actions(self, method: str, parts: list[str], portfolio_id: str, action: str) -> bool:
        if action == 'governance-queues' and len(parts) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            queue = self.release_portfolio_governance_store.create_from_portfolio(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            status = _interfaces_api_runtime.HTTPStatus.OK if queue.get('existing') else _interfaces_api_runtime.HTTPStatus.CREATED
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'queue': queue, 'summary': _interfaces_api_runtime.queue_summary(queue)}, status=status)
            return True
        if action == 'export' and len(parts) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.release_portfolio_audit_store.export_portfolio(portfolio_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return True
        if action == 'export' and len(parts) == 3 and (parts[2] == 'zip'):
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            zip_info = self.release_portfolio_audit_store.build_zip(portfolio_id, now=_interfaces_api_runtime._utc_now())
            manifest = self.release_portfolio_audit_store.read_export_manifest(portfolio_id)
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info, 'summary': manifest.get('summary', {})})
            return True
        if action == 'verify' and len(parts) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            report = _interfaces_api_runtime.verify_release_portfolio_audit_package(self.release_portfolio_audit_store.zip_path(portfolio_id), strict=bool(payload.get('strict', False)), require_reviewer_packs=bool(payload.get('require_reviewer_packs', False)), require_audit=bool(payload.get('require_audit', False)), require_archive=bool(payload.get('require_archive', False)))
            _interfaces_api_runtime.write_release_portfolio_audit_verification_report(report, self.release_portfolio_audit_store.verification_report_path(portfolio_id))
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'summary': _interfaces_api_runtime.release_portfolio_audit_verification_summary(report)})
            return True
        if action == 'download' and len(parts) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            self._send_file(self.release_portfolio_audit_store.zip_path(portfolio_id), 'application/zip', filename=f'musicforge-{portfolio_id}-portfolio-audit.zip')
            return True
        if action == 'archive' and len(parts) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            portfolio = self.release_portfolio_audit_store.archive(portfolio_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'portfolio': portfolio, 'summary': {'status': portfolio.get('status')}})
            return True
        return False
