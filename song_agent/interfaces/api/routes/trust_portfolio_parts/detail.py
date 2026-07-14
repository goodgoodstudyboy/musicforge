from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustPortfolioDetailRoutes:
    def _dispatch_portfolio_detail(self, method, parts, portfolio_id, action) -> bool:
        if len(parts) == 1:
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            portfolio = self.release_portfolio_audit_store.get_portfolio(portfolio_id)
            report = self.release_portfolio_audit_store.read_report(portfolio_id, default={})
            stale = self.release_portfolio_audit_store.report_is_stale(portfolio_id, report) if report else False
            summary = portfolio_audit_summary(report) if report else {'status': 'missing'}
            summary['stale'] = stale
            self._send_json({'ok': True, 'portfolio': portfolio, 'report': report, 'summary': summary, 'stale': stale})
            return True
        if action == 'refresh' and len(parts) == 2:
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.release_portfolio_audit_store.refresh(portfolio_id, self._optional_json_body(), now=_utc_now())
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': portfolio_audit_summary(report)})
            return True
        if action == 'report' and len(parts) == 2:
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.release_portfolio_audit_store.read_report(portfolio_id, default={})
            stale = self.release_portfolio_audit_store.report_is_stale(portfolio_id, report) if report else False
            summary = portfolio_audit_summary(report) if report else {'status': 'missing'}
            summary['stale'] = stale
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': summary, 'stale': stale})
            return True
        if action == 'trends' and len(parts) == 2:
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            trend = self.release_portfolio_audit_store.read_trend_report(portfolio_id, default={})
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'trend_report': trend, 'summary': {'status': trend.get('status') or 'missing', 'finding_count': len(trend.get('trend_findings', []) if isinstance(trend.get('trend_findings'), list) else [])}})
            return True
        if action == 'risks' and len(parts) == 2:
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            risks = self.release_portfolio_audit_store.read_risk_register(portfolio_id, default={})
            self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'risk_register': risks, 'summary': {'risk_count': len(risks.get('risks', []) if isinstance(risks.get('risks'), list) else [])}})
            return True
        return False
