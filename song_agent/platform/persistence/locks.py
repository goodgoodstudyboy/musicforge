from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable


class WorkspaceLockError(RuntimeError):
    pass


@dataclass
class _ProcessLockState:
    mutex: threading.RLock = field(default_factory=threading.RLock)
    owner_thread_id: int | None = None
    depth: int = 0
    token: str = ""


_STATES: dict[str, _ProcessLockState] = {}
_STATES_GUARD = threading.Lock()


class WorkspaceLock:
    """A process-shared, thread-reentrant exclusive workspace write lock."""

    def __init__(
        self,
        workspace_root: Path | str,
        *,
        operation: str = "workflow-write",
        timeout_seconds: float = 30.0,
        lease_seconds: int = 300,
        on_commit: Callable[[], None] | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.lock_path = self.workspace_root / "state" / "locks" / "workspace-write.lock"
        self.operation = str(operation)[:120]
        self.timeout_seconds = float(timeout_seconds)
        self.lease_seconds = int(lease_seconds)
        self.on_commit = on_commit
        key = os.path.normcase(str(self.lock_path))
        with _STATES_GUARD:
            self._state = _STATES.setdefault(key, _ProcessLockState())

    def __enter__(self) -> "WorkspaceLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if exc_type is None and self._state.depth == 1 and self.on_commit is not None:
                self.on_commit()
        finally:
            self.release()

    def acquire(self) -> None:
        self._state.mutex.acquire()
        thread_id = threading.get_ident()
        if self._state.owner_thread_id == thread_id and self._state.depth:
            self._state.depth += 1
            return
        deadline = time.monotonic() + self.timeout_seconds
        try:
            while True:
                self.lock_path.parent.mkdir(parents=True, exist_ok=True)
                token = uuid.uuid4().hex
                document = {
                    "schema_version": 1,
                    "owner_pid": os.getpid(),
                    "owner_thread_id": thread_id,
                    "operation": self.operation,
                    "acquired_at": datetime.now(UTC).isoformat(),
                    "lease_seconds": self.lease_seconds,
                    "token": token,
                }
                try:
                    descriptor = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                except FileExistsError:
                    lock = _read_lock(self.lock_path)
                    owner_pid = int(lock.get("owner_pid") or 0)
                    if owner_pid and not _pid_exists(owner_pid):
                        self._remove_stale(owner_pid=owner_pid, token=str(lock.get("token") or ""))
                        continue
                    if time.monotonic() >= deadline:
                        raise WorkspaceLockError(
                            f"Workspace is locked by pid={owner_pid or 'unknown'} operation={lock.get('operation') or 'unknown'}."
                        )
                    time.sleep(0.05)
                    continue
                write_error: Exception | None = None
                try:
                    os.write(descriptor, (json.dumps(document, sort_keys=True) + "\n").encode("utf-8"))
                    os.fsync(descriptor)
                except Exception as exc:
                    write_error = exc
                finally:
                    os.close(descriptor)
                if write_error is not None:
                    current = _read_lock(self.lock_path)
                    if not current or (current.get("token") == token and int(current.get("owner_pid") or 0) == os.getpid()):
                        self.lock_path.unlink(missing_ok=True)
                    raise write_error
                self._state.owner_thread_id = thread_id
                self._state.depth = 1
                self._state.token = token
                return
        except Exception:
            self._state.mutex.release()
            raise

    def release(self) -> None:
        thread_id = threading.get_ident()
        if self._state.owner_thread_id != thread_id or self._state.depth < 1:
            raise WorkspaceLockError("Workspace lock is not owned by the current thread.")
        self._state.depth -= 1
        if self._state.depth == 0:
            lock = _read_lock(self.lock_path)
            if lock.get("token") != self._state.token or int(lock.get("owner_pid") or 0) != os.getpid():
                self._state.owner_thread_id = None
                self._state.token = ""
                self._state.mutex.release()
                raise WorkspaceLockError("Workspace lock ownership changed before release.")
            try:
                self.lock_path.unlink(missing_ok=True)
            finally:
                self._state.owner_thread_id = None
                self._state.token = ""
        self._state.mutex.release()

    def recover(self, *, force: bool = False) -> bool:
        lock = _read_lock(self.lock_path)
        if not lock:
            return False
        owner_pid = int(lock.get("owner_pid") or 0)
        if not force and owner_pid and _pid_exists(owner_pid):
            raise WorkspaceLockError("Cannot recover a lock owned by a live process.")
        return self._remove_stale(owner_pid=owner_pid, token=str(lock.get("token") or ""), force=force)

    def _remove_stale(self, *, owner_pid: int, token: str, force: bool = False) -> bool:
        current = _read_lock(self.lock_path)
        if int(current.get("owner_pid") or 0) != owner_pid or str(current.get("token") or "") != token:
            return False
        if not force and owner_pid and _pid_exists(owner_pid):
            raise WorkspaceLockError("Lock owner is still alive.")
        self.lock_path.unlink(missing_ok=True)
        return True


def _read_lock(path: Path) -> ImplementationDocument:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes

        kernel32 = getattr(ctypes, "windll").kernel32
        process = kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return False
        kernel32.CloseHandle(process)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
