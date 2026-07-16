from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustPortfolioReviewerRoutes:
    def _dispatch_portfolio_reviewer(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-reviewer-pack':
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_reviewer_pack_store.read_report(portfolio_id, default={})
                stale = self.release_portfolio_governance_reviewer_pack_store.report_is_stale(portfolio_id, report) if report else False
                summary = _interfaces_api_runtime.portfolio_governance_reviewer_pack_summary(report) if report else {'status': 'missing'}
                summary['stale'] = stale
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'retrospective': self.release_portfolio_governance_reviewer_pack_store.read_retrospective(portfolio_id, default={}), 'evidence_index': self.release_portfolio_governance_reviewer_pack_store.read_evidence_index(portfolio_id, default={}), 'timeline': self.release_portfolio_governance_reviewer_pack_store.read_timeline(portfolio_id, default={}), 'summary': summary, 'stale': stale})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_reviewer_pack_store.refresh(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': _interfaces_api_runtime.portfolio_governance_reviewer_pack_summary(report)})
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                manifest = self.release_portfolio_governance_reviewer_pack_store.export_pack(portfolio_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                zip_info = self.release_portfolio_governance_reviewer_pack_store.build_zip(portfolio_id, now=_interfaces_api_runtime._utc_now())
                manifest = self.release_portfolio_governance_reviewer_pack_store.read_export_manifest(portfolio_id)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info, 'summary': manifest.get('summary', {})})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                report = _interfaces_api_runtime.verify_release_portfolio_governance_reviewer_pack(self.release_portfolio_governance_reviewer_pack_store.zip_path(portfolio_id), strict=bool(payload.get('strict', False)), require_audit=bool(payload.get('require_audit', False)), require_signed=bool(payload.get('require_signed', False)), require_archives=bool(payload.get('require_archives', False)), require_no_force=bool(payload.get('require_no_force', False)), require_reset_cr_causality=bool(payload.get('require_reset_cr_causality', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_reviewer_pack_verification_report(report, self.release_portfolio_governance_reviewer_pack_store.verification_report_path(portfolio_id))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'summary': _interfaces_api_runtime.release_portfolio_governance_reviewer_pack_verification_summary(report)})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Reviewer Pack route not found.')
            return True
        return False
