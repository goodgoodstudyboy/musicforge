from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.creation.renderers.audio import RendererConfig, RendererError, test_renderer_config


AUDIO_PROFILE_SCHEMA_VERSION = 1
AUDIO_PROFILE_ROOT = Path(".musicforge") / "audio-profiles"


class AudioProfileError(ValueError):
    pass


class AudioProfileNotFoundError(AudioProfileError):
    pass


@dataclass
class RendererProfile:
    profile_id: str
    name: str
    engine: str
    enabled: bool
    is_default: bool
    engine_path: str
    soundfont_path: str
    sample_rate: int = 44100
    channels: int = 2
    bit_depth: int = 16
    gain: float = 0.6
    timeout_seconds: int = 60
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RendererProfile":
        now = now_iso()
        return cls(
            profile_id=_profile_id(str(data.get("profile_id") or "arp-000001")),
            name=_bounded(data.get("name"), 120) or "Local FluidSynth GM",
            engine=str(data.get("engine") or data.get("renderer_type") or "fluidsynth").strip() or "fluidsynth",
            enabled=bool(data.get("enabled", True)),
            is_default=bool(data.get("is_default", False)),
            engine_path=str(data.get("engine_path") or data.get("fluidsynth_path") or "fluidsynth").strip(),
            soundfont_path=str(data.get("soundfont_path") or "").strip(),
            sample_rate=int(data.get("sample_rate") or 44100),
            channels=int(data.get("channels") or 2),
            bit_depth=int(data.get("bit_depth") or 16),
            gain=float(data.get("gain") if data.get("gain") not in {None, ""} else 0.6),
            timeout_seconds=max(1, int(data.get("timeout_seconds") or 60)),
            created_at=str(data.get("created_at") or now),
            updated_at=str(data.get("updated_at") or now),
        )

    def validate(self) -> None:
        if self.engine != "fluidsynth":
            raise AudioProfileError("Only fluidsynth renderer profiles are supported.")
        if not self.engine_path:
            raise AudioProfileError("engine_path is required.")
        if self.sample_rate < 8000 or self.sample_rate > 192000:
            raise AudioProfileError("sample_rate must be between 8000 and 192000.")
        if self.channels not in {1, 2}:
            raise AudioProfileError("channels must be 1 or 2.")
        if self.bit_depth not in {16, 24, 32}:
            raise AudioProfileError("bit_depth must be 16, 24, or 32.")
        if self.gain < 0 or self.gain > 10:
            raise AudioProfileError("gain must be between 0 and 10.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": AUDIO_PROFILE_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "name": self.name,
            "engine": self.engine,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "engine_path": self.engine_path,
            "soundfont_path": self.soundfont_path,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "gain": self.gain,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_renderer_config(self) -> RendererConfig:
        return RendererConfig(renderer_type="fluidsynth", fluidsynth_path=self.engine_path, soundfont_path=self.soundfont_path, sample_rate=self.sample_rate, output_format="wav", gain=self.gain)

    def public_summary(self) -> dict[str, Any]:
        payload = self.to_dict()
        payload.pop("engine_path", None)
        payload.pop("soundfont_path", None)
        payload["soundfont_sha256"] = _sha256_path(Path(self.soundfont_path)) if self.soundfont_path and Path(self.soundfont_path).exists() else None
        payload["soundfont_exists"] = bool(self.soundfont_path and Path(self.soundfont_path).exists())
        payload["profile_hash"] = renderer_profile_hash(self)
        payload["paths_redacted"] = True
        return sanitize_metadata(payload)


class AudioProfileStore:
    def __init__(self, root: Path = AUDIO_PROFILE_ROOT) -> None:
        self.root = Path(root)
        self.lock = threading.RLock()

    @property
    def profiles_path(self) -> Path:
        return self.root / "profiles.json"

    def list_profiles(self, *, include_hidden: bool = False) -> list[RendererProfile]:
        profiles = self._read_profiles()
        if not profiles:
            legacy = legacy_renderer_profile()
            profiles = [legacy] if legacy is not None else []
        if include_hidden:
            return profiles
        return [profile for profile in profiles if profile.enabled]

    def get_profile(self, profile_id: str | None = None) -> RendererProfile:
        profiles = self._read_profiles()
        if not profiles:
            profile = legacy_renderer_profile()
            if profile is None:
                raise AudioProfileNotFoundError("Audio profile is not configured.")
            return profile
        target = _profile_id(profile_id) if profile_id else None
        if target:
            for profile in profiles:
                if profile.profile_id == target:
                    return profile
            raise AudioProfileNotFoundError(f"Audio profile not found: {target}.")
        default = next((profile for profile in profiles if profile.is_default), None)
        return default or profiles[0]

    def upsert_profile(self, payload: dict[str, Any]) -> RendererProfile:
        with self.lock:
            profiles = self._read_profiles()
            now = now_iso()
            profile_id = str(payload.get("profile_id") or "").strip()
            if profile_id:
                profile_id = _profile_id(profile_id)
            else:
                profile_id = self._next_profile_id(profiles)
            existing = next((profile for profile in profiles if profile.profile_id == profile_id), None)
            merged = {**(existing.to_dict() if existing else {}), **payload, "profile_id": profile_id, "updated_at": now}
            if existing is None:
                merged["created_at"] = now
            profile = RendererProfile.from_dict(merged)
            profile.validate()
            if profile.is_default:
                profiles = [RendererProfile.from_dict({**item.to_dict(), "is_default": item.profile_id == profile.profile_id}) for item in profiles]
            profiles = [item for item in profiles if item.profile_id != profile.profile_id]
            if not profiles:
                profile.is_default = True
            profiles.append(profile)
            self._write_profiles(profiles)
            self._append_event("profile_upserted", {"profile_id": profile.profile_id})
            return profile

    def set_default(self, profile_id: str) -> RendererProfile:
        with self.lock:
            profiles = self._read_profiles()
            target = _profile_id(profile_id)
            found = False
            updated = []
            for profile in profiles:
                data = profile.to_dict()
                data["is_default"] = profile.profile_id == target
                if profile.profile_id == target:
                    found = True
                    data["enabled"] = True
                updated.append(RendererProfile.from_dict(data))
            if not found:
                raise AudioProfileNotFoundError(f"Audio profile not found: {target}.")
            self._write_profiles(updated)
            self._append_event("profile_default_set", {"profile_id": target})
            return self.get_profile(target)

    def hide(self, profile_id: str, *, hidden: bool = True) -> RendererProfile:
        with self.lock:
            profiles = self._read_profiles()
            target = _profile_id(profile_id)
            updated = []
            found = False
            for profile in profiles:
                data = profile.to_dict()
                if profile.profile_id == target:
                    found = True
                    data["enabled"] = not hidden
                    if hidden:
                        data["is_default"] = False
                updated.append(RendererProfile.from_dict(data))
            if not found:
                raise AudioProfileNotFoundError(f"Audio profile not found: {target}.")
            if updated and not any(profile.is_default and profile.enabled for profile in updated):
                for profile in updated:
                    if profile.enabled:
                        profile.is_default = True
                        break
            self._write_profiles(updated)
            self._append_event("profile_hidden" if hidden else "profile_unhidden", {"profile_id": target})
            return next(profile for profile in updated if profile.profile_id == target)

    def test_profile(self, profile_id: str) -> dict[str, Any]:
        profile = self.get_profile(profile_id)
        try:
            result = test_renderer_config(profile.to_renderer_config(), timeout_seconds=profile.timeout_seconds)
            status = "passed"
            message = result.get("message") or "Renderer profile test passed."
        except RendererError as exc:
            status = "failed"
            message = sanitize_sensitive_text(str(exc))
        return sanitize_metadata({"profile": profile.public_summary(), "status": status, "message": message})

    def _read_profiles(self) -> list[RendererProfile]:
        if not self.profiles_path.exists():
            return []
        data = read_json(self.profiles_path)
        rows = data.get("profiles") if isinstance(data, dict) else []
        return [RendererProfile.from_dict(item) for item in rows if isinstance(item, dict)]

    def _write_profiles(self, profiles: list[RendererProfile]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        write_json(self.profiles_path, {"schema_version": AUDIO_PROFILE_SCHEMA_VERSION, "profiles": [profile.to_dict() for profile in sorted(profiles, key=lambda item: item.profile_id)]})

    def _next_profile_id(self, profiles: list[RendererProfile]) -> str:
        used = {profile.profile_id for profile in profiles}
        for index in range(1, 1_000_000):
            candidate = f"arp-{index:06d}"
            if candidate not in used:
                return candidate
        raise AudioProfileError("Unable to allocate audio profile id.")

    def _append_event(self, event_type: str, payload: ImplementationDocument) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "events.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(sanitize_metadata({"timestamp": now_iso(), "type": event_type, "payload": payload}), ensure_ascii=False) + "\n")


def renderer_profile_hash(profile: RendererProfile | dict[str, Any]) -> str:
    data = profile.to_dict() if isinstance(profile, RendererProfile) else dict(profile)
    return stable_hash(
        {
            "profile_id": data.get("profile_id"),
            "engine": data.get("engine"),
            "sample_rate": data.get("sample_rate"),
            "channels": data.get("channels"),
            "bit_depth": data.get("bit_depth"),
            "gain": data.get("gain"),
            "soundfont_sha256": _sha256_path(Path(str(data.get("soundfont_path") or ""))) if data.get("soundfont_path") else None,
        }
    )


def legacy_renderer_profile() -> RendererProfile | None:
    path = Path(".musicforge") / "renderer.json"
    if not path.exists():
        return None
    data = read_json(path)
    return RendererProfile.from_dict(
        {
            "profile_id": "arp-legacy",
            "name": "Legacy Renderer",
            "engine": data.get("renderer_type") or "fluidsynth",
            "is_default": True,
            "enabled": True,
            "engine_path": data.get("fluidsynth_path") or "fluidsynth",
            "soundfont_path": data.get("soundfont_path") or "",
            "sample_rate": data.get("sample_rate") or 44100,
            "gain": data.get("gain") if data.get("gain") not in {None, ""} else 0.6,
        }
    )


def _profile_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        raise AudioProfileError("profile_id is required.")
    if text == "arp-legacy":
        return text
    re_match = re.match(r"^arp-[0-9]{6}$", text)
    if not re_match:
        raise AudioProfileError("profile_id must look like arp-000001.")
    return re_match.group(0)


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
