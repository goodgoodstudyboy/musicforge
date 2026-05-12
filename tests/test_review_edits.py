from __future__ import annotations

import pytest

from song_agent.editor_audition import EditorAuditionManifest
from song_agent.review_edits import ReviewEditUnavailableError, apply_review_edit, build_review_edit
from tests.test_editor_audition import demo_song_plan


def test_review_notes_bass_too_busy_maps_to_density_reduce() -> None:
    plan = demo_song_plan()
    audition = _audition(plan, review={"rating": 4, "status": "needs_fix", "notes": "bass 太满, chorus 第二遍需要更强"})

    review_edit = build_review_edit(project_id="project-001", parent_version_id="v001", parent_plan=plan, audition=audition, audition_plan=plan)

    edit_types = [item["edit_type"] for item in review_edit.intents]
    assert "track_density" in edit_types
    assert "section_energy" in edit_types
    density = next(item for item in review_edit.intents if item["edit_type"] == "track_density")
    assert "bass" in density["target"]["track_name"].lower()
    assert density["payload"]["density_scale"] < 1


def test_review_marker_hook_is_preserved_not_changed() -> None:
    plan = demo_song_plan()
    audition = _audition(plan, review={"rating": 5, "status": "keep", "notes": "hook is good", "markers": [{"marker_id": "marker-001", "beat": 1, "kind": "hook", "label": "keep hook", "severity": "info"}]})

    review_edit = build_review_edit(project_id="project-001", parent_version_id="v001", parent_plan=plan, audition=audition, audition_plan=plan, payload={"intent_overrides": [{"edit_type": "section_energy", "target": {"section_name": plan.sections[0].name}, "strength": 6, "preserve": ["tempo", "key"], "payload": {}}]})

    assert review_edit.warnings == ["Used explicit intent overrides."]


def test_rejected_review_returns_no_intent() -> None:
    plan = demo_song_plan()
    audition = _audition(plan, review={"rating": 1, "status": "reject", "notes": "bad"})

    with pytest.raises(ReviewEditUnavailableError, match="rejected"):
        build_review_edit(project_id="project-001", parent_version_id="v001", parent_plan=plan, audition=audition, audition_plan=plan)


def test_review_edit_sanitizes_source_and_applies() -> None:
    plan = demo_song_plan()
    audition = _audition(plan, review={"rating": 4, "status": "needs_fix", "notes": r"bass reduce api_key=sk-secret-value C:\Users\demo\song.wav"})

    review_edit = build_review_edit(project_id="project-001", parent_version_id="v001", parent_plan=plan, audition=audition, audition_plan=plan)
    result = apply_review_edit(plan, review_edit)
    serialized = str(review_edit.to_dict())

    assert result.plan.title == plan.title
    assert result.summary["edit_source"] == "audition_review"
    assert result.summary["operation_count"] >= 1
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_custom_range_marker_targets_parent_section_by_global_beat() -> None:
    plan = demo_song_plan()
    audition = _audition(
        plan,
        review={"rating": 4, "status": "needs_fix", "notes": "fix this range", "markers": [{"marker_id": "marker-001", "beat": 1, "kind": "fix", "label": "local fix"}]},
        range_data={"mode": "custom", "start_beat": 16.0, "end_beat": 24.0},
    )

    review_edit = build_review_edit(project_id="project-001", parent_version_id="v001", parent_plan=plan, audition=audition, audition_plan=plan)

    assert review_edit.intents[0]["target"]["section_name"] == "verse"


def test_changed_sections_marker_targets_parent_section_by_global_beat() -> None:
    plan = demo_song_plan()
    audition = _audition(
        plan,
        review={"rating": 4, "status": "needs_fix", "notes": "fix changed part", "markers": [{"marker_id": "marker-001", "beat": 1, "kind": "fix", "label": "local fix"}]},
        range_data={"mode": "changed_sections", "section_names": ["verse"], "start_beat": 16.0, "end_beat": 48.0},
    )

    review_edit = build_review_edit(project_id="project-001", parent_version_id="v001", parent_plan=plan, audition=audition, audition_plan=plan)

    assert review_edit.intents[0]["target"]["section_name"] == "verse"


def _audition(plan, review: dict, range_data: dict | None = None) -> EditorAuditionManifest:
    range_data = range_data or {"mode": "section", "section_name": plan.sections[0].name, "start_beat": 0, "end_beat": plan.sections[0].bars * 4}
    return EditorAuditionManifest.from_dict(
        {
            "schema_version": 1,
            "audition_id": "audition-001",
            "project_id": "project-001",
            "preview_id": "preview-001",
            "parent_version_id": "v001",
            "parent_job_id": "job-001",
            "source": "preview",
            "source_plan_hash": "abc",
            "base_plan_hash": "base",
            "status": "completed",
            "created_at": "2026-05-12T00:00:00+00:00",
            "updated_at": "2026-05-12T00:00:00+00:00",
            "range": range_data,
            "track_mode": "solo",
            "track_ids": ["track-003"],
            "track_count": 1,
            "note_count": 16,
            "duration_beats": 8,
            "midi": {"status": "completed"},
            "audio": {"status": "not_started"},
            "review": review,
        }
    )
