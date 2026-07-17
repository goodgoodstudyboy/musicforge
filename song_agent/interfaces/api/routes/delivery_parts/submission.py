from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.interfaces.api.route_contexts.delivery import DeliveryRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class DeliveryRoutesSubmission(DeliveryRouteContext):
    def _handle_submission_route_part_01(self, method: str, release_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method == 'GET':
                batches = self.submission_store.list_submissions(release_id)
                self._send_json({'ok': True, 'release_id': release_id, 'submissions': [self._submission_payload_with_evidence_summary(release_id, _split_state['batch']) for _split_state['batch'] in batches], 'summary': self.submission_store.summary(release_id)})
                return (True, None)
            if method == 'POST':
                _split_state['batch'] = self.submission_store.create_submission(release_id, self._optional_json_body())
                self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/batches' or tail == '':
            if method == 'GET':
                batches = self.submission_store.list_submissions(release_id)
                self._send_json({'ok': True, 'release_id': release_id, 'submissions': [self._submission_payload_with_evidence_summary(release_id, _split_state['batch']) for _split_state['batch'] in batches], 'summary': self.submission_store.summary(release_id)})
                return (True, None)
            if method == 'POST':
                _split_state['batch'] = self.submission_store.create_submission(release_id, self._optional_json_body())
                self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        route = _interfaces_api_runtime._match_submission_tail(tail)
        if route is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Submission route not found.')
            return (True, None)
        _split_state['submission_id'], _split_state['action'], _split_state['item_id'] = route
        _split_state['batch'] = self.submission_store.get_submission(release_id, _split_state['submission_id'])
        if _split_state['action'] == '':
            if method == 'GET':
                _split_state['signoff'] = self.submission_store.read_signoff(release_id, _split_state['submission_id'], default={})
                qa = self._get_or_refresh_submission_qa(release_id, _split_state['batch'], refresh=False)
                self._send_json({'ok': True, 'release_id': release_id, 'submission': self._submission_payload_with_evidence_summary(release_id, _split_state['batch']), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch']), 'qa_summary': _interfaces_api_runtime.submission_qa_summary(qa), 'signoff_summary': _interfaces_api_runtime.submission_signoff_summary(_split_state['signoff']), 'events': self.submission_store.read_events(release_id, _split_state['submission_id'])})
                return (True, None)
            if method in {'POST', 'PATCH'}:
                _split_state['batch'] = self.submission_store.update_submission(release_id, _split_state['submission_id'], self._optional_json_body())
                self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'targets':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._read_json_body()
            target_id = str(_split_state['payload'].get('target_id') or '').strip()
            if not target_id:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'target_id is required.')
                return (True, None)
            _split_state['batch'] = self.submission_store.add_target(release_id, _split_state['submission_id'], target_id)
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
            return (True, None)
        if _split_state['action'] == 'remove-item':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'] = self.submission_store.remove_target(release_id, _split_state['submission_id'], _split_state['item_id'] or '')
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
            return (True, None)
        if _split_state['action'] == 'refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'] = self.submission_store.refresh_items(release_id, _split_state['submission_id'])
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
            return (True, None)
        return (False, None)

    def _handle_submission_route_part_02(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'qa':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self._get_or_refresh_submission_qa(release_id, _split_state['batch'], refresh=False)
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'submission_qa': _split_state['report'], 'summary': _interfaces_api_runtime.submission_qa_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'qa-refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.submission_store.ensure_mutable(_split_state['batch'])
            _split_state['report'] = self._get_or_refresh_submission_qa(release_id, _split_state['batch'], refresh=True)
            self.submission_store.append_event(release_id, _split_state['submission_id'], 'submission_qa_refreshed', {'status': _split_state['report'].get('status')})
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'submission_qa': _split_state['report'], 'summary': _interfaces_api_runtime.submission_qa_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'export':
            if method == 'GET':
                try:
                    _split_state['manifest'] = _interfaces_api_runtime.read_submission_export_manifest(self.submission_store, release_id, _split_state['submission_id'])
                except FileNotFoundError:
                    self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'manifest': {}, 'summary': _interfaces_api_runtime.submission_export_summary({})})
                    return (True, None)
                self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'manifest': _split_state['manifest'], 'summary': _interfaces_api_runtime.submission_export_summary(_split_state['manifest'])})
                return (True, None)
            if method == 'POST':
                self.submission_store.ensure_mutable(_split_state['batch'])
                _split_state['report'] = self._get_or_refresh_submission_qa(release_id, _split_state['batch'], refresh=False)
                _split_state['manifest'] = _interfaces_api_runtime.build_submission_export_bundle(store=self.submission_store, release_id=release_id, submission=_split_state['batch'], qa_report=_split_state['report'], now=_interfaces_api_runtime._utc_now())
                _split_state['batch'] = self.submission_store.get_submission(release_id, _split_state['submission_id'])
                self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'manifest': _split_state['manifest'], 'summary': _interfaces_api_runtime.submission_export_summary(_split_state['manifest'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'export-zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.submission_store.ensure_mutable(_split_state['batch'])
            _split_state['zip_info'] = _interfaces_api_runtime.build_submission_package_zip(self.submission_store, release_id, _split_state['batch'], now=_interfaces_api_runtime._utc_now())
            _split_state['manifest'] = _interfaces_api_runtime.read_submission_export_manifest(self.submission_store, release_id, _split_state['submission_id'])
            _split_state['batch'] = self.submission_store.update_export_summary(release_id, _split_state['submission_id'], _interfaces_api_runtime.submission_export_summary(_split_state['manifest']))
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'zip': _split_state['zip_info'], 'summary': _interfaces_api_runtime.submission_export_summary(_split_state['manifest'])})
            return (True, None)
        if _split_state['action'] == 'export-zip-download':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.submission_store.get_submission(release_id, _split_state['submission_id'])
            self._send_file(self.submission_store.package_zip_path(release_id, _split_state['submission_id']), 'application/zip', filename=f"musicforge-{release_id}-{_split_state['submission_id']}-submission.zip")
            return (True, None)
        return (False, None)

    def _handle_submission_route_part_03(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'signoff':
            if method == 'GET':
                _split_state['signoff'] = self.submission_store.read_signoff(release_id, _split_state['submission_id'], default={})
                self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'signoff': _split_state['signoff'], 'summary': _interfaces_api_runtime.submission_signoff_summary(_split_state['signoff'])})
                return (True, None)
            if method == 'POST':
                self.submission_store.ensure_mutable(_split_state['batch'])
                _split_state['report'] = self._get_or_refresh_submission_qa(release_id, _split_state['batch'], refresh=True)
                _split_state['payload'] = self._optional_json_body()
                if bool(_split_state['payload'].get('require_rights_clearance', False)):
                    rights_gate = self.rights_clearance_store.gate(release_id, required=True, now=_interfaces_api_runtime._utc_now())
                    if rights_gate.get('hard_block') and rights_gate.get('status') == 'failed':
                        self._send_json({'error': str(rights_gate.get('message') or 'Rights clearance gate failed.'), 'rights_clearance': rights_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    try:
                        export_manifest = _interfaces_api_runtime.read_submission_export_manifest(self.submission_store, release_id, _split_state['submission_id'])
                    except FileNotFoundError:
                        export_manifest = {}
                    export_gate = self._package_rights_clearance_export_gate(export_manifest, rights_gate, package_label='Submission')
                    if export_gate.get('status') == 'failed':
                        self._send_json({'error': str(export_gate.get('message') or 'Submission Export is stale. Rebuild export before signoff.'), 'rights_clearance': rights_gate, 'rights_clearance_export': export_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    _split_state['payload'] = {**_split_state['payload'], 'require_rights_clearance': True, 'rights_clearance': rights_gate}
                _split_state['signoff'] = _interfaces_api_runtime.sign_submission_package(store=self.submission_store, release_id=release_id, submission=_split_state['batch'], qa_report=_split_state['report'], payload=_split_state['payload'], now=_interfaces_api_runtime._utc_now())
                _split_state['batch'] = self.submission_store.get_submission(release_id, _split_state['submission_id'])
                self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'signoff': _split_state['signoff'], 'summary': _interfaces_api_runtime.submission_signoff_summary(_split_state['signoff'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'signoff-reset':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['reason'] = str(_split_state['payload'].get('reason') or '').strip()
            if not _split_state['reason']:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'reason is required.')
                return (True, None)
            _split_state['event'] = self.submission_store.reset_signoff(release_id, _split_state['submission_id'], _split_state['reason'])
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'summary': {'status': 'reset'}, 'history_event': _split_state['event']})
            return (True, None)
        if _split_state['action'] == 'verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['report'] = _interfaces_api_runtime.verify_submission_package(self.submission_store.package_zip_path(release_id, _split_state['submission_id']), strict=bool(_split_state['payload'].get('strict', False)), require_submitted=bool(_split_state['payload'].get('require_submitted', False)), require_accepted=bool(_split_state['payload'].get('require_accepted', False)), deep=bool(_split_state['payload'].get('deep', False)))
            _interfaces_api_runtime.write_submission_verification_report(_split_state['report'], self.submission_store.submission_dir(release_id, _split_state['submission_id']) / 'submission-verification-report.json')
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'verification': _split_state['report'], 'summary': _interfaces_api_runtime.submission_verification_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'evidence':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            overview = self.submission_evidence_store.overview(release_id, _split_state['submission_id'])
            self._send_json({'ok': True, **overview})
            return (True, None)
        return (False, None)

    def _handle_submission_route_part_04(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'evidence-report-refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self.submission_evidence_store.refresh_report(release_id, _split_state['submission_id'])
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'evidence_report': _split_state['report'], 'summary': _interfaces_api_runtime.submission_evidence_report_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'evidence-export':
            if method == 'GET':
                try:
                    _split_state['manifest'] = self.submission_evidence_store.read_export_manifest(release_id, _split_state['submission_id'])
                except _interfaces_api_runtime.SubmissionEvidenceNotFoundError:
                    self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'manifest': {}, 'summary': {'status': 'missing'}})
                    return (True, None)
                self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {})})
                return (True, None)
            if method == 'POST':
                _split_state['manifest'] = self.submission_evidence_store.export_evidence(release_id, _split_state['submission_id'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'manifest': _split_state['manifest'], 'summary': _split_state['manifest'].get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'evidence-export-zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['zip_info'] = self.submission_evidence_store.build_zip(release_id, _split_state['submission_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'zip': _split_state['zip_info']})
            return (True, None)
        if _split_state['action'] == 'evidence-export-zip-download':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_file(self.submission_evidence_store.package_zip_path(release_id, _split_state['submission_id']), 'application/zip', filename=f"musicforge-{release_id}-{_split_state['submission_id']}-submission-evidence.zip")
            return (True, None)
        if _split_state['action'] == 'evidence-signoff':
            if method == 'GET':
                _split_state['signoff'] = self.submission_evidence_store.read_signoff(release_id, _split_state['submission_id'], default={})
                self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'signoff': _split_state['signoff'], 'summary': _interfaces_api_runtime.submission_evidence_signoff_summary(_split_state['signoff'])})
                return (True, None)
            if method == 'POST':
                _split_state['signoff'] = self.submission_evidence_store.signoff_evidence(release_id, _split_state['submission_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'signoff': _split_state['signoff'], 'summary': _interfaces_api_runtime.submission_evidence_signoff_summary(_split_state['signoff'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'evidence-signoff-reset':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['reason'] = str(_split_state['payload'].get('reason') or '').strip()
            _split_state['event'] = self.submission_evidence_store.reset_signoff(release_id, _split_state['submission_id'], _split_state['reason'])
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'summary': {'status': 'reset'}, 'history_event': _split_state['event']})
            return (True, None)
        return (False, None)

    def _handle_submission_route_part_05(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'evidence-verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['report'] = _interfaces_api_runtime.verify_submission_evidence_package(self.submission_evidence_store.package_zip_path(release_id, _split_state['submission_id']), strict=bool(_split_state['payload'].get('strict', False)), deep=bool(_split_state['payload'].get('deep', False)), require_submitted=bool(_split_state['payload'].get('require_submitted', False)), require_accepted=bool(_split_state['payload'].get('require_accepted', False)), require_rights_clearance=bool(_split_state['payload'].get('require_rights_clearance', False)))
            _interfaces_api_runtime.write_submission_evidence_verification_report(_split_state['report'], self.submission_store.submission_dir(release_id, _split_state['submission_id']) / 'submission-evidence-verification-report.json')
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'verification': _split_state['report'], 'summary': _interfaces_api_runtime.submission_evidence_verification_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'evidence-upload-attachment':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            attachment = self.submission_evidence_store.upload_attachment(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._read_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'item_id': _split_state['item_id'], 'attachment': attachment}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['action'] == 'evidence-submission-receipt':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'], _split_state['evidence'] = self.submission_evidence_store.record_submission(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._optional_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'evidence': _split_state['evidence'], 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['action'] == 'evidence-feedback':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'], _split_state['evidence'] = self.submission_evidence_store.record_feedback(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._optional_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'evidence': _split_state['evidence'], 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['action'] == 'evidence-acceptance':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'], _split_state['evidence'] = self.submission_evidence_store.mark_accepted(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._optional_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'evidence': _split_state['evidence'], 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['action'] == 'evidence-resubmission-round':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            round_record = self.submission_evidence_store.create_resubmission_round(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._read_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission_id': _split_state['submission_id'], 'item_id': _split_state['item_id'], 'round': round_record}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['action'] == 'record-submission':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'], _split_state['evidence'] = self.submission_evidence_store.record_submission(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._optional_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'evidence': _split_state['evidence'], 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
            return (True, None)
        if _split_state['action'] == 'record-feedback':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'], _split_state['evidence'] = self.submission_evidence_store.record_feedback(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._optional_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'evidence': _split_state['evidence'], 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
            return (True, None)
        return (False, None)

    def _handle_submission_route_part_06(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'mark-accepted':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'], _split_state['evidence'] = self.submission_evidence_store.mark_accepted(release_id, _split_state['submission_id'], _split_state['item_id'] or '', self._optional_json_body())
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'evidence': _split_state['evidence'], 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
            return (True, None)
        if _split_state['action'] == 'archive':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['batch'] = self.submission_store.archive_submission(release_id, _split_state['submission_id'])
            self._send_json({'ok': True, 'release_id': release_id, 'submission': _split_state['batch'].to_dict(), 'summary': _interfaces_api_runtime.submission_batch_summary(_split_state['batch'])})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Submission route not found.')
        return (False, None)

    def _handle_submission_route(self, method: str, release_id: str, tail: str) -> None:
        _split_state: dict[str, _InferenceType] = {}
        try:
            _split_result = self._handle_submission_route_part_01(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_submission_route_part_02(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_submission_route_part_03(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_submission_route_part_04(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_submission_route_part_05(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_submission_route_part_06(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except (_interfaces_api_runtime.ReleaseNotFoundError, _interfaces_api_runtime.SubmissionNotFoundError, _interfaces_api_runtime.SubmissionEvidenceNotFoundError, FileNotFoundError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.SubmissionStateError, _interfaces_api_runtime.SubmissionEvidenceStateError, _interfaces_api_runtime.SubmissionExportError, _interfaces_api_runtime.ReleaseStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.SubmissionValidationError, _interfaces_api_runtime.SubmissionEvidenceValidationError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
