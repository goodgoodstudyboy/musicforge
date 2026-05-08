from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.projectio import write_json
from song_agent.projects import ProjectStore, ProjectVersion
from song_agent.schemas.song import SongRequest


@dataclass
class FakeJob:
    job_id: str
    title: str
    output_dir: str
    status: str = "completed"
    created_at: str = "2026-05-06T00:00:00+00:00"
    updated_at: str = "2026-05-06T00:01:00+00:00"
    summary: dict[str, Any] = field(default_factory=lambda: {"title": "Project Song"})
    input_payload: dict[str, Any] = field(default_factory=lambda: request_payload())
    generation_mode: str = "local"
    pipeline_mode: str = "single"
    artifacts: dict[str, str] = field(default_factory=dict)


def request_payload() -> dict[str, Any]:
    return {
        "title": "Project Song",
        "language": "English",
        "style": "synth pop",
        "theme": "workspace",
    }


def make_run(tmp_path: Path, job_id: str = "project-song") -> Path:
    run_dir = tmp_path / "runs" / job_id
    plan = deterministic_compose(SongRequest.from_dict(request_payload()))
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
    (run_dir / "renders").mkdir(parents=True, exist_ok=True)
    (run_dir / "renders" / "song.mid").write_bytes(b"MThd")
    return run_dir


