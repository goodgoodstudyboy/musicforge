from __future__ import annotations

from song_agent.platform.contracts.documents import JsonDocument

from song_agent.platform.contracts.coercion import as_document as _as_document

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesAudioQualityActions(QualityRouteContext):
    def _handle_audio_quality_actions_route_part_01(self, method: str, path: str, _split_state):
        if path == '/api/audio-quality-actions':
            if method == 'GET':
                rows = self.release_audio_quality_action_queue_store.list_queues()
                self._send_json({'ok': True, 'queues': rows, 'summary': {'queue_count': len(rows)}})
                return (True, None)
            if method == 'POST':
                _split_state['payload'] = self._read_json_body()
                queue = self.release_audio_quality_action_queue_store.create_from_observatory(_split_state['payload'].get('observatory_id', ''), name=_split_state['payload'].get('name'), include_risks=bool(_split_state['payload'].get('include_risks', True)), include_recommendations=bool(_split_state['payload'].get('include_recommendations', True)), severity_floor=str(_split_state['payload'].get('severity_floor') or 'warning'), policy=_as_document(_split_state['payload'].get('policy')))
                self._send_json({'ok': True, 'queue': queue, 'summary': queue.get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        rest = path.removeprefix('/api/audio-quality-actions/').strip('/')
        _split_state['parts'] = rest.split('/') if rest else []
        if len(_split_state['parts']) == 1:
            _split_state['queue_id'] = _split_state['parts'][0]
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            queue = self.release_audio_quality_action_queue_store.read_queue(_split_state['queue_id'])
            _split_state['summary'] = self.release_audio_quality_action_queue_store.read_summary(_split_state['queue_id']) if self.release_audio_quality_action_queue_store.summary_path(_split_state['queue_id']).exists() else {}
            self._send_json({'ok': True, 'queue': queue, 'summary_report': _split_state['summary'], 'summary': _split_state['summary'].get('summary', {}) if _split_state['summary'] else {}})
            return (True, None)
        return (False, None)

    def _handle_audio_quality_actions_route_part_02(self, method: str, path: str, _split_state):
        if len(_split_state['parts']) == 2:
            _split_state['queue_id'], action = _split_state['parts']
            if action == 'download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.release_audio_quality_action_queue_store.zip_path(_split_state['queue_id']), 'application/zip', filename='release-audio-quality-action-queue.zip')
                return (True, None)
            if action == 'archive-download':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.release_audio_quality_action_signoff_store.archive_zip_path(_split_state['queue_id']), 'application/zip', filename='release-audio-quality-action-queue-signoff-archive.zip')
                return (True, None)
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            if action == 'refresh':
                _split_state['summary'] = self.release_audio_quality_action_queue_store.refresh_status(_split_state['queue_id'])
                self._send_json({'ok': _split_state['summary'].get('status') != 'stale', 'summary_report': _split_state['summary'], 'summary': _split_state['summary'].get('summary', {}), 'status': _split_state['summary'].get('status')})
                return (True, None)
            if action == 'run-safe':
                result = self.release_audio_quality_action_queue_store.run_safe(_split_state['queue_id'])
                self._send_json({'ok': result.get('status') not in {'failed', 'stale'}, **result})
                return (True, None)
            if action == 'export':
                result = self.release_audio_quality_action_queue_store.export_package(_split_state['queue_id'])
                self._send_json({'ok': result.get('status') not in {'failed', 'stale'}, **result})
                return (True, None)
            if action == 'zip':
                result = self.release_audio_quality_action_queue_store.build_zip(_split_state['queue_id'])
                self._send_json({'ok': result.get('status') not in {'failed', 'stale'}, **result})
                return (True, None)
            if action == 'verify':
                report = self.release_audio_quality_action_queue_store.verify_zip(_split_state['queue_id'], strict=bool(_split_state['payload'].get('strict', True)), require_current_observatory=bool(_split_state['payload'].get('require_current_observatory', False)), observatory_zip_path=_split_state['payload'].get('observatory_zip'), observatory_verification_report_path=_split_state['payload'].get('observatory_verification_report'), evidence_root=_split_state['payload'].get('evidence_root') or self.release_store.root, require_no_blocking=bool(_split_state['payload'].get('require_no_blocking', True)))
                self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
                return (True, None)
            if action == 'manual-items':
                result = self.release_audio_quality_action_signoff_store.list_manual_items(_split_state['queue_id'])
                self._send_json({'ok': True, **result, 'status': 'passed'})
                return (True, None)
            if action == 'resolve-manual':
                item_id = str(_split_state['payload'].get('item_id') or '')
                result = self.release_audio_quality_action_signoff_store.resolve_manual_item(_split_state['queue_id'], item_id, _split_state['payload'])
                self._send_json({'ok': True, 'resolution': result, 'status': 'passed'})
                return (True, None)
            if action == 'closeout':
                closeout = self.release_audio_quality_action_signoff_store.refresh_closeout(_split_state['queue_id'])
                self._send_json({'ok': closeout.get('status') == 'passed', 'closeout': closeout, 'summary': closeout.get('summary', {}), 'status': closeout.get('status')})
                return (True, None)
            if action == 'signoff':
                result = self.release_audio_quality_action_signoff_store.signoff(_split_state['queue_id'], _split_state['payload'])
                self._send_json({'ok': True, **result})
                return (True, None)
            if action == 'archive':
                result = self.release_audio_quality_action_signoff_store.export_archive(_split_state['queue_id'])
                self._send_json({'ok': result.get('status') == 'passed', **result})
                return (True, None)
            if action == 'archive-zip':
                result = self.release_audio_quality_action_signoff_store.build_archive_zip(_split_state['queue_id'])
                self._send_json({'ok': result.get('status') == 'passed', **result})
                return (True, None)
            if action == 'archive-verify':
                report = self.release_audio_quality_action_signoff_store.verify_archive(_split_state['queue_id'], strict=bool(_split_state['payload'].get('strict', True)), require_current_queue=bool(_split_state['payload'].get('require_current_queue', True)), require_signed=bool(_split_state['payload'].get('require_signed', True)), queue_zip_path=_split_state['payload'].get('queue_zip'), queue_verification_report_path=_split_state['payload'].get('queue_verification_report'), observatory_zip_path=_split_state['payload'].get('observatory_zip'), observatory_verification_report_path=_split_state['payload'].get('observatory_verification_report'), evidence_root=_split_state['payload'].get('evidence_root') or self.release_store.root)
                self._send_json({'ok': report.get('status') == 'passed', 'verification': report, 'summary': report.get('summary', {}), 'status': report.get('status')})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Audio Quality Action Queue route not found.')
            return (True, None)
        return (False, None)

    def _handle_audio_quality_actions_route_part_03(self, method: str, path: str, _split_state):
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Audio Quality Action Queue route not found.')
        return (False, None)

    def _handle_audio_quality_actions_route(self, method: str, path: str) -> None:
        _split_state: dict[str, JsonDocument] = {}
        try:
            _split_result = self._handle_audio_quality_actions_route_part_01(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_audio_quality_actions_route_part_02(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_audio_quality_actions_route_part_03(method, path, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueSignoffNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueSignoffStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueSignoffValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioQualityActionQueueSignoffError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_mastering_profiles_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/mastering/profiles":
                if method == "GET":
                    profiles = [profile.to_dict() for profile in self.server.mastering_profile_store.list_profiles(include_builtins=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.server.mastering_profile_store.create_profile(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/mastering/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Mastering profile route not found.")
                return
            profile_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    profile = self.server.mastering_profile_store.get_profile(profile_id)
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "PATCH":
                    profile = self.server.mastering_profile_store.update_profile(profile_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "DELETE":
                    self.server.mastering_profile_store.delete_profile(profile_id)
                    self._send_json({"ok": True, "deleted": True, "profile_id": profile_id})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[1] == "clone":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                profile = self.server.mastering_profile_store.clone_profile(profile_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "profile": profile.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Mastering profile route not found.")
        except _interfaces_api_runtime.MasteringProfileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.MasteringProfileError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_encoding_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-encoding/config":
                if method == "GET":
                    self._send_json({"ok": True, "config": self.server.audio_encoding_store.read_config().public_summary()})
                    return
                if method == "POST":
                    config = self.server.audio_encoding_store.write_config(self._read_json_body())
                    self._send_json({"ok": True, "config": config})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path == "/api/audio-encoding/config/test":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.server.audio_encoding_store.test_config()})
                return
            if path == "/api/audio-encoding/config/reset":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "config": self.server.audio_encoding_store.reset_config()})
                return
            if path == "/api/audio-encoding/profiles":
                if method == "GET":
                    profiles = [profile.to_dict() for profile in self.server.audio_encoding_profile_store.list_profiles(include_builtins=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.server.audio_encoding_profile_store.create_profile(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio-encoding/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio encoding profile route not found.")
                return
            profile_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    profile = self.server.audio_encoding_profile_store.get_profile(profile_id)
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "PATCH":
                    profile = self.server.audio_encoding_profile_store.update_profile(profile_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "DELETE":
                    self.server.audio_encoding_profile_store.delete_profile(profile_id)
                    self._send_json({"ok": True, "deleted": True, "profile_id": profile_id})
                    return
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[1] == "clone":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                profile = self.server.audio_encoding_profile_store.clone_profile(profile_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "profile": profile.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio encoding profile route not found.")
        except _interfaces_api_runtime.AudioEncodingProfileNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioEncodingProfileError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
