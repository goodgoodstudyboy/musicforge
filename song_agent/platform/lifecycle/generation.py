from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

from song_agent.platform.contracts.lifecycle import GenerationRef
from song_agent.platform.verification.hashing import integrity_hash


class GenerationService:
    @staticmethod
    def successor(current: int) -> int:
        if int(current) < 1:
            raise ValueError("Generation must be positive.")
        return int(current) + 1

    @staticmethod
    def build_document(
        reference: GenerationRef,
        *,
        package_type: str,
        schema_version: int = 1,
        extra: DomainDocument | None = None,
    ) -> DomainDocument:
        document: ImplementationDocument = {
            "schema_version": schema_version,
            "package_type": package_type,
            **reference.to_dict(),
        }
        document.pop("subject_id")
        if extra:
            document.update(extra)
        document["integrity_hash"] = integrity_hash(document)
        return document

    @staticmethod
    def require_current(actual: int, expected: int) -> None:
        if int(actual) != int(expected):
            raise ValueError("Evidence generation is not current.")
