from __future__ import annotations

from .dependencies import *

from .part_004 import build_public_trust_center_publication_monitor_parser, build_trust_operations_assurance_watch_parser, build_trust_operations_assurance_watch_signoff_parser, build_trust_operations_hub_parser

from .part_005 import _trust_operations_assurance_watch_source_payload

from .part_007 import _build_public_trust_center_publication_store

def _execute_public_trust_center_publication_monitor(argv: list[str]) -> None:
    raw_args = ['public-trust-center-publication-monitor', *argv]
    pass
    pass
    parser = build_public_trust_center_publication_monitor_parser()
    args = parser.parse_args(raw_args[1:])
    publication_store = _build_public_trust_center_publication_store()
    store = PublicTrustCenterPublicationMonitoringStore(publication_store=publication_store)
    result: dict[str, Any] = {"ok": True, "center_id": args.center_id, "channel_id": args.channel_id}
    monitor_id = args.monitor_id
    if args.create_monitor:
        monitor = store.create_monitor(args.center_id, args.channel_id, {"monitor_id": monitor_id, "name": args.monitor_name, "publication_id": args.publication_id, "mirror_dir": args.mirror_dir})
        monitor_id = str(monitor.get("monitor_id") or monitor_id or "")
        result["monitor"] = monitor
    elif monitor_id:
        result["monitor"] = store.read_monitor(args.center_id, args.channel_id, monitor_id)
    else:
        monitors = store.list_monitors(args.center_id, args.channel_id)
        if monitors:
            monitor_id = str(monitors[0].get("monitor_id") or "")
            result["monitor"] = monitors[0]
        else:
            monitor = store.create_monitor(args.center_id, args.channel_id, {"name": args.monitor_name, "publication_id": args.publication_id, "mirror_dir": args.mirror_dir})
            monitor_id = str(monitor.get("monitor_id") or "")
            result["monitor"] = monitor
    if not monitor_id:
        raise ValueError("--monitor-id is required.")
    run_id = args.run_id
    if args.run:
        run_result = store.run_monitor(args.center_id, args.channel_id, monitor_id, {"publication_id": args.publication_id, "mirror_dir": args.mirror_dir, "publication_channel_state_path": args.publication_channel_state})
        run_id = str((run_result.get("monitor_run") or {}).get("run_id") or run_id or "")
        result.update(run_result)
        result["summary"] = monitoring_summary(run_result.get("monitor_run") or {})
    if args.ack_incident:
        result["incident"] = store.acknowledge_incident(args.center_id, args.channel_id, monitor_id, args.ack_incident, {"reason": args.reason})
    if args.resolve_incident:
        result["incident"] = store.resolve_incident(args.center_id, args.channel_id, monitor_id, args.resolve_incident, {"resolution_note": args.reason})
    if args.waive_incident:
        result["incident"] = store.waive_incident(args.center_id, args.channel_id, monitor_id, args.waive_incident, {"waiver_reason": args.reason})
    if args.reopen_incident:
        result["incident"] = store.reopen_incident(args.center_id, args.channel_id, monitor_id, args.reopen_incident, {"reason": args.reason})
    if args.export:
        if not run_id:
            raise ValueError("--run-id is required for --export unless --run was used.")
        result["manifest"] = store.export_monitoring_run(args.center_id, args.channel_id, monitor_id, run_id)
    if args.zip:
        if not run_id:
            raise ValueError("--run-id is required for --zip unless --run was used.")
        result["zip"] = store.build_monitoring_zip(args.center_id, args.channel_id, monitor_id, run_id)
    if args.verify:
        if not run_id:
            raise ValueError("--run-id is required for --verify unless --run was used.")
        verification = store.verify_monitoring_zip(
            args.center_id,
            args.channel_id,
            monitor_id,
            run_id,
            {
                "strict": args.strict,
                "require_current": args.require_current,
                "require_no_revoked": args.require_no_revoked,
                "require_ready": args.require_ready,
                "require_no_drift": args.require_no_drift,
                "require_no_open_critical_incidents": args.require_no_open_critical_incidents,
                "allow_waived_incidents": args.allow_waived_incidents,
                "publication_channel_state_path": args.publication_channel_state,
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
            print_public_trust_center_publication_monitoring_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_public_trust_center_publication_monitor(argv: list[str]) -> None:
    _execute_public_trust_center_publication_monitor(argv)

def _execute_trust_operations_hub(argv: list[str]) -> None:
    raw_args = ['trust-operations-hub', *argv]
    pass
    pass
    parser = build_trust_operations_hub_parser()
    args = parser.parse_args(raw_args[1:])
    store = TrustOperationsHubStore()
    result: dict[str, Any] = {"ok": True}
    hub_id = args.hub_id
    if args.create or not hub_id:
        if hub_id and store.hub_path(hub_id).exists():
            hub = store.read_hub(hub_id)
        else:
            hub = store.create_hub({"hub_id": hub_id, "name": args.name})
        hub_id = str(hub.get("hub_id") or hub_id or "")
        result["hub"] = hub
    if not hub_id:
        hubs = store.list_hubs()
        if not hubs:
            hub = store.create_hub({"name": args.name})
            hubs = [hub]
        hub_id = str(hubs[0].get("hub_id") or "")
        result["hub"] = hubs[0]
    if not hub_id:
        raise ValueError("--hub-id is required.")
    report_id = args.report_id
    source_payload = {
        "publication_channel_state_path": args.publication_channel_state,
        "public_trust_center_verification_path": args.public_trust_center_verification,
        "publication_monitoring_verification_path": args.publication_monitoring_verification,
        "release_verification_paths": args.release_verification,
        "distribution_verification_paths": args.distribution_verification,
        "submission_verification_paths": args.submission_verification,
        "submission_evidence_verification_paths": args.submission_evidence_verification,
        "release_operations_verification_paths": args.release_operations_verification,
    }
    if args.refresh:
        refreshed = store.refresh_report(hub_id, source_payload)
        report_id = str((refreshed.get("hub_report") or {}).get("report_id") or report_id or "")
        result.update(refreshed)
    if not report_id:
        current = read_json(store.current_report_path(hub_id)) if store.current_report_path(hub_id).exists() else {}
        report_id = str(current.get("report_id") or "")
    if args.create_change_request:
        result["change_request"] = store.create_change_request(hub_id, {"reason": args.reason, "change_request_id": args.change_request_id})
    if args.approve_change_request:
        result["change_request"] = store.approve_change_request(hub_id, args.approve_change_request)
    if args.reset_signoff:
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for --reset-signoff.")
        result["reset"] = store.reset_signoff(hub_id, args.change_request_id)
    if args.export:
        if not report_id:
            raise ValueError("--report-id is required for --export unless --refresh was used.")
        result["manifest"] = store.export_report(hub_id, report_id)
    if args.zip:
        if not report_id:
            raise ValueError("--report-id is required for --zip unless --refresh was used.")
        result["zip"] = store.build_zip(hub_id, report_id)
    if args.verify:
        if not report_id:
            raise ValueError("--report-id is required for --verify unless --refresh was used.")
        verification = store.verify_zip(
            hub_id,
            report_id,
            {
                "strict": args.strict,
                "require_ready": args.require_ready,
                "require_signed": args.require_signed,
                "require_current": args.require_current,
                "require_no_critical_blockers": args.require_no_critical_blockers,
                "require_publication_monitoring_clean": args.require_publication_monitoring_clean,
                "require_delivery_ready": args.require_delivery_ready,
                "require_incident_closeout": args.require_incident_closeout,
                "require_incident_regression_guards": args.require_incident_regression_guards,
                "require_trust_controls": args.require_trust_controls,
                "require_trust_control_signoff": args.require_trust_control_signoff,
                "require_continuous_assurance": args.require_continuous_assurance,
                "publication_channel_state_path": args.publication_channel_state,
                "public_trust_center_verification_path": args.public_trust_center_verification,
                "publication_monitoring_verification_path": args.publication_monitoring_verification,
                "release_verification_paths": args.release_verification,
                "distribution_verification_paths": args.distribution_verification,
                "submission_verification_paths": args.submission_verification,
                "submission_evidence_verification_paths": args.submission_evidence_verification,
                "release_operations_verification_paths": args.release_operations_verification,
                "hub_signoff_path": args.hub_signoff,
                "hub_verification_report_path": args.hub_verification_report,
                "incident_board_package_path": args.incident_board_package,
                "incident_board_verification_report_path": args.incident_board_verification_report,
                "incident_knowledge_package_path": args.incident_knowledge_package,
                "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
                "trust_control_package_path": args.trust_control_package,
                "trust_control_verification_report_path": args.trust_control_verification_report,
                "trust_control_signoff_archive_path": args.trust_control_signoff_archive,
                "trust_control_signoff_verification_report_path": args.trust_control_signoff_verification_report,
                "continuous_assurance_archive_path": args.continuous_assurance_archive,
                "continuous_assurance_verification_report_path": args.continuous_assurance_verification_report,
                "require_assurance_watch_clear": args.require_assurance_watch_clear,
                "assurance_watch_package_path": args.assurance_watch_package,
                "assurance_watch_verification_report_path": args.assurance_watch_verification_report,
                "require_assurance_watch_signoff": args.require_assurance_watch_signoff,
                "assurance_watch_signoff_archive_path": args.assurance_watch_signoff_archive,
                "assurance_watch_signoff_verification_report_path": args.assurance_watch_signoff_verification_report,
            },
        )
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.signoff:
        if not report_id:
            raise ValueError("--report-id is required for --signoff unless --refresh was used.")
        result["signoff"] = store.signoff(hub_id, report_id, {"signed_by": args.signed_by, "reason": args.reason, "force": args.force, "override_reason": args.override_reason})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_hub_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": hub_id, "report_id": report_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_hub(argv: list[str]) -> None:
    _execute_trust_operations_hub(argv)

def _execute_trust_operations_assurance_watch(argv: list[str]) -> None:
    raw_args = ['trust-operations-assurance-watch', *argv]
    pass
    pass
    pass
    pass
    parser = build_trust_operations_assurance_watch_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    assurance_store = TrustOperationsAssuranceStore(hub_store=hub_store)
    store = TrustOperationsAssuranceWatchStore(assurance_store=assurance_store, hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "schedule_id": args.schedule_id}
    source_payload = _trust_operations_assurance_watch_source_payload(args)
    schedule_patch: dict[str, Any] = {}
    if args.hub_id:
        schedule_patch.setdefault("scope", {})["hub_ids"] = [args.hub_id]
    if args.interval_days is not None or args.grace_days is not None:
        schedule_patch.setdefault("cadence", {})
        if args.interval_days is not None:
            schedule_patch["cadence"]["interval_days"] = args.interval_days
        if args.grace_days is not None:
            schedule_patch["cadence"]["grace_days"] = args.grace_days
    if args.write_schedule:
        result["schedule"] = store.write_schedule({"schedule_id": args.schedule_id, **schedule_patch})
    if args.list:
        result["queues"] = store.list_queues(args.schedule_id)
    if args.refresh:
        refresh_payload: dict[str, Any] = {**source_payload}
        if args.queue_id:
            refresh_payload["queue_id"] = args.queue_id
        if args.hub_id:
            refresh_payload["hub_id"] = args.hub_id
        refreshed = store.refresh_queue(refresh_payload, schedule_id=args.schedule_id)
        result.update(refreshed)
        args.queue_id = str((refreshed.get("queue") or {}).get("queue_id") or args.queue_id or "")
    if args.export:
        if not args.queue_id:
            raise ValueError("--queue-id is required for --export unless --refresh was used.")
        result["manifest"] = store.export_watch(args.queue_id, source_payload)
    if args.zip:
        if not args.queue_id:
            raise ValueError("--queue-id is required for --zip unless --refresh was used.")
        result["zip"] = store.build_watch_zip(args.queue_id, source_payload)
    if args.verify:
        if not args.queue_id:
            raise ValueError("--queue-id is required for --verify unless --refresh was used.")
        verification = store.verify_watch_zip(args.queue_id, {**source_payload, "strict": args.strict, "require_clear": args.require_clear, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.write_schedule, args.list, args.refresh, args.export, args.zip, args.verify]):
        result["summary"] = store.summary(args.queue_id) if args.queue_id else {"schedule": store.read_schedule(args.schedule_id), "queues": store.list_queues(args.schedule_id)}
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_assurance_watch_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "queue_id": args.queue_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_assurance_watch(argv: list[str]) -> None:
    _execute_trust_operations_assurance_watch(argv)

def _execute_trust_operations_assurance_watch_signoff(argv: list[str]) -> None:
    raw_args = ['trust-operations-assurance-watch-signoff', *argv]
    pass
    pass
    pass
    pass
    pass
    parser = build_trust_operations_assurance_watch_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    assurance_store = TrustOperationsAssuranceStore(hub_store=hub_store)
    watch_store = TrustOperationsAssuranceWatchStore(assurance_store=assurance_store, hub_store=hub_store)
    store = TrustOperationsAssuranceWatchSignoffStore(watch_store=watch_store, assurance_store=assurance_store, hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "queue_id": args.queue_id}
    source_payload = {
        "watch_package_path": args.watch_package,
        "watch_verification_report_path": args.watch_verification_report,
        "hub_package_path": args.hub_package,
        "hub_verification_report_path": args.hub_verification_report,
        "continuous_assurance_report_path": args.continuous_assurance_report,
    }
    if args.refresh_closeout:
        result["closeout"] = store.refresh_closeout(args.queue_id, source_payload)
    if args.sign:
        result["signoff"] = store.sign(args.queue_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
    if args.create_change_request:
        result["change_request"] = store.create_change_request(args.queue_id, {"reason": args.reason, "requested_by": args.signed_by})
    if args.approve_change_request:
        result["change_request"] = store.approve_change_request(args.queue_id, args.approve_change_request, {"approved_by": args.signed_by})
    if args.reset_signoff:
        result["reset"] = store.reset_signoff(args.queue_id, args.reset_signoff)
    if args.export:
        result["manifest"] = store.export_archive(args.queue_id, source_payload)
    if args.zip:
        result["zip"] = store.build_archive_zip(args.queue_id)
    if args.verify:
        verification = store.verify_archive_zip(args.queue_id, {**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.refresh_closeout, args.sign, args.create_change_request, args.approve_change_request, args.reset_signoff, args.export, args.zip, args.verify]):
        result["summary"] = store.summary(args.queue_id)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_assurance_watch_signoff_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "queue_id": args.queue_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_assurance_watch_signoff(argv: list[str]) -> None:
    _execute_trust_operations_assurance_watch_signoff(argv)

__all__ = ('_execute_public_trust_center_publication_monitor', 'handle_public_trust_center_publication_monitor', '_execute_trust_operations_hub', 'handle_trust_operations_hub', '_execute_trust_operations_assurance_watch', 'handle_trust_operations_assurance_watch', '_execute_trust_operations_assurance_watch_signoff', 'handle_trust_operations_assurance_watch_signoff')
