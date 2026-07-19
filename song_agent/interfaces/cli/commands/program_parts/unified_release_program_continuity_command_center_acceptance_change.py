from __future__ import annotations


from song_agent.platform.contracts.documents import ImplementationDocument

from . import dependencies as _commands_program_parts_dependencies

from .program_component_and_cross_domain_adapters import _add_command_center_acceptance_source_args
Any, CommandSpec, Path, ProgramApplicationService, ProviderConfig, ProviderError, SongRequest, UnifiedCommandCenterContinuousReviewStore, UnifiedCommandCenterDriftResponseStore, UnifiedCommandCenterEvidenceReviewStore, UnifiedCommandCenterHandoffStore, UnifiedCommandCenterReleaseTrainChangeControlStore, UnifiedCommandCenterReleaseTrainHandoffStore, UnifiedCommandCenterReleaseTrainLifecycleStore, UnifiedCommandCenterReleaseTrainStore, UnifiedCommandCenterReviewerDecisionBoardStore, UnifiedCommandCenterSignoffStore, UnifiedCommandCenterStore, argparse, build_auth_config, generate_request, json, load_provider_config, os, provider_configured, read_json, sys, test_provider_config, write_interface_document, write_json, write_unified_command_center_archive_verification_report, write_unified_command_center_continuous_review_verification_report, write_unified_command_center_drift_response_verification_report, write_unified_command_center_evidence_review_acceptance_verification_report, write_unified_command_center_evidence_review_verification_report, write_unified_command_center_handoff_verification_report, write_unified_command_center_release_train_change_control_verification_report, write_unified_command_center_release_train_handoff_verification_report, write_unified_command_center_release_train_lifecycle_verification_report, write_unified_command_center_release_train_verification_report, write_unified_command_center_reviewer_decision_board_verification_report, write_unified_command_center_verification_report, write_unified_release_program_accepted_evidence_verification_report, write_unified_release_program_continuity_acceptance_change_verification_report, write_unified_release_program_continuity_acceptance_verification_report, write_unified_release_program_continuity_command_center_verification_report, write_unified_release_program_continuity_distribution_verification_report, write_unified_release_program_continuity_verification_report, write_unified_release_program_handoff_verification_report, write_unified_release_program_operations_verification_report, write_unified_release_program_review_pack_verification_report, write_unified_release_program_vault_operations_verification_report, write_unified_release_program_vault_verification_report, write_unified_release_program_verification_report = _commands_program_parts_dependencies.Any, _commands_program_parts_dependencies.CommandSpec, _commands_program_parts_dependencies.Path, _commands_program_parts_dependencies.ProgramApplicationService, _commands_program_parts_dependencies.ProviderConfig, _commands_program_parts_dependencies.ProviderError, _commands_program_parts_dependencies.SongRequest, _commands_program_parts_dependencies.UnifiedCommandCenterContinuousReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterDriftResponseStore, _commands_program_parts_dependencies.UnifiedCommandCenterEvidenceReviewStore, _commands_program_parts_dependencies.UnifiedCommandCenterHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainChangeControlStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainHandoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainLifecycleStore, _commands_program_parts_dependencies.UnifiedCommandCenterReleaseTrainStore, _commands_program_parts_dependencies.UnifiedCommandCenterReviewerDecisionBoardStore, _commands_program_parts_dependencies.UnifiedCommandCenterSignoffStore, _commands_program_parts_dependencies.UnifiedCommandCenterStore, _commands_program_parts_dependencies.argparse, _commands_program_parts_dependencies.build_auth_config, _commands_program_parts_dependencies.generate_request, _commands_program_parts_dependencies.json, _commands_program_parts_dependencies.load_provider_config, _commands_program_parts_dependencies.os, _commands_program_parts_dependencies.provider_configured, _commands_program_parts_dependencies.read_json, _commands_program_parts_dependencies.sys, _commands_program_parts_dependencies.test_provider_config, _commands_program_parts_dependencies.write_interface_document, _commands_program_parts_dependencies.write_json, _commands_program_parts_dependencies.write_unified_command_center_archive_verification_report, _commands_program_parts_dependencies.write_unified_command_center_continuous_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_drift_response_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_command_center_evidence_review_verification_report, _commands_program_parts_dependencies.write_unified_command_center_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_change_control_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_handoff_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_lifecycle_verification_report, _commands_program_parts_dependencies.write_unified_command_center_release_train_verification_report, _commands_program_parts_dependencies.write_unified_command_center_reviewer_decision_board_verification_report, _commands_program_parts_dependencies.write_unified_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_accepted_evidence_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_change_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_acceptance_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_command_center_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_distribution_verification_report, _commands_program_parts_dependencies.write_unified_release_program_continuity_verification_report, _commands_program_parts_dependencies.write_unified_release_program_handoff_verification_report, _commands_program_parts_dependencies.write_unified_release_program_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_review_pack_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_operations_verification_report, _commands_program_parts_dependencies.write_unified_release_program_vault_verification_report, _commands_program_parts_dependencies.write_unified_release_program_verification_report
def build_unified_release_program_continuity_command_center_acceptance_change_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Receiver Acceptance Change Control and lifecycle audit.")
    subparsers = parser.add_subparsers(dest="action", required=True)
    actions = ("status", "create-cr", "approve-cr", "reset-signoff", "refresh-lifecycle", "export", "zip", "verify", "gate")
    for action in actions:
        cmd = subparsers.add_parser(action, help=f"{action} Receiver Acceptance Change Control.")
        cmd.add_argument("program_id")
        cmd.add_argument("--json", action="store_true")
        cmd.add_argument("--change-request-id", default=None)
        cmd.add_argument("--change-type", default=None)
        cmd.add_argument("--allowed-action", action="append", default=[])
        cmd.add_argument("--reason", default=None)
        cmd.add_argument("--requested-by", default=None)
        cmd.add_argument("--approved-by", default=None)
        cmd.add_argument("--role", default=None)
        cmd.add_argument("--approved-action", action="append", default=[])
        cmd.add_argument("--reset-by", default=None)
        cmd.add_argument("--archive-zip", type=Path, default=None)
        cmd.add_argument("--verification-report", type=Path, default=None)
        cmd.add_argument("--receiver-acceptance-archive", "--acceptance-archive", dest="acceptance_archive", type=Path, default=None)
        cmd.add_argument("--receiver-acceptance-verification-report", "--acceptance-verification-report", dest="acceptance_verification_report", type=Path, default=None)
        cmd.add_argument("--receiver-acceptance-signoff-binding", "--acceptance-signoff-binding", dest="acceptance_signoff_binding", type=Path, default=None)
        cmd.add_argument("--previous-acceptance-root", type=Path, default=None)
        cmd.add_argument("--strict", action="store_true")
        cmd.add_argument("--require-current", action="store_true")
        cmd.add_argument("--require-reset-proofs", action="store_true")
        cmd.add_argument("--report-out", type=Path, default=None)
        _add_command_center_acceptance_source_args(cmd)
    return parser

