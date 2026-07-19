# ruff: noqa: E402,F401
from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document, as_list as _as_list

import hashlib as hashlib
import os as os
import re as re
import shutil as shutil
import threading as threading
import zipfile as zipfile
from dataclasses import dataclass as dataclass
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.project_quality import QualityGateResult as QualityGateResult
from song_agent.domains.studio.projectio import read_json as read_json, write_json as write_json
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.creation.stems import read_stem_manifest as read_stem_manifest, stem_audio_path as stem_audio_path, stem_manifest_stale as stem_manifest_stale, stem_midi_path as stem_midi_path


class FinalExportError(ValueError):
    pass


BLOCKED_ASSET_METADATA_KEYS = {
    "absolute_path",
    "access_token",
    "api_key",
    "authorization",
    "credential",
    "file",
    "local_path",
    "password",
    "path",
    "raw_provider_response",
    "secret",
    "token",
}


@dataclass
class FinalExportOptions:
    version_id: str | None = None
    include_audio: bool = True
    include_stems: bool = True
    include_stem_audio: bool = True
    include_asset_refs: bool = True
    include_reference_refs: bool = True
    force: bool = False

    @classmethod
    def from_dict(cls, data: DomainDocument) -> "FinalExportOptions":
        return cls(
            version_id=_optional_str(data.get("version_id")),
            include_audio=bool(data.get("include_audio", True)),
            include_stems=bool(data.get("include_stems", True)),
            include_stem_audio=bool(data.get("include_stem_audio", True)),
            include_asset_refs=bool(data.get("include_asset_refs", True)),
            include_reference_refs=bool(data.get("include_reference_refs", True)),
            force=bool(data.get("force", False)),
        )

    def to_dict(self) -> DomainDocument:
        return {
            "version_id": self.version_id,
            "include_audio": self.include_audio,
            "include_stems": self.include_stems,
            "include_stem_audio": self.include_stem_audio,
            "include_asset_refs": self.include_asset_refs,
            "include_reference_refs": self.include_reference_refs,
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
    project_export: DomainDocument | None = None,
) -> DomainDocument:
    if gate.status not in {"passed", "warning"} and not options.force:
        raise FinalExportError("Quality gate failed.")

    plan_path = run_dir / "data" / "song-plan.json"
    midi_path = run_dir / "renders" / "song.mid"
    _require_source(run_dir, plan_path, "data/song-plan.json")
    _require_source(run_dir, midi_path, "renders/song.mid")
    plan = _load_song_plan(plan_path)
    clear_final_export_zip(project_dir)
    export_dir = _prepare_export_dir(project_dir)

    files: list[ImplementationDocument] = []
    if project_export is not None:
        public_project_export = sanitize_metadata(
            project_export,
            blocked_keys=BLOCKED_ASSET_METADATA_KEYS,
        )
        write_json(export_dir / "project-export.json", public_project_export)
        files.append({"kind": "project_export", "path": "project-export.json", "exists": True, "required": False})

    _copy_optional(run_dir, export_dir, plan_path, "song-plan.json", "song_plan", files, required=True)
    _copy_optional(run_dir, export_dir, run_dir / "data" / "run-summary.json", "run-summary.json", "run_summary", files)
    _copy_optional(run_dir, export_dir, run_dir / "data" / "validator-report.json", "validator-report.json", "validator_report", files)
    _write_quality_report(export_dir, gate, files, plan=plan)
    _copy_optional(run_dir, export_dir, midi_path, "song.mid", "midi", files, required=True)
    if options.include_audio:
        _copy_optional(run_dir, export_dir, run_dir / "renders" / "song.wav", "song.wav", "audio", files)
        _copy_optional(run_dir, export_dir, run_dir / "renders" / "audio-artifact.json", "audio-artifact.json", "audio_artifact", files)
    else:
        files.append({"kind": "audio", "path": "song.wav", "exists": False, "required": False, "skipped": "disabled"})
        files.append({"kind": "audio_artifact", "path": "audio-artifact.json", "exists": False, "required": False, "skipped": "disabled"})
    if options.include_stems:
        _copy_stems(run_dir, export_dir, options, files, plan=plan)
    else:
        files.append({"kind": "stem_manifest", "path": "stems/manifest.json", "exists": False, "required": False, "skipped": "disabled"})
    mix_summary = _copy_mix_exports(run_dir, export_dir, files)
    asset_refs = _write_asset_ref_summaries(
        run_dir=run_dir,
        export_dir=export_dir,
        version_id=version.version_id,
        project_export=project_export,
        files=files,
        enabled=options.include_asset_refs,
    )
    reference_refs = _write_reference_ref_summaries(
        run_dir=run_dir,
        export_dir=export_dir,
        version_id=version.version_id,
        project_export=project_export,
        files=files,
        enabled=options.include_reference_refs,
    )
    context_pack = _final_version_context_pack(run_dir, version.version_id, project_export)
    edit_metadata = _final_version_edit_metadata(run_dir, version.version_id, project_export)
    review_sprint_summary = _final_review_sprint_summary(project_export)
    review_sprint_recommendations = _final_review_sprint_recommendations(project_export)
    review_sprint_action_queues = _final_review_sprint_action_queues(project_export)
    review_metrics = _final_review_metrics(project_export)
    review_judge = _final_review_judge(project_export, edit_metadata)
    review_sprint_closeout = _final_review_sprint_closeout(project_export)
    acceptance_fix_sprint = _final_acceptance_fix_sprint(project_export)
    acceptance_fix_plan = _final_acceptance_fix_plan(project_export)
    acceptance_fix_plan_review = _final_acceptance_fix_plan_review(project_export)
    acceptance_kb = _final_acceptance_kb(project_export)
    planning_rule_simulation = _final_planning_rule_simulation(project_export)
    planning_rule_governance = _final_planning_rule_governance(project_export)
    planning_rule_impact = _final_planning_rule_impact(project_export)
    delivery_qa = _final_delivery_qa(project_export)
    delivery_signoff = _final_delivery_signoff(project_export)

    manifest = {
        "project_id": project.project_id,
        "project_name": project.name,
        "version_id": version.version_id,
        "version_name": version.name,
        "job_id": version.job_id,
        "generated_at": now,
        "options": options.to_dict(),
        "quality_gate": gate.to_dict(),
        "asset_refs": asset_refs,
        "reference_refs": reference_refs,
        "context_pack": context_pack,
        "edit": edit_metadata,
        "review_sprint_summary": review_sprint_summary,
        "review_sprint_recommendations": review_sprint_recommendations,
        "review_sprint_action_queues": review_sprint_action_queues,
        "review_metrics": review_metrics,
        "review_judge": review_judge,
        "review_sprint_closeout": review_sprint_closeout,
        "acceptance_fix_sprint": acceptance_fix_sprint,
        "acceptance_fix_plan": acceptance_fix_plan,
        "acceptance_fix_plan_review": acceptance_fix_plan_review,
        "acceptance_kb": acceptance_kb,
        "planning_rule_simulation": planning_rule_simulation,
        "planning_rule_governance": planning_rule_governance,
        "planning_rule_impact": planning_rule_impact,
        "delivery_qa": delivery_qa,
        "delivery_signoff": delivery_signoff,
        "mix": mix_summary,
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


def read_final_export_manifest(project_dir: Path) -> DomainDocument:
    path = project_dir / "final-export" / "manifest.json"
    if not path.exists():
        raise FileNotFoundError("Final export has not been generated.")
    return read_json(path)


def final_export_dir(project_dir: Path) -> Path:
    return project_dir / "final-export"


def final_export_zip_path(project_dir: Path) -> Path:
    return project_dir / "final-export.zip"


def clear_final_export_zip(project_dir: Path) -> None:
    project_dir = project_dir.resolve()
    zip_path = final_export_zip_path(project_dir)
    if zip_path.is_symlink():
        raise FinalExportError("Refusing to remove a symlinked final export ZIP.")
    _ensure_within(project_dir, zip_path)
    if not zip_path.exists():
        return
    zip_path.unlink()


def build_final_export_zip(project_dir: Path, *, now: str) -> DomainDocument:
    project_dir = project_dir.resolve()
    export_dir = final_export_dir(project_dir).resolve()
    _ensure_within(project_dir, export_dir)
    if not export_dir.exists() or not export_dir.is_dir():
        raise FileNotFoundError("Final export has not been generated.")
    zip_path = final_export_zip_path(project_dir)
    _ensure_within(project_dir, zip_path)
    tmp_path = zip_path.with_name(f".{zip_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    entries: list[str] = []
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(export_dir.rglob("*")):
                if not file.is_file() or file.is_symlink():
                    continue
                resolved = file.resolve()
                _ensure_within(export_dir, resolved)
                entry = _safe_zip_entry(resolved.relative_to(export_dir).as_posix())
                archive.write(resolved, entry)
                entries.append(entry)
        tmp_path.replace(zip_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    zip_info = {
        "created_at": now,
        "filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "sha256": _sha256(zip_path),
        "entry_count": len(entries),
        "entries": entries,
    }
    manifest = read_final_export_manifest(project_dir)
    manifest["zip"] = zip_info
    write_json(export_dir / "manifest.json", manifest)
    return zip_info


def _copy_optional(
    run_dir: Path,
    export_dir: Path,
    source: Path,
    relative_target: str,
    kind: str,
    files: list[ImplementationDocument],
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
    files: list[ImplementationDocument],
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
    _copy_optional(run_dir, export_dir, run_dir / "stems" / "stem-health.json", "stems/stem-health.json", "stem_health", files)
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


def _copy_mix_exports(run_dir: Path, export_dir: Path, files: list[ImplementationDocument]) -> ImplementationDocument:
    from song_agent.domains.quality.mix_controls import mix_patch_hash, mix_patch_integrity_ok, mix_state_hash, mix_state_integrity_ok
    from song_agent.domains.creation.stem_health import read_stem_health_report, stem_health_integrity_ok, stem_health_summary

    summary: ImplementationDocument = {}
    state_path = run_dir / "data" / "mix-state.json"
    patch_path = run_dir / "data" / "mix-patch.json"
    if state_path.exists():
        _copy_optional(run_dir, export_dir, state_path, "mix-state.json", "mix_state", files)
        try:
            state = read_json(state_path)
            summary["mix_state_hash"] = mix_state_hash(state) if mix_state_integrity_ok(state) else None
            summary["mix_state_integrity_ok"] = mix_state_integrity_ok(state)
        except (OSError, ValueError, TypeError):
            summary["mix_state_integrity_ok"] = False
    else:
        files.append({"kind": "mix_state", "path": "mix-state.json", "exists": False, "required": False})
    if patch_path.exists():
        _copy_optional(run_dir, export_dir, patch_path, "mix-patch.json", "mix_patch", files)
        try:
            patch = read_json(patch_path)
            summary["mix_patch_hash"] = mix_patch_hash(patch) if mix_patch_integrity_ok(patch) else None
            summary["mix_patch_integrity_ok"] = mix_patch_integrity_ok(patch)
            summary["patch_id"] = patch.get("patch_id")
        except (OSError, ValueError, TypeError):
            summary["mix_patch_integrity_ok"] = False
    else:
        files.append({"kind": "mix_patch", "path": "mix-patch.json", "exists": False, "required": False})
    try:
        report = read_stem_health_report(run_dir, default={})
    except (OSError, ValueError, TypeError):
        report = {}
    if report:
        summary["stem_health"] = stem_health_summary(report)
        summary["stem_health_integrity_ok"] = stem_health_integrity_ok(report)
    return _drop_empty(_sanitize_asset_metadata(summary))


def _write_quality_report(
    export_dir: Path,
    gate: QualityGateResult,
    files: list[ImplementationDocument],
    *,
    plan: SongPlan | None,
) -> None:
    quality = plan.quality.to_dict() if plan is not None and plan.quality is not None else None
    write_json(export_dir / "quality-report.json", {"quality_gate": gate.to_dict(), "quality": quality})
    files.append({"kind": "quality_report", "path": "quality-report.json", "exists": True, "required": False})


def _write_asset_ref_summaries(
    *,
    run_dir: Path,
    export_dir: Path,
    version_id: str,
    project_export: ImplementationDocument | None,
    files: list[ImplementationDocument],
    enabled: bool,
) -> list[ImplementationDocument]:
    if not enabled:
        files.append({"kind": "asset_refs", "path": "assets", "exists": False, "required": False, "skipped": "disabled"})
        return []
    refs = _final_version_asset_refs(run_dir, version_id, project_export)
    if not refs:
        files.append({"kind": "asset_refs", "path": "assets", "exists": False, "required": False})
        return []
    assets_dir = export_dir / "assets"
    _ensure_within(export_dir, assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)
    written: list[ImplementationDocument] = []
    for ref in refs:
        asset_id = _safe_asset_id(str(ref.get("asset_id") or ""))
        summary = _asset_ref_export_summary(ref)
        target = assets_dir / f"{asset_id}.json"
        _ensure_within(export_dir, target)
        write_json(target, summary)
        record = {"kind": "asset_ref", "path": f"assets/{asset_id}.json", "exists": True, "required": False, "size_bytes": target.stat().st_size}
        files.append(record)
        written.append(summary)
    return written


def _final_version_asset_refs(run_dir: Path, version_id: str, project_export: ImplementationDocument | None) -> list[ImplementationDocument]:
    refs_by_id: dict[str, ImplementationDocument] = {}
    snapshot_path = run_dir / "data" / "asset-refs.json"
    if snapshot_path.exists():
        _ensure_within(run_dir, snapshot_path)
        try:
            snapshot = read_json(snapshot_path)
        except (OSError, ValueError, TypeError):
            snapshot = {}
        for ref in snapshot.get("asset_refs", []) if isinstance(snapshot, dict) else []:
            if isinstance(ref, dict) and ref.get("asset_id"):
                refs_by_id[str(ref["asset_id"])] = _asset_ref_export_summary({**ref, "used_by_versions": [version_id]})
    if isinstance(project_export, dict):
        for ref in project_export.get("asset_refs", []):
            if not isinstance(ref, dict) or not ref.get("asset_id"):
                continue
            used_by_versions = _as_list(ref.get("used_by_versions"))
            if version_id not in used_by_versions:
                continue
            asset_id = str(ref["asset_id"])
            refs_by_id.setdefault(asset_id, _asset_ref_export_summary(ref))
    return [refs_by_id[key] for key in sorted(refs_by_id)]


from song_agent.domains.creation import v142_fe_readiness as _v142_fe_readiness
from song_agent.domains.creation.v142_fe_readiness import (
    _write_reference_ref_summaries,
    _final_version_reference_refs,
    _final_version_context_pack,
    _final_version_edit_metadata,
    _edit_metadata_export_summary,
    _final_review_sprint_summary,
    _final_review_sprint_recommendations,
    _final_review_sprint_action_queues,
    _final_review_metrics,
    _final_review_judge,
    _final_review_sprint_closeout,
    _final_delivery_qa,
    _final_acceptance_fix_sprint,
    _final_acceptance_fix_plan,
    _final_acceptance_fix_plan_review,
    _final_acceptance_kb,
    _final_planning_rule_simulation,
    _final_planning_rule_governance,
    _final_planning_rule_impact,
)
from song_agent.domains.creation import v142_fe_evidence as _v142_fe_evidence
from song_agent.domains.creation.v142_fe_evidence import (
    _final_delivery_signoff,
    _context_pack_export_summary,
    _reference_ref_export_summary,
    _asset_ref_export_summary,
    _drop_empty,
    _safe_asset_id,
    _safe_reference_id,
    _sanitize_asset_metadata,
    _write_readme,
    _prepare_export_dir,
    _load_song_plan,
    _relative_to_run_dir,
    _unsafe_stem_path_records,
    _skipped_stem_record,
    _ensure_within,
    _safe_zip_entry,
    _sha256,
    _optional_str,
)

_v142_fe_readiness.bind_globals(globals())
_v142_fe_evidence.bind_globals(globals())
