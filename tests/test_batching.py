import json
from pathlib import Path

import pytest

from song_agent.batching import BatchStore, parse_batch_csv


CSV_TEXT = """title,language,style,theme,duration_seconds,tempo_bpm,key,vocal_mode,lyrics,generation_mode,pipeline_mode
Batch Song,English,synth pop,city lights,120,118,C,guide_melody,hello,local,multinode
Second Song,English,folk,home,,,,,,provider,single
"""


def test_parse_batch_csv_builds_requests_with_defaults() -> None:
    items = parse_batch_csv(CSV_TEXT, generation_mode="local", pipeline_mode="multinode")

    assert len(items) == 2
    assert items[0].index == 1
    assert items[0].request["title"] == "Batch Song"
    assert items[0].request["duration_seconds"] == 120
    assert items[0].request["tempo_bpm"] == 118
    assert items[0].request["generation_mode"] == "local"
    assert items[0].request["pipeline_mode"] == "multinode"
    assert items[1].request["duration_seconds"] == 180
    assert "tempo_bpm" not in items[1].request
    assert items[1].request["generation_mode"] == "provider"
    assert items[1].request["pipeline_mode"] == "single"


def test_parse_batch_csv_rejects_empty_csv() -> None:
    with pytest.raises(ValueError, match="CSV is empty"):
        parse_batch_csv("")


def test_parse_batch_csv_rejects_missing_required_column() -> None:
    with pytest.raises(ValueError, match="missing required columns: theme"):
        parse_batch_csv("title,language,style\nSong,English,pop\n")


def test_parse_batch_csv_rejects_row_missing_required_value() -> None:
    with pytest.raises(ValueError, match="CSV row 2 is missing required field: theme"):
        parse_batch_csv("title,language,style,theme\nSong,English,pop,\n")


def test_parse_batch_csv_validates_duration_and_tempo_ranges() -> None:
    with pytest.raises(ValueError, match="duration_seconds must be between 30 and 600"):
        parse_batch_csv("title,language,style,theme,duration_seconds\nSong,English,pop,sky,20\n")

    with pytest.raises(ValueError, match="tempo_bpm must be between 40 and 240"):
        parse_batch_csv("title,language,style,theme,tempo_bpm\nSong,English,pop,sky,260\n")


def test_import_csv_creates_unique_batch_dirs(tmp_path: Path) -> None:
    store = BatchStore(tmp_path / "batches")

    first = store.import_csv(name="Same Batch", csv_text=CSV_TEXT, max_concurrency=2)
    second = store.import_csv(name="Same Batch", csv_text=CSV_TEXT)

    assert first.state.batch_id == "same-batch"
    assert second.state.batch_id == "same-batch-2"
    assert (tmp_path / "batches" / "same-batch" / "batch.json").exists()
    assert first.state.total_count == 2
    assert first.state.queued_count == 2
    assert first.state.max_concurrency == 2


def test_list_batches_honors_hidden_flag(tmp_path: Path) -> None:
    store = BatchStore(tmp_path / "batches")
    batch = store.import_csv(name="Hidden Batch", csv_text=CSV_TEXT)

    store.hide_batch(batch.state.batch_id, True)

    assert store.list_batches() == []
    assert [doc.state.batch_id for doc in store.list_batches(include_hidden=True)] == [batch.state.batch_id]


def test_export_batch_writes_report(tmp_path: Path) -> None:
    store = BatchStore(tmp_path / "batches")
    batch = store.import_csv(name="Export Batch", csv_text=CSV_TEXT)
    batch.items[0].status = "completed"
    batch.items[0].job_id = "job-1"
    batch.items[0].output_dir = "runs/job-1"
    batch.items[0].audio_status = "completed"
    batch.items[0].audio_path = str(Path("runs/job-1") / "renders" / "song.wav")
    batch.items[0].stem_status = "completed"
    batch.items[0].stem_manifest_path = str(Path("runs/job-1") / "stems" / "manifest.json")
    batch.items[0].stem_count = 4
    batch.items[0].stem_audio_completed_count = 4
    store.save_batch(batch)

    export = store.export_batch(batch.state.batch_id)

    assert export["batch"]["batch_id"] == batch.state.batch_id
    assert export["items"][0]["song_plan"] == str(Path("runs/job-1") / "data" / "song-plan.json")
    assert export["items"][0]["midi"] == str(Path("runs/job-1") / "renders" / "song.mid")
    assert export["items"][0]["audio_status"] == "completed"
    assert export["items"][0]["audio"] == str(Path("runs/job-1") / "renders" / "song.wav")
    assert export["items"][0]["stem_status"] == "completed"
    assert export["items"][0]["stem_manifest"] == str(Path("runs/job-1") / "stems" / "manifest.json")
    assert export["items"][0]["stem_count"] == 4
    assert export["items"][0]["stem_audio_completed_count"] == 4
    export_path = tmp_path / "batches" / batch.state.batch_id / "export.json"
    assert json.loads(export_path.read_text(encoding="utf-8"))["items"][0]["job_id"] == "job-1"


def test_batch_item_loads_stem_defaults_for_old_json(tmp_path: Path) -> None:
    store = BatchStore(tmp_path / "batches")
    batch = store.import_csv(name="Compat Batch", csv_text=CSV_TEXT)
    batch_dir = tmp_path / "batches" / batch.state.batch_id
    items = json.loads((batch_dir / "items.json").read_text(encoding="utf-8"))
    for item in items["items"]:
        item.pop("stem_status", None)
        item.pop("stem_manifest_path", None)
        item.pop("stem_count", None)
        item.pop("stem_audio_completed_count", None)
        item.pop("stem_error", None)
    (batch_dir / "items.json").write_text(json.dumps(items), encoding="utf-8")

    loaded = store.get_batch(batch.state.batch_id)

    assert loaded.items[0].stem_status == "not_started"
    assert loaded.items[0].stem_count == 0


def test_delete_batch_refuses_paths_outside_root(tmp_path: Path) -> None:
    store = BatchStore(tmp_path / "batches")

    with pytest.raises(ValueError, match="outside the batch root"):
        store.ensure_batch_dir_is_safe(tmp_path / "other")


def test_delete_batch_removes_only_batch_dir(tmp_path: Path) -> None:
    store = BatchStore(tmp_path / "batches")
    batch = store.import_csv(name="Delete Batch", csv_text=CSV_TEXT)
    batch_dir = tmp_path / "batches" / batch.state.batch_id

    store.delete_batch(batch.state.batch_id)

    assert not batch_dir.exists()
    assert (tmp_path / "batches").exists()
