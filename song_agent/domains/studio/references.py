# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import base64 as base64
import binascii as binascii
import hashlib as hashlib
import json as json
import re as re
import shutil as shutil
import threading as threading
from dataclasses import asdict as asdict, dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.assets import AssetStore as AssetStore, asset_public_dict as asset_public_dict, sanitize_asset_metadata as sanitize_asset_metadata
from song_agent.domains.studio.projectio import now_iso as now_iso, read_json as read_json, write_json as write_json
from song_agent.domains.studio.reference_paths import reference_file_path as reference_file_path, stored_reference_filename as stored_reference_filename
from song_agent.domains.creation.redaction import sanitize_sensitive_text as sanitize_sensitive_text


REFERENCE_ROOT = Path(".musicforge") / "references"
REFERENCE_ID_PATTERN = re.compile(r"^ref-[0-9]{3,6}$")
REFERENCE_SCHEMA_VERSION = 1
MAX_REFERENCE_REFS = 5
MAX_REFERENCE_WAV_BYTES = 50 * 1024 * 1024
MAX_REFERENCE_MIDI_BYTES = 2 * 1024 * 1024
MAX_REFERENCE_TEXT_BYTES = 256 * 1024
MAX_REFERENCE_TEXT_LINES = 5000
REFERENCE_TYPES = {"audio_wav", "midi", "lyrics_text", "style_note"}
REFERENCE_EXTENSIONS = {
    "audio_wav": {".wav"},
    "midi": {".mid", ".midi"},
    "lyrics_text": {".txt", ".md"},
    "style_note": {".txt", ".md"},
}
REFERENCE_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mid": "audio/midi",
    ".midi": "audio/midi",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,159}$")


@dataclass(frozen=True)
class ReferenceItem:
    schema_version: int
    reference_id: str
    reference_type: str
    title: str
    original_filename: str
    stored_filename: str
    extension: str
    media_type: str
    size_bytes: int
    sha256: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    tempo_bpm: int | None = None
    key: str = ""
    meter: str = ""
    favorite: bool = False
    hidden: bool = False
    usage_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    imported_at: str = ""
    source_note: str = ""
    license_note: str = ""
    text_excerpt: str = ""
    linked_project_ids: list[str] = field(default_factory=list)
    derived_asset_ids: list[str] = field(default_factory=list)
    metadata: ImplementationDocument = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "ReferenceItem":
        reference_id = validate_reference_id(str(data.get("reference_id") or "ref-001"))
        reference_type = str(data.get("reference_type") or "").strip()
        if reference_type not in REFERENCE_TYPES:
            raise ValueError(f"Unsupported reference_type: {reference_type}.")
        extension = _extension(str(data.get("extension") or Path(str(data.get("original_filename") or "")).suffix))
        if extension not in REFERENCE_EXTENSIONS[reference_type]:
            raise ValueError(f"{reference_type} does not support {extension} files.")
        size_bytes = int(data.get("size_bytes") or 0)
        _validate_size(reference_type, size_bytes)
        tempo = _optional_tempo(data.get("tempo_bpm"))
        sha256 = str(data.get("sha256") or "").strip().lower()
        if not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise ValueError("Invalid reference sha256.")
        return cls(
            schema_version=int(data.get("schema_version", REFERENCE_SCHEMA_VERSION) or REFERENCE_SCHEMA_VERSION),
            reference_id=reference_id,
            reference_type=reference_type,
            title=sanitize_sensitive_text(_bounded_text(data.get("title"), "title", 120)) or reference_id,
            original_filename=_safe_filename(str(data.get("original_filename") or f"reference{extension}"), strict=False),
            stored_filename=_stored_filename(reference_type, extension),
            extension=extension,
            media_type=REFERENCE_MEDIA_TYPES.get(extension, "application/octet-stream"),
            size_bytes=size_bytes,
            sha256=sha256,
            description=sanitize_sensitive_text(_bounded_text(data.get("description"), "description", 1000)),
            tags=_clean_tags(data.get("tags", [])),
            tempo_bpm=tempo,
            key=sanitize_sensitive_text(_bounded_text(data.get("key"), "key", 40)),
            meter=sanitize_sensitive_text(_bounded_text(data.get("meter"), "meter", 16)),
            favorite=bool(data.get("favorite", False)),
            hidden=bool(data.get("hidden", False)),
            usage_count=max(0, int(data.get("usage_count") or 0)),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or data.get("created_at") or ""),
            imported_at=str(data.get("imported_at") or data.get("created_at") or ""),
            source_note=sanitize_sensitive_text(_bounded_text(data.get("source_note"), "source_note", 1000)),
            license_note=sanitize_sensitive_text(_bounded_text(data.get("license_note"), "license_note", 1000)),
            text_excerpt=sanitize_sensitive_text(_bounded_text(data.get("text_excerpt"), "text_excerpt", 2000)),
            linked_project_ids=_clean_ids(data.get("linked_project_ids", []), "project"),
            derived_asset_ids=_clean_ids(data.get("derived_asset_ids", []), "asset"),
            metadata=sanitize_reference_metadata(dict(data.get("metadata") or {})),
        )

    def to_dict(self) -> DomainDocument:
        return asdict(self)


