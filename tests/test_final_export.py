from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.final_export import (
    clear_final_export_zip,
    FinalExportError,
    FinalExportOptions,
    build_final_export_zip,
    build_final_export_bundle,
    read_final_export_manifest,
)
from song_agent.project_quality import QualityGateConfig, evaluate_quality_gate
from song_agent.projectio import read_json, write_json
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import SongRequest
from song_agent.stems import read_stem_manifest, render_stem_midis
import zipfile


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


def test_final_export_includes_sanitized_asset_refs(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    write_json(
        run_dir / "data" / "asset-refs.json",
        {
            "schema_version": 1,
            "asset_refs": [
                {
                    "asset_id": "asset-001",
                    "asset_type": "chord_progression",
                    "name": "Good Chords",
                    "role": "chord_reference",
                    "strength": 0.9,
                    "content_summary": {"chord_count": 4},
                    "source": {"project_id": "source", "version_id": "v003"},
                }
            ],
        },
    )

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
        project_export={
            "project": {"project_id": "export-project"},
            "asset_refs": [
                {
                    "asset_id": "asset-001",
                    "asset_type": "chord_progression",
                    "name": "Good Chords",
                    "roles": ["chord_reference"],
                    "used_by_versions": ["v001"],
                    "used_by_candidate_groups": ["cg-001"],
                    "content_summary": {"chord_count": 4},
                    "source": {"project_id": "source", "version_id": "v003"},
                }
            ],
        },
    )

    asset_path = project_dir / "final-export" / "assets" / "asset-001.json"
    assert asset_path.exists()
    asset_summary = read_json(asset_path)
    assert manifest["asset_refs"][0]["asset_id"] == "asset-001"
    assert manifest["asset_refs"][0]["used_by_versions"] == ["v001"]
    assert asset_summary["content_summary"] == {"chord_count": 4}
    serialized = str(manifest) + asset_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in serialized
    assert "provider.json" not in serialized


def test_final_export_manifest_includes_context_pack_summary(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    write_json(
        run_dir / "data" / "context-pack.json",
        {
            "schema_version": 1,
            "pack_id": "pack-001",
            "name": "Final Context",
            "query": {"text": "Bearer secret-token D:\\Music\\seed.mid"},
            "asset_refs": [{"asset_id": "asset-001"}],
            "reference_refs": [{"reference_id": "ref-001"}],
        },
    )

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
    serialized = json.dumps(manifest, ensure_ascii=False)

    assert manifest["context_pack"]["pack_id"] == "pack-001"
    assert manifest["context_pack"]["asset_count"] == 1
    assert "secret-token" not in serialized
    assert "D:\\Music" not in serialized


def test_final_export_review_metrics_uses_latest_sprint_summary(tmp_path: Path) -> None:
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
        project_export={
            "project": {"project_id": "export-project"},
            "review_metrics_summary": {
                "latest_sprint_id": "sprint-002",
                "latest_readiness": "ready_to_close",
                "sprint_count": 2,
                "active_sprint_count": 1,
                "total_provider_tokens": 77,
                "total_candidate_count": 9,
                "total_applied_candidate_count": 2,
            },
            "review_sprints": [
                {
                    "sprint_id": "sprint-001",
                    "metrics_summary": {
                        "sprint_id": "sprint-001",
                        "readiness": "needs_review",
                        "completion_rate": 0.1,
                        "quality_delta": -2,
                        "warnings": ["old sprint warning"],
                    },
                },
                {
                    "sprint_id": "sprint-002",
                    "metrics_summary": {
                        "sprint_id": "sprint-002",
                        "readiness": "ready_to_close",
                        "completion_rate": 1.0,
                        "quality_delta": 5,
                        "warnings": ["latest sprint warning"],
                    },
                },
            ],
        },
    )

    review_metrics = manifest["review_metrics"]
    assert review_metrics["latest_sprint_id"] == "sprint-002"
    assert review_metrics["latest_readiness"] == "ready_to_close"
    assert review_metrics["completion_rate"] == 1.0
    assert review_metrics["quality_delta"] == 5
    assert review_metrics["warnings"] == ["latest sprint warning"]


def test_final_export_review_judge_uses_latest_sprint_from_metrics_summary(tmp_path: Path) -> None:
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
        project_export={
            "project": {"project_id": "export-project"},
            "review_metrics_summary": {"latest_sprint_id": "sprint-002"},
            "review_sprints": [
                {
                    "sprint_id": "sprint-001",
                    "judge_summary": {
                        "sprint_id": "sprint-001",
                        "judged_task_count": 1,
                        "stale_judge_count": 0,
                        "judge_provider_tokens": 100,
                        "high_risk_candidate_count": 0,
                    },
                },
                {
                    "sprint_id": "sprint-002",
                    "judge_summary": {
                        "sprint_id": "sprint-002",
                        "judged_task_count": 2,
                        "stale_judge_count": 1,
                        "judge_provider_tokens": 200,
                        "high_risk_candidate_count": 1,
                    },
                },
            ],
        },
    )

    review_judge = manifest["review_judge"]
    assert review_judge["latest_sprint_id"] == "sprint-002"
    assert review_judge["judged_task_count"] == 3
    assert review_judge["stale_judge_count"] == 1
    assert review_judge["judge_provider_tokens"] == 300
    assert review_judge["high_risk_candidate_count"] == 1


