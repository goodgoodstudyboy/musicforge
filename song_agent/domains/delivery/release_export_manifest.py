from __future__ import annotations

from song_agent.platform.contracts.coercion import as_document as _as_document

import json
from pathlib import Path
from typing import Any, Protocol

from song_agent.domains import _ImplementationDocument as ReleaseSignoffDocument
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS


RELEASE_EXPORT_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}


class ReleaseExportManifestPort(Protocol):
    def export_dir(self, release_id: str) -> Path: ...


class ReleaseExportDocument(Protocol):
    status: str
    latest_signoff_summary: ReleaseSignoffDocument


class ReleaseExportPort(ReleaseExportManifestPort, Protocol):
    def release_dir(self, release_id: str) -> Path: ...

    def zip_path(self, release_id: str) -> Path: ...

    def get_release(self, release_id: str) -> ReleaseExportDocument: ...

    def read_signoff(
        self,
        release_id: str,
        *,
        default: ReleaseSignoffDocument,
    ) -> ReleaseSignoffDocument: ...


def read_release_export_manifest(release_store: ReleaseExportManifestPort, release_id: str) -> dict[str, Any]:
    path = release_store.export_dir(release_id) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Release export has not been generated.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return sanitize_metadata(
        _as_document(data),
        blocked_keys=RELEASE_EXPORT_BLOCKED_KEYS,
    )
