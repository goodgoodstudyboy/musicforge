from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument
from pathlib import Path

from song_agent.platform.contracts.lifecycle import SignoffRef
from song_agent.platform.lifecycle.event_ledger import HistoryChain
from song_agent.platform.verification.hashing import integrity_hash, integrity_ok, stable_hash


class SignoffService:
    @staticmethod
    def seal(document: DomainDocument, *, payload_hash: bool = True) -> DomainDocument:
        result = dict(document)
        if payload_hash:
            result["payload_hash"] = stable_hash({key: value for key, value in result.items() if key not in {"payload_hash", "integrity_hash"}})
        result["integrity_hash"] = integrity_hash(result)
        return result

    @staticmethod
    def validate_pair(signoff: DomainDocument, binding: DomainDocument, *, signoff_field: str = "signoff_hash") -> bool:
        return integrity_ok(signoff) and integrity_ok(binding) and binding.get(signoff_field) == signoff.get("integrity_hash")

    @staticmethod
    def validate_history_binding(history: HistoryChain, reference: SignoffRef) -> bool:
        validation = history.validate()
        latest = validation.latest or {}
        return (
            validation.valid
            and latest.get("event_hash") == reference.history_event_hash
            and latest.get("signoff_hash") == reference.signoff_hash
        )

    @staticmethod
    def assert_transition_allowed(
        history: HistoryChain,
        *,
        artifact_paths: tuple[Path, ...],
        signed_event_types: set[str],
        reset_event_types: set[str],
    ) -> None:
        artifacts_exist = any(path.exists() for path in artifact_paths)
        if not history.path.is_file():
            if artifacts_exist:
                raise ValueError("Signoff history is missing while lifecycle artifacts remain.")
            return
        validation = history.validate()
        if not validation.valid or not validation.rows:
            raise ValueError("Signoff history is unreadable, empty, or invalid.")
        latest_type = str(validation.rows[-1].get("event_type") or "")
        if latest_type in signed_event_types:
            raise ValueError("Evidence is already signed.")
        if latest_type not in reset_event_types:
            raise ValueError("Latest lifecycle event does not authorize successor signoff.")