def test_final_export_review_closeout_uses_latest_sprint_from_metrics_summary(tmp_path: Path) -> None:
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
        project_export={
            "project": {"project_id": "export-project"},
            "review_metrics_summary": {"latest_sprint_id": "sprint-002"},
            "review_sprints": [
                {
                    "sprint_id": "sprint-001",
                    "status": "closed",
                    "closeout_summary": {"status": "failed", "readiness": "blocked", "blocker_count": 3, "warning_count": 1, "recommended_final_version_id": "v001"},
                    "signoff_summary": {"status": "signed", "forced": True, "selected_version_id": "v001"},
                },
                {
                    "sprint_id": "sprint-002",
                    "status": "closed",
                    "closeout_summary": {"status": "passed", "readiness": "ready_to_close", "blocker_count": 0, "warning_count": 2, "recommended_final_version_id": "v004"},
                    "signoff_summary": {"status": "signed", "forced": False, "selected_version_id": "v004"},
                },
            ],
        },
    )

    closeout = manifest["review_sprint_closeout"]
    assert closeout["latest_sprint_id"] == "sprint-002"
    assert closeout["latest_closeout_status"] == "passed"
    assert closeout["latest_closeout_readiness"] == "ready_to_close"
    assert closeout["blocker_count"] == 0
    assert closeout["warning_count"] == 2
    assert closeout["selected_version_id"] == "v004"
    assert closeout["forced_close_count"] == 1


def test_final_export_manifest_includes_delivery_summaries(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-15T00:00:00Z",
        project_export={
            "project": {"project_id": "export-project"},
            "delivery_qa_summary": {
                "status": "passed",
                "readiness": "ready_to_handoff",
                "handoff_allowed": True,
                "artifact_count": 9,
                "blocker_count": 0,
                "warning_count": 1,
                "final_version_id": "v001",
                "zip_sha256": "abc123",
                "zip_matches_manifest": True,
            },
            "delivery_signoff_summary": {
                "status": "signed",
                "signed_at": "2026-05-15T00:00:00+00:00",
                "signed_by": "local-user",
                "forced": False,
                "delivery_qa_status": "passed",
                "final_version_id": "v001",
                "zip_sha256": "abc123",
            },
        },
    )

    assert manifest["delivery_qa"]["status"] == "passed"
    assert manifest["delivery_qa"]["handoff_allowed"] is True
    assert manifest["delivery_qa"]["zip_sha256"] == "abc123"
    assert manifest["delivery_signoff"]["status"] == "signed"
    assert manifest["delivery_signoff"]["final_version_id"] == "v001"


def test_final_export_redacts_polluted_asset_ref_metadata(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
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
                        "path": str(tmp_path / "private.mid"),
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

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
    )

    asset_path = project_dir / "final-export" / "assets" / "asset-001.json"
    serialized = json.dumps(manifest["asset_refs"], ensure_ascii=False) + asset_path.read_text(encoding="utf-8")
    assert "note_count" in serialized
    assert "safe" in serialized
    assert "version_id" in serialized
    assert str(tmp_path) not in serialized
    assert "sk-polluted-secret" not in serialized
    assert "api_key" not in serialized
    assert "local_path" not in serialized
    assert "raw_provider_response" not in serialized
    assert "secret" not in serialized
    assert '"path"' not in serialized


def test_final_export_can_disable_asset_refs(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    write_json(run_dir / "data" / "asset-refs.json", {"schema_version": 1, "asset_refs": [{"asset_id": "asset-001"}]})

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(include_asset_refs=False),
        now="2026-05-06T00:00:00Z",
    )

    assert manifest["asset_refs"] == []
    assert not (project_dir / "final-export" / "assets").exists()
    assert any(file["kind"] == "asset_refs" and file["skipped"] == "disabled" for file in manifest["files"])


