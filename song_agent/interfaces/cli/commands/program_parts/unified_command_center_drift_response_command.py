from __future__ import annotations

from typing import Any as _InterfaceType

from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_program_parts_dependencies

from .unified_release_program_continuity_command_center_acceptance_change import _unified_command_center_drift_response_payload_from_args
Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = _commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report
def _run_unified_command_center_drift_response_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass
    pass
    pass
    pass

    center_store = UnifiedCommandCenterStore()
    signoff_store = UnifiedCommandCenterSignoffStore(center_store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    store = UnifiedCommandCenterDriftResponseStore(center_store, signoff_store=signoff_store, handoff_store=handoff_store)
    payload = _unified_command_center_drift_response_payload_from_args(args)
    if args.action == "create":
        result = store.create_response(args.center_id, payload)
        case = result.get("case", {})
        return {"ok": True, **result, "summary": {"response_id": case.get("response_id")}, "status": case.get("status")}
    if args.action == "list":
        rows = store.list_responses(args.center_id)
        return {"ok": True, "responses": rows, "summary": {"response_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.read_response(args.center_id, args.response_id)
        closeout = docs.get("closeout") or {}
        return {"ok": True, "response": docs, "summary": closeout.get("summary", {}), "status": closeout.get("status") or docs.get("case", {}).get("status")}
    if args.action == "run-safe":
        result = store.run_safe(args.center_id, args.response_id, payload)
        failed = int((result.get("summary") or {}).get("failed_count") or 0)
        return {"ok": failed == 0, "action_results": result, "summary": result.get("summary", {}), "status": "passed" if failed == 0 else "failed"}
    if args.action == "bind-cr":
        result = store.bind_change_request(
            args.center_id,
            args.response_id,
            {"item_id": args.item_id, "change_request_id": args.change_request_id, "status": "approved", "approved_by": args.approved_by, "reason": args.reason},
        )
        return {"ok": True, "change_request_bindings": result, "summary": result.get("summary", {}), "status": "passed"}
    if args.action == "bind-recheck":
        result = store.bind_recheck(
            args.center_id,
            args.response_id,
            {"recheck_review_id": args.recheck_review_id, "recheck_review_zip": args.recheck_review_zip, "recheck_review_verification_report": args.recheck_review_verification_report},
        )
        return {"ok": result.get("status") == "passed", "recheck": result, "summary": result.get("summary", {}), "status": result.get("status")}
    if args.action == "closeout":
        result = store.closeout(args.center_id, args.response_id, {"closed_by": args.closed_by, "reason": args.reason})
        return {"ok": result.get("status") == "closed", "closeout": result, "summary": result.get("summary", {}), "status": result.get("status")}
    if args.action == "export":
        result = store.export_package(args.center_id, args.response_id, payload)
        return {"ok": result.get("status") == "closed", **result, "summary": result.get("manifest", {}).get("summary", {})}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.response_id, payload)
        return {"ok": result.get("status") == "closed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.center_id,
            args.response_id,
            {
                **payload,
                "strict": args.strict,
                "require_closed": args.require_closed,
                "require_recheck_clear": args.require_recheck_clear,
                "require_current_review": args.require_current_review,
            },
        )
        if args.report_out is not None:
            write_unified_command_center_drift_response_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-drift-response command.")

def _unified_command_center_evidence_review_payload_from_args(args: argparse.Namespace) -> ImplementationDocument:
    return {
        "review_id": getattr(args, "review_id", None),
        "ucc_zip": getattr(args, "ucc_zip", None),
        "ucc_verification_report": getattr(args, "ucc_verification_report", None),
        "archive_zip": getattr(args, "archive_zip", None),
        "archive_verification_report": getattr(args, "archive_verification_report", None),
        "handoff_zip": getattr(args, "handoff_zip", None),
        "handoff_verification_report": getattr(args, "handoff_verification_report", None),
        "continuous_review_id": getattr(args, "continuous_review_id", None),
        "continuous_review_zip": getattr(args, "continuous_review_zip", None),
        "continuous_review_verification_report": getattr(args, "continuous_review_verification_report", None),
        "source_review_zip": getattr(args, "source_review_zip", None),
        "source_review_verification_report": getattr(args, "source_review_verification_report", None),
        "recheck_review_id": getattr(args, "recheck_review_id", None),
        "recheck_review_zip": getattr(args, "recheck_review_zip", None),
        "recheck_review_verification_report": getattr(args, "recheck_review_verification_report", None),
        "drift_response_id": getattr(args, "drift_response_id", None),
        "drift_response_zip": getattr(args, "drift_response_zip", None),
        "drift_response_verification_report": getattr(args, "drift_response_verification_report", None),
        "drift_change_request_binding_report": getattr(args, "drift_change_request_binding_report", None),
        "signoff_binding": getattr(args, "signoff_binding", None),
        "ga_readiness_report": getattr(args, "ga_readiness_report", None),
        "release_check_report": getattr(args, "release_check_report", None),
    }

def _run_unified_command_center_evidence_review_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass




    store = UnifiedCommandCenterEvidenceReviewStore()
    payload = _unified_command_center_evidence_review_payload_from_args(args)
    if args.action == "create":
        docs = store.create_review(args.center_id, payload)
        return {"ok": True, "review": docs, "summary": {"review_id": docs.get("source", {}).get("review_id")}, "status": docs.get("source", {}).get("status")}
    if args.action == "list":
        rows = store.list_reviews(args.center_id)
        return {"ok": True, "reviews": rows, "summary": {"review_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.get_review(args.center_id, args.review_id)
        replay = docs.get("replay_result") or {}
        return {"ok": True, "review": docs, "summary": replay.get("summary", {}), "status": replay.get("status") or docs.get("source", {}).get("status")}
    if args.action == "refresh":
        docs = store.refresh_review(args.center_id, args.review_id, payload)
        return {"ok": True, "review": docs, "summary": {"review_id": args.review_id}, "status": docs.get("source", {}).get("status")}
    if args.action == "replay":
        replay = store.run_replay(args.center_id, args.review_id, payload)
        return {"ok": replay.get("status") == "passed", "replay_result": replay, "summary": replay.get("summary", {}), "status": replay.get("status")}
    if args.action == "export":
        result = store.export_review(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"manifest_hash": result.get("manifest_hash")}}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(args.center_id, args.review_id, {**payload, "strict": args.strict, "require_replay_passed": args.require_replay_passed})
        if args.report_out is not None:
            write_unified_command_center_evidence_review_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "import-response":
        if args.response_json:
            payload = read_json(args.response_json)
        else:
            payload = {"response_base64": args.response_base64}
        response = store.import_response(args.center_id, args.review_id, payload)
        return {"ok": response.get("status") == "current", "response": response, "summary": {"response_id": response.get("response_id")}, "status": response.get("status")}
    if args.action == "acceptance-evidence":
        result = store.create_acceptance_evidence(args.center_id, args.review_id, args.response_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"evidence_id": result.get("evidence_id")}}
    if args.action == "verify-acceptance":
        report = store.verify_acceptance_evidence(args.center_id, args.review_id, args.evidence_id, {"strict": args.strict, "require_accepted": args.require_accepted})
        if args.report_out is not None:
            write_unified_command_center_evidence_review_acceptance_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-evidence-review command.")

def _unified_command_center_reviewer_decision_board_payload_from_args(args: argparse.Namespace) -> ImplementationDocument:
    accepted_zips = list(getattr(args, "accepted_evidence", []) or [])
    accepted_reports = list(getattr(args, "accepted_evidence_verification_report", []) or [])
    accepted_response_reports = list(getattr(args, "accepted_evidence_response_verification_report", []) or [])
    accepted_rows = []
    for index, zip_path in enumerate(accepted_zips):
        accepted_rows.append(
            {
                "zip_path": zip_path,
                "verification_report_path": accepted_reports[index] if index < len(accepted_reports) else None,
                "response_verification_report_path": accepted_response_reports[index] if index < len(accepted_response_reports) else None,
            }
        )
    policy: dict[str, _InterfaceType] = {}
    if getattr(args, "required_role", None):
        policy["required_roles"] = list(args.required_role)
    if getattr(args, "min_accepted_count", None) is not None:
        policy["min_accepted_count"] = args.min_accepted_count
    if getattr(args, "min_organization_count", None) is not None:
        policy["min_organization_count"] = args.min_organization_count
    return {
        "board_id": getattr(args, "board_id", None),
        "review_id": getattr(args, "review_id", None),
        "review_zip": getattr(args, "review_zip", None),
        "review_verification_report": getattr(args, "review_verification_report", None),
        "accepted_evidence": accepted_rows,
        "policy": policy,
    }

def _run_unified_command_center_reviewer_decision_board_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass

    store = UnifiedCommandCenterReviewerDecisionBoardStore()
    payload = _unified_command_center_reviewer_decision_board_payload_from_args(args)
    if args.action == "create":
        docs = store.create_board(args.center_id, payload)
        return {"ok": docs.get("decision_report", {}).get("status") == "ready_for_signoff", "board": docs, "summary": docs.get("decision_report", {}).get("summary", {}), "status": docs.get("decision_report", {}).get("status")}
    if args.action == "list":
        rows = store.list_boards(args.center_id)
        return {"ok": True, "boards": rows, "summary": {"board_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.get_board(args.center_id, args.board_id)
        return {"ok": True, "board": docs, "summary": docs.get("decision_report", {}).get("summary", {}), "status": docs.get("decision_report", {}).get("status") or docs.get("source", {}).get("status")}
    if args.action == "refresh":
        docs = store.refresh_board(args.center_id, args.board_id, payload)
        return {"ok": docs.get("decision_report", {}).get("status") == "ready_for_signoff", "board": docs, "summary": docs.get("decision_report", {}).get("summary", {}), "status": docs.get("decision_report", {}).get("status")}
    if args.action == "signoff":
        signoff = store.signoff(args.center_id, args.board_id, {**payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "export":
        result = store.export_archive(args.center_id, args.board_id, payload)
        return {"ok": result.get("status") == "signed", **result, "summary": {"manifest_hash": result.get("manifest_hash")}}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.board_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_archive(args.center_id, args.board_id, {**payload, "strict": args.strict, "require_signed": args.require_signed, "require_quorum": args.require_quorum})
        if args.report_out is not None:
            write_unified_command_center_reviewer_decision_board_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-reviewer-decision-board command.")

def _run_unified_command_center_release_train_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass

    store = UnifiedCommandCenterReleaseTrainStore()
    if args.action == "create":
        train = store.create_train(
            {
                "train_id": args.train_id,
                "name": args.name,
                "profile": args.profile,
                "allow_duplicate_center": args.allow_duplicate_center,
                "required_evidence": args.required_evidence,
            }
        )
        return {"ok": True, "train": train, "summary": {"train_id": train.get("train_id")}, "status": train.get("status")}
    if args.action == "list":
        trains = store.list_trains()
        return {"ok": True, "trains": trains, "summary": {"train_count": len(trains)}, "status": "passed"}
    if args.action == "add-item":
        item = store.add_item(
            args.train_id,
            {
                "item_id": args.item_id,
                "center_id": args.center_id,
                "label": args.label,
                "wave": args.wave,
                "depends_on": args.depends_on,
                "allow_duplicate_center": args.allow_duplicate_center,
                "required_evidence": args.required_evidence,
            },
        )
        return {"ok": True, "item": item, "summary": {"item_id": item.get("item_id")}, "status": item.get("status")}
    if args.action == "status":
        docs = store.read_docs(args.train_id) if store.report_path(args.train_id).exists() else {"train": store.read_train(args.train_id)}
        report = docs.get("report", {})
        return {"ok": True, "train": docs.get("train"), "report": report, "summary": report.get("summary", {}), "status": report.get("status") or docs.get("train", {}).get("status")}
    payload = {"external_evidence_manifest": getattr(args, "external_evidence_manifest", None)}
    if args.action == "refresh":
        report = store.refresh(args.train_id, payload)
        return {"ok": report.get("status") == "go", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "run-safe":
        result = store.run_safe(args.train_id, payload)
        failed = int((result.get("summary") or {}).get("failed_count") or 0)
        return {"ok": failed == 0, "runbook_result": result, "summary": result.get("summary", {}), "status": "passed" if failed == 0 else "failed"}
    if args.action == "signoff":
        signoff = store.signoff(args.train_id, {**payload, "signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": signoff.get("status") == "signed", "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "export":
        manifest = store.export_archive(args.train_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "zip":
        result = store.build_zip(args.train_id)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_archive(args.train_id, {**payload, "strict": args.strict, "require_go": args.require_go, "require_signed": args.require_signed, "signoff_binding": args.signoff_binding})
        if args.report_out is not None:
            write_unified_command_center_release_train_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-release-train command.")

__all__ = ('_run_unified_command_center_drift_response_command', '_unified_command_center_evidence_review_payload_from_args', '_run_unified_command_center_evidence_review_command', '_unified_command_center_reviewer_decision_board_payload_from_args', '_run_unified_command_center_reviewer_decision_board_command', '_run_unified_command_center_release_train_command')
