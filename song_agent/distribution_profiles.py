from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from song_agent.redaction import sanitize_metadata
from song_agent.releases import BLOCKED_RELEASE_KEYS, stable_hash


DISTRIBUTION_PROFILE_SCHEMA_VERSION = 1
DISTRIBUTION_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}


@dataclass(frozen=True)
class DistributionProfile:
    profile_id: str
    name: str
    description: str
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": DISTRIBUTION_PROFILE_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "name": self.name,
            "description": self.description,
            "options": self.options,
        }
        data = sanitize_metadata(payload, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
        data["profile_hash"] = stable_hash(payload)
        return data


BUILTIN_DISTRIBUTION_PROFILES: dict[str, DistributionProfile] = {
    "generic_dsp": DistributionProfile(
        profile_id="generic_dsp",
        name="Generic DSP",
        description="Common platform-ready package with metadata, cover art, and optional audio checks.",
        options={
            "require_release_signed": True,
            "require_release_zip_verified": True,
            "require_metadata_export": True,
            "require_artwork": True,
            "artwork_min_px": 3000,
            "artwork_square": True,
            "artwork_max_bytes": 20 * 1024 * 1024,
            "require_upc": True,
            "require_isrc": True,
            "require_audio": True,
        },
    ),
    "demo_pitch": DistributionProfile(
        profile_id="demo_pitch",
        name="Demo Pitch",
        description="Pitch package for sharing demos without platform identifiers as hard blockers.",
        options={
            "require_release_signed": True,
            "require_release_zip_verified": True,
            "require_metadata_export": True,
            "require_artwork": True,
            "artwork_min_px": 1400,
            "artwork_square": True,
            "artwork_max_bytes": 20 * 1024 * 1024,
            "require_upc": False,
            "require_isrc": False,
            "require_audio": False,
        },
    ),
    "internal_archive": DistributionProfile(
        profile_id="internal_archive",
        name="Internal Archive",
        description="Portable internal archive with signed Release provenance and relaxed platform requirements.",
        options={
            "require_release_signed": True,
            "require_release_zip_verified": True,
            "require_metadata_export": True,
            "require_artwork": False,
            "artwork_min_px": 0,
            "artwork_square": False,
            "artwork_max_bytes": 50 * 1024 * 1024,
            "require_upc": False,
            "require_isrc": False,
            "require_audio": False,
        },
    ),
}


def list_distribution_profiles() -> list[dict[str, Any]]:
    return [profile.to_dict() for profile in BUILTIN_DISTRIBUTION_PROFILES.values()]


def get_distribution_profile(profile_id: str) -> dict[str, Any]:
    key = str(profile_id or "").strip() or "generic_dsp"
    profile = BUILTIN_DISTRIBUTION_PROFILES.get(key)
    if profile is None:
        raise ValueError(f"Unsupported distribution profile: {profile_id}.")
    return profile.to_dict()


def merge_profile_options(profile: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(profile.get("options") if isinstance(profile.get("options"), dict) else {})
    overrides = overrides if isinstance(overrides, dict) else {}
    allowed = set(base) | {"artwork_id", "submission_note"}
    for key, value in overrides.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            base[key] = value
    return sanitize_metadata(base, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
