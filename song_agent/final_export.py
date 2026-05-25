from __future__ import annotations

import hashlib
import os
import re
import shutil
import threading
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from song_agent.project_quality import QualityGateResult
from song_agent.projectio import read_json, write_json
from song_agent.redaction import sanitize_metadata
from song_agent.schemas.song import SongPlan
from song_agent.stems import read_stem_manifest, stem_audio_path, stem_manifest_stale, stem_midi_path


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
    def from_dict(cls, data: dict[str, Any]) -> "FinalExportOptions":
        return cls(
            version_id=_optional_str(data.get("version_id")),
            include_audio=bool(data.get("include_audio", True)),
            include_stems=bool(data.get("include_stems", True)),
            include_stem_audio=bool(data.get("include_stem_audio", True)),
            include_asset_refs=bool(data.get("include_asset_refs", True)),
            include_reference_refs=bool(data.get("include_reference_refs", True)),
            force=bool(data.get("force", False)),
        )

    def to_dict(self) -> dict[str, Any]:
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
    project_export: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if gate.status not in {"passed", "warning"} and not options.force:
        raise FinalExportError("Quality gate failed.")

    plan_path = run_dir / "data" / "song-plan.json"
    midi_path = run_dir / "renders" / "song.mid"
    _require_source(run_dir, plan_path, "data/song-plan.json")
    _require_source(run_dir, midi_path, "renders/song.mid")
    plan = _load_song_plan(plan_path)
    clear_final_export_zip(project_dir)
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
        _copy_optional(run_dir, export_dir, run_dir / "renders" / "audio-artifact.json", "audio-artifact.json", "audio_artifact", files)
    else:
        files.append({"kind": "audio", "path": "song.wav", "exists": False, "required": False, "skipped": "disabled"})
        files.append({"kind": "audio_artifact", "path": "audio-artifact.json", "exists": False, "required": False, "skipped": "disabled"})
    if options.include_stems:
        _copy_stems(run_dir, export_dir, options, files, plan=plan)
    else:
        files.append({"kind": "stem_manifest", "path": "stems/manifest.json", "exists": False, "required": False, "skipped": "disabled"})
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


def final_export_zip_path(project_dir: Path) -> Path:
    return project_dir / "final-export.zip"


def clear_final_export_zip(project_dir: Path) -> None:
    project_dir = project_dir.resolve()
    zip_path = final_export_zip_path(project_dir).resolve()
    _ensure_within(project_dir, zip_path)
    if not zip_path.exists():
        return
    if zip_path.is_symlink():
        raise FinalExportError("Refusing to remove a symlinked final export ZIP.")
    zip_path.unlink()


def build_final_export_zip(project_dir: Path, *, now: str) -> dict[str, Any]:
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


def _write_asset_ref_summaries(
    *,
    run_dir: Path,
    export_dir: Path,
    version_id: str,
    project_export: dict[str, Any] | None,
    files: list[dict[str, Any]],
    enabled: bool,
) -> list[dict[str, Any]]:
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
    written: list[dict[str, Any]] = []
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


def _final_version_asset_refs(run_dir: Path, version_id: str, project_export: dict[str, Any] | None) -> list[dict[str, Any]]:
    refs_by_id: dict[str, dict[str, Any]] = {}
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
            used_by_versions = ref.get("used_by_versions") if isinstance(ref.get("used_by_versions"), list) else []
            if version_id not in used_by_versions:
                continue
            asset_id = str(ref["asset_id"])
            refs_by_id.setdefault(asset_id, _asset_ref_export_summary(ref))
    return [refs_by_id[key] for key in sorted(refs_by_id)]


