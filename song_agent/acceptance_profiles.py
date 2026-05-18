from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from song_agent.redaction import sanitize_metadata


ACCEPTANCE_PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AcceptanceProfile:
    profile_id: str
    name: str
    case_count: int
    render_audio: str
    require_audio_if_renderer_configured: bool
    min_rating: int
    allow_synthetic_review: bool
    require_manual_review: bool
    release_ready: bool
    songbook_id: str = "builtin_v1"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "schema_version": ACCEPTANCE_PROFILE_SCHEMA_VERSION,
                "profile_id": self.profile_id,
                "name": self.name,
                "case_count": self.case_count,
                "render_audio": self.render_audio,
                "require_audio_if_renderer_configured": self.require_audio_if_renderer_configured,
                "min_rating": self.min_rating,
                "allow_synthetic_review": self.allow_synthetic_review,
                "require_manual_review": self.require_manual_review,
                "release_ready": self.release_ready,
                "songbook_id": self.songbook_id,
                "description": self.description,
            }
        )


BUILTIN_ACCEPTANCE_PROFILES: dict[str, AcceptanceProfile] = {
    "midi_smoke": AcceptanceProfile(
        profile_id="midi_smoke",
        name="MIDI Smoke",
        case_count=2,
        render_audio="never",
        require_audio_if_renderer_configured=False,
        min_rating=3,
        allow_synthetic_review=True,
        require_manual_review=False,
        release_ready=False,
        description="Fast deterministic MIDI-only smoke profile for CI and local sanity checks.",
    ),
    "developer_manual": AcceptanceProfile(
        profile_id="developer_manual",
        name="Developer Manual",
        case_count=6,
        render_audio="auto",
        require_audio_if_renderer_configured=True,
        min_rating=3,
        allow_synthetic_review=True,
        require_manual_review=False,
        release_ready=False,
        description="Developer self-check profile. Synthetic reviews are allowed but do not make release-ready evidence.",
    ),
    "release_candidate": AcceptanceProfile(
        profile_id="release_candidate",
        name="Release Candidate",
        case_count=12,
        render_audio="auto",
        require_audio_if_renderer_configured=True,
        min_rating=4,
        allow_synthetic_review=False,
        require_manual_review=True,
        release_ready=True,
        description="Manual release candidate gate. Synthetic reviews cannot sign this profile as release-ready.",
    ),
    "audio_required": AcceptanceProfile(
        profile_id="audio_required",
        name="Audio Required",
        case_count=12,
        render_audio="always",
        require_audio_if_renderer_configured=True,
        min_rating=4,
        allow_synthetic_review=False,
        require_manual_review=True,
        release_ready=True,
        description="Strict release profile requiring rendered WAV artifacts and manual playback reviews.",
    ),
}


def list_acceptance_profiles() -> list[dict[str, Any]]:
    return [profile.to_dict() for profile in BUILTIN_ACCEPTANCE_PROFILES.values()]


def get_acceptance_profile(profile_id: str | None) -> AcceptanceProfile:
    key = str(profile_id or "developer_manual").strip() or "developer_manual"
    try:
        return BUILTIN_ACCEPTANCE_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown acceptance profile: {key}.") from exc


def profile_payload(profile: AcceptanceProfile) -> dict[str, Any]:
    return profile.to_dict()
