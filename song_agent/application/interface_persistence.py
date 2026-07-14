from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from song_agent.platform.persistence import write_json_atomic


class JobWriter(Protocol):
    def _write_job(self, job: Any) -> None: ...


def write_interface_document(path: Path | str, document: Any) -> None:
    """Persist an interface-requested document through the application boundary."""

    write_json_atomic(Path(path), document)


def persist_interface_job(store: JobWriter, job: Any) -> None:
    """Compatibility command for legacy JobStore persistence."""

    store._write_job(job)
