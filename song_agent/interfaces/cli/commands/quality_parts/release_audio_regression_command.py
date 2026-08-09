from __future__ import annotations

from song_agent.interfaces.bootstrap.cli import stores as _quality_stores


from song_agent.platform.contracts.documents import JsonDocument, normalize_json_value

from . import dependencies as _commands_quality_parts_dependencies
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def _run_release_audio_regression_command(args: argparse.Namespace) -> JsonDocument:
    pass
    pass

    store = _quality_stores.release_audio_regression_store()
    if args.action == "configure":
        policy = {}
        if args.identity_mode:
            policy["identity_mode"] = args.identity_mode
        config = store.configure_baseline(
            args.release_id,
            {
                "baseline_release_id": args.baseline_release_id,
                "baseline_timeline": args.baseline_timeline,
                "baseline_timeline_verification_report": args.baseline_timeline_verification_report,
                "baseline_certification": args.baseline_certification,
                "baseline_certification_verification_report": args.baseline_certification_verification_report,
                "current_timeline": args.current_timeline,
                "current_timeline_verification_report": args.current_timeline_verification_report,
                "current_certification": args.current_certification,
                "current_certification_verification_report": args.current_certification_verification_report,
                "policy": policy,
            },
        )
        return {"ok": True, "config": config, "summary": {"baseline_release_id": (config.get("baseline") or {}).get("release_id")}, "status": "configured"}
    if args.action == "refresh":
        report = store.refresh_report(args.release_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "status":
        report = store.read_report(args.release_id, default={})
        config = store.read_config(args.release_id, default={})
        signoff = read_json(store.signoff_path(args.release_id)) if store.signoff_path(args.release_id).exists() else {}
        return {"ok": report.get("status") == "passed", "config": config, "report": report, "signoff": signoff, "summary": report.get("summary", {}), "status": report.get("status") or "missing"}
    if args.action == "signoff":
        result = store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_package(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.release_id,
            strict=args.strict,
            require_passed=args.require_passed,
            require_signed=args.require_signed,
            require_current=args.require_current,
            require_baseline_current=args.require_baseline_current,
            baseline_timeline_path=args.baseline_timeline,
            baseline_timeline_verification_report_path=args.baseline_timeline_verification_report,
            baseline_certification_path=args.baseline_certification,
            baseline_certification_verification_report_path=args.baseline_certification_verification_report,
            current_timeline_path=args.current_timeline,
            current_timeline_verification_report_path=args.current_timeline_verification_report,
            current_certification_path=args.current_certification,
            current_certification_verification_report_path=args.current_certification_verification_report,
        )
        if args.report_out is not None:
            write_release_audio_regression_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-regression command.")

def _run_release_audio_baseline_command(args: argparse.Namespace) -> JsonDocument:
    pass
    pass

    store = _quality_stores.release_audio_baseline_governance_store()
    if args.action == "from-release":
        baseline = store.create_from_release(
            args.release_id,
            {
                "timeline": args.timeline,
                "timeline_verification_report": args.timeline_verification_report,
                "certification": args.certification,
                "certification_verification_report": args.certification_verification_report,
                "scope_type": args.scope_type,
                "release_line_id": args.release_line_id,
            },
        )
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "approve":
        baseline = store.approve(args.baseline_id, {"approved_by": args.approved_by, "role": args.role, "reason": args.reason})
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "activate":
        baseline = store.activate(args.baseline_id, {"supersede_existing": args.supersede_existing})
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "revoke":
        baseline = store.revoke(args.baseline_id, {"reason": args.reason})
        return {"ok": True, "baseline": baseline, "summary": {"baseline_id": baseline.get("baseline_id"), "status": baseline.get("status")}, "status": baseline.get("status")}
    if args.action == "list":
        rows = store.list_baselines()
        return {"ok": True, "baselines": normalize_json_value(rows), "summary": {"baseline_count": len(rows)}, "status": "passed"}
    if args.action == "preflight-release":
        result = store.preflight_release(
            args.release_id,
            args.baseline_id,
            {
                "timeline": args.timeline,
                "timeline_verification_report": args.timeline_verification_report,
                "certification": args.certification,
                "certification_verification_report": args.certification_verification_report,
            },
        )
        return {"ok": result.get("status") == "passed", **result, "summary": {"baseline_id": args.baseline_id}, "status": result.get("status")}
    if args.action == "export":
        result = store.export_registry()
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip()
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(strict=args.strict, require_active=args.require_active)
        if args.report_out is not None:
            write_release_audio_baseline_registry_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-baseline command.")

def _run_release_audio_regression_response_command(args: argparse.Namespace) -> JsonDocument:
    pass
    pass

    store = _quality_stores.release_audio_regression_response_store()
    if args.action == "create":
        plan = store.create_plan(args.release_id)
        return {"ok": True, "plan": plan, "summary": plan.get("summary", {}), "status": plan.get("status")}
    if args.action == "waive":
        waivers = store.add_waiver(args.release_id, {"action_id": args.action_id, "reason": args.reason, "waived_by": args.waived_by})
        return {"ok": True, "waivers": waivers, "summary": {"waiver_count": len(waivers.get("waivers", []))}, "status": "waived"}
    if args.action == "run-safe":
        result = store.run_safe_actions(args.release_id)
        return {"ok": True, **result, "summary": {"result_count": len(result.get("results", []))}, "status": result.get("status")}
    if args.action == "closeout":
        closeout = store.closeout(args.release_id, {"closed_by": args.closed_by, "reason": args.reason})
        return {"ok": closeout.get("status") == "closed", "closeout": closeout, "summary": closeout, "status": closeout.get("status")}
    if args.action == "signoff":
        result = store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("closeout", {}), "status": result.get("status")}
    if args.action == "status":
        plan = store.read_plan(args.release_id, default={})
        closeout = read_json(store.closeout_path(args.release_id)) if store.closeout_path(args.release_id).exists() else {}
        signoff = read_json(store.signoff_path(args.release_id)) if store.signoff_path(args.release_id).exists() else {}
        return {"ok": bool(plan), "plan": plan, "closeout": closeout, "signoff": signoff, "summary": plan.get("summary", {}), "status": signoff.get("status") or closeout.get("status") or plan.get("status") or "missing"}
    if args.action == "export":
        result = store.export_package(args.release_id)
        return {"ok": result.get("status") in {"closed", "signed"}, **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id)
        return {"ok": result.get("status") in {"closed", "signed"}, **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(args.release_id, strict=args.strict, require_closed=args.require_closed, require_signed=args.require_signed, require_regression_current=args.require_regression_current, **store._response_verifier_kwargs(args.release_id))  # noqa: SLF001 - CLI uses store-resolved external evidence.
        if args.report_out is not None:
            write_release_audio_regression_response_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-regression-response command.")

def _run_release_audio_quality_observatory_command(args: argparse.Namespace) -> JsonDocument:
    pass
    pass

    store = _quality_stores.release_audio_quality_observatory_store()
    if args.action == "create":
        config = store.create({"name": args.name, "release_ids": args.release_id})
        return {"ok": True, "observatory": config, "summary": {"observatory_id": config.get("observatory_id")}, "status": "created"}
    if args.action == "list":
        rows = store.list_observatories()
        return {"ok": True, "observatories": normalize_json_value(rows), "summary": {"observatory_count": len(rows)}, "status": "passed"}
    if args.action == "refresh":
        summary = store.refresh(args.observatory_id)
        return {"ok": summary.get("status") == "passed", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")}
    if args.action == "status":
        config = store.read_config(args.observatory_id)
        summary = store.read_summary(args.observatory_id) if store.summary_path(args.observatory_id).exists() else {}
        return {"ok": bool(config), "observatory": config, "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status") or "missing"}
    if args.action == "export":
        result = store.export_package(args.observatory_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.observatory_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.observatory_id,
            strict=args.strict,
            require_current_evidence=args.require_current_evidence,
            evidence_root=args.evidence_root,
            require_no_critical_risk=args.require_no_critical_risk,
        )
        if args.report_out is not None:
            write_release_audio_quality_observatory_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-quality-observatory command.")

def _run_release_audio_quality_actions_command(args: argparse.Namespace) -> JsonDocument:
    pass
    pass
    pass
    pass

    store = _quality_stores.release_audio_quality_action_queue_store()
    signoff_store = _quality_stores.release_audio_quality_action_queue_signoff_store(queue_store=store, release_store=store.release_store)
    if args.action == "create":
        include_risks = not bool(args.recommendations_only)
        include_recommendations = not bool(args.risks_only)
        queue = store.create_from_observatory(
            args.observatory_id,
            name=args.name,
            include_risks=include_risks,
            include_recommendations=include_recommendations,
            severity_floor=args.severity_floor,
        )
        return {"ok": True, "queue": queue, "summary": queue.get("summary", {}), "status": queue.get("status")}
    if args.action == "list":
        rows = store.list_queues()
        return {"ok": True, "queues": normalize_json_value(rows), "summary": {"queue_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        queue = store.read_queue(args.queue_id)
        summary = store.read_summary(args.queue_id)
        return {"ok": bool(queue), "queue": queue, "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status") or queue.get("status")}
    if args.action == "refresh":
        summary = store.refresh_status(args.queue_id)
        return {"ok": summary.get("status") != "stale", "summary_report": summary, "summary": summary.get("summary", {}), "status": summary.get("status")}
    if args.action == "run-safe":
        result = store.run_safe(args.queue_id)
        return {"ok": result.get("status") not in {"failed", "stale"}, **result}
    if args.action == "export":
        result = store.export_package(args.queue_id)
        return {"ok": result.get("status") not in {"failed", "stale"}, **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.queue_id)
        return {"ok": result.get("status") not in {"failed", "stale"}, **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.queue_id,
            strict=args.strict,
            require_current_observatory=args.require_current_observatory,
            observatory_zip_path=args.observatory_zip,
            observatory_verification_report_path=args.observatory_verification_report,
            evidence_root=args.evidence_root,
            require_no_blocking=not args.allow_blocking,
        )
        if args.report_out is not None:
            write_release_audio_quality_action_queue_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "manual-items":
        result = signoff_store.list_manual_items(args.queue_id)
        return {"ok": True, **result, "status": "passed"}
    if args.action == "resolve-manual":
        resolution = signoff_store.resolve_manual_item(
            args.queue_id,
            args.item_id,
            {"status": args.status, "resolved_by": args.resolved_by, "role": args.role, "reason": args.reason},
        )
        return {"ok": True, "resolution": resolution, "status": "passed"}
    if args.action == "closeout":
        closeout = signoff_store.refresh_closeout(args.queue_id)
        return {"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "signoff":
        result = signoff_store.signoff(args.queue_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result}
    if args.action == "archive":
        result = signoff_store.export_archive(args.queue_id)
        return {"ok": result.get("status") == "passed", **result}
    if args.action == "archive-zip":
        result = signoff_store.build_archive_zip(args.queue_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-archive":
        report = signoff_store.verify_archive(
            args.queue_id,
            strict=args.strict,
            require_current_queue=args.require_current_queue,
            require_signed=args.require_signed,
            queue_zip_path=args.queue_zip,
            queue_verification_report_path=args.queue_verification_report,
            observatory_zip_path=args.observatory_zip,
            observatory_verification_report_path=args.observatory_verification_report,
            evidence_root=args.evidence_root,
        )
        if args.report_out is not None:
            write_release_audio_quality_action_queue_signoff_archive_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-quality-actions command.")

def _release_audio_command_center_evidence_from_args(args: argparse.Namespace) -> JsonDocument:
    return {
        "certification": {"zip": getattr(args, "certification_zip", None), "verification_report": getattr(args, "certification_verification_report", None)},
        "timeline": {"zip": getattr(args, "timeline_zip", None), "verification_report": getattr(args, "timeline_verification_report", None)},
        "regression": {"zip": getattr(args, "regression_zip", None), "verification_report": getattr(args, "regression_verification_report", None)},
        "baseline_governance": {"zip": getattr(args, "baseline_registry_zip", None), "verification_report": getattr(args, "baseline_registry_verification_report", None)},
        "regression_response": {"zip": getattr(args, "regression_response_zip", None), "verification_report": getattr(args, "regression_response_verification_report", None)},
        "observatory": {"zip": getattr(args, "observatory_zip", None), "verification_report": getattr(args, "observatory_verification_report", None)},
        "action_queue": {"zip": getattr(args, "action_queue_zip", None), "verification_report": getattr(args, "action_queue_verification_report", None)},
        "action_queue_signoff": {"zip": getattr(args, "action_queue_signoff_archive", None), "verification_report": getattr(args, "action_queue_signoff_verification_report", None)},
        "evidence_root": getattr(args, "evidence_root", None),
    }

__all__ = ('_run_release_audio_regression_command', '_run_release_audio_baseline_command', '_run_release_audio_regression_response_command', '_run_release_audio_quality_observatory_command', '_run_release_audio_quality_actions_command', '_release_audio_command_center_evidence_from_args')
