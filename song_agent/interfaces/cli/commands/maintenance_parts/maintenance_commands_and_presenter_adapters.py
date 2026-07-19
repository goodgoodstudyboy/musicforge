from __future__ import annotations


from song_agent.platform.contracts.documents import ImplementationDocument

from song_agent.interfaces.cli.bindings import BINDINGS as CLI_BINDINGS

from . import dependencies as _commands_maintenance_parts_dependencies

from .cross_domain_adapters import _writable_status
Any, CommandSpec, LTSMaintenanceStore, MAINTENANCE_PROFILES, Path, ProviderConfig, ProviderError, SongRequest, argparse, build_auth_config, generate_request, json, load_provider_config, maintenance_backup_verification_exit_code, os, print_maintenance_backup_verification_report, provider_configured, read_json, sys, test_provider_config, verify_maintenance_backup_zip, write_interface_document, write_json, write_maintenance_backup_verification_report = _commands_maintenance_parts_dependencies.Any, _commands_maintenance_parts_dependencies.CommandSpec, _commands_maintenance_parts_dependencies.LTSMaintenanceStore, _commands_maintenance_parts_dependencies.MAINTENANCE_PROFILES, _commands_maintenance_parts_dependencies.Path, _commands_maintenance_parts_dependencies.ProviderConfig, _commands_maintenance_parts_dependencies.ProviderError, _commands_maintenance_parts_dependencies.SongRequest, _commands_maintenance_parts_dependencies.argparse, _commands_maintenance_parts_dependencies.build_auth_config, _commands_maintenance_parts_dependencies.generate_request, _commands_maintenance_parts_dependencies.json, _commands_maintenance_parts_dependencies.load_provider_config, _commands_maintenance_parts_dependencies.maintenance_backup_verification_exit_code, _commands_maintenance_parts_dependencies.os, _commands_maintenance_parts_dependencies.print_maintenance_backup_verification_report, _commands_maintenance_parts_dependencies.provider_configured, _commands_maintenance_parts_dependencies.read_json, _commands_maintenance_parts_dependencies.sys, _commands_maintenance_parts_dependencies.test_provider_config, _commands_maintenance_parts_dependencies.verify_maintenance_backup_zip, _commands_maintenance_parts_dependencies.write_interface_document, _commands_maintenance_parts_dependencies.write_json, _commands_maintenance_parts_dependencies.write_maintenance_backup_verification_report
print_acceptance_fix_sprint_result = CLI_BINDINGS.quality.print_acceptance_fix_sprint_result

print_acceptance_kb_result = CLI_BINDINGS.quality.print_acceptance_kb_result

print_ga_readiness_report = CLI_BINDINGS.release_check.print_ga_readiness_report

print_planning_rule_governance_result = CLI_BINDINGS.quality.print_planning_rule_governance_result

print_planning_rule_impact_result = CLI_BINDINGS.quality.print_planning_rule_impact_result

print_planning_ruleset_result = CLI_BINDINGS.quality.print_planning_ruleset_result

print_planning_simulation_result = CLI_BINDINGS.quality.print_planning_simulation_result

print_public_trust_center_result = CLI_BINDINGS.trust.print_public_trust_center_result

print_release_audio_review_result = CLI_BINDINGS.quality.print_release_audio_review_result

print_release_operations_archive_result = CLI_BINDINGS.delivery.print_release_operations_archive_result

print_release_operations_audit_result = CLI_BINDINGS.delivery.print_release_operations_audit_result

print_release_operations_result = CLI_BINDINGS.delivery.print_release_operations_result

print_release_operations_reviewer_pack_result = CLI_BINDINGS.delivery.print_release_operations_reviewer_pack_result

print_release_operations_runbook_result = CLI_BINDINGS.delivery.print_release_operations_runbook_result

print_release_operations_signoff_result = CLI_BINDINGS.delivery.print_release_operations_signoff_result

print_release_portfolio_audit_result = CLI_BINDINGS.trust.print_release_portfolio_audit_result

print_release_portfolio_governance_attestation_accepted_evidence_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_accepted_evidence_result

print_release_portfolio_governance_attestation_portal_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_portal_result

print_release_portfolio_governance_attestation_portal_review_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_portal_review_result

print_release_portfolio_governance_attestation_registry_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_registry_result

print_release_portfolio_governance_attestation_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_result

print_release_portfolio_governance_attestation_transparency_acknowledgement_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_transparency_acknowledgement_result

print_release_portfolio_governance_attestation_transparency_result = CLI_BINDINGS.trust.print_release_portfolio_governance_attestation_transparency_result