class ReferenceStore:
    def __init__(self, root: Path | str = REFERENCE_ROOT):
        self.root = Path(root)
        self.lock = threading.RLock()

    def list_references(self, include_hidden: bool = False, filters: DomainDocument | None = None) -> list[ReferenceItem]:
        filters = filters or {}
        references: list[ReferenceItem] = []
        if not self.root.exists():
            return []
        for path in self.root.glob("*/reference.json"):
            try:
                reference = ReferenceItem.from_dict(read_json(path))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if reference.hidden and not include_hidden:
                continue
            if _reference_matches(reference, filters):
                references.append(reference)
        return sorted(references, key=lambda item: item.updated_at or item.created_at, reverse=True)

    def read_reference(self, reference_id: str) -> ReferenceItem:
        path = self.reference_dir(reference_id) / "reference.json"
        if not path.exists():
            raise FileNotFoundError(reference_id)
        return ReferenceItem.from_dict(read_json(path))

    def import_reference(self, payload: DomainDocument, now: str | None = None) -> tuple[ReferenceItem, bool]:
        if not isinstance(payload, dict):
            raise ValueError("reference import payload must be an object.")
        now = now or now_iso()
        reference_type = str(payload.get("reference_type") or "").strip()
        if reference_type not in REFERENCE_TYPES:
            raise ValueError(f"Unsupported reference_type: {reference_type}.")
        filename = _safe_filename(str(payload.get("filename") or ""))
        extension = _extension(Path(filename).suffix)
        if extension not in REFERENCE_EXTENSIONS[reference_type]:
            raise ValueError(f"{reference_type} does not support {extension} files.")
        content = _decode_base64(payload.get("content_base64"))
        _validate_size(reference_type, len(content))
        text_excerpt = _validate_reference_content(reference_type, content)
        sha256 = hashlib.sha256(content).hexdigest()
        with self.lock:
            duplicate = self._find_by_sha256(sha256)
            if duplicate:
                return duplicate, True
            self.root.mkdir(parents=True, exist_ok=True)
            reference_id = self._next_reference_id()
            reference_dir = self.reference_dir(reference_id)
            data = {
                "schema_version": REFERENCE_SCHEMA_VERSION,
                "reference_id": reference_id,
                "reference_type": reference_type,
                "title": payload.get("title") or Path(filename).stem,
                "original_filename": filename,
                "stored_filename": _stored_filename(reference_type, extension),
                "extension": extension,
                "media_type": REFERENCE_MEDIA_TYPES.get(extension, "application/octet-stream"),
                "size_bytes": len(content),
                "sha256": sha256,
                "description": payload.get("description") or "",
                "tags": payload.get("tags") or [],
                "tempo_bpm": payload.get("tempo_bpm"),
                "key": payload.get("key") or "",
                "meter": payload.get("meter") or "",
                "favorite": bool(payload.get("favorite", False)),
                "hidden": False,
                "usage_count": 0,
                "created_at": now,
                "updated_at": now,
                "imported_at": now,
                "source_note": payload.get("source_note") or "",
                "license_note": payload.get("license_note") or "",
                "text_excerpt": text_excerpt,
                "linked_project_ids": _clean_ids(payload.get("linked_project_ids", []), "project"),
                "derived_asset_ids": [],
                "metadata": sanitize_reference_metadata(dict(payload.get("metadata") or {})),
            }
            reference = ReferenceItem.from_dict(data)
            try:
                reference_dir.mkdir(parents=True, exist_ok=False)
                original_dir = reference_dir / "original"
                original_dir.mkdir(parents=True, exist_ok=True)
                reference_file_path(reference_dir, reference).write_bytes(content)
                write_json(reference_dir / "reference.json", reference.to_dict())
                _append_reference_event(reference_dir, "reference_imported", {"reference_type": reference.reference_type, "size_bytes": reference.size_bytes}, now)
            except Exception:
                if reference_dir.exists() and not (reference_dir / "reference.json").exists():
                    shutil.rmtree(reference_dir)
                raise
            return reference, False

    def update_reference(self, reference_id: str, patch: DomainDocument) -> ReferenceItem:
        allowed = {"title", "description", "tags", "tempo_bpm", "key", "meter", "source_note", "license_note", "favorite"}
        if any(key not in allowed for key in patch):
            raise ValueError("Only reference metadata fields can be updated.")
        reference = self.read_reference(reference_id)
        updated = ReferenceItem.from_dict({**reference.to_dict(), **{key: patch[key] for key in patch if key in allowed}, "updated_at": now_iso()})
        self._write_reference(updated)
        _append_reference_event(self.reference_dir(reference_id), "reference_updated", {"fields": sorted(patch)}, updated.updated_at)
        return updated

    def hide_reference(self, reference_id: str, hidden: bool = True) -> ReferenceItem:
        reference = self.read_reference(reference_id)
        updated = ReferenceItem.from_dict({**reference.to_dict(), "hidden": hidden, "updated_at": now_iso()})
        self._write_reference(updated)
        _append_reference_event(self.reference_dir(reference_id), "reference_hidden" if hidden else "reference_unhidden", {}, updated.updated_at)
        return updated

    def favorite_reference(self, reference_id: str, favorite: bool = True) -> ReferenceItem:
        reference = self.read_reference(reference_id)
        updated = ReferenceItem.from_dict({**reference.to_dict(), "favorite": favorite, "updated_at": now_iso()})
        self._write_reference(updated)
        _append_reference_event(self.reference_dir(reference_id), "reference_favorited" if favorite else "reference_unfavorited", {}, updated.updated_at)
        return updated

    def delete_reference(self, reference_id: str) -> None:
        reference_dir = self.reference_dir(reference_id)
        if not reference_dir.exists():
            raise FileNotFoundError(reference_id)
        resolved = reference_dir.resolve()
        base = self.root.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to delete outside references.") from exc
        if resolved.is_symlink():
            raise ValueError("Refusing to delete symlink reference.")
        shutil.rmtree(resolved)

    def file_path(self, reference_id: str) -> Path:
        reference = self.read_reference(reference_id)
        path = reference_file_path(self.reference_dir(reference.reference_id), reference)
        if not path.exists():
            raise FileNotFoundError(reference.reference_id)
        return path

    def link_project(self, reference_id: str, project_id: str) -> ReferenceItem:
        reference = self.read_reference(reference_id)
        project_id = _validate_external_id(project_id, "project")
        linked = list(reference.linked_project_ids)
        if project_id not in linked:
            linked.append(project_id)
        updated = ReferenceItem.from_dict({**reference.to_dict(), "linked_project_ids": linked, "updated_at": now_iso()})
        self._write_reference(updated)
        _append_reference_event(self.reference_dir(reference_id), "reference_linked_project", {"project_id": project_id}, updated.updated_at)
        return updated

    def unlink_project(self, reference_id: str, project_id: str) -> ReferenceItem:
        reference = self.read_reference(reference_id)
        project_id = _validate_external_id(project_id, "project")
        linked = [item for item in reference.linked_project_ids if item != project_id]
        updated = ReferenceItem.from_dict({**reference.to_dict(), "linked_project_ids": linked, "updated_at": now_iso()})
        self._write_reference(updated)
        _append_reference_event(self.reference_dir(reference_id), "reference_unlinked_project", {"project_id": project_id}, updated.updated_at)
        return updated

    def mark_used(self, reference_refs: list[DomainDocument], context: DomainDocument | None = None) -> list[DomainDocument]:
        refs = resolve_reference_refs(self, reference_refs)
        now = now_iso()
        for ref in refs:
            reference = self.read_reference(ref["reference_id"])
            updated = ReferenceItem.from_dict({**reference.to_dict(), "usage_count": reference.usage_count + 1, "updated_at": now})
            self._write_reference(updated)
            _append_reference_event(self.reference_dir(reference.reference_id), "reference_used", {**(context or {}), "role": ref.get("role"), "strength": ref.get("strength")}, now)
        return refs

    def create_asset_from_reference(self, reference_id: str, payload: DomainDocument, asset_store: AssetStore) -> DomainDocument:
        reference = self.read_reference(reference_id)
        if reference.hidden:
            raise ValueError("Hidden references cannot be converted to assets.")
        if reference.reference_type == "audio_wav":
            raise ValueError("audio_wav references cannot be converted to assets in v1.7.0.")
        asset_payload = reference_to_asset_payload(reference, payload)
        asset = asset_store.create_asset(asset_payload)
        linked = list(reference.derived_asset_ids)
        if asset.asset_id not in linked:
            linked.append(asset.asset_id)
        updated = ReferenceItem.from_dict({**reference.to_dict(), "derived_asset_ids": linked, "updated_at": now_iso()})
        self._write_reference(updated)
        _append_reference_event(self.reference_dir(reference_id), "reference_asset_created", {"asset_id": asset.asset_id}, updated.updated_at)
        return asset_public_dict(asset)

    def reference_dir(self, reference_id: str) -> Path:
        reference_id = validate_reference_id(reference_id)
        base = self.root.resolve()
        raw_target = base / reference_id
        if raw_target.is_symlink():
            raise ValueError("Refusing to operate on symlink reference.")
        target = raw_target.resolve()
        try:
            target.relative_to(base)
        except ValueError as exc:
            raise ValueError("Refusing to operate outside references.") from exc
        return target

    def _write_reference(self, reference: ReferenceItem) -> ReferenceItem:
        write_json(self.reference_dir(reference.reference_id) / "reference.json", reference.to_dict())
        return reference

    def _find_by_sha256(self, sha256: str) -> ReferenceItem | None:
        for reference in self.list_references(include_hidden=True):
            if reference.sha256 == sha256:
                return reference
        return None

    def _next_reference_id(self) -> str:
        for index in range(1, 1_000_000):
            reference_id = f"ref-{index:03d}"
            if not (self.root / reference_id).exists():
                return reference_id
        raise RuntimeError("Could not allocate reference id.")


