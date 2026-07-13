from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document
from song_agent.interfaces.api.runtime import *

class QualityRoutes:
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

    def _handle_release_audio_revisions(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    sessions = self.audio_revision_store.list_sessions(release_id)
                    summary = self.audio_revision_store.gate(release_id, required=False, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "sessions": sessions, "summary": summary})
                    return
                if method == "POST":
                    session = self.audio_revision_store.create_session(release_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "session": session, "summary": self.audio_revision_store.gate(release_id, required=False, now=_utc_now())}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if tail == "/summary":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                summary = self.audio_revision_store.gate(release_id, required=False, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "summary": summary})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Audio revision route not found.")
                return
            session_id = parts[0]
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                session = self.audio_revision_store.read_session(release_id, session_id)
                issues = self.audio_revision_store.list_issues(release_id, session_id)
                candidates = self.audio_revision_store.list_candidates(release_id, session_id)
                closeout = self.audio_revision_store.read_closeout(release_id, session_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "session": session, "issues": issues, "candidates": candidates, "closeout": closeout})
                return
            if len(parts) == 2 and parts[1] == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_revision_store.refresh_recheck_status(release_id, session_id, now=_utc_now())
                self._send_json({"ok": True, **result})
                return
            if len(parts) == 2 and parts[1] == "close":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_revision_store.close_session(release_id, session_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result})
                return
            if len(parts) == 2 and parts[1] == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                session = self.audio_revision_store.archive_session(release_id, session_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "session": session})
                return
            if len(parts) >= 2 and parts[1] == "issues":
                if len(parts) == 2:
                    if method == "GET":
                        self._send_json({"ok": True, "release_id": release_id, "session_id": session_id, "issues": self.audio_revision_store.list_issues(release_id, session_id)})
                        return
                    if method == "POST":
                        issue = self.audio_revision_store.create_issue(release_id, session_id, self._read_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "issue": issue}, status=HTTPStatus.CREATED)
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                issue_id = parts[2]
                if len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    issue = self.audio_revision_store.read_issue(release_id, session_id, issue_id)
                    self._send_json({"ok": True, "release_id": release_id, "issue": issue})
                    return
                if len(parts) == 4 and parts[3] in {"waive", "reopen"}:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if parts[3] == "waive":
                        issue = self.audio_revision_store.waive_issue(release_id, session_id, issue_id, self._optional_json_body(), now=_utc_now())
                    else:
                        issue = self.audio_revision_store.reopen_issue(release_id, session_id, issue_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "issue": issue})
                    return
                if len(parts) == 5 and parts[3] == "candidates" and parts[4] == "generate":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_revision_store.generate_candidates(release_id, session_id, issue_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                    return
            if len(parts) >= 2 and parts[1] == "candidates":
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_json({"ok": True, "release_id": release_id, "session_id": session_id, "candidates": self.audio_revision_store.list_candidates(release_id, session_id)})
                    return
                candidate_id = parts[2]
                if len(parts) == 3:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    candidate = self.audio_revision_store.read_candidate(release_id, session_id, candidate_id)
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                    return
                if len(parts) == 4 and parts[3] in {"midi", "audio"}:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    path, media_type, filename = self.audio_revision_store.download_candidate_artifact(release_id, session_id, candidate_id, "midi" if parts[3] == "midi" else "audio")
                    self._send_file(path, media_type, filename=filename)
                    return
                if len(parts) == 4 and parts[3] in {"review", "select", "apply"}:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if parts[3] == "review":
                        candidate = self.audio_revision_store.review_candidate(release_id, session_id, candidate_id, self._read_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                        return
                    if parts[3] == "select":
                        candidate = self.audio_revision_store.select_candidate(release_id, session_id, candidate_id, now=_utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                        return
                    result = self.audio_revision_store.apply_candidate(release_id, session_id, candidate_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, **result})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio revision route not found.")
        except AudioRevisionNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioRevisionStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioRevisionError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (MixControlStateError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (MixControlError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_mastering(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json(
                    {
                        "ok": True,
                        "release_id": release_id,
                        "summary": self.mastering_store.get_summary(release_id, now=_utc_now()),
                        "analysis": self.mastering_store.read_analysis(release_id, default={}),
                        "plan": self.mastering_store.read_plan(release_id, default={}),
                        "candidates": self.mastering_store.list_candidates(release_id),
                        "selected_candidate": self.mastering_store.read_selected_candidate(release_id, default={}),
                    }
                )
                return
            if tail == "/analyze":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                analysis = self.mastering_store.analyze(release_id, self._optional_json_body(), now=_utc_now())
                self.release_store.append_event(release_id, "release_mastering_analyzed", {"status": analysis.get("status"), "profile_id": analysis.get("profile_id")})
                self._send_json({"ok": True, "release_id": release_id, "analysis": analysis, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                return
            if tail == "/plan":
                if method == "GET":
                    plan = self.mastering_store.read_plan(release_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "plan": plan, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.mastering_store.build_plan(release_id, self._optional_json_body(), now=_utc_now())
                self.release_store.append_event(release_id, "release_mastering_plan_created", {"action_count": plan.get("summary", {}).get("action_count")})
                self._send_json({"ok": True, "release_id": release_id, "plan": plan, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                return
            if tail == "/candidates":
                if method == "GET":
                    self._send_json({"ok": True, "release_id": release_id, "candidates": self.mastering_store.list_candidates(release_id), "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                candidate = self.mastering_store.render_candidate(release_id, self._optional_json_body(), now=_utc_now())
                self.release_store.append_event(release_id, "release_mastering_candidate_rendered", {"candidate_id": candidate.get("candidate_id"), "status": candidate.get("status")})
                self._send_json({"ok": True, "release_id": release_id, "candidate": candidate, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())}, status=HTTPStatus.CREATED)
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.mastering_store.refresh(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, **result})
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.mastering_store.reset(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if len(parts) >= 2 and parts[0] == "candidates":
                candidate_id = parts[1]
                if len(parts) == 2:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    candidate = self.mastering_store.read_candidate(release_id, candidate_id)
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate})
                    return
                if len(parts) == 5 and parts[2] == "tracks" and parts[4] == "audio":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    path = self.mastering_store.candidate_audio_path(release_id, candidate_id, parts[3])
                    self._send_file(path, "audio/wav", filename=f"{parts[3]}-mastered.wav")
                    return
                if len(parts) == 3 and parts[2] in {"review", "select"}:
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    if parts[2] == "review":
                        candidate = self.mastering_store.review_candidate(release_id, candidate_id, self._read_json_body(), now=_utc_now())
                    else:
                        candidate = self.mastering_store.select_candidate(release_id, candidate_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "candidate": candidate, "summary": self.mastering_store.get_summary(release_id, now=_utc_now())})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Mastering route not found.")
        except MasteringNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (MasteringStateError, ReleaseStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (MasteringQAError, MasteringProfileError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_encoded_audio(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "release_id": release_id, "summary": self.audio_encoding_store.get_summary(release_id, now=_utc_now()), "formats": self.audio_encoding_store.list_manifests(release_id)})
                return
            if tail == "/render":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_encoding_store.render(release_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/render-format":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                profile_id = str(payload.get("profile_id") or "").strip()
                if not profile_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "profile_id is required.")
                    return
                manifest = self.audio_encoding_store.render_format(release_id, profile_id, payload, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest, "summary": self.audio_encoding_store.get_summary(release_id, now=_utc_now())}, status=HTTPStatus.CREATED)
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_encoding_store.verify(release_id, self._optional_json_body())
                self._send_json({"ok": True, **result})
                return
            if tail == "/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_encoding_store.reset(release_id, self._optional_json_body())
                self._send_json({"ok": True, **result})
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if len(parts) == 1 and parts[0] == "health":
                if method == "GET":
                    self._send_json({"ok": True, "release_id": release_id, "health": self.encoded_audio_acceptance_store.list_health(release_id)})
                    return
                if method == "POST":
                    payload = self._optional_json_body()
                    result = self.encoded_audio_acceptance_store.refresh_health(release_id, normalize_required_profiles(payload.get("profile_ids") or payload.get("profiles") or payload.get("required_audio_format_profiles") or []), now=_utc_now())
                    self._send_json({"ok": True, **result})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[0] == "health" and method == "GET":
                report = self.encoded_audio_acceptance_store.read_health(release_id, parts[1])
                self._send_json({"ok": True, "release_id": release_id, "profile_id": parts[1], "health": report})
                return
            if len(parts) == 1 and parts[0] == "reviews":
                if method == "GET":
                    reviews = self.encoded_audio_acceptance_store.list_reviews(release_id)
                    self._send_json({"ok": True, "release_id": release_id, "reviews": reviews})
                    return
                if method == "POST":
                    review = self.encoded_audio_acceptance_store.create_review(release_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "review": review}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[0] == "reviews":
                review_id = parts[1]
                if method == "GET":
                    review = self.encoded_audio_acceptance_store.read_review(release_id, review_id)
                    self._send_json({"ok": True, "release_id": release_id, "review": review})
                    return
                if method in {"POST", "PATCH"}:
                    review = self.encoded_audio_acceptance_store.update_review(release_id, review_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "review": review})
                    return
                if method == "DELETE":
                    result = self.encoded_audio_acceptance_store.delete_review(release_id, review_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, **result})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 1 and parts[0] == "acceptance":
                if method == "GET":
                    payload_profiles = []
                    summary = self.encoded_audio_acceptance_store.build_summary(release_id, required_profiles=payload_profiles, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "summary": summary})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[0] == "acceptance" and parts[1] == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                summary = self.encoded_audio_acceptance_store.write_summary(release_id, required_profiles=normalize_required_profiles(payload.get("profile_ids") or payload.get("profiles") or payload.get("required_audio_format_profiles") or []), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "summary": summary})
                return
            if len(parts) == 2 and parts[0] == "formats" and method == "GET":
                manifest = self.audio_encoding_store.read_manifest(release_id, parts[1])
                self._send_json({"ok": True, "release_id": release_id, "manifest": manifest})
                return
            if len(parts) == 5 and parts[0] == "formats" and parts[2] == "tracks" and parts[4] == "audio" and method == "GET":
                manifest = self.audio_encoding_store.read_manifest(release_id, parts[1])
                track = next((row for row in manifest.get("tracks", []) if isinstance(row, dict) and row.get("track_id") == parts[3]), None)
                if not track:
                    self._send_error(HTTPStatus.NOT_FOUND, "Encoded track audio not found.")
                    return
                path = self.audio_encoding_store.track_audio_path(release_id, parts[1], parts[3])
                self._send_file(path, "application/octet-stream", filename=path.name)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Encoded audio route not found.")
        except (ReleaseNotFoundError, AudioEncodingNotFoundError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (EncodedAudioAcceptanceNotFoundError,) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (ReleaseStateError, AudioEncodingStateError, EncodedAudioAcceptanceStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (AudioEncodingError, AudioEncodingProfileError, EncodedAudioAcceptanceError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_profiles_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio/profiles":
                if method == "GET":
                    profiles = [profile.public_summary() for profile in self.audio_profile_store.list_profiles(include_hidden=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.audio_profile_store.upsert_profile(self._read_json_body())
                    self._send_json({"ok": True, "profile": profile.public_summary()}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Audio profile route not found.")
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
            self._send_error(HTTPStatus.NOT_FOUND, "Audio profile route not found.")
        except AudioProfileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioProfileError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_lab_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-lab" or path == "/api/audio-lab/environment":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "environment": self.audio_lab_store.environment_status()})
                return
            if path == "/api/audio-lab/environment/detect":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "environment": self.audio_lab_store.detect_environment()})
                return
            if path == "/api/audio-lab/environment/test-profile":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = self.audio_lab_store.test_profile(str(payload.get("profile_id") or payload.get("profile") or "default"))
                self._send_json({"ok": result.get("status") != "failed", "profile_test": result})
                return
            if path == "/api/audio-lab/environment/report":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.audio_lab_store.setup_report()
                self._send_json({"ok": True, "report": report, "summary": report.get("summary", {})})
                return
            if path == "/api/audio-lab/smoke-runs":
                if method == "GET":
                    runs = self.audio_lab_store.list_smoke_runs()
                    self._send_json({"ok": True, "smoke_runs": runs, "summary": {"smoke_run_count": len(runs)}})
                    return
                if method == "POST":
                    report = self.audio_lab_store.run_smoke(self._optional_json_body())
                    self._send_json({"ok": report.get("status") != "failed", "smoke_run": report, "summary": report.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path.startswith("/api/audio-lab/smoke-runs/"):
                parts = path.removeprefix("/api/audio-lab/smoke-runs/").strip("/").split("/")
                smoke_id = parts[0]
                if len(parts) == 1 or parts[1] == "report":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_lab_store.read_smoke_report(smoke_id)
                    self._send_json({"ok": True, "smoke_run": report, "summary": report.get("summary", {})})
                    return
            if path == "/api/audio-lab/listening-sessions":
                if method == "GET":
                    sessions = self.audio_lab_store.list_sessions()
                    self._send_json({"ok": True, "sessions": sessions, "summary": {"session_count": len(sessions)}})
                    return
                if method == "POST":
                    session = self.audio_lab_store.create_session(self._read_json_body())
                    self._send_json({"ok": True, "session": session, "summary": session.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path.startswith("/api/audio-lab/listening-sessions/"):
                parts = path.removeprefix("/api/audio-lab/listening-sessions/").strip("/").split("/")
                session_id = parts[0]
                if len(parts) == 1:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    session = self.audio_lab_store.read_session(session_id)
                    self._send_json({"ok": True, "session": session, "summary": session.get("summary", {})})
                    return
                if len(parts) == 2 and parts[1] == "report":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_lab_store.session_report(session_id)
                    self._send_json({"ok": report.get("status") != "failed", "report": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 2 and parts[1] == "close":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_lab_store.close_session(session_id, self._optional_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 4 and parts[1] == "items" and parts[3] == "review":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_lab_store.write_item_review(session_id, parts[2], self._read_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 4 and parts[1] == "items" and parts[3] == "markers":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_lab_store.add_marker(session_id, parts[2], self._read_json_body())
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                    return
                if len(parts) == 4 and parts[1] == "markers":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    action = parts[3]
                    draft_type = {"create-review-task": "review_task", "create-audio-revision-draft": "audio_revision", "create-mix-patch-draft": "mix_patch"}.get(action)
                    if draft_type:
                        result = self.audio_lab_store.create_marker_draft(session_id, parts[2], draft_type, self._optional_json_body())
                        self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                        return
            if path == "/api/audio-lab/comparisons":
                if method == "GET":
                    comparisons = self.audio_lab_store.list_comparisons()
                    self._send_json({"ok": True, "comparisons": comparisons, "summary": {"comparison_count": len(comparisons)}})
                    return
                if method == "POST":
                    comparison = self.audio_lab_store.create_comparison(self._read_json_body())
                    self._send_json({"ok": True, "comparison": comparison}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path.startswith("/api/audio-lab/comparisons/"):
                parts = path.removeprefix("/api/audio-lab/comparisons/").strip("/").split("/")
                comparison_id = parts[0]
                if len(parts) == 1:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_json({"ok": True, "comparison": self.audio_lab_store.read_comparison(comparison_id)})
                    return
                if len(parts) == 2 and parts[1] == "review":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    comparison = self.audio_lab_store.review_comparison(comparison_id, self._read_json_body())
                    self._send_json({"ok": True, "comparison": comparison})
                    return
                if len(parts) == 2 and parts[1] == "report":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_lab_store.comparison_report(comparison_id)
                    self._send_json({"ok": report.get("status") != "failed", "report": report})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio Lab route not found.")
        except AudioLabNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioLabStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioLabValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AudioLabError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_fix_sprint_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-fix-sprints":
                if method == "GET":
                    sprints = self.audio_fix_sprint_store.list_sprints()
                    self._send_json({"ok": True, "sprints": sprints, "summary": {"sprint_count": len(sprints)}})
                    return
                if method == "POST":
                    sprint = self.audio_fix_sprint_store.create_sprint(self._read_json_body())
                    self._send_json({"ok": True, "sprint": sprint, "summary": sprint.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path.startswith("/api/audio-fix-sprints/"):
                parts = path.removeprefix("/api/audio-fix-sprints/").strip("/").split("/")
                sprint_id = parts[0]
                if len(parts) == 1:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    sprint = self.audio_fix_sprint_store.read_sprint(sprint_id)
                    self._send_json({"ok": True, "sprint": sprint, "summary": sprint.get("summary", {})})
                    return
                action = parts[1]
                if len(parts) == 2 and action == "refresh":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    sprint = self.audio_fix_sprint_store.refresh_sprint(sprint_id)
                    self._send_json({"ok": True, "sprint": sprint, "summary": sprint.get("summary", {})})
                    return
                if len(parts) == 2 and action == "drafts":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.create_drafts(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "candidates":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.generate_candidates(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "recheck-session":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.create_recheck_session(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "closeout":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_fix_sprint_store.closeout_report(sprint_id)
                    self._send_json({"ok": report.get("status") == "passed", "closeout": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 2 and action == "close":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.close_sprint(sprint_id, self._optional_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 6 and parts[1] == "items" and parts[3] == "candidates" and parts[5] == "review":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.review_candidate(sprint_id, parts[2], parts[4], self._read_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 6 and parts[1] == "items" and parts[3] == "candidates" and parts[5] == "select":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.select_candidate(sprint_id, parts[2], parts[4], self._optional_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 4 and parts[1] == "recheck-items" and parts[3] == "review":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_fix_sprint_store.review_recheck_item(sprint_id, parts[2], self._read_json_body())
                    self._send_json({"ok": True, **result})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio Fix Sprint route not found.")
        except AudioFixSprintNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioFixSprintStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioFixSprintValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AudioFixSprintError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_campaign_route(self, method: str, path: str) -> None:
        try:
            self.audio_campaign_governance_store.campaign_store = self.audio_campaign_store
            self.audio_campaign_governance_store.analytics_store.campaign_store = self.audio_campaign_store
            if path == "/api/audio-campaigns":
                if method == "GET":
                    campaigns = self.audio_campaign_store.list_campaigns()
                    self._send_json({"ok": True, "campaigns": campaigns, "summary": {"campaign_count": len(campaigns)}})
                    return
                if method == "POST":
                    campaign = self.audio_campaign_store.create_campaign(self._read_json_body())
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path.startswith("/api/audio-campaigns/"):
                parts = path.removeprefix("/api/audio-campaigns/").strip("/").split("/")
                campaign_id = parts[0]
                if len(parts) == 1:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    campaign = self.audio_campaign_store.read_campaign(campaign_id)
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})})
                    return
                action = parts[1]
                if len(parts) == 2 and action == "refresh":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    campaign = self.audio_campaign_store.refresh_campaign(campaign_id)
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})})
                    return
                if len(parts) == 2 and action == "link-listening-session":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._read_json_body()
                    session_id = str(payload.get("session_id") or payload.get("from_session") or "")
                    campaign = self.audio_campaign_store.link_listening_session(campaign_id, session_id)
                    self._send_json({"ok": True, "campaign": campaign, "summary": campaign.get("summary", {})})
                    return
                if len(parts) == 2 and action == "fix-sprints":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.create_fix_sprints(campaign_id, self._optional_json_body())
                    self._send_json({"ok": result.get("status") == "passed", **result}, status=HTTPStatus.CREATED)
                    return
                if len(parts) == 2 and action == "report":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_campaign_store.refresh_report(campaign_id)
                    self._send_json({"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 2 and action == "signoff":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.signoff(campaign_id, self._read_json_body())
                    self._send_json({"ok": True, **result})
                    return
                if len(parts) == 2 and action == "export":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.export_campaign(campaign_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if len(parts) == 2 and action == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_store.build_zip(campaign_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if len(parts) == 2 and action == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = self.audio_campaign_store.verify_zip(
                        campaign_id,
                        strict=bool(payload.get("strict")),
                        require_real_audio=bool(payload.get("require_real_audio")),
                        require_manual_review=bool(payload.get("require_manual_review")),
                        require_fix_sprints_closed=bool(payload.get("require_fix_sprints_closed")),
                        require_signed=bool(payload.get("require_signed")),
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 2 and action == "governance":
                    if method == "GET":
                        report = self.audio_campaign_governance_store.read_governance_report(campaign_id, default={})
                        self._send_json({"ok": True, "governance": report, "summary": report.get("summary", {}) if isinstance(report, dict) else {}})
                        return
                    if method == "POST":
                        report = self.audio_campaign_governance_store.refresh_governance_report(campaign_id)
                        self._send_json({"ok": report.get("status") == "signed", "governance": report, "summary": report.get("summary", {})})
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if len(parts) == 2 and action == "analytics":
                    if method == "GET":
                        analytics = self.audio_campaign_governance_store.analytics_store.read(campaign_id, default={})
                        self._send_json({"ok": True, "analytics": analytics, "summary": analytics.get("summary", {}) if isinstance(analytics, dict) else {}})
                        return
                    if method == "POST":
                        analytics = self.audio_campaign_governance_store.refresh_analytics(campaign_id)
                        self._send_json({"ok": True, "analytics": analytics, "summary": analytics.get("summary", {})})
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if len(parts) == 2 and action == "archive":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    manifest = self.audio_campaign_governance_store.export_archive(campaign_id)
                    self._send_json({"ok": True, "manifest": manifest, "summary": manifest.get("summary", {})})
                    return
                if len(parts) == 3 and parts[1] == "archive" and parts[2] == "zip":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.audio_campaign_governance_store.build_archive_zip(campaign_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if len(parts) == 3 and parts[1] == "archive" and parts[2] == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    report = self.audio_campaign_governance_store.verify_archive(campaign_id, self._optional_json_body())
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {})})
                    return
                if len(parts) == 3 and parts[1] == "archive" and parts[2] == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.audio_campaign_governance_store.archive_zip_path(campaign_id), "application/zip", filename="audio-campaign-archive.zip")
                    return
                if len(parts) == 2 and action == "change-requests":
                    if method == "GET":
                        rows = self.audio_campaign_governance_store.list_change_requests(campaign_id)
                        self._send_json({"ok": True, "change_requests": rows, "summary": {"count": len(rows)}})
                        return
                    if method == "POST":
                        cr = self.audio_campaign_governance_store.create_change_request(campaign_id, self._read_json_body())
                        self._send_json({"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}}, status=HTTPStatus.CREATED)
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if len(parts) == 4 and parts[1] == "change-requests" and parts[3] == "approve":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    cr = self.audio_campaign_governance_store.approve_change_request(campaign_id, parts[2], self._optional_json_body())
                    self._send_json({"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}})
                    return
                if len(parts) == 3 and parts[1] == "signoff" and parts[2] == "reset":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._read_json_body()
                    result = self.audio_campaign_governance_store.reset_signoff(campaign_id, str(payload.get("change_request_id") or ""), payload)
                    self._send_json({"ok": True, **result})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio Campaign route not found.")
        except AudioCampaignNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioCampaignGovernanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioCampaignStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioCampaignGovernanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioCampaignValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AudioCampaignError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AudioCampaignGovernanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_campaign_plan(self, method: str, release_id: str, tail: str) -> None:
        try:
            self.audio_campaign_planner_store.release_store = self.release_store
            self.audio_campaign_planner_store.project_store = self.project_store
            self.audio_campaign_planner_store.audio_lab_store = self.audio_lab_store
            self.audio_campaign_planner_store.audio_campaign_store = self.audio_campaign_store
            if tail == "":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                status = self.audio_campaign_planner_store.status(release_id)
                self._send_json({"ok": True, **status})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.audio_campaign_planner_store.refresh_plan(release_id, self._optional_json_body())
                self._send_json({"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("preflight_summary", {})})
                return
            if tail == "/preflight":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                preflight = self.audio_campaign_planner_store.preflight(release_id, self._optional_json_body())
                self._send_json({"ok": preflight.get("status") == "passed", "preflight": preflight, "summary": preflight.get("summary", {})})
                return
            if tail == "/create":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_planner_store.create_campaign_from_release(release_id, self._optional_json_body())
                self._send_json({"ok": True, **result, "summary": result.get("link", {}).get("coverage", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/status":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                status = self.audio_campaign_planner_store.status(release_id)
                self._send_json({"ok": status.get("status") != "failed", **status})
                return
            if tail == "/link":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                link = self.audio_campaign_planner_store.link_campaign(release_id, str(payload.get("campaign_id") or ""), payload)
                self._send_json({"ok": True, "link": link, "summary": link.get("coverage", {})}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Campaign plan route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioCampaignPlannerNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioCampaignPlannerStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioCampaignPlannerValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AudioCampaignPlannerError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_campaign_remediation(self, method: str, release_id: str, tail: str) -> None:
        try:
            self.audio_campaign_remediation_store.release_store = self.release_store
            self.audio_campaign_remediation_store.project_store = self.project_store
            self.audio_campaign_remediation_store.planner_store = self.audio_campaign_planner_store
            self.audio_campaign_remediation_store.campaign_store = self.audio_campaign_store
            self.audio_campaign_remediation_store.fix_sprint_store = self.audio_fix_sprint_store
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.audio_campaign_remediation_store.read_plan(release_id, default={})
                queue = self.audio_campaign_remediation_store.read_queue(release_id, default={})
                closeout = self.audio_campaign_remediation_store.read_closeout(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "plan": plan, "queue": queue, "closeout": closeout, "status": closeout.get("status") or plan.get("status") or "missing"})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.audio_campaign_remediation_store.refresh_plan(release_id, self._optional_json_body())
                self._send_json({"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("summary", {})})
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.run_safe_actions(release_id, self._optional_json_body())
                self._send_json({"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {})})
                return
            if tail == "/status":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.audio_campaign_remediation_store.refresh_plan(release_id)
                queue = self.audio_campaign_remediation_store.build_action_queue(release_id)
                closeout = self.audio_campaign_remediation_store.closeout_report(release_id)
                self._send_json({"ok": closeout.get("status") == "passed", "plan": plan, "queue": queue, "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")})
                return
            if tail == "/closeout":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.audio_campaign_remediation_store.closeout_report(release_id)
                self._send_json({"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.export_package(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {})})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.audio_campaign_remediation_store.build_zip(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.audio_campaign_remediation_store.verify_zip(release_id, strict=bool(payload.get("strict")), require_passed=bool(payload.get("require_passed", True)), require_signed=bool(payload.get("require_signed", False)))
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.audio_campaign_remediation_store.zip_path(release_id), "application/zip", filename="audio-campaign-remediation.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Campaign remediation route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioCampaignRemediationNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioCampaignRemediationStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AudioCampaignRemediationValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except AudioCampaignRemediationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_certification(self, method: str, release_id: str, tail: str) -> None:
        try:
            self.release_audio_certification_store.release_store = self.release_store
            self.release_audio_certification_store.project_store = self.project_store
            self.release_audio_certification_store.planner_store = self.audio_campaign_planner_store
            self.release_audio_certification_store.campaign_store = self.audio_campaign_store
            self.release_audio_certification_store.governance_store = self.audio_campaign_governance_store
            self.release_audio_certification_store.remediation_store = self.audio_campaign_remediation_store
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_certification_store.read_report(release_id, default={})
                matrix = self.release_audio_certification_store.read_matrix(release_id, default={})
                evidence = self.release_audio_certification_store.read_evidence_index(release_id, default={})
                blockers = self.release_audio_certification_store.read_blocker_register(release_id, default={})
                signoff = read_json(self.release_audio_certification_store.signoff_path(release_id)) if self.release_audio_certification_store.signoff_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "report": report, "matrix": matrix, "evidence_index": evidence, "blocker_register": blockers, "signoff": signoff, "summary": report.get("summary", {}) if report else {}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_certification_store.refresh_report(release_id)
                self._send_json({"ok": report.get("status") == "passed", "release_id": release_id, "report": report, "summary": report.get("summary", {})})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_certification_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_certification_store.export_package(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_certification_store.build_zip(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_certification_store.verify_zip(
                    release_id,
                    strict=bool(payload.get("strict", True)),
                    require_passed=bool(payload.get("require_passed", True)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_real_audio=bool(payload.get("require_real_audio", True)),
                    require_manual_review=bool(payload.get("require_manual_review", True)),
                    require_remediation_when_needed=bool(payload.get("require_remediation_when_needed", True)),
                )
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_certification_store.zip_path(release_id), "application/zip", filename="release-audio-certification.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Certification route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioCertificationNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioCertificationStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioCertificationValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioCertificationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_timeline(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.release_audio_timeline_store.list_timelines(release_id)})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                result = self.release_audio_timeline_store.refresh_timeline(release_id, force_new=bool(payload.get("force_new", False)))
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/current":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                timeline_id = self.release_audio_timeline_store._resolve_timeline_id(release_id, None)
                report = self.release_audio_timeline_store.read_timeline(release_id, timeline_id)
                signoff = read_json(self.release_audio_timeline_store.signoff_path(release_id, timeline_id)) if self.release_audio_timeline_store.signoff_path(release_id, timeline_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "timeline_id": timeline_id, "report": report, "signoff": signoff, "summary": report.get("summary", {})})
                return
            parts = [part for part in tail.split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Timeline route not found.")
                return
            timeline_id = parts[0]
            action = parts[1] if len(parts) > 1 else ""
            if action == "":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_timeline_store.read_timeline(release_id, timeline_id)
                signoff = read_json(self.release_audio_timeline_store.signoff_path(release_id, timeline_id)) if self.release_audio_timeline_store.signoff_path(release_id, timeline_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "timeline_id": timeline_id, "report": report, "signoff": signoff, "summary": report.get("summary", {})})
                return
            if action == "events":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.release_audio_timeline_store.read_events(release_id, timeline_id)})
                return
            if action == "tracks":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "track_index": self.release_audio_timeline_store.read_track_index(release_id, timeline_id)})
                return
            if action == "trend":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "quality_trend": self.release_audio_timeline_store.read_quality_trend(release_id, timeline_id)})
                return
            if action == "risks":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "risk_register": self.release_audio_timeline_store.read_risk_register(release_id, timeline_id)})
                return
            if action == "signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_timeline_store.signoff_timeline(release_id, timeline_id, self._read_json_body())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if action == "export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_timeline_store.export_timeline(release_id, timeline_id)
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if action == "zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_timeline_store.build_zip(release_id, timeline_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if action == "verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_timeline_store.verify_zip(
                    release_id,
                    timeline_id,
                    strict=bool(payload.get("strict", True)),
                    require_passed=bool(payload.get("require_passed", True)),
                    require_signed=bool(payload.get("require_signed", False)),
                    require_real_audio=bool(payload.get("require_real_audio", True)),
                    require_manual_review=bool(payload.get("require_manual_review", True)),
                    require_current_certification=bool(payload.get("require_current_certification", True)),
                )
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if action == "download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_timeline_store.zip_path(release_id, timeline_id), "application/zip", filename="release-audio-timeline.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Timeline route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioTimelineNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioTimelineStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioTimelineValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioTimelineError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_regression(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_regression_store.read_report(release_id, default={})
                config = self.release_audio_regression_store.read_config(release_id, default={})
                signoff = read_json(self.release_audio_regression_store.signoff_path(release_id)) if self.release_audio_regression_store.signoff_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "config": config, "report": report, "signoff": signoff, "summary": report.get("summary", {}) if report else {}})
                return
            if tail == "/configure":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config = self.release_audio_regression_store.configure_baseline(release_id, self._read_json_body())
                self._send_json({"ok": True, "release_id": release_id, "config": config, "summary": {"baseline_release_id": (config.get("baseline") or {}).get("release_id")}}, status=HTTPStatus.CREATED)
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_regression_store.refresh_report(release_id)
                self._send_json({"ok": report.get("status") == "passed", "release_id": release_id, "report": report, "summary": report.get("summary", {})})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_store.export_package(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_store.build_zip(release_id)
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
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
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_regression_store.zip_path(release_id), "application/zip", filename="release-audio-regression.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Regression route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioRegressionNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioRegressionStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioRegressionValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioRegressionError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_regression_response(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.release_audio_regression_response_store.read_plan(release_id, default={})
                closeout = read_json(self.release_audio_regression_response_store.closeout_path(release_id)) if self.release_audio_regression_response_store.closeout_path(release_id).exists() else {}
                signoff = read_json(self.release_audio_regression_response_store.signoff_path(release_id)) if self.release_audio_regression_response_store.signoff_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "plan": plan, "closeout": closeout, "signoff": signoff, "summary": plan.get("summary", {}) if plan else {}})
                return
            if tail == "/create":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.release_audio_regression_response_store.create_plan(release_id, self._optional_json_body())
                self._send_json({"ok": True, "plan": plan, "summary": plan.get("summary", {})}, status=HTTPStatus.CREATED)
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.run_safe_actions(release_id)
                self._send_json({"ok": True, **result})
                return
            if tail == "/waive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                waivers = self.release_audio_regression_response_store.add_waiver(release_id, self._read_json_body())
                self._send_json({"ok": True, "waivers": waivers, "summary": {"waiver_count": len(waivers.get("waivers", []))}})
                return
            if tail == "/closeout":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.release_audio_regression_response_store.closeout(release_id, self._optional_json_body())
                self._send_json({"ok": True, "closeout": closeout, "summary": closeout})
                return
            if tail == "/signoff":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.signoff(release_id, self._read_json_body())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.export_package(release_id)
                self._send_json({"ok": True, **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_regression_response_store.build_zip(release_id)
                self._send_json({"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
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
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_regression_response_store.zip_path(release_id), "application/zip", filename="release-audio-regression-response.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Regression Response route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioRegressionResponseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioRegressionResponseStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioRegressionResponseValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioRegressionResponseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_audio_command_center(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_command_center_store.read_report(release_id) if self.release_audio_command_center_store.report_path(release_id).exists() else {}
                inventory = self.release_audio_command_center_store.read_inventory(release_id) if self.release_audio_command_center_store.inventory_path(release_id).exists() else {}
                readiness = read_json(self.release_audio_command_center_store.readiness_path(release_id)) if self.release_audio_command_center_store.readiness_path(release_id).exists() else {}
                gap_plan = read_json(self.release_audio_command_center_store.gap_plan_path(release_id)) if self.release_audio_command_center_store.gap_plan_path(release_id).exists() else {}
                runbook = read_json(self.release_audio_command_center_store.runbook_path(release_id)) if self.release_audio_command_center_store.runbook_path(release_id).exists() else {}
                self._send_json({"ok": True, "release_id": release_id, "report": report, "inventory": inventory, "readiness": readiness, "gap_plan": gap_plan, "runbook": runbook, "summary": report.get("summary", {}) if report else {}})
                return
            if tail == "/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.release_audio_command_center_store.refresh(release_id, self._optional_json_body())
                self._send_json({"ok": report.get("status") == "passed", "release_id": release_id, "report": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/runbook":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                runbook = self.release_audio_command_center_store.create_runbook(release_id, self._optional_json_body())
                self._send_json({"ok": True, "release_id": release_id, "runbook": runbook, "summary": runbook.get("summary", {})})
                return
            if tail == "/run-safe":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_command_center_store.run_safe(release_id, self._optional_json_body())
                self._send_json({"ok": result.get("summary", {}).get("failed_count") == 0, "release_id": release_id, "runbook_results": result, "summary": result.get("summary", {})})
                return
            if tail == "/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_command_center_store.export_package(release_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if tail == "/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_command_center_store.build_zip(release_id, self._optional_json_body())
                self._send_json({"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}})
                return
            if tail == "/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_command_center_store.verify_zip(release_id, evidence=payload, strict=bool(payload.get("strict", True)), require_ready=bool(payload.get("require_ready", False)))
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                return
            if tail == "/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_command_center_store.zip_path(release_id), "application/zip", filename="release-audio-command-center.zip")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Release Audio Command Center route not found.")
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioCommandCenterNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioCommandCenterStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioCommandCenterError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_baselines_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-baselines":
                if method == "GET":
                    baselines = self.release_audio_baseline_governance_store.list_baselines()
                    self._send_json({"ok": True, "baselines": baselines, "summary": {"baseline_count": len(baselines)}})
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    release_id = str(payload.get("release_id") or "")
                    if not release_id:
                        self._send_error(HTTPStatus.BAD_REQUEST, "release_id is required.")
                        return
                    baseline = self.release_audio_baseline_governance_store.create_from_release(release_id, payload)
                    self._send_json({"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path == "/api/audio-baselines/export":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_baseline_governance_store.export_registry()
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if path == "/api/audio-baselines/zip":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.release_audio_baseline_governance_store.build_zip()
                self._send_json({"ok": result.get("status") == "passed", **result})
                return
            if path == "/api/audio-baselines/verify":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                report = self.release_audio_baseline_governance_store.verify_zip(strict=bool(payload.get("strict", True)), require_active=bool(payload.get("require_active", False)))
                self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {})})
                return
            if path == "/api/audio-baselines/download":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_file(self.release_audio_baseline_governance_store.zip_path(), "application/zip", filename="release-audio-baseline-registry.zip")
                return
            rest = path.removeprefix("/api/audio-baselines/").strip("/")
            parts = rest.split("/") if rest else []
            if len(parts) == 1:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                baseline = self.release_audio_baseline_governance_store.read_baseline(parts[0])
                self._send_json({"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}})
                return
            if len(parts) == 2:
                baseline_id, action = parts
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "approve":
                    baseline = self.release_audio_baseline_governance_store.approve(baseline_id, self._read_json_body())
                elif action == "activate":
                    baseline = self.release_audio_baseline_governance_store.activate(baseline_id, self._optional_json_body())
                elif action == "revoke":
                    baseline = self.release_audio_baseline_governance_store.revoke(baseline_id, self._read_json_body())
                else:
                    self._send_error(HTTPStatus.NOT_FOUND, "Audio Baseline route not found.")
                    return
                self._send_json({"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio Baseline route not found.")
        except ReleaseAudioBaselineGovernanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioBaselineGovernanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioBaselineGovernanceValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioBaselineGovernanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_quality_observatories_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-quality-observatories":
                if method == "GET":
                    rows = self.release_audio_quality_observatory_store.list_observatories()
                    self._send_json({"ok": True, "observatories": rows, "summary": {"observatory_count": len(rows)}})
                    return
                if method == "POST":
                    config = self.release_audio_quality_observatory_store.create(self._optional_json_body())
                    self._send_json({"ok": True, "observatory": config, "summary": {"observatory_id": config.get("observatory_id")}}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio-quality-observatories/").strip("/")
            parts = rest.split("/") if rest else []
            if len(parts) == 1:
                observatory_id = parts[0]
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                config = self.release_audio_quality_observatory_store.read_config(observatory_id)
                summary = self.release_audio_quality_observatory_store.read_summary(observatory_id) if self.release_audio_quality_observatory_store.summary_path(observatory_id).exists() else {}
                self._send_json({"ok": True, "observatory": config, "summary_report": summary, "summary": summary.get("summary", {}) if summary else {}})
                return
            if len(parts) == 2:
                observatory_id, action = parts
                if action == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.release_audio_quality_observatory_store.zip_path(observatory_id), "application/zip", filename="release-audio-quality-observatory.zip")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if action == "refresh":
                    summary = self.release_audio_quality_observatory_store.refresh(observatory_id, payload)
                    self._send_json({"ok": summary.get("status") == "passed", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")})
                    return
                if action == "export":
                    result = self.release_audio_quality_observatory_store.export_package(observatory_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "zip":
                    result = self.release_audio_quality_observatory_store.build_zip(observatory_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "verify":
                    report = self.release_audio_quality_observatory_store.verify_zip(
                        observatory_id,
                        strict=bool(payload.get("strict", True)),
                        require_current_evidence=bool(payload.get("require_current_evidence", False)),
                        evidence_root=payload.get("evidence_root") or self.release_store.root,
                        require_no_critical_risk=bool(payload.get("require_no_critical_risk", False)),
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Audio Quality Observatory route not found.")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio Quality Observatory route not found.")
        except ReleaseAudioQualityObservatoryNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioQualityObservatoryStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioQualityObservatoryValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioQualityObservatoryError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_quality_actions_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-quality-actions":
                if method == "GET":
                    rows = self.release_audio_quality_action_queue_store.list_queues()
                    self._send_json({"ok": True, "queues": rows, "summary": {"queue_count": len(rows)}})
                    return
                if method == "POST":
                    payload = self._read_json_body()
                    queue = self.release_audio_quality_action_queue_store.create_from_observatory(
                        payload.get("observatory_id", ""),
                        name=payload.get("name"),
                        include_risks=bool(payload.get("include_risks", True)),
                        include_recommendations=bool(payload.get("include_recommendations", True)),
                        severity_floor=str(payload.get("severity_floor") or "warning"),
                        policy=payload.get("policy") if isinstance(payload.get("policy"), dict) else {},
                    )
                    self._send_json({"ok": True, "queue": queue, "summary": queue.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio-quality-actions/").strip("/")
            parts = rest.split("/") if rest else []
            if len(parts) == 1:
                queue_id = parts[0]
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                queue = self.release_audio_quality_action_queue_store.read_queue(queue_id)
                summary = self.release_audio_quality_action_queue_store.read_summary(queue_id) if self.release_audio_quality_action_queue_store.summary_path(queue_id).exists() else {}
                self._send_json({"ok": True, "queue": queue, "summary_report": summary, "summary": summary.get("summary", {}) if summary else {}})
                return
            if len(parts) == 2:
                queue_id, action = parts
                if action == "download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.release_audio_quality_action_queue_store.zip_path(queue_id), "application/zip", filename="release-audio-quality-action-queue.zip")
                    return
                if action == "archive-download":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.release_audio_quality_action_signoff_store.archive_zip_path(queue_id), "application/zip", filename="release-audio-quality-action-queue-signoff-archive.zip")
                    return
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                if action == "refresh":
                    summary = self.release_audio_quality_action_queue_store.refresh_status(queue_id)
                    self._send_json({"ok": summary.get("status") != "stale", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")})
                    return
                if action == "run-safe":
                    result = self.release_audio_quality_action_queue_store.run_safe(queue_id)
                    self._send_json({"ok": result.get("status") not in {"failed", "stale"}, **result})
                    return
                if action == "export":
                    result = self.release_audio_quality_action_queue_store.export_package(queue_id)
                    self._send_json({"ok": result.get("status") not in {"failed", "stale"}, **result})
                    return
                if action == "zip":
                    result = self.release_audio_quality_action_queue_store.build_zip(queue_id)
                    self._send_json({"ok": result.get("status") not in {"failed", "stale"}, **result})
                    return
                if action == "verify":
                    report = self.release_audio_quality_action_queue_store.verify_zip(
                        queue_id,
                        strict=bool(payload.get("strict", True)),
                        require_current_observatory=bool(payload.get("require_current_observatory", False)),
                        observatory_zip_path=payload.get("observatory_zip"),
                        observatory_verification_report_path=payload.get("observatory_verification_report"),
                        evidence_root=payload.get("evidence_root") or self.release_store.root,
                        require_no_blocking=bool(payload.get("require_no_blocking", True)),
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                if action == "manual-items":
                    result = self.release_audio_quality_action_signoff_store.list_manual_items(queue_id)
                    self._send_json({"ok": True, **result, "status": "passed"})
                    return
                if action == "resolve-manual":
                    item_id = str(payload.get("item_id") or "")
                    result = self.release_audio_quality_action_signoff_store.resolve_manual_item(queue_id, item_id, payload)
                    self._send_json({"ok": True, "resolution": result, "status": "passed"})
                    return
                if action == "closeout":
                    closeout = self.release_audio_quality_action_signoff_store.refresh_closeout(queue_id)
                    self._send_json({"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")})
                    return
                if action == "signoff":
                    result = self.release_audio_quality_action_signoff_store.signoff(queue_id, payload)
                    self._send_json({"ok": True, **result})
                    return
                if action == "archive":
                    result = self.release_audio_quality_action_signoff_store.export_archive(queue_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "archive-zip":
                    result = self.release_audio_quality_action_signoff_store.build_archive_zip(queue_id)
                    self._send_json({"ok": result.get("status") == "passed", **result})
                    return
                if action == "archive-verify":
                    report = self.release_audio_quality_action_signoff_store.verify_archive(
                        queue_id,
                        strict=bool(payload.get("strict", True)),
                        require_current_queue=bool(payload.get("require_current_queue", True)),
                        require_signed=bool(payload.get("require_signed", True)),
                        queue_zip_path=payload.get("queue_zip"),
                        queue_verification_report_path=payload.get("queue_verification_report"),
                        observatory_zip_path=payload.get("observatory_zip"),
                        observatory_verification_report_path=payload.get("observatory_verification_report"),
                        evidence_root=payload.get("evidence_root") or self.release_store.root,
                    )
                    self._send_json({"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")})
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Audio Quality Action Queue route not found.")
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio Quality Action Queue route not found.")
        except ReleaseAudioQualityActionQueueNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioQualityActionQueueStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioQualityActionQueueValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioQualityActionQueueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioQualityActionQueueSignoffNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except ReleaseAudioQualityActionQueueSignoffStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except ReleaseAudioQualityActionQueueSignoffValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except ReleaseAudioQualityActionQueueSignoffError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_mastering_profiles_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/mastering/profiles":
                if method == "GET":
                    profiles = [profile.to_dict() for profile in self.mastering_profile_store.list_profiles(include_builtins=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.mastering_profile_store.create_profile(self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/mastering/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Mastering profile route not found.")
                return
            profile_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    profile = self.mastering_profile_store.get_profile(profile_id)
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "PATCH":
                    profile = self.mastering_profile_store.update_profile(profile_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "DELETE":
                    self.mastering_profile_store.delete_profile(profile_id)
                    self._send_json({"ok": True, "deleted": True, "profile_id": profile_id})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[1] == "clone":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                profile = self.mastering_profile_store.clone_profile(profile_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Mastering profile route not found.")
        except MasteringProfileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except MasteringProfileError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_audio_encoding_route(self, method: str, path: str) -> None:
        try:
            if path == "/api/audio-encoding/config":
                if method == "GET":
                    self._send_json({"ok": True, "config": self.audio_encoding_store.read_config().public_summary()})
                    return
                if method == "POST":
                    config = self.audio_encoding_store.write_config(self._read_json_body())
                    self._send_json({"ok": True, "config": config})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if path == "/api/audio-encoding/config/test":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, **self.audio_encoding_store.test_config()})
                return
            if path == "/api/audio-encoding/config/reset":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "config": self.audio_encoding_store.reset_config()})
                return
            if path == "/api/audio-encoding/profiles":
                if method == "GET":
                    profiles = [profile.to_dict() for profile in self.audio_encoding_profile_store.list_profiles(include_builtins=True)]
                    self._send_json({"ok": True, "profiles": profiles})
                    return
                if method == "POST":
                    profile = self.audio_encoding_profile_store.create_profile(self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            rest = path.removeprefix("/api/audio-encoding/profiles/").strip("/")
            parts = rest.split("/") if rest else []
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Audio encoding profile route not found.")
                return
            profile_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    profile = self.audio_encoding_profile_store.get_profile(profile_id)
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "PATCH":
                    profile = self.audio_encoding_profile_store.update_profile(profile_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "profile": profile.to_dict()})
                    return
                if method == "DELETE":
                    self.audio_encoding_profile_store.delete_profile(profile_id)
                    self._send_json({"ok": True, "deleted": True, "profile_id": profile_id})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[1] == "clone":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                profile = self.audio_encoding_profile_store.clone_profile(profile_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "profile": profile.to_dict()}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Audio encoding profile route not found.")
        except AudioEncodingProfileNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AudioEncodingProfileError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_format_decisions(self, method: str, release_id: str, tail: str) -> None:
        try:
            if tail in {"", "/"}:
                if method == "GET":
                    sessions = self.format_decision_store.list_sessions(release_id, include_archived=True)
                    active = self.format_decision_store.read_active_session(release_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "sessions": sessions, "active_session": active})
                    return
                if method == "POST":
                    session = self.format_decision_store.create_session(release_id, self._optional_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "session": session}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                self._send_error(HTTPStatus.NOT_FOUND, "Format decision route not found.")
                return
            session_id = parts[0]
            if len(parts) == 1:
                if method == "GET":
                    session = self.format_decision_store.read_session(release_id, session_id)
                    matrix = self.format_decision_store.read_matrix(release_id, session_id, default={})
                    recommendation = self.format_decision_store.read_recommendation(release_id, session_id, default={})
                    report = self.format_decision_store.read_report(release_id, session_id, default={})
                    self._send_json({"ok": True, "release_id": release_id, "session": session, "matrix": matrix, "recommendation": recommendation, "report": report})
                    return
                if method == "DELETE":
                    session = self.format_decision_store.archive_session(release_id, session_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "session": session})
                    return
            if len(parts) == 2 and parts[1] == "matrix":
                if method == "GET":
                    matrix = self.format_decision_store.read_matrix(release_id, session_id)
                    self._send_json({"ok": True, "release_id": release_id, "matrix": matrix})
                    return
                if method == "POST":
                    matrix = self.format_decision_store.build_matrix(release_id, session_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "matrix": matrix})
                    return
            if len(parts) == 2 and parts[1] == "recommend":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                recommendation = self.format_decision_store.build_recommendation(release_id, session_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "recommendation": recommendation})
                return
            if len(parts) == 2 and parts[1] == "recommendation":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                recommendation = self.format_decision_store.read_recommendation(release_id, session_id)
                self._send_json({"ok": True, "release_id": release_id, "recommendation": recommendation})
                return
            if len(parts) == 2 and parts[1] == "select":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                session = self.format_decision_store.select_profiles(release_id, session_id, self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "session": session})
                return
            if len(parts) == 2 and parts[1] == "report":
                if method == "GET":
                    report = self.format_decision_store.read_report(release_id, session_id)
                    self._send_json({"ok": True, "release_id": release_id, "report": report})
                    return
                if method == "POST":
                    report = self.format_decision_store.build_report(release_id, session_id, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "report": report})
                    return
            if len(parts) == 2 and parts[1] == "activate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                active = self.format_decision_store.activate_session(release_id, session_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "active_session": active})
                return
            if len(parts) == 2 and parts[1] == "gate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                gate = self.format_decision_store.gate(
                    release_id,
                    required=True,
                    session_id=session_id,
                    required_profiles=normalize_required_profiles(payload.get("required_audio_format_profiles") or payload.get("profiles") or []),
                )
                self._send_json({"ok": True, "release_id": release_id, "gate": gate})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Format decision route not found.")
        except (ReleaseNotFoundError, FormatDecisionNotFoundError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (ReleaseStateError, FormatDecisionStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (FormatDecisionError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_rights(self, method: str, release_id: str, tail: str) -> None:
        try:
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.rights_clearance_store.read_report(release_id, default={})
                self._send_json({"ok": True, "release_id": release_id, "report": report, "parties": self.rights_clearance_store.list_parties(release_id)})
                return
            if parts == ["refresh"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.rights_clearance_store.refresh_report(release_id, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "report": report})
                return
            if parts == ["gate"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                gate = self.rights_clearance_store.gate(release_id, required=True, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "gate": gate})
                return
            if parts == ["parties"]:
                if method == "GET":
                    self._send_json({"ok": True, "release_id": release_id, "parties": self.rights_clearance_store.list_parties(release_id)})
                    return
                if method == "POST":
                    party = self.rights_clearance_store.upsert_party(release_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "party": party}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            if len(parts) == 2 and parts[0] == "parties":
                if method not in {"POST", "PATCH"}:
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                party = self.rights_clearance_store.upsert_party(release_id, {**self._read_json_body(), "party_id": parts[1]}, now=_utc_now())
                self._send_json({"ok": True, "release_id": release_id, "party": party})
                return
            if len(parts) >= 2 and parts[0] == "tracks":
                track_id = parts[1]
                action = parts[2] if len(parts) >= 3 else ""
                if not action:
                    if method == "GET":
                        record = self.rights_clearance_store.read_track(release_id, track_id, default={})
                        self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                        return
                    if method in {"POST", "PATCH"}:
                        record = self.rights_clearance_store.upsert_track(release_id, track_id, self._optional_json_body(), now=_utc_now())
                        self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                        return
                if action == "contributors":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    contributors = payload.get("contributors") if isinstance(payload.get("contributors"), list) else payload if isinstance(payload, list) else []
                    record = self.rights_clearance_store.upsert_track(release_id, track_id, {"contributors": contributors}, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
                if action == "sources":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    sources = payload.get("source_usages") if isinstance(payload.get("source_usages"), list) else payload.get("sources") if isinstance(payload.get("sources"), list) else payload if isinstance(payload, list) else []
                    record = self.rights_clearance_store.upsert_track(release_id, track_id, {"source_usages": sources}, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
                if action == "review":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    record = self.rights_clearance_store.review_track(release_id, track_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
                if action == "reset-review":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    reason = str(payload.get("reason") or "").strip()
                    if not reason:
                        self._send_error(HTTPStatus.BAD_REQUEST, "reason is required.")
                        return
                    record = self.rights_clearance_store.reset_track_review(release_id, track_id, reason=reason, now=_utc_now())
                    self._send_json({"ok": True, "release_id": release_id, "track_id": track_id, "rights": record})
                    return
            self._send_error(HTTPStatus.NOT_FOUND, "Rights clearance route not found.")
        except (ReleaseNotFoundError, RightsClearanceNotFoundError, FileNotFoundError) as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (ReleaseStateError, RightsClearanceStateError) as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (RightsClearanceError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _job_audio_artifact_stale_reasons(self, job: JobState) -> list[str]:
        run_dir = Path(job.output_dir)
        wav_path = run_dir / "renders" / "song.wav"
        midi_path = run_dir / "renders" / "song.mid"
        plan_path = run_dir / "data" / "song-plan.json"
        manifest = read_audio_artifact_manifest(run_dir / "renders" / AUDIO_ARTIFACT_FILENAME, default={})
        profile = None
        renderer = manifest.get("renderer") if isinstance(manifest.get("renderer"), dict) else {}
        profile_id = str(renderer.get("profile_id") or "")
        if profile_id.startswith("arp-"):
            try:
                profile = self.audio_profile_store.get_profile(profile_id)
            except AudioProfileError:
                profile = None
        return audio_artifact_stale_reasons_for_profile(manifest, wav_path=wav_path, midi_path=midi_path, song_plan_path=plan_path, profile=profile)

    def _release_mastering_export_gate(self, export_manifest: dict[str, Any], mastering_gate: dict[str, Any]) -> dict[str, Any]:
        manifest_mastering = export_manifest.get("mastering") if isinstance(export_manifest.get("mastering"), dict) else {}
        required_fields = ("analysis_hash", "plan_hash", "selected_candidate_id", "selected_candidate_hash")
        missing_fields = [field for field in required_fields if not manifest_mastering.get(field)]
        mismatched_fields = [
            field
            for field in required_fields
            if str(manifest_mastering.get(field) or "") != str(mastering_gate.get(field) or "")
        ]
        manifest_status = str(manifest_mastering.get("status") or "")
        if manifest_status not in {"passed", "warning"}:
            mismatched_fields.append("status")
        failed = bool(missing_fields or mismatched_fields)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current Mastering QA evidence.",
            "missing_fields": sorted(set(missing_fields)),
            "mismatched_fields": sorted(set(mismatched_fields)),
            "manifest_selected_candidate_id": manifest_mastering.get("selected_candidate_id"),
            "current_selected_candidate_id": mastering_gate.get("selected_candidate_id"),
            "manifest_status": manifest_status or "missing",
        }

    def _release_encoded_audio_export_gate(self, export_manifest: dict[str, Any], encoded_gate: dict[str, Any]) -> dict[str, Any]:
        manifest_encoded = export_manifest.get("encoded_audio") if isinstance(export_manifest.get("encoded_audio"), dict) else {}
        manifest_profiles = manifest_encoded.get("profiles") if isinstance(manifest_encoded.get("profiles"), list) else []
        by_profile = {str(row.get("profile_id") or ""): row for row in manifest_profiles if isinstance(row, dict)}
        missing: list[str] = []
        mismatched: list[str] = []
        for row in encoded_gate.get("profiles", []) if isinstance(encoded_gate.get("profiles"), list) else []:
            if not isinstance(row, dict):
                continue
            profile_id = str(row.get("profile_id") or "")
            manifest_row = by_profile.get(profile_id)
            if not manifest_row:
                missing.append(profile_id)
                continue
            for field in ("source_hash", "manifest_hash"):
                if str(manifest_row.get(field) or "") != str(row.get(field) or ""):
                    mismatched.append(f"{profile_id}:{field}")
            if str(manifest_row.get("status") or "") != "completed":
                mismatched.append(f"{profile_id}:status")
        failed = bool(missing or mismatched)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current encoded audio evidence.",
            "missing_profiles": missing,
            "mismatched_profiles": sorted(set(mismatched)),
        }

    def _release_encoded_audio_acceptance_export_gate(self, export_manifest: dict[str, Any], acceptance_gate: dict[str, Any]) -> dict[str, Any]:
        manifest_acceptance = export_manifest.get("encoded_audio_acceptance") if isinstance(export_manifest.get("encoded_audio_acceptance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_acceptance:
            missing.append("encoded_audio_acceptance")
        summary: dict[str, Any] = {}
        release_id = str(export_manifest.get("release_id") or "")
        export_dir = self.release_store.export_dir(release_id)
        summary_path = str(manifest_acceptance.get("summary_path") or "encoded-audio-acceptance-summary.json")
        if manifest_acceptance:
            try:
                candidate = read_json(export_dir / summary_path)
                summary = candidate if isinstance(candidate, dict) else {}
            except Exception:
                missing.append(summary_path)
        if summary:
            expected_hash = str(manifest_acceptance.get("summary_hash") or "")
            actual_hash = encoded_audio_acceptance_summary_hash(summary)
            if not expected_hash or expected_hash != actual_hash or not encoded_audio_acceptance_summary_integrity_ok(summary):
                mismatched.append("summary_hash")
        elif manifest_acceptance:
            mismatched.append("summary")
        manifest_profiles = {str(item) for item in summary.get("required_profiles", []) if str(item).strip()} if isinstance(summary.get("required_profiles"), list) else {str(item) for item in manifest_acceptance.get("required_profiles", []) if str(item).strip()} if isinstance(manifest_acceptance.get("required_profiles"), list) else set()
        gate_profiles = {str(item) for item in acceptance_gate.get("required_profiles", []) if str(item).strip()} if isinstance(acceptance_gate.get("required_profiles"), list) else set()
        missing_profiles = sorted(gate_profiles - manifest_profiles)
        summary_tracks = summary.get("tracks") if isinstance(summary.get("tracks"), list) else []
        by_profile_track = {
            (str(row.get("profile_id") or ""), str(row.get("track_id") or "")): row
            for row in summary_tracks
            if isinstance(row, dict)
        }
        gate_summary = self.encoded_audio_acceptance_store.build_summary(release_id, required_profiles=sorted(gate_profiles), now=_utc_now())
        gate_tracks = gate_summary.get("tracks") if isinstance(gate_summary.get("tracks"), list) else []
        review_hashes = {
            str(row.get("review_id") or ""): {"path": str(row.get("path") or ""), "payload_hash": str(row.get("payload_hash") or "")}
            for row in manifest_acceptance.get("review_hashes", [])
            if isinstance(row, dict) and str(row.get("review_id") or "")
        }
        for row in gate_tracks:
            if not isinstance(row, dict):
                continue
            profile_id = str(row.get("profile_id") or "")
            track_id = str(row.get("track_id") or "")
            manifest_row = by_profile_track.get((profile_id, track_id))
            if not manifest_row:
                missing.append(f"{profile_id}/{track_id}")
                continue
            for field in ("status", "manifest_hash", "health_hash", "encoded_track_hash", "accepted_review_id"):
                if str(manifest_row.get(field) or "") != str(row.get(field) or ""):
                    mismatched.append(f"{profile_id}/{track_id}:{field}")
            review_id = str(row.get("accepted_review_id") or "")
            review_record = review_hashes.get(review_id) or {}
            review_path = str(review_record.get("path") or "")
            if not review_path:
                missing.append(f"{profile_id}/{track_id}:review")
                continue
            try:
                review = read_json(export_dir / review_path)
            except Exception:
                missing.append(review_path)
                continue
            if not isinstance(review, dict) or not encoded_audio_review_integrity_ok(review):
                mismatched.append(f"{profile_id}/{track_id}:review_integrity")
            if encoded_audio_review_integrity_hash(review if isinstance(review, dict) else {}) != str(review_record.get("payload_hash") or ""):
                mismatched.append(f"{profile_id}/{track_id}:review_hash")
        failed = bool(missing or mismatched or missing_profiles)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current encoded audio acceptance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
        }

    def _release_format_decision_export_gate(self, export_manifest: dict[str, Any], format_decision_gate: dict[str, Any]) -> dict[str, Any]:
        manifest_decision = export_manifest.get("format_decision") if isinstance(export_manifest.get("format_decision"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_decision or manifest_decision.get("status") in {"", "missing"}:
            missing.append("format_decision")
        release_id = str(export_manifest.get("release_id") or "")
        export_dir = self.release_store.export_dir(release_id)
        report_path = str(manifest_decision.get("report_path") or "format-decision/decision-report.json")
        report: dict[str, Any] = {}
        try:
            candidate = read_json(export_dir / report_path)
            report = candidate if isinstance(candidate, dict) else {}
        except Exception:
            missing.append(report_path)
        expected_report_hash = str(format_decision_gate.get("report_hash") or "")
        manifest_report_hash = str(manifest_decision.get("report_hash") or "")
        if expected_report_hash and manifest_report_hash != expected_report_hash:
            mismatched.append("report_hash")
        if report and str(report.get("integrity_hash") or "") != expected_report_hash:
            mismatched.append("report_payload")
        selected = set(manifest_decision.get("selected_profiles", []) if isinstance(manifest_decision.get("selected_profiles"), list) else [])
        gate_required = set(format_decision_gate.get("required_profiles", []) if isinstance(format_decision_gate.get("required_profiles"), list) else [])
        missing_profiles = sorted(gate_required - selected)
        failed = bool(missing or mismatched or missing_profiles)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current format decision evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
        }

    def _release_rights_clearance_export_gate(self, export_manifest: dict[str, Any], rights_gate: dict[str, Any]) -> dict[str, Any]:
        manifest_rights = export_manifest.get("rights_clearance") if isinstance(export_manifest.get("rights_clearance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_rights:
            missing.append("rights_clearance")
        for field in ("report_hash", "source_hash"):
            manifest_value = str(manifest_rights.get(field) or "")
            gate_value = str(rights_gate.get(field) or "")
            if not manifest_value or manifest_value != gate_value:
                mismatched.append(field)
        if str(manifest_rights.get("status") or "") != "passed":
            mismatched.append("status")
        failed = bool(missing or mismatched)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Release Export is stale. Rebuild export before signoff." if failed else "Release Export contains current rights clearance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "manifest_status": manifest_rights.get("status") or "missing",
        }

    def _distribution_encoded_audio_acceptance_export_gate(self, export_manifest: dict[str, Any], acceptance_gate: dict[str, Any]) -> dict[str, Any]:
        manifest_acceptance = export_manifest.get("encoded_audio_acceptance") if isinstance(export_manifest.get("encoded_audio_acceptance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_acceptance:
            missing.append("encoded_audio_acceptance")
        for field in ("source_hash", "summary_hash", "status"):
            manifest_value = str(manifest_acceptance.get(field) or "")
            gate_value = str(acceptance_gate.get(field) or "")
            if not manifest_value or manifest_value != gate_value:
                mismatched.append(field)
        manifest_profiles = {str(item) for item in manifest_acceptance.get("required_profiles", []) if str(item).strip()} if isinstance(manifest_acceptance.get("required_profiles"), list) else set()
        gate_profiles = {str(item) for item in acceptance_gate.get("required_profiles", []) if str(item).strip()} if isinstance(acceptance_gate.get("required_profiles"), list) else set()
        missing_profiles = sorted(gate_profiles - manifest_profiles)
        failed = bool(missing or mismatched or missing_profiles)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Distribution Export is stale. Rebuild export before signoff." if failed else "Distribution Export contains current encoded audio acceptance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
        }

    def _distribution_format_decision_export_gate(self, export_manifest: dict[str, Any], format_decision_gate: dict[str, Any]) -> dict[str, Any]:
        manifest_decision = export_manifest.get("format_decision") if isinstance(export_manifest.get("format_decision"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_decision or manifest_decision.get("status") in {"", "missing"}:
            missing.append("format_decision")
        if str(manifest_decision.get("report_hash") or "") != str(format_decision_gate.get("report_hash") or ""):
            mismatched.append("report_hash")
        gate_required = set(format_decision_gate.get("required_profiles", []) if isinstance(format_decision_gate.get("required_profiles"), list) else [])
        covered = set(manifest_decision.get("covered_profiles", []) if isinstance(manifest_decision.get("covered_profiles"), list) else [])
        missing_profiles = sorted(gate_required - covered)
        if isinstance(manifest_decision.get("missing_profiles"), list):
            missing_profiles = sorted(set(missing_profiles) | {str(item) for item in manifest_decision.get("missing_profiles", []) if str(item).strip()})
        role_incompatible = sorted({str(item) for item in manifest_decision.get("role_incompatible_profiles", []) if str(item).strip()}) if isinstance(manifest_decision.get("role_incompatible_profiles"), list) else []
        target = export_manifest.get("target") if isinstance(export_manifest.get("target"), dict) else {}
        coverage = distribution_target_format_decision_coverage(
            target,
            sorted(gate_required),
            {
                "selected_profiles": manifest_decision.get("selected_profiles", []),
                "archive_profiles": manifest_decision.get("archive_profiles", []),
            },
        )
        if sorted(covered) != list(coverage.get("covered_profiles", [])):
            mismatched.append("covered_profiles")
        role_incompatible = sorted(set(role_incompatible) | set(coverage.get("role_incompatible_profiles", [])))
        missing_profiles = sorted(set(missing_profiles) | set(coverage.get("missing_profiles", [])))
        failed = bool(missing or mismatched or missing_profiles or role_incompatible)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": "Distribution Export is stale. Rebuild export before signoff." if failed else "Distribution Export contains current format decision evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "missing_profiles": missing_profiles,
            "role_incompatible_profiles": role_incompatible,
        }

    def _package_rights_clearance_export_gate(self, export_manifest: dict[str, Any], rights_gate: dict[str, Any], *, package_label: str) -> dict[str, Any]:
        manifest_rights = export_manifest.get("rights_clearance") if isinstance(export_manifest.get("rights_clearance"), dict) else {}
        missing: list[str] = []
        mismatched: list[str] = []
        if not manifest_rights:
            missing.append("rights_clearance")
        for field in ("report_hash", "source_hash"):
            manifest_value = str(manifest_rights.get(field) or "")
            gate_value = str(rights_gate.get(field) or "")
            if not manifest_value or manifest_value != gate_value:
                mismatched.append(field)
        if str(manifest_rights.get("status") or "") != "passed":
            mismatched.append("status")
        failed = bool(missing or mismatched)
        return {
            "status": "failed" if failed else "passed",
            "hard_block": failed,
            "message": f"{package_label} Export is stale. Rebuild export before signoff." if failed else f"{package_label} Export contains current rights clearance evidence.",
            "missing": missing,
            "mismatched_fields": sorted(set(mismatched)),
            "manifest_status": manifest_rights.get("status") or "missing",
        }

    def _release_acceptance_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        suite_id = str(payload.get("acceptance_suite_id") or "").strip()
        analytics_evidence = self._release_acceptance_analytics_gate(payload)
        fix_sprint_evidence = self._release_acceptance_fix_sprint_gate(payload)
        fix_plan_evidence = self._release_acceptance_fix_plan_gate(payload)
        fix_plan_review_evidence = self._release_acceptance_fix_plan_review_gate(payload)
        kb_evidence = self._release_acceptance_kb_gate(payload)
        planning_simulation_evidence = self._release_planning_rule_simulation_gate(payload)
        planning_governance_evidence = self._release_planning_rule_governance_gate(payload)
        planning_impact_evidence = self._release_planning_rule_impact_gate(payload)
        if not suite_id:
            if not analytics_evidence:
                gate = {}
                if fix_plan_evidence:
                    gate["acceptance_fix_plan"] = fix_plan_evidence
                    if fix_plan_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                        gate["status"] = "failed"
                        gate["message"] = str(fix_plan_evidence.get("message") or "Acceptance Fix Plan gate failed.")
                if fix_plan_review_evidence:
                    gate["acceptance_fix_plan_review"] = fix_plan_review_evidence
                    if fix_plan_review_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                        gate["status"] = "failed"
                        gate["message"] = str(fix_plan_review_evidence.get("message") or "Acceptance Fix Plan Outcome Review gate failed.")
                if fix_sprint_evidence:
                    gate["acceptance_fix_sprint"] = fix_sprint_evidence
                if kb_evidence:
                    gate["acceptance_kb"] = kb_evidence
                if planning_simulation_evidence:
                    gate["planning_rule_simulation"] = planning_simulation_evidence
                    if planning_simulation_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                        gate["status"] = "failed"
                        gate["message"] = str(planning_simulation_evidence.get("message") or "Planning Rule Simulation gate failed.")
                if planning_governance_evidence:
                    gate["planning_rule_governance"] = planning_governance_evidence
                    if planning_governance_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                        gate["status"] = "failed"
                        gate["message"] = str(planning_governance_evidence.get("message") or "Planning Rule Governance gate failed.")
                if planning_impact_evidence:
                    gate["planning_rule_impact"] = planning_impact_evidence
                    if planning_impact_evidence.get("status") == "failed":
                        gate["status"] = "failed"
                        gate["message"] = str(planning_impact_evidence.get("message") or "Planning Rule Impact gate failed.")
                return gate
            gate = {"acceptance_analytics": analytics_evidence}
            if fix_plan_evidence:
                gate["acceptance_fix_plan"] = fix_plan_evidence
                if fix_plan_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                    gate["status"] = "failed"
                    gate["message"] = str(fix_plan_evidence.get("message") or "Acceptance Fix Plan gate failed.")
            if fix_plan_review_evidence:
                gate["acceptance_fix_plan_review"] = fix_plan_review_evidence
                if fix_plan_review_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                    gate["status"] = "failed"
                    gate["message"] = str(fix_plan_review_evidence.get("message") or "Acceptance Fix Plan Outcome Review gate failed.")
            if fix_sprint_evidence:
                gate["acceptance_fix_sprint"] = fix_sprint_evidence
                if fix_sprint_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                    gate["status"] = "failed"
                    gate["message"] = str(fix_sprint_evidence.get("message") or "Acceptance Fix Sprint gate failed.")
            if kb_evidence:
                gate["acceptance_kb"] = kb_evidence
            if planning_simulation_evidence:
                gate["planning_rule_simulation"] = planning_simulation_evidence
                if planning_simulation_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                    gate["status"] = "failed"
                    gate["message"] = str(planning_simulation_evidence.get("message") or "Planning Rule Simulation gate failed.")
            if planning_governance_evidence:
                gate["planning_rule_governance"] = planning_governance_evidence
                if planning_governance_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                    gate["status"] = "failed"
                    gate["message"] = str(planning_governance_evidence.get("message") or "Planning Rule Governance gate failed.")
            if planning_impact_evidence:
                gate["planning_rule_impact"] = planning_impact_evidence
                if planning_impact_evidence.get("status") == "failed":
                    gate["status"] = "failed"
                    gate["message"] = str(planning_impact_evidence.get("message") or "Planning Rule Impact gate failed.")
            if analytics_evidence.get("readiness_status") == "blocked" and not bool(payload.get("force", False)):
                gate["status"] = "failed"
                gate["message"] = "Acceptance analytics readiness is blocked."
            return gate
        report = self.acceptance_store.read_report(suite_id)
        summary = acceptance_report_summary(report)
        acceptance_status = str(summary.get("acceptance_status") or "")
        release_ready = bool(summary.get("release_ready", False))
        coverage_status = str(summary.get("songbook_coverage_status") or "not_applicable")
        human_review_pack = summary.get("human_review_pack") if isinstance(summary.get("human_review_pack"), dict) else {}
        require_release_ready = bool(payload.get("require_acceptance_release_ready", False)) or str(summary.get("profile_id") or "") in {"release_candidate", "audio_required"}
        if require_release_ready:
            ok = report.get("status") == "passed" and release_ready and acceptance_status == "release_ready_passed" and coverage_status in {"complete", "not_applicable"}
            message = "Acceptance suite is not manual release-ready."
        else:
            ok = report.get("status") == "passed" and int(summary.get("manual_accepted_count", 0) or 0) > 0 and acceptance_status in {"manual_passed", "release_ready_passed", "passed"}
            message = "Acceptance suite is not manually accepted."
        gate = {
            "status": "passed" if ok else "failed",
            "suite_id": suite_id,
            "profile_id": summary.get("profile_id"),
            "acceptance_status": acceptance_status,
            "release_ready": release_ready,
            "songbook_coverage_status": coverage_status,
            "expected_case_count": summary.get("expected_case_count", 0),
            "missing_song_ids": summary.get("missing_song_ids", []),
            "duplicate_song_ids": summary.get("duplicate_song_ids", []),
            "manual_accepted_count": summary.get("manual_accepted_count", 0),
            "synthetic_accepted_count": summary.get("synthetic_accepted_count", 0),
            "manual_audio_accepted_count": summary.get("manual_audio_accepted_count", 0),
            "audio_passed_count": summary.get("audio_passed_count", 0),
            "require_acceptance_release_ready": require_release_ready,
            "human_review_pack": human_review_pack,
            "message": message,
        }
        if analytics_evidence:
            gate["acceptance_analytics"] = analytics_evidence
            if analytics_evidence.get("readiness_status") == "blocked" and not bool(payload.get("force", False)):
                gate["status"] = "failed"
                gate["message"] = "Acceptance analytics readiness is blocked."
        if fix_plan_evidence:
            gate["acceptance_fix_plan"] = fix_plan_evidence
            if fix_plan_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                gate["status"] = "failed"
                gate["message"] = str(fix_plan_evidence.get("message") or "Acceptance Fix Plan gate failed.")
        if fix_plan_review_evidence:
            gate["acceptance_fix_plan_review"] = fix_plan_review_evidence
            if fix_plan_review_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                gate["status"] = "failed"
                gate["message"] = str(fix_plan_review_evidence.get("message") or "Acceptance Fix Plan Outcome Review gate failed.")
        if fix_sprint_evidence:
            gate["acceptance_fix_sprint"] = fix_sprint_evidence
            if fix_sprint_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                gate["status"] = "failed"
                gate["message"] = str(fix_sprint_evidence.get("message") or "Acceptance Fix Sprint gate failed.")
        if kb_evidence:
            gate["acceptance_kb"] = kb_evidence
        if planning_simulation_evidence:
            gate["planning_rule_simulation"] = planning_simulation_evidence
            if planning_simulation_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                gate["status"] = "failed"
                gate["message"] = str(planning_simulation_evidence.get("message") or "Planning Rule Simulation gate failed.")
        if planning_governance_evidence:
            gate["planning_rule_governance"] = planning_governance_evidence
            if planning_governance_evidence.get("status") == "failed" and not bool(payload.get("force", False)):
                gate["status"] = "failed"
                gate["message"] = str(planning_governance_evidence.get("message") or "Planning Rule Governance gate failed.")
        if planning_impact_evidence:
            gate["planning_rule_impact"] = planning_impact_evidence
            if planning_impact_evidence.get("status") == "failed":
                gate["status"] = "failed"
                gate["message"] = str(planning_impact_evidence.get("message") or "Planning Rule Impact gate failed.")
        return gate

    def _release_audio_campaign_gate(self, release_id: str, payload: dict[str, Any], *, required: bool) -> dict[str, Any]:
        campaign_id = str(payload.get("audio_campaign_id") or payload.get("campaign_id") or "").strip()
        if not campaign_id:
            return {"status": "failed" if required else "missing", "hard_block": bool(required), "message": "Audio Campaign id is required.", "release_id": release_id}
        gate = self.audio_campaign_governance_store.gate(
            campaign_id,
            required=required,
            archive_zip_path=payload.get("audio_campaign_archive_zip_path") or payload.get("audio_campaign_archive"),
            archive_verification_report_path=payload.get("audio_campaign_archive_verification_report_path") or payload.get("audio_campaign_archive_verification_report"),
        )
        try:
            release = self.release_store.get_release(release_id)
            track_count = len(release.tracks)
        except Exception:
            release = None
            track_count = 0
        summary = gate.get("summary") if isinstance(gate.get("summary"), dict) else {}
        case_count = int(summary.get("case_count") or 0)
        gate = {**gate, "release_id": release_id, "track_count": track_count, "case_count": case_count}
        if required and gate.get("status") == "passed" and track_count > 0 and case_count < track_count:
            gate.update(
                {
                    "status": "failed",
                    "hard_block": True,
                    "message": "Audio Campaign does not cover all release tracks.",
                }
            )
        if required and gate.get("status") == "passed" and release is not None and track_count > 0:
            coverage = self._release_audio_campaign_coverage(release, campaign_id)
            gate["release_track_coverage"] = coverage
            if coverage.get("status") != "passed":
                gate.update(
                    {
                        "status": "failed",
                        "hard_block": True,
                        "message": "Audio Campaign does not cover the current release tracks.",
                    }
                )
            current_final_exports = self._release_audio_campaign_final_export_current(release)
            gate["release_track_final_exports"] = current_final_exports
            if current_final_exports.get("status") != "passed":
                gate.update(
                    {
                        "status": "failed",
                        "hard_block": True,
                        "message": "Release track Final Export evidence changed after the Audio Campaign was planned.",
                    }
                )
        return gate

    def _release_audio_campaign_coverage(self, release: Any, campaign_id: str) -> dict[str, Any]:
        try:
            case_index = read_json(self.audio_campaign_store.case_index_path(campaign_id))
        except Exception as exc:
            return {"status": "failed", "message": f"Audio Campaign case index is unavailable: {sanitize_sensitive_text(str(exc))}", "missing_tracks": []}
        return audio_campaign_release_track_coverage(release.tracks, case_index)

    def _release_audio_campaign_final_export_current(self, release: Any) -> dict[str, Any]:
        rows = []
        stale = []
        for track in sorted(release.tracks, key=lambda item: (getattr(item, "disc_number", 1), getattr(item, "track_number", 1), getattr(item, "track_id", ""))):
            project_id = str(getattr(track, "project_id", "") or "")
            recorded_hash = str(getattr(track, "final_export_hash", "") or "")
            manifest_path = final_export_dir(self.project_store.project_dir(project_id)) / "manifest.json"
            current_hash = _server_file_sha256(manifest_path) if manifest_path.exists() else ""
            current = bool(recorded_hash and current_hash and recorded_hash == current_hash)
            row = {
                "track_id": getattr(track, "track_id", None),
                "track_number": getattr(track, "track_number", None),
                "title": getattr(track, "title", None),
                "project_id": project_id,
                "version_id": getattr(track, "version_id", None),
                "final_export_hash": recorded_hash,
                "current_final_export_hash": current_hash or None,
                "current": current,
            }
            rows.append(row)
            if not current:
                stale.append(row)
        return {"status": "passed" if not stale else "failed", "track_count": len(rows), "current_track_count": len(rows) - len(stale), "stale_tracks": stale, "tracks": rows}

    def _release_audio_gate(self, release_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        require_health = bool(payload.get("require_audio_health", False))
        require_human = bool(payload.get("require_human_audio_review", False))
        require_per_track_review = bool(payload.get("require_per_track_audio_review", False))
        require_stem_health = bool(payload.get("require_stem_audio_health", False))
        require_current_mix = bool(payload.get("require_current_mix_state", False))
        require_audio_revision = bool(payload.get("require_audio_revision_closeout", False))
        require_current = bool(payload.get("require_audio_artifact_current", require_health or require_per_track_review))
        if not (require_health or require_human or require_per_track_review or require_current or require_stem_health or require_current_mix or require_audio_revision):
            return {}
        try:
            document = self.release_store.get_release(release_id)
            current_hash = release_audio_source_hash(document, project_store=self.project_store, release_store=self.release_store)
            report = read_release_audio_qa(self.release_store, release_id, default={})
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": f"Release Audio QA is unavailable: {sanitize_sensitive_text(str(exc))}"}
        summary = release_audio_summary(report)
        evidence: dict[str, Any] = {
            **summary,
            "require_audio_health": require_health,
            "require_human_audio_review": require_human,
            "require_per_track_audio_review": require_per_track_review,
            "require_audio_artifact_current": require_current,
            "require_stem_audio_health": require_stem_health,
            "require_current_mix_state": require_current_mix,
            "require_audio_revision_closeout": require_audio_revision,
        }
        revision_gate = self.audio_revision_store.gate(release_id, required=require_audio_revision, now=_utc_now())
        if require_audio_revision or revision_gate.get("session_count"):
            evidence["audio_revision"] = revision_gate
            if revision_gate.get("status") == "failed":
                return {**evidence, "status": "failed", "hard_block": True, "message": str(revision_gate.get("message") or "Audio revision closeout gate failed.")}
        mix_gate = self._release_mix_gate(release_id, require_stem_health=require_stem_health, require_current_mix=require_current_mix)
        if mix_gate:
            evidence["mix"] = mix_gate
            if mix_gate.get("status") == "failed":
                return {**evidence, "status": "failed", "hard_block": True, "message": str(mix_gate.get("message") or "Release mix gate failed.")}
        if require_health or require_per_track_review:
            if not report:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Release Audio QA is missing. Refresh audio QA before signoff."}
            if not release_audio_report_integrity_ok(report):
                return {**evidence, "status": "failed", "hard_block": True, "message": "Release Audio QA integrity failed. Refresh audio QA before signoff."}
            if require_current and report.get("source_hash") != current_hash:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Release Audio QA is stale. Refresh audio QA before signoff.", "current_source_hash": current_hash}
            if not release_audio_allows_signoff(report, current_source_hash=current_hash if require_current else None):
                return {**evidence, "status": "failed", "hard_block": True, "message": "Release Audio QA has blocking audio failures."}
        if require_per_track_review:
            per_track_gate = release_audio_review_gate(self.release_store, self.project_store, release_id, now=_utc_now())
            evidence["per_track_review"] = per_track_gate
            if per_track_gate.get("status") != "passed":
                return {**evidence, "status": "failed", "hard_block": True, "message": str(per_track_gate.get("message") or "Per-track audio review gate failed.")}
        if require_human:
            if require_per_track_review:
                per_track = evidence.get("per_track_review") if isinstance(evidence.get("per_track_review"), dict) else {}
                evidence["manual_audio_accepted_count"] = per_track.get("manual_accepted_track_count", 0)
            else:
                suite_id = str(payload.get("acceptance_suite_id") or "").strip()
                if not suite_id:
                    return {**evidence, "status": "failed", "hard_block": True, "message": "require_human_audio_review needs acceptance_suite_id."}
                try:
                    acceptance = self.acceptance_store.read_report(suite_id)
                except Exception as exc:
                    return {**evidence, "status": "failed", "hard_block": True, "message": f"Acceptance report is unavailable: {sanitize_sensitive_text(str(exc))}"}
                acceptance_summary = acceptance_report_summary(acceptance)
                evidence["manual_audio_accepted_count"] = acceptance_summary.get("manual_audio_accepted_count", 0)
                evidence["acceptance_status"] = acceptance_summary.get("acceptance_status")
                if int(acceptance_summary.get("manual_audio_accepted_count", 0) or 0) <= 0:
                    return {**evidence, "status": "failed", "hard_block": True, "message": "Human WAV listening review evidence is missing."}
        return {**evidence, "status": "passed", "message": "Release audio gate passed."}

    def _release_acceptance_analytics_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        report_id = str(payload.get("acceptance_analytics_report_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        try:
            if report_id:
                report = self.acceptance_analytics_store.get_report(report_id)
            elif release_id:
                report = self.acceptance_analytics_store.latest_report(AnalyticsScope.from_values(scope_type="release", release_id=release_id))
            else:
                return {}
        except (AcceptanceAnalyticsError, AcceptanceAnalyticsNotFoundError, ReleaseNotFoundError, ValueError):
            return {"status": "missing", "warning": "acceptance_analytics_unavailable"}
        return release_acceptance_analytics_evidence(report)

    def _release_acceptance_fix_sprint_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        fix_sprint_id = str(payload.get("acceptance_fix_sprint_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_acceptance_fix_sprint", False))
        try:
            if fix_sprint_id:
                sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
            elif release_id:
                summary = latest_fix_sprint_summary(self.acceptance_fix_sprint_store, release_id=release_id)
                if summary.get("status") == "missing":
                    return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Sprint evidence is missing."}
                sprint = self.acceptance_fix_sprint_store.read_sprint(str(summary.get("fix_sprint_id") or ""))
            else:
                return {}
            items = self.acceptance_fix_sprint_store.read_items(sprint.fix_sprint_id)
            closeout = self.acceptance_fix_sprint_store.read_closeout(sprint.fix_sprint_id, default={})
            summary = fix_sprint_summary(sprint, items)
            closeout_summary = acceptance_fix_closeout_summary(closeout)
            stale = self.acceptance_fix_sprint_store.sprint_is_stale(sprint)
            ok = sprint.status == "closed" and closeout_summary.get("status") in {"passed", "warning", "force_closed"}
            evidence = {**summary, "sprint_status": summary.get("status"), "stale": stale, "closeout": closeout_summary}
            if stale:
                return {**evidence, "status": "failed" if require_gate else "warning", "message": "Acceptance Fix Sprint source analytics is stale. Refresh analytics before signoff."}
            if require_gate and not ok:
                return {**evidence, "status": "failed", "message": "Acceptance Fix Sprint is not closed."}
            return {**evidence, "status": "passed" if ok else "warning" if summary.get("status") != "missing" else "missing"}
        except AcceptanceFixSprintNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Sprint evidence is missing."}
        except AcceptanceFixSprintError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_acceptance_fix_plan_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = str(payload.get("acceptance_fix_plan_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_acceptance_fix_plan", False))
        try:
            if plan_id:
                plan = self.acceptance_fix_plan_store.read_plan(plan_id)
                summary = fix_plan_summary(plan)
            elif release_id:
                summary = latest_fix_plan_summary(self.acceptance_fix_plan_store, release_id=release_id)
                if summary.get("status") == "missing":
                    return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Plan evidence is missing."}
                plan = self.acceptance_fix_plan_store.read_plan(str(summary.get("plan_id") or ""))
            else:
                return {}
            stale = self.acceptance_fix_plan_store.plan_is_stale(plan)
            status = "passed" if plan.status in {"ready", "used", "warning"} and not stale else "warning"
            evidence = {**summary, "stale": stale}
            if stale:
                return {**evidence, "status": "failed" if require_gate else "warning", "message": "Acceptance Fix Plan is stale. Refresh the plan before signoff."}
            if require_gate and plan.status not in {"ready", "used", "warning"}:
                return {**evidence, "status": "failed", "message": "Acceptance Fix Plan is not ready."}
            return {**evidence, "status": status}
        except AcceptanceFixPlanNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Plan evidence is missing."}
        except AcceptanceFixPlanError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_acceptance_fix_plan_review_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        review_id = str(payload.get("acceptance_fix_plan_review_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_acceptance_fix_plan_review", False))
        try:
            if review_id:
                review = self.acceptance_fix_plan_review_store.read_review(review_id)
                summary = fix_plan_review_summary(review)
            elif release_id:
                summary = latest_fix_plan_review_summary(self.acceptance_fix_plan_review_store, release_id=release_id)
                if summary.get("status") == "missing":
                    return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Plan Outcome Review evidence is missing."}
                review = self.acceptance_fix_plan_review_store.read_review(str(summary.get("review_id") or ""))
            else:
                return {}
            stale = self.acceptance_fix_plan_review_store.review_is_stale(review)
            scope = review.scope if isinstance(review.scope, dict) else {}
            scope_ok = not release_id or scope.get("release_id") == release_id
            evidence = {**summary, "stale": stale}
            if stale:
                return {**evidence, "status": "failed" if require_gate else "warning", "message": "Acceptance Fix Plan Outcome Review is stale. Refresh the review before signoff."}
            if require_gate and review.status in {"blocked", "archived", "stale"}:
                return {**evidence, "status": "failed", "message": "Acceptance Fix Plan Outcome Review is not ready."}
            if require_gate and not scope_ok:
                return {**evidence, "status": "failed", "message": "Acceptance Fix Plan Outcome Review is not scoped to this release."}
            return {**evidence, "status": "passed" if review.status in REVIEW_READY_STATUSES else "warning"}
        except AcceptanceFixPlanReviewNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Plan Outcome Review evidence is missing."}
        except AcceptanceFixPlanReviewError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_acceptance_kb_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        release_id = str(payload.get("release_id") or "").strip()
        if not release_id:
            return {}
        try:
            summary = self.acceptance_kb_store.summary(release_id=release_id)
            status = "warning" if summary.get("stale") else "available" if int(summary.get("entry_count") or 0) else "missing"
            return {**summary, "status": status}
        except AcceptanceKnowledgeBaseError as exc:
            return {"status": "warning", "message": str(exc)}

    def _release_planning_rule_simulation_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        simulation_id = str(payload.get("planning_simulation_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_planning_rule_simulation", False))
        try:
            if simulation_id:
                simulation = self.planning_rule_simulation_store.read_simulation(simulation_id)
                summary = planning_simulation_summary(simulation)
            elif release_id:
                summary = self.planning_rule_simulation_store.latest_summary(release_id=release_id)
                if summary.get("status") == "missing":
                    return {"status": "failed" if require_gate else "missing", "message": "Planning Rule Simulation evidence is missing."}
                simulation = self.planning_rule_simulation_store.read_simulation(str(summary.get("simulation_id") or ""))
            else:
                return {}
            stale = self.planning_rule_simulation_store.simulation_is_stale(simulation)
            scope = simulation.scope if isinstance(simulation.scope, dict) else {}
            scope_ok = not release_id or scope.get("release_id") == release_id or self._planning_simulation_reviews_match_release(simulation, release_id)
            evidence = {**summary, "stale": stale}
            if stale:
                return {**evidence, "status": "failed" if require_gate else "warning", "message": "Planning Rule Simulation is stale. Refresh the simulation before signoff."}
            if require_gate and simulation.status in {"blocked", "archived", "stale"}:
                return {**evidence, "status": "failed", "message": "Planning Rule Simulation is not ready."}
            if require_gate and not scope_ok:
                return {**evidence, "status": "failed", "message": "Planning Rule Simulation is not scoped to this release."}
            status = "passed" if simulation.status in {"ready", "warning"} else "warning"
            if summary.get("recommendation") == "candidate_worse":
                return {**evidence, "status": status, "message": "Planning Rule Simulation candidate is worse; review before adopting rules."}
            return {**evidence, "status": status}
        except PlanningRuleSimulationNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Planning Rule Simulation evidence is missing."}
        except PlanningRuleSimulationError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_planning_rule_governance_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        require_gate = bool(payload.get("require_planning_rule_governance", False))
        requested_version_id = str(payload.get("planning_rule_version_id") or "").strip()
        force = bool(payload.get("force", False))
        try:
            active = self.planning_rule_governance_store.active_version()
            if active is None:
                return {"status": "failed" if require_gate else "missing", "message": "Planning Rule Governance active version is missing."}
            summary = self.planning_rule_governance_store.active_summary()
            evidence_stale = self.planning_rule_governance_store.version_evidence_is_stale(active)
            frozen_integrity_ok = self.planning_rule_governance_store.frozen_ruleset_integrity_ok(active)
            version_source_integrity_ok = self.planning_rule_governance_store.version_source_integrity_ok(active)
            integrity_ok = frozen_integrity_ok and version_source_integrity_ok
            evidence = {**summary, "evidence_stale": evidence_stale, "integrity_ok": integrity_ok, "frozen_ruleset_integrity_ok": frozen_integrity_ok, "version_source_integrity_ok": version_source_integrity_ok}
            if active.status in {"rolled_back", "archived"}:
                return {**evidence, "status": "failed", "message": "Planning Rule Governance active version is not active."}
            if evidence_stale:
                return {**evidence, "status": "failed" if require_gate else "warning", "message": "Planning Rule Governance simulation evidence is stale."}
            if not frozen_integrity_ok:
                return {**evidence, "status": "failed", "message": "Planning Rule Governance frozen ruleset integrity failed."}
            if not version_source_integrity_ok:
                return {**evidence, "status": "failed", "message": "Planning Rule Governance version source integrity failed."}
            if requested_version_id and requested_version_id != active.version_id:
                if not force:
                    return {**evidence, "status": "failed" if require_gate else "warning", "message": "Requested Planning Rule Version is not active."}
                if not str(payload.get("override_reason") or "").strip():
                    return {**evidence, "status": "failed", "message": "override_reason is required when forcing Planning Rule Version mismatch."}
                return {**evidence, "status": "warning", "message": "Planning Rule Version mismatch was force-accepted."}
            return {**evidence, "status": "passed"}
        except PlanningRuleGovernanceError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_planning_rule_impact_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        report_id = str(payload.get("planning_rule_impact_report_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_planning_rule_impact", False))
        force = bool(payload.get("force", False))
        allow_warning = bool(payload.get("allow_impact_warning", False))
        override_reason = str(payload.get("override_reason") or "").strip()
        min_manual_reviews = max(0, int(payload.get("impact_min_manual_reviews") or 1))
        try:
            if report_id:
                report = self.planning_rule_impact_store.get_report(report_id)
            elif release_id:
                summary = self.planning_rule_impact_store.latest_summary(release_id=release_id)
                if summary.get("status") == "missing":
                    return {"status": "failed" if require_gate else "missing", "message": "Planning Rule Impact evidence is missing."}
                report = self.planning_rule_impact_store.get_report(str(summary.get("report_id") or ""))
            else:
                return {}
            raw_status = report.status
            summary = planning_rule_impact_summary(report)
            stale = self.planning_rule_impact_store.report_is_stale(report)
            integrity_ok = self.planning_rule_impact_store.report_integrity_ok(report)
            active = self.planning_rule_governance_store.active_version()
            active_id = active.version_id if active else None
            recommendation = str(summary.get("recommendation") or "")
            evidence = {
                **summary,
                "stale": stale,
                "integrity_ok": integrity_ok,
                "expected_integrity_hash": report.integrity_hash,
                "actual_integrity_hash": planning_rule_impact_report_hash(report),
                "current_active_version_id": active_id,
            }
            if not integrity_ok:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Planning Rule Impact report integrity failed. Refresh impact monitoring before signoff."}
            if stale:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Planning Rule Impact report is stale. Refresh impact monitoring before signoff."}
            if active_id and summary.get("active_version_id") != active_id:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Planning Rule Impact report does not match the current active Planning Rule Version."}
            active_report_version = report.active_version if isinstance(report.active_version, dict) else {}
            if active_report_version.get("integrity_ok") is False:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Planning Rule Impact active version integrity failed."}
            if raw_status in {"archived", "stale"}:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Planning Rule Impact report is not ready."}
            if recommendation == "rollback_recommended":
                if not force or not override_reason:
                    return {**evidence, "status": "failed", "message": "Planning Rule Impact recommends rollback."}
                return {**evidence, "status": "warning", "message": "Planning Rule Impact rollback recommendation was force-accepted."}
            if recommendation == "rollback_watch" and not (allow_warning or force):
                return {**evidence, "status": "failed" if require_gate else "warning", "message": "Planning Rule Impact is on rollback watch."}
            if recommendation == "increase_manual_review" and int(summary.get("manual_review_count") or 0) < min_manual_reviews:
                if not force or not override_reason:
                    return {**evidence, "status": "failed" if require_gate else "warning", "message": "Planning Rule Impact requires more manual review evidence."}
                return {**evidence, "status": "warning", "message": "Planning Rule Impact manual review warning was force-accepted."}
            if raw_status == "failed":
                return {**evidence, "status": "failed", "message": "Planning Rule Impact report is not ready."}
            if require_gate and raw_status == "missing":
                return {**evidence, "status": "failed", "message": "Planning Rule Impact evidence is missing."}
            return {**evidence, "status": "passed" if raw_status in {"ready", "warning"} else "warning"}
        except PlanningRuleImpactNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Planning Rule Impact evidence is missing."}
        except (PlanningRuleImpactError, PlanningRuleGovernanceError, ValueError) as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _planning_simulation_reviews_match_release(self, simulation: Any, release_id: str) -> bool:
        source = simulation.source if hasattr(simulation, "source") and isinstance(simulation.source, dict) else {}
        review_ids = source.get("review_ids") if isinstance(source.get("review_ids"), list) else []
        if not review_ids:
            return False
        for review_id in review_ids:
            try:
                review = self.acceptance_fix_plan_review_store.read_review(str(review_id))
            except AcceptanceFixPlanReviewError:
                return False
            if review.scope.get("release_id") != release_id:
                return False
        return True

    def _handle_acceptance_route(self, method: str, suite_id: str, tail: str) -> None:
        try:
            parts = [part for part in tail.strip("/").split("/") if part]
            if not parts:
                if method == "GET":
                    suite = self.acceptance_store.get_suite(suite_id)
                    cases = self.acceptance_store.list_cases(suite_id)
                    self._send_json({"ok": True, "suite": suite.to_dict(), "cases": [case.to_dict() for case in cases], "summary": acceptance_suite_summary(suite), "events": self.acceptance_store.read_events(suite_id)})
                    return
                if method == "POST":
                    suite = self.acceptance_store.get_suite(suite_id)
                    self.acceptance_store.ensure_mutable(suite)
                    payload = self._optional_json_body()
                    if payload.get("name"):
                        suite.name = str(payload.get("name"))
                    if payload.get("mode"):
                        suite.mode = str(payload.get("mode"))
                    if payload.get("min_rating") is not None:
                        suite.min_rating = int(payload.get("min_rating"))
                    suite = self.acceptance_store.save_suite(suite)
                    self._send_json({"ok": True, "suite": suite.to_dict(), "summary": acceptance_suite_summary(suite)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if parts == ["cases"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                case = self.acceptance_store.add_case(suite_id, self._read_json_body())
                self._send_json({"ok": True, "case": case.to_dict(), "summary": acceptance_suite_summary(self.acceptance_store.get_suite(suite_id))}, status=HTTPStatus.CREATED)
                return

            if parts == ["report"]:
                if method == "GET":
                    report = self.acceptance_store.read_report(suite_id, default={})
                    self._send_json({"ok": True, "suite_id": suite_id, "report": report, "summary": acceptance_report_summary(report)})
                    return
                if method == "POST":
                    report = self.acceptance_store.build_report(suite_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "report": report, "summary": acceptance_report_summary(report)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if parts == ["signoff"]:
                if method == "GET":
                    signoff = self.acceptance_store.read_signoff(suite_id, default={})
                    self._send_json({"ok": True, "suite_id": suite_id, "signoff": signoff, "summary": acceptance_signoff_summary(signoff)})
                    return
                if method == "POST":
                    signoff = self.acceptance_store.signoff(suite_id, self._optional_json_body())
                    self._send_json({"ok": True, "suite_id": suite_id, "signoff": signoff, "summary": acceptance_signoff_summary(signoff)})
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if parts == ["signoff", "reset"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                reason = str(payload.get("reason") or "").strip()
                if not reason:
                    self._send_error(HTTPStatus.BAD_REQUEST, "reason is required.")
                    return
                event = self.acceptance_store.reset_signoff(suite_id, reason)
                self._send_json({"ok": True, "suite_id": suite_id, "summary": {"status": "reset"}, "history_event": event})
                return

            if parts == ["archive"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                suite = self.acceptance_store.archive_suite(suite_id)
                self._send_json({"ok": True, "suite": suite.to_dict(), "summary": acceptance_suite_summary(suite)})
                return

            if parts == ["diff"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                other_suite_id = str(payload.get("other_suite_id") or payload.get("left_suite_id") or "").strip()
                if not other_suite_id:
                    self._send_error(HTTPStatus.BAD_REQUEST, "other_suite_id is required.")
                    return
                left = self.acceptance_store.read_report(other_suite_id)
                right = self.acceptance_store.read_report(suite_id)
                diff = build_acceptance_diff(left, right)
                self._send_json({"ok": True, "suite_id": suite_id, "other_suite_id": other_suite_id, "diff": diff, "summary": diff.get("summary", {})})
                return

            if parts == ["analytics"]:
                self._handle_suite_acceptance_analytics(method, suite_id)
                return

            if parts == ["analytics", "refresh"]:
                self._handle_suite_acceptance_analytics_refresh(method, suite_id)
                return

            if parts == ["human-review-packs"]:
                if method == "GET":
                    packs = self.human_review_pack_store.list_packs(suite_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "packs": packs, "summary": {"pack_count": len(packs)}})
                    return
                if method == "POST":
                    result = self.human_review_pack_store.create_pack(suite_id, self._optional_json_body())
                    self._send_json({"ok": True, "suite_id": suite_id, **result}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if len(parts) >= 2 and parts[0] == "human-review-packs":
                pack_id = parts[1]
                action = parts[2] if len(parts) >= 3 else ""
                if not action:
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    pack = self.human_review_pack_store.get_pack(suite_id, pack_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "pack": pack})
                    return
                if action == "zip":
                    if method == "POST":
                        result = self.human_review_pack_store.build_zip(suite_id, pack_id)
                        self._send_json({"ok": True, "suite_id": suite_id, **result})
                        return
                    if method == "GET":
                        self._send_file(self.human_review_pack_store.zip_path(suite_id, pack_id), "application/zip", filename=f"{suite_id}-{pack_id}-human-review-pack.zip")
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "verify":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    report = self.human_review_pack_store.verify_pack(suite_id, pack_id, strict=bool(payload.get("strict", False)))
                    self._send_json({"ok": report.get("status") == "passed", "suite_id": suite_id, "pack_id": pack_id, "report": report, "summary": report.get("summary", {})})
                    return

            if parts == ["review-imports"]:
                if method == "GET":
                    imports = self.human_review_pack_store.list_imports(suite_id)
                    self._send_json({"ok": True, "suite_id": suite_id, "imports": imports, "summary": {"import_count": len(imports)}})
                    return
                if method == "POST":
                    record = self.human_review_pack_store.import_response(suite_id, self._read_json_body())
                    self._send_json({"ok": True, "suite_id": suite_id, "import": record, "summary": record.get("summary", {})}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if len(parts) == 2 and parts[0] == "review-imports":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                record = self.human_review_pack_store.get_import(suite_id, parts[1])
                self._send_json({"ok": True, "suite_id": suite_id, "import": record, "summary": record.get("summary", {})})
                return

            if len(parts) >= 2 and parts[0] == "cases":
                case_id = parts[1]
                action = parts[2] if len(parts) >= 3 else ""
                if not action:
                    case = self.acceptance_store.get_case(suite_id, case_id)
                    self._send_json({"ok": True, "case": case.to_dict(), "health": self.acceptance_store.read_health(suite_id, case_id, default={}), "review": self.acceptance_store.read_review(suite_id, case_id, default={})})
                    return
                if action == "generate":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    case = self.acceptance_store.generate_case(suite_id, case_id, render_audio_mode=str(payload.get("render_audio") or "auto"))
                    self._send_json({"ok": True, "case": case.to_dict()})
                    return
                if action == "health":
                    if method == "GET":
                        report = self.acceptance_store.read_health(suite_id, case_id, default={})
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "health": report})
                        return
                    if method == "POST":
                        report = self.acceptance_store.run_health(suite_id, case_id)
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "health": report})
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "render-audio":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._optional_json_body()
                    profile = self._renderer_profile_from_payload(payload)
                    config = profile.to_renderer_config() if profile is not None else None
                    result = self.acceptance_store.render_audio(suite_id, case_id, mode=str(payload.get("mode") or "auto"), config=config)
                    self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, **result})
                    return
                if action == "review":
                    if method == "GET":
                        review = self.acceptance_store.read_review(suite_id, case_id, default={})
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "review": review, "summary": listening_review_summary(review)})
                        return
                    if method == "POST":
                        review = self.acceptance_store.write_review(suite_id, case_id, self._read_json_body())
                        self._send_json({"ok": True, "suite_id": suite_id, "case_id": case_id, "review": review, "summary": listening_review_summary(review)})
                        return
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if action == "midi":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.acceptance_store.case_dir(suite_id, case_id) / "song.mid", "audio/midi", filename=f"{suite_id}-{case_id}.mid")
                    return
                if action == "audio":
                    if method != "GET":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    self._send_file(self.acceptance_store.case_dir(suite_id, case_id) / "song.wav", "audio/wav", filename=f"{suite_id}-{case_id}.wav")
                    return

            self._send_error(HTTPStatus.NOT_FOUND, "Acceptance route not found.")
        except AcceptanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except HumanReviewPackStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AcceptanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except HumanReviewPackNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except HumanReviewPackValidationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_suite_acceptance_analytics(self, method: str, suite_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "suite_id": suite_id, "analytics": report, "summary": acceptance_analytics_summary(report)})
        except AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (AcceptanceAnalyticsError, AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_suite_acceptance_analytics_refresh(self, method: str, suite_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = AnalyticsScope.from_values(scope_type="suite", suite_id=suite_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_utc_now())
            self._send_json({"ok": True, "suite_id": suite_id, "analytics": report, "summary": acceptance_analytics_summary(report)}, status=HTTPStatus.CREATED)
        except (AcceptanceAnalyticsError, AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_acceptance_analytics(self, method: str, project_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            scope = AnalyticsScope.from_values(scope_type="project", project_id=project_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "project_id": project_id, "analytics": report, "summary": acceptance_analytics_summary(report)})
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except (AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_acceptance_analytics_refresh(self, method: str, project_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.project_store.get_project(project_id)
            scope = AnalyticsScope.from_values(scope_type="project", project_id=project_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_utc_now())
            self._send_json({"ok": True, "project_id": project_id, "analytics": report, "summary": acceptance_analytics_summary(report)}, status=HTTPStatus.CREATED)
        except FileNotFoundError:
            self._send_error(HTTPStatus.NOT_FOUND, "Project not found.")
        except (AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_acceptance_analytics(self, method: str, release_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.release_store.get_release(release_id)
            scope = AnalyticsScope.from_values(scope_type="release", release_id=release_id)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "release_id": release_id, "analytics": report, "summary": acceptance_analytics_summary(report)})
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (AcceptanceAnalyticsError, AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_release_acceptance_analytics_refresh(self, method: str, release_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            self.release_store.get_release(release_id)
            scope = AnalyticsScope.from_values(scope_type="release", release_id=release_id)
            report = self.acceptance_analytics_store.refresh(scope, now=_utc_now())
            self._send_json({"ok": True, "release_id": release_id, "analytics": report, "summary": acceptance_analytics_summary(report)}, status=HTTPStatus.CREATED)
        except ReleaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (AcceptanceAnalyticsError, AcceptanceNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_root(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            scope = _analytics_scope_from_query(query_string)
            report = self.acceptance_analytics_store.latest_report(scope)
            self._send_json({"ok": True, "analytics": report, "summary": acceptance_analytics_summary(report)})
        except AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (AcceptanceAnalyticsError, AcceptanceNotFoundError, ReleaseNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_refresh(self, method: str, query_string: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            payload = self._optional_json_body()
            query = parse_qs(query_string)
            scope = AnalyticsScope.from_values(
                scope_type=str(payload.get("scope") or _query_value(query, "scope") or "global"),
                suite_id=payload.get("suite_id") or _query_value(query, "suite_id") or None,
                release_id=payload.get("release_id") or _query_value(query, "release_id") or None,
                project_id=payload.get("project_id") or _query_value(query, "project_id") or None,
            )
            report = self.acceptance_analytics_store.refresh(scope, now=_utc_now())
            self._send_json({"ok": True, "analytics": report, "summary": acceptance_analytics_summary(report)}, status=HTTPStatus.CREATED)
        except (AcceptanceAnalyticsError, AcceptanceNotFoundError, ReleaseNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_report(self, method: str, report_id: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            report = self.acceptance_analytics_store.get_report(report_id)
            self._send_json({"ok": True, "analytics": report, "summary": acceptance_analytics_summary(report)})
        except AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceAnalyticsError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_recommendation(self, method: str, report_id: str, recommendation_id: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            result = self.acceptance_analytics_store.create_review_task_from_recommendation(report_id, recommendation_id, self._optional_json_body())
            status = HTTPStatus.CREATED if result.get("status") == "created" else HTTPStatus.OK
            self._send_json({"ok": True, **result}, status=status)
        except AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceAnalyticsStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (AcceptanceAnalyticsError, FileNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_sprints_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _query_value(query, "status") or None
                sprints = self.acceptance_fix_sprint_store.list_sprints(include_archived=include_archived, status=status)
                self._send_json(
                    {
                        "ok": True,
                        "fix_sprints": [sprint.to_dict() for sprint in sprints],
                        "summary": {"fix_sprint_count": len(sprints), "latest": fix_sprint_summary(sprints[0]) if sprints else {"status": "missing"}},
                    }
                )
                return
            if method == "POST":
                sprint = self.acceptance_fix_sprint_store.create_from_analytics(self._read_json_body())
                items = self.acceptance_fix_sprint_store.read_items(sprint.fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except AcceptanceFixSprintNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceFixSprintStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (AcceptanceFixSprintError, AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plans_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _query_value(query, "status")
                plans = self.acceptance_fix_plan_store.list_plans(include_archived=include_archived, status=status)
                self._send_json({"ok": True, "fix_plans": [plan.to_dict() for plan in plans], "summary": {"plan_count": len(plans)}})
                return
            if method == "POST":
                plan = self.acceptance_fix_plan_store.create(self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except AcceptanceFixPlanStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (AcceptanceFixPlanError, AcceptanceAnalyticsError, AcceptanceKnowledgeBaseError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plans_recommend(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            preview = self.acceptance_fix_plan_store.preview(self._optional_json_body(), now=_utc_now())
            self._send_json({"ok": True, "fix_plan_preview": preview, "summary": fix_plan_summary(preview)})
        except AcceptanceFixPlanStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (AcceptanceFixPlanError, AcceptanceAnalyticsError, AcceptanceKnowledgeBaseError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plan_reviews_root(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
            status = _query_value(query, "status") or None
            release_id = _query_value(query, "release_id") or None
            project_id = _query_value(query, "project_id") or None
            reviews = self.acceptance_fix_plan_review_store.list_reviews(include_archived=include_archived, status=status, release_id=release_id, project_id=project_id)
            self._send_json({"ok": True, "outcome_reviews": [review.to_dict() for review in reviews], "summary": {"review_count": len(reviews), "latest": fix_plan_review_summary(reviews[0]) if reviews else {"status": "missing"}}})
        except AcceptanceFixPlanReviewError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plan_review_route(self, method: str, route: tuple[str, str]) -> None:
        review_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.acceptance_fix_plan_review_store.read_review(review_id)
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": fix_plan_review_summary(review)})
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.acceptance_fix_plan_review_store.refresh_review(review_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": fix_plan_review_summary(review)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.acceptance_fix_plan_review_store.archive_review(review_id, now=_utc_now())
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": fix_plan_review_summary(review)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Acceptance Fix Plan Outcome Review route not found.")
        except AcceptanceFixPlanReviewNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceFixPlanReviewStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AcceptanceFixPlanReviewError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rulesets_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
                rulesets = self.planning_rule_simulation_store.list_rulesets(include_archived=include_archived)
                self._send_json({"ok": True, "rulesets": [ruleset.to_dict() for ruleset in rulesets], "summary": {"ruleset_count": len(rulesets)}})
                return
            if method == "POST":
                ruleset = self.planning_rule_simulation_store.create_ruleset(self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except PlanningRuleSimulationStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleSimulationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_ruleset_route(self, method: str, route: tuple[str, str]) -> None:
        ruleset_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                ruleset = self.planning_rule_simulation_store.read_ruleset(ruleset_id)
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)})
                return
            if action == "clone":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                ruleset = self.planning_rule_simulation_store.clone_ruleset(ruleset_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}, status=HTTPStatus.CREATED)
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                ruleset = self.planning_rule_simulation_store.archive_ruleset(ruleset_id, now=_utc_now())
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)})
                return
            if action == "validate":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "validation": self.planning_rule_simulation_store.validate_ruleset(ruleset_id)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Planning Rule Set route not found.")
        except PlanningRuleSimulationNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PlanningRuleSimulationStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleSimulationError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_simulations_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _query_value(query, "status") or None
                release_id = _query_value(query, "release_id") or None
                project_id = _query_value(query, "project_id") or None
                simulations = self.planning_rule_simulation_store.list_simulations(include_archived=include_archived, status=status, release_id=release_id, project_id=project_id)
                self._send_json({"ok": True, "simulations": [simulation.to_dict() for simulation in simulations], "summary": {"simulation_count": len(simulations), "latest": planning_simulation_summary(simulations[0]) if simulations else {"status": "missing"}}})
                return
            if method == "POST":
                simulation = self.planning_rule_simulation_store.create_simulation(self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except PlanningRuleSimulationStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleSimulationNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (PlanningRuleSimulationError, AcceptanceFixPlanReviewError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_simulation_route(self, method: str, route: tuple[str, str]) -> None:
        simulation_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                simulation = self.planning_rule_simulation_store.read_simulation(simulation_id)
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)})
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                simulation = self.planning_rule_simulation_store.refresh_simulation(simulation_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                simulation = self.planning_rule_simulation_store.archive_simulation(simulation_id, now=_utc_now())
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Planning Rule Simulation route not found.")
        except PlanningRuleSimulationNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PlanningRuleSimulationStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (PlanningRuleSimulationError, AcceptanceFixPlanReviewError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_active(self, method: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        version = self.planning_rule_governance_store.active_version()
        active = self.planning_rule_governance_store.active_pointer()
        summary = self.planning_rule_governance_store.active_summary()
        self._send_json({"ok": True, "active": active, "version": version.to_dict() if version else {}, "summary": summary})

    def _handle_planning_rule_governance_versions(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = parse_qs(query_string)
        include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
        status = _query_value(query, "status") or None
        versions = self.planning_rule_governance_store.list_versions(include_archived=include_archived, status=status)
        self._send_json({"ok": True, "versions": [version.to_dict() for version in versions], "summary": {"version_count": len(versions), "active": self.planning_rule_governance_store.active_summary()}})

    def _handle_planning_rule_governance_version_route(self, method: str, route: tuple[str, str]) -> None:
        version_id, action = route
        try:
            if action or method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED if action else HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            version = self.planning_rule_governance_store.read_version(version_id)
            frozen = self.planning_rule_governance_store.frozen_ruleset(version_id)
            active = self.planning_rule_governance_store.active_pointer()
            self._send_json({"ok": True, "version": version.to_dict(), "frozen_ruleset_summary": ruleset_summary(frozen), "summary": governance_summary(version, active=active, evidence_stale=self.planning_rule_governance_store.version_evidence_is_stale(version))})
        except PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PlanningRuleGovernanceError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_promotions(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _query_value(query, "status") or None
                promotions = self.planning_rule_governance_store.list_promotions(include_archived=include_archived, status=status)
                self._send_json({"ok": True, "promotions": [promotion.to_dict() for promotion in promotions], "summary": {"promotion_count": len(promotions)}})
                return
            if method == "POST":
                promotion = self.planning_rule_governance_store.create_promotion(self._read_json_body(), now=_utc_now())
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except PlanningRuleGovernanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (PlanningRuleGovernanceError, PlanningRuleSimulationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_promotion_route(self, method: str, route: tuple[str, str]) -> None:
        promotion_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                promotion = self.planning_rule_governance_store.read_promotion(promotion_id)
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)})
                return
            if action == "approve":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                promotion = self.planning_rule_governance_store.approve_promotion(promotion_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)})
                return
            if action == "reject":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                promotion = self.planning_rule_governance_store.reject_promotion(promotion_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)})
                return
            if action == "promote":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.planning_rule_governance_store.promote(promotion_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "version": result["version"].to_dict(), "active": result["active"], "promotion": result["promotion"].to_dict(), "summary": result["summary"]}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Planning Rule Governance promotion route not found.")
        except PlanningRuleGovernanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (PlanningRuleGovernanceError, PlanningRuleSimulationError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_rollback(self, method: str) -> None:
        if method != "POST":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            result = self.planning_rule_governance_store.rollback(self._read_json_body(), now=_utc_now())
            self._send_json({"ok": True, "version": result["version"].to_dict(), "active": result["active"], "summary": result["summary"]})
        except PlanningRuleGovernanceStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except (PlanningRuleGovernanceError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_events(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = parse_qs(query_string)
        limit = int(_query_value(query, "limit") or 50)
        events = self.planning_rule_governance_store.events(limit=limit)
        self._send_json({"ok": True, "events": events, "summary": {"event_count": len(events)}})

    def _handle_planning_rule_impact_reports(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = parse_qs(query_string)
                include_archived = _query_value(query, "include_archived") in {"1", "true", "yes"}
                release_id = _query_value(query, "release_id") or None
                project_id = _query_value(query, "project_id") or None
                reports = self.planning_rule_impact_store.list_reports(include_archived=include_archived, release_id=release_id, project_id=project_id)
                self._send_json({"ok": True, "reports": [report.to_dict() for report in reports], "summary": {"report_count": len(reports), "latest": planning_rule_impact_summary(reports[0]) if reports else {"status": "missing"}}})
                return
            if method == "POST":
                report = self.planning_rule_impact_store.refresh(self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except PlanningRuleImpactStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleImpactError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_impact_latest(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = parse_qs(query_string)
        summary = self.planning_rule_impact_store.latest_summary(release_id=_query_value(query, "release_id") or None, project_id=_query_value(query, "project_id") or None)
        self._send_json({"ok": True, "summary": summary})

    def _handle_planning_rule_impact_report_route(self, method: str, route: tuple[str, str]) -> None:
        report_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.planning_rule_impact_store.get_report(report_id)
                integrity_ok = self.planning_rule_impact_store.report_integrity_ok(report)
                self._send_json(
                    {
                        "ok": True,
                        "impact_report": report.to_dict(),
                        "summary": planning_rule_impact_summary(report),
                        "stale": self.planning_rule_impact_store.report_is_stale(report),
                        "integrity_ok": integrity_ok,
                        "integrity": {
                            "ok": integrity_ok,
                            "expected_integrity_hash": report.integrity_hash,
                            "actual_integrity_hash": planning_rule_impact_report_hash(report),
                        },
                    }
                )
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.planning_rule_impact_store.refresh_report(report_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.planning_rule_impact_store.archive_report(report_id, now=_utc_now())
                self._send_json({"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Planning Rule Impact route not found.")
        except PlanningRuleImpactNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except PlanningRuleImpactStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except PlanningRuleImpactError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plan_route(self, method: str, route: tuple[str, str]) -> None:
        plan_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.acceptance_fix_plan_store.read_plan(plan_id)
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)})
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.acceptance_fix_plan_store.refresh_plan(plan_id, now=_utc_now())
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.acceptance_fix_plan_store.archive_plan(plan_id, now=_utc_now())
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)})
                return
            if action == "create-fix-sprint":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.acceptance_fix_plan_store.create_fix_sprint(plan_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return
            if action == "outcome-review":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.acceptance_fix_plan_review_store.get_or_missing_for_plan(plan_id)
                self._send_json({"ok": True, "outcome_review": review, "summary": fix_plan_review_summary(review)})
                return
            if action == "outcome-review/refresh":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.acceptance_fix_plan_review_store.refresh_for_plan(plan_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": fix_plan_review_summary(review)}, status=HTTPStatus.CREATED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Acceptance Fix Plan route not found.")
        except AcceptanceFixPlanNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceFixPlanStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AcceptanceFixPlanReviewStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except AcceptanceFixPlanReviewError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
        except (AcceptanceFixPlanError, AcceptanceAnalyticsError, AcceptanceKnowledgeBaseError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_sprint_route(self, method: str, route: tuple[str, list[str]]) -> None:
        fix_sprint_id, parts = route
        try:
            if not parts:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
                items = self.acceptance_fix_sprint_store.read_items(fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)})
                return

            if parts == ["archive"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = self.acceptance_fix_sprint_store.archive_sprint(fix_sprint_id, now=_utc_now())
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "summary": fix_sprint_summary(sprint)})
                return

            if parts == ["refresh-status"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                sprint = self.acceptance_fix_sprint_store.refresh_status(fix_sprint_id, now=_utc_now())
                items = self.acceptance_fix_sprint_store.read_items(fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)})
                return

            if parts == ["items"]:
                if method == "GET":
                    items = self.acceptance_fix_sprint_store.read_items(fix_sprint_id)
                    sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
                    self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)})
                    return
                if method == "POST":
                    item = self.acceptance_fix_sprint_store.add_item(fix_sprint_id, self._read_json_body(), now=_utc_now())
                    self._send_json({"ok": True, "item": item.to_dict()}, status=HTTPStatus.CREATED)
                    return
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return

            if len(parts) >= 3 and parts[0] == "items":
                item_id = parts[1]
                action = parts[2]
                if action == "waive":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    payload = self._read_json_body()
                    item = self.acceptance_fix_sprint_store.waive_item(fix_sprint_id, item_id, str(payload.get("reason") or payload.get("notes") or ""), now=_utc_now())
                    self._send_json({"ok": True, "item": item.to_dict()})
                    return
                if action == "reopen":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    item = self.acceptance_fix_sprint_store.reopen_item(fix_sprint_id, item_id, now=_utc_now())
                    self._send_json({"ok": True, "item": item.to_dict()})
                    return
                if action == "create-review-task":
                    if method != "POST":
                        self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                        return
                    result = self.acceptance_fix_sprint_store.create_review_tasks(fix_sprint_id, item_id=item_id, now=_utc_now())
                    created = any(row.get("status") == "created" for row in result.get("results", []) if isinstance(row, dict))
                    self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED if created else HTTPStatus.OK)
                    return
                self._send_error(HTTPStatus.NOT_FOUND, "Acceptance Fix Sprint item route not found.")
                return

            if parts == ["create-review-tasks"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.acceptance_fix_sprint_store.create_review_tasks(fix_sprint_id, now=_utc_now())
                created = any(row.get("status") == "created" for row in result.get("results", []) if isinstance(row, dict))
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED if created else HTTPStatus.OK)
                return

            if parts == ["create-recheck-suite"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.acceptance_fix_sprint_store.create_recheck_suite(fix_sprint_id, self._optional_json_body(), now=_utc_now())
                self._send_json({"ok": True, **result}, status=HTTPStatus.CREATED)
                return

            if parts == ["link-recheck-suite"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._read_json_body()
                sprint = self.acceptance_fix_sprint_store.link_recheck_suite(fix_sprint_id, str(payload.get("suite_id") or ""), now=_utc_now())
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "summary": fix_sprint_summary(sprint)})
                return

            if parts == ["delta"]:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                delta = self.acceptance_fix_sprint_store.read_delta(fix_sprint_id)
                self._send_json({"ok": True, "delta_report": delta, "summary": delta.get("summary", {})})
                return

            if parts == ["delta", "refresh"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                delta = self.acceptance_fix_sprint_store.refresh_delta(fix_sprint_id, now=_utc_now())
                self._send_json({"ok": True, "delta_report": delta, "summary": delta.get("summary", {})})
                return

            if parts == ["closeout"]:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.acceptance_fix_sprint_store.read_closeout(fix_sprint_id)
                self._send_json({"ok": True, "closeout_report": closeout, "summary": acceptance_fix_closeout_summary(closeout)})
                return

            if parts == ["close"]:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                closeout = self.acceptance_fix_sprint_store.close(fix_sprint_id, self._optional_json_body(), now=_utc_now())
                sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "closeout_report": closeout, "summary": acceptance_fix_closeout_summary(closeout)})
                return

            self._send_error(HTTPStatus.NOT_FOUND, "Acceptance Fix Sprint route not found.")
        except AcceptanceFixSprintNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceFixSprintStateError as exc:
            self._send_error(HTTPStatus.CONFLICT, str(exc))
        except (AcceptanceFixSprintError, AcceptanceAnalyticsError, AcceptanceNotFoundError, FileNotFoundError, ValueError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_root(self, method: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.latest_report()
            self._send_json({"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_refresh(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.refresh(self._optional_json_body(), now=_utc_now())
            self._send_json({"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}, status=HTTPStatus.CREATED)
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_report(self, method: str, report_id: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            report = self.acceptance_kb_store.get_report(report_id)
            self._send_json({"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)})
        except AcceptanceKnowledgeBaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_entries(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            entries = self.acceptance_kb_store.list_entries(include_hidden=include_hidden)
            self._send_json({"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_entry_route(self, method: str, route: tuple[str, str]) -> None:
        entry_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                entry = self.acceptance_kb_store.read_entry(entry_id)
                self._send_json({"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)})
                return
            if action in {"hide", "unhide"}:
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                entry = self.acceptance_kb_store.hide_entry(entry_id, hidden=action == "hide", now=_utc_now())
                self._send_json({"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "Acceptance KB entry route not found.")
        except AcceptanceKnowledgeBaseNotFoundError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, str(exc))
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_search(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = parse_qs(query_string)
            payload = {
                "issue_type": _query_value(query, "issue_type") or "",
                "style": _query_value(query, "style") or "",
                "song_id": _query_value(query, "song_id") or "",
                "project_id": _query_value(query, "project_id") or "",
                "release_id": _query_value(query, "release_id") or "",
                "outcome_status": _query_value(query, "outcome_status") or "",
            }
            include_hidden = _query_value(query, "include_hidden") in {"1", "true", "yes"}
            entries = self.acceptance_kb_store.search_entries(payload, include_hidden=include_hidden)
            self._send_json({"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_kb_recommend(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            recommendation = self.acceptance_kb_store.recommend(self._optional_json_body())
            self._send_json({"ok": True, "recommendation": recommendation})
        except AcceptanceKnowledgeBaseError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_project_version_audio_route(self, method: str, project_id: str, version_id: str, action: str) -> None:
        try:
            document = self.project_store.sync_project(project_id, self.store.get_job)
            version = next((item for item in document.versions if item.version_id == version_id), None)
            if version is None:
                raise FileNotFoundError(version_id)
            job = self.store.get_job(version.job_id)
            if job is None:
                raise FileNotFoundError(version.job_id)
            audio_path = Path(job.output_dir) / "renders" / "song.wav"
            if action == "audio":
                if method != "GET":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                if not audio_path.exists():
                    self._send_error(HTTPStatus.NOT_FOUND, "Audio render is not available for this version.")
                    return
                stale_reasons = self._job_audio_artifact_stale_reasons(job)
                if stale_reasons:
                    self._send_error(HTTPStatus.CONFLICT, f"Audio artifact is stale: {', '.join(stale_reasons)}.")
                    return
                self._send_file(audio_path, "audio/wav", filename=f"{project_id}-{version_id}.wav")
                return
            if action == "render-audio":
                if method != "POST":
                    self._send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                payload = self._optional_json_body()
                profile = self._renderer_profile_from_payload(payload)
                config = profile.to_renderer_config() if profile is not None else None
                audio, status, error = self.store.render_job_audio(job.job_id, config=config, audio_profile=profile)
                if error is not None:
                    self._send_error(status, str(sanitize_metadata({"error": error}).get("error") or "Audio render failed."))
                    return
                self.project_store.append_event(project_id, "project_version_audio_rendered", {"version_id": version_id, "job_id": job.job_id})
                wav_path = Path(job.output_dir) / "renders" / "song.wav"
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
            self._send_error(HTTPStatus.NOT_FOUND, "Version not found.")
            return
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._send_error(HTTPStatus.NOT_FOUND, "Project version audio route not found.")

    def _render_editor_preview_audio(self, project_id: str, preview_id: str) -> Any:
        store = EditorPreviewStore(self.project_store.project_dir(project_id))
        preview = store.read_preview(preview_id)
        preview_dir = store.preview_dir(preview_id)
        midi_path = preview_dir / "song.mid"
        try:
            _document, parent, parent_job, parent_plan = self._project_edit_parent(project_id, preview.parent_version_id)
        except FileNotFoundError as exc:
            raise FileNotFoundError("Parent version not found.") from exc
        if preview.parent_job_id != parent_job.job_id:
            raise EditorPatchStaleError("Editor preview parent job does not match the current version.")
        if editor_song_plan_hash(parent_plan) != preview.base_plan_hash:
            raise EditorPatchStaleError("Editor preview is stale because the parent song-plan.json has changed.")
        patch = store.read_patch(preview_id)
        result = apply_editor_patch(parent_plan, patch)
        result.plan.validate()
        write_interface_document(preview_dir / "song-plan.json", result.plan.to_dict())
        render_midi(result.plan, midi_path)
        report_path = preview_dir / "validator-report.json"
        report = read_json(report_path) if report_path.exists() else {}
        report.update(_build_validator_report(preview_dir / "song-plan.json", midi_path))
        try:
            config, _sources = load_renderer_config()
            config.validate_ready_for_render()
            wav_path = render_audio(midi_path, preview_dir / "song.wav", config)
        except RendererError as exc:
            updated = store.update_preview_audio(
                preview_id,
                status="failed",
                audio_error=str(sanitize_metadata({"error": str(exc)}).get("error") or "Audio render failed."),
                now=_utc_now(),
            )
            self.project_store.append_event(project_id, "editor_preview_audio_failed", {"preview_id": preview_id, "error": updated.audio_error})
            raise
        updated = store.update_preview_audio(
            preview_id,
            status="completed",
            audio_url=f"/api/projects/{project_id}/editor-previews/{preview_id}/audio",
            audio_size_bytes=wav_path.stat().st_size,
            now=_utc_now(),
        )
        report["audio"] = _audio_report(wav_path)
        write_interface_document(report_path, report)
        self.project_store.append_event(project_id, "editor_preview_audio_rendered", {"preview_id": preview_id, "size_bytes": wav_path.stat().st_size})
        return updated
