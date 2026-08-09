from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document

import json as json
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.quality.audio_health import analyze_wav_health as analyze_wav_health, audio_health_allows_release as audio_health_allows_release, audio_health_integrity_ok as audio_health_integrity_ok, audio_health_summary as audio_health_summary
from song_agent.domains.quality.mix_controls import file_sha256 as file_sha256, mix_state_hash as mix_state_hash, mix_state_integrity_ok as mix_state_integrity_ok, song_plan_hash as song_plan_hash, stable_hash as stable_hash
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.creation.stems import read_stem_manifest as read_stem_manifest, stem_audio_path as stem_audio_path, stem_midi_path as stem_midi_path


STEM_HEALTH_SCHEMA_VERSION = 1
STEM_HEALTH_INTEGRITY_EXCLUDE_KEYS = {"integrity_hash", "stale", "current_source_hash", "stale_reasons"}


class StemHealthError(ValueError):
    pass


def build_stem_health_report(
    *,
    run_dir: Path,
    project_id: str,
    version_id: str,
    mix_state: dict[str, Any] | None = None,
    require_wav: bool = False,
    now: str,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    plan_path = run_dir / "data" / "song-plan.json"
    if not plan_path.exists():
        raise StemHealthError("song-plan.json is missing.")
    plan = SongPlan.from_dict(read_json(plan_path))
    manifest = read_stem_manifest(run_dir)
    if manifest is None:
        raise StemHealthError("Stem manifest is missing. Render stems first.")
    blockers: list[str] = []
    warnings: list[str] = []
    stems: list[dict[str, Any]] = []
    for stem in manifest.stems:
        stem_blockers: list[str] = []
        stem_warnings: list[str] = []
        midi_exists = False
        midi_sha256 = ""
        wav_exists = False
        wav_sha256 = ""
        health: dict[str, Any] = {}
        try:
            midi_file = stem_midi_path(run_dir, manifest, stem.stem_id)
            midi_exists = midi_file.exists() and midi_file.is_file() and not midi_file.is_symlink()
            midi_sha256 = file_sha256(midi_file)
        except Exception:
            midi_exists = False
        if stem.note_count and not midi_exists:
            stem_blockers.append("stem_midi_missing")
        try:
            wav_file = stem_audio_path(run_dir, manifest, stem.stem_id)
            wav_exists = wav_file.exists() and wav_file.is_file() and not wav_file.is_symlink()
            if wav_exists:
                health = analyze_wav_health(
                    wav_file,
                    source={"project_id": project_id, "version_id": version_id, "stem_id": stem.stem_id, "track_id": stem.stem_id},
                    report_id=f"shr-{project_id}-{version_id}-{stem.stem_id}",
                    now=now,
                )
                wav_sha256 = str(health.get("wav_sha256") or file_sha256(wav_file))
        except Exception as exc:
            stem_blockers.append("stem_wav_invalid")
            stem_warnings.append(str(exc)[:160])
        if require_wav and stem.note_count and not wav_exists:
            stem_blockers.append("stem_wav_missing")
        if wav_exists and (not audio_health_integrity_ok(health) or not audio_health_allows_release(health)):
            stem_blockers.append("stem_audio_health_failed")
        status = "failed" if stem_blockers else "warning" if stem_warnings else "passed"
        blockers.extend(f"{stem.stem_id}: {item}" for item in stem_blockers)
        warnings.extend(f"{stem.stem_id}: {item}" for item in stem_warnings)
        stems.append(
            sanitize_metadata(
                {
                    "stem_id": stem.stem_id,
                    "track_id": stem.stem_id,
                    "track_name": stem.track_name,
                    "role": stem.role,
                    "note_count": stem.note_count,
                    "midi_path": stem.midi_path,
                    "midi_exists": midi_exists,
                    "midi_sha256": midi_sha256,
                    "wav_path": stem.audio_path,
                    "wav_exists": wav_exists,
                    "wav_sha256": wav_sha256,
                    "audio_status": "missing" if not wav_exists else str(health.get("status") or "unknown"),
                    "audio_health": audio_health_summary(health) if health else {},
                    "status": status,
                    "blockers": stem_blockers,
                    "warnings": stem_warnings,
                }
            )
        )
    source = stem_health_source_state(run_dir=run_dir, project_id=project_id, version_id=version_id, plan=plan, mix_state=mix_state)
    status = "failed" if blockers else "warning" if warnings else "passed"
    report = {
        "schema_version": STEM_HEALTH_SCHEMA_VERSION,
        "project_id": project_id,
        "version_id": version_id,
        "status": status,
        "generated_at": now,
        "require_wav": require_wav,
        "source": source,
        "source_hash": stable_hash(source),
        "summary": {
            "stem_count": len(stems),
            "passed_count": sum(1 for item in stems if item.get("status") == "passed"),
            "failed_count": sum(1 for item in stems if item.get("status") == "failed"),
            "wav_present_count": sum(1 for item in stems if item.get("wav_exists")),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
            "mix_state_hash": source.get("mix_state_hash"),
        },
        "stems": stems,
        "blockers": blockers,
        "warnings": warnings,
    }
    report["integrity_hash"] = stem_health_integrity_hash(report)
    return sanitize_metadata(report)


def write_stem_health_report(run_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    clean = sanitize_metadata(report)
    write_json(stem_health_path(run_dir), clean)
    return clean


def read_stem_health_report(run_dir: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    path = stem_health_path(run_dir)
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError("Stem health report is missing.")
    return sanitize_metadata(read_json(path))


def stem_health_path(run_dir: Path) -> Path:
    return run_dir / "stems" / "stem-health.json"


def stem_health_source_state(*, run_dir: Path, project_id: str, version_id: str, plan: SongPlan, mix_state: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = read_stem_manifest(run_dir)
    midi_path = run_dir / "renders" / "song.mid"
    if not midi_path.exists():
        midi_path = run_dir / "song.mid"
    stem_files: list[dict[str, Any]] = []
    if manifest is not None:
        for stem in manifest.stems:
            try:
                midi_path = stem_midi_path(run_dir, manifest, stem.stem_id)
            except Exception:
                midi_path = run_dir / stem.midi_path
            try:
                audio_path = stem_audio_path(run_dir, manifest, stem.stem_id)
            except Exception:
                audio_path = run_dir / stem.audio_path
            stem_files.append(
                {
                    "stem_id": stem.stem_id,
                    "note_count": stem.note_count,
                    "midi": _file_state(midi_path),
                    "wav": _file_state(audio_path),
                }
            )
    return {
        "project_id": project_id,
        "version_id": version_id,
        "song_plan_hash": song_plan_hash(plan),
        "midi_sha256": file_sha256(midi_path),
        "mix_state_hash": mix_state_hash(mix_state) if isinstance(mix_state, dict) and mix_state_integrity_ok(mix_state) else None,
        "stem_manifest_hash": stable_hash(manifest.to_dict()) if manifest is not None else None,
        "stem_files": stem_files,
    }


def stem_health_integrity_hash(report: dict[str, Any]) -> str:
    return stable_hash({key: value for key, value in report.items() if key not in STEM_HEALTH_INTEGRITY_EXCLUDE_KEYS})


def stem_health_integrity_ok(report: dict[str, Any]) -> bool:
    expected = str(report.get("integrity_hash") or "")
    return bool(expected) and expected == stem_health_integrity_hash(report)


def stem_health_stale_reasons(report: dict[str, Any], *, run_dir: Path, project_id: str, version_id: str, mix_state: dict[str, Any] | None = None) -> list[str]:
    reasons = []
    if not stem_health_integrity_ok(report):
        reasons.append("stem_health_integrity")
    plan_path = run_dir / "data" / "song-plan.json"
    if not plan_path.exists():
        return [*reasons, "song_plan_missing"]
    plan = SongPlan.from_dict(read_json(plan_path))
    current_source = stem_health_source_state(run_dir=run_dir, project_id=project_id, version_id=version_id, plan=plan, mix_state=mix_state)
    if report.get("source_hash") != stable_hash(current_source):
        reasons.append("source_hash")
    return reasons


def stem_health_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "source_hash": data.get("source_hash"),
            "integrity_hash": data.get("integrity_hash"),
            "stem_count": summary.get("stem_count", 0),
            "passed_count": summary.get("passed_count", 0),
            "failed_count": summary.get("failed_count", 0),
            "wav_present_count": summary.get("wav_present_count", 0),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "mix_state_hash": summary.get("mix_state_hash"),
        }
    )


def stem_health_allows_signoff(report: dict[str, Any], *, current_source_hash: str | None = None) -> bool:
    if not report or not stem_health_integrity_ok(report):
        return False
    if current_source_hash is not None and report.get("source_hash") != current_source_hash:
        return False
    return str(report.get("status") or "") in {"passed", "warning"}


def _file_state(path: Path) -> ImplementationDocument:
    if not path.exists() or not path.is_file() or path.is_symlink():
        return {"exists": False}
    return {"exists": True, "sha256": file_sha256(path), "size_bytes": path.stat().st_size}
