from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument

from song_agent.interfaces.api.route_contexts.program import ProgramRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class ProgramRoutesUnifiedCommandCenterReleaseTrains(ProgramRouteContext):
    def _handle_unified_command_center_release_trains_route_part_01(self, method: str, path: str, _split_state):
        if path == '/api/unified-command-center-release-trains':
            if method == 'GET':
                trains = self.unified_command_center_release_train_store.list_trains()
                self._send_json({'ok': True, 'trains': trains, 'summary': {'train_count': len(trains)}})
                return (True, None)
            if method == 'POST':
                train = self.unified_command_center_release_train_store.create_train(self._optional_json_body())
                self._send_json({'ok': True, 'train': train, 'summary': {'train_id': train.get('train_id')}, 'status': train.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        prefix = '/api/unified-command-center-release-trains/'
        if not path.startswith(prefix):
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Unified Command Center Release Train route not found.')
            return (True, None)
        parts = path.removeprefix(prefix).strip('/').split('/')
        _split_state['train_id'] = parts[0]
        _split_state['tail'] = '/' + '/'.join(parts[1:]) if len(parts) > 1 else ''
        if _split_state['tail'] in {'', '/'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            train = self.unified_command_center_release_train_store.read_train(_split_state['train_id'])
            docs = self.unified_command_center_release_train_store.read_docs(_split_state['train_id']) if self.unified_command_center_release_train_store.report_path(_split_state['train_id']).exists() else {}
            _split_state['report'] = docs.get('report', {}) if docs else {}
            self._send_json({'ok': True, 'train': train, 'docs': docs, 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status') or train.get('status')})
            return (True, None)
        if _split_state['tail'] == '/lifecycle':
            if method == 'GET':
                _split_state['report'] = self.unified_command_center_release_train_lifecycle_store.read_report(_split_state['train_id']) if self.unified_command_center_release_train_lifecycle_store.report_path(_split_state['train_id']).exists() else {}
                self._send_json({'ok': True, 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {}) if _split_state['report'] else {}, 'status': _split_state['report'].get('status') if _split_state['report'] else 'not_configured'})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_unified_command_center_release_trains_route_part_02(self, method: str, path: str, _split_state):
        if _split_state['tail'].startswith('/lifecycle/'):
            lifecycle_tail = _split_state['tail'].removeprefix('/lifecycle/').strip('/')
            if lifecycle_tail == 'refresh':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.unified_command_center_release_train_lifecycle_store.refresh_report(_split_state['train_id'], self._optional_json_body())
                self._send_json({'ok': _split_state['report'].get('status') == 'passed', 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
                return (True, None)
            if lifecycle_tail == 'export':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['manifest'] = self.unified_command_center_release_train_lifecycle_store.export_package(_split_state['train_id'], self._optional_json_body())
                self._send_json({'ok': True, 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {}), 'status': 'passed'})
                return (True, None)
            if lifecycle_tail == 'zip':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.unified_command_center_release_train_lifecycle_store.build_zip(_split_state['train_id'], self._optional_json_body())
                self._send_json({'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}})
                return (True, None)
            if lifecycle_tail == 'verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.unified_command_center_release_train_lifecycle_store.verify_package(_split_state['train_id'], self._optional_json_body())
                self._send_json({'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
                return (True, None)
            if lifecycle_tail == 'download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.unified_command_center_release_train_lifecycle_store.zip_path(_split_state['train_id']), 'application/zip', filename='musicforge-unified-command-center-release-train-lifecycle.zip')
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Train Lifecycle route not found.')
            return (True, None)
        if _split_state['tail'] == '/handoffs':
            if method == 'GET':
                handoffs = self.unified_command_center_release_train_handoff_store.list_handoffs(_split_state['train_id'])
                self._send_json({'ok': True, 'handoffs': handoffs, 'summary': {'handoff_count': len(handoffs)}, 'status': 'passed'})
                return (True, None)
            if method == 'POST':
                _split_state['detail'] = self.unified_command_center_release_train_handoff_store.create_handoff(_split_state['train_id'], self._optional_json_body())
                _split_state['report'] = _split_state['detail'].get('report', {})
                self._send_json({'ok': True, **_split_state['detail'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_unified_command_center_release_trains_route_part_03(self, method: str, path: str, _split_state):
        if _split_state['tail'].startswith('/handoffs/'):
            handoff_parts = _split_state['tail'].removeprefix('/handoffs/').strip('/').split('/')
            handoff_id = handoff_parts[0]
            _split_state['action'] = '/'.join(handoff_parts[1:]) if len(handoff_parts) > 1 else ''
            if _split_state['action'] == '':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['detail'] = self.unified_command_center_release_train_handoff_store.get_handoff(_split_state['train_id'], handoff_id)
                _split_state['report'] = _split_state['detail'].get('report', {})
                self._send_json({'ok': True, **_split_state['detail'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
                return (True, None)
            if _split_state['action'] == 'refresh':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.unified_command_center_release_train_handoff_store.refresh_report(_split_state['train_id'], handoff_id, self._optional_json_body())
                self._send_json({'ok': _split_state['report'].get('status') == 'ready', 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
                return (True, None)
            if _split_state['action'] == 'export':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['manifest'] = self.unified_command_center_release_train_handoff_store.export_handoff(_split_state['train_id'], handoff_id)
                self._send_json({'ok': True, 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {}), 'status': 'passed'})
                return (True, None)
            if _split_state['action'] == 'zip':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.unified_command_center_release_train_handoff_store.build_zip(_split_state['train_id'], handoff_id)
                self._send_json({'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}})
                return (True, None)
            if _split_state['action'] == 'verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.unified_command_center_release_train_handoff_store.verify_package(_split_state['train_id'], handoff_id, self._optional_json_body())
                self._send_json({'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
                return (True, None)
            if _split_state['action'] == 'import-response':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.unified_command_center_release_train_handoff_store.import_response(_split_state['train_id'], handoff_id, self._read_json_body())
                self._send_json({'ok': _split_state['result'].get('verification', {}).get('status') == 'passed', **_split_state['result'], 'summary': _split_state['result'].get('verification', {}).get('summary', {}), 'status': _split_state['result'].get('response', {}).get('decision')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['action'].startswith('accepted-evidence/'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                response_id = _split_state['action'].removeprefix('accepted-evidence/').strip('/')
                evidence = self.unified_command_center_release_train_handoff_store.create_accepted_evidence(_split_state['train_id'], handoff_id, response_id)
                self._send_json({'ok': True, 'accepted_evidence': evidence, 'summary': evidence.get('public_summary', {}), 'status': 'passed'}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if _split_state['action'] == 'signoff':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['signoff'] = self.unified_command_center_release_train_handoff_store.signoff(_split_state['train_id'], handoff_id, self._optional_json_body())
                self._send_json({'ok': _split_state['signoff'].get('status') == 'signed', 'signoff': _split_state['signoff'], 'summary': {'signed_by': _split_state['signoff'].get('signed_by')}, 'status': _split_state['signoff'].get('status')})
                return (True, None)
            if _split_state['action'] == 'download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.unified_command_center_release_train_handoff_store.zip_path(_split_state['train_id'], handoff_id), 'application/zip', filename='musicforge-unified-command-center-release-train-handoff.zip')
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Train Handoff route not found.')
            return (True, None)
        return (False, None)

    def _handle_unified_command_center_release_trains_route_part_04(self, method: str, path: str, _split_state):
        if _split_state['tail'] == '/changes':
            if method == 'GET':
                _split_state['report'] = self.unified_command_center_release_train_change_control_store.refresh_report(_split_state['train_id']) if self.unified_command_center_release_train_change_control_store.change_dir(_split_state['train_id']).exists() else {}
                requests = self.unified_command_center_release_train_change_control_store.list_requests(_split_state['train_id'])
                self._send_json({'ok': True, 'report': _split_state['report'], 'change_requests': requests, 'summary': _split_state['report'].get('summary', {}) if _split_state['report'] else {}, 'status': _split_state['report'].get('status') if _split_state['report'] else 'not_configured'})
                return (True, None)
            if method == 'POST':
                request = self.unified_command_center_release_train_change_control_store.create_request(_split_state['train_id'], self._optional_json_body())
                self._send_json({'ok': True, 'change_request': request, 'summary': {'change_request_id': request.get('change_request_id')}, 'status': request.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['tail'].startswith('/changes/'):
            change_tail = _split_state['tail'].removeprefix('/changes/').strip('/')
            if change_tail == 'export':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['manifest'] = self.unified_command_center_release_train_change_control_store.export_package(_split_state['train_id'])
                self._send_json({'ok': True, 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {}), 'status': 'passed'})
                return (True, None)
            if change_tail == 'zip':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.unified_command_center_release_train_change_control_store.build_zip(_split_state['train_id'])
                self._send_json({'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}})
                return (True, None)
            if change_tail == 'verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.unified_command_center_release_train_change_control_store.verify_package(_split_state['train_id'], self._optional_json_body())
                self._send_json({'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
                return (True, None)
            if change_tail == 'download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.unified_command_center_release_train_change_control_store.zip_path(_split_state['train_id']), 'application/zip', filename='musicforge-unified-command-center-release-train-change-control.zip')
                return (True, None)
            change_parts = change_tail.split('/')
            request_id = change_parts[0]
            _split_state['action'] = '/' + '/'.join(change_parts[1:]) if len(change_parts) > 1 else ''
            if _split_state['action'] in {'', '/'}:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                request = self.unified_command_center_release_train_change_control_store.read_request(_split_state['train_id'], request_id)
                self._send_json({'ok': True, 'change_request': request, 'summary': {'change_request_id': request.get('change_request_id')}, 'status': request.get('status')})
                return (True, None)
            if _split_state['action'] == '/approve':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                approval = self.unified_command_center_release_train_change_control_store.approve_request(_split_state['train_id'], request_id, self._optional_json_body())
                self._send_json({'ok': approval.get('status') == 'approved', 'approval': approval, 'summary': {'approval_hash': approval.get('integrity_hash')}, 'status': approval.get('status')})
                return (True, None)
            if _split_state['action'] == '/reset':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                proof = self.unified_command_center_release_train_change_control_store.reset_train_signoff(_split_state['train_id'], request_id, self._optional_json_body())
                self._send_json({'ok': proof.get('status') == 'applied', 'reset_proof': proof, 'summary': {'reset_event_hash': proof.get('reset_event_hash')}, 'status': proof.get('status')})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Train Change Control route not found.')
            return (True, None)
        return (False, None)

    def _handle_unified_command_center_release_trains_route_part_05(self, method: str, path: str, _split_state):
        if _split_state['tail'] == '/items':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            item = self.unified_command_center_release_train_store.add_item(_split_state['train_id'], self._read_json_body())
            self._send_json({'ok': True, 'item': item, 'summary': {'item_id': item.get('item_id')}, 'status': item.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['tail'] == '/refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self.unified_command_center_release_train_store.refresh(_split_state['train_id'], self._optional_json_body())
            self._send_json({'ok': _split_state['report'].get('status') == 'go', 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
            return (True, None)
        if _split_state['tail'] == '/run-safe':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.unified_command_center_release_train_store.run_safe(_split_state['train_id'], self._optional_json_body())
            failed_count = int((_split_state['result'].get('summary') or {}).get('failed_count') or 0)
            self._send_json({'ok': failed_count == 0, 'runbook_result': _split_state['result'], 'summary': _split_state['result'].get('summary', {}), 'status': 'passed' if failed_count == 0 else 'failed'})
            return (True, None)
        if _split_state['tail'] == '/signoff':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['signoff'] = self.unified_command_center_release_train_store.signoff(_split_state['train_id'], self._optional_json_body())
            self._send_json({'ok': _split_state['signoff'].get('status') == 'signed', 'signoff': _split_state['signoff'], 'summary': {'signoff_hash': _split_state['signoff'].get('integrity_hash')}, 'status': _split_state['signoff'].get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['tail'] == '/archive':
            if method == 'GET':
                manifest_path = self.unified_command_center_release_train_store.archive_manifest_path(_split_state['train_id'])
                _split_state['manifest'] = _interfaces_api_runtime.read_json(manifest_path) if manifest_path.exists() else {}
                self._send_json({'ok': bool(_split_state['manifest']), 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {}) if _split_state['manifest'] else {}})
                return (True, None)
            if method == 'POST':
                _split_state['manifest'] = self.unified_command_center_release_train_store.export_archive(_split_state['train_id'])
                self._send_json({'ok': True, 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {}), 'status': 'passed'})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['tail'] == '/archive/zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.unified_command_center_release_train_store.build_zip(_split_state['train_id'])
            self._send_json({'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}})
            return (True, None)
        if _split_state['tail'] == '/archive/verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self.unified_command_center_release_train_store.verify_archive(_split_state['train_id'], self._optional_json_body())
            self._send_json({'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
            return (True, None)
        if _split_state['tail'] == '/download':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_file(self.unified_command_center_release_train_store.zip_path(_split_state['train_id']), 'application/zip', filename='musicforge-unified-command-center-release-train.zip')
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Unified Command Center Release Train route not found.')
        return (False, None)

    def _handle_unified_command_center_release_trains_route(self, method: str, path: str) -> None:
        _split_state: ImplementationDocument = {}
        try:
            _split_result = self._handle_unified_command_center_release_trains_route_part_01(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_unified_command_center_release_trains_route_part_02(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_unified_command_center_release_trains_route_part_03(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_unified_command_center_release_trains_route_part_04(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_unified_command_center_release_trains_route_part_05(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainChangeControlNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainLifecycleNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainChangeControlStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainLifecycleStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainChangeControlError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainLifecycleError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.UnifiedCommandCenterReleaseTrainError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_unified_release_programs_route(self, method: str, path: str) -> None:
        self.program_application.dispatch_http(self, method, path)
