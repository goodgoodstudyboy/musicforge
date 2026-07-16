from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustPortfolioVaultRoutes:
    def _dispatch_portfolio_vault(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-evidence-vault':
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_evidence_vault_store.read_report(portfolio_id, default={})
                stale = self.release_portfolio_governance_evidence_vault_store.report_is_stale(portfolio_id, report) if report else False
                summary = _interfaces_api_runtime.portfolio_governance_evidence_vault_summary(report) if report else {'status': 'missing'}
                summary['stale'] = stale
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'package_index': self.release_portfolio_governance_evidence_vault_store.read_package_index(portfolio_id, default={}), 'verification_index': self.release_portfolio_governance_evidence_vault_store.read_verification_index(portfolio_id, default={}), 'chain_of_custody': self.release_portfolio_governance_evidence_vault_store.read_chain_of_custody(portfolio_id, default={}), 'verification': _interfaces_api_runtime.read_json(self.release_portfolio_governance_evidence_vault_store.verification_report_path(portfolio_id)) if self.release_portfolio_governance_evidence_vault_store.verification_report_path(portfolio_id).exists() else {}, 'summary': summary, 'stale': stale})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.release_portfolio_governance_evidence_vault_store.refresh_report(portfolio_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'report': report, 'summary': _interfaces_api_runtime.portfolio_governance_evidence_vault_summary(report)})
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                manifest = self.release_portfolio_governance_evidence_vault_store.export_vault(portfolio_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                zip_info = self.release_portfolio_governance_evidence_vault_store.build_zip(portfolio_id, now=_interfaces_api_runtime._utc_now())
                manifest = self.release_portfolio_governance_evidence_vault_store.read_export_manifest(portfolio_id)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info, 'summary': manifest.get('summary', {})})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                report = _interfaces_api_runtime.verify_release_portfolio_governance_evidence_vault_package(self.release_portfolio_governance_evidence_vault_store.zip_path(portfolio_id), strict=bool(payload.get('strict', False)), deep=bool(payload.get('deep', False)), require_final_board=bool(payload.get('require_final_board', False)), require_reviewer_pack=bool(payload.get('require_reviewer_pack', False)), require_audit=bool(payload.get('require_audit', False)), require_archives=bool(payload.get('require_archives', False)), require_queue_packages=bool(payload.get('require_queue_packages', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_evidence_vault_verification_report(report, self.release_portfolio_governance_evidence_vault_store.verification_report_path(portfolio_id))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report, 'summary': _interfaces_api_runtime.portfolio_governance_evidence_vault_summary(self.release_portfolio_governance_evidence_vault_store.read_report(portfolio_id, default={}))})
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Evidence Vault route not found.')
            return True
        return False
