from __future__ import annotations

from song_agent.platform.contracts import ImplementationDocument, as_document as _as_document

import math as math
import wave as wave
from pathlib import Path as Path
from typing import Any as Any

from song_agent.domains.creation.midi_analysis import MidiParseError as MidiParseError, midi_summary as midi_summary, parse_midi as parse_midi
from song_agent.domains.creation.redaction import sanitize_metadata as sanitize_metadata
from song_agent.domains.creation.schemas.song import NoteEvent as NoteEvent, SongPlan as SongPlan, TrackPlan as TrackPlan


MUSIC_HEALTH_SCHEMA_VERSION = 1
DEFAULT_MIN_TOTAL_NOTES = 64
DEFAULT_MIN_NOTE_TRACKS = 3
DEFAULT_MAX_WARNINGS = 8


def analyze_music_health(
    plan: SongPlan,
    *,
    case_id: str | None = None,
    midi_path: Path | None = None,
    wav_path: Path | None = None,
    validator_report: dict[str, Any] | None = None,
    quality_report: dict[str, Any] | None = None,
    renderer_configured: bool = False,
    audio_not_required_status: str = "skipped_renderer_not_configured",
    now: str | None = None,
) -> dict[str, Any]:
    """Run deterministic checks that catch obvious broken music artifacts."""
    checks: list[dict[str, Any]] = []
    notes = _all_notes(plan)
    section_summary = _section_summary(plan)
    track_summary = _track_summary(plan)
    total_bars = _total_bars(plan)
    total_beats = total_bars * _beats_per_bar(plan.meter)
    note_tracks = [track for track in plan.tracks if track.notes]
    quality_overall = _quality_overall(plan, quality_report)

    checks.append(_check("song_plan_parse", True, "blocking", "SongPlan object is parseable."))
    checks.append(_check("title_present", bool(plan.title.strip()), "warning", "Song title is present."))
    checks.append(_check("tempo_range", 40 <= plan.tempo_bpm <= 220, "blocking", f"Tempo {plan.tempo_bpm} is within 40..220 BPM."))
    checks.append(_check("meter_supported", plan.meter in {"4/4"}, "blocking", f"Meter {plan.meter} is supported."))
    checks.append(_check("sections_present", len(plan.sections) >= 3, "blocking", f"{len(plan.sections)} sections >= 3."))
    checks.append(_check("tracks_present", bool(plan.tracks), "blocking", "At least one track exists."))
    checks.append(_check("total_duration_reasonable", 16 <= total_beats <= 1200, "blocking", f"Song duration is {round(total_beats, 3)} beats."))

    checks.append(_check("section_timeline_contiguous", _sections_contiguous(plan), "blocking", "Sections form a contiguous timeline."))
    checks.append(_check("section_duration_positive", all(section.bars > 0 for section in plan.sections), "blocking", "All sections have positive duration."))
    checks.append(_check("hook_or_chorus_present", _has_hook_or_chorus(plan), "warning", "Hook or chorus section is present."))
    checks.append(_check("energy_shape_reasonable", _energy_shape_reasonable(plan), "warning", "Hook/chorus energy is not lower than verse energy."))
    checks.append(_check("arrangement_density_not_flat", _density_not_flat(plan), "warning", "Arrangement density varies across sections."))

    role_names = [_track_role(track) for track in plan.tracks]
    checks.append(_check("note_bearing_track_exists", bool(note_tracks), "blocking", "At least one note-bearing track exists."))
    checks.append(_check("melody_or_lead_exists", any(role in {"melody", "lead"} for role in role_names), "warning", "Melody or lead track exists."))
    checks.append(_check("bass_or_low_support_exists", any(role == "bass" or "bass" in track.instrument.lower() for role, track in zip(role_names, plan.tracks)), "warning", "Bass or low support exists."))
    checks.append(_check("harmony_support_exists", any(role in {"chords", "harmony", "pad"} for role in role_names), "warning", "Harmony support exists."))
    checks.append(_check("rhythm_support_exists", any(role in {"drums", "percussion", "rhythm"} for role in role_names), "warning", "Rhythm support exists."))
    empty_count = sum(1 for track in plan.tracks if not track.notes)
    checks.append(_check("empty_tracks_limited", empty_count <= max(1, len(plan.tracks) // 2), "warning", f"{empty_count} empty tracks."))

    checks.append(_check("note_count_minimum", len(notes) >= DEFAULT_MIN_TOTAL_NOTES, "blocking", f"{len(notes)} notes >= {DEFAULT_MIN_TOTAL_NOTES}."))
    checks.append(_check("note_tracks_minimum", len(note_tracks) >= DEFAULT_MIN_NOTE_TRACKS, "warning", f"{len(note_tracks)} note-bearing tracks >= {DEFAULT_MIN_NOTE_TRACKS}."))
    checks.append(_check("note_duration_positive", all(note.duration_beats > 0 for note in notes), "blocking", "All notes have positive duration."))
    checks.append(_check("note_within_song_bounds", all(0 <= note.start_beat and note.start_beat + note.duration_beats <= total_beats + 0.001 for note in notes), "blocking", "All notes stay within song bounds."))
    checks.append(_check("pitch_range_valid", all(0 <= note.pitch <= 127 for note in notes), "blocking", "All MIDI pitches are 0..127."))
    checks.append(_check("velocity_range_valid", all(1 <= note.velocity <= 127 for note in notes), "blocking", "All velocities are 1..127."))
    checks.append(_check("no_extreme_overlaps", _overlap_ratio(plan) <= 0.35, "warning", "Same-track note overlap ratio is limited."))
    checks.append(_check("no_excessive_long_notes", _long_note_ratio(notes, total_beats) <= 0.2, "warning", "Excessive long notes are limited."))
    checks.append(_check("no_mechanical_grid_only", _mechanical_grid_ratio(notes) < 0.98, "warning", "Notes are not completely quantized to one grid."))

    checks.append(_check("leading_silence_limited", _leading_silence(notes) <= 8.0, "warning", "Leading silence is limited."))
    checks.append(_check("trailing_silence_limited", _trailing_silence(notes, total_beats) <= 8.0, "warning", "Trailing silence is limited."))
    checks.append(_check("longest_internal_silence_limited", _longest_internal_silence(notes) <= 16.0, "warning", "Internal silence gaps are limited."))
    checks.append(_check("density_minimum", _density_minimum(notes, total_beats), "blocking", "Every broad song window has enough notes."))
    checks.append(_check("density_peak_exists", _density_peak_exists(notes, total_beats), "warning", "A density peak exists."))
    checks.append(_check("quality_score_minimum", quality_overall is None or quality_overall >= 75, "warning", f"Quality score is {quality_overall if quality_overall is not None else 'not available'}."))

    midi_status = "missing"
    midi_info: dict[str, Any] = {}
    if midi_path is None:
        checks.append(_check("midi_exists", False, "blocking", "MIDI path was not provided."))
    elif not midi_path.exists():
        checks.append(_check("midi_exists", False, "blocking", "MIDI file exists."))
    else:
        checks.append(_check("midi_exists", True, "blocking", "MIDI file exists."))
        data = midi_path.read_bytes()
        checks.append(_check("midi_header_valid", data.startswith(b"MThd"), "blocking", "MIDI header starts with MThd."))
        try:
            parsed = parse_midi(data)
            midi_info = midi_summary(parsed)
            midi_status = "present"
            checks.append(_check("midi_note_events_present", bool(parsed.notes), "blocking", "MIDI contains note events."))
            checks.append(_check("midi_tracks_match_plan", parsed.track_count >= min(1, len(plan.tracks)), "warning", "MIDI track count is compatible with SongPlan."))
            checks.append(_check("midi_eot_present", all(track.has_eot for track in parsed.tracks), "blocking", "Every MIDI track has EOT."))
        except MidiParseError as exc:
            midi_status = "invalid"
            checks.append(_check("midi_note_events_present", False, "blocking", f"MIDI parse failed: {exc}"))
            checks.append(_check("midi_tracks_match_plan", False, "warning", "MIDI track count could not be parsed."))
            checks.append(_check("midi_eot_present", False, "blocking", "MIDI EOT could not be verified."))

    audio_status = "skipped_renderer_not_configured"
    if renderer_configured:
        if wav_path is None or not wav_path.exists():
            audio_status = "missing"
            checks.append(_check("audio_rendered", False, "blocking", "song.wav exists because renderer is configured."))
        else:
            audio_status = "rendered"
            data = wav_path.read_bytes()
            checks.append(_check("audio_rendered", True, "blocking", "song.wav exists."))
            checks.append(_check("wav_header_valid", data.startswith(b"RIFF") and data[8:12] == b"WAVE", "blocking", "WAV header is RIFF/WAVE."))
            checks.append(_check("wav_nonzero_size", wav_path.stat().st_size > 44, "blocking", "WAV file is non-empty."))
            checks.append(_check("wav_duration_reasonable", _wav_duration_reasonable(wav_path, total_beats, plan.tempo_bpm), "warning", "WAV duration is close to SongPlan duration."))
    else:
        audio_status = audio_not_required_status or "skipped_renderer_not_configured"
        audio_message = "Audio renderer is not configured; WAV render is skipped."
        if audio_status == "skipped_by_request":
            audio_message = "Audio rendering was skipped by request; WAV is not required for this suite."
        checks.append(_check("audio_renderer_configured", False, "info", audio_message))

    blockers = [check for check in checks if check["status"] == "failed" and check["severity"] == "blocking"]
    warnings = [check for check in checks if check["status"] == "warning"]
    status = "failed" if blockers else "warning" if len(warnings) > DEFAULT_MAX_WARNINGS else "passed"
    return sanitize_metadata(
        {
            "schema_version": MUSIC_HEALTH_SCHEMA_VERSION,
            "status": status,
            "case_id": case_id,
            "generated_at": now,
            "summary": {
                "duration_beats": round(total_beats, 3),
                "section_count": len(plan.sections),
                "track_count": len(plan.tracks),
                "note_count": len(notes),
                "note_track_count": len(note_tracks),
                "quality_overall": quality_overall,
                "blocking_failed": len(blockers),
                "warning_count": len(warnings),
                "audio_status": audio_status,
                "midi_status": midi_status,
            },
            "checks": checks,
            "track_summary": track_summary,
            "section_summary": section_summary,
            "midi_summary": midi_info,
            "validator_summary": _safe_summary(validator_report),
            "quality_summary": _safe_summary(quality_report),
            "warnings": [_check_message(check) for check in warnings],
            "blockers": [_check_message(check) for check in blockers],
        }
    )


def music_health_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return sanitize_metadata(
        {
            "status": data.get("status") or "missing",
            "blocking_failed": summary.get("blocking_failed", 0),
            "warning_count": summary.get("warning_count", 0),
            "note_count": summary.get("note_count", 0),
            "track_count": summary.get("track_count", 0),
            "section_count": summary.get("section_count", 0),
            "audio_status": summary.get("audio_status") or "missing",
            "midi_status": summary.get("midi_status") or "missing",
            "quality_overall": summary.get("quality_overall"),
        }
    )


def music_health_allows_review(report: dict[str, Any] | None) -> bool:
    data = _as_document(report)
    summary = _as_document(data.get("summary"))
    return data.get("status") in {"passed", "warning"} and int(summary.get("blocking_failed", 0) or 0) == 0


def _check(check_id: str, passed: bool, severity: str, message: str) -> ImplementationDocument:
    status = "passed" if passed else "warning" if severity in {"warning", "info"} else "failed"
    if severity == "info":
        status = "skipped" if not passed else "passed"
    return {"check_id": check_id, "status": status, "severity": severity, "message": message}


def _check_message(check: ImplementationDocument) -> ImplementationDocument:
    return {"check_id": check.get("check_id"), "message": check.get("message"), "severity": check.get("severity")}


def _all_notes(plan: SongPlan) -> list[NoteEvent]:
    return [note for track in plan.tracks for note in track.notes]


def _beats_per_bar(meter: str) -> int:
    try:
        numerator, denominator = meter.split("/", 1)
        if int(denominator) == 4:
            return max(1, int(numerator))
    except (ValueError, ZeroDivisionError):
        pass
    return 4


def _total_bars(plan: SongPlan) -> int:
    return max([section.start_bar + section.bars - 1 for section in plan.sections] + [0])


def _sections_contiguous(plan: SongPlan) -> bool:
    expected = 1
    for section in sorted(plan.sections, key=lambda item: item.start_bar):
        if section.start_bar != expected or section.bars <= 0:
            return False
        expected += section.bars
    return bool(plan.sections)


def _has_hook_or_chorus(plan: SongPlan) -> bool:
    names = " ".join(section.name.lower() for section in plan.sections)
    hooks = set(plan.quality.hook_sections) if plan.quality else set()
    return "hook" in names or "chorus" in names or bool(hooks)


def _energy_shape_reasonable(plan: SongPlan) -> bool:
    if not plan.quality or not plan.quality.section_intents:
        return True
    verse = [intent.energy for intent in plan.quality.section_intents if "verse" in intent.section_name.lower()]
    hook = [intent.energy for intent in plan.quality.section_intents if "chorus" in intent.section_name.lower() or intent.hook or "hook" in intent.section_name.lower()]
    if not verse or not hook:
        return True
    return max(hook) >= max(verse)


def _density_not_flat(plan: SongPlan) -> bool:
    counts = []
    for section in plan.sections:
        start = (section.start_bar - 1) * _beats_per_bar(plan.meter)
        end = start + section.bars * _beats_per_bar(plan.meter)
        counts.append(sum(1 for note in _all_notes(plan) if start <= note.start_beat < end))
    return len(set(counts)) > 1 if len(counts) > 1 else True


def _track_role(track: TrackPlan) -> str:
    value = f"{track.name} {track.instrument}".lower()
    for role in ("melody", "lead", "chords", "harmony", "pad", "bass", "drums", "percussion", "rhythm"):
        if role in value:
            return role
    return track.name.strip().lower()


def _overlap_ratio(plan: SongPlan) -> float:
    overlaps = 0
    total_pairs = 0
    for track in plan.tracks:
        notes = sorted(track.notes, key=lambda note: (note.start_beat, note.pitch))
        for left, right in zip(notes, notes[1:]):
            total_pairs += 1
            if left.start_beat + left.duration_beats > right.start_beat and left.pitch == right.pitch:
                overlaps += 1
    return overlaps / total_pairs if total_pairs else 0.0


def _long_note_ratio(notes: list[NoteEvent], total_beats: float) -> float:
    if not notes:
        return 0.0
    threshold = max(8.0, total_beats * 0.2)
    return sum(1 for note in notes if note.duration_beats >= threshold) / len(notes)


def _mechanical_grid_ratio(notes: list[NoteEvent]) -> float:
    if not notes:
        return 0.0
    return sum(1 for note in notes if math.isclose(note.start_beat % 1.0, 0.0, abs_tol=0.001)) / len(notes)


def _leading_silence(notes: list[NoteEvent]) -> float:
    return min((note.start_beat for note in notes), default=0.0)


def _trailing_silence(notes: list[NoteEvent], total_beats: float) -> float:
    last = max((note.start_beat + note.duration_beats for note in notes), default=0.0)
    return max(0.0, total_beats - last)


def _longest_internal_silence(notes: list[NoteEvent]) -> float:
    spans = sorted((note.start_beat, note.start_beat + note.duration_beats) for note in notes)
    if len(spans) < 2:
        return 0.0
    longest = 0.0
    current_end = spans[0][1]
    for start, end in spans[1:]:
        longest = max(longest, max(0.0, start - current_end))
        current_end = max(current_end, end)
    return longest


def _density_minimum(notes: list[NoteEvent], total_beats: float) -> bool:
    if not notes:
        return False
    window = 32.0
    start = 0.0
    while start < total_beats:
        end = min(total_beats, start + window)
        if sum(1 for note in notes if start <= note.start_beat < end) < 4:
            return False
        start += window
    return True


def _density_peak_exists(notes: list[NoteEvent], total_beats: float) -> bool:
    if total_beats <= 32:
        return True
    buckets = []
    start = 0.0
    while start < total_beats:
        end = min(total_beats, start + 16.0)
        buckets.append(sum(1 for note in notes if start <= note.start_beat < end))
        start += 16.0
    return bool(buckets) and max(buckets) >= max(8, min(buckets) * 1.2)


def _section_summary(plan: SongPlan) -> list[ImplementationDocument]:
    beats = _beats_per_bar(plan.meter)
    notes = _all_notes(plan)
    rows = []
    for section in plan.sections:
        start = (section.start_bar - 1) * beats
        end = start + section.bars * beats
        rows.append(
            {
                "name": section.name,
                "start_bar": section.start_bar,
                "bars": section.bars,
                "note_count": sum(1 for note in notes if start <= note.start_beat < end),
            }
        )
    return rows


def _track_summary(plan: SongPlan) -> list[ImplementationDocument]:
    rows = []
    for track in plan.tracks:
        pitches = [note.pitch for note in track.notes]
        rows.append(
            {
                "name": track.name,
                "instrument": track.instrument,
                "role": _track_role(track),
                "note_count": len(track.notes),
                "pitch_min": min(pitches) if pitches else None,
                "pitch_max": max(pitches) if pitches else None,
            }
        )
    return rows


def _quality_overall(plan: SongPlan, quality_report: ImplementationDocument | None) -> int | None:
    if plan.quality and plan.quality.scores:
        return plan.quality.scores.overall
    if isinstance(quality_report, dict):
        for key in ("overall", "score", "quality_score"):
            value = quality_report.get(key)
            if isinstance(value, int):
                return value
        summary = quality_report.get("summary")
        if isinstance(summary, dict) and isinstance(summary.get("overall"), int):
            return summary["overall"]
    return None


def _wav_duration_reasonable(path: Path, total_beats: float, tempo_bpm: int) -> bool:
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            seconds = frames / rate if rate else 0.0
    except (wave.Error, OSError):
        return False
    expected = total_beats * 60 / max(1, tempo_bpm)
    if expected <= 0:
        return False
    return 0.5 <= seconds / expected <= 1.8


def _safe_summary(report: ImplementationDocument | None) -> ImplementationDocument:
    if not isinstance(report, dict):
        return {}
    summary = report.get("summary")
    if isinstance(summary, dict):
        return dict(summary)
    return {key: value for key, value in report.items() if key in {"status", "score", "overall", "generated_at"}}
