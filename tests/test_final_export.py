from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.final_export import (
    FinalExportError,
    FinalExportOptions,
    build_final_export_bundle,
    read_final_export_manifest,
)
from song_agent.project_quality import QualityGateConfig, evaluate_quality_gate
from song_agent.projectio import read_json, write_json
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import SongRequest
from song_agent.stems import read_stem_manifest, render_stem_midis


class Project:
    project_id = "export-project"
    name = "Export Project"


class Version:
    version_id = "v001"
    name = "Final"
    job_id = "export-job"
    note = "approved"


def request() -> SongRequest:
    return SongRequest(
        title="Final Export Song",
        language="en",
        style="synth pop",
        theme="final bundle",
        tempo_bpm=96,
    )


def make_run(tmp_path: Path) -> tuple[Path, object]:
    run_dir = tmp_path / "runs" / "export-job"
    plan = deterministic_compose(request())
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
    write_json(run_dir / "data" / "run-summary.json", {"title": plan.title})
    write_json(run_dir / "data" / "validator-report.json", {"status": "passed"})
    render_midi(plan, run_dir / "renders" / "song.mid")
    (run_dir / "renders" / "song.wav").write_bytes(b"RIFFfinalWAVE")
    render_stem_midis(plan, run_dir, "export-job", now="2026-05-06T00:00:00Z")
    (run_dir / "stems" / "audio").mkdir(parents=True, exist_ok=True)
    for midi_path in (run_dir / "stems" / "midi").glob("*.mid"):
        (run_dir / "stems" / "audio" / f"{midi_path.stem}.wav").write_bytes(b"RIFFstemWAVE")
    return run_dir, plan


def passed_gate(run_dir: Path):
    return evaluate_quality_gate(run_dir, QualityGateConfig(), now="2026-05-06T00:00:00Z")


def test_final_export_bundle_copies_core_audio_stems_and_manifest(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
        project_export={"project": {"project_id": "export-project"}},
    )

    export_dir = project_dir / "final-export"
    assert manifest["project_id"] == "export-project"
    assert manifest["quality_gate"]["status"] == "passed"
    assert (export_dir / "song-plan.json").exists()
    assert (export_dir / "song.mid").read_bytes().startswith(b"MThd")
    assert (export_dir / "song.wav").read_bytes().startswith(b"RIFF")
    assert (export_dir / "stems" / "manifest.json").exists()
    assert any((export_dir / "stems" / "midi").glob("*.mid"))
    assert any((export_dir / "stems" / "audio").glob("*.wav"))
    assert (export_dir / "project-export.json").exists()
    assert "MusicForge Final Export" in (export_dir / "README.txt").read_text(encoding="utf-8")
    assert read_final_export_manifest(project_dir)["version_id"] == "v001"


def test_final_export_skips_stale_stems(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, plan = make_run(tmp_path)
    changed = replace(plan, tempo_bpm=plan.tempo_bpm + 1)
    write_json(run_dir / "data" / "song-plan.json", changed.to_dict())

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
    )

    stem_record = next(file for file in manifest["files"] if file["kind"] == "stem_manifest")
    assert stem_record["exists"] is False
    assert stem_record["skipped"] == "stale"
    assert not (project_dir / "final-export" / "stems" / "manifest.json").exists()


def test_final_export_respects_optional_audio_and_stem_audio_flags(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(include_audio=False, include_stem_audio=False),
        now="2026-05-06T00:00:00Z",
    )

    assert not (project_dir / "final-export" / "song.wav").exists()
    assert any(file["kind"] == "audio" and file["skipped"] == "disabled" for file in manifest["files"])
    assert any(file["kind"] == "stem_audio" and file["skipped"] == "disabled" for file in manifest["files"])
    assert not (project_dir / "final-export" / "stems" / "audio").exists()


def test_final_export_blocks_failed_gate_unless_forced(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    failed = evaluate_quality_gate(
        run_dir,
        QualityGateConfig(min_overall=100, min_structure=100, min_melody=100, min_harmony=100, min_arrangement=100),
        now="2026-05-06T00:00:00Z",
    )

    with pytest.raises(FinalExportError, match="Quality gate failed"):
        build_final_export_bundle(
            project=Project(),
            version=Version(),
            project_dir=project_dir,
            run_dir=run_dir,
            gate=failed,
            options=FinalExportOptions(),
            now="2026-05-06T00:00:00Z",
        )

    forced = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=failed,
        options=FinalExportOptions(force=True),
        now="2026-05-06T00:00:00Z",
    )

    assert forced["quality_gate"]["status"] == "failed"
    assert (project_dir / "final-export" / "song-plan.json").exists()


def test_final_export_rejects_missing_required_files_before_replacing_existing_bundle(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    existing = project_dir / "final-export" / "manifest.json"
    write_json(existing, {"old": True})
    (run_dir / "renders" / "song.mid").unlink()

    with pytest.raises(FinalExportError, match="song.mid"):
        build_final_export_bundle(
            project=Project(),
            version=Version(),
            project_dir=project_dir,
            run_dir=run_dir,
            gate=passed_gate(run_dir),
            options=FinalExportOptions(),
            now="2026-05-06T00:00:00Z",
        )

    assert read_json(existing)["old"] is True


def test_final_export_skips_polluted_stem_manifest_paths(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    write_json(run_dir / "data" / "provider-snapshot.json", {"api_key_masked": "sk-...cret"})
    manifest = read_stem_manifest(run_dir)
    assert manifest is not None
    data = manifest.to_dict()
    data["stems"][0]["midi_path"] = "data/provider-snapshot.json"
    data["stems"][0]["audio_path"] = "data/provider-snapshot.json"
    write_json(run_dir / "stems" / "manifest.json", data)

    exported = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
    )

    stem_manifest = next(file for file in exported["files"] if file["kind"] == "stem_manifest")
    assert stem_manifest["exists"] is False
    assert stem_manifest["skipped"] == "unsafe_path"
    assert any(file["kind"] == "stem_midi" and file["skipped"] == "unsafe_path" for file in exported["files"])
    assert not (project_dir / "final-export" / "stems" / "manifest.json").exists()
    assert not (project_dir / "final-export" / "data" / "provider-snapshot.json").exists()
