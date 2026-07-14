from __future__ import annotations

from http import HTTPStatus

class ProgramOperationsHttpRoutes:
    def _dispatch_operations(self, method, program_id, tail) -> bool:
        if tail == '/operations/change-requests':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request = self.unified_release_program_operations_store.create_change_request(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'change_request': request, 'summary': {'change_request_id': request.get('change_request_id')}, 'status': request.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/operations/change-requests/') and tail.endswith('/approve'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request_id = tail.split('/')[3]
            approval = self.unified_release_program_operations_store.approve_change_request(program_id, request_id, self._optional_json_body())
            self._send_json({'ok': True, 'approval': approval, 'summary': {'change_request_id': approval.get('change_request_id')}, 'status': approval.get('status')})
            return True
        if tail == '/operations/reset-signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            proof = self.unified_release_program_operations_store.reset_program_signoff(program_id, self._optional_json_body())
            self._send_json({'ok': proof.get('status') == 'applied', 'reset_proof': proof, 'summary': {'reset_event_hash': proof.get('reset_event_hash')}, 'status': proof.get('status')})
            return True
        if tail == '/operations/runbooks':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            runbook = self.unified_release_program_operations_store.create_runbook(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'runbook': runbook, 'summary': runbook.get('summary', {}), 'status': runbook.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/operations/runbooks/') and tail.endswith('/run-safe'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            runbook_id = tail.split('/')[3]
            result = self.unified_release_program_operations_store.run_safe(program_id, runbook_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') in {'completed', 'completed_with_manual_actions'}, **result})
            return True
        if tail == '/operations/continuous-review/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            review = self.unified_release_program_operations_store.refresh_continuous_review(program_id, self._optional_json_body())
            self._send_json({'ok': review.get('status') == 'passed', 'review': review, 'summary': review.get('summary', {}), 'status': review.get('status')})
            return True
        if tail == '/operations/lifecycle/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_operations_store.refresh_lifecycle_audit(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'lifecycle': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/operations/archive/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_operations_store.export_operations_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/operations/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_operations_store.build_operations_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        if tail == '/operations/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_operations_store.verify_operations_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        return False
