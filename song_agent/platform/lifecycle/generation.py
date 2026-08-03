from __future__ import annotations

from typing import Any

from song_agent.platform.contracts import GenerationRef
from song_agent.platform.contracts.packages import require_registered_package_type as _require_registered_package_type
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
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        document: dict[str, Any] = {
            "schema_version": schema_version,
            "package_type": _require_registered_package_type(package_type, writer_id="song_agent.platform.lifecycle.generation.GenerationService.build_document"),
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
