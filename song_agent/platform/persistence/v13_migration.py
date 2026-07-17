from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import json
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from song_agent.platform.contracts.packages import PackageSpec
from song_agent.platform.persistence.database import MusicForgeDatabase, SCHEMA_VERSION
from song_agent.platform.persistence.file_artifacts import sha256_path
from song_agent.platform.persistence.migrations import DEFAULT_LEGACY_ROOTS, LegacyWorkspaceMigrator
from song_agent.platform.verification.engine import verify_package_envelope
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok, sha256_bytes, sha256_file
from song_agent.platform.verification.model import build_check, build_verification_report


V13_MIGRATION_PACKAGE_TYPE = "musicforge_v13_migration_evidence"
V13_MIGRATION_VERIFICATION_TYPE = "musicforge_v13_migration_evidence_verification"
V13_MIGRATION_ANCHOR_TYPE = "musicforge_v13_migration_evidence_anchor"
V13_MIGRATION_SPEC = PackageSpec(
    package_type=V13_MIGRATION_PACKAGE_TYPE,
    verification_package_type=V13_MIGRATION_VERIFICATION_TYPE,
    check_prefix="v13_migration",
    required_entries=frozenset({"manifest.json", "migration-plan.json", "migration-report.json", "rollback-rehearsal.json", "README.txt"}),
    semantic_verifier=lambda context: _migration_semantic_checks(context),
)


