from __future__ import annotations

from song_agent.application.interface_persistence import persist_interface_job, write_interface_document

import song_agent.interfaces.api.runtime as _interfaces_api_runtime

class QualityRoutesReleaseAcceptanceGate:
    def _release_acceptance_gate(self, payload: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
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
        summary = _interfaces_api_runtime.acceptance_report_summary(report)
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

    def _release_audio_campaign_gate(self, release_id: str, payload: dict[str, Any], *, required: bool) -> dict[str, _interfaces_api_runtime.Any]:
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

    def _release_audio_campaign_coverage(self, release: Any, campaign_id: str) -> dict[str, _interfaces_api_runtime.Any]:
        try:
            case_index = _interfaces_api_runtime.read_json(self.audio_campaign_store.case_index_path(campaign_id))
        except Exception as exc:
            return {"status": "failed", "message": f"Audio Campaign case index is unavailable: {sanitize_sensitive_text(str(exc))}", "missing_tracks": []}
        return _interfaces_api_runtime.audio_campaign_release_track_coverage(release.tracks, case_index)

    def _release_audio_campaign_final_export_current(self, release: Any) -> dict[str, _interfaces_api_runtime.Any]:
        rows = []
        stale = []
        for track in sorted(release.tracks, key=lambda item: (getattr(item, "disc_number", 1), getattr(item, "track_number", 1), getattr(item, "track_id", ""))):
            project_id = str(getattr(track, "project_id", "") or "")
            recorded_hash = str(getattr(track, "final_export_hash", "") or "")
            manifest_path = _interfaces_api_runtime.final_export_dir(self.project_store.project_dir(project_id)) / "manifest.json"
            current_hash = _interfaces_api_runtime._server_file_sha256(manifest_path) if manifest_path.exists() else ""
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

    def _release_audio_gate(self, release_id: str, payload: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
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
            current_hash = _interfaces_api_runtime.release_audio_source_hash(document, project_store=self.project_store, release_store=self.release_store)
            report = _interfaces_api_runtime.read_release_audio_qa(self.release_store, release_id, default={})
        except Exception as exc:
            return {"status": "failed", "hard_block": True, "message": f"Release Audio QA is unavailable: {sanitize_sensitive_text(str(exc))}"}
        summary = _interfaces_api_runtime.release_audio_summary(report)
        evidence: dict[str, _interfaces_api_runtime.Any] = {
            **summary,
            "require_audio_health": require_health,
            "require_human_audio_review": require_human,
            "require_per_track_audio_review": require_per_track_review,
            "require_audio_artifact_current": require_current,
            "require_stem_audio_health": require_stem_health,
            "require_current_mix_state": require_current_mix,
            "require_audio_revision_closeout": require_audio_revision,
        }
        revision_gate = self.audio_revision_store.gate(release_id, required=require_audio_revision, now=_interfaces_api_runtime._utc_now())
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
            if not _interfaces_api_runtime.release_audio_report_integrity_ok(report):
                return {**evidence, "status": "failed", "hard_block": True, "message": "Release Audio QA integrity failed. Refresh audio QA before signoff."}
            if require_current and report.get("source_hash") != current_hash:
                return {**evidence, "status": "failed", "hard_block": True, "message": "Release Audio QA is stale. Refresh audio QA before signoff.", "current_source_hash": current_hash}
            if not _interfaces_api_runtime.release_audio_allows_signoff(report, current_source_hash=current_hash if require_current else None):
                return {**evidence, "status": "failed", "hard_block": True, "message": "Release Audio QA has blocking audio failures."}
        if require_per_track_review:
            per_track_gate = _interfaces_api_runtime.release_audio_review_gate(self.release_store, self.project_store, release_id, now=_interfaces_api_runtime._utc_now())
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
                acceptance_summary = _interfaces_api_runtime.acceptance_report_summary(acceptance)
                evidence["manual_audio_accepted_count"] = acceptance_summary.get("manual_audio_accepted_count", 0)
                evidence["acceptance_status"] = acceptance_summary.get("acceptance_status")
                if int(acceptance_summary.get("manual_audio_accepted_count", 0) or 0) <= 0:
                    return {**evidence, "status": "failed", "hard_block": True, "message": "Human WAV listening review evidence is missing."}
        return {**evidence, "status": "passed", "message": "Release audio gate passed."}

    def _release_acceptance_analytics_gate(self, payload: dict[str, Any]) -> dict[str, _interfaces_api_runtime.Any]:
        report_id = str(payload.get("acceptance_analytics_report_id") or "").strip()
        release_id = str(payload.get("release_id") or "").strip()
        try:
            if report_id:
                report = self.acceptance_analytics_store.get_report(report_id)
            elif release_id:
                report = self.acceptance_analytics_store.latest_report(_interfaces_api_runtime.AnalyticsScope.from_values(scope_type="release", release_id=release_id))
            else:
                return {}
        except (_interfaces_api_runtime.AcceptanceAnalyticsError, _interfaces_api_runtime.AcceptanceAnalyticsNotFoundError, _interfaces_api_runtime.ReleaseNotFoundError, ValueError):
            return {"status": "missing", "warning": "acceptance_analytics_unavailable"}
        return _interfaces_api_runtime.release_acceptance_analytics_evidence(report)