print_release_portfolio_governance_audit_result = CLI_BINDINGS.trust.print_release_portfolio_governance_audit_result

print_release_portfolio_governance_evidence_vault_result = CLI_BINDINGS.trust.print_release_portfolio_governance_evidence_vault_result

print_release_portfolio_governance_final_board_result = CLI_BINDINGS.trust.print_release_portfolio_governance_final_board_result

print_release_portfolio_governance_result = CLI_BINDINGS.trust.print_release_portfolio_governance_result

print_release_portfolio_governance_reviewer_pack_result = CLI_BINDINGS.trust.print_release_portfolio_governance_reviewer_pack_result

print_release_portfolio_governance_signoff_result = CLI_BINDINGS.trust.print_release_portfolio_governance_signoff_result

run_acceptance_check = CLI_BINDINGS.quality.run_acceptance_check

def build_doctor_parser() -> argparse.ArgumentParser:
    doctor_parser = argparse.ArgumentParser(description="Check the local MusicForge setup.")
    doctor_parser.add_argument(
        "--provider-test",
        action="store_true",
        help="Run the configured provider connectivity check.",
    )
    return doctor_parser

def build_maintenance_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local MusicForge LTS maintenance, backups, upgrades, and checks.")
    subparsers = parser.add_subparsers(dest="section", required=True)

    status = subparsers.add_parser("status", help="Show local LTS maintenance status.")
    status.add_argument("--json", action="store_true", help="Print JSON output.")

    backup = subparsers.add_parser("backup", help="Create, verify, and restore maintenance backups.")
    backup_sub = backup.add_subparsers(dest="backup_action", required=True)
    create = backup_sub.add_parser("create", help="Create a maintenance backup.")
    create.add_argument("--mode", choices=["metadata", "workspace", "workspace_with_artifacts"], default="workspace")
    create.add_argument("--json", action="store_true")
    listing = backup_sub.add_parser("list", help="List maintenance backups.")
    listing.add_argument("--json", action="store_true")
    verify = backup_sub.add_parser("verify", help="Verify a maintenance backup by id.")
    verify.add_argument("--backup-id", required=True)
    verify.add_argument("--json", action="store_true")
    restore_plan = backup_sub.add_parser("restore-plan", help="Create a restore plan from a backup.")
    restore_plan.add_argument("--backup-id", default=None)
    restore_plan.add_argument("--zip", dest="zip_path", type=Path, default=None)
    restore_plan.add_argument("--target", type=Path, required=True)
    restore_plan.add_argument("--json", action="store_true")
    restore = backup_sub.add_parser("restore", help="Restore a backup into a target directory.")
    restore.add_argument("--backup-id", default=None)
    restore.add_argument("--zip", dest="zip_path", type=Path, default=None)
    restore.add_argument("--target", type=Path, required=True)
    restore.add_argument("--confirm", action="store_true")
    restore.add_argument("--overwrite", action="store_true")
    restore.add_argument("--allow-current-workspace", action="store_true")
    restore.add_argument("--json", action="store_true")

    upgrade = subparsers.add_parser("upgrade", help="Run upgrade preflight checks.")
    upgrade_sub = upgrade.add_subparsers(dest="upgrade_action", required=True)
    preflight = upgrade_sub.add_parser("preflight", help="Run upgrade preflight checks.")
    preflight.add_argument("--target-version", required=True)
    preflight.add_argument("--require-verified-backup", action="store_true")
    preflight.add_argument("--allow-dirty", action="store_true")
    preflight.add_argument("--json", action="store_true")

    migration = subparsers.add_parser("migration", help="Manage local LTS migrations.")
    migration_sub = migration.add_subparsers(dest="migration_action", required=True)
    migration_sub.add_parser("status", help="Show migration status.").add_argument("--json", action="store_true")
    migration_sub.add_parser("plan", help="Show pending migrations.").add_argument("--json", action="store_true")
    migration_run = migration_sub.add_parser("run", help="Run pending migrations.")
    migration_run.add_argument("--require-backup", action="store_true")
    migration_run.add_argument("--json", action="store_true")

    check = subparsers.add_parser("check", help="Run periodic maintenance checks.")
    check_sub = check.add_subparsers(dest="check_action", required=True)
    check_list = check_sub.add_parser("list", help="List maintenance check profiles and prior runs.")
    check_list.add_argument("--json", action="store_true")
    check_run = check_sub.add_parser("run", help="Run a maintenance check profile.")
    check_run.add_argument("--profile", choices=["daily", "weekly", "release", "emergency"], default="daily")
    check_run.add_argument("--json", action="store_true")
    check_show = check_sub.add_parser("show", help="Show a maintenance check report.")
    check_show.add_argument("--check-id", required=True)
    check_show.add_argument("--json", action="store_true")
    return parser

