# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_float as _as_float, as_list as _as_list
import hashlib as hashlib
import io as io
import math as math
import shutil as shutil
import threading as threading
import wave as wave
from pathlib import Path as Path
from typing import Protocol as Protocol
from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_integrity_ok as audio_health_integrity_ok, audio_health_summary as audio_health_summary
from song_agent.domains.creation.final_export import final_export_dir as final_export_dir
from song_agent.domains.quality.mastering_profiles import MasteringProfile as MasteringProfile, MasteringProfileError as MasteringProfileError, MasteringProfileStore as MasteringProfileStore, mastering_profile_hash as mastering_profile_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseDocument as ReleaseDocument, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

MASTERING_BLOCKED_KEYS = _make_deferred_global('MASTERING_BLOCKED_KEYS')
MasteringStateError = _make_deferred_global('MasteringStateError')
file_sha256 = _make_deferred_global('file_sha256')
key = _make_deferred_global('key')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global MASTERING_BLOCKED_KEYS, MasteringStateError, file_sha256, key, part
    MASTERING_BLOCKED_KEYS = namespace.get('MASTERING_BLOCKED_KEYS', MASTERING_BLOCKED_KEYS)
    MasteringStateError = namespace.get('MasteringStateError', MasteringStateError)
    file_sha256 = namespace.get('file_sha256', file_sha256)
    key = namespace.get('key', key)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


MASTERING_SCHEMA_VERSION = 1
MASTERING_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash"}
MASTERING_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}




def _analyze_mastering_track(*, track: DomainDocument, wav_path: Path, profile: MasteringProfile, now: str) -> DomainDocument:
    source = {"track_id": track.get("track_id"), "project_id": track.get("project_id"), "version_id": track.get("version_id"), "scope": "mastering"}
    if not wav_path.exists() or not wav_path.is_file() or wav_path.is_symlink():
        return {
            "track_id": track.get("track_id"),
            "status": "failed",
            "source_wav_path": str(wav_path),
            "wav_sha256": None,
            "format": {},
            "metrics": {},
            "profile_limits": _profile_limits(profile),
            "checks": [_check("wav_exists", "failed", "Track WAV is missing.")],
            "warnings": [],
            "failures": ["wav_missing"],
        }
    health = analyze_wav_health(
        wav_path,
        source=source,
        expected_sample_rate=profile.sample_rate,
        expected_channels=profile.channels,
        expected_bit_depth=profile.bit_depth,
        report_id=f"mqa-{track.get('track_id')}",
        now=now,
    )
    fmt = _as_document(health.get("format"))
    metrics = dict(_as_document(health.get("metrics")))
    peak = float(metrics.get("peak") or 0.0)
    rms = float(metrics.get("rms") or 0.0)
    peak_dbfs = _amplitude_db(peak)
    loudness = _amplitude_db(rms)
    metrics["peak_dbfs"] = peak_dbfs
    metrics["loudness_proxy_db"] = loudness
    checks = list(_as_list(health.get("checks")))
    warnings = [str(item) for item in health.get("warnings", []) if str(item)]
    failures = [str(item) for item in health.get("failures", []) if str(item)]
    if not audio_health_integrity_ok(health):
        failures.append("audio_health_integrity")
    if float(fmt.get("duration_seconds") or 0.0) < profile.min_duration_seconds:
        failures.append("duration_too_short_profile")
        checks.append(_check("mastering_duration_min", "failed", "Track duration is below mastering profile minimum."))
    if profile.max_duration_seconds and float(fmt.get("duration_seconds") or 0.0) > profile.max_duration_seconds:
        warnings.append("duration_long_profile")
        checks.append(_check("mastering_duration_max", "warning", "Track duration exceeds mastering profile maximum."))
    if peak_dbfs > profile.max_peak_dbfs:
        failures.append("peak_too_high")
        checks.append(_check("mastering_peak", "failed", f"Peak {peak_dbfs:.2f} dBFS exceeds {profile.max_peak_dbfs:.2f} dBFS."))
    else:
        checks.append(_check("mastering_peak", "passed", "Peak is within mastering profile limit."))
    if float(metrics.get("clipping_ratio") or 0.0) > profile.max_clipping_ratio:
        failures.append("clipping_ratio")
        checks.append(_check("mastering_clipping", "failed", "Clipping ratio exceeds mastering profile limit."))
    else:
        checks.append(_check("mastering_clipping", "passed", "Clipping ratio is within mastering profile limit."))
    if abs(loudness - profile.target_loudness_proxy_db) > profile.loudness_tolerance_db:
        warnings.append("target_loudness_proxy_delta")
        checks.append(_check("mastering_loudness_proxy", "warning", "Loudness proxy is outside target tolerance."))
    else:
        checks.append(_check("mastering_loudness_proxy", "passed", "Loudness proxy is within target tolerance."))
    if float(metrics.get("leading_silence_seconds") or 0.0) > profile.max_leading_silence_seconds:
        warnings.append("leading_silence_profile")
        checks.append(_check("mastering_leading_silence", "warning", "Leading silence exceeds mastering profile limit."))
    if float(metrics.get("trailing_silence_seconds") or 0.0) > profile.max_trailing_silence_seconds:
        warnings.append("trailing_silence_profile")
        checks.append(_check("mastering_trailing_silence", "warning", "Trailing silence exceeds mastering profile limit."))
    status = "failed" if failures else "warning" if warnings else "passed"
    return sanitize_metadata(
        {
            "track_id": track.get("track_id"),
            "track_number": track.get("track_number"),
            "disc_number": track.get("disc_number"),
            "title": track.get("title"),
            "project_id": track.get("project_id"),
            "version_id": track.get("version_id"),
            "status": status,
            "source_wav_path": str(wav_path),
            "wav_sha256": health.get("wav_sha256"),
            "format": fmt,
            "metrics": metrics,
            "profile_limits": _profile_limits(profile),
            "checks": checks,
            "warnings": sorted(set(warnings)),
            "failures": sorted(set(failures)),
        },
        blocked_keys=MASTERING_BLOCKED_KEYS,
    )

