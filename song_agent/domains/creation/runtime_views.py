from __future__ import annotations

from song_agent.domains.legacy_documents import ImplementationDocument, _as_document

from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.music_quality import analyze_song_quality as analyze_song_quality, quality_issues_for_plan as quality_issues_for_plan
from song_agent.domains.studio.projectio import read_json as read_json
from song_agent.domains.creation.schemas.song import SongPlan as SongPlan


def build_summary_view(plan: Any) -> dict[str, Any]:
    plan_data = _as_dict(plan)
    tracks = _as_list(plan_data.get("tracks", []))
    sections = _as_list(plan_data.get("sections", []))
    return {
        "title": plan_data.get("title"),
        "tempo_bpm": plan_data.get("tempo_bpm"),
        "key": plan_data.get("key"),
        "meter": plan_data.get("meter"),
        "section_count": len(sections),
        "track_count": len(tracks),
        "note_count": sum(len(_as_list(track.get("notes", []))) for track in tracks),
        "total_bars": _total_bars(sections),
        "quality_score": _quality_score(plan_data),
    }


def build_timeline_view(plan: Any) -> dict[str, Any]:
    plan_data = _as_dict(plan)
    tempo_bpm = _positive_float(plan_data.get("tempo_bpm"), "tempo_bpm")
    meter = str(plan_data.get("meter") or "4/4")
    sections = _as_list(plan_data.get("sections", []))
    intents = _section_intents_by_name(plan_data)
    beats_per_bar, warnings = _beats_per_bar(meter)
    seconds_per_beat = 60 / tempo_bpm

    section_views: list[dict[str, Any]] = []
    for index, section in enumerate(sections):
        section = _as_dict(section)
        start_bar = int(section.get("start_bar", 1))
        bars = int(section.get("bars", 0))
        intent = intents.get(str(section.get("name", "")))
        start_beat = (start_bar - 1) * beats_per_bar
        end_beat = start_beat + bars * beats_per_bar
        section_views.append(
            {
                "index": index,
                "name": section.get("name"),
                "start_bar": start_bar,
                "end_bar": start_bar + bars - 1 if bars else start_bar - 1,
                "bars": bars,
                "start_beat": start_beat,
                "end_beat": end_beat,
                "estimated_start_seconds": round(start_beat * seconds_per_beat, 2),
                "estimated_end_seconds": round(end_beat * seconds_per_beat, 2),
                "chords": _as_list(section.get("chords", [])),
                "energy": intent.get("energy", 0) if intent else 0,
                "tension": intent.get("tension", 0) if intent else 0,
                "density": intent.get("density", 0) if intent else 0,
                "role": intent.get("role", "") if intent else "",
                "hook": bool(intent.get("hook", False)) if intent else False,
            }
        )

    total_bars = _total_bars(sections)
    return {
        "title": plan_data.get("title"),
        "tempo_bpm": int(tempo_bpm) if tempo_bpm.is_integer() else tempo_bpm,
        "meter": meter,
        "total_bars": total_bars,
        "estimated_seconds": round(total_bars * beats_per_bar * seconds_per_beat, 2),
        "sections": section_views,
        "warnings": warnings,
    }


def build_tracks_view(plan: Any) -> dict[str, Any]:
    plan_data = _as_dict(plan)
    sections = _as_list(plan_data.get("sections", []))
    total_bars = _total_bars(sections)
    tracks = _as_list(plan_data.get("tracks", []))

    track_views: list[dict[str, Any]] = []
    total_note_count = 0
    for index, track in enumerate(tracks):
        track = _as_dict(track)
        notes = [_as_dict(note) for note in _as_list(track.get("notes", []))]
        total_note_count += len(notes)
        pitches = [int(note["pitch"]) for note in notes if "pitch" in note and note["pitch"] is not None]
        starts = [
            float(note["start_beat"])
            for note in notes
            if "start_beat" in note and note["start_beat"] is not None
        ]
        ends = [
            float(note.get("start_beat", 0)) + float(note.get("duration_beats", 0))
            for note in notes
        ]
        velocities = [int(note.get("velocity", 90)) for note in notes]
        track_views.append(
            {
                "index": index,
                "name": track.get("name"),
                "instrument": track.get("instrument"),
                "note_count": len(notes),
                "pitch_min": min(pitches) if pitches else None,
                "pitch_max": max(pitches) if pitches else None,
                "start_beat_min": min(starts) if starts else None,
                "end_beat_max": max(ends) if ends else None,
                "average_velocity": round(sum(velocities) / len(velocities), 2)
                if velocities
                else None,
                "density_notes_per_bar": round(len(notes) / total_bars, 2)
                if total_bars
                else None,
            }
        )

    return {
        "track_count": len(tracks),
        "note_count": total_note_count,
        "total_bars": total_bars,
        "tracks": track_views,
    }


