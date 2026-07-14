from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class ProgramUccCoreRoutes:
    def _dispatch_ucc_core(self, method, center_id, tail) -> bool:
        if tail in {'', '/'}:
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            center = self.unified_command_center_store.read_center(center_id)
            report = self.unified_command_center_store.read_report(center_id) if self.unified_command_center_store.report_path(center_id).exists() else {}
            inventory = read_json(self.unified_command_center_store.inventory_path(center_id)) if self.unified_command_center_store.inventory_path(center_id).exists() else {}
            readiness = read_json(self.unified_command_center_store.readiness_path(center_id)) if self.unified_command_center_store.readiness_path(center_id).exists() else {}
            gap_plan = read_json(self.unified_command_center_store.gap_plan_path(center_id)) if self.unified_command_center_store.gap_plan_path(center_id).exists() else {}
            runbook = read_json(self.unified_command_center_store.runbook_path(center_id)) if self.unified_command_center_store.runbook_path(center_id).exists() else {}
            self._send_json({'ok': True, 'center': center, 'report': report, 'inventory': inventory, 'readiness': readiness, 'gap_plan': gap_plan, 'runbook': runbook, 'summary': report.get('summary', {}) if report else {}})
            return True
        if tail == '/refresh':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_command_center_store.refresh(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
            self._send_json({'ok': report.get('status') == 'ready', 'center_id': center_id, 'report': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/runbook':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            runbook = self.unified_command_center_store.create_runbook(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
            self._send_json({'ok': True, 'center_id': center_id, 'runbook': runbook, 'summary': runbook.get('summary', {})})
            return True
        if tail == '/run-safe':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_command_center_store.run_safe(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
            self._send_json({'ok': result.get('summary', {}).get('failed_count') == 0, 'center_id': center_id, 'runbook_result': result, 'summary': result.get('summary', {})})
            return True
        if tail == '/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_command_center_store.export_package(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
            self._send_json({'ok': result.get('status') == 'ready', **result})
            return True
        if tail == '/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_command_center_store.build_zip(center_id, self._unified_command_center_evidence_from_payload(self._optional_json_body()))
            self._send_json({'ok': result.get('status') == 'ready', **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        if tail == '/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            report = self.unified_command_center_store.verify_zip(center_id, evidence=self._unified_command_center_evidence_from_payload(payload), strict=bool(payload.get('strict', True)), require_ready=bool(payload.get('require_ready', False)))
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_command_center_signoff_store.signoff(center_id, self._optional_json_body())
            self._send_json({'ok': True, 'signoff': signoff, 'summary': {'signoff_hash': signoff.get('integrity_hash')}, 'status': signoff.get('status')})
            return True
        if tail == '/archive':
            if method == 'GET':
                manifest = read_json(self.unified_command_center_signoff_store.archive_manifest_path(center_id)) if self.unified_command_center_signoff_store.archive_manifest_path(center_id).exists() else {}
                self._send_json({'ok': bool(manifest), 'manifest': manifest, 'summary': manifest.get('summary', {}) if manifest else {}})
                return True
            if method == 'POST':
                manifest = self.unified_command_center_signoff_store.export_archive(center_id)
                self._send_json({'ok': True, 'manifest': manifest, 'summary': manifest.get('summary', {}), 'status': 'passed'})
                return True
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return True
        if tail == '/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_command_center_signoff_store.build_archive_zip(center_id)
            self._send_json({'ok': True, **result, 'summary': {'zip_sha256': result.get('zip_sha256')}})
            return True
        return False
