from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from song_agent.platform.persistence.database import SCHEMA_VERSION, MusicForgeDatabase
from song_agent.platform.persistence.locks import WorkspaceLock
from song_agent.platform.verification.hashing import sha256_bytes, stable_hash


ProgramCrashHook = Callable[[str], None]
PROGRAM_COMPONENTS = (
    "program", "operations", "handoff", "vault", "continuity", "acceptance", "command_center",
    "receiver_acceptance", "change_control",
)


class ProgramPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProgramDocumentRecord:
    relative_path: str
    program_id: str
    component_type: str
    generation: int
    status: str
    version: int
    authority_path: str
    payload_hash: str
    projection_sha256: str


@dataclass(frozen=True)
class ProgramAggregate:
    program_id: str
    components: dict[str, tuple[ProgramDocumentRecord, ...]]


class ProgramStateRepository:
    def __init__(self, workspace_root: Path | str, *, database: MusicForgeDatabase | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.database = database or MusicForgeDatabase.from_workspace(self.workspace_root)
        self.database.initialize()

    def write_projection(
        self,
        path: Path | str,
        document: DomainDocument,
        *,
        crash_hook: ProgramCrashHook | None = None,
    ) -> Path:
        self._ensure_database()
        target, relative = self._target(path)
        payload = _json_bytes(document)
        payload_hash = sha256_bytes(payload)
        authority = self._write_authority(payload, payload_hash)
        self._crash(crash_hook, "after_state_write_before_event")
        transaction_id = f"program-{uuid.uuid4().hex}"
        metadata = _document_metadata(relative, document)
        with WorkspaceLock(self.workspace_root, operation=f"program-write:{relative}"):
            self._recover_pending_locked()
            version = self._record_state_event(
                relative, authority, payload_hash, transaction_id, metadata
            )
            self._crash(crash_hook, "after_event_append_before_projection")
            _write_bytes_atomic(target, payload)
            with self.database.transaction() as connection:
                connection.execute(
                    "UPDATE program_projection_transactions SET status='projection_written' WHERE transaction_id=?",
                    (transaction_id,),
                )
            self._crash(crash_hook, "after_projection_before_index")
            self._commit_index(relative, version, transaction_id)
        return target

    def read_projection(self, path: Path | str) -> DomainDocument:
        self._ensure_database()
        target, relative = self._target(path)
        with WorkspaceLock(self.workspace_root, operation=f"program-read:{relative}"):
            self._recover_pending_locked()
            record = self._row(relative)
            if record is None:
                return _read_json(target)
            payload = self._authority_payload(record)
            if not target.is_file() or target.read_bytes() != payload:
                raise ProgramPersistenceError(f"Program projection differs from repository authority: {relative}")
        value = json.loads(payload)
        if not isinstance(value, dict):
            raise ProgramPersistenceError(f"Program authority is not a JSON object: {relative}")
        return value

    def recover_pending(self) -> list[str]:
        self._ensure_database()
        with WorkspaceLock(self.workspace_root, operation="program-persistence-recovery"):
            return self._recover_pending_locked()

    def aggregate(self, program_id: str) -> ProgramAggregate:
        self._ensure_database()
        self.recover_pending()
        with self.database.session() as connection:
            rows = connection.execute(
                "SELECT * FROM program_documents WHERE program_id=? ORDER BY component_type, relative_path",
                (program_id,),
            ).fetchall()
        components: dict[str, list[ProgramDocumentRecord]] = {}
        for row in rows:
            record = _record(row)
            components.setdefault(record.component_type, []).append(record)
        return ProgramAggregate(program_id, {key: tuple(value) for key, value in components.items()})

    def adopt_legacy_document(
        self,
        connection: Any,
        relative_path: str,
        document: DomainDocument,
        payload: bytes,
        *,
        migration_id: str,
    ) -> bool:
        existing = connection.execute(
            "SELECT payload_hash FROM program_documents WHERE relative_path=?", (relative_path,)
        ).fetchone()
        if existing:
            return False
        payload_hash = sha256_bytes(payload)
        authority = self._write_authority(payload, payload_hash)
        metadata = _document_metadata(relative_path, document)
        now = _now()
        self._insert_document(connection, relative_path, authority, payload_hash, 1, metadata, now)
        event = _event(relative_path, 1, payload_hash, "legacy_import", "", now)
        connection.execute(
            "INSERT INTO program_document_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event["event_hash"], relative_path, 1, "legacy_import", "", payload_hash, now),
        )
        self._upsert_index(connection, relative_path, 1, metadata, payload_hash, now)
        connection.execute(
            "INSERT INTO legacy_migration_program_documents VALUES (?, ?, ?)",
            (migration_id, relative_path, payload_hash),
        )
        return True

    def _record_state_event(
        self,
        relative: str,
        authority: Path,
        payload_hash: str,
        transaction_id: str,
        metadata: ImplementationDocument,
    ) -> int:
        now = _now()
        with self.database.transaction() as connection:
            current = connection.execute(
                "SELECT version FROM program_documents WHERE relative_path=?", (relative,)
            ).fetchone()
            version = int(current[0]) + 1 if current else 1
            previous = connection.execute(
                "SELECT event_hash FROM program_document_events WHERE relative_path=? ORDER BY document_version DESC LIMIT 1",
                (relative,),
            ).fetchone()
            previous_hash = str(previous[0]) if previous else ""
            self._insert_document(connection, relative, authority, payload_hash, version, metadata, now)
            event = _event(relative, version, payload_hash, "projection_updated", previous_hash, now)
            connection.execute(
                "INSERT INTO program_document_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (event["event_hash"], relative, version, "projection_updated", previous_hash, payload_hash, now),
            )
            connection.execute(
                "INSERT INTO program_projection_transactions VALUES (?, ?, ?, 'event_appended', ?, ?, '')",
                (transaction_id, relative, version, payload_hash, now),
            )
        return version

    def _insert_document(
        self,
        connection: Any,
        relative: str,
        authority: Path,
        payload_hash: str,
        version: int,
        metadata: ImplementationDocument,
        now: str,
    ) -> None:
        connection.execute(
            """INSERT INTO program_documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET program_id=excluded.program_id,
            component_type=excluded.component_type, generation=excluded.generation, status=excluded.status,
            version=excluded.version, authority_path=excluded.authority_path, payload_hash=excluded.payload_hash,
            projection_sha256=excluded.projection_sha256, updated_at=excluded.updated_at""",
            (
                relative, metadata["program_id"], metadata["component_type"], metadata["generation"],
                metadata["status"], version, authority.relative_to(self.workspace_root).as_posix(),
                payload_hash, payload_hash, now,
            ),
        )

    def _commit_index(self, relative: str, version: int, transaction_id: str) -> None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM program_documents WHERE relative_path=? AND version=?", (relative, version)
            ).fetchone()
            if row is None:
                raise ProgramPersistenceError("Program document version disappeared before index commit.")
            metadata = dict(row)
            self._upsert_index(connection, relative, version, metadata, str(row["payload_hash"]), _now())
            connection.execute(
                "UPDATE program_projection_transactions SET status='committed', committed_at=? WHERE transaction_id=?",
                (_now(), transaction_id),
            )

    def _recover_pending_locked(self) -> list[str]:
        with self.database.session() as connection:
            pending = connection.execute(
                "SELECT * FROM program_projection_transactions WHERE status!='committed' ORDER BY created_at"
            ).fetchall()
        recovered: list[str] = []
        for transaction in pending:
            relative = str(transaction["relative_path"])
            record = self._row(relative)
            if record is None or record.version != int(transaction["document_version"]):
                raise ProgramPersistenceError(f"Pending Program transaction version mismatch: {relative}")
            payload = self._authority_payload(record)
            target, _ = self._target(self.workspace_root / relative)
            if not target.is_file() or target.read_bytes() != payload:
                _write_bytes_atomic(target, payload)
            self._commit_index(relative, record.version, str(transaction["transaction_id"]))
            recovered.append(str(transaction["transaction_id"]))
        return recovered

    def _upsert_index(
        self,
        connection: Any,
        relative: str,
        version: int,
        metadata: ImplementationDocument,
        payload_hash: str,
        now: str,
    ) -> None:
        connection.execute(
            """INSERT INTO program_document_index VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET program_id=excluded.program_id,
            component_type=excluded.component_type, generation=excluded.generation, status=excluded.status,
            current_version=excluded.current_version, payload_hash=excluded.payload_hash, updated_at=excluded.updated_at""",
            (
                relative, metadata["program_id"], metadata["component_type"], int(metadata["generation"]),
                metadata["status"], version, payload_hash, now,
            ),
        )

    def _row(self, relative: str) -> ProgramDocumentRecord | None:
        with self.database.session() as connection:
            row = connection.execute("SELECT * FROM program_documents WHERE relative_path=?", (relative,)).fetchone()
        return _record(row) if row else None

    def _authority_payload(self, record: ProgramDocumentRecord) -> bytes:
        path = (self.workspace_root / record.authority_path).resolve()
        if not path.is_relative_to(self.workspace_root) or not path.is_file():
            raise ProgramPersistenceError(f"Program authority object is missing: {record.relative_path}")
        payload = path.read_bytes()
        if sha256_bytes(payload) != record.payload_hash:
            raise ProgramPersistenceError(f"Program authority object integrity failed: {record.relative_path}")
        return payload

    def _write_authority(self, payload: bytes, payload_hash: str) -> Path:
        path = self.workspace_root / "state" / "program-authority" / "objects" / payload_hash[:2] / f"{payload_hash}.json"
        if path.exists():
            if path.read_bytes() != payload:
                raise ProgramPersistenceError("Program authority hash collision.")
            return path
        _write_bytes_atomic(path, payload)
        return path

    def _target(self, path: Path | str) -> tuple[Path, str]:
        target = Path(path).resolve()
        if not target.is_relative_to(self.workspace_root):
            raise ProgramPersistenceError("Program projection path escapes the workspace.")
        relative = target.relative_to(self.workspace_root).as_posix()
        if relative.startswith("state/program-authority/"):
            raise ProgramPersistenceError("Program projection cannot target authority storage.")
        return target, relative

    def _ensure_database(self) -> None:
        if not self.database.path.is_file() or self.database.schema_version() < SCHEMA_VERSION:
            self.database.initialize()

    @staticmethod
    def _crash(hook: ProgramCrashHook | None, stage: str) -> None:
        if hook is not None:
            hook(stage)


