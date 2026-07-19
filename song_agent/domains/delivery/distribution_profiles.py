from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument
from song_agent.platform.contracts.coercion import as_document as _as_document

from dataclasses import dataclass as dataclass, field as field
from typing import Any as Any

from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, stable_hash as stable_hash


DISTRIBUTION_PROFILE_SCHEMA_VERSION = 1
DISTRIBUTION_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}


@dataclass(frozen=True)
class DistributionProfile:
    profile_id: str
    name: str
    description: str
    options: ImplementationDocument = field(default_factory=dict)

    def to_dict(self) -> DomainDocument:
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
            "require_encoded_audio": False,
            "primary_audio_format": "wav_master",
            "audio_format_profiles": ["wav_master"],
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
            "require_encoded_audio": False,
            "primary_audio_format": "wav_master",
            "audio_format_profiles": ["wav_master"],
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
            "require_encoded_audio": False,
            "primary_audio_format": "wav_master",
            "audio_format_profiles": ["wav_master"],
        },
    ),
}


def list_distribution_profiles() -> list[DomainDocument]:
    return [profile.to_dict() for profile in BUILTIN_DISTRIBUTION_PROFILES.values()]


def get_distribution_profile(profile_id: str) -> DomainDocument:
    key = str(profile_id or "").strip() or "generic_dsp"
    profile = BUILTIN_DISTRIBUTION_PROFILES.get(key)
    if profile is None:
        raise ValueError(f"Unsupported distribution profile: {profile_id}.")
    return profile.to_dict()


def merge_profile_options(profile: DomainDocument, overrides: DomainDocument | None = None) -> DomainDocument:
    base = dict(_as_document(profile.get("options")))
    overrides = _as_document(overrides)
    allowed = set(base) | {"artwork_id", "submission_note"}
    for key, value in overrides.items():
        if key not in allowed:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            base[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) or item is None for item in value):
            base[key] = value
    return sanitize_metadata(base, blocked_keys=DISTRIBUTION_BLOCKED_KEYS)
