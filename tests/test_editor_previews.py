from __future__ import annotations

import os

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.schemas.song import SongRequest
from song_agent.song_editor import EditorPreviewStore, apply_editor_patch, build_editor_state


def sample_plan():
    return deterministic_compose(
        SongRequest(
            title="Preview History",
            language="English",
            style="synth pop",
            theme="history",
            tempo_bpm=120,
            key="C",
        )
    )


def make_preview(store: EditorPreviewStore, plan, *, label: str, now: str):
    state = build_editor_state(plan)
    result = apply_editor_patch(
        plan,
        {
            "schema_version": 1,
            "base_plan_hash": state["base_plan_hash"],
            "label": label,
            "operations": [{"op": "set_section_lyrics", "section_id": "section-001", "lyrics": f"{label} sk-secret-token"}],
        },
    )
    return store.create_preview(
        project_id="project-001",
        parent_version_id="v001",
        parent_job_id="job-001",
        parent_plan=plan,
        patch=result.patch,
        result=result,
        now=now,
    )[0]


def test_preview_history_lists_newest_first_and_summarizes_patch(tmp_path):
    plan = sample_plan()
    store = EditorPreviewStore(tmp_path / "project-001")
    first = make_preview(store, plan, label="first", now="2026-05-01T00:00:00+00:00")
    second = make_preview(store, plan, label="second", now="2026-05-08T00:00:00+00:00")

    previews = store.list_previews()
    summary = store.read_patch_summary(first.preview_id)
    full = store.read_patch_summary(first.preview_id, include_operations=True)

    assert [preview.preview_id for preview in previews] == [second.preview_id, first.preview_id]
    assert summary["operation_counts"] == {"set_section_lyrics": 1}
    assert "operations" not in summary
    assert "operations" in full
    assert "sk-secret-token" not in str(summary)
    assert "sk-secret-token" not in str(full)


def test_preview_cleanup_keeps_applied_and_latest(tmp_path):
    plan = sample_plan()
    store = EditorPreviewStore(tmp_path / "project-001")
    old = make_preview(store, plan, label="old", now="2026-04-01T00:00:00+00:00")
    applied = make_preview(store, plan, label="applied", now="2026-04-02T00:00:00+00:00")
    newer = [
        make_preview(store, plan, label=f"new-{index}", now=f"2026-05-{index + 1:02d}T00:00:00+00:00")
        for index in range(5)
    ]
    store.mark_applied(applied.preview_id, version_id="v002", job_id="job-002", now="2026-04-03T00:00:00+00:00")

    result = store.cleanup_previews(delete_unapplied_older_than_days=7, keep_latest=5, now="2026-05-20T00:00:00+00:00")
    remaining = {preview.preview_id for preview in store.list_previews()}

    assert old.preview_id in result["deleted"]
    assert old.preview_id not in remaining
    assert applied.preview_id in remaining
    assert {preview.preview_id for preview in newer}.issubset(remaining)


def test_preview_cleanup_rejects_symlink(tmp_path):
    plan = sample_plan()
    store = EditorPreviewStore(tmp_path / "project-001")
    old = make_preview(store, plan, label="old", now="2026-04-01T00:00:00+00:00")
    preview_dir = store.preview_dir(old.preview_id)
    target = tmp_path / "outside"
    target.mkdir()
    for child in preview_dir.iterdir():
        child.unlink()
    preview_dir.rmdir()
    try:
        os.symlink(target, preview_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink is not available on this platform")

    with pytest.raises(ValueError, match="symlink"):
        store.cleanup_previews(delete_unapplied_older_than_days=7, keep_latest=5, now="2026-05-20T00:00:00+00:00")
