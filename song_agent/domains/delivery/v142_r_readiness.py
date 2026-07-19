# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir, final_export_zip_path as final_export_zip_path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, ProjectStore as ProjectStore, ProjectVersion as ProjectVersion, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata

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

RELEASE_ROOT = _make_deferred_global('RELEASE_ROOT')
ReleaseConflictError = _make_deferred_global('ReleaseConflictError')
ReleaseDocument = _make_deferred_global('ReleaseDocument')
ReleaseError = _make_deferred_global('ReleaseError')
ReleaseNotFoundError = _make_deferred_global('ReleaseNotFoundError')
ReleaseStateError = _make_deferred_global('ReleaseStateError')
ReleaseTrack = _make_deferred_global('ReleaseTrack')
ReleaseValidationError = _make_deferred_global('ReleaseValidationError')
_bounded_text = _make_deferred_global('_bounded_text')
_export_snapshot = _make_deferred_global('_export_snapshot')
_file_sha256 = _make_deferred_global('_file_sha256')
_find_version = _make_deferred_global('_find_version')
_next_track_id = _make_deferred_global('_next_track_id')
_optional_bounded_text = _make_deferred_global('_optional_bounded_text')
_project_snapshot = _make_deferred_global('_project_snapshot')
_qa_snapshot = _make_deferred_global('_qa_snapshot')
_read_optional_json = _make_deferred_global('_read_optional_json')
_release_type = _make_deferred_global('_release_type')
_renumber_tracks = _make_deferred_global('_renumber_tracks')
_safe_dict = _make_deferred_global('_safe_dict')
_signoff_snapshot = _make_deferred_global('_signoff_snapshot')
_stable_hash = _make_deferred_global('_stable_hash')
_stale_summary = _make_deferred_global('_stale_summary')
_track_title = _make_deferred_global('_track_title')
_validate_release_id = _make_deferred_global('_validate_release_id')
_validate_track_id = _make_deferred_global('_validate_track_id')
item = _make_deferred_global('item')

