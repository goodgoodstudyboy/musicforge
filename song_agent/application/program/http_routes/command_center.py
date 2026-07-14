from __future__ import annotations

from http import HTTPStatus

class ProgramCommandCenterHttpRoutes:
    def _dispatch_command_center(self, method, program_id, tail) -> bool:
        if tail == '/continuity-command-center':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_continuity_command_center_store.get_command_center(program_id)
            report = detail.get('report') or {}
            self._send_json({'ok': True, **detail, 'summary': report.get('summary', {}), 'status': report.get('status') or 'unknown'})
            return True
        if tail == '/continuity-command-center/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_store.refresh_command_center(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'ready', 'report': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity-command-center/run-safe':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_command_center_store.run_safe(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') in {'passed', 'warning'}, 'runbook_result': result, 'summary': result.get('summary', {}), 'status': result.get('status')})
            return True
        if tail == '/continuity-command-center/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_command_center_store.export_package(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/continuity-command-center/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_command_center_store.build_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256'), 'manifest_hash': result.get('manifest_hash')}})
            return True
        if tail == '/continuity-command-center/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_command_center_store.verify_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity-command-center/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_continuity_command_center_store.gate(program_id, required=True, command_center_zip_path=payload.get('command_center_zip') or payload.get('continuity_command_center'), verification_report_path=payload.get('verification_report') or payload.get('command_center_verification_report'), evidence_manifest_path=payload.get('external_evidence_manifest') or payload.get('evidence_manifest'))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
