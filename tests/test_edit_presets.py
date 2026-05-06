from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.edit_presets import EditPresetStore, merge_preset_intent
from song_agent.schemas.song import SongRequest


def plan():
    return deterministic_compose(
        SongRequest.from_dict(
            {
                "title": "Preset Song",
                "language": "English",
                "style": "synth pop",
                "theme": "presets",
            }
        )
    )


def test_builtin_presets_load_and_include_safe_harmony_chords(tmp_path: Path) -> None:
    store = EditPresetStore(tmp_path / ".musicforge" / "edit-presets.json")

    data = store.to_response()
    brighter = store.get_preset("brighter-chorus-harmony")

    assert data["built_in_count"] >= 7
    assert data["user_count"] == 0
    assert brighter.built_in is True
    assert brighter.payload["chords"] == ["Cmaj7", "Am7", "Fmaj7", "G7"]


def test_user_preset_save_update_delete_and_reset(tmp_path: Path) -> None:
    path = tmp_path / ".musicforge" / "edit-presets.json"
    store = EditPresetStore(path)

    saved = store.save_preset(
        {
            "preset_id": "custom-lift",
            "name": "Custom Lift",
            "description": "Lift the hook",
            "edit_type": "section_energy",
            "strength": 0.7,
            "target_defaults": {"section_role": "chorus"},
            "preserve": ["tempo", "key"],
        }
    )
    updated = store.save_preset({"name": "Custom Lift 2", "edit_type": "section_energy", "strength": 0.5}, preset_id="custom-lift")

    assert saved.preset_id == "custom-lift"
    assert updated.name == "Custom Lift 2"
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip().startswith("{")
    assert store.to_response()["user_count"] == 1

    store.delete_preset("custom-lift")
    assert store.to_response()["user_count"] == 0

    store.save_preset({"preset_id": "custom-lift", "name": "Custom Lift", "edit_type": "section_energy"})
    store.reset()
    assert not path.exists()


def test_preset_validation_rejects_bad_id_type_path_and_chord(tmp_path: Path) -> None:
    store = EditPresetStore(tmp_path / ".musicforge" / "edit-presets.json")

    with pytest.raises(ValueError, match="preset_id"):
        store.save_preset({"preset_id": "Bad ID", "name": "Bad", "edit_type": "section_energy"})
    with pytest.raises(ValueError, match="edit_type"):
        store.save_preset({"preset_id": "bad-type", "name": "Bad", "edit_type": "provider_magic"})
    with pytest.raises(ValueError, match="path"):
        store.save_preset({"preset_id": "bad-path", "name": "Bad", "edit_type": "section_energy", "payload": {"path": "C:/secret"}})
    with pytest.raises(ValueError, match="Unsupported chord names"):
        store.save_preset(
            {
                "preset_id": "bad-chord",
                "name": "Bad",
                "edit_type": "section_harmony",
                "payload": {"chords": ["Hmaj7"]},
            }
        )
    with pytest.raises(ValueError, match="overwrite built-in"):
        store.save_preset({"preset_id": "lift-final-chorus", "name": "Bad", "edit_type": "section_energy"})
    with pytest.raises(PermissionError, match="Built-in"):
        store.delete_preset("lift-final-chorus")


def test_merge_preset_intent_resolves_targets_and_allows_explicit_override(tmp_path: Path) -> None:
    store = EditPresetStore(tmp_path / ".musicforge" / "edit-presets.json")
    preset = store.get_preset("brighter-chorus-harmony")

    merged = merge_preset_intent(
        preset,
        {
            "intent": {
                "strength": 4,
                "target": {"section_name": "verse"},
                "payload": {"chords": ["G7", "Cmaj7"]},
            },
            "name": "Preset Override",
        },
        plan(),
    )

    assert merged["edit_type"] == "section_harmony"
    assert merged["target"]["section_name"] == "verse"
    assert merged["target"]["field"] == "chords"
    assert merged["payload"]["chords"] == ["G7", "Cmaj7"]
    assert merged["strength"] == 4
    assert merged["name"] == "Preset Override"
