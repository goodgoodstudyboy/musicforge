from __future__ import annotations

from typing import Any

from song_agent.platform.contracts.documents import ImplementationDocument


import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseAcceptanceFixSprintGate:
    def _release_acceptance_fix_sprint_gate(self, payload: ImplementationDocument) -> ImplementationDocument:
        fix_sprint_id = str(payload.get("acceptance_fix_sprint_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_acceptance_fix_sprint", False))
        try:
            if fix_sprint_id:
                sprint = self.acceptance_fix_sprint_store.read_sprint(fix_sprint_id)
            elif release_id:
                summary = _interfaces_api_runtime.latest_fix_sprint_summary(self.acceptance_fix_sprint_store, release_id=release_id)
                if summary.get("status") == "missing":
                    return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Sprint evidence is missing."}
                sprint = self.acceptance_fix_sprint_store.read_sprint(str(summary.get("fix_sprint_id") or ""))
            else:
                return {}
            items = self.acceptance_fix_sprint_store.read_items(sprint.fix_sprint_id)
            closeout = self.acceptance_fix_sprint_store.read_closeout(sprint.fix_sprint_id, default={})
            summary = _interfaces_api_runtime.fix_sprint_summary(sprint, items)
            closeout_summary = _interfaces_api_runtime.acceptance_fix_closeout_summary(closeout)
            stale = self.acceptance_fix_sprint_store.sprint_is_stale(sprint)
            ok = sprint.status == "closed" and closeout_summary.get("status") in {"passed", "warning", "force_closed"}
            evidence = {**summary, "sprint_status": summary.get("status"), "stale": stale, "closeout": closeout_summary}
            if stale:
                return {**evidence, "status": "failed" if require_gate else "warning", "message": "Acceptance Fix Sprint source analytics is stale. Refresh analytics before signoff."}
            if require_gate and not ok:
                return {**evidence, "status": "failed", "message": "Acceptance Fix Sprint is not closed."}
            return {**evidence, "status": "passed" if ok else "warning" if summary.get("status") != "missing" else "missing"}
        except _interfaces_api_runtime.AcceptanceFixSprintNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Sprint evidence is missing."}
        except _interfaces_api_runtime.AcceptanceFixSprintError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_acceptance_fix_plan_gate(self, payload: ImplementationDocument) -> ImplementationDocument:
        plan_id = str(payload.get("acceptance_fix_plan_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_acceptance_fix_plan", False))
        try:
            if plan_id:
                plan = self.acceptance_fix_plan_store.read_plan(plan_id)
                summary = _interfaces_api_runtime.fix_plan_summary(plan)
            elif release_id:
                summary = _interfaces_api_runtime.latest_fix_plan_summary(self.acceptance_fix_plan_store, release_id=release_id)
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
        except _interfaces_api_runtime.AcceptanceFixPlanNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Plan evidence is missing."}
        except _interfaces_api_runtime.AcceptanceFixPlanError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_acceptance_fix_plan_review_gate(self, payload: ImplementationDocument) -> ImplementationDocument:
        review_id = str(payload.get("acceptance_fix_plan_review_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_acceptance_fix_plan_review", False))
        try:
            if review_id:
                review = self.acceptance_fix_plan_review_store.read_review(review_id)
                summary = _interfaces_api_runtime.fix_plan_review_summary(review)
            elif release_id:
                summary = _interfaces_api_runtime.latest_fix_plan_review_summary(self.acceptance_fix_plan_review_store, release_id=release_id)
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
            return {**evidence, "status": "passed" if review.status in _interfaces_api_runtime.REVIEW_READY_STATUSES else "warning"}
        except _interfaces_api_runtime.AcceptanceFixPlanReviewNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Acceptance Fix Plan Outcome Review evidence is missing."}
        except _interfaces_api_runtime.AcceptanceFixPlanReviewError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_acceptance_kb_gate(self, payload: ImplementationDocument) -> ImplementationDocument:
        release_id = str(payload.get("release_id") or "").strip()
        if not release_id:
            return {}
        try:
            summary = self.acceptance_kb_store.summary(release_id=release_id)
            status = "warning" if summary.get("stale") else "available" if int(summary.get("entry_count") or 0) else "missing"
            return {**summary, "status": status}
        except _interfaces_api_runtime.AcceptanceKnowledgeBaseError as exc:
            return {"status": "warning", "message": str(exc)}

    def _release_planning_rule_simulation_gate(self, payload: ImplementationDocument) -> ImplementationDocument:
        simulation_id = str(payload.get("planning_simulation_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        require_gate = bool(payload.get("require_planning_rule_simulation", False))
        try:
            if simulation_id:
                simulation = self.planning_rule_simulation_store.read_simulation(simulation_id)
                summary = _interfaces_api_runtime.planning_simulation_summary(simulation)
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
        except _interfaces_api_runtime.PlanningRuleSimulationNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Planning Rule Simulation evidence is missing."}
        except _interfaces_api_runtime.PlanningRuleSimulationError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_planning_rule_governance_gate(self, payload: ImplementationDocument) -> ImplementationDocument:
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
        except _interfaces_api_runtime.PlanningRuleGovernanceError as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _release_planning_rule_impact_gate(self, payload: ImplementationDocument) -> ImplementationDocument:
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
            summary = _interfaces_api_runtime.planning_rule_impact_summary(report)
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
                "actual_integrity_hash": _interfaces_api_runtime.planning_rule_impact_report_hash(report),
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
        except _interfaces_api_runtime.PlanningRuleImpactNotFoundError:
            return {"status": "failed" if require_gate else "missing", "message": "Planning Rule Impact evidence is missing."}
        except (_interfaces_api_runtime.PlanningRuleImpactError, _interfaces_api_runtime.PlanningRuleGovernanceError, ValueError) as exc:
            return {"status": "failed" if require_gate else "warning", "message": str(exc)}

    def _planning_simulation_reviews_match_release(self, simulation: Any, release_id: str) -> bool:
        source = simulation.source if hasattr(simulation, "source") and isinstance(simulation.source, dict) else {}
        review_ids = source.get("review_ids") if isinstance(source.get("review_ids"), list) else []
        if not review_ids:
            return False
        for review_id in review_ids:
            try:
                review = self.acceptance_fix_plan_review_store.read_review(str(review_id))
            except _interfaces_api_runtime.AcceptanceFixPlanReviewError:
                return False
            if review.scope.get("release_id") != release_id:
                return False
        return True
