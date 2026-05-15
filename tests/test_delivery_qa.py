from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from song_agent.agent.pipeline import deterministic_compose
from song_agent.delivery_qa import (
    build_delivery_qa_report,
    build_delivery_signoff_record,
    delivery_qa_allows_signoff,
    delivery_qa_summary,
    delivery_signoff_summary,
    mark_delivery_qa_stale,
)
from song_agent.final_export import FinalExportOptions, build_final_export_bundle, build_final_export_zip
from song_agent.project_quality import QualityGateConfig, evaluate_quality_gate
from song_agent.projectio import read_json, write_json
from song_agent.projects import ProjectDocument, ProjectState, ProjectVersion
from song_agent.renderers.midi import render_midi
from song_agent.schemas.song import SongRequest
from song_agent.stems import render_stem_midis


@dataclass
class Project:
    project_id: str = "project-001"
    name: str = "Delivery Project"


@dataclass
class Version:
    version_id: str = "v001"
    name: str = "Final"
    job_id: str = "job-001"
    note: str = ""


def test_delivery_qa_passes_final_export_zip_and_signoff(tmp_path: Path) -> None:
    project_dir, document, manifest = _bundle(tmp_path, with_zip=True)

    report = build_delivery_qa_report(project_id="project-001", project_document=document, project_dir=project_dir, final_export_manifest=manifest, now="2026-05-15T00:00:00+00:00")
    signoff = build_delivery_signoff_record(project_id="project-001", report=report, payload={"notes": r"accepted C:\Users\demo api_key=sk-secret-value"}, now="2026-05-15T00:01:00+00:00")
    serialized = json.dumps({"report": report, "signoff": signoff}, ensure_ascii=False)

    assert report["status"] in {"passed", "warning"}
    assert report["handoff_allowed"] is True
    assert delivery_qa_allows_signoff(report) is True
    assert report["zip"]["matches_manifest"] is True
    assert report["artifact_integrity"]["checked_count"] >= 4
    assert any(file["path"] == "song.mid" for file in report["artifact_integrity"]["files"])
    assert delivery_qa_summary(report)["final_version_id"] == "v001"
    assert delivery_signoff_summary(signoff)["status"] == "signed"
    assert signoff["final_version_id"] == "v001"
    assert "sk-secret-value" not in serialized
    assert "C:\\Users" not in serialized


def test_delivery_qa_blocks_missing_zip(tmp_path: Path) -> None:
    project_dir, document, manifest = _bundle(tmp_path, with_zip=False)

    report = build_delivery_qa_report(project_id="project-001", project_document=document, project_dir=project_dir, final_export_manifest=manifest)
    zip_check = _check(report, "zip_exists")

    assert report["status"] == "failed"
    assert report["readiness"] == "needs_zip"
    assert report["handoff_allowed"] is False
    assert zip_check["status"] == "failed"


def test_delivery_qa_blocks_unsafe_manifest_path(tmp_path: Path) -> None:
    project_dir, document, manifest = _bundle(tmp_path, with_zip=False)
    manifest["files"].append({"kind": "midi", "path": "../secret.mid", "exists": True, "required": True})

    report = build_delivery_qa_report(project_id="project-001", project_document=document, project_dir=project_dir, final_export_manifest=manifest)
    unsafe = _check(report, "artifact_path_safe")

    assert report["status"] == "failed"
    assert unsafe["status"] == "failed"


def test_delivery_qa_blocks_missing_core_artifact_even_when_manifest_entry_removed(tmp_path: Path) -> None:
    project_dir, document, manifest = _bundle(tmp_path, with_zip=True)
    export_dir = project_dir / "final-export"
    (export_dir / "song.mid").unlink()
    manifest["files"] = [file for file in manifest["files"] if file.get("path") != "song.mid"]
    write_json(export_dir / "manifest.json", manifest)
    build_final_export_zip(project_dir, now="2026-05-15T00:02:00+00:00")
    manifest = read_json(export_dir / "manifest.json")

    report = build_delivery_qa_report(project_id="project-001", project_document=document, project_dir=project_dir, final_export_manifest=manifest)
    required = _check(report, "required_artifacts_exist")
    midi = next(file for file in report["artifact_integrity"]["files"] if file["path"] == "song.mid")

    assert report["status"] == "failed"
    assert report["handoff_allowed"] is False
    assert required["status"] == "failed"
    assert midi["kind"] == "midi"
    assert midi["required"] is True
    assert midi["exists"] is False


