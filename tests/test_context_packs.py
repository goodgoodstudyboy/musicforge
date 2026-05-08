from __future__ import annotations

import json
from pathlib import Path

import pytest

from song_agent.assets import AssetStore
from song_agent.context_packs import ContextPackStaleError, ContextPackStore
from song_agent.references import ReferenceStore


def create_asset(store: AssetStore):
    return store.create_asset(
        {
            "asset_type": "motif",
            "name": "Context Motif",
            "tags": ["context"],
            "content": {"notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1}]},
        },
        now="2026-05-08T00:00:00+00:00",
    )


def create_reference(store: ReferenceStore):
    return store.import_reference(
        {
            "reference_type": "style_note",
            "filename": "context.md",
            "title": "Context Reference",
            "content_base64": "Q29udGV4dCBub3Rl",
            "tags": ["context"],
        },
        now="2026-05-08T00:00:00+00:00",
    )[0]


def test_context_pack_create_apply_and_redact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    asset_store = AssetStore()
    reference_store = ReferenceStore()
    asset = create_asset(asset_store)
    reference = create_reference(reference_store)

    store = ContextPackStore()
    pack = store.create_pack(
        {
            "name": "Pack api_key=sk-secret123456",
            "description": "D:\\Music\\secret.mid",
            "asset_refs": [{"asset_id": asset.asset_id, "role": "hook", "strength": 0.9}],
            "reference_refs": [{"reference_id": reference.reference_id, "role": "style", "strength": 0.5}],
        },
        asset_store=asset_store,
        reference_store=reference_store,
        now="2026-05-08T00:00:00+00:00",
    )
    applied = store.apply_preview(pack.pack_id, asset_store=asset_store, reference_store=reference_store)

    serialized = json.dumps(pack.to_dict(), ensure_ascii=False)
    assert pack.pack_id == "pack-001"
    assert applied["asset_refs"][0]["asset_id"] == asset.asset_id
    assert applied["reference_refs"][0]["reference_id"] == reference.reference_id
    assert "sk-secret123456" not in serialized
    assert "D:\\Music" not in serialized


def test_context_pack_rejects_hidden_and_stale_sources(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    asset_store = AssetStore()
    reference_store = ReferenceStore()
    asset = create_asset(asset_store)
    reference = create_reference(reference_store)
    store = ContextPackStore()
    pack = store.create_pack(
        {
            "asset_refs": [{"asset_id": asset.asset_id}],
            "reference_refs": [{"reference_id": reference.reference_id}],
        },
        asset_store=asset_store,
        reference_store=reference_store,
    )

    asset_store.hide_asset(asset.asset_id, True)
    with pytest.raises(ContextPackStaleError):
        store.apply_preview(pack.pack_id, asset_store=asset_store, reference_store=reference_store)

    asset_store.hide_asset(asset.asset_id, False)
    path = Path(".musicforge") / "assets" / asset.asset_id / "asset.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["content"]["notes"].append({"pitch": 64, "start_beat": 1, "duration_beats": 1})
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ContextPackStaleError):
        store.apply_preview(pack.pack_id, asset_store=asset_store, reference_store=reference_store)


def test_context_pack_delete_rejects_symlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    store = ContextPackStore()
    root = Path(".musicforge") / "context-packs"
    root.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    link = root / "pack-001"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        return

    with pytest.raises(ValueError, match="symlink"):
        store.delete_pack("pack-001")
