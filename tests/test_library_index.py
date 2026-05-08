from __future__ import annotations

from pathlib import Path

from song_agent.assets import AssetStore
from song_agent.library_index import (
    LibraryIndexStore,
    build_library_index,
    recommend_library_context,
    search_library,
    tokenize_library_text,
)
from song_agent.references import ReferenceStore


def test_tokenizer_handles_english_chinese_and_redaction() -> None:
    tokens = tokenize_library_text("雨夜 synth hook api_key=sk-secret123456 D:\\Music\\seed.mid")

    assert "synth" in tokens
    assert "hook" in tokens
    assert "雨夜" in tokens
    assert "sk-secret123456" not in tokens
    assert "d:" not in tokens


def test_library_index_extracts_assets_references_and_searches(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    asset_store = AssetStore()
    reference_store = ReferenceStore()
    asset = asset_store.create_asset(
        {
            "asset_type": "motif",
            "name": "Rainy synth hook",
            "description": "A bright rainy hook.",
            "tags": ["rainy", "hook"],
            "style": "synth pop",
            "mood": "melancholic",
            "key": "C",
            "tempo_bpm": 120,
            "quality_score": 90,
            "favorite": True,
            "content": {"notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1, "velocity": 90}]},
        },
        now="2026-05-08T00:00:00+00:00",
    )
    reference, duplicate = reference_store.import_reference(
        {
            "reference_type": "lyrics_text",
            "filename": "hook.txt",
            "title": "Rainy style reference",
            "tags": ["rainy"],
            "content_base64": "UmFpbnkgc3ludGggaG9vaw==",
        },
        now="2026-05-08T00:00:00+00:00",
    )

    index = build_library_index(asset_store, reference_store, now="2026-05-08T00:00:00+00:00")
    result = search_library(index, {"query": "rainy synth hook", "roles": ["hook"], "tempo_bpm": 118, "key": "C"})
    recommended = recommend_library_context(index, {"source": "song_request", "goal": "generate", "song_request": {"style": "synth pop", "theme": "rainy hook", "tempo_bpm": 118, "key": "C"}})

    assert duplicate is False
    assert len(index.items) == 2
    assert result["results"][0]["source_id"] == asset.asset_id
    assert any(item["reason"] == "query_token_match" for item in result["results"][0]["score_breakdown"])
    assert recommended["recommendation"]["context_pack_preview"]["asset_refs"][0]["asset_id"] == asset.asset_id
    assert recommended["recommendation"]["context_pack_preview"]["reference_refs"][0]["reference_id"] == reference.reference_id


def test_library_index_store_rebuild_persists_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    asset_store = AssetStore()
    reference_store = ReferenceStore()
    asset_store.create_asset(
        {
            "asset_type": "bass_pattern",
            "name": "Warm bass",
            "content": {"notes": [{"pitch": 36, "start_beat": 0, "duration_beats": 1}]},
        }
    )

    store = LibraryIndexStore()
    index = store.rebuild(asset_store, reference_store, now="2026-05-08T00:00:00+00:00")
    loaded = store.read_index()

    assert index.summary()["item_count"] == 1
    assert loaded.items[0].item_id == "asset:asset-001"


def test_library_search_tie_break_prefers_newer_items(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    asset_store = AssetStore()
    reference_store = ReferenceStore()
    old_asset = asset_store.create_asset(
        {
            "asset_type": "motif",
            "name": "Shared hook",
            "tags": ["shared", "hook"],
            "content": {"notes": [{"pitch": 60, "start_beat": 0, "duration_beats": 1}]},
        },
        now="2026-05-01T00:00:00+00:00",
    )
    new_asset = asset_store.create_asset(
        {
            "asset_type": "motif",
            "name": "Shared hook",
            "tags": ["shared", "hook"],
            "content": {"notes": [{"pitch": 64, "start_beat": 0, "duration_beats": 1}]},
        },
        now="2026-05-08T00:00:00+00:00",
    )

    index = build_library_index(asset_store, reference_store, now="2026-05-08T00:00:00+00:00")
    result = search_library(index, {"query": "shared hook", "limit": 2})

    assert [item["source_id"] for item in result["results"]] == [new_asset.asset_id, old_asset.asset_id]
