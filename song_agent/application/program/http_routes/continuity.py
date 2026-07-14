from __future__ import annotations

from http import HTTPStatus

class ProgramContinuityHttpRoutes:
    def _dispatch_continuity(self, method, program_id, tail) -> bool:
        return (
            self._dispatch_continuity_workflow(method, program_id, tail)
            or self._dispatch_continuity_archive(method, program_id, tail)
        )

    def _dispatch_continuity_workflow(self, method, program_id, tail) -> bool:
        if tail == '/continuity':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_continuity_store.get_continuity(program_id)
            report = detail.get('report') or {}
            self._send_json({'ok': True, **detail, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity/policy':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            policy = self.unified_release_program_continuity_store.init_policy(program_id, self._optional_json_body())
            self._send_json({'ok': policy.get('status') == 'active', 'policy': policy, 'summary': {'policy_hash': policy.get('integrity_hash')}, 'status': policy.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/continuity/plan':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            plan = self.unified_release_program_continuity_store.create_recovery_plan(program_id, self._optional_json_body())
            self._send_json({'ok': plan.get('status') == 'planned', 'recovery_plan': plan, 'summary': {'plan_hash': plan.get('integrity_hash')}, 'status': plan.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/continuity/drill':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            drill = self.unified_release_program_continuity_store.run_recovery_drill(program_id, self._optional_json_body())
            self._send_json({'ok': drill.get('status') == 'passed', 'drill_report': drill, 'summary': drill.get('summary', {}), 'status': drill.get('status')})
            return True
        if tail == '/continuity/readiness':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            readiness = self.unified_release_program_continuity_store.refresh_readiness(program_id, self._optional_json_body())
            self._send_json({'ok': readiness.get('status') == 'passed', 'readiness': readiness, 'summary': readiness.get('summary', {}), 'status': readiness.get('status')})
            return True
        if tail == '/continuity/runbook':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            runbook = self.unified_release_program_continuity_store.generate_runbook(program_id, self._optional_json_body())
            self._send_json({'ok': runbook.get('status') == 'ready', 'runbook': runbook, 'summary': runbook.get('summary', {}), 'status': runbook.get('status')})
            return True
        if tail == '/continuity/signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_release_program_continuity_store.signoff_continuity(program_id, self._optional_json_body())
            self._send_json({'ok': signoff.get('status') == 'signed', 'signoff': signoff, 'summary': {'signoff_hash': signoff.get('integrity_hash')}, 'status': signoff.get('status')}, status=HTTPStatus.CREATED)
            return True
        return False

    def _dispatch_continuity_archive(self, method, program_id, tail) -> bool:
        if tail == '/continuity/archive/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_store.export_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/continuity/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_store.build_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256'), 'manifest_hash': result.get('manifest_hash')}})
            return True
        if tail == '/continuity/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_store.verify_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_continuity_store.gate(program_id, required=True, archive_zip_path=payload.get('archive_zip') or payload.get('continuity_archive'), verification_report_path=payload.get('verification_report') or payload.get('continuity_verification_report'), signoff_binding_path=payload.get('signoff_binding') or payload.get('continuity_signoff_binding'), vault_operations_archive_path=payload.get('vault_operations_archive'), vault_operations_verification_report_path=payload.get('vault_operations_verification_report'), vault_operations_signoff_binding_path=payload.get('vault_operations_signoff_binding'))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