def _write_reference_ref_summaries(
    *,
    run_dir: Path,
    export_dir: Path,
    version_id: str,
    project_export: dict[str, Any] | None,
    files: list[dict[str, Any]],
    enabled: bool,
) -> list[dict[str, Any]]:
    if not enabled:
        files.append({"kind": "reference_refs", "path": "references", "exists": False, "required": False, "skipped": "disabled"})
        return []
    refs = _final_version_reference_refs(run_dir, version_id, project_export)
    if not refs:
        files.append({"kind": "reference_refs", "path": "references", "exists": False, "required": False})
        return []
    refs_dir = export_dir / "references"
    _ensure_within(export_dir, refs_dir)
    refs_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    for ref in refs:
        reference_id = _safe_reference_id(str(ref.get("reference_id") or ""))
        summary = _reference_ref_export_summary(ref)
        target = refs_dir / f"{reference_id}.json"
        _ensure_within(export_dir, target)
        write_json(target, summary)
        record = {"kind": "reference_ref", "path": f"references/{reference_id}.json", "exists": True, "required": False, "size_bytes": target.stat().st_size}
        files.append(record)
        written.append(summary)
    return written


def _final_version_reference_refs(run_dir: Path, version_id: str, project_export: dict[str, Any] | None) -> list[dict[str, Any]]:
    refs_by_id: dict[str, dict[str, Any]] = {}
    snapshot_path = run_dir / "data" / "reference-refs.json"
    if snapshot_path.exists():
        _ensure_within(run_dir, snapshot_path)
        try:
            snapshot = read_json(snapshot_path)
        except (OSError, ValueError, TypeError):
            snapshot = {}
        for ref in snapshot.get("reference_refs", []) if isinstance(snapshot, dict) else []:
            if isinstance(ref, dict) and ref.get("reference_id"):
                refs_by_id[str(ref["reference_id"])] = _reference_ref_export_summary({**ref, "used_by_versions": [version_id]})
    if isinstance(project_export, dict):
        for ref in project_export.get("reference_refs", []):
            if not isinstance(ref, dict) or not ref.get("reference_id"):
                continue
            used_by_versions = ref.get("used_by_versions") if isinstance(ref.get("used_by_versions"), list) else []
            if version_id not in used_by_versions and not ref.get("linked_to_project"):
                continue
            reference_id = str(ref["reference_id"])
            refs_by_id.setdefault(reference_id, _reference_ref_export_summary(ref))
    return [refs_by_id[key] for key in sorted(refs_by_id)]


def _final_version_context_pack(run_dir: Path, version_id: str, project_export: dict[str, Any] | None) -> dict[str, Any]:
    snapshot_path = run_dir / "data" / "context-pack.json"
    if snapshot_path.exists():
        _ensure_within(run_dir, snapshot_path)
        try:
            snapshot = read_json(snapshot_path)
        except (OSError, ValueError, TypeError):
            snapshot = {}
        if isinstance(snapshot, dict) and snapshot.get("pack_id"):
            return _context_pack_export_summary({**snapshot, "used_by_versions": [version_id]})
    if isinstance(project_export, dict):
        for pack in project_export.get("context_packs", []):
            if not isinstance(pack, dict) or not pack.get("pack_id"):
                continue
            used_by_versions = pack.get("used_by_versions") if isinstance(pack.get("used_by_versions"), list) else []
            if version_id in used_by_versions:
                return _context_pack_export_summary(pack)
    return {}


def _final_version_edit_metadata(run_dir: Path, version_id: str, project_export: dict[str, Any] | None) -> dict[str, Any]:
    path = run_dir / "data" / "edit-metadata.json"
    if path.exists():
        try:
            return _edit_metadata_export_summary(read_json(path))
        except (OSError, ValueError, TypeError):
            pass
    if isinstance(project_export, dict):
        for version in project_export.get("versions", []):
            if isinstance(version, dict) and version.get("version_id") == version_id and isinstance(version.get("edit"), dict):
                return _edit_metadata_export_summary(version["edit"])
    return {}


