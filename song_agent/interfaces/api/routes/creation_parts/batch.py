from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class CreationRoutesBatch:
    def _handle_batch_route_part_01(self, method: str, batch_id: str, tail: str, _split_state):
        if tail == '':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                _split_state['document'] = self.batch_store.get_batch(batch_id)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Batch not found.')
                return (True, None)
            self._send_json(_split_state['document'].to_dict())
            return (True, None)
        if tail == '/launch':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'], _split_state['status'], _split_state['error'], started = self.batch_runner.launch_batch(batch_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'started_count': started, **_split_state['document'].to_dict()}, status=_split_state['status'])
            return (True, None)
        if tail == '/pause':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'], _split_state['status'], _split_state['error'] = self.batch_runner.pause_batch(batch_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, **_split_state['document'].to_dict()}, status=_split_state['status'])
            return (True, None)
        if tail == '/resume':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'], _split_state['status'], _split_state['error'] = self.batch_runner.resume_batch(batch_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, **_split_state['document'].to_dict()}, status=_split_state['status'])
            return (True, None)
        if tail == '/retry-failed':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'], _split_state['status'], _split_state['error'], reset_count = self.batch_runner.retry_failed(batch_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'reset_count': reset_count, **_split_state['document'].to_dict()}, status=_split_state['status'])
            return (True, None)
        if tail in {'/render-audio', '/render-failed-audio'}:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'], _split_state['status'], _split_state['error'], _split_state['queued_count'] = self.batch_runner.render_audio(batch_id, failed_only=tail == '/render-failed-audio')
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'queued_count': _split_state['queued_count'], **_split_state['document'].to_dict()}, status=_split_state['status'])
            return (True, None)
        return (False, None)

    def _handle_batch_route_part_02(self, method: str, batch_id: str, tail: str, _split_state):
        if tail in {'/render-stems', '/render-stem-audio', '/render-failed-stems', '/render-failed-stem-audio'}:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['document'], _split_state['status'], _split_state['error'], _split_state['queued_count'] = self.batch_runner.render_stems(batch_id, audio=tail in {'/render-stem-audio', '/render-failed-stem-audio'}, failed_only=tail in {'/render-failed-stems', '/render-failed-stem-audio'})
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'queued_count': _split_state['queued_count'], **_split_state['document'].to_dict()}, status=_split_state['status'])
            return (True, None)
        if tail == '/export':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                self._send_json(self.batch_store.export_batch(batch_id))
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Batch not found.')
            return (True, None)
        if tail in {'/hide', '/unhide'}:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                _split_state['document'] = self.batch_store.hide_batch(batch_id, tail == '/hide')
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Batch not found.')
                return (True, None)
            self._send_json({'ok': True, **_split_state['document'].to_dict()})
            return (True, None)
        if tail == '/delete':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            deleted, _split_state['status'], _split_state['error'] = self.batch_runner.delete_batch(batch_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'deleted': deleted, 'batch_id': batch_id})
            return (True, None)
        if tail == '/open-folder':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            try:
                batch_dir = self.batch_store.batch_dir(batch_id)
                if not batch_dir.exists():
                    raise FileNotFoundError(batch_id)
            except FileNotFoundError:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Batch not found.')
                return (True, None)
            _interfaces_api_runtime.open_folder(batch_dir)
            self._send_json({'ok': True, 'path': str(batch_dir)})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Batch route not found.')
        return (False, None)

    def _handle_batch_route(self, method: str, batch_id: str, tail: str) -> None:
        _split_state = {}
        _split_result = self._handle_batch_route_part_01(method, batch_id, tail, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_batch_route_part_02(method, batch_id, tail, _split_state)
        if _split_result[0]:
            return _split_result[1]

    def _handle_job_route_part_01(self, method: str, job_id: str, tail: str, _split_state):
        _split_state['job'] = self.store.get_job(job_id)
        if _split_state['job'] is None:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Job not found.')
            return (True, None)
        _split_state['run_dir'] = _interfaces_api_runtime.Path(_split_state['job'].output_dir)
        if tail == '/open-folder':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _interfaces_api_runtime.open_folder(_split_state['run_dir'])
            self._send_json({'ok': True, 'path': str(_split_state['run_dir'])})
            return (True, None)
        if tail in {'/hide', '/unhide'}:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['job'] = self.store.hide_job(job_id, hidden=tail == '/hide')
            if _split_state['job'] is None:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Job not found.')
                return (True, None)
            self._send_json({'ok': True, 'job': _split_state['job'].to_dict()})
            return (True, None)
        if tail == '/cancel':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['job'], _split_state['status'], _split_state['error'] = self.store.cancel_job(job_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'job': _split_state['job'].to_dict() if _split_state['job'] is not None else None})
            return (True, None)
        if tail == '/retry':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['job'], _split_state['status'], _split_state['error'] = self.store.retry_job(job_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'job': _split_state['job'].to_dict() if _split_state['job'] is not None else None})
            return (True, None)
        if tail == '/delete':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            deleted, _split_state['status'], _split_state['error'] = self.store.delete_job(job_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'deleted': deleted, 'job_id': job_id})
            return (True, None)
        if tail == '/render-audio':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            profile = self._renderer_profile_from_payload(_split_state['payload'])
            config = profile.to_renderer_config() if profile is not None else None
            audio, _split_state['status'], _split_state['error'] = self.store.render_job_audio(job_id, config=config, audio_profile=profile)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, 'job_id': job_id, **audio}, status=_split_state['status'])
            return (True, None)
        return (False, None)

    def _handle_job_route_part_02(self, method: str, job_id: str, tail: str, _split_state):
        if tail == '/render-stems':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['data'], _split_state['status'], _split_state['error'] = self.store.render_job_stems(job_id, force=bool(_split_state['payload'].get('force', False)))
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, **_split_state['data']}, status=_split_state['status'])
            return (True, None)
        if tail == '/render-stem-audio':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            stem_ids = _split_state['payload'].get('stem_ids')
            if stem_ids is not None:
                if not isinstance(stem_ids, list):
                    self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'stem_ids must be a list.')
                    return (True, None)
                stem_ids = [str(stem_id) for stem_id in stem_ids]
            _split_state['data'], _split_state['status'], _split_state['error'] = self.store.render_job_stem_audio(job_id, stem_ids=stem_ids, force=bool(_split_state['payload'].get('force', False)))
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json({'ok': True, **_split_state['data']}, status=_split_state['status'])
            return (True, None)
        if tail.startswith('/nodes/') and tail.endswith('/retry'):
            self._send_node_retry(method, _split_state['job'], tail)
            return (True, None)
        if method != 'GET':
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '':
            self._send_json(_split_state['job'].to_dict())
            return (True, None)
        if tail == '/song-plan':
            plan_path = _split_state['run_dir'] / 'data' / 'song-plan.json'
            if not plan_path.exists():
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, 'song-plan.json is not available for this job yet.')
                return (True, None)
            self._send_json(_interfaces_api_runtime.read_json(plan_path))
            return (True, None)
        if tail == '/timeline':
            self._send_runtime_view(_split_state['job'], 'timeline')
            return (True, None)
        if tail == '/tracks':
            self._send_runtime_view(_split_state['job'], 'tracks')
            return (True, None)
        if tail == '/validator':
            self._send_runtime_view(_split_state['job'], 'validator')
            return (True, None)
        if tail == '/quality':
            self._send_runtime_view(_split_state['job'], 'quality')
            return (True, None)
        if tail == '/edit':
            metadata = _interfaces_api_runtime._read_edit_metadata_for_run(_split_state['run_dir'])
            if metadata is None:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Edit metadata not found.')
                return (True, None)
            self._send_json({'job_id': _split_state['job'].job_id, 'edit': metadata})
            return (True, None)
        return (False, None)

    def _handle_job_route_part_03(self, method: str, job_id: str, tail: str, _split_state):
        if tail == '/provider-usage':
            usage_path = _split_state['run_dir'] / 'data' / 'provider-usage.json'
            if not usage_path.exists():
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Provider usage not found.')
                return (True, None)
            self._send_json({'job_id': _split_state['job'].job_id, 'usage': _interfaces_api_runtime.read_json(usage_path)})
            return (True, None)
        if tail == '/events':
            self._send_json({'events': _interfaces_api_runtime._read_events(_split_state['run_dir'] / 'logs' / 'events.jsonl')})
            return (True, None)
        if tail == '/artifacts':
            self._send_json({'artifacts': _interfaces_api_runtime.discover_artifacts(_split_state['run_dir'])})
            return (True, None)
        if tail == '/midi':
            self._send_file(_split_state['run_dir'] / 'renders' / 'song.mid', 'audio/midi')
            return (True, None)
        if tail == '/audio':
            audio_path = _split_state['run_dir'] / 'renders' / 'song.wav'
            if not audio_path.exists():
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Audio render is not available for this job.')
                return (True, None)
            stale_reasons = self._job_audio_artifact_stale_reasons(_split_state['job'])
            if stale_reasons:
                self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, f"Audio artifact is stale: {', '.join(stale_reasons)}.")
                return (True, None)
            self._send_file(audio_path, 'audio/wav')
            return (True, None)
        if tail == '/stems':
            _split_state['data'], _split_state['status'], _split_state['error'] = self.store.get_job_stems(job_id)
            if _split_state['error'] is not None:
                self._send_error(_split_state['status'], _split_state['error'])
                return (True, None)
            self._send_json(_split_state['data'], status=_split_state['status'])
            return (True, None)
        if tail.startswith('/stems/'):
            self._send_stem_file(_split_state['job'], tail)
            return (True, None)
        if tail == '/nodes':
            self._send_nodes_list(_split_state['job'])
            return (True, None)
        if tail.startswith('/nodes/'):
            self._send_node_route(method, _split_state['job'], tail)
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Job route not found.')
        return (False, None)

    def _handle_job_route(self, method: str, job_id: str, tail: str) -> None:
        _split_state = {}
        _split_result = self._handle_job_route_part_01(method, job_id, tail, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_job_route_part_02(method, job_id, tail, _split_state)
        if _split_result[0]:
            return _split_result[1]
        _split_result = self._handle_job_route_part_03(method, job_id, tail, _split_state)
        if _split_result[0]:
            return _split_result[1]
