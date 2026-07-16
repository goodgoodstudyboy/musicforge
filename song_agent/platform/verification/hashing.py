from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from song_agent.platform.verification.sanitization import sanitize_metadata


def stable_hash(value: Any) -> str:
    payload = json.dumps(sanitize_metadata(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def integrity_hash(document: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in document.items() if key != "integrity_hash"})


def integrity_ok(document: dict[str, Any]) -> bool:
    return bool(document) and bool(document.get("integrity_hash")) and document.get("integrity_hash") == integrity_hash(document)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_text_bytes(data: bytes) -> bytes:
    """Return UTF-8 text bytes with platform-independent line endings."""
    text = data.decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def sha256_text_file(path: Path | str | None) -> str | None:
    if path is None:
        return None
    target = Path(path)
    if not target.exists() or not target.is_file():
        return None
    return sha256_bytes(canonical_text_bytes(target.read_bytes()))


def sha256_file(path: Path | str | None) -> str | None:
    if path is None:
        return None
    target = Path(path)
    if not target.exists() or not target.is_file():
        return None
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_or_integrity(path: Path | str | None) -> str | None:
    if path is None:
        return None
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return sha256_file(target)
    if isinstance(value, dict) and value.get("integrity_hash"):
        return str(value["integrity_hash"])
    return sha256_file(target)
