from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.assets import (
    AssetStore,
    apply_asset_refs_to_plan,
    asset_audio_path,
    asset_midi_path,
    extract_assets_from_song_plan,
    resolve_asset_refs,
)
from song_agent.renderers.audio import RendererConfig
from song_agent.schemas.song import SongRequest


def plan():
    return deterministic_compose(
        SongRequest.from_dict(
            {
                "title": "Asset Song",
                "language": "English",
                "style": "synth pop",
                "theme": "asset tests",
            }
        )
    )


def motif_payload() -> dict[str, object]:
    return {
        "asset_type": "motif",
        "name": "test motif",
        "tags": ["chorus", "hook"],
        "style": "synth pop",
        "key": "C major",
        "tempo_bpm": 100,
        "duration_beats": 8,
        "source": {"source_type": "manual"},
        "content": {
            "kind": "motif",
            "rhythm_pattern": [1.0, 1.0, 0.5, 0.5],
            "pitch_intervals": [0, 3, 5, 7],
            "anchor_pitch": 64,
        },
    }


def test_asset_store_creates_reads_filters_and_deletes(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / ".musicforge" / "assets")
    asset = store.create_asset(motif_payload(), now="2026-05-07T00:00:00Z")

    assert asset.asset_id == "asset-001"
    assert store.read_asset("asset-001").name == "test motif"
    assert store.list_assets(filters={"q": "motif"})[0].asset_id == "asset-001"
    assert store.list_assets(filters={"type": "motif"})[0].asset_id == "asset-001"
    assert store.list_assets(filters={"tag": "chorus"})[0].asset_id == "asset-001"

    updated = store.update_asset("asset-001", {"favorite": True, "tags": ["saved"]})
    assert updated.favorite is True
    assert store.list_assets(filters={"favorite": "1"})[0].tags == ["saved"]

    hidden = store.hide_asset("asset-001")
    assert hidden.hidden is True
    assert store.list_assets() == []
    assert store.list_assets(include_hidden=True)[0].asset_id == "asset-001"
    assert store.hide_asset("asset-001", hidden=False).hidden is False

    store.delete_asset("asset-001")
    assert store.list_assets(include_hidden=True) == []