def resolve_reference_refs(store: ReferenceStore, raw_refs: Any) -> list[DomainDocument]:
    if raw_refs is None:
        return []
    if not isinstance(raw_refs, list):
        raise ValueError("reference_refs must be a list.")
    if len(raw_refs) > MAX_REFERENCE_REFS:
        raise ValueError(f"reference_refs supports at most {MAX_REFERENCE_REFS} references.")
    refs = []
    seen = set()
    for item in raw_refs:
        if not isinstance(item, dict):
            raise ValueError("reference_refs items must be objects.")
        reference_id = validate_reference_id(str(item.get("reference_id") or ""))
        if reference_id in seen:
            continue
        seen.add(reference_id)
        reference = store.read_reference(reference_id)
        if reference.hidden:
            raise ValueError("Hidden references cannot be used.")
        ref = {
            "reference_id": reference.reference_id,
            "reference_type": reference.reference_type,
            "title": reference.title,
            "role": _bounded_text(item.get("role"), "role", 80) or _default_reference_role(reference.reference_type),
            "strength": _strength(item.get("strength")),
            "sha256": reference.sha256,
            "size_bytes": reference.size_bytes,
            "metadata_summary": reference_metadata_summary(reference),
        }
        try:
            from song_agent.domains.studio.reference_analysis import reference_analysis_summary_for_export

            analysis_summary = reference_analysis_summary_for_export(store, reference.reference_id)
            if analysis_summary:
                ref["analysis_summary"] = analysis_summary
        except (OSError, ValueError, TypeError):
            pass
        refs.append(ref)
    return refs


