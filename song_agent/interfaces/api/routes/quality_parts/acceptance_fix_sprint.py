from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesAcceptanceFixSprint(QualityRouteContext):
    def _handle_acceptance_fix_sprint_route_part_01(self, method: str, route: tuple[str, list[str]], _split_state):
        if not _split_state['parts']:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['sprint'] = self.acceptance_fix_sprint_store.read_sprint(_split_state['fix_sprint_id'])
            items = self.acceptance_fix_sprint_store.read_items(_split_state['fix_sprint_id'])
            self._send_json({'ok': True, 'fix_sprint': _split_state['sprint'].to_dict(), 'items': [item.to_dict() for item in items], 'summary': _interfaces_api_runtime.fix_sprint_summary(_split_state['sprint'], items)})
            return (True, None)
        if _split_state['parts'] == ['archive']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['sprint'] = self.acceptance_fix_sprint_store.archive_sprint(_split_state['fix_sprint_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'fix_sprint': _split_state['sprint'].to_dict(), 'summary': _interfaces_api_runtime.fix_sprint_summary(_split_state['sprint'])})
            return (True, None)
        if _split_state['parts'] == ['refresh-status']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['sprint'] = self.acceptance_fix_sprint_store.refresh_status(_split_state['fix_sprint_id'], now=_interfaces_api_runtime._utc_now())
            items = self.acceptance_fix_sprint_store.read_items(_split_state['fix_sprint_id'])
            self._send_json({'ok': True, 'fix_sprint': _split_state['sprint'].to_dict(), 'items': [item.to_dict() for item in items], 'summary': _interfaces_api_runtime.fix_sprint_summary(_split_state['sprint'], items)})
            return (True, None)
        if _split_state['parts'] == ['items']:
            if method == 'GET':
                items = self.acceptance_fix_sprint_store.read_items(_split_state['fix_sprint_id'])
                _split_state['sprint'] = self.acceptance_fix_sprint_store.read_sprint(_split_state['fix_sprint_id'])
                self._send_json({'ok': True, 'fix_sprint': _split_state['sprint'].to_dict(), 'items': [item.to_dict() for item in items], 'summary': _interfaces_api_runtime.fix_sprint_summary(_split_state['sprint'], items)})
                return (True, None)
            if method == 'POST':
                item = self.acceptance_fix_sprint_store.add_item(_split_state['fix_sprint_id'], self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'item': item.to_dict()}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if len(_split_state['parts']) >= 3 and _split_state['parts'][0] == 'items':
            item_id = _split_state['parts'][1]
            action = _split_state['parts'][2]
            if action == 'waive':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['payload'] = self._read_json_body()
                item = self.acceptance_fix_sprint_store.waive_item(_split_state['fix_sprint_id'], item_id, str(_split_state['payload'].get('reason') or _split_state['payload'].get('notes') or ''), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'item': item.to_dict()})
                return (True, None)
            if action == 'reopen':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                item = self.acceptance_fix_sprint_store.reopen_item(_split_state['fix_sprint_id'], item_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'item': item.to_dict()})
                return (True, None)
            if action == 'create-review-task':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['result'] = self.acceptance_fix_sprint_store.create_review_tasks(_split_state['fix_sprint_id'], item_id=item_id, now=_interfaces_api_runtime._utc_now())
                _split_state['created'] = any((_split_state['row'].get('status') == 'created' for _split_state['row'] in _split_state['result'].get('results', []) if isinstance(_split_state['row'], dict)))
                self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED if _split_state['created'] else _interfaces_api_runtime.HTTPStatus.OK)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Acceptance Fix Sprint item route not found.')
            return (True, None)
        return (False, None)

    def _handle_acceptance_fix_sprint_route_part_02(self, method: str, route: tuple[str, list[str]], _split_state):
        if _split_state['parts'] == ['create-review-tasks']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.acceptance_fix_sprint_store.create_review_tasks(_split_state['fix_sprint_id'], now=_interfaces_api_runtime._utc_now())
            _split_state['created'] = any((_split_state['row'].get('status') == 'created' for _split_state['row'] in _split_state['result'].get('results', []) if isinstance(_split_state['row'], dict)))
            self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED if _split_state['created'] else _interfaces_api_runtime.HTTPStatus.OK)
            return (True, None)
        if _split_state['parts'] == ['create-recheck-suite']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.acceptance_fix_sprint_store.create_recheck_suite(_split_state['fix_sprint_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['parts'] == ['link-recheck-suite']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._read_json_body()
            _split_state['sprint'] = self.acceptance_fix_sprint_store.link_recheck_suite(_split_state['fix_sprint_id'], str(_split_state['payload'].get('suite_id') or ''), now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'fix_sprint': _split_state['sprint'].to_dict(), 'summary': _interfaces_api_runtime.fix_sprint_summary(_split_state['sprint'])})
            return (True, None)
        if _split_state['parts'] == ['delta']:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            delta = self.acceptance_fix_sprint_store.read_delta(_split_state['fix_sprint_id'])
            self._send_json({'ok': True, 'delta_report': delta, 'summary': delta.get('summary', {})})
            return (True, None)
        if _split_state['parts'] == ['delta', 'refresh']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            delta = self.acceptance_fix_sprint_store.refresh_delta(_split_state['fix_sprint_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'delta_report': delta, 'summary': delta.get('summary', {})})
            return (True, None)
        if _split_state['parts'] == ['closeout']:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            closeout = self.acceptance_fix_sprint_store.read_closeout(_split_state['fix_sprint_id'])
            self._send_json({'ok': True, 'closeout_report': closeout, 'summary': _interfaces_api_runtime.acceptance_fix_closeout_summary(closeout)})
            return (True, None)
        if _split_state['parts'] == ['close']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            closeout = self.acceptance_fix_sprint_store.close(_split_state['fix_sprint_id'], self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            _split_state['sprint'] = self.acceptance_fix_sprint_store.read_sprint(_split_state['fix_sprint_id'])
            self._send_json({'ok': True, 'fix_sprint': _split_state['sprint'].to_dict(), 'closeout_report': closeout, 'summary': _interfaces_api_runtime.acceptance_fix_closeout_summary(closeout)})
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Acceptance Fix Sprint route not found.')
        return (False, None)

    def _handle_acceptance_fix_sprint_route(self, method: str, route: tuple[str, list[str]]) -> None:
        _split_state: ImplementationDocument = {}
        _split_state['fix_sprint_id'], _split_state['parts'] = route
        try:
            _split_result = self._handle_acceptance_fix_sprint_route_part_01(method, route, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_acceptance_fix_sprint_route_part_02(method, route, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.AcceptanceFixSprintNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceFixSprintStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.AcceptanceFixSprintError, _interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, FileNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_root(self, method: str) -> None:
        try:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.latest_report()
            self._send_json({"ok": True, "knowledge_report": report, "summary": _interfaces_api_runtime.knowledge_report_summary(report)})
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_refresh(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.refresh(self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "knowledge_report": report, "summary": _interfaces_api_runtime.knowledge_report_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_report(self, method: str, report_id: str) -> None:
        try:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.get_report(report_id)
            self._send_json({"ok": True, "knowledge_report": report, "summary": _interfaces_api_runtime.knowledge_report_summary(report)})
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_entries(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = _interfaces_api_runtime.parse_qs(query_string)
            include_hidden = _interfaces_api_runtime._query_value(query, "include_hidden") in {"1", "true", "yes"}
            entries = self.acceptance_kb_store.list_entries(include_hidden=include_hidden)
            self._send_json({"ok": True, "entries": [_interfaces_api_runtime.knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}})
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_entry_route(self, method: str, route: tuple[str, str]) -> None:
        entry_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                entry = self.acceptance_kb_store.read_entry(entry_id)
                self._send_json({"ok": True, "entry": entry.to_dict(), "summary": _interfaces_api_runtime.knowledge_entry_summary(entry)})
                return
            if action in {"hide", "unhide"}:
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                entry = self.acceptance_kb_store.hide_entry(entry_id, hidden=action == "hide", now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "entry": entry.to_dict(), "summary": _interfaces_api_runtime.knowledge_entry_summary(entry)})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Acceptance KB entry route not found.")
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_search(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = _interfaces_api_runtime.parse_qs(query_string)
            payload = {
                "issue_type": _interfaces_api_runtime._query_value(query, "issue_type") or "",
                "style": _interfaces_api_runtime._query_value(query, "style") or "",
                "song_id": _interfaces_api_runtime._query_value(query, "song_id") or "",
                "project_id": _interfaces_api_runtime._query_value(query, "project_id") or "",
                "release_id": _interfaces_api_runtime._query_value(query, "release_id") or "",
                "outcome_status": _interfaces_api_runtime._query_value(query, "outcome_status") or "",
            }
            include_hidden = _interfaces_api_runtime._query_value(query, "include_hidden") in {"1", "true", "yes"}
            entries = self.acceptance_kb_store.search_entries(payload, include_hidden=include_hidden)
            self._send_json({"ok": True, "entries": [_interfaces_api_runtime.knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}})
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_recommend(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            recommendation = self.acceptance_kb_store.recommend(self._optional_json_body())
            self._send_json({"ok": True, "recommendation": recommendation})
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_version_audio_route(self, method: str, project_id: str, version_id: str, action: str) -> None:
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next((item for item in document.versions if item.version_id == version_id), None)
            if version is None:
                raise FileNotFoundError(version_id)
            job = self.store.get_job(version.job_id)
            if job is None:
                raise FileNotFoundError(version.job_id)
            audio_path = _interfaces_api_runtime.Path(job.output_dir) / "renders" / "song.wav"
            if action == "audio":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if not audio_path.exists():
                    self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio render is not available for this version.")
                    return
                stale_reasons = self._job_audio_artifact_stale_reasons(job)
                if stale_reasons:
                    self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, f"Audio artifact is stale: {', '.join(stale_reasons)}.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{version_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                profile = self._renderer_profile_from_payload(payload)
                config = profile.to_renderer_config() if profile is not None else None
                audio, status, error = self.store.render_job_audio(job.job_id, config=config, audio_profile=profile)
                if error is not None:
                    self._send_error(status, str(_interfaces_api_runtime.sanitize_metadata({"error": error}).get("error") or "Audio render failed."))
                    return
                self.project_store.append_event(project_id, "project_version_audio_rendered", {"version_id": version_id, "job_id": job.job_id})
                wav_path = _interfaces_api_runtime.Path(job.output_dir) / "renders" / "song.wav"
                self._send_json(
                    {
                        "ok": True,
                        "version_id": version_id,
                        "job_id": job.job_id,
                        "audio_status": "completed",
                        "audio_url": f"/api/projects/{project_id}/versions/{version_id}/audio",
                        "audio": {"exists": wav_path.exists(), "size_bytes": wav_path.stat().st_size if wav_path.exists() else 0, **audio},
                    },
                    status=status,
                )
                return
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except ValueError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project version audio route not found.")
