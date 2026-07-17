from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust_portfolio import TrustPortfolioRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustPortfolioFinalBoardRoutes(TrustPortfolioRouteContext):
    def _dispatch_portfolio_final_board(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-final-board':
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_final_board_store.read_report(portfolio_id, default={})
                signoff = self.release_portfolio_governance_final_board_store.read_signoff(portfolio_id, default={})
                stale = self.release_portfolio_governance_final_board_store.report_is_stale(portfolio_id, report) if report else False
                summary = _interfaces_api_runtime.sanitize_metadata(_interfaces_api_runtime.portfolio_governance_final_board_summary(report) if report else {'status': 'missing'})
                summary['stale'] = stale
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'signoff': signoff, 'signoff_summary': self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=signoff) if signoff else _interfaces_api_runtime.portfolio_governance_final_board_signoff_summary(signoff), 'reviewer_responses': self.release_portfolio_governance_final_board_store.list_reviewer_responses(portfolio_id), 'change_requests': self.release_portfolio_governance_final_board_store.list_change_requests(portfolio_id), 'verification': _interfaces_api_runtime.read_json(self.release_portfolio_governance_final_board_store.verification_report_path(portfolio_id)) if self.release_portfolio_governance_final_board_store.verification_report_path(portfolio_id).exists() else {}, 'summary': summary, 'stale': stale})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_final_board_store.refresh_report(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': _interfaces_api_runtime.portfolio_governance_final_board_summary(report)})
                return True
            if subaction == 'reviewer-responses' and len(parts) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                responses = self.release_portfolio_governance_final_board_store.list_reviewer_responses(portfolio_id)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'reviewer_responses': responses, 'summary': {'count': len(responses)}})
                return True
            if subaction == 'reviewer-responses' and len(parts) == 4 and (parts[3] == 'import'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                response = self.release_portfolio_governance_final_board_store.import_reviewer_response(portfolio_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                report = self.release_portfolio_governance_final_board_store.refresh_report(portfolio_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'response': response, 'report': report, 'summary': _interfaces_api_runtime.portfolio_governance_final_board_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            if subaction == 'signoff' and len(parts) == 3:
                if method == 'GET':
                    signoff = self.release_portfolio_governance_final_board_store.read_signoff(portfolio_id, default={})
                    report = self.release_portfolio_governance_final_board_store.read_report(portfolio_id, default={})
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'signoff': signoff, 'summary': self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=signoff), 'report_summary': _interfaces_api_runtime.portfolio_governance_final_board_summary(report)})
                    return True
                if method == 'POST':
                    signoff = self.release_portfolio_governance_final_board_store.signoff(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'signoff': signoff, 'summary': self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=signoff)})
                    return True
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            if subaction == 'signoff' and len(parts) == 4 and (parts[3] == 'reset'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                reset = self.release_portfolio_governance_final_board_store.reset_signoff(portfolio_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'signoff': reset, 'summary': self.release_portfolio_governance_final_board_store.signoff_summary(portfolio_id, signoff=reset)})
                return True
            if subaction == 'change-requests' and len(parts) == 3:
                if method == 'GET':
                    items = self.release_portfolio_governance_final_board_store.list_change_requests(portfolio_id)
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'change_requests': items, 'summary': {'count': len(items)}})
                    return True
                if method == 'POST':
                    item = self.release_portfolio_governance_final_board_store.create_change_request(portfolio_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'change_request': item}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return True
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            if subaction == 'change-requests' and len(parts) == 5 and (parts[4] in {'approve', 'reject'}):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                item = self.release_portfolio_governance_final_board_store.update_change_request_status(portfolio_id, parts[3], parts[4], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'change_request': item})
                return True
            if subaction == 'archive' and len(parts) == 4 and (parts[3] == 'export'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                manifest = self.release_portfolio_governance_final_board_store.export_archive(portfolio_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('final_board_signoff', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            if subaction == 'archive' and len(parts) == 4 and (parts[3] == 'zip'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                zip_info = self.release_portfolio_governance_final_board_store.build_archive_zip(portfolio_id, now=_interfaces_api_runtime._utc_now())
                manifest = self.release_portfolio_governance_final_board_store.read_export_manifest(portfolio_id)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info, 'summary': manifest.get('final_board_signoff', {})})
                return True
            if subaction == 'archive' and len(parts) == 4 and (parts[3] == 'verify'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                report = _interfaces_api_runtime.verify_release_portfolio_governance_final_board_package(self.release_portfolio_governance_final_board_store.archive_zip_path(portfolio_id), strict=bool(payload.get('strict', False)), require_signed=bool(payload.get('require_signed', False)), require_reviewer_pack=bool(payload.get('require_reviewer_pack', False)), require_audit=bool(payload.get('require_audit', False)), require_archives=bool(payload.get('require_archives', False)), require_reviewer_response=bool(payload.get('require_reviewer_response', False)), require_no_force=bool(payload.get('require_no_force', False)), require_reset_cr_causality=bool(payload.get('require_reset_cr_causality', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_final_board_verification_report(report, self.release_portfolio_governance_final_board_store.verification_report_path(portfolio_id))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'summary': _interfaces_api_runtime.release_portfolio_governance_final_board_verification_summary(report)})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Final Board route not found.')
            return True
        return False
