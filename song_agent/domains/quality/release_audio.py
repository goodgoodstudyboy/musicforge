from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

import json
from pathlib import Path
from typing import Any

from song_agent.domains.quality.audio_health import analyze_wav_health, audio_health_allows_release, audio_health_integrity_ok, audio_health_summary
from song_agent.domains.quality.audio_artifacts import audio_artifact_stale_reasons_for_profile, audio_artifact_summary
from song_agent.domains.quality.audio_profiles import AudioProfileStore
from song_agent.domains.creation.final_export import final_export_dir
from song_agent.domains.studio.projectio import read_json, write_json
from song_agent.domains.studio.project_repository import ProjectStore, now_iso
from song_agent.domains.creation.redaction import sanitize_metadata
from song_agent.domains.delivery.release_qa import release_source_hash
from song_agent.domains.delivery.releases import BLOCKED_RELEASE_KEYS, ReleaseDocument, ReleaseStore, stable_hash


RELEASE_AUDIO_QA_SCHEMA_VERSION = 1


class ReleaseAudioError(ValueError):
    pass


def build_release_audio_qa_report(
    *,
    release: ReleaseDocument,
    release_store: ReleaseStore,
    project_store: ProjectStore,
    require_audio: bool = True,
    now: str | None = None,
) -> dict[str, Any]:
    now = now or now_iso()
    tracks: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        export_dir = final_export_dir(project_store.project_dir(track.project_id)).resolve()
        project_root = project_store.project_dir(track.project_id).resolve()
        try:
            export_dir.relative_to(project_root)
        except ValueError as exc:
            raise ReleaseAudioError("Project Final Export path is outside project root.") from exc
        wav_path = export_dir / "song.wav"
        artifact_path = export_dir / "audio-artifact.json"
        health = {}
        artifact = {}
        if wav_path.exists() and wav_path.is_file() and not wav_path.is_symlink():
            health = analyze_wav_health(
                wav_path,
                source={"release_id": release.release_id, "track_id": track.track_id, "project_id": track.project_id, "version_id": track.version_id},
                report_id=f"ahr-{release.release_id}-{track.track_id}",
                now=now,
            )
        if artifact_path.exists() and artifact_path.is_file() and not artifact_path.is_symlink():
            artifact = read_json(artifact_path)
        artifact_stale_reasons = _artifact_stale_reasons(artifact, wav_path=wav_path, midi_path=export_dir / "song.mid", song_plan_path=export_dir / "song-plan.json", project_store=project_store)
        summary = audio_health_summary(health)
        missing = not bool(health)
        artifact_current = bool(artifact) and not artifact_stale_reasons
        current = bool(health) and audio_health_integrity_ok(health) and artifact_current
        status = "missing" if missing else "passed" if audio_health_allows_release(health) and current else "failed"
        if require_audio and missing:
            blockers.append(f"{track.track_id}: song.wav is missing")
        elif require_audio and not artifact_current:
            blockers.append(f"{track.track_id}: audio artifact is stale or missing")
        elif require_audio and status == "failed":
            blockers.append(f"{track.track_id}: audio health failed")
        elif status == "failed":
            warnings.append(f"{track.track_id}: optional audio health failed")
        tracks.append(
            sanitize_metadata(
                {
                    "track_id": track.track_id,
                    "disc_number": track.disc_number,
                    "track_number": track.track_number,
                    "title": track.title,
                    "project_id": track.project_id,
                    "version_id": track.version_id,
                    "audio_required": require_audio,
                    "audio_status": status,
                    "health_status": summary.get("status"),
                    "health": summary,
                    "health_report": health,
                    "artifact": {**audio_artifact_summary(artifact, wav_path=wav_path, midi_path=export_dir / "song.mid", song_plan_path=export_dir / "song-plan.json"), "stale_reasons": artifact_stale_reasons, "current": artifact_current},
                },
                blocked_keys=BLOCKED_RELEASE_KEYS,
            )
        )
    status = "failed" if blockers else "warning" if warnings else "passed"
    source_hash = release_audio_source_hash(release, project_store=project_store, release_store=release_store)
    report = {
        "schema_version": RELEASE_AUDIO_QA_SCHEMA_VERSION,
        "release_id": release.release_id,
        "status": status,
        "generated_at": now,
        "source_hash": source_hash,
        "require_audio": require_audio,
        "summary": {
            "track_count": len(tracks),
            "audio_required": require_audio,
            "audio_passed_count": sum(1 for item in tracks if item.get("audio_status") == "passed"),
            "missing_audio_count": sum(1 for item in tracks if item.get("audio_status") == "missing"),
            "failed_audio_count": sum(1 for item in tracks if item.get("audio_status") == "failed"),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
        "tracks": tracks,
        "blockers": blockers,
        "warnings": warnings,
    }
    report["integrity_hash"] = release_audio_report_hash(report)
    return sanitize_metadata(report, blocked_keys=BLOCKED_RELEASE_KEYS)


def release_audio_source_hash(release: ReleaseDocument, *, project_store: ProjectStore, release_store: ReleaseStore) -> str:
    tracks: list[dict[str, Any]] = []
    for track in sorted(release.tracks, key=lambda item: (item.disc_number, item.track_number, item.track_id)):
        export_dir = final_export_dir(project_store.project_dir(track.project_id))
        wav_path = export_dir / "song.wav"
        manifest_path = export_dir / "manifest.json"
        artifact_path = export_dir / "audio-artifact.json"
        tracks.append(
            {
                "track_id": track.track_id,
                "project_id": track.project_id,
                "version_id": track.version_id,
                "wav": _file_state(wav_path),
                "audio_artifact": _json_state(artifact_path),
                "final_export_manifest": _json_state(manifest_path),
            }
        )
    return stable_hash({"release_source": release_source_hash(release, project_store=project_store, release_store=release_store), "tracks": tracks})


def release_audio_report_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in report.items() if key != "integrity_hash"})


