from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseEncodedAudio(QualityRouteContext):
    def _handle_release_encoded_audio_part_01(self, method: str, release_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, 'release_id': release_id, 'summary': self.audio_encoding_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now()), 'formats': self.audio_encoding_store.list_manifests(release_id)})
            return (True, None)
        if tail == '/render':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.audio_encoding_store.render(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if tail == '/render-format':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            profile_id = str(_split_state['payload'].get('profile_id') or '').strip()
            if not profile_id:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'profile_id is required.')
                return (True, None)
            _split_state['manifest'] = self.audio_encoding_store.render_format(release_id, profile_id, _split_state['payload'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'manifest': _split_state['manifest'], 'summary': self.audio_encoding_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now())}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if tail == '/verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.audio_encoding_store.verify(release_id, self._optional_json_body())
            self._send_json({'ok': True, **_split_state['result']})
            return (True, None)
        if tail == '/reset':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.audio_encoding_store.reset(release_id, self._optional_json_body())
            self._send_json({'ok': True, **_split_state['result']})
            return (True, None)
        _split_state['parts'] = [part for part in tail.strip('/').split('/') if part]
        if len(_split_state['parts']) == 1 and _split_state['parts'][0] == 'health':
            if method == 'GET':
                self._send_json({'ok': True, 'release_id': release_id, 'health': self.encoded_audio_acceptance_store.list_health(release_id)})
                return (True, None)
            if method == 'POST':
                _split_state['payload'] = self._optional_json_body()
                _split_state['result'] = self.encoded_audio_acceptance_store.refresh_health(release_id, _interfaces_api_runtime.normalize_required_profiles(_split_state['payload'].get('profile_ids') or _split_state['payload'].get('profiles') or _split_state['payload'].get('required_audio_format_profiles') or []), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, **_split_state['result']})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][0] == 'health' and (method == 'GET'):
            report = self.encoded_audio_acceptance_store.read_health(release_id, _split_state['parts'][1])
            self._send_json({'ok': True, 'release_id': release_id, 'profile_id': _split_state['parts'][1], 'health': report})
            return (True, None)
        if len(_split_state['parts']) == 1 and _split_state['parts'][0] == 'reviews':
            if method == 'GET':
                reviews = self.encoded_audio_acceptance_store.list_reviews(release_id)
                self._send_json({'ok': True, 'release_id': release_id, 'reviews': reviews})
                return (True, None)
            if method == 'POST':
                _split_state['review'] = self.encoded_audio_acceptance_store.create_review(release_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'review': _split_state['review']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_release_encoded_audio_part_02(self, method: str, release_id: str, tail: str, _split_state):
        if len(_split_state['parts']) == 2 and _split_state['parts'][0] == 'reviews':
            review_id = _split_state['parts'][1]
            if method == 'GET':
                _split_state['review'] = self.encoded_audio_acceptance_store.read_review(release_id, review_id)
                self._send_json({'ok': True, 'release_id': release_id, 'review': _split_state['review']})
                return (True, None)
            if method in {'POST', 'PATCH'}:
                _split_state['review'] = self.encoded_audio_acceptance_store.update_review(release_id, review_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'review': _split_state['review']})
                return (True, None)
            if method == 'DELETE':
                _split_state['result'] = self.encoded_audio_acceptance_store.delete_review(release_id, review_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, **_split_state['result']})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if len(_split_state['parts']) == 1 and _split_state['parts'][0] == 'acceptance':
            if method == 'GET':
                payload_profiles: list[_InferenceType] = []
                summary = self.encoded_audio_acceptance_store.build_summary(release_id, required_profiles=payload_profiles, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'summary': summary})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][0] == 'acceptance' and (_split_state['parts'][1] == 'refresh'):
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            summary = self.encoded_audio_acceptance_store.write_summary(release_id, required_profiles=_interfaces_api_runtime.normalize_required_profiles(_split_state['payload'].get('profile_ids') or _split_state['payload'].get('profiles') or _split_state['payload'].get('required_audio_format_profiles') or []), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'summary': summary})
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][0] == 'formats' and (method == 'GET'):
            _split_state['manifest'] = self.audio_encoding_store.read_manifest(release_id, _split_state['parts'][1])
            self._send_json({'ok': True, 'release_id': release_id, 'manifest': _split_state['manifest']})
            return (True, None)
        if len(_split_state['parts']) == 5 and _split_state['parts'][0] == 'formats' and (_split_state['parts'][2] == 'tracks') and (_split_state['parts'][4] == 'audio') and (method == 'GET'):
            _split_state['manifest'] = self.audio_encoding_store.read_manifest(release_id, _split_state['parts'][1])
            track = next((row for row in _split_state['manifest'].get('tracks', []) if isinstance(row, dict) and row.get('track_id') == _split_state['parts'][3]), None)
            if not track:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Encoded track audio not found.')
                return (True, None)
            path = self.audio_encoding_store.track_audio_path(release_id, _split_state['parts'][1], _split_state['parts'][3])
            self._send_file(path, 'application/octet-stream', filename=path.name)
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Encoded audio route not found.')
        return (False, None)

    def _handle_release_encoded_audio(self, method: str, release_id: str, tail: str) -> None:
        _split_state: dict[str, _InferenceType] = {}
        try:
            _split_result = self._handle_release_encoded_audio_part_01(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_encoded_audio_part_02(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except (_interfaces_api_runtime.ReleaseNotFoundError, _interfaces_api_runtime.AudioEncodingNotFoundError, FileNotFoundError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.EncodedAudioAcceptanceNotFoundError,) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.ReleaseStateError, _interfaces_api_runtime.AudioEncodingStateError, _interfaces_api_runtime.EncodedAudioAcceptanceStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.AudioEncodingError, _interfaces_api_runtime.AudioEncodingProfileError, _interfaces_api_runtime.EncodedAudioAcceptanceError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_profiles_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio/profiles":
                if method == "GET":
                    profiles = [profile.public_summary() for profile in self.audio_profile_store.list_profiles(include_hidden=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.audio_profile_store.upsert_profile(self._read_json_body())
                    self._send_json({"ok": True, "profile": profile.public_summary()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio profile route not found.")
                return
            profile_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    profile = self.audio_profile_store.get_profile(profile_id)
                    self._send_json({"ok": True, "profile": profile.public_summary()})
                    return
                if method == "POST":
                    profile = self.audio_profile_store.upsert_profile({**self._read_json_body(), "profile_id": profile_id})
                    self._send_json({"ok": True, "profile": profile.public_summary()})
                    return
            if len(parts) == 2 and method == "POST":
                action = parts[1]
                if action == "test":
                    self._send_json({"ok": True, **self.audio_profile_store.test_profile(profile_id)})
                    return
                if action == "set-default":
                    profile = self.audio_profile_store.set_default(profile_id)
                    self._send_json({"ok": True, "profile": profile.public_summary()})
                    return
                if action == "hide":
                    profile = self.audio_profile_store.hide(profile_id, hidden=True)
                    self._send_json({"ok": True, "profile": profile.public_summary()})
                    return
                if action == "unhide":
                    profile = self.audio_profile_store.hide(profile_id, hidden=False)
                    self._send_json({"ok": True, "profile": profile.public_summary()})
                    return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio profile route not found.")
        except _interfaces_api_runtime.AudioProfileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioProfileError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_lab_route_part_01(self, method: str, path: str, _split_state):
        if path == '/api/audio-lab' or path == '/api/audio-lab/environment':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, 'environment': self.audio_lab_store.environment_status()})
            return (True, None)
        if path == '/api/audio-lab/environment/detect':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, 'environment': self.audio_lab_store.detect_environment()})
            return (True, None)
        if path == '/api/audio-lab/environment/test-profile':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            payload = self._optional_json_body()
            _split_state['result'] = self.audio_lab_store.test_profile(str(payload.get('profile_id') or payload.get('profile') or 'default'))
            self._send_json({'ok': _split_state['result'].get('status') != 'failed', 'profile_test': _split_state['result']})
            return (True, None)
        if path == '/api/audio-lab/environment/report':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self.audio_lab_store.setup_report()
            self._send_json({'ok': True, 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
            return (True, None)
        if path == '/api/audio-lab/smoke-runs':
            if method == 'GET':
                runs = self.audio_lab_store.list_smoke_runs()
                self._send_json({'ok': True, 'smoke_runs': runs, 'summary': {'smoke_run_count': len(runs)}})
                return (True, None)
            if method == 'POST':
                _split_state['report'] = self.audio_lab_store.run_smoke(self._optional_json_body())
                self._send_json({'ok': _split_state['report'].get('status') != 'failed', 'smoke_run': _split_state['report'], 'summary': _split_state['report'].get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if path.startswith('/api/audio-lab/smoke-runs/'):
            _split_state['parts'] = path.removeprefix('/api/audio-lab/smoke-runs/').strip('/').split('/')
            smoke_id = _split_state['parts'][0]
            if len(_split_state['parts']) == 1 or _split_state['parts'][1] == 'report':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.audio_lab_store.read_smoke_report(smoke_id)
                self._send_json({'ok': True, 'smoke_run': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
                return (True, None)
        if path == '/api/audio-lab/listening-sessions':
            if method == 'GET':
                sessions = self.audio_lab_store.list_sessions()
                self._send_json({'ok': True, 'sessions': sessions, 'summary': {'session_count': len(sessions)}})
                return (True, None)
            if method == 'POST':
                _split_state['session'] = self.audio_lab_store.create_session(self._read_json_body())
                self._send_json({'ok': True, 'session': _split_state['session'], 'summary': _split_state['session'].get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_audio_lab_route_part_02(self, method: str, path: str, _split_state):
        if path.startswith('/api/audio-lab/listening-sessions/'):
            _split_state['parts'] = path.removeprefix('/api/audio-lab/listening-sessions/').strip('/').split('/')
            session_id = _split_state['parts'][0]
            if len(_split_state['parts']) == 1:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['session'] = self.audio_lab_store.read_session(session_id)
                self._send_json({'ok': True, 'session': _split_state['session'], 'summary': _split_state['session'].get('summary', {})})
                return (True, None)
            if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'report':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.audio_lab_store.session_report(session_id)
                self._send_json({'ok': _split_state['report'].get('status') != 'failed', 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
                return (True, None)
            if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'close':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.audio_lab_store.close_session(session_id, self._optional_json_body())
                self._send_json({'ok': True, **_split_state['result']})
                return (True, None)
            if len(_split_state['parts']) == 4 and _split_state['parts'][1] == 'items' and (_split_state['parts'][3] == 'review'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.audio_lab_store.write_item_review(session_id, _split_state['parts'][2], self._read_json_body())
                self._send_json({'ok': True, **_split_state['result']})
                return (True, None)
            if len(_split_state['parts']) == 4 and _split_state['parts'][1] == 'items' and (_split_state['parts'][3] == 'markers'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.audio_lab_store.add_marker(session_id, _split_state['parts'][2], self._read_json_body())
                self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            if len(_split_state['parts']) == 4 and _split_state['parts'][1] == 'markers':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                action = _split_state['parts'][3]
                draft_type = {'create-review-task': 'review_task', 'create-audio-revision-draft': 'audio_revision', 'create-mix-patch-draft': 'mix_patch'}.get(action)
                if draft_type:
                    _split_state['result'] = self.audio_lab_store.create_marker_draft(session_id, _split_state['parts'][2], draft_type, self._optional_json_body())
                    self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return (True, None)
        if path == '/api/audio-lab/comparisons':
            if method == 'GET':
                comparisons = self.audio_lab_store.list_comparisons()
                self._send_json({'ok': True, 'comparisons': comparisons, 'summary': {'comparison_count': len(comparisons)}})
                return (True, None)
            if method == 'POST':
                _split_state['comparison'] = self.audio_lab_store.create_comparison(self._read_json_body())
                self._send_json({'ok': True, 'comparison': _split_state['comparison']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_audio_lab_route_part_03(self, method: str, path: str, _split_state):
        if path.startswith('/api/audio-lab/comparisons/'):
            _split_state['parts'] = path.removeprefix('/api/audio-lab/comparisons/').strip('/').split('/')
            comparison_id = _split_state['parts'][0]
            if len(_split_state['parts']) == 1:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_json({'ok': True, 'comparison': self.audio_lab_store.read_comparison(comparison_id)})
                return (True, None)
            if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'review':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['comparison'] = self.audio_lab_store.review_comparison(comparison_id, self._read_json_body())
                self._send_json({'ok': True, 'comparison': _split_state['comparison']})
                return (True, None)
            if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'report':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['report'] = self.audio_lab_store.comparison_report(comparison_id)
                self._send_json({'ok': _split_state['report'].get('status') != 'failed', 'report': _split_state['report']})
                return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Audio Lab route not found.')
        return (False, None)

    def _handle_audio_lab_route(self, method: str, path: str) -> None:
        _split_state: dict[str, _InferenceType] = {}
        try:
            _split_result = self._handle_audio_lab_route_part_01(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_audio_lab_route_part_02(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_audio_lab_route_part_03(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.AudioLabNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioLabStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AudioLabValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AudioLabError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
