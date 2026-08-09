from __future__ import annotations

from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document

import json
import os
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence

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
        self._records: dict[str, JsonDocument] = {}

    def write_bytes(self, relative_path: str, data: bytes) -> JsonDocument:
        record = self.artifacts.write_staged(self.transaction_id, relative_path, data)
        self._records[str(record["path"])] = record
        return record

    def write_json(self, relative_path: str, value: Mapping[str, object]) -> JsonDocument:
        record = self.artifacts.write_staged_json(self.transaction_id, relative_path, value)
        self._records[str(record["path"])] = record
        return record

    def commit(self) -> JsonDocument:
        lock = WorkspaceLock(self.workspace_root, operation=f"artifact-commit:{self.namespace}")
        with lock:
            staging = self.artifacts.staging_dir(self.transaction_id)
            records = sorted(self._records.values(), key=lambda row: str(row["path"]))
            if not records or not self.artifacts.verify_tree(staging, records):
                raise RuntimeError("Staged artifact fingerprints are incomplete or invalid.")
            intent, intent_path = self._prepare_intent(records)
            self._crash("after_intent")
            generation = self._commit_generation(staging, records)
            self._crash("after_generation")
            pointer_path = self._write_pointer(intent)
            pointer_hash = sha256_path(pointer_path)
            self._crash("after_pointer")
            self._record_commit(generation, intent, pointer_hash)
            self._crash("after_database_commit")
            self._finalize_intent(intent, intent_path, pointer_hash)
            self._crash("after_marker")
            return normalize_json_document({
                "status": "committed",
                "transaction_id": self.transaction_id,
                "namespace": self.namespace,
                "generation_path": str(generation),
                "pointer_path": str(pointer_path),
                "tree_hash": intent["tree_hash"],
                "previous_generation": intent["previous_generation"],
            })

    def _prepare_intent(self, records: Sequence[Mapping[str, object]]) -> tuple[JsonDocument, Path]:
        previous = self.artifacts.read_pointer(self.namespace)
        intent = normalize_json_document({
            "schema_version": 1,
            "transaction_id": self.transaction_id,
            "namespace": self.namespace,
            "status": "prepared",
            "created_at": _now(),
            "previous_generation": previous.get("generation_id") or "",
            "generation_id": self.transaction_id,
            "tree_hash": stable_tree_hash(records),
            "files": records,
        })
        path = self.artifacts.intent_path(self.transaction_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(path, intent)
        return intent, path

    def _commit_generation(self, staging: Path, records: Sequence[Mapping[str, object]]) -> Path:
        generation = self.artifacts.generation_dir(self.namespace, self.transaction_id)
        if generation.exists():
            raise RuntimeError("Artifact generation already exists.")
        generation.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(generation)
        if not self.artifacts.verify_tree(generation, records):
            raise RuntimeError("Committed generation fingerprint mismatch.")
        return generation

    def _write_pointer(self, intent: JsonDocument) -> Path:
        return self.artifacts.write_pointer_atomic(self.namespace, {
            "schema_version": 1,
            "namespace": self.namespace,
            "generation_id": self.transaction_id,
            "tree_hash": intent["tree_hash"],
            "updated_at": _now(),
        })

    def _record_commit(self, generation: Path, intent: JsonDocument, pointer_hash: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO artifact_transactions(
                    transaction_id, namespace, status, generation_path,
                    previous_generation, pointer_hash, created_at, committed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.transaction_id, self.namespace, "committed",
                    generation.relative_to(self.workspace_root).as_posix(),
                    intent["previous_generation"], pointer_hash, intent["created_at"], _now(),
                ),
            )
            self._crash("before_database_commit")

    def _finalize_intent(self, intent: JsonDocument, path: Path, pointer_hash: str) -> None:
        marker = self.artifacts.marker_path(self.transaction_id)
        marker.write_text(json.dumps({"transaction_id": self.transaction_id, "pointer_hash": pointer_hash}, sort_keys=True) + "\n", encoding="utf-8")
        intent.update({"status": "committed", "pointer_hash": pointer_hash, "committed_at": _now()})
        _write_json_atomic(path, intent)

    def abort(self) -> None:
        transaction = self.artifacts.transaction_dir(self.transaction_id)
        if transaction.exists():
            shutil.rmtree(transaction)

    def _crash(self, stage: str) -> None:
        if self.crash_hook is not None:
            self.crash_hook(stage)


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat()
