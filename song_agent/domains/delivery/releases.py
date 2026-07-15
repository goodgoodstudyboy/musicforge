from __future__ import annotations

import hashlib
import json
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from song_agent.domains.creation.final_export import final_export_dir, final_export_zip_path
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import ProjectDocument, ProjectStore, ProjectVersion, now_iso
from song_agent.domains.creation.redaction import sanitize_metadata


RELEASE_ROOT = Path(".musicforge") / "releases"
RELEASE_SCHEMA_VERSION = 1
RELEASE_TRACK_SCHEMA_VERSION = 1
RELEASE_TYPES = {"single_pack", "ep", "album", "demo_pack"}
RELEASE_STATUSES = {"draft", "qa_failed", "qa_warning", "qa_passed", "exported", "signed", "archived"}
SIGNED_RELEASE_STATUSES = {"signed"}
BLOCKED_RELEASE_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "provider_snapshot",
    "raw_provider_response",
    "secret",
    "token",
}


class ReleaseError(Exception):
    pass


class ReleaseNotFoundError(ReleaseError):
    pass


class ReleaseValidationError(ReleaseError):
    pass


class ReleaseStateError(ReleaseError):
    pass


class ReleaseConflictError(ReleaseError):
    pass


@dataclass
class ReleaseTrack:
    track_id: str
    track_number: int
    disc_number: int
    title: str
    artist: str | None
    project_id: str
    version_id: str
    final_export_hash: str | None = None
    delivery_qa_hash: str | None = None
    delivery_signoff_hash: str | None = None
    project_snapshot: dict[str, Any] = field(default_factory=dict)
    export_snapshot: dict[str, Any] = field(default_factory=dict)
    qa_snapshot: dict[str, Any] = field(default_factory=dict)
    signoff_snapshot: dict[str, Any] = field(default_factory=dict)
    stale: bool = False
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": RELEASE_TRACK_SCHEMA_VERSION,
                "track_id": self.track_id,
                "track_number": self.track_number,
                "disc_number": self.disc_number,
                "title": self.title,
                "artist": self.artist,
                "project_id": self.project_id,
                "version_id": self.version_id,
                "final_export_hash": self.final_export_hash,
                "delivery_qa_hash": self.delivery_qa_hash,
                "delivery_signoff_hash": self.delivery_signoff_hash,
                "project_snapshot": self.project_snapshot,
                "export_snapshot": self.export_snapshot,
                "qa_snapshot": self.qa_snapshot,
                "signoff_snapshot": self.signoff_snapshot,
                "stale": self.stale,
                "warnings": self.warnings,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            },
            blocked_keys=BLOCKED_RELEASE_KEYS,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseTrack":
        now = str(data.get("created_at") or now_iso())
        return cls(
            track_id=_validate_track_id(str(data.get("track_id") or "track-000001")),
            track_number=max(1, int(data.get("track_number", 1) or 1)),
            disc_number=max(1, int(data.get("disc_number", 1) or 1)),
            title=_bounded_text(data.get("title"), 120) or "Untitled Track",
            artist=_optional_bounded_text(data.get("artist"), 120),
            project_id=_required_id(data.get("project_id"), "project_id"),
            version_id=_required_id(data.get("version_id"), "version_id"),
            final_export_hash=_optional_bounded_text(data.get("final_export_hash"), 128),
            delivery_qa_hash=_optional_bounded_text(data.get("delivery_qa_hash"), 128),
            delivery_signoff_hash=_optional_bounded_text(data.get("delivery_signoff_hash"), 128),
            project_snapshot=_safe_dict(data.get("project_snapshot")),
            export_snapshot=_safe_dict(data.get("export_snapshot")),
            qa_snapshot=_safe_dict(data.get("qa_snapshot")),
            signoff_snapshot=_safe_dict(data.get("signoff_snapshot")),
            stale=bool(data.get("stale", False)),
            warnings=[str(item)[:240] for item in data.get("warnings", []) if str(item).strip()],
            created_at=now,
            updated_at=str(data.get("updated_at") or now),
        )


