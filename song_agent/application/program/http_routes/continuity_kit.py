from __future__ import annotations

from song_agent.application.program.http_context import ProgramHttpContext

from http import HTTPStatus

class ProgramContinuityKitHttpRoutes(ProgramHttpContext):
    def _dispatch_continuity_kit(self, method, program_id, tail) -> bool:
        if tail == '/continuity-kit':
            if method != 'GET':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            detail = self.unified_release_program_continuity_distribution_store.get_kit(program_id)
            source = detail.get('source_binding') or {}
            self._send_json({'ok': True, **detail, 'summary': source, 'status': source.get('status') or 'unknown'})
            return True
        if tail == '/continuity-kit/prepare':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            source = self.unified_release_program_continuity_distribution_store.prepare_kit(program_id, self._optional_json_body())
            self._send_json({'ok': source.get('status') == 'passed', 'source_binding': source, 'summary': source, 'status': source.get('status')}, status=HTTPStatus.CREATED)
            return True
        if tail == '/continuity-kit/export':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            manifest = self.unified_release_program_continuity_distribution_store.export_kit(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'manifest': manifest, 'summary': {'manifest_hash': manifest.get('integrity_hash')}, 'status': 'passed'})
            return True
        if tail == '/continuity-kit/zip':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            result = self.unified_release_program_continuity_distribution_store.build_kit_zip(program_id, self._optional_json_body())
            self._send_json({'ok': result.get('status') == 'passed', **result, 'summary': {'zip_sha256': result.get('zip_sha256'), 'manifest_hash': result.get('manifest_hash')}})
            return True
        if tail == '/continuity-kit/verify':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            report = self.unified_release_program_continuity_distribution_store.verify_kit(program_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity-kit/receipt-template':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            template = self.unified_release_program_continuity_distribution_store.create_receiver_receipt_template(program_id, self._optional_json_body())
            self._send_json({'ok': True, 'receiver_receipt_template': template, 'summary': {'kit_sha256': template.get('kit_sha256')}, 'status': 'passed'})
            return True
        if tail == '/continuity-kit/receipts':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            receipt = self.unified_release_program_continuity_distribution_store.import_receiver_receipt(program_id, self._read_json_body())
            self._send_json({'ok': receipt.get('decision') == 'accepted', 'receiver_receipt': receipt, 'summary': {'receipt_id': receipt.get('receipt_id')}, 'status': receipt.get('decision')}, status=HTTPStatus.CREATED)
            return True
        if tail.startswith('/continuity-kit/receipts/') and tail.endswith('/verify'):
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            receipt_id = tail.split('/')[3]
            report = self.unified_release_program_continuity_distribution_store.verify_receiver_receipt(program_id, receipt_id, self._optional_json_body())
            self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
            return True
        if tail == '/continuity-kit/gate':
            if method != 'POST':
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return True
            payload = self._optional_json_body()
            gate = self.unified_release_program_continuity_distribution_store.gate(program_id, required=True, kit_zip_path=payload.get('kit_zip') or payload.get('continuity_kit'), verification_report_path=payload.get('verification_report') or payload.get('continuity_kit_verification_report'), receiver_receipt_path=payload.get('receiver_receipt'), require_receiver_receipt=bool(payload.get('require_receiver_receipt', False)))
            self._send_json({'ok': gate.get('status') == 'passed', 'gate': gate, 'summary': gate.get('summary', {}), 'status': gate.get('status')})
            return True
        return False
