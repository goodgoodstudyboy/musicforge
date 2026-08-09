from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from song_agent.platform.contracts.coercion import as_int
from song_agent.platform.contracts.documents import JsonDocument, normalize_json_document


@dataclass(frozen=True)
class EvidenceRef:
    component_type: str
    component_id: str
    evidence_type: str
    generation: int = 1
    package_type: str = ""
    zip_sha256: str = ""
    zip_size_bytes: int = 0
    manifest_hash: str = ""
    verification_report_hash: str = ""
    source_hash: str = ""
    signoff_hash: str = ""
    history_event_hash: str = ""
    schema_version: int = 1

    @property
    def identity(self) -> tuple[str, str, str, int]:
        return (
            self.component_type,
            self.component_id,
            self.evidence_type,
            self.generation,
        )

    def to_dict(self) -> JsonDocument:
        return normalize_json_document(asdict(self))

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "EvidenceRef":
        return cls(
            schema_version=as_int(value.get("schema_version") or 1),
            component_type=str(value.get("component_type") or ""),
            component_id=str(value.get("component_id") or ""),
            evidence_type=str(value.get("evidence_type") or ""),
            generation=as_int(value.get("generation") or 1),
            package_type=str(value.get("package_type") or ""),
            zip_sha256=str(value.get("zip_sha256") or ""),
            zip_size_bytes=as_int(value.get("zip_size_bytes") or 0),
            manifest_hash=str(value.get("manifest_hash") or ""),
            verification_report_hash=str(value.get("verification_report_hash") or ""),
            source_hash=str(value.get("source_hash") or ""),
            signoff_hash=str(value.get("signoff_hash") or ""),
            history_event_hash=str(value.get("history_event_hash") or ""),
        )
