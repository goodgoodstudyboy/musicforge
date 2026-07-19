# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or

import csv as csv
import hashlib as hashlib
import io as io
import json as json
import os as os
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any

from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseDocument as ReleaseDocument, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash


RELEASE_METADATA_SCHEMA_VERSION = 1
METADATA_EXPORT_SCHEMA_VERSION = 1
METADATA_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}
METADATA_EXPORT_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}
CREDIT_ROLES = {
    "composer",
    "lyricist",
    "producer",
    "arranger",
    "performer",
    "vocalist",
    "mixing_engineer",
    "mastering_engineer",
    "recording_engineer",
    "programmer",
    "other",
}
PLATFORM_CSV_FIELDS = [
    "disc_number",
    "track_number",
    "title",
    "display_artist",
    "primary_artist",
    "featured_artists",
    "version_subtitle",
    "isrc",
    "explicit",
    "instrumental",
    "language",
    "upc",
    "label",
    "release_date",
    "copyright",
    "phonographic_copyright",
]
CREDITS_CSV_FIELDS = ["track_id", "disc_number", "track_number", "track_title", "role", "name", "affiliation", "source"]


class ReleaseMetadataError(ValueError):
    pass


@dataclass
class CreditRole:
    role: str
    name: str
    affiliation: str | None = None
    source: str = "user"

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "role": self.role,
                "name": self.name,
                "affiliation": self.affiliation,
                "source": self.source,
            },
            blocked_keys=METADATA_BLOCKED_KEYS,
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "CreditRole":
        role = _safe_text(data.get("role"), 80) or "other"
        if role not in CREDIT_ROLES:
            role = "other"
        return cls(
            role=role,
            name=_safe_text(data.get("name"), 160),
            affiliation=_optional_text(data.get("affiliation"), 160),
            source=_safe_text(data.get("source"), 80) or "user",
        )


@dataclass
class ReleaseMetadata:
    title: str
    display_artist: str
    primary_artist: str
    label: str | None = None
    release_type: str = "demo_pack"
    language: str | None = None
    release_date: str | None = None
    upc: str | None = None
    copyright: str | None = None
    phonographic_copyright: str | None = None
    territories_note: str | None = None
    rights_note: str | None = None
    notes: str | None = None
    confirmed: bool = False

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "title": self.title,
                "display_artist": self.display_artist,
                "primary_artist": self.primary_artist,
                "label": self.label,
                "release_type": self.release_type,
                "language": self.language,
                "release_date": self.release_date,
                "upc": self.upc,
                "copyright": self.copyright,
                "phonographic_copyright": self.phonographic_copyright,
                "territories_note": self.territories_note,
                "rights_note": self.rights_note,
                "notes": self.notes,
                "confirmed": self.confirmed,
            },
            blocked_keys=METADATA_BLOCKED_KEYS,
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "ReleaseMetadata":
        return cls(
            title=_safe_text(data.get("title"), 160),
            display_artist=_safe_text(data.get("display_artist"), 160),
            primary_artist=_safe_text(data.get("primary_artist"), 160),
            label=_optional_text(data.get("label"), 160),
            release_type=_safe_text(data.get("release_type"), 80) or "demo_pack",
            language=_optional_text(data.get("language"), 80),
            release_date=_optional_text(data.get("release_date"), 32),
            upc=_optional_text(data.get("upc"), 32),
            copyright=_optional_text(data.get("copyright"), 240),
            phonographic_copyright=_optional_text(data.get("phonographic_copyright"), 240),
            territories_note=_optional_text(data.get("territories_note"), 500),
            rights_note=_optional_text(data.get("rights_note"), 1000),
            notes=_optional_text(data.get("notes"), 2000),
            confirmed=bool(data.get("confirmed", False)),
        )


@dataclass
class TrackMetadata:
    track_id: str
    disc_number: int
    track_number: int
    title: str
    display_artist: str
    primary_artist: str
    featured_artists: list[str] = field(default_factory=list)
    version_subtitle: str | None = None
    isrc: str | None = None
    explicit: bool = False
    instrumental: bool = False
    language: str | None = None
    lyrics: str | None = None
    credits: list[CreditRole] = field(default_factory=list)
    copyright: str | None = None
    rights_note: str | None = None
    confirmed: bool = False

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "track_id": self.track_id,
                "disc_number": self.disc_number,
                "track_number": self.track_number,
                "title": self.title,
                "display_artist": self.display_artist,
                "primary_artist": self.primary_artist,
                "featured_artists": self.featured_artists,
                "version_subtitle": self.version_subtitle,
                "isrc": self.isrc,
                "explicit": self.explicit,
                "instrumental": self.instrumental,
                "language": self.language,
                "lyrics": self.lyrics,
                "credits": [credit.to_dict() for credit in self.credits],
                "copyright": self.copyright,
                "rights_note": self.rights_note,
                "confirmed": self.confirmed,
            },
            blocked_keys=METADATA_BLOCKED_KEYS,
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "TrackMetadata":
        return cls(
            track_id=_safe_text(data.get("track_id"), 80),
            disc_number=max(1, _safe_int(data.get("disc_number"), 1)),
            track_number=max(1, _safe_int(data.get("track_number"), 1)),
            title=_safe_text(data.get("title"), 160),
            display_artist=_safe_text(data.get("display_artist"), 160),
            primary_artist=_safe_text(data.get("primary_artist"), 160),
            featured_artists=[_safe_text(item, 160) for item in data.get("featured_artists", []) if _safe_text(item, 160)],
            version_subtitle=_optional_text(data.get("version_subtitle"), 120),
            isrc=_optional_text(data.get("isrc"), 32),
            explicit=bool(data.get("explicit", False)),
            instrumental=bool(data.get("instrumental", False)),
            language=_optional_text(data.get("language"), 80),
            lyrics=_optional_text(data.get("lyrics"), 120_000),
            credits=[CreditRole.from_dict(item) for item in data.get("credits", []) if isinstance(item, dict)],
            copyright=_optional_text(data.get("copyright"), 240),
            rights_note=_optional_text(data.get("rights_note"), 1000),
            confirmed=bool(data.get("confirmed", False)),
        )