def _edit_metadata_export_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "edit_source": metadata.get("edit_source"),
        "edit_type": metadata.get("edit_type"),
        "preview_id": metadata.get("preview_id"),
        "operation_count": metadata.get("operation_count"),
        "changed_sections": metadata.get("changed_sections") or [],
        "changed_tracks": metadata.get("changed_tracks") or [],
        "clip_inserts": metadata.get("clip_inserts") or [],
        "template_inserts": metadata.get("template_inserts") or [],
        "audition_summary": metadata.get("audition_summary") if isinstance(metadata.get("audition_summary"), dict) else {},
        "review_edit": metadata.get("review_edit") if isinstance(metadata.get("review_edit"), dict) else {},
        "review_summary": metadata.get("review_summary") if isinstance(metadata.get("review_summary"), dict) else {},
        "review_task": metadata.get("review_task") if isinstance(metadata.get("review_task"), dict) else {},
        "review_candidate": metadata.get("review_candidate") if isinstance(metadata.get("review_candidate"), dict) else {},
        "review_candidate_source": metadata.get("review_candidate_source") if isinstance(metadata.get("review_candidate_source"), dict) else {},
        "review_provider_patch": metadata.get("review_provider_patch") if isinstance(metadata.get("review_provider_patch"), dict) else {},
        "review_decision": metadata.get("review_decision") if isinstance(metadata.get("review_decision"), dict) else {},
        "review_sprint": metadata.get("review_sprint") if isinstance(metadata.get("review_sprint"), dict) else {},
        "review_sprint_recommendation": metadata.get("review_sprint_recommendation") if isinstance(metadata.get("review_sprint_recommendation"), dict) else {},
        "review_sprint_action_queue": metadata.get("review_sprint_action_queue") if isinstance(metadata.get("review_sprint_action_queue"), dict) else {},
        "review_judge": metadata.get("review_judge") if isinstance(metadata.get("review_judge"), dict) else {},
        "summary": metadata.get("summary") if isinstance(metadata.get("summary"), dict) else {},
        "structure": metadata.get("structure") if isinstance(metadata.get("structure"), dict) else {},
        "warnings": metadata.get("warnings") or [],
    }
    return _drop_empty(_sanitize_asset_metadata(summary))


def _final_review_sprint_summary(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict):
        return {}
    try:
        from song_agent.review_sprints import review_sprint_project_rollup

        sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
        if not sprints:
            return {}
        return _drop_empty(_sanitize_asset_metadata(review_sprint_project_rollup(sprints)))
    except (OSError, ValueError, TypeError):
        return {}


