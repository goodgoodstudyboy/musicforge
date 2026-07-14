from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

class QualityRoutesPart015:
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
