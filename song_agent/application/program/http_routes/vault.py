from __future__ import annotations

from song_agent.application.program.http_context import ProgramHttpContext
from song_agent.platform.contracts.coercion import as_document

from http import HTTPStatus

class ProgramVaultHttpRoutes(ProgramHttpContext):
    def _dispatch_vault(self, method, program_id, tail) -> bool:
        if tail == '/vault':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_vault_store.get_vault(program_id)
            report = as_document(detail.get('report'))
            self._send_json({'ok': True, **detail, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/vault/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_vault_store.refresh_vault(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'report': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/vault/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_vault_store.export_vault(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/vault/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_vault_store.build_vault_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256'), 'anchor_path': result.get('anchor_path')}})
            return True
        if tail == '/vault/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_vault_store.verify_vault_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/vault/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_vault_store.gate(program_id, required=True, vault_zip_path=payload.get('vault_zip') or payload.get('vault'), vault_verification_report_path=payload.get('vault_verification_report'), vault_anchor_path=payload.get('vault_anchor') or payload.get('anchor'), require_current_program=bool(payload.get('require_current_program', False)), require_current_operations=bool(payload.get('require_current_operations', False)), require_current_handoff=bool(payload.get('require_current_handoff', False)), require_accepted_evidence=bool(payload.get('require_accepted_evidence', True)))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        if tail == '/vault-operations':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_vault_operations_store.get_operations(program_id)
            report = as_document(detail.get('report'))
            self._send_json({'ok': True, **detail, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        return False