def _final_review_sprint_recommendations(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict):
        return {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    summaries = [sprint.get("recommendation_summary", {}) for sprint in sprints if isinstance(sprint.get("recommendation_summary"), dict)]
    if not summaries:
        return {}
    latest = summaries[0]
    summary = {
        "latest_sprint_id": sprints[0].get("sprint_id") if sprints else None,
        "next_action": latest.get("next_action"),
        "ready_to_close": bool(latest.get("ready_to_close", False)),
        "open_recommendation_count": sum(int(item.get("open_recommendation_count") or 0) for item in summaries),
        "context_recommendation_count": sum(int(item.get("context_recommendation_count") or 0) for item in summaries),
        "top_recommendation": latest.get("top_recommendation") if isinstance(latest.get("top_recommendation"), dict) else {},
    }
    return _drop_empty(_sanitize_asset_metadata(summary))


def _final_review_sprint_action_queues(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict):
        return {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    summaries = [sprint.get("action_queue_summary", {}) for sprint in sprints if isinstance(sprint.get("action_queue_summary"), dict)]
    if not summaries:
        return {}
    latest = summaries[0]
    summary = {
        "latest_sprint_id": sprints[0].get("sprint_id") if sprints else None,
        "latest_queue_id": latest.get("latest_queue_id"),
        "queue_count": sum(int(item.get("queue_count") or 0) for item in summaries),
        "completed_action_count": sum(int(item.get("completed_action_count") or 0) for item in summaries),
        "manual_required_count": sum(int(item.get("manual_required_count") or 0) for item in summaries),
        "failed_action_count": sum(int(item.get("failed_action_count") or 0) for item in summaries),
        "latest_status": latest.get("latest_status"),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))


def _final_review_metrics(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict):
        return {}
    project_summary = project_export.get("review_metrics_summary") if isinstance(project_export.get("review_metrics_summary"), dict) else {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    sprint_summaries = []
    for sprint in sprints:
        metrics_summary = sprint.get("metrics_summary", {})
        if not isinstance(metrics_summary, dict):
            continue
        if not metrics_summary.get("sprint_id") and sprint.get("sprint_id"):
            metrics_summary = {**metrics_summary, "sprint_id": sprint.get("sprint_id")}
        sprint_summaries.append(metrics_summary)
    latest_sprint_id = str(project_summary.get("latest_sprint_id") or "")
    latest = next((summary for summary in sprint_summaries if str(summary.get("sprint_id") or "") == latest_sprint_id), None) if latest_sprint_id else None
    if latest is None:
        latest = sprint_summaries[0] if sprint_summaries else {}
    summary = {
        "latest_readiness": project_summary.get("latest_readiness") or latest.get("readiness"),
        "latest_sprint_id": latest_sprint_id or latest.get("sprint_id"),
        "sprint_count": project_summary.get("sprint_count") or len(sprints),
        "active_sprint_count": project_summary.get("active_sprint_count"),
        "completion_rate": latest.get("completion_rate"),
        "quality_delta": latest.get("quality_delta"),
        "provider_tokens": project_summary.get("total_provider_tokens") if project_summary else latest.get("provider_tokens"),
        "total_candidate_count": project_summary.get("total_candidate_count"),
        "total_applied_candidate_count": project_summary.get("total_applied_candidate_count"),
        "warnings": latest.get("warnings") if isinstance(latest.get("warnings"), list) else [],
    }
    return _drop_empty(_sanitize_asset_metadata(summary))


def _final_review_judge(project_export: dict[str, Any] | None, edit_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    edit_judge = edit_metadata.get("review_judge") if isinstance(edit_metadata, dict) and isinstance(edit_metadata.get("review_judge"), dict) else {}
    project_summary = project_export.get("review_metrics_summary") if isinstance(project_export, dict) and isinstance(project_export.get("review_metrics_summary"), dict) else {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)] if isinstance(project_export, dict) else []
    judge_summaries = []
    for sprint in sprints:
        judge_summary = sprint.get("judge_summary", {})
        if not isinstance(judge_summary, dict):
            continue
        if not judge_summary.get("sprint_id") and sprint.get("sprint_id"):
            judge_summary = {**judge_summary, "sprint_id": sprint.get("sprint_id")}
        judge_summaries.append(judge_summary)
    latest_sprint_id = str(project_summary.get("latest_sprint_id") or "")
    latest = next((summary for summary in judge_summaries if str(summary.get("sprint_id") or "") == latest_sprint_id), None) if latest_sprint_id else None
    if latest is None:
        latest = judge_summaries[0] if judge_summaries else {}
    summary = {
        "latest_sprint_id": latest_sprint_id or latest.get("sprint_id"),
        "judged_task_count": sum(int(item.get("judged_task_count") or 0) for item in judge_summaries),
        "stale_judge_count": sum(int(item.get("stale_judge_count") or 0) for item in judge_summaries),
        "judge_provider_tokens": sum(int(item.get("judge_provider_tokens") or 0) for item in judge_summaries),
        "high_risk_candidate_count": sum(int(item.get("high_risk_candidate_count") or 0) for item in judge_summaries),
        "applied_matches_judge": edit_judge.get("applied_matches_judge"),
        "manual_review_required": True if judge_summaries or edit_judge else None,
        "judge_recommended_candidate_id": edit_judge.get("judge_recommended_candidate_id"),
        "top_overall": edit_judge.get("top_overall"),
        "confidence": edit_judge.get("confidence"),
        "judge_stale_at_apply": edit_judge.get("judge_stale_at_apply"),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))


def _final_review_sprint_closeout(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict):
        return {}
    project_summary = project_export.get("review_metrics_summary") if isinstance(project_export.get("review_metrics_summary"), dict) else {}
    sprints = [sprint for sprint in project_export.get("review_sprints", []) if isinstance(sprint, dict)]
    if not sprints:
        return {}
    latest_sprint_id = str(project_summary.get("latest_sprint_id") or "")
    latest_sprint = next((sprint for sprint in sprints if str(sprint.get("sprint_id") or "") == latest_sprint_id), None) if latest_sprint_id else None
    if latest_sprint is None:
        latest_sprint = sprints[0]
        latest_sprint_id = str(latest_sprint.get("sprint_id") or "")
    closeout_summaries = [sprint.get("closeout_summary", {}) for sprint in sprints if isinstance(sprint.get("closeout_summary"), dict)]
    signoff_summaries = [sprint.get("signoff_summary", {}) for sprint in sprints if isinstance(sprint.get("signoff_summary"), dict)]
    latest_closeout = latest_sprint.get("closeout_summary") if isinstance(latest_sprint.get("closeout_summary"), dict) else {}
    latest_signoff = latest_sprint.get("signoff_summary") if isinstance(latest_sprint.get("signoff_summary"), dict) else {}
    summary = {
        "latest_sprint_id": latest_sprint_id or None,
        "closed_sprint_count": len([sprint for sprint in sprints if sprint.get("status") == "closed"]),
        "signed_sprint_count": len([item for item in signoff_summaries if item.get("status") == "signed"]),
        "forced_close_count": len([item for item in signoff_summaries if item.get("forced")]) or len([item for item in closeout_summaries if item.get("forced")]),
        "latest_closeout_status": latest_closeout.get("status"),
        "latest_closeout_readiness": latest_closeout.get("readiness"),
        "blocker_count": latest_closeout.get("blocker_count"),
        "warning_count": latest_closeout.get("warning_count"),
        "selected_version_id": latest_signoff.get("selected_version_id") or latest_closeout.get("recommended_final_version_id"),
    }
    return _drop_empty(_sanitize_asset_metadata(summary))


def _final_delivery_qa(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("delivery_qa_summary"), dict):
        return {}
    summary = project_export["delivery_qa_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "readiness": summary.get("readiness"),
                "handoff_allowed": summary.get("handoff_allowed"),
                "artifact_count": summary.get("artifact_count"),
                "blocker_count": summary.get("blocker_count"),
                "warning_count": summary.get("warning_count"),
                "final_version_id": summary.get("final_version_id"),
                "zip_sha256": summary.get("zip_sha256"),
                "zip_matches_manifest": summary.get("zip_matches_manifest"),
            }
        )
    )


