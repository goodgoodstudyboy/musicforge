# ruff: noqa: E402,F401
from __future__ import annotations

from typing import Any as _InferenceType

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import json as json
import os as os
import shutil as shutil
import subprocess as subprocess
import threading as threading
from dataclasses import dataclass as dataclass
from pathlib import Path as Path, PurePosixPath as PurePosixPath
from typing import Any as Any, Protocol as Protocol

from song_agent.domains.quality.audio_encoding_profiles import AudioEncodingProfile as AudioEncodingProfile, AudioEncodingProfileError as AudioEncodingProfileError, AudioEncodingProfileStore as AudioEncodingProfileStore, audio_encoding_profile_hash as audio_encoding_profile_hash, audio_encoding_profile_integrity_ok as audio_encoding_profile_integrity_ok
from song_agent.domains.quality.mastering_qa import mastering_summary_hash as mastering_summary_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.studio.project_repository import ProjectStore as ProjectStore, now_iso as now_iso
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata, sanitize_sensitive_text as sanitize_sensitive_text
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS as BLOCKED_RELEASE_KEYS, ReleaseStateError as ReleaseStateError, ReleaseStore as ReleaseStore, stable_hash as stable_hash


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
    def from_dict(cls, data: DomainDocument | None, *, allow_fake_runner: bool = False) -> "AudioEncoderConfig":
        data = _as_document(data)
        return cls(
            engine=str(data.get("engine") or "ffmpeg").strip().lower(),
            ffmpeg_path=str(os.environ.get("MUSICFORGE_FFMPEG_PATH") or data.get("ffmpeg_path") or "ffmpeg").strip(),
            ffprobe_path=str(os.environ.get("MUSICFORGE_FFPROBE_PATH") or data.get("ffprobe_path") or "ffprobe").strip(),
            timeout_seconds=_int_range(os.environ.get("MUSICFORGE_AUDIO_ENCODER_TIMEOUT") or data.get("timeout_seconds") or 300, "timeout_seconds", 1, 3600),
            max_parallel=_int_range(data.get("max_parallel") or 2, "max_parallel", 1, 16),
            fake_runner=bool(data.get("fake_runner", False)) if allow_fake_runner else False,
        )

    def to_dict(self) -> DomainDocument:
        return {
            "engine": self.engine,
            "ffmpeg_path": self.ffmpeg_path,
            "ffprobe_path": self.ffprobe_path,
            "timeout_seconds": self.timeout_seconds,
            "max_parallel": self.max_parallel,
        }

    def public_summary(self) -> DomainDocument:
        return sanitize_metadata(
            {
                "engine": self.engine,
                "ffmpeg": {"basename": Path(self.ffmpeg_path).name, "configured": bool(self.ffmpeg_path), "exists": _executable_exists(self.ffmpeg_path)},
                "ffprobe": {"basename": Path(self.ffprobe_path).name, "configured": bool(self.ffprobe_path), "exists": _executable_exists(self.ffprobe_path)},
                "timeout_seconds": self.timeout_seconds,
                "max_parallel": self.max_parallel,
                "paths_redacted": True,
            },
            blocked_keys=AUDIO_ENCODING_BLOCKED_KEYS,
        )


class EncoderRunner(Protocol):
    def encode(self, *, source: Path, target: Path, profile: AudioEncodingProfile, config: AudioEncoderConfig) -> DomainDocument:
        ...


