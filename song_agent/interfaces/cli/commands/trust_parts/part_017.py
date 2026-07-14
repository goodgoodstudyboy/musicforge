from __future__ import annotations

from .dependencies import *

from .part_005 import build_trust_operations_hub_incidents_parser, build_trust_operations_incident_knowledge_parser

def _execute_trust_operations_hub_incidents(argv: list[str]) -> None:
    raw_args = ['trust-operations-hub-incidents', *argv]
    pass
    pass
    pass
    pass
    parser = build_trust_operations_hub_incidents_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    store = TrustOperationsIncidentStore(hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    incident_id = args.incident_id
    if args.refresh:
        refreshed = store.refresh_board(args.hub_id, {"report_id": args.report_id} if args.report_id else {})
        result.update(refreshed)
    if args.list:
        result["incidents"] = store.list_incidents(args.hub_id)
    if any([args.triage, args.create_plan, args.add_evidence, args.verify_fix, args.close, args.archive]) and not incident_id:
        incidents = store.list_incidents(args.hub_id)
        if not incidents:
            raise ValueError("--incident-id is required when no incidents exist.")
        incident_id = str(incidents[0].get("incident_id") or "")
    if args.triage:
        result["incident"] = store.triage_incident(args.hub_id, str(incident_id), {"severity": args.severity, "owner": args.owner, "notes": args.notes})
    if args.create_plan:
        result["plan"] = store.create_plan(args.hub_id, str(incident_id))
    if args.add_evidence:
        content_base64 = args.content_base64
        if args.evidence_file is not None:
            content_base64 = base64.b64encode(args.evidence_file.read_bytes()).decode("ascii")
        result["evidence"] = store.add_evidence(
            args.hub_id,
            str(incident_id),
            {
                "kind": args.evidence_kind,
                "component_type": args.component_type,
                "component_id": args.component_id,
                "content_base64": content_base64,
            },
        )
    if args.verify_fix:
        result["fix_verification"] = store.verify_fix(args.hub_id, str(incident_id))
    if args.close:
        result["closeout"] = store.close_incident(args.hub_id, str(incident_id), {"closed_by": args.closed_by, "reason": args.reason})
    if args.archive:
        result["incident"] = store.archive_incident(args.hub_id, str(incident_id))
    if args.export:
        result["manifest"] = store.export_board(args.hub_id)
    if args.zip:
        result["zip"] = store.build_zip(args.hub_id)
    if args.verify:
        verification = store.verify_zip(
            args.hub_id,
            {
                "strict": args.strict,
                "require_no_open_critical": args.require_no_open_critical,
                "require_no_open_blocking": args.require_no_open_blocking,
                "require_current_hub": args.require_current_hub,
                "hub_verification_report_path": args.hub_verification_report,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_hub_incident_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "incident_id": incident_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_hub_incidents(argv: list[str]) -> None:
    _execute_trust_operations_hub_incidents(argv)

def _execute_trust_operations_incident_knowledge(argv: list[str]) -> None:
    raw_args = ['trust-operations-incident-knowledge', *argv]
    pass
    pass
    pass
    pass
    parser = build_trust_operations_incident_knowledge_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
    store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    if args.refresh:
        result.update(store.refresh(args.hub_id, {"incident_board_verification_report_path": args.incident_board_verification_report, "hub_verification_report_path": args.hub_verification_report}))
    if args.list_entries:
        result["entries"] = store.list_entries(args.hub_id)
    if any([args.hide_entry, args.unhide_entry, args.create_guard]) and not args.entry_id:
        entries = store.list_entries(args.hub_id)
        if not entries:
            raise ValueError("--entry-id is required when no entries exist.")
        args.entry_id = str(entries[0].get("entry_id") or "")
    if args.hide_entry:
        result["entry"] = store.hide_entry(args.hub_id, str(args.entry_id))
    if args.unhide_entry:
        result["entry"] = store.unhide_entry(args.hub_id, str(args.entry_id))
    if args.create_guard:
        result["guard"] = store.create_guard(args.hub_id, str(args.entry_id), {"guard_id": args.guard_id, "guard_type": args.guard_type})
        args.guard_id = str(result["guard"].get("guard_id") or args.guard_id or "")
    if args.run_guard:
        if not args.guard_id:
            guards = store.list_guards(args.hub_id)
            if not guards:
                raise ValueError("--guard-id is required when no guards exist.")
            args.guard_id = str(guards[0].get("guard_id") or "")
        result["guard_run"] = store.run_guard(args.hub_id, str(args.guard_id))
    if args.run_all_guards:
        result["guard_runs"] = store.run_all_guards(args.hub_id)
    if args.refresh_recurrence:
        result["recurrence"] = store.refresh_recurrence(args.hub_id)
    if args.export:
        result["manifest"] = store.export_knowledge(args.hub_id)
    if args.zip:
        result["zip"] = store.build_zip(args.hub_id)
    if args.verify:
        verification = store.verify_zip(
            args.hub_id,
            {
                "strict": args.strict,
                "require_guards_passed": args.require_guards_passed,
                "require_no_open_recurrence": args.require_no_open_recurrence,
                "incident_board_package_path": args.incident_board_package,
                "incident_board_verification_report_path": args.incident_board_verification_report,
                "hub_verification_report_path": args.hub_verification_report,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_incident_knowledge_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_incident_knowledge(argv: list[str]) -> None:
    _execute_trust_operations_incident_knowledge(argv)

__all__ = ('_execute_trust_operations_hub_incidents', 'handle_trust_operations_hub_incidents', '_execute_trust_operations_incident_knowledge', 'handle_trust_operations_incident_knowledge')
