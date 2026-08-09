from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeAlias

from song_agent.platform.contracts import as_documents as _as_documents
from song_agent.platform.contracts.documents import (
    JsonDocument,
    is_json_document,
    normalize_json_document,
)
from song_agent.platform.persistence.database import MusicForgeDatabase, SCHEMA_VERSION
from song_agent.platform.persistence.file_artifacts import sha256_path, write_json_atomic
from song_agent.platform.persistence.locks import WorkspaceLock
from song_agent.platform.persistence.migrations import DEFAULT_LEGACY_ROOTS, LegacyWorkspaceMigrator
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok


V14_MIGRATION_PLAN_TYPE = "musicforge_v14_migration_plan"
V14_MIGRATION_INTENT_TYPE = "musicforge_v14_migration_intent"
V14_MIGRATION_REPORT_TYPE = "musicforge_v14_migration_report"
V14_MIGRATION_COMMIT_TYPE = "musicforge_v14_migration_commit_marker"
V14_MIGRATION_ROLLBACK_TYPE = "musicforge_v14_migration_rollback_rehearsal"
Document: TypeAlias = JsonDocument


class V14MigrationOrchestrator:
    """Adopt mutable legacy indexes without rewriting offline evidence artifacts."""

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.database = MusicForgeDatabase.from_workspace(self.workspace_root)
        self.migrator = LegacyWorkspaceMigrator(self.workspace_root, database=self.database)
        self.root = self.workspace_root / "state" / "migrations" / "v14"

    def plan(self) -> Document:
        legacy = self.migrator.dry_run()
        migration_id = f"v14-{str(legacy['source_hash'])[:16]}"
        source_rows = _source_rows(self.workspace_root, _as_documents(legacy.get("files")))
        immutable_rows = _immutable_rows(self.workspace_root, source_rows)
        pointers = _pointer_rows(self.workspace_root)
        return _integrity_document(
            {
                "schema_version": 1,
                "package_type": V14_MIGRATION_PLAN_TYPE,
                "migration_id": migration_id,
                "legacy_migration_id": legacy["migration_id"],
                "status": legacy["status"],
                "source_hash": legacy["source_hash"],
                "source_file_count": len(source_rows),
                "source_files": source_rows,
                "immutable_artifact_count": len(immutable_rows),
                "immutable_artifacts": immutable_rows,
                "current_pointers": pointers,
                "database_schema_version": SCHEMA_VERSION,
                "verified_backup_required": bool(source_rows),
                "signed_artifacts_read_only": True,
                "rollback_required": bool(source_rows),
            }
        )

    def apply(self) -> Document:
        plan = self.plan()
        migration_id = str(plan["migration_id"])
        directory = self.root / migration_id
        plan_path = directory / "migration-plan.json"
        intent_path = directory / "intent.json"
        report_path = directory / "migration-report.json"
        marker_path = directory / "commit-marker.json"
        with WorkspaceLock(self.workspace_root, operation=f"v14-migration:{migration_id}"):
            if marker_path.is_file():
                stored_plan = _read_document(plan_path)
                report = _read_document(report_path)
                marker = _read_document(marker_path)
                intent = _read_document(intent_path)
                try:
                    _require_committed_evidence(migration_id, stored_plan, intent, report, marker)
                    self._require_database_binding(stored_plan, report)
                except RuntimeError:
                    raise RuntimeError("V14 migration committed evidence is invalid.")
                return {**report, "status": "already_applied", "idempotent": True}
            if plan_path.exists() or intent_path.exists() or report_path.exists():
                raise RuntimeError("V14 migration has incomplete prior evidence; recover before retrying.")
            directory.mkdir(parents=True, exist_ok=True)
            write_json_atomic(plan_path, plan)
            before_state = _logical_state(self.workspace_root, self.database)
            intent = _integrity_document(
                {
                    "schema_version": 1,
                    "package_type": V14_MIGRATION_INTENT_TYPE,
                    "migration_id": migration_id,
                    "status": "prepared",
                    "plan_hash": plan["integrity_hash"],
                    "source_hash": plan["source_hash"],
                    "before_state_hash": before_state["integrity_hash"],
                    "prepared_at": _now(),
                }
            )
            write_json_atomic(intent_path, intent)
            applied = self.migrator.execute()
            plan_sources = _as_documents(plan.get("source_files"))
            plan_immutable = _as_documents(plan.get("immutable_artifacts"))
            plan_pointers = _as_documents(plan.get("current_pointers"))
            source_after = _source_rows(self.workspace_root, plan_sources)
            immutable_after = _immutable_rows(self.workspace_root, source_after)
            pointers_after = _pointer_rows(self.workspace_root)
            backup_verified = _backup_matches(self.workspace_root, applied, plan_sources)
            source_preserved = source_after == plan_sources
            immutable_preserved = immutable_after == plan_immutable
            pointers_preserved = pointers_after == plan_pointers
            schema_current = self.database.schema_version() == SCHEMA_VERSION
            after_state = _logical_state(self.workspace_root, self.database)
            passed = all(
                (backup_verified, source_preserved, immutable_preserved, pointers_preserved, schema_current)
            )
            report = _integrity_document(
                {
                    "schema_version": 1,
                    "package_type": V14_MIGRATION_REPORT_TYPE,
                    "migration_id": migration_id,
                    "legacy_migration_id": applied.get("migration_id"),
                    "status": "passed" if passed else "failed",
                    "plan_hash": plan["integrity_hash"],
                    "intent_hash": intent["integrity_hash"],
                    "source_hash": plan["source_hash"],
                    "before_state_hash": before_state["integrity_hash"],
                    "after_state_hash": after_state["integrity_hash"],
                    "verified_backup": backup_verified,
                    "source_preserved": source_preserved,
                    "immutable_artifacts_preserved": immutable_preserved,
                    "current_pointers_preserved": pointers_preserved,
                    "database_schema_version": self.database.schema_version(),
                    "backup_path": str(applied.get("backup_path") or ""),
                    "applied_at": _now(),
                }
            )
            write_json_atomic(report_path, report)
            if not passed:
                raise RuntimeError("V14 migration post-apply verification failed.")
            marker = _integrity_document(
                {
                    "schema_version": 1,
                    "package_type": V14_MIGRATION_COMMIT_TYPE,
                    "migration_id": migration_id,
                    "status": "committed",
                    "plan_hash": plan["integrity_hash"],
                    "intent_hash": intent["integrity_hash"],
                    "report_hash": report["integrity_hash"],
                    "source_hash": plan["source_hash"],
                    "committed_at": _now(),
                }
            )
            write_json_atomic(marker_path, marker)
            return {**report, "commit_marker_hash": marker["integrity_hash"], "idempotent": False}

    def rollback(self, migration_id: str) -> Document:
        directory = self.root / migration_id
        plan = _read_document(directory / "migration-plan.json")
        intent = _read_document(directory / "intent.json")
        report = _read_document(directory / "migration-report.json")
        marker = _read_document(directory / "commit-marker.json")
        _require_committed_evidence(migration_id, plan, intent, report, marker)
        self._require_database_binding(plan, report)
        before = _logical_state(self.workspace_root, self.database)
        result = self.migrator.rollback(str(report["legacy_migration_id"]))
        after = _logical_state(self.workspace_root, self.database)
        expected_sources = _as_documents(self.plan().get("source_files"))
        source_rows = _source_rows(self.workspace_root, expected_sources)
        source_preserved = bool(source_rows) and source_rows == expected_sources
        rollback = _integrity_document(
            {
                "schema_version": 1,
                "package_type": "musicforge_v14_migration_rollback",
                "migration_id": migration_id,
                "status": "rolled_back",
                "source_preserved": source_preserved,
                "backup_verified": result.get("backup_verified") is True,
                "before_rollback_state_hash": before["integrity_hash"],
                "after_rollback_state_hash": after["integrity_hash"],
                "rolled_back_at": _now(),
            }
        )
        write_json_atomic(directory / "rollback-marker.json", rollback)
        return rollback

    def _require_database_binding(self, plan: Document, report: Document) -> None:
        with self.database.session() as connection:
            row = connection.execute(
                "SELECT migration_id, status, source_hash, backup_path FROM legacy_migrations WHERE migration_id=?",
                (str(plan.get("legacy_migration_id") or ""),),
            ).fetchone()
        if row is None:
            raise RuntimeError("V14 migration ledger entry is missing.")
        if (
            str(row["source_hash"]) != str(plan.get("source_hash") or "")
            or str(row["backup_path"]) != str(report.get("backup_path") or "")
            or str(report.get("legacy_migration_id") or "") != str(row["migration_id"])
            or str(row["status"]) != "applied"
        ):
            raise RuntimeError("V14 migration ledger binding failed.")

    def rollback_rehearsal(self) -> Document:
        with tempfile.TemporaryDirectory(prefix="musicforge-v14-rollback-") as temp:
            clone = Path(temp) / ".musicforge"
            _copy_rehearsal_input(self.workspace_root, clone)
            if not any((clone / name).is_dir() for name in DEFAULT_LEGACY_ROOTS):
                _write_representative_workspace(clone)
            rehearsal = V14MigrationOrchestrator(clone)
            plan = rehearsal.plan()
            before = _logical_state(clone, rehearsal.database)
            source_before = _as_documents(plan.get("source_files"))
            immutable_before = _as_documents(plan.get("immutable_artifacts"))
            pointers_before = _as_documents(plan.get("current_pointers"))
            applied = rehearsal.apply()
            rolled_back = rehearsal.rollback(str(plan["migration_id"]))
            source_after = _source_rows(clone, source_before)
            immutable_after = _immutable_rows(clone, source_after)
            pointers_after = _pointer_rows(clone)
            after = _logical_state(clone, rehearsal.database)
            logical_identical = before["integrity_hash"] == after["integrity_hash"]
            byte_identical = source_before == source_after
            immutable_identical = immutable_before == immutable_after
            pointers_identical = pointers_before == pointers_after
            passed = all(
                (
                    applied.get("status") == "passed",
                    rolled_back.get("status") == "rolled_back",
                    rolled_back.get("backup_verified") is True,
                    logical_identical,
                    byte_identical,
                    immutable_identical,
                    pointers_identical,
                )
            )
            return _integrity_document(
                {
                    "schema_version": 1,
                    "package_type": V14_MIGRATION_ROLLBACK_TYPE,
                    "status": "passed" if passed else "failed",
                    "migration_id": plan["migration_id"],
                    "file_count": plan["source_file_count"],
                    "verified_backup": rolled_back.get("backup_verified") is True,
                    "byte_identical": byte_identical,
                    "immutable_artifacts_identical": immutable_identical,
                    "current_pointers_identical": pointers_identical,
                    "logical_state_identical": logical_identical,
                    "before_state_hash": before["integrity_hash"],
                    "after_state_hash": after["integrity_hash"],
                }
            )


