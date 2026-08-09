from __future__ import annotations

from song_agent.platform.contracts.documents import JsonDocument

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseAudioRevisions(QualityRouteContext):
    def _handle_release_audio_revisions_part_01(self, method: str, release_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method == 'GET':
                sessions = self.server.audio_revision_store.list_sessions(release_id)
                summary = self.server.audio_revision_store.gate(release_id, required=False, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'sessions': sessions, 'summary': summary})
                return (True, None)
            if method == 'POST':
                session = self.server.audio_revision_store.create_session(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'session': session, 'summary': self.server.audio_revision_store.gate(release_id, required=False, now=_interfaces_api_runtime._utc_now())}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/summary':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            summary = self.server.audio_revision_store.gate(release_id, required=False, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'summary': summary})
            return (True, None)
        _split_state['parts'] = [part for part in tail.strip('/').split('/') if part]
        if not _split_state['parts']:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Audio revision route not found.')
            return (True, None)
        _split_state['session_id'] = _split_state['parts'][0]
        if len(_split_state['parts']) == 1:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            session = self.server.audio_revision_store.read_session(release_id, _split_state['session_id'])
            issues = self.server.audio_revision_store.list_issues(release_id, _split_state['session_id'])
            candidates = self.server.audio_revision_store.list_candidates(release_id, _split_state['session_id'])
            closeout = self.server.audio_revision_store.read_closeout(release_id, _split_state['session_id'], default={})
            self._send_json({'ok': True, 'release_id': release_id, 'session': session, 'issues': issues, 'candidates': candidates, 'closeout': closeout})
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.server.audio_revision_store.refresh_recheck_status(release_id, _split_state['session_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, **_split_state['result']})
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'close':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.server.audio_revision_store.close_session(release_id, _split_state['session_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, **_split_state['result']})
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'archive':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            session = self.server.audio_revision_store.archive_session(release_id, _split_state['session_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'session': session})
            return (True, None)
        return (False, None)

    def _handle_release_audio_revisions_part_02(self, method: str, release_id: str, tail: str, _split_state):
        if len(_split_state['parts']) >= 2 and _split_state['parts'][1] == 'issues':
            if len(_split_state['parts']) == 2:
                if method == 'GET':
                    self._send_json({'ok': True, 'release_id': release_id, 'session_id': _split_state['session_id'], 'issues': self.server.audio_revision_store.list_issues(release_id, _split_state['session_id'])})
                    return (True, None)
                if method == 'POST':
                    issue = self.server.audio_revision_store.create_issue(release_id, _split_state['session_id'], self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({'ok': True, 'release_id': release_id, 'issue': issue}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                    return (True, None)
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            issue_id = _split_state['parts'][2]
            if len(_split_state['parts']) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                issue = self.server.audio_revision_store.read_issue(release_id, _split_state['session_id'], issue_id)
                self._send_json({'ok': True, 'release_id': release_id, 'issue': issue})
                return (True, None)
            if len(_split_state['parts']) == 4 and _split_state['parts'][3] in {'waive', 'reopen'}:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                if _split_state['parts'][3] == 'waive':
                    issue = self.server.audio_revision_store.waive_issue(release_id, _split_state['session_id'], issue_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                else:
                    issue = self.server.audio_revision_store.reopen_issue(release_id, _split_state['session_id'], issue_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'issue': issue})
                return (True, None)
            if len(_split_state['parts']) == 5 and _split_state['parts'][3] == 'candidates' and (_split_state['parts'][4] == 'generate'):
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.server.audio_revision_store.generate_candidates(release_id, _split_state['session_id'], issue_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
        return (False, None)

    def _handle_release_audio_revisions_part_03(self, method: str, release_id: str, tail: str, _split_state):
        if len(_split_state['parts']) >= 2 and _split_state['parts'][1] == 'candidates':
            if len(_split_state['parts']) == 2:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_json({'ok': True, 'release_id': release_id, 'session_id': _split_state['session_id'], 'candidates': self.server.audio_revision_store.list_candidates(release_id, _split_state['session_id'])})
                return (True, None)
            candidate_id = _split_state['parts'][2]
            if len(_split_state['parts']) == 3:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                candidate = self.server.audio_revision_store.read_candidate(release_id, _split_state['session_id'], candidate_id)
                self._send_json({'ok': True, 'release_id': release_id, 'candidate': candidate})
                return (True, None)
            if len(_split_state['parts']) == 4 and _split_state['parts'][3] in {'midi', 'audio'}:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                path, media_type, filename = self.server.audio_revision_store.download_candidate_artifact(release_id, _split_state['session_id'], candidate_id, 'midi' if _split_state['parts'][3] == 'midi' else 'audio')
                self._send_file(path, media_type, filename=filename)
                return (True, None)
            if len(_split_state['parts']) == 4 and _split_state['parts'][3] in {'review', 'select', 'apply'}:
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                if _split_state['parts'][3] == 'review':
                    candidate = self.server.audio_revision_store.review_candidate(release_id, _split_state['session_id'], candidate_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({'ok': True, 'release_id': release_id, 'candidate': candidate})
                    return (True, None)
                if _split_state['parts'][3] == 'select':
                    candidate = self.server.audio_revision_store.select_candidate(release_id, _split_state['session_id'], candidate_id, now=_interfaces_api_runtime._utc_now())
                    self._send_json({'ok': True, 'release_id': release_id, 'candidate': candidate})
                    return (True, None)
                _split_state['result'] = self.server.audio_revision_store.apply_candidate(release_id, _split_state['session_id'], candidate_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, **_split_state['result']})
                return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Audio revision route not found.')
        return (False, None)

    def _handle_release_audio_revisions(self, method: str, release_id: str, tail: str) -> None:
        _split_state: dict[str, JsonDocument] = {}
        try:
            _split_result = self._handle_release_audio_revisions_part_01(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_audio_revisions_part_02(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_audio_revisions_part_03(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.AudioRevisionNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioRevisionStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AudioRevisionError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except (_interfaces_api_runtime.MixControlStateError, _interfaces_api_runtime.ReleaseStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.MixControlError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_mastering(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(
                    {
                        "ok": True,
                        "release_id": release_id,
                        "summary": self.server.mastering_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now()),
                        "analysis": self.server.mastering_store.read_analysis(release_id, default={}),
                        "plan": self.server.mastering_store.read_plan(release_id, default={}),
                        "candidates": self.server.mastering_store.list_candidates(release_id),
                        "selected_candidate": self.server.mastering_store.read_selected_candidate(release_id, default={}),
                    }
                )
                return
            if tail == "/analyze":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                analysis = self.server.mastering_store.analyze(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self.release_store.append_event(release_id, "release_mastering_analyzed", {"status": analysis.get("status"), "profile_id": analysis.get("profile_id")})
                self._send_json({"ok": True, "release_id": release_id, "analysis": analysis, "summary": self.server.mastering_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now())})
                return
            if tail == "/plan":
                if method == "GET":
                    plan = self.server.mastering_store.read_plan(release_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "plan": plan, "summary": self.server.mastering_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now())})
                    return
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.server.mastering_store.build_plan(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self.release_store.append_event(release_id, "release_mastering_plan_created", {"action_count": plan.get("summary", {}).get("action_count")})
                self._send_json({"ok": True, "release_id": release_id, "plan": plan, "summary": self.server.mastering_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now())})
                return
            if tail == "/candidates":
                if method == "GET":
                    self._send_json({"ok": True, "release_id": release_id, "candidates": self.server.mastering_store.list_candidates(release_id), "summary": self.server.mastering_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now())})
                    return
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidate = self.server.mastering_store.render_candidate(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self.release_store.append_event(release_id, "release_mastering_candidate_rendered", {"candidate_id": candidate.get("candidate_id"), "status": candidate.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "candidate": candidate, "summary": self.server.mastering_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now())}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.server.mastering_store.refresh(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "release_id": release_id, **result})
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.server.mastering_store.reset(release_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, **result})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if len(parts) >= 2 and parts[0] == "candidates":
                candidate_id = parts[1]
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    candidate = self.server.mastering_store.read_candidate(release_id, candidate_id)
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                    return
                if len(parts) == 5 and parts[2] == "tracks" and parts[4] == "audio":
                    if method != "GET":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    path = self.server.mastering_store.candidate_audio_path(release_id, candidate_id, parts[3])
                    self._send_file(path, "audio/wav", filename=f"{parts[3]}-mastered.wav")
                    return
                if len(parts) == 3 and parts[2] in {"review", "select"}:
                    if method != "POST":
                        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if parts[2] == "review":
                        candidate = self.server.mastering_store.review_candidate(release_id, candidate_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                    else:
                        candidate = self.server.mastering_store.select_candidate(release_id, candidate_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate, "summary": self.server.mastering_store.get_summary(release_id, now=_interfaces_api_runtime._utc_now())})
                    return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Mastering route not found.")
        except _interfaces_api_runtime.MasteringNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.MasteringStateError, _interfaces_api_runtime.ReleaseStateError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.MasteringQAError, _interfaces_api_runtime.MasteringProfileError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