def build_verify_unified_release_program_continuity_command_center_acceptance_change_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a Receiver Acceptance Change Control Archive ZIP.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-current", action="store_true")
    parser.add_argument("--require-reset-proofs", action="store_true")
    parser.add_argument("--receiver-acceptance-archive", "--acceptance-archive", dest="acceptance_archive", type=Path, default=None)
    parser.add_argument("--receiver-acceptance-verification-report", "--acceptance-verification-report", dest="acceptance_verification_report", type=Path, default=None)
    parser.add_argument("--receiver-acceptance-signoff-binding", "--acceptance-signoff-binding", dest="acceptance_signoff_binding", type=Path, default=None)
    parser.add_argument("--previous-acceptance-root", type=Path, default=None)
    parser.add_argument("--max-zip-size-mb", type=int, default=256)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=512)
    parser.add_argument("--max-entry-count", type=int, default=2000)
    return parser

def _unified_command_center_requirements_from_args(args: argparse.Namespace) -> dict[str, bool]:
    requirements: dict[str, bool] = {}
    mapping = {
        "require_audio_command_center": "require_audio_command_center",
        "require_trust_operations_hub": "require_trust_operations_hub",
        "require_public_trust_center": "require_public_trust_center",
        "require_maintenance_backup": "require_maintenance_backup",
        "require_ga_readiness": "require_ga_readiness",
        "require_release_check": "require_release_check",
        "require_release_ready": "require_release_ready",
        "require_distribution_ready": "require_distribution_ready",
        "require_submission_ready": "require_submission_ready",
        "require_operations_ready": "require_operations_ready",
    }
    for attr, key in mapping.items():
        if bool(getattr(args, attr, False)):
            requirements[key] = True
    negative = {
        "no_require_audio_command_center": "require_audio_command_center",
        "no_require_trust_operations_hub": "require_trust_operations_hub",
        "no_require_public_trust_center": "require_public_trust_center",
        "no_require_ga_readiness": "require_ga_readiness",
        "no_require_release_check": "require_release_check",
        "no_require_release_ready": "require_release_ready",
        "no_require_distribution_ready": "require_distribution_ready",
        "no_require_submission_ready": "require_submission_ready",
        "no_require_operations_ready": "require_operations_ready",
    }
    for attr, key in negative.items():
        if bool(getattr(args, attr, False)):
            requirements[key] = False
    return requirements

