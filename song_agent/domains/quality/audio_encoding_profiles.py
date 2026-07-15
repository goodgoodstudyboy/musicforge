from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS, stable_hash


AUDIO_ENCODING_PROFILE_SCHEMA_VERSION = 1
PROFILE_ID_RE = re.compile(r"^(aenc-[a-z0-9-]+|[a-z0-9][a-z0-9_-]{2,80})$")
PROFILE_INTEGRITY_EXCLUDE = {"integrity_hash"}
SUPPORTED_FORMATS = {"wav", "mp3", "flac", "aac"}
SUPPORTED_ENGINES = {"passthrough", "ffmpeg", "fake"}


class AudioEncodingProfileError(ValueError):
    pass


class AudioEncodingProfileNotFoundError(AudioEncodingProfileError):
    pass


BUILTIN_AUDIO_ENCODING_PROFILES: dict[str, dict[str, Any]] = {
    "wav_master": {
        "name": "WAV Master",
        "engine": "passthrough",
        "format": "wav",
        "extension": "wav",
        "codec": "pcm_s16le",
        "bitrate_kbps": None,
        "quality": None,
        "sample_rate": 44100,
        "channels": 2,
        "container": "wav",
        "compression_level": None,
        "allow_distribution": True,
        "allow_warning_signoff": False,
    },
    "mp3_320": {
        "name": "MP3 320 kbps",
        "engine": "ffmpeg",
        "format": "mp3",
        "extension": "mp3",
        "codec": "libmp3lame",
        "bitrate_kbps": 320,
        "quality": None,
        "sample_rate": 44100,
        "channels": 2,
        "container": "mp3",
        "compression_level": None,
        "allow_distribution": True,
        "allow_warning_signoff": False,
    },
    "mp3_v0": {
        "name": "MP3 V0",
        "engine": "ffmpeg",
        "format": "mp3",
        "extension": "mp3",
        "codec": "libmp3lame",
        "bitrate_kbps": None,
        "quality": "0",
        "sample_rate": 44100,
        "channels": 2,
        "container": "mp3",
        "compression_level": None,
        "allow_distribution": True,
        "allow_warning_signoff": False,
    },
    "flac_lossless": {
        "name": "FLAC Lossless",
        "engine": "ffmpeg",
        "format": "flac",
        "extension": "flac",
        "codec": "flac",
        "bitrate_kbps": None,
        "quality": None,
        "sample_rate": 44100,
        "channels": 2,
        "container": "flac",
        "compression_level": 8,
        "allow_distribution": True,
        "allow_warning_signoff": False,
    },
    "aac_256": {
        "name": "AAC 256 kbps",
        "engine": "ffmpeg",
        "format": "aac",
        "extension": "m4a",
        "codec": "aac",
        "bitrate_kbps": 256,
        "quality": None,
        "sample_rate": 44100,
        "channels": 2,
        "container": "ipod",
        "compression_level": None,
        "allow_distribution": True,
        "allow_warning_signoff": False,
    },
}


@dataclass(frozen=True)
class AudioEncodingProfile:
    schema_version: int
    profile_id: str
    name: str
    engine: str
    format: str
    extension: str
    codec: str
    bitrate_kbps: int | None
    quality: str | None
    sample_rate: int
    channels: int
    container: str
    compression_level: int | None
    allow_distribution: bool
    allow_warning_signoff: bool
    built_in: bool
    notes: str
    created_at: str
    updated_at: str
    integrity_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "name": self.name,
            "engine": self.engine,
            "format": self.format,
            "extension": self.extension,
            "codec": self.codec,
            "bitrate_kbps": self.bitrate_kbps,
            "quality": self.quality,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "container": self.container,
            "compression_level": self.compression_level,
            "allow_distribution": self.allow_distribution,
            "allow_warning_signoff": self.allow_warning_signoff,
            "built_in": self.built_in,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "integrity_hash": self.integrity_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AudioEncodingProfile":
        fmt = _safe_format(data.get("format"))
        extension = _safe_extension(data.get("extension") or fmt)
        profile = cls(
            schema_version=int(data.get("schema_version") or AUDIO_ENCODING_PROFILE_SCHEMA_VERSION),
            profile_id=_validate_profile_id(str(data.get("profile_id") or "")),
            name=sanitize_sensitive_text(str(data.get("name") or "Audio Encoding Profile"))[:160],
            engine=_safe_engine(data.get("engine")),
            format=fmt,
            extension=extension,
            codec=sanitize_sensitive_text(str(data.get("codec") or _default_codec(fmt)))[:80],
            bitrate_kbps=_optional_int_range(data.get("bitrate_kbps"), "bitrate_kbps", 8, 2000),
            quality=_optional_text(data.get("quality"), 40),
            sample_rate=_int_range(data.get("sample_rate") or 44100, "sample_rate", 8000, 384000),
            channels=_int_range(data.get("channels") or 2, "channels", 1, 8),
            container=sanitize_sensitive_text(str(data.get("container") or _default_container(fmt)))[:80],
            compression_level=_optional_int_range(data.get("compression_level"), "compression_level", 0, 12),
            allow_distribution=bool(data.get("allow_distribution", True)),
            allow_warning_signoff=bool(data.get("allow_warning_signoff", False)),
            built_in=bool(data.get("built_in", False)),
            notes=sanitize_sensitive_text(str(data.get("notes") or ""))[:1000],
            created_at=str(data.get("created_at") or now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or now_iso()),
            integrity_hash=str(data.get("integrity_hash") or ""),
        )
        if profile.format == "wav" and profile.extension != "wav":
            raise AudioEncodingProfileError("WAV profiles must use .wav extension.")
        if profile.format == "mp3" and profile.extension != "mp3":
            raise AudioEncodingProfileError("MP3 profiles must use .mp3 extension.")
        if profile.format == "flac" and profile.extension != "flac":
            raise AudioEncodingProfileError("FLAC profiles must use .flac extension.")
        if profile.format == "aac" and profile.extension not in {"m4a", "aac"}:
            raise AudioEncodingProfileError("AAC profiles must use .m4a or .aac extension.")
        if profile.engine == "passthrough" and profile.format != "wav":
            raise AudioEncodingProfileError("Only WAV profiles can use passthrough engine.")
        return profile


