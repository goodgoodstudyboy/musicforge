from __future__ import annotations

from song_agent.platform.contracts import DomainDocument, ImplementationDocument, as_document as _as_document

import json as json
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.studio.project_quality import QualityGateConfig as QualityGateConfig, evaluate_quality_gate as evaluate_quality_gate
from song_agent.domains.studio.projectio import read_json as read_json
from song_agent.domains.studio.project_repository import ProjectDocument as ProjectDocument, ProjectVersion as ProjectVersion
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan


def compare_project_versions(document: ProjectDocument, left_id: str, right_id: str) -> DomainDocument:
    if not str(left_id or "").strip() or not str(right_id or "").strip():
        raise ValueError("left and right version ids are required.")
    left = _find_version(document, left_id)
    right = _find_version(document, right_id)
    left_plan = _read_plan(left)
    right_plan = _read_plan(right)
    left_view = _version_view(document.state.project_id, left, left_plan)
    right_view = _version_view(document.state.project_id, right, right_plan)
    sections = _compare_sections(left_plan, right_plan)
    tracks = _compare_tracks(left_plan, right_plan)
    quality_delta = _quality_delta(left_view, right_view)
    return {
        "project_id": document.state.project_id,
        "left": left_view,
        "right": right_view,
        "summary": {
            "quality_delta": quality_delta,
            "section_changes": sum(1 for item in sections if item["changed"]),
            "track_changes": sum(1 for item in tracks if item["changed"]),
            "recommendation": _recommend(left_view, right_view),
        },
        "sections": sections,
        "tracks": tracks,
        "artifacts": {
            "left": _artifact_links(left),
            "right": _artifact_links(right),
        },
    }


def _version_view(project_id: str, version: ProjectVersion, plan: SongPlan | None) -> ImplementationDocument:
    return {
        "project_id": project_id,
        "version_id": version.version_id,
        "name": version.name,
        "job_id": version.job_id,
        "status": version.status,
        "parent_version_id": version.parent_version_id,
        "variant_type": version.variant_type,
        "change_summary": version.change_summary,
        "quality": _quality_view(version, plan),
        "gate": _gate_view(version),
        "midi_available": version.has_midi,
        "audio_available": version.has_audio,
        "stems_available": version.has_stems,
        "stem_audio_available": version.has_stem_audio,
        "edit": _edit_view(version),
    }


def _quality_view(version: ProjectVersion, plan: SongPlan | None) -> ImplementationDocument:
    if plan is not None and plan.quality is not None and plan.quality.scores is not None:
        return {
            "overall": plan.quality.scores.overall,
            "dimension_scores": plan.quality.scores.to_dict(),
            "warnings": list(plan.quality.warnings),
        }
    return {
        "overall": version.quality_score,
        "dimension_scores": {},
        "warnings": [],
    }


def _gate_view(version: ProjectVersion) -> ImplementationDocument:
    return {
        "status": version.quality_gate_status,
        "score": version.quality_gate_score,
        "warnings": list(version.quality_gate_warnings),
    }


def _edit_view(version: ProjectVersion) -> ImplementationDocument | None:
    path = Path(version.output_dir) / "data" / "edit-metadata.json"
    if not path.exists():
        return None
    try:
        metadata = read_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    preset = metadata.get("preset") if isinstance(metadata.get("preset"), dict) else None
    return {
        "schema_version": metadata.get("schema_version"),
        "edit_source": metadata.get("edit_source"),
        "edit_type": metadata.get("edit_type"),
        "target": metadata.get("target") or {},
        "instruction": metadata.get("instruction") or "",
        "preserve": metadata.get("preserve") or [],
        "strength": metadata.get("strength"),
        "provider_mode": metadata.get("provider_mode") or "local",
        "provider": _as_document(metadata.get("provider")),
        "template_id": metadata.get("template_id"),
        "preview_id": metadata.get("preview_id"),
        "operation_count": metadata.get("operation_count"),
        "changed_sections": metadata.get("changed_sections") or [],
        "changed_tracks": metadata.get("changed_tracks") or [],
        "clip_inserts": metadata.get("clip_inserts") or [],
        "template_inserts": metadata.get("template_inserts") or [],
        "audition_summary": _as_document(metadata.get("audition_summary")),
        "review_edit": _as_document(metadata.get("review_edit")),
        "review_summary": _as_document(metadata.get("review_summary")),
        "review_task": _as_document(metadata.get("review_task")),
        "review_candidate": _as_document(metadata.get("review_candidate")),
        "review_candidate_source": _as_document(metadata.get("review_candidate_source")),
        "review_provider_patch": _provider_patch_view(metadata.get("review_provider_patch") or metadata.get("provider_patch")),
        "review_decision": _as_document(metadata.get("review_decision")),
        "review_judge": _as_document(metadata.get("review_judge")),
        "review_sprint": _as_document(metadata.get("review_sprint")),
        "review_sprint_recommendation": _as_document(metadata.get("review_sprint_recommendation")),
        "review_sprint_action_queue": _as_document(metadata.get("review_sprint_action_queue")),
        "provider_patch": _provider_patch_view(metadata.get("provider_patch")),
        "preset": preset,
        "preset_id": preset.get("preset_id") if preset else None,
        "summary": metadata.get("summary") or {},
        "structure": metadata.get("structure") or {},
        "warnings": metadata.get("warnings") or [],
    }


