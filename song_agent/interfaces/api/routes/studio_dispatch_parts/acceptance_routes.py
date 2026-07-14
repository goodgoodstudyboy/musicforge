from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

from song_agent.interfaces.api.runtime import *

from song_agent.interfaces.api.routes.program_registry import PROGRAM_ROUTE_REGISTRY

class StudioAcceptance_RoutesDispatch:
    def _dispatch_studio_acceptance_routes(self, method, path, parsed) -> bool:
        planning_ruleset_route = _match_planning_ruleset_route(path)
        if planning_ruleset_route is not None:
            self._handle_planning_ruleset_route(method, planning_ruleset_route)
            return True
        if path == '/api/acceptance/planning-simulations':
            self._handle_planning_simulations_root(method, parsed.query)
            return True
        planning_simulation_route = _match_planning_simulation_route(path)
        if planning_simulation_route is not None:
            self._handle_planning_simulation_route(method, planning_simulation_route)
            return True
        if path == '/api/acceptance/planning-rule-governance/active':
            self._handle_planning_rule_governance_active(method)
            return True
        if path == '/api/acceptance/planning-rule-governance/versions':
            self._handle_planning_rule_governance_versions(method, parsed.query)
            return True
        if path == '/api/acceptance/planning-rule-governance/promotions':
            self._handle_planning_rule_governance_promotions(method, parsed.query)
            return True
        if path == '/api/acceptance/planning-rule-governance/rollback':
            self._handle_planning_rule_governance_rollback(method)
            return True
        if path == '/api/acceptance/planning-rule-governance/events':
            self._handle_planning_rule_governance_events(method, parsed.query)
            return True
        governance_version_route = _match_planning_rule_governance_version_route(path)
        if governance_version_route is not None:
            self._handle_planning_rule_governance_version_route(method, governance_version_route)
            return True
        governance_promotion_route = _match_planning_rule_governance_promotion_route(path)
        if governance_promotion_route is not None:
            self._handle_planning_rule_governance_promotion_route(method, governance_promotion_route)
            return True
        if path == '/api/acceptance/planning-rule-impact/reports':
            self._handle_planning_rule_impact_reports(method, parsed.query)
            return True
        if path == '/api/acceptance/planning-rule-impact/latest':
            self._handle_planning_rule_impact_latest(method, parsed.query)
            return True
        impact_report_route = _match_planning_rule_impact_report_route(path)
        if impact_report_route is not None:
            self._handle_planning_rule_impact_report_route(method, impact_report_route)
            return True
        return False
