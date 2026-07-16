from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesAcceptance:
    def _handle_acceptance_route_part_01(self, method: str, suite_id: str, tail: str, _split_state):
        _split_state['parts'] = [part for part in tail.strip('/').split('/') if part]
        if not _split_state['parts']:
            if method == 'GET':
                suite = self.acceptance_store.get_suite(suite_id)
                cases = self.acceptance_store.list_cases(suite_id)
                self._send_json({'ok': True, 'suite': suite.to_dict(), 'cases': [_split_state['case'].to_dict() for _split_state['case'] in cases], 'summary': _interfaces_api_runtime.acceptance_suite_summary(suite), 'events': self.acceptance_store.read_events(suite_id)})
                return (True, None)
            if method == 'POST':
                suite = self.acceptance_store.get_suite(suite_id)
                self.acceptance_store.ensure_mutable(suite)
                _split_state['payload'] = self._optional_json_body()
                if _split_state['payload'].get('name'):
                    suite.name = str(_split_state['payload'].get('name'))
                if _split_state['payload'].get('mode'):
                    suite.mode = str(_split_state['payload'].get('mode'))
                if _split_state['payload'].get('min_rating') is not None:
                    suite.min_rating = int(_split_state['payload'].get('min_rating'))
                suite = self.acceptance_store.save_suite(suite)
                self._send_json({'ok': True, 'suite': suite.to_dict(), 'summary': _interfaces_api_runtime.acceptance_suite_summary(suite)})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['parts'] == ['cases']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['case'] = self.acceptance_store.add_case(suite_id, self._read_json_body())
            self._send_json({'ok': True, 'case': _split_state['case'].to_dict(), 'summary': _interfaces_api_runtime.acceptance_suite_summary(self.acceptance_store.get_suite(suite_id))}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        if _split_state['parts'] == ['report']:
            if method == 'GET':
                _split_state['report'] = self.acceptance_store.read_report(suite_id, default={})
                self._send_json({'ok': True, 'suite_id': suite_id, 'report': _split_state['report'], 'summary': _interfaces_api_runtime.acceptance_report_summary(_split_state['report'])})
                return (True, None)
            if method == 'POST':
                _split_state['report'] = self.acceptance_store.build_report(suite_id)
                self._send_json({'ok': True, 'suite_id': suite_id, 'report': _split_state['report'], 'summary': _interfaces_api_runtime.acceptance_report_summary(_split_state['report'])})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['parts'] == ['signoff']:
            if method == 'GET':
                signoff = self.acceptance_store.read_signoff(suite_id, default={})
                self._send_json({'ok': True, 'suite_id': suite_id, 'signoff': signoff, 'summary': _interfaces_api_runtime.acceptance_signoff_summary(signoff)})
                return (True, None)
            if method == 'POST':
                signoff = self.acceptance_store.signoff(suite_id, self._optional_json_body())
                self._send_json({'ok': True, 'suite_id': suite_id, 'signoff': signoff, 'summary': _interfaces_api_runtime.acceptance_signoff_summary(signoff)})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if _split_state['parts'] == ['signoff', 'reset']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            reason = str(_split_state['payload'].get('reason') or '').strip()
            if not reason:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'reason is required.')
                return (True, None)
            event = self.acceptance_store.reset_signoff(suite_id, reason)
            self._send_json({'ok': True, 'suite_id': suite_id, 'summary': {'status': 'reset'}, 'history_event': event})
            return (True, None)
        if _split_state['parts'] == ['archive']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            suite = self.acceptance_store.archive_suite(suite_id)
            self._send_json({'ok': True, 'suite': suite.to_dict(), 'summary': _interfaces_api_runtime.acceptance_suite_summary(suite)})
            return (True, None)
        return (False, None)

    def _handle_acceptance_route_part_02(self, method: str, suite_id: str, tail: str, _split_state):
        if _split_state['parts'] == ['diff']:
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            other_suite_id = str(_split_state['payload'].get('other_suite_id') or _split_state['payload'].get('left_suite_id') or '').strip()
            if not other_suite_id:
                self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, 'other_suite_id is required.')
                return (True, None)
            left = self.acceptance_store.read_report(other_suite_id)
            right = self.acceptance_store.read_report(suite_id)
            diff = _interfaces_api_runtime.build_acceptance_diff(left, right)
            self._send_json({'ok': True, 'suite_id': suite_id, 'other_suite_id': other_suite_id, 'diff': diff, 'summary': diff.get('summary', {})})
            return (True, None)
        if _split_state['parts'] == ['analytics']:
            self._handle_suite_acceptance_analytics(method, suite_id)
            return (True, None)
        if _split_state['parts'] == ['analytics', 'refresh']:
            self._handle_suite_acceptance_analytics_refresh(method, suite_id)
            return (True, None)
        if _split_state['parts'] == ['human-review-packs']:
            if method == 'GET':
                packs = self.human_review_pack_store.list_packs(suite_id)
                self._send_json({'ok': True, 'suite_id': suite_id, 'packs': packs, 'summary': {'pack_count': len(packs)}})
                return (True, None)
            if method == 'POST':
                _split_state['result'] = self.human_review_pack_store.create_pack(suite_id, self._optional_json_body())
                self._send_json({'ok': True, 'suite_id': suite_id, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if len(_split_state['parts']) >= 2 and _split_state['parts'][0] == 'human-review-packs':
            pack_id = _split_state['parts'][1]
            _split_state['action'] = _split_state['parts'][2] if len(_split_state['parts']) >= 3 else ''
            if not _split_state['action']:
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                pack = self.human_review_pack_store.get_pack(suite_id, pack_id)
                self._send_json({'ok': True, 'suite_id': suite_id, 'pack': pack})
                return (True, None)
            if _split_state['action'] == 'zip':
                if method == 'POST':
                    _split_state['result'] = self.human_review_pack_store.build_zip(suite_id, pack_id)
                    self._send_json({'ok': True, 'suite_id': suite_id, **_split_state['result']})
                    return (True, None)
                if method == 'GET':
                    self._send_file(self.human_review_pack_store.zip_path(suite_id, pack_id), 'application/zip', filename=f'{suite_id}-{pack_id}-human-review-pack.zip')
                    return (True, None)
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            if _split_state['action'] == 'verify':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['payload'] = self._optional_json_body()
                _split_state['report'] = self.human_review_pack_store.verify_pack(suite_id, pack_id, strict=bool(_split_state['payload'].get('strict', False)))
                self._send_json({'ok': _split_state['report'].get('status') == 'passed', 'suite_id': suite_id, 'pack_id': pack_id, 'report': _split_state['report'], 'summary': _split_state['report'].get('summary', {})})
                return (True, None)
        if _split_state['parts'] == ['review-imports']:
            if method == 'GET':
                imports = self.human_review_pack_store.list_imports(suite_id)
                self._send_json({'ok': True, 'suite_id': suite_id, 'imports': imports, 'summary': {'import_count': len(imports)}})
                return (True, None)
            if method == 'POST':
                _split_state['record'] = self.human_review_pack_store.import_response(suite_id, self._read_json_body())
                self._send_json({'ok': True, 'suite_id': suite_id, 'import': _split_state['record'], 'summary': _split_state['record'].get('summary', {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        return (False, None)

    def _handle_acceptance_route_part_03(self, method: str, suite_id: str, tail: str, _split_state):
        if len(_split_state['parts']) == 2 and _split_state['parts'][0] == 'review-imports':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['record'] = self.human_review_pack_store.get_import(suite_id, _split_state['parts'][1])
            self._send_json({'ok': True, 'suite_id': suite_id, 'import': _split_state['record'], 'summary': _split_state['record'].get('summary', {})})
            return (True, None)
        if len(_split_state['parts']) >= 2 and _split_state['parts'][0] == 'cases':
            case_id = _split_state['parts'][1]
            _split_state['action'] = _split_state['parts'][2] if len(_split_state['parts']) >= 3 else ''
            if not _split_state['action']:
                _split_state['case'] = self.acceptance_store.get_case(suite_id, case_id)
                self._send_json({'ok': True, 'case': _split_state['case'].to_dict(), 'health': self.acceptance_store.read_health(suite_id, case_id, default={}), 'review': self.acceptance_store.read_review(suite_id, case_id, default={})})
                return (True, None)
            if _split_state['action'] == 'generate':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['payload'] = self._optional_json_body()
                _split_state['case'] = self.acceptance_store.generate_case(suite_id, case_id, render_audio_mode=str(_split_state['payload'].get('render_audio') or 'auto'))
                self._send_json({'ok': True, 'case': _split_state['case'].to_dict()})
                return (True, None)
            if _split_state['action'] == 'health':
                if method == 'GET':
                    _split_state['report'] = self.acceptance_store.read_health(suite_id, case_id, default={})
                    self._send_json({'ok': True, 'suite_id': suite_id, 'case_id': case_id, 'health': _split_state['report']})
                    return (True, None)
                if method == 'POST':
                    _split_state['report'] = self.acceptance_store.run_health(suite_id, case_id)
                    self._send_json({'ok': True, 'suite_id': suite_id, 'case_id': case_id, 'health': _split_state['report']})
                    return (True, None)
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            if _split_state['action'] == 'render-audio':
                if method != 'POST':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                _split_state['payload'] = self._optional_json_body()
                profile = self._renderer_profile_from_payload(_split_state['payload'])
                config = profile.to_renderer_config() if profile is not None else None
                _split_state['result'] = self.acceptance_store.render_audio(suite_id, case_id, mode=str(_split_state['payload'].get('mode') or 'auto'), config=config)
                self._send_json({'ok': True, 'suite_id': suite_id, 'case_id': case_id, **_split_state['result']})
                return (True, None)
            if _split_state['action'] == 'review':
                if method == 'GET':
                    review = self.acceptance_store.read_review(suite_id, case_id, default={})
                    self._send_json({'ok': True, 'suite_id': suite_id, 'case_id': case_id, 'review': review, 'summary': _interfaces_api_runtime.listening_review_summary(review)})
                    return (True, None)
                if method == 'POST':
                    review = self.acceptance_store.write_review(suite_id, case_id, self._read_json_body())
                    self._send_json({'ok': True, 'suite_id': suite_id, 'case_id': case_id, 'review': review, 'summary': _interfaces_api_runtime.listening_review_summary(review)})
                    return (True, None)
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            if _split_state['action'] == 'midi':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.acceptance_store.case_dir(suite_id, case_id) / 'song.mid', 'audio/midi', filename=f'{suite_id}-{case_id}.mid')
                return (True, None)
            if _split_state['action'] == 'audio':
                if method != 'GET':
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                    return (True, None)
                self._send_file(self.acceptance_store.case_dir(suite_id, case_id) / 'song.wav', 'audio/wav', filename=f'{suite_id}-{case_id}.wav')
                return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Acceptance route not found.')
        return (False, None)

    def _handle_acceptance_route(self, method: str, suite_id: str, tail: str) -> None:
        _split_state = {}
        try:
            _split_result = self._handle_acceptance_route_part_01(method, suite_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_acceptance_route_part_02(method, suite_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_acceptance_route_part_03(method, suite_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.AcceptanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.HumanReviewPackStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AcceptanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.HumanReviewPackNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.HumanReviewPackValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_suite_acceptance_analytics(self, method: str, suite_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "suite_id": suite_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except _interfaces_api_runtime.AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_suite_acceptance_analytics_refresh(self, method: str, suite_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "suite_id": suite_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_acceptance_analytics(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="project", project_id=project_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "project_id": project_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_acceptance_analytics_refresh(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="project", project_id=project_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "project_id": project_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except FileNotFoundError:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Project not found.")
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_acceptance_analytics(self, method: str, release_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.release_store.get_release(release_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="release", release_id=release_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "release_id": release_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_acceptance_analytics_refresh(self, method: str, release_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.release_store.get_release(release_id)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(scope_type="release", release_id=release_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "release_id": release_id, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_root(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = _interfaces_api_runtime._analytics_scope_from_query(query_string)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except _interfaces_api_runtime.AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, _interfaces_api_runtime.ReleaseNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
