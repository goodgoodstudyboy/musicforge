from __future__ import annotations

from pathlib import Path

from song_agent.agent.pipeline import SongAgent
from song_agent.music_health import analyze_music_health, music_health_allows_review
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import NoteEvent, SongPlan, SongRequest, TrackPlan


def test_music_health_passes_generated_song(tmp_path: Path) -> None:
    plan = SongAgent().generate(SongRequest("Health Song", "English", "upbeat pop", "test", 90))
    midi_path = tmp_path / "song.mid"
    render_midi(plan, midi_path)

    report = analyze_music_health(plan, case_id="case-000001", midi_path=midi_path)

    assert report["status"] in {"passed", "warning"}
    assert report["summary"]["note_count"] >= 64
    assert report["summary"]["audio_status"] == "skipped_renderer_not_configured"
    assert music_health_allows_review(report) is True


def test_music_health_blocks_missing_midi(tmp_path: Path) -> None:
    plan = SongAgent().generate(SongRequest("Missing MIDI", "English", "pop", "test", 90))

    report = analyze_music_health(plan, case_id="case-000001", midi_path=tmp_path / "missing.mid")

    assert report["status"] == "failed"
    assert any(item["check_id"] == "midi_exists" for item in report["blockers"])


def test_music_health_blocks_bad_notes(tmp_path: Path) -> None:
    plan = SongAgent().generate(SongRequest("Bad Notes", "English", "pop", "test", 90))
    bad_track = TrackPlan(plan.tracks[0].name, plan.tracks[0].instrument, [NoteEvent(200, 0, -1, 0)])
    bad_plan = SongPlan(plan.title, plan.key, plan.tempo_bpm, plan.meter, plan.sections, [bad_track])
    midi_path = tmp_path / "bad.mid"
    midi_path.write_bytes(b"MThd")

    report = analyze_music_health(bad_plan, case_id="case-000001", midi_path=midi_path)

    blocker_ids = {item["check_id"] for item in report["blockers"]}
    assert {"note_duration_positive", "pitch_range_valid", "velocity_range_valid"}.issubset(blocker_ids)


def test_music_health_blocks_invalid_wav_when_renderer_required(tmp_path: Path) -> None:
    plan = SongAgent().generate(SongRequest("Bad WAV", "English", "pop", "test", 90))
    midi_path = tmp_path / "song.mid"
    wav_path = tmp_path / "song.wav"
    render_midi(plan, midi_path)
    wav_path.write_bytes(b"not-wave")

    report = analyze_music_health(plan, case_id="case-000001", midi_path=midi_path, wav_path=wav_path, renderer_configured=True)

    assert report["status"] == "failed"
    assert any(item["check_id"] == "wav_header_valid" for item in report["blockers"])
