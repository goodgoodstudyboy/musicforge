from __future__ import annotations

import json
import tempfile
from pathlib import Path

from song_agent.platform.persistence import V13MigrationOrchestrator, verify_v13_migration_evidence
from song_agent.platform.verification.hashing import integrity_hash
from song_agent.release_check.lts_audit import build_lts_audit, write_reviewer_package


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
    source = workspace / "unified-release-programs" / "urp-v13" / "program-report.json"
    source.parent.mkdir(parents=True)
    document = {"program_id": "urp-v13", "status": "ready", "api_key": "sk-not-exported"}
    document["integrity_hash"] = integrity_hash(document)
    source.write_text(json.dumps(document), encoding="utf-8")
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
    return {
        "lts_audit_passed": audit.get("status") == "passed",
        "verified_backup": bool(report.get("verified_backup")),
        "source_preserved": bool(report.get("source_preserved")),
        "rollback_passed": rollback.get("status") == "passed",
        "migration_archive_passed": verification.get("status") == "passed",
        "migration_tamper_failed": tampered.get("status") == "failed",
        "migration_secret_redacted": b"sk-not-exported" not in original,
        "reviewer_package_complete": _reviewer_files(reviewer),
        "reviewer_paths_public_safe": str(root).encode() not in reviewer_bytes and str(temp).encode() not in reviewer_bytes,
    }


def _reviewer_files(root: Path) -> bool:
    required = {
        "README.md",
        "architecture.json",
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
    }
    return {path.name for path in root.iterdir() if path.is_file()} == required
