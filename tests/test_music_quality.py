from dataclasses import replace

from song_agent.agent.pipeline import deterministic_compose
from song_agent.music_quality import (
    analyze_song_quality,
    quality_issues_for_plan,
    repair_quality_metadata,
    score_song_plan,
)
from song_agent.schemas.song import SongQualityMeta, NoteEvent, SongRequest, TrackPlan


def request(vocal_mode: str = "guide_melody") -> SongRequest:
    return SongRequest(
        title="Quality Song",
        language="English",
        style="synth pop",
        theme="city lights",
        vocal_mode=vocal_mode,
    )


def test_deterministic_plan_scores_above_threshold() -> None:
    plan = deterministic_compose(request())
    quality = analyze_song_quality(plan)

    assert quality.scores is not None
    assert quality.scores.overall >= 70
    assert "chorus" in quality.hook_sections


def test_missing_hook_warns() -> None:
    plan = deterministic_compose(request())
    sections = [replace(section, name="part_a" if section.name == "chorus" else section.name) for section in plan.sections]
    plan = replace(plan, sections=sections, quality=None)

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "missing_hook" for issue in issues)


def test_chorus_energy_not_lifted_warns() -> None:
    plan = deterministic_compose(request())
    quality = analyze_song_quality(plan)
    intents = [
        replace(intent, energy=3) if intent.section_name == "chorus" else intent
        for intent in quality.section_intents
    ]
    plan = replace(plan, quality=replace(quality, section_intents=intents))

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "chorus_energy_not_lifted" for issue in issues)


def test_melody_range_too_narrow_warns() -> None:
    plan = deterministic_compose(request())
    tracks = [
        replace(track, notes=[replace(note, pitch=64) for note in track.notes])
        if track.name == "melody"
        else track
        for track in plan.tracks
    ]
    plan = replace(plan, tracks=tracks, quality=None)

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "melody_range_too_narrow" for issue in issues)


def test_missing_melody_track_is_error() -> None:
    plan = deterministic_compose(request())
    plan = replace(plan, tracks=[track for track in plan.tracks if track.name != "melody"], quality=None)

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "missing_melody_track" and issue.severity == "error" for issue in issues)


def test_instrumental_skips_lyric_fit_weight() -> None:
    plan = deterministic_compose(request(vocal_mode="instrumental"))
    scores = score_song_plan(plan)

    assert scores.lyric_fit == 0


def test_instrumental_detection_ignores_quality_warning_text() -> None:
    plan = deterministic_compose(request())
    section = replace(plan.sections[1], lyrics=" ".join(["word"] * 80))
    plan = replace(
        plan,
        sections=[plan.sections[0], section, *plan.sections[2:]],
        quality=SongQualityMeta(warnings=["instrumental reference in a warning"]),
    )

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "lyrics_too_dense_for_melody" for issue in issues)


def test_lyrics_too_dense_warns() -> None:
    plan = deterministic_compose(request())
    section = plan.sections[1]
    dense_section = replace(section, lyrics=" ".join(["word"] * 80))
    plan = replace(plan, sections=[plan.sections[0], dense_section, *plan.sections[2:]], quality=None)

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "lyrics_too_dense_for_melody" for issue in issues)


def test_bass_root_mismatch_warns() -> None:
    plan = deterministic_compose(request())
    tracks = [
        TrackPlan(track.name, track.instrument, [NoteEvent(80, note.start_beat, note.duration_beats, note.velocity) for note in track.notes])
        if track.name == "bass"
        else track
        for track in plan.tracks
    ]
    plan = replace(plan, tracks=tracks, quality=None)

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "bass_root_mismatch" for issue in issues)


def test_bass_root_mismatch_allows_octaves() -> None:
    plan = deterministic_compose(request())
    tracks = [
        TrackPlan(track.name, track.instrument, [replace(note, pitch=note.pitch + 24) for note in track.notes])
        if track.name == "bass"
        else track
        for track in plan.tracks
    ]
    plan = replace(plan, tracks=tracks, quality=None)

    issues = quality_issues_for_plan(plan)

    assert not any(issue.code == "bass_root_mismatch" for issue in issues)


def test_bass_root_mismatch_ignores_passing_notes() -> None:
    plan = deterministic_compose(request())
    bass = next(track for track in plan.tracks if track.name == "bass")
    notes = []
    for note in bass.notes:
        notes.append(note)
        notes.append(replace(note, pitch=80, start_beat=note.start_beat + 1.0, duration_beats=0.5))
    tracks = [
        replace(track, notes=notes) if track.name == "bass" else track
        for track in plan.tracks
    ]
    plan = replace(plan, tracks=tracks, quality=None)

    issues = quality_issues_for_plan(plan)

    assert not any(issue.code == "bass_root_mismatch" for issue in issues)


def test_hook_repetition_is_allowed() -> None:
    plan = deterministic_compose(request())
    chorus = next(section for section in plan.sections if section.name == "chorus")
    motif = [NoteEvent(pitch, (chorus.start_bar - 1) * 4 + index * 2, 1.5, 100) for index, pitch in enumerate([72, 74, 76, 74] * 4)]
    tracks = [
        replace(track, notes=motif) if track.name == "melody" else track
        for track in plan.tracks
    ]
    plan = replace(plan, tracks=tracks, quality=None)

    issues = quality_issues_for_plan(plan)

    assert not any(issue.code == "mechanical_melody_repetition" for issue in issues)


def test_mechanical_repetition_warns_across_non_hook_sections() -> None:
    plan = deterministic_compose(request())
    repeated_sections = [replace(section, name=f"part_{index}") for index, section in enumerate(plan.sections)]
    motif = [60, 62, 64, 65]
    notes = []
    for section in repeated_sections:
        section_start = (section.start_bar - 1) * 4
        for phrase in range(2):
            for index, pitch in enumerate(motif):
                notes.append(NoteEvent(pitch, section_start + phrase * 8 + index * 2, 1.5, 90))
    tracks = [
        replace(track, notes=notes) if track.name == "melody" else track
        for track in plan.tracks
    ]
    plan = replace(plan, sections=repeated_sections, tracks=tracks, quality=None)

    issues = quality_issues_for_plan(plan)

    assert any(issue.code == "mechanical_melody_repetition" for issue in issues)


def test_quality_summary_mentions_overall_hook_and_warning_count() -> None:
    plan = deterministic_compose(request())

    quality = analyze_song_quality(plan)

    assert "overall" in quality.summary
    assert "Hook:" in quality.summary
    assert "Warnings:" in quality.summary


def test_repair_quality_recomputes_final_score_without_regression() -> None:
    plan = deterministic_compose(request())
    before = score_song_plan(plan).overall
    tracks = [
        replace(track, notes=[replace(note, pitch=64) for note in track.notes])
        if track.name == "melody"
        else track
        for track in plan.tracks
    ]
    bad = replace(plan, tracks=tracks, quality=None)

    repaired, actions = repair_quality_metadata(bad)

    assert "lift_chorus_melody" in actions
    assert repaired.quality is not None
    assert repaired.quality.scores is not None
    assert repaired.quality.scores.overall >= min(before, score_song_plan(bad).overall)
