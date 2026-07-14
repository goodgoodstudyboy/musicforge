from __future__ import annotations

from .dependencies import *

from .part_004 import build_trust_operations_assurance_parser, build_trust_operations_final_readiness_parser

from .part_005 import _trust_operations_assurance_source_payload, _trust_operations_final_readiness_source_payload, build_trust_operations_control_signoff_parser, build_trust_operations_controls_parser, build_trust_operations_hub_runbook_parser

def _execute_trust_operations_final_readiness(argv: list[str]) -> None:
    raw_args = ['trust-operations-final-readiness', *argv]
    pass
    pass
    parser = build_trust_operations_final_readiness_parser()
    args = parser.parse_args(raw_args[1:])
    store = TrustOperationsFinalReadinessStore()
    result: dict[str, Any] = {"ok": True}
    source_payload = _trust_operations_final_readiness_source_payload(args)
    if args.refresh_report:
        result.update(store.refresh_report(source_payload))
    if args.create_certificate:
        result["certificate"] = store.create_certificate()
    if args.sign:
        result["signoff"] = store.sign({"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
    if args.create_change_request:
        result["change_request"] = store.create_change_request({"reason": args.reason, "requested_by": args.signed_by})
    if args.approve_change_request:
        result["change_request"] = store.approve_change_request(args.approve_change_request, {"approved_by": args.signed_by})
    if args.reset_signoff:
        result["reset"] = store.reset_signoff(args.reset_signoff)
    if args.export:
        result["manifest"] = store.export_handoff(source_payload)
    if args.zip:
        result["zip"] = store.build_handoff_zip()
    if args.verify:
        verification = store.verify_handoff_zip({**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.refresh_report, args.create_certificate, args.sign, args.create_change_request, args.approve_change_request, args.reset_signoff, args.export, args.zip, args.verify]):
        result["summary"] = store.summary()
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_final_handoff_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok"}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_final_readiness(argv: list[str]) -> None:
    _execute_trust_operations_final_readiness(argv)

def _execute_trust_operations_controls(argv: list[str]) -> None:
    raw_args = ['trust-operations-controls', *argv]
    pass
    pass
    pass
    pass
    pass
    parser = build_trust_operations_controls_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
    knowledge_store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
    store = TrustOperationsControlStore(hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    source_payload = {
        "hub_package_path": args.hub_package,
        "hub_verification_report_path": args.hub_verification_report,
        "incident_board_package_path": args.incident_board_package,
        "incident_board_verification_report_path": args.incident_board_verification_report,
        "incident_knowledge_package_path": args.incident_knowledge_package,
        "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
    }
    if args.refresh_catalog:
        result["catalog"] = store.refresh_catalog(args.hub_id, source_payload)
    if args.create_policy:
        policy = store.create_policy_bundle(args.hub_id, {"policy_id": args.policy_id, "name": args.policy_name})
        args.policy_id = str(policy.get("policy_id") or args.policy_id or "")
        result["policy"] = policy
    if args.assess:
        if not args.policy_id:
            policies = store.list_policies(args.hub_id)
            if not policies:
                raise ValueError("--policy-id is required when no policy exists.")
            args.policy_id = str(policies[0].get("policy_id") or "")
        assessed = store.assess_policy(args.hub_id, str(args.policy_id), {**source_payload, "assessment_id": args.assessment_id})
        args.assessment_id = str((assessed.get("assessment") or {}).get("assessment_id") or args.assessment_id or "")
        result.update(assessed)
    if not args.assessment_id and (args.export or args.zip or args.verify):
        assessments = sorted(store.assessments_dir(args.hub_id).glob("*/control-assessment-report.json")) if store.assessments_dir(args.hub_id).exists() else []
        if assessments:
            args.assessment_id = assessments[-1].parent.name
    if args.export:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --export unless --assess was used.")
        result["manifest"] = store.export_controls(args.hub_id, str(args.assessment_id))
    if args.zip:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --zip unless --assess was used.")
        result["zip"] = store.build_zip(args.hub_id, str(args.assessment_id))
    if args.verify:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --verify unless --assess was used.")
        verification = store.verify_zip(args.hub_id, str(args.assessment_id), {**source_payload, "strict": args.strict, "require_policy_passed": args.require_policy_passed})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_control_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "assessment_id": args.assessment_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_controls(argv: list[str]) -> None:
    _execute_trust_operations_controls(argv)

def _execute_trust_operations_assurance(argv: list[str]) -> None:
    raw_args = ['trust-operations-assurance', *argv]
    pass
    pass
    pass
    parser = build_trust_operations_assurance_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    store = TrustOperationsAssuranceStore(hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    source_payload = _trust_operations_assurance_source_payload(args)
    if args.list:
        result["runs"] = store.list_runs(args.hub_id)
    if args.refresh:
        refreshed = store.refresh_run(args.hub_id, {**source_payload, "run_id": args.run_id}, policy_id=args.policy_id)
        result.update(refreshed)
        args.run_id = str((refreshed.get("run") or {}).get("run_id") or args.run_id or "")
    if args.export:
        if not args.run_id:
            raise ValueError("--run-id is required for --export unless --refresh was used.")
        result["manifest"] = store.export_archive(args.run_id, source_payload)
    if args.zip:
        if not args.run_id:
            raise ValueError("--run-id is required for --zip unless --refresh was used.")
        result["zip"] = store.build_archive_zip(args.run_id, source_payload)
    if args.verify:
        if not args.run_id:
            raise ValueError("--run-id is required for --verify unless --refresh was used.")
        verification = store.verify_archive_zip(args.run_id, {**source_payload, "strict": args.strict, "require_passed": args.require_passed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.list, args.refresh, args.export, args.zip, args.verify]):
        if not args.run_id:
            result["runs"] = store.list_runs(args.hub_id)
        else:
            result["summary"] = store.summary(args.run_id)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_assurance_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "run_id": args.run_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_assurance(argv: list[str]) -> None:
    _execute_trust_operations_assurance(argv)

def _execute_trust_operations_control_signoff(argv: list[str]) -> None:
    raw_args = ['trust-operations-control-signoff', *argv]
    pass
    pass
    pass
    pass
    pass
    pass
    parser = build_trust_operations_control_signoff_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    incident_store = TrustOperationsIncidentStore(hub_store=hub_store)
    knowledge_store = TrustOperationsIncidentKnowledgeStore(hub_store=hub_store, incident_store=incident_store)
    control_store = TrustOperationsControlStore(hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    store = TrustOperationsControlSignoffStore(control_store=control_store, hub_store=hub_store, incident_store=incident_store, knowledge_store=knowledge_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    source_payload = {
        "control_package_path": args.control_package,
        "control_verification_report_path": args.control_verification_report,
        "hub_package_path": args.hub_package,
        "hub_verification_report_path": args.hub_verification_report,
        "incident_board_package_path": args.incident_board_package,
        "incident_board_verification_report_path": args.incident_board_verification_report,
        "incident_knowledge_package_path": args.incident_knowledge_package,
        "incident_knowledge_verification_report_path": args.incident_knowledge_verification_report,
    }
    if args.sign:
        if not args.assessment_id:
            raise ValueError("--assessment-id is required for --sign.")
        result["signoff"] = store.sign(args.hub_id, str(args.assessment_id), {**source_payload, "signed_by": args.signed_by, "reason": args.reason})
    if args.request_exception:
        if not args.assessment_id or not args.control_id:
            raise ValueError("--assessment-id and --control-id are required for --request-exception.")
        result["exception"] = store.request_exception(args.hub_id, {"assessment_id": args.assessment_id, "control_id": args.control_id, "requested_by": args.requested_by, "reason": args.reason, "expires_at": args.expires_at, "mitigation": args.mitigation})
    if args.approve_exception:
        if not args.exception_id:
            raise ValueError("--exception-id is required for --approve-exception.")
        result["exception"] = store.approve_exception(args.hub_id, args.exception_id, {"approved_by": args.approved_by, "reason": args.reason})
    if args.reject_exception:
        if not args.exception_id:
            raise ValueError("--exception-id is required for --reject-exception.")
        result["exception"] = store.reject_exception(args.hub_id, args.exception_id, {"approved_by": args.approved_by, "reason": args.reason})
    if args.create_change_request:
        result["change_request"] = store.create_change_request(args.hub_id, {"reason": args.reason, "created_by": args.requested_by, "change_request_id": args.change_request_id})
    if args.approve_change_request:
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for --approve-change-request.")
        result["change_request"] = store.approve_change_request(args.hub_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
    if args.reset:
        if not args.change_request_id:
            raise ValueError("--change-request-id is required for --reset.")
        result["reset"] = store.reset_signoff(args.hub_id, args.change_request_id)
    if args.export:
        result["manifest"] = store.export_archive(args.hub_id, source_payload)
    if args.zip:
        result["zip"] = store.build_archive_zip(args.hub_id)
    if args.verify:
        verification = store.verify_archive_zip(args.hub_id, {**source_payload, "strict": args.strict, "require_signed": args.require_signed, "require_current": args.require_current})
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if not any([args.sign, args.request_exception, args.approve_exception, args.reject_exception, args.create_change_request, args.approve_change_request, args.reset, args.export, args.zip, args.verify]):
        result["summary"] = store.summary(args.hub_id)
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_control_signoff_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_control_signoff(argv: list[str]) -> None:
    _execute_trust_operations_control_signoff(argv)

def _execute_trust_operations_hub_runbook(argv: list[str]) -> None:
    raw_args = ['trust-operations-hub-runbook', *argv]
    pass
    pass
    pass
    parser = build_trust_operations_hub_runbook_parser()
    args = parser.parse_args(raw_args[1:])
    hub_store = TrustOperationsHubStore()
    store = TrustOperationsHubRunbookStore(hub_store=hub_store)
    result: dict[str, Any] = {"ok": True, "hub_id": args.hub_id}
    report_id = args.report_id
    if not report_id:
        current = read_json(hub_store.current_report_path(args.hub_id)) if hub_store.current_report_path(args.hub_id).exists() else {}
        report_id = str(current.get("report_id") or "")
    runbook_id = args.runbook_id
    if args.create:
        if not report_id:
            raise ValueError("--report-id is required for --create unless a current Hub report exists.")
        runbook = store.create_runbook(args.hub_id, report_id, {"runbook_id": runbook_id})
        runbook_id = str(runbook.get("runbook_id") or runbook_id or "")
        result["runbook"] = runbook
    if not runbook_id:
        raise ValueError("--runbook-id is required unless --create was used.")
    if args.run_safe:
        result["result"] = store.run_safe_actions(args.hub_id, runbook_id)
    if args.export:
        result["manifest"] = store.export_runbook(args.hub_id, runbook_id)
    if args.zip:
        result["zip"] = store.build_zip(args.hub_id, runbook_id)
    if args.verify:
        verification = verify_trust_operations_hub_runbook_package(store.zip_path(args.hub_id, runbook_id), strict=args.strict, require_completed=args.require_completed, require_no_blocked=args.require_no_blocked)
        result["verification"] = verification
        result["verification_summary"] = verification.get("summary", {})
    if args.report_out is not None:
        write_interface_document(args.report_out, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if "verification" in result:
            print_trust_operations_hub_runbook_verification_report(result["verification"])
        else:
            print(json.dumps(result.get("summary") or {"status": "ok", "hub_id": args.hub_id, "runbook_id": runbook_id}, ensure_ascii=False, indent=2))
    raise SystemExit(0)

def handle_trust_operations_hub_runbook(argv: list[str]) -> None:
    _execute_trust_operations_hub_runbook(argv)

__all__ = ('_execute_trust_operations_final_readiness', 'handle_trust_operations_final_readiness', '_execute_trust_operations_controls', 'handle_trust_operations_controls', '_execute_trust_operations_assurance', 'handle_trust_operations_assurance', '_execute_trust_operations_control_signoff', 'handle_trust_operations_control_signoff', '_execute_trust_operations_hub_runbook', 'handle_trust_operations_hub_runbook')
