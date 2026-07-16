from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class ProgramUccDriftsRoutes:
    def _dispatch_ucc_drifts(self, method, center_id, tail) -> bool:
        if tail == '/drift-responses':
            if method == 'GET':
                responses = self.unified_command_center_drift_response_store.list_responses(center_id)
                self._send_json({'ok': True, 'responses': responses, 'summary': {'response_count': len(responses)}})
                return True
            if method == 'POST':
                result = self.unified_command_center_drift_response_store.create_response(center_id, self._optional_json_body())
                case = result.get('case', {})
                self._send_json({'ok': True, **result, 'summary': {'response_id': case.get('response_id')}, 'status': case.get('status')}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        if tail.startswith('/drift-responses/'):
            response_tail = tail.removeprefix('/drift-responses/')
            response_parts = response_tail.split('/')
            response_id = response_parts[0]
            response_action = '/' + '/'.join(response_parts[1:]) if len(response_parts) > 1 else ''
            if response_action in {'', '/'}:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                response = self.unified_command_center_drift_response_store.read_response(center_id, response_id)
                self._send_json({'ok': True, 'response': response, 'summary': (response.get('closeout') or {}).get('summary', {}), 'status': (response.get('closeout') or response.get('case') or {}).get('status')})
                return True
            if response_action == '/run-safe':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_drift_response_store.run_safe(center_id, response_id, self._optional_json_body())
                self._send_json({'ok': int((result.get('summary') or {}).get('failed_count') or 0) == 0, 'action_results': result, 'summary': result.get('summary', {}), 'status': 'passed' if int((result.get('summary') or {}).get('failed_count') or 0) == 0 else 'failed'})
                return True
            if response_action == '/bind-cr':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_drift_response_store.bind_change_request(center_id, response_id, self._optional_json_body())
                self._send_json({'ok': True, 'change_request_bindings': result, 'summary': result.get('summary', {}), 'status': 'passed'})
                return True
            if response_action == '/bind-recheck':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_drift_response_store.bind_recheck(center_id, response_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'passed', 'recheck': result, 'summary': result.get('summary', {}), 'status': result.get('status')})
                return True
            if response_action == '/closeout':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_drift_response_store.closeout(center_id, response_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'closed', 'closeout': result, 'summary': result.get('summary', {}), 'status': result.get('status')})
                return True
            if response_action == '/export':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_drift_response_store.export_package(center_id, response_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'closed', **result})
                return True
            if response_action == '/zip':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                result = self.unified_command_center_drift_response_store.build_zip(center_id, response_id, self._optional_json_body())
                self._send_json({'ok': result.get('status') == 'closed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
                return True
            if response_action == '/verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                report = self.unified_command_center_drift_response_store.verify_package(center_id, response_id, self._optional_json_body())
                self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
                return True
            if response_action == '/download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return True
                self._send_file(self.unified_command_center_drift_response_store.zip_path(center_id, response_id), 'application/zip', filename='musicforge-unified-command-center-drift-response.zip')
                return True
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Unified Command Center Drift Response route not found.')
            return True
        return False
