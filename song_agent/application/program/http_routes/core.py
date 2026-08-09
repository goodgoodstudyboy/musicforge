from __future__ import annotations

from song_agent.application.program.http_context import ProgramHttpContext
from song_agent.platform.contracts.coercion import as_document

from http import HTTPStatus

class ProgramCoreHttpRoutes(ProgramHttpContext):
    def _dispatch_core(self, method, program_id, tail) -> bool:
        if tail in {'', '/'}:
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.service.get_program(program_id)
            report = as_document(detail.get('report'))
            program = as_document(detail.get('program'))
            self._send_json({'ok': True, **detail, 'summary': report.get('summary', {}), 'status': report.get('status') or program.get('status')})
            return True
        if tail == '/items':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            item = self.unified_release_program_store.add_train_item(program_id, self._read_json_body())
            self._send_json({'ok': True, 'item': item, 'summary': {'item_id': item.get('item_id')}, 'status': item.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_store.refresh_report(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'ready', 'report': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_release_program_store.signoff(program_id, self._optional_json_body())
            self._send_json({'ok': signoff.get('status') == 'signed', 'signoff': signoff, 'summary': {'signoff_hash': signoff.get('integrity_hash')}, 'status': signoff.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_store.export_program(program_id)
            self._send_json({'ok': True, 'manifest': manifest, 'summary': manifest.get('summary', {}), 'status': 'passed'})
            return True
        if tail == '/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_store.build_zip(program_id)
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        if tail == '/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_store.verify_package(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.service.evaluate_gate(program_id, payload)
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
