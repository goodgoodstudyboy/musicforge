from __future__ import annotations

from song_agent.platform.contracts.documents import DomainDocument, ImplementationDocument

import re as re
import threading as threading
from dataclasses import dataclass as dataclass
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, stable_hash as stable_hash


MASTERING_PROFILE_SCHEMA_VERSION = 1
PROFILE_ID_RE = re.compile(r"^(mprof-[a-z0-9-]+|[a-z0-9][a-z0-9_-]{2,80})$")
PROFILE_INTEGRITY_EXCLUDE = {"integrity_hash"}


class MasteringProfileError(ValueError):
    pass


class MasteringProfileNotFoundError(MasteringProfileError):
    pass


BUILTIN_MASTERING_PROFILES: dict[str, ImplementationDocument] = {
    "streaming_balanced": {
        "name": "Streaming Balanced",
        "target_type": "streaming",
        "sample_rate": 44100,
        "channels": 2,
        "bit_depth": 16,
        "target_loudness_proxy_db": -15.0,
        "loudness_tolerance_db": 8.0,
        "max_peak_dbfs": -0.5,
        "max_clipping_ratio": 0.001,
        "max_track_loudness_delta_db": 3.0,
        "max_leading_silence_seconds": 2.0,
        "max_trailing_silence_seconds": 4.0,
        "min_duration_seconds": 8.0,
        "max_duration_seconds": 600.0,
        "allow_warning_signoff": False,
    },
    "demo_review": {
        "name": "Demo Review",
        "target_type": "demo",
        "sample_rate": 44100,
        "channels": 2,
        "bit_depth": 16,
        "target_loudness_proxy_db": -15.0,
        "loudness_tolerance_db": 10.0,
        "max_peak_dbfs": -0.1,
        "max_clipping_ratio": 0.005,
        "max_track_loudness_delta_db": 6.0,
        "max_leading_silence_seconds": 3.0,
        "max_trailing_silence_seconds": 6.0,
        "min_duration_seconds": 8.0,
        "max_duration_seconds": 600.0,
        "allow_warning_signoff": True,
    },
    "album_consistency": {
        "name": "Album Consistency",
        "target_type": "album",
        "sample_rate": 44100,
        "channels": 2,
        "bit_depth": 16,
        "target_loudness_proxy_db": -15.0,
        "loudness_tolerance_db": 6.0,
        "max_peak_dbfs": -0.5,
        "max_clipping_ratio": 0.001,
        "max_track_loudness_delta_db": 2.0,
        "max_leading_silence_seconds": 2.0,
        "max_trailing_silence_seconds": 4.0,
        "min_duration_seconds": 8.0,
        "max_duration_seconds": 600.0,
        "allow_warning_signoff": False,
    },
    "podcast_music_bed": {
        "name": "Podcast Music Bed",
        "target_type": "podcast_music_bed",
        "sample_rate": 44100,
        "channels": 2,
        "bit_depth": 16,
        "target_loudness_proxy_db": -18.0,
        "loudness_tolerance_db": 8.0,
        "max_peak_dbfs": -1.0,
        "max_clipping_ratio": 0.001,
        "max_track_loudness_delta_db": 4.0,
        "max_leading_silence_seconds": 2.0,
        "max_trailing_silence_seconds": 5.0,
        "min_duration_seconds": 8.0,
        "max_duration_seconds": 1200.0,
        "allow_warning_signoff": True,
    },
}