def _require_committed_evidence(
    migration_id: str,
    plan: Document,
    intent: Document,
    report: Document,
    marker: Document,
) -> None:
    if not all(integrity_ok(value) for value in (plan, intent, report, marker)):
        raise RuntimeError("V14 migration evidence integrity failed.")
    if not all(value.get("migration_id") == migration_id for value in (plan, intent, report, marker)):
        raise RuntimeError("V14 migration evidence identity mismatch.")
    plan_hash = plan.get("integrity_hash")
    if not all(value.get("plan_hash") == plan_hash for value in (intent, report, marker)):
        raise RuntimeError("V14 migration plan binding failed.")
    if not all(value.get("source_hash") == plan.get("source_hash") for value in (intent, report, marker)):
        raise RuntimeError("V14 migration source binding failed.")
    if report.get("legacy_migration_id") != plan.get("legacy_migration_id"):
        raise RuntimeError("V14 legacy migration identity binding failed.")
    if marker.get("intent_hash") != intent.get("integrity_hash"):
        raise RuntimeError("V14 migration intent binding failed.")
    if marker.get("report_hash") != report.get("integrity_hash"):
        raise RuntimeError("V14 migration report binding failed.")
    if marker.get("status") != "committed" or report.get("status") != "passed":
        raise RuntimeError("V14 migration is not committed.")


