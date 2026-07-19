from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document

from typing import Any as _InterfaceType

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

from . import dependencies as _commands_quality_parts_dependencies

from .release_audio_regression_command import _release_audio_command_center_evidence_from_args
AcceptanceAnalyticsStore, AcceptanceFixPlanReviewStore, AcceptanceFixPlanningStore, AcceptanceFixSprintStore, AcceptanceKnowledgeBaseStore, AcceptanceStore, AnalyticsScope, Any, AudioCampaignGovernanceStore, AudioCampaignPlannerStore, AudioCampaignRemediationStore, AudioCampaignStore, AudioEncodingProfileStore, AudioEncodingStore, AudioFixSprintStore, AudioLabStore, AudioProfileStore, AudioReviewEvidenceStore, CommandSpec, DistributionStore, EncodedAudioAcceptanceStore, FormatDecisionStore, Path, PlanningRuleGovernanceStore, PlanningRuleImpactStore, PlanningRuleSimulationStore, ProjectStore, ProviderConfig, ProviderError, ReleaseAudioBaselineGovernanceStore, ReleaseAudioCertificationStore, ReleaseAudioCommandCenterStore, ReleaseAudioQualityActionQueueSignoffStore, ReleaseAudioQualityActionQueueStore, ReleaseAudioQualityObservatoryStore, ReleaseAudioRegressionResponseStore, ReleaseAudioRegressionStore, ReleaseAudioTimelineStore, ReleaseStore, SongRequest, acceptance_analytics_summary, analyze_wav_health, argparse, audio_campaign_archive_verification_exit_code, audio_campaign_remediation_verification_exit_code, audio_campaign_verification_exit_code, audio_review_summary_public, build_acceptance_diff, build_acceptance_report, build_auth_config, default_acceptance_song_cases, encoded_audio_acceptance_summary_public, evidence_to_verifier_kwargs, fix_plan_review_summary, fix_plan_summary, fix_sprint_summary, generate_request, get_acceptance_profile, governance_summary, json, knowledge_entry_summary, knowledge_report_summary, load_provider_config, music_health_allows_review, normalize_required_profiles, os, planning_rule_impact_summary, planning_simulation_summary, promotion_summary, provider_configured, read_json, release_audio_baseline_registry_verification_exit_code, release_audio_certification_verification_exit_code, release_audio_command_center_verification_exit_code, release_audio_quality_action_queue_signoff_archive_verification_exit_code, release_audio_quality_action_queue_verification_exit_code, release_audio_quality_observatory_verification_exit_code, release_audio_regression_response_verification_exit_code, release_audio_regression_verification_exit_code, release_audio_timeline_verification_exit_code, ruleset_summary, sys, test_provider_config, unified_command_center_evidence_review_acceptance_verification_exit_code, unified_release_program_continuity_acceptance_change_verification_exit_code, unified_release_program_continuity_acceptance_verification_exit_code, unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, verification_exit_code, verify_audio_campaign_archive_package, verify_audio_campaign_package, verify_audio_campaign_remediation_package, verify_release_audio_baseline_registry_package, verify_release_audio_certification_package, verify_release_audio_command_center_package, verify_release_audio_quality_action_queue_package, verify_release_audio_quality_action_queue_signoff_archive_package, verify_release_audio_quality_observatory_package, verify_release_audio_regression_package, verify_release_audio_regression_response_package, verify_release_audio_timeline_package, verify_unified_command_center_evidence_review_acceptance_package, verify_unified_release_program_continuity_acceptance_change_package, verify_unified_release_program_continuity_acceptance_package, verify_unified_release_program_continuity_command_center_acceptance_change_package, verify_unified_release_program_continuity_command_center_acceptance_package, write_audio_campaign_archive_verification_report, write_audio_campaign_remediation_verification_report, write_audio_campaign_verification_report, write_interface_document, write_json, write_release_audio_baseline_registry_verification_report, write_release_audio_certification_verification_report, write_release_audio_command_center_verification_report, write_release_audio_quality_action_queue_signoff_archive_verification_report, write_release_audio_quality_action_queue_verification_report, write_release_audio_quality_observatory_verification_report, write_release_audio_regression_response_verification_report, write_release_audio_regression_verification_report, write_release_audio_timeline_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_acceptance_change_verification_report, write_verification_report = _commands_quality_parts_dependencies.AcceptanceAnalyticsStore, _commands_quality_parts_dependencies.AcceptanceFixPlanReviewStore, _commands_quality_parts_dependencies.AcceptanceFixPlanningStore, _commands_quality_parts_dependencies.AcceptanceFixSprintStore, _commands_quality_parts_dependencies.AcceptanceKnowledgeBaseStore, _commands_quality_parts_dependencies.AcceptanceStore, _commands_quality_parts_dependencies.AnalyticsScope, _commands_quality_parts_dependencies.Any, _commands_quality_parts_dependencies.AudioCampaignGovernanceStore, _commands_quality_parts_dependencies.AudioCampaignPlannerStore, _commands_quality_parts_dependencies.AudioCampaignRemediationStore, _commands_quality_parts_dependencies.AudioCampaignStore, _commands_quality_parts_dependencies.AudioEncodingProfileStore, _commands_quality_parts_dependencies.AudioEncodingStore, _commands_quality_parts_dependencies.AudioFixSprintStore, _commands_quality_parts_dependencies.AudioLabStore, _commands_quality_parts_dependencies.AudioProfileStore, _commands_quality_parts_dependencies.AudioReviewEvidenceStore, _commands_quality_parts_dependencies.CommandSpec, _commands_quality_parts_dependencies.DistributionStore, _commands_quality_parts_dependencies.EncodedAudioAcceptanceStore, _commands_quality_parts_dependencies.FormatDecisionStore, _commands_quality_parts_dependencies.Path, _commands_quality_parts_dependencies.PlanningRuleGovernanceStore, _commands_quality_parts_dependencies.PlanningRuleImpactStore, _commands_quality_parts_dependencies.PlanningRuleSimulationStore, _commands_quality_parts_dependencies.ProjectStore, _commands_quality_parts_dependencies.ProviderConfig, _commands_quality_parts_dependencies.ProviderError, _commands_quality_parts_dependencies.ReleaseAudioBaselineGovernanceStore, _commands_quality_parts_dependencies.ReleaseAudioCertificationStore, _commands_quality_parts_dependencies.ReleaseAudioCommandCenterStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueSignoffStore, _commands_quality_parts_dependencies.ReleaseAudioQualityActionQueueStore, _commands_quality_parts_dependencies.ReleaseAudioQualityObservatoryStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionResponseStore, _commands_quality_parts_dependencies.ReleaseAudioRegressionStore, _commands_quality_parts_dependencies.ReleaseAudioTimelineStore, _commands_quality_parts_dependencies.ReleaseStore, _commands_quality_parts_dependencies.SongRequest, _commands_quality_parts_dependencies.acceptance_analytics_summary, _commands_quality_parts_dependencies.analyze_wav_health, _commands_quality_parts_dependencies.argparse, _commands_quality_parts_dependencies.audio_campaign_archive_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_remediation_verification_exit_code, _commands_quality_parts_dependencies.audio_campaign_verification_exit_code, _commands_quality_parts_dependencies.audio_review_summary_public, _commands_quality_parts_dependencies.build_acceptance_diff, _commands_quality_parts_dependencies.build_acceptance_report, _commands_quality_parts_dependencies.build_auth_config, _commands_quality_parts_dependencies.default_acceptance_song_cases, _commands_quality_parts_dependencies.encoded_audio_acceptance_summary_public, _commands_quality_parts_dependencies.evidence_to_verifier_kwargs, _commands_quality_parts_dependencies.fix_plan_review_summary, _commands_quality_parts_dependencies.fix_plan_summary, _commands_quality_parts_dependencies.fix_sprint_summary, _commands_quality_parts_dependencies.generate_request, _commands_quality_parts_dependencies.get_acceptance_profile, _commands_quality_parts_dependencies.governance_summary, _commands_quality_parts_dependencies.json, _commands_quality_parts_dependencies.knowledge_entry_summary, _commands_quality_parts_dependencies.knowledge_report_summary, _commands_quality_parts_dependencies.load_provider_config, _commands_quality_parts_dependencies.music_health_allows_review, _commands_quality_parts_dependencies.normalize_required_profiles, _commands_quality_parts_dependencies.os, _commands_quality_parts_dependencies.planning_rule_impact_summary, _commands_quality_parts_dependencies.planning_simulation_summary, _commands_quality_parts_dependencies.promotion_summary, _commands_quality_parts_dependencies.provider_configured, _commands_quality_parts_dependencies.read_json, _commands_quality_parts_dependencies.release_audio_baseline_registry_verification_exit_code, _commands_quality_parts_dependencies.release_audio_certification_verification_exit_code, _commands_quality_parts_dependencies.release_audio_command_center_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_signoff_archive_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_action_queue_verification_exit_code, _commands_quality_parts_dependencies.release_audio_quality_observatory_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_response_verification_exit_code, _commands_quality_parts_dependencies.release_audio_regression_verification_exit_code, _commands_quality_parts_dependencies.release_audio_timeline_verification_exit_code, _commands_quality_parts_dependencies.ruleset_summary, _commands_quality_parts_dependencies.sys, _commands_quality_parts_dependencies.test_provider_config, _commands_quality_parts_dependencies.unified_command_center_evidence_review_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_acceptance_verification_exit_code, _commands_quality_parts_dependencies.unified_release_program_continuity_command_center_acceptance_change_verification_exit_code, _commands_quality_parts_dependencies.verification_exit_code, _commands_quality_parts_dependencies.verify_audio_campaign_archive_package, _commands_quality_parts_dependencies.verify_audio_campaign_package, _commands_quality_parts_dependencies.verify_audio_campaign_remediation_package, _commands_quality_parts_dependencies.verify_release_audio_baseline_registry_package, _commands_quality_parts_dependencies.verify_release_audio_certification_package, _commands_quality_parts_dependencies.verify_release_audio_command_center_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_package, _commands_quality_parts_dependencies.verify_release_audio_quality_action_queue_signoff_archive_package, _commands_quality_parts_dependencies.verify_release_audio_quality_observatory_package, _commands_quality_parts_dependencies.verify_release_audio_regression_package, _commands_quality_parts_dependencies.verify_release_audio_regression_response_package, _commands_quality_parts_dependencies.verify_release_audio_timeline_package, _commands_quality_parts_dependencies.verify_unified_command_center_evidence_review_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_acceptance_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_change_package, _commands_quality_parts_dependencies.verify_unified_release_program_continuity_command_center_acceptance_package, _commands_quality_parts_dependencies.write_audio_campaign_archive_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_remediation_verification_report, _commands_quality_parts_dependencies.write_audio_campaign_verification_report, _commands_quality_parts_dependencies.write_interface_document, _commands_quality_parts_dependencies.write_json, _commands_quality_parts_dependencies.write_release_audio_baseline_registry_verification_report, _commands_quality_parts_dependencies.write_release_audio_certification_verification_report, _commands_quality_parts_dependencies.write_release_audio_command_center_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_signoff_archive_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_action_queue_verification_report, _commands_quality_parts_dependencies.write_release_audio_quality_observatory_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_response_verification_report, _commands_quality_parts_dependencies.write_release_audio_regression_verification_report, _commands_quality_parts_dependencies.write_release_audio_timeline_verification_report, _commands_quality_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_quality_parts_dependencies.write_unified_release_program_continuity_command_center_acceptance_change_verification_report, _commands_quality_parts_dependencies.write_verification_report
def _run_release_audio_command_center_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass

    store = ReleaseAudioCommandCenterStore()
    evidence = _release_audio_command_center_evidence_from_args(args)
    if args.action == "refresh":
        report = store.refresh(args.release_id, evidence)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "report":
        report = store.read_report(args.release_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "inventory":
        inventory = store.read_inventory(args.release_id)
        return {"ok": True, "inventory": inventory, "summary": inventory.get("summary", {}), "status": "passed"}
    if args.action == "readiness":
        readiness = read_json(store.readiness_path(args.release_id))
        return {"ok": readiness.get("status") == "ready", "readiness": readiness, "summary": readiness.get("summary", {}), "status": readiness.get("status")}
    if args.action == "gap-plan":
        gap_plan = read_json(store.gap_plan_path(args.release_id))
        return {"ok": gap_plan.get("status") == "passed", "gap_plan": gap_plan, "summary": gap_plan.get("summary", {}), "status": gap_plan.get("status")}
    if args.action == "runbook":
        runbook = store.create_runbook(args.release_id, evidence)
        return {"ok": True, "runbook": runbook, "summary": runbook.get("summary", {}), "status": "passed"}
    if args.action == "run-safe":
        result = store.run_safe(args.release_id, evidence)
        return {"ok": int((result.get("summary") or {}).get("failed_count") or 0) == 0, "runbook_results": result, "summary": result.get("summary", {}), "status": "passed" if int((result.get("summary") or {}).get("failed_count") or 0) == 0 else "failed"}
    if args.action == "export":
        result = store.export_package(args.release_id, evidence)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {})}
    if args.action == "zip":
        result = store.build_zip(args.release_id, evidence)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(args.release_id, evidence=evidence, strict=args.strict, require_ready=args.require_ready)
        if args.report_out is not None:
            write_release_audio_command_center_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-command-center command.")

