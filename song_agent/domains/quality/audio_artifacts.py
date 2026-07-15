from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from song_agent.domains.quality.audio_profiles import RendererProfile, renderer_profile_hash
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import now_iso
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.releases import stable_hash
from song_agent.domains.creation.renderers.audio import RendererConfig


AUDIO_ARTIFACT_SCHEMA_VERSION = 1
AUDIO_ARTIFACT_FILENAME = "audio-artifact.json"
_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "current", "stale_reasons"}


def build_audio_artifact_manifest(
    *,
    artifact_id: str,
    scope: str,
    wav_path: Path,
    midi_path: Path,
    song_plan_path: Path,
    renderer_config: RendererConfig,
    profile: RendererProfile | None = None,
    extra_source: dict[str, Any] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    profile_payload = _renderer_profile_payload(profile, renderer_config)
    manifest = {
        "schema_version": AUDIO_ARTIFACT_SCHEMA_VERSION,
        "artifact_id": _safe_text(artifact_id, 120),
        "scope": _safe_text(scope, 80),
        "status": "ready" if wav_path.exists() else "missing",
        "created_at": now,
        "updated_at": now,
        "wav": _file_state(wav_path),
        "midi": _file_state(midi_path),
        "song_plan": _json_file_state(song_plan_path),
        "renderer": profile_payload,
        "source": sanitize_metadata(extra_source or {}),
    }
    manifest["source_hash"] = audio_artifact_source_hash(manifest)
    manifest["integrity_hash"] = audio_artifact_integrity_hash(manifest)
    manifest["current"] = audio_artifact_current(manifest, wav_path=wav_path, midi_path=midi_path, song_plan_path=song_plan_path)
    return sanitize_metadata(manifest)


def write_audio_artifact_manifest(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    clean = sanitize_metadata(manifest)
    write_json(path, clean)
    return clean


def read_audio_artifact_manifest(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default if default is not None else {}
    data = read_json(path)
    return sanitize_metadata(data if isinstance(data, dict) else {})


def audio_artifact_source_hash(manifest: dict[str, Any]) -> str:
    return stable_hash(
        {
            "wav": _state_for_source(manifest.get("wav")),
            "midi": _state_for_source(manifest.get("midi")),
            "song_plan": _state_for_source(manifest.get("song_plan")),
            "renderer": manifest.get("renderer") if isinstance(manifest.get("renderer"), dict) else {},
            "source": manifest.get("source") if isinstance(manifest.get("source"), dict) else {},
        }
    )


def audio_artifact_integrity_hash(manifest: dict[str, Any]) -> str:
    core = {key: value for key, value in manifest.items() if key not in _INTEGRITY_EXCLUDE_KEYS}
    return stable_hash(sanitize_metadata(core))


def audio_artifact_integrity_ok(manifest: dict[str, Any]) -> bool:
    expected = str(manifest.get("integrity_hash") or "")
    return bool(expected) and expected == audio_artifact_integrity_hash(manifest)


def audio_artifact_current(manifest: dict[str, Any], *, wav_path: Path, midi_path: Path, song_plan_path: Path) -> bool:
    return not audio_artifact_stale_reasons(manifest, wav_path=wav_path, midi_path=midi_path, song_plan_path=song_plan_path)


def audio_artifact_stale_reasons(manifest: dict[str, Any], *, wav_path: Path, midi_path: Path, song_plan_path: Path) -> list[str]:
    return audio_artifact_stale_reasons_for_profile(manifest, wav_path=wav_path, midi_path=midi_path, song_plan_path=song_plan_path, profile=None)


def audio_artifact_stale_reasons_for_profile(
    manifest: dict[str, Any],
    *,
    wav_path: Path,
    midi_path: Path,
    song_plan_path: Path,
    profile: RendererProfile | None = None,
) -> list[str]:
    if not manifest:
        return ["missing_manifest"]
    reasons: list[str] = []
    if not audio_artifact_integrity_ok(manifest):
        reasons.append("manifest_integrity")
    if _state_for_source(manifest.get("wav")) != _state_for_source(_file_state(wav_path)):
        reasons.append("wav_changed")
    if _state_for_source(manifest.get("midi")) != _state_for_source(_file_state(midi_path)):
        reasons.append("midi_changed")
    if _state_for_source(manifest.get("song_plan")) != _state_for_source(_json_file_state(song_plan_path)):
        reasons.append("song_plan_changed")
    if profile is not None and isinstance(manifest.get("renderer"), dict):
        renderer = manifest["renderer"]
        if renderer.get("profile_id") == profile.profile_id and renderer.get("profile_hash") != renderer_profile_hash(profile):
            reasons.append("renderer_profile_changed")
    if str(manifest.get("source_hash") or "") != audio_artifact_source_hash(manifest):
        reasons.append("source_hash")
    return reasons


def audio_artifact_summary(manifest: dict[str, Any], *, wav_path: Path | None = None, midi_path: Path | None = None, song_plan_path: Path | None = None) -> dict[str, Any]:
    current = bool(manifest.get("current", False))
    stale_reasons: list[str] = []
    if manifest and wav_path is not None and midi_path is not None and song_plan_path is not None:
        stale_reasons = audio_artifact_stale_reasons(manifest, wav_path=wav_path, midi_path=midi_path, song_plan_path=song_plan_path)
        current = not stale_reasons
    wav = manifest.get("wav") if isinstance(manifest.get("wav"), dict) else {}
    renderer = manifest.get("renderer") if isinstance(manifest.get("renderer"), dict) else {}
    return sanitize_metadata(
        {
            "artifact_id": manifest.get("artifact_id"),
            "scope": manifest.get("scope"),
            "status": manifest.get("status") or "missing",
            "current": current,
            "stale_reasons": stale_reasons,
            "wav_sha256": wav.get("sha256"),
            "wav_size_bytes": wav.get("size_bytes"),
            "renderer_profile_id": renderer.get("profile_id"),
            "renderer_profile_hash": renderer.get("profile_hash"),
            "soundfont_sha256": renderer.get("soundfont_sha256"),
            "source_hash": manifest.get("source_hash"),
            "integrity_hash": manifest.get("integrity_hash"),
        }
    )


def _renderer_profile_payload(profile: RendererProfile | None, config: RendererConfig) -> dict[str, Any]:
    if profile is not None:
        return {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "engine": profile.engine,
            "profile_hash": renderer_profile_hash(profile),
            "soundfont_sha256": _sha256_path(Path(profile.soundfont_path)) if profile.soundfont_path else None,
            "sample_rate": profile.sample_rate,
            "channels": profile.channels,
            "bit_depth": profile.bit_depth,
            "gain": profile.gain,
            "paths_redacted": True,
        }
    return {
        "profile_id": "renderer-config",
        "name": "Renderer Config",
        "engine": config.renderer_type,
        "profile_hash": stable_hash(
            {
                "renderer_type": config.renderer_type,
                "sample_rate": config.sample_rate,
                "output_format": config.output_format,
                "gain": config.gain,
                "soundfont_sha256": _sha256_path(Path(config.soundfont_path)) if config.soundfont_path else None,
            }
        ),
        "soundfont_sha256": _sha256_path(Path(config.soundfont_path)) if config.soundfont_path else None,
        "sample_rate": config.sample_rate,
        "channels": None,
        "bit_depth": None,
        "gain": config.gain,
        "paths_redacted": True,
    }


def _file_state(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {"exists": False}
    return {"exists": True, "name": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256_path(path)}


def _json_file_state(path: Path) -> dict[str, Any]:
    state = _file_state(path)
    if not state.get("exists"):
        return state
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        payload = {}
    state["payload_hash"] = stable_hash(payload if isinstance(payload, dict) else {})
    return state


def _state_for_source(value: Any) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    return {
        "exists": bool(data.get("exists", False)),
        "size_bytes": data.get("size_bytes"),
        "sha256": data.get("sha256"),
        "payload_hash": data.get("payload_hash"),
    }


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]
