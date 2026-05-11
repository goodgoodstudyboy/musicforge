from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from song_agent.editor_audition import (
    EditorAuditionStore,
    EditorAuditionUnavailableError,
    build_audition_plan,
    render_audition_midi,
)
from song_agent.agent.pipeline import deterministic_compose
from song_agent.schemas.song import SongRequest
from song_agent.song_editor import EditorPreview, song_plan_hash


def test_build_full_song_audition_plan_keeps_notes() -> None:
    plan = demo_song_plan()

    audition, summary = build_audition_plan(plan, range_payload={"mode": "full_song"}, track_mode="all")

    assert audition.title.endswith("Audition")
    assert summary["note_count"] == sum(len(track.notes) for track in plan.tracks)
    assert summary["duration_beats"] == 96
    assert len(audition.tracks) == len(plan.tracks)


def test_section_audition_clips_and_rebases_notes() -> None:
    plan = demo_song_plan()

    audition, summary = build_audition_plan(plan, range_payload={"mode": "section", "section_id": "section-002"}, track_mode="solo", track_ids=["track-001"])

    assert summary["range"]["section_id"] == "section-002"
    assert summary["track_ids"] == ["track-001"]
    assert len(audition.tracks) == 1
    assert all(0 <= note.start_beat < summary["duration_beats"] for note in audition.tracks[0].notes)


def test_custom_audition_clips_note_crossing_boundary() -> None:
    plan = demo_song_plan()

    audition, _summary = build_audition_plan(plan, range_payload={"mode": "custom", "start_beat": 0.25, "end_beat": 0.75}, track_mode="solo", track_ids=["track-001"])

    first = audition.tracks[0].notes[0]
    assert first.start_beat == 0
    assert 0 < first.duration_beats <= 0.5


def test_changed_sections_requires_preview_changes() -> None:
    plan = demo_song_plan()

    with pytest.raises(EditorAuditionUnavailableError, match="no changed sections"):
        build_audition_plan(plan, range_payload={"mode": "changed_sections"}, changed_sections=[])


def test_unknown_track_and_no_notes_are_clear_errors() -> None:
    plan = demo_song_plan()

    with pytest.raises(ValueError, match="Unknown track ids"):
        build_audition_plan(plan, range_payload={"mode": "full_song"}, track_mode="solo", track_ids=["track-999"])

    with pytest.raises(EditorAuditionUnavailableError, match="no notes"):
        build_audition_plan(plan, range_payload={"mode": "full_song"}, track_mode="mute", track_ids=["track-001", "track-002", "track-003", "track-004"])


def test_audition_store_allocates_unique_ids_concurrently(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    plan = demo_song_plan()
    preview = _preview(plan)

    def create_one(index: int) -> str:
        store = EditorAuditionStore(project_dir)
        manifest = store.create_audition(
            project_id="project-001",
            preview=preview,
            source_plan=plan,
            payload={"source": "preview", "label": f"take {index}", "range": {"mode": "full_song"}, "track_mode": "solo", "track_ids": ["track-001"]},
            now="2026-05-12T00:00:00+00:00",
        )
        return manifest.audition_id

    with ThreadPoolExecutor(max_workers=12) as executor:
        ids = list(executor.map(create_one, range(24)))

    assert len(ids) == 24
    assert len(set(ids)) == 24
    assert all((project_dir / "editor-previews" / "preview-001" / "auditions" / audition_id / "audition.json").exists() for audition_id in ids)


def test_audition_midi_renderer_allows_solo_track(tmp_path: Path) -> None:
    plan = demo_song_plan()
    audition, _summary = build_audition_plan(plan, range_payload={"mode": "section", "section_id": "section-001"}, track_mode="solo", track_ids=["track-001"])

    midi_path = render_audition_midi(audition, tmp_path / "solo.mid")

    assert midi_path.read_bytes().startswith(b"MThd")


def test_delete_symlink_audition_is_rejected(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    root = project_dir / "editor-previews" / "preview-001" / "auditions"
    root.mkdir(parents=True)
    target = tmp_path / "target"
    target.mkdir()
    link = root / "audition-001"
    try:
        link.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not available")

    with pytest.raises(ValueError, match="symlink"):
        EditorAuditionStore(project_dir).delete_audition("preview-001", "audition-001")


def _preview(plan) -> EditorPreview:
    return EditorPreview(
        schema_version=1,
        preview_id="preview-001",
        project_id="project-001",
        parent_version_id="v001",
        parent_job_id="job-001",
        base_plan_hash=song_plan_hash(plan),
        status="completed",
        created_at="2026-05-12T00:00:00+00:00",
        updated_at="2026-05-12T00:00:00+00:00",
        changed_sections=["verse"],
        changed_tracks=["melody"],
    )


def demo_song_plan():
    return deterministic_compose(
        SongRequest(
            title="Audition Smoke",
            language="English",
            style="synth pop",
            theme="audition",
            duration_seconds=90,
            tempo_bpm=120,
            key="C",
        )
    )
