from __future__ import annotations

from dataclasses import replace
from typing import Any

from song_agent.schemas.agent_nodes import CriticIssue
from song_agent.schemas.song import (
    MotifPlan,
    NoteEvent,
    QualityScores,
    SectionIntent,
    SongPlan,
    SongQualityMeta,
    SongSection,
    TrackPlan,
)


QUALITY_DIMENSIONS = ("structure", "melody", "harmony", "arrangement", "lyric_fit")


def analyze_song_quality(plan: SongPlan) -> SongQualityMeta:
    scores = score_song_plan(plan)
    issues = quality_issues_for_plan(plan)
    warnings = [issue.message for issue in issues if issue.severity in {"warning", "info"}]
    section_intents = infer_section_intents(plan)
    hook_sections = [intent.section_name for intent in section_intents if intent.hook]
    primary_motif = _infer_primary_motif(plan, hook_sections)
    summary = _quality_summary(plan, scores, hook_sections)
    return SongQualityMeta(
        summary=summary,
        primary_motif=primary_motif,
        section_intents=section_intents,
        hook_sections=hook_sections,
        scores=scores,
        warnings=warnings,
    )


def attach_quality(plan: SongPlan) -> SongPlan:
    return replace(plan, quality=analyze_song_quality(plan))


def score_song_plan(plan: SongPlan) -> QualityScores:
    issues = quality_issues_for_plan(plan)
    scores = {dimension: 88 for dimension in QUALITY_DIMENSIONS}
    for issue in issues:
        dimension = _dimension_for_issue(issue.code)
        penalty = 18 if issue.severity == "error" else 8 if issue.severity == "warning" else 3
        scores[dimension] = max(0, scores[dimension] - penalty)
    if _is_instrumental(plan):
        scores["lyric_fit"] = 0
        weights = {"structure": 20, "melody": 30, "harmony": 22, "arrangement": 28}
    else:
        weights = {"structure": 20, "melody": 25, "harmony": 20, "arrangement": 25, "lyric_fit": 10}
    total_weight = sum(weights.values())
    overall = round(sum(scores[name] * weight for name, weight in weights.items()) / total_weight)
    return QualityScores(
        overall=_clamp(overall, 0, 100),
        structure=_clamp(scores["structure"], 0, 100),
        melody=_clamp(scores["melody"], 0, 100),
        harmony=_clamp(scores["harmony"], 0, 100),
        arrangement=_clamp(scores["arrangement"], 0, 100),
        lyric_fit=_clamp(scores["lyric_fit"], 0, 100),
    )


def quality_issues_for_plan(plan: SongPlan) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    issues.extend(detect_section_energy_shape(plan))
    issues.extend(_detect_melody_quality(plan))
    issues.extend(_detect_harmony_quality(plan))
    issues.extend(_detect_arrangement_quality(plan))
    issues.extend(_detect_lyric_fit(plan))
    issues.extend(detect_repetition(plan))
    return issues


def melody_range_by_track(plan: SongPlan) -> dict[str, tuple[int, int]]:
    ranges: dict[str, tuple[int, int]] = {}
    for track in plan.tracks:
        pitches = [note.pitch for note in track.notes]
        if pitches:
            ranges[track.name] = (min(pitches), max(pitches))
    return ranges


def track_density_by_section(plan: SongPlan) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for track in plan.tracks:
        section_density: dict[str, float] = {}
        for section in plan.sections:
            start, end = _section_beat_range(section)
            notes = [note for note in track.notes if start <= note.start_beat < end]
            section_density[section.name] = round(len(notes) / max(section.bars, 1), 2)
        result[track.name] = section_density
    return result


def infer_section_intents(plan: SongPlan) -> list[SectionIntent]:
    existing = {
        intent.section_name: intent
        for intent in (plan.quality.section_intents if plan.quality else [])
    }
    intents: list[SectionIntent] = []
    densities = track_density_by_section(plan)
    for section in plan.sections:
        if section.name in existing:
            intents.append(existing[section.name])
            continue
        lower = section.name.lower()
        energy = _default_energy(lower)
        density = _section_density_score(section, densities)
        tension = _default_tension(lower, energy)
        role = _default_role(lower)
        hook = "chorus" in lower or "hook" in lower
        intents.append(
            SectionIntent(
                section_name=section.name,
                role=role,
                energy=energy,
                tension=tension,
                density=density,
                transition=_default_transition(lower),
                hook=hook,
            )
        )
    return intents


