# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_text as _as_text

import hashlib as hashlib
import math as math
import re as re
import struct as struct
import threading as threading
import wave as wave
from collections.abc import Callable as Callable
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.agent.pipeline import SongAgent as SongAgent
from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_summary as audio_health_summary
from song_agent.domains.quality.audio_profiles import AudioProfileNotFoundError as AudioProfileNotFoundError, AudioProfileStore as AudioProfileStore, renderer_profile_hash as renderer_profile_hash
from song_agent.domains.quality.music_acceptance import default_acceptance_song_cases as default_acceptance_song_cases
from song_agent.domains.creation.music_health import analyze_music_health as analyze_music_health, music_health_summary as music_health_summary
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import stable_hash as stable_hash
from song_agent.domains.creation.renderers.audio import RendererError as RendererError, load_renderer_config as load_renderer_config, renderer_configured as renderer_configured, render_audio as render_audio
from song_agent.domains.creation.renderers.midi import render_midi as render_midi
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan, SongRequest as SongRequest
from song_agent.domains.quality.v142_al_readiness import AudioLabStoreReadinessMixin
from song_agent.domains.quality import v142_al_readiness as _v142_al_readiness
from song_agent.domains.quality.v142_al_evidence import AudioLabStoreEvidenceMixin
from song_agent.domains.quality import v142_al_evidence as _v142_al_evidence



AUDIO_LAB_ROOT = Path(".musicforge") / "audio-lab"
AUDIO_LAB_SCHEMA_VERSION = 1
REVIEW_RESULTS = {"accepted", "needs_fix", "rejected"}
MARKER_CATEGORIES = {
    "audio_silent",
    "audio_clipping",
    "mix_balance",
    "unbalanced_mix",
    "harshness",
    "timing",
    "arrangement",
    "mastering",
    "other",
}
MARKER_SEVERITIES = {"low", "medium", "high", "critical"}


class AudioLabError(ValueError):
    pass


class AudioLabNotFoundError(AudioLabError):
    pass


class AudioLabStateError(AudioLabError):
    pass


class AudioLabValidationError(AudioLabError):
    pass


WavWriter = Callable[[Path, Path], Path]


class AudioLabStore(AudioLabStoreReadinessMixin, AudioLabStoreEvidenceMixin):
    def __init__(
        self,
        root: Path | str = AUDIO_LAB_ROOT,
        *,
        audio_profile_store: AudioProfileStore | None = None,
        wav_writer: WavWriter | None = None,
    ) -> None:
        self.root = Path(root)
        self.audio_profile_store = audio_profile_store or AudioProfileStore(self.root.parent / "audio-profiles")
        self.wav_writer = wav_writer
        self.lock = threading.RLock()













































def write_lab_test_wav(_midi_path: Path, wav_path: Path, *, duration_seconds: float = 9.0, sample_rate: int = 44100, amplitude: float = 0.2) -> Path:
    """Test-only WAV writer used by release-check and unit tests, never by public config."""
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frame_count):
            value = int(amplitude * 32767 * math.sin(2 * math.pi * 440 * (index / sample_rate)))
            wav.writeframesraw(struct.pack("<hh", value, value))
    return wav_path


def _renderer_public_summary(config: Any, sources: dict[str, str]) -> ImplementationDocument:
    soundfont = Path(config.soundfont_path) if getattr(config, "soundfont_path", "") else None
    return sanitize_metadata(
        {
            "renderer_type": config.renderer_type,
            "fluidsynth_configured": bool(config.fluidsynth_path),
            "soundfont_configured": bool(config.soundfont_path),
            "soundfont_exists": bool(soundfont and soundfont.exists()),
            "sample_rate": config.sample_rate,
            "output_format": config.output_format,
            "gain": config.gain,
            "sources": {key: value for key, value in sources.items() if key not in {"fluidsynth_path", "soundfont_path"}},
            "paths_redacted": True,
        }
    )


def _default_profile_id(value: Any) -> str | None:
    text = str(value or "").strip()
    return None if text in {"", "default", "None", "null"} else text


def _validate_id(value: str, prefix: str) -> str:
    text = str(value or "").strip()
    if not re.match(rf"^{re.escape(prefix)}-\d{{3,6}}$", text):
        raise AudioLabValidationError(f"Invalid {prefix} id.")
    return text


def _bounded(value: Any, limit: int) -> str:
    return sanitize_sensitive_text(str(value or "").strip())[:limit]


