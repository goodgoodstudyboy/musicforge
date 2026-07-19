from __future__ import annotations

from song_agent.platform.contracts import DomainDocument
from song_agent.platform.contracts.coercion import as_document as _as_document

import json

from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS, ReleaseStore


RELEASE_EXPORT_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}


def read_release_export_manifest(release_store: ReleaseStore, release_id: str) -> DomainDocument:
    path = release_store.export_dir(release_id) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Release export has not been generated.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return sanitize_metadata(
        _as_document(data),
        blocked_keys=RELEASE_EXPORT_BLOCKED_KEYS,
    )