def test_final_export_includes_sanitized_reference_refs_without_original_files(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
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
                        "license_note": "api_key=sk-polluted-secret D:\\Music\\private\\reference.wav",
                        "path": str(tmp_path / "reference.wav"),
                        "nested": {"api_key": "sk-polluted-secret", "safe": "ok"},
                    },
                    "analysis_summary": {
                        "status": "completed",
                        "summary": {"duration_beats": 8, "preview_path": str(tmp_path / "preview.mid")},
                        "slice_count": 1,
                    },
                }
            ],
        },
    )

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-08T00:00:00Z",
        project_export={
            "project": {"project_id": "export-project"},
            "reference_refs": [
                {
                    "reference_id": "ref-001",
                    "reference_type": "style_note",
                    "title": "Style Seed",
                    "used_by_versions": ["v001"],
                    "metadata_summary": {"text_excerpt": "Use a bright hook from \\\\server\\share\\client\\ref.wav."},
                    "analysis_summary": {"status": "completed", "summary": {"note_count": 4}, "slice_count": 1},
                }
            ],
        },
    )

    ref_path = project_dir / "final-export" / "references" / "ref-001.json"
    assert ref_path.exists()
    assert manifest["reference_refs"][0]["reference_id"] == "ref-001"
    assert manifest["reference_refs"][0]["used_by_versions"] == ["v001"]
    assert manifest["reference_refs"][0]["analysis_summary"]["slice_count"] == 1
    serialized = json.dumps(manifest["reference_refs"], ensure_ascii=False) + ref_path.read_text(encoding="utf-8")
    assert "text_excerpt" in serialized
    assert "safe" in serialized
    assert str(tmp_path) not in serialized
    assert "D:\\Music\\private" not in serialized
    assert "\\\\server\\share" not in serialized
    assert "sk-polluted-secret" not in serialized
    assert "api_key" not in serialized
    assert '"path"' not in serialized
    assert not any(file["path"].endswith(".wav") and file["path"].startswith("references/") for file in manifest["files"])


def test_final_export_can_disable_reference_refs(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    write_json(run_dir / "data" / "reference-refs.json", {"schema_version": 1, "reference_refs": [{"reference_id": "ref-001"}]})

    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(include_reference_refs=False),
        now="2026-05-08T00:00:00Z",
    )

    assert manifest["reference_refs"] == []
    assert not (project_dir / "final-export" / "references").exists()
    assert any(file["kind"] == "reference_refs" and file["skipped"] == "disabled" for file in manifest["files"])


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


def test_final_export_zip_contains_only_safe_relative_entries(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
        project_export={"project": {"project_id": "export-project"}},
    )

    zip_info = build_final_export_zip(project_dir, now="2026-05-06T00:00:00Z")

    zip_path = project_dir / "final-export.zip"
    assert zip_info["entry_count"] > 0
    assert zip_info["sha256"]
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    assert "manifest.json" in names
    assert "README.txt" in names
    assert "song.mid" in names
    assert all(not name.startswith(("/", "\\")) for name in names)
    assert all(".." not in name.split("/") for name in names)
    assert ".musicforge/provider.json" not in names
    assert read_final_export_manifest(project_dir)["zip"]["entry_count"] == zip_info["entry_count"]


def test_final_export_zip_metadata_never_writes_absolute_path(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
        project_export={"project": {"project_id": "export-project"}},
    )

    build_final_export_zip(project_dir, now="2026-05-06T00:00:00Z")
    zip_info = build_final_export_zip(project_dir, now="2026-05-06T00:01:00Z")
    disk_manifest = read_final_export_manifest(project_dir)
    with zipfile.ZipFile(project_dir / "final-export.zip") as archive:
        zipped_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    serialized_zip_metadata = json.dumps({"zip_info": zip_info, "disk": disk_manifest["zip"], "zipped": zipped_manifest["zip"]}, ensure_ascii=False)

    assert "path" not in zip_info
    assert "path" not in disk_manifest["zip"]
    assert "path" not in zipped_manifest["zip"]
    assert str(project_dir) not in serialized_zip_metadata
    assert str(project_dir).replace("\\", "/") not in serialized_zip_metadata


def test_final_export_zip_requires_existing_export_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Final export"):
        build_final_export_zip(tmp_path / ".musicforge" / "projects" / "missing", now="2026-05-06T00:00:00Z")


def test_final_export_bundle_clears_stale_zip_and_manifest_zip_info(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    run_dir, _plan = make_run(tmp_path)
    build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T00:00:00Z",
    )
    zip_info = build_final_export_zip(project_dir, now="2026-05-06T00:00:00Z")
    assert zip_info["entry_count"] > 0
    assert (project_dir / "final-export.zip").exists()

    build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=passed_gate(run_dir),
        options=FinalExportOptions(),
        now="2026-05-06T01:00:00Z",
    )

    assert not (project_dir / "final-export.zip").exists()
    assert "zip" not in read_final_export_manifest(project_dir)


def test_clear_final_export_zip_refuses_symlink(tmp_path: Path) -> None:
    project_dir = tmp_path / ".musicforge" / "projects" / "export-project"
    project_dir.mkdir(parents=True)
    target = tmp_path / "outside.zip"
    target.write_bytes(b"PK")
    zip_path = project_dir / "final-export.zip"
    try:
        zip_path.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not available on this platform")

    with pytest.raises(FinalExportError, match="symlinked"):
        clear_final_export_zip(project_dir)