@dataclass
class ReleaseMetadataDocument:
    schema_version: int
    release_id: str
    updated_at: str
    release: ReleaseMetadata
    tracks: list[TrackMetadata]
    source_summary: ImplementationDocument = field(default_factory=dict)

    def to_dict(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "release_id": self.release_id,
                "updated_at": self.updated_at,
                "release": self.release.to_dict(),
                "tracks": [track.to_dict() for track in sorted(self.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id))],
                "source_summary": self.source_summary,
            },
            blocked_keys=METADATA_BLOCKED_KEYS,
        )

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "ReleaseMetadataDocument":
        return cls(
            schema_version=int(data.get("schema_version", RELEASE_METADATA_SCHEMA_VERSION) or RELEASE_METADATA_SCHEMA_VERSION),
            release_id=_safe_text(data.get("release_id"), 80),
            updated_at=_safe_text(data.get("updated_at"), 80) or now_iso(),
            release=ReleaseMetadata.from_dict(_as_document(data.get("release"))),
            tracks=[TrackMetadata.from_dict(item) for item in data.get("tracks", []) if isinstance(item, dict)],
            source_summary=sanitize_metadata(_as_document(data.get("source_summary")), blocked_keys=METADATA_BLOCKED_KEYS),
        )


def release_metadata_path(release_store: ReleaseStore, release_id: str) -> Path:
    return release_store.release_dir(release_id) / "metadata.json"


def release_metadata_history_path(release_store: ReleaseStore, release_id: str) -> Path:
    return release_store.release_dir(release_id) / "metadata-history.jsonl"


def release_metadata_qa_path(release_store: ReleaseStore, release_id: str) -> Path:
    return release_store.release_dir(release_id) / "metadata-qa.json"


def read_release_metadata(
    release_store: ReleaseStore,
    release_id: str,
    *,
    default: DomainDocument | None = None,
) -> DomainDocument:
    release_store.get_release(release_id)
    path = release_metadata_path(release_store, release_id)
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError("Release metadata does not exist.")
    value = read_json(path)
    return ReleaseMetadataDocument.from_dict(_as_document(value)).to_dict()


def write_release_metadata(
    release_store: ReleaseStore,
    release_id: str,
    payload: DomainDocument,
    *,
    now: str | None = None,
    event_type: str = "release_metadata_saved",
) -> DomainDocument:
    now = now or now_iso()
    release = release_store.get_release(release_id)
    _ensure_release_metadata_mutable(release)
    source_summary = _document_or(payload.get("source_summary"), _source_summary(release, release_store.project_store))
    document = ReleaseMetadataDocument.from_dict(
        {
            **payload,
            "schema_version": RELEASE_METADATA_SCHEMA_VERSION,
            "release_id": release_id,
            "updated_at": now,
            "source_summary": source_summary,
        }
    )
    clean = document.to_dict()
    write_json(release_metadata_path(release_store, release_id), clean)
    append_release_metadata_history(release_store, release_id, event_type, {"source_hash": release_metadata_source_hash(release, clean)}, now=now)
    mark_release_export_stale_for_metadata(release_store, release_id)
    return clean


def initialize_release_metadata(
    release_store: ReleaseStore,
    release_id: str,
    *,
    force: bool = False,
    merge: bool = False,
    now: str | None = None,
) -> DomainDocument:
    now = now or now_iso()
    release = release_store.get_release(release_id)
    _ensure_release_metadata_mutable(release)
    path = release_metadata_path(release_store, release_id)
    inferred = _metadata_from_release(release, release_store.project_store, now=now)
    if path.exists() and not force:
        existing = read_release_metadata(release_store, release_id)
        if not merge:
            return existing
        merged = _merge_missing_metadata(existing, inferred)
        if merged == existing:
            return existing
        return write_release_metadata(release_store, release_id, merged, now=now, event_type="release_metadata_merged")
    return write_release_metadata(release_store, release_id, inferred, now=now, event_type="release_metadata_initialized")