def _final_acceptance_fix_sprint(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_fix_sprint_summary"), dict):
        return {}
    summary = project_export["acceptance_fix_sprint_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "fix_sprint_id": summary.get("fix_sprint_id"),
                "item_count": summary.get("item_count"),
                "open_item_count": summary.get("open_item_count"),
                "linked_review_task_count": summary.get("linked_review_task_count"),
                "completed_review_task_count": summary.get("completed_review_task_count"),
                "recheck_suite_id": summary.get("recheck_suite_id"),
                "delta_status": summary.get("delta_status"),
                "closeout_status": summary.get("closeout_status"),
            }
        )
    )


def _final_acceptance_fix_plan(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_fix_plan_summary"), dict):
        return {}
    summary = project_export["acceptance_fix_plan_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "plan_id": summary.get("plan_id"),
                "planned_item_count": summary.get("planned_item_count"),
                "high_priority_count": summary.get("high_priority_count"),
                "kb_match_count": summary.get("kb_match_count"),
                "risk_warning_count": summary.get("risk_warning_count"),
                "created_fix_sprint_id": summary.get("created_fix_sprint_id"),
                "stale": summary.get("stale"),
            }
        )
    )


def _final_acceptance_fix_plan_review(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_fix_plan_review_summary"), dict):
        return {}
    summary = project_export["acceptance_fix_plan_review_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "readiness": summary.get("readiness"),
                "review_id": summary.get("review_id"),
                "plan_id": summary.get("plan_id"),
                "fix_sprint_id": summary.get("fix_sprint_id"),
                "plan_effectiveness_score": summary.get("plan_effectiveness_score"),
                "ranking_alignment_score": summary.get("ranking_alignment_score"),
                "kb_evidence_helpfulness": summary.get("kb_evidence_helpfulness"),
                "stale": summary.get("stale"),
            }
        )
    )


