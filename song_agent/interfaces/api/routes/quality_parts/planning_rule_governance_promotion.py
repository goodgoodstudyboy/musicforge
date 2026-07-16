from __future__ import annotations


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesPlanningRuleGovernancePromotion:
    def _handle_planning_rule_governance_promotion_route(self, method: str, route: tuple[str, str]) -> None:
        promotion_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                promotion = self.planning_rule_governance_store.read_promotion(promotion_id)
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": _interfaces_api_runtime.promotion_summary(promotion)})
                return
            if action == "approve":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                promotion = self.planning_rule_governance_store.approve_promotion(promotion_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": _interfaces_api_runtime.promotion_summary(promotion)})
                return
            if action == "reject":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                promotion = self.planning_rule_governance_store.reject_promotion(promotion_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": _interfaces_api_runtime.promotion_summary(promotion)})
                return
            if action == "promote":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.planning_rule_governance_store.promote(promotion_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "version": result["version"].to_dict(), "active": result["active"], "promotion": result["promotion"].to_dict(), "summary": result["summary"]}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Planning Rule Governance promotion route not found.")
        except _interfaces_api_runtime.PlanningRuleGovernanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.PlanningRuleGovernanceError, _interfaces_api_runtime.PlanningRuleSimulationError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_rollback(self, method: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            result = self.planning_rule_governance_store.rollback(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "version": result["version"].to_dict(), "active": result["active"], "summary": result["summary"]})
        except _interfaces_api_runtime.PlanningRuleGovernanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.PlanningRuleGovernanceError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_events(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = _interfaces_api_runtime.parse_qs(query_string)
        limit = int(_interfaces_api_runtime._query_value(query, "limit") or 50)
        events = self.planning_rule_governance_store.events(limit=limit)
        self._send_json({"ok": True, "events": events, "summary": {"event_count": len(events)}})

    def _handle_planning_rule_impact_reports(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(query_string)
                include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
                release_id = _interfaces_api_runtime._query_value(query, "release_id") or None
                project_id = _interfaces_api_runtime._query_value(query, "project_id") or None
                reports = self.planning_rule_impact_store.list_reports(include_archived=include_archived, release_id=release_id, project_id=project_id)
                self._send_json({"ok": True, "reports": [report.to_dict() for report in reports], "summary": {"report_count": len(reports), "latest": _interfaces_api_runtime.planning_rule_impact_summary(reports[0]) if reports else {"status": "missing"}}})
                return
            if method == "POST":
                report = self.planning_rule_impact_store.refresh(self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "impact_report": report.to_dict(), "summary": _interfaces_api_runtime.planning_rule_impact_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.PlanningRuleImpactStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleImpactError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_impact_latest(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = _interfaces_api_runtime.parse_qs(query_string)
        summary = self.planning_rule_impact_store.latest_summary(release_id=_interfaces_api_runtime._query_value(query, "release_id") or None, project_id=_interfaces_api_runtime._query_value(query, "project_id") or None)
        self._send_json({"ok": True, "summary": summary})

    def _handle_planning_rule_impact_report_route(self, method: str, route: tuple[str, str]) -> None:
        report_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.planning_rule_impact_store.get_report(report_id)
                integrity_ok = self.planning_rule_impact_store.report_integrity_ok(report)
                self._send_json(
                    {
                        "ok": True,
                        "impact_report": report.to_dict(),
                        "summary": _interfaces_api_runtime.planning_rule_impact_summary(report),
                        "stale": self.planning_rule_impact_store.report_is_stale(report),
                        "integrity_ok": integrity_ok,
                        "integrity": {
                            "ok": integrity_ok,
                            "expected_integrity_hash": report.integrity_hash,
                            "actual_integrity_hash": _interfaces_api_runtime.planning_rule_impact_report_hash(report),
                        },
                    }
                )
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.planning_rule_impact_store.refresh_report(report_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "impact_report": report.to_dict(), "summary": _interfaces_api_runtime.planning_rule_impact_summary(report)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                report = self.planning_rule_impact_store.archive_report(report_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "impact_report": report.to_dict(), "summary": _interfaces_api_runtime.planning_rule_impact_summary(report)})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Planning Rule Impact route not found.")
        except _interfaces_api_runtime.PlanningRuleImpactNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PlanningRuleImpactStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleImpactError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plan_route(self, method: str, route: tuple[str, str]) -> None:
        plan_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.acceptance_fix_plan_store.read_plan(plan_id)
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": _interfaces_api_runtime.fix_plan_summary(plan)})
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.acceptance_fix_plan_store.refresh_plan(plan_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": _interfaces_api_runtime.fix_plan_summary(plan)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                plan = self.acceptance_fix_plan_store.archive_plan(plan_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": _interfaces_api_runtime.fix_plan_summary(plan)})
                return
            if action == "create-fix-sprint":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                result = self.acceptance_fix_plan_store.create_fix_sprint(plan_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, **result}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "outcome-review":
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.acceptance_fix_plan_review_store.get_or_missing_for_plan(plan_id)
                self._send_json({"ok": True, "outcome_review": review, "summary": _interfaces_api_runtime.fix_plan_review_summary(review)})
                return
            if action == "outcome-review/refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.acceptance_fix_plan_review_store.refresh_for_plan(plan_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": _interfaces_api_runtime.fix_plan_review_summary(review)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Acceptance Fix Plan route not found.")
        except _interfaces_api_runtime.AcceptanceFixPlanNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceFixPlanStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AcceptanceFixPlanReviewStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AcceptanceFixPlanReviewError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
        except (_interfaces_api_runtime.AcceptanceFixPlanError, _interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceKnowledgeBaseError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