def reference_refs_snapshot(store: ReferenceStore, raw_refs: Any, *, captured_at: str | None = None) -> DomainDocument:
    refs = resolve_reference_refs(store, raw_refs)
    return {"schema_version": 1, "reference_refs": refs, "captured_at": captured_at or now_iso()}


def reference_prompt_summaries(store: ReferenceStore, raw_refs: Any) -> list[DomainDocument]:
    summaries = []
    for ref in resolve_reference_refs(store, raw_refs):
        reference = store.read_reference(ref["reference_id"])
        summaries.append(
            {
                "reference_id": reference.reference_id,
                "reference_type": reference.reference_type,
                "title": reference.title,
                "tags": list(reference.tags),
                "role": ref["role"],
                "strength": ref["strength"],
                "summary": reference_metadata_summary(reference),
                "analysis_summary": ref.get("analysis_summary"),
            }
        )
    try:
        from song_agent.domains.studio.reference_analysis import provider_reference_summaries_with_analysis

        return provider_reference_summaries_with_analysis(store, summaries)
    except (OSError, ValueError, TypeError):
        return summaries


def write_reference_refs_snapshot(run_dir: Path, snapshot: DomainDocument) -> Path:
    return write_json(run_dir / "data" / "reference-refs.json", snapshot)


def reference_metadata_summary(reference: ReferenceItem) -> DomainDocument:
    summary = {
        "description": reference.description,
        "tags": list(reference.tags),
        "tempo_bpm": reference.tempo_bpm,
        "key": reference.key,
        "meter": reference.meter,
        "source_note": reference.source_note,
        "license_note": reference.license_note,
        "text_excerpt": reference.text_excerpt,
    }
    return sanitize_reference_metadata({key: value for key, value in summary.items() if value is not None and value != "" and value != []})


