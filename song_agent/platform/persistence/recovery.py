from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from song_agent.platform.persistence.database import MusicForgeDatabase
from song_agent.platform.persistence.file_artifacts import FileArtifactStore, sha256_path
from song_agent.platform.persistence.locks import WorkspaceLock


class PersistenceRecovery:
    def __init__(self, workspace_root: Path | str, *, database: MusicForgeDatabase | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.database = database or MusicForgeDatabase.from_workspace(self.workspace_root)
        self.database.initialize()
        self.artifacts = FileArtifactStore(self.workspace_root)

    def inspect(self) -> list[dict[str, Any]]:
        if not self.artifacts.transactions_root.exists():
            return []
        rows = []
        for intent_path in sorted(self.artifacts.transactions_root.glob("*/intent.json")):
            try:
                intent = json.loads(intent_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Recovery intent is unreadable: {intent_path.name}.") from exc
            if not isinstance(intent, dict):
                raise RuntimeError(f"Recovery intent must be a JSON object: {intent_path.name}.")
            marker = intent_path.parent / "commit.marker"
            if not marker.exists() or intent.get("status") != "committed":
                rows.append(intent)
        return rows

    def recover(self) -> dict[str, Any]:
        recovered: list[str] = []
        rolled_back: list[str] = []
        with WorkspaceLock(self.workspace_root, operation="persistence-recovery"):
            for intent in self.inspect():
                transaction_id = str(intent.get("transaction_id") or "")
                namespace = str(intent.get("namespace") or "")
                generation = self.artifacts.generation_dir(namespace, transaction_id)
                pointer = self.artifacts.read_pointer(namespace)
                raw_files = intent.get("files")
                if not isinstance(raw_files, list) or not raw_files or not all(isinstance(row, dict) for row in raw_files):
                    raise RuntimeError(f"Recovery file ledger is invalid for transaction {transaction_id}.")
                files: list[dict[str, Any]] = raw_files
                if generation.exists():
                    if not self.artifacts.verify_tree(generation, files):
                        raise RuntimeError(f"Recovery integrity failure for transaction {transaction_id}.")
                    if pointer.get("generation_id") != transaction_id:
                        if str(pointer.get("generation_id") or "") != str(intent.get("previous_generation") or ""):
                            raise RuntimeError(f"Recovery pointer mismatch for transaction {transaction_id}.")
                        self.artifacts.write_pointer_atomic(
                            namespace,
                            {"schema_version": 1, "namespace": namespace, "generation_id": transaction_id, "tree_hash": intent.get("tree_hash"), "updated_at": _now()},
                        )
                        pointer = self.artifacts.read_pointer(namespace)
                    if pointer.get("tree_hash") != intent.get("tree_hash"):
                        raise RuntimeError(f"Recovery pointer fingerprint mismatch for transaction {transaction_id}.")
                    pointer_hash = sha256_path(self.artifacts.current_pointer_path(namespace))
                    self._record_committed(intent, generation, pointer_hash)
                    marker = self.artifacts.marker_path(transaction_id)
                    marker.write_text(json.dumps({"transaction_id": transaction_id, "pointer_hash": pointer_hash}, sort_keys=True) + "\n", encoding="utf-8")
                    intent["status"] = "committed"
                    intent["pointer_hash"] = pointer_hash
                    intent["committed_at"] = _now()
                    self.artifacts.intent_path(transaction_id).write_text(json.dumps(intent, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    recovered.append(transaction_id)
                    continue
                previous = str(intent.get("previous_generation") or "")
                if pointer.get("generation_id") == transaction_id:
                    if previous:
                        previous_dir = self.artifacts.generation_dir(namespace, previous)
                        if not previous_dir.is_dir():
                            raise RuntimeError(f"Recovery previous generation is missing for {transaction_id}.")
                        previous_rows = self.artifacts.fingerprint_tree(previous_dir)
                        self.artifacts.write_pointer_atomic(
                            namespace,
                            {"schema_version": 1, "namespace": namespace, "generation_id": previous, "tree_hash": _tree_hash(previous_rows), "updated_at": _now()},
                        )
                    else:
                        self.artifacts.current_pointer_path(namespace).unlink(missing_ok=True)
                intent["status"] = "rolled_back"
                intent["rolled_back_at"] = _now()
                self.artifacts.intent_path(transaction_id).write_text(json.dumps(intent, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                staging = self.artifacts.staging_dir(transaction_id)
                if staging.exists():
                    import shutil

                    shutil.rmtree(staging)
                rolled_back.append(transaction_id)
        return {"status": "passed", "recovered": recovered, "rolled_back": rolled_back}

    def _record_committed(self, intent: dict[str, Any], generation: Path, pointer_hash: str) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO artifact_transactions(
                    transaction_id, namespace, status, generation_path,
                    previous_generation, pointer_hash, created_at, committed_at
                ) VALUES (?, ?, 'committed', ?, ?, ?, ?, ?)
                """,
                (
                    intent["transaction_id"],
                    intent["namespace"],
                    generation.relative_to(self.workspace_root).as_posix(),
                    intent.get("previous_generation") or "",
                    pointer_hash,
                    intent.get("created_at") or _now(),
                    _now(),
                ),
            )


def _tree_hash(rows: list[dict[str, Any]]) -> str:
    from song_agent.platform.persistence.file_artifacts import stable_tree_hash

    return stable_tree_hash(rows)


def _now() -> str:
    return datetime.now(UTC).isoformat()
