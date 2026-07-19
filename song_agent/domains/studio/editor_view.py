from __future__ import annotations

from song_agent.platform.contracts.documents import ImplementationDocument

from collections import Counter as Counter
from typing import Any as Any

from song_agent.domains.creation.schemas.song import SongPlan as SongPlan
from song_agent.domains.studio.song_editor import EditorPatch as EditorPatch, EditorPatchResult as EditorPatchResult, build_editor_state as build_editor_state


EDITOR_VIEW_SCHEMA_VERSION = 1
DEFAULT_PITCH_MIN = 36
DEFAULT_PITCH_MAX = 84


def build_editor_view(
    plan: SongPlan,
    *,
    section_identity: dict[str, str | None] | None = None,
    track_identity: dict[str, str | None] | None = None,
    note_identity: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    state = build_editor_state(plan)
    sections = _stable_sections(state["sections"], section_identity)
    tracks = []
    lanes = []
    pitches: list[int] = []
    stable_tracks = _stable_tracks(state["tracks"], track_identity)
    for track in stable_tracks:
        notes = []
        source_notes = _view_notes_for_track(
            list(track.get("notes", [])),
            note_identity,
            str(track["track_id"]),
            track_derived=bool(track.get("derived", False)),
        )
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
                "editable": bool(note.get("editable", True)),
                "derived": bool(note.get("derived", False)),
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
    return build_editor_view(
        result.plan,
        section_identity=result.summary.get("section_identity") or None,
        track_identity=result.summary.get("track_identity") or None,
        note_identity=result.summary.get("note_identity") or None,
    )


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


def _section_id_for_beat(start_beat: float, sections: list[ImplementationDocument]) -> str | None:
    for section in sections:
        if float(section["start_beat"]) <= start_beat < float(section["end_beat"]):
            return str(section["section_id"])
    return sections[-1]["section_id"] if sections else None


def _stable_sections(sections: list[ImplementationDocument], section_identity: dict[str, str | None] | None) -> list[ImplementationDocument]:
    if not section_identity:
        return [dict(section, editable=True, derived=False) for section in sections]
    id_by_name = {name: section_id for section_id, name in section_identity.items() if name is not None}
    stable = []
    derived_index = 1
    for section in sections:
        name = str(section.get("name") or "")
        section_id = id_by_name.get(name)
        if section_id:
            stable.append({**section, "section_id": section_id, "editable": True, "derived": False})
        else:
            stable.append({**section, "section_id": f"derived-section-{derived_index:03d}", "editable": False, "derived": True})
            derived_index += 1
    return stable


def _stable_tracks(tracks: list[ImplementationDocument], track_identity: dict[str, str | None] | None) -> list[ImplementationDocument]:
    if not track_identity:
        return [dict(track, editable=True, derived=False) for track in tracks]
    id_by_name = {name: track_id for track_id, name in track_identity.items() if name is not None}
    stable = []
    derived_index = 1
    for track in tracks:
        name = str(track.get("name") or "")
        track_id = id_by_name.get(name)
        if track_id:
            stable.append({**track, "track_id": track_id, "editable": True, "derived": False})
        else:
            stable.append({**track, "track_id": f"derived-track-{derived_index:03d}", "editable": False, "derived": True, "notes": list(track.get("notes", []))})
            derived_index += 1
    return stable


def _view_notes_for_track(
    source_notes: list[ImplementationDocument],
    note_identity: dict[str, dict[str, ImplementationDocument]] | None,
    track_id: str,
    *,
    track_derived: bool,
) -> list[ImplementationDocument]:
    if track_derived:
        return [_derived_note(track_id, index, note) for index, note in enumerate(source_notes, start=1)]
    if not note_identity or track_id not in note_identity:
        return [dict(note, editable=True, derived=False) for note in source_notes]
    ids_by_key: dict[tuple[int, float, float, int], list[str]] = {}
    for note_id, note in note_identity[track_id].items():
        ids_by_key.setdefault(_note_key(note), []).append(note_id)
    notes = []
    derived_index = 1
    for note in source_notes:
        candidates = ids_by_key.get(_note_key(note)) or []
        if candidates:
            notes.append({**note, "note_id": candidates.pop(0), "editable": True, "derived": False})
        else:
            notes.append(_derived_note(track_id, derived_index, note))
            derived_index += 1
    return notes


def _note_key(note: ImplementationDocument) -> tuple[int, float, float, int]:
    return (
        int(note["pitch"]),
        round(float(note["start_beat"]), 6),
        round(float(note["duration_beats"]), 6),
        int(note["velocity"]),
    )


def _derived_note(track_id: str, index: int, note: ImplementationDocument) -> ImplementationDocument:
    return {
        **note,
        "note_id": f"derived-note-{track_id}-{index:04d}",
        "editable": False,
        "derived": True,
    }


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
