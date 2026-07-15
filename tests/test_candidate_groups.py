from __future__ import annotations

from pathlib import Path

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.candidate_groups import CandidateGroupStore, candidate_audio_path, candidate_group_stale, candidate_midi_path
from song_agent.renderers.audio import RendererConfig
from song_agent.schemas.song import SongRequest


def candidate_plan() -> dict[str, object]:
    return deterministic_compose(
        SongRequest.from_dict(
            {
                "title": "Candidate Preview",
                "language": "English",
                "style": "synth pop",
                "theme": "candidate preview",
            }
        )
    ).to_dict()


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
        candidate_plan=candidate_plan(),
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
        candidate_plan=candidate_plan(),
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
    assert store.read_candidate_plan("cg-001", "cand-001")["title"] == "Candidate Preview"
    assert candidate_group_stale(read, "abc") is False
    assert candidate_group_stale(read, "def") is True

    applied = store.mark_applied("cg-001", "cand-002", version_id="v002", job_id="job-002")
    assert applied.status == "applied"
    assert applied.selected_candidate_id == "cand-002"
    assert applied.applied_version_id == "v002"

    store.delete_group("cg-001")
    assert not (tmp_path / ".musicforge" / "projects" / "candidate-project" / "candidate-groups" / "cg-001").exists()


def test_candidate_group_store_renders_midi_and_audio(tmp_path: Path) -> None:
    store = CandidateGroupStore(tmp_path / ".musicforge" / "projects" / "candidate-project")
    group = store.create_group(
        project_id="candidate-project",
        parent_version_id="v001",
        parent_job_id="parent-job",
        instruction="Give me 2 options.",
        template_id="provider-edit-candidates",
        candidate_count=2,
        source={"song_plan_sha256": "abc"},
    )
    candidate = store.add_candidate(
        group,
        summary="first",
        status="ready",
        patch={"schema_version": 1, "summary": "first", "operations": []},
        scores={"combined": 60, "quality_overall": 80},
        validator={"status": "passed"},
        quality={"scores": {"overall": 80}},
        candidate_plan=candidate_plan(),
    )

    midi_candidate = store.render_candidate_midi(group.group_id, candidate.candidate_id)
    midi_path = candidate_midi_path(store.candidate_dir(group.group_id, candidate.candidate_id))

    assert midi_candidate.midi_status == "completed"
    assert midi_candidate.midi_url == "/api/projects/candidate-project/candidate-groups/cg-001/candidates/cand-001/midi"
    assert midi_candidate.midi_size_bytes > 0
    assert midi_path.read_bytes().startswith(b"MThd")

    def fake_runner(cmd, capture_output, text, timeout, shell):
        wav_path = Path(cmd[cmd.index("-F") + 1])
        wav_path.write_bytes(b"RIFFfakeWAVE")
        class Result:
            returncode = 0
            stderr = ""
            stdout = ""
        return Result()

    config = RendererConfig(soundfont_path=str(tmp_path / "soundfont.sf2"))
    Path(config.soundfont_path).write_bytes(b"sf2")
    from song_agent.domains.quality import candidate_groups as candidate_groups_module

    original_render_audio = candidate_groups_module.render_audio
    try:
        candidate_groups_module.render_audio = lambda midi, wav, cfg: original_render_audio(midi, wav, cfg, runner=fake_runner)
        audio_candidate = store.render_candidate_audio(group.group_id, candidate.candidate_id, config)
    finally:
        candidate_groups_module.render_audio = original_render_audio

    assert audio_candidate.audio_status == "completed"
    assert audio_candidate.audio_url == "/api/projects/candidate-project/candidate-groups/cg-001/candidates/cand-001/audio"
    assert candidate_audio_path(store.candidate_dir(group.group_id, candidate.candidate_id)).read_bytes().startswith(b"RIFF")


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
