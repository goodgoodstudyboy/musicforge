from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseAudioTimeline(QualityRouteContext):
    def _handle_release_audio_timeline_part_01(self, method: str, release_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, **self.release_audio_timeline_store.list_timelines(release_id)})
            return (True, None)
        if tail == '/refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['result'] = self.release_audio_timeline_store.refresh_timeline(release_id, force_new=bool(_split_state['payload'].get('force_new', False)))
            self._send_json({'ok': _split_state['result'].get('status') == 'passed', **_split_state['result']})
            return (True, None)
        if tail == '/current':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['timeline_id'] = self.release_audio_timeline_store._resolve_timeline_id(release_id, None)
            _split_state['report'] = self.release_audio_timeline_store.read_timeline(release_id, _split_state['timeline_id'])
            signoff = _interfaces_api_runtime.read_json(self.release_audio_timeline_store.signoff_path(release_id, _split_state['timeline_id'])) if self.release_audio_timeline_store.signoff_path(release_id, _split_state['timeline_id']).exists() else {}
            self._send_json({'ok': True, 'release_id': release_id, 'timeline_id': _split_state['timeline_id'], 'report': _split_state['report'], 'signoff': signoff, 'summary': _split_state['report'].get('summary', {})})
            return (True, None)
        parts = [part for part in tail.split('/') if part]
        if not parts:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Audio Timeline route not found.')
            return (True, None)
        _split_state['timeline_id'] = parts[0]
        _split_state['action'] = parts[1] if len(parts) > 1 else ''
        if _split_state['action'] == '':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['report'] = self.release_audio_timeline_store.read_timeline(release_id, _split_state['timeline_id'])
            signoff = _interfaces_api_runtime.read_json(self.release_audio_timeline_store.signoff_path(release_id, _split_state['timeline_id'])) if self.release_audio_timeline_store.signoff_path(release_id, _split_state['timeline_id']).exists() else {}
            self._send_json({'ok': True, 'release_id': release_id, 'timeline_id': _split_state['timeline_id'], 'report': _split_state['report'], 'signoff': signoff, 'summary': _split_state['report'].get('summary', {})})
            return (True, None)
        if _split_state['action'] == 'events':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, **self.release_audio_timeline_store.read_events(release_id, _split_state['timeline_id'])})
            return (True, None)
        if _split_state['action'] == 'tracks':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, 'track_index': self.release_audio_timeline_store.read_track_index(release_id, _split_state['timeline_id'])})
            return (True, None)
        if _split_state['action'] == 'trend':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, 'quality_trend': self.release_audio_timeline_store.read_quality_trend(release_id, _split_state['timeline_id'])})
            return (True, None)
        if _split_state['action'] == 'risks':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_json({'ok': True, 'risk_register': self.release_audio_timeline_store.read_risk_register(release_id, _split_state['timeline_id'])})
            return (True, None)
        if _split_state['action'] == 'signoff':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.release_audio_timeline_store.signoff_timeline(release_id, _split_state['timeline_id'], self._read_json_body())
            self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        return (False, None)

    def _handle_release_audio_timeline_part_02(self, method: str, release_id: str, tail: str, _split_state):
        if _split_state['action'] == 'export':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.release_audio_timeline_store.export_timeline(release_id, _split_state['timeline_id'])
            self._send_json({'ok': _split_state['result'].get('status') == 'passed', **_split_state['result']})
            return (True, None)
        if _split_state['action'] == 'zip':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.release_audio_timeline_store.build_zip(release_id, _split_state['timeline_id'])
            self._send_json({'ok': _split_state['result'].get('status') == 'passed', **_split_state['result'], 'summary': {'zip_sha256': _split_state['result'].get('zip_sha256')}})
            return (True, None)
        if _split_state['action'] == 'verify':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['payload'] = self._optional_json_body()
            _split_state['report'] = self.release_audio_timeline_store.verify_zip(release_id, _split_state['timeline_id'], strict=bool(_split_state['payload'].get('strict', True)), require_passed=bool(_split_state['payload'].get('require_passed', True)), require_signed=bool(_split_state['payload'].get('require_signed', False)), require_real_audio=bool(_split_state['payload'].get('require_real_audio', True)), require_manual_review=bool(_split_state['payload'].get('require_manual_review', True)), require_current_certification=bool(_split_state['payload'].get('require_current_certification', True)))
            self._send_json({'ok': _split_state['report'].get('status') == 'passed', 'verification': _split_state['report'], 'summary': _split_state['report'].get('summary', {}), 'status': _split_state['report'].get('status')})
            return (True, None)
        if _split_state['action'] == 'download':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self._send_file(self.release_audio_timeline_store.zip_path(release_id, _split_state['timeline_id']), 'application/zip', filename='release-audio-timeline.zip')
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Release Audio Timeline route not found.')
        return (False, None)

    def _handle_release_audio_timeline(self, method: str, release_id: str, tail: str) -> None:
        _split_state: dict[str, _InferenceType] = {}
        try:
            _split_result = self._handle_release_audio_timeline_part_01(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_audio_timeline_part_02(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioTimelineNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioTimelineStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioTimelineValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioTimelineError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_regression(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_regression_store.read_report(release_id, default={})
                config = self.release_audio_regression_store.read_config(release_id, default={})
                signoff = _interfaces_api_runtime.read_json(self.release_audio_regression_store.signoff_path(release_id)) if self.release_audio_regression_store.signoff_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "config": config, "report": report, "signoff": signoff, "summary": report.get("summary", {}) if report else {}})
                return
            if tail == "/configure":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config = self.release_audio_regression_store.configure_baseline(release_id, self._read_json_body())
                self._send_json({"ok": True, "release_id": release_id, "config": config, "summary": {"baseline_release_id": (config.get("baseline") or {}).get("release_id")}}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_regression_store.refresh_report(release_id)
                self._send_json({"ok": report.get("status") == "passed", "release_id": release_id, "report": report, "summary": report.get("summary", {})})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_store.export_package(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_store.build_zip(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_regression_store.verify_zip(
                    release_id,
                    strict=bool(payload.get("strict", True)),
                    require_passed=bool(payload.get("require_passed", True)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_current=bool(payload.get("require_current", True)),
                    require_baseline_current=bool(payload.get("require_baseline_current", True)),
                    baseline_timeline_path=payload.get("baseline_timeline"),
                    baseline_timeline_verification_report_path=payload.get("baseline_timeline_verification_report"),
                    baseline_certification_path=payload.get("baseline_certification"),
                    baseline_certification_verification_report_path=payload.get("baseline_certification_verification_report"),
                    current_timeline_path=payload.get("current_timeline"),
                    current_timeline_verification_report_path=payload.get("current_timeline_verification_report"),
                    current_certification_path=payload.get("current_certification"),
                    current_certification_verification_report_path=payload.get("current_certification_verification_report"),
                )
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_regression_store.zip_path(release_id), "application/zip", filename="release-audio-regression.zip")
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Audio Regression route not found.")
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_regression_response(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.release_audio_regression_response_store.read_plan(release_id, default={})
                closeout = _interfaces_api_runtime.read_json(self.release_audio_regression_response_store.closeout_path(release_id)) if self.release_audio_regression_response_store.closeout_path(release_id).exists() else {}
                signoff = _interfaces_api_runtime.read_json(self.release_audio_regression_response_store.signoff_path(release_id)) if self.release_audio_regression_response_store.signoff_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "plan": plan, "closeout": closeout, "signoff": signoff, "summary": plan.get("summary", {}) if plan else {}})
                return
            if tail == "/create":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.release_audio_regression_response_store.create_plan(release_id, self._optional_json_body())
                self._send_json({"ok": True, "plan": plan, "summary": plan.get("summary", {})}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.run_safe_actions(release_id)
                self._send_json({"ok": True, **result})
                return
            if tail == "/waive":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                waivers = self.release_audio_regression_response_store.add_waiver(release_id, self._read_json_body())
                self._send_json({"ok": True, "waivers": waivers, "summary": {"waiver_count": len(waivers.get("waivers", []))}})
                return
            if tail == "/closeout":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.release_audio_regression_response_store.closeout(release_id, self._optional_json_body())
                self._send_json({"ok": True, "closeout": closeout, "summary": closeout})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.export_package(release_id)
                self._send_json({"ok": True, **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.build_zip(release_id)
                self._send_json({"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_regression_response_store.verify_zip(
                    release_id,
                    strict=bool(payload.get("strict", True)),
                    require_closed=bool(payload.get("require_closed", False)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_regression_current=bool(payload.get("require_regression_current", False)),
                    **self.release_audio_regression_response_store._response_verifier_kwargs(release_id),  # noqa: SLF001 - server resolves current release evidence.
                )
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_regression_response_store.zip_path(release_id), "application/zip", filename="release-audio-regression-response.zip")
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Release Audio Regression Response route not found.")
        except _interfaces_api_runtime.ReleaseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionResponseNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionResponseStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionResponseValidationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.ReleaseAudioRegressionResponseError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