def _command_center_acceptance_payload(args: argparse.Namespace) -> ImplementationDocument:
    payload = {
        "review_pack": getattr(args, "review_pack", None),
        "review_pack_verification_report": getattr(args, "review_pack_verification_report", None),
        "accepted_evidence_dir": getattr(args, "accepted_evidence_dir", None),
        "response_proof_dir": getattr(args, "response_proof_dir", None),
        "command_center_signoff_archive": getattr(args, "command_center_signoff_archive", None),
        "command_center_signoff_archive_verification_report": getattr(args, "command_center_signoff_archive_verification_report", None),
        "command_center_final_handoff": getattr(args, "command_center_final_handoff", None),
        "command_center_final_handoff_verification_report": getattr(args, "command_center_final_handoff_verification_report", None),
        "command_center_signoff_binding": getattr(args, "command_center_signoff_binding", None),
        "command_center": getattr(args, "command_center", None),
        "command_center_verification_report": getattr(args, "command_center_verification_report", None),
        "command_center_evidence_manifest": getattr(args, "command_center_evidence_manifest", None),
        "signed_by": getattr(args, "signed_by", None),
        "role": getattr(args, "role", None),
        "reason": getattr(args, "reason", None),
    }
    policy = {}
    if getattr(args, "min_accepted_count", None) is not None:
        policy["min_accepted_count"] = args.min_accepted_count
    if getattr(args, "min_organization_count", None) is not None:
        policy["min_organization_count"] = args.min_organization_count
    if getattr(args, "required_role", None):
        policy["required_roles"] = args.required_role
    if policy:
        payload["policy"] = policy
    return {key: value for key, value in payload.items() if value is not None}

