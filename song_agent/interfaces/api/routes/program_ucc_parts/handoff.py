from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class ProgramUccHandoffRoutes:
    def _dispatch_ucc_handoff(self, method, center_id, tail) -> bool:
        if tail == '/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            report = self.unified_command_center_signoff_store.verify_archive(center_id, payload)
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/archive/download':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self._send_file(self.unified_command_center_signoff_store.archive_zip_path(center_id), 'application/zip', filename='unified-command-center-archive.zip')
            return True
        if tail == '/handoff':
            if method == 'GET':
                manifest = read_json(self.unified_command_center_handoff_store.manifest_path(center_id)) if self.unified_command_center_handoff_store.manifest_path(center_id).exists() else {}
                self._send_json({'ok': bool(manifest), 'manifest': manifest, 'summary': manifest.get('summary', {}) if manifest else {}})
                return True
            if method == 'POST':
                manifest = self.unified_command_center_handoff_store.export_handoff(center_id)
                self._send_json({'ok': True, 'manifest': manifest, 'summary': manifest.get('summary', {}), 'status': 'passed'})
                return True
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        if tail == '/handoff/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_command_center_handoff_store.build_handoff_zip(center_id)
            self._send_json({'ok': True, **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        if tail == '/handoff/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            report = self.unified_command_center_handoff_store.verify_handoff(center_id, payload)
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/handoff/download':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self._send_file(self.unified_command_center_handoff_store.zip_path(center_id), 'application/zip', filename='musicforge-final-handoff-pack.zip')
            return True
        if tail == '/change-requests':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            cr = self.unified_command_center_signoff_store.create_change_request(center_id, self._optional_json_body())
            self._send_json({'ok': True, 'change_request': cr, 'summary': {'change_request_id': cr.get('change_request_id')}, 'status': cr.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/change-requests/') and tail.endswith('/approve'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            change_request_id = tail.split('/')[2]
            cr = self.unified_command_center_signoff_store.approve_change_request(center_id, change_request_id, self._optional_json_body())
            self._send_json({'ok': True, 'change_request': cr, 'summary': {'change_request_id': cr.get('change_request_id')}, 'status': cr.get('status')})
            return True
        if tail.startswith('/signoff/reset/'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            change_request_id = tail.split('/')[-1]
            result = self.unified_command_center_signoff_store.reset_signoff(center_id, change_request_id, self._optional_json_body())
            self._send_json({'ok': True, **result})
            return True
        if tail == '/download':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            self._send_file(self.unified_command_center_store.zip_path(center_id), 'application/zip', filename='musicforge-unified-command-center.zip')
            return True
        return False