class AudioEncodingProfileStore:
    def __init__(self, root: Path | str = Path(".musicforge") / "audio-encoding-profiles") -> None:
        self.root = Path(root)
        self.lock = threading.RLock()

    def list_profiles(self, *, include_builtins: bool = True) -> list[AudioEncodingProfile]:
        profiles: list[AudioEncodingProfile] = []
        if include_builtins:
            profiles.extend(builtin_profiles())
        if self.root.exists():
            for path in sorted(self.root.glob("*/profile.json")):
                try:
                    profiles.append(AudioEncodingProfile.from_dict(read_json(path)))
                except Exception:
                    continue
        dedup: dict[str, AudioEncodingProfile] = {}
        for profile in profiles:
            dedup[profile.profile_id] = profile
        return sorted(dedup.values(), key=lambda item: (not item.built_in, item.name.lower(), item.profile_id))

    def get_profile(self, profile_id: str) -> AudioEncodingProfile:
        profile_id = _validate_profile_id(profile_id or "wav_master")
        if profile_id in BUILTIN_AUDIO_ENCODING_PROFILES:
            return builtin_profile(profile_id)
        path = self.profile_path(profile_id)
        if not path.exists():
            raise AudioEncodingProfileNotFoundError(f"Audio encoding profile not found: {profile_id}.")
        profile = AudioEncodingProfile.from_dict(read_json(path))
        if not audio_encoding_profile_integrity_ok(profile.to_dict()):
            raise AudioEncodingProfileError("Audio encoding profile integrity failed.")
        return profile

    def create_profile(self, payload: dict[str, Any], *, now: str | None = None) -> AudioEncodingProfile:
        now = now or now_iso()
        with self.lock:
            profile_id = str(payload.get("profile_id") or self._reserve_profile_id())
            if profile_id in BUILTIN_AUDIO_ENCODING_PROFILES:
                raise AudioEncodingProfileError("Built-in audio encoding profiles are read-only; clone them before editing.")
            profile = _profile_from_payload({**payload, "profile_id": profile_id, "built_in": False}, now=now)
            self._write_profile(profile)
            return profile

    def update_profile(self, profile_id: str, payload: dict[str, Any], *, now: str | None = None) -> AudioEncodingProfile:
        now = now or now_iso()
        profile_id = _validate_profile_id(profile_id)
        if profile_id in BUILTIN_AUDIO_ENCODING_PROFILES:
            raise AudioEncodingProfileError("Built-in audio encoding profiles are read-only; clone them before editing.")
        existing = self.get_profile(profile_id)
        merged = {**existing.to_dict(), **payload, "profile_id": profile_id, "built_in": False, "created_at": existing.created_at, "updated_at": now}
        profile = _profile_from_payload(merged, now=now)
        self._write_profile(profile)
        return profile

    def clone_profile(self, profile_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> AudioEncodingProfile:
        now = now or now_iso()
        source = self.get_profile(profile_id)
        payload = payload or {}
        clone = {
            **source.to_dict(),
            **payload,
            "profile_id": str(payload.get("profile_id") or self._reserve_profile_id()),
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
        if profile_id in BUILTIN_AUDIO_ENCODING_PROFILES:
            raise AudioEncodingProfileError("Built-in audio encoding profiles cannot be deleted.")
        path = self.profile_path(profile_id)
        if not path.exists():
            raise AudioEncodingProfileNotFoundError(f"Audio encoding profile not found: {profile_id}.")
        path.unlink()
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def profile_path(self, profile_id: str) -> Path:
        return self.root / _validate_profile_id(profile_id) / "profile.json"

    def _write_profile(self, profile: AudioEncodingProfile) -> None:
        write_json(self.profile_path(profile.profile_id), sanitize_metadata(profile.to_dict(), blocked_keys=BLOCKED_RELEASE_KEYS))

    def _reserve_profile_id(self) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        for index in range(1, 1_000_000):
            profile_id = f"aenc-{index:06d}"
            if not self.profile_path(profile_id).exists():
                return profile_id
        raise AudioEncodingProfileError("Unable to allocate audio encoding profile id.")


def builtin_profiles() -> list[AudioEncodingProfile]:
    return [builtin_profile(profile_id) for profile_id in BUILTIN_AUDIO_ENCODING_PROFILES]


def builtin_profile(profile_id: str) -> AudioEncodingProfile:
    now = "builtin"
    payload = {
        **BUILTIN_AUDIO_ENCODING_PROFILES[_validate_profile_id(profile_id)],
        "schema_version": AUDIO_ENCODING_PROFILE_SCHEMA_VERSION,
        "profile_id": profile_id,
        "built_in": True,
        "notes": "",
        "created_at": now,
        "updated_at": now,
    }
    return _profile_from_payload(payload, now=now)


def audio_encoding_profile_hash(profile: AudioEncodingProfile | dict[str, Any]) -> str:
    data = profile.to_dict() if isinstance(profile, AudioEncodingProfile) else profile
    return stable_hash(sanitize_metadata({key: value for key, value in data.items() if key not in PROFILE_INTEGRITY_EXCLUDE}, blocked_keys=BLOCKED_RELEASE_KEYS))


def audio_encoding_profile_integrity_ok(profile: dict[str, Any]) -> bool:
    expected = str(profile.get("integrity_hash") or "")
    return bool(expected) and expected == audio_encoding_profile_hash(profile)


def _profile_from_payload(payload: dict[str, Any], *, now: str) -> AudioEncodingProfile:
    data = {
        "schema_version": AUDIO_ENCODING_PROFILE_SCHEMA_VERSION,
        "profile_id": payload.get("profile_id"),
        "name": payload.get("name") or "Audio Encoding Profile",
        "engine": payload.get("engine") or "ffmpeg",
        "format": payload.get("format") or "mp3",
        "extension": payload.get("extension") or payload.get("format") or "mp3",
        "codec": payload.get("codec") or _default_codec(str(payload.get("format") or "mp3")),
        "bitrate_kbps": payload.get("bitrate_kbps"),
        "quality": payload.get("quality"),
        "sample_rate": payload.get("sample_rate", 44100),
        "channels": payload.get("channels", 2),
        "container": payload.get("container") or _default_container(str(payload.get("format") or "mp3")),
        "compression_level": payload.get("compression_level"),
        "allow_distribution": bool(payload.get("allow_distribution", True)),
        "allow_warning_signoff": bool(payload.get("allow_warning_signoff", False)),
        "built_in": bool(payload.get("built_in", False)),
        "notes": payload.get("notes") or "",
        "created_at": payload.get("created_at") or now,
        "updated_at": payload.get("updated_at") or now,
    }
    profile = AudioEncodingProfile.from_dict(data)
    clean = profile.to_dict()
    clean["integrity_hash"] = audio_encoding_profile_hash(clean)
    return AudioEncodingProfile.from_dict(clean)


def _validate_profile_id(value: str) -> str:
    profile_id = str(value or "").strip()
    if not PROFILE_ID_RE.match(profile_id):
        raise AudioEncodingProfileError("Invalid audio encoding profile id.")
    return profile_id


def _safe_engine(value: Any) -> str:
    engine = str(value or "ffmpeg").strip().lower()
    if engine not in SUPPORTED_ENGINES:
        raise AudioEncodingProfileError("Unsupported audio encoding engine.")
    return engine


def _safe_format(value: Any) -> str:
    fmt = str(value or "mp3").strip().lower()
    if fmt not in SUPPORTED_FORMATS:
        raise AudioEncodingProfileError("Unsupported audio encoding format.")
    return fmt


def _safe_extension(value: Any) -> str:
    extension = str(value or "").strip().lower().lstrip(".")
    if not extension or not re.fullmatch(r"[a-z0-9]{2,8}", extension):
        raise AudioEncodingProfileError("Invalid audio encoding extension.")
    return extension


def _default_codec(fmt: str) -> str:
    return {"wav": "pcm_s16le", "mp3": "libmp3lame", "flac": "flac", "aac": "aac"}.get(str(fmt).lower(), "copy")


def _default_container(fmt: str) -> str:
    return {"wav": "wav", "mp3": "mp3", "flac": "flac", "aac": "ipod"}.get(str(fmt).lower(), str(fmt).lower())


def _int_range(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AudioEncodingProfileError(f"{field} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise AudioEncodingProfileError(f"{field} must be between {minimum} and {maximum}.")
    return parsed


def _optional_int_range(value: Any, field: str, minimum: int, maximum: int) -> int | None:
    if value in (None, ""):
        return None
    return _int_range(value, field, minimum, maximum)


def _optional_text(value: Any, maximum: int) -> str | None:
    text = sanitize_sensitive_text(str(value or "")).strip()
    return text[:maximum] if text else None
