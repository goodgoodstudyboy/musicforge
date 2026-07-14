from __future__ import annotations

from .dependencies import *

def _run_audio_fix_sprint_command(args: argparse.Namespace) -> dict[str, Any]:
    pass

    store = AudioFixSprintStore()
    if args.action == "create":
        sprint = store.create_sprint({"session_ids": args.session_ids, "name": args.name, "include_test_audio": args.include_test_audio})
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "list":
        sprints = store.list_sprints()
        return {"ok": True, "sprints": sprints, "summary": {"sprint_count": len(sprints)}, "status": "passed"}
    if args.action == "detail":
        sprint = store.read_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "refresh":
        sprint = store.refresh_sprint(args.sprint_id)
        return {"ok": True, "sprint": sprint, "summary": sprint.get("summary", {}), "status": sprint.get("status")}
    if args.action == "create-drafts":
        result = store.create_drafts(args.sprint_id, {"draft_type": args.draft_type, "item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "generate-candidates":
        result = store.generate_candidates(args.sprint_id, {"item_ids": args.item_ids or []})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "review-candidate":
        result = store.review_candidate(
            args.sprint_id,
            args.item_id,
            args.candidate_id,
            {
                "preferred": args.preferred,
                "rating": args.rating,
                "rating_delta": args.rating_delta,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("candidate", {}).get("status")}
    if args.action == "select-candidate":
        result = store.select_candidate(args.sprint_id, args.item_id, args.candidate_id, {"selected_by": args.selected_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    if args.action == "create-recheck-session":
        result = store.create_recheck_session(args.sprint_id)
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "review-recheck":
        result = store.review_recheck_item(
            args.sprint_id,
            args.item_id,
            {
                "result": args.result,
                "rating": args.rating,
                "reviewer": {"name": args.reviewer, "role": args.role},
                "notes": args.notes,
                "playback_confirmed": args.playback_confirmed,
            },
        )
        return {"ok": True, **result, "summary": result.get("recheck_session", {}).get("summary", {}), "status": result.get("recheck_session", {}).get("status")}
    if args.action == "closeout":
        report = store.closeout_report(args.sprint_id)
        return {"ok": report.get("status") == "passed", "closeout": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "close":
        result = store.close_sprint(args.sprint_id, {"closed_by": args.closed_by})
        return {"ok": True, **result, "summary": result.get("sprint", {}).get("summary", {}), "status": result.get("sprint", {}).get("status")}
    raise ValueError("Unsupported audio-fix-sprint command.")

def _run_audio_campaign_command(args: argparse.Namespace) -> dict[str, Any]:
    pass
    pass
    pass
    pass
    pass
    pass
    pass

    store = AudioCampaignStore()
    governance_store = AudioCampaignGovernanceStore(campaign_store=store)
    planner_store = AudioCampaignPlannerStore(audio_lab_store=store.audio_lab_store, audio_campaign_store=store)
    remediation_store = AudioCampaignRemediationStore(planner_store=planner_store, campaign_store=store, fix_sprint_store=store.audio_fix_sprint_store)
    if args.action == "plan-release":
        plan = planner_store.refresh_plan(args.release_id)
        return {"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("preflight_summary", {}), "status": plan.get("status")}
    if args.action == "preflight-release":
        preflight = planner_store.preflight(args.release_id)
        return {"ok": preflight.get("status") == "passed", "preflight": preflight, "summary": preflight.get("summary", {}), "status": preflight.get("status")}
    if args.action == "create-from-release":
        result = planner_store.create_campaign_from_release(args.release_id, {"name": args.name, "minimum_rating": args.minimum_rating, "allow_failed_preflight": args.allow_failed_preflight})
        return {"ok": True, **result, "summary": result.get("link", {}).get("coverage", {}), "status": result.get("campaign", {}).get("status")}
    if args.action == "release-status":
        status = planner_store.status(args.release_id)
        return {"ok": status.get("status") != "failed", **status}
    if args.action == "release-link":
        link = planner_store.link_campaign(args.release_id, args.campaign_id)
        return {"ok": True, "link": link, "summary": link.get("coverage", {}), "status": link.get("coverage_status")}
    if args.action == "create":
        campaign = store.create_campaign(
            {
                "session_ids": args.session_ids,
                "name": args.name,
                "profile": args.profile,
                "allow_test_audio": args.allow_test_audio,
                "allow_synthetic_review": args.allow_synthetic_review,
                "minimum_rating": args.minimum_rating,
            }
        )
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "list":
        campaigns = store.list_campaigns()
        return {"ok": True, "campaigns": campaigns, "summary": {"campaign_count": len(campaigns)}, "status": "passed"}
    if args.action == "detail":
        campaign = store.read_campaign(args.campaign_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "refresh":
        campaign = store.refresh_campaign(args.campaign_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "link-session":
        campaign = store.link_listening_session(args.campaign_id, args.session_id)
        return {"ok": True, "campaign": campaign, "summary": campaign.get("summary", {}), "status": campaign.get("status")}
    if args.action == "create-fix-sprints":
        result = store.create_fix_sprints(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("report", {}).get("summary", {})}
    if args.action == "report":
        report = store.refresh_report(args.campaign_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "signoff":
        result = store.signoff(args.campaign_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {})}
    if args.action == "export":
        result = store.export_campaign(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {})}
    if args.action == "zip":
        result = store.build_zip(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(
            args.campaign_id,
            strict=args.strict,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_fix_sprints_closed=args.require_fix_sprints_closed,
            require_signed=args.require_signed,
        )
        if args.report_out is not None:
            write_audio_campaign_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "governance":
        report = governance_store.refresh_governance_report(args.campaign_id)
        return {"ok": report.get("status") == "signed", "governance": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "analytics":
        analytics = governance_store.refresh_analytics(args.campaign_id)
        return {"ok": True, "analytics": analytics, "summary": analytics.get("summary", {}), "status": analytics.get("status")}
    if args.action == "archive":
        manifest = governance_store.export_archive(args.campaign_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "archive-zip":
        result = governance_store.build_archive_zip(args.campaign_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-archive":
        report = governance_store.verify_archive(args.campaign_id, {"strict": args.strict, "require_signed": True, "require_verification_passed": True})
        if args.report_out is not None:
            write_audio_campaign_archive_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "remediation-plan":
        plan = remediation_store.refresh_plan(args.release_id)
        return {"ok": plan.get("status") != "blocked", "plan": plan, "summary": plan.get("summary", {}), "status": plan.get("status")}
    if args.action == "remediation-status":
        plan = remediation_store.refresh_plan(args.release_id)
        queue = remediation_store.build_action_queue(args.release_id)
        closeout = remediation_store.closeout_report(args.release_id)
        return {"ok": closeout.get("status") == "passed", "plan": plan, "queue": queue, "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "remediation-run-safe":
        result = remediation_store.run_safe_actions(args.release_id, {"closed_by": args.closed_by})
        return {"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {}), "status": result.get("closeout", {}).get("status")}
    if args.action == "remediation-closeout":
        closeout = remediation_store.closeout_report(args.release_id)
        return {"ok": closeout.get("status") == "passed", "closeout": closeout, "summary": closeout.get("summary", {}), "status": closeout.get("status")}
    if args.action == "remediation-signoff":
        result = remediation_store.signoff(args.release_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("closeout", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "remediation-export":
        result = remediation_store.export_package(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "remediation-zip":
        result = remediation_store.build_zip(args.release_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "remediation-verify":
        report = remediation_store.verify_zip(args.release_id, strict=args.strict, require_passed=args.require_passed, require_signed=args.require_signed)
        if args.report_out is not None:
            write_audio_campaign_remediation_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "change-request-create":
        cr = governance_store.create_change_request(args.campaign_id, {"created_by": args.created_by, "reason": args.reason, "risk": args.risk})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "change-request-approve":
        cr = governance_store.approve_change_request(args.campaign_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "signoff-reset":
        result = governance_store.reset_signoff(args.campaign_id, args.change_request_id, {"reason": args.reason})
        return {"ok": True, **result, "summary": {"change_request_id": result.get("change_request", {}).get("change_request_id")}, "status": result.get("status")}
    raise ValueError("Unsupported audio-campaign command.")

def _run_release_audio_certification_command(args: argparse.Namespace) -> dict[str, Any]:
    pass
    pass

    store = ReleaseAudioCertificationStore()
    if args.action == "refresh":
        report = store.refresh_report(args.release_id)
        return {"ok": report.get("status") == "passed", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "status":
        report = store.read_report(args.release_id, default={})
        matrix = store.read_matrix(args.release_id, default={})
        evidence = store.read_evidence_index(args.release_id, default={})
        blockers = store.read_blocker_register(args.release_id, default={})
        return {"ok": report.get("status") == "passed", "report": report, "matrix": matrix, "evidence_index": evidence, "blocker_register": blockers, "summary": report.get("summary", {}), "status": report.get("status") or "missing"}
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
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_remediation_when_needed=args.require_remediation_when_needed,
        )
        if args.report_out is not None:
            write_release_audio_certification_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-certification command.")

def _run_release_audio_timeline_command(args: argparse.Namespace) -> dict[str, Any]:
    pass
    pass

    store = ReleaseAudioTimelineStore()
    if args.action == "refresh":
        result = store.refresh_timeline(args.release_id, force_new=bool(args.force_new))
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "status":
        timeline_id = args.timeline_id or None
        report = store.read_timeline(args.release_id, timeline_id)
        signoff = read_json(store.signoff_path(args.release_id, timeline_id)) if store.signoff_path(args.release_id, timeline_id).exists() else {}
        return {"ok": report.get("status") == "passed", "timeline_id": report.get("timeline_id"), "report": report, "signoff": signoff, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "events":
        result = store.read_events(args.release_id, args.timeline_id or None)
        return {"ok": True, **result, "summary": {"event_count": len(result.get("events") or [])}, "status": "passed"}
    if args.action == "signoff":
        result = store.signoff_timeline(args.release_id, args.timeline_id or None, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, **result, "summary": result.get("report", {}).get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_timeline(args.release_id, args.timeline_id or None)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}), "status": result.get("status")}
    if args.action == "zip":
        result = store.build_zip(args.release_id, args.timeline_id or None)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}, "status": result.get("status")}
    if args.action == "verify":
        report = store.verify_zip(
            args.release_id,
            args.timeline_id or None,
            strict=args.strict,
            require_passed=args.require_passed,
            require_signed=args.require_signed,
            require_real_audio=args.require_real_audio,
            require_manual_review=args.require_manual_review,
            require_current_certification=args.require_current_certification,
        )
        if args.report_out is not None:
            write_release_audio_timeline_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported release-audio-timeline command.")

__all__ = ('_run_audio_fix_sprint_command', '_run_audio_campaign_command', '_run_release_audio_certification_command', '_run_release_audio_timeline_command')
