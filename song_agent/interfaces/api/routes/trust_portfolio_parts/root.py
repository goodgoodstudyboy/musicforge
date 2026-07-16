from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustPortfolioRootRoutes:
    def _dispatch_portfolio_root(self, method, tail) -> bool:
        if tail in {'', '/'}:
            if method == 'GET':
                query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
                include_archived = str(query.get('include_archived', [''])[0]).lower() in {'1', 'true', 'yes'}
                portfolios = self.release_portfolio_audit_store.list_portfolios(include_archived=include_archived)
                self._send_json({'ok': True, 'portfolios': portfolios, 'summary': {'count': len(portfolios)}})
                return True
            if method == 'POST':
                portfolio = self.release_portfolio_audit_store.create(self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio': portfolio, 'summary': {'portfolio_id': portfolio.get('portfolio_id'), 'status': portfolio.get('status')}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        return False
