from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustPortfolioPortalRoutes:
    def _dispatch_portfolio_portal(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-attestation-portal':
            query = parse_qs(urlparse(self.path).query)
            query_profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_attestation_portal_store.read_report(portfolio_id, profile=query_profile, default={})
                verification_path = self.release_portfolio_governance_attestation_portal_store.verification_report_path(portfolio_id, query_profile)
                summary = portfolio_governance_attestation_portal_summary(report) if report else {'status': 'missing', 'profile': query_profile}
                if report:
                    summary['stale'] = self.release_portfolio_governance_attestation_portal_store.report_is_stale(portfolio_id, report, profile=query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'profile': query_profile, 'report': report, 'verification': read_json(verification_path) if verification_path.exists() else {}, 'summary': summary})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                report = self.release_portfolio_governance_attestation_portal_store.refresh_report(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': portfolio_governance_attestation_portal_summary(report)})
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                manifest = self.release_portfolio_governance_attestation_portal_store.export_portal(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest}, status=HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                zip_info = self.release_portfolio_governance_attestation_portal_store.build_zip(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                profile = str(payload.get('profile') or query_profile)
                report = verify_release_portfolio_governance_attestation_portal(self.release_portfolio_governance_attestation_portal_store.zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_current=bool(payload.get('require_current', False)), require_registry=bool(payload.get('require_registry', False)), require_attestation=bool(payload.get('require_attestation', False)), require_accepted_evidence=bool(payload.get('require_accepted_evidence', False)))
                write_release_portfolio_governance_attestation_portal_verification_report(report, self.release_portfolio_governance_attestation_portal_store.verification_report_path(portfolio_id, profile))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'verification_summary': portfolio_governance_attestation_portal_verification_summary(report)})
                return True
            self._send_error(HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Attestation Portal route not found.')
            return True
        return False