def bind_globals(namespace: dict[str, object]) -> None:
    global RELEASE_ROOT, ReleaseConflictError, ReleaseDocument, ReleaseError, ReleaseNotFoundError, ReleaseStateError, ReleaseTrack, ReleaseValidationError
    global _bounded_text, _export_snapshot, _file_sha256, _find_version, _next_track_id, _optional_bounded_text, _project_snapshot
    global _qa_snapshot, _read_optional_json, _release_type, _renumber_tracks, _safe_dict, _signoff_snapshot, _stable_hash, _stale_summary
    global _track_title, _validate_release_id, _validate_track_id, item
    RELEASE_ROOT = namespace.get('RELEASE_ROOT', RELEASE_ROOT)
    ReleaseConflictError = namespace.get('ReleaseConflictError', ReleaseConflictError)
    ReleaseDocument = namespace.get('ReleaseDocument', ReleaseDocument)
    ReleaseError = namespace.get('ReleaseError', ReleaseError)
    ReleaseNotFoundError = namespace.get('ReleaseNotFoundError', ReleaseNotFoundError)
    ReleaseStateError = namespace.get('ReleaseStateError', ReleaseStateError)
    ReleaseTrack = namespace.get('ReleaseTrack', ReleaseTrack)
    ReleaseValidationError = namespace.get('ReleaseValidationError', ReleaseValidationError)
    _bounded_text = namespace.get('_bounded_text', _bounded_text)
    _export_snapshot = namespace.get('_export_snapshot', _export_snapshot)
    _file_sha256 = namespace.get('_file_sha256', _file_sha256)
    _find_version = namespace.get('_find_version', _find_version)
    _next_track_id = namespace.get('_next_track_id', _next_track_id)
    _optional_bounded_text = namespace.get('_optional_bounded_text', _optional_bounded_text)
    _project_snapshot = namespace.get('_project_snapshot', _project_snapshot)
    _qa_snapshot = namespace.get('_qa_snapshot', _qa_snapshot)
    _read_optional_json = namespace.get('_read_optional_json', _read_optional_json)
    _release_type = namespace.get('_release_type', _release_type)
    _renumber_tracks = namespace.get('_renumber_tracks', _renumber_tracks)
    _safe_dict = namespace.get('_safe_dict', _safe_dict)
    _signoff_snapshot = namespace.get('_signoff_snapshot', _signoff_snapshot)
    _stable_hash = namespace.get('_stable_hash', _stable_hash)
    _stale_summary = namespace.get('_stale_summary', _stale_summary)
    _track_title = namespace.get('_track_title', _track_title)
    _validate_release_id = namespace.get('_validate_release_id', _validate_release_id)
    _validate_track_id = namespace.get('_validate_track_id', _validate_track_id)
    item = namespace.get('item', item)
    _bind_deferred_defaults(namespace)


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

    def create_release(self, payload: DomainDocument) -> ReleaseDocument:
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

    def update_release(self, release_id: str, patch: DomainDocument) -> ReleaseDocument:
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

    def delete_release(self, release_id: str) -> DomainDocument:
        with self.lock:
            release_dir = self.release_dir(release_id)
            self.ensure_release_dir_is_safe(release_dir)
            if not release_dir.exists():
                raise ReleaseNotFoundError(release_id)
            shutil.rmtree(release_dir)
            return {"release_id": release_id, "deleted": True}

    def add_track(self, release_id: str, payload: DomainDocument) -> ReleaseDocument:
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

    def reorder_tracks(self, release_id: str, payload: DomainDocument) -> ReleaseDocument:
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

    def update_qa_summary(self, release_id: str, summary: DomainDocument) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.latest_qa_summary = _safe_dict(summary)
            status = str(summary.get("status") or "")
            if document.status != "archived":
                document.status = {"passed": "qa_passed", "warning": "qa_warning", "failed": "qa_failed", "stale": "qa_failed"}.get(status, document.status)
            return self.save_release(document)

    def update_export_summary(self, release_id: str, summary: DomainDocument) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.latest_export_summary = _safe_dict(summary)
            if document.status not in {"signed", "archived"}:
                document.status = "exported"
            return self.save_release(document)

    def update_signoff_summary(self, release_id: str, summary: DomainDocument) -> ReleaseDocument:
        with self.lock:
            document = self.get_release(release_id)
            document.latest_signoff_summary = _safe_dict(summary)
            status = str(summary.get("status") or "")
            if status in {"signed", "force_signed"} and document.status != "archived":
                document.status = "signed"
            return self.save_release(document)

    def read_qa(self, release_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.release_dir(release_id) / "release-qa.json"
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseNotFoundError("Release QA does not exist.")
        return _safe_dict(read_json(path))

    def write_qa(self, release_id: str, report: DomainDocument) -> DomainDocument:
        self.get_release(release_id)
        clean = _safe_dict(report)
        write_json(self.release_dir(release_id) / "release-qa.json", clean)
        return clean

    def read_signoff(self, release_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.release_dir(release_id) / "release-signoff.json"
        if not path.exists():
            if default is not None:
                return default
            raise ReleaseNotFoundError("Release signoff does not exist.")
        return _safe_dict(read_json(path))

    def write_signoff(self, release_id: str, record: DomainDocument) -> DomainDocument:
        self.get_release(release_id)
        clean = _safe_dict(record)
        write_json(self.release_dir(release_id) / "release-signoff.json", clean)
        return clean

    def reset_signoff(self, release_id: str, history_event: DomainDocument) -> DomainDocument:
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

    def read_events(self, release_id: str) -> list[DomainDocument]:
        path = self.release_dir(release_id) / "events.jsonl"
        if not path.exists():
            return []
        events: list[DomainDocument] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return sanitize_metadata(events, blocked_keys=BLOCKED_RELEASE_KEYS)

    def append_event(self, release_id: str, event_type: str, payload: DomainDocument) -> None:
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

def release_summary(document: ReleaseDocument) -> DomainDocument:
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
