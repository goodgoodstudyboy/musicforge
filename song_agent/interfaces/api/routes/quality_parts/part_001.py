from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class QualityRoutesPart001:
    @property
    def audio_campaign_planner_store(self) -> AudioCampaignPlannerStore:
        return self.server.audio_campaign_planner_store  # type: ignore[attr-defined]

    @property
    def audio_review_store(self) -> AudioReviewEvidenceStore:
        return self.server.audio_review_store  # type: ignore[attr-defined]

    @property
    def audio_revision_store(self) -> AudioRevisionStore:
        return self.server.audio_revision_store  # type: ignore[attr-defined]

    @property
    def audio_lab_store(self) -> AudioLabStore:
        return self.server.audio_lab_store  # type: ignore[attr-defined]

    @property
    def audio_fix_sprint_store(self) -> AudioFixSprintStore:
        return self.server.audio_fix_sprint_store  # type: ignore[attr-defined]

    @property
    def audio_campaign_store(self) -> AudioCampaignStore:
        return self.server.audio_campaign_store  # type: ignore[attr-defined]

    @property
    def audio_campaign_governance_store(self) -> AudioCampaignGovernanceStore:
        return self.server.audio_campaign_governance_store  # type: ignore[attr-defined]

    @property
    def audio_campaign_remediation_store(self) -> AudioCampaignRemediationStore:
        store = self.server.audio_campaign_remediation_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.project_store = self.project_store
        store.planner_store = self.audio_campaign_planner_store
        store.campaign_store = self.audio_campaign_store
        store.fix_sprint_store = self.audio_campaign_store.audio_fix_sprint_store
        return store

    @property
    def release_audio_certification_store(self) -> ReleaseAudioCertificationStore:
        store = self.server.release_audio_certification_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.project_store = self.project_store
        store.planner_store = self.audio_campaign_planner_store
        store.campaign_store = self.audio_campaign_store
        store.governance_store = self.audio_campaign_governance_store
        store.remediation_store = self.audio_campaign_remediation_store
        return store

    @property
    def release_audio_timeline_store(self) -> ReleaseAudioTimelineStore:
        store = self.server.release_audio_timeline_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.project_store = self.project_store
        store.planner_store = self.audio_campaign_planner_store
        store.campaign_store = self.audio_campaign_store
        store.governance_store = self.audio_campaign_governance_store
        store.remediation_store = self.audio_campaign_remediation_store
        store.certification_store = self.release_audio_certification_store
        return store

    @property
    def release_audio_regression_store(self) -> ReleaseAudioRegressionStore:
        store = self.server.release_audio_regression_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.certification_store = self.release_audio_certification_store
        store.timeline_store = self.release_audio_timeline_store
        return store

    @property
    def release_audio_baseline_governance_store(self) -> ReleaseAudioBaselineGovernanceStore:
        store = self.server.release_audio_baseline_governance_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        return store

    @property
    def release_audio_regression_response_store(self) -> ReleaseAudioRegressionResponseStore:
        store = self.server.release_audio_regression_response_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.regression_store = self.release_audio_regression_store
        return store

    @property
    def release_audio_quality_observatory_store(self) -> ReleaseAudioQualityObservatoryStore:
        store = self.server.release_audio_quality_observatory_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        return store

    @property
    def release_audio_quality_action_queue_store(self) -> ReleaseAudioQualityActionQueueStore:
        store = self.server.release_audio_quality_action_queue_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.observatory_store = self.release_audio_quality_observatory_store
        return store

    @property
    def release_audio_quality_action_signoff_store(self) -> ReleaseAudioQualityActionQueueSignoffStore:
        store = self.server.release_audio_quality_action_signoff_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.queue_store = self.release_audio_quality_action_queue_store
        return store

    @property
    def release_audio_command_center_store(self) -> ReleaseAudioCommandCenterStore:
        store = self.server.release_audio_command_center_store  # type: ignore[attr-defined]
        store.release_store = self.release_store
        store.observatory_store = self.release_audio_quality_observatory_store
        store.action_queue_store = self.release_audio_quality_action_queue_store
        store.action_signoff_store = self.release_audio_quality_action_signoff_store
        return store

    @property
    def acceptance_store(self) -> AcceptanceStore:
        return self.server.acceptance_store  # type: ignore[attr-defined]

    @property
    def acceptance_analytics_store(self) -> AcceptanceAnalyticsStore:
        return self.server.acceptance_analytics_store  # type: ignore[attr-defined]

    @property
    def acceptance_fix_sprint_store(self) -> AcceptanceFixSprintStore:
        return self.server.acceptance_fix_sprint_store  # type: ignore[attr-defined]

    @property
    def acceptance_fix_plan_store(self) -> AcceptanceFixPlanningStore:
        return self.server.acceptance_fix_plan_store  # type: ignore[attr-defined]

    @property
    def acceptance_fix_plan_review_store(self) -> AcceptanceFixPlanReviewStore:
        return self.server.acceptance_fix_plan_review_store  # type: ignore[attr-defined]

    @property
    def acceptance_kb_store(self) -> AcceptanceKnowledgeBaseStore:
        return self.server.acceptance_kb_store  # type: ignore[attr-defined]

    @property
    def planning_rule_simulation_store(self) -> PlanningRuleSimulationStore:
        return self.server.planning_rule_simulation_store  # type: ignore[attr-defined]

    @property
    def planning_rule_governance_store(self) -> PlanningRuleGovernanceStore:
        return self.server.planning_rule_governance_store  # type: ignore[attr-defined]

    @property
    def planning_rule_impact_store(self) -> PlanningRuleImpactStore:
        return self.server.planning_rule_impact_store  # type: ignore[attr-defined]

    @property
    def audio_profile_store(self) -> AudioProfileStore:
        return self.server.audio_profile_store  # type: ignore[attr-defined]

    @property
    def mastering_profile_store(self) -> MasteringProfileStore:
        return self.server.mastering_profile_store  # type: ignore[attr-defined]

    @property
    def mastering_store(self) -> MasteringStore:
        return self.server.mastering_store  # type: ignore[attr-defined]

    @property
    def audio_encoding_profile_store(self) -> AudioEncodingProfileStore:
        return self.server.audio_encoding_profile_store  # type: ignore[attr-defined]

    @property
    def audio_encoding_store(self) -> AudioEncodingStore:
        return self.server.audio_encoding_store  # type: ignore[attr-defined]

    @property
    def encoded_audio_acceptance_store(self) -> EncodedAudioAcceptanceStore:
        return self.server.encoded_audio_acceptance_store  # type: ignore[attr-defined]

    @property
    def format_decision_store(self) -> FormatDecisionStore:
        return self.server.format_decision_store  # type: ignore[attr-defined]

    @property
    def rights_clearance_store(self) -> RightsClearanceStore:
        return self.server.rights_clearance_store  # type: ignore[attr-defined]

    def _handle_acceptance_suites_root(self, method: str, query_string: str) -> None:
        if method == "GET":
            query = parse_qs(query_string)
            include_archived = query.get("include_archived", ["0"])[0] in {"1", "true", "yes"}
            suites = self.acceptance_store.list_suites(include_archived=include_archived)
            self._send_json({"ok": True, "suites": [suite.to_dict() for suite in suites], "summary": {"suite_count": len(suites)}})
            return
        if method == "POST":
            suite = self.acceptance_store.create_suite(self._optional_json_body())
            self._send_json({"ok": True, "suite": suite.to_dict(), "summary": acceptance_suite_summary(suite)}, status=HTTPStatus.CREATED)
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_release_audio_qa(self, method: str, release_id: str) -> None:
        if method == "GET":
            report = read_release_audio_qa(self.release_store, release_id, default={})
            self._send_json({"ok": True, "release_id": release_id, "audio_qa": report, "summary": release_audio_summary(report)})
            return
        if method == "POST":
            payload = self._optional_json_body()
            report = build_release_audio_qa_report(
                release=self.release_store.get_release(release_id),
                release_store=self.release_store,
                project_store=self.project_store,
                require_audio=bool(payload.get("require_audio", True)),
                now=_utc_now(),
            )
            report = write_release_audio_qa(self.release_store, release_id, report)
            self.release_store.append_event(release_id, "release_audio_qa_refreshed", {"status": report.get("status")})
            self._send_json({"ok": True, "release_id": release_id, "audio_qa": report, "summary": release_audio_summary(report)})
            return
        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

    def _handle_release_audio_reviews(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    reviews = self.audio_review_store.list_reviews(release_id)
                    summary = self.audio_review_store.build_summary(release_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "reviews": reviews, "summary": audio_review_summary_public(summary)})
                    return
                if method == "POST":
                    review = self.audio_review_store.create_review(release_id, self._read_json_body(), now=_utc_now())
                    summary = self.audio_review_store.build_summary(release_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "review": review, "summary": audio_review_summary_public(summary)}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/summary":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                summary = self.audio_review_store.build_summary(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "summary": audio_review_summary_public(summary), "audio_review_summary": summary})
                return
            if tail == "/refresh-summary":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self.audio_review_store._ensure_release_mutable(release_id)
                summary = self.audio_review_store.write_summary(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "summary": audio_review_summary_public(summary), "audio_review_summary": summary})
                return
            if tail == "/import-human-review-pack":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_review_store.import_human_review_pack(release_id, self._read_json_body(), acceptance_store=self.acceptance_store, now=_utc_now())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Audio review route not found.")
                return
            review_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    review = self.audio_review_store.read_review(release_id, review_id)
                    self._send_json({"ok": True, "release_id": release_id, "review": review, "summary": audio_review_summary_public(self.audio_review_store.build_summary(release_id, now=_utc_now()))})
                    return
                if method == "POST":
                    review = self.audio_review_store.update_review(release_id, review_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "review": review, "summary": audio_review_summary_public(self.audio_review_store.build_summary(release_id, now=_utc_now()))})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[1] == "delete":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_review_store.delete_review(release_id, review_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, **result})
                return
            if len(parts) == 2 and parts[1] == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.audio_review_store.refresh_review(release_id, review_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "review": review, "summary": audio_review_summary_public(self.audio_review_store.build_summary(release_id, now=_utc_now()))})
                return
            if len(parts) == 4 and parts[1] == "markers" and parts[3] == "create-review-task":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_review_store.create_review_task_from_marker(release_id, review_id, parts[2], self._optional_json_body(), now=_utc_now())
                status = HTTPStatus.CREATED if result.get("status") == "created" else HTTPStatus.OK
                self._send_json({"ok": True, "release_id": release_id, **result}, status=status)
                return
            if len(parts) == 4 and parts[1] == "markers" and parts[3] == "mix-patch-draft":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = MixRenderStore(self.project_store, self.store).marker_mix_patch_draft(
                    release_store=self.release_store,
                    audio_review_store=self.audio_review_store,
                    release_id=release_id,
                    review_id=review_id,
                    marker_id=parts[2],
                    payload=self._optional_json_body(),
                    now=_utc_now(),
                )
                self._send_json({"ok": True, "release_id": release_id, **result}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio review route not found.")
        except AudioReviewEvidenceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioReviewEvidenceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except MixControlStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except MixControlError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AudioReviewEvidenceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