def test_create_project_uses_unique_slug_and_empty_versions(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")

    first = store.create_project("Same Project", tags=["demo", " pop "])
    second = store.create_project("Same Project")

    assert first.state.project_id == "same-project"
    assert second.state.project_id == "same-project-2"
    assert first.versions == []
    assert first.state.tags == ["demo", "pop"]
    assert (tmp_path / "projects" / "same-project" / "project.json").exists()
    assert (tmp_path / "projects" / "same-project" / "versions.json").exists()


def test_project_id_path_safety(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")

    with pytest.raises(ValueError, match="Invalid project_id"):
        store.get_project("../secret")

    with pytest.raises(ValueError, match="outside the project root"):
        store.ensure_project_dir_is_safe(tmp_path / "elsewhere")


def test_add_version_from_job_sets_index_flags_and_quality(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Versioned Song")
    run_dir = make_run(tmp_path)
    job = FakeJob(
        job_id="project-song",
        title="Project Song",
        output_dir=str(run_dir),
        artifacts={"midi": str(run_dir / "renders" / "song.mid")},
    )

    updated = store.add_version_from_job(document.state.project_id, job, name="First keeper", note="Good hook")

    assert updated.state.version_count == 1
    assert updated.state.latest_version_id == "v001"
    assert updated.state.best_quality_version_id == "v001"
    assert updated.versions[0].version_id == "v001"
    assert updated.versions[0].index == 1
    assert updated.versions[0].name == "First keeper"
    assert updated.versions[0].note == "Good hook"
    assert updated.versions[0].has_midi is True
    assert updated.versions[0].quality_score is not None
    assert updated.versions[0].variant_type == "original"
    assert updated.versions[0].parent_version_id is None
    assert updated.versions[0].quality_gate_status == "not_evaluated"


def test_add_version_rejects_duplicate_job(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Duplicate Song")
    run_dir = make_run(tmp_path)
    job = FakeJob(job_id="job-1", title="Project Song", output_dir=str(run_dir))

    store.add_version_from_job(document.state.project_id, job)

    with pytest.raises(ValueError, match="already attached"):
        store.add_version_from_job(document.state.project_id, job)


def test_selected_and_final_versions(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Final Song")
    completed = FakeJob(job_id="done", title="Done", output_dir=str(make_run(tmp_path, "done")), status="completed")
    queued = FakeJob(job_id="queued", title="Queued", output_dir=str(make_run(tmp_path, "queued")), status="queued")
    store.add_version_from_job(document.state.project_id, completed)
    store.add_version_from_job(document.state.project_id, queued)

    selected = store.set_selected_version(document.state.project_id, "v002")
    assert selected.state.selected_version_id == "v002"

    with pytest.raises(ValueError, match="Only completed"):
        store.set_final_version(document.state.project_id, "v002")

    final = store.set_final_version(document.state.project_id, "v001")
    assert final.state.final_version_id == "v001"
    assert final.state.status == "finalized"


def test_add_variation_version_records_lineage(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Lineage Song")
    parent_run = make_run(tmp_path, "parent")
    child_run = make_run(tmp_path, "child")
    store.add_version_from_job(
        document.state.project_id,
        FakeJob(job_id="parent", title="Parent", output_dir=str(parent_run)),
    )

    updated = store.add_version_from_job(
        document.state.project_id,
        FakeJob(job_id="child", title="Child", output_dir=str(child_run)),
        name="Warmer version",
        parent_version_id="v001",
        variant_type="style_variation",
        change_summary="style -> warm synth pop",
    )

    child = updated.versions[1]
    assert child.version_id == "v002"
    assert child.parent_version_id == "v001"
    assert child.variant_type == "style_variation"
    assert child.change_summary == "style -> warm synth pop"


def test_add_variation_rejects_unknown_parent_or_type(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Bad Lineage")
    run_dir = make_run(tmp_path, "child")

    with pytest.raises(FileNotFoundError):
        store.add_version_from_job(
            document.state.project_id,
            FakeJob(job_id="child", title="Child", output_dir=str(run_dir)),
            parent_version_id="v999",
        )

    with pytest.raises(ValueError, match="variant_type"):
        store.add_version_from_job(
            document.state.project_id,
            FakeJob(job_id="child-2", title="Child", output_dir=str(run_dir)),
            variant_type="random",
        )


def test_export_project_writes_manifest_without_deleting_runs(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Export Project")
    run_dir = make_run(tmp_path, "export-job")
    store.add_version_from_job(document.state.project_id, FakeJob(job_id="export-job", title="Export", output_dir=str(run_dir)))

    export = store.export_project(document.state.project_id)

    assert export["project"]["project_id"] == document.state.project_id
    assert export["versions"][0]["song_plan"] == str(run_dir / "data" / "song-plan.json")
    assert (tmp_path / "projects" / document.state.project_id / "export.json").exists()

    store.delete_project(document.state.project_id)

    assert not (tmp_path / "projects" / document.state.project_id).exists()
    assert run_dir.exists()


def test_export_project_includes_asset_refs_from_versions_and_candidates(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Asset Export Project")
    run_dir = make_run(tmp_path, "asset-job")
    write_json(
        run_dir / "data" / "asset-refs.json",
        {
            "schema_version": 1,
            "asset_refs": [
                {
                    "asset_id": "asset-001",
                    "asset_type": "motif",
                    "name": "Saved Motif",
                    "role": "motif_reference",
                    "strength": 0.8,
                    "content_summary": {"note_count": 8},
                    "source": {"project_id": "source-project", "version_id": "v002"},
                }
            ],
        },
    )
    document = store.add_version_from_job(document.state.project_id, FakeJob(job_id="asset-job", title="Asset", output_dir=str(run_dir)))
    group_dir = tmp_path / "projects" / document.state.project_id / "candidate-groups" / "cg-001"
    write_json(
        group_dir / "group.json",
        {
            "group_id": "cg-001",
            "source": {
                "asset_refs": [
                    {
                        "asset_id": "asset-001",
                        "asset_type": "motif",
                        "name": "Saved Motif",
                        "role": "candidate_reference",
                        "strength": 0.6,
                    }
                ]
            },
        },
    )

    export = store.export_project(document.state.project_id)

    assert export["asset_refs"] == [
        {
            "asset_id": "asset-001",
            "asset_type": "motif",
            "name": "Saved Motif",
            "roles": ["motif_reference", "candidate_reference"],
            "used_by_versions": ["v001"],
            "used_by_candidate_groups": ["cg-001"],
            "content_summary": {"note_count": 8},
            "source": {"project_id": "source-project", "version_id": "v002"},
        }
    ]
    assert str(tmp_path) not in json.dumps(export["asset_refs"])


def test_export_project_redacts_polluted_asset_ref_metadata(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Polluted Asset Export")
    run_dir = make_run(tmp_path, "polluted-asset-job")
    store.add_version_from_job(document.state.project_id, FakeJob(job_id="polluted-asset-job", title="Asset", output_dir=str(run_dir)))
    write_json(
        run_dir / "data" / "asset-refs.json",
        {
            "schema_version": 1,
            "asset_refs": [
                {
                    "asset_id": "asset-001",
                    "asset_type": "motif",
                    "name": "Polluted Motif",
                    "role": "motif_reference",
                    "content_summary": {
                        "note_count": 8,
                        "path": str(tmp_path / "secret.mid"),
                        "nested": {"api_key": "sk-polluted-secret", "safe": "ok"},
                    },
                    "source": {
                        "project_id": "source",
                        "local_path": str(tmp_path),
                        "raw_provider_response": {"token": "bad"},
                        "nested": {"secret": "bad", "version_id": "v001"},
                    },
                }
            ],
        },
    )
    group_dir = tmp_path / "projects" / document.state.project_id / "candidate-groups" / "cg-001"
    write_json(
        group_dir / "group.json",
        {
            "group_id": "cg-001",
            "source": {
                "asset_refs": [
                    {
                        "asset_id": "asset-002",
                        "asset_type": "chord_progression",
                        "name": "Polluted Chords",
                        "role": "chord_reference",
                        "source": {"path": str(tmp_path), "job_id": "job-1"},
                        "content_summary": {"api_key": "bad", "chord_count": 4},
                    }
                ]
            },
        },
    )

    export = store.export_project(document.state.project_id)
    serialized = json.dumps(export["asset_refs"], ensure_ascii=False)

    assert "note_count" in serialized
    assert "chord_count" in serialized
    assert "version_id" in serialized
    assert "job-1" in serialized
    assert str(tmp_path) not in serialized
    assert "sk-polluted-secret" not in serialized
    assert "api_key" not in serialized
    assert "local_path" not in serialized
    assert "raw_provider_response" not in serialized
    assert "secret" not in serialized
    assert '"path"' not in serialized


def test_export_project_includes_redacted_reference_refs(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Reference Export Project")
    run_dir = make_run(tmp_path, "reference-job")
    write_json(
        run_dir / "data" / "reference-refs.json",
        {
            "schema_version": 1,
            "reference_refs": [
                {
                    "reference_id": "ref-001",
                    "reference_type": "style_note",
                    "title": "Style Seed",
                    "role": "style",
                    "metadata_summary": {
                        "text_excerpt": "Use a bright hook.",
                        "license_note": "api_key=sk-polluted-secret",
                        "path": str(tmp_path / "secret.wav"),
                        "nested": {"api_key": "sk-polluted-secret", "safe": "ok"},
                    },
                }
            ],
        },
    )
    document = store.add_version_from_job(document.state.project_id, FakeJob(job_id="reference-job", title="Reference", output_dir=str(run_dir)))
    group_dir = tmp_path / "projects" / document.state.project_id / "candidate-groups" / "cg-001"
    write_json(
        group_dir / "group.json",
        {
            "group_id": "cg-001",
            "source": {
                "reference_refs": [
                    {
                        "reference_id": "ref-002",
                        "reference_type": "midi",
                        "title": "MIDI Seed",
                        "metadata_summary": {"local_path": str(tmp_path), "source_note": "Authorization: Bearer bad-token", "key": "C"},
                    }
                ]
            },
        },
    )

    export = store.export_project(document.state.project_id)
    serialized = json.dumps(export["reference_refs"], ensure_ascii=False)

    assert [ref["reference_id"] for ref in export["reference_refs"]] == ["ref-001", "ref-002"]
    assert export["reference_refs"][0]["used_by_versions"] == ["v001"]
    assert export["reference_refs"][1]["used_by_candidate_groups"] == ["cg-001"]
    assert "text_excerpt" in serialized
    assert "key" in serialized
    assert str(tmp_path) not in serialized
    assert "sk-polluted-secret" not in serialized
    assert "bad-token" not in serialized
    assert "api_key" not in serialized
    assert "local_path" not in serialized
    assert '"path"' not in serialized


def test_old_project_json_defaults_and_missing_job_sync(tmp_path: Path) -> None:
    project_dir = tmp_path / "projects" / "legacy"
    project_dir.mkdir(parents=True)
    write_json(project_dir / "project.json", {"project_id": "legacy", "name": "Legacy", "status": "unknown"})
    write_json(
        project_dir / "versions.json",
        {
            "versions": [
                {
                    "version_id": "v001",
                    "project_id": "legacy",
                    "index": 1,
                    "name": "Old",
                    "job_id": "missing",
                    "output_dir": "runs/missing",
                    "status": "completed",
                    "created_at": "2026-05-06T00:00:00+00:00",
                    "updated_at": "2026-05-06T00:00:00+00:00",
                }
            ]
        },
    )
    store = ProjectStore(tmp_path / "projects")

    loaded = store.get_project("legacy")
    synced = store.sync_project("legacy", lambda _job_id: None)

    assert loaded.state.status == "active"
    assert loaded.state.version_count == 1
    assert loaded.versions[0].parent_version_id is None
    assert loaded.versions[0].variant_type == "original"
    assert loaded.versions[0].quality_gate_status == "not_evaluated"
    assert loaded.versions[0].final_export_path is None
    assert synced.versions[0].status == "missing_job"
    assert synced.versions[0].missing_job is True


def test_diff_versions_reports_changed_request_and_artifacts(tmp_path: Path) -> None:
    store = ProjectStore(tmp_path / "projects")
    document = store.create_project("Diff Song")
    left_run = make_run(tmp_path, "left")
    right_run = make_run(tmp_path, "right")
    left = FakeJob(job_id="left", title="Left", output_dir=str(left_run))
    right = FakeJob(
        job_id="right",
        title="Right",
        output_dir=str(right_run),
        input_payload={**request_payload(), "tempo_bpm": 96},
        artifacts={"midi": str(right_run / "renders" / "song.mid"), "audio": str(right_run / "renders" / "song.wav")},
    )
    (right_run / "renders" / "song.wav").write_bytes(b"RIFF")
    store.add_version_from_job(document.state.project_id, left)
    store.add_version_from_job(
        document.state.project_id,
        right,
        parent_version_id="v001",
        variant_type="tempo_key_variation",
        change_summary="tempo -> 96",
    )

    diff = store.diff_versions(document.state.project_id, "v001", "v002")

    assert diff["changed"]["request"]["tempo_bpm"] == {"left": None, "right": 96}
    assert diff["changed"]["artifacts"]["audio"] == {"left": False, "right": True}
    assert diff["right"]["parent_version_id"] == "v001"
    assert diff["right"]["variant_type"] == "tempo_key_variation"
    assert diff["changed"]["lineage"]["change_summary"] == {"left": "", "right": "tempo -> 96"}


def test_project_version_rejects_invalid_version_id() -> None:
    with pytest.raises(ValueError, match="Invalid version_id"):
        ProjectVersion.from_dict({"version_id": "../1", "project_id": "demo"})
