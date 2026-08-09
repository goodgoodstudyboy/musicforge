from __future__ import annotations

from song_agent.application.program.http_context import ProgramHttpContext
from song_agent.platform.contracts.coercion import as_document

from http import HTTPStatus

class ProgramAcceptanceChangeHttpRoutes(ProgramHttpContext):
    def _dispatch_acceptance_change(self, method, program_id, tail) -> bool:
        if tail == '/continuity-acceptance/change-control':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_continuity_acceptance_change_store.get_state(program_id)
            state = as_document(detail.get('state'))
            self._send_json({'ok': True, **detail, 'summary': state, 'status': state.get('status') or 'unknown'})
            return True
        if tail == '/continuity-acceptance/change-control/change-requests':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request = self.unified_release_program_continuity_acceptance_change_store.create_change_request(program_id, self._optional_json_body())
            self._send_json({'ok': request.get('status') in {'submitted', 'approved'}, 'change_request': request, 'summary': {'change_request_id': request.get('change_request_id')}, 'status': request.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/continuity-acceptance/change-control/change-requests/') and tail.endswith('/approve'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request_id = tail.split('/')[4]
            approval = self.unified_release_program_continuity_acceptance_change_store.approve_change_request(program_id, request_id, self._optional_json_body())
            self._send_json({'ok': approval.get('status') == 'approved', 'approval': approval, 'summary': {'change_request_id': approval.get('change_request_id')}, 'status': approval.get('status')})
            return True
        if tail == '/continuity-acceptance/change-control/reset-signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._read_json_body()
            proof = self.unified_release_program_continuity_acceptance_change_store.reset_acceptance_signoff(program_id, payload)
            self._send_json({'ok': proof.get('status') == 'applied', 'reset_proof': proof, 'summary': {'reset_proof_hash': proof.get('integrity_hash')}, 'status': proof.get('status')})
            return True
        if tail == '/continuity-acceptance/change-control/lifecycle':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_acceptance_change_store.refresh_lifecycle_audit(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'lifecycle_report': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity-acceptance/change-control/archive':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_acceptance_change_store.export_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/continuity-acceptance/change-control/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_acceptance_change_store.build_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256'), 'manifest_hash': result.get('manifest_hash')}})
            return True
        if tail == '/continuity-acceptance/change-control/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_acceptance_change_store.verify_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity-acceptance/change-control/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_continuity_acceptance_change_store.gate(program_id, required=True, archive_zip_path=payload.get('archive_zip') or payload.get('change_control_archive'), verification_report_path=payload.get('verification_report') or payload.get('change_control_verification_report'), acceptance_archive=payload.get('acceptance_archive'), acceptance_verification_report=payload.get('acceptance_verification_report'), acceptance_signoff_binding=payload.get('acceptance_signoff_binding'))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
