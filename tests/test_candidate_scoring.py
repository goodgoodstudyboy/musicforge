from __future__ import annotations

from song_agent.agent.pipeline import deterministic_compose
from song_agent.candidate_scoring import group_status_for_candidates, rank_candidate_summaries, score_provider_edit_candidate
from song_agent.provider_edits import ProviderEditPatch, apply_provider_edit_patch
from song_agent.schemas.song import SongRequest


def parent_plan():
    return deterministic_compose(
        SongRequest.from_dict(
            {
                "title": "Candidate Score Parent",
                "language": "English",
                "style": "synth pop",
                "theme": "candidate score",
            }
        )
    )


def test_score_provider_edit_candidate_uses_quality_confidence_and_novelty() -> None:
    plan = parent_plan()
    patch = ProviderEditPatch.from_dict(
        {
            "schema_version": 1,
            "summary": "lift chorus",
            "operations": [{"op": "set_section_energy", "section_name": "chorus", "energy": 0.9}],
            "confidence": 0.8,
        }
    )
    result = apply_provider_edit_patch(plan, patch)

    score = score_provider_edit_candidate(parent_plan=plan, candidate_plan=result.plan, patch=patch)

    assert score.quality_overall > 0
    assert score.validator == 100
    assert score.patch_confidence == 80
    assert score.combined > 0


def test_rank_candidate_summaries_excludes_failed_and_orders_ready() -> None:
    ranking = rank_candidate_summaries(
        [
            {"candidate_id": "cand-001", "status": "ready", "scores": {"combined": 70, "quality_overall": 90}},
            {"candidate_id": "cand-002", "status": "failed", "scores": {"combined": 99, "quality_overall": 99}},
            {"candidate_id": "cand-003", "status": "ready", "scores": {"combined": 82, "quality_overall": 80}},
        ]
    )

    assert [item["candidate_id"] for item in ranking] == ["cand-003", "cand-001"]
    assert [item["rank"] for item in ranking] == [1, 2]


def test_group_status_for_candidates() -> None:
    assert group_status_for_candidates([]) == "failed"
    assert group_status_for_candidates([{"status": "ready"}]) == "ready"
    assert group_status_for_candidates([{"status": "ready"}, {"status": "failed"}]) == "partial_ready"
    assert group_status_for_candidates([{"status": "failed"}]) == "failed"
