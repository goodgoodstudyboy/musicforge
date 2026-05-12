from __future__ import annotations

import json

import pytest

from song_agent.editor_audition import EditorAuditionManifest
from song_agent.edits import EditIntent
from song_agent.review_tasks import (
    ReviewCandidate,
    ReviewTaskStateError,
    ReviewTaskStore,
    apply_candidate_intents,
    build_local_review_candidates,
    candidate_intents_for_strategy,
    ensure_candidate_current,
    ensure_task_current,
    mark_task_resolved,
    review_task_target,
)
from song_agent.song_editor import song_plan_hash
from tests.test_editor_audition import demo_song_plan


class Preview:
    preview_id = "preview-001"
    base_plan_hash = "base-hash"


def test_create_review_task_maps_custom_marker_to_parent_section_and_sanitizes(tmp_path):
    plan = demo_song_plan()
    store = ReviewTaskStore(tmp_path / "project")
    audition = _audition(
        review={
            "rating": 4,
            "status": "needs_fix",
            "notes": r"bass 太满 api_key=sk-secret-value C:\Users\demo\song.wav",
            "markers": [{"marker_id": "marker-001", "beat": 1, "kind": "fix", "label": "local fix sk-secret-value"}],
        },
        range_data={"mode": "custom", "start_beat": 16.0, "end_beat": 24.0},
    )

    task = store.create_task(
        project_id="project-001",
        parent_version_id="v001",
        parent_plan=plan,
        preview=Preview(),
        audition=audition,
        audition_plan=plan,
        now="2026-05-12T00:00:00+00:00",
    )

    assert task.task_id == "review-task-001"
    assert task.target["section_name"] == "verse"
    assert task.target["local_marker_beat"] == 1.0
    assert task.target["global_marker_beat"] == 17.0
    serialized = json.dumps(task.to_dict(), ensure_ascii=False)
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized
    assert store.read_events(task.task_id)[0]["event"] == "review_task_created"


def test_fix_marker_wins_over_earlier_keep_marker():
    plan = demo_song_plan()
    audition = _audition(
        review={
            "rating": 4,
            "status": "needs_fix",
            "notes": "keep hook but fix verse bass",
            "markers": [
                {"marker_id": "marker-001", "beat": 0, "kind": "keep", "label": "keep this hook"},
                {"marker_id": "marker-002", "beat": 1, "kind": "fix", "label": "fix here"},
            ],
        },
        range_data={"mode": "changed_sections", "section_names": ["verse"], "start_beat": 16.0, "end_beat": 48.0},
    )

    target = review_task_target(plan, audition, audition.review)

    assert target["marker_kind"] == "fix"
    assert target["section_name"] == "verse"
    assert target["global_marker_beat"] == 17.0


def test_local_review_candidates_generate_rank_and_render_midi(tmp_path):
    plan = demo_song_plan()
    store = ReviewTaskStore(tmp_path / "project")
    task = _task(store, plan)

    generated = [
        store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary)
        for candidate, candidate_plan, validator, summary in build_local_review_candidates(task, plan)
    ]
    ranked = store.rank_candidates(task)
    task = store.update_counts(task)

    assert len(generated) >= 2
    assert task.status == "candidate_ready"
    assert task.counts["ready_candidate_count"] >= 2
    assert ranked[0].rank == 1
    assert store.candidate_midi_path(task.task_id, ranked[0].candidate_id).read_bytes().startswith(b"MThd")


def test_keep_marker_preserves_melody_variation(tmp_path):
    plan = demo_song_plan()
    task = _task(
        ReviewTaskStore(tmp_path / "project"),
        plan,
        review={
            "rating": 4,
            "status": "needs_fix",
            "notes": "make melody hook stronger",
            "markers": [{"marker_id": "marker-001", "beat": 1, "kind": "keep", "label": "keep hook"}],
        },
    )

    intents = candidate_intents_for_strategy(task, "bold")

    assert all(intent.edit_type != "melody_variation" for intent in intents)


