from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustPortfolioAcknowledgementRoutes:
    def _dispatch_portfolio_acknowledgement_part_01_actions_01(self, method, parts, portfolio_id, action, _split_state, query_profile, subaction):
        if subaction == 'pack' and len(parts) >= 4:
            pack_action = parts[3]
            if pack_action == 'refresh' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                pack = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.refresh_pack(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'pack': pack, 'summary': {'status': pack.get('status'), 'pack_id': pack.get('pack_id')}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, True)
            if pack_action == 'export' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                manifest = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.export_pack(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, True)
            if pack_action == 'zip' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                zip_info = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.build_pack_zip(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info})
                return (True, True)
            if pack_action == 'verify' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                profile = str(payload.get('profile') or query_profile)
                report = _interfaces_api_runtime.verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_pack=True, require_transparency=bool(payload.get('require_transparency', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_verification_report_path(portfolio_id, profile))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report})
                return (True, True)
        return (False, None)

    def _dispatch_portfolio_acknowledgement_part_01_actions_02(self, method, parts, portfolio_id, action, _split_state, query_profile, subaction):
        if subaction == 'responses' and len(parts) >= 3:
            if len(parts) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'responses': self.release_portfolio_governance_attestation_transparency_acknowledgement_store.list_responses(portfolio_id, profile=query_profile)})
                return (True, True)
            if parts[3] == 'import' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._read_json_body()
                payload.setdefault('profile', query_profile)
                imported = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.import_response(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, **imported}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, True)
            response_id = parts[3]
            if len(parts) == 4:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                response = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.read_response(portfolio_id, response_id, profile=query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'response': response})
                return (True, True)
            if len(parts) == 5 and parts[4] == 'verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                report = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.verify_response(portfolio_id, response_id, profile=query_profile, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report})
                return (True, True)
            if len(parts) == 5 and parts[4] == 'create-change-request':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                change_request = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.create_change_request(portfolio_id, response_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'change_request': change_request}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, True)
        return (False, None)

    def _dispatch_portfolio_acknowledgement_part_01_actions_03(self, method, parts, portfolio_id, action, _split_state, query_profile, subaction):
        if subaction == 'evidence' and len(parts) >= 4:
            evidence_action = parts[3]
            if evidence_action == 'refresh' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                evidence = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.refresh_evidence(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'acknowledgement_evidence': evidence, 'summary': _interfaces_api_runtime.portfolio_governance_attestation_transparency_acknowledgement_summary(evidence)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, True)
            if evidence_action == 'export' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                manifest = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.export_evidence(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'manifest': manifest}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, True)
            if evidence_action == 'zip' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                payload.setdefault('profile', query_profile)
                zip_info = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.build_evidence_zip(portfolio_id, payload, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'zip': zip_info})
                return (True, True)
            if evidence_action == 'verify' and len(parts) == 4:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                payload = self._optional_json_body()
                profile = str(payload.get('profile') or query_profile)
                report = _interfaces_api_runtime.verify_release_portfolio_governance_attestation_transparency_acknowledgement_package(self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_zip_path(portfolio_id, profile), strict=bool(payload.get('strict', False)), require_response=True, require_accepted=bool(payload.get('require_accepted', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_attestation_transparency_acknowledgement_verification_report(report, self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_verification_report_path(portfolio_id, profile))
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'verification': report})
                return (True, True)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Attestation Transparency Acknowledgement route not found.')
        return (True, True)
        return (False, None)

    def _dispatch_portfolio_acknowledgement_part_01(self, method, parts, portfolio_id, action, _split_state):
        if action == 'governance-attestation-transparency-acknowledgement':
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            query_profile = str(query.get('profile', ['public_summary'])[0] or 'public_summary')
            if len(parts) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, True)
                pack = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.read_pack(portfolio_id, profile=query_profile, default={})
                evidence = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.read_evidence(portfolio_id, profile=query_profile, default={})
                summary = {'status': pack.get('status', 'missing') if pack else 'missing', 'profile': query_profile, 'pack_id': pack.get('pack_id') if pack else None}
                if pack:
                    summary['stale'] = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.pack_is_stale(portfolio_id, pack, profile=query_profile)
                evidence_summary = _interfaces_api_runtime.portfolio_governance_attestation_transparency_acknowledgement_summary(evidence) if evidence else {'status': 'missing', 'external_review_status': 'missing'}
                if evidence:
                    evidence_summary['stale'] = self.release_portfolio_governance_attestation_transparency_acknowledgement_store.evidence_is_stale(portfolio_id, evidence, profile=query_profile)
                self._send_json({'ok': True, 'portfolio_id': portfolio_id, 'profile': query_profile, 'pack': pack, 'responses': self.release_portfolio_governance_attestation_transparency_acknowledgement_store.list_responses(portfolio_id, profile=query_profile), 'acknowledgement_evidence': evidence, 'change_requests': self.release_portfolio_governance_attestation_transparency_acknowledgement_store.list_change_requests(portfolio_id, profile=query_profile), 'summary': summary, 'evidence_summary': evidence_summary})
                return (True, True)
            subaction = parts[2] if len(parts) > 2 else ''
            _split_action_result = self._dispatch_portfolio_acknowledgement_part_01_actions_01(method, parts, portfolio_id, action, _split_state, query_profile, subaction)
            if _split_action_result[0]:
                return _split_action_result
            _split_action_result = self._dispatch_portfolio_acknowledgement_part_01_actions_02(method, parts, portfolio_id, action, _split_state, query_profile, subaction)
            if _split_action_result[0]:
                return _split_action_result
            _split_action_result = self._dispatch_portfolio_acknowledgement_part_01_actions_03(method, parts, portfolio_id, action, _split_state, query_profile, subaction)
            if _split_action_result[0]:
                return _split_action_result
        return (False, None)

    def _dispatch_portfolio_acknowledgement_part_02(self, method, parts, portfolio_id, action, _split_state):
        return (True, False)
        return (False, None)

    def _dispatch_portfolio_acknowledgement(self, method, parts, portfolio_id, action) -> bool:
        _split_state = {}
        _split_result = self._dispatch_portfolio_acknowledgement_part_01(method, parts, portfolio_id, action, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._dispatch_portfolio_acknowledgement_part_02(method, parts, portfolio_id, action, _split_state)
        if _split_result[0]:
            return _split_result[1]