def test_delivery_qa_blocks_missing_required_stem_midi_even_when_manifest_entry_removed(tmp_path: Path) -> None:
    project_dir, document, manifest = _bundle(tmp_path, with_zip=True, require_stems=True)
    export_dir = project_dir / "final-export"
    stem_path = next(file["path"] for file in manifest["files"] if file.get("kind") == "stem_midi" and file.get("exists"))
    (export_dir / stem_path).unlink()
    manifest["files"] = [file for file in manifest["files"] if file.get("path") != stem_path]
    write_json(export_dir / "manifest.json", manifest)
    build_final_export_zip(project_dir, now="2026-05-15T00:02:00+00:00")
    manifest = read_json(export_dir / "manifest.json")

    report = build_delivery_qa_report(project_id="project-001", project_document=document, project_dir=project_dir, final_export_manifest=manifest)
    required = _check(report, "required_artifacts_exist")
    stem = next(file for file in report["artifact_integrity"]["files"] if file["path"] == stem_path)

    assert report["status"] == "failed"
    assert required["status"] == "failed"
    assert report["quality_gate"]["require_stems"] is True
    assert stem["kind"] == "stem_midi"
    assert stem["required"] is True
    assert stem["exists"] is False


def test_delivery_qa_scans_raw_manifest_before_sanitizing_zip_path(tmp_path: Path) -> None:
    project_dir, document, manifest = _bundle(tmp_path, with_zip=True)
    manifest["zip"]["path"] = r"C:\Users\demo\Documents\musicforge\final-export.zip"
    write_json(project_dir / "final-export" / "manifest.json", manifest)

    report = build_delivery_qa_report(project_id="project-001", project_document=document, project_dir=project_dir, final_export_manifest=manifest)
    redaction = _check(report, "redaction_scan")
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["status"] == "failed"
    assert redaction["status"] == "failed"
    assert "C:\\Users" not in serialized


def test_delivery_qa_blocks_zip_entry_mismatch(tmp_path: Path) -> None:
    project_dir, document, manifest = _bundle(tmp_path, with_zip=True)
    with zipfile.ZipFile(project_dir / "final-export.zip", "a") as archive:
        archive.writestr("extra.txt", "not in manifest")

    report = build_delivery_qa_report(project_id="project-001", project_document=document, project_dir=project_dir, final_export_manifest=manifest)
    zip_check = _check(report, "zip_manifest_match")

    assert report["status"] == "failed"
    assert zip_check["status"] == "failed"
    assert report["zip"]["extra_entry_count"] == 1


def test_delivery_signoff_force_requires_reason_and_stale_disallows_normal() -> None:
    report = mark_delivery_qa_stale({"status": "passed", "handoff_allowed": True, "source_hash": "old"})

    assert delivery_qa_allows_signoff(report) is False
    with pytest.raises(ValueError, match="override_reason"):
        build_delivery_signoff_record(project_id="project-001", report=report, payload={"force": True})
    forced = build_delivery_signoff_record(project_id="project-001", report=report, payload={"force": True, "override_reason": "accepted manually"})
    assert delivery_signoff_summary(forced)["status"] == "force_signed"


def _bundle(tmp_path: Path, *, with_zip: bool, require_stems: bool = False) -> tuple[Path, ProjectDocument, dict[str, Any]]:
    project_dir = tmp_path / ".musicforge" / "projects" / "project-001"
    run_dir = tmp_path / "runs" / "job-001"
    plan = deterministic_compose(SongRequest(title="Delivery Song", language="English", style="synth pop", theme="handoff"))
    write_json(run_dir / "data" / "song-plan.json", plan.to_dict())
    write_json(run_dir / "data" / "run-summary.json", {"title": plan.title})
    write_json(run_dir / "data" / "validator-report.json", {"status": "passed"})
    render_midi(plan, run_dir / "renders" / "song.mid")
    (run_dir / "renders" / "song.wav").write_bytes(b"RIFFdeliveryWAVE")
    if require_stems:
        render_stem_midis(plan, run_dir, "job-001", now="2026-05-15T00:00:00+00:00")
    gate = evaluate_quality_gate(run_dir, QualityGateConfig(require_stems=require_stems), now="2026-05-15T00:00:00+00:00")
    manifest = build_final_export_bundle(
        project=Project(),
        version=Version(),
        project_dir=project_dir,
        run_dir=run_dir,
        gate=gate,
        options=FinalExportOptions(include_stems=require_stems, include_stem_audio=False),
        now="2026-05-15T00:00:00+00:00",
        project_export={"project": {"project_id": "project-001"}},
    )
    if with_zip:
        build_final_export_zip(project_dir, now="2026-05-15T00:01:00+00:00")
        manifest = read_json(project_dir / "final-export" / "manifest.json")
    document = ProjectDocument(
        state=ProjectState(project_id="project-001", name="Delivery Project", final_version_id="v001", selected_version_id="v001", latest_version_id="v001", version_count=1),
        versions=[
            ProjectVersion(
                version_id="v001",
                project_id="project-001",
                index=1,
                name="Final",
                job_id="job-001",
                output_dir=str(run_dir),
                status="completed",
                created_at="2026-05-15T00:00:00+00:00",
                updated_at="2026-05-15T00:00:00+00:00",
                quality_score=90,
                quality_gate_status=gate.status,
                quality_gate_score=gate.score,
            )
        ],
    )
    return project_dir, document, manifest


def _check(report: dict[str, Any], check_id: str) -> dict[str, Any]:
    return next(check for check in report["checks"] if check["check_id"] == check_id)
