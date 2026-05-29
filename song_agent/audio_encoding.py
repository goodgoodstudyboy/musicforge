from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from song_agent.audio_encoding_profiles import (
    AudioEncodingProfile,
    AudioEncodingProfileError,
    AudioEncodingProfileStore,
    audio_encoding_profile_hash,
    audio_encoding_profile_integrity_ok,
)
from song_agent.mastering_qa import mastering_summary_hash
from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectStore, now_iso
from song_agent.redaction import sanitize_metadata, sanitize_sensitive_text
from song_agent.releases import BLOCKED_RELEASE_KEYS, ReleaseStateError, ReleaseStore, stable_hash


AUDIO_ENCODING_SCHEMA_VERSION = 1
AUDIO_ENCODING_BLOCKED_KEYS = BLOCKED_RELEASE_KEYS - {"path"}
AUDIO_ENCODING_INTEGRITY_EXCLUDE = {"integrity_hash", "stale", "stale_reasons", "current_source_hash", "current"}
AUDIO_ENCODING_SUMMARY_INTEGRITY_EXCLUDE = {"integrity_hash", "generated_at"}
ENCODER_CONFIG_FILENAME = "audio-encoder.json"
COMMAND_POLICY_VERSION = "v1"
MIN_ENCODED_AUDIO_BYTES = 8


class AudioEncodingError(ValueError):
    pass


class AudioEncodingNotFoundError(AudioEncodingError):
    pass


class AudioEncodingStateError(AudioEncodingError):
    pass


