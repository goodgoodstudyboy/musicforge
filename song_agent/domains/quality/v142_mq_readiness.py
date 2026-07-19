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
MasteringStore = _make_deferred_global('MasteringStore')
_NullProjectStore = _make_deferred_global('_NullProjectStore')
_NullReleaseStore = _make_deferred_global('_NullReleaseStore')
_ProjectPathStore = _make_deferred_global('_ProjectPathStore')
_analyze_mastering_track = _make_deferred_global('_analyze_mastering_track')
_check = _make_deferred_global('_check')
_ensure_within = _make_deferred_global('_ensure_within')
_file_record = _make_deferred_global('_file_record')
_file_state = _make_deferred_global('_file_state')
_json_file_state = _make_deferred_global('_json_file_state')
_object_hash = _make_deferred_global('_object_hash')
_profile_limits = _make_deferred_global('_profile_limits')
_release_stub_from_analysis = _make_deferred_global('_release_stub_from_analysis')
_short_hash = _make_deferred_global('_short_hash')
_validate_track_id = _make_deferred_global('_validate_track_id')
failure = _make_deferred_global('failure')
index = _make_deferred_global('index')
warning = _make_deferred_global('warning')

def bind_globals(namespace: dict[str, object]) -> None:
    global MASTERING_BLOCKED_KEYS, MasteringStateError, MasteringStore, _NullProjectStore, _NullReleaseStore, _ProjectPathStore, _analyze_mastering_track, _check
    global _ensure_within, _file_record, _file_state, _json_file_state, _object_hash, _profile_limits, _release_stub_from_analysis
    global _short_hash, _validate_track_id, failure, index, warning
    MASTERING_BLOCKED_KEYS = namespace.get('MASTERING_BLOCKED_KEYS', MASTERING_BLOCKED_KEYS)
    MasteringStateError = namespace.get('MasteringStateError', MasteringStateError)
    MasteringStore = namespace.get('MasteringStore', MasteringStore)
    _NullProjectStore = namespace.get('_NullProjectStore', _NullProjectStore)
    _NullReleaseStore = namespace.get('_NullReleaseStore', _NullReleaseStore)
    _ProjectPathStore = namespace.get('_ProjectPathStore', _ProjectPathStore)
    _analyze_mastering_track = namespace.get('_analyze_mastering_track', _analyze_mastering_track)
    _check = namespace.get('_check', _check)
    _ensure_within = namespace.get('_ensure_within', _ensure_within)
    _file_record = namespace.get('_file_record', _file_record)
    _file_state = namespace.get('_file_state', _file_state)
    _json_file_state = namespace.get('_json_file_state', _json_file_state)
    _object_hash = namespace.get('_object_hash', _object_hash)
    _profile_limits = namespace.get('_profile_limits', _profile_limits)
    _release_stub_from_analysis = namespace.get('_release_stub_from_analysis', _release_stub_from_analysis)
    _short_hash = namespace.get('_short_hash', _short_hash)
    _validate_track_id = namespace.get('_validate_track_id', _validate_track_id)
    failure = namespace.get('failure', failure)
    index = namespace.get('index', index)
    warning = namespace.get('warning', warning)
    _bind_deferred_defaults(namespace)


MASTERING_SCHEMA_VERSION = 1
MASTERING_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash"}
MASTERING_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}




