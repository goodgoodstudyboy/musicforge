# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import shutil as shutil
import threading as threading
from dataclasses import dataclass as dataclass, field as field
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.final_export import final_export_dir as final_export_dir, final_export_zip_path as final_export_zip_path
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, ProjectStore as ProjectStore, ProjectVersion as ProjectVersion, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata


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
    project_snapshot: ImplementationDocument = field(default_factory=dict)
    export_snapshot: ImplementationDocument = field(default_factory=dict)
    qa_snapshot: ImplementationDocument = field(default_factory=dict)
    signoff_snapshot: ImplementationDocument = field(default_factory=dict)
    stale: bool = False
    warnings: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "ReleaseTrack":
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
    metadata: ImplementationDocument = field(default_factory=dict)
    tracks: list[ReleaseTrack] = field(default_factory=list)
    latest_qa_summary: ImplementationDocument = field(default_factory=dict)
    latest_export_summary: ImplementationDocument = field(default_factory=dict)
    latest_signoff_summary: ImplementationDocument = field(default_factory=dict)

    def to_dict(self) -> DomainDocument:
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
    def from_dict(cls, data: DomainDocument) -> "ReleaseDocument":
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


from song_agent.domains.delivery import v142_r_readiness as _v142_r_readiness
from song_agent.domains.delivery.v142_r_readiness import ReleaseStore as ReleaseStore, build_release_track_snapshot as build_release_track_snapshot, release_summary as release_summary
from song_agent.domains.delivery import v142_r_evidence as _v142_r_evidence
from song_agent.domains.delivery.v142_r_evidence import release_document_source as release_document_source, stable_hash as stable_hash, _project_snapshot as _project_snapshot, _export_snapshot as _export_snapshot, _qa_snapshot as _qa_snapshot, _signoff_snapshot as _signoff_snapshot, _track_title as _track_title, _duration_beats as _duration_beats, _find_version as _find_version, _read_optional_json as _read_optional_json, _file_sha256 as _file_sha256, _stable_hash as _stable_hash, _renumber_tracks as _renumber_tracks, _next_track_id as _next_track_id, _stale_summary as _stale_summary, _safe_dict as _safe_dict, _release_type as _release_type, _validate_release_id as _validate_release_id, _validate_track_id as _validate_track_id, _required_id as _required_id, _bounded_text as _bounded_text, _optional_bounded_text as _optional_bounded_text

_v142_r_readiness.bind_globals(globals())
_v142_r_evidence.bind_globals(globals())
