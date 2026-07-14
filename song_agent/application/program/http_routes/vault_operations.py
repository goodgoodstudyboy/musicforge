from __future__ import annotations

from http import HTTPStatus

class ProgramVaultOperationsHttpRoutes:
    def _dispatch_vault_operations(self, method, program_id, tail) -> bool:
        if tail == '/vault-operations/policy':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            policy = self.unified_release_program_vault_operations_store.init_policy(program_id, self._optional_json_body())
            self._send_json({'ok': policy.get('status') == 'active', 'policy': policy, 'summary': {'policy_hash': policy.get('integrity_hash')}, 'status': policy.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/vault-operations/register-vault':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            registry = self.unified_release_program_vault_operations_store.register_vault(program_id, self._optional_json_body())
            self._send_json({'ok': registry.get('status') == 'current', 'registry': registry, 'summary': registry.get('summary', {}), 'status': registry.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/vault-operations/refresh-registry':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            registry = self.unified_release_program_vault_operations_store.refresh_registry(program_id, self._optional_json_body())
            self._send_json({'ok': registry.get('status') == 'current', 'registry': registry, 'summary': registry.get('summary', {}), 'status': registry.get('status')})
            return True
        if tail == '/vault-operations/review':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            review = self.unified_release_program_vault_operations_store.run_custody_review(program_id, self._optional_json_body())
            self._send_json({'ok': review.get('status') == 'passed', 'review': review, 'summary': review.get('summary', {}), 'status': review.get('status')})
            return True
        if tail == '/vault-operations/rotation-plan':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            plan = self.unified_release_program_vault_operations_store.create_rotation_plan(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'rotation_plan': plan, 'summary': {'plan_id': plan.get('plan_id')}, 'status': plan.get('status')})
            return True
        if tail == '/vault-operations/supersede':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            registry = self.unified_release_program_vault_operations_store.supersede_vault(program_id, self._optional_json_body())
            self._send_json({'ok': registry.get('status') == 'current', 'registry': registry, 'summary': registry.get('summary', {}), 'status': registry.get('status')})
            return True
        if tail == '/vault-operations/revoke':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            registry = self.unified_release_program_vault_operations_store.revoke_vault(program_id, self._optional_json_body())
            self._send_json({'ok': registry.get('status') != 'current', 'registry': registry, 'summary': registry.get('summary', {}), 'status': registry.get('status')})
            return True
        if tail == '/vault-operations/transfer-pack':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            transfer = self.unified_release_program_vault_operations_store.create_transfer_pack(program_id, self._optional_json_body())
            self._send_json({'ok': transfer.get('status') == 'ready', 'transfer_report': transfer, 'summary': transfer.get('summary', {}), 'status': transfer.get('status')})
            return True
        if tail == '/vault-operations/signoff':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            signoff = self.unified_release_program_vault_operations_store.signoff_operations(program_id, self._optional_json_body())
            self._send_json({'ok': signoff.get('status') == 'signed', 'signoff': signoff, 'summary': {'signoff_hash': signoff.get('integrity_hash')}, 'status': signoff.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/vault-operations/archive/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_vault_operations_store.export_archive(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/vault-operations/archive/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_vault_operations_store.build_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256'), 'manifest_hash': result.get('manifest_hash')}})
            return True
        if tail == '/vault-operations/archive/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_vault_operations_store.verify_archive_zip(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/vault-operations/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_vault_operations_store.gate(program_id, required=True, archive_zip_path=payload.get('archive_zip') or payload.get('vault_operations_archive'), verification_report_path=payload.get('verification_report') or payload.get('vault_operations_verification_report'), signoff_binding_path=payload.get('signoff_binding') or payload.get('vault_operations_signoff_binding'))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
