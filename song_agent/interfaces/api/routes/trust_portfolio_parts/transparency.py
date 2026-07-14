from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustPortfolioTransparencyRoutes:
    def _dispatch_portfolio_transparency(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-attestation-transparency':
            query = parse_qs(urlparse(self.path).query)
            query_profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                feed = self.release_portfolio_governance_attestation_transparency_store.read_feed(portfolio_id, profile=query_profile, default={})
                report = self.release_portfolio_governance_attestation_transparency_store.read_report(portfolio_id, profile=query_profile, default={})
                summary = portfolio_governance_attestation_transparency_summary(feed) if feed else {'status': 'missing', 'profile': query_profile}
                if feed:
                    summary['stale'] = self.release_portfolio_governance_attestation_transparency_store.feed_is_stale(portfolio_id, feed, profile=query_profile)
                verification_path = self.release_portfolio_governance_attestation_transparency_store.verification_report_path(portfolio_id, query_profile)
                verification = read_json(verification_path) if verification_path.exists() else {}
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'profile': query_profile, 'feed': feed, 'report': report, 'summary': summary, 'verification': verification})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                feed = self.release_portfolio_governance_attestation_transparency_store.refresh_feed(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'feed': feed, 'summary': portfolio_governance_attestation_transparency_summary(feed)}, status=HTTPStatus.CREATED)
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                manifest = self.release_portfolio_governance_attestation_transparency_store.export_transparency(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('current_public_state', {})}, status=HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                zip_info = self.release_portfolio_governance_attestation_transparency_store.build_zip(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                profile = str(payload.get('profile') or query_profile)
                report = verify_release_portfolio_governance_attestation_transparency(self.release_portfolio_governance_attestation_transparency_store.zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_current=bool(payload.get('require_current', False)), require_accepted_evidence=bool(payload.get('require_accepted_evidence', False)), require_no_revoked_current=bool(payload.get('require_no_revoked_current', False)), require_contiguous_chain=bool(payload.get('require_contiguous_chain', False)))
                write_release_portfolio_governance_attestation_transparency_verification_report(report, self.release_portfolio_governance_attestation_transparency_store.verification_report_path(portfolio_id, profile))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report})
                return True
            if subaction == 'notices' and len(parts) == 3:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                notices = self.release_portfolio_governance_attestation_transparency_store.list_notices(portfolio_id, profile=query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'notices': notices})
                return True
            if subaction == 'notices' and len(parts) == 4:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                notice = self.release_portfolio_governance_attestation_transparency_store.get_notice(portfolio_id, parts[3], profile=query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'notice': notice})
                return True
            self._send_error(HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Attestation Transparency route not found.')
            return True
        return False