def build_mastering_analysis(
    *,
    release: ReleaseDocument,
    release_store: object,
    project_store: _ProjectPathStore,
    profile: MasteringProfile,
    now: str | None = None,
    source_override: DomainDocument | None = None,
    wav_overrides: dict[str, Path] | None = None,
) -> DomainDocument:
    now = now or now_iso()
    wav_overrides = wav_overrides or {}
    source = source_override or mastering_source_state(release=release, release_store=release_store, project_store=project_store, profile=profile)
    track_reports: list[DomainDocument] = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        wav_path = wav_overrides.get(track.track_id) or final_export_dir(project_store.project_dir(track.project_id)) / "song.wav"
        track_reports.append(_analyze_mastering_track(track=track.to_dict(), wav_path=wav_path, profile=profile, now=now))
    loudness_values = [float(item.get("metrics", {}).get("loudness_proxy_db") or -120.0) for item in track_reports if item.get("status") != "missing"]
    max_delta = round(max(loudness_values) - min(loudness_values), 3) if len(loudness_values) >= 2 else 0.0
    checks: list[DomainDocument] = []
    warnings: list[str] = []
    failures: list[str] = []
    if max_delta > profile.max_track_loudness_delta_db:
        checks.append(_check("album_loudness_consistency", "failed", f"Track loudness delta {max_delta:.2f} dB exceeds {profile.max_track_loudness_delta_db:.2f} dB."))
        failures.append("album_loudness_delta")
    else:
        checks.append(_check("album_loudness_consistency", "passed", "Track loudness delta is within profile tolerance."))
    for item in track_reports:
        failures.extend(f"{item.get('track_id')}:{failure}" for failure in item.get("failures", []) if str(failure))
        warnings.extend(f"{item.get('track_id')}:{warning}" for warning in item.get("warnings", []) if str(warning))
    status = "failed" if failures else "warning" if warnings else "passed"
    analysis = {
        "schema_version": MASTERING_SCHEMA_VERSION,
        "analysis_id": f"man-{_short_hash(release.release_id + now)}",
        "release_id": release.release_id,
        "profile_id": profile.profile_id,
        "profile_hash": mastering_profile_hash(profile),
        "profile": _profile_limits(profile),
        "generated_at": now,
        "status": status,
        "source": source,
        "source_hash": stable_hash(source),
        "tracks": track_reports,
        "checks": checks,
        "warnings": sorted(set(warnings)),
        "failures": sorted(set(failures)),
        "summary": {
            "track_count": len(track_reports),
            "average_loudness_proxy_db": round(sum(loudness_values) / len(loudness_values), 3) if loudness_values else None,
            "max_track_loudness_delta_db": max_delta,
            "failed_track_count": len([item for item in track_reports if item.get("status") == "failed"]),
            "warning_track_count": len([item for item in track_reports if item.get("status") == "warning"]),
        },
    }
    analysis["integrity_hash"] = _object_hash(analysis, MASTERING_INTEGRITY_EXCLUDE)
    return sanitize_metadata(analysis, blocked_keys=MASTERING_BLOCKED_KEYS)

def mastering_source_state(*, release: ReleaseDocument, release_store: object, project_store: _ProjectPathStore, profile: MasteringProfile) -> DomainDocument:
    tracks: list[DomainDocument] = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        project_dir = project_store.project_dir(track.project_id)
        export_dir = final_export_dir(project_dir)
        wav_path = export_dir / "song.wav"
        audio_artifact_path = export_dir / "audio-artifact.json"
        tracks.append(
            {
                "track_id": track.track_id,
                "track_number": track.track_number,
                "disc_number": track.disc_number,
                "project_id": track.project_id,
                "version_id": track.version_id,
                "final_export_hash": track.final_export_hash,
                "song_wav": _file_state(wav_path),
                "audio_artifact": _json_file_state(audio_artifact_path),
            }
        )
    return sanitize_metadata(
        {
            "release_id": release.release_id,
            "release_name": release.name,
            "release_type": release.release_type,
            "track_count": len(tracks),
            "tracks": tracks,
            "profile": {"profile_id": profile.profile_id, "profile_hash": mastering_profile_hash(profile)},
        },
        blocked_keys=MASTERING_BLOCKED_KEYS,
    )

