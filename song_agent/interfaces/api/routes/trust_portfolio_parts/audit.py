from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustPortfolioAuditRoutes:
    def _dispatch_portfolio_audit(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-audit':
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_audit_store.read_report(portfolio_id, default={})
                stale = self.release_portfolio_governance_audit_store.report_is_stale(portfolio_id, report) if report else False
                summary = portfolio_governance_audit_summary(report) if report else {'status': 'missing'}
                summary['stale'] = stale
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': summary, 'stale': stale})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_audit_store.refresh(portfolio_id, self._optional_json_body(), now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': portfolio_governance_audit_summary(report)})
                return True
            if subaction == 'ledger' and len(parts) == 3:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                query = parse_qs(urlparse(self.path).query)
                limit_raw = str(query.get('limit', [''])[0] or '').strip()
                limit = max(0, int(limit_raw)) if limit_raw.isdigit() else 0
                entries = self.release_portfolio_governance_audit_store.read_ledger(portfolio_id)
                if limit:
                    entries = entries[-limit:]
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'entries': entries, 'summary': {'entry_count': len(entries)}})
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                manifest = self.release_portfolio_governance_audit_store.export_audit(portfolio_id, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('summary', {})}, status=HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                zip_info = self.release_portfolio_governance_audit_store.build_zip(portfolio_id, now=_utc_now())
                manifest = self.release_portfolio_governance_audit_store.read_export_manifest(portfolio_id)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info, 'summary': manifest.get('summary', {})})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                report = verify_release_portfolio_governance_audit_package(self.release_portfolio_governance_audit_store.zip_path(portfolio_id), strict=bool(payload.get('strict', False)), require_signed=bool(payload.get('require_signed', False)), require_archives=bool(payload.get('require_archives', False)), require_no_force=bool(payload.get('require_no_force', False)), require_reset_cr_causality=bool(payload.get('require_reset_cr_causality', False)))
                write_release_portfolio_governance_audit_verification_report(report, self.release_portfolio_governance_audit_store.verification_report_path(portfolio_id))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'summary': release_portfolio_governance_audit_verification_summary(report)})
                return True
            self._send_error(HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Audit route not found.')
            return True
        return False
