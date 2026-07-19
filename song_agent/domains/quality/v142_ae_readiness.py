# ruff: noqa: E402,F401,F821,F822,F403,F405
# mypy: ignore-errors
from __future__ import annotations
from song_agent.platform.contracts import DomainDocument, as_document as _as_document, as_list as _as_list
import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import subprocess as subprocess
import threading as threading
from dataclasses import dataclass as dataclass
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Protocol as Protocol
from song_agent.domains.quality.audio_encoding_profiles import AudioEncodingProfile as AudioEncodingProfile, AudioEncodingProfileError as AudioEncodingProfileError, AudioEncodingProfileStore as AudioEncodingProfileStore, audio_encoding_profile_hash as audio_encoding_profile_hash, audio_encoding_profile_integrity_ok as audio_encoding_profile_integrity_ok
from song_agent.domains.quality.mastering_qa import mastering_summary_hash as mastering_summary_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash

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

AUDIO_ENCODING_BLOCKED_KEYS = _make_deferred_global('AUDIO_ENCODING_BLOCKED_KEYS')
AudioEncoderConfig = _make_deferred_global('AudioEncoderConfig')
AudioEncodingStateError = _make_deferred_global('AudioEncodingStateError')
AudioEncodingStore = _make_deferred_global('AudioEncodingStore')
EncoderRunner = _make_deferred_global('EncoderRunner')
FakeEncoderRunner = _make_deferred_global('FakeEncoderRunner')
FfmpegEncoderRunner = _make_deferred_global('FfmpegEncoderRunner')
ch = _make_deferred_global('ch')
key = _make_deferred_global('key')
part = _make_deferred_global('part')

def bind_globals(namespace: dict[str, object]) -> None:
    global AUDIO_ENCODING_BLOCKED_KEYS, AudioEncoderConfig, AudioEncodingStateError, AudioEncodingStore, EncoderRunner, FakeEncoderRunner, FfmpegEncoderRunner
    global ch, key, part
    AUDIO_ENCODING_BLOCKED_KEYS = namespace.get('AUDIO_ENCODING_BLOCKED_KEYS', AUDIO_ENCODING_BLOCKED_KEYS)
    AudioEncoderConfig = namespace.get('AudioEncoderConfig', AudioEncoderConfig)
    AudioEncodingStateError = namespace.get('AudioEncodingStateError', AudioEncodingStateError)
    AudioEncodingStore = namespace.get('AudioEncodingStore', AudioEncodingStore)
    EncoderRunner = namespace.get('EncoderRunner', EncoderRunner)
    FakeEncoderRunner = namespace.get('FakeEncoderRunner', FakeEncoderRunner)
    FfmpegEncoderRunner = namespace.get('FfmpegEncoderRunner', FfmpegEncoderRunner)
    ch = namespace.get('ch', ch)
    key = namespace.get('key', key)
    part = namespace.get('part', part)
    _bind_deferred_defaults(namespace)


AUDIO_ENCODING_SCHEMA_VERSION = 1
AUDIO_ENCODING_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
AUDIO_ENCODING_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}
ENCODER_CONFIG_FILENAME = "audio-encoder.json"
COMMAND_POLICY_VERSION = "v1"
MIN_ENCODED_AUDIO_BYTES = 8




