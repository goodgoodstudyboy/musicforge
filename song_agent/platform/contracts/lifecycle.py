from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from song_agent.platform.contracts.documents import JsonDocument, JsonValue


@dataclass(frozen=True)
class SignoffRef:
    subject_id: str
    generation: int
    signoff_hash: str
    binding_hash: str
    history_event_hash: str
    source_hash: str = ""

    def to_dict(self) -> JsonDocument:
        return {
            "subject_id": self.subject_id,
            "generation": self.generation,
            "signoff_hash": self.signoff_hash,
            "binding_hash": self.binding_hash,
            "history_event_hash": self.history_event_hash,
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True)
class ResetAuthorization:
    subject_id: str
    request_id: str
    action: str
    change_type: str
    target: Mapping[str, JsonValue]
    source: Mapping[str, JsonValue] | None = None


@dataclass(frozen=True)
class GenerationRef:
    subject_id: str
    generation: int
    status: str
    previous_generation: int | None = None
    reset_proof_hash: str | None = None

    def to_dict(self) -> JsonDocument:
        return {
            "subject_id": self.subject_id,
            "generation": self.generation,
            "status": self.status,
            "previous_generation": self.previous_generation,
            "reset_proof_hash": self.reset_proof_hash,
        }