def test_asset_store_rejects_bad_payloads_and_symlink_delete(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / ".musicforge" / "assets")

    with pytest.raises(ValueError, match="Unsupported asset_type"):
        store.create_asset({**motif_payload(), "asset_type": "bad"})
    with pytest.raises(ValueError, match="blocked field"):
        store.create_asset({**motif_payload(), "content": {"api_key": "secret"}})
    with pytest.raises(ValueError, match="at most 1024"):
        store.create_asset({**motif_payload(), "content": {"kind": "motif", "notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1}] * 1025}})

    store.root.mkdir(parents=True, exist_ok=True)
    if hasattr(Path, "symlink_to"):
        target = tmp_path / "outside"
        target.mkdir()
        link = store.root / "asset-001"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            return
        with pytest.raises(ValueError, match="symlink"):
            store.delete_asset("asset-001")


def test_extract_assets_from_song_plan_records_source_hash() -> None:
    song_plan = plan()
    payloads = extract_assets_from_song_plan(
        song_plan,
        {"source_type": "job", "job_id": "job-001", "style": "synth pop"},
        {"asset_types": ["motif", "chord_progression", "drum_pattern", "bass_pattern"], "section_name": "chorus", "tags": ["asset"]},
    )

    assert [payload["asset_type"] for payload in payloads] == ["motif", "chord_progression", "drum_pattern", "bass_pattern"]
    assert payloads[0]["content"]["pitch_intervals"]
    assert payloads[1]["content"]["chords"] == ["Cmaj7", "Am7", "Dm7", "G7"]
    assert payloads[2]["content"]["notes"]
    assert payloads[3]["content"]["notes"]
    assert payloads[0]["source"]["song_plan_sha256"]


def test_extract_assets_rejects_missing_section_or_track() -> None:
    song_plan = plan()
    with pytest.raises(ValueError, match="Section not found"):
        extract_assets_from_song_plan(song_plan, {"source_type": "job"}, {"asset_types": ["motif"], "section_name": "missing"})
    with pytest.raises(ValueError, match="Track not found"):
        extract_assets_from_song_plan(song_plan, {"source_type": "job"}, {"asset_types": ["motif"], "track_name": "missing"})


def test_asset_midi_and_audio_preview(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / ".musicforge" / "assets")
    asset = store.create_asset(motif_payload())
    midi_asset = store.render_asset_midi(asset.asset_id)
    midi_path = asset_midi_path(store.asset_dir(asset.asset_id))

    assert midi_asset.preview["midi_status"] == "completed"
    assert midi_asset.preview["midi_url"] == "/api/assets/asset-001/midi"
    assert midi_path.read_bytes().startswith(b"MThd")

    def fake_runner(cmd, capture_output, text, timeout, shell):
        wav_path = Path(cmd[cmd.index("-F") + 1])
        wav_path.write_bytes(b"RIFFfakeWAVE")
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    from song_agent import assets as assets_module

    soundfont = tmp_path / "soundfont.sf2"
    soundfont.write_bytes(b"sf2")
    original = assets_module.render_audio
    try:
        assets_module.render_audio = lambda midi, wav, cfg: original(midi, wav, cfg, runner=fake_runner)
        audio_asset = store.render_asset_audio(asset.asset_id, RendererConfig(soundfont_path=str(soundfont)))
    finally:
        assets_module.render_audio = original

    assert audio_asset.preview["audio_status"] == "completed"
    assert audio_asset.preview["audio_url"] == "/api/assets/asset-001/audio"
    assert asset_audio_path(store.asset_dir(asset.asset_id)).read_bytes().startswith(b"RIFF")


def test_asset_refs_resolve_and_mark_used(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / ".musicforge" / "assets")
    asset = store.create_asset(motif_payload())
    refs = resolve_asset_refs(store, [{"asset_id": asset.asset_id, "role": "motif_reference", "strength": 0.8}])

    assert refs[0]["asset_id"] == asset.asset_id
    assert refs[0]["content_summary"]["note_count"] == 0

    store.mark_used([{"asset_id": asset.asset_id, "role": "motif_reference", "strength": 0.8}], {"usage_type": "test"})
    assert store.read_asset(asset.asset_id).usage_count == 1

    store.hide_asset(asset.asset_id)
    with pytest.raises(ValueError, match="Hidden assets"):
        resolve_asset_refs(store, [{"asset_id": asset.asset_id}])


def test_apply_asset_refs_updates_chorus_chords_and_melody(tmp_path: Path) -> None:
    store = AssetStore(tmp_path / ".musicforge" / "assets")
    song_plan = plan()
    chord_asset = store.create_asset(
        {
            "asset_type": "chord_progression",
            "name": "borrowed chords",
            "key": song_plan.key,
            "tempo_bpm": song_plan.tempo_bpm,
            "duration_beats": 16,
            "content": {"kind": "chord_progression", "section_name": "chorus", "chords": ["Fmaj7", "G7", "Am7", "Cmaj7"]},
        }
    )
    motif_asset = store.create_asset(motif_payload())

    updated = apply_asset_refs_to_plan(
        song_plan,
        store,
        [
            {"asset_id": chord_asset.asset_id, "role": "chord_reference", "strength": 1.0},
            {"asset_id": motif_asset.asset_id, "role": "motif_reference", "strength": 1.0},
        ],
    )

    chorus = next(section for section in updated.sections if section.name == "chorus")
    melody = next(track for track in updated.tracks if track.name == "melody")
    chorus_start = (chorus.start_bar - 1) * 4
    chorus_notes = [note for note in melody.notes if note.start_beat >= chorus_start and note.start_beat < chorus_start + 4]
    assert chorus.chords == ["Fmaj7", "G7", "Am7", "Cmaj7"]
    assert [note.pitch for note in chorus_notes[:4]] == [64, 67, 69, 71]