def append_release_metadata_history(release_store: ReleaseStore, release_id: str, event_type: str, payload: DomainDocument, *, now: str | None = None) -> None:
    release_store.get_release(release_id)
    path = release_metadata_history_path(release_store, release_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"timestamp": now or now_iso(), "type": event_type, "payload": payload}, blocked_keys=METADATA_BLOCKED_KEYS)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
    release_store.append_event(release_id, event_type, _as_document(event.get("payload")))


def read_release_metadata_history(release_store: ReleaseStore, release_id: str) -> list[DomainDocument]:
    release_store.get_release(release_id)
    path = release_metadata_history_path(release_store, release_id)
    if not path.exists():
        return []
    events: list[ImplementationDocument] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return sanitize_metadata(events, blocked_keys=METADATA_BLOCKED_KEYS)


def read_release_metadata_qa(release_store: ReleaseStore, release_id: str, *, default: DomainDocument | None = None) -> DomainDocument:
    release_store.get_release(release_id)
    path = release_metadata_qa_path(release_store, release_id)
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError("Release metadata QA does not exist.")
    value = read_json(path)
    return sanitize_metadata(_as_document(value), blocked_keys=METADATA_BLOCKED_KEYS)


def write_release_metadata_qa(release_store: ReleaseStore, release_id: str, report: DomainDocument) -> DomainDocument:
    release_store.get_release(release_id)
    clean = sanitize_metadata(report, blocked_keys=METADATA_BLOCKED_KEYS)
    write_json(release_metadata_qa_path(release_store, release_id), clean)
    return clean


def release_metadata_source_hash(release: ReleaseDocument, metadata: DomainDocument | None) -> str:
    return stable_hash(
        {
            "release": {
                "release_id": release.release_id,
                "name": release.name,
                "release_type": release.release_type,
                "primary_artist": release.primary_artist,
                "label": release.label,
                "language": release.language,
                "tracks": [
                    {
                        "track_id": track.track_id,
                        "disc_number": track.disc_number,
                        "track_number": track.track_number,
                        "title": track.title,
                        "artist": track.artist,
                        "project_id": track.project_id,
                        "version_id": track.version_id,
                    }
                    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id))
                ],
            },
            "metadata": metadata or {},
        }
    )


def release_metadata_summary(metadata: DomainDocument | None, qa_report: DomainDocument | None = None, export_summary: DomainDocument | None = None) -> DomainDocument:
    data = _as_document(metadata)
    release = _as_document(data.get("release"))
    tracks = _as_list(data.get("tracks"))
    qa = _as_document(qa_report)
    qa_summary = _as_document(qa.get("summary"))
    export_data = _as_document(export_summary)
    return sanitize_metadata(
        {
            "exists": bool(data),
            "release_id": data.get("release_id"),
            "title": release.get("title"),
            "display_artist": release.get("display_artist"),
            "track_count": len(tracks),
            "confirmed_track_count": sum(1 for item in tracks if isinstance(item, dict) and item.get("confirmed")),
            "qa_status": qa.get("status") or qa_summary.get("status"),
            "export_status": export_data.get("status"),
            "payload_hash": stable_hash(data) if data else None,
            "updated_at": data.get("updated_at"),
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )


def metadata_qa_allows_export(report: DomainDocument | None, *, current_source_hash: str | None = None) -> bool:
    if not isinstance(report, dict):
        return False
    if report.get("status") not in {"passed", "warning"}:
        return False
    if current_source_hash and report.get("source_hash") != current_source_hash:
        return False
    return True


def metadata_export_summary(manifest: DomainDocument | None = None) -> DomainDocument:
    data = _as_document(manifest)
    metadata = _as_document(data.get("metadata"))
    return sanitize_metadata(
        {
            "status": "exported" if metadata.get("exists") else "missing",
            "exists": bool(metadata.get("exists")),
            "qa_status": metadata.get("qa_status"),
            "track_count": metadata.get("track_count", 0),
            "file_count": len(metadata.get("files", [])) if isinstance(metadata.get("files"), list) else 0,
            "payload_hash": metadata.get("payload_hash"),
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )


from song_agent.domains.delivery import v142_rm_readiness as _v142_rm_readiness
from song_agent.domains.delivery.v142_rm_readiness import (
    export_release_metadata_files,
    attach_metadata_export_to_manifest,
    mark_release_export_stale_for_metadata,
    _metadata_from_release,
    _merge_missing_metadata,
    _source_summary,
    _track_plan,
    _extract_lyrics,
    _duration_beats,
    _write_platform_csv,
    _write_credits_csv,
    _write_csv,
    _write_lyrics,
    _write_text,
    _file_record,
    _sha256,
    _validate_relative_path,
    _ensure_within,
    _qa_summary,
    _ensure_release_metadata_mutable,
    _safe_int,
    _safe_text,
    _optional_text,
)

_v142_rm_readiness.bind_globals(globals())