def build_validator_view(
    report: dict[str, Any] | None,
    plan: Any | None = None,
) -> dict[str, Any]:
    quality_warnings = _quality_warnings(plan) if plan is not None else []
    if report is None:
        return {
            "status": "missing",
            "passed": False,
            "check_count": 0,
            "checks": [],
            "midi": {"exists": False, "size": 0},
            "audio": {"exists": False, "path": "", "size_bytes": 0},
            "warnings": ["validator-report.json was not found.", *quality_warnings],
        }

    status = str(report.get("status", "unknown"))
    checks = [_normalize_check(check, status) for check in _as_list(report.get("checks", []))]
    warnings = [str(warning) for warning in _as_list(report.get("warnings", []))]
    return {
        "status": status,
        "passed": status == "passed",
        "check_count": len(checks),
        "checks": checks,
        "midi": {
            "exists": bool(report.get("midi_exists", False)),
            "size": int(report.get("midi_size", 0) or 0),
        },
        "audio": _audio_view(report.get("audio")),
        "warnings": [*warnings, *quality_warnings],
    }


def build_quality_view(plan: Any, critic_report: dict[str, Any] | None = None) -> dict[str, Any]:
    quality = _quality_view_from_plan(plan)
    if critic_report:
        quality["critic"] = {
            "passed": bool(critic_report.get("passed", False)),
            "score": int(critic_report.get("score", 0) or 0),
            "dimension_scores": _as_dict_or_empty(critic_report.get("dimension_scores")),
            "summary": str(critic_report.get("summary", "")),
        }
    return quality


def build_runtime_views(plan_path: Path, validator_path: Path | None = None) -> dict[str, Any]:
    plan = read_json(plan_path)
    report = None
    if validator_path is not None and validator_path.exists():
        report = read_json(validator_path)
    return {
        "summary": build_summary_view(plan),
        "timeline": build_timeline_view(plan),
        "tracks": build_tracks_view(plan),
        "validator": build_validator_view(report, plan),
        "quality": build_quality_view(plan),
    }


def _as_dict(value: Any) -> ImplementationDocument:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, dict):
        raise ValueError("Runtime view input must be a JSON object.")
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Runtime view field must be a list.")
    return value


def _positive_float(value: Any, name: str) -> float:
    if value is None:
        raise ValueError(f"{name} is required for runtime views.")
    number = float(value)
    if number <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return number


def _beats_per_bar(meter: str) -> tuple[int, list[str]]:
    if meter == "4/4":
        return 4, []
    return 4, [f"Unsupported meter {meter}; timeline estimated with 4 beats per bar."]


def _total_bars(sections: list[Any]) -> int:
    total = 0
    for section in sections:
        section = _as_dict(section)
        start_bar = int(section.get("start_bar", 1))
        bars = int(section.get("bars", 0))
        total = max(total, start_bar + bars - 1)
    return total


def _normalize_check(check: Any, fallback_status: str) -> dict[str, str]:
    if isinstance(check, dict):
        return {
            "name": str(check.get("name", "unnamed_check")),
            "status": str(check.get("status", fallback_status)),
        }
    return {"name": str(check), "status": fallback_status}


def _audio_view(value: Any) -> ImplementationDocument:
    audio = _as_document(value)
    return {
        "exists": bool(audio.get("exists", False)),
        "path": str(audio.get("path", "") or ""),
        "size_bytes": int(audio.get("size_bytes", 0) or 0),
    }


def _quality_view_from_plan(plan: Any) -> ImplementationDocument:
    plan_data = _as_dict(plan)
    song_plan = SongPlan.from_dict(plan_data)
    analyzed = analyze_song_quality(song_plan)
    quality = song_plan.quality or analyzed
    scores = quality.scores or analyzed.scores
    primary_motif = quality.primary_motif or analyzed.primary_motif
    hook_sections = quality.hook_sections or analyzed.hook_sections
    section_intents = quality.section_intents or analyzed.section_intents
    warnings = _dedupe([*quality.warnings, *analyzed.warnings])
    issues = [issue.to_dict() for issue in quality_issues_for_plan(song_plan)]
    return {
        "summary": quality.summary or analyzed.summary,
        "scores": scores.to_dict() if scores else {},
        "overall": scores.overall if scores else 0,
        "primary_motif": primary_motif.to_dict() if primary_motif else None,
        "hook_sections": hook_sections,
        "section_intents": [intent.to_dict() for intent in section_intents],
        "issues": issues,
        "warnings": warnings,
    }


def _quality_score(plan_data: ImplementationDocument) -> int | None:
    quality = plan_data.get("quality")
    if isinstance(quality, dict):
        scores = quality.get("scores")
        if isinstance(scores, dict) and scores.get("overall") is not None:
            return int(scores["overall"])
    try:
        analyzed = analyze_song_quality(SongPlan.from_dict(plan_data))
    except ValueError:
        return None
    return analyzed.scores.overall if analyzed.scores else None


def _section_intents_by_name(plan_data: ImplementationDocument) -> dict[str, ImplementationDocument]:
    quality = plan_data.get("quality")
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(quality, dict):
        quality = {}
    intents = _as_list(quality.get("section_intents", []))
    for intent in intents:
        intent_data = _as_dict(intent)
        result[str(intent_data.get("section_name", ""))] = intent_data
    try:
        inferred = analyze_song_quality(SongPlan.from_dict(plan_data)).section_intents
    except ValueError:
        return result
    for intent in inferred:
        result.setdefault(intent.section_name, intent.to_dict())
    return result


def _as_dict_or_empty(value: Any) -> ImplementationDocument:
    return _as_document(value)


def _quality_warnings(plan: Any) -> list[str]:
    return [str(warning) for warning in _as_list(_quality_view_from_plan(plan).get("warnings", []))]


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
