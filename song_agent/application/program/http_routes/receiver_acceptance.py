from __future__ import annotations

from http import HTTPStatus

class ProgramReceiverAcceptanceHttpRoutes:
    def _dispatch_receiver_acceptance(self, method, program_id, tail) -> bool:
        if tail == '/continuity-command-center-acceptance':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            state = self.unified_release_program_continuity_command_center_acceptance_store.status(program_id)
            self._send_json({'ok': True, **state})
            return True
        if tail == '/continuity-command-center-acceptance/review-pack':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_command_center_acceptance_store.create_review_pack(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result}, status=HTTPStatus.CREATED)
            return True
        if tail == '/continuity-command-center-acceptance/review-pack/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_acceptance_store.verify_review_pack(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
            return True
        if tail == '/continuity-command-center-acceptance/responses/import':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._read_json_body()
            forbidden = sorted({str(key) for key in payload if str(key).lower() in {'source_path', 'local_path', 'file_path', 'path'}})
            if forbidden:
                self._send_error(HTTPStatus.BAD_REQUEST, 'Receiver response import does not accept path fields: ' + ', '.join(forbidden))
                return True
            result = self.unified_release_program_continuity_command_center_acceptance_store.import_response(program_id, payload)
            self._send_json({'ok': result.get('status') == 'imported', **result, 'summary': {'response_id': result['response'].get('response_id')}}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/continuity-command-center-acceptance/responses/') and tail.endswith('/accepted-evidence'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            response_id = tail.split('/')[3]
            result = self.unified_release_program_continuity_command_center_acceptance_store.create_accepted_evidence(program_id, response_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'accepted', **result}, status=HTTPStatus.CREATED)
            return True
        if tail == '/continuity-command-center-acceptance/board/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_acceptance_store.refresh_board(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'ready_for_signoff', 'report': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
            return True
        if tail == '/continuity-command-center-acceptance/signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_release_program_continuity_command_center_acceptance_store.signoff(program_id, self._optional_json_body())
            self._send_json({'ok': signoff.get('status') == 'signed', 'signoff': signoff, 'status': signoff.get('status'), 'summary': {'signoff_hash': signoff.get('integrity_hash')}})
            return True
        if tail == '/continuity-command-center-acceptance/archive/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_command_center_acceptance_store.export_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'status': 'passed', 'summary': {'manifest_hash': manifest.get('integrity_hash')}})
            return True
        if tail == '/continuity-command-center-acceptance/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_command_center_acceptance_store.build_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result})
            return True
        if tail == '/continuity-command-center-acceptance/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_acceptance_store.verify_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
            return True
        return False
