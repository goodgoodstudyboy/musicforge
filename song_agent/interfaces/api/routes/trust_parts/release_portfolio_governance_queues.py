from __future__ import annotations

from song_agent.interfaces.api.route_contexts.trust import TrustRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class TrustRoutesReleasePortfolioGovernanceQueues(TrustRouteContext):
    def _handle_release_portfolio_governance_queues_part_01(self, method: str, path: str, _split_state):
        if _split_state['tail'] in {'', '/'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            query = _interfaces_api_runtime.parse_qs(_interfaces_api_runtime.urlparse(self.path).query)
            portfolio_id = str(query.get('portfolio_id', [''])[0] or '').strip() or None
            include_archived = str(query.get('include_archived', [''])[0]).lower() in {'1', 'true', 'yes'}
            queues = self.release_portfolio_governance_store.list_queues(portfolio_id=portfolio_id, include_archived=include_archived)
            self._send_json({'ok': True, 'queues': queues, 'summary': {'count': len(queues)}})
            return (True, None)
        _split_state['parts'] = [part for part in _split_state['tail'].strip('/').split('/') if part]
        if not _split_state['parts']:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Queue route not found.')
            return (True, None)
        _split_state['queue_id'] = _split_state['parts'][0]
        _split_state['action'] = _split_state['parts'][1] if len(_split_state['parts']) > 1 else ''
        if len(_split_state['parts']) == 1:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['queue'] = self.release_portfolio_governance_store.get_queue(_split_state['queue_id'])
            execution = self.release_portfolio_governance_store.read_execution_report(_split_state['queue_id'], default={})
            self._send_json({'ok': True, 'queue': _split_state['queue'], 'summary': _interfaces_api_runtime.queue_summary(_split_state['queue'], execution), 'signoff_summary': self.release_portfolio_governance_signoff_store.signoff_summary(_split_state['queue_id']), 'archive_summary': self.release_portfolio_governance_signoff_store.archive_summary(_split_state['queue_id']), 'change_request_summary': self.release_portfolio_governance_signoff_store.change_request_summary(_split_state['queue_id'])})
            return (True, None)
        if _split_state['action'] == 'plan' and len(_split_state['parts']) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            plan = self.release_portfolio_governance_store.read_action_plan(_split_state['queue_id'], default={})
            self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'action_plan': plan, 'summary': {'item_count': len(plan.get('items', []) if isinstance(plan.get('items'), list) else [])}})
            return (True, None)
        if _split_state['action'] == 'execution' and len(_split_state['parts']) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            execution = self.release_portfolio_governance_store.read_execution_report(_split_state['queue_id'], default={})
            self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'execution_report': execution, 'summary': execution.get('summary', {})})
            return (True, None)
        if _split_state['action'] == 'manual-actions' and len(_split_state['parts']) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            manual = self.release_portfolio_governance_store.read_manual_action_list(_split_state['queue_id'], default={})
            self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'manual_action_list': manual, 'summary': {'count': len(manual.get('items', []) if isinstance(manual.get('items'), list) else [])}})
            return (True, None)
        if _split_state['action'] == 'run-safe' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['queue'] = self.release_portfolio_governance_store.run_safe_actions(_split_state['queue_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            execution = self.release_portfolio_governance_store.read_execution_report(_split_state['queue_id'], default={})
            self._send_json({'ok': True, 'queue': _split_state['queue'], 'execution_report': execution, 'summary': _interfaces_api_runtime.queue_summary(_split_state['queue'], execution)})
            return (True, None)
        if _split_state['action'] == 'export' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['manifest'] = self.release_portfolio_governance_store.export_queue(_split_state['queue_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        return (False, None)

    def _handle_release_portfolio_governance_queues_part_02(self, method: str, path: str, _split_state):
        if _split_state['action'] == 'export' and len(_split_state['parts']) == 3 and (_split_state['parts'][2] == 'zip'):
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['zip_info'] = self.release_portfolio_governance_store.build_zip(_split_state['queue_id'], now=_interfaces_api_runtime._utc_now())
            _split_state['manifest'] = self.release_portfolio_governance_store.read_export_manifest(_split_state['queue_id'])
            self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'zip': _split_state['zip_info'], 'summary': _split_state['manifest'].get('summary', {})})
            return (True, None)
        if _split_state['action'] == 'verify' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['report'] = _interfaces_api_runtime.verify_release_portfolio_governance_package(self.release_portfolio_governance_store.zip_path(_split_state['queue_id']), strict=bool(_split_state['payload'].get('strict', False)), require_manual_actions=bool(_split_state['payload'].get('require_manual_actions', False)), require_no_blocked=bool(_split_state['payload'].get('require_no_blocked', False)))
            _interfaces_api_runtime.write_release_portfolio_governance_verification_report(_split_state['report'], self.release_portfolio_governance_store.verification_report_path(_split_state['queue_id']))
            self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'verification': _split_state['report'], 'summary': _interfaces_api_runtime.release_portfolio_governance_verification_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'signoff' and len(_split_state['parts']) == 2:
            if method == 'GET':
                signoff = self.release_portfolio_governance_signoff_store.read_signoff(_split_state['queue_id'], default={})
                gate = self.release_portfolio_governance_signoff_store.gate(_split_state['queue_id'], {}, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'signoff': signoff, 'summary': self.release_portfolio_governance_signoff_store.signoff_summary(_split_state['queue_id'], signoff=signoff), 'gate': gate})
                return (True, None)
            if method == 'POST':
                signoff = self.release_portfolio_governance_signoff_store.signoff(_split_state['queue_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'signoff': signoff, 'summary': self.release_portfolio_governance_signoff_store.signoff_summary(_split_state['queue_id'], signoff=signoff)})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'signoff' and len(_split_state['parts']) == 3 and (_split_state['parts'][2] == 'reset'):
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            signoff = self.release_portfolio_governance_signoff_store.reset_signoff(_split_state['queue_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'signoff': signoff, 'summary': self.release_portfolio_governance_signoff_store.signoff_summary(_split_state['queue_id'], signoff=signoff)})
            return (True, None)
        if _split_state['action'] == 'change-requests':
            if len(_split_state['parts']) == 2:
                if method == 'GET':
                    rows = self.release_portfolio_governance_signoff_store.list_change_requests(_split_state['queue_id'])
                    self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'change_requests': rows, 'summary': self.release_portfolio_governance_signoff_store.change_request_summary(_split_state['queue_id'])})
                    return (True, None)
                if method == 'POST':
                    item = self.release_portfolio_governance_signoff_store.create_change_request(_split_state['queue_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'change_request': item, 'summary': self.release_portfolio_governance_signoff_store.change_request_summary(_split_state['queue_id'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return (True, None)
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            change_request_id = _split_state['parts'][2]
            if len(_split_state['parts']) == 3 and method == 'GET':
                item = self.release_portfolio_governance_signoff_store.get_change_request(_split_state['queue_id'], change_request_id)
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'change_request': item})
                return (True, None)
            if len(_split_state['parts']) == 4 and method == 'POST' and (_split_state['parts'][3] in {'approve', 'reject', 'archive'}):
                item = self.release_portfolio_governance_signoff_store.update_change_request_status(_split_state['queue_id'], change_request_id, _split_state['parts'][3], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'change_request': item, 'summary': self.release_portfolio_governance_signoff_store.change_request_summary(_split_state['queue_id'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Change Request route not found.')
            return (True, None)
        return (False, None)

    def _handle_release_portfolio_governance_queues_part_03(self, method: str, path: str, _split_state):
        if _split_state['action'] == 'archive.zip' and len(_split_state['parts']) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.release_portfolio_governance_store.get_queue(_split_state['queue_id'])
            self._send_file(self.release_portfolio_governance_signoff_store.archive_zip_path(_split_state['queue_id']), 'application/zip', filename=f"musicforge-{_split_state['queue_id']}-portfolio-governance-archive.zip")
            return (True, None)
        if _split_state['action'] == 'archive' and len(_split_state['parts']) >= 2:
            if len(_split_state['parts']) == 2 and method == 'GET':
                _split_state['manifest'] = self.release_portfolio_governance_signoff_store.read_archive_manifest(_split_state['queue_id'])
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'manifest': _split_state['manifest'], 'summary': self.release_portfolio_governance_signoff_store.archive_summary(_split_state['queue_id'])})
                return (True, None)
            if len(_split_state['parts']) == 3 and _split_state['parts'][2] == 'export':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['manifest'] = self.release_portfolio_governance_signoff_store.export_archive(_split_state['queue_id'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if len(_split_state['parts']) == 3 and _split_state['parts'][2] == 'zip':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['zip_info'] = self.release_portfolio_governance_signoff_store.build_archive_zip(_split_state['queue_id'], now=_interfaces_api_runtime._utc_now())
                _split_state['manifest'] = self.release_portfolio_governance_signoff_store.read_archive_manifest(_split_state['queue_id'])
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'zip': _split_state['zip_info'], 'summary': _split_state['manifest'].get('summary', {})})
                return (True, None)
            if len(_split_state['parts']) == 3 and _split_state['parts'][2] == 'verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['payload'] = self._optional_json_body()
                _split_state['report'] = _interfaces_api_runtime.verify_release_portfolio_governance_archive_package(self.release_portfolio_governance_signoff_store.archive_zip_path(_split_state['queue_id']), strict=bool(_split_state['payload'].get('strict', False)), require_signed=bool(_split_state['payload'].get('require_signed', False)), require_no_force=bool(_split_state['payload'].get('require_no_force', False)))
                _interfaces_api_runtime.write_release_portfolio_governance_archive_verification_report(_split_state['report'], self.release_portfolio_governance_signoff_store.archive_verification_report_path(_split_state['queue_id']))
                self._send_json({'ok': True, 'queue_id': _split_state['queue_id'], 'verification': _split_state['report'], 'summary': _interfaces_api_runtime.release_portfolio_governance_archive_verification_summary(_split_state['report'])})
                return (True, None)
        if _split_state['action'] == 'download' and len(_split_state['parts']) == 2:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.release_portfolio_governance_store.get_queue(_split_state['queue_id'])
            self._send_file(self.release_portfolio_governance_store.zip_path(_split_state['queue_id']), 'application/zip', filename=f"musicforge-{_split_state['queue_id']}-portfolio-governance.zip")
            return (True, None)
        if _split_state['action'] == 'archive' and len(_split_state['parts']) == 2:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['queue'] = self.release_portfolio_governance_store.archive(_split_state['queue_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'queue': _split_state['queue'], 'summary': _interfaces_api_runtime.queue_summary(_split_state['queue'])})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Portfolio Governance Queue route not found.')
        return (False, None)

    def _handle_release_portfolio_governance_queues(self, method: str, path: str) -> None:
        _split_state = {}
        prefix = '/api/release-portfolio-governance-queues'
        _split_state['tail'] = path[len(prefix):]
        try:
            _split_result = self._handle_release_portfolio_governance_queues_part_01(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_portfolio_governance_queues_part_02(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_portfolio_governance_queues_part_03(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.ReleasePortfolioGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceSignoffNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceSignoffStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceSignoffError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleasePortfolioGovernanceError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
