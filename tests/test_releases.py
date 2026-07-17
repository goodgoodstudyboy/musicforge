from __future__ import annotations

import concurrent.futures
from pathlib import Path

from song_agent.delivery_qa import build_delivery_qa_report, build_delivery_signoff_record
from song_agent.final_export import FinalExportOptions, build_final_export_bundle, build_final_export_zip
from song_agent.project_quality import QualityGateConfig, evaluate_quality_gate
from song_agent.projects import ProjectStore
from song_agent.releases import ReleaseStateError, ReleaseStore
from tests.test_delivery_qa import Version
from tests.test_final_export import make_run


def test_release_store_create_add_reorder_refresh_and_hide(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "First Song")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)

    release = release_store.create_release({"name": "Demo EP", "release_type": "ep", "primary_artist": "Local Artist"})
    release = release_store.add_track(release.release_id, {"project_id": project_id, "title": "First Song"})
    release = release_store.add_track(release.release_id, {"project_id": project_id, "title": "First Song Alt"})
    release = release_store.reorder_tracks(release.release_id, {"track_ids": [release.tracks[1].track_id, release.tracks[0].track_id]})
    release = release_store.refresh_track(release.release_id, release.tracks[0].track_id)
    hidden = release_store.hide_release(release.release_id, True)

    assert release.release_id == "release-000001"
    assert [track.track_number for track in release.tracks] == [1, 2]
    assert release.tracks[0].project_snapshot["final_version_id"] == "v001"
    assert hidden.hidden is True
    assert release_store.list_releases() == []
    assert release_store.list_releases(include_hidden=True)[0].release_id == release.release_id
    assert release_store.read_events(release.release_id)


def test_release_store_concurrent_create_allocates_unique_ids(tmp_path: Path) -> None:
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=ProjectStore(tmp_path / ".musicforge" / "projects"))

    def create(index: int) -> str:
        return release_store.create_release({"name": f"Release {index}", "release_type": "demo_pack"}).release_id

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        ids = list(executor.map(create, range(24)))

    assert len(ids) == len(set(ids))
    assert ids[0] == "release-000001"
    assert sorted(ids)[-1] == "release-000024"


def test_signed_release_blocks_mutation_until_reset(tmp_path: Path) -> None:
    project_store = ProjectStore(tmp_path / ".musicforge" / "projects")
    project_id = _signed_project(tmp_path, project_store, "Signed Song")
    release_store = ReleaseStore(tmp_path / ".musicforge" / "releases", project_store=project_store)
    release = release_store.create_release({"name": "Signed Pack", "release_type": "demo_pack"})
    release = release_store.add_track(release.release_id, {"project_id": project_id})
    release_store.update_signoff_summary(release.release_id, {"status": "signed"})

    try:
        release_store.add_track(release.release_id, {"project_id": project_id, "title": "Blocked"})
        raised = False
    except ReleaseStateError:
        raised = True

    assert raised is True


def _signed_project(tmp_path: Path, project_store: ProjectStore, title: str) -> str:
    document = project_store.create_project(title)
    run_dir, _plan = make_run(tmp_path / title)
    project_id = document.state.project_id
    version = Version()
    version.version_id = "v001"
    version.project_id = project_id
    version.name = title
    version.job_id = "export-job"
    job = type(
        "Job",
        (),
        {
            "job_id": "export-job",
            "title": title,
            "output_dir": str(run_dir),
            "status": "completed",
            "created_at": "2026-05-15T00:00:00+00:00",
            "updated_at": "2026-05-15T00:00:00+00:00",
            "summary": {"title": title},
            "input_payload": {"title": title},
            "generation_mode": "local",
            "pipeline_mode": "single",
            "artifacts": {},
        },
    )()
    document = project_store.add_version_from_job(project_id, job, name=title)
    document = project_store.set_final_version(project_id, "v001")
    project_dir = project_store.project_dir(project_id)
    gate = evaluate_quality_gate(run_dir, QualityGateConfig(), now="2026-05-15T00:00:00+00:00")
    project_export = project_store.project_export_snapshot(project_id)
    build_final_export_bundle(project=document.state, version=document.versions[0], project_dir=project_dir, run_dir=run_dir, gate=gate, options=FinalExportOptions(include_stems=False, include_stem_audio=False), now="2026-05-15T00:00:00+00:00", project_export=project_export)
    project_store.update_version_final_export(project_id, "v001", project_dir / "final-export")
    build_final_export_zip(project_dir, now="2026-05-15T00:01:00+00:00")
    report = build_delivery_qa_report(project_id=project_id, project_document=project_store.get_project(project_id), project_dir=project_dir, project_export=project_store.project_export_snapshot(project_id), final_export_manifest=None)
    project_store.write_delivery_qa(project_id, report)
    signoff = build_delivery_signoff_record(project_id=project_id, report=report, payload={"signed_by": "tester"}, now="2026-05-15T00:02:00+00:00")
    project_store.write_delivery_signoff(project_id, signoff)
    return project_id
