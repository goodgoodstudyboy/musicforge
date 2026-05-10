from __future__ import annotations

from collections import Counter
from typing import Any

from song_agent.schemas.song import SongPlan
from song_agent.song_editor import EditorPatch, EditorPatchResult, build_editor_state


EDITOR_VIEW_SCHEMA_VERSION = 1
DEFAULT_PITCH_MIN = 36
DEFAULT_PITCH_MAX = 84


def build_editor_view(plan: SongPlan, *, note_identity: dict[str, dict[str, dict[str, Any]]] | None = None) -> dict[str, Any]:
    state = build_editor_state(plan)
    sections = [dict(section) for section in state["sections"]]
    tracks = []
    lanes = []
    pitches: list[int] = []
    for track in state["tracks"]:
        notes = []
        identity_notes = _identity_notes_for_track(note_identity, str(track["track_id"]))
        source_notes = identity_notes if identity_notes is not None else list(track.get("notes", []))
        for note in source_notes:
            section_id = _section_id_for_beat(float(note["start_beat"]), sections)
            end_beat = round(float(note["start_beat"]) + float(note["duration_beats"]), 6)
            view_note = {
                "note_id": note["note_id"],
                "pitch": int(note["pitch"]),
                "start_beat": float(note["start_beat"]),
                "end_beat": end_beat,
                "duration_beats": float(note["duration_beats"]),
                "velocity": int(note["velocity"]),
                "section_id": section_id,
            }
            notes.append(view_note)
            pitches.append(view_note["pitch"])
        tracks.append({key: value for key, value in track.items() if key != "notes"})
        lanes.append({"track_id": track["track_id"], "notes": notes})
    pitch_range = _pitch_range(pitches)
    return {
        "ok": True,
        "schema_version": EDITOR_VIEW_SCHEMA_VERSION,
        "base_plan_hash": state["base_plan_hash"],
        "song": {
            **state["song"],
            "total_beats": state["song"]["total_bars"] * state["song"]["beats_per_bar"],
        },
        "sections": sections,
        "tracks": tracks,
        "lanes": lanes,
        "pitch_range": pitch_range,
        "warnings": list(state.get("warnings") or []),
    }


def build_editor_view_from_result(result: EditorPatchResult) -> dict[str, Any]:
    return build_editor_view(result.plan, note_identity=result.summary.get("note_identity") or None)


def build_editor_diff(parent: SongPlan, edited: SongPlan, patch: EditorPatch) -> dict[str, Any]:
    parent_state = build_editor_state(parent)
    edited_state = build_editor_state(edited)
    parent_sections = parent_state["sections"]
    edited_sections = edited_state["sections"]
    parent_tracks = parent_state["tracks"]
    edited_tracks = edited_state["tracks"]
    parent_section_names = [section["name"] for section in parent_sections]
    edited_section_names = [section["name"] for section in edited_sections]
    parent_track_names = [track["name"] for track in parent_tracks]
    edited_track_names = [track["name"] for track in edited_tracks]
    parent_note_count = sum(int(track["note_count"]) for track in parent_tracks)
    edited_note_count = sum(int(track["note_count"]) for track in edited_tracks)
    operation_counts = Counter(str(operation.get("op") or "") for operation in patch.operations)
    return {
        "sections": {
            "added": [name for name in edited_section_names if name not in parent_section_names],
            "removed": [name for name in parent_section_names if name not in edited_section_names],
            "changed": _changed_section_names(parent.sections, edited.sections),
            "moved": _moved_names(parent_section_names, edited_section_names),
        },
        "tracks": {
            "added": [name for name in edited_track_names if name not in parent_track_names],
            "removed": [name for name in parent_track_names if name not in edited_track_names],
            "renamed": _rename_count(operation_counts),
            "changed": _changed_track_names(parent.tracks, edited.tracks),
        },
        "notes": {
            "added": max(0, edited_note_count - parent_note_count),
            "removed": max(0, parent_note_count - edited_note_count),
            "changed": sum(operation_counts[op] for op in {"update_note", "transpose_notes", "quantize_notes", "scale_velocity"}),
            "moved": operation_counts["move_notes"],
        },
        "operation_counts": dict(operation_counts),
        "warnings": [],
    }


def _section_id_for_beat(start_beat: float, sections: list[dict[str, Any]]) -> str | None:
    for section in sections:
        if float(section["start_beat"]) <= start_beat < float(section["end_beat"]):
            return str(section["section_id"])
    return sections[-1]["section_id"] if sections else None


def _identity_notes_for_track(note_identity: dict[str, dict[str, dict[str, Any]]] | None, track_id: str) -> list[dict[str, Any]] | None:
    if not note_identity or track_id not in note_identity:
        return None
    notes = []
    for note_id, note in note_identity[track_id].items():
        notes.append(
            {
                "note_id": note_id,
                "pitch": int(note["pitch"]),
                "start_beat": float(note["start_beat"]),
                "duration_beats": float(note["duration_beats"]),
                "velocity": int(note["velocity"]),
            }
        )
    return sorted(notes, key=lambda item: (item["start_beat"], item["pitch"], item["note_id"]))


def _pitch_range(pitches: list[int]) -> dict[str, int]:
    if not pitches:
        return {"min": DEFAULT_PITCH_MIN, "max": DEFAULT_PITCH_MAX}
    return {"min": max(0, min(DEFAULT_PITCH_MIN, min(pitches))), "max": min(127, max(DEFAULT_PITCH_MAX, max(pitches)))}


def _changed_section_names(parent: list[Any], edited: list[Any]) -> list[str]:
    changed = []
    edited_by_name = {section.name: section for section in edited}
    for section in parent:
        other = edited_by_name.get(section.name)
        if other and section.to_dict() != other.to_dict():
            changed.append(section.name)
    return changed


def _changed_track_names(parent: list[Any], edited: list[Any]) -> list[str]:
    changed = []
    edited_by_name = {track.name: track for track in edited}
    for track in parent:
        other = edited_by_name.get(track.name)
        if other and track.to_dict() != other.to_dict():
            changed.append(track.name)
    return changed


def _moved_names(parent_names: list[str], edited_names: list[str]) -> list[str]:
    moved = []
    for name in parent_names:
        if name in edited_names and parent_names.index(name) != edited_names.index(name):
            moved.append(name)
    return moved


def _rename_count(operation_counts: Counter[str]) -> int:
    return int(operation_counts.get("rename_track", 0))