def _compare_sections(left: SongPlan | None, right: SongPlan | None) -> list[ImplementationDocument]:
    left_sections = {section.name: section for section in left.sections} if left else {}
    right_sections = {section.name: section for section in right.sections} if right else {}
    rows = []
    for name in sorted(set(left_sections) | set(right_sections)):
        left_section = left_sections.get(name)
        right_section = right_sections.get(name)
        left_data = _section_data(left_section)
        right_data = _section_data(right_section)
        rows.append({"section": name, "left": left_data, "right": right_data, "changed": left_data != right_data})
    return rows


def _compare_tracks(left: SongPlan | None, right: SongPlan | None) -> list[ImplementationDocument]:
    left_tracks = {track.name: track for track in left.tracks} if left else {}
    right_tracks = {track.name: track for track in right.tracks} if right else {}
    rows = []
    for name in sorted(set(left_tracks) | set(right_tracks)):
        left_track = left_tracks.get(name)
        right_track = right_tracks.get(name)
        left_data = _track_data(left_track, left)
        right_data = _track_data(right_track, right)
        rows.append({"track": name, "left": left_data, "right": right_data, "changed": left_data != right_data})
    return rows


def _section_data(section: Any) -> ImplementationDocument | None:
    if section is None:
        return None
    return {
        "bars": section.bars,
        "start_bar": section.start_bar,
        "chords": list(section.chords),
        "lyrics": _short_text(section.lyrics),
    }


def _track_data(track: Any, plan: SongPlan | None) -> ImplementationDocument | None:
    if track is None:
        return None
    song_beats = _song_beats(plan)
    return {
        "instrument": track.instrument,
        "note_count": len(track.notes),
        "density": round(len(track.notes) / song_beats, 3) if song_beats else 0,
        "average_velocity": _average_velocity(track),
    }


def _artifact_links(version: ProjectVersion) -> ImplementationDocument:
    return {
        "job_id": version.job_id,
        "midi": f"/api/jobs/{version.job_id}/midi" if version.has_midi else None,
        "audio": f"/api/jobs/{version.job_id}/audio" if version.has_audio else None,
        "stems": version.has_stems,
        "final_export": version.final_export_path,
    }


def _recommend(left: ImplementationDocument, right: ImplementationDocument) -> str:
    left_gate = left["gate"]["status"]
    right_gate = right["gate"]["status"]
    passing = {"passed", "warning"}
    if left_gate in passing and right_gate not in passing:
        return "left"
    if right_gate in passing and left_gate not in passing:
        return "right"
    left_score = left["quality"].get("overall")
    right_score = right["quality"].get("overall")
    if left_score is None or right_score is None:
        return "unknown"
    if abs(int(right_score) - int(left_score)) < 2:
        return "tie"
    return "right" if int(right_score) > int(left_score) else "left"


def _quality_delta(left: ImplementationDocument, right: ImplementationDocument) -> int | None:
    left_score = left["quality"].get("overall")
    right_score = right["quality"].get("overall")
    if left_score is None or right_score is None:
        return None
    return int(right_score) - int(left_score)


def _find_version(document: ProjectDocument, version_id: str) -> ProjectVersion:
    for version in document.versions:
        if version.version_id == version_id:
            return version
    raise FileNotFoundError(version_id)


def _read_plan(version: ProjectVersion) -> SongPlan | None:
    path = Path(version.output_dir) / "data" / "song-plan.json"
    if not path.exists():
        return None
    try:
        return SongPlan.from_dict(read_json(path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _song_beats(plan: SongPlan | None) -> float:
    if plan is None or not plan.sections:
        return 0.0
    return max((section.start_bar - 1 + section.bars) * 4 for section in plan.sections)


def _average_velocity(track: Any) -> float:
    if not track.notes:
        return 0.0
    return round(sum(note.velocity for note in track.notes) / len(track.notes), 2)


def _short_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:120] + ("..." if len(text) > 120 else "")


def _provider_patch_view(value: Any) -> ImplementationDocument | None:
    if not isinstance(value, dict):
        return None
    operations = value.get("operations")
    return {
        "summary": value.get("summary") or "",
        "operation_count": len(operations) if isinstance(operations, list) else 0,
        "confidence": value.get("confidence"),
    }