def reference_public_dict(reference: ReferenceItem) -> DomainDocument:
    data = reference.to_dict()
    data["metadata"] = sanitize_reference_metadata(dict(data.get("metadata") or {}))
    data["file_url"] = reference_file_url(reference.reference_id)
    return data


def reference_to_asset_payload(reference: ReferenceItem, payload: DomainDocument) -> DomainDocument:
    asset_type = str(payload.get("asset_type") or "").strip()
    if reference.reference_type in {"lyrics_text", "style_note"}:
        if not asset_type:
            asset_type = "lyric_hook" if reference.reference_type == "lyrics_text" else "section_template"
        if asset_type not in {"lyric_hook", "section_template", "arrangement_template"}:
            raise ValueError("Text references can create lyric_hook, section_template, or arrangement_template assets.")
        text = _read_text_excerpt(reference, payload)
        content: ImplementationDocument = {
            "kind": asset_type,
            "reference_id": reference.reference_id,
            "text": text,
            "source_reference_type": reference.reference_type,
        }
        if asset_type == "section_template":
            content.update({"section_name": "reference", "bars": 8, "chords": ["Cmaj7", "Am7", "Fmaj7", "G7"]})
        if asset_type == "arrangement_template":
            content.update({"sections": [], "tracks": []})
    elif reference.reference_type == "midi":
        if not asset_type:
            asset_type = "motif"
        if asset_type not in {"motif", "chord_progression", "drum_pattern", "bass_pattern"}:
            raise ValueError("MIDI references can create motif, chord_progression, drum_pattern, or bass_pattern assets.")
        content = _midi_seed_content(reference, asset_type)
    else:
        raise ValueError(f"{reference.reference_type} references cannot be converted to assets.")
    return {
        "asset_type": asset_type,
        "name": _bounded_text(payload.get("name"), "name", 120) or f"{reference.title} seed",
        "description": _bounded_text(payload.get("description"), "description", 1000) or f"Created from reference {reference.reference_id}.",
        "tags": _clean_tags(payload.get("tags", reference.tags)),
        "key": reference.key or "C",
        "tempo_bpm": reference.tempo_bpm or 92,
        "meter": reference.meter or "4/4",
        "duration_beats": float(payload.get("duration_beats") or 8.0),
        "favorite": bool(payload.get("favorite", False)),
        "source": {
            "source_type": "reference",
            "reference_id": reference.reference_id,
            "reference_type": reference.reference_type,
            "sha256": reference.sha256,
        },
        "content": content,
    }


def reference_file_url(reference_id: str) -> str:
    return f"/api/references/{reference_id}/file"


def validate_reference_id(reference_id: str) -> str:
    if not REFERENCE_ID_PATTERN.match(reference_id):
        raise ValueError("Invalid reference id.")
    return reference_id


def sanitize_reference_metadata(value: Any) -> Any:
    return sanitize_asset_metadata(value)


from song_agent.domains.studio import v142_r_readiness as _v142_r_readiness
from song_agent.domains.studio.v142_r_readiness import _decode_base64 as _decode_base64, _validate_reference_content as _validate_reference_content, _validate_size as _validate_size, _safe_filename as _safe_filename, _filename_is_safe as _filename_is_safe, _fallback_safe_filename as _fallback_safe_filename, _extension as _extension, _stored_filename as _stored_filename, _clean_tags as _clean_tags, _clean_ids as _clean_ids, _validate_external_id as _validate_external_id, _bounded_text as _bounded_text, _optional_tempo as _optional_tempo, _reference_matches as _reference_matches, _strength as _strength, _default_reference_role as _default_reference_role, _read_text_excerpt as _read_text_excerpt, _midi_seed_content as _midi_seed_content, _append_reference_event as _append_reference_event

_v142_r_readiness.bind_globals(globals())