class FfmpegEncoderRunner:
    def encode(self, *, source: Path, target: Path, profile: AudioEncodingProfile, config: AudioEncoderConfig) -> DomainDocument:
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
    def encode(self, *, source: Path, target: Path, profile: AudioEncodingProfile, config: AudioEncoderConfig) -> DomainDocument:
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

    def write_config(self, payload: DomainDocument) -> DomainDocument:
        if isinstance(payload, dict) and bool(payload.get("fake_runner", False)):
            raise AudioEncodingError("fake_runner is test-only and cannot be persisted through the public audio encoding config.")
        config = AudioEncoderConfig.from_dict(payload)
        write_json(self.config_path, config.to_dict())
        return config.public_summary()

    def reset_config(self) -> DomainDocument:
        if self.config_path.exists():
            self.config_path.unlink()
        return self.read_config().public_summary()

    def test_config(self) -> DomainDocument:
        config = self.read_config()
        ffmpeg_ok = _executable_exists(config.ffmpeg_path)
        status = "passed" if ffmpeg_ok else "failed"
        message = "Encoder config is usable." if status == "passed" else "Encoder executable was not found."
        return {"status": status, "message": message, "config": config.public_summary()}

    def get_summary(self, release_id: str, *, now: str | None = None, current: bool = True) -> DomainDocument:
        self.release_store.get_release(release_id)
        manifests = self.list_manifests(release_id, current=current)
        summary = build_encoded_audio_summary(release_id, manifests, now=now)
        write_json(self.summary_path(release_id), summary)
        return summary

    def list_manifests(self, release_id: str, *, current: bool = True) -> list[DomainDocument]:
        self.release_store.get_release(release_id)
        rows: list[ImplementationDocument] = []
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

    def read_manifest(self, release_id: str, profile_id: str, default: DomainDocument | None = None) -> DomainDocument:
        path = self.manifest_path(release_id, profile_id)
        if not path.exists():
            if default is not None:
                return default
            raise AudioEncodingNotFoundError(f"Encoded audio manifest not found: {profile_id}.")
        data = read_json(path)
        return self.with_current_state(release_id, _as_document(data))

    def render(self, release_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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

    def render_format(self, release_id: str, profile_id: str, payload: DomainDocument | None = None, *, now: str | None = None) -> DomainDocument:
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
            runner = self.runner or (FakeEncoderRunner() if profile.engine == "fake" else FfmpegEncoderRunner())
            runner_kind = encoder_runner_kind(runner=runner, profile=profile)
            fake_evidence = encoder_runner_is_fake(runner=runner, profile=profile)
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
                "encoder": encoder_manifest_payload(profile, config, runner_kind=runner_kind, fake_evidence=fake_evidence),
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

    def verify(self, release_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        payload = payload or {}
        required = normalize_required_profiles(payload.get("required_audio_format_profiles") or payload.get("profile_ids") or payload.get("profiles") or [])
        if bool(payload.get("require_encoded_audio", False)) and not required:
            required = ["wav_master"]
        gate = encoded_audio_gate(self, release_id, required_profiles=required, required=bool(payload.get("require_encoded_audio", False)))
        return {"release_id": release_id, "gate": gate, "summary": self.get_summary(release_id)}

    def reset(self, release_id: str, payload: DomainDocument | None = None) -> DomainDocument:
        self._ensure_release_mutable(release_id)
        root = self.root_dir(release_id)
        if root.exists():
            shutil.rmtree(root)
        self.release_store.append_event(release_id, "release_encoded_audio_reset", {"reason": sanitize_sensitive_text(str((payload or {}).get("reason") or ""))[:240]})
        return {"status": "reset", "release_id": release_id}

    def with_current_state(self, release_id: str, manifest: DomainDocument) -> DomainDocument:
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
        source_row: ImplementationDocument,
        *,
        config: AudioEncoderConfig,
        runner: EncoderRunner,
        now: str,
    ) -> ImplementationDocument:
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
        run_result: ImplementationDocument
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


from song_agent.domains.quality import v142_ae_readiness as _v142_ae_readiness
from song_agent.domains.quality.v142_ae_readiness import encoded_audio_source_state as encoded_audio_source_state, build_encoded_audio_summary as build_encoded_audio_summary, release_export_audio_source_hash as release_export_audio_source_hash, encoded_audio_gate as encoded_audio_gate, export_encoded_audio_summary as export_encoded_audio_summary, encoded_manifest_hash as encoded_manifest_hash, encoded_manifest_integrity_ok as encoded_manifest_integrity_ok, encoded_audio_summary_hash as encoded_audio_summary_hash, encoded_audio_summary_integrity_ok as encoded_audio_summary_integrity_ok, normalize_required_profiles as normalize_required_profiles, resolve_target_audio_format_profiles as resolve_target_audio_format_profiles, primary_target_audio_format_profile as primary_target_audio_format_profile, build_ffmpeg_command as build_ffmpeg_command, encoder_manifest_payload as encoder_manifest_payload, encoder_runner_kind as encoder_runner_kind, encoder_runner_is_fake as encoder_runner_is_fake, encoded_manifest_uses_fake as encoded_manifest_uses_fake, encoded_audio_summary_uses_fake as encoded_audio_summary_uses_fake, detect_audio_header as detect_audio_header, detect_audio_format_bytes as detect_audio_format_bytes, validate_relative_path as validate_relative_path, encoded_audio_file_record as encoded_audio_file_record, _profile_source as _profile_source, _track_result as _track_result, _encoder_result_public as _encoder_result_public, _validate_profile_id as _validate_profile_id, _validate_track_id as _validate_track_id, _ensure_within as _ensure_within, _sha256_file as _sha256_file, _wav_duration_seconds as _wav_duration_seconds
from song_agent.domains.quality import v142_ae_evidence as _v142_ae_evidence
from song_agent.domains.quality.v142_ae_evidence import _executable_exists as _executable_exists, _int_range as _int_range

_v142_ae_readiness.bind_globals(globals())
_v142_ae_evidence.bind_globals(globals())