def encoded_audio_source_state(release_store: ReleaseStore, release_id: str, profile: AudioEncodingProfile) -> DomainDocument:
    from song_agent.domains.delivery.release_export_manifest import read_release_export_manifest

    try:
        manifest = read_release_export_manifest(release_store, release_id)
    except FileNotFoundError:
        return {"release_id": release_id, "profile": _profile_source(profile), "status": "missing", "message": "Release Export is missing."}
    export_dir = release_store.export_dir(release_id)
    tracks = _as_list(manifest.get("tracks"))
    mastering = _as_document(manifest.get("mastering"))
    export_hash = release_export_audio_source_hash(manifest)
    source_tracks: list[DomainDocument] = []
    missing: list[str] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        track_id = str(track.get("track_id") or "")
        directory = str(track.get("directory") or "").strip("/")
        rel = validate_relative_path(f"{directory}/song.wav" if directory else "song.wav")
        wav_path = (export_dir / rel).resolve()
        try:
            _ensure_within(export_dir.resolve(), wav_path)
        except AudioEncodingStateError:
            missing.append(rel)
            continue
        if not wav_path.exists() or not wav_path.is_file() or wav_path.is_symlink():
            missing.append(rel)
            continue
        header = detect_audio_header(wav_path, expected_format="wav")
        if not header.get("valid"):
            missing.append(rel)
            continue
        source_tracks.append(
            {
                "track_id": _validate_track_id(track_id),
                "directory": directory,
                "source_path": rel,
                "source_wav_sha256": _sha256_file(wav_path),
                "source_size_bytes": wav_path.stat().st_size,
                "duration_seconds": _wav_duration_seconds(wav_path),
            }
        )
    status = "current"
    message = "Release Export audio source is current."
    if missing:
        status = "missing"
        message = "Release Export is missing selected mastered WAV track audio."
    if mastering.get("status") not in {"passed", "warning"} or not mastering.get("selected_candidate_hash"):
        status = "missing"
        message = "Mastering QA evidence is missing."
    return sanitize_metadata(
        {
            "release_id": release_id,
            "status": status,
            "message": message,
            "release_export_manifest_hash": export_hash,
            "mastering": {
                "summary_hash": mastering.get("summary_hash") or mastering_summary_hash(mastering) if mastering else None,
                "analysis_hash": mastering.get("analysis_hash"),
                "plan_hash": mastering.get("plan_hash"),
                "selected_candidate_id": mastering.get("selected_candidate_id"),
                "selected_candidate_hash": mastering.get("selected_candidate_hash"),
                "status": mastering.get("status"),
            },
            "profile": _profile_source(profile),
            "command_policy_version": COMMAND_POLICY_VERSION,
            "tracks": source_tracks,
            "missing_tracks": missing,
        },
        blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
    )

def build_encoded_audio_summary(release_id: str, manifests: list[DomainDocument], *, now: str | None = None) -> DomainDocument:
    now = now or now_iso()
    profiles = []
    missing: list[object] = []
    stale = []
    failed = []
    for manifest in manifests:
        profile_id = str(manifest.get("profile_id") or "")
        summary = _as_document(manifest.get("summary"))
        row = {
            "profile_id": profile_id,
            "status": "stale" if manifest.get("stale") else summary.get("status") or "missing",
            "format": manifest.get("format"),
            "extension": manifest.get("extension"),
            "encoder_engine": (manifest.get("encoder") or {}).get("engine") if isinstance(manifest.get("encoder"), dict) else None,
            "encoder_runner_kind": ((manifest.get("encoder") or {}).get("runner") or {}).get("kind") if isinstance((manifest.get("encoder") or {}).get("runner"), dict) else None,
            "fake_evidence": encoded_manifest_uses_fake(manifest),
            "track_count": summary.get("track_count", 0),
            "completed_count": summary.get("completed_count", 0),
            "failed_count": summary.get("failed_count", 0),
            "source_hash": manifest.get("source_hash"),
            "manifest_hash": manifest.get("integrity_hash"),
        }
        profiles.append(row)
        if manifest.get("stale"):
            stale.append(profile_id)
        if summary.get("status") == "failed":
            failed.append(profile_id)
    status = "failed" if failed else "stale" if stale else "completed" if profiles else "missing"
    summary = {
        "schema_version": AUDIO_ENCODING_SCHEMA_VERSION,
        "release_id": release_id,
        "generated_at": now,
        "status": status,
        "profile_count": len(profiles),
        "profiles": profiles,
        "completed_profiles": [row["profile_id"] for row in profiles if row.get("status") == "completed"],
        "missing_profiles": missing,
        "stale_profiles": stale,
        "failed_profiles": failed,
    }
    summary["integrity_hash"] = encoded_audio_summary_hash(summary)
    return sanitize_metadata(summary, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS)

