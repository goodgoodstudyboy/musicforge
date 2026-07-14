from __future__ import annotations

from http import HTTPStatus


class ProgramHandoffHttpRoutes:
    def _dispatch_handoff(self, method, program_id, tail) -> bool:
        return (
            self._dispatch_handoff_review(method, program_id, tail)
            or self._dispatch_handoff_responses(method, program_id, tail)
            or self._dispatch_handoff_decision(method, program_id, tail)
        )

    def _dispatch_handoff_review(self, method, program_id, tail) -> bool:
        if tail == '/handoff':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_handoff_store.get_handoff(program_id)
            report = detail.get('report') or {}
            self._send_json({'ok': True, **detail, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/handoff/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_handoff_store.refresh_handoff(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') in {'ready_for_review', 'ready_for_signoff'}, 'report': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/handoff/review-pack':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            pack = self.unified_release_program_handoff_store.export_review_pack(program_id, self._optional_json_body())
            self._send_json({'ok': pack.get('status') == 'ready', 'review_pack': pack, 'summary': {'review_pack_id': pack.get('review_pack_id')}, 'status': pack.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/handoff/review-packs/') and tail.endswith('/zip'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            review_pack_id = tail.split('/')[3]
            result = self.unified_release_program_handoff_store.build_review_pack_zip(program_id, review_pack_id)
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        if tail.startswith('/handoff/review-packs/') and tail.endswith('/verify'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            review_pack_id = tail.split('/')[3]
            report = self.unified_release_program_handoff_store.verify_review_pack_zip(program_id, review_pack_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        return False

    def _dispatch_handoff_responses(self, method, program_id, tail) -> bool:
        if tail == '/handoff/responses/import':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            response = self.unified_release_program_handoff_store.import_response(program_id, self._read_json_body())
            self._send_json({'ok': response.get('status') == 'imported', 'response': response.get('response'), 'verification': response.get('verification'), 'summary': {'response_id': response.get('response', {}).get('response_id')}, 'status': response.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/handoff/responses/') and tail.endswith('/accepted-evidence'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            response_id = tail.split('/')[3]
            result = self.unified_release_program_handoff_store.create_accepted_evidence(program_id, response_id)
            self._send_json({'ok': result.get('status') == 'accepted', **result, 'summary': {'evidence_id': result.get('evidence', {}).get('evidence_id')}}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/handoff/accepted-evidence/') and tail.endswith('/zip'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            evidence_id = tail.split('/')[3]
            result = self.unified_release_program_handoff_store.build_accepted_evidence_zip(program_id, evidence_id)
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        if tail.startswith('/handoff/accepted-evidence/') and tail.endswith('/verify'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            evidence_id = tail.split('/')[3]
            report = self.unified_release_program_handoff_store.verify_accepted_evidence_zip(program_id, evidence_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        return False

    def _dispatch_handoff_decision(self, method, program_id, tail) -> bool:
        if tail == '/handoff/decision-board/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            board = self.unified_release_program_handoff_store.refresh_decision_board(program_id, self._optional_json_body())
            self._send_json({'ok': board.get('status') == 'ready_for_signoff', 'decision_board': board, 'summary': board.get('readiness', {}), 'status': board.get('status')})
            return True
        if tail == '/handoff/signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_release_program_handoff_store.signoff_handoff(program_id, self._optional_json_body())
            self._send_json({'ok': signoff.get('status') == 'signed', 'signoff': signoff, 'summary': {'signoff_hash': signoff.get('integrity_hash')}, 'status': signoff.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/handoff/archive/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_handoff_store.export_handoff_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/handoff/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_handoff_store.build_handoff_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        if tail == '/handoff/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_handoff_store.verify_handoff_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/handoff/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_handoff_store.gate(program_id, required=True, handoff_archive_zip_path=payload.get('handoff_archive_zip'), handoff_archive_verification_report_path=payload.get('handoff_archive_verification_report'), external_evidence_manifest=payload.get('external_evidence_manifest'), handoff_signoff_binding=payload.get('handoff_signoff_binding'))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
