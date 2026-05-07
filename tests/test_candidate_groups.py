from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.candidate_groups import CandidateGroupStore, candidate_group_stale


def test_candidate_group_store_creates_ranks_reads_and_deletes(tmp_path: Path) -> None:
    store = CandidateGroupStore(tmp_path / ".musicforge" / "projects" / "candidate-project")
    group = store.create_group(
        project_id="candidate-project",
        parent_version_id="v001",
        parent_job_id="parent-job",
        instruction="Give me 3 options.",
        template_id="provider-edit-candidates",
        candidate_count=3,
        source={"song_plan_sha256": "abc"},
        provider_usage={"prompt_tokens": 10, "total_tokens": 15},
        provider_request_id="req-1",
        now="2026-05-07T00:00:00Z",
    )

    first = store.add_candidate(
        group,
        summary="first",
        status="ready",
        patch={"schema_version": 1, "summary": "first", "operations": []},
        scores={"combined": 60, "quality_overall": 80},
        validator={"status": "passed"},
        quality={"scores": {"overall": 80}},
        candidate_plan={"title": "candidate"},
        now="2026-05-07T00:00:01Z",
    )
    second = store.add_candidate(
        group,
        summary="second",
        status="ready",
        patch={"schema_version": 1, "summary": "second", "operations": []},
        scores={"combined": 90, "quality_overall": 88},
        validator={"status": "passed"},
        quality={"scores": {"overall": 88}},
        candidate_plan={"title": "candidate"},
        now="2026-05-07T00:00:02Z",
    )
    read = store.read_group(group.group_id)

    assert group.group_id == "cg-001"
    assert first.candidate_id == "cand-001"
    assert second.candidate_id == "cand-002"
    assert read.status == "ready"
    assert read.ranking[0]["candidate_id"] == "cand-002"
    assert read.provider_usage["total_tokens"] == 15
    assert store.list_groups()[0].group_id == "cg-001"
    assert store.read_candidate_plan("cg-001", "cand-001")["title"] == "candidate"
    assert candidate_group_stale(read, "abc") is False
    assert candidate_group_stale(read, "def") is True

    applied = store.mark_applied("cg-001", "cand-002", version_id="v002", job_id="job-002")
    assert applied.status == "applied"
    assert applied.selected_candidate_id == "cand-002"
    assert applied.applied_version_id == "v002"

    store.delete_group("cg-001")
    assert not (tmp_path / ".musicforge" / "projects" / "candidate-project" / "candidate-groups" / "cg-001").exists()


def test_candidate_group_store_rejects_bad_ids(tmp_path: Path) -> None:
    store = CandidateGroupStore(tmp_path / "project")

    with pytest.raises(ValueError, match="Invalid candidate group id"):
        store.read_group("../bad")
    with pytest.raises(ValueError, match="Invalid candidate id"):
        store.candidate_dir("cg-001", "../bad")
    with pytest.raises(ValueError, match="candidate_count"):
        store.create_group(
            project_id="project",
            parent_version_id="v001",
            parent_job_id="job",
            instruction="x",
            template_id="provider-edit-candidates",
            candidate_count=6,
            source={},
        )
