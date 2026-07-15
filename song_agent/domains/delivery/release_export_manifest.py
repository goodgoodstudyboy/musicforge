from __future__ import annotations

import json
from typing import Any

from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS, ReleaseStore


RELEASE_EXPORT_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}


def read_release_export_manifest(release_store: ReleaseStore, release_id: str) -> dict[str, Any]:
    path = release_store.export_dir(release_id) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Release export has not been generated.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return sanitize_metadata(
        data if isinstance(data, dict) else {},
        blocked_keys=RELEASE_EXPORT_BLOCKED_KEYS,
    )