class V13MigrationOrchestrator:
    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.database = MusicForgeDatabase.from_workspace(self.workspace_root)
        self.migrator = LegacyWorkspaceMigrator(self.workspace_root, database=self.database)

    def dry_run(self) -> dict[str, Any]:
        legacy = self.migrator.dry_run()
        document = {
            "schema_version": 1,
            "package_type": "musicforge_v13_migration_plan",
            "status": legacy["status"],
            "migration_id": legacy["migration_id"],
            "source_hash": legacy["source_hash"],
            "file_count": legacy["file_count"],
            "total_size_bytes": legacy["total_size_bytes"],
            "files": legacy["files"],
            "target_database_schema_version": SCHEMA_VERSION,
            "source_preserved": True,
            "verified_backup_required": bool(legacy["file_count"]),
            "rollback_rehearsal_required": bool(legacy["file_count"]),
            "compatibility": {
                "json_sources_read_only": True,
                "legacy_verifiers_retained": True,
                "active_workflow_index_only": True,
            },
        }
        document["integrity_hash"] = integrity_hash(document)
        return document

    def execute(self) -> dict[str, Any]:
        plan = self.dry_run()
        applied = self.migrator.execute()
        source_preserved = _source_rows(self.workspace_root, plan["files"]) == plan["files"]
        schema_current = self.database.schema_version() == SCHEMA_VERSION
        backup_verified = applied.get("status") in {"no_changes", "already_applied"} or bool(applied.get("backup_path"))
        target_hash = _database_state_hash(self.database)
        status = "passed" if source_preserved and schema_current and backup_verified else "failed"
        report = {
            "schema_version": 1,
            "package_type": "musicforge_v13_migration_report",
            "status": status,
            "migration_id": plan["migration_id"],
            "source_hash": plan["source_hash"],
            "target_hash": target_hash,
            "database_schema_version": self.database.schema_version(),
            "legacy_migration_status": applied.get("status"),
            "verified_backup": backup_verified,
            "source_preserved": source_preserved,
            "imported_workflow_count": int(applied.get("imported_workflow_count") or 0),
            "imported_program_document_count": int(applied.get("imported_program_document_count") or 0),
            "backup_path": applied.get("backup_path") or "",
            "rollback_command": f"song-agent-state migrate-rollback {plan['migration_id']}" if plan["file_count"] else "not_required",
            "executed_at": _now(),
        }
        report["integrity_hash"] = integrity_hash(report)
        target = self.workspace_root / "state" / "migrations" / "v13" / "migration-report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if status != "passed":
            raise RuntimeError("V13 migration post-verification failed.")
        return report

    def rollback_rehearsal(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="musicforge-v13-rollback-") as temp:
            clone = Path(temp) / ".musicforge"
            for name in DEFAULT_LEGACY_ROOTS:
                source = self.workspace_root / name
                if source.is_dir():
                    shutil.copytree(source, clone / name)
            rehearsal = V13MigrationOrchestrator(clone)
            plan = rehearsal.dry_run()
            if not plan["file_count"]:
                return _integrity_document(
                    {
                        "schema_version": 1,
                        "package_type": "musicforge_v13_rollback_rehearsal",
                        "status": "passed",
                        "migration_id": plan["migration_id"],
                        "no_changes": True,
                        "backup_verified": True,
                        "source_restored": True,
                    }
                )
            before = _source_rows(clone, plan["files"])
            applied = rehearsal.execute()
            rolled_back = rehearsal.migrator.rollback(str(applied["migration_id"]))
            after = _source_rows(clone, plan["files"])
            return _integrity_document(
                {
                    "schema_version": 1,
                    "package_type": "musicforge_v13_rollback_rehearsal",
                    "status": "passed" if before == after and rolled_back.get("backup_verified") else "failed",
                    "migration_id": plan["migration_id"],
                    "backup_verified": bool(rolled_back.get("backup_verified")),
                    "source_restored": before == after,
                }
            )

    def build_evidence_archive(
        self,
        plan: dict[str, Any],
        report: dict[str, Any],
        rollback: dict[str, Any],
        target: Path | str,
    ) -> tuple[Path, dict[str, Any]]:
        documents = {
            "migration-plan.json": _json_bytes(plan),
            "migration-report.json": _json_bytes(report),
            "rollback-rehearsal.json": _json_bytes(rollback),
            "README.txt": b"MusicForge v13 migration evidence. Paths are workspace-relative.\n",
        }
        manifest = {
            "schema_version": 1,
            "package_type": V13_MIGRATION_PACKAGE_TYPE,
            "migration_id": plan["migration_id"],
            "source_hash": plan["source_hash"],
            "files": [
                {"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)}
                for name, data in sorted(documents.items())
            ],
        }
        manifest["integrity_hash"] = integrity_hash(manifest)
        archive_path = Path(target)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        temp = archive_path.with_suffix(archive_path.suffix + ".tmp")
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", _json_bytes(manifest))
            for name, data in sorted(documents.items()):
                archive.writestr(name, data)
        temp.replace(archive_path)
        envelope = verify_package_envelope(archive_path, V13_MIGRATION_SPEC, strict=True)
        if envelope.get("status") != "passed":
            raise RuntimeError("V13 migration evidence verification failed.")
        anchor = _integrity_document(
            {
                "schema_version": 1,
                "package_type": V13_MIGRATION_ANCHOR_TYPE,
                "migration_id": plan["migration_id"],
                "source_hash": plan["source_hash"],
                "target_hash": report["target_hash"],
                "archive_sha256": sha256_file(archive_path),
                "archive_size_bytes": archive_path.stat().st_size,
                "manifest_hash": envelope.get("summary", {}).get("manifest_hash"),
                "created_at": _now(),
            }
        )
        anchor_path = migration_anchor_path(archive_path)
        anchor_path.write_text(json.dumps(anchor, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verification = verify_v13_migration_evidence(archive_path, anchor_path=anchor_path, require_anchor=True)
        if verification.get("status") != "passed":
            raise RuntimeError("V13 migration evidence anchor verification failed.")
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO migration_evidence_archives(migration_id, archive_sha256, verification_hash, created_at) VALUES (?, ?, ?, ?)",
                (plan["migration_id"], sha256_file(archive_path), verification["integrity_hash"], _now()),
            )
        return archive_path, verification


def migration_anchor_path(path: Path | str) -> Path:
    return Path(path).with_suffix(".anchor.json")


def verify_v13_migration_evidence(
    path: Path | str,
    *,
    anchor_path: Path | str | None = None,
    require_anchor: bool = False,
) -> dict[str, Any]:
    target = Path(path)
    envelope = verify_package_envelope(target, V13_MIGRATION_SPEC, strict=True)
    anchor_target = Path(anchor_path) if anchor_path is not None else migration_anchor_path(target)
    if not require_anchor and anchor_path is None and not anchor_target.is_file():
        return envelope
    checks = [*envelope.get("checks", []), *_migration_anchor_checks(target, anchor_target, envelope)]
    summary = dict(envelope.get("summary") or {})
    if anchor_target.is_file():
        try:
            value = json.loads(anchor_target.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                summary["anchor_hash"] = value.get("integrity_hash")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    return build_verification_report(
        package_type=V13_MIGRATION_VERIFICATION_TYPE,
        checks=checks,
        summary=summary,
    )


def _migration_semantic_checks(context: ImplementationDocument) -> list[ImplementationDocument]:
    archive = context["archive"]
    manifest = context["manifest"]
    try:
        plan = json.loads(archive.read("migration-plan.json"))
        report = json.loads(archive.read("migration-report.json"))
        rollback = json.loads(archive.read("rollback-rehearsal.json"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [build_check("v13_migration_documents_readable", False, "Migration documents are readable JSON.", {"error_type": type(exc).__name__})]
    if not all(isinstance(row, dict) for row in (plan, report, rollback)):
        return [build_check("v13_migration_documents_objects", False, "Migration documents are JSON objects.")]
    identifiers_match = bool(plan.get("migration_id")) and plan.get("migration_id") == report.get("migration_id") == rollback.get("migration_id") == manifest.get("migration_id")
    source_hashes_match = bool(plan.get("source_hash")) and plan.get("source_hash") == report.get("source_hash") == manifest.get("source_hash")
    context["summary"].update(
        {
            "migration_id": report.get("migration_id"),
            "source_hash": report.get("source_hash"),
            "target_hash": report.get("target_hash"),
        }
    )
    return [
        build_check("v13_migration_documents_integrity", all(integrity_ok(row) for row in (plan, report, rollback)), "Migration documents have valid integrity hashes."),
        build_check("v13_migration_identifiers_match", identifiers_match, "Plan, report, rollback, and manifest migration identities match."),
        build_check("v13_migration_source_hashes_match", source_hashes_match, "Plan, report, and manifest source hashes match."),
        build_check(
            "v13_migration_report_semantics",
            report.get("status") == "passed"
            and report.get("verified_backup") is True
            and report.get("source_preserved") is True
            and report.get("database_schema_version") == SCHEMA_VERSION
            and isinstance(report.get("target_hash"), str)
            and len(report["target_hash"]) == 64
            and bool(report.get("rollback_command")),
            "Migration report records a verified backup, preserved source, target hash, schema, and rollback command.",
        ),
        build_check(
            "v13_migration_rollback_semantics",
            rollback.get("status") == "passed" and rollback.get("backup_verified") is True and rollback.get("source_restored") is True,
            "Rollback rehearsal verified its backup and restored source state.",
        ),
    ]


def _migration_anchor_checks(
    archive_path: Path,
    anchor_path: Path,
    envelope: ImplementationDocument,
) -> list[ImplementationDocument]:
    exists = anchor_path.is_file()
    anchor: dict[str, Any] = {}
    readable = False
    if exists:
        try:
            value = json.loads(anchor_path.read_text(encoding="utf-8"))
            anchor = _as_document(value)
            readable = isinstance(value, dict)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            readable = False
    summary_value = envelope.get("summary")
    summary: dict[str, Any] = _as_document(summary_value)
    return [
        build_check("v13_migration_anchor_exists", exists, "External migration anchor exists."),
        build_check("v13_migration_anchor_readable", readable, "External migration anchor is a JSON object."),
        build_check("v13_migration_anchor_integrity", integrity_ok(anchor), "External migration anchor integrity is valid."),
        build_check("v13_migration_anchor_package_type", anchor.get("package_type") == V13_MIGRATION_ANCHOR_TYPE, "External migration anchor package type is valid."),
        build_check("v13_migration_anchor_migration_id", bool(summary.get("migration_id")) and anchor.get("migration_id") == summary.get("migration_id"), "External migration anchor binds the migration identity."),
        build_check("v13_migration_anchor_source_hash", bool(summary.get("source_hash")) and anchor.get("source_hash") == summary.get("source_hash"), "External migration anchor binds the source hash."),
        build_check("v13_migration_anchor_target_hash", bool(summary.get("target_hash")) and anchor.get("target_hash") == summary.get("target_hash"), "External migration anchor binds the target hash."),
        build_check("v13_migration_anchor_archive_hash", archive_path.is_file() and anchor.get("archive_sha256") == sha256_file(archive_path), "External migration anchor binds the archive bytes."),
        build_check("v13_migration_anchor_archive_size", archive_path.is_file() and anchor.get("archive_size_bytes") == archive_path.stat().st_size, "External migration anchor binds the archive size."),
        build_check("v13_migration_anchor_manifest_hash", bool(summary.get("manifest_hash")) and anchor.get("manifest_hash") == summary.get("manifest_hash"), "External migration anchor binds the manifest hash."),
    ]


def _database_state_hash(database: MusicForgeDatabase) -> str:
    with database.session() as connection:
        rows = connection.execute(
            "SELECT object_type, object_id, generation, status, version, payload_hash FROM workflow_objects ORDER BY object_type, object_id"
        ).fetchall()
    return integrity_hash(
        {
            "schema_version": database.schema_version(),
            "workflow_objects": [dict(row) for row in rows],
        }
    )


def _source_rows(root: Path, expected: list[ImplementationDocument]) -> list[ImplementationDocument]:
    rows = []
    for row in expected:
        relative = str(row["path"])
        path = root / relative
        if not path.is_file():
            return []
        rows.append({"path": relative, "sha256": sha256_path(path), "size_bytes": path.stat().st_size})
    return rows


def _integrity_document(document: ImplementationDocument) -> ImplementationDocument:
    result = dict(document)
    result["integrity_hash"] = integrity_hash(result)
    return result


def _json_bytes(document: ImplementationDocument) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat()
