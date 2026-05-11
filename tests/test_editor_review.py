from __future__ import annotations

import pytest

from song_agent.editor_review import (
    add_marker,
    apply_review_patch,
    audition_asset_payload,
    review_board,
    review_summary,
)
from tests.test_editor_audition import demo_song_plan


def test_review_patch_sanitizes_sensitive_notes_and_tags() -> None:
    review = apply_review_patch(
        {},
        {
            "rating": 5,
            "status": "keep",
            "favorite": True,
            "notes": r"good hook api_key=sk-secret-value C:\Users\demo\song.wav",
            "tags": ["Hook", "hook", "token=ghp_123456789012345678901234567890123456"],
        },
        duration_beats=16,
        now="2026-05-12T00:00:00+00:00",
    )

    assert review["rating"] == 5
    assert review["favorite"] is True
    assert "sk-secret-value" not in review["notes"]
    assert "C:\\Users" not in review["notes"]
    assert review["tags"] == ["Hook", "[REDACTED]"]


def test_marker_lifecycle_validates_duration_and_summary() -> None:
    review = add_marker({}, {"beat": 4, "kind": "hook", "label": "hook sk-secret-value"}, duration_beats=8, now="2026-05-12T00:00:00+00:00")

    assert review["markers"][0]["marker_id"] == "marker-001"
    assert "sk-secret-value" not in review["markers"][0]["label"]
    assert review_summary([{"review": review}])["marker_count"] == 1

    with pytest.raises(ValueError, match="within audition duration"):
        add_marker(review, {"beat": 9, "kind": "issue"}, duration_beats=8)


def test_review_board_filters_and_sorts_rating() -> None:
    rows = [
        {"audition_id": "audition-001", "source": "preview", "track_mode": "all", "range": {"mode": "full_song"}, "note_count": 1, "duration_beats": 4, "created_at": "1", "updated_at": "1", "review": {"rating": 2, "status": "maybe"}},
        {"audition_id": "audition-002", "source": "preview", "track_mode": "solo", "range": {"mode": "section"}, "note_count": 2, "duration_beats": 8, "created_at": "2", "updated_at": "2", "review": {"rating": 5, "status": "keep", "favorite": True}},
    ]

    board = review_board(rows, {"min_rating": "3", "sort": "rating"})

    assert board["summary"]["audition_count"] == 1
    assert board["summary"]["best_rating"] == 5
    assert board["auditions"][0]["audition_id"] == "audition-002"


def test_audition_asset_payload_uses_plan_not_paths() -> None:
    plan = demo_song_plan()
    manifest = {
        "audition_id": "audition-001",
        "project_id": "project-001",
        "preview_id": "preview-001",
        "parent_version_id": "v001",
        "parent_job_id": "job-001",
        "source": "preview",
        "source_plan_hash": "abc",
        "range": {"mode": "section", "section_name": plan.sections[0].name, "start_beat": 0, "end_beat": 8},
        "track_mode": "solo",
        "track_ids": ["track-001"],
        "duration_beats": 8,
        "review": {"rating": 5, "notes": r"token=sk-secret-value D:\Music\demo.wav"},
    }

    payload = audition_asset_payload(plan, manifest, {"asset_type": "motif", "track_id": "track-001", "name": "Hook Asset"})
    serialized = str(payload)

    assert payload["asset_type"] == "motif"
    assert payload["content"]["notes"]
    assert payload["source"]["source_type"] == "editor_audition"
    assert "sk-secret-value" not in serialized
    assert "D:\\Music" not in serialized