def _final_acceptance_kb(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("acceptance_kb_summary"), dict):
        return {}
    summary = project_export["acceptance_kb_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "report_id": summary.get("report_id"),
                "entry_count": summary.get("entry_count"),
                "effective_count": summary.get("effective_count"),
                "ineffective_count": summary.get("ineffective_count"),
                "average_effectiveness_score": summary.get("average_effectiveness_score"),
                "top_recurring_issues": summary.get("top_recurring_issues") if isinstance(summary.get("top_recurring_issues"), list) else [],
                "warning_count": summary.get("warning_count"),
                "stale": summary.get("stale"),
            }
        )
    )


def _final_planning_rule_simulation(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("planning_rule_simulation_summary"), dict):
        return {}
    summary = project_export["planning_rule_simulation_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "simulation_id": summary.get("simulation_id"),
                "ruleset_id": summary.get("ruleset_id"),
                "review_count": summary.get("review_count"),
                "item_count": summary.get("item_count"),
                "alignment_delta": summary.get("alignment_delta"),
                "recommendation": summary.get("recommendation"),
                "stale": summary.get("stale"),
            }
        )
    )


def _final_planning_rule_governance(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("planning_rule_governance_summary"), dict):
        return {}
    summary = project_export["planning_rule_governance_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "active_version_id": summary.get("active_version_id"),
                "ruleset_id": summary.get("ruleset_id"),
                "promotion_id": summary.get("promotion_id"),
                "simulation_id": summary.get("simulation_id"),
                "recommendation": summary.get("recommendation"),
                "alignment_delta": summary.get("alignment_delta"),
                "stale": summary.get("stale"),
                "evidence_stale": summary.get("evidence_stale"),
            }
        )
    )


def _final_planning_rule_impact(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("planning_rule_impact_summary"), dict):
        return {}
    summary = project_export["planning_rule_impact_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "report_id": summary.get("report_id"),
                "active_version_id": summary.get("active_version_id"),
                "observed_plan_count": summary.get("observed_plan_count"),
                "observed_review_count": summary.get("observed_review_count"),
                "manual_review_count": summary.get("manual_review_count"),
                "synthetic_review_count": summary.get("synthetic_review_count"),
                "effectiveness_delta": summary.get("effectiveness_delta"),
                "ranking_alignment_delta": summary.get("ranking_alignment_delta"),
                "recommendation": summary.get("recommendation"),
                "rollback_recommended": summary.get("rollback_recommended"),
                "stale": summary.get("stale"),
            }
        )
    )