def _profile_limits(profile: MasteringProfile) -> DomainDocument:
    return {
        "target_loudness_proxy_db": profile.target_loudness_proxy_db,
        "loudness_tolerance_db": profile.loudness_tolerance_db,
        "max_peak_dbfs": profile.max_peak_dbfs,
        "max_clipping_ratio": profile.max_clipping_ratio,
        "max_track_loudness_delta_db": profile.max_track_loudness_delta_db,
        "max_leading_silence_seconds": profile.max_leading_silence_seconds,
        "max_trailing_silence_seconds": profile.max_trailing_silence_seconds,
        "min_duration_seconds": profile.min_duration_seconds,
    }

def _release_stub_from_analysis(analysis: DomainDocument) -> ReleaseDocument:
    from song_agent.domains.delivery.releases import ReleaseDocument, ReleaseTrack

    tracks = []
    for index, item in enumerate(analysis.get("tracks", []) if isinstance(analysis.get("tracks"), list) else [], start=1):
        if not isinstance(item, dict):
            continue
        tracks.append(
            ReleaseTrack(
                track_id=str(item.get("track_id") or f"track-{index:06d}"),
                track_number=int(item.get("track_number") or index),
                disc_number=int(item.get("disc_number") or 1),
                title=str(item.get("title") or item.get("track_id") or "Track"),
                artist=None,
                project_id=str(item.get("project_id") or ""),
                version_id=str(item.get("version_id") or ""),
            )
        )
    return ReleaseDocument(
        schema_version=MASTERING_SCHEMA_VERSION,
        release_id=str(analysis.get("release_id") or "release-000000"),
        name="Mastered Candidate",
        release_type="demo_pack",
        status="draft",
        primary_artist="",
        label=None,
        language=None,
        notes=None,
        created_at=str(analysis.get("generated_at") or now_iso()),
        updated_at=str(analysis.get("generated_at") or now_iso()),
        tracks=tracks,
    )

class _NullReleaseStore:
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id

    def export_dir(self, release_id: str) -> Path:
        return Path(".")

class _NullProjectStore:
    def __init__(self, wavs: dict[str, Path]) -> None:
        self.wavs = wavs

    def project_dir(self, project_id: str) -> Path:
        return Path(".")

def _object_hash(value: DomainDocument, exclude: set[str]) -> str:
    return stable_hash(sanitize_metadata({key: item for key, item in value.items() if key not in exclude}, blocked_keys=MASTERING_BLOCKED_KEYS))

def _file_state(path: Path) -> DomainDocument:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {"exists": False, "sha256": None, "size_bytes": 0}
    return {"exists": True, "sha256": file_sha256(path), "size_bytes": path.stat().st_size}

def _json_file_state(path: Path) -> DomainDocument:
    state = _file_state(path)
    if state.get("exists"):
        try:
            state["payload_hash"] = stable_hash(read_json(path))
        except Exception:
            state["payload_hash"] = None
    return state

def _file_record(export_dir: Path, path: Path) -> DomainDocument:
    rel = path.resolve().relative_to(export_dir.resolve()).as_posix()
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": file_sha256(path)}

def _validate_candidate_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("mcand-") or any(part in text for part in ("/", "\\", "..", ":")):
        raise MasteringStateError("Invalid mastered candidate id.")
    return text

def _validate_track_id(value: str) -> str:
    text = str(value or "")
    if not text.startswith("track-") or any(part in text for part in ("/", "\\", "..", ":")):
        raise MasteringStateError("Invalid release track id.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise MasteringStateError("Refusing to operate outside mastering boundaries.") from exc

def _check(check_id: str, status: str, message: str) -> DomainDocument:
    return {"id": check_id, "status": status, "message": message}

def _amplitude_db(value: float) -> float:
    if value <= 0:
        return -120.0
    return round(20.0 * math.log10(min(max(value, 1e-12), 1.0)), 3)

def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:12]
