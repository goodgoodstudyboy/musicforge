from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.platform.persistence import V13MigrationOrchestrator
from song_agent.release_check.lts_audit import build_lts_audit
from song_agent.release_check.matrix import select_check_definitions


CURRENT_PROFILES = ("v13", "latest", "ga", "security")
FINAL_PROFILES = (*CURRENT_PROFILES, "full")
PROGRAM_IMPORTER_PREFIXES = (
    "song_agent.domains.program",
    "song_agent.application.program",
    "song_agent.interfaces.api.routes.program",
    "song_agent.interfaces.cli.commands.program",
)


def build_lts_recertification(
    repo_root: Path | str = ".",
    *,
    audit: DomainDocument | None = None,
    runtime: DomainDocument | None = None,
) -> DomainDocument:
    root = Path(repo_root).resolve()
    from song_agent.release_check.checks.registry import callable_provenance

    lts_audit = audit or build_lts_audit(root)
    snapshot = build_architecture_snapshot(root)
    program_imports = [
        row
        for row in snapshot.get("active_to_compatibility_imports") or []
        if str(row.get("importer") or "").startswith(PROGRAM_IMPORTER_PREFIXES)
    ]
    profile_legacy = {
        profile: [
            definition.check_id
            for definition in select_check_definitions(profile=profile, run_tests=False)
            if definition.callable_name and callable_provenance(definition.callable_name) != "active"
        ]
        for profile in CURRENT_PROFILES
    }
    migration = _migration_rehearsal(root)
    quality_workflow = (root / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    nightly_workflow = (root / ".github" / "workflows" / "nightly.yml").read_text(encoding="utf-8")
    structural_checks = {
        "lts_audit_passed": lts_audit.get("status") == "passed",
        "program_active_to_compatibility_zero": not program_imports,
        "current_profiles_legacy_zero": all(not rows for rows in profile_legacy.values()),
        "representative_migration_nonempty": int(migration.get("file_count") or 0) > 0,
        "migration_backup_verified": migration.get("backup_verified") is True,
        "migration_rollback_bit_identical": migration.get("rollback_identical") is True,
        "active_source_reduced": (lts_audit.get("checks") or {}).get("source_reduction_target") is True,
        "final_sha_ci_attestations": all(
            token in quality_workflow and token in nightly_workflow
            for token in ("certification:", "tools/assert_ci_final_sha.py", "evidence_kind", "actions/upload-artifact@v4")
        ),
    }
    p1_blockers = [check_id for check_id, passed in structural_checks.items() if not passed]
    runtime_checks = _runtime_checks(runtime or {}) if runtime else {}
    runtime_status = "pending" if not runtime else ("passed" if all(runtime_checks.values()) else "failed")
    structural_status = "passed" if not p1_blockers else "failed"
    return {
        "schema_version": 1,
        "package_type": "musicforge_v13_lts_recertification",
        "status": "failed" if structural_status == "failed" or runtime_status == "failed" else "passed",
        "structural_status": structural_status,
        "runtime_status": runtime_status,
        "checks": structural_checks,
        "runtime_checks": runtime_checks,
        "p1_blockers": p1_blockers,
        "summary": {
            "open_p1_count": len(p1_blockers),
            "program_active_to_compatibility_import_count": len(program_imports),
            "current_profile_legacy_callable_count": sum(len(rows) for rows in profile_legacy.values()),
            "migration_file_count": int(migration.get("file_count") or 0),
        },
        "source": {
            "program_active_to_compatibility_imports": program_imports,
            "current_profile_legacy_callables": profile_legacy,
            "migration": migration,
            "source_comparison": lts_audit.get("comparison") or {},
            "known_non_blocking_debt": ["ARCH-007", "ARCH-008", "ARCH-010", "ARCH-012", "QUAL-001"],
        },
    }


def run_lts_recertification_smoke(root: Path) -> tuple[bool, str]:
    try:
        report = build_lts_recertification(root)
        current = (report.get("source") or {}).get("source_comparison", {}).get("current", {})
        checks = {
            "structural_status": report.get("structural_status") == "passed",
            "p1_zero": (report.get("summary") or {}).get("open_p1_count") == 0,
            "program_slice_zero": (report.get("summary") or {}).get("program_active_to_compatibility_import_count") == 0,
            "current_profiles_zero": (report.get("summary") or {}).get("current_profile_legacy_callable_count") == 0,
            "migration_nonempty": (report.get("summary") or {}).get("migration_file_count", 0) > 0,
            "source_total_visible": int(current.get("lines") or 0) > 0,
            "source_active_visible": int(current.get("active_lines") or 0) > 0,
            "source_compatibility_visible": int(current.get("compatibility_lines") or 0) > 0,
        }
        return all(checks.values()), json.dumps(checks, sort_keys=True)
    except Exception as exc:
        return False, f"v13.8 LTS recertification smoke failed: {exc}"


def _migration_rehearsal(root: Path) -> ImplementationDocument:
    fixture = root / "tests" / "fixtures" / "v12_13_program_workspace" / "workspace"
    with tempfile.TemporaryDirectory(prefix="musicforge-v138-migration-") as temp:
        workspace = Path(temp) / ".musicforge"
        shutil.copytree(fixture, workspace)
        orchestrator = V13MigrationOrchestrator(workspace)
        plan = orchestrator.dry_run()
        rehearsal = orchestrator.rollback_rehearsal()
    return {
        "status": "passed"
        if int(plan.get("file_count") or 0) > 0
        and rehearsal.get("status") == "passed"
        and rehearsal.get("source_restored") is True
        else "failed",
        "file_count": int(plan.get("file_count") or 0),
        "backup_verified": rehearsal.get("backup_verified") is True,
        "rollback_identical": rehearsal.get("source_restored") is True,
    }


def _runtime_checks(runtime: ImplementationDocument) -> dict[str, bool]:
    final_sha = str(runtime.get("final_sha") or "")
    ci = runtime.get("ci") if isinstance(runtime.get("ci"), dict) else {}
    profiles = runtime.get("release_checks") if isinstance(runtime.get("release_checks"), dict) else {}
    profile_rows = profiles.get("profiles") if isinstance(profiles.get("profiles"), dict) else {}
    tests = runtime.get("tests") if isinstance(runtime.get("tests"), dict) else {}
    migration = runtime.get("migration") if isinstance(runtime.get("migration"), dict) else {}
    performance = runtime.get("performance") if isinstance(runtime.get("performance"), dict) else {}
    alignment = runtime.get("alignment") if isinstance(runtime.get("alignment"), dict) else {}
    return {
        "final_sha_present": len(final_sha) == 40,
        "quality_final_sha": _passed_sha(ci.get("quality"), final_sha),
        "nightly_final_sha": _passed_sha(ci.get("nightly"), final_sha),
        **{f"release_check_{profile}": _passed_sha(profile_rows.get(profile), final_sha) for profile in FINAL_PROFILES},
        "active_tests": _passed_sha(tests.get("active"), final_sha),
        "legacy_tests": _passed_sha(tests.get("legacy"), final_sha),
        "runtime_migration": _passed_sha(migration, final_sha)
        and int(migration.get("file_count") or 0) > 0
        and migration.get("rollback_identical") is True,
        "runtime_performance": _passed_sha(performance, final_sha),
        "release_alignment": _passed_sha(alignment, final_sha),
    }


def _passed_sha(value: Any, final_sha: str) -> bool:
    row = value if isinstance(value, dict) else {}
    return bool(final_sha) and row.get("status") == "passed" and row.get("sha") == final_sha
