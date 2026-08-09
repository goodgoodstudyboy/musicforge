from __future__ import annotations

from song_agent.interfaces.api.route_contexts.quality import QualityRouteContext


import song_agent.interfaces.api.runtime as _interfaces_api_runtime


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None

class QualityRoutesAcceptanceAnalyticsRefresh(QualityRouteContext):
    def _handle_acceptance_analytics_refresh(self, method: str, query_string: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            payload = self._optional_json_body()
            query = _interfaces_api_runtime.parse_qs(query_string)
            scope = _interfaces_api_runtime.AnalyticsScope.from_values(
                scope_type=str(payload.get("scope") or _interfaces_api_runtime._query_value(query, "scope") or "global"),
                suite_id=_optional_text(payload.get("suite_id")) or _interfaces_api_runtime._query_value(query, "suite_id") or None,
                release_id=_optional_text(payload.get("release_id")) or _interfaces_api_runtime._query_value(query, "release_id") or None,
                project_id=_optional_text(payload.get("project_id")) or _interfaces_api_runtime._query_value(query, "project_id") or None,
            )
            report = self.server.acceptance_analytics_store.refresh(scope, now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceNotFoundError, _interfaces_api_runtime.ReleaseNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_report(self, method: str, report_id: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            report = self.server.acceptance_analytics_store.get_report(report_id)
            self._send_json({"ok": True, "analytics": report, "summary": _interfaces_api_runtime.acceptance_analytics_summary(report)})
        except _interfaces_api_runtime.AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceAnalyticsError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_analytics_recommendation(self, method: str, report_id: str, recommendation_id: str) -> None:
        if method != "POST":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        try:
            result = self.server.acceptance_analytics_store.create_review_task_from_recommendation(report_id, recommendation_id, self._optional_json_body())
            status = _interfaces_api_runtime.HTTPStatus.CREATED if result.get("status") == "created" else _interfaces_api_runtime.HTTPStatus.OK
            self._send_json({"ok": True, **result}, status=status)
        except _interfaces_api_runtime.AcceptanceAnalyticsNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceAnalyticsStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, FileNotFoundError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_sprints_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(query_string)
                include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _interfaces_api_runtime._query_value(query, "status") or None
                sprints = self.server.acceptance_fix_sprint_store.list_sprints(include_archived=include_archived, status=status)
                self._send_json(
                    {
                        "ok": True,
                        "fix_sprints": [sprint.to_dict() for sprint in sprints],
                        "summary": {"fix_sprint_count": len(sprints), "latest": _interfaces_api_runtime.fix_sprint_summary(sprints[0]) if sprints else {"status": "missing"}},
                    }
                )
                return
            if method == "POST":
                sprint = self.server.acceptance_fix_sprint_store.create_from_analytics(self._read_json_body())
                items = self.server.acceptance_fix_sprint_store.read_items(sprint.fix_sprint_id)
                self._send_json({"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": _interfaces_api_runtime.fix_sprint_summary(sprint, items)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.AcceptanceFixSprintNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceFixSprintStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.AcceptanceFixSprintError, _interfaces_api_runtime.AcceptanceAnalyticsError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plans_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(query_string)
                include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _interfaces_api_runtime._query_value(query, "status")
                plans = self.server.acceptance_fix_plan_store.list_plans(include_archived=include_archived, status=status)
                self._send_json({"ok": True, "fix_plans": [plan.to_dict() for plan in plans], "summary": {"plan_count": len(plans)}})
                return
            if method == "POST":
                plan = self.server.acceptance_fix_plan_store.create(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "fix_plan": plan.to_dict(), "summary": _interfaces_api_runtime.fix_plan_summary(plan)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.AcceptanceFixPlanStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.AcceptanceFixPlanError, _interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceKnowledgeBaseError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plans_recommend(self, method: str) -> None:
        try:
            if method != "POST":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            preview = self.server.acceptance_fix_plan_store.preview(self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
            self._send_json({"ok": True, "fix_plan_preview": preview, "summary": _interfaces_api_runtime.fix_plan_summary(preview)})
        except _interfaces_api_runtime.AcceptanceFixPlanStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.AcceptanceFixPlanError, _interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceKnowledgeBaseError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plan_reviews_root(self, method: str, query_string: str) -> None:
        try:
            if method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            query = _interfaces_api_runtime.parse_qs(query_string)
            include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
            status = _interfaces_api_runtime._query_value(query, "status") or None
            release_id = _interfaces_api_runtime._query_value(query, "release_id") or None
            project_id = _interfaces_api_runtime._query_value(query, "project_id") or None
            reviews = self.server.acceptance_fix_plan_review_store.list_reviews(include_archived=include_archived, status=status, release_id=release_id, project_id=project_id)
            self._send_json({"ok": True, "outcome_reviews": [review.to_dict() for review in reviews], "summary": {"review_count": len(reviews), "latest": _interfaces_api_runtime.fix_plan_review_summary(reviews[0]) if reviews else {"status": "missing"}}})
        except _interfaces_api_runtime.AcceptanceFixPlanReviewError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_acceptance_fix_plan_review_route(self, method: str, route: tuple[str, str]) -> None:
        review_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.server.acceptance_fix_plan_review_store.read_review(review_id)
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": _interfaces_api_runtime.fix_plan_review_summary(review)})
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.server.acceptance_fix_plan_review_store.refresh_review(review_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": _interfaces_api_runtime.fix_plan_review_summary(review)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                review = self.server.acceptance_fix_plan_review_store.archive_review(review_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "outcome_review": review.to_dict(), "summary": _interfaces_api_runtime.fix_plan_review_summary(review)})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Acceptance Fix Plan Outcome Review route not found.")
        except _interfaces_api_runtime.AcceptanceFixPlanReviewNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.AcceptanceFixPlanReviewStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.AcceptanceFixPlanReviewError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rulesets_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(query_string)
                include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
                rulesets = self.server.planning_rule_simulation_store.list_rulesets(include_archived=include_archived)
                self._send_json({"ok": True, "rulesets": [ruleset.to_dict() for ruleset in rulesets], "summary": {"ruleset_count": len(rulesets)}})
                return
            if method == "POST":
                ruleset = self.server.planning_rule_simulation_store.create_ruleset(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": _interfaces_api_runtime.ruleset_summary(ruleset)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.PlanningRuleSimulationStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleSimulationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_ruleset_route(self, method: str, route: tuple[str, str]) -> None:
        ruleset_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                ruleset = self.server.planning_rule_simulation_store.read_ruleset(ruleset_id)
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": _interfaces_api_runtime.ruleset_summary(ruleset)})
                return
            if action == "clone":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                ruleset = self.server.planning_rule_simulation_store.clone_ruleset(ruleset_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": _interfaces_api_runtime.ruleset_summary(ruleset)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                ruleset = self.server.planning_rule_simulation_store.archive_ruleset(ruleset_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "ruleset": ruleset.to_dict(), "summary": _interfaces_api_runtime.ruleset_summary(ruleset)})
                return
            if action == "validate":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                self._send_json({"ok": True, "validation": self.server.planning_rule_simulation_store.validate_ruleset(ruleset_id)})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Planning Rule Set route not found.")
        except _interfaces_api_runtime.PlanningRuleSimulationNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PlanningRuleSimulationStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleSimulationError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_simulations_root(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(query_string)
                include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _interfaces_api_runtime._query_value(query, "status") or None
                release_id = _interfaces_api_runtime._query_value(query, "release_id") or None
                project_id = _interfaces_api_runtime._query_value(query, "project_id") or None
                simulations = self.server.planning_rule_simulation_store.list_simulations(include_archived=include_archived, status=status, release_id=release_id, project_id=project_id)
                self._send_json({"ok": True, "simulations": [simulation.to_dict() for simulation in simulations], "summary": {"simulation_count": len(simulations), "latest": _interfaces_api_runtime.planning_simulation_summary(simulations[0]) if simulations else {"status": "missing"}}})
                return
            if method == "POST":
                simulation = self.server.planning_rule_simulation_store.create_simulation(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": _interfaces_api_runtime.planning_simulation_summary(simulation)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.PlanningRuleSimulationStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleSimulationNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.PlanningRuleSimulationError, _interfaces_api_runtime.AcceptanceFixPlanReviewError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_simulation_route(self, method: str, route: tuple[str, str]) -> None:
        simulation_id, action = route
        try:
            if not action:
                if method != "GET":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                simulation = self.server.planning_rule_simulation_store.read_simulation(simulation_id)
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": _interfaces_api_runtime.planning_simulation_summary(simulation)})
                return
            if action == "refresh":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                simulation = self.server.planning_rule_simulation_store.refresh_simulation(simulation_id, self._optional_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": _interfaces_api_runtime.planning_simulation_summary(simulation)})
                return
            if action == "archive":
                if method != "POST":
                    self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                    return
                simulation = self.server.planning_rule_simulation_store.archive_simulation(simulation_id, now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "simulation": simulation.to_dict(), "summary": _interfaces_api_runtime.planning_simulation_summary(simulation)})
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, "Planning Rule Simulation route not found.")
        except _interfaces_api_runtime.PlanningRuleSimulationNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PlanningRuleSimulationStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except (_interfaces_api_runtime.PlanningRuleSimulationError, _interfaces_api_runtime.AcceptanceFixPlanReviewError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_active(self, method: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        version = self.server.planning_rule_governance_store.active_version()
        active = self.server.planning_rule_governance_store.active_pointer()
        summary = self.server.planning_rule_governance_store.active_summary()
        self._send_json({"ok": True, "active": active, "version": version.to_dict() if version else {}, "summary": summary})

    def _handle_planning_rule_governance_versions(self, method: str, query_string: str) -> None:
        if method != "GET":
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
            return
        query = _interfaces_api_runtime.parse_qs(query_string)
        include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
        status = _interfaces_api_runtime._query_value(query, "status") or None
        versions = self.server.planning_rule_governance_store.list_versions(include_archived=include_archived, status=status)
        self._send_json({"ok": True, "versions": [version.to_dict() for version in versions], "summary": {"version_count": len(versions), "active": self.server.planning_rule_governance_store.active_summary()}})

    def _handle_planning_rule_governance_version_route(self, method: str, route: tuple[str, str]) -> None:
        version_id, action = route
        try:
            if action or method != "GET":
                self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED if action else _interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
                return
            version = self.server.planning_rule_governance_store.read_version(version_id)
            frozen = self.server.planning_rule_governance_store.frozen_ruleset(version_id)
            active = self.server.planning_rule_governance_store.active_pointer()
            self._send_json({"ok": True, "version": version.to_dict(), "frozen_ruleset_summary": _interfaces_api_runtime.ruleset_summary(frozen), "summary": _interfaces_api_runtime.governance_summary(version, active=active, evidence_stale=self.server.planning_rule_governance_store.version_evidence_is_stale(version))})
        except _interfaces_api_runtime.PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except _interfaces_api_runtime.PlanningRuleGovernanceError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))

    def _handle_planning_rule_governance_promotions(self, method: str, query_string: str) -> None:
        try:
            if method == "GET":
                query = _interfaces_api_runtime.parse_qs(query_string)
                include_archived = _interfaces_api_runtime._query_value(query, "include_archived") in {"1", "true", "yes"}
                status = _interfaces_api_runtime._query_value(query, "status") or None
                promotions = self.server.planning_rule_governance_store.list_promotions(include_archived=include_archived, status=status)
                self._send_json({"ok": True, "promotions": [promotion.to_dict() for promotion in promotions], "summary": {"promotion_count": len(promotions)}})
                return
            if method == "POST":
                promotion = self.server.planning_rule_governance_store.create_promotion(self._read_json_body(), now=_interfaces_api_runtime._utc_now())
                self._send_json({"ok": True, "promotion": promotion.to_dict(), "summary": _interfaces_api_runtime.promotion_summary(promotion)}, status=_interfaces_api_runtime.HTTPStatus.CREATED)
                return
            self._send_error(_interfaces_api_runtime.HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")
        except _interfaces_api_runtime.PlanningRuleGovernanceStateError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.CONFLICT, str(exc))
        except _interfaces_api_runtime.PlanningRuleGovernanceNotFoundError as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.NOT_FOUND, str(exc))
        except (_interfaces_api_runtime.PlanningRuleGovernanceError, _interfaces_api_runtime.PlanningRuleSimulationError, ValueError) as exc:
            self._send_error(_interfaces_api_runtime.HTTPStatus.BAD_REQUEST, str(exc))
