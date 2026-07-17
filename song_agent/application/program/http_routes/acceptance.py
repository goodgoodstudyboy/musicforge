from __future__ import annotations

from song_agent.application.program.http_context import ProgramHttpContext

from http import HTTPStatus

class ProgramAcceptanceHttpRoutes(ProgramHttpContext):
    def _dispatch_acceptance(self, method, program_id, tail) -> bool:
        if tail == '/continuity-acceptance':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_continuity_acceptance_store.get_board(program_id)
            report = detail.get('report') or {}
            self._send_json({'ok': True, **detail, 'summary': report.get('summary', {}), 'status': report.get('status') or 'unknown'})
            return True
        if tail == '/continuity-acceptance/responses':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_acceptance_store.import_response(program_id, self._read_json_body())
            self._send_json({'ok': result.get('status') == 'imported', **result, 'summary': {'response_id': result.get('response', {}).get('response_id')}, 'status': result.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/continuity-acceptance/responses/') and tail.endswith('/accepted-evidence'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            response_id = tail.split('/')[3]
            result = self.unified_release_program_continuity_acceptance_store.create_accepted_evidence(program_id, response_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'accepted', **result, 'summary': {'evidence_id': result.get('evidence', {}).get('evidence_id')}, 'status': result.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/continuity-acceptance/board':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            board = self.unified_release_program_continuity_acceptance_store.refresh_decision_board(program_id, self._optional_json_body())
            self._send_json({'ok': board.get('status') == 'ready_for_signoff', 'board': board, 'summary': board.get('readiness', {}), 'status': board.get('status')})
            return True
        if tail == '/continuity-acceptance/signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_release_program_continuity_acceptance_store.signoff_acceptance(program_id, self._read_json_body())
            self._send_json({'ok': signoff.get('status') == 'signed', 'signoff': signoff, 'summary': {'signoff_hash': signoff.get('integrity_hash')}, 'status': signoff.get('status')})
            return True
        if tail == '/continuity-acceptance/archive':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_acceptance_store.export_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/continuity-acceptance/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_acceptance_store.build_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256'), 'manifest_hash': result.get('manifest_hash')}})
            return True
        if tail == '/continuity-acceptance/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_acceptance_store.verify_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity-acceptance/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_continuity_acceptance_store.gate(program_id, required=True, archive_zip_path=payload.get('archive_zip') or payload.get('continuity_acceptance_archive'), verification_report_path=payload.get('verification_report') or payload.get('continuity_acceptance_verification_report'), continuity_kit=payload.get('continuity_kit'), continuity_kit_verification_report=payload.get('continuity_kit_verification_report'), signoff_binding=payload.get('signoff_binding'))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