def detect_repetition(plan: SongPlan) -> list[CriticIssue]:
    melody = _track_by_role(plan, "melody")
    if melody is None or len(melody.notes) < 8:
        return []
    windows = [
        tuple(note.pitch for note in melody.notes[index : index + 4])
        for index in range(0, len(melody.notes) - 3, 4)
    ]
    if len(set(windows)) <= 1 and len(windows) > 2:
        return [
            _issue(
                "warning",
                "mechanical_melody_repetition",
                "Melody repeats the same four-note shape across too many phrases.",
                "tracks.melody",
            )
        ]
    return []


def detect_section_energy_shape(plan: SongPlan) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    intents = {intent.section_name.lower(): intent for intent in infer_section_intents(plan)}
    verse = _first_intent(intents, "verse")
    chorus = _first_intent(intents, "chorus")
    outro = _first_intent(intents, "outro")
    if len(plan.sections) < 3:
        issues.append(_issue("warning", "few_sections", "Song has fewer than three sections.", "sections"))
    if not chorus and not any(intent.hook for intent in intents.values()):
        issues.append(_issue("warning", "missing_hook", "No hook or chorus section is marked.", "quality.hook_sections"))
    if verse and chorus and chorus.energy <= verse.energy:
        issues.append(
            _issue(
                "warning",
                "chorus_energy_not_lifted",
                "Chorus energy should be higher than verse energy.",
                "quality.section_intents",
            )
        )
    if outro and chorus and outro.energy >= chorus.energy:
        issues.append(
            _issue(
                "info",
                "outro_not_resolving",
                "Outro energy is not lower than chorus energy.",
                "quality.section_intents",
            )
        )
    return issues


def repair_quality_metadata(plan: SongPlan) -> tuple[SongPlan, list[str]]:
    actions: list[str] = []
    quality = analyze_song_quality(plan)
    if plan.quality is None:
        actions.append("add_quality_metadata")
    if not quality.hook_sections and any(section.name.lower() == "chorus" for section in plan.sections):
        intents = [
            replace(intent, hook=True)
            if intent.section_name.lower() == "chorus"
            else intent
            for intent in quality.section_intents
        ]
        quality = replace(quality, section_intents=intents, hook_sections=["chorus"])
        actions.append("mark_chorus_hook")
    plan = replace(plan, quality=quality)
    issues = {issue.code for issue in quality_issues_for_plan(plan)}
    if "chorus_energy_not_lifted" in issues:
        intents = _lift_chorus_intent(plan.quality.section_intents if plan.quality else [])
        quality = replace(plan.quality, section_intents=intents) if plan.quality else quality
        plan = replace(plan, quality=quality)
        actions.append("lift_chorus_energy")
    if "melody_range_too_narrow" in issues:
        plan = _lift_chorus_melody(plan)
        plan = replace(plan, quality=analyze_song_quality(plan))
        actions.append("lift_chorus_melody")
    return plan, actions


def _detect_melody_quality(plan: SongPlan) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    melody = _track_by_role(plan, "melody")
    if melody is None:
        return [_issue("error", "missing_melody_track", "SongPlan is missing melody track.", "tracks")]
    if not melody.notes:
        return [_issue("error", "empty_melody_track", "Melody track has no notes.", "tracks.melody")]
    pitches = [note.pitch for note in melody.notes]
    spread = max(pitches) - min(pitches)
    if spread < 5:
        issues.append(_issue("warning", "melody_range_too_narrow", "Melody range is too narrow.", "tracks.melody"))
    if spread > 24:
        issues.append(_issue("warning", "melody_range_too_wide", "Melody range is very wide.", "tracks.melody"))
    sections_with_melody = {
        section.name
        for section in plan.sections
        if _notes_in_section(melody.notes, section)
    }
    main_sections = [section.name for section in plan.sections if section.bars >= 4]
    missing = [section for section in main_sections if section not in sections_with_melody]
    if missing:
        issues.append(
            _issue(
                "warning",
                "missing_section_melody",
                f"Melody is missing in sections: {', '.join(missing)}.",
                "tracks.melody",
            )
        )
    durations = [note.duration_beats for note in melody.notes]
    if durations and sum(duration < 0.25 for duration in durations) > len(durations) / 3:
        issues.append(_issue("info", "melody_too_fragmented", "Melody has many very short notes.", "tracks.melody"))
    return issues