def release_export_audio_source_hash(manifest: DomainDocument) -> str:
    mastering = _as_document(manifest.get("mastering"))
    return stable_hash(
        sanitize_metadata(
            {
                "schema_version": manifest.get("schema_version"),
                "release_id": manifest.get("release_id"),
                "release_name": manifest.get("release_name"),
                "tracks": [
                    {
                        "track_id": item.get("track_id"),
                        "disc_number": item.get("disc_number"),
                        "track_number": item.get("track_number"),
                        "project_id": item.get("project_id"),
                        "version_id": item.get("version_id"),
                        "directory": item.get("directory"),
                    }
                    for item in (_as_list(manifest.get("tracks")))
                    if isinstance(item, dict)
                ],
                "mastering": {
                    "status": mastering.get("status"),
                    "analysis_hash": mastering.get("analysis_hash"),
                    "plan_hash": mastering.get("plan_hash"),
                    "selected_candidate_id": mastering.get("selected_candidate_id"),
                    "selected_candidate_hash": mastering.get("selected_candidate_hash"),
                    "summary_hash": mastering.get("summary_hash"),
                },
            },
            blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
        )
    )

def encoded_audio_gate(store: AudioEncodingStore, release_id: str, *, required_profiles: list[str], required: bool, force: bool = False) -> DomainDocument:
    required_profiles = normalize_required_profiles(required_profiles)
    if required and not required_profiles:
        required_profiles = ["wav_master"]
    if not required:
        summary = store.get_summary(release_id)
        return {**summary, "require_encoded_audio": False, "status": "passed" if summary.get("status") in {"completed", "missing"} else summary.get("status")}
    missing: list[str] = []
    stale: list[str] = []
    failed: list[str] = []
    fake: list[str] = []
    warnings: list[str] = []
    profile_summaries: list[DomainDocument] = []
    for profile_id in required_profiles:
        manifest = store.read_manifest(release_id, profile_id, default={})
        if not manifest:
            missing.append(profile_id)
            continue
        row = {
            "profile_id": profile_id,
            "status": "stale" if manifest.get("stale") else (manifest.get("summary") or {}).get("status"),
            "source_hash": manifest.get("source_hash"),
            "manifest_hash": manifest.get("integrity_hash"),
            "encoder_engine": (manifest.get("encoder") or {}).get("engine") if isinstance(manifest.get("encoder"), dict) else None,
            "encoder_runner_kind": ((manifest.get("encoder") or {}).get("runner") or {}).get("kind") if isinstance((manifest.get("encoder") or {}).get("runner"), dict) else None,
            "fake_evidence": encoded_manifest_uses_fake(manifest),
        }
        profile_summaries.append(row)
        if manifest.get("stale") or not encoded_manifest_integrity_ok(manifest):
            stale.append(profile_id)
        if encoded_manifest_uses_fake(manifest):
            fake.append(profile_id)
        if (manifest.get("summary") or {}).get("status") == "failed":
            failed.append(profile_id)
        elif (manifest.get("summary") or {}).get("status") == "warning":
            warnings.append(profile_id)
    hard = bool(missing or stale or failed or fake)
    warning_block = bool(warnings and not force)
    return sanitize_metadata(
        {
            "status": "failed" if hard or warning_block else "passed",
            "hard_block": hard,
            "require_encoded_audio": True,
            "required_audio_format_profiles": required_profiles,
            "profiles": profile_summaries,
            "missing_profiles": missing,
            "stale_profiles": stale,
            "failed_profiles": failed,
            "fake_profiles": fake,
            "warning_profiles": warnings,
            "message": "Encoded audio gate failed." if hard or warning_block else "Encoded audio gate passed.",
        },
        blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
    )

def export_encoded_audio_summary(release_store: ReleaseStore, release_id: str, export_dir: Path, *, store: AudioEncodingStore | None = None) -> DomainDocument:
    store = store or AudioEncodingStore(release_store, project_store=release_store.project_store)
    summary = store.get_summary(release_id, current=False)
    target = export_dir / "encoded-audio-summary.json"
    write_json(target, summary)
    return {
        **summary,
        "summary_path": "encoded-audio-summary.json",
        "summary_hash": encoded_audio_summary_hash(summary),
    }

def encoded_manifest_hash(manifest: DomainDocument) -> str:
    return stable_hash(sanitize_metadata({key: value for key, value in manifest.items() if key not in AUDIO_ENCODING_INTEGRITY_EXCLUDE}, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS))

def encoded_manifest_integrity_ok(manifest: DomainDocument) -> bool:
    expected = str(manifest.get("integrity_hash") or "")
    return bool(expected) and expected == encoded_manifest_hash(manifest)

def encoded_audio_summary_hash(summary: DomainDocument) -> str:
    return stable_hash(sanitize_metadata({key: value for key, value in summary.items() if key not in AUDIO_ENCODING_SUMMARY_INTEGRITY_EXCLUDE}, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS))