@dataclass(frozen=True)
class MasteringProfile:
    schema_version: int
    profile_id: str
    name: str
    target_type: str
    sample_rate: int
    channels: int
    bit_depth: int
    target_loudness_proxy_db: float
    loudness_tolerance_db: float
    max_peak_dbfs: float
    max_clipping_ratio: float
    max_track_loudness_delta_db: float
    max_leading_silence_seconds: float
    max_trailing_silence_seconds: float
    min_duration_seconds: float
    max_duration_seconds: float
    allow_warning_signoff: bool
    built_in: bool
    notes: str
    created_at: str
    updated_at: str
    integrity_hash: str

    def to_dict(self) -> DomainDocument:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "name": self.name,
            "target_type": self.target_type,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "target_loudness_proxy_db": self.target_loudness_proxy_db,
            "loudness_tolerance_db": self.loudness_tolerance_db,
            "max_peak_dbfs": self.max_peak_dbfs,
            "max_clipping_ratio": self.max_clipping_ratio,
            "max_track_loudness_delta_db": self.max_track_loudness_delta_db,
            "max_leading_silence_seconds": self.max_leading_silence_seconds,
            "max_trailing_silence_seconds": self.max_trailing_silence_seconds,
            "min_duration_seconds": self.min_duration_seconds,
            "max_duration_seconds": self.max_duration_seconds,
            "allow_warning_signoff": self.allow_warning_signoff,
            "built_in": self.built_in,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "integrity_hash": self.integrity_hash,
        }

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "MasteringProfile":
        profile = cls(
            schema_version=int(data.get("schema_version") or MASTERING_PROFILE_SCHEMA_VERSION),
            profile_id=_validate_profile_id(str(data.get("profile_id") or "")),
            name=sanitize_sensitive_text(str(data.get("name") or "Mastering Profile"))[:160],
            target_type=sanitize_sensitive_text(str(data.get("target_type") or "custom"))[:80],
            sample_rate=_int_range(data.get("sample_rate"), "sample_rate", 8000, 384000),
            channels=_int_range(data.get("channels"), "channels", 1, 8),
            bit_depth=_int_range(data.get("bit_depth"), "bit_depth", 8, 32),
            target_loudness_proxy_db=_float_range(data.get("target_loudness_proxy_db"), "target_loudness_proxy_db", -80.0, 0.0),
            loudness_tolerance_db=_float_range(data.get("loudness_tolerance_db"), "loudness_tolerance_db", 0.1, 40.0),
            max_peak_dbfs=_float_range(data.get("max_peak_dbfs"), "max_peak_dbfs", -60.0, 0.0),
            max_clipping_ratio=_float_range(data.get("max_clipping_ratio"), "max_clipping_ratio", 0.0, 1.0),
            max_track_loudness_delta_db=_float_range(data.get("max_track_loudness_delta_db"), "max_track_loudness_delta_db", 0.0, 80.0),
            max_leading_silence_seconds=_float_range(data.get("max_leading_silence_seconds"), "max_leading_silence_seconds", 0.0, 120.0),
            max_trailing_silence_seconds=_float_range(data.get("max_trailing_silence_seconds"), "max_trailing_silence_seconds", 0.0, 120.0),
            min_duration_seconds=_float_range(data.get("min_duration_seconds"), "min_duration_seconds", 0.0, 7200.0),
            max_duration_seconds=_float_range(data.get("max_duration_seconds"), "max_duration_seconds", 1.0, 7200.0),
            allow_warning_signoff=bool(data.get("allow_warning_signoff", False)),
            built_in=bool(data.get("built_in", False)),
            notes=sanitize_sensitive_text(str(data.get("notes") or ""))[:1000],
            created_at=str(data.get("created_at") or now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now_iso()),
            integrity_hash=str(data.get("integrity_hash") or ""),
        )
        if profile.max_duration_seconds < profile.min_duration_seconds:
            raise MasteringProfileError("max_duration_seconds must be greater than min_duration_seconds.")
        return profile


