from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from song_agent.platform.persistence.database import MusicForgeDatabase, SCHEMA_VERSION
from song_agent.platform.persistence.file_artifacts import sha256_path, stable_tree_hash
from song_agent.platform.persistence.locks import WorkspaceLock
from song_agent.platform.persistence.program import ProgramStateRepository
from song_agent.platform.persistence.repository import collect_active_v12_state


DEFAULT_LEGACY_ROOTS = ("unified-release-programs", "urpccca")


class LegacyWorkspaceMigrator:
    def __init__(
        self,
        workspace_root: Path | str,
        *,
        database: MusicForgeDatabase | None = None,
        legacy_roots: Iterable[str] = DEFAULT_LEGACY_ROOTS,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.database = database or MusicForgeDatabase.from_workspace(self.workspace_root)
        self.database.initialize()
        self.legacy_roots = tuple(_safe_legacy_root(value) for value in legacy_roots)
        self.migration_root = self.workspace_root / "state" / "migrations"

    def dry_run(self) -> DomainDocument:
        files = self._source_files()
        source_hash = stable_tree_hash(files)
        migration_id = f"legacy-{source_hash[:16]}"
        existing = self._existing(migration_id)
        return {
            "schema_version": 1,
            "package_type": "musicforge_legacy_workspace_migration_plan",
            "migration_id": migration_id,
            "status": "no_changes" if not files else ("already_applied" if existing and existing["status"] == "applied" else "planned"),
            "database_schema_version": SCHEMA_VERSION,
            "source_hash": source_hash,
            "file_count": len(files),
            "total_size_bytes": sum(int(row["size_bytes"]) for row in files),
            "files": files,
            "source_preserved": True,
            "backup_required": True,
        }

    def execute(self, *, fail_after_backup: bool = False) -> DomainDocument:
        plan = self.dry_run()
        migration_id = str(plan["migration_id"])
        if plan["status"] == "no_changes":
            return {**plan, "idempotent": True}
        if plan["status"] == "already_applied":
            return {**plan, "status": "already_applied", "idempotent": True}
        with WorkspaceLock(self.workspace_root, operation=f"legacy-migration:{migration_id}"):
            plan = self.dry_run()
            if plan["status"] == "already_applied":
                return {**plan, "status": "already_applied", "idempotent": True}
            backup = self.migration_root / "backups" / migration_id
            if backup.exists():
                raise RuntimeError("Legacy migration backup already exists without a committed migration.")
            for row in plan["files"]:
                source = self.workspace_root / str(row["path"])
                target = backup / str(row["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            backup_rows = _fingerprint_paths(backup, [str(row["path"]) for row in plan["files"]])
            if backup_rows != plan["files"]:
                raise RuntimeError("Legacy migration backup verification failed.")
            if fail_after_backup:
                raise RuntimeError("Injected migration failure after verified backup.")
            created_at = _now()
            workflow_rows = collect_active_v12_state(backup)
            program_documents = _program_documents(backup, plan["files"])
            imported_workflow_count = 0
            imported_program_document_count = 0
            program_repository = ProgramStateRepository(self.workspace_root, database=self.database)
            with self.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO legacy_migrations(migration_id, status, source_hash, backup_path, schema_version, created_at) VALUES (?, 'applied', ?, ?, ?, ?)",
                    (migration_id, plan["source_hash"], backup.relative_to(self.workspace_root).as_posix(), SCHEMA_VERSION, created_at),
                )
                connection.executemany(
                    "INSERT INTO legacy_migration_files(migration_id, relative_path, sha256, size_bytes) VALUES (?, ?, ?, ?)",
                    [(migration_id, row["path"], row["sha256"], row["size_bytes"]) for row in plan["files"]],
                )
                for relative_path, document, payload in program_documents:
                    if program_repository.adopt_legacy_document(
                        connection,
                        relative_path,
                        document,
                        payload,
                        migration_id=migration_id,
                    ):
                        imported_program_document_count += 1
                for row in workflow_rows:
                    inserted = connection.execute(
                        """
                        INSERT INTO workflow_objects(object_type, object_id, generation, status, version, payload_hash, updated_at)
                        VALUES (?, ?, ?, ?, 1, ?, ?)
                        ON CONFLICT(object_type, object_id) DO NOTHING
                        """,
                        (row["object_type"], row["object_id"], row["generation"], row["status"], row["payload_hash"], created_at),
                    )
                    if inserted.rowcount == 1:
                        imported_workflow_count += 1
                        connection.execute(
                            "INSERT INTO legacy_migration_objects(migration_id, object_type, object_id, payload_hash) VALUES (?, ?, ?, ?)",
                            (migration_id, row["object_type"], row["object_id"], row["payload_hash"]),
                        )
            report = {
                **plan,
                "package_type": "musicforge_legacy_workspace_migration_report",
                "status": "applied",
                "applied_at": created_at,
                "backup_path": backup.relative_to(self.workspace_root).as_posix(),
                "rollback_command": f"song-agent-state migrate-rollback {migration_id}",
                "idempotent": False,
                "imported_workflow_count": imported_workflow_count,
                "imported_program_document_count": imported_program_document_count,
            }
            report_path = self.migration_root / "reports" / f"{migration_id}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return report

    def rollback(self, migration_id: str) -> DomainDocument:
        with WorkspaceLock(self.workspace_root, operation=f"legacy-migration-rollback:{migration_id}"):
            existing = self._existing(migration_id)
            if not existing:
                raise RuntimeError("Legacy migration was not found.")
            if existing["status"] == "rolled_back":
                return {"migration_id": migration_id, "status": "already_rolled_back", "idempotent": True}
            backup = self.workspace_root / str(existing["backup_path"])
            if not backup.is_dir():
                raise RuntimeError("Legacy migration rollback backup is missing.")
            rows = self._migration_files(migration_id)
            backup_rows = _fingerprint_paths(backup, [str(row["path"]) for row in rows])
            if backup_rows != rows:
                raise RuntimeError("Legacy migration rollback backup verification failed.")
            rolled_back_at = _now()
            with self.database.transaction() as connection:
                program_documents = connection.execute(
                    "SELECT relative_path, payload_hash FROM legacy_migration_program_documents WHERE migration_id=?",
                    (migration_id,),
                ).fetchall()
                for row in program_documents:
                    current = connection.execute(
                        "SELECT version, payload_hash FROM program_documents WHERE relative_path=?",
                        (row["relative_path"],),
                    ).fetchone()
                    if (
                        current is None
                        or int(current["version"]) != 1
                        or str(current["payload_hash"]) != str(row["payload_hash"])
                    ):
                        raise RuntimeError(
                            f"Migrated Program document changed after import: {row['relative_path']}"
                        )
                    connection.execute(
                        "DELETE FROM program_documents WHERE relative_path=?",
                        (row["relative_path"],),
                    )
                imported = connection.execute(
                    "SELECT object_type, object_id, payload_hash FROM legacy_migration_objects WHERE migration_id=?",
                    (migration_id,),
                ).fetchall()
                for row in imported:
                    connection.execute(
                        "DELETE FROM workflow_objects WHERE object_type=? AND object_id=? AND version=1 AND payload_hash=?",
                        (row["object_type"], row["object_id"], row["payload_hash"]),
                    )
                connection.execute(
                    "UPDATE legacy_migrations SET status='rolled_back', rolled_back_at=? WHERE migration_id=?",
                    (rolled_back_at, migration_id),
                )
            return {
                "migration_id": migration_id,
                "status": "rolled_back",
                "rolled_back_at": rolled_back_at,
                "source_files_preserved": True,
                "backup_verified": True,
            }

    def _source_files(self) -> list[ImplementationDocument]:
        paths: list[Path] = []
        for relative_root in self.legacy_roots:
            root = self.workspace_root / relative_root
            if not root.is_dir():
                continue
            paths.extend(
                path
                for path in root.rglob("*")
                if path.is_file()
                and not path.is_symlink()
                and path.resolve().is_relative_to(self.workspace_root)
                and path.suffix.lower() in {".json", ".jsonl"}
            )
        rows = []
        for path in sorted(set(paths)):
            relative = path.relative_to(self.workspace_root).as_posix()
            rows.append({"path": relative, "sha256": sha256_path(path), "size_bytes": path.stat().st_size})
        return rows

    def _existing(self, migration_id: str) -> ImplementationDocument:
        with self.database.session() as connection:
            row = connection.execute("SELECT * FROM legacy_migrations WHERE migration_id=?", (migration_id,)).fetchone()
        return dict(row) if row else {}

    def _migration_files(self, migration_id: str) -> list[ImplementationDocument]:
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT relative_path, sha256, size_bytes FROM legacy_migration_files WHERE migration_id=? ORDER BY relative_path",
                (migration_id,),
            ).fetchall()
        return [{"path": str(row["relative_path"]), "sha256": str(row["sha256"]), "size_bytes": int(row["size_bytes"])} for row in rows]


def _fingerprint_paths(root: Path, relative_paths: list[str]) -> list[ImplementationDocument]:
    rows = []
    for relative in sorted(relative_paths):
        path = root / relative
        if not path.is_file():
            return []
        rows.append({"path": relative, "sha256": sha256_path(path), "size_bytes": path.stat().st_size})
    return rows


def _program_documents(
    root: Path,
    rows: list[ImplementationDocument],
) -> list[tuple[str, ImplementationDocument, bytes]]:
    documents: list[tuple[str, ImplementationDocument, bytes]] = []
    for row in rows:
        relative = str(row["path"])
        parts = Path(relative.replace("\\", "/")).parts
        if (
            not parts
            or parts[0].lower() not in {"unified-release-programs", "urpccca"}
            or not relative.lower().endswith(".json")
        ):
            continue
        payload = (root / relative).read_bytes()
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Legacy Program JSON is unreadable: {relative}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"Legacy Program JSON is not an object: {relative}")
        documents.append((relative, value, payload))
    return documents


def migration_source_id(rows: list[DomainDocument]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_legacy_root(value: str) -> str:
    path = Path(value.replace("\\", "/"))
    if not value or path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ValueError("Legacy migration roots must be direct workspace children.")
    return path.as_posix()