def build_verify_maintenance_backup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify a MusicForge LTS maintenance backup ZIP.")
    parser.add_argument("zip_path", type=Path, help="Path to musicforge-maintenance-backup.zip.")
    parser.add_argument("--json", action="store_true", help="Print the full verification report as JSON.")
    parser.add_argument("--report-out", type=Path, default=None, help="Write the verification report to this JSON file.")
    parser.add_argument("--strict", action="store_true", help="Run strict verification.")
    parser.add_argument("--max-zip-size-mb", type=int, default=512)
    parser.add_argument("--max-uncompressed-size-mb", type=int, default=2048)
    parser.add_argument("--max-entry-count", type=int, default=20000)
    return parser

def _run_maintenance_command(args: argparse.Namespace) -> ImplementationDocument:
    pass

    store = LTSMaintenanceStore()
    if args.section == "status":
        return store.status()
    if args.section == "backup":
        if args.backup_action == "create":
            result = store.backups.create_backup(mode=args.mode)
            return {"status": result.get("verification", {}).get("status") or "unknown", **result}
        if args.backup_action == "list":
            return {"status": "passed", "backups": store.backups.list_backups()}
        if args.backup_action == "verify":
            verification = store.backups.verify_backup(args.backup_id)
            return {"status": verification.get("status"), "backup_id": args.backup_id, "verification": verification}
        if args.backup_action == "restore-plan":
            plan = store.backups.restore_plan(backup_id=args.backup_id, zip_path=args.zip_path, target=args.target)
            return {"status": plan.get("status"), "restore_plan": plan}
        if args.backup_action == "restore":
            result = store.backups.restore(
                backup_id=args.backup_id,
                zip_path=args.zip_path,
                target=args.target,
                confirm=args.confirm,
                overwrite=args.overwrite,
                allow_current_workspace=args.allow_current_workspace,
            )
            return {"status": result.get("status"), **result}
    if args.section == "upgrade" and args.upgrade_action == "preflight":
        report = store.run_upgrade_preflight(target_version=args.target_version, require_verified_backup=args.require_verified_backup, allow_dirty=args.allow_dirty)
        return {"status": report.get("status"), "preflight": report}
    if args.section == "migration":
        if args.migration_action == "status":
            return {"status": "passed", "migration": store.migration_status()}
        if args.migration_action == "plan":
            return {"status": "passed", "migration_plan": store.migration_plan()}
        if args.migration_action == "run":
            result = store.run_migrations(require_backup=args.require_backup)
            return {"status": "passed", **result}
    if args.section == "check":
        if args.check_action == "list":
            return {"status": "passed", "profiles": sorted(MAINTENANCE_PROFILES), "runs": store.list_check_runs()}
        if args.check_action == "run":
            report = store.run_check(profile=args.profile)
            return {"status": report.get("status"), "report": report}
        if args.check_action == "show":
            path = store.check_runs_dir / args.check_id / "maintenance-check-report.json"
            return {"status": "passed", "report": read_json(path)}
    raise ValueError("Unsupported maintenance command.")

