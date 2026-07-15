from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class PortalReviewStorePort(Protocol):
    portal_store: Any

    def get_response(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

    def pack_is_stale(self, *args: Any, **kwargs: Any) -> bool: ...

    def read_pack(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

    def responses_dir(self, *args: Any, **kwargs: Any) -> Path: ...

    def verify_response(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...


class AttestationPortalStorePort(Protocol):
    attestation_store: Any

    def export_dir(self, *args: Any, **kwargs: Any) -> Path: ...

    def read_report(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...

    def verification_report_path(self, *args: Any, **kwargs: Any) -> Path: ...

    def zip_path(self, *args: Any, **kwargs: Any) -> Path: ...


class AttestationRegistryStorePort(Protocol):
    def zip_path(self, *args: Any, **kwargs: Any) -> Path: ...