def encoded_audio_summary_integrity_ok(summary: DomainDocument) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_summary_hash(summary)

def normalize_required_profiles(value: object) -> list[str]:
    if isinstance(value, str):
        raw = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        raw = [str(item).strip() for item in value]
    else:
        raw = []
    result: list[str] = []
    for item in raw:
        if not item or item in result:
            continue
        result.append(_validate_profile_id(item))
    return result

def resolve_target_audio_format_profiles(target: object, template: DomainDocument | None = None) -> list[str]:
    options = getattr(target, "options", None)
    options = _as_document(options)
    rules = template.get("rules") if isinstance(template, dict) and isinstance(template.get("rules"), dict) else {}
    profiles = normalize_required_profiles(options.get("audio_format_profiles"))
    if not profiles:
        profiles = normalize_required_profiles(_as_document(rules).get("required_audio_formats"))
    if not profiles:
        primary = str(options.get("primary_audio_format") or _as_document(rules).get("primary_audio_format") or "").strip()
        profiles = normalize_required_profiles(primary)
    return profiles or ["wav_master"]

def primary_target_audio_format_profile(target: object, template: DomainDocument | None = None) -> str:
    options = getattr(target, "options", None)
    options = _as_document(options)
    rules = template.get("rules") if isinstance(template, dict) and isinstance(template.get("rules"), dict) else {}
    primary = str(options.get("primary_audio_format") or _as_document(rules).get("primary_audio_format") or "").strip()
    if primary:
        return _validate_profile_id(primary)
    return resolve_target_audio_format_profiles(target, template)[0]

def build_ffmpeg_command(*, source: Path, target: Path, profile: AudioEncodingProfile, config: AudioEncoderConfig) -> list[str]:
    argv = [config.ffmpeg_path, "-y", "-hide_banner", "-nostdin", "-i", str(source), "-vn"]
    if profile.sample_rate:
        argv.extend(["-ar", str(profile.sample_rate)])
    if profile.channels:
        argv.extend(["-ac", str(profile.channels)])
    if profile.codec:
        argv.extend(["-codec:a", profile.codec])
    if profile.bitrate_kbps:
        argv.extend(["-b:a", f"{profile.bitrate_kbps}k"])
    if profile.quality is not None and profile.format == "mp3":
        argv.extend(["-q:a", str(profile.quality)])
    if profile.compression_level is not None and profile.format == "flac":
        argv.extend(["-compression_level", str(profile.compression_level)])
    if profile.container:
        argv.extend(["-f", profile.container])
    argv.append(str(target))
    return argv

def encoder_manifest_payload(profile: AudioEncodingProfile, config: AudioEncoderConfig, *, runner_kind: str | None = None, fake_evidence: bool = False) -> DomainDocument:
    command_template = build_ffmpeg_command(source=Path("{source}"), target=Path("{target}"), profile=profile, config=AudioEncoderConfig(ffmpeg_path="{ffmpeg}", ffprobe_path="{ffprobe}", timeout_seconds=config.timeout_seconds, max_parallel=config.max_parallel))
    return sanitize_metadata(
        {
            "engine": profile.engine,
            "profile_id": profile.profile_id,
            "profile_hash": audio_encoding_profile_hash(profile),
            "command_template_hash": stable_hash(command_template),
            "command_policy_version": COMMAND_POLICY_VERSION,
            "ffmpeg": {"basename": Path(config.ffmpeg_path).name if profile.engine == "ffmpeg" else None},
            "runner": {"kind": runner_kind or "unknown", "fake": bool(fake_evidence)},
        },
        blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
    )

def encoder_runner_kind(*, runner: EncoderRunner, profile: AudioEncodingProfile) -> str:
    if profile.engine == "passthrough":
        return "passthrough"
    if profile.engine == "fake":
        return "fake"
    if isinstance(runner, FakeEncoderRunner):
        return "fake"
    if isinstance(runner, FfmpegEncoderRunner):
        return "ffmpeg"
    return "custom"