def _print_maintenance_result(result: ImplementationDocument, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    status = result.get("status") or result.get("report", {}).get("status") or result.get("verification", {}).get("status") or "unknown"
    print(f"MusicForge LTS Maintenance: {status}")
    if "backup" in result:
        backup = result.get("backup") or {}
        print(f"backup: {backup.get('backup_id')} {backup.get('verification_status') or backup.get('status')}")
    if "verification" in result:
        verification = result.get("verification") or {}
        print(f"verification: {verification.get('status')} blockers={(verification.get('summary') or {}).get('blocker_count')}")
    if "restore_plan" in result:
        plan = result.get("restore_plan") or {}
        print(f"restore plan: {plan.get('status')} actions={len(plan.get('actions') or [])}")
    if "preflight" in result:
        preflight = result.get("preflight") or {}
        print(f"preflight: {preflight.get('preflight_id')} {preflight.get('status')}")
    if "migration" in result:
        migration = result.get("migration") or {}
        print(f"migration: {migration.get('status')} applied={len(migration.get('applied') or [])}")
    if "report" in result:
        report = result.get("report") or {}
        print(f"report: {report.get('check_id')} {report.get('profile')} {report.get('status')}")

def run_doctor(*, provider_test: bool = False) -> None:
    print("MusicForge doctor")
    print(f"python: ok ({sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")
    print(f"cwd writable: {_writable_status(Path.cwd())}")
    print(f"runs writable: {_writable_status(Path('runs'))}")
    try:
        config, _sources = load_provider_config()
        if provider_configured(config):
            print(
                "provider config: configured "
                f"({config.wire_api}, model={config.model}, key={config.to_public_dict()['api_key_masked'] or '-'})"
            )
        elif config.model or config.base_url or config.api_key:
            print("provider config: warning incomplete")
        else:
            print("provider config: missing")
        if provider_test:
            result = test_provider_config(config)
            print(f"provider test: ok ({result['provider']['wire_api']})")
    except ProviderError as exc:
        print(f"provider config: warning {exc}")
        if provider_test:
            print(f"provider test: failed ({exc})")
    print("local deterministic mode: ok")

def _execute_doctor(argv: list[str]) -> None:
    raw_args = ['doctor', *argv]
    parser = build_doctor_parser()
    args = parser.parse_args(raw_args[1:])
    run_doctor(provider_test=args.provider_test)
    return

def handle_doctor(argv: list[str]) -> None:
    _execute_doctor(argv)

def _execute_maintenance(argv: list[str]) -> None:
    raw_args = ['maintenance', *argv]
    parser = build_maintenance_parser()
    args = parser.parse_args(raw_args[1:])
    result = _run_maintenance_command(args)
    _print_maintenance_result(result, json_output=bool(getattr(args, "json", False)))
    status = str(result.get("status") or result.get("report", {}).get("status") or result.get("verification", {}).get("status") or "")
    if status in {"blocked", "failed"}:
        raise SystemExit(1)
    return

def handle_maintenance(argv: list[str]) -> None:
    _execute_maintenance(argv)

def _execute_verify_maintenance_backup(argv: list[str]) -> None:
    raw_args = ['verify-maintenance-backup', *argv]
    pass





    parser = build_verify_maintenance_backup_parser()
    args = parser.parse_args(raw_args[1:])
    report = verify_maintenance_backup_zip(
        args.zip_path,
        strict=args.strict,
        max_zip_size_mb=args.max_zip_size_mb,
        max_uncompressed_size_mb=args.max_uncompressed_size_mb,
        max_entry_count=args.max_entry_count,
    )
    if args.report_out is not None:
        write_maintenance_backup_verification_report(report, args.report_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_maintenance_backup_verification_report(report)
    raise SystemExit(maintenance_backup_verification_exit_code(report))

def handle_verify_maintenance_backup(argv: list[str]) -> None:
    _execute_verify_maintenance_backup(argv)

__all__ = ('print_acceptance_fix_sprint_result', 'print_acceptance_kb_result', 'print_ga_readiness_report', 'print_planning_rule_governance_result', 'print_planning_rule_impact_result', 'print_planning_ruleset_result', 'print_planning_simulation_result', 'print_public_trust_center_result', 'print_release_audio_review_result', 'print_release_operations_archive_result', 'print_release_operations_audit_result', 'print_release_operations_result', 'print_release_operations_reviewer_pack_result', 'print_release_operations_runbook_result', 'print_release_operations_signoff_result', 'print_release_portfolio_audit_result', 'print_release_portfolio_governance_attestation_accepted_evidence_result', 'print_release_portfolio_governance_attestation_portal_result', 'print_release_portfolio_governance_attestation_portal_review_result', 'print_release_portfolio_governance_attestation_registry_result', 'print_release_portfolio_governance_attestation_result', 'print_release_portfolio_governance_attestation_transparency_acknowledgement_result', 'print_release_portfolio_governance_attestation_transparency_result', 'print_release_portfolio_governance_audit_result', 'print_release_portfolio_governance_evidence_vault_result', 'print_release_portfolio_governance_final_board_result', 'print_release_portfolio_governance_result', 'print_release_portfolio_governance_reviewer_pack_result', 'print_release_portfolio_governance_signoff_result', 'run_acceptance_check', 'build_doctor_parser', 'build_maintenance_parser', 'build_verify_maintenance_backup_parser', '_run_maintenance_command', '_print_maintenance_result', 'run_doctor', '_execute_doctor', 'handle_doctor', '_execute_maintenance', 'handle_maintenance', '_execute_verify_maintenance_backup', 'handle_verify_maintenance_backup')
