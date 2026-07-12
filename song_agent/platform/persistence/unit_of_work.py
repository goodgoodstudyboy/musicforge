from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from song_agent.platform.persistence.database import MusicForgeDatabase
from song_agent.platform.persistence.file_artifacts import FileArtifactStore, sha256_path, stable_tree_hash
from song_agent.platform.persistence.locks import WorkspaceLock


CrashHook = Callable[[str], None]


class FileUnitOfWork:
    def __init__(
        self,
        workspace_root: Path | str,
        namespace: str,
        *,
        database: MusicForgeDatabase | None = None,
        transaction_id: str | None = None,
        crash_hook: CrashHook | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.namespace = namespace
        self.database = database or MusicForgeDatabase.from_workspace(self.workspace_root)
        self.database.initialize()
        self.artifacts = FileArtifactStore(self.workspace_root)
        self.transaction_id = transaction_id or f"tx-{uuid.uuid4().hex}"
        self.crash_hook = crash_hook
        self._records: dict[str, dict[str, Any]] = {}

    def write_bytes(self, relative_path: str, data: bytes) -> dict[str, Any]:
        record = self.artifacts.write_staged(self.transaction_id, relative_path, data)
        self._records[str(record["path"])] = record
        return record

    def write_json(self, relative_path: str, value: dict[str, Any]) -> dict[str, Any]:
        record = self.artifacts.write_staged_json(self.transaction_id, relative_path, value)
        self._records[str(record["path"])] = record
        return record

    def commit(self) -> dict[str, Any]:
        lock = WorkspaceLock(self.workspace_root, operation=f"artifact-commit:{self.namespace}")
        with lock:
            staging = self.artifacts.staging_dir(self.transaction_id)
            records = sorted(self._records.values(), key=lambda row: str(row["path"]))
            if not records or not self.artifacts.verify_tree(staging, records):
                raise RuntimeError("Staged artifact fingerprints are incomplete or invalid.")
            previous = self.artifacts.read_pointer(self.namespace)
            intent = {
                "schema_version": 1,
                "transaction_id": self.transaction_id,
                "namespace": self.namespace,
                "status": "prepared",
                "created_at": _now(),
                "previous_generation": previous.get("generation_id") or "",
                "generation_id": self.transaction_id,
                "tree_hash": stable_tree_hash(records),
                "files": records,
            }
            intent_path = self.artifacts.intent_path(self.transaction_id)
            intent_path.parent.mkdir(parents=True, exist_ok=True)
            _write_json_atomic(intent_path, intent)
            self._crash("after_intent")

            generation = self.artifacts.generation_dir(self.namespace, self.transaction_id)
            if generation.exists():
                raise RuntimeError("Artifact generation already exists.")
            generation.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(generation)
            if not self.artifacts.verify_tree(generation, records):
                raise RuntimeError("Committed generation fingerprint mismatch.")
            self._crash("after_generation")

            pointer = {
                "schema_version": 1,
                "namespace": self.namespace,
                "generation_id": self.transaction_id,
                "tree_hash": intent["tree_hash"],
                "updated_at": _now(),
            }
            pointer_path = self.artifacts.write_pointer_atomic(self.namespace, pointer)
            pointer_hash = sha256_path(pointer_path)
            self._crash("after_pointer")

            with self.database.transaction() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO artifact_transactions(
                        transaction_id, namespace, status, generation_path,
                        previous_generation, pointer_hash, created_at, committed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self.transaction_id,
                        self.namespace,
                        "committed",
                        generation.relative_to(self.workspace_root).as_posix(),
                        intent["previous_generation"],
                        pointer_hash,
                        intent["created_at"],
                        _now(),
                    ),
                )
                self._crash("before_database_commit")
            self._crash("after_database_commit")

            marker = self.artifacts.marker_path(self.transaction_id)
            marker.write_text(json.dumps({"transaction_id": self.transaction_id, "pointer_hash": pointer_hash}, sort_keys=True) + "\n", encoding="utf-8")
            intent["status"] = "committed"
            intent["pointer_hash"] = pointer_hash
            intent["committed_at"] = _now()
            _write_json_atomic(intent_path, intent)
            self._crash("after_marker")
            return {
                "status": "committed",
                "transaction_id": self.transaction_id,
                "namespace": self.namespace,
                "generation_path": str(generation),
                "pointer_path": str(pointer_path),
                "tree_hash": intent["tree_hash"],
                "previous_generation": intent["previous_generation"],
            }

    def abort(self) -> None:
        transaction = self.artifacts.transaction_dir(self.transaction_id)
        if transaction.exists():
            shutil.rmtree(transaction)

    def _crash(self, stage: str) -> None:
        if self.crash_hook is not None:
            self.crash_hook(stage)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat()
