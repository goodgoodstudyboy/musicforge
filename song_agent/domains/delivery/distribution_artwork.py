from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import base64 as base64
import hashlib as hashlib
import os as os
import shutil as shutil
import struct as struct
import threading as threading
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.delivery.distribution import DistributionStateError as DistributionStateError, DistributionStore as DistributionStore, DistributionValidationError as DistributionValidationError
from song_agent.domains.delivery.distribution_profiles import DISTRIBUTION_BLOCKED_KEYS as DISTRIBUTION_BLOCKED_KEYS
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text


SUPPORTED_ARTWORK_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_ARTWORK_BYTES = 50 * 1024 * 1024


class DistributionArtworkError(ValueError):
    pass


def import_distribution_artwork(store: DistributionStore, release_id: str, payload: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    if store.any_signed_target(release_id):
        raise DistributionStateError("Signed distribution packages cannot change artwork. Reset distribution signoff before importing artwork.")
    store.release_store.get_release(release_id)
    now = now or now_iso()
    filename = _safe_filename(str(payload.get("filename") or "cover.png"))
    source = _payload_bytes(payload)
    if not source:
        raise DistributionArtworkError("Artwork payload is empty.")
    if len(source) > MAX_ARTWORK_BYTES:
        raise DistributionArtworkError("Artwork exceeds the maximum allowed size.")
    width, height, media_type = _image_dimensions(source, filename)
    artwork_id = _reserve_artwork_id(store, release_id)
    artwork_dir = store.artwork_dir(release_id) / artwork_id
    artwork_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"cover{Path(filename).suffix.lower()}"
    file_path = artwork_dir / stored_filename
    _write_bytes(file_path, source)
    record = sanitize_metadata(
        {
            "schema_version": 1,
            "artwork_id": artwork_id,
            "release_id": release_id,
            "filename": filename,
            "stored_filename": stored_filename,
            "media_type": media_type,
            "width": width,
            "height": height,
            "size_bytes": file_path.stat().st_size,
            "sha256": _sha256(file_path),
            "created_at": now,
            "status": "ready",
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )
    write_json(artwork_dir / "artwork.json", record)
    store.append_event(release_id, "distribution_artwork_imported", {"artwork_id": artwork_id, "width": width, "height": height})
    return record


def list_distribution_artwork(store: DistributionStore, release_id: str) -> list[dict[str, Any]]:
    store.release_store.get_release(release_id)
    rows: list[dict[str, Any]] = []
    for path in sorted(store.artwork_dir(release_id).glob("artwork-*/artwork.json")):
        try:
            value = read_json(path)
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            rows.append(sanitize_metadata(value, blocked_keys=DISTRIBUTION_BLOCKED_KEYS))
    return sorted(rows, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def read_distribution_artwork(store: DistributionStore, release_id: str, artwork_id: str) -> dict[str, Any]:
    store.release_store.get_release(release_id)
    path = store.artwork_dir(release_id) / _validate_artwork_id(artwork_id) / "artwork.json"
    if not path.exists():
        raise FileNotFoundError("Distribution artwork does not exist.")
    value = read_json(path)
    return sanitize_metadata(_as_document(value), blocked_keys=DISTRIBUTION_BLOCKED_KEYS)


def latest_distribution_artwork(store: DistributionStore, release_id: str) -> dict[str, Any]:
    rows = list_distribution_artwork(store, release_id)
    return rows[0] if rows else {}


def distribution_artwork_file_path(store: DistributionStore, release_id: str, artwork: dict[str, Any] | str) -> Path:
    record = read_distribution_artwork(store, release_id, artwork) if isinstance(artwork, str) else artwork
    artwork_id = _validate_artwork_id(str(record.get("artwork_id") or ""))
    stored_filename = _safe_filename(str(record.get("stored_filename") or "cover.png"))
    return store.artwork_dir(release_id) / artwork_id / stored_filename


def delete_distribution_artwork(store: DistributionStore, release_id: str, artwork_id: str) -> dict[str, Any]:
    if store.any_signed_target(release_id):
        raise DistributionStateError("Signed distribution packages cannot change artwork. Reset distribution signoff before deleting artwork.")
    store.release_store.get_release(release_id)
    target_dir = store.artwork_dir(release_id) / _validate_artwork_id(artwork_id)
    root = store.artwork_dir(release_id).resolve()
    try:
        target_dir.resolve().relative_to(root)
    except ValueError as exc:
        raise DistributionValidationError("Refusing to operate outside distribution artwork boundaries.") from exc
    if not target_dir.exists():
        raise FileNotFoundError("Distribution artwork does not exist.")
    shutil.rmtree(target_dir)
    store.append_event(release_id, "distribution_artwork_deleted", {"artwork_id": artwork_id})
    return {"artwork_id": artwork_id, "deleted": True}


def distribution_artwork_summary(record: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(record)
    return sanitize_metadata(
        {
            "exists": bool(data),
            "artwork_id": data.get("artwork_id"),
            "filename": data.get("filename"),
            "media_type": data.get("media_type"),
            "width": data.get("width"),
            "height": data.get("height"),
            "size_bytes": data.get("size_bytes"),
            "sha256": data.get("sha256"),
            "status": data.get("status") or "missing",
        },
        blocked_keys=DISTRIBUTION_BLOCKED_KEYS,
    )


def _payload_bytes(payload: ImplementationDocument) -> bytes:
    if "source_path" in payload:
        raise DistributionArtworkError("Artwork source_path is not supported. Upload content_base64 instead.")
    encoded = str(payload.get("content_base64") or payload.get("data_base64") or "").strip()
    if encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            raise DistributionArtworkError("Artwork base64 payload is invalid.") from exc
    return b""


def _image_dimensions(data: bytes, filename: str) -> tuple[int, int, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_ARTWORK_EXTENSIONS:
        raise DistributionArtworkError("Artwork must be PNG or JPEG.")
    if suffix == ".png":
        if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16] != b"IHDR":
            raise DistributionArtworkError("PNG artwork header is invalid.")
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if width <= 0 or height <= 0:
            raise DistributionArtworkError("PNG artwork dimensions are invalid.")
        return width, height, "image/png"
    return (*_jpeg_dimensions(data), "image/jpeg")


def _jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise DistributionArtworkError("JPEG artwork header is invalid.")
    offset = 2
    while offset + 9 < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(data):
            break
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        if length < 2 or offset + length > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3}:
            if length < 7:
                break
            height = struct.unpack(">H", data[offset + 3 : offset + 5])[0]
            width = struct.unpack(">H", data[offset + 5 : offset + 7])[0]
            if width > 0 and height > 0:
                return width, height
        offset += length
    raise DistributionArtworkError("JPEG artwork dimensions could not be read.")


def _reserve_artwork_id(store: DistributionStore, release_id: str) -> str:
    root = store.artwork_dir(release_id)
    root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 1_000_000):
        artwork_id = f"artwork-{index:06d}"
        if not (root / artwork_id).exists():
            return artwork_id
    raise DistributionArtworkError("Unable to allocate a unique artwork id.")


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp_path.write_bytes(data)
    tmp_path.replace(path)


def _safe_filename(value: str) -> str:
    raw = sanitize_sensitive_text(str(value or "").strip())[:160]
    name = Path(raw).name
    suffix = Path(name).suffix.lower()
    stem = slugify(Path(name).stem or "cover")[:80]
    if suffix not in SUPPORTED_ARTWORK_EXTENSIONS:
        raise DistributionArtworkError("Artwork filename must end in .png, .jpg, or .jpeg.")
    if any(ch in raw for ch in ("/", "\\", ":", "\x00")):
        raise DistributionArtworkError("Artwork filename is unsafe.")
    return f"{stem}{suffix}"


def _validate_artwork_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("artwork-") or not text.removeprefix("artwork-").isdigit():
        raise DistributionArtworkError("Invalid distribution artwork id.")
    return text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