def build_mastering_plan(analysis: DomainDocument, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
    payload = payload or {}
    now = now or now_iso()
    profile_id = str(analysis.get("profile_id") or "streaming_balanced")
    profile_limits = _as_document(analysis.get("profile"))
    target_loudness = _as_float(profile_limits.get("target_loudness_proxy_db") if profile_limits.get("target_loudness_proxy_db") is not None else payload.get("target_loudness_proxy_db") or -15.0)
    actions: list[DomainDocument] = []
    for track in analysis.get("tracks", []) if isinstance(analysis.get("tracks"), list) else []:
        if not isinstance(track, dict):
            continue
        metrics = _as_document(track.get("metrics"))
        fmt = _as_document(track.get("format"))
        loudness = _as_float(metrics.get("loudness_proxy_db") if metrics.get("loudness_proxy_db") is not None else -120.0)
        peak_dbfs = _as_float(metrics.get("peak_dbfs") if metrics.get("peak_dbfs") is not None else -120.0)
        max_peak_dbfs = float(track.get("profile_limits", {}).get("max_peak_dbfs") if isinstance(track.get("profile_limits"), dict) else -0.5)
        desired_gain = target_loudness - loudness
        headroom_gain = max_peak_dbfs - peak_dbfs
        gain_db = max(-12.0, min(12.0, desired_gain, headroom_gain))
        track_actions: list[DomainDocument] = []
        if abs(gain_db) >= 0.1:
            track_actions.append({"type": "gain", "gain_db": round(gain_db, 3), "reason": "target_loudness_proxy"})
        leading = float(metrics.get("leading_silence_seconds") or 0.0)
        trailing = float(metrics.get("trailing_silence_seconds") or 0.0)
        max_leading = float(track.get("profile_limits", {}).get("max_leading_silence_seconds") if isinstance(track.get("profile_limits"), dict) else 3.0)
        max_trailing = float(track.get("profile_limits", {}).get("max_trailing_silence_seconds") if isinstance(track.get("profile_limits"), dict) else 4.0)
        duration = float(fmt.get("duration_seconds") or 0.0)
        min_duration = float(track.get("profile_limits", {}).get("min_duration_seconds") if isinstance(track.get("profile_limits"), dict) else 8.0)
        if leading > max_leading and duration - (leading - max_leading) >= min_duration:
            track_actions.append({"type": "trim_leading", "seconds": round(leading - max_leading, 3), "reason": "leading_silence"})
        if trailing > max_trailing and duration - (trailing - max_trailing) >= min_duration:
            track_actions.append({"type": "trim_trailing", "seconds": round(trailing - max_trailing, 3), "reason": "trailing_silence"})
        actions.append({"track_id": track.get("track_id"), "source_wav_sha256": track.get("wav_sha256"), "actions": track_actions})
    plan = {
        "schema_version": MASTERING_SCHEMA_VERSION,
        "plan_id": f"mpln-{_short_hash(str(analysis.get('integrity_hash')) + now)}",
        "release_id": analysis.get("release_id"),
        "profile_id": profile_id,
        "analysis_hash": analysis.get("integrity_hash"),
        "analysis_source_hash": analysis.get("source_hash"),
        "created_at": now,
        "status": "ready",
        "actions": actions,
        "summary": {
            "track_count": len(actions),
            "action_count": sum(len(item.get("actions", [])) for item in actions if isinstance(item, dict)),
        },
        "warnings": [],
    }
    plan["integrity_hash"] = _object_hash(plan, MASTERING_INTEGRITY_EXCLUDE)
    return sanitize_metadata(plan, blocked_keys=MASTERING_BLOCKED_KEYS)

def build_mastered_candidate(
    *,
    candidate_id: str,
    release_id: str,
    analysis: DomainDocument,
    plan: DomainDocument,
    profile: MasteringProfile,
    source_wavs: dict[str, Path] | None = None,
    candidate_dir: Path,
    payload: DomainDocument | None = None,
    now: str | None = None,
) -> DomainDocument:
    payload = payload or {}
    source_wavs = source_wavs or {}
    now = now or now_iso()
    actions_by_track = {str(item.get("track_id") or ""): item.get("actions", []) for item in plan.get("actions", []) if isinstance(item, dict)}
    source_tracks = {str(item.get("track_id") or ""): item for item in analysis.get("tracks", []) if isinstance(item, dict)}
    track_rows: list[DomainDocument] = []
    after_wavs: dict[str, Path] = {}
    for track_id, track in source_tracks.items():
        source_path = source_wavs.get(track_id) or Path(str(track.get("source_wav_path") or ""))
        if not source_path.exists() or not source_path.is_file() or source_path.is_symlink():
            raise MasteringStateError(f"Source WAV is missing for {track_id}.")
        output_rel = Path("tracks") / _validate_track_id(track_id) / "song.wav"
        output_path = candidate_dir / output_rel
        output_path.parent.mkdir(parents=True, exist_ok=True)
        applied = apply_mastering_actions(source_path, output_path, actions_by_track.get(track_id, []), profile=profile)
        after_wavs[track_id] = output_path
        track_rows.append(
            {
                "track_id": track_id,
                "source_wav_sha256": track.get("wav_sha256"),
                "candidate_wav": output_rel.as_posix(),
                "candidate_wav_sha256": file_sha256(output_path),
                "applied_actions": applied,
            }
        )
    release_stub = _release_stub_from_analysis(analysis)
    after_analysis = build_mastering_analysis(
        release=release_stub,
        release_store=_NullReleaseStore(release_id),
        project_store=_NullProjectStore(after_wavs),
        profile=profile,
        now=now,
        source_override={
            "release_id": release_id,
            "candidate_id": candidate_id,
            "analysis_hash": analysis.get("integrity_hash"),
            "plan_hash": plan.get("integrity_hash"),
            "profile": {"profile_id": profile.profile_id, "profile_hash": mastering_profile_hash(profile)},
            "tracks": [{"track_id": row["track_id"], "candidate_wav_sha256": row["candidate_wav_sha256"]} for row in track_rows],
        },
        wav_overrides=after_wavs,
    )
    source = {
        "release_id": release_id,
        "analysis_hash": analysis.get("integrity_hash"),
        "plan_hash": plan.get("integrity_hash"),
        "profile_hash": mastering_profile_hash(profile),
        "source_track_wav_hashes": {row["track_id"]: row["source_wav_sha256"] for row in track_rows},
    }
    candidate = {
        "schema_version": MASTERING_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "release_id": release_id,
        "profile_id": profile.profile_id,
        "status": "ready_for_review",
        "created_at": now,
        "updated_at": now,
        "analysis_hash": analysis.get("integrity_hash"),
        "plan_hash": plan.get("integrity_hash"),
        "source": source,
        "source_hash": stable_hash(source),
        "tracks": track_rows,
        "after_analysis": after_analysis,
        "after_analysis_hash": after_analysis.get("integrity_hash"),
        "review": {},
        "selected": False,
        "notes": sanitize_sensitive_text(str(payload.get("notes") or ""))[:1000],
    }
    candidate["integrity_hash"] = _object_hash(candidate, MASTERING_INTEGRITY_EXCLUDE)
    return sanitize_metadata(candidate, blocked_keys=MASTERING_BLOCKED_KEYS)

def apply_mastering_actions(source: Path, target: Path, actions: list[DomainDocument], *, profile: MasteringProfile) -> list[DomainDocument]:
    with wave.open(str(source), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        compression = wav.getcomptype()
        frames = wav.readframes(wav.getnframes())
    if compression != "NONE" or sample_width != 2:
        shutil.copy2(source, target)
        return [{"type": "copy", "reason": "unsupported_pcm_format"}]
    samples = [int.from_bytes(frames[index : index + 2], byteorder="little", signed=True) for index in range(0, len(frames), 2)]
    frame_count = len(samples) // max(1, channels)
    applied: list[DomainDocument] = []
    start_frame = 0
    end_frame = frame_count
    gain_db = 0.0
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type") or "")
        if action_type == "gain":
            gain_db += float(action.get("gain_db") or 0.0)
            applied.append({"type": "gain", "gain_db": round(float(action.get("gain_db") or 0.0), 3)})
        elif action_type == "trim_leading":
            frames_to_trim = int(max(0.0, float(action.get("seconds") or 0.0)) * sample_rate)
            start_frame = min(end_frame, start_frame + frames_to_trim)
            applied.append({"type": "trim_leading", "seconds": round(frames_to_trim / sample_rate, 3) if sample_rate else 0.0})
        elif action_type == "trim_trailing":
            frames_to_trim = int(max(0.0, float(action.get("seconds") or 0.0)) * sample_rate)
            end_frame = max(start_frame, end_frame - frames_to_trim)
            applied.append({"type": "trim_trailing", "seconds": round(frames_to_trim / sample_rate, 3) if sample_rate else 0.0})
    selected = samples[start_frame * channels : end_frame * channels]
    gain = math.pow(10.0, gain_db / 20.0) if gain_db else 1.0
    encoded = bytearray()
    for value in selected:
        adjusted = int(round(value * gain))
        adjusted = max(-32768, min(32767, adjusted))
        encoded.extend(int(adjusted).to_bytes(2, byteorder="little", signed=True))
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(encoded))
    if not applied:
        applied.append({"type": "copy"})
    return applied

def mastering_analysis_summary(analysis: DomainDocument) -> DomainDocument:
    summary = _as_document(analysis.get("summary"))
    return sanitize_metadata(
        {
            "status": analysis.get("status") or "missing",
            "analysis_id": analysis.get("analysis_id"),
            "profile_id": analysis.get("profile_id"),
            "analysis_hash": analysis.get("integrity_hash"),
            "source_hash": analysis.get("source_hash"),
            "track_count": summary.get("track_count", 0),
            "average_loudness_proxy_db": summary.get("average_loudness_proxy_db"),
            "max_track_loudness_delta_db": summary.get("max_track_loudness_delta_db"),
            "warning_count": len(analysis.get("warnings", [])) if isinstance(analysis.get("warnings"), list) else 0,
            "failure_count": len(analysis.get("failures", [])) if isinstance(analysis.get("failures"), list) else 0,
        },
        blocked_keys=MASTERING_BLOCKED_KEYS,
    )

def selected_mastering_track_sources(release_store: ReleaseStore, release_id: str, project_store: ProjectStore | None = None, profile_store: MasteringProfileStore | None = None) -> dict[str, Path]:
    store = MasteringStore(release_store, project_store=project_store, profile_store=profile_store)
    selected = store.read_selected_candidate(release_id, default={})
    if not selected or selected.get("stale") or not mastering_candidate_integrity_ok(selected):
        return {}
    result: dict[str, Path] = {}
    candidate_id = str(selected.get("candidate_id") or "")
    for row in selected.get("tracks", []) if isinstance(selected.get("tracks"), list) else []:
        if not isinstance(row, dict):
            continue
        rel = str(row.get("candidate_wav") or "")
        if not rel:
            continue
        path = (store.candidate_dir(release_id, candidate_id) / rel).resolve()
        try:
            _ensure_within(store.candidate_dir(release_id, candidate_id).resolve(), path)
        except MasteringStateError:
            continue
        if path.exists() and path.is_file() and not path.is_symlink():
            result[str(row.get("track_id") or "")] = path
    return result

def export_mastering(release_store: ReleaseStore, release_id: str, export_dir: Path, project_store: ProjectStore | None = None, profile_store: MasteringProfileStore | None = None) -> DomainDocument:
    store = MasteringStore(release_store, project_store=project_store, profile_store=profile_store)
    summary = store.get_summary(release_id)
    target = export_dir / "mastering"
    target.mkdir(parents=True, exist_ok=True)
    files: list[DomainDocument] = []
    write_json(target / "summary.json", summary)
    files.append(_file_record(export_dir, target / "summary.json"))
    for source_name in ("analysis.json", "plan.json", "selected-candidate.json"):
        source = store.root_dir(release_id) / source_name
        if source.exists() and source.is_file() and not source.is_symlink():
            dest = target / source_name
            write_json(dest, read_json(source))
            files.append(_file_record(export_dir, dest))
    selected = store.read_selected_candidate(release_id, default={})
    if selected:
        for row in selected.get("tracks", []) if isinstance(selected.get("tracks"), list) else []:
            if not isinstance(row, dict):
                continue
            track_id = str(row.get("track_id") or "")
            candidate_wav = store.candidate_audio_path(release_id, str(selected.get("candidate_id") or ""), track_id)
            dest = target / "tracks" / _validate_track_id(track_id) / "song.wav"
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(candidate_wav, dest)
            files.append(_file_record(export_dir, dest))
    export_summary = {
        **summary,
        "summary_path": "mastering/summary.json",
        "summary_hash": mastering_summary_hash(summary),
        "files": files,
    }
    return sanitize_metadata(export_summary, blocked_keys=MASTERING_BLOCKED_KEYS)

def mastering_summary_hash(summary: DomainDocument) -> str:
    return _object_hash(summary, MASTERING_SUMMARY_INTEGRITY_EXCLUDE)

def mastering_analysis_integrity_ok(analysis: DomainDocument) -> bool:
    expected = str(analysis.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(analysis, MASTERING_INTEGRITY_EXCLUDE)

def mastering_plan_integrity_ok(plan: DomainDocument) -> bool:
    expected = str(plan.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(plan, MASTERING_INTEGRITY_EXCLUDE)

def mastering_candidate_integrity_ok(candidate: DomainDocument) -> bool:
    expected = str(candidate.get("integrity_hash") or "")
    return bool(expected) and expected == _object_hash(candidate, MASTERING_INTEGRITY_EXCLUDE)

def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