def test_apply_recomputes_from_parent_and_intents_not_cached_plan(tmp_path):
    plan = demo_song_plan()
    store = ReviewTaskStore(tmp_path / "project")
    task = _task(store, plan)
    candidate, candidate_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    stored = store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary)
    polluted_path = store.candidate_dir(task.task_id, stored.candidate_id) / "candidate-song-plan.json"
    polluted = json.loads(polluted_path.read_text(encoding="utf-8"))
    polluted["tracks"][0]["notes"] = []
    polluted_path.write_text(json.dumps(polluted), encoding="utf-8")

    result = apply_candidate_intents(plan, [EditIntent.from_dict(item) for item in stored.intents])

    assert result.plan.tracks[0].notes


def test_stale_and_unsafe_candidate_artifact_guards(tmp_path):
    plan = demo_song_plan()
    store = ReviewTaskStore(tmp_path / "project")
    task = _task(store, plan)
    candidate, candidate_plan, validator, summary = build_local_review_candidates(task, plan, strategies=["balanced"])[0]
    stored = store.create_candidate(task=task, candidate=candidate, candidate_plan=candidate_plan, validator=validator, summary=summary)
    bad_candidate = ReviewCandidate.from_dict({**stored.to_dict(), "artifacts": {**stored.artifacts, "midi_path": f"review-tasks/{task.task_id}/candidates/revcand-999/renders/song.mid"}})
    store.update_candidate(bad_candidate)

    with pytest.raises(ValueError, match="unsafe"):
        store.candidate_midi_path(task.task_id, stored.candidate_id)

    changed_plan = type(plan).from_dict({**plan.to_dict(), "tempo_bpm": plan.tempo_bpm + 1})
    with pytest.raises(ReviewTaskStateError, match="stale"):
        ensure_task_current(task, changed_plan)
    with pytest.raises(ReviewTaskStateError, match="stale"):
        ensure_candidate_current(task, stored, changed_plan)


def test_resolve_requires_applied_task(tmp_path):
    plan = demo_song_plan()
    task = _task(ReviewTaskStore(tmp_path / "project"), plan)

    with pytest.raises(ReviewTaskStateError):
        mark_task_resolved(task)


def _task(store: ReviewTaskStore, plan, review: dict | None = None):
    return store.create_task(
        project_id="project-001",
        parent_version_id="v001",
        parent_plan=plan,
        preview=Preview(),
        audition=_audition(review=review),
        audition_plan=plan,
        now="2026-05-12T00:00:00+00:00",
    )


def _audition(review: dict | None = None, range_data: dict | None = None) -> EditorAuditionManifest:
    review = review or {
        "rating": 4,
        "status": "needs_fix",
        "notes": "bass 太满, chorus 更强",
        "markers": [{"marker_id": "marker-001", "beat": 1, "kind": "fix", "label": "fix point"}],
    }
    range_data = range_data or {"mode": "changed_sections", "section_names": ["verse"], "start_beat": 16.0, "end_beat": 48.0}
    return EditorAuditionManifest.from_dict(
        {
            "schema_version": 1,
            "audition_id": "audition-001",
            "project_id": "project-001",
            "preview_id": "preview-001",
            "parent_version_id": "v001",
            "parent_job_id": "job-001",
            "source": "preview",
            "source_plan_hash": song_plan_hash(demo_song_plan()),
            "base_plan_hash": "base",
            "status": "completed",
            "created_at": "2026-05-12T00:00:00+00:00",
            "updated_at": "2026-05-12T00:00:00+00:00",
            "range": range_data,
            "track_mode": "solo",
            "track_ids": ["track-003"],
            "track_count": 1,
            "note_count": 16,
            "duration_beats": 32,
            "midi": {"status": "completed"},
            "audio": {"status": "not_started"},
            "review": review,
        }
    )
