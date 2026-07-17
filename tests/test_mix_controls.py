from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.mix_controls import (
    MixControlError,
    apply_patch_and_render_plan,
    build_mix_patch,
    default_mix_state,
)
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import NoteEvent, SongPlan, SongSection, TrackPlan


def test_mix_patch_scales_velocity_mute_solo_and_section_automation(tmp_path: Path) -> None:
    plan = _plan()
    midi_path = tmp_path / "song.mid"
    render_midi(plan, midi_path)
    state = default_mix_state(project_id="project", version_id="v001", plan=plan, midi_path=midi_path, now="2026-05-26T00:00:00+00:00")
    patch = build_mix_patch(
        patch_id="mixpatch-000001",
        project_id="project",
        version_id="v001",
        state=state,
        plan=plan,
        operations=[
            {"op": "set_track_volume", "track_id": "track-001", "volume_db": -6},
            {"op": "set_section_track_velocity_scale", "track_id": "track-001", "section_id": "section-002", "velocity_scale": 0.5},
            {"op": "set_track_pan", "track_id": "track-001", "pan": 50},
            {"op": "set_track_mute", "track_id": "track-002", "mute": True},
        ],
        now="2026-05-26T00:00:00+00:00",
    )

    result = apply_patch_and_render_plan(state, patch, plan, now="2026-05-26T00:00:01+00:00")

    assert result.plan.tracks[0].notes[0].velocity < plan.tracks[0].notes[0].velocity
    assert result.plan.tracks[0].notes[1].velocity < result.plan.tracks[0].notes[0].velocity
    assert result.track_volumes[1] == 0
    assert result.track_pans[0] > 64


def test_mix_patch_rejects_out_of_range_values(tmp_path: Path) -> None:
    plan = _plan()
    midi_path = tmp_path / "song.mid"
    render_midi(plan, midi_path)
    state = default_mix_state(project_id="project", version_id="v001", plan=plan, midi_path=midi_path, now="2026-05-26T00:00:00+00:00")

    with pytest.raises(MixControlError):
        build_mix_patch(
            patch_id="mixpatch-000001",
            project_id="project",
            version_id="v001",
            state=state,
            plan=plan,
            operations=[{"op": "set_track_volume", "track_id": "track-001", "volume_db": 40}],
            now="2026-05-26T00:00:00+00:00",
        )


def test_midi_renderer_writes_pan_controller(tmp_path: Path) -> None:
    plan = _plan()
    midi_path = tmp_path / "pan.mid"
    render_midi(plan, midi_path, track_pans={0: 96})

    assert b"\xb0\x0a\x60" in midi_path.read_bytes()


def _plan() -> SongPlan:
    return SongPlan(
        title="Mix Test",
        key="C",
        tempo_bpm=120,
        meter="4/4",
        sections=[
            SongSection("verse", 1, 2, ["C"]),
            SongSection("chorus", 3, 3, ["F"]),
        ],
        tracks=[
            TrackPlan("melody", "lead", [NoteEvent(64, 0, 1, 100), NoteEvent(67, 8, 1, 100)]),
            TrackPlan("drums", "kit", [NoteEvent(36, 0, 0.25, 100), NoteEvent(38, 8, 0.25, 100)]),
            TrackPlan("chords", "pad", [NoteEvent(60, 0, 4, 80), NoteEvent(65, 8, 4, 80)]),
            TrackPlan("bass", "bass", [NoteEvent(36, 0, 2, 90), NoteEvent(41, 8, 2, 90)]),
        ],
    )