def _print_audio_lab_result(result: ImplementationDocument, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("environment", {}).get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Lab")
    print(f"status: {status}")
    if "environment" in result:
        summary = result["environment"].get("summary", {})
        print(f"renderer: {summary.get('renderer_status')}")
        print(f"real_audio_ready: {summary.get('real_audio_ready')}")
    if "smoke_run" in result:
        smoke = result["smoke_run"]
        print(f"smoke_run: {smoke.get('smoke_run_id')}")
    if "session" in result:
        session = result["session"]
        print(f"session: {session.get('session_id')}")
    if "comparison" in result:
        comparison = result["comparison"]
        print(f"comparison: {comparison.get('comparison_id')}")

def _print_audio_fix_sprint_result(result: ImplementationDocument, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Fix Sprint")
    print(f"status: {status}")
    summary = _as_document(result.get("summary"))
    if summary:
        details = []
        for key in ("issue_count", "candidate_count", "selected_count", "resolved_count", "manual_recheck_count", "test_fake_count"):
            if key in summary:
                details.append(f"{key}={summary.get(key)}")
        if details:
            print("summary: " + " ".join(details))
    if "sprint" in result:
        sprint = result["sprint"]
        print(f"sprint: {sprint.get('fix_sprint_id')} stale={sprint.get('stale', False)}")
    if "closeout" in result:
        closeout = result["closeout"]
        blockers = closeout.get("blockers") or []
        print(f"closeout: {closeout.get('status')} blockers={','.join(blockers) if blockers else '-'}")

def _print_audio_campaign_result(result: ImplementationDocument, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Audio Campaign")
    print(f"status: {status}")
    summary = _as_document(result.get("summary"))
    details = []
    for key in ("case_count", "manual_review_count", "real_audio_count", "test_fake_count", "open_fix_sprint_count"):
        if key in summary:
            details.append(f"{key}={summary.get(key)}")
    if details:
        print("summary: " + " ".join(details))
    if "campaign" in result:
        campaign = result["campaign"]
        print(f"campaign: {campaign.get('campaign_id')} {campaign.get('name')}")
    if "verification" in result:
        verification = result["verification"]
        print(f"verification: {verification.get('status')} blockers={verification.get('blockers') or []}")

def _print_release_audio_certification_result(result: ImplementationDocument, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("summary", {}).get("status") or "unknown"
    print("MusicForge Release Audio Certification")
    print(f"status: {status}")
    summary = _as_document(result.get("summary"))
    details = []
    for key in ("track_count", "manual_accepted_track_count", "real_audio_track_count", "blocker_count", "remediation_status"):
        if key in summary:
            details.append(f"{key}={summary.get(key)}")
    if details:
        print("summary: " + " ".join(details))
    if "verification" in result:
        verification = result["verification"]
        print(f"verification: {verification.get('status')} blockers={verification.get('blockers') or []}")

def run_acceptance_check(
    *,
    out_dir: _InterfaceType,
    profile_id: str,
    cases: int,
    render_audio_mode: str,
    auto_review: bool,
    min_rating: int,
    manual_required: bool = False,
) -> DomainDocument:
    pass
    pass
    pass

    profile = get_acceptance_profile(profile_id)
    if cases == 6 and profile.case_count != 6:
        cases = profile.case_count
    if render_audio_mode == "require":
        render_audio_mode = "always"
    render_audio_mode = render_audio_mode if render_audio_mode != "auto" or profile.render_audio == "auto" else profile.render_audio
    store = AcceptanceStore(out_dir)
    suite_payload = {
        "name": f"v4.5 {profile.profile_id} music acceptance",
        "mode": profile.profile_id,
        "profile_id": profile.profile_id,
        "min_rating": max(min_rating, profile.min_rating),
        "require_audio_if_renderer_configured": profile.require_audio_if_renderer_configured,
        "allow_synthetic_review": profile.allow_synthetic_review and not manual_required,
        "require_manual_review": profile.require_manual_review or manual_required,
        "release_ready_profile": profile.release_ready,
    }
    if render_audio_mode == "never":
        suite_payload["require_audio_if_renderer_configured"] = False
    suite = store.create_suite(suite_payload)
    for index, song in enumerate(default_acceptance_song_cases(cases), start=1):
        request = song["request"]
        case = store.add_case(
            suite.suite_id,
            {
                "name": song.get("title") or request.get("style"),
                "source_type": "regression_songbook",
                "song_id": song.get("song_id"),
                "songbook_id": song.get("songbook_id") or "builtin_v1",
                "songbook_version": song.get("songbook_version") or "2026-05-19",
                "expectations": song.get("expectations") or {},
                "request": request,
            },
        )
        store.generate_case(suite.suite_id, case.case_id, render_audio_mode=render_audio_mode)
        health = store.run_health(suite.suite_id, case.case_id)
        if auto_review and profile.allow_synthetic_review and music_health_allows_review(health):
            store.write_review(
                suite.suite_id,
                case.case_id,
                {
                    "rating": max(min_rating, 4),
                    "status": "accepted",
                    "playback_confirmed": True,
                    "listened_by": "acceptance-check",
                    "audio_mode": "midi",
                    "review_mode": "synthetic",
                    "notes": f"Synthetic acceptance smoke review for case {index}; MIDI artifact was generated and health checks were reviewed.",
                },
            )
    report = store.build_report(suite.suite_id) if auto_review else build_acceptance_report(store, store.get_suite(suite.suite_id))
    if not auto_review:
        report = {**report, "status": "needs_review", "summary": {**report.get("summary", {}), "review_required": True}}
        write_interface_document(store.report_path(suite.suite_id), report)
    elif report.get("status") == "passed":
        store.signoff(suite.suite_id, {"signed_by": "acceptance-check", "notes": "Synthetic CI acceptance signoff."})
        report = store.read_report(suite.suite_id)
    return report

def print_acceptance_check_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge acceptance-check")
    print(f"status: {report.get('status')}")
    print(f"suite: {report.get('suite_id')}")
    print(f"cases: {summary.get('case_count', 0)}")
    print(f"accepted: {summary.get('accepted_count', 0)}")
    print(f"average_rating: {summary.get('average_rating')}")
    print(f"renderer: {summary.get('renderer_status')}")
    print(f"acceptance_status: {summary.get('acceptance_status')}")

def print_acceptance_diff_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    print("MusicForge acceptance-diff")
    print(f"status: {report.get('status')}")
    print(f"left: {report.get('left_suite_id')}")
    print(f"right: {report.get('right_suite_id')}")
    print(f"songs: {summary.get('song_count', 0)}")
    print(f"new_blockers: {summary.get('new_blocker_count', 0)}")
    print(f"rating_regressions: {summary.get('rating_regression_count', 0)}")

def print_release_audio_review_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    review = _as_document(result.get("review"))
    print("MusicForge release-audio-review")
    print(f"release: {result.get('release_id') or summary.get('release_id') or '-'}")
    print(f"status: {summary.get('status') or review.get('status') or result.get('status') or '-'}")
    print(f"tracks: {summary.get('track_count', 0)}")
    print(f"manual accepted: {summary.get('manual_accepted_track_count', 0)}")
    print(f"missing: {len(summary.get('missing_track_ids', []) or [])}")
    print(f"stale: {summary.get('stale_review_count', 0)}")
    print(f"needs_fix: {summary.get('needs_fix_track_count', 0)}")
    if review:
        print(f"review: {review.get('review_id')}")
    if result.get("task_id"):
        print(f"task: {result.get('task_id')}")
    if result.get("reviews") is not None:
        print(f"reviews: {len(result.get('reviews') or [])}")

def print_acceptance_analytics_report(report: DomainDocument) -> None:
    summary = _as_document(report.get("summary"))
    source = _as_document(report.get("source_summary"))
    print("MusicForge acceptance-analytics")
    print(f"readiness: {summary.get('readiness_status')}")
    print(f"scope: {(report.get('scope') or {}).get('type') if isinstance(report.get('scope'), dict) else 'global'}")
    print(f"report: {report.get('report_id')}")
    print(f"suites: {source.get('suite_count', 0)}")
    print(f"cases: {summary.get('case_count', 0)}")
    print(f"manual_coverage: {summary.get('manual_coverage_rate', 0.0)}")
    print(f"average_rating: {summary.get('average_rating')}")
    print(f"issues: {summary.get('issue_count', 0)}")
    print(f"recommendations: {summary.get('recommendation_count', 0)}")

def print_acceptance_fix_sprint_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    sprint = _as_document(result.get("fix_sprint"))
    delta = _as_document(result.get("delta_report"))
    closeout = _as_document(result.get("closeout_report"))
    print("MusicForge acceptance-fix-sprint")
    print(f"fix_sprint: {summary.get('fix_sprint_id') or sprint.get('fix_sprint_id') or delta.get('fix_sprint_id') or closeout.get('fix_sprint_id') or '-'}")
    print(f"status: {summary.get('status') or sprint.get('status') or closeout.get('status') or '-'}")
    if "item_count" in summary:
        print(f"items: {summary.get('item_count', 0)}")
        print(f"open_items: {summary.get('open_item_count', 0)}")
    if result.get("results"):
        print(f"task_results: {len(result.get('results') or [])}")
    if delta:
        print(f"delta_status: {(delta.get('summary') or {}).get('status')}")
    if closeout:
        print(f"closeout_status: {closeout.get('status')}")

def print_acceptance_fix_plan_result(result: DomainDocument) -> None:
    summary = _as_document(result.get("summary"))
    plan = result.get("fix_plan") or result.get("fix_plan_preview")
    plan = _as_document(plan)
    review = _as_document(result.get("outcome_review"))
    if review:
        print("MusicForge acceptance-fix-plan review")
        print(f"review: {summary.get('review_id') or review.get('review_id') or '-'}")
        print(f"plan: {summary.get('plan_id') or review.get('plan_id') or '-'}")
        print(f"sprint: {summary.get('fix_sprint_id') or review.get('fix_sprint_id') or '-'}")
        print(f"status: {summary.get('status') or review.get('status') or '-'}")
        print(f"effectiveness: {summary.get('plan_effectiveness_score') if summary.get('plan_effectiveness_score') is not None else '-'}")
        print(f"kb_helpfulness: {summary.get('kb_evidence_helpfulness') or '-'}")
        print(f"warnings: {summary.get('warning_count', 0)}")
        return
    print("MusicForge acceptance-fix-plan")
    print(f"plan: {summary.get('plan_id') or plan.get('plan_id') or '-'}")
    print(f"status: {summary.get('status') or plan.get('status') or '-'}")
    print(f"items: {summary.get('planned_item_count', 0)}")
    print(f"kb_matches: {summary.get('kb_match_count', 0)}")
    if result.get("fix_sprint"):
        print(f"created_fix_sprint: {(result.get('fix_sprint') or {}).get('fix_sprint_id')}")

__all__ = ('_run_release_audio_command_center_command', '_command_center_acceptance_payload', '_print_audio_lab_result', '_print_audio_fix_sprint_result', '_print_audio_campaign_result', '_print_release_audio_certification_result', 'run_acceptance_check', 'print_acceptance_check_report', 'print_acceptance_diff_report', 'print_release_audio_review_result', 'print_acceptance_analytics_report', 'print_acceptance_fix_sprint_result', 'print_acceptance_fix_plan_result')
