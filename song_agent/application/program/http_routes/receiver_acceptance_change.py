from __future__ import annotations

from http import HTTPStatus

class ProgramReceiverAcceptanceChangeHttpRoutes:
    def _dispatch_receiver_acceptance_change(self, method, program_id, tail) -> bool:
        change_roots = {'/continuity-command-center-acceptance/change-control', '/continuity-command-center/acceptance/change'}
        if tail in change_roots:
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_continuity_command_center_acceptance_change_store.get_state(program_id)
            state = detail.get('state') or {}
            self._send_json({'ok': True, **detail, 'status': state.get('status') or 'not_configured', 'summary': state})
            return True
        if tail in {root + '/cr' for root in change_roots}:
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request = self.unified_release_program_continuity_command_center_acceptance_change_store.create_change_request(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'change_request': request, 'status': request.get('status'), 'summary': {'change_request_id': request.get('change_request_id')}}, status=HTTPStatus.CREATED)
            return True
        if any((tail.startswith(root + '/cr/') and tail.endswith('/approve') for root in change_roots)):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request_id = tail.split('/')[-2]
            approval = self.unified_release_program_continuity_command_center_acceptance_change_store.approve_change_request(program_id, request_id, self._optional_json_body())
            self._send_json({'ok': True, 'approval': approval, 'status': approval.get('status'), 'summary': {'approval_hash': approval.get('integrity_hash')}})
            return True
        if any((tail.startswith(root + '/cr/') and tail.endswith('/reset-signoff') for root in change_roots)):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            request_id = tail.split('/')[-2]
            proof = self.unified_release_program_continuity_command_center_acceptance_change_store.reset_receiver_acceptance_signoff(program_id, request_id, self._optional_json_body())
            self._send_json({'ok': proof.get('status') == 'applied', 'reset_proof': proof, 'status': proof.get('status'), 'summary': {'reset_proof_hash': proof.get('integrity_hash')}})
            return True
        action_routes = {'/lifecycle': 'lifecycle', '/export': 'export', '/zip': 'zip', '/verify': 'verify', '/gate': 'gate'}
        matched_action = next((action for suffix, action in action_routes.items() if tail in {root + suffix for root in change_roots}), None)
        if matched_action:
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            if matched_action == 'lifecycle':
                report = self.unified_release_program_continuity_command_center_acceptance_change_store.refresh_lifecycle_audit(program_id, payload)
                self._send_json({'ok': report.get('status') == 'passed', 'lifecycle_report': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
                return True
            if matched_action == 'export':
                manifest = self.unified_release_program_continuity_command_center_acceptance_change_store.export_archive(program_id, payload)
                self._send_json({'ok': True, 'manifest': manifest, 'status': 'passed', 'summary': {'manifest_hash': manifest.get('integrity_hash')}})
                return True
            if matched_action == 'zip':
                result = self.unified_release_program_continuity_command_center_acceptance_change_store.build_archive_zip(program_id, payload)
                self._send_json({'ok': result.get('status') == 'passed', **result})
                return True
            if matched_action == 'verify':
                report = self.unified_release_program_continuity_command_center_acceptance_change_store.verify_archive_zip(program_id, payload)
                self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'status': report.get('status'), 'summary': report.get('summary', {})})
                return True
            gate = self.unified_release_program_continuity_command_center_acceptance_change_store.gate(program_id, required=True, archive_zip_path=payload.get('archive_zip') or payload.get('change_archive'), verification_report_path=payload.get('verification_report') or payload.get('change_verification_report'), **{key: value for key, value in payload.items() if key not in {'archive_zip', 'change_archive', 'verification_report', 'change_verification_report'}})
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'status': gate.get('status'), 'summary': gate.get('summary', {})})
            return True
        return False
