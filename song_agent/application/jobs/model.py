from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class JobState:
    job_id: str
    title: str
    output_dir: str
    status: str
    created_at: str
    updated_at: str
    step: str = "created"
    message: str = ""
    summary: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    attempt_count: int = 0
    cancel_requested: bool = False
    pause_requested: bool = False
    hidden: bool = False
    input_payload: dict[str, Any] = field(default_factory=dict)
    provider_snapshot: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    deleted: bool = False
    interrupted: bool = False
    last_seen_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    heartbeat_at: str | None = None
    retry_requested: bool = False
    retry_count: int = 0
    max_retries: int = 0
    next_retry_at: str | None = None
    last_error: str | None = None
    stalled: bool = False
    stall_timeout_seconds: int = 300
    generation_mode: str = "local"
    pipeline_mode: str = "single"
    job_type: str = "song"
    edit_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobState":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            job_id=str(data["job_id"]),
            title=str(data.get("title", data["job_id"])),
            output_dir=str(data["output_dir"]),
            status=str(data.get("status", "completed")),
            created_at=str(data.get("created_at", now)),
            updated_at=str(data.get("updated_at", now)),
            step=str(data.get("step", "")),
            message=str(data.get("message", "")),
            summary=_dict_or_empty(data.get("summary")),
            error=None if data.get("error") is None else str(data.get("error")),
            attempt_count=int(data.get("attempt_count", 0) or 0),
            cancel_requested=bool(data.get("cancel_requested", False)),
            pause_requested=bool(data.get("pause_requested", False)),
            hidden=bool(data.get("hidden", False)),
            input_payload=_dict_or_empty(data.get("input_payload")),
            provider_snapshot=_dict_or_empty(data.get("provider_snapshot")),
            artifacts=_dict_or_empty(data.get("artifacts")),
            deleted=bool(data.get("deleted", False)),
            interrupted=bool(data.get("interrupted", False)),
            last_seen_at=None if data.get("last_seen_at") is None else str(data.get("last_seen_at")),
            started_at=None if data.get("started_at") is None else str(data.get("started_at")),
            finished_at=None if data.get("finished_at") is None else str(data.get("finished_at")),
            heartbeat_at=None if data.get("heartbeat_at") is None else str(data.get("heartbeat_at")),
            retry_requested=bool(data.get("retry_requested", False)),
            retry_count=int(data.get("retry_count", 0) or 0),
            max_retries=int(data.get("max_retries", 0) or 0),
            next_retry_at=None if data.get("next_retry_at") is None else str(data.get("next_retry_at")),
            last_error=None if data.get("last_error") is None else str(data.get("last_error")),
            stalled=bool(data.get("stalled", False)),
            stall_timeout_seconds=int(data.get("stall_timeout_seconds", 300) or 300),
            generation_mode=str(data.get("generation_mode", "local") or "local"),
            pipeline_mode=str(data.get("pipeline_mode", "single") or "single"),
            job_type=str(data.get("job_type", "song") or "song"),
            edit_metadata=_dict_or_empty(data.get("edit_metadata")),
        )


def _dict_or_empty(value: Any) -> ImplementationDocument:
    return value if isinstance(value, dict) else {}