def _unified_command_center_evidence_from_args(args: argparse.Namespace) -> ImplementationDocument:
    evidence: ImplementationDocument = {
        "release": {
            "zip": getattr(args, "release_zip", None),
            "verification_report": getattr(args, "release_verification_report", None),
        },
        "audio-command-center": {
            "zip": getattr(args, "release_audio_command_center", None),
            "verification_report": getattr(args, "release_audio_command_center_verification_report", None),
        },
        "distribution": {
            "zips": getattr(args, "distribution_zip", []),
            "verification_reports": getattr(args, "distribution_verification_report", []),
        },
        "submission": {
            "zips": getattr(args, "submission_zip", []),
            "verification_reports": getattr(args, "submission_verification_report", []),
        },
        "operations": {
            "zip": getattr(args, "release_operations_zip", None),
            "verification_report": getattr(args, "release_operations_verification_report", None),
        },
        "trust-operations-hub": {
            "zip": getattr(args, "trust_operations_hub", None),
            "verification_report": getattr(args, "trust_operations_hub_verification_report", None),
        },
        "public-trust-center": {
            "zip": getattr(args, "public_trust_center", None),
            "verification_report": getattr(args, "public_trust_center_verification_report", None),
        },
        "maintenance": {
            "zip": getattr(args, "maintenance_backup", None),
            "verification_report": getattr(args, "maintenance_backup_verification_report", None),
        },
        "ga-readiness": {
            "report": getattr(args, "ga_readiness_report", None),
            "verification_report": getattr(args, "ga_readiness_verification_report", None),
        },
        "release-check": {"report": getattr(args, "release_check_report", None)},
    }
    requirements = _unified_command_center_requirements_from_args(args)
    if requirements:
        evidence["requirements"] = requirements
    return evidence