class MasteringProfileStore:
    def __init__(self, root: Path | str = Path(".musicforge") / "mastering-profiles") -> None:
        self.root = Path(root)
        self.lock = threading.RLock()

    def list_profiles(self, *, include_builtins: bool = True) -> list[MasteringProfile]:
        profiles: list[MasteringProfile] = []
        if include_builtins:
            profiles.extend(builtin_profiles())
        if self.root.exists():
            for path in sorted(self.root.glob("*/profile.json")):
                try:
                    profile = MasteringProfile.from_dict(read_json(path))
                except Exception:
                    continue
                profiles.append(profile)
        dedup: dict[str, MasteringProfile] = {}
        for profile in profiles:
            dedup[profile.profile_id] = profile
        return sorted(dedup.values(), key=lambda item: (not item.built_in, item.name.lower(), item.profile_id))

    def get_profile(self, profile_id: str) -> MasteringProfile:
        profile_id = _validate_profile_id(profile_id or "streaming_balanced")
        if profile_id in BUILTIN_MASTERING_PROFILES:
            return builtin_profile(profile_id)
        path = self.profile_path(profile_id)
        if not path.exists():
            raise MasteringProfileNotFoundError(f"Mastering profile not found: {profile_id}.")
        profile = MasteringProfile.from_dict(read_json(path))
        if not mastering_profile_integrity_ok(profile.to_dict()):
            raise MasteringProfileError("Mastering profile integrity failed.")
        return profile

    def create_profile(self, payload: DomainDocument, *, now: str | None = None) -> MasteringProfile:
        now = now or now_iso()
        with self.lock:
            profile_id = str(payload.get("profile_id") or self._reserve_profile_id())
            if profile_id in BUILTIN_MASTERING_PROFILES:
                raise MasteringProfileError("Built-in mastering profiles are read-only; clone them before editing.")
            profile = _profile_from_payload({**payload, "profile_id": profile_id, "built_in": False}, now=now)
            self._write_profile(profile)
            return profile

    def update_profile(self, profile_id: str, payload: DomainDocument, *, now: str | None = None) -> MasteringProfile:
        now = now or now_iso()
        profile_id = _validate_profile_id(profile_id)
        if profile_id in BUILTIN_MASTERING_PROFILES:
            raise MasteringProfileError("Built-in mastering profiles are read-only; clone them before editing.")
        existing = self.get_profile(profile_id)
        merged = {**existing.to_dict(), **payload, "profile_id": profile_id, "built_in": False, "created_at": existing.created_at, "updated_at": now}
        profile = _profile_from_payload(merged, now=now)
        self._write_profile(profile)
        return profile

    def clone_profile(self, profile_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> MasteringProfile:
        now = now or now_iso()
        source = self.get_profile(profile_id)
        payload = payload or {}
        clone_id = str(payload.get("profile_id") or self._reserve_profile_id())
        clone = {
            **source.to_dict(),
            **payload,
            "profile_id": clone_id,
            "name": str(payload.get("name") or f"{source.name} Copy"),
            "built_in": False,
            "created_at": now,
            "updated_at": now,
            "integrity_hash": "",
        }
        profile = _profile_from_payload(clone, now=now)
        self._write_profile(profile)
        return profile

    def delete_profile(self, profile_id: str) -> None:
        profile_id = _validate_profile_id(profile_id)
        if profile_id in BUILTIN_MASTERING_PROFILES:
            raise MasteringProfileError("Built-in mastering profiles cannot be deleted.")
        path = self.profile_path(profile_id)
        if not path.exists():
            raise MasteringProfileNotFoundError(f"Mastering profile not found: {profile_id}.")
        path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def profile_path(self, profile_id: str) -> Path:
        return self.root / _validate_profile_id(profile_id) / "profile.json"

    def _write_profile(self, profile: MasteringProfile) -> None:
        write_json(self.profile_path(profile.profile_id), sanitize_metadata(profile.to_dict(), blocked_keys=BLOCKED_RELEASE_KEYS))

    def _reserve_profile_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            profile_id = f"mprof-{index:06d}"
            if not self.profile_path(profile_id).exists():
                return profile_id
        raise MasteringProfileError("Unable to allocate mastering profile id.")


def builtin_profiles() -> list[MasteringProfile]:
    return [builtin_profile(profile_id) for profile_id in BUILTIN_MASTERING_PROFILES]


def builtin_profile(profile_id: str) -> MasteringProfile:
    now = "builtin"
    payload = {
        **BUILTIN_MASTERING_PROFILES[_validate_profile_id(profile_id)],
        "schema_version": MASTERING_PROFILE_SCHEMA_VERSION,
        "profile_id": profile_id,
        "built_in": True,
        "notes": "",
        "created_at": now,
        "updated_at": now,
    }
    return _profile_from_payload(payload, now=now)


def mastering_profile_hash(profile: MasteringProfile | DomainDocument) -> str:
    data = profile.to_dict() if isinstance(profile, MasteringProfile) else profile
    return stable_hash(sanitize_metadata({key: value for key, value in data.items() if key not in PROFILE_INTEGRITY_EXCLUDE}, blocked_keys=BLOCKED_RELEASE_KEYS))


def mastering_profile_integrity_ok(profile: DomainDocument) -> bool:
    expected = str(profile.get("integrity_hash") or "")
    return bool(expected) and expected == mastering_profile_hash(profile)


def _profile_from_payload(payload: ImplementationDocument, *, now: str) -> MasteringProfile:
    data = {
        "schema_version": MASTERING_PROFILE_SCHEMA_VERSION,
        "profile_id": payload.get("profile_id"),
        "name": payload.get("name") or "Mastering Profile",
        "target_type": payload.get("target_type") or "custom",
        "sample_rate": payload.get("sample_rate", 44100),
        "channels": payload.get("channels", 2),
        "bit_depth": payload.get("bit_depth", 16),
        "target_loudness_proxy_db": payload.get("target_loudness_proxy_db", -15.0),
        "loudness_tolerance_db": payload.get("loudness_tolerance_db", 8.0),
        "max_peak_dbfs": payload.get("max_peak_dbfs", -0.5),
        "max_clipping_ratio": payload.get("max_clipping_ratio", 0.001),
        "max_track_loudness_delta_db": payload.get("max_track_loudness_delta_db", 3.0),
        "max_leading_silence_seconds": payload.get("max_leading_silence_seconds", 2.0),
        "max_trailing_silence_seconds": payload.get("max_trailing_silence_seconds", 4.0),
        "min_duration_seconds": payload.get("min_duration_seconds", 8.0),
        "max_duration_seconds": payload.get("max_duration_seconds", 600.0),
        "allow_warning_signoff": bool(payload.get("allow_warning_signoff", False)),
        "built_in": bool(payload.get("built_in", False)),
        "notes": payload.get("notes") or "",
        "created_at": payload.get("created_at") or now,
        "updated_at": payload.get("updated_at") or now,
    }
    profile = MasteringProfile.from_dict(data)
    clean = profile.to_dict()
    clean["integrity_hash"] = mastering_profile_hash(clean)
    return MasteringProfile.from_dict(clean)


def _validate_profile_id(value: str) -> str:
    profile_id = str(value or "").strip()
    if not PROFILE_ID_RE.match(profile_id):
        raise MasteringProfileError("Invalid mastering profile id.")
    return profile_id


def _int_range(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MasteringProfileError(f"{field} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise MasteringProfileError(f"{field} must be between {minimum} and {maximum}.")
    return parsed


def _float_range(value: Any, field: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise MasteringProfileError(f"{field} must be a number.") from exc
    if parsed < minimum or parsed > maximum:
        raise MasteringProfileError(f"{field} must be between {minimum} and {maximum}.")
    return round(parsed, 6)