def _detect_harmony_quality(plan: SongPlan) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    if any(not section.chords for section in plan.sections):
        issues.append(_issue("error", "missing_section_chords", "One or more sections have no chords.", "sections"))
    unique_progressions = {tuple(section.chords) for section in plan.sections}
    if len(unique_progressions) == 1 and len(plan.sections) > 2:
        issues.append(
            _issue(
                "info",
                "static_harmony",
                "All sections use the same chord progression.",
                "sections.chords",
            )
        )
    bass = _track_by_role(plan, "bass")
    if bass is not None and bass.notes and plan.sections:
        mismatches = _bass_root_mismatches(plan, bass)
        if mismatches:
            issues.append(
                _issue(
                    "warning",
                    "bass_root_mismatch",
                    "Bass root does not align with section chord roots.",
                    "tracks.bass",
                )
            )
    return issues


def _detect_arrangement_quality(plan: SongPlan) -> list[CriticIssue]:
    issues: list[CriticIssue] = []
    for role in ("melody", "chords", "bass", "drums"):
        track = _track_by_role(plan, role)
        if track is None:
            issues.append(_issue("error", f"missing_{role}_track", f"Missing {role} track.", "tracks"))
        elif not track.notes:
            issues.append(_issue("error", f"empty_{role}_track", f"{role} track has no notes.", f"tracks.{role}"))
    drums = _track_by_role(plan, "drums")
    if drums and plan.sections:
        densities = track_density_by_section(plan).get(drums.name, {})
        verse_density = _density_for(densities, "verse")
        chorus_density = _density_for(densities, "chorus")
        if verse_density is not None and chorus_density is not None and chorus_density <= verse_density:
            issues.append(
                _issue(
                    "warning",
                    "drums_do_not_lift_chorus",
                    "Drum density should lift in the chorus.",
                    "tracks.drums",
                )
            )
    return issues


def _detect_lyric_fit(plan: SongPlan) -> list[CriticIssue]:
    if _is_instrumental(plan):
        return []
    issues: list[CriticIssue] = []
    melody = _track_by_role(plan, "melody")
    if melody is None:
        return issues
    for section in plan.sections:
        if not section.lyrics:
            continue
        melody_notes = _notes_in_section(melody.notes, section)
        words = section.lyrics.split()
        if len(words) > len(melody_notes) * 2:
            issues.append(
                _issue(
                    "warning",
                    "lyrics_too_dense_for_melody",
                    f"Section {section.name} has more lyric words than the guide melody can comfortably carry.",
                    f"sections.{section.name}.lyrics",
                )
            )
    return issues


def _infer_primary_motif(plan: SongPlan, hook_sections: list[str]) -> MotifPlan | None:
    if plan.quality and plan.quality.primary_motif:
        return plan.quality.primary_motif
    melody = _track_by_role(plan, "melody")
    if melody is None or len(melody.notes) < 4:
        return None
    notes = melody.notes[:5]
    intervals = [0]
    intervals.extend(notes[index].pitch - notes[index - 1].pitch for index in range(1, len(notes)))
    rhythms = [round(note.duration_beats, 2) for note in notes]
    return MotifPlan(
        name="primary hook",
        description="A short interval and rhythm cell reused across the generated melody.",
        rhythm_pattern=rhythms,
        pitch_intervals=intervals,
        anchor_section=hook_sections[0] if hook_sections else (plan.sections[0].name if plan.sections else None),
    )


def _quality_summary(plan: SongPlan, scores: QualityScores, hook_sections: list[str]) -> str:
    hook_text = ", ".join(hook_sections) if hook_sections else "no explicit hook"
    return f"{plan.title} scores {scores.overall}/100 with {hook_text}."


def _dimension_for_issue(code: str) -> str:
    if any(token in code for token in ("section", "chorus", "hook", "outro")):
        return "structure"
    if "melody" in code or "repetition" in code:
        return "melody"
    if "chord" in code or "harmony" in code or "bass_root" in code:
        return "harmony"
    if "lyric" in code:
        return "lyric_fit"
    return "arrangement"


def _is_instrumental(plan: SongPlan) -> bool:
    if plan.quality and any("instrumental" in warning.lower() for warning in plan.quality.warnings):
        return True
    return all(not section.lyrics for section in plan.sections)


