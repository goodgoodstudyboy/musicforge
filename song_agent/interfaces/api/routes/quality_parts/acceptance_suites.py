from __future__ import annotations

from song_agent.interfaces.bootstrap.api import creation_quality as _api_store_factories

from song_agent.application.http_ports import quality as quality_ports
from song_agent.platform.contracts.documents import JsonDocument

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


class QualityRoutesAcceptanceSuites(QualityRouteContext):
    @property
    def audio_campaign_remediation_store(self) -> quality_ports.AudioCampaignRemediationStore:
        store = self.server.audio_campaign_remediation_store
        store.release_store = self.release_store
        store.project_store = self.project_store
        store.planner_store = self.server.audio_campaign_planner_store
        store.campaign_store = self.server.audio_campaign_store
        store.fix_sprint_store = self.server.audio_campaign_store.audio_fix_sprint_store
        return store

    @property
    def release_audio_certification_store(self) -> quality_ports.ReleaseAudioCertificationStore:
        store = self.server.release_audio_certification_store
        store.release_store = self.release_store
        store.project_store = self.project_store
        store.planner_store = self.server.audio_campaign_planner_store
        store.campaign_store = self.server.audio_campaign_store
        store.governance_store = self.server.audio_campaign_governance_store
        store.remediation_store = self.audio_campaign_remediation_store
        return store

    @property
    def release_audio_timeline_store(self) -> quality_ports.ReleaseAudioTimelineStore:
        store = self.server.release_audio_timeline_store
        store.release_store = self.release_store
        store.project_store = self.project_store
        store.planner_store = self.server.audio_campaign_planner_store
        store.campaign_store = self.server.audio_campaign_store
        store.governance_store = self.server.audio_campaign_governance_store
        store.remediation_store = self.audio_campaign_remediation_store
        store.certification_store = self.release_audio_certification_store
        return store

    @property
    def release_audio_regression_store(self) -> quality_ports.ReleaseAudioRegressionStore:
        store = self.server.release_audio_regression_store
        store.release_store = self.release_store
        store.certification_store = self.release_audio_certification_store
        store.timeline_store = self.release_audio_timeline_store
        return store

    @property
    def release_audio_baseline_governance_store(self) -> quality_ports.ReleaseAudioBaselineGovernanceStore:
        store = self.server.release_audio_baseline_governance_store
        store.release_store = self.release_store
        return store

    @property
    def release_audio_regression_response_store(self) -> quality_ports.ReleaseAudioRegressionResponseStore:
        store = self.server.release_audio_regression_response_store
        store.release_store = self.release_store
        store.regression_store = self.release_audio_regression_store
        return store

    @property
    def release_audio_quality_observatory_store(self) -> quality_ports.ReleaseAudioQualityObservatoryStore:
        store = self.server.release_audio_quality_observatory_store
        store.release_store = self.release_store
        return store

    @property
    def release_audio_quality_action_queue_store(self) -> quality_ports.ReleaseAudioQualityActionQueueStore:
        store = self.server.release_audio_quality_action_queue_store
        store.release_store = self.release_store
        store.observatory_store = self.release_audio_quality_observatory_store
        return store

    @property
    def release_audio_quality_action_signoff_store(self) -> quality_ports.ReleaseAudioQualityActionQueueSignoffStore:
        store = self.server.release_audio_quality_action_signoff_store
        store.release_store = self.release_store
        store.queue_store = self.release_audio_quality_action_queue_store
        return store

    @property
    def release_audio_command_center_store(self) -> quality_ports.ReleaseAudioCommandCenterStore:
        store = self.server.release_audio_command_center_store
        store.release_store = self.release_store
        store.observatory_store = self.release_audio_quality_observatory_store
        store.action_queue_store = self.release_audio_quality_action_queue_store
        store.action_signoff_store = self.release_audio_quality_action_signoff_store
        return store

    def _handle_acceptance_suites_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = _interfaces_api_runtime.parse_qs(query_string)
            include_archived = query.get("include_archived", ["0"])[0] in {"1", "true", "yes"}
            suites = self.server.acceptance_store.list_suites(include_archived=include_archived)
            self._send_json({"ok": True, "suites": [suite.to_dict() for suite in suites], "summary": {"suite_count": len(suites)}})
            return
        if method == "POST":
            suite = self.server.acceptance_store.create_suite(self._optional_json_body())
            self._send_json({"ok": True, "suite": suite.to_dict(), "summary": _interfaces_api_runtime.acceptance_suite_summary(suite)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_release_audio_qa(self, method: str, release_id: str) -> None:
        if method == "GET":
            report = _interfaces_api_runtime.read_release_audio_qa(self.release_store, release_id, default={})
            self._send_json({"ok": True, "release_id": release_id, "audio_qa": report, "summary": _interfaces_api_runtime.release_audio_summary(report)})
            return
        if method == "POST":
            payload = self._optional_json_body()
            report = _interfaces_api_runtime.build_release_audio_qa_report(
                release=self.release_store.get_release(release_id),
                release_store=self.release_store,
                project_store=self.project_store,
                require_audio=bool(payload.get("require_audio", True)),
                now=_interfaces_api_runtime._utc_now(),
            )
            report = _interfaces_api_runtime.write_release_audio_qa(self.release_store, release_id, report)
            self.release_store.append_event(release_id, "release_audio_qa_refreshed", {"status": report.get("status")})
            self._send_json({"ok": True, "release_id": release_id, "audio_qa": report, "summary": _interfaces_api_runtime.release_audio_summary(report)})
            return
        self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_release_audio_reviews_part_01(self, method: str, release_id: str, tail: str, _split_state):
        if tail in {'', '/'}:
            if method == 'GET':
                reviews = self.server.audio_review_store.list_reviews(release_id)
                summary = self.server.audio_review_store.build_summary(release_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'reviews': reviews, 'summary': _interfaces_api_runtime.audio_review_summary_public(summary)})
                return (True, None)
            if method == 'POST':
                review = self.server.audio_review_store.create_review(release_id, self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                summary = self.server.audio_review_store.build_summary(release_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'review': review, 'summary': _interfaces_api_runtime.audio_review_summary_public(summary)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if tail == '/summary':
            if method != 'GET':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            summary = self.server.audio_review_store.build_summary(release_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'summary': _interfaces_api_runtime.audio_review_summary_public(summary), 'audio_review_summary': summary})
            return (True, None)
        if tail == '/refresh-summary':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            self.server.audio_review_store._ensure_release_mutable(release_id)
            summary = self.server.audio_review_store.write_summary(release_id, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'summary': _interfaces_api_runtime.audio_review_summary_public(summary), 'audio_review_summary': summary})
            return (True, None)
        if tail == '/import-human-review-pack':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.server.audio_review_store.import_human_review_pack(release_id, self._read_json_body(), acceptance_store=self.server.acceptance_store, now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, **_split_state['result']}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
            return (True, None)
        _split_state['parts'] = [part for part in tail.strip('/').split('/') if part]
        if not _split_state['parts']:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, 'Audio review route not found.')
            return (True, None)
        _split_state['review_id'] = _split_state['parts'][0]
        if len(_split_state['parts']) == 1:
            if method == 'GET':
                review = self.server.audio_review_store.read_review(release_id, _split_state['review_id'])
                self._send_json({'ok': True, 'release_id': release_id, 'review': review, 'summary': _interfaces_api_runtime.audio_review_summary_public(self.server.audio_review_store.build_summary(release_id, now=_interfaces_api_runtime._utc_now()))})
                return (True, None)
            if method == 'POST':
                review = self.server.audio_review_store.update_review(release_id, _split_state['review_id'], self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({'ok': True, 'release_id': release_id, 'review': review, 'summary': _interfaces_api_runtime.audio_review_summary_public(self.server.audio_review_store.build_summary(release_id, now=_interfaces_api_runtime._utc_now()))})
                return (True, None)
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'delete':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            _split_state['result'] = self.server.audio_review_store.delete_review(release_id, _split_state['review_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, **_split_state['result']})
            return (True, None)
        if len(_split_state['parts']) == 2 and _split_state['parts'][1] == 'refresh':
            if method != 'POST':
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, 'Method not allowed.')
                return (True, None)
            review = self.server.audio_review_store.refresh_review(release_id, _split_state['review_id'], now=_interfaces_api_runtime._utc_now())
            self._send_json({'ok': True, 'release_id': release_id, 'review': review, 'summary': _interfaces_api_runtime.audio_review_summary_public(self.server.audio_review_store.build_summary(release_id, now=_interfaces_api_runtime._utc_now()))})
            return (True, None)
        return (False, None)

    def _handle_release_audio_reviews_part_02(self, method: str, release_id: str, tail: str, _split_state):
        if len(_split_state["parts"]) == 4 and _split_state["parts"][1] == "markers" and (_split_state["parts"][3] == "create-review-task"):
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["result"] = self.server.audio_review_store.create_review_task_from_marker(
                release_id,
                _split_state["review_id"],
                _split_state["parts"][2],
                self._optional_json_body(),
                now=_interfaces_api_runtime._utc_now(),
            )
            status = (
                _interfaces_api_runtime.HTTPStatus.CREATED
                if _split_state["result"].get("status") == "created"
                else _interfaces_api_runtime.HTTPStatus.OK
            )
            self._send_json({"ok": True, "release_id": release_id, **_split_state["result"]}, status=status)
            return (True, None)
        if len(_split_state["parts"]) == 4 and _split_state["parts"][1] == "markers" and (_split_state["parts"][3] == "mix-patch-draft"):
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return (True, None)
            _split_state["result"] = _api_store_factories.mix_render_store(self.project_store, self.store).marker_mix_patch_draft(
                release_store=self.release_store,
                audio_review_store=self.server.audio_review_store,
                release_id=release_id,
                review_id=_split_state["review_id"],
                marker_id=_split_state["parts"][2],
                payload=self._optional_json_body(),
                now=_interfaces_api_runtime._utc_now(),
            )
            self._send_json(
                {"ok": True, "release_id": release_id, **_split_state["result"]}, status=_interfaces_api_runtime.HTTPStatus.CREATED
            )
            return (True, None)
        self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Audio review route not found.")
        return (False, None)

    def _handle_release_audio_reviews(self, method: str, release_id: str, tail: str) -> None:
        _split_state: dict[str, JsonDocument] = {}
        try:
            _split_result = self._handle_release_audio_reviews_part_01(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
            _split_result = self._handle_release_audio_reviews_part_02(method, release_id, tail, _split_state)
            if _split_result[0]:
                return _split_result[1]
        except _interfaces_api_runtime.AudioReviewEvidenceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AudioReviewEvidenceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.MixControlStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.MixControlError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except _interfaces_api_runtime.AudioReviewEvidenceError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
