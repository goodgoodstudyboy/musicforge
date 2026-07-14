from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustPortfolioPortalReviewRoutes:
    def _dispatch_portfolio_portal_review(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-attestation-portal-review':
            query = parse_qs(urlparse(self.path).query)
            query_profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                pack = self.release_portfolio_governance_attestation_portal_review_store.read_pack(portfolio_id, profile=query_profile, default={})
                summary = portfolio_governance_attestation_portal_review_pack_summary(pack) if pack else {'status': 'missing', 'profile': query_profile}
                if pack:
                    summary['stale'] = self.release_portfolio_governance_attestation_portal_review_store.pack_is_stale(portfolio_id, pack, profile=query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'profile': query_profile, 'review_pack': pack, 'summary': summary, 'responses': self.release_portfolio_governance_attestation_portal_review_store.list_responses(portfolio_id, profile=query_profile)})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'pack' and len(parts) >= 3:
                pack_action = parts[3] if len(parts) > 3 else ''
                if pack_action == 'refresh' and len(parts) == 4:
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    payload = self._optional_json_body()
                    payload.setdefault('profile', query_profile)
                    pack = self.release_portfolio_governance_attestation_portal_review_store.refresh_pack(portfolio_id, payload, now=_utc_now())
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'review_pack': pack, 'summary': portfolio_governance_attestation_portal_review_pack_summary(pack)})
                    return True
                if pack_action == 'export' and len(parts) == 4:
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    payload = self._optional_json_body()
                    payload.setdefault('profile', query_profile)
                    manifest = self.release_portfolio_governance_attestation_portal_review_store.export_pack(portfolio_id, payload, now=_utc_now())
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest}, status=HTTPStatus.CREATED)
                    return True
                if pack_action == 'zip' and len(parts) == 4:
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    payload = self._optional_json_body()
                    payload.setdefault('profile', query_profile)
                    zip_info = self.release_portfolio_governance_attestation_portal_review_store.build_pack_zip(portfolio_id, payload, now=_utc_now())
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info})
                    return True
                if pack_action == 'verify' and len(parts) == 4:
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    payload = self._optional_json_body()
                    profile = str(payload.get('profile') or query_profile)
                    report = verify_release_portfolio_governance_attestation_portal_review_pack(self.release_portfolio_governance_attestation_portal_review_store.pack_zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_current=bool(payload.get('require_current', False)))
                    write_release_portfolio_governance_attestation_portal_review_pack_verification_report(report, self.release_portfolio_governance_attestation_portal_review_store.pack_verification_report_path(portfolio_id, profile))
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report})
                    return True
            if subaction == 'responses' and len(parts) >= 3:
                if len(parts) == 3:
                    if method != 'GET':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'responses': self.release_portfolio_governance_attestation_portal_review_store.list_responses(portfolio_id, profile=query_profile)})
                    return True
                if parts[3] == 'import' and len(parts) == 4:
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    payload = self._read_json_body()
                    payload.setdefault('profile', query_profile)
                    imported = self.release_portfolio_governance_attestation_portal_review_store.import_response(portfolio_id, payload, now=_utc_now())
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, **imported}, status=HTTPStatus.CREATED)
                    return True
                response_id = parts[3]
                if len(parts) == 4:
                    if method != 'GET':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    response = self.release_portfolio_governance_attestation_portal_review_store.get_response(portfolio_id, response_id, profile=query_profile)
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'response': response, 'summary': portfolio_governance_attestation_portal_response_summary(response)})
                    return True
                if len(parts) == 5 and parts[4] == 'verify':
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    report = self.release_portfolio_governance_attestation_portal_review_store.verify_response(portfolio_id, response_id, profile=query_profile, now=_utc_now())
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report})
                    return True
                if len(parts) == 5 and parts[4] == 'create-change-request':
                    if method != 'POST':
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                        return True
                    result = self.release_portfolio_governance_attestation_portal_review_store.create_change_request(portfolio_id, response_id, self._optional_json_body(), profile=query_profile, now=_utc_now())
                    status = HTTPStatus.OK if result.get('existing') else HTTPStatus.CREATED
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, **result}, status=status)
                    return True
            self._send_error(HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Attestation Portal Review route not found.')
            return True
        return False