@dataclass(frozen=True)
class AudioEncoderConfig:
    engine: str = "ffmpeg"
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    timeout_seconds: int = 300
    max_parallel: int = 2
    fake_runner: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AudioEncoderConfig":
        data = data if isinstance(data, dict) else {}
        return cls(
            engine=str(data.get("engine") or "ffmpeg").strip().lower(),
            ffmpeg_path=str(os.environ.get("MUSICFORGE_FFMPEG_PATH") or data.get("ffmpeg_path") or "ffmpeg").strip(),
            ffprobe_path=str(os.environ.get("MUSICFORGE_FFPROBE_PATH") or data.get("ffprobe_path") or "ffprobe").strip(),
            timeout_seconds=_int_range(os.environ.get("MUSICFORGE_AUDIO_ENCODER_TIMEOUT") or data.get("timeout_seconds") or 300, "timeout_seconds", 1, 3600),
            max_parallel=_int_range(data.get("max_parallel") or 2, "max_parallel", 1, 16),
            fake_runner=bool(data.get("fake_runner", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "ffmpeg_path": self.ffmpeg_path,
            "ffprobe_path": self.ffprobe_path,
            "timeout_seconds": self.timeout_seconds,
            "max_parallel": self.max_parallel,
            "fake_runner": self.fake_runner,
        }

    def public_summary(self) -> dict[str, Any]:
        return sanitize_metadata(
            {
                "engine": self.engine,
                "ffmpeg": {"basename": Path(self.ffmpeg_path).name, "configured": bool(self.ffmpeg_path), "exists": _executable_exists(self.ffmpeg_path)},
                "ffprobe": {"basename": Path(self.ffprobe_path).name, "configured": bool(self.ffprobe_path), "exists": _executable_exists(self.ffprobe_path)},
                "timeout_seconds": self.timeout_seconds,
                "max_parallel": self.max_parallel,
                "fake_runner": self.fake_runner,
                "paths_redacted": True,
            },
            blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
        )


class EncoderRunner(Protocol):
    def encode(self, *, source: Path, target: Path, profile: AudioEncodingProfile, config: AudioEncoderConfig) -> dict[str, Any]:
        ...


class FfmpegEncoderRunner:
    def encode(self, *, source: Path, target: Path, profile: AudioEncodingProfile, config: AudioEncoderConfig) -> dict[str, Any]:
        argv = build_ffmpeg_command(source=source, target=target, profile=profile, config=config)
        try:
            completed = subprocess.run(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=config.timeout_seconds,
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {"status": "failed", "returncode": None, "message": f"Encoder timed out after {config.timeout_seconds} seconds.", "stderr_summary": sanitize_sensitive_text(str(exc))[:500]}
        except OSError as exc:
            return {"status": "failed", "returncode": None, "message": "Encoder executable was not found or could not be started.", "stderr_summary": sanitize_sensitive_text(str(exc))[:500]}
        stderr = sanitize_sensitive_text((completed.stderr or b"").decode("utf-8", errors="replace"))[:1000]
        stdout = sanitize_sensitive_text((completed.stdout or b"").decode("utf-8", errors="replace"))[:1000]
        return {
            "status": "completed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "message": "Encoder completed." if completed.returncode == 0 else "Encoder failed.",
            "stdout_summary": stdout,
            "stderr_summary": stderr,
        }


class FakeEncoderRunner:
    def encode(self, *, source: Path, target: Path, profile: AudioEncodingProfile, config: AudioEncoderConfig) -> dict[str, Any]:
        target.parent.mkdir(parents=True, exist_ok=True)
        if profile.format == "wav":
            shutil.copy2(source, target)
        elif profile.format == "mp3":
            target.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x15MusicForgeFakeMP3")
        elif profile.format == "flac":
            target.write_bytes(b"fLaC\x00\x00\x00\"MusicForgeFakeFLAC")
        elif profile.format == "aac":
            target.write_bytes(b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00M4A isommp42")
        else:
            return {"status": "failed", "returncode": None, "message": "Unsupported fake encoder format."}
        return {"status": "completed", "returncode": 0, "message": "Fake encoder completed for deterministic tests."}


class AudioEncodingStore:
    def __init__(
        self,
        release_store: ReleaseStore,
        project_store: ProjectStore | None = None,
        profile_store: AudioEncodingProfileStore | None = None,
        runner: EncoderRunner | None = None,
    ) -> None:
        self.release_store = release_store
        self.project_store = project_store or release_store.project_store
        self.profile_store = profile_store or AudioEncodingProfileStore(self.release_store.root.parent / "audio-encoding-profiles")
        self.runner = runner
        self.lock = threading.RLock()

    @property
    def config_path(self) -> Path:
        return self.release_store.root.parent / ENCODER_CONFIG_FILENAME

    def root_dir(self, release_id: str) -> Path:
        return self.release_store.release_dir(release_id) / "encoded-audio"

    def formats_dir(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "formats"

    def format_dir(self, release_id: str, profile_id: str) -> Path:
        return self.formats_dir(release_id) / _validate_profile_id(profile_id)

    def manifest_path(self, release_id: str, profile_id: str) -> Path:
        return self.format_dir(release_id, profile_id) / "manifest.json"

    def summary_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "summary.json"

    def source_snapshot_path(self, release_id: str) -> Path:
        return self.root_dir(release_id) / "source-snapshot.json"

    def track_audio_path(self, release_id: str, profile_id: str, track_id: str) -> Path:
        profile = self.profile_store.get_profile(profile_id)
        return self.format_dir(release_id, profile.profile_id) / "tracks" / _validate_track_id(track_id) / f"song.{profile.extension}"

    def read_config(self) -> AudioEncoderConfig:
        if not self.config_path.exists():
            return AudioEncoderConfig.from_dict({})
        return AudioEncoderConfig.from_dict(read_json(self.config_path))

    def write_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = AudioEncoderConfig.from_dict(payload)
        write_json(self.config_path, config.to_dict())
        return config.public_summary()

    def reset_config(self) -> dict[str, Any]:
        if self.config_path.exists():
            self.config_path.unlink()
        return self.read_config().public_summary()

    def test_config(self) -> dict[str, Any]:
        config = self.read_config()
        ffmpeg_ok = _executable_exists(config.ffmpeg_path)
        status = "passed" if ffmpeg_ok or config.fake_runner else "failed"
        message = "Encoder config is usable." if status == "passed" else "Encoder executable was not found."
        return {"status": status, "message": message, "config": config.public_summary()}

    def get_summary(self, release_id: str, *, now: str | None = None, current: bool = True) -> dict[str, Any]:
        self.release_store.get_release(release_id)
        manifests = self.list_manifests(release_id, current=current)
        summary = build_encoded_audio_summary(release_id, manifests, now=now)
        write_json(self.summary_path(release_id), summary)
        return summary

    def list_manifests(self, release_id: str, *, current: bool = True) -> list[dict[str, Any]]:
        self.release_store.get_release(release_id)
        rows: list[dict[str, Any]] = []
        if not self.formats_dir(release_id).exists():
            return rows
        for path in sorted(self.formats_dir(release_id).glob("*/manifest.json")):
            try:
                data = read_json(path)
                if isinstance(data, dict):
                    if current:
                        rows.append(self.with_current_state(release_id, data))
                    else:
                        clean = sanitize_metadata(data, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS)
                        if not encoded_manifest_integrity_ok(clean):
                            clean["stale"] = True
                            clean["stale_reasons"] = ["integrity_hash"]
                        rows.append(clean)
            except Exception:
                continue
        return rows

    def read_manifest(self, release_id: str, profile_id: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
        path = self.manifest_path(release_id, profile_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioEncodingNotFoundError(f"Encoded audio manifest not found: {profile_id}.")
        data = read_json(path)
        return self.with_current_state(release_id, data if isinstance(data, dict) else {})

    def render(self, release_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        profile_ids = payload.get("profile_ids")
        if isinstance(profile_ids, str):
            profile_ids = [item.strip() for item in profile_ids.split(",") if item.strip()]
        if not isinstance(profile_ids, list) or not profile_ids:
            profile_ids = [str(payload.get("profile_id") or "wav_master")]
        manifests = []
        for profile_id in profile_ids:
            manifests.append(self.render_format(release_id, str(profile_id), payload, now=now))
        return {"release_id": release_id, "formats": manifests, "summary": self.get_summary(release_id, now=now)}

    def render_format(self, release_id: str, profile_id: str, payload: dict[str, Any] | None = None, *, now: str | None = None) -> dict[str, Any]:
        payload = payload or {}
        now = now or now_iso()
        self._ensure_release_mutable(release_id)
        profile = self.profile_store.get_profile(profile_id)
        if not audio_encoding_profile_integrity_ok(profile.to_dict()):
            raise AudioEncodingProfileError("Audio encoding profile integrity failed.")
        source = encoded_audio_source_state(self.release_store, release_id, profile)
        if source.get("status") != "current":
            raise AudioEncodingStateError(str(source.get("message") or "Release Export is stale. Rebuild export before encoding."))
        with self.lock:
            root = self.format_dir(release_id, profile.profile_id)
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True, exist_ok=True)
            source_snapshot = sanitize_metadata({key: value for key, value in source.items() if key not in {"tracks_by_id"}}, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS)
            write_json(self.source_snapshot_path(release_id), source_snapshot)
            tracks = []
            config = self.read_config()
            runner = self.runner or (FakeEncoderRunner() if config.fake_runner or profile.engine == "fake" else FfmpegEncoderRunner())
            for row in source.get("tracks", []) if isinstance(source.get("tracks"), list) else []:
                tracks.append(self._render_track(release_id, profile, row, config=config, runner=runner, now=now))
            failed_count = sum(1 for row in tracks if row.get("status") == "failed")
            warning_count = sum(1 for row in tracks if row.get("warnings"))
            status = "failed" if failed_count else "warning" if warning_count else "completed"
            manifest = {
                "schema_version": AUDIO_ENCODING_SCHEMA_VERSION,
                "release_id": release_id,
                "profile_id": profile.profile_id,
                "profile_hash": audio_encoding_profile_hash(profile),
                "format": profile.format,
                "extension": profile.extension,
                "generated_at": now,
                "source": source_snapshot,
                "source_hash": stable_hash(source_snapshot),
                "encoder": encoder_manifest_payload(profile, config),
                "tracks": tracks,
                "summary": {
                    "status": status,
                    "track_count": len(tracks),
                    "completed_count": sum(1 for row in tracks if row.get("status") == "completed"),
                    "failed_count": failed_count,
                    "warning_count": warning_count,
                },
            }
            manifest["integrity_hash"] = encoded_manifest_hash(manifest)
            manifest = sanitize_metadata(manifest, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS)
            write_json(self.manifest_path(release_id, profile.profile_id), manifest)
            self.release_store.append_event(release_id, "release_encoded_audio_rendered", {"profile_id": profile.profile_id, "status": status})
            self.get_summary(release_id, now=now)
            return manifest

    def verify(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        required = normalize_required_profiles(payload.get("required_audio_format_profiles") or payload.get("profile_ids") or payload.get("profiles") or [])
        if bool(payload.get("require_encoded_audio", False)) and not required:
            required = ["wav_master"]
        gate = encoded_audio_gate(self, release_id, required_profiles=required, required=bool(payload.get("require_encoded_audio", False)))
        return {"release_id": release_id, "gate": gate, "summary": self.get_summary(release_id)}

    def reset(self, release_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ensure_release_mutable(release_id)
        root = self.root_dir(release_id)
        if root.exists():
            shutil.rmtree(root)
        self.release_store.append_event(release_id, "release_encoded_audio_reset", {"reason": sanitize_sensitive_text(str((payload or {}).get("reason") or ""))[:240]})
        return {"status": "reset", "release_id": release_id}

    def with_current_state(self, release_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        clean = sanitize_metadata(manifest, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS)
        reasons: list[str] = []
        profile_id = str(clean.get("profile_id") or "")
        try:
            profile = self.profile_store.get_profile(profile_id)
            current_source = encoded_audio_source_state(self.release_store, release_id, profile)
            current_snapshot = sanitize_metadata({key: value for key, value in current_source.items() if key not in {"tracks_by_id"}}, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS)
            current_hash = stable_hash(current_snapshot)
        except Exception:
            current_hash = ""
        if current_hash and clean.get("source_hash") != current_hash:
            reasons.append("source_hash")
        if not encoded_manifest_integrity_ok(clean):
            reasons.append("integrity_hash")
        for row in clean.get("tracks", []) if isinstance(clean.get("tracks"), list) else []:
            if not isinstance(row, dict):
                continue
            path = self.root_dir(release_id) / validate_relative_path(str(row.get("output_rel") or ""))
            if not path.exists() or not path.is_file() or path.is_symlink():
                reasons.append(f"{row.get('track_id')}:missing_output")
                continue
            if _sha256_file(path) != row.get("output_sha256"):
                reasons.append(f"{row.get('track_id')}:output_hash")
            header = detect_audio_header(path, expected_format=str(clean.get("format") or ""))
            if not header.get("valid"):
                reasons.append(f"{row.get('track_id')}:header")
        clean["current_source_hash"] = current_hash or None
        clean["stale_reasons"] = sorted(set(reasons))
        clean["stale"] = bool(reasons)
        clean["current"] = not reasons
        return clean

    def _render_track(
        self,
        release_id: str,
        profile: AudioEncodingProfile,
        source_row: dict[str, Any],
        *,
        config: AudioEncoderConfig,
        runner: EncoderRunner,
        now: str,
    ) -> dict[str, Any]:
        track_id = _validate_track_id(str(source_row.get("track_id") or ""))
        source_rel = validate_relative_path(str(source_row.get("source_path") or ""))
        release_export_dir = self.release_store.export_dir(release_id).resolve()
        source_path = (release_export_dir / source_rel).resolve()
        _ensure_within(release_export_dir, source_path)
        if not source_path.exists() or not source_path.is_file() or source_path.is_symlink():
            return _track_result(profile, track_id, source_row, status="failed", message="Source WAV is missing.")
        output_rel = f"formats/{profile.profile_id}/tracks/{track_id}/song.{profile.extension}"
        output_path = (self.root_dir(release_id) / validate_relative_path(output_rel)).resolve()
        _ensure_within(self.root_dir(release_id).resolve(), output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        run_result: dict[str, Any]
        if profile.engine == "passthrough":
            shutil.copy2(source_path, output_path)
            run_result = {"status": "completed", "returncode": 0, "message": "WAV master copied without re-encoding."}
        else:
            run_result = runner.encode(source=source_path, target=output_path, profile=profile, config=config)
        if run_result.get("status") == "completed" and (not output_path.exists() or not output_path.is_file()):
            run_result = {**run_result, "status": "failed", "message": "Encoder reported success but output file is missing."}
        header = detect_audio_header(output_path, expected_format=profile.format) if output_path.exists() else {"valid": False, "detected_format": "missing"}
        size = output_path.stat().st_size if output_path.exists() else 0
        warnings: list[str] = []
        failures: list[str] = []
        if run_result.get("status") != "completed":
            failures.append("encoder_failed")
        if size < MIN_ENCODED_AUDIO_BYTES:
            failures.append("output_too_small")
        if not header.get("valid"):
            failures.append("header_mismatch")
        status = "failed" if failures else "completed"
        return sanitize_metadata(
            {
                "track_id": track_id,
                "status": status,
                "source_path": source_rel,
                "source_wav_sha256": source_row.get("source_wav_sha256"),
                "source_size_bytes": source_row.get("source_size_bytes"),
                "output_rel": output_rel,
                "output_sha256": _sha256_file(output_path) if output_path.exists() else None,
                "size_bytes": size,
                "duration_seconds": source_row.get("duration_seconds"),
                "header": header,
                "encoder_result": _encoder_result_public(run_result),
                "warnings": warnings,
                "failures": failures,
                "generated_at": now,
            },
            blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
        )

    def _ensure_release_mutable(self, release_id: str) -> None:
        release = self.release_store.get_release(release_id)
        if release.status == "archived":
            raise ReleaseStateError("Archived releases are read-only.")
        if release.status == "signed":
            raise ReleaseStateError("Signed releases cannot mutate encoded audio. Reset signoff before encoding again.")


def encoded_audio_source_state(release_store: ReleaseStore, release_id: str, profile: AudioEncodingProfile) -> dict[str, Any]:
    from song_agent.release_export import read_release_export_manifest

    try:
        manifest = read_release_export_manifest(release_store, release_id)
    except FileNotFoundError:
        return {"release_id": release_id, "profile": _profile_source(profile), "status": "missing", "message": "Release Export is missing."}
    export_dir = release_store.export_dir(release_id)
    tracks = manifest.get("tracks") if isinstance(manifest.get("tracks"), list) else []
    mastering = manifest.get("mastering") if isinstance(manifest.get("mastering"), dict) else {}
    export_hash = release_export_audio_source_hash(manifest)
    source_tracks: list[dict[str, Any]] = []
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


def build_encoded_audio_summary(release_id: str, manifests: list[dict[str, Any]], *, now: str | None = None) -> dict[str, Any]:
    now = now or now_iso()
    profiles = []
    missing = []
    stale = []
    failed = []
    for manifest in manifests:
        profile_id = str(manifest.get("profile_id") or "")
        summary = manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {}
        row = {
            "profile_id": profile_id,
            "status": "stale" if manifest.get("stale") else summary.get("status") or "missing",
            "format": manifest.get("format"),
            "extension": manifest.get("extension"),
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


def release_export_audio_source_hash(manifest: dict[str, Any]) -> str:
    mastering = manifest.get("mastering") if isinstance(manifest.get("mastering"), dict) else {}
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
                    for item in (manifest.get("tracks") if isinstance(manifest.get("tracks"), list) else [])
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


def encoded_audio_gate(store: AudioEncodingStore, release_id: str, *, required_profiles: list[str], required: bool, force: bool = False) -> dict[str, Any]:
    required_profiles = normalize_required_profiles(required_profiles)
    if required and not required_profiles:
        required_profiles = ["wav_master"]
    if not required:
        summary = store.get_summary(release_id)
        return {**summary, "require_encoded_audio": False, "status": "passed" if summary.get("status") in {"completed", "missing"} else summary.get("status")}
    missing: list[str] = []
    stale: list[str] = []
    failed: list[str] = []
    warnings: list[str] = []
    profile_summaries: list[dict[str, Any]] = []
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
        }
        profile_summaries.append(row)
        if manifest.get("stale") or not encoded_manifest_integrity_ok(manifest):
            stale.append(profile_id)
        if (manifest.get("summary") or {}).get("status") == "failed":
            failed.append(profile_id)
        elif (manifest.get("summary") or {}).get("status") == "warning":
            warnings.append(profile_id)
    hard = bool(missing or stale or failed)
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
            "warning_profiles": warnings,
            "message": "Encoded audio gate failed." if hard or warning_block else "Encoded audio gate passed.",
        },
        blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
    )


def export_encoded_audio_summary(release_store: ReleaseStore, release_id: str, export_dir: Path, *, store: AudioEncodingStore | None = None) -> dict[str, Any]:
    store = store or AudioEncodingStore(release_store, project_store=release_store.project_store)
    summary = store.get_summary(release_id, current=False)
    target = export_dir / "encoded-audio-summary.json"
    write_json(target, summary)
    return {
        **summary,
        "summary_path": "encoded-audio-summary.json",
        "summary_hash": encoded_audio_summary_hash(summary),
    }


def encoded_manifest_hash(manifest: dict[str, Any]) -> str:
    return stable_hash(sanitize_metadata({key: value for key, value in manifest.items() if key not in AUDIO_ENCODING_INTEGRITY_EXCLUDE}, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS))


def encoded_manifest_integrity_ok(manifest: dict[str, Any]) -> bool:
    expected = str(manifest.get("integrity_hash") or "")
    return bool(expected) and expected == encoded_manifest_hash(manifest)


def encoded_audio_summary_hash(summary: dict[str, Any]) -> str:
    return stable_hash(sanitize_metadata({key: value for key, value in summary.items() if key not in AUDIO_ENCODING_SUMMARY_INTEGRITY_EXCLUDE}, blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS))


def encoded_audio_summary_integrity_ok(summary: dict[str, Any]) -> bool:
    expected = str(summary.get("integrity_hash") or "")
    return bool(expected) and expected == encoded_audio_summary_hash(summary)


def normalize_required_profiles(value: Any) -> list[str]:
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


def resolve_target_audio_format_profiles(target: Any, template: dict[str, Any] | None = None) -> list[str]:
    options = getattr(target, "options", None)
    options = options if isinstance(options, dict) else {}
    rules = template.get("rules") if isinstance(template, dict) and isinstance(template.get("rules"), dict) else {}
    profiles = normalize_required_profiles(options.get("audio_format_profiles"))
    if not profiles:
        profiles = normalize_required_profiles(rules.get("required_audio_formats"))
    if not profiles:
        primary = str(options.get("primary_audio_format") or rules.get("primary_audio_format") or "").strip()
        profiles = normalize_required_profiles(primary)
    return profiles or ["wav_master"]


def primary_target_audio_format_profile(target: Any, template: dict[str, Any] | None = None) -> str:
    options = getattr(target, "options", None)
    options = options if isinstance(options, dict) else {}
    rules = template.get("rules") if isinstance(template, dict) and isinstance(template.get("rules"), dict) else {}
    primary = str(options.get("primary_audio_format") or rules.get("primary_audio_format") or "").strip()
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


def encoder_manifest_payload(profile: AudioEncodingProfile, config: AudioEncoderConfig) -> dict[str, Any]:
    command_template = build_ffmpeg_command(source=Path("{source}"), target=Path("{target}"), profile=profile, config=AudioEncoderConfig(ffmpeg_path="{ffmpeg}", ffprobe_path="{ffprobe}", timeout_seconds=config.timeout_seconds, max_parallel=config.max_parallel))
    return sanitize_metadata(
        {
            "engine": profile.engine,
            "profile_id": profile.profile_id,
            "profile_hash": audio_encoding_profile_hash(profile),
            "command_template_hash": stable_hash(command_template),
            "command_policy_version": COMMAND_POLICY_VERSION,
            "ffmpeg": {"basename": Path(config.ffmpeg_path).name if profile.engine == "ffmpeg" else None},
        },
        blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
    )


def detect_audio_header(path: Path, *, expected_format: str | None = None) -> dict[str, Any]:
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


def encoded_audio_file_record(root: Path, path: Path) -> dict[str, Any]:
    rel = validate_relative_path(path.resolve().relative_to(root.resolve()).as_posix())
    return {"path": rel, "size_bytes": path.stat().st_size, "sha256": _sha256_file(path)}


def _profile_source(profile: AudioEncodingProfile) -> dict[str, Any]:
    return {"profile_id": profile.profile_id, "profile_hash": audio_encoding_profile_hash(profile), "format": profile.format, "extension": profile.extension}


def _track_result(profile: AudioEncodingProfile, track_id: str, source_row: dict[str, Any], *, status: str, message: str) -> dict[str, Any]:
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


def _encoder_result_public(result: dict[str, Any]) -> dict[str, Any]:
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


def _executable_exists(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if any(sep in text for sep in ("/", "\\")):
        path = Path(text)
        return path.exists() and path.is_file()
    return shutil.which(text) is not None


def _int_range(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AudioEncodingError(f"{field} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise AudioEncodingError(f"{field} must be between {minimum} and {maximum}.")
    return parsed
