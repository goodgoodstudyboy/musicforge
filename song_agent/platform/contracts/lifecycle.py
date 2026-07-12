from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SignoffRef:
    subject_id: str
    generation: int
    signoff_hash: str
    binding_hash: str
    history_event_hash: str
    source_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResetAuthorization:
    subject_id: str
    request_id: str
    action: str
    change_type: str
    target: dict[str, Any]
    source: dict[str, Any] | None = None


@dataclass(frozen=True)
class GenerationRef:
    subject_id: str
    generation: int
    status: str
    previous_generation: int | None = None
    reset_proof_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
