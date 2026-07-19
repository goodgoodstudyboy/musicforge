from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument

from song_agent.interfaces.api.route_contexts.delivery import DeliveryRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class DeliveryRoutesRelease(DeliveryRouteContext):
    def _handle_release_route_part_01(self, method: str, release_id: str, tail: str, query_string: str, _split_state):
        if tail == '':
            if method == 'GET':
                _split_state['document'] = self.release_store.get_release(release_id)
                self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'summary': _interfaces_api_runtime.release_summary(_split_state['document']), 'events': self.release_store.read_events(release_id)})
                return (True, None)
            if method == 'PATCH':
                _split_state['payload'] = self._read_json_body()
                _split_state['document'] = self.release_store.update_release(release_id, _split_state['payload'])
                self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'summary': _interfaces_api_runtime.release_summary(_split_state['document'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail in {'/hide', '/unhide'}:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'] = self.release_store.hide_release(release_id, hidden=tail == '/hide')
            self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'summary': _interfaces_api_runtime.release_summary(_split_state['document'])})
            return (True, None)
        if tail == '/archive':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'] = self.release_store.archive_release(release_id)
            self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'summary': _interfaces_api_runtime.release_summary(_split_state['document'])})
            return (True, None)
        if tail == '/delete':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, **self.release_store.delete_release(release_id)})
            return (True, None)
        if tail == '/tracks':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._read_json_body()
            _split_state['document'] = self.release_store.add_track(release_id, _split_state['payload'])
            self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'summary': _interfaces_api_runtime.release_summary(_split_state['document'])})
            return (True, None)
        if tail == '/tracks/reorder':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'] = self.release_store.reorder_tracks(release_id, self._read_json_body())
            self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'summary': _interfaces_api_runtime.release_summary(_split_state['document'])})
            return (True, None)
        track_route = _interfaces_api_runtime._match_release_track_tail(tail)
        if track_route is not None:
            track_id, action = track_route
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            if action == 'remove':
                _split_state['document'] = self.release_store.remove_track(release_id, track_id)
            elif action == 'refresh':
                _split_state['document'] = self.release_store.refresh_track(release_id, track_id)
            elif action == 'replace-version':
                self.audio_revision_store.replace_release_track_version(release_id, track_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                _split_state['document'] = self.release_store.get_release(release_id)
            else:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release track route not found.')
                return (True, None)
            self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'summary': _interfaces_api_runtime.release_summary(_split_state['document'])})
            return (True, None)
        return (False, None)

    def _handle_release_route_part_02(self, method: str, release_id: str, tail: str, query_string: str, _split_state):
        if tail == '/qa':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self._get_or_refresh_release_qa(release_id, refresh=False, options={})
            self._send_json({'ok': True, 'release_id': release_id, 'release_qa': _split_state['report'], 'summary': _interfaces_api_runtime.release_qa_summary(_split_state['report'])})
            return (True, None)
        if tail == '/qa/refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self._get_or_refresh_release_qa(release_id, refresh=True, options=self._optional_json_body())
            self.release_store.append_event(release_id, 'release_qa_refreshed', {'status': _split_state['report'].get('status')})
            self._send_json({'ok': True, 'release_id': release_id, 'release_qa': _split_state['report'], 'summary': _interfaces_api_runtime.release_qa_summary(_split_state['report'])})
            return (True, None)
        if tail == '/audio-qa':
            self._handle_release_audio_qa(method, release_id)
            return (True, None)
        if tail == '/audio-reviews' or tail.startswith('/audio-reviews/'):
            self._handle_release_audio_reviews(method, release_id, tail.removeprefix('/audio-reviews'))
            return (True, None)
        if tail == '/audio-revisions' or tail.startswith('/audio-revisions/'):
            self._handle_release_audio_revisions(method, release_id, tail.removeprefix('/audio-revisions'))
            return (True, None)
        if tail == '/audio-campaign-plan' or tail.startswith('/audio-campaign-plan/'):
            self._handle_release_audio_campaign_plan(method, release_id, tail.removeprefix('/audio-campaign-plan'))
            return (True, None)
        if tail == '/audio-campaign-remediation' or tail.startswith('/audio-campaign-remediation/'):
            self._handle_release_audio_campaign_remediation(method, release_id, tail.removeprefix('/audio-campaign-remediation'))
            return (True, None)
        if tail == '/audio-certification' or tail.startswith('/audio-certification/'):
            self._handle_release_audio_certification(method, release_id, tail.removeprefix('/audio-certification'))
            return (True, None)
        if tail == '/audio-timelines' or tail.startswith('/audio-timelines/'):
            self._handle_release_audio_timeline(method, release_id, tail.removeprefix('/audio-timelines'))
            return (True, None)
        if tail == '/audio-regression' or tail.startswith('/audio-regression/'):
            self._handle_release_audio_regression(method, release_id, tail.removeprefix('/audio-regression'))
            return (True, None)
        if tail == '/audio-regression-response' or tail.startswith('/audio-regression-response/'):
            self._handle_release_audio_regression_response(method, release_id, tail.removeprefix('/audio-regression-response'))
            return (True, None)
        if tail == '/audio-command-center' or tail.startswith('/audio-command-center/'):
            self._handle_release_audio_command_center(method, release_id, tail.removeprefix('/audio-command-center'))
            return (True, None)
        if tail == '/mastering' or tail.startswith('/mastering/'):
            self._handle_release_mastering(method, release_id, tail.removeprefix('/mastering'))
            return (True, None)
        if tail == '/encoded-audio' or tail.startswith('/encoded-audio/'):
            self._handle_release_encoded_audio(method, release_id, tail.removeprefix('/encoded-audio'))
            return (True, None)
        if tail == '/format-decisions' or tail.startswith('/format-decisions/'):
            self._handle_release_format_decisions(method, release_id, tail.removeprefix('/format-decisions'))
            return (True, None)
        if tail == '/rights' or tail.startswith('/rights/'):
            self._handle_release_rights(method, release_id, tail.removeprefix('/rights'))
            return (True, None)
        return (False, None)

    def _handle_release_route_part_03(self, method: str, release_id: str, tail: str, query_string: str, _split_state):
        if tail == '/metadata':
            if method == 'GET':
                metadata = _interfaces_api_runtime.read_release_metadata(self.release_store, release_id, default={})
                qa_report = self._get_or_refresh_release_metadata_qa(release_id, refresh=False) if metadata else {}
                self._send_json({'ok': True, 'release_id': release_id, 'metadata': metadata, 'history': _interfaces_api_runtime.read_release_metadata_history(self.release_store, release_id), 'summary': _interfaces_api_runtime.release_metadata_summary(metadata, qa_report, _interfaces_api_runtime.metadata_export_summary(_interfaces_api_runtime._safe_read_release_export_manifest(self.release_store, release_id)))})
                return (True, None)
            if method == 'POST':
                metadata = _interfaces_api_runtime.write_release_metadata(self.release_store, release_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                _split_state['report'] = self._get_or_refresh_release_metadata_qa(release_id, refresh=True)
                self._send_json({'ok': True, 'release_id': release_id, 'metadata': metadata, 'summary': _interfaces_api_runtime.release_metadata_summary(metadata, _split_state['report'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/metadata/init':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            metadata = _interfaces_api_runtime.initialize_release_metadata(self.release_store, release_id, force=bool(_split_state['payload'].get('force', False)), merge=bool(_split_state['payload'].get('merge', False)), now=_interfaces_api_runtime._utc_now())
            _split_state['report'] = self._get_or_refresh_release_metadata_qa(release_id, refresh=True)
            self._send_json({'ok': True, 'release_id': release_id, 'metadata': metadata, 'summary': _interfaces_api_runtime.release_metadata_summary(metadata, _split_state['report'])})
            return (True, None)
        if tail == '/metadata/qa':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self._get_or_refresh_release_metadata_qa(release_id, refresh=False)
            self._send_json({'ok': True, 'release_id': release_id, 'metadata_qa': _split_state['report'], 'summary': _interfaces_api_runtime.release_metadata_qa_summary(_split_state['report'])})
            return (True, None)
        if tail == '/metadata/qa/refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self._get_or_refresh_release_metadata_qa(release_id, refresh=True)
            self.release_store.append_event(release_id, 'release_metadata_qa_refreshed', {'status': _split_state['report'].get('status')})
            self._send_json({'ok': True, 'release_id': release_id, 'metadata_qa': _split_state['report'], 'summary': _interfaces_api_runtime.release_metadata_qa_summary(_split_state['report'])})
            return (True, None)
        if tail == '/metadata/export':
            if method == 'GET':
                _split_state['manifest'] = _interfaces_api_runtime._safe_read_release_export_manifest(self.release_store, release_id)
                self._send_json({'ok': True, 'release_id': release_id, 'metadata_export': _split_state['manifest'].get('metadata', {}), 'summary': _interfaces_api_runtime.metadata_export_summary(_split_state['manifest'])})
                return (True, None)
            if method == 'POST':
                self._ensure_release_export_mutable(release_id)
                _split_state['report'] = self._get_or_refresh_release_metadata_qa(release_id, refresh=False)
                export_summary = _interfaces_api_runtime.export_release_metadata_files(release_store=self.release_store, release_id=release_id, qa_report=_split_state['report'], now=_interfaces_api_runtime._utc_now())
                _split_state['manifest'] = _interfaces_api_runtime.attach_metadata_export_to_manifest(self.release_store, release_id, export_summary)
                _interfaces_api_runtime.build_release_export_zip(self.release_store, release_id, now=_interfaces_api_runtime._utc_now())
                _split_state['manifest'] = _interfaces_api_runtime.read_release_export_manifest(self.release_store, release_id)
                _split_state['document'] = self.release_store.update_export_summary(release_id, _interfaces_api_runtime.release_export_summary(_split_state['manifest']))
                self.release_store.append_event(release_id, 'release_metadata_exported', {'file_count': len(export_summary.get('files', []))})
                self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'manifest': _split_state['manifest'], 'metadata_export': export_summary, 'summary': _interfaces_api_runtime.metadata_export_summary(_split_state['manifest'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_release_route_part_04(self, method: str, release_id: str, tail: str, query_string: str, _split_state):
        if tail in {'/metadata/platform.csv', '/metadata/credits.csv'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            filename = 'platform-metadata.csv' if tail.endswith('platform.csv') else 'credits.csv'
            self.release_store.get_release(release_id)
            self._send_file(self.release_store.export_dir(release_id) / filename, 'text/csv; charset=utf-8', filename=filename)
            return (True, None)
        if tail == '/operations' or tail.startswith('/operations/'):
            self._handle_release_operations(method, release_id, tail.removeprefix('/operations'))
            return (True, None)
        if tail.startswith('/distribution'):
            self._handle_distribution_route(method, release_id, tail.removeprefix('/distribution'))
            return (True, None)
        if tail.startswith('/submissions'):
            self._handle_submission_route(method, release_id, tail.removeprefix('/submissions'))
            return (True, None)
        if tail == '/acceptance-analytics':
            self._handle_release_acceptance_analytics(method, release_id)
            return (True, None)
        if tail == '/acceptance-analytics/refresh':
            self._handle_release_acceptance_analytics_refresh(method, release_id)
            return (True, None)
        if tail == '/export':
            if method == 'GET':
                try:
                    _split_state['manifest'] = _interfaces_api_runtime.read_release_export_manifest(self.release_store, release_id)
                except FileNotFoundError:
                    self._send_json({'ok': True, 'release_id': release_id, 'manifest': {}, 'summary': _interfaces_api_runtime.release_export_summary({})})
                    return (True, None)
                self._send_json({'ok': True, 'release_id': release_id, 'manifest': _split_state['manifest'], 'summary': _interfaces_api_runtime.release_export_summary(_split_state['manifest'])})
                return (True, None)
            if method == 'POST':
                _split_state['document'] = self.release_store.get_release(release_id)
                self._ensure_release_export_mutable(release_id, document=_split_state['document'])
                _split_state['report'] = self._get_or_refresh_release_qa(release_id, refresh=False, options={})
                _split_state['manifest'] = _interfaces_api_runtime.build_release_export_bundle(release=_split_state['document'], release_store=self.release_store, project_store=self.project_store, qa_report=_split_state['report'], now=_interfaces_api_runtime._utc_now())
                _split_state['document'] = self.release_store.update_export_summary(release_id, _interfaces_api_runtime.release_export_summary(_split_state['manifest']))
                self.release_store.append_event(release_id, 'release_export_created', {'file_count': _split_state['manifest'].get('summary', {}).get('file_count')})
                self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'manifest': _split_state['manifest'], 'summary': _interfaces_api_runtime.release_export_summary(_split_state['manifest'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/export/zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._ensure_release_export_mutable(release_id)
            zip_info = _interfaces_api_runtime.build_release_export_zip(self.release_store, release_id, now=_interfaces_api_runtime._utc_now())
            _split_state['manifest'] = _interfaces_api_runtime.read_release_export_manifest(self.release_store, release_id)
            _split_state['document'] = self.release_store.update_export_summary(release_id, _interfaces_api_runtime.release_export_summary(_split_state['manifest']))
            self.release_store.append_event(release_id, 'release_export_zip_created', {'sha256': zip_info.get('sha256')})
            self._send_json({'ok': True, 'release': _split_state['document'].to_dict(), 'zip': zip_info, 'summary': _interfaces_api_runtime.release_export_summary(_split_state['manifest'])})
            return (True, None)
        if tail == '/export.zip':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.release_store.get_release(release_id)
            self._send_file(self.release_store.zip_path(release_id), 'application/zip', filename=f'musicforge-{release_id}-release-export.zip')
            return (True, None)
        if tail == '/signoff':
            self._handle_release_signoff(method, release_id)
            return (True, None)
        if tail == '/signoff/reset':
            self._handle_release_signoff_reset(method, release_id)
            return (True, None)
        return (False, None)

    def _handle_release_route_part_05(self, method: str, release_id: str, tail: str, query_string: str, _split_state):
        if tail == '/events':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.release_store.get_release(release_id)
            self._send_json({'events': self.release_store.read_events(release_id)})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release route not found.')
        return (False, None)

    def _handle_release_route(self, method: str, release_id: str, tail: str, query_string: str) -> None:
        _split_state: ImplementationDocument = {}
        try:
            _split_result = self._handle_release_route_part_01(method, release_id, tail, query_string, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_route_part_02(method, release_id, tail, query_string, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_route_part_03(method, release_id, tail, query_string, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_route_part_04(method, release_id, tail, query_string, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_route_part_05(method, release_id, tail, query_string, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.ReleaseConflictError, _interfaces_api_runtime.ReleaseStateError, _interfaces_api_runtime.ReleaseExportError, _interfaces_api_runtime.ReleaseOperationsError, _interfaces_api_runtime.ReleaseOperationsRunbookStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseOperationsRunbookNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.ReleaseValidationError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except FileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
