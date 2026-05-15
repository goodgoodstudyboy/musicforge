from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from song_agent.final_export import final_export_dir
from song_agent.projectio import slugify, write_json
from song_agent.projects import ProjectStore, now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.release_qa import release_qa_allows_export, release_qa_summary, release_source_hash
from song_agent.releases import BLOCKED_RELEASE_KEYS, ReleaseDocument, ReleaseStore, stable_hash


RELEASE_EXPORT_SCHEMA_VERSION = 1
CORE_COPY_FILES = {"manifest.json", "README.txt", "project-export.json", "song-plan.json", "song.mid"}
OPTIONAL_COPY_FILES = {"song.wav", "quality-report.json", "validator-report.json", "run-summary.json"}
OPTIONAL_COPY_PREFIXES = ("stems/", "assets/", "references/")
RELEASE_EXPORT_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}


class ReleaseExportError(ValueError):
    pass


def build_release_export_bundle(
    *,
    release: ReleaseDocument,
    release_store: ReleaseStore,
    project_store: ProjectStore,
    qa_report: dict[str, Any],
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    current_source_hash = release_source_hash(release, project_store=project_store, release_store=release_store)
    if not release_qa_allows_export(qa_report, current_source_hash=current_source_hash):
        raise ReleaseExportError("Release QA gate failed. Refresh QA before export.")
    release_dir = release_store.release_dir(release.release_id).resolve()
    export_dir = release_store.export_dir(release.release_id).resolve()
    _ensure_within(release_dir, export_dir)
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[dict[str, Any]] = []
    tracklist: list[dict[str, Any]] = []
    used_slugs: set[str] = set()
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        source_dir = final_export_dir(project_store.project_dir(track.project_id)).resolve()
        _ensure_within(project_store.project_dir(track.project_id).resolve(), source_dir)
        track_dir_name = _track_dir_name(track.disc_number, track.track_number, track.title or track.track_id, used_slugs)
        target_dir = (export_dir / "tracks" / track_dir_name).resolve()
        _ensure_within(export_dir, target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        track_files = _copy_track_files(source_dir, target_dir, track_dir_name)
        copied_files.extend(track_files)
        tracklist.append(
            {
                "track_id": track.track_id,
                "disc_number": track.disc_number,
                "track_number": track.track_number,
                "title": track.title,
                "artist": track.artist or release.primary_artist,
                "project_id": track.project_id,
                "version_id": track.version_id,
                "directory": f"tracks/{track_dir_name}",
                "file_count": len(track_files),
            }
        )

    release_public = _release_export_summary(release)
    qa_public = release_qa_summary(qa_report)
    signoff = release_store.read_signoff(release.release_id, default={})
    signoff_public = _release_signoff_export_summary(signoff)
    write_json(export_dir / "release.json", release_public)
    write_json(export_dir / "tracklist.json", {"tracks": tracklist})
    write_json(export_dir / "release-qa.json", qa_public)
    write_json(export_dir / "release-signoff.json", signoff_public)
    _write_readme(export_dir, release, tracklist, qa_public, signoff_public)
    copied_files.extend(_file_record(export_dir, path) for path in [export_dir / "release.json", export_dir / "tracklist.json", export_dir / "release-qa.json", export_dir / "release-signoff.json", export_dir / "README.txt"])

    manifest = {
        "schema_version": RELEASE_EXPORT_SCHEMA_VERSION,
        "release_id": release.release_id,
        "release_name": release.name,
        "generated_at": now,
        "source_hash": current_source_hash,
        "qa_source_hash": qa_report.get("source_hash"),
        "signoff_hash": stable_hash(signoff) if signoff else None,
        "tracks": tracklist,
        "files": sorted(copied_files, key=lambda item: item["path"]),
        "summary": {
            "track_count": len(tracklist),
            "file_count": len(copied_files),
            "total_bytes": sum(int(item.get("size_bytes") or 0) for item in copied_files),
            "qa_status": qa_report.get("status"),
            "signoff_status": signoff_public.get("status"),
        },
        "redaction_summary": {"status": "passed"},
    }
    write_json(export_dir / "manifest.json", sanitize_metadata(manifest, blocked_keys=RELEASE_EXPORT_BLOCKED_KEYS))
    manifest = read_release_export_manifest(release_store, release.release_id)
    return manifest


def build_release_export_zip(release_store: ReleaseStore, release_id: str, *, now: str | None = None) -> dict[str, Any]:
    refresh_release_export_signoff_summary(release_store, release_id)
    now = now or now_iso()
    release_dir = release_store.release_dir(release_id).resolve()
    export_dir = release_store.export_dir(release_id).resolve()
    zip_path = release_store.zip_path(release_id).resolve()
    _ensure_within(release_dir, export_dir)
    _ensure_within(release_dir, zip_path)
    if not export_dir.exists() or not export_dir.is_dir():
        raise FileNotFoundError("Release export has not been generated.")
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    entries: list[str] = []
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(export_dir.rglob("*")):
                if not file.is_file() or file.is_symlink():
                    continue
                resolved = file.resolve()
                _ensure_within(export_dir, resolved)
                entry = _validate_relative_path(resolved.relative_to(export_dir).as_posix())
                archive.write(resolved, entry)
                entries.append(entry)
        tmp_path.replace(zip_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    zip_info = {
        "created_at": now,
        "filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "sha256": _sha256(zip_path),
        "entry_count": len(entries),
        "entries": entries,
    }
    manifest = read_release_export_manifest(release_store, release_id)
    manifest["zip"] = zip_info
    write_json(export_dir / "manifest.json", sanitize_metadata(manifest, blocked_keys=RELEASE_EXPORT_BLOCKED_KEYS))
    return sanitize_metadata(zip_info, blocked_keys=BLOCKED_RELEASE_KEYS)


def refresh_release_export_signoff_summary(release_store: ReleaseStore, release_id: str) -> dict[str, Any]:
    export_dir = release_store.export_dir(release_id)
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Release export has not been generated.")
    signoff = release_store.read_signoff(release_id, default={})
    signoff_public = _release_signoff_export_summary(signoff)
    write_json(export_dir / "release-signoff.json", signoff_public)
    manifest = read_release_export_manifest(release_store, release_id)
    manifest["signoff_hash"] = stable_hash(signoff) if signoff else None
    summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
    summary["signoff_status"] = signoff_public.get("status")
    manifest["summary"] = summary
    files = [item for item in manifest.get("files", []) if isinstance(item, dict) and item.get("path") != "release-signoff.json"]
    files.append(_file_record(export_dir, export_dir / "release-signoff.json"))
    manifest["files"] = sorted(files, key=lambda item: item["path"])
    write_json(manifest_path, sanitize_metadata(manifest, blocked_keys=RELEASE_EXPORT_BLOCKED_KEYS))
    return read_release_export_manifest(release_store, release_id)


def read_release_export_manifest(release_store: ReleaseStore, release_id: str) -> dict[str, Any]:
    path = release_store.export_dir(release_id) / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Release export has not been generated.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return sanitize_metadata(data if isinstance(data, dict) else {}, blocked_keys=RELEASE_EXPORT_BLOCKED_KEYS)


def release_export_summary(manifest: dict[str, Any] | None) -> dict[str, Any]:
    data = manifest if isinstance(manifest, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    zip_info = data.get("zip") if isinstance(data.get("zip"), dict) else {}
    return sanitize_metadata(
        {
            "status": "exported" if data else "missing",
            "exists": bool(data),
            "release_id": data.get("release_id"),
            "generated_at": data.get("generated_at"),
            "source_hash": data.get("source_hash"),
            "qa_source_hash": data.get("qa_source_hash"),
            "track_count": summary.get("track_count", 0),
            "file_count": summary.get("file_count", 0),
            "total_bytes": summary.get("total_bytes", 0),
            "zip_filename": zip_info.get("filename"),
            "zip_sha256": zip_info.get("sha256"),
            "zip_entry_count": zip_info.get("entry_count"),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _copy_track_files(source_dir: Path, target_dir: Path, track_dir_name: str) -> list[dict[str, Any]]:
    if not source_dir.exists() or not source_dir.is_dir() or source_dir.is_symlink():
        raise ReleaseExportError("Project Final Export directory is missing.")
    records: list[dict[str, Any]] = []
    for file in sorted(source_dir.rglob("*")):
        if not file.is_file() or file.is_symlink():
            continue
        resolved = file.resolve()
        _ensure_within(source_dir, resolved)
        rel = _validate_relative_path(resolved.relative_to(source_dir).as_posix())
        if not _copy_allowed(rel):
            continue
        target = (target_dir / rel).resolve()
        _ensure_within(target_dir, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved, target)
        records.append(_file_record(target_dir.parent.parent, target))
    for required in CORE_COPY_FILES:
        if not (target_dir / required).exists():
            raise ReleaseExportError(f"Required track export file is missing: {required}.")
    return records


def _copy_allowed(rel: str) -> bool:
    if rel in CORE_COPY_FILES or rel in OPTIONAL_COPY_FILES:
        return True
    return any(rel.startswith(prefix) for prefix in OPTIONAL_COPY_PREFIXES)


def _track_dir_name(disc_number: int, track_number: int, title: str, used: set[str]) -> str:
    prefix = f"{track_number:02d}" if disc_number <= 1 else f"{disc_number:02d}-{track_number:02d}"
    base_slug = slugify(title)[:60].strip("-") or "track"
    candidate = f"{prefix}-{base_slug}"
    index = 2
    while candidate in used:
        candidate = f"{prefix}-{base_slug}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def _file_record(export_dir: Path, path: Path) -> dict[str, Any]:
    rel = _validate_relative_path(path.resolve().relative_to(export_dir.resolve()).as_posix())
    return {
        "path": rel,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _write_readme(export_dir: Path, release: ReleaseDocument, tracklist: list[dict[str, Any]], qa: dict[str, Any], signoff: dict[str, Any]) -> None:
    lines = [
        f"MusicForge Release Export: {sanitize_sensitive_text(release.name)}",
        "",
        f"Release ID: {release.release_id}",
        f"Type: {release.release_type}",
        f"Primary Artist: {sanitize_sensitive_text(release.primary_artist or '')}",
        f"QA: {qa.get('status', 'missing')}",
        f"Signoff: {signoff.get('status', 'not_signed')}",
        "",
        "Tracklist:",
    ]
    for item in tracklist:
        lines.append(f"{item['track_number']:02d}. {sanitize_sensitive_text(str(item.get('title') or 'Untitled'))} ({item.get('project_id')}/{item.get('version_id')})")
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _release_export_summary(release: ReleaseDocument) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "release_id": release.release_id,
            "name": release.name,
            "release_type": release.release_type,
            "primary_artist": release.primary_artist,
            "label": release.label,
            "language": release.language,
            "track_count": len(release.tracks),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _release_signoff_export_summary(signoff: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "status": signoff.get("status") or "not_signed",
            "signed_at": signoff.get("signed_at"),
            "signed_by": signoff.get("signed_by"),
            "forced": bool(signoff.get("forced", False)),
            "qa_source_hash": signoff.get("qa_source_hash"),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _validate_relative_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or normalized.startswith("/") or normalized.startswith("\\") or normalized.startswith("//") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise ValueError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ReleaseExportError("Refusing to operate outside release export boundaries.") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