def write_program_json(path: Path, data: DomainDocument) -> Path:
    workspace = _program_workspace(path)
    if workspace is None:
        _write_bytes_atomic(path, _json_bytes(data))
        return path
    return _cached_repository(str(workspace)).write_projection(path, data)


def read_program_json(path: Path) -> DomainDocument:
    workspace = _program_workspace(path)
    if workspace is None:
        return _read_json(path)
    return _cached_repository(str(workspace)).read_projection(path)


def program_json_facade(error_type: type[Exception]) -> tuple[Callable[[Path], DomainDocument], Callable[[Path, DomainDocument], Path]]:
    def read(path: Path) -> DomainDocument:
        try:
            return read_program_json(path)
        except ProgramPersistenceError as exc:
            raise error_type(str(exc)) from exc

    def write(path: Path, data: DomainDocument) -> Path:
        try:
            return write_program_json(path, data)
        except ProgramPersistenceError as exc:
            raise error_type(str(exc)) from exc

    return read, write


@lru_cache(maxsize=64)
def _cached_repository(workspace: str) -> ProgramStateRepository:
    return ProgramStateRepository(workspace)


def _program_workspace(path: Path | str) -> Path | None:
    target = Path(path).resolve()
    for parent in (target.parent, *target.parents):
        if parent.name.lower() == ".musicforge":
            return parent
    for parent in (target.parent, *target.parents):
        if parent.name.lower() in {"unified-release-programs", "urpccca"}:
            return parent.parent
    return None