def _source_rows(root: Path, expected: list[Document]) -> list[Document]:
    rows: list[Document] = []
    for row in expected:
        relative = str(row["path"])
        path = root / relative
        if not path.is_file():
            return []
        rows.append({"path": relative, "sha256": sha256_path(path), "size_bytes": path.stat().st_size})
    return rows


def _immutable_rows(root: Path, source_rows: list[Document]) -> list[Document]:
    immutable: list[Document] = []
    for row in source_rows:
        relative = str(row["path"])
        name = Path(relative).name.lower()
        if Path(relative).suffix.lower() in {".zip", ".jsonl"} or any(
            token in name for token in ("signoff", "binding", "anchor", "checkpoint")
        ):
            immutable.append(dict(row))
    return immutable


def _pointer_rows(root: Path) -> list[Document]:
    state = root / "state" / "current"
    if not state.is_dir():
        return []
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": sha256_path(path), "size_bytes": path.stat().st_size}
        for path in sorted(state.rglob("*"))
        if path.is_file() and not path.is_symlink()
    ]


def _backup_matches(
    root: Path,
    applied: Document,
    source_rows: list[Document],
) -> bool:
    if not source_rows:
        return applied.get("status") in {"no_changes", "already_applied"}
    backup_value = str(applied.get("backup_path") or "")
    if not backup_value:
        return False
    backup = root / backup_value
    return _source_rows(backup, source_rows) == source_rows


