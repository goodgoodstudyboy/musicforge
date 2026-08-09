from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document, _as_list, _document_or

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

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "CreditRole":
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

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseMetadata":
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

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "TrackMetadata":
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
    source_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseMetadataDocument":
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
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    payload: dict[str, Any],
    *,
    now: str | None = None,
    event_type: str = "release_metadata_saved",
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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


def append_release_metadata_history(release_store: ReleaseStore, release_id: str, event_type: str, payload: dict[str, Any], *, now: str | None = None) -> None:
    release_store.get_release(release_id)
    path = release_metadata_history_path(release_store, release_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = sanitize_metadata({"timestamp": now or now_iso(), "type": event_type, "payload": payload}, blocked_keys=METADATA_BLOCKED_KEYS)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False) + "\n")
    release_store.append_event(release_id, event_type, _as_document(event.get("payload")))


def read_release_metadata_history(release_store: ReleaseStore, release_id: str) -> list[dict[str, Any]]:
    release_store.get_release(release_id)
    path = release_metadata_history_path(release_store, release_id)
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
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


def read_release_metadata_qa(release_store: ReleaseStore, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    release_store.get_release(release_id)
    path = release_metadata_qa_path(release_store, release_id)
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError("Release metadata QA does not exist.")
    value = read_json(path)
    return sanitize_metadata(_as_document(value), blocked_keys=METADATA_BLOCKED_KEYS)


def write_release_metadata_qa(release_store: ReleaseStore, release_id: str, report: dict[str, Any]) -> dict[str, Any]:
    release_store.get_release(release_id)
    clean = sanitize_metadata(report, blocked_keys=METADATA_BLOCKED_KEYS)
    write_json(release_metadata_qa_path(release_store, release_id), clean)
    return clean


def release_metadata_source_hash(release: ReleaseDocument, metadata: dict[str, Any] | None) -> str:
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


def release_metadata_summary(metadata: dict[str, Any] | None, qa_report: dict[str, Any] | None = None, export_summary: dict[str, Any] | None = None) -> dict[str, Any]:
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


def metadata_qa_allows_export(report: dict[str, Any] | None, *, current_source_hash: str | None = None) -> bool:
    if not isinstance(report, dict):
        return False
    if report.get("status") not in {"passed", "warning"}:
        return False
    if current_source_hash and report.get("source_hash") != current_source_hash:
        return False
    return True


def metadata_export_summary(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
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


def export_release_metadata_files(
    *,
    release_store: ReleaseStore,
    release_id: str,
    qa_report: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    release = release_store.get_release(release_id)
    metadata = read_release_metadata(release_store, release_id)
    current_hash = release_metadata_source_hash(release, metadata)
    if not metadata_qa_allows_export(qa_report, current_source_hash=current_hash):
        raise ReleaseMetadataError("Release Metadata QA gate failed. Refresh metadata QA before export.")
    export_dir = release_store.export_dir(release_id).resolve()
    release_dir = release_store.release_dir(release_id).resolve()
    _ensure_within(release_dir, export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    clean_metadata = ReleaseMetadataDocument.from_dict(metadata).to_dict()
    qa_summary = _qa_summary(qa_report)
    export_payload = sanitize_metadata(
        {
            "schema_version": METADATA_EXPORT_SCHEMA_VERSION,
            "release_id": release_id,
            "release": clean_metadata.get("release", {}),
            "tracks": clean_metadata.get("tracks", []),
            "metadata_qa_summary": qa_summary,
            "generated_at": now,
        },
        blocked_keys=METADATA_EXPORT_BLOCKED_KEYS,
    )
    write_json(export_dir / "release-metadata.json", export_payload)
    _write_platform_csv(export_dir / "platform-metadata.csv", clean_metadata)
    _write_credits_csv(export_dir / "credits.csv", clean_metadata)
    lyric_files = _write_lyrics(export_dir / "lyrics", clean_metadata)
    files = ["release-metadata.json", "platform-metadata.csv", "credits.csv", *lyric_files]
    return sanitize_metadata(
        {
            "exists": True,
            "qa_status": qa_report.get("status"),
            "source_hash": current_hash,
            "track_count": len(clean_metadata.get("tracks", [])),
            "files": files,
            "payload_hash": stable_hash(export_payload),
            "generated_at": now,
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )


def attach_metadata_export_to_manifest(release_store: ReleaseStore, release_id: str, metadata_export: dict[str, Any]) -> dict[str, Any]:
    export_dir = release_store.export_dir(release_id).resolve()
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Release export has not been generated.")
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        manifest = {}
    metadata_paths = set(str(path) for path in metadata_export.get("files", []) if str(path).strip())
    metadata_prefixes = ("lyrics/",)
    generated_metadata_files = {"release-metadata.json", "platform-metadata.csv", "credits.csv"}
    existing_files = [
        item
        for item in manifest.get("files", [])
        if isinstance(item, dict)
        and str(item.get("path") or "") not in metadata_paths
        and str(item.get("path") or "") not in generated_metadata_files
        and not str(item.get("path") or "").startswith(metadata_prefixes)
    ]
    new_files = [_file_record(export_dir, export_dir / str(path)) for path in metadata_export.get("files", []) if str(path).strip()]
    files = sorted([*existing_files, *new_files], key=lambda item: item["path"])
    manifest["files"] = files
    manifest["metadata"] = metadata_export
    summary = _as_document(manifest.get("summary"))
    summary["file_count"] = len(files)
    summary["total_bytes"] = sum(int(item.get("size_bytes") or 0) for item in files)
    summary["metadata_status"] = metadata_export.get("qa_status")
    manifest["summary"] = summary
    if isinstance(manifest.get("zip"), dict):
        manifest["zip"] = {"status": "stale", "reason": "metadata_export_updated"}
    write_json(manifest_path, sanitize_metadata(manifest, blocked_keys=METADATA_EXPORT_BLOCKED_KEYS))
    return sanitize_metadata(read_json(manifest_path), blocked_keys=METADATA_EXPORT_BLOCKED_KEYS)


def mark_release_export_stale_for_metadata(release_store: ReleaseStore, release_id: str) -> None:
    document = release_store.get_release(release_id)
    summary = dict(document.latest_export_summary or {})
    if summary:
        summary["stale"] = True
        if summary.get("status") in {"exported", "passed", "warning"}:
            summary["status"] = "stale"
        summary["stale_reason"] = "metadata_changed"
        release_store.update_export_summary(release_id, summary)


def _metadata_from_release(release: ReleaseDocument, project_store: ProjectStore, *, now: str) -> ImplementationDocument:
    tracks = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        plan = _track_plan(project_store, track.project_id)
        language = _optional_text(plan.get("language"), 80) or release.language
        lyrics = _extract_lyrics(plan)
        tracks.append(
            TrackMetadata(
                track_id=track.track_id,
                disc_number=track.disc_number,
                track_number=track.track_number,
                title=track.title,
                display_artist=track.artist or release.primary_artist,
                primary_artist=track.artist or release.primary_artist,
                language=language,
                lyrics=lyrics,
            ).to_dict()
        )
    document = ReleaseMetadataDocument(
        schema_version=RELEASE_METADATA_SCHEMA_VERSION,
        release_id=release.release_id,
        updated_at=now,
        release=ReleaseMetadata(
            title=release.name,
            display_artist=release.primary_artist,
            primary_artist=release.primary_artist,
            label=release.label,
            release_type=release.release_type,
            language=release.language,
        ),
        tracks=[TrackMetadata.from_dict(item) for item in tracks],
        source_summary=_source_summary(release, project_store),
    )
    return document.to_dict()


def _merge_missing_metadata(existing: ImplementationDocument, inferred: ImplementationDocument) -> ImplementationDocument:
    merged = json.loads(json.dumps(existing, ensure_ascii=False))
    release_existing = merged.setdefault("release", {})
    release_inferred = _as_document(inferred.get("release"))
    for key, value in release_inferred.items():
        if release_existing.get(key) in (None, "", []):
            release_existing[key] = value
    by_id = {item.get("track_id"): item for item in merged.get("tracks", []) if isinstance(item, dict)}
    for inferred_track in inferred.get("tracks", []) if isinstance(inferred.get("tracks"), list) else []:
        if not isinstance(inferred_track, dict):
            continue
        existing_track = by_id.get(inferred_track.get("track_id"))
        if existing_track is None:
            merged.setdefault("tracks", []).append(inferred_track)
            continue
        for key, value in inferred_track.items():
            if existing_track.get(key) in (None, "", []):
                existing_track[key] = value
    merged["source_summary"] = inferred.get("source_summary", {})
    return ReleaseMetadataDocument.from_dict(merged).to_dict()


def _source_summary(release: ReleaseDocument, project_store: ProjectStore) -> ImplementationDocument:
    tracks: list[dict[str, Any]] = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        plan = _track_plan(project_store, track.project_id)
        tracks.append(
            sanitize_metadata(
                {
                    "track_id": track.track_id,
                    "project_id": track.project_id,
                    "version_id": track.version_id,
                    "tempo_bpm": plan.get("tempo_bpm"),
                    "key": plan.get("key"),
                    "language": plan.get("language"),
                    "duration_beats": _duration_beats(plan),
                },
                blocked_keys=METADATA_BLOCKED_KEYS,
            )
        )
    return sanitize_metadata(
        {
            "release_id": release.release_id,
            "release_updated_at": release.updated_at,
            "track_count": len(release.tracks),
            "tracks": tracks,
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )


def _track_plan(project_store: ProjectStore, project_id: str) -> ImplementationDocument:
    try:
        path = final_export_dir(project_store.project_dir(project_id)) / "song-plan.json"
        value = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return _as_document(value)


def _extract_lyrics(plan: ImplementationDocument) -> str | None:
    for key in ("lyrics", "lyric", "vocal_lyrics"):
        value = plan.get(key)
        if isinstance(value, str) and value.strip():
            return _optional_text(value, 120_000)
    sections = _as_list(plan.get("sections"))
    lines: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        for key in ("lyrics", "lyric"):
            value = section.get(key)
            if isinstance(value, str) and value.strip():
                lines.append(value.strip())
    return _optional_text("\n\n".join(lines), 120_000) if lines else None


def _duration_beats(plan: ImplementationDocument) -> float | None:
    sections = _as_list(plan.get("sections"))
    values: list[float] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        try:
            values.append(float(section.get("start_beat", 0) or 0) + float(section.get("length_bars", 0) or 0) * 4)
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


def _write_platform_csv(path: Path, metadata: ImplementationDocument) -> None:
    release = _as_document(metadata.get("release"))
    rows = []
    for track in metadata.get("tracks", []) if isinstance(metadata.get("tracks"), list) else []:
        if not isinstance(track, dict):
            continue
        rows.append(
            {
                "disc_number": track.get("disc_number"),
                "track_number": track.get("track_number"),
                "title": track.get("title"),
                "display_artist": track.get("display_artist"),
                "primary_artist": track.get("primary_artist"),
                "featured_artists": "; ".join(track.get("featured_artists", []) if isinstance(track.get("featured_artists"), list) else []),
                "version_subtitle": track.get("version_subtitle"),
                "isrc": track.get("isrc"),
                "explicit": "true" if track.get("explicit") else "false",
                "instrumental": "true" if track.get("instrumental") else "false",
                "language": track.get("language") or release.get("language"),
                "upc": release.get("upc"),
                "label": release.get("label"),
                "release_date": release.get("release_date"),
                "copyright": track.get("copyright") or release.get("copyright"),
                "phonographic_copyright": release.get("phonographic_copyright"),
            }
        )
    _write_csv(path, PLATFORM_CSV_FIELDS, rows)


def _write_credits_csv(path: Path, metadata: ImplementationDocument) -> None:
    rows = []
    for track in metadata.get("tracks", []) if isinstance(metadata.get("tracks"), list) else []:
        if not isinstance(track, dict):
            continue
        for credit in track.get("credits", []) if isinstance(track.get("credits"), list) else []:
            if not isinstance(credit, dict):
                continue
            rows.append(
                {
                    "track_id": track.get("track_id"),
                    "disc_number": track.get("disc_number"),
                    "track_number": track.get("track_number"),
                    "track_title": track.get("title"),
                    "role": credit.get("role"),
                    "name": credit.get("name"),
                    "affiliation": credit.get("affiliation"),
                    "source": credit.get("source"),
                }
            )
    _write_csv(path, CREDITS_CSV_FIELDS, rows)


def _write_csv(path: Path, fields: list[str], rows: list[ImplementationDocument]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: sanitize_sensitive_text(str(row.get(key) or "")) for key in fields})
    _write_text(path, buffer.getvalue())


def _write_lyrics(lyrics_dir: Path, metadata: ImplementationDocument) -> list[str]:
    if lyrics_dir.exists():
        for file in sorted(lyrics_dir.rglob("*"), reverse=True):
            if file.is_file():
                file.unlink()
            elif file.is_dir():
                try:
                    file.rmdir()
                except OSError:
                    pass
    written: list[str] = []
    for track in metadata.get("tracks", []) if isinstance(metadata.get("tracks"), list) else []:
        if not isinstance(track, dict):
            continue
        lyrics = str(track.get("lyrics") or "").strip()
        if not lyrics:
            continue
        if bool(track.get("instrumental")) and not bool(track.get("lyrics_keep_for_instrumental", False)):
            continue
        name = f"{int(track.get('track_number') or 1):02d}-{slugify(str(track.get('title') or 'track'))[:60]}.txt"
        rel = _validate_relative_path(f"lyrics/{name}")
        _write_text(lyrics_dir.parent / rel, sanitize_sensitive_text(lyrics) + "\n")
        written.append(rel)
    return written


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def _file_record(export_dir: Path, path: Path) -> ImplementationDocument:
    resolved = path.resolve()
    _ensure_within(export_dir.resolve(), resolved)
    rel = _validate_relative_path(resolved.relative_to(export_dir.resolve()).as_posix())
    return {
        "path": rel,
        "size_bytes": resolved.stat().st_size,
        "sha256": _sha256(resolved),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_relative_path(path: str) -> str:
    normalized = str(path or "")
    if "\\" in normalized:
        raise ValueError("Unsafe relative path.")
    parts = [part for part in normalized.split("/") if part]
    if not parts or normalized.startswith("/") or normalized.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise ValueError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseMetadataError("Refusing to operate outside release metadata boundaries.") from exc


def _qa_summary(report: ImplementationDocument) -> ImplementationDocument:
    summary = _as_document(report.get("summary"))
    return sanitize_metadata(
        {
            "status": report.get("status") or summary.get("status") or "missing",
            "source_hash": report.get("source_hash") or summary.get("source_hash"),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "generated_at": report.get("generated_at") or summary.get("generated_at"),
        },
        blocked_keys=METADATA_BLOCKED_KEYS,
    )


def _ensure_release_metadata_mutable(release: ReleaseDocument) -> None:
    if release.status == "archived":
        raise ReleaseStateError("Archived releases are read-only.")
    if release.status == "signed":
        raise ReleaseStateError("Signed releases cannot be modified. Reset signoff before changing metadata.")


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_text(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _optional_text(value: Any, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None