def _document_metadata(relative: str, document: ImplementationDocument) -> ImplementationDocument:
    parts = Path(relative).parts
    program_id = str(document.get("program_id") or (parts[1] if len(parts) > 1 else "unknown"))
    path_text = "/".join(parts).lower()
    if parts and parts[0].lower() == "urpccca":
        component = "change_control" if "change-control" in path_text else "receiver_acceptance"
    else:
        markers = (
            ("continuity-command-center", "command_center"), ("acceptance", "acceptance"),
            ("continuity", "continuity"), ("vault-operations", "vault"), ("vault", "vault"),
            ("handoff", "handoff"), ("operations", "operations"),
        )
        component = next((value for marker, value in markers if marker in path_text), "program")
    return {
        "program_id": program_id,
        "component_type": component,
        "generation": int(document.get("current_generation") or document.get("generation") or 1),
        "status": str(document.get("status") or document.get("readiness") or "projection"),
    }


def _event(relative: str, version: int, payload_hash: str, event_type: str, previous: str, created_at: str) -> ImplementationDocument:
    event = {
        "relative_path": relative, "document_version": version, "event_type": event_type,
        "previous_event_hash": previous, "payload_hash": payload_hash, "created_at": created_at,
    }
    event["event_hash"] = stable_hash(event)
    return event


def _record(row: Any) -> ProgramDocumentRecord:
    return ProgramDocumentRecord(
        relative_path=str(row["relative_path"]), program_id=str(row["program_id"]),
        component_type=str(row["component_type"]), generation=int(row["generation"]),
        status=str(row["status"]), version=int(row["version"]), authority_path=str(row["authority_path"]),
        payload_hash=str(row["payload_hash"]), projection_sha256=str(row["projection_sha256"]),
    )


def _json_bytes(value: ImplementationDocument) -> bytes:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if os.linesep != "\n":
        text = text.replace("\n", os.linesep)
    return text.encode("utf-8")


def _read_json(path: Path) -> ImplementationDocument:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProgramPersistenceError(f"JSON document is not an object: {path.name}")
    return value


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(UTC).isoformat()
