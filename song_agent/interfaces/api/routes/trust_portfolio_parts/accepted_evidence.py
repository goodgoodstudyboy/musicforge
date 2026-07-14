from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class TrustPortfolioAcceptedEvidenceRoutes:
    def _dispatch_portfolio_accepted_evidence(self, method, parts, portfolio_id, action) -> bool:
        if action == 'governance-attestation-accepted-evidence':
            query = parse_qs(urlparse(self.path).query)
            query_profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                evidence = self.release_portfolio_governance_attestation_accepted_evidence_store.read_evidence(portfolio_id, profile=query_profile, default={})
                summary = portfolio_governance_attestation_accepted_evidence_summary(evidence) if evidence else {'status': 'missing', 'external_review_status': 'missing', 'profile': query_profile}
                if evidence:
                    summary['stale'] = self.release_portfolio_governance_attestation_accepted_evidence_store.evidence_is_stale(portfolio_id, evidence, profile=query_profile)
                verification_path = self.release_portfolio_governance_attestation_accepted_evidence_store.verification_report_path(portfolio_id, query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'profile': query_profile, 'accepted_evidence': evidence, 'summary': summary, 'verification': read_json(verification_path) if verification_path.exists() else {}})
                return True
            subaction = parts[2] if len(parts) > 2 else ''
            if subaction == 'refresh' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                evidence = self.release_portfolio_governance_attestation_accepted_evidence_store.refresh_evidence(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'accepted_evidence': evidence, 'summary': portfolio_governance_attestation_accepted_evidence_summary(evidence)}, status=HTTPStatus.CREATED)
                return True
            if subaction == 'export' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                manifest = self.release_portfolio_governance_attestation_accepted_evidence_store.export_evidence(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest, 'summary': manifest.get('public_summary', {})}, status=HTTPStatus.CREATED)
                return True
            if subaction == 'zip' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                zip_info = self.release_portfolio_governance_attestation_accepted_evidence_store.build_zip(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info})
                return True
            if subaction == 'verify' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                profile = str(payload.get('profile') or query_profile)
                report = verify_release_portfolio_governance_attestation_accepted_evidence(self.release_portfolio_governance_attestation_accepted_evidence_store.zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_current=bool(payload.get('require_current', False)))
                write_release_portfolio_governance_attestation_accepted_evidence_verification_report(report, self.release_portfolio_governance_attestation_accepted_evidence_store.verification_report_path(portfolio_id, profile))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report})
                return True
            if subaction == 'archive' and len(parts) == 3:
                if method != 'POST':
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                evidence = self.release_portfolio_governance_attestation_accepted_evidence_store.archive_evidence(portfolio_id, payload, now=_utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'accepted_evidence': evidence, 'summary': portfolio_governance_attestation_accepted_evidence_summary(evidence)})
                return True
            self._send_error(HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Attestation Accepted Evidence route not found.')
            return True
        return False
