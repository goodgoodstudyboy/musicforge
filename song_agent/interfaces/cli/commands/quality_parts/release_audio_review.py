from __future__ import annotations

from . import dependencies as _commands_quality_parts_dependencies

from .release_audio_quality_actions import build_acceptance_analytics_parser, build_acceptance_diff_parser, build_acceptance_fix_sprint_parser, build_encoded_audio_acceptance_parser, build_format_decision_parser, build_release_audio_review_parser

from .acceptance_fix_plan import build_acceptance_fix_plan_parser, build_planning_ruleset_parser, build_planning_simulation_parser

from .release_audio_command_center_command import print_acceptance_analytics_report, print_acceptance_diff_report, print_acceptance_fix_plan_result, print_acceptance_fix_sprint_result, print_release_audio_review_result

from .planning_ruleset import _acceptance_analytics_fail_on, print_planning_ruleset_result, print_planning_simulation_result
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, Any, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.Any, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def _execute_release_audio_review(argv: list[str]) -> None:
    raw_args = ['release-audio-review', *argv]
    pass
    pass
    pass
    parser = build_release_audio_review_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    store = AudioReviewEvidenceStore(release_store, project_store)
    if args.action == "list":
        reviews = store.list_reviews(args.release_id)
        summary = store.build_summary(args.release_id)
        result = {"ok": True, "release_id": args.release_id, "reviews": reviews, "summary": audio_review_summary_public(summary)}
    elif args.action == "summary":
        summary = store.write_summary(args.release_id) if args.write else store.build_summary(args.release_id)
        result = {"ok": True, "release_id": args.release_id, "summary": audio_review_summary_public(summary), "audio_review_summary": summary}
    elif args.action == "add":
        review = store.create_review(
            args.release_id,
            {
                "track_id": args.track_id,
                "status": args.status,
                "review_mode": args.review_mode,
                "rating": args.rating,
                "reviewer": {"name": args.reviewer},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        summary = store.build_summary(args.release_id)
        result = {"ok": True, "release_id": args.release_id, "review": review, "summary": audio_review_summary_public(summary)}
    elif args.action == "create-task":
        payload = {key: value for key, value in {"title": args.title, "instruction": args.instruction}.items() if value}
        result = {"ok": True, "release_id": args.release_id, **store.create_review_task_from_marker(args.release_id, args.review_id, args.marker_id, payload)}
    else:
        parser.error("unknown release-audio-review action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_release_audio_review_result(result)
    raise SystemExit(0)

def handle_release_audio_review(argv: list[str]) -> None:
    _execute_release_audio_review(argv)

def _execute_encoded_audio_acceptance(argv: list[str]) -> None:
    raw_args = ['encoded-audio-acceptance', *argv]
    pass
    pass
    pass
    pass
    pass
    parser = build_encoded_audio_acceptance_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
    encoding_store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
    store = EncodedAudioAcceptanceStore(release_store, project_store=project_store, audio_encoding_store=encoding_store)
    profiles = normalize_required_profiles(args.profiles)
    health = store.refresh_health(args.release_id, profiles) if args.refresh_health else {"profiles": store.list_health(args.release_id)}
    summary = store.write_summary(args.release_id, required_profiles=profiles) if args.write else store.build_summary(args.release_id, required_profiles=profiles)
    payload = {"ok": True, "release_id": args.release_id, "health": health, "summary": encoded_audio_acceptance_summary_public(summary), "encoded_audio_acceptance": summary}
    if args.report_out is not None:
        write_interface_document(args.report_out, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge encoded-audio-acceptance\nrelease: {args.release_id}\nstatus: {summary.get('status')}\nprofiles: {summary.get('profile_count', 0)}")
    raise SystemExit(0 if summary.get("status") == "passed" else 1)

def handle_encoded_audio_acceptance(argv: list[str]) -> None:
    _execute_encoded_audio_acceptance(argv)

def _execute_format_decision(argv: list[str]) -> None:
    raw_args = ['format-decision', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_format_decision_parser()
    args = parser.parse_args(raw_args[1:])
    project_store = ProjectStore()
    release_store = ReleaseStore(project_store=project_store)
    profile_store = AudioEncodingProfileStore(release_store.root.parent / "audio-encoding-profiles")
    encoding_store = AudioEncodingStore(release_store, project_store=project_store, profile_store=profile_store)
    distribution_store = DistributionStore(release_store)
    store = FormatDecisionStore(release_store, project_store=project_store, encoding_store=encoding_store, distribution_store=distribution_store)
    session = store.create_session(args.release_id, {"profiles": normalize_required_profiles(args.profiles)})
    matrix = store.build_matrix(args.release_id, session["session_id"])
    recommendation = store.build_recommendation(args.release_id, session["session_id"])
    selected = normalize_required_profiles(args.select) or recommendation.get("selected_defaults", [])
    archive = normalize_required_profiles(args.archive) or recommendation.get("archive_defaults", [])
    fallback = normalize_required_profiles(args.fallback)
    rejected = normalize_required_profiles(args.reject) or recommendation.get("rejected_defaults", [])
    session = store.select_profiles(
        args.release_id,
        session["session_id"],
        {
            "selected_profiles": selected,
            "archive_profiles": archive,
            "fallback_profiles": fallback,
            "rejected_profiles": rejected,
            "decided_by": args.decided_by,
            "reason": args.reason,
        },
    )
    report = store.build_report(args.release_id, session["session_id"])
    active = store.activate_session(args.release_id, session["session_id"]) if args.activate else {}
    payload = {"ok": True, "release_id": args.release_id, "session": session, "matrix": matrix, "recommendation": recommendation, "report": report, "active_session": active}
    if args.report_out is not None:
        write_interface_document(args.report_out, payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"MusicForge format-decision\nrelease: {args.release_id}\nstatus: {report.get('status')}\nselected: {', '.join(report.get('decision', {}).get('selected_profiles', []))}")
    raise SystemExit(0 if report.get("status") in {"passed", "warning"} else 1)

def handle_format_decision(argv: list[str]) -> None:
    _execute_format_decision(argv)

def _execute_acceptance_diff(argv: list[str]) -> None:
    raw_args = ['acceptance-diff', *argv]
    pass
    parser = build_acceptance_diff_parser()
    args = parser.parse_args(raw_args[1:])
    report = build_acceptance_diff(read_json(args.left_report), read_json(args.right_report))
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_acceptance_diff_report(report)
    raise SystemExit(0 if report.get("status") == "passed" else 1)

def handle_acceptance_diff(argv: list[str]) -> None:
    _execute_acceptance_diff(argv)

def _execute_acceptance_analytics(argv: list[str]) -> None:
    raw_args = ['acceptance-analytics', *argv]
    pass
    parser = build_acceptance_analytics_parser()
    args = parser.parse_args(raw_args[1:])
    scope = AnalyticsScope.from_values(scope_type=args.scope, suite_id=args.suite_id, release_id=args.release_id, project_id=args.project_id)
    store = AcceptanceAnalyticsStore()
    report = store.refresh(scope) if args.refresh else store.latest_report(scope)
    if args.report_out is not None:
        write_interface_document(args.report_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_acceptance_analytics_report(report)
    summary = acceptance_analytics_summary(report)
    raise SystemExit(1 if _acceptance_analytics_fail_on(str(summary.get("readiness_status") or ""), args.fail_on) else 0)

def handle_acceptance_analytics(argv: list[str]) -> None:
    _execute_acceptance_analytics(argv)

def _execute_acceptance_fix_sprint(argv: list[str]) -> None:
    raw_args = ['acceptance-fix-sprint', *argv]
    pass
    parser = build_acceptance_fix_sprint_parser()
    args = parser.parse_args(raw_args[1:])
    store = AcceptanceFixSprintStore()
    if args.action == "create":
        sprint = store.create_from_analytics(
            {
                "analytics_report_id": args.analytics_report_id,
                "name": args.name,
                "max_items": args.max_items,
                "recommendation_ids": args.recommendation_ids,
            }
        )
        items = store.read_items(sprint.fix_sprint_id)
        result = {"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)}
    elif args.action == "show":
        sprint = store.read_sprint(args.fix_sprint_id)
        items = store.read_items(args.fix_sprint_id)
        result = {"ok": True, "fix_sprint": sprint.to_dict(), "items": [item.to_dict() for item in items], "summary": fix_sprint_summary(sprint, items)}
    elif args.action == "list":
        sprints = store.list_sprints(include_archived=args.include_archived)
        result = {"ok": True, "fix_sprints": [sprint.to_dict() for sprint in sprints], "summary": {"fix_sprint_count": len(sprints)}}
    elif args.action == "create-review-tasks":
        result = {"ok": True, **store.create_review_tasks(args.fix_sprint_id, item_id=args.item_id)}
    elif args.action == "create-recheck-suite":
        result = {"ok": True, **store.create_recheck_suite(args.fix_sprint_id, {"profile_id": args.profile} if args.profile else {})}
    elif args.action == "delta":
        report = store.refresh_delta(args.fix_sprint_id) if args.refresh else store.read_delta(args.fix_sprint_id)
        result = {"ok": True, "delta_report": report, "summary": report.get("summary", {})}
    elif args.action == "close":
        report = store.close(args.fix_sprint_id, {"force": args.force, "override_reason": args.override_reason})
        result = {"ok": True, "closeout_report": report, "summary": report.get("summary", {})}
    else:
        parser.error("unknown acceptance-fix-sprint action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_acceptance_fix_sprint_result(result)
    raise SystemExit(0)

def handle_acceptance_fix_sprint(argv: list[str]) -> None:
    _execute_acceptance_fix_sprint(argv)

def _execute_acceptance_fix_plan(argv: list[str]) -> None:
    raw_args = ['acceptance-fix-plan', *argv]
    pass
    pass
    parser = build_acceptance_fix_plan_parser()
    args = parser.parse_args(raw_args[1:])
    store = AcceptanceFixPlanningStore()
    if args.action == "create":
        plan = store.create({"analytics_report_id": args.analytics_report_id, "kb_report_id": args.kb_report_id, "max_items": args.max_items, "include_hidden_kb": args.include_hidden_kb})
        result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
    elif args.action == "list":
        plans = store.list_plans(include_archived=args.include_archived)
        result = {"ok": True, "fix_plans": [plan.to_dict() for plan in plans], "summary": {"plan_count": len(plans)}}
    elif args.action == "show":
        plan = store.read_plan(args.plan_id)
        result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
    elif args.action == "refresh":
        plan = store.refresh_plan(args.plan_id)
        result = {"ok": True, "fix_plan": plan.to_dict(), "summary": fix_plan_summary(plan)}
    elif args.action == "create-fix-sprint":
        result = {"ok": True, **store.create_fix_sprint(args.plan_id, {"name": args.name, "planned_item_ids": args.planned_item_ids, "profile_id": args.profile})}
    elif args.action == "review":
        review_store = AcceptanceFixPlanReviewStore(plan_store=store, fix_sprint_store=store.fix_sprint_store, kb_store=store.kb_store, project_store=store.project_store)
        if args.refresh:
            review = review_store.refresh_for_plan(args.plan_id)
            result = {"ok": True, "outcome_review": review.to_dict(), "summary": fix_plan_review_summary(review)}
        else:
            review = review_store.get_or_missing_for_plan(args.plan_id)
            result = {"ok": True, "outcome_review": review, "summary": fix_plan_review_summary(review)}
    elif args.action == "recommend":
        preview = store.preview({"analytics_report_id": args.analytics_report_id, "kb_report_id": args.kb_report_id, "max_items": args.max_items, "include_hidden_kb": args.include_hidden_kb})
        result = {"ok": True, "fix_plan_preview": preview, "summary": fix_plan_summary(preview)}
    else:
        parser.error("unknown acceptance-fix-plan action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_acceptance_fix_plan_result(result)
    raise SystemExit(0)

def handle_acceptance_fix_plan(argv: list[str]) -> None:
    _execute_acceptance_fix_plan(argv)

def _execute_planning_ruleset(argv: list[str]) -> None:
    raw_args = ['planning-ruleset', *argv]
    pass
    parser = build_planning_ruleset_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleSimulationStore()
    if args.action == "create":
        payload = {"template": args.template, "name": args.name, "description": args.description}
        ruleset = store.create_ruleset(payload)
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "list":
        rulesets = store.list_rulesets(include_archived=args.include_archived)
        result = {"ok": True, "rulesets": [ruleset.to_dict() for ruleset in rulesets], "summary": {"ruleset_count": len(rulesets)}}
    elif args.action == "show":
        ruleset = store.read_ruleset(args.ruleset_id)
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "clone":
        ruleset = store.clone_ruleset(args.ruleset_id, {"name": args.name} if args.name else {})
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "archive":
        ruleset = store.archive_ruleset(args.ruleset_id)
        result = {"ok": True, "ruleset": ruleset.to_dict(), "summary": ruleset_summary(ruleset)}
    elif args.action == "validate":
        result = {"ok": True, "validation": store.validate_ruleset(args.ruleset_id)}
    else:
        parser.error("unknown planning-ruleset action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_ruleset_result(result)
    raise SystemExit(0)

def handle_planning_ruleset(argv: list[str]) -> None:
    _execute_planning_ruleset(argv)

def _execute_planning_simulation(argv: list[str]) -> None:
    raw_args = ['planning-simulation', *argv]
    pass
    parser = build_planning_simulation_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleSimulationStore()
    if args.action == "run":
        scope = {"type": "release" if args.release_id else "project" if args.project_id else "global", "release_id": args.release_id, "project_id": args.project_id}
        simulation = store.create_simulation({"ruleset_id": args.ruleset_id, "scope": scope, "review_ids": args.review_ids, "include_warning_reviews": args.include_warning_reviews, "exclude_synthetic_only": args.exclude_synthetic_only})
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "show":
        simulation = store.read_simulation(args.simulation_id)
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "refresh":
        simulation = store.refresh_simulation(args.simulation_id)
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "archive":
        simulation = store.archive_simulation(args.simulation_id)
        result = {"ok": True, "simulation": simulation.to_dict(), "summary": planning_simulation_summary(simulation)}
    elif args.action == "list":
        simulations = store.list_simulations(include_archived=args.include_archived)
        result = {"ok": True, "simulations": [simulation.to_dict() for simulation in simulations], "summary": {"simulation_count": len(simulations)}}
    else:
        parser.error("unknown planning-simulation action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_simulation_result(result)
    raise SystemExit(0)

def handle_planning_simulation(argv: list[str]) -> None:
    _execute_planning_simulation(argv)

__all__ = ('_execute_release_audio_review', 'handle_release_audio_review', '_execute_encoded_audio_acceptance', 'handle_encoded_audio_acceptance', '_execute_format_decision', 'handle_format_decision', '_execute_acceptance_diff', 'handle_acceptance_diff', '_execute_acceptance_analytics', 'handle_acceptance_analytics', '_execute_acceptance_fix_sprint', 'handle_acceptance_fix_sprint', '_execute_acceptance_fix_plan', 'handle_acceptance_fix_plan', '_execute_planning_ruleset', 'handle_planning_ruleset', '_execute_planning_simulation', 'handle_planning_simulation')
