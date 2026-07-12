from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from song_agent.platform.persistence.database import MusicForgeDatabase
from song_agent.platform.verification.hashing import integrity_ok


@dataclass(frozen=True)
class WorkflowRecord:
    object_type: str
    object_id: str
    generation: int
    status: str
    version: int
    payload_hash: str
    updated_at: str


class WorkflowRepository:
    def __init__(self, database: MusicForgeDatabase) -> None:
        self.database = database
        self.database.initialize()

    def get(self, object_type: str, object_id: str) -> WorkflowRecord | None:
        with self.database.session() as connection:
            row = connection.execute(
                "SELECT * FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
        return _record(row) if row else None

    def save(
        self,
        object_type: str,
        object_id: str,
        *,
        generation: int,
        status: str,
        payload_hash: str = "",
        expected_version: int | None = None,
    ) -> WorkflowRecord:
        with self.database.transaction() as connection:
            current = connection.execute(
                "SELECT version FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
            current_version = int(current[0]) if current else 0
            if expected_version is not None and current_version != expected_version:
                raise RuntimeError("Workflow record changed concurrently.")
            version = current_version + 1
            connection.execute(
                """
                INSERT INTO workflow_objects(object_type, object_id, generation, status, version, payload_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(object_type, object_id) DO UPDATE SET
                    generation=excluded.generation,
                    status=excluded.status,
                    version=excluded.version,
                    payload_hash=excluded.payload_hash,
                    updated_at=excluded.updated_at
                """,
                (object_type, object_id, int(generation), status, version, payload_hash, _now()),
            )
            row = connection.execute(
                "SELECT * FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
        return _record(row)

    def next_id(self, namespace: str, *, prefix: str) -> str:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT next_value FROM id_counters WHERE namespace=?", (namespace,)).fetchone()
            value = int(row[0]) if row else 1
            connection.execute(
                "INSERT INTO id_counters(namespace, next_value) VALUES (?, ?) ON CONFLICT(namespace) DO UPDATE SET next_value=excluded.next_value",
                (namespace, value + 1),
            )
        return f"{prefix}{value:06d}"


def _record(row: sqlite3.Row) -> WorkflowRecord:
    return WorkflowRecord(
        object_type=str(row["object_type"]),
        object_id=str(row["object_id"]),
        generation=int(row["generation"]),
        status=str(row["status"]),
        version=int(row["version"]),
        payload_hash=str(row["payload_hash"]),
        updated_at=str(row["updated_at"]),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def sync_active_v12_state(workspace_root: Path | str) -> int:
    root = Path(workspace_root)
    rows = collect_active_v12_state(root)
    if not rows:
        return 0
    database = MusicForgeDatabase.from_workspace(root)
    database.initialize()
    with database.transaction() as connection:
        for row in rows:
            object_type = str(row["object_type"])
            object_id = str(row["object_id"])
            current = connection.execute(
                "SELECT version FROM workflow_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
            version = int(current[0]) + 1 if current else 1
            connection.execute(
                """
                INSERT INTO workflow_objects(object_type, object_id, generation, status, version, payload_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(object_type, object_id) DO UPDATE SET
                    generation=excluded.generation,
                    status=excluded.status,
                    version=excluded.version,
                    payload_hash=excluded.payload_hash,
                    updated_at=excluded.updated_at
                """,
                (object_type, object_id, row["generation"], row["status"], version, row["payload_hash"], _now()),
            )
    return len(rows)


def collect_active_v12_state(workspace_root: Path | str) -> list[dict[str, object]]:
    root = Path(workspace_root)
    candidates = [
        *root.glob("unified-release-programs/*/continuity-command-center/command-center-report.json"),
        *root.glob("unified-release-programs/*/continuity-command-center/signoff/command-center-signoff-state.json"),
        *root.glob("urpccca/*/signoff/receiver-acceptance-state.json"),
        *root.glob("urpccca/*/change-control/current-generation.json"),
    ]
    rows: list[dict[str, object]] = []
    for path in sorted(set(candidates)):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Mutable workflow index source is unreadable: {path.name}") from exc
        if not isinstance(document, dict):
            raise RuntimeError(f"Mutable workflow index source is not an object: {path.name}")
        if not integrity_ok(document):
            raise RuntimeError(f"Mutable workflow index source integrity failed: {path.name}")
        program_id = str(document.get("program_id") or path.parts[-3])
        if path.name == "command-center-report.json":
            object_type = "continuity_command_center"
        elif path.name == "command-center-signoff-state.json":
            object_type = "continuity_command_center_signoff"
        elif path.name == "receiver-acceptance-state.json":
            object_type = "receiver_acceptance"
        else:
            object_type = "receiver_acceptance_change"
        rows.append(
            {
                "object_type": object_type,
                "object_id": program_id,
                "generation": int(document.get("generation") or 1),
                "status": str(document.get("status") or "unknown"),
                "payload_hash": str(document.get("integrity_hash") or ""),
            }
        )
    return rows