@dataclass
class ReleaseDocument:
    schema_version: int
    release_id: str
    name: str
    release_type: str
    status: str
    primary_artist: str
    label: str | None
    language: str | None
    notes: str | None
    created_at: str
    updated_at: str
    hidden: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    tracks: list[ReleaseTrack] = field(default_factory=list)
    latest_qa_summary: dict[str, Any] = field(default_factory=dict)
    latest_export_summary: dict[str, Any] = field(default_factory=dict)
    latest_signoff_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": self.schema_version,
                "release_id": self.release_id,
                "name": self.name,
                "release_type": self.release_type,
                "status": self.status,
                "primary_artist": self.primary_artist,
                "label": self.label,
                "language": self.language,
                "notes": self.notes,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "hidden": self.hidden,
                "metadata": self.metadata,
                "tracks": [track.to_dict() for track in sorted(self.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id))],
                "latest_qa_summary": self.latest_qa_summary,
                "latest_export_summary": self.latest_export_summary,
                "latest_signoff_summary": self.latest_signoff_summary,
            },
            blocked_keys=BLOCKED_RELEASE_KEYS,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReleaseDocument":
        created_at = str(data.get("created_at") or now_iso())
        release_type = str(data.get("release_type") or "demo_pack")
        if release_type not in RELEASE_TYPES:
            release_type = "demo_pack"
        status = str(data.get("status") or "draft")
        if status not in RELEASE_STATUSES:
            status = "draft"
        return cls(
            schema_version=int(data.get("schema_version", RELEASE_SCHEMA_VERSION) or RELEASE_SCHEMA_VERSION),
            release_id=_validate_release_id(str(data.get("release_id") or "")),
            name=_bounded_text(data.get("name"), 120) or "Untitled Release",
            release_type=release_type,
            status=status,
            primary_artist=_bounded_text(data.get("primary_artist"), 120),
            label=_optional_bounded_text(data.get("label"), 120),
            language=_optional_bounded_text(data.get("language"), 60),
            notes=_optional_bounded_text(data.get("notes"), 2000),
            created_at=created_at,
            updated_at=str(data.get("updated_at") or created_at),
            hidden=bool(data.get("hidden", False)),
            metadata=_safe_dict(data.get("metadata")),
            tracks=[ReleaseTrack.from_dict(item) for item in data.get("tracks", []) if isinstance(item, dict)],
            latest_qa_summary=_safe_dict(data.get("latest_qa_summary")),
            latest_export_summary=_safe_dict(data.get("latest_export_summary")),
            latest_signoff_summary=_safe_dict(data.get("latest_signoff_summary")),
        )