def _review_payload(payload: ImplementationDocument) -> ImplementationDocument:
    result = str(payload.get("result") or payload.get("status") or "").strip()
    if result not in REVIEW_RESULTS:
        raise AudioLabValidationError("review result must be accepted, needs_fix, or rejected.")
    if not bool(payload.get("playback_confirmed", False)):
        raise AudioLabValidationError("playback_confirmed=true is required for manual Audio Lab review.")
    if str(payload.get("review_mode") or "manual") != "manual":
        raise AudioLabValidationError("Audio Lab session review must use review_mode=manual.")
    reviewer_payload = _as_document(payload.get("reviewer"))
    reviewer_name = payload.get("reviewer_name") or reviewer_payload.get("name") or (payload.get("reviewer") if isinstance(payload.get("reviewer"), str) else "")
    reviewer_role = payload.get("reviewer_role") or reviewer_payload.get("role") or payload.get("role")
    reviewer = {"name": _bounded(reviewer_name, 120), "role": _bounded(reviewer_role, 120)}
    if not reviewer["name"] or not reviewer["role"]:
        raise AudioLabValidationError("reviewer name and role are required.")
    rating = max(1, min(5, int(payload.get("rating") or 0)))
    if rating <= 0:
        raise AudioLabValidationError("rating must be 1..5.")
    review = {
        "status": result,
        "result": result,
        "rating": rating,
        "review_mode": "manual",
        "playback_confirmed": True,
        "reviewer": reviewer,
        "notes": _bounded(payload.get("notes"), 2000),
        "reviewed_at": now_iso(),
    }
    return sanitize_metadata(review)


def _comparison_review_payload(payload: ImplementationDocument) -> ImplementationDocument:
    preferred = str(payload.get("preferred") or "").strip()
    if preferred not in {"left", "right", "same"}:
        raise AudioLabValidationError("preferred must be left, right, or same.")
    base = _review_payload({**payload, "result": payload.get("result") or "accepted", "rating": payload.get("rating") or 4})
    base["preferred"] = preferred
    base["rating_delta"] = int(payload.get("rating_delta") or 0)
    return base


def _marker_payload(marker_id: str, item: ImplementationDocument, payload: ImplementationDocument) -> ImplementationDocument:
    category = str(payload.get("category") or "other").strip()
    if category not in MARKER_CATEGORIES:
        category = "other"
    severity = str(payload.get("severity") or "medium").strip()
    if severity not in MARKER_SEVERITIES:
        severity = "medium"
    marker = sanitize_metadata(
        {
            "marker_id": marker_id,
            "created_at": now_iso(),
            "time_seconds": max(0.0, float(payload.get("time_seconds") or 0.0)),
            "category": category,
            "severity": severity,
            "message": _bounded(payload.get("message") or payload.get("notes"), 1000),
            "source": {"item_source_hash": item.get("source_hash"), "wav_sha256": item.get("artifact_hashes", {}).get("wav_sha256")},
            "auto_apply": False,
        }
    )
    marker["source_hash"] = stable_hash(marker["source"])
    marker["integrity_hash"] = _integrity_hash(marker)
    return marker


def _artifact_from_payload(value: Any) -> ImplementationDocument:
    if isinstance(value, dict):
        raw_path = value.get("path") or value.get("artifact_path") or value.get("source_abspath")
        label = str(value.get("label") or "").strip()
        artifact_type = str(value.get("artifact_type") or "").strip()
    else:
        raw_path = value
        label = ""
        artifact_type = ""
    path = Path(str(raw_path or "")).resolve()
    if not path.exists() or not path.is_file():
        raise AudioLabValidationError("Comparison artifact file does not exist.")
    suffix = path.suffix.lower().lstrip(".") or "artifact"
    artifact = {
        "label": _bounded(label, 80) or path.stem,
        "artifact_type": artifact_type or suffix,
        "artifact_hash": _sha256_path(path),
        "size_bytes": path.stat().st_size,
        "filename": path.name,
        "source_abspath": str(path),
        "summary_hash": stable_hash({"filename": path.name, "sha256": _sha256_path(path), "size_bytes": path.stat().st_size}),
    }
    return artifact


def _artifact_source(artifact: ImplementationDocument) -> ImplementationDocument:
    return {"artifact_hash": artifact.get("artifact_hash"), "size_bytes": artifact.get("size_bytes"), "summary_hash": artifact.get("summary_hash")}


def _item_source(item: ImplementationDocument) -> ImplementationDocument:
    return {
        "source_hash": item.get("source_hash"),
        "artifact_hashes": item.get("artifact_hashes"),
        "audio_status": item.get("audio_status"),
        "renderer": item.get("renderer"),
    }


def _review_core(review: ImplementationDocument) -> ImplementationDocument:
    return {key: review.get(key) for key in ("status", "rating", "review_mode", "playback_confirmed", "reviewer", "preferred", "rating_delta")}