def _logical_state(root: Path, database: MusicForgeDatabase) -> Document:
    database.initialize()
    with database.session() as connection:
        workflows = [
            dict(row)
            for row in connection.execute(
                "SELECT object_type, object_id, generation, status, version, payload_hash "
                "FROM workflow_objects ORDER BY object_type, object_id"
            ).fetchall()
        ]
        program = [
            dict(row)
            for row in connection.execute(
                "SELECT relative_path, program_id, component_type, generation, status, version, "
                "payload_hash, projection_sha256 FROM program_documents ORDER BY relative_path"
            ).fetchall()
        ]
    sources: list[Document] = []
    for legacy_root in DEFAULT_LEGACY_ROOTS:
        directory = root / legacy_root
        if directory.is_dir():
            sources.extend(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_path(path),
                    "size_bytes": path.stat().st_size,
                }
                for path in sorted(directory.rglob("*"))
                if path.is_file() and not path.is_symlink()
            )
    return _integrity_document(
        {
            "schema_version": SCHEMA_VERSION,
            "source_files": sources,
            "current_pointers": _pointer_rows(root),
            "workflow_objects": workflows,
            "program_documents": program,
        }
    )


def _copy_rehearsal_input(source_root: Path, target_root: Path) -> None:
    for name in DEFAULT_LEGACY_ROOTS:
        source = source_root / name
        if source.is_dir():
            shutil.copytree(source, target_root / name)
    pointers = source_root / "state" / "current"
    if pointers.is_dir():
        shutil.copytree(pointers, target_root / "state" / "current")


def _write_representative_workspace(root: Path) -> None:
    program = root / "unified-release-programs" / "migration-sample"
    program.mkdir(parents=True, exist_ok=True)
    (program / "program.json").write_text(
        '{"component_type":"unified_release_program","generation":2,"program_id":"migration-sample","status":"ready"}\n',
        encoding="utf-8",
    )
    (program / "program-signoff.json").write_text(
        '{"integrity_hash":"sample-signoff","signed_by":"release-owner","status":"signed"}\n',
        encoding="utf-8",
    )
    (program / "program-signoff-history.jsonl").write_text(
        '{"event_hash":"sample-event","event_type":"signed"}\n', encoding="utf-8"
    )
    pointer = root / "state" / "current" / "program.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text('{"generation_id":"generation-000002"}\n', encoding="utf-8")


def _read_document(path: Path) -> Document:
    if not path.is_file():
        raise RuntimeError(f"V14 migration evidence is missing: {path.name}")
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"V14 migration evidence is unreadable: {path.name}") from exc
    if not is_json_document(value):
        raise RuntimeError(f"V14 migration evidence is not an object: {path.name}")
    return value


def _integrity_document(document: Mapping[str, object]) -> Document:
    result = normalize_json_document(document)
    result["integrity_hash"] = integrity_hash(result)
    return result


def _now() -> str:
    return datetime.now(UTC).isoformat()