def _run_unified_command_center_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass
    pass
    pass
    pass
    pass

    store = UnifiedCommandCenterStore()
    signoff_store = UnifiedCommandCenterSignoffStore(store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    evidence = _unified_command_center_evidence_from_args(args)
    if args.action == "create":
        payload = {
            "center_id": args.center_id,
            "name": args.name,
            "scope": args.scope,
            "profile": args.profile,
            "primary_release_id": args.primary_release_id,
            "release_ids": args.release_id,
            "requirements": _unified_command_center_requirements_from_args(args),
        }
        center = store.create(payload)
        return {"ok": True, "center": center, "summary": {"center_id": center.get("center_id")}, "status": center.get("status")}
    if args.action == "list":
        centers = store.list_centers()
        return {"ok": True, "centers": centers, "summary": {"center_count": len(centers)}, "status": "passed"}
    if args.action == "status":
        center = store.read_center(args.center_id)
        report = store.read_report(args.center_id) if store.report_path(args.center_id).exists() else {}
        return {"ok": True, "center": center, "report": report, "summary": report.get("summary", {}), "status": center.get("status")}
    if args.action == "refresh":
        report = store.refresh(args.center_id, evidence)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "report":
        report = store.read_report(args.center_id)
        return {"ok": report.get("status") == "ready", "report": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "inventory":
        inventory = read_json(store.inventory_path(args.center_id))
        return {"ok": True, "inventory": inventory, "summary": inventory.get("summary", {}), "status": "passed"}
    if args.action == "readiness":
        readiness = read_json(store.readiness_path(args.center_id))
        return {"ok": readiness.get("overall_status") == "ready", "readiness": readiness, "summary": {"overall_status": readiness.get("overall_status")}, "status": readiness.get("overall_status")}
    if args.action == "gap-plan":
        gap_plan = read_json(store.gap_plan_path(args.center_id))
        return {"ok": int((gap_plan.get("summary") or {}).get("action_count") or 0) == 0, "gap_plan": gap_plan, "summary": gap_plan.get("summary", {}), "status": "passed" if int((gap_plan.get("summary") or {}).get("action_count") or 0) == 0 else "blocked"}
    if args.action == "runbook":
        runbook = store.create_runbook(args.center_id, evidence)
        return {"ok": True, "runbook": runbook, "summary": runbook.get("summary", {}), "status": "passed"}
    if args.action == "run-safe":
        result = store.run_safe(args.center_id, evidence)
        failed = int((result.get("summary") or {}).get("failed_count") or 0)
        return {"ok": failed == 0, "runbook_result": result, "summary": result.get("summary", {}), "status": "passed" if failed == 0 else "failed"}
    if args.action == "export":
        result = store.export_package(args.center_id, evidence)
        return {"ok": result.get("status") == "ready", **result, "summary": result.get("manifest", {})}
    if args.action == "zip":
        result = store.build_zip(args.center_id, evidence)
        return {"ok": result.get("status") == "ready", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_zip(args.center_id, evidence=evidence, strict=args.strict, require_ready=args.require_ready)
        if args.report_out is not None:
            write_unified_command_center_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "signoff":
        signoff = signoff_store.signoff(args.center_id, {"signed_by": args.signed_by, "role": args.role, "reason": args.reason})
        return {"ok": True, "signoff": signoff, "summary": {"signoff_hash": signoff.get("integrity_hash")}, "status": signoff.get("status")}
    if args.action == "archive":
        manifest = signoff_store.export_archive(args.center_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "archive-zip":
        result = signoff_store.build_archive_zip(args.center_id)
        return {"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-archive":
        report = signoff_store.verify_archive(args.center_id, {"strict": args.strict, "require_current_ucc": args.require_current_ucc})
        if args.report_out is not None:
            write_unified_command_center_archive_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "handoff":
        manifest = handoff_store.export_handoff(args.center_id)
        return {"ok": True, "manifest": manifest, "summary": manifest.get("summary", {}), "status": "passed"}
    if args.action == "handoff-zip":
        result = handoff_store.build_handoff_zip(args.center_id)
        return {"ok": True, **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify-handoff":
        report = handoff_store.verify_handoff(args.center_id, {"strict": args.strict, "require_archive": args.require_archive})
        if args.report_out is not None:
            write_unified_command_center_handoff_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    if args.action == "change-request-create":
        cr = signoff_store.create_change_request(args.center_id, {"created_by": args.created_by, "reason": args.reason, "risk": args.risk})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "change-request-approve":
        cr = signoff_store.approve_change_request(args.center_id, args.change_request_id, {"approved_by": args.approved_by, "reason": args.reason})
        return {"ok": True, "change_request": cr, "summary": {"change_request_id": cr.get("change_request_id")}, "status": cr.get("status")}
    if args.action == "signoff-reset":
        result = signoff_store.reset_signoff(args.center_id, args.change_request_id, {"reason": args.reason})
        return {"ok": True, **result, "summary": {"change_request_id": args.change_request_id}}
    raise ValueError("Unsupported unified-command-center command.")

def _unified_command_center_review_payload_from_args(args: argparse.Namespace) -> ImplementationDocument:
    return {
        "review_id": getattr(args, "review_id", None),
        "created_by": getattr(args, "created_by", None),
        "include_handoff": getattr(args, "include_handoff", True),
        "archive_zip": getattr(args, "archive_zip", None),
        "archive_verification_report": getattr(args, "archive_verification_report", None),
        "handoff_zip": getattr(args, "handoff_zip", None),
        "handoff_verification_report": getattr(args, "handoff_verification_report", None),
        "command_center_zip": getattr(args, "command_center_zip", None),
        "command_center_verification_report": getattr(args, "command_center_verification_report", None),
        "signoff_binding": getattr(args, "signoff_binding", None),
        "ga_readiness_report": getattr(args, "ga_readiness_report", None),
        "release_check_report": getattr(args, "release_check_report", None),
    }

def _run_unified_command_center_review_command(args: argparse.Namespace) -> ImplementationDocument:
    pass
    pass
    pass
    pass
    pass

    center_store = UnifiedCommandCenterStore()
    signoff_store = UnifiedCommandCenterSignoffStore(center_store)
    handoff_store = UnifiedCommandCenterHandoffStore(signoff_store)
    store = UnifiedCommandCenterContinuousReviewStore(center_store, signoff_store=signoff_store, handoff_store=handoff_store)
    payload = _unified_command_center_review_payload_from_args(args)
    if args.action == "create":
        plan = store.create_plan(args.center_id, payload)
        return {"ok": True, "plan": plan, "summary": {"review_id": plan.get("review_id")}, "status": plan.get("status")}
    if args.action == "list":
        rows = store.list_reviews(args.center_id)
        return {"ok": True, "reviews": rows, "summary": {"review_count": len(rows)}, "status": "passed"}
    if args.action == "status":
        docs = store.read_review(args.center_id, args.review_id)
        drift = docs.get("drift_report") or {}
        return {"ok": bool(docs), "review": docs, "summary": drift.get("summary", {}), "status": drift.get("status") or docs.get("plan", {}).get("status")}
    if args.action == "run":
        result = store.run_review(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result}
    if args.action == "export":
        result = store.export_package(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": result.get("manifest", {}).get("summary", {})}
    if args.action == "zip":
        result = store.build_zip(args.center_id, args.review_id, payload)
        return {"ok": result.get("status") == "passed", **result, "summary": {"zip_sha256": result.get("zip_sha256")}}
    if args.action == "verify":
        report = store.verify_package(
            args.center_id,
            args.review_id,
            {
                **payload,
                "strict": args.strict,
                "require_clear": args.require_clear,
                "require_recovery_drill": args.require_recovery_drill,
                "require_current_review": args.require_current_review,
            },
        )
        if args.report_out is not None:
            write_unified_command_center_continuous_review_verification_report(report, args.report_out)
        return {"ok": report.get("status") == "passed", "verification": report, "summary": report.get("summary", {}), "status": report.get("status")}
    raise ValueError("Unsupported unified-command-center-review command.")

def _unified_command_center_drift_response_payload_from_args(args: argparse.Namespace) -> ImplementationDocument:
    return {
        "response_id": getattr(args, "response_id", None),
        "source_review_id": getattr(args, "source_review_id", None),
        "created_by": getattr(args, "created_by", None),
        "source_review_zip": getattr(args, "source_review_zip", None),
        "source_review_verification_report": getattr(args, "source_review_verification_report", None),
        "recheck_review_zip": getattr(args, "recheck_review_zip", None),
        "recheck_review_verification_report": getattr(args, "recheck_review_verification_report", None),
        "change_request_binding_report": getattr(args, "change_request_binding_report", None),
        "archive_zip": getattr(args, "archive_zip", None),
        "archive_verification_report": getattr(args, "archive_verification_report", None),
        "handoff_zip": getattr(args, "handoff_zip", None),
        "handoff_verification_report": getattr(args, "handoff_verification_report", None),
        "command_center_zip": getattr(args, "command_center_zip", None),
        "command_center_verification_report": getattr(args, "command_center_verification_report", None),
        "signoff_binding": getattr(args, "signoff_binding", None),
    }

__all__ = ('build_unified_release_program_continuity_command_center_acceptance_change_parser', 'build_verify_unified_release_program_continuity_command_center_acceptance_change_parser', '_unified_command_center_requirements_from_args', '_unified_command_center_evidence_from_args', '_run_unified_command_center_command', '_unified_command_center_review_payload_from_args', '_run_unified_command_center_review_command', '_unified_command_center_drift_response_payload_from_args')
