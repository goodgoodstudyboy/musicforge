from dataclasses import replace

from song_agent.agent.pipeline import deterministic_compose
from song_agent.music_quality import (
    analyze_song_quality,
    quality_issues_for_plan,
    score_song_plan,
)
from song_agent.schemas.song import NoteEvent, SongPlan, SongRequest, TrackPlan


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
