from __future__ import annotations

import json
from pathlib import Path

from song_agent.platform.contracts.documents import JsonDocument
from song_agent.platform.verification.hashing import sha256_file, stable_hash


class EvidenceGraphBuildError(RuntimeError):
    pass


def path_from_row(
    root: Path,
    row: JsonDocument,
    *keys: str,
    allowed_root: Path | None = None,
) -> Path | None:
    for key in keys:
        value = row.get(key)
        if value:
            return resolve_path(root, str(value), allowed_root=allowed_root)
    return None


def resolve_path(root: Path, value: str, *, allowed_root: Path | None = None) -> Path:
    target = Path(value)
    resolved = (target if target.is_absolute() else root / target).resolve()
    if allowed_root is not None:
        try:
            resolved.relative_to(allowed_root)
        except ValueError as exc:
            raise EvidenceGraphBuildError("Evidence manifest references a path outside the allowed workspace.") from exc
    return resolved


def proof_hash(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return str(sha256_file(path) or "")
    if isinstance(value, dict) and value.get("integrity_hash"):
        return str(value["integrity_hash"])
    return stable_hash(value)


__all__ = ("EvidenceGraphBuildError", "path_from_row", "proof_hash", "resolve_path")