def _default_energy(section_name: str) -> int:
    if "intro" in section_name:
        return 2
    if "verse" in section_name:
        return 4
    if "pre" in section_name:
        return 5
    if "chorus" in section_name or "hook" in section_name:
        return 7
    if "bridge" in section_name:
        return 6
    if "outro" in section_name:
        return 3
    return 5


def _default_tension(section_name: str, energy: int) -> int:
    if "outro" in section_name:
        return 2
    if "pre" in section_name:
        return min(10, energy + 2)
    if "chorus" in section_name:
        return max(5, energy - 1)
    return energy


def _default_role(section_name: str) -> str:
    if "intro" in section_name:
        return "establish"
    if "verse" in section_name:
        return "narrative"
    if "pre" in section_name:
        return "build"
    if "chorus" in section_name or "hook" in section_name:
        return "hook"
    if "bridge" in section_name:
        return "contrast"
    if "outro" in section_name:
        return "resolve"
    return "section"


def _default_transition(section_name: str) -> str:
    if "intro" in section_name:
        return "open into verse"
    if "verse" in section_name:
        return "build toward hook"
    if "chorus" in section_name:
        return "land the hook"
    if "outro" in section_name:
        return "reduce density"
    return ""


def _section_density_score(section: SongSection, densities: dict[str, dict[str, float]]) -> int:
    values = [
        section_densities.get(section.name, 0.0)
        for section_densities in densities.values()
    ]
    if not values:
        return _default_energy(section.name.lower())
    return _clamp(round(sum(values) / len(values)), 0, 10)


def _section_beat_range(section: SongSection) -> tuple[float, float]:
    start = float((section.start_bar - 1) * 4)
    return start, start + float(section.bars * 4)


def _notes_in_section(notes: list[NoteEvent], section: SongSection) -> list[NoteEvent]:
    start, end = _section_beat_range(section)
    return [note for note in notes if start <= note.start_beat < end]


def _track_by_role(plan: SongPlan, role: str) -> TrackPlan | None:
    for track in plan.tracks:
        if role in track.name.lower():
            return track
    return None


def _first_intent(intents: dict[str, SectionIntent], token: str) -> SectionIntent | None:
    for name, intent in intents.items():
        if token in name:
            return intent
    return None


def _density_for(densities: dict[str, float], token: str) -> float | None:
    for section_name, density in densities.items():
        if token in section_name.lower():
            return density
    return None


def _bass_root_mismatches(plan: SongPlan, bass: TrackPlan) -> list[str]:
    mismatches: list[str] = []
    for section in plan.sections:
        if not section.chords:
            continue
        expected = _bass_root(section.chords[0])
        notes = _notes_in_section(bass.notes, section)
        if notes and abs(notes[0].pitch - expected) > 12:
            mismatches.append(section.name)
    return mismatches


def _bass_root(chord: str) -> int:
    roots = {"C": 36, "D": 38, "E": 40, "F": 41, "G": 31, "A": 33, "B": 35}
    if not chord:
        return 36
    return roots.get(chord[0].upper(), 36)


def _lift_chorus_intent(intents: list[SectionIntent]) -> list[SectionIntent]:
    verse_energy = max((intent.energy for intent in intents if "verse" in intent.section_name.lower()), default=4)
    return [
        replace(intent, energy=max(intent.energy, min(10, verse_energy + 2)), hook=True)
        if "chorus" in intent.section_name.lower()
        else intent
        for intent in intents
    ]


def _lift_chorus_melody(plan: SongPlan) -> SongPlan:
    fixed_tracks: list[TrackPlan] = []
    chorus_sections = [section for section in plan.sections if "chorus" in section.name.lower()]
    for track in plan.tracks:
        if "melody" not in track.name.lower():
            fixed_tracks.append(track)
            continue
        fixed_notes: list[NoteEvent] = []
        for note in track.notes:
            in_chorus = any(start <= note.start_beat < end for start, end in map(_section_beat_range, chorus_sections))
            fixed_notes.append(replace(note, pitch=min(127, note.pitch + 5)) if in_chorus else note)
        fixed_tracks.append(replace(track, notes=fixed_notes))
    return replace(plan, tracks=fixed_tracks)


def _issue(severity: str, code: str, message: str, target: str | None = None) -> CriticIssue:
    return CriticIssue(severity=severity, code=code, message=message, target=target)


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))
