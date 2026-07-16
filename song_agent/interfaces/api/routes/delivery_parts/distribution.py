from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class DeliveryRoutesDistribution:
    def _handle_distribution_route_part_01(self, method: str, release_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            targets = self.distribution_store.list_targets(release_id)
            self._send_json({'ok': True, 'release_id': release_id, 'summary': self.distribution_store.summary(release_id), 'targets': [_split_state['target'].to_dict() for _split_state['target'] in targets], 'template_packs': self.distribution_template_store.list_templates(), 'events': self.distribution_store.read_events(release_id)})
            return (True, None)
        if tail == '/targets':
            if method == 'GET':
                targets = self.distribution_store.list_targets(release_id)
                self._send_json({'ok': True, 'release_id': release_id, 'targets': [_split_state['target'].to_dict() for _split_state['target'] in targets], 'summary': self.distribution_store.summary(release_id), 'template_packs': self.distribution_template_store.list_templates()})
                return (True, None)
            if method == 'POST':
                _split_state['target'] = self.distribution_store.create_target(release_id, self._optional_json_body())
                self._send_json({'ok': True, 'release_id': release_id, 'target': _split_state['target'].to_dict(), 'summary': _interfaces_api_runtime.distribution_target_summary(_split_state['target'])}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/artwork':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            rows = _interfaces_api_runtime.list_distribution_artwork(self.distribution_store, release_id)
            self._send_json({'ok': True, 'release_id': release_id, 'artwork': rows, 'latest': rows[0] if rows else {}, 'summary': _interfaces_api_runtime.distribution_artwork_summary(rows[0] if rows else {})})
            return (True, None)
        if tail == '/artwork/import':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            artwork = _interfaces_api_runtime.import_distribution_artwork(self.distribution_store, release_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'artwork': artwork, 'summary': _interfaces_api_runtime.distribution_artwork_summary(artwork)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        artwork_route = _interfaces_api_runtime._match_distribution_artwork_tail(tail)
        if artwork_route is not None:
            artwork_id, _split_state['action'] = artwork_route
            if _split_state['action'] == '':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                artwork = _interfaces_api_runtime.read_distribution_artwork(self.distribution_store, release_id, artwork_id)
                self._send_json({'ok': True, 'release_id': release_id, 'artwork': artwork, 'summary': _interfaces_api_runtime.distribution_artwork_summary(artwork)})
                return (True, None)
            if _split_state['action'] == 'download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                artwork = _interfaces_api_runtime.read_distribution_artwork(self.distribution_store, release_id, artwork_id)
                path = _interfaces_api_runtime.distribution_artwork_file_path(self.distribution_store, release_id, artwork)
                self._send_file(path, str(artwork.get('media_type') or 'application/octet-stream'), filename=str(artwork.get('stored_filename') or path.name))
                return (True, None)
            if _split_state['action'] == 'delete':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                result = _interfaces_api_runtime.delete_distribution_artwork(self.distribution_store, release_id, artwork_id)
                self._send_json({'ok': True, **result})
                return (True, None)
        _split_state['target_route'] = _interfaces_api_runtime._match_distribution_target_tail(tail)
        if _split_state['target_route'] is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Distribution route not found.')
            return (True, None)
        return (False, None)

    def _handle_distribution_route_part_02(self, method: str, release_id: str, tail: str, _split_state):
        _split_state['target_id'], _split_state['action'] = _split_state['target_route']
        _split_state['target'] = self.distribution_store.get_target(release_id, _split_state['target_id'])
        if _split_state['action'] == '':
            if method == 'GET':
                _split_state['signoff'] = self.distribution_store.read_signoff(release_id, _split_state['target'], default={})
                qa = self._get_or_refresh_distribution_qa(release_id, _split_state['target'], refresh=False)
                _split_state['template'] = self.distribution_store.resolve_target_template(_split_state['target'])
                checklist = _interfaces_api_runtime.reconcile_distribution_checklist(self.distribution_store, release_id, _split_state['target'], _split_state['template'], write=False) if _split_state['template'] else _interfaces_api_runtime.read_distribution_checklist(self.distribution_store, release_id, _split_state['target_id'], default={})
                self._send_json({'ok': True, 'release_id': release_id, 'target': _split_state['target'].to_dict(), 'template': _split_state['template'], 'template_summary': _interfaces_api_runtime.template_summary(_split_state['template']) if _split_state['template'] else {}, 'checklist': checklist, 'checklist_summary': _interfaces_api_runtime.checklist_summary(checklist), 'summary': _interfaces_api_runtime.distribution_target_summary(_split_state['target']), 'qa_summary': _interfaces_api_runtime.distribution_qa_summary(qa), 'signoff_summary': _interfaces_api_runtime.distribution_signoff_summary(_split_state['signoff'])})
                return (True, None)
            if method in {'POST', 'PATCH'}:
                _split_state['target'] = self.distribution_store.update_target(release_id, _split_state['target_id'], self._optional_json_body())
                self._send_json({'ok': True, 'release_id': release_id, 'target': _split_state['target'].to_dict(), 'summary': _interfaces_api_runtime.distribution_target_summary(_split_state['target'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'delete':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, **self.distribution_store.delete_target(release_id, _split_state['target_id'])})
            return (True, None)
        if _split_state['action'] == 'qa':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self._get_or_refresh_distribution_qa(release_id, _split_state['target'], refresh=False)
            self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'distribution_qa': _split_state['report'], 'summary': _interfaces_api_runtime.distribution_qa_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'checklist':
            _split_state['template'] = self.distribution_store.resolve_target_template(_split_state['target'])
            if method == 'GET':
                checklist = _interfaces_api_runtime.reconcile_distribution_checklist(self.distribution_store, release_id, _split_state['target'], _split_state['template'], write=False) if _split_state['template'] else _interfaces_api_runtime.read_distribution_checklist(self.distribution_store, release_id, _split_state['target_id'], default={})
                self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'checklist': checklist, 'summary': _interfaces_api_runtime.checklist_summary(checklist)})
                return (True, None)
            if method == 'POST':
                if not _split_state['template']:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'Distribution target has no template_pack_id.')
                    return (True, None)
                checklist = _interfaces_api_runtime.initialize_distribution_checklist(self.distribution_store, release_id, _split_state['target'], _split_state['template'], now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'checklist': checklist, 'summary': _interfaces_api_runtime.checklist_summary(checklist)})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'layout':
            if method not in {'GET', 'POST'}:
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            layout = self._build_distribution_layout(release_id, _split_state['target'])
            if method == 'POST':
                layout = self.distribution_store.write_layout(release_id, _split_state['target_id'], layout)
                self.distribution_store.append_event(release_id, 'distribution_layout_refreshed', {'target_id': _split_state['target_id'], 'status': layout.get('summary', {}).get('status')})
            self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'layout': layout, 'summary': _interfaces_api_runtime.layout_summary(layout)})
            return (True, None)
        if _split_state['action'].startswith('checklist-item:'):
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['template'] = self.distribution_store.resolve_target_template(_split_state['target'])
            if not _split_state['template']:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'Distribution target has no template_pack_id.')
                return (True, None)
            item_id = _split_state['action'].split(':', 1)[1]
            checklist = _interfaces_api_runtime.update_distribution_checklist_item(self.distribution_store, release_id, _split_state['target'], _split_state['template'], item_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'checklist': checklist, 'summary': _interfaces_api_runtime.checklist_summary(checklist)})
            return (True, None)
        return (False, None)

    def _handle_distribution_route_part_03(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'qa-refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.distribution_store.ensure_target_mutable(release_id, _split_state['target'])
            _split_state['report'] = self._get_or_refresh_distribution_qa(release_id, _split_state['target'], refresh=True)
            self.distribution_store.append_event(release_id, 'distribution_qa_refreshed', {'target_id': _split_state['target_id'], 'status': _split_state['report'].get('status')})
            self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'distribution_qa': _split_state['report'], 'summary': _interfaces_api_runtime.distribution_qa_summary(_split_state['report'])})
            return (True, None)
        if _split_state['action'] == 'export':
            if method == 'GET':
                _split_state['package_id'] = self.distribution_store.latest_package_id(_split_state['target'])
                if not _split_state['package_id']:
                    self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'manifest': {}, 'summary': _interfaces_api_runtime.distribution_export_summary({})})
                    return (True, None)
                manifest = _interfaces_api_runtime.read_distribution_export_manifest(self.distribution_store, release_id, _split_state['package_id'])
                self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'manifest': manifest, 'summary': _interfaces_api_runtime.distribution_export_summary(manifest)})
                return (True, None)
            if method == 'POST':
                self.distribution_store.ensure_target_mutable(release_id, _split_state['target'])
                _split_state['report'] = self._get_or_refresh_distribution_qa(release_id, _split_state['target'], refresh=False)
                manifest = _interfaces_api_runtime.build_distribution_export_package(store=self.distribution_store, release_id=release_id, target=_split_state['target'], qa_report=_split_state['report'], now=_interfaces_api_runtime._utc_now())
                _split_state['target'] = self.distribution_store.get_target(release_id, _split_state['target_id'])
                self._send_json({'ok': True, 'release_id': release_id, 'target': _split_state['target'].to_dict(), 'manifest': manifest, 'summary': _interfaces_api_runtime.distribution_export_summary(manifest), 'layout_summary': _interfaces_api_runtime.layout_summary(manifest.get('layout') if isinstance(manifest.get('layout'), dict) else {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['action'] == 'export-zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.distribution_store.ensure_target_mutable(release_id, _split_state['target'])
            zip_info = _interfaces_api_runtime.build_distribution_package_zip(self.distribution_store, release_id, _split_state['target'], now=_interfaces_api_runtime._utc_now())
            _split_state['target'] = self.distribution_store.get_target(release_id, _split_state['target_id'])
            _split_state['package_id'] = self.distribution_store.latest_package_id(_split_state['target'])
            manifest = _interfaces_api_runtime.read_distribution_export_manifest(self.distribution_store, release_id, _split_state['package_id']) if _split_state['package_id'] else {}
            self._send_json({'ok': True, 'release_id': release_id, 'target': _split_state['target'].to_dict(), 'zip': zip_info, 'summary': _interfaces_api_runtime.distribution_export_summary(manifest)})
            return (True, None)
        if _split_state['action'] == 'export-zip-download':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['package_id'] = self.distribution_store.latest_package_id(_split_state['target'])
            if not _split_state['package_id']:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Distribution package ZIP not found.')
                return (True, None)
            self._send_file(self.distribution_store.package_zip_path(release_id, _split_state['package_id']), 'application/zip', filename=f"musicforge-{release_id}-{_split_state['target_id']}-distribution.zip")
            return (True, None)
        if _split_state['action'] == 'verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['package_id'] = self.distribution_store.latest_package_id(_split_state['target'])
            if not _split_state['package_id']:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Distribution package ZIP not found.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['report'] = _interfaces_api_runtime.verify_distribution_package(self.distribution_store.package_zip_path(release_id, _split_state['package_id']), strict=bool(_split_state['payload'].get('strict', False)), require_audio=bool(_split_state['payload'].get('require_audio', False)), require_artwork=bool(_split_state['payload'].get('require_artwork', False)), require_encoded_audio=bool(_split_state['payload'].get('require_encoded_audio', False)), require_encoded_audio_review=bool(_split_state['payload'].get('require_encoded_audio_review', False)))
            _interfaces_api_runtime.write_distribution_verification_report(_split_state['report'], self.distribution_store.package_dir(release_id, _split_state['package_id']) / 'verification-report.json')
            self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'verification': _split_state['report'], 'summary': _interfaces_api_runtime.distribution_verification_summary(_split_state['report'])})
            return (True, None)
        return (False, None)

    def _handle_distribution_route_part_04(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'signoff':
            if method == 'GET':
                _split_state['signoff'] = self.distribution_store.read_signoff(release_id, _split_state['target'], default={})
                self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'signoff': _split_state['signoff'], 'summary': _interfaces_api_runtime.distribution_signoff_summary(_split_state['signoff'])})
                return (True, None)
            if method == 'POST':
                self.distribution_store.ensure_target_mutable(release_id, _split_state['target'])
                _split_state['report'] = self._get_or_refresh_distribution_qa(release_id, _split_state['target'], refresh=True)
                _split_state['payload'] = self._optional_json_body()
                require_encoded_review = bool(_split_state['payload'].get('require_encoded_audio_review', False) or (_split_state['target'].options or {}).get('require_encoded_audio_review', False))
                require_format_decision = bool(_split_state['payload'].get('require_format_decision', False) or (_split_state['target'].options or {}).get('require_format_decision', False))
                require_rights_clearance = bool(_split_state['payload'].get('require_rights_clearance', False) or (_split_state['target'].options or {}).get('require_rights_clearance', False))
                if require_encoded_review:
                    _split_state['template'] = self.distribution_store.resolve_target_template(_split_state['target'])
                    required_profiles = [profile_id for profile_id in _interfaces_api_runtime.resolve_target_audio_format_profiles(_split_state['target'], _split_state['template']) if profile_id != 'wav_master']
                    encoded_acceptance_gate = self.encoded_audio_acceptance_store.gate(release_id, required_profiles=required_profiles, required=True, now=_interfaces_api_runtime._utc_now())
                    if encoded_acceptance_gate.get('hard_block') and encoded_acceptance_gate.get('status') == 'failed':
                        self._send_json({'error': str(encoded_acceptance_gate.get('message') or 'Encoded audio acceptance gate failed.'), 'encoded_audio_acceptance': encoded_acceptance_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    _split_state['package_id'] = self.distribution_store.latest_package_id(_split_state['target'])
                    export_manifest = _interfaces_api_runtime.read_distribution_export_manifest(self.distribution_store, release_id, _split_state['package_id']) if _split_state['package_id'] else {}
                    export_gate = self._distribution_encoded_audio_acceptance_export_gate(export_manifest, encoded_acceptance_gate)
                    if export_gate.get('status') == 'failed':
                        self._send_json({'error': str(export_gate.get('message') or 'Distribution Export is stale. Rebuild export before signoff.'), 'encoded_audio_acceptance': encoded_acceptance_gate, 'encoded_audio_acceptance_export': export_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    _split_state['payload'] = {**_split_state['payload'], 'require_encoded_audio_review': True, 'encoded_audio_acceptance': encoded_acceptance_gate}
                if require_format_decision:
                    format_decision_gate = self.format_decision_store.distribution_gate(release_id, _split_state['target'], required=True, session_id=str(_split_state['payload'].get('format_decision_session_id') or '') or None)
                    if format_decision_gate.get('hard_block') and format_decision_gate.get('status') == 'failed':
                        self._send_json({'error': str(format_decision_gate.get('message') or 'Format decision gate failed.'), 'format_decision': format_decision_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    _split_state['package_id'] = self.distribution_store.latest_package_id(_split_state['target'])
                    export_manifest = _interfaces_api_runtime.read_distribution_export_manifest(self.distribution_store, release_id, _split_state['package_id']) if _split_state['package_id'] else {}
                    export_gate = self._distribution_format_decision_export_gate(export_manifest, format_decision_gate)
                    if export_gate.get('status') == 'failed':
                        self._send_json({'error': str(export_gate.get('message') or 'Distribution Export is stale. Rebuild export before signoff.'), 'format_decision': format_decision_gate, 'format_decision_export': export_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    _split_state['payload'] = {**_split_state['payload'], 'require_format_decision': True, 'format_decision': format_decision_gate}
                if require_rights_clearance:
                    rights_gate = self.rights_clearance_store.gate(release_id, required=True, now=_interfaces_api_runtime._utc_now())
                    if rights_gate.get('hard_block') and rights_gate.get('status') == 'failed':
                        self._send_json({'error': str(rights_gate.get('message') or 'Rights clearance gate failed.'), 'rights_clearance': rights_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    _split_state['package_id'] = self.distribution_store.latest_package_id(_split_state['target'])
                    export_manifest = _interfaces_api_runtime.read_distribution_export_manifest(self.distribution_store, release_id, _split_state['package_id']) if _split_state['package_id'] else {}
                    export_gate = self._package_rights_clearance_export_gate(export_manifest, rights_gate, package_label='Distribution')
                    if export_gate.get('status') == 'failed':
                        self._send_json({'error': str(export_gate.get('message') or 'Distribution Export is stale. Rebuild export before signoff.'), 'rights_clearance': rights_gate, 'rights_clearance_export': export_gate}, status=_interfaces_api_runtime.HTTPStatus.CONFLICT)
                        return (True, None)
                    _split_state['payload'] = {**_split_state['payload'], 'require_rights_clearance': True, 'rights_clearance': rights_gate}
                _split_state['signoff'] = _interfaces_api_runtime.sign_distribution_package(store=self.distribution_store, release_id=release_id, target=_split_state['target'], qa_report=_split_state['report'], payload=_split_state['payload'], now=_interfaces_api_runtime._utc_now())
                _split_state['target'] = self.distribution_store.get_target(release_id, _split_state['target_id'])
                self._send_json({'ok': True, 'release_id': release_id, 'target': _split_state['target'].to_dict(), 'signoff': _split_state['signoff'], 'summary': _interfaces_api_runtime.distribution_signoff_summary(_split_state['signoff'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_distribution_route_part_05(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'signoff-reset':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            reason = str(_split_state['payload'].get('reason') or '').strip()
            if not reason:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'reason is required.')
                return (True, None)
            event = self.distribution_store.reset_signoff(release_id, _split_state['target_id'], reason)
            self._send_json({'ok': True, 'release_id': release_id, 'target_id': _split_state['target_id'], 'summary': {'status': 'reset'}, 'history_event': event})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Distribution target route not found.')
        return (False, None)

    def _handle_distribution_route(self, method: str, release_id: str, tail: str) -> None:
        _split_state = {}
        try:
            _split_result = self._handle_distribution_route_part_01(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_distribution_route_part_02(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_distribution_route_part_03(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_distribution_route_part_04(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_distribution_route_part_05(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except (_interfaces_api_runtime.ReleaseNotFoundError, _interfaces_api_runtime.DistributionNotFoundError, FileNotFoundError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.DistributionStateError, _interfaces_api_runtime.DistributionExportError, _interfaces_api_runtime.ReleaseStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.DistributionChecklistError, _interfaces_api_runtime.DistributionValidationError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
