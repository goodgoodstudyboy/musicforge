from __future__ import annotations

from http import HTTPStatus

class ProgramCommandCenterSignoffHttpRoutes:
    def _dispatch_command_center_signoff(self, method, program_id, tail) -> bool:
        return (
            self._dispatch_command_center_signoff_workflow(method, program_id, tail)
            or self._dispatch_command_center_signoff_archive(method, program_id, tail)
        )

    def _dispatch_command_center_signoff_workflow(self, method, program_id, tail) -> bool:
        if tail == '/continuity-command-center-signoff':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            state = self.unified_release_program_continuity_command_center_signoff_store.get_state(program_id)
            self._send_json({'ok': True, **state, 'summary': {'status': state.get('status')}})
            return True
        if tail == '/continuity-command-center-signoff/preflight':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_signoff_store.preflight(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'preflight': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
            return True
        if tail == '/continuity-command-center-signoff/sign':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_release_program_continuity_command_center_signoff_store.signoff(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'signoff': signoff, 'status': signoff.get('status'), 'summary': signoff.get('summary', {})})
            return True
        if tail == '/continuity-command-center-signoff/change-requests':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request = self.unified_release_program_continuity_command_center_signoff_store.create_change_request(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'change_request': request, 'status': request.get('status'), 'summary': {'change_request_id': request.get('change_request_id')}}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/continuity-command-center-signoff/change-requests/') and tail.endswith('/approve'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request_id = tail.split('/')[3]
            approval = self.unified_release_program_continuity_command_center_signoff_store.approve_change_request(program_id, request_id, self._optional_json_body())
            self._send_json({'ok': True, 'approval': approval, 'status': approval.get('status'), 'summary': {'change_request_id': request_id}})
            return True
        if tail == '/continuity-command-center-signoff/reset':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            proof = self.unified_release_program_continuity_command_center_signoff_store.reset_signoff(program_id, str(payload.get('change_request_id') or ''), payload)
            self._send_json({'ok': proof.get('status') == 'applied', 'reset_proof': proof, 'status': proof.get('status'), 'summary': {'reset_event_hash': proof.get('reset_event_hash')}})
            return True
        return False

    def _dispatch_command_center_signoff_archive(self, method, program_id, tail) -> bool:
        if tail == '/continuity-command-center-signoff/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_command_center_signoff_store.export_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'status': 'passed', 'summary': {'manifest_hash': manifest.get('integrity_hash')}})
            return True
        if tail == '/continuity-command-center-signoff/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_command_center_signoff_store.build_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': True, **result})
            return True
        if tail == '/continuity-command-center-signoff/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_signoff_store.verify_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
            return True
        if tail == '/continuity-command-center-signoff/handoff/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_command_center_signoff_store.export_final_handoff(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'status': 'passed', 'summary': {'manifest_hash': manifest.get('integrity_hash')}})
            return True
        if tail == '/continuity-command-center-signoff/handoff/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_command_center_signoff_store.build_final_handoff_zip(program_id, self._optional_json_body())
            self._send_json({'ok': True, **result})
            return True
        if tail == '/continuity-command-center-signoff/handoff/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_signoff_store.verify_final_handoff_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
            return True
        if tail == '/continuity-command-center-signoff/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_continuity_command_center_signoff_store.gate(program_id, required=True, archive_zip_path=payload.get('archive_zip'), archive_verification_report_path=payload.get('archive_verification_report'), signoff_binding_path=payload.get('signoff_binding'), command_center_zip_path=payload.get('command_center'), command_center_verification_report_path=payload.get('command_center_verification_report'), command_center_external_evidence_manifest_path=payload.get('command_center_external_evidence_manifest'))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'status': gate.get('status'), 'summary': gate.get('summary', {})})
            return True
        return False
