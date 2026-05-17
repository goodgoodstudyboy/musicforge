from __future__ import annotations

from pathlib import Path

from song_agent.distribution_layout import build_distribution_layout_plan


def test_distribution_layout_defaults_and_hash_are_deterministic(tmp_path: Path) -> None:
    export_dir = _release_export(tmp_path)

    plan = _plan(export_dir=export_dir)
    repeat = _plan(export_dir=export_dir)

    assert plan["summary"]["status"] == "passed"
    assert _entry(plan, "audio:track-001")["path"] == "audio/01-layout-song.wav"
    assert _entry(plan, "lyrics:track-001")["path"] == "lyrics/01-layout-song.txt"
    assert _entry(plan, "artwork:cover")["path"] == "artwork/cover.png"
    assert plan["layout_hash"] == repeat["layout_hash"]
    assert "C:\\" not in str(plan)


def test_distribution_layout_preserves_custom_subdirectories(tmp_path: Path) -> None:
    export_dir = _release_export(tmp_path)
    template = _template(
        file_naming={
            "audio": "tracks/disc-{disc_number}/{track_number:02d}-{slug_title}.{ext}",
            "lyrics": "text/{language}/{track_number:02d}-{slug_title}.txt",
            "artwork": "artwork/{release_slug}-cover.{ext}",
        }
    )

    plan = _plan(export_dir=export_dir, template=template)

    assert plan["summary"]["status"] == "passed"
    assert _entry(plan, "audio:track-001")["path"] == "tracks/disc-1/01-layout-song.wav"
    assert _entry(plan, "lyrics:track-001")["path"] == "text/english/01-layout-song.txt"
    assert _entry(plan, "artwork:cover")["path"] == "artwork/layout-release-cover.png"


def test_distribution_layout_rejects_bad_variables_and_paths(tmp_path: Path) -> None:
    export_dir = _release_export(tmp_path)

    artwork_track_var = _plan(export_dir=export_dir, template=_template(file_naming={"artwork": "artwork/{slug_title}.{ext}"}))
    unknown = _plan(export_dir=export_dir, template=_template(file_naming={"audio": "audio/{unknown}.wav"}))
    parent = _plan(export_dir=export_dir, template=_template(file_naming={"audio": "../x.wav"}))
    windows = _plan(export_dir=export_dir, template=_template(file_naming={"audio": r"C:\x.wav"}))
    backslash = _plan(export_dir=export_dir, template=_template(file_naming={"audio": r"audio\bad.wav"}))

    assert artwork_track_var["summary"]["status"] == "failed"
    assert any(error["check_id"] == "file_naming_artwork_variables" for error in artwork_track_var["errors"])
    assert unknown["summary"]["status"] == "failed"
    assert any(error["check_id"] == "file_naming_audio_variables" for error in unknown["errors"])
    assert parent["summary"]["status"] == "failed"
    assert windows["summary"]["status"] == "failed"
    assert backslash["summary"]["status"] == "failed"


def test_distribution_layout_appends_collision_index(tmp_path: Path) -> None:
    export_dir = _release_export(tmp_path, track_count=2)
    template = _template(file_naming={"audio": "audio/song.{ext}"})

    plan = _plan(export_dir=export_dir, template=template, track_count=2)
    entries = [entry for entry in plan["entries"] if entry["kind"] == "audio"]

    assert plan["summary"]["status"] == "warning"
    assert entries[0]["path"] == "audio/song.wav"
    assert entries[1]["path"] == "audio/song-2.wav"
    assert entries[1]["collision"] is True
    assert plan["summary"]["collision_count"] == 1


def test_distribution_layout_fails_fixed_sidecar_collision(tmp_path: Path) -> None:
    export_dir = _release_export(tmp_path)
    template = _template(file_naming={"audio": "distribution-manifest.json"})

    plan = _plan(export_dir=export_dir, template=template)

    assert plan["summary"]["status"] == "failed"
    assert any(error["check_id"] == "layout_reserved_collision" for error in plan["errors"])


def _release_export(tmp_path: Path, *, track_count: int = 1) -> Path:
    export_dir = tmp_path / "release-export"
    for index in range(1, track_count + 1):
        track_dir = export_dir / "tracks" / f"{index:02d}-layout-song"
        track_dir.mkdir(parents=True, exist_ok=True)
        (track_dir / "song.wav").write_bytes(b"RIFF\x04\x00\x00\x00WAVE")
    lyrics_dir = export_dir / "lyrics"
    lyrics_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, track_count + 1):
        (lyrics_dir / f"{index:02d}-layout-song.txt").write_text("Clean lyric\n", encoding="utf-8")
    return export_dir


def _plan(*, export_dir: Path, template: dict | None = None, track_count: int = 1) -> dict:
    return build_distribution_layout_plan(
        release_id="release-000001",
        target={"target_id": "target-000001", "profile_id": "demo_pitch", "options": {"require_artwork": True}},
        release={"release_id": "release-000001", "name": "Layout Release", "language": "English"},
        release_manifest={
            "tracks": [
                {
                    "track_id": f"track-{index:03d}",
                    "disc_number": 1,
                    "track_number": index,
                    "title": "Layout Song",
                    "directory": f"tracks/{index:02d}-layout-song",
                }
                for index in range(1, track_count + 1)
            ]
        },
        release_metadata={
            "release": {"title": "Layout Release", "language": "English", "upc": "123456789012"},
            "tracks": [
                {
                    "track_id": f"track-{index:03d}",
                    "disc_number": 1,
                    "track_number": index,
                    "title": "Layout Song",
                    "language": "English",
                    "isrc": f"USABC26000{index:02d}",
                    "lyrics": "Clean lyric",
                }
                for index in range(1, track_count + 1)
            ],
        },
        template=template,
        artwork={"artwork_id": "artwork-001", "stored_filename": "cover.png"},
        release_export_dir=export_dir,
    )


def _template(*, file_naming: dict[str, str]) -> dict:
    return {
        "template_pack_id": "tpl-000001",
        "template_hash": "template-hash",
        "slug": "layout-template",
        "name": "Layout Template",
        "source": "user",
        "rules": {"require_artwork": True},
        "file_naming": file_naming,
    }


def _entry(plan: dict, entry_id: str) -> dict:
    return next(entry for entry in plan["entries"] if entry["entry_id"] == entry_id)
