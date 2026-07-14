from __future__ import annotations

from .dependencies import *

from .part_006 import build_acceptance_kb_parser, build_planning_rule_governance_parser, build_planning_rule_impact_parser

from .part_010 import print_acceptance_kb_result, print_planning_rule_governance_result, print_planning_rule_impact_result

def _execute_planning_rule_governance(argv: list[str]) -> None:
    raw_args = ['planning-rule-governance', *argv]
    pass
    parser = build_planning_rule_governance_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleGovernanceStore()
    if args.action == "active":
        version = store.active_version()
        result = {"ok": True, "active": store.active_pointer(), "version": version.to_dict() if version else {}, "summary": store.active_summary()}
    elif args.action == "versions":
        versions = store.list_versions(include_archived=args.include_archived)
        result = {"ok": True, "versions": [version.to_dict() for version in versions], "summary": {"version_count": len(versions), "active": store.active_summary()}}
    elif args.action == "version":
        version = store.read_version(args.version_id)
        result = {"ok": True, "version": version.to_dict(), "frozen_ruleset_summary": {}, "summary": governance_summary(version, active=store.active_pointer(), evidence_stale=store.version_evidence_is_stale(version))}
    elif args.action == "promotions":
        promotions = store.list_promotions(include_archived=args.include_archived)
        result = {"ok": True, "promotions": [promotion.to_dict() for promotion in promotions], "summary": {"promotion_count": len(promotions)}}
    elif args.action == "promotion":
        promotion = store.read_promotion(args.promotion_id)
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "promote-request":
        promotion = store.create_promotion({"ruleset_id": args.ruleset_id, "simulation_id": args.simulation_id, "note": args.note})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "approve":
        promotion = store.approve_promotion(args.promotion_id, {"approved_by": args.approved_by, "approval_note": args.note, "force": args.force, "override_reason": args.override_reason})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "reject":
        promotion = store.reject_promotion(args.promotion_id, {"rejected_by": args.rejected_by, "reason": args.reason})
        result = {"ok": True, "promotion": promotion.to_dict(), "summary": promotion_summary(promotion)}
    elif args.action == "promote":
        promoted = store.promote(args.promotion_id, {"promoted_by": args.promoted_by, "activation_note": args.activation_note})
        result = {"ok": True, "version": promoted["version"].to_dict(), "active": promoted["active"], "promotion": promoted["promotion"].to_dict(), "summary": promoted["summary"]}
    elif args.action == "rollback":
        rolled_back = store.rollback({"target_version_id": args.target_version_id, "rolled_back_by": args.rolled_back_by, "reason": args.reason})
        result = {"ok": True, "version": rolled_back["version"].to_dict(), "active": rolled_back["active"], "summary": rolled_back["summary"]}
    elif args.action == "events":
        events = store.events(limit=args.limit)
        result = {"ok": True, "events": events, "summary": {"event_count": len(events)}}
    else:
        parser.error("unknown planning-rule-governance action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_rule_governance_result(result)
    raise SystemExit(0)

def handle_planning_rule_governance(argv: list[str]) -> None:
    _execute_planning_rule_governance(argv)

def _execute_planning_rule_impact(argv: list[str]) -> None:
    raw_args = ['planning-rule-impact', *argv]
    pass
    parser = build_planning_rule_impact_parser()
    args = parser.parse_args(raw_args[1:])
    store = PlanningRuleImpactStore()
    if args.action == "refresh":
        scope = {"type": "release" if args.release_id else "project" if args.project_id else "global", "release_id": args.release_id, "project_id": args.project_id}
        report = store.refresh({"scope": scope, "include_legacy": not args.exclude_legacy, "include_superseded": not args.exclude_superseded})
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    elif args.action == "list":
        reports = store.list_reports(include_archived=args.include_archived, release_id=args.release_id, project_id=args.project_id)
        result = {"ok": True, "reports": [report.to_dict() for report in reports], "summary": {"report_count": len(reports), "latest": planning_rule_impact_summary(reports[0]) if reports else {"status": "missing"}}}
    elif args.action == "show":
        report = store.get_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report), "stale": store.report_is_stale(report), "integrity_ok": store.report_integrity_ok(report)}
    elif args.action == "refresh-existing":
        report = store.refresh_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    elif args.action == "archive":
        report = store.archive_report(args.report_id)
        result = {"ok": True, "impact_report": report.to_dict(), "summary": planning_rule_impact_summary(report)}
    else:
        parser.error("unknown planning-rule-impact action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_planning_rule_impact_result(result)
    raise SystemExit(0)

def handle_planning_rule_impact(argv: list[str]) -> None:
    _execute_planning_rule_impact(argv)

def _execute_acceptance_kb(argv: list[str]) -> None:
    raw_args = ['acceptance-kb', *argv]
    pass
    parser = build_acceptance_kb_parser()
    args = parser.parse_args(raw_args[1:])
    store = AcceptanceKnowledgeBaseStore()
    if args.action == "refresh":
        scope = {"type": "global", "project_id": args.project_id, "release_id": args.release_id}
        report = store.refresh(scope)
        result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
    elif args.action == "report":
        report = store.latest_report()
        result = {"ok": True, "knowledge_report": report, "summary": knowledge_report_summary(report)}
    elif args.action == "entries":
        entries = store.list_entries(include_hidden=args.include_hidden)
        result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
    elif args.action == "show":
        entry = store.read_entry(args.entry_id)
        result = {"ok": True, "entry": entry.to_dict(), "summary": knowledge_entry_summary(entry)}
    elif args.action == "search":
        query = {"issue_type": args.issue_type, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id, "outcome_status": args.outcome_status}
        entries = store.search_entries(query)
        result = {"ok": True, "entries": [knowledge_entry_summary(entry) for entry in entries], "summary": {"entry_count": len(entries)}}
    elif args.action == "recommend":
        recommendation = store.recommend({"issue_types": args.issue_types, "style": args.style, "song_id": args.song_id, "project_id": args.project_id, "release_id": args.release_id})
        result = {"ok": True, "recommendation": recommendation}
    else:
        parser.error("unknown acceptance-kb action")
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_acceptance_kb_result(result)
    raise SystemExit(0)

def handle_acceptance_kb(argv: list[str]) -> None:
    _execute_acceptance_kb(argv)

__all__ = ('_execute_planning_rule_governance', 'handle_planning_rule_governance', '_execute_planning_rule_impact', 'handle_planning_rule_impact', '_execute_acceptance_kb', 'handle_acceptance_kb')