def _final_delivery_signoff(project_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(project_export, dict) or not isinstance(project_export.get("delivery_signoff_summary"), dict):
        return {}
    summary = project_export["delivery_signoff_summary"]
    return _drop_empty(
        _sanitize_asset_metadata(
            {
                "status": summary.get("status"),
                "signed_at": summary.get("signed_at"),
                "signed_by": summary.get("signed_by"),
                "forced": summary.get("forced"),
                "delivery_qa_status": summary.get("delivery_qa_status"),
                "final_version_id": summary.get("final_version_id"),
                "zip_sha256": summary.get("zip_sha256"),
            }
        )
    )


def _context_pack_export_summary(pack: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "pack_id": str(pack.get("pack_id") or ""),
        "name": str(pack.get("name") or pack.get("pack_id") or ""),
        "asset_count": len(pack.get("asset_refs") or []) if isinstance(pack.get("asset_refs"), list) else int(pack.get("asset_count") or 0),
        "reference_count": len(pack.get("reference_refs") or []) if isinstance(pack.get("reference_refs"), list) else int(pack.get("reference_count") or 0),
        "created_from": _sanitize_asset_metadata(pack.get("created_from")) if isinstance(pack.get("created_from"), dict) else {},
        "query": _sanitize_asset_metadata(pack.get("query")) if isinstance(pack.get("query"), dict) else {},
        "used_by_versions": [str(item) for item in pack.get("used_by_versions", []) if str(item).strip()] if isinstance(pack.get("used_by_versions"), list) else [],
    }
    return _drop_empty(_sanitize_asset_metadata(summary))


def _reference_ref_export_summary(ref: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "reference_id": _safe_reference_id(str(ref.get("reference_id") or "")),
        "reference_type": str(ref.get("reference_type") or ""),
        "title": str(ref.get("title") or ref.get("reference_id") or ""),
        "roles": [str(item) for item in ref.get("roles", []) if str(item).strip()] if isinstance(ref.get("roles"), list) else [],
        "role": str(ref.get("role") or "") if ref.get("role") else None,
        "strength": ref.get("strength") if isinstance(ref.get("strength"), (int, float)) else None,
        "used_by_versions": [str(item) for item in ref.get("used_by_versions", []) if str(item).strip()] if isinstance(ref.get("used_by_versions"), list) else [],
        "used_by_candidate_groups": [str(item) for item in ref.get("used_by_candidate_groups", []) if str(item).strip()] if isinstance(ref.get("used_by_candidate_groups"), list) else [],
        "linked_to_project": True if ref.get("linked_to_project") else None,
        "metadata_summary": _sanitize_asset_metadata(ref.get("metadata_summary")) if isinstance(ref.get("metadata_summary"), dict) else {},
        "analysis_summary": _sanitize_asset_metadata(ref.get("analysis_summary")) if isinstance(ref.get("analysis_summary"), dict) else {},
    }
    return _drop_empty(summary)


def _asset_ref_export_summary(ref: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "asset_id": _safe_asset_id(str(ref.get("asset_id") or "")),
        "asset_type": str(ref.get("asset_type") or ""),
        "name": str(ref.get("name") or ref.get("asset_id") or ""),
        "roles": [str(item) for item in ref.get("roles", []) if str(item).strip()] if isinstance(ref.get("roles"), list) else [],
        "role": str(ref.get("role") or "") if ref.get("role") else None,
        "strength": ref.get("strength") if isinstance(ref.get("strength"), (int, float)) else None,
        "used_by_versions": [str(item) for item in ref.get("used_by_versions", []) if str(item).strip()] if isinstance(ref.get("used_by_versions"), list) else [],
        "used_by_candidate_groups": [str(item) for item in ref.get("used_by_candidate_groups", []) if str(item).strip()] if isinstance(ref.get("used_by_candidate_groups"), list) else [],
        "content_summary": _sanitize_asset_metadata(ref.get("content_summary")) if isinstance(ref.get("content_summary"), dict) else {},
        "source": _sanitize_asset_metadata(ref.get("source")) if isinstance(ref.get("source"), dict) else {},
    }
    return _drop_empty(summary)


def _drop_empty(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


def _safe_asset_id(asset_id: str) -> str:
    if not re.match(r"^asset-[0-9]{3,6}$", asset_id):
        raise FinalExportError("Invalid asset id in asset refs.")
    return asset_id


def _safe_reference_id(reference_id: str) -> str:
    if not re.match(r"^ref-[0-9]{3,6}$", reference_id):
        raise FinalExportError("Invalid reference id in reference refs.")
    return reference_id


def _sanitize_asset_metadata(value: Any) -> Any:
    return sanitize_metadata(value, blocked_keys=BLOCKED_ASSET_METADATA_KEYS)


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


def _safe_zip_entry(entry: str) -> str:
    normalized = entry.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if (
        not normalized
        or normalized.startswith("/")
        or normalized.startswith("\\")
        or ".." in parts
        or any(part == "." for part in parts)
        or (parts and ":" in parts[0])
    ):
        raise FinalExportError(f"Unsafe ZIP entry: {entry}.")
    return "/".join(parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_str(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()
