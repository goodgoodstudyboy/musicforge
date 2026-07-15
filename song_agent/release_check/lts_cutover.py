from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from song_agent.platform.persistence import V13MigrationOrchestrator, verify_v13_migration_evidence
from song_agent.architecture_guardrails import build_architecture_snapshot
from song_agent.release_check.lts_audit import build_lts_audit, write_reviewer_package
from song_agent.release_check.architecture_ratchet import verify_architecture_ratchet_report


def run_lts_cutover_smoke(root: Path) -> tuple[bool, str]:
    try:
        audit = build_lts_audit(root)
        with tempfile.TemporaryDirectory(prefix="musicforge-v13-cutover-") as temp:
            details = _exercise_migration(root, Path(temp), audit)
        return all(details.values()), json.dumps(details, sort_keys=True)
    except Exception as exc:
        return False, f"v13 LTS cutover smoke failed: {exc}"


def _exercise_migration(root: Path, temp: Path, audit: dict[str, object]) -> dict[str, bool]:
    workspace = temp / ".musicforge"
    shutil.copytree(root / "tests" / "fixtures" / "v12_13_program_workspace" / "workspace", workspace)
    migration = V13MigrationOrchestrator(workspace)
    plan = migration.dry_run()
    rollback = migration.rollback_rehearsal()
    report = migration.execute()
    archive, verification = migration.build_evidence_archive(plan, report, rollback, temp / "migration-evidence.zip")
    original = archive.read_bytes()
    archive.write_bytes(original + b"tamper")
    tampered = verify_v13_migration_evidence(archive, require_anchor=True)
    reviewer = write_reviewer_package(root, temp / "reviewer", runtime={"migration": verification})
    reviewer_bytes = b"\n".join(path.read_bytes() for path in reviewer.iterdir() if path.is_file())
    current_baseline = json.loads((root / "architecture-baseline.json").read_text(encoding="utf-8"))
    ratchet_report = json.loads((reviewer / "architecture-ratchet.json").read_text(encoding="utf-8"))
    ratchet_verification = verify_architecture_ratchet_report(
        root,
        ratchet_report,
        current_baseline=current_baseline,
        snapshot=build_architecture_snapshot(root),
    )
    return {
        "lts_audit_passed": audit.get("status") == "passed",
        "verified_backup": bool(report.get("verified_backup")),
        "source_preserved": bool(report.get("source_preserved")),
        "rollback_passed": rollback.get("status") == "passed",
        "migration_fixture_nonempty": int(plan.get("file_count") or 0) >= 6,
        "program_documents_imported": int(report.get("imported_program_document_count") or 0) >= 6,
        "migration_archive_passed": verification.get("status") == "passed",
        "migration_tamper_failed": tampered.get("status") == "failed",
        "migration_secret_redacted": b"fixture-review-chair" not in original,
        "reviewer_package_complete": _reviewer_files(reviewer),
        "reviewer_architecture_ratchet_recomputed": ratchet_verification.get("status") == "passed",
        "reviewer_paths_public_safe": str(root).encode() not in reviewer_bytes and str(temp).encode() not in reviewer_bytes,
    }


def _reviewer_files(root: Path) -> bool:
    required = {
        "README.md",
        "architecture.json",
        "architecture-ratchet.json",
        "source-comparison.json",
        "import-graph.json",
        "duplicate-helpers.json",
        "verifier-migration.json",
        "lifecycle-migration.json",
        "persistence-migration.json",
        "cli-api-compatibility.json",
        "compatibility.json",
        "deprecations.json",
        "migration-rollback.json",
        "ci-matrix.json",
        "release-check-reports.json",
        "performance.json",
        "debt.json",
        "release-alignment.json",
        "security-attack-matrix.json",
        "runtime-verification.json",
        "reviewer-package-manifest.json",
        "lts-certification.json",
    }
    return {path.name for path in root.iterdir() if path.is_file()} == required