def release_audio_report_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == release_audio_report_hash(report)


def release_audio_allows_signoff(report: dict[str, Any], *, current_source_hash: str | None = None) -> bool:
    if not report:
        return False
    if not release_audio_report_integrity_ok(report):
        return False
    if current_source_hash is not None and report.get("source_hash") != current_source_hash:
        return False
    return str(report.get("status") or "") in {"passed", "warning"}


def release_audio_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = report if isinstance(report, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "release_id": data.get("release_id"),
            "source_hash": data.get("source_hash"),
            "integrity_hash": data.get("integrity_hash"),
            "require_audio": bool(data.get("require_audio", False)),
            "track_count": summary.get("track_count", 0),
            "audio_passed_count": summary.get("audio_passed_count", 0),
            "missing_audio_count": summary.get("missing_audio_count", 0),
            "failed_audio_count": summary.get("failed_audio_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        },
        blocked_keys=BLOCKED_RELEASE_KEYS,
    )


def read_release_audio_qa(release_store: ReleaseStore, release_id: str, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    path = release_store.release_dir(release_id) / "release-audio-qa.json"
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError("Release Audio QA does not exist.")
    return sanitize_metadata(read_json(path), blocked_keys=BLOCKED_RELEASE_KEYS)


def write_release_audio_qa(release_store: ReleaseStore, release_id: str, report: dict[str, Any]) -> dict[str, Any]:
    release_store.get_release(release_id)
    clean = sanitize_metadata(report, blocked_keys=BLOCKED_RELEASE_KEYS)
    write_json(release_store.release_dir(release_id) / "release-audio-qa.json", clean)
    return clean


def _file_state(path: Path) -> ImplementationDocument:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {"exists": False}
    return {"exists": True, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _json_state(path: Path) -> ImplementationDocument:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {"exists": False}
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        payload = {}
    return {"exists": True, "sha256": _sha256(path), "payload_hash": stable_hash(payload) if isinstance(payload, dict) else None}


def _sha256(path: Path) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_stale_reasons(artifact: ImplementationDocument, *, wav_path: Path, midi_path: Path, song_plan_path: Path, project_store: ProjectStore) -> list[str]:
    renderer = artifact.get("renderer") if isinstance(artifact.get("renderer"), dict) else {}
    profile_id = str(renderer.get("profile_id") or "")
    profile = None
    if profile_id.startswith("arp-"):
        try:
            profile = AudioProfileStore(project_store.root.parent / "audio-profiles").get_profile(profile_id)
        except Exception:
            profile = None
    return audio_artifact_stale_reasons_for_profile(artifact, wav_path=wav_path, midi_path=midi_path, song_plan_path=song_plan_path, profile=profile)
