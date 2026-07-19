from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SignoffRef:
    subject_id: str
    generation: int
    signoff_hash: str
    binding_hash: str
    history_event_hash: str
    source_hash: str = ""

    def to_dict(self) -> DomainDocument:
        return asdict(self)


@dataclass(frozen=True)
class ResetAuthorization:
    subject_id: str
    request_id: str
    action: str
    change_type: str
    target: ImplementationDocument
    source: ImplementationDocument | None = None


@dataclass(frozen=True)
class GenerationRef:
    subject_id: str
    generation: int
    status: str
    previous_generation: int | None = None
    reset_proof_hash: str | None = None

    def to_dict(self) -> DomainDocument:
        return asdict(self)