def encoder_runner_is_fake(*, runner: EncoderRunner | None = None, profile: AudioEncodingProfile | None = None, manifest: DomainDocument | None = None, summary_row: DomainDocument | None = None) -> bool:
    if manifest is not None:
        encoder = _as_document(manifest.get("encoder"))
        runner_doc = _as_document(encoder.get("runner"))
        return bool(encoder.get("engine") == "fake" or runner_doc.get("kind") == "fake" or runner_doc.get("fake"))
    if summary_row is not None:
        return bool(summary_row.get("fake_evidence") or summary_row.get("encoder_engine") == "fake" or summary_row.get("encoder_runner_kind") == "fake")
    return bool((profile and profile.engine == "fake") or isinstance(runner, FakeEncoderRunner))

def encoded_manifest_uses_fake(manifest: DomainDocument) -> bool:
    return encoder_runner_is_fake(manifest=manifest)

def encoded_audio_summary_uses_fake(summary: DomainDocument) -> bool:
    profiles = _as_list(summary.get("profiles"))
    return any(encoder_runner_is_fake(summary_row=row) for row in profiles if isinstance(row, dict))

def detect_audio_header(path: Path, *, expected_format: str | None = None) -> DomainDocument:
    try:
        data = path.read_bytes()[:32]
    except OSError:
        return {"valid": False, "detected_format": "missing"}
    detected = detect_audio_format_bytes(data)
    expected = str(expected_format or "").lower()
    valid = bool(detected and (not expected or detected == expected or (expected == "aac" and detected in {"aac", "m4a"})))
    return {"valid": valid, "detected_format": detected or "unknown", "expected_format": expected or None}

def detect_audio_format_bytes(data: bytes) -> str | None:
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "wav"
    if data.startswith(b"fLaC"):
        return "flac"
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "mp3"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        major = data[8:12].decode("ascii", errors="ignore").strip().lower()
        if major in {"m4a", "m4a ", "isom", "mp42", "mp41"} or "m4a" in data[:32].decode("ascii", errors="ignore").lower():
            return "aac"
    return None

def validate_relative_path(path: str) -> str:
    raw = str(path or "")
    if "\\" in raw:
        raise AudioEncodingStateError("Unsafe relative path.")
    parts = [part for part in raw.split("/") if part]
    if not parts or raw.startswith("/") or raw.startswith("//") or raw.endswith("/") or any(part in {"..", "."} for part in parts) or ":" in parts[0]:
        raise AudioEncodingStateError("Unsafe relative path.")
    return PurePosixPath(*parts).as_posix()

def encoded_audio_file_record(root: Path, path: Path) -> DomainDocument:
    rel = validate_relative_path(path.resolve().relative_to(root.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)}

def _profile_source(profile: AudioEncodingProfile) -> DomainDocument:
    return {"profile_id": profile.profile_id, "profile_hash": audio_encoding_profile_hash(profile), "format": profile.format, "extension": profile.extension}

def _track_result(profile: AudioEncodingProfile, track_id: str, source_row: DomainDocument, *, status: str, message: str) -> DomainDocument:
    return sanitize_metadata(
        {
            "track_id": track_id,
            "status": status,
            "source_path": source_row.get("source_path"),
            "source_wav_sha256": source_row.get("source_wav_sha256"),
            "output_rel": f"formats/{profile.profile_id}/tracks/{track_id}/song.{profile.extension}",
            "message": message,
            "failures": ["source_missing"],
            "warnings": [],
        },
        blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
    )

def _encoder_result_public(result: DomainDocument) -> DomainDocument:
    return sanitize_metadata(
        {
            "status": result.get("status"),
            "returncode": result.get("returncode"),
            "message": sanitize_sensitive_text(str(result.get("message") or ""))[:300],
            "stderr_summary": sanitize_sensitive_text(str(result.get("stderr_summary") or ""))[:500],
        },
        blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
    )

def _validate_profile_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not all(ch.isalnum() or ch in {"_", "-"} for ch in text) or len(text) > 100:
        raise AudioEncodingStateError("Invalid audio encoding profile id.")
    return text

def _validate_track_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not all(ch.isalnum() or ch in {"_", "-"} for ch in text) or len(text) > 100:
        raise AudioEncodingStateError("Invalid track id.")
    return text

def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise AudioEncodingStateError("Refusing to operate outside audio encoding boundaries.") from exc

def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None

def _wav_duration_seconds(path: Path) -> float | None:
    import wave

    try:
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            return round(wav.getnframes() / rate, 6) if rate else None
    except (OSError, EOFError, wave.Error):
        return None