class ReleaseStore:
    def __init__(self, root: Path | str = RELEASE_ROOT, project_store: ProjectStore | None = None) -> None:
        self.root = Path(root).resolve()
        self.project_store = project_store or ProjectStore()
        self.lock = threading.RLock()

    def list_releases(self, include_hidden: bool = False) -> list[ReleaseDocument]:
        documents: list[ReleaseDocument] = []
        for release_json in self.root.glob("*/release.json"):
            try:
                document = self.get_release(release_json.parent.name)
            except (ReleaseError, OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if document.hidden and not include_hidden:
                continue
            documents.append(document)
        return sorted(documents, key=lambda item: item.updated_at, reverse=True)

    def create_release(self, payload: dict[str, Any]) -> ReleaseDocument:
        with self.lock:
            release_dir = self._reserve_release_dir()
            now = now_iso()
            document = ReleaseDocument(
                schema_version=RELEASE_SCHEMA_VERSION,
                release_id=release_dir.name,
                name=_bounded_text(payload.get("name"), 120) or "Untitled Release",
                release_type=_release_type(payload.get("release_type")),
                status="draft",
                primary_artist=_bounded_text(payload.get("primary_artist"), 120),
                label=_optional_bounded_text(payload.get("label"), 120),
                language=_optional_bounded_text(payload.get("language"), 60),
                notes=_optional_bounded_text(payload.get("notes"), 2000),
                metadata=_safe_dict(payload.get("metadata")),
                created_at=now,
                updated_at=now,
            )
            self.save_release(document, touch=False)
            self.append_event(document.release_id, "release_created", {"name": document.name})
            return document

    def get_release(self, release_id: str) -> ReleaseDocument:
        with self.lock:
            release_dir = self.release_dir(release_id)
            path = release_dir / "release.json"
            if not path.exists():
                raise ReleaseNotFoundError(release_id)
            return ReleaseDocument.from_dict(read_json(path))

    def save_release(self, document: ReleaseDocument, *, touch: bool = True) -> ReleaseDocument:
        with self.lock:
            if touch:
                document.updated_at = now_iso()
            document.release_id = _validate_release_id(document.release_id)
            if document.release_type not in RELEASE_TYPES:
                raise ReleaseValidationError(f"Unsupported release_type: {document.release_type}.")
            if document.status not in RELEASE_STATUSES:
                raise ReleaseValidationError(f"Unsupported release status: {document.status}.")
            self.release_dir(document.release_id).mkdir(parents=True, exist_ok=True)
            document.tracks = _renumber_tracks(document.tracks)
            write_json(self.release_dir(document.release_id) / "release.json", document.to_dict())
            return document

    def update_release(self, release_id: str, patch: dict[str, Any]) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            self._ensure_mutable(document)
            if "name" in patch:
                document.name = _bounded_text(patch.get("name"), 120) or document.name
            if "release_type" in patch:
                document.release_type = _release_type(patch.get("release_type"))
            if "primary_artist" in patch:
                document.primary_artist = _bounded_text(patch.get("primary_artist"), 120)
            if "label" in patch:
                document.label = _optional_bounded_text(patch.get("label"), 120)
            if "language" in patch:
                document.language = _optional_bounded_text(patch.get("language"), 60)
            if "notes" in patch:
                document.notes = _optional_bounded_text(patch.get("notes"), 2000)
            if "metadata" in patch:
                document.metadata = _safe_dict(patch.get("metadata"))
            document.latest_qa_summary = _stale_summary(document.latest_qa_summary)
            document.latest_export_summary = _stale_summary(document.latest_export_summary)
            self.save_release(document)
            self.append_event(document.release_id, "release_updated", {"status": document.status})
            return document

    def hide_release(self, release_id: str, hidden: bool = True) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.hidden = hidden
            self.save_release(document)
            self.append_event(release_id, "release_hidden" if hidden else "release_unhidden", {})
            return document

    def archive_release(self, release_id: str) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.status = "archived"
            self.save_release(document)
            self.append_event(release_id, "release_archived", {})
            return document

    def delete_release(self, release_id: str) -> dict[str, Any]:
        with self.lock:
            release_dir = self.release_dir(release_id)
            self.ensure_release_dir_is_safe(release_dir)
            if not release_dir.exists():
                raise ReleaseNotFoundError(release_id)
            shutil.rmtree(release_dir)
            return {"release_id": release_id, "deleted": True}

    def add_track(self, release_id: str, payload: dict[str, Any]) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            self._ensure_mutable(document)
            track_id = _next_track_id(document.tracks)
            track_number = int(payload.get("track_number") or (max((track.track_number for track in document.tracks if track.disc_number == int(payload.get("disc_number") or 1)), default=0) + 1))
            disc_number = max(1, int(payload.get("disc_number", 1) or 1))
            track = build_release_track_snapshot(
                self.project_store,
                track_id=track_id,
                project_id=str(payload.get("project_id") or ""),
                version_id=_optional_bounded_text(payload.get("version_id"), 80),
                track_number=track_number,
                disc_number=disc_number,
                title=_optional_bounded_text(payload.get("title"), 120),
                artist=_optional_bounded_text(payload.get("artist"), 120),
                now=now_iso(),
            )
            document.tracks.append(track)
            document.latest_qa_summary = _stale_summary(document.latest_qa_summary)
            document.latest_export_summary = _stale_summary(document.latest_export_summary)
            document.status = "draft" if document.status not in {"archived"} else document.status
            self.save_release(document)
            self.append_event(release_id, "release_track_added", {"track_id": track.track_id, "project_id": track.project_id, "version_id": track.version_id})
            return document

    def remove_track(self, release_id: str, track_id: str) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            self._ensure_mutable(document)
            before = len(document.tracks)
            document.tracks = [track for track in document.tracks if track.track_id != _validate_track_id(track_id)]
            if len(document.tracks) == before:
                raise ReleaseNotFoundError(track_id)
            document.latest_qa_summary = _stale_summary(document.latest_qa_summary)
            document.latest_export_summary = _stale_summary(document.latest_export_summary)
            self.save_release(document)
            self.append_event(release_id, "release_track_removed", {"track_id": track_id})
            return document

    def reorder_tracks(self, release_id: str, payload: dict[str, Any]) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            self._ensure_mutable(document)
            order = [str(item) for item in payload.get("track_ids", []) if str(item).strip()]
            if set(order) != {track.track_id for track in document.tracks}:
                raise ReleaseValidationError("track_ids must contain every existing track exactly once.")
            by_id = {track.track_id: track for track in document.tracks}
            document.tracks = []
            for index, track_id in enumerate(order, start=1):
                track = by_id[track_id]
                track.track_number = index
                track.disc_number = max(1, int(payload.get("disc_number") or track.disc_number or 1))
                track.updated_at = now_iso()
                document.tracks.append(track)
            document.latest_qa_summary = _stale_summary(document.latest_qa_summary)
            document.latest_export_summary = _stale_summary(document.latest_export_summary)
            self.save_release(document)
            self.append_event(release_id, "release_tracks_reordered", {"track_ids": order})
            return document

    def refresh_track(self, release_id: str, track_id: str) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            self._ensure_mutable(document)
            found = False
            refreshed: list[ReleaseTrack] = []
            for track in document.tracks:
                if track.track_id != _validate_track_id(track_id):
                    refreshed.append(track)
                    continue
                found = True
                refreshed.append(
                    build_release_track_snapshot(
                        self.project_store,
                        track_id=track.track_id,
                        project_id=track.project_id,
                        version_id=track.version_id,
                        track_number=track.track_number,
                        disc_number=track.disc_number,
                        title=track.title,
                        artist=track.artist,
                        now=now_iso(),
                    )
                )
            if not found:
                raise ReleaseNotFoundError(track_id)
            document.tracks = refreshed
            document.latest_qa_summary = _stale_summary(document.latest_qa_summary)
            document.latest_export_summary = _stale_summary(document.latest_export_summary)
            self.save_release(document)
            self.append_event(release_id, "release_track_refreshed", {"track_id": track_id})
            return document

    def update_qa_summary(self, release_id: str, summary: dict[str, Any]) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.latest_qa_summary = _safe_dict(summary)
            status = str(summary.get("status") or "")
            if document.status != "archived":
                document.status = {"passed": "qa_passed", "warning": "qa_warning", "failed": "qa_failed", "stale": "qa_failed"}.get(status, document.status)
            return self.save_release(document)

    def update_export_summary(self, release_id: str, summary: dict[str, Any]) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.latest_export_summary = _safe_dict(summary)
            if document.status not in {"signed", "archived"}:
                document.status = "exported"
            return self.save_release(document)

    def update_signoff_summary(self, release_id: str, summary: dict[str, Any]) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.latest_signoff_summary = _safe_dict(summary)
            status = str(summary.get("status") or "")
            if status in {"signed", "force_signed"} and document.status != "archived":
                document.status = "signed"
            return self.save_release(document)

    def read_qa(self, release_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.release_dir(release_id) / "release-qa.json"
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseNotFoundError("Release QA does not exist.")
        return _safe_dict(read_json(path))

    def write_qa(self, release_id: str, report: dict[str, Any]) -> dict[str, Any]:
        self.get_release(release_id)
        clean = _safe_dict(report)
        write_json(self.release_dir(release_id) / "release-qa.json", clean)
        return clean

    def read_signoff(self, release_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.release_dir(release_id) / "release-signoff.json"
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseNotFoundError("Release signoff does not exist.")
        return _safe_dict(read_json(path))

    def write_signoff(self, release_id: str, record: dict[str, Any]) -> dict[str, Any]:
        self.get_release(release_id)
        clean = _safe_dict(record)
        write_json(self.release_dir(release_id) / "release-signoff.json", clean)
        return clean

    def reset_signoff(self, release_id: str, history_event: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            existing = self.read_signoff(release_id, default={})
            event = _safe_dict(history_event)
            history_path = self.release_dir(release_id) / "release-signoff-history.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)
            if existing:
                with history_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event, ensure_ascii=False) + "\n")
                signoff_path = self.release_dir(release_id) / "release-signoff.json"
                if signoff_path.exists():
                    signoff_path.unlink()
            document = self.get_release(release_id)
            document.latest_signoff_summary = {"status": "not_signed"}
            if document.status == "signed":
                document.status = "exported" if document.latest_export_summary.get("exists") else "draft"
            self.save_release(document)
            return event

    def read_events(self, release_id: str) -> list[dict[str, Any]]:
        path = self.release_dir(release_id) / "events.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return sanitize_metadata(events, blocked_keys=BLOCKED_RELEASE_KEYS)

    def append_event(self, release_id: str, event_type: str, payload: dict[str, Any]) -> None:
        release_dir = self.release_dir(release_id)
        release_dir.mkdir(parents=True, exist_ok=True)
        event = sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload}, blocked_keys=BLOCKED_RELEASE_KEYS)
        with (release_dir / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def release_dir(self, release_id: str) -> Path:
        return self.root / _validate_release_id(release_id)

    def export_dir(self, release_id: str) -> Path:
        return self.release_dir(release_id) / "release-export"

    def zip_path(self, release_id: str) -> Path:
        return self.release_dir(release_id) / "release-export.zip"

    def ensure_release_dir_is_safe(self, release_dir: Path) -> None:
        root = self.root.resolve()
        target = release_dir.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ReleaseValidationError("Refusing to operate outside the release root.") from exc

    def _reserve_release_dir(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            release_dir = self.root / f"release-{index:06d}"
            try:
                release_dir.mkdir(parents=True, exist_ok=False)
                return release_dir
            except FileExistsError:
                continue
        raise ReleaseConflictError("Unable to allocate a unique release id.")

    def _ensure_mutable(self, document: ReleaseDocument) -> None:
        if document.status == "archived":
            raise ReleaseStateError("Archived releases are read-only.")
        if document.status in SIGNED_RELEASE_STATUSES:
            raise ReleaseStateError("Signed releases cannot be modified. Reset signoff before changing tracks.")


def build_release_track_snapshot(
    project_store: ProjectStore,
    *,
    track_id: str,
    project_id: str,
    version_id: str | None,
    track_number: int,
    disc_number: int,
    title: str | None,
    artist: str | None,
    now: str | None = None,
) -> ReleaseTrack:
    now = now or now_iso()
    document = project_store.get_project(project_id)
    target_version_id = version_id or document.state.final_version_id
    if not target_version_id:
        raise ReleaseConflictError("Project has no final version.")
    version = _find_version(document, target_version_id)
    project_dir = project_store.project_dir(project_id)
    manifest = _read_optional_json(final_export_dir(project_dir) / "manifest.json")
    qa = project_store.read_delivery_qa(project_id, default={})
    signoff = project_store.read_delivery_signoff(project_id, default={})
    plan = _read_optional_json(final_export_dir(project_dir) / "song-plan.json")
    warnings = []
    if not manifest:
        warnings.append("Final Export manifest is missing.")
    if not qa:
        warnings.append("Delivery QA is missing.")
    if not signoff:
        warnings.append("Delivery Signoff is missing.")
    if target_version_id != document.state.final_version_id:
        warnings.append("Track version is not the current Project final version.")
    return ReleaseTrack(
        track_id=_validate_track_id(track_id),
        track_number=max(1, int(track_number or 1)),
        disc_number=max(1, int(disc_number or 1)),
        title=_bounded_text(title, 120) or _track_title(document, version, manifest, plan),
        artist=_optional_bounded_text(artist, 120),
        project_id=document.state.project_id,
        version_id=version.version_id,
        final_export_hash=_file_sha256(final_export_dir(project_dir) / "manifest.json"),
        delivery_qa_hash=_stable_hash(qa) if qa else None,
        delivery_signoff_hash=_stable_hash(signoff) if signoff else None,
        project_snapshot=_project_snapshot(document, version, plan),
        export_snapshot=_export_snapshot(project_dir, manifest),
        qa_snapshot=_qa_snapshot(qa),
        signoff_snapshot=_signoff_snapshot(signoff),
        stale=False,
        warnings=warnings,
        created_at=now,
        updated_at=now,
    )


def release_summary(document: ReleaseDocument) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "release_id": document.release_id,
            "name": document.name,
            "release_type": document.release_type,
            "status": document.status,
            "primary_artist": document.primary_artist,
            "track_count": len(document.tracks),
            "hidden": document.hidden,
            "qa_summary": document.latest_qa_summary,
            "export_summary": document.latest_export_summary,
            "signoff_summary": document.latest_signoff_summary,
            "latest_qa_status": document.latest_qa_summary.get("status"),
            "latest_export_status": document.latest_export_summary.get("status"),
            "latest_signoff_status": document.latest_signoff_summary.get("status"),
            "updated_at": document.updated_at,
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def release_document_source(document: ReleaseDocument) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "schema_version": document.schema_version,
            "release_id": document.release_id,
            "name": document.name,
            "release_type": document.release_type,
            "primary_artist": document.primary_artist,
            "label": document.label,
            "language": document.language,
            "notes": document.notes,
            "metadata": document.metadata,
            "tracks": [
                {
                    "track_id": track.track_id,
                    "disc_number": track.disc_number,
                    "track_number": track.track_number,
                    "title": track.title,
                    "artist": track.artist,
                    "project_id": track.project_id,
                    "version_id": track.version_id,
                    "final_export_hash": track.final_export_hash,
                    "delivery_qa_hash": track.delivery_qa_hash,
                    "delivery_signoff_hash": track.delivery_signoff_hash,
                }
                for track in sorted(document.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id))
            ],
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def stable_hash(value: Any) -> str:
    return _stable_hash(value)


def _project_snapshot(document: ProjectDocument, version: ProjectVersion, plan: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "name": document.state.name,
            "hidden": document.state.hidden,
            "final_version_id": document.state.final_version_id,
            "version_id": version.version_id,
            "quality_score": version.quality_score,
            "quality_gate_status": version.quality_gate_status,
            "quality_gate_score": version.quality_gate_score,
            "tempo_bpm": plan.get("tempo_bpm"),
            "key": plan.get("key"),
            "duration_beats": _duration_beats(plan),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _export_snapshot(project_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    zip_path = final_export_zip_path(project_dir)
    return sanitize_metadata(
        {
            "exists": bool(manifest),
            "version_id": manifest.get("version_id") if manifest else None,
            "file_count": len(manifest.get("files", [])) if isinstance(manifest.get("files"), list) else 0,
            "generated_at": manifest.get("generated_at") if manifest else None,
            "zip_exists": zip_path.exists(),
            "zip_sha256": _file_sha256(zip_path),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _qa_snapshot(qa: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "status": qa.get("status"),
            "readiness": qa.get("readiness"),
            "handoff_allowed": qa.get("handoff_allowed"),
            "source_hash": qa.get("source_hash"),
            "final_version_id": (qa.get("final_version") or {}).get("version_id") if isinstance(qa.get("final_version"), dict) else None,
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _signoff_snapshot(signoff: dict[str, Any]) -> dict[str, Any]:
    return sanitize_metadata(
        {
            "status": signoff.get("status"),
            "signed_at": signoff.get("signed_at"),
            "final_version_id": signoff.get("final_version_id"),
            "delivery_qa_source_hash": signoff.get("delivery_qa_source_hash"),
            "delivery_qa_hash": signoff.get("delivery_qa_hash"),
            "forced": bool(signoff.get("forced", False)),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def _track_title(document: ProjectDocument, version: ProjectVersion, manifest: dict[str, Any], plan: dict[str, Any]) -> str:
    for value in (manifest.get("version_name"), plan.get("title"), version.name, document.state.name):
        text = _bounded_text(value, 120)
        if text:
            return text
    return "Untitled Track"


def _duration_beats(plan: dict[str, Any]) -> float | None:
    sections = plan.get("sections") if isinstance(plan.get("sections"), list) else []
    try:
        return max((float(section.get("start_beat", 0) or 0) + float(section.get("length_bars", 0) or 0) * 4 for section in sections if isinstance(section, dict)), default=None)
    except (TypeError, ValueError):
        return None


def _find_version(document: ProjectDocument, version_id: str) -> ProjectVersion:
    for version in document.versions:
        if version.version_id == version_id:
            return version
    raise ReleaseConflictError("Project version does not exist.")


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(value: Any) -> str:
    clean = sanitize_metadata(value, blocked_keys=BLOCKED_RELEASE_KEYS)
    payload = json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _renumber_tracks(tracks: list[ReleaseTrack]) -> list[ReleaseTrack]:
    ordered = sorted(tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id))
    counters: dict[int, int] = {}
    for track in ordered:
        track.disc_number = max(1, int(track.disc_number or 1))
        counters[track.disc_number] = counters.get(track.disc_number, 0) + 1
        track.track_number = counters[track.disc_number]
    return ordered


def _next_track_id(tracks: list[ReleaseTrack]) -> str:
    used = {track.track_id for track in tracks}
    for index in range(1, 1_000_000):
        track_id = f"track-{index:06d}"
        if track_id not in used:
            return track_id
    raise ReleaseConflictError("Unable to allocate a unique track id.")


def _stale_summary(summary: dict[str, Any]) -> dict[str, Any]:
    data = _safe_dict(summary)
    if not data:
        return {}
    data["stale"] = True
    if data.get("status") in {"passed", "warning", "signed", "force_signed", "exported"}:
        data["status"] = "stale"
    return data


def _safe_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return sanitize_metadata(value, blocked_keys=BLOCKED_RELEASE_KEYS)


def _release_type(value: Any) -> str:
    release_type = str(value or "demo_pack").strip()
    if release_type not in RELEASE_TYPES:
        raise ReleaseValidationError(f"Unsupported release_type: {release_type}.")
    return release_type


def _validate_release_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("release-") or not text.removeprefix("release-").isdigit():
        raise ReleaseValidationError("Invalid release_id.")
    return text


def _validate_track_id(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("track-") or not text.removeprefix("track-").isdigit():
        raise ReleaseValidationError("Invalid track_id.")
    return text


def _required_id(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ReleaseValidationError(f"{field} is required.")
    return text


def _bounded_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _optional_bounded_text(value: Any, limit: int) -> str | None:
    text = _bounded_text(value, limit)
    return text or None
