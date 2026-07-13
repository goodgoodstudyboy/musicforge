from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator


SCHEMA_VERSION = 2


class MusicForgeDatabase:
    def __init__(self, path: Path | str, *, busy_timeout_ms: int = 30_000) -> None:
        self.path = Path(path)
        self.busy_timeout_ms = int(busy_timeout_ms)

    @classmethod
    def from_workspace(cls, workspace_root: Path | str) -> "MusicForgeDatabase":
        return cls(Path(workspace_root) / "state" / "musicforge.db")

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout_ms / 1000, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={self.busy_timeout_ms}")
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.transaction() as connection:
            statements = (
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS workflow_objects (
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    generation INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    payload_hash TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (object_type, object_id)
                )""",
                """CREATE TABLE IF NOT EXISTS id_counters (
                    namespace TEXT PRIMARY KEY,
                    next_value INTEGER NOT NULL
                )""",
                """CREATE TABLE IF NOT EXISTS artifact_transactions (
                    transaction_id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    status TEXT NOT NULL,
                    generation_path TEXT NOT NULL,
                    previous_generation TEXT NOT NULL DEFAULT '',
                    pointer_hash TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    committed_at TEXT NOT NULL DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS legacy_migrations (
                    migration_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    backup_path TEXT NOT NULL,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    rolled_back_at TEXT NOT NULL DEFAULT ''
                )""",
                """CREATE TABLE IF NOT EXISTS legacy_migration_files (
                    migration_id TEXT NOT NULL REFERENCES legacy_migrations(migration_id),
                    relative_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    PRIMARY KEY (migration_id, relative_path)
                )""",
                """CREATE TABLE IF NOT EXISTS legacy_migration_objects (
                    migration_id TEXT NOT NULL REFERENCES legacy_migrations(migration_id),
                    object_type TEXT NOT NULL,
                    object_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    PRIMARY KEY (migration_id, object_type, object_id)
                )""",
                """CREATE TABLE IF NOT EXISTS migration_evidence_archives (
                    migration_id TEXT PRIMARY KEY,
                    archive_sha256 TEXT NOT NULL,
                    verification_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""",
            )
            for statement in statements:
                connection.execute(statement)
            for version in range(1, SCHEMA_VERSION + 1):
                connection.execute(
                    "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, _now()),
                )
            connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def schema_version(self) -> int:
        with self.session() as connection:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _now() -> str:
    return datetime.now(UTC).isoformat()
