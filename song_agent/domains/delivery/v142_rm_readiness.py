# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list, document_or as _document_or
import csv as csv
import hashlib as hashlib
import io as io
import json as json
import os as os
import re as re
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.studio.projectio import read_json as read_json, slugify as slugify, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseDocument as ReleaseDocument, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash

class _DeferredGlobal:
    def __init__(self, name: str) -> None:
        self.name = name


def _make_deferred_global(name: str) -> type[object]:
    base: type[object] = Exception if name.endswith("Error") else object
    return type(f"_DeferredGlobal_{name}", (base,), {"_deferred_global_name": name})


def _deferred_global_name(value: object) -> str | None:
    if isinstance(value, _DeferredGlobal):
        return value.name
    if isinstance(value, type):
        name = getattr(value, "_deferred_global_name", None)
        if isinstance(name, str):
            return name
    return None


def _resolve_bound_default(value: object, namespace: dict[str, object]) -> object:
    name = _deferred_global_name(value)
    if name is not None:
        return namespace.get(name, value)
    if isinstance(value, tuple):
        return tuple(_resolve_bound_default(item, namespace) for item in value)
    if isinstance(value, list):
        return [_resolve_bound_default(item, namespace) for item in value]
    if isinstance(value, dict):
        return {
            _resolve_bound_default(key, namespace): _resolve_bound_default(item, namespace)
            for key, item in value.items()
        }
    return value


def _bind_function_defaults(function: object, namespace: dict[str, object]) -> None:
    defaults = getattr(function, "__defaults__", None)
    if defaults:
        function.__defaults__ = tuple(_resolve_bound_default(item, namespace) for item in defaults)
    kwdefaults = getattr(function, "__kwdefaults__", None)
    if kwdefaults:
        function.__kwdefaults__ = {
            key: _resolve_bound_default(item, namespace)
            for key, item in kwdefaults.items()
        }


def _bind_class_bases(cls: type[object], namespace: dict[str, object]) -> None:
    bases = tuple(_resolve_bound_default(base, namespace) for base in cls.__bases__)
    if bases != cls.__bases__ and all(isinstance(base, type) for base in bases):
        try:
            cls.__bases__ = bases
        except TypeError:
            pass


def _bind_deferred_defaults(namespace: dict[str, object]) -> None:
    for value in list(globals().values()):
        if callable(value) and hasattr(value, "__defaults__"):
            _bind_function_defaults(value, namespace)
        if isinstance(value, type):
            _bind_class_bases(value, namespace)
            for member in vars(value).values():
                target = member
                if isinstance(member, (staticmethod, classmethod)):
                    target = member.__func__
                if callable(target) and hasattr(target, "__defaults__"):
                    _bind_function_defaults(target, namespace)

METADATA_BLOCKED_KEYS = _make_deferred_global('METADATA_BLOCKED_KEYS')
METADATA_EXPORT_BLOCKED_KEYS = _make_deferred_global('METADATA_EXPORT_BLOCKED_KEYS')
ReleaseMetadata = _make_deferred_global('ReleaseMetadata')
ReleaseMetadataDocument = _make_deferred_global('ReleaseMetadataDocument')
ReleaseMetadataError = _make_deferred_global('ReleaseMetadataError')
TrackMetadata = _make_deferred_global('TrackMetadata')
item = _make_deferred_global('item')
metadata_qa_allows_export = _make_deferred_global('metadata_qa_allows_export')
part = _make_deferred_global('part')
read_release_metadata = _make_deferred_global('read_release_metadata')
release_metadata_source_hash = _make_deferred_global('release_metadata_source_hash')

def bind_globals(namespace: dict[str, object]) -> None:
    global METADATA_BLOCKED_KEYS, METADATA_EXPORT_BLOCKED_KEYS, ReleaseMetadata, ReleaseMetadataDocument, ReleaseMetadataError, TrackMetadata, item
    global metadata_qa_allows_export, part, read_release_metadata, release_metadata_source_hash
    METADATA_BLOCKED_KEYS = namespace.get('METADATA_BLOCKED_KEYS', METADATA_BLOCKED_KEYS)
    METADATA_EXPORT_BLOCKED_KEYS = namespace.get('METADATA_EXPORT_BLOCKED_KEYS', METADATA_EXPORT_BLOCKED_KEYS)
    ReleaseMetadata = namespace.get('ReleaseMetadata', ReleaseMetadata)
    ReleaseMetadataDocument = namespace.get('ReleaseMetadataDocument', ReleaseMetadataDocument)
    ReleaseMetadataError = namespace.get('ReleaseMetadataError', ReleaseMetadataError)
    TrackMetadata = namespace.get('TrackMetadata', TrackMetadata)
    item = namespace.get('item', item)
    metadata_qa_allows_export = namespace.get('metadata_qa_allows_export', metadata_qa_allows_export)
    part = namespace.get('part', part)
    read_release_metadata = namespace.get('read_release_metadata', read_release_metadata)
    release_metadata_source_hash = namespace.get('release_metadata_source_hash', release_metadata_source_hash)
    _bind_deferred_defaults(namespace)


RELEASE_METADATA_SCHEMA_VERSION = 1
METADATA_EXPORT_SCHEMA_VERSION = 1
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




def export_release_metadata_files(
    *,
    release_store: ReleaseStore,
    release_id: str,
    qa_report: DomainDocument,
    now: str | None = None,
) -> DomainDocument:
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

def attach_metadata_export_to_manifest(release_store: ReleaseStore, release_id: str, metadata_export: DomainDocument) -> DomainDocument:
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

def _metadata_from_release(release: ReleaseDocument, project_store: ProjectStore, *, now: str) -> DomainDocument:
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

def _merge_missing_metadata(existing: DomainDocument, inferred: DomainDocument) -> DomainDocument:
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

def _source_summary(release: ReleaseDocument, project_store: ProjectStore) -> DomainDocument:
    tracks: list[DomainDocument] = []
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

def _track_plan(project_store: ProjectStore, project_id: str) -> DomainDocument:
    try:
        path = final_export_dir(project_store.project_dir(project_id)) / "song-plan.json"
        value = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return _as_document(value)

def _extract_lyrics(plan: DomainDocument) -> str | None:
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

def _duration_beats(plan: DomainDocument) -> float | None:
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

def _write_platform_csv(path: Path, metadata: DomainDocument) -> None:
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

def _write_credits_csv(path: Path, metadata: DomainDocument) -> None:
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

def _write_csv(path: Path, fields: list[str], rows: list[DomainDocument]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: sanitize_sensitive_text(str(row.get(key) or "")) for key in fields})
    _write_text(path, buffer.getvalue())

def _write_lyrics(lyrics_dir: Path, metadata: DomainDocument) -> list[str]:
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

def _file_record(export_dir: Path, path: Path) -> DomainDocument:
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

def _qa_summary(report: DomainDocument) -> DomainDocument:
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

def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _safe_text(value: object, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]

def _optional_text(value: object, limit: int) -> str | None:
    text = _safe_text(value, limit)
    return text or None
