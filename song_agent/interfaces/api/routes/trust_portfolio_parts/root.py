from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustPortfolioRootRoutes:
    def _dispatch_portfolio_root(self, method, tail) -> bool:
        if tail in {'', '/'}:
            if method == 'GET':
                query = parse_qs(urlparse(self.path).query)
                include_archived = str(query.get('include_archived', [''])[0]).lower() in {'1', 'true', 'yes'}
                portfolios = self.release_portfolio_audit_store.list_portfolios(include_archived=include_archived)
                self._send_json({'ok': True, 'portfolios': portfolios, 'summary': {'count': len(portfolios)}})
                return True
            if method == 'POST':
                portfolio = self.release_portfolio_audit_store.create(self._optional_json_body(), now=_utc_now())
                self._send_json({'ok': True, 'portfolio': portfolio, 'summary': {'portfolio_id': portfolio.get('portfolio_id'), 'status': portfolio.get('status')}}, status=HTTPStatus.CREATED)
                return True
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        return False
