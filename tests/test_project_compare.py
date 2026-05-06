from __future__ import annotations

from pathlib import Path

from song_agent.agent.pipeline import deterministic_compose
from song_agent.edits import EditIntent, apply_edit_intent, build_edit_metadata
from song_agent.project_compare import compare_project_versions
from song_agent.projectio import write_json
from song_agent.projects import ProjectStore
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import SongRequest


class Job:
    def __init__(self, job_id: str, run_dir: Path, request: dict, *, title: str | None = None) -> None:
        self.job_id = job_id
        self.title = title or request["title"]
        self.output_dir = str(run_dir)
        self.status = "completed"
        self.created_at = "2026-05-06T00:00:00Z"
        self.updated_at = "2026-05-06T00:00:00Z"
        self.input_payload = request
        self.generation_mode = "local"
        self.pipeline_mode = "single"
        self.summary = {"title": self.title}
        self.artifacts = {"midi": str(run_dir / "renders" / "song.mid")}


def request_payload(title: str) -> dict:
    return {"title": title, "language": "English", "style": "synth pop", "theme": "compare"}


def write_plan(run_dir: Path, request: dict):
    plan = deterministic_compose(SongRequest.from_dict(request))
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
    render_midi(plan, run_dir / "renders" / "song.mid")
    return plan


def test_compare_original_and_edit_version(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / ".musicforge" / "projects")
    document = store.create_project("Compare Project")
    first_request = request_payload("Compare One")
    first_dir = tmp_path / "runs" / "compare-one"
    first_plan = write_plan(first_dir, first_request)
    first_job = Job("compare-one", first_dir, first_request)
    document = store.add_version_from_job(document.state.project_id, first_job, name="Original")

    intent = EditIntent.from_dict({"edit_type": "section_energy", "target": {"section_name": "chorus"}, "strength": 8})
    edited = apply_edit_intent(first_plan, intent)
    second_dir = tmp_path / "runs" / "compare-two"
    write_json(second_dir / "data" / "song-plan.json", edited.plan.to_dict())
    write_json(
        second_dir / "data" / "edit-metadata.json",
        build_edit_metadata(
            project_id=document.state.project_id,
            parent_version_id="v001",
            parent_job_id="compare-one",
            intent=intent,
            created_at="2026-05-06T00:00:00Z",
            summary=edited.summary,
            warnings=edited.warnings,
        ),
    )
    render_midi(edited.plan, second_dir / "renders" / "song.mid")
    document = store.add_version_from_job(
        document.state.project_id,
        Job("compare-two", second_dir, first_request),
        name="Chorus Lift",
        parent_version_id="v001",
        variant_type="section_edit",
        change_summary="lift chorus",
    )

    compare = compare_project_versions(document, "v001", "v002")

    assert compare["left"]["version_id"] == "v001"
    assert compare["right"]["edit"]["edit_type"] == "section_energy"
    assert compare["summary"]["track_changes"] >= 1
    assert compare["summary"]["recommendation"] in {"left", "right", "tie", "unknown"}
    assert compare["artifacts"]["left"]["midi"] == "/api/jobs/compare-one/midi"


def test_compare_missing_plan_and_missing_version_are_safe(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / ".musicforge" / "projects")
    document = store.create_project("Missing Compare")
    request = request_payload("Missing Plan")
    run_dir = tmp_path / "runs" / "missing-plan"
    (run_dir / "renders").mkdir(parents=True)
    (run_dir / "renders" / "song.mid").write_bytes(b"MThd")
    document = store.add_version_from_job(document.state.project_id, Job("missing-plan", run_dir, request), name="Missing")

    compare = compare_project_versions(document, "v001", "v001")

    assert compare["left"]["quality"]["overall"] is None
    assert compare["sections"] == []
    try:
        compare_project_versions(document, "v001", "v999")
    except FileNotFoundError as exc:
        assert str(exc)
    else:
        raise AssertionError("missing version should raise")
