from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

from song_agent.platform.verification.hashing import sha256_file, stable_hash
from song_agent.platform.verification.sanitization import sanitize_metadata


Sanitizer = Callable[[Any], Any]
HistoryAdapter = Callable[[tuple[dict[str, Any], ...]], list[dict[str, Any]]]
HistoryHashMode = Literal["event", "payload"]


@dataclass(frozen=True)
class HistoryValidation:
    valid: bool
    rows: tuple[dict[str, Any], ...]
    error_index: int | None = None
    error_code: str = ""

    @property
    def latest(self) -> dict[str, Any] | None:
        return self.rows[-1] if self.rows else None


@dataclass(frozen=True)
class HistoryMigrationReport:
    source_path: str
    target_path: str
    rollback_path: str
    source_hash: str
    target_hash: str
    source_schema_version: int
    target_schema_version: int
    row_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "target_path": self.target_path,
            "rollback_path": self.rollback_path,
            "source_hash": self.source_hash,
            "target_hash": self.target_hash,
            "source_schema_version": self.source_schema_version,
            "target_schema_version": self.target_schema_version,
            "row_count": self.row_count,
        }


class HistoryChain:
    def __init__(
        self,
        path: Path | str,
        *,
        sanitizer: Sanitizer = sanitize_metadata,
        hash_mode: HistoryHashMode = "event",
    ) -> None:
        self.path = Path(path)
        self.sanitizer = sanitizer
        self.hash_mode = hash_mode

    def read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("History rows must be JSON objects.")
            rows.append(value)
        return rows

    def validate(self) -> HistoryValidation:
        try:
            rows = self.read()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return HistoryValidation(False, (), None, "history_unreadable")
        previous: str | None = None if self.hash_mode == "payload" else ""
        for index, row in enumerate(rows):
            payload_hash = self._payload_hash(row)
            normalized = {**row, "payload_hash": payload_hash}
            event_hash = stable_hash({key: value for key, value in normalized.items() if key != "event_hash"})
            if row.get("payload_hash") != payload_hash:
                return HistoryValidation(False, tuple(rows), index, "history_payload_hash")
            if row.get("event_hash") != event_hash:
                return HistoryValidation(False, tuple(rows), index, "history_event_hash")
            actual_previous = row.get("previous_event_hash") if self.hash_mode == "payload" else str(row.get("previous_event_hash") or "")
            if actual_previous != previous:
                return HistoryValidation(False, tuple(rows), index, "history_chain")
            previous = str(row.get("event_hash") or "")
        return HistoryValidation(True, tuple(rows))

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate()
        if not validation.valid:
            raise ValueError(f"Cannot append to invalid history: {validation.error_code}")
        previous = (
            (validation.latest or {}).get("event_hash")
            if self.hash_mode == "payload"
            else str((validation.latest or {}).get("event_hash") or "")
        )
        event = self._build_current_event(payload, previous_event_hash=previous)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    @staticmethod
    def build_event(payload: dict[str, Any], *, previous_event_hash: str = "", sanitizer: Sanitizer = sanitize_metadata) -> dict[str, Any]:
        event = sanitizer({**payload, "previous_event_hash": previous_event_hash})
        event["payload_hash"] = stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        return event

    def _build_current_event(self, payload: ImplementationDocument, *, previous_event_hash: str | None) -> ImplementationDocument:
        event = self.sanitizer({**payload, "previous_event_hash": previous_event_hash})
        event["payload_hash"] = self._payload_hash(event)
        event["event_hash"] = stable_hash({key: value for key, value in event.items() if key != "event_hash"})
        return event

    def _payload_hash(self, event: ImplementationDocument) -> str:
        if self.hash_mode == "payload":
            payload = _as_document(event.get("payload"))
            return stable_hash(payload)
        return stable_hash({key: value for key, value in event.items() if key not in {"payload_hash", "event_hash"}})

    def through(self, event_hash: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for row in self.read():
            rows.append(row)
            if row.get("event_hash") == event_hash:
                return rows
        raise ValueError("History event was not found.")

    def latest_state(self, event_states: dict[str, str], *, default: str = "unsigned") -> dict[str, Any]:
        state: dict[str, Any] = {"status": default, "event": None}
        for row in self.read():
            event_type = str(row.get("event_type") or "")
            if event_type in event_states:
                state = {"status": event_states[event_type], "event": row}
        return state

    def migrate_copy(
        self,
        target_path: Path | str,
        *,
        source_schema_version: int = 1,
        target_schema_version: int = 1,
        rollback_path: Path | str | None = None,
        adapter: HistoryAdapter | None = None,
    ) -> HistoryMigrationReport:
        validation = self.validate()
        if not self.path.is_file() or not validation.valid:
            raise ValueError("Only a valid existing history can be migrated.")
        target = Path(target_path)
        if target.exists():
            raise ValueError("Migration target already exists.")
        rollback = Path(rollback_path) if rollback_path is not None else target.with_suffix(target.suffix + ".rollback")
        if rollback.exists():
            raise ValueError("Migration rollback copy already exists.")
        if source_schema_version != target_schema_version and adapter is None:
            raise ValueError("A schema-changing migration requires an explicit adapter.")
        target.parent.mkdir(parents=True, exist_ok=True)
        rollback.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.path, rollback)
        if adapter is None:
            shutil.copy2(self.path, target)
        else:
            migrated = adapter(validation.rows)
            target_chain = HistoryChain(target, sanitizer=self.sanitizer, hash_mode=self.hash_mode)
            try:
                for payload in migrated:
                    target_chain.append(
                        {
                            key: value
                            for key, value in payload.items()
                            if key not in {"previous_event_hash", "payload_hash", "event_hash"}
                        }
                    )
            except Exception:
                target.unlink(missing_ok=True)
                raise
            if not target_chain.validate().valid:
                target.unlink(missing_ok=True)
                raise ValueError("Migrated history is invalid.")
        source_hash = str(sha256_file(self.path) or "")
        target_hash = str(sha256_file(target) or "")
        if adapter is None and source_hash != target_hash:
            target.unlink(missing_ok=True)
            raise ValueError("Migrated history fingerprint mismatch.")
        return HistoryMigrationReport(
            source_path=str(self.path),
            target_path=str(target),
            rollback_path=str(rollback),
            source_hash=source_hash,
            target_hash=target_hash,
            source_schema_version=source_schema_version,
            target_schema_version=target_schema_version,
            row_count=len(validation.rows),
        )
