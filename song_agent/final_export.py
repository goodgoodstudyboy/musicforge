from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from song_agent.project_quality import QualityGateResult
from song_agent.projectio import read_json, write_json
from song_agent.schemas.song import SongPlan
from song_agent.stems import read_stem_manifest, stem_audio_path, stem_manifest_stale, stem_midi_path


class FinalExportError(ValueError):
    pass


@dataclass
class FinalExportOptions:
    version_id: str | None = None
    include_audio: bool = True
    include_stems: bool = True
    include_stem_audio: bool = True
    force: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FinalExportOptions":
        return cls(
            version_id=_optional_str(data.get("version_id")),
            include_audio=bool(data.get("include_audio", True)),
            include_stems=bool(data.get("include_stems", True)),
            include_stem_audio=bool(data.get("include_stem_audio", True)),
            force=bool(data.get("force", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "include_audio": self.include_audio,
            "include_stems": self.include_stems,
            "include_stem_audio": self.include_stem_audio,
            "force": self.force,
        }


def build_final_export_bundle(
    *,
    project: Any,
    version: Any,
    project_dir: Path,
    run_dir: Path,
    gate: QualityGateResult,
    options: FinalExportOptions,
    now: str,
    project_export: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if gate.status not in {"passed", "warning"} and not options.force:
        raise FinalExportError("Quality gate failed.")

    plan_path = run_dir / "data" / "song-plan.json"
    midi_path = run_dir / "renders" / "song.mid"
    _require_source(run_dir, plan_path, "data/song-plan.json")
    _require_source(run_dir, midi_path, "renders/song.mid")
    plan = _load_song_plan(plan_path)
    export_dir = _prepare_export_dir(project_dir)

    files: list[dict[str, Any]] = []
    if project_export is not None:
        write_json(export_dir / "project-export.json", project_export)
        files.append({"kind": "project_export", "path": "project-export.json", "exists": True, "required": False})

    _copy_optional(run_dir, export_dir, plan_path, "song-plan.json", "song_plan", files, required=True)
    _copy_optional(run_dir, export_dir, run_dir / "data" / "run-summary.json", "run-summary.json", "run_summary", files)
    _copy_optional(run_dir, export_dir, run_dir / "data" / "validator-report.json", "validator-report.json", "validator_report", files)
    _write_quality_report(export_dir, gate, files, plan=plan)
    _copy_optional(run_dir, export_dir, midi_path, "song.mid", "midi", files, required=True)
    if options.include_audio:
        _copy_optional(run_dir, export_dir, run_dir / "renders" / "song.wav", "song.wav", "audio", files)
    else:
        files.append({"kind": "audio", "path": "song.wav", "exists": False, "required": False, "skipped": "disabled"})
    if options.include_stems:
        _copy_stems(run_dir, export_dir, options, files, plan=plan)
    else:
        files.append({"kind": "stem_manifest", "path": "stems/manifest.json", "exists": False, "required": False, "skipped": "disabled"})

    manifest = {
        "project_id": project.project_id,
        "project_name": project.name,
        "version_id": version.version_id,
        "version_name": version.name,
        "job_id": version.job_id,
        "generated_at": now,
        "options": options.to_dict(),
        "quality_gate": gate.to_dict(),
        "files": files,
        "source": {
            "job_id": version.job_id,
            "run_dir": run_dir.name,
            "song_plan": "data/song-plan.json",
        },
    }
    write_json(export_dir / "manifest.json", manifest)
    _write_readme(export_dir, project, version, gate, manifest)
    return manifest


def read_final_export_manifest(project_dir: Path) -> dict[str, Any]:
    path = project_dir / "final-export" / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Final export has not been generated.")
    return read_json(path)


def final_export_dir(project_dir: Path) -> Path:
    return project_dir / "final-export"


def _copy_optional(
    run_dir: Path,
    export_dir: Path,
    source: Path,
    relative_target: str,
    kind: str,
    files: list[dict[str, Any]],
    *,
    required: bool = False,
) -> None:
    record = {"kind": kind, "path": relative_target, "exists": source.exists(), "required": required}
    _ensure_within(run_dir, source)
    if source.exists():
        target = export_dir / relative_target
        _ensure_within(export_dir, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        record["size_bytes"] = target.stat().st_size
    elif required:
        files.append(record)
        raise FinalExportError(f"Required export file is missing: {source.relative_to(run_dir).as_posix()}.")
    files.append(record)


def _require_source(run_dir: Path, source: Path, label: str) -> None:
    _ensure_within(run_dir, source)
    if not source.exists():
        raise FinalExportError(f"Required export file is missing: {label}.")


def _copy_stems(
    run_dir: Path,
    export_dir: Path,
    options: FinalExportOptions,
    files: list[dict[str, Any]],
    *,
    plan: SongPlan | None,
) -> None:
    manifest = read_stem_manifest(run_dir)
    if manifest is None or plan is None:
        files.append({"kind": "stem_manifest", "path": "stems/manifest.json", "exists": False, "required": False})
        return
    if stem_manifest_stale(manifest, plan):
        files.append({"kind": "stem_manifest", "path": "stems/manifest.json", "exists": False, "required": False, "skipped": "stale"})
        return
    unsafe_records = _unsafe_stem_path_records(run_dir, manifest, options)
    if unsafe_records:
        files.append({"kind": "stem_manifest", "path": "stems/manifest.json", "exists": False, "required": False, "skipped": "unsafe_path"})
        files.extend(unsafe_records)
        return

    _copy_optional(run_dir, export_dir, run_dir / "stems" / "manifest.json", "stems/manifest.json", "stem_manifest", files)
    for stem in manifest.stems:
        try:
            midi_source = stem_midi_path(run_dir, manifest, stem.stem_id)
            midi_target = _relative_to_run_dir(run_dir, midi_source)
        except (FileNotFoundError, ValueError) as exc:
            files.append(_skipped_stem_record("stem_midi", stem.midi_path, exc))
            if options.include_stem_audio:
                files.append(_skipped_stem_record("stem_audio", stem.audio_path, exc))
            continue
        _copy_optional(run_dir, export_dir, midi_source, midi_target, "stem_midi", files)
        if options.include_stem_audio:
            try:
                audio_source = stem_audio_path(run_dir, manifest, stem.stem_id)
                audio_target = _relative_to_run_dir(run_dir, audio_source)
            except (FileNotFoundError, ValueError) as exc:
                files.append(_skipped_stem_record("stem_audio", stem.audio_path, exc))
                continue
            _copy_optional(run_dir, export_dir, audio_source, audio_target, "stem_audio", files)
        else:
            files.append({"kind": "stem_audio", "path": stem.audio_path, "exists": False, "required": False, "skipped": "disabled"})


def _write_quality_report(
    export_dir: Path,
    gate: QualityGateResult,
    files: list[dict[str, Any]],
    *,
    plan: SongPlan | None,
) -> None:
    quality = plan.quality.to_dict() if plan is not None and plan.quality is not None else None
    write_json(export_dir / "quality-report.json", {"quality_gate": gate.to_dict(), "quality": quality})
    files.append({"kind": "quality_report", "path": "quality-report.json", "exists": True, "required": False})


def _write_readme(export_dir: Path, project: Any, version: Any, gate: QualityGateResult, manifest: dict[str, Any]) -> None:
    lines = [
        "MusicForge Final Export",
        "",
        f"Project: {project.name}",
        f"Version: {version.version_id} {version.name}",
        f"Job: {version.job_id}",
        f"Generated: {manifest['generated_at']}",
        f"Quality Overall: {gate.score if gate.score is not None else '-'}",
        f"Quality Gate: {gate.status}",
        "",
        "Files:",
    ]
    lines.extend(f"- {file['path']}" for file in manifest["files"] if file.get("exists"))
    if version.note:
        lines.extend(["", "Notes:", version.note])
    (export_dir / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prepare_export_dir(project_dir: Path) -> Path:
    project_dir = project_dir.resolve()
    export_dir = (project_dir / "final-export").resolve()
    _ensure_within(project_dir, export_dir)
    if export_dir == project_dir:
        raise FinalExportError("Refusing to replace the project directory.")
    if export_dir.exists():
        if export_dir.is_symlink():
            raise FinalExportError("Refusing to replace a symlinked final export directory.")
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _load_song_plan(plan_path: Path) -> SongPlan | None:
    if not plan_path.exists():
        return None
    try:
        return SongPlan.from_dict(read_json(plan_path))
    except (OSError, TypeError, ValueError):
        return None


def _relative_to_run_dir(run_dir: Path, source: Path) -> str:
    try:
        return source.resolve().relative_to(run_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("Refusing to copy a source outside the job run directory.") from exc


def _unsafe_stem_path_records(run_dir: Path, manifest: Any, options: FinalExportOptions) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for stem in manifest.stems:
        try:
            stem_midi_path(run_dir, manifest, stem.stem_id)
        except (FileNotFoundError, ValueError) as exc:
            records.append(_skipped_stem_record("stem_midi", stem.midi_path, exc))
        if options.include_stem_audio:
            try:
                stem_audio_path(run_dir, manifest, stem.stem_id)
            except (FileNotFoundError, ValueError) as exc:
                records.append(_skipped_stem_record("stem_audio", stem.audio_path, exc))
    return records


def _skipped_stem_record(kind: str, path: str, exc: Exception) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path,
        "exists": False,
        "required": False,
        "skipped": "unsafe_path",
        "error": str(exc),
    }


def _ensure_within(base: Path, target: Path) -> None:
    base = base.resolve()
    target = target.resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Refusing to operate outside the expected directory.") from exc


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()
