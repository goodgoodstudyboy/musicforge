from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument
from dataclasses import dataclass
from typing import Iterable

from song_agent.platform.contracts.evidence import EvidenceRef


@dataclass(frozen=True)
class ExternalEvidenceManifest:
    items: tuple[EvidenceRef, ...]
    schema_version: int = 1

    @classmethod
    def from_dict(cls, value: DomainDocument) -> "ExternalEvidenceManifest":
        return cls(
            schema_version=int(value.get("schema_version") or 1),
            items=tuple(EvidenceRef.from_dict(row) for row in value.get("items") or [] if isinstance(row, dict)),
        )

    def by_identity(self) -> dict[tuple[str, str, str, int], EvidenceRef]:
        return {item.identity: item for item in self.items}

    @property
    def identities_unique(self) -> bool:
        return len(self.by_identity()) == len(self.items)

    def matches_identity_set(self, actual: Iterable[EvidenceRef]) -> bool:
        rows = tuple(actual)
        actual_by_identity = {item.identity: item for item in rows}
        return (
            self.identities_unique
            and len(actual_by_identity) == len(rows)
            and set(self.by_identity()) == set(actual_by_identity)
        )

    def to_dict(self) -> DomainDocument:
        return {"schema_version": self.schema_version, "items": [item.to_dict() for item in self.items]}
