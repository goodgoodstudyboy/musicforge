from dataclasses import replace

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.schemas.song import SongRequest
from song_agent.stems import (
    build_stem_manifest,
    find_stem,
    read_stem_manifest,
    render_stem_midis,
    stem_midi_path,
)
from tests.test_midi_renderer import parse_midi


def request() -> SongRequest:
    return SongRequest(
        title="Stem Song",
        language="en",
        style="pop",
        theme="stem export",
        tempo_bpm=120,
    )


def test_build_stem_manifest_derives_safe_unique_ids(tmp_path):
    plan = deterministic_compose(request())
    duplicate_tracks = [plan.tracks[0], replace(plan.tracks[0], instrument="second lead")]
    plan = replace(plan, tracks=[*duplicate_tracks, *plan.tracks[1:]])

    manifest = build_stem_manifest(plan, tmp_path, "job-1", now="2026-05-06T00:00:00Z")

    assert [stem.stem_id for stem in manifest.stems[:2]] == ["melody", "melody-2"]
    assert manifest.stems[0].midi_path == "stems/midi/melody.mid"
    assert manifest.stems[0].audio_path == "stems/audio/melody.wav"
    assert manifest.stems[0].note_count == len(plan.tracks[0].notes)
    assert manifest.stems[-1].role == "drums"
    assert manifest.stems[-1].channel == 9


def test_render_stem_midis_writes_manifest_and_type1_files(tmp_path):
    plan = deterministic_compose(request())

    manifest = render_stem_midis(plan, tmp_path, "job-1", now="2026-05-06T00:00:00Z")

    persisted = read_stem_manifest(tmp_path)
    assert persisted is not None
    assert persisted.to_dict() == manifest.to_dict()
    assert all(stem.midi_exists for stem in manifest.stems)
    assert {stem.stem_id for stem in manifest.stems} == {"melody", "chords", "bass", "drums"}

    for stem in manifest.stems:
        parsed = parse_midi((tmp_path / stem.midi_path).read_bytes())
        assert parsed["format"] == 1
        assert parsed["track_count"] == 2
        assert parsed["ppq"] == 480
        assert 500000 in parsed["tracks"][0]["tempos"]
        assert all(track["has_eot"] for track in parsed["tracks"])
        assert sorted(parsed["tracks"][1]["note_on"]) == sorted(parsed["tracks"][1]["note_off"])
        if stem.stem_id == "drums":
            assert any(channel == 9 for channel, _pitch in parsed["tracks"][1]["note_on"])


def test_render_stem_midis_skips_empty_tracks(tmp_path):
    plan = deterministic_compose(request())
    empty = replace(plan.tracks[0], notes=[])
    plan = replace(plan, tracks=[empty, *plan.tracks[1:]])

    manifest = render_stem_midis(plan, tmp_path, "job-1", now="2026-05-06T00:00:00Z")

    melody = find_stem(manifest, "melody")
    assert melody.audio_status == "skipped"
    assert melody.audio_error == "Track has no notes."
    assert not (tmp_path / melody.midi_path).exists()


def test_stem_path_rejects_path_traversal(tmp_path):
    plan = deterministic_compose(request())
    manifest = render_stem_midis(plan, tmp_path, "job-1", now="2026-05-06T00:00:00Z")

    with pytest.raises(FileNotFoundError):
        stem_midi_path(tmp_path, manifest, "../melody")