def _session_item_public(item: ImplementationDocument) -> ImplementationDocument:
    return sanitize_metadata(
        {
            "item_id": item.get("item_id"),
            "song_id": item.get("song_id"),
            "title": item.get("title"),
            "audio_status": item.get("audio_status"),
            "audio_health_summary": item.get("audio_health_summary", {}),
            "music_health_summary": item.get("music_health_summary", {}),
            "review": item.get("review", {}),
            "markers": item.get("markers", []),
            "stale": item.get("stale", False),
            "stale_reasons": item.get("stale_reasons", []),
        }
    )


def _session_status(items: list[ImplementationDocument]) -> str:
    if any(item.get("stale") for item in items):
        return "stale"
    reviews = [item.get("review") for item in items if isinstance(item.get("review"), dict) and item.get("review")]
    if len(reviews) < len(items):
        return "needs_review"
    if any(_as_document(review).get("status") == "rejected" for review in reviews):
        return "failed"
    if any(_as_document(review).get("status") == "needs_fix" for review in reviews):
        return "needs_fix"
    return "passed"


def _session_summary(items: list[ImplementationDocument], status: str) -> ImplementationDocument:
    reviews = [item.get("review") for item in items if isinstance(item.get("review"), dict) and item.get("review")]
    return {
        "status": status,
        "item_count": len(items),
        "manual_review_count": sum(1 for review in reviews if _as_document(review).get("review_mode") == "manual"),
        "accepted_count": sum(1 for review in reviews if _as_document(review).get("status") == "accepted"),
        "needs_fix_count": sum(1 for review in reviews if _as_document(review).get("status") == "needs_fix"),
        "rejected_count": sum(1 for review in reviews if _as_document(review).get("status") == "rejected"),
        "marker_count": sum(len(item.get("markers") or []) for item in items),
        "stale_count": sum(1 for item in items if item.get("stale")),
        "rendered_wav_count": sum(1 for item in items if item.get("audio_status") == "rendered"),
        "real_audio_count": sum(
            1
            for item in items
            if item.get("audio_status") == "rendered"
            and item.get("renderer", {}).get("runner_kind") == "real"
            and item.get("renderer", {}).get("release_ready") is True
        ),
        "test_fake_count": sum(1 for item in items if item.get("renderer", {}).get("runner_kind") == "test_fake"),
        "release_ready_audio_count": sum(1 for item in items if item.get("renderer", {}).get("release_ready") is True),
        "test_fake_audio_not_release_ready": any(item.get("renderer", {}).get("runner_kind") == "test_fake" for item in items),
    }


def _smoke_summary(items: list[ImplementationDocument], status: str) -> ImplementationDocument:
    return {
        "status": status,
        "item_count": len(items),
        "midi_count": sum(1 for item in items if item.get("artifact_hashes", {}).get("midi_sha256")),
        "wav_count": sum(1 for item in items if item.get("artifact_hashes", {}).get("wav_sha256")),
        "rendered_count": sum(1 for item in items if item.get("audio_status") == "rendered"),
        "skipped_count": sum(1 for item in items if str(item.get("audio_status") or "").startswith("skipped")),
        "failed_count": sum(1 for item in items if item.get("status") == "failed"),
        "test_fake_count": sum(1 for item in items if item.get("renderer", {}).get("runner_kind") == "test_fake"),
    }


def _smoke_warnings(items: list[ImplementationDocument]) -> list[str]:
    warnings = []
    if any(item.get("audio_status") == "skipped_renderer_not_configured" for item in items):
        warnings.append("renderer_not_configured")
    if any(item.get("renderer", {}).get("runner_kind") == "test_fake" for item in items):
        warnings.append("test_fake_audio_not_release_ready")
    return warnings


def _check(check_id: str, passed: bool, message: str) -> ImplementationDocument:
    return {"check_id": check_id, "status": "passed" if passed else "warning", "message": message}


def _integrity_hash(payload: ImplementationDocument) -> str:
    return stable_hash({key: value for key, value in payload.items() if key != "integrity_hash"})


def _read_optional_json(path: Path) -> ImplementationDocument:
    if not path.exists():
        return {}
    try:
        return sanitize_metadata(read_json(path))
    except (OSError, ValueError):
        return {}


def _sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    return stable_hash(read_json(path))


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _resolve_rel(root: Path, relpath: str) -> Path:
    base = root.resolve()
    target = (base / relpath).resolve()
    if base != target and base not in target.parents:
        raise AudioLabValidationError("Unsafe Audio Lab artifact path.")
    return target

_v142_al_readiness.bind_globals(globals())
_v142_al_evidence.bind_globals(globals())
