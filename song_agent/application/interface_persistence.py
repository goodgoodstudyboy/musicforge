from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypeVar

from song_agent.platform.persistence import write_json_atomic


JobType = TypeVar("JobType", contravariant=True)


class JobWriter(Protocol[JobType]):
    def _write_job(self, job: JobType) -> None: ...


def write_interface_document(path: Path | str, document: object) -> None:
    """Persist an interface-requested document through the application boundary."""

    write_json_atomic(Path(path), document)


def persist_interface_job(store: JobWriter[JobType], job: JobType) -> None:
    """Compatibility command for legacy JobStore persistence."""

    store._write_job(job)
